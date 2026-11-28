"""Deterministic, offline engineering retry *decision* policy.

Advisory only. No code execution, API calls, spending, issue writes or retries.
A separate approved controller must verify real CI/check evidence before it
may request the existing owner-gated Claude patch lane.
"""
import re
from datetime import datetime, timedelta, timezone

SHA = re.compile(r"^[a-f0-9]{40}$")
DIGEST = re.compile(r"^[a-f0-9]{64}$")
MAX_ATTEMPTS = 2
COOLDOWN_MINUTES = 30
ALLOWED_STATES = {"needs_human_triage", "checks_pending", "review_gate", "missing_check_evidence"}

def _decision(action, reason, task_id, attempt, **extra):
    return {"schema": "core8-dev-loop-decision-v1",
            "task_id": task_id, "attempt": attempt,
            "action": action, "reason": reason,
            "execution_authorized": False,
            "may_spend": False, "may_merge": False,
            "may_deploy": False, **extra}

def decide(task, observation, history, now):
    """Return a safe next-action *suggestion* with no authority.

    task: immutable scope digest and explicitly human-approved flag.
    observation: current PR SHA and normalized check state from the observer.
    history: attempts of that exact task+scope at previously approved SHAs.
    """
    if not isinstance(task, dict) or not isinstance(observation, dict) or not isinstance(history, (list, tuple)):
        return _decision("blocked", "invalid_input_shape", "", 0)
    if any(not isinstance(item, dict) for item in history):
        return _decision("blocked", "invalid_attempt_history", "", len(history))
    task_id = task.get("task_id", "")
    digest = task.get("scope_digest", "")
    sha = observation.get("head_sha", "")
    attempt = len(history)
    if not isinstance(task_id, str) or not 1 <= len(task_id) <= 100 or not DIGEST.fullmatch(str(digest)):
        return _decision("blocked", "invalid_task_identity", str(task_id)[:100], attempt)
    if not SHA.fullmatch(str(sha)) or not isinstance(observation.get("state"), str) or observation.get("state") not in ALLOWED_STATES:
        return _decision("blocked", "invalid_current_ci_snapshot", task_id, attempt)
    if task.get("approved") is not True or task.get("approved_scope_digest") != digest:
        return _decision("blocked", "missing_exact_owner_approval", task_id, attempt)
    if task.get("approved_head_sha") != sha:
        return _decision("blocked", "stale_head_requires_approval", task_id, attempt)
    if observation["state"] == "checks_pending":
        return _decision("wait", "ci_still_running", task_id, attempt)
    if observation["state"] == "missing_check_evidence":
        return _decision("blocked", "no_ci_evidence", task_id, attempt)
    if observation["state"] == "review_gate":
        return _decision("human_review", "checks_no_longer_fail", task_id, attempt)
    if attempt >= MAX_ATTEMPTS:
        return _decision("human_review", "retry_budget_exhausted", task_id, attempt)
    if not isinstance(now, datetime) or now.tzinfo is None:
        return _decision("blocked", "clock_invalid", task_id, attempt)
    for item in history:
        if item.get("task_id") != task_id or item.get("scope_digest") != digest:
            return _decision("blocked", "history_scope_conflict", task_id, attempt)
        if item.get("head_sha") != sha:
            return _decision("blocked", "head_changed_between_attempts", task_id, attempt)
    if history:
        previous = history[-1]
        try:
            raw_time = previous["started_at"]
            if not isinstance(raw_time, str):
                raise ValueError("invalid_time_type")
            recorded = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
            if recorded.tzinfo is None or recorded > now:
                raise ValueError("invalid_time")
        except (ValueError, TypeError, KeyError):
            return _decision("blocked", "invalid_attempt_history", task_id, attempt)
        if now - recorded < timedelta(minutes=COOLDOWN_MINUTES):
            return _decision("wait", "retry_cooldown", task_id, attempt)
        if previous.get("result") not in ("failed", "tested_failed"):
            return _decision("blocked", "previous_attempt_not_confirmed_failed", task_id, attempt)
    if task.get("allow_paid_execution") is not True:
        return _decision("blocked", "paid_execution_not_approved", task_id, attempt)
    return _decision("propose_approved_patch_lane", "bounded_retry_candidate",
                     task_id, attempt + 1,
                     head_sha=sha, scope_digest=digest,
                     max_attempts=MAX_ATTEMPTS, owner_gate_still_required=True)
