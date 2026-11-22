"""Offline no-secret review pipeline: validate -> git apply --check -> reserve.

Does NOT apply patches, run generated code, publish a PR, or start Claude.
Never accept expected_record from artifact text: independently authenticate the
approved task and GitHub run/artifact metadata before calling this function.
"""
import os
import subprocess
from pathlib import Path
from artifact_receipt import validate_artifact_receipt
from patch_gate import validate_patch
from replay_ledger import ReplayLedger

class ReviewRejected(ValueError):
    pass

def stage_review(*, receipt, expected_record, patch_bytes, now, ledger_path,
                 checkout_path, consumed=frozenset()):
    """Prepare an approved artifact for external human-controlled review."""
    verified = validate_artifact_receipt(
        receipt=receipt, expected_record=expected_record,
        patch_bytes=patch_bytes, now=now, consumed=consumed)
    summary = validate_patch(patch_bytes, verified["sha256"])
    checkout = Path(checkout_path).resolve(strict=True)
    if not checkout.is_dir():
        raise ReviewRejected("checkout_not_directory")
    # Minimal subprocess environment: do not expose credentials from caller.
    env = {
        "PATH": os.defpath,
        "HOME": "/nonexistent",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
    }
    try:
        result = subprocess.run(
            ["git", "-C", str(checkout), "apply", "--check", "-"],
            input=patch_bytes, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=15, check=False, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReviewRejected("git_apply_check_unavailable") from None
    if result.returncode != 0:
        raise ReviewRejected("git_apply_check_failed")
    key = verified["artifact_key"]
    ReplayLedger(ledger_path).reserve(
        repo=key[0], run_id=key[1], artifact_id=key[2],
        task_digest=receipt["task_digest"], patch_sha256=verified["sha256"])
    return {"status": "RESERVED_FOR_REVIEW", "paths": summary["files"],
            "artifact_key": key, "sha256": verified["sha256"]}
