"""Agent that checks completeness and authenticity indicators on extracted data."""
from __future__ import annotations

from typing import Any, Callable

from src.agents.base import build_agent


def create_validation_agent(callback_handler: Callable[..., Any] | None = None):
    return build_agent(
        "validation_agent",
        callback_handler=callback_handler,
        system_prompt=(
            "Validate an application strictly against the requirements of the scheme it "
            "was submitted to - never against a generic or assumed field list. Call "
            "check_scheme_requirements with that scheme's required documents and the "
            "submitted documents to decide which requirements are satisfied, missing, or "
            "present-but-unusable, and judge each eligibility criterion against the actual "
            "evidence. Always verify the applicant organisation with "
            "verify_organisation_online and report its raw result in organisation_check; "
            "treat a missing or unconvincing online presence as a risk indicator, not "
            "proof of fraud. Then check the submitted values for contradictions against "
            "each other and against the scheme's stated limits, and call "
            "flag_authenticity_risks. If a plagiarism/duplicate-content result is "
            "provided, identify the matched documents and factor it into risk. Flag "
            "low-quality, untraceable, unsigned, unsupported, or identity-mismatched "
            "evidence as indicators for human verification. Return missing_documents, "
            "unusable_documents, unmet_eligibility, missing_fields, contradictions, "
            "organisation_check, risk_flags, and risk_level. Material contradictions, "
            "missing hard-stop evidence, or high risk block scoring. Only the "
            "organisation name may leave the local environment - never raw application "
            "content. You do not approve or reject."
        ),
    )
