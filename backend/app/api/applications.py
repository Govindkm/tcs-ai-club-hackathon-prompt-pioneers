"""Application submission and staged human-in-the-loop analysis workflow.

Flow: submit -> background ingestion (extract text, index in ChromaDB, run a
plagiarism/duplicate-content check) -> all admins are notified -> any admin
assigns themself to the case, which kicks off extraction + validation ->
the assigned admin reviews the validation result and either resumes it with
free-text feedback (looping validation again) or marks it complete, which
kicks off scoring -> once scoring finishes, any admin can approve the score;
once at least 2 distinct admins approve, the submission's timeline is marked
complete. A human reviewer decision (see reviews.py) is still the only thing
that can finalize status to approved/rejected.

Every stage runs as a background job (dedicated daemon thread, not FastAPI
BackgroundTasks - see _start_background_job) so slow ingestion/OCR/LLM calls
never starve unrelated requests. submission.timeline_stage drives the color
coded submission-timeline UI (green=done, blinking green=running now,
orange=not started yet, red=failed).
"""
from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import threading
from typing import Callable

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response, StreamingResponse

from backend.app.schemas import (
    AnalysisEventOut,
    AnalysisStatusOut,
    AnalyzeRequest,
    ReevaluationRequestIn,
    ScoreApprovalOut,
    SubmissionOut,
    ValidationFeedbackRequest,
)
from backend.app.security import get_current_user, require_role
from src.agents.orchestrator import create_orchestrator
from src.db import repository as db
from src.ingestion.document_reader import combine_document_text, extract_documents
from src.ingestion.storage import load_uploaded_files, save_uploaded_files

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/applications", tags=["applications"])

_REQUIRED_FIELDS = ["amounts_found", "dates_found"]

# timeline_stage values - drive the color-coded submission timeline in the UI.
STAGE_INGESTING = "ingesting"
STAGE_AWAITING_ADMIN_REVIEW = "awaiting_admin_review"
STAGE_EXTRACTION_RUNNING = "extraction_running"
STAGE_VALIDATION_RUNNING = "validation_running"
STAGE_AWAITING_ADMIN_VALIDATION = "awaiting_admin_validation"
STAGE_SCORING_RUNNING = "scoring_running"
STAGE_AWAITING_SCORE_APPROVAL = "awaiting_score_approval"
STAGE_COMPLETED = "completed"

_SCORE_APPROVALS_REQUIRED = 2


def _to_out(sub: dict) -> SubmissionOut:
    return SubmissionOut(**sub)


def _check_ownership(submission: dict, current_user: dict) -> None:
    if current_user["role"] != "admin" and submission["user_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your application")


def _check_assigned_admin(submission: dict, current_user: dict) -> None:
    """Only the admin who claimed this case can control its analysis (feedback/resume/complete)."""
    if submission.get("assigned_admin_id") != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned admin can control this submission's analysis.",
        )


def _notify_admins(title: str, message: str) -> None:
    db.create_notification(title, message, created_by=None)


def _start_background_job(target: Callable, *args) -> None:
    """Run a job in a dedicated daemon thread - see module docstring for why not BackgroundTasks."""
    threading.Thread(target=target, args=args, daemon=True).start()


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


def _make_sink(submission_id: int) -> Callable[[str, str, str], None]:
    def sink(stage: str, event_type: str, content: str) -> None:
        db.append_analysis_event(submission_id, stage, event_type, content)
        if event_type == "stage_start":
            db.set_analysis_status(submission_id, "running", stage=stage)
            logger.info("Submission %s: stage '%s' started.", submission_id, stage)
        elif event_type == "stage_complete":
            logger.info("Submission %s: stage '%s' complete.", submission_id, stage)

    return sink


