"""Unit tests for tool logic - no live model calls, pure function tests."""
from src.tools import verification_tools
from src.tools.document_tools import extract_fields, summarize_document
from src.tools.scoring_tools import apply_rule_score, apply_scheme_score
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


def test_verify_organisation_online_skips_without_api_key(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.setattr(verification_tools, "_client", None)
    result = verification_tools.verify_organisation_online("Acme Renewables Pvt Ltd")
    assert result["checked"] is False


def test_verify_organisation_online_requires_a_name():
    result = verification_tools.verify_organisation_online("")
    assert result["checked"] is False


def test_verify_organisation_online_returns_matches(monkeypatch):
    class _FakeResult:
        def __init__(self, title, url, highlights):
            self.title = title
            self.url = url
            self.highlights = highlights

    class _FakeResponse:
        def __init__(self):
            self.results = [_FakeResult("Acme Renewables", "https://acme.example", ["Acme Renewables is..."])]

    class _FakeClient:
        def search(self, *args, **kwargs):
            return _FakeResponse()

    monkeypatch.setattr(verification_tools, "_get_client", lambda: _FakeClient())
    result = verification_tools.verify_organisation_online("Acme Renewables")
    assert result["checked"] is True
    assert result["has_online_presence"] is True
    assert result["match_count"] == 1
    assert result["matches"][0]["url"] == "https://acme.example"


def test_apply_rule_score_penalizes_risk():
    result = apply_rule_score({"is_complete": True, "requires_human_review": True})
    assert result["score"] < 0.6
    assert "explanation" in result


def test_apply_scheme_score_computes_weighted_breakdown():
    criteria = [
        {"name": "Eligibility fit", "weight": 60.0, "rationale": "Matches scheme eligibility."},
        {"name": "Completeness", "weight": 40.0, "rationale": "All required documents present."},
    ]
    result = apply_scheme_score(criteria, {"Eligibility fit": 100.0, "Completeness": 50.0})
    assert result["score"] == 80.0
    breakdown = {c["criterion"]: c for c in result["explanation"]["criteria"]}
    assert breakdown["Eligibility fit"]["weighted_contribution"] == 60.0
    assert breakdown["Completeness"]["weighted_contribution"] == 20.0


def test_apply_scheme_score_clamps_and_defaults_missing_awards():
    criteria = [{"name": "Risk controls", "weight": 100.0, "rationale": "x"}]
    result = apply_scheme_score(criteria, {"Risk controls": 150.0})
    assert result["score"] == 100.0

    result_missing = apply_scheme_score(criteria, {})
    assert result_missing["score"] == 0.0


def test_route_to_reviewer_requires_pool():
    result = route_to_reviewer(score=0.9, reviewer_pool=["alice", "bob"])
    assert result["assigned_reviewer"] in {"alice", "bob"}


def test_record_and_get_audit_trail_roundtrip():
    record_review_decision("case-1", "alice", "approved", "meets criteria")
    entries = get_audit_trail("case-1")
    assert len(entries) == 1
    assert entries[0]["decision"] == "approved"
