"""Generate clearly labeled, synthetic Core8 engineering dashboard demo data.

No network access, customer data, secrets, real PR identifiers or approvals.
This fixture is NOT evidence of live CI statuses or task completion.
"""
import json
from pathlib import Path

SHA = "a" * 40


def sample():
    data = [
        (901001, "needs_human_triage", ["demo-contract-failure"]),
        (901002, "checks_pending", []),
        (901003, "incomplete_check_evidence", []),
        (901004, "review_gate", []),
        (901005, "missing_check_evidence", []),
    ]
    return {
        "schema": "core8-dev-loop-health-v1",
        "mode": "observe_only",
        "demo": True,
        "repository": "V1P3eR1/Core8-AI",
        "items": [
            {"pr": number, "head_sha": SHA, "draft": True, "state": state,
             "failed_checks": checks, "approval": "not_granted_by_this_report"}
            for number, state, checks in data
        ],
        "boundaries": {"may_commit": False, "may_merge": False,
                       "may_deploy": False, "may_spend": False},
    }


def main():
    Path("core8-dev-loop-report.json").write_text(
        json.dumps(sample(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("core8_dashboard_demo_fixture_written synthetic=true")


if __name__ == "__main__":
    main()
