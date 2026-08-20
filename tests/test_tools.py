"""Unit tests for tool logic - no live model calls, pure function tests."""
from src.tools.document_tools import extract_fields, summarize_document
from src.tools.scoring_tools import apply_rule_score
from src.tools.validation_tools import check_completeness, flag_authenticity_risks
from src.tools.workflow_tools import get_audit_trail, record_review_decision, route_to_reviewer


def test_extract_fields_finds_amounts_and_dates():
    text = "Grant of Rs. 50,000 approved on 12/05/2024 for the project."
    result = extract_fields(text)
    assert "50,000" in result["amounts_found"]
    assert "12/05/2024" in result["dates_found"]


def test_summarize_document_limits_sentences():
    text = "One. Two. Three. Four."
    summary = summarize_document(text, max_sentences=2)
    assert summary == "One. Two."


def test_check_completeness_flags_missing_fields():
    result = check_completeness({"name": "Acme"}, ["name", "amount"])
    assert result["is_complete"] is False
    assert result["missing_fields"] == ["amount"]


def test_flag_authenticity_risks_detects_duplicates():
    result = flag_authenticity_risks({"amounts_found": ["100", "100"]})
    assert "duplicate_amount_values" in result["risk_flags"]
    assert result["requires_human_review"] is True


def test_apply_rule_score_penalizes_risk():
    result = apply_rule_score({"is_complete": True, "requires_human_review": True})
    assert result["score"] < 0.6
    assert "explanation" in result


def test_route_to_reviewer_requires_pool():
    result = route_to_reviewer(score=0.9, reviewer_pool=["alice", "bob"])
    assert result["assigned_reviewer"] in {"alice", "bob"}


def test_record_and_get_audit_trail_roundtrip():
    record_review_decision("case-1", "alice", "approved", "meets criteria")
    entries = get_audit_trail("case-1")
    assert len(entries) == 1
    assert entries[0]["decision"] == "approved"
