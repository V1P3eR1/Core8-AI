"""Offline evidence ledger for bounded engineering attempts (candidate only).

Hash-chained, append-only *local fixture* with explicit event fields, sequence
checks and deterministic replay. No API, no automated runner, no external write.
A local file is NOT an authoritative distributed lock or approval record.
"""
import hashlib
import json
import re
from datetime import datetime

SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
TASK = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,99}$")
EVENTS = {"attempt_started", "attempt_failed", "attempt_tested_failed",
          "attempt_succeeded", "attempt_cancelled"}
TERMINAL = {"attempt_failed", "attempt_tested_failed",
            "attempt_succeeded", "attempt_cancelled"}
GENESIS = "0" * 64
MAX_EVENTS = 1000

class InvalidLedger(ValueError):
    pass

def _timestamp(value):
    if not isinstance(value, str):
        raise InvalidLedger("invalid_timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise InvalidLedger("invalid_timestamp") from None
    if parsed.tzinfo is None:
        raise InvalidLedger("invalid_timestamp")
    return parsed

def _fields(event):
    if not isinstance(event, dict) or set(event) != {
        "seq", "event", "task_id", "scope_digest", "head_sha",
        "attempt", "at", "prev", "hash"
    }:
        raise InvalidLedger("invalid_schema")
    if not isinstance(event["seq"], int) or isinstance(event["seq"], bool):
        raise InvalidLedger("invalid_sequence")
    if event["event"] not in EVENTS:
        raise InvalidLedger("unknown_event")
    if not isinstance(event["task_id"], str) or not TASK.fullmatch(event["task_id"]):
        raise InvalidLedger("invalid_task")
    if not isinstance(event["scope_digest"], str) or not DIGEST.fullmatch(event["scope_digest"]):
        raise InvalidLedger("invalid_scope")
    if not isinstance(event["head_sha"], str) or not SHA.fullmatch(event["head_sha"]):
        raise InvalidLedger("invalid_sha")
    if type(event["attempt"]) is not int or not 1 <= event["attempt"] <= 2:
        raise InvalidLedger("invalid_attempt_number")
    _timestamp(event["at"])
    if not isinstance(event["prev"], str) or not DIGEST.fullmatch(event["prev"]):
        raise InvalidLedger("invalid_prev")
    if not isinstance(event["hash"], str) or not DIGEST.fullmatch(event["hash"]):
        raise InvalidLedger("invalid_hash")

def _hash(event):
    data = {key: value for key, value in event.items() if key != "hash"}
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

def replay(events):
    """Strictly verify integrity and lifecycle; return per-scope immutable attempts."""
    if not isinstance(events, list) or len(events) > MAX_EVENTS:
        raise InvalidLedger("event_limit")
    prev = GENESIS
    active = {}
    attempts = {}
    last_at = None
    for pos, event in enumerate(events, 1):
        _fields(event)
        current_at = _timestamp(event["at"])
        if last_at is not None and current_at < last_at:
            raise InvalidLedger("non_monotonic_time")
        last_at = current_at
        if event["seq"] != pos or event["prev"] != prev or event["hash"] != _hash(event):
            raise InvalidLedger("broken_hash_chain")
        prev = event["hash"]
        key = (event["task_id"], event["scope_digest"], event["head_sha"])
        index = event["attempt"]
        store = attempts.setdefault(key, {})
        if event["event"] == "attempt_started":
            if key in active or index in store or index != len(store) + 1:
                raise InvalidLedger("duplicate_or_out_of_order_claim")
            if store and store[index - 1]["result"] not in ("failed", "tested_failed"):
                raise InvalidLedger("previous_attempt_not_failed")
            store[index] = {
                "task_id": event["task_id"],
                "scope_digest": event["scope_digest"],
                "head_sha": event["head_sha"],
                "started_at": event["at"],
                "result": "in_progress",
            }
            active[key] = index
        else:
            if active.get(key) != index:
                raise InvalidLedger("terminal_without_active_attempt")
            result = {
                "attempt_failed": "failed",
                "attempt_tested_failed": "tested_failed",
                "attempt_succeeded": "succeeded",
                "attempt_cancelled": "cancelled",
            }[event["event"]]
            if _timestamp(event["at"]) < _timestamp(store[index]["started_at"]):
                raise InvalidLedger("terminal_before_start")
            store[index]["result"] = result
            del active[key]
    return {
        "head": prev,
        "event_count": len(events),
        "active_count": len(active),
        "attempts": attempts,
    }

def make_event(events, event, task_id, scope_digest, head_sha, attempt, at):
    """Produce a proposed event. Caller stores it only after explicit authorization."""
    prev_state = replay(events)
    value = {
        "seq": len(events) + 1,
        "event": event,
        "task_id": task_id,
        "scope_digest": scope_digest,
        "head_sha": head_sha,
        "attempt": attempt,
        "at": at,
        "prev": prev_state["head"],
        "hash": "0" * 64,
    }
    _fields(value)
    value["hash"] = _hash(value)
    replay(events + [value])
    return value

def history_for(events, task_id, scope_digest, head_sha):
    """Verified input for retry_policy.decide; never grants approval."""
    state = replay(events)
    return [
        dict(entry) for _, entry in sorted(
            state["attempts"].get((task_id, scope_digest, head_sha), {}).items())
    ]
