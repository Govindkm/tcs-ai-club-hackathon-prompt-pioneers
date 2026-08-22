"""Application submission, agentic analysis, and retrieval endpoints.

Each submission is run through an ingestion -> extraction -> validation ->
scoring pipeline as a background job: the submit/analyze endpoints return
immediately with analysis_status='queued', and the job updates status/stage/
events in the DB as it progresses so clients can poll GET /{id} or
/{id}/status. A human reviewer decision (see reviews.py) is the only thing
that can finalize status. If the job fails at any stage, the submission is
kept (not lost) with analysis_status='failed' and can be retried via
POST /{id}/analyze.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Callable

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from backend.app.schemas import AnalysisEventOut, AnalysisStatusOut, AnalyzeRequest, SubmissionOut
from backend.app.security import get_current_user, require_role
from src.agents.orchestrator import create_orchestrator
from src.db import repository as db
from src.ingestion.document_reader import combine_document_text, extract_documents

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/applications", tags=["applications"])

_REQUIRED_FIELDS = ["amounts_found", "dates_found"]


def _to_out(sub: dict) -> SubmissionOut:
    return SubmissionOut(**sub)


def _check_ownership(submission: dict, current_user: dict) -> None:
    if current_user["role"] != "admin" and submission["user_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your application")


def _ingest_documents(
    files: list[tuple[str, bytes]], pasted_text: str, sink: Callable[[str, str, str], None]
) -> tuple[str, list[dict]]:
    """Extract text from uploads - including any slow vision/OCR calls - entirely off the request path."""
    sink("ingestion", "stage_start", f"Extracting text from {len(files)} file(s).")
    documents = []
    for filename, content in files:
        try:
            documents.extend(extract_documents([(filename, content)]))
        except Exception as exc:  # noqa: BLE001 - untrusted uploads + external OCR calls fail in many ways
            sink("ingestion", "error", f"Failed to extract '{filename}': {exc}")
            documents.append({
                "title": filename,
                "extension": f".{filename.rsplit('.', 1)[-1].lower()}" if "." in filename else "",
                "source_path": filename,
                "metadata": "{}",
                "content": f"[extraction failed: {exc}]",
                "status": "failed",
                "error": str(exc),
            })
    if pasted_text.strip():
        documents.append({
            "title": "pasted-text.txt",
            "extension": ".txt",
            "source_path": "pasted-text.txt",
            "metadata": "{}",
            "content": pasted_text.strip(),
            "status": "extracted",
            "error": None,
        })
    document_text = combine_document_text(documents)
    sink("ingestion", "stage_complete", f"Extracted {len(document_text)} characters of text.")
    return document_text, documents


def run_agentic_analysis_job(
    submission_id: int, files: list[tuple[str, bytes]], pasted_text: str, admin_feedback: str = ""
) -> None:
    """Background job: ingest documents, then run the agentic pipeline, streaming events into the DB."""
    logger.info("Analysis job started for submission %s.", submission_id)
    db.set_analysis_status(submission_id, "running", stage="ingestion")

    def sink(stage: str, event_type: str, content: str) -> None:
        db.append_analysis_event(submission_id, stage, event_type, content)
        if event_type == "stage_start":
            db.set_analysis_status(submission_id, "running", stage=stage)
            logger.info("Submission %s: stage '%s' started.", submission_id, stage)
        elif event_type == "stage_complete":
            logger.info("Submission %s: stage '%s' complete.", submission_id, stage)

    try:
        document_text, document_bundle = _ingest_documents(files, pasted_text, sink)
        if not document_text.strip():
            raise ValueError("No extractable document content.")
        db.update_submission_documents(submission_id, document_text, document_bundle)

        pipeline = create_orchestrator(event_sink=sink)
        result = pipeline.process(
            document_text,
            required_fields=_REQUIRED_FIELDS,
            admin_feedback=admin_feedback,
            document_bundle=document_bundle if files else None,
            scheme_id=db.get_submission(submission_id)["scheme_id"] if files else None,
            scheme_title=db.get_scheme(db.get_submission(submission_id)["scheme_id"])["name"] if files else "",
            submission_id=submission_id if files else None,
        )
        db.save_analysis_result(
            submission_id,
            extracted_fields=result["extraction"].extracted_fields,
            summary=result["extraction"].summary,
            validation_result=result["validation"].model_dump(),
            score=result["scoring"].score,
            score_explanation=result["scoring"].explanation,
        )
        logger.info("Analysis job completed for submission %s (score=%s).", submission_id, result["scoring"].score)
    except Exception as exc:
        # Untrusted file extraction and external model calls fail in many expected
        # ways (bad uploads, network/tunnel timeouts, auth) - don't lose the submission.
        logger.exception("Agentic analysis failed for submission %s.", submission_id)
        db.append_analysis_event(submission_id, "pipeline", "error", str(exc))
        db.set_analysis_status(submission_id, "failed", error=str(exc))


def _start_analysis_job(
    submission_id: int, files: list[tuple[str, bytes]], pasted_text: str, admin_feedback: str = ""
) -> None:
    """Run the analysis job in a dedicated daemon thread.

    Deliberately NOT using FastAPI's BackgroundTasks: those run via the shared
    anyio worker threadpool that every plain `def` route handler also uses, so
    a slow ingestion/LLM call there was starving unrelated requests (e.g. GET
    /notifications) of worker capacity. A dedicated thread fully decouples it.
    """
    threading.Thread(
        target=run_agentic_analysis_job,
        args=(submission_id, files, pasted_text, admin_feedback),
        daemon=True,
    ).start()


@router.post("", response_model=SubmissionOut, status_code=status.HTTP_201_CREATED)
async def submit_application(
    scheme_id: int = Form(...),
    notes: str = Form(""),
    pasted_text: str = Form(""),
    files: list[UploadFile] = File(default_factory=list),
    current_user: dict = Depends(get_current_user),
) -> SubmissionOut:
    if not files and not pasted_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Please upload at least one document or paste some content."
        )

    # Only read raw bytes here (fast) - text/OCR extraction happens in the background job.
    file_payloads = [(upload.filename or "upload", await upload.read()) for upload in files]

    submission_id = db.create_submission(current_user["id"], scheme_id, notes, pasted_text.strip())
    _start_analysis_job(submission_id, file_payloads, pasted_text)
    return _to_out(db.get_submission(submission_id))


@router.post("/{application_id}/analyze", response_model=SubmissionOut)
def analyze_application(
    application_id: int,
    payload: AnalyzeRequest,
    current_user: dict = Depends(get_current_user),
) -> SubmissionOut:
    """(Re)run the agentic analysis in the background - e.g. after a transient model
    failure, or with human-in-the-loop feedback for the agents to incorporate."""
    submission = db.get_submission(application_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    _check_ownership(submission, current_user)
    if submission["status"] in ("approved", "rejected"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This case has already been finalized.")

    db.set_analysis_status(application_id, "queued")
    if payload.feedback.strip():
        db.append_analysis_event(application_id, "pipeline", "text", f"Admin feedback: {payload.feedback}")
    # No raw files stored from the original submission - re-analysis reuses the
    # already-extracted document_text (skips the ingestion/OCR stage).
    _start_analysis_job(application_id, [], submission["document_text"], payload.feedback)
    return _to_out(db.get_submission(application_id))


@router.get("", response_model=list[SubmissionOut])
def list_applications(
    status_filter: str | None = None, current_user: dict = Depends(get_current_user)
) -> list[SubmissionOut]:
    if current_user["role"] == "admin":
        return [_to_out(s) for s in db.list_all_submissions(status_filter)]
    return [_to_out(s) for s in db.list_submissions_for_user(current_user["id"])]


@router.get("/{application_id}", response_model=SubmissionOut)
def get_application(application_id: int, current_user: dict = Depends(get_current_user)) -> SubmissionOut:
    submission = db.get_submission(application_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    _check_ownership(submission, current_user)
    return _to_out(submission)


@router.get("/{application_id}/status", response_model=AnalysisStatusOut)
def get_analysis_status(application_id: int, current_user: dict = Depends(get_current_user)) -> AnalysisStatusOut:
    """Lightweight polling endpoint for the async analysis job's progress."""
    submission = db.get_submission(application_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    _check_ownership(submission, current_user)
    return AnalysisStatusOut(**submission)


@router.get("/{application_id}/events", response_model=list[AnalysisEventOut])
def list_analysis_events(
    application_id: int, current_user: dict = Depends(require_role("admin"))
) -> list[AnalysisEventOut]:
    """The AI's step-by-step reasoning/tool-use/output log for admin review."""
    submission = db.get_submission(application_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return [AnalysisEventOut(**e) for e in db.list_analysis_events(application_id)]


@router.get("/{application_id}/events/stream")
async def stream_analysis_events(application_id: int, current_user: dict = Depends(require_role("admin"))):
    """Server-sent events: live-tails the AI's reasoning/tool-use log as it's produced."""
    submission = db.get_submission(application_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    async def _event_stream():
        last_id = 0
        while True:
            events = db.list_analysis_events(application_id, after_id=last_id)
            for event in events:
                last_id = event["id"]
                yield f"event: {event['event_type']}\ndata: {json.dumps(event)}\n\n"
            current = db.get_submission(application_id)
            if current and current["analysis_status"] in ("completed", "failed") and not events:
                yield "event: end\ndata: {}\n\n"
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(_event_stream(), media_type="text/event-stream")
