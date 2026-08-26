"""Organisation legitimacy check via Exa web search (https://exa.ai).

Helps the validation agent flag submissions from organisations with no
discoverable public/company presence online - one authenticity signal among
several, never a final accept/reject determination.

Data-boundary note: only the organisation name (never document content,
financial figures, or other submission data) is sent to this external API -
consistent with the "no restricted data to public cloud services" rule; the
whole point of this check is to search the public web for that name.
"""
from __future__ import annotations

import os

from strands import tool

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        return None
    from exa_py import Exa

    _client = Exa(api_key=api_key)
    return _client


@tool
def verify_organisation_online(organisation_name: str) -> dict:
    """Search the public web for an applicant organisation to check it has a
    genuine, findable presence (news, official site, registry listing, etc.).

    Args:
        organisation_name: The applicant's organisation name, exactly as submitted.
    """
    if not organisation_name or not organisation_name.strip():
        return {"checked": False, "reason": "No organisation name provided."}

    client = _get_client()
    if client is None:
        return {"checked": False, "reason": "EXA_API_KEY not configured - skipping online verification."}

    try:
        response = client.search(
            organisation_name.strip(),
            type="auto",
            category="company",
            num_results=5,
            contents={"highlights": True},
        )
    except Exception as exc:  # noqa: BLE001 - external API can fail in many ways (network, quota, auth)
        return {"checked": False, "reason": f"Organisation lookup failed: {exc}"}

    matches = [
        {
            "title": getattr(result, "title", None),
            "url": getattr(result, "url", None),
            "highlights": getattr(result, "highlights", None),
        }
        for result in getattr(response, "results", [])
    ]
    return {
        "checked": True,
        "organisation_name": organisation_name.strip(),
        "match_count": len(matches),
        "has_online_presence": len(matches) > 0,
        "matches": matches,
    }


TOOLS = [verify_organisation_online]