def run_ingestion_job(submission_id: int, files: list[tuple[str, bytes]], pasted_text: str) -> None:
    """Stage 1 (automatic, or re-run via restart_pipeline): extract text, index it in
    ChromaDB, and check for plagiarized/duplicate content - then notify admins that
    it's ready for review."""
    logger.info("Ingestion job started for submission %s.", submission_id)
    db.set_timeline_stage(submission_id, STAGE_INGESTING)
    db.set_analysis_status(submission_id, "running", stage="ingestion")
    sink = _make_sink(submission_id)
    try:
        submission = db.get_submission(submission_id)

        # Persist the raw uploads (idempotent - same content, same paths) + pasted
        # text so this ingestion (including OCR) can be retried later without a
        # re-upload, even for pasted-text-only submissions (empty raw_files list).
        # Stored per-scheme/per-submission so uploads stay organized by scheme too.
        raw_files = save_uploaded_files(submission["scheme_id"], submission_id, files)
        db.save_raw_files(submission_id, raw_files, pasted_text)

        document_text, document_bundle = _ingest_documents(files, pasted_text, sink)
        if not document_text.strip():
            raise ValueError("No extractable document content.")
        db.update_submission_documents(submission_id, document_text, document_bundle)

        scheme = db.get_scheme(submission["scheme_id"])
        pipeline = create_orchestrator(event_sink=sink)
        indexed = pipeline.index_and_check(
            document_bundle, submission["scheme_id"], scheme["name"] if scheme else "", submission_id
        )
        db.save_plagiarism_result(submission_id, indexed["plagiarism"])

        db.set_analysis_status(submission_id, "completed", stage="ingestion_done")
        db.set_timeline_stage(submission_id, STAGE_AWAITING_ADMIN_REVIEW)

        flagged_note = " (potential plagiarism/duplicate content flagged)" if indexed["plagiarism"]["flagged"] else ""
        _notify_admins(
            f"New submission #{submission_id} ready for review",
            f"{submission.get('applicant_name') or 'An applicant'} submitted to "
            f"'{scheme['name'] if scheme else submission['scheme_id']}'{flagged_note}. "
            "Assign yourself to run the AI analysis.",
        )
        logger.info("Ingestion job completed for submission %s.", submission_id)
    except Exception as exc:  # noqa: BLE001 - untrusted uploads + external calls fail in many expected ways
        logger.exception("Ingestion failed for submission %s.", submission_id)
        db.append_analysis_event(submission_id, "ingestion", "error", str(exc))
        db.set_analysis_status(submission_id, "failed", error=str(exc))
        # Leave timeline_stage at STAGE_INGESTING - the UI marks the current stage red
        # on failure and renders every later stage as not-yet-started (orange).


def run_ingestion_retry_job(submission_id: int) -> None:
    """Re-run stage 1 from scratch (re-extraction, incl. OCR) using the originally
    uploaded files reloaded from disk - e.g. after fixing a broken Ollama connection,
    so a stale '[extraction failed: ...]' placeholder isn't baked into the analysis."""
    submission = db.get_submission(submission_id)
    raw_files = submission.get("raw_files") or []
    try:
        files = load_uploaded_files(raw_files) if raw_files else []
    except FileNotFoundError as exc:
        logger.exception("Ingestion retry failed for submission %s: stored upload missing.", submission_id)
        db.append_analysis_event(submission_id, "ingestion", "error", str(exc))
        db.set_analysis_status(submission_id, "failed", error=str(exc))
        return
    run_ingestion_job(submission_id, files, submission.get("pasted_text") or "")


