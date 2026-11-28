"""Private-side Core8 task overview from an existing verified audit report.

Offline-only. Never read private Notion data in public GitHub CI.
Never serialize task IDs, issue IDs, note text or approval evidence.
An audited row is informational; this module cannot approve execution.
"""
from collections import Counter

SCHEMA = "core8-notion-github-readonly-audit-v1"
KNOWN_FLAGS = frozenset({
    "public_export_disabled", "decision_not_approved",
    "public_scope_gate_incomplete", "issue_evidence_missing",
    "linked_record_is_pr", "scope_mapping_mismatch",
    "invalid_issue_state", "closed_issue_needs_review",
    "reopened_issue_needs_review",
    "existing_link_not_new_export_permission",
})
ALLOWED_STATUS = frozenset({
    "Queued", "In progress", "Review", "Blocked",
    "Closed - unverified", "Awaiting approval",
})
GITHUB_STATES = frozenset({"not_linked", "open", "closed", "unverified", "invalid"})
MAX_TASKS = 100

class PrivateSummaryError(ValueError):
    pass


def summarize(audit):
    """Compute aggregate diagnostics; never leak task-level identifiers."""
    if not isinstance(audit, dict) or audit.get("schema") != SCHEMA:
        raise PrivateSummaryError("invalid_schema")
    if audit.get("mode") != "observe_only":
        raise PrivateSummaryError("not_observe_only")
    for key in ("can_change_notion", "can_export_private_scope", "can_authorize_claude"):
        if audit.get(key) is not False:
            raise PrivateSummaryError("unsafe_permissions")
    items = audit.get("items")
    if not isinstance(items, list) or len(items) > MAX_TASKS:
        raise PrivateSummaryError("invalid_items")
    if audit.get("task_count") != len(items):
        raise PrivateSummaryError("count_mismatch")
    statuses, states, flags = Counter(), Counter(), Counter()
    seen_tasks, seen_issues = set(), set()
    linked, attention = 0, 0
    for item in items:
        if not isinstance(item, dict):
            raise PrivateSummaryError("invalid_item")
        tid, iid = item.get("task_id"), item.get("issue_number")
        status, state, codes = item.get("notion_status"), item.get("github_state"), item.get("flags")
        if not isinstance(tid, str) or tid in seen_tasks or len(tid) > 50:
            raise PrivateSummaryError("duplicate_or_invalid_task")
        seen_tasks.add(tid)
        if iid is not None:
            if type(iid) is not int or iid < 1 or iid in seen_issues:
                raise PrivateSummaryError("duplicate_or_invalid_issue")
            seen_issues.add(iid)
            linked += 1
        if status not in ALLOWED_STATUS or state not in GITHUB_STATES:
            raise PrivateSummaryError("unknown_status")
        if not isinstance(codes, list) or len(codes) > len(KNOWN_FLAGS):
            raise PrivateSummaryError("invalid_flags")
        if len(codes) != len(set(codes)) or any(x not in KNOWN_FLAGS for x in codes):
            raise PrivateSummaryError("unexpected_flag")
        if item.get("public_scope_gate") not in ("blocked", "verified_metadata_only"):
            raise PrivateSummaryError("invalid_gate")
        statuses[status] += 1
        states[state] += 1
        flags.update(codes)
        attention += bool(codes)
    if audit.get("linked_task_count") != linked or audit.get("attention_count") != attention:
        raise PrivateSummaryError("inconsistent_totals")
    return {
        "schema": "core8-private-metadata-summary-v1",
        "scope": "private_local_only",
        "mode": "observe_only",
        "tasks": len(items),
        "linked_issues": linked,
        "needs_review": attention,
        "status_counts": {k: statuses[k] for k in sorted(ALLOWED_STATUS) if statuses[k]},
        "github_state_counts": {k: states[k] for k in sorted(GITHUB_STATES) if states[k]},
        "diagnostic_counts": {k: flags[k] for k in sorted(KNOWN_FLAGS) if flags[k]},
        "may_publish_to_public_ci": False,
        "may_write_to_notion": False,
        "may_authorize_claude": False,
    }
