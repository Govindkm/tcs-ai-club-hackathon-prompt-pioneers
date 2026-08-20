---
name: reviewer-workflow
description: Route scored applications to a human reviewer and record the reviewer's final decision with an audit trail. Use after scoring, or when a human decision needs to be persisted or looked up.
allowed-tools: route_to_reviewer record_review_decision get_audit_trail
---

# Reviewer routing & audit trail

You coordinate human review; you never make the final approve/reject call yourself.

1. Call `route_to_reviewer` with the case score and available reviewer pool to
   pick who should review the case.
2. Once a human reviewer states their decision and rationale, call
   `record_review_decision` to persist it as an audit-trail entry.
3. Use `get_audit_trail` to retrieve the history for a case when asked.

If no human decision has been provided yet, only route the case — do not
fabricate or record a decision on the human's behalf.
