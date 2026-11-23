"""Read-only Notion↔GitHub task reconciliation for Core8 engineering.

This pure module consumes *already obtained* trusted API snapshots. It neither
requests credentials nor writes Notion/GitHub. Private scope/acceptance text is
never copied into the output; approval is not inferred from issue existence.
"""
import re
from urllib.parse import urlparse

REPO = "V1P3eR1/Core8-AI"
ISSUE = re.compile(r"^https://github\.com/V1P3eR1/Core8-AI/issues/([1-9][0-9]*)/?$")
MARKER = re.compile(r"<!-- core8-task:([0-9a-fA-F-]{36}) -->")
ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
APPROVED = "Approved"

class ReconciliationError(ValueError):
    pass


def _prop(row, key):
    return (row.get("properties") or {}).get(key) or {}


def _status(row, key):
    return ((_prop(row, key).get("select") or {}).get("name") or "")


def _issue_number(row):
    url = _prop(row, "GitHub issue").get("url")
    if not url:
        return None
    if not isinstance(url, str):
        raise ReconciliationError("invalid_issue_url")
    m = ISSUE.fullmatch(url)
    if not m:
        raise ReconciliationError("unexpected_issue_host_or_path")
    return int(m.group(1))


def reconcile(rows, issues):
    """Return minimal metadata diagnostics; never export task descriptions.

    The canonical Notion task remains the only source of approval. An existing
    issue does not satisfy Public export, Approval evidence or human approval.
    """
    if not isinstance(rows, list) or len(rows) > 100:
        raise ReconciliationError("invalid_row_count")
    if not isinstance(issues, dict) or len(issues) > 200:
        raise ReconciliationError("invalid_issue_snapshot")
    seen_tasks, linked_issue_numbers, items = set(), set(), []
    for row in rows:
        if not isinstance(row, dict):
            raise ReconciliationError("invalid_row")
        task_id = str(row.get("id") or "").lower()
        if not ID.fullmatch(task_id) or task_id in seen_tasks:
            raise ReconciliationError("duplicate_or_invalid_task_id")
        seen_tasks.add(task_id)
        decision = _status(row, "Decision")
        status = _status(row, "Status")
        exported = _prop(row, "Public export").get("checkbox") is True
        approval_evidence = _prop(row, "Approval evidence").get("url")
        # Never export the private approval evidence URL.
        approved_for_public_scope = (
            decision == APPROVED and exported and
            isinstance(approval_evidence, str) and
            approval_evidence.startswith("https://")
        )
        issue_number = _issue_number(row)
        flags = []
        if not exported:
            flags.append("public_export_disabled")
        if decision != APPROVED:
            flags.append("decision_not_approved")
        if not approved_for_public_scope:
            flags.append("public_scope_gate_incomplete")
        actual_state = "not_linked"
        if issue_number is not None:
            if issue_number in linked_issue_numbers:
                raise ReconciliationError("duplicate_issue_mapping")
            linked_issue_numbers.add(issue_number)
            issue = issues.get(issue_number)
            if issue is None:
                flags.append("issue_evidence_missing")
                actual_state = "unverified"
            elif not isinstance(issue, dict):
                raise ReconciliationError("invalid_issue_record")
            elif issue.get("pull_request"):
                flags.append("linked_record_is_pr")
                actual_state = "invalid"
            else:
                body = issue.get("body") or ""
                if not isinstance(body, str):
                    raise ReconciliationError("invalid_issue_body")
                marks = MARKER.findall(body)
                if len(marks) != 1 or marks[0].lower() != task_id:
                    flags.append("scope_mapping_mismatch")
                    actual_state = "invalid"
                elif issue.get("state") not in ("open", "closed"):
                    flags.append("invalid_issue_state")
                    actual_state = "unverified"
                else:
                    actual_state = issue["state"]
                    if issue["state"] == "closed" and status not in ("Closed - unverified", "Review"):
                        flags.append("closed_issue_needs_review")
                    elif issue["state"] == "open" and status == "Closed - unverified":
                        flags.append("reopened_issue_needs_review")
                    if not approved_for_public_scope:
                        flags.append("existing_link_not_new_export_permission")
        items.append({
            "task_id": task_id,
            "issue_number": issue_number,
            "notion_status": status,
            "github_state": actual_state,
            "public_scope_gate": "verified_metadata_only" if approved_for_public_scope else "blocked",
            "flags": sorted(set(flags)),
        })
    return {
        "schema": "core8-notion-github-readonly-audit-v1",
        "mode": "observe_only",
        "task_count": len(items),
        "linked_task_count": len(linked_issue_numbers),
        "attention_count": sum(bool(x["flags"]) for x in items),
        "items": items,
        "can_change_notion": False,
        "can_export_private_scope": False,
        "can_authorize_claude": False,
    }