def run_extraction_and_validation_job(submission_id: int, admin_feedback: str = "") -> None:
    """Stage 2 (admin-triggered via /assign): extraction, then validation."""
    logger.info("Extraction+validation job started for submission %s.", submission_id)
    sink = _make_sink(submission_id)
    try:
        db.set_timeline_stage(submission_id, STAGE_EXTRACTION_RUNNING)
        db.set_analysis_status(submission_id, "running", stage="extraction")
        submission = db.get_submission(submission_id)
        pipeline = create_orchestrator(event_sink=sink)
        extraction = pipeline.run_extraction(submission["document_text"], admin_feedback)

        db.set_timeline_stage(submission_id, STAGE_VALIDATION_RUNNING)
        scheme = db.get_scheme(submission["scheme_id"])
        validation = pipeline.run_validation(
            extraction.extracted_fields,
            _REQUIRED_FIELDS,
            admin_feedback,
            plagiarism_summary=submission.get("plagiarism_result"),
            organisation_name=submission.get("applicant_organisation"),
            scoring_pattern=scheme.get("scoring_pattern") if scheme else None,
        )
        db.save_extraction_and_validation(
            submission_id, extraction.extracted_fields, extraction.summary, validation.model_dump()
        )
        db.set_analysis_status(submission_id, "completed", stage="validation_done")
        db.set_timeline_stage(submission_id, STAGE_AWAITING_ADMIN_VALIDATION)
        logger.info("Extraction+validation completed for submission %s.", submission_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Extraction/validation failed for submission %s.", submission_id)
        db.append_analysis_event(submission_id, "validation", "error", str(exc))
        db.set_analysis_status(submission_id, "failed", error=str(exc))
        # timeline_stage stays at whichever of extraction_running/validation_running was active.


def run_validation_feedback_job(submission_id: int, feedback: str) -> None:
    """Assigned admin gave free-text instructions - resume/re-check validation with them."""
    logger.info("Validation feedback loop started for submission %s.", submission_id)
    sink = _make_sink(submission_id)
    try:
        db.set_timeline_stage(submission_id, STAGE_VALIDATION_RUNNING)
        db.set_analysis_status(submission_id, "running", stage="validation")
        submission = db.get_submission(submission_id)
        pipeline = create_orchestrator(event_sink=sink)
        scheme = db.get_scheme(submission["scheme_id"])
        validation = pipeline.run_validation(
            submission.get("extracted_fields") or {},
            _REQUIRED_FIELDS,
            admin_feedback=feedback,
            plagiarism_summary=submission.get("plagiarism_result"),
            organisation_name=submission.get("applicant_organisation"),
            scoring_pattern=scheme.get("scoring_pattern") if scheme else None,
        )
        db.save_validation_result(submission_id, validation.model_dump(), feedback=feedback)
        db.set_analysis_status(submission_id, "completed", stage="validation_done")
        db.set_timeline_stage(submission_id, STAGE_AWAITING_ADMIN_VALIDATION)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Validation feedback loop failed for submission %s.", submission_id)
        db.append_analysis_event(submission_id, "validation", "error", str(exc))
        db.set_analysis_status(submission_id, "failed", error=str(exc))


def run_scoring_job(submission_id: int) -> None:
    """Stage 3 (admin-triggered via /validation/complete): explainable scoring."""
    logger.info("Scoring job started for submission %s.", submission_id)
    sink = _make_sink(submission_id)
    try:
        db.set_timeline_stage(submission_id, STAGE_SCORING_RUNNING)
        db.set_analysis_status(submission_id, "running", stage="scoring")
        submission = db.get_submission(submission_id)
        pipeline = create_orchestrator(event_sink=sink)
        scheme = db.get_scheme(submission["scheme_id"])
        scoring = pipeline.run_scoring(
            submission.get("validation_result") or {}, scoring_pattern=scheme.get("scoring_pattern") if scheme else None
        )
        db.save_scoring_result(submission_id, scoring.score, scoring.explanation)
        db.set_analysis_status(submission_id, "completed", stage="scoring_done")
        db.set_timeline_stage(submission_id, STAGE_AWAITING_SCORE_APPROVAL)
        _notify_admins(
            f"Score ready for submission #{submission_id}",
            f"Advisory score {scoring.score} is ready for review and approval.",
        )
        logger.info("Scoring completed for submission %s (score=%s).", submission_id, scoring.score)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Scoring failed for submission %s.", submission_id)
        db.append_analysis_event(submission_id, "scoring", "error", str(exc))
        db.set_analysis_status(submission_id, "failed", error=str(exc))


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
    _start_background_job(run_ingestion_job, submission_id, file_payloads, pasted_text)
    return _to_out(db.get_submission(submission_id))


@router.post("/{application_id}/assign", response_model=SubmissionOut)
def assign_application(application_id: int, current_user: dict = Depends(require_role("admin"))) -> SubmissionOut:
    """An admin claims a case to run/oversee its AI analysis (extraction + validation)."""
    submission = db.get_submission(application_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if submission["timeline_stage"] == STAGE_INGESTING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Still ingesting/indexing this submission.")
    if not db.assign_admin(application_id, current_user["id"]):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already assigned to another admin.")
    if submission["timeline_stage"] == STAGE_AWAITING_ADMIN_REVIEW:
        _start_background_job(run_extraction_and_validation_job, application_id, "")
    return _to_out(db.get_submission(application_id))


@router.post("/{application_id}/validation/feedback", response_model=SubmissionOut)
def submit_validation_feedback(
    application_id: int, payload: ValidationFeedbackRequest, current_user: dict = Depends(require_role("admin"))
) -> SubmissionOut:
    """Assigned admin gives text instructions to re-check; loops validation again."""
    submission = db.get_submission(application_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    _check_assigned_admin(submission, current_user)
    if submission["timeline_stage"] != STAGE_AWAITING_ADMIN_VALIDATION:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Validation is not awaiting admin input.")
    _start_background_job(run_validation_feedback_job, application_id, payload.feedback)
    return _to_out(db.get_submission(application_id))


@router.post("/{application_id}/validation/complete", response_model=SubmissionOut)
def complete_validation(application_id: int, current_user: dict = Depends(require_role("admin"))) -> SubmissionOut:
    """Assigned admin marks validation complete, advancing the case to scoring."""
    submission = db.get_submission(application_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    _check_assigned_admin(submission, current_user)
    if submission["timeline_stage"] != STAGE_AWAITING_ADMIN_VALIDATION:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Validation is not awaiting admin input.")
    _start_background_job(run_scoring_job, application_id)
    return _to_out(db.get_submission(application_id))


@router.post("/{application_id}/score/approve", response_model=SubmissionOut)
def approve_score(application_id: int, current_user: dict = Depends(require_role("admin"))) -> SubmissionOut:
    """Any admin approves the computed score; once >= 2 distinct admins approve, the
    submission's timeline is marked complete (final approve/reject is still via reviews.py)."""
    submission = db.get_submission(application_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if submission["timeline_stage"] not in (STAGE_AWAITING_SCORE_APPROVAL, STAGE_COMPLETED):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Score is not ready for approval yet.")
    approval_count = db.add_score_approval(application_id, current_user["id"])
    if approval_count >= _SCORE_APPROVALS_REQUIRED:
        db.set_timeline_stage(application_id, STAGE_COMPLETED)
        _notify_admins(
            f"Submission #{application_id} complete",
            f"The score was approved by {approval_count} admins; the submission timeline is now complete.",
        )
    return _to_out(db.get_submission(application_id))


@router.get("/{application_id}/score/approvals", response_model=list[ScoreApprovalOut])
def list_score_approvals(application_id: int, current_user: dict = Depends(get_current_user)) -> list[ScoreApprovalOut]:
    submission = db.get_submission(application_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    _check_ownership(submission, current_user)
    return [ScoreApprovalOut(**a) for a in db.list_score_approvals(application_id)]


@router.post("/{application_id}/restart", response_model=SubmissionOut)
def restart_pipeline(application_id: int, current_user: dict = Depends(require_role("admin"))) -> SubmissionOut:
    """Admin-only: restart the pipeline from whichever stage was in progress when it failed."""
    submission = db.get_submission(application_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if submission["analysis_status"] != "failed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This submission is not currently failed.")

    stage = submission["timeline_stage"]
    if stage == STAGE_INGESTING:
        # Re-runs ingestion from scratch (incl. OCR) using the originally uploaded files
        # reloaded from disk - e.g. after fixing a broken Ollama/model connection.
        _start_background_job(run_ingestion_retry_job, application_id)
    elif stage in (STAGE_EXTRACTION_RUNNING, STAGE_VALIDATION_RUNNING):
        db.assign_admin(application_id, current_user["id"])
        _start_background_job(run_extraction_and_validation_job, application_id, "")
    elif stage == STAGE_SCORING_RUNNING:
        _start_background_job(run_scoring_job, application_id)
    else:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Stage '{stage}' cannot be restarted.")
    return _to_out(db.get_submission(application_id))


@router.post("/{application_id}/request-reevaluation", response_model=SubmissionOut)
def request_reevaluation(
    application_id: int, payload: ReevaluationRequestIn, current_user: dict = Depends(get_current_user)
) -> SubmissionOut:
    """The submitting applicant asks admins to reevaluate with changes/clarifications.
    This only flags the request for admin attention - it does not itself control the
    pipeline (only an assigned/any admin can act via /assign, /validation/*, /restart)."""
    submission = db.get_submission(application_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if current_user["role"] != "applicant" or submission["user_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the submitting applicant can request this.")
    db.request_reevaluation(application_id, payload.details)
    _notify_admins(
        f"Re-evaluation requested for submission #{application_id}",
        f"{submission.get('applicant_name') or 'The applicant'} requested a re-evaluation: {payload.details}",
    )
    return _to_out(db.get_submission(application_id))


@router.post("/{application_id}/analyze", response_model=SubmissionOut)
def analyze_application(
    application_id: int,
    payload: AnalyzeRequest,
    current_user: dict = Depends(require_role("admin")),
) -> SubmissionOut:
    """Legacy/manual retry hook: re-run extraction+validation from scratch (e.g. after
    a transient failure). Only the assigned admin may do this; unassigned cases can be
    claimed via /assign instead."""
    submission = db.get_submission(application_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    if submission["status"] in ("approved", "rejected"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This case has already been finalized.")
    if submission.get("assigned_admin_id") not in (None, current_user["id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned admin can retry this case.")
    db.assign_admin(application_id, current_user["id"])
    if payload.feedback.strip():
        db.append_analysis_event(application_id, "pipeline", "text", f"Admin feedback: {payload.feedback}")
    _start_background_job(run_extraction_and_validation_job, application_id, payload.feedback)
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


@router.get("/{application_id}/files")
def list_submission_files(application_id: int, current_user: dict = Depends(get_current_user)) -> list[dict]:
    """Lightweight manifest (filename/size only, no server paths) so the UI can offer previews."""
    submission = db.get_submission(application_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    _check_ownership(submission, current_user)
    raw_files = submission.get("raw_files") or []
    return [
        {"index": index, "filename": entry["filename"], "size": entry.get("size", 0)}
        for index, entry in enumerate(raw_files)
    ]


@router.get("/{application_id}/files/{file_index}")
def get_submission_file(
    application_id: int, file_index: int, current_user: dict = Depends(get_current_user)
) -> Response:
    """Streams one originally-uploaded raw file back for in-browser preview/download."""
    submission = db.get_submission(application_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    _check_ownership(submission, current_user)
    raw_files = submission.get("raw_files") or []
    if file_index < 0 or file_index >= len(raw_files):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    entry = raw_files[file_index]
    try:
        [(filename, content)] = load_uploaded_files([entry])
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
