"""
Tool approval gate — enforces APPROVAL_MODE and TOOL_BLOCKLIST.

Risk levels:
  LOW   — read-only, side-effect-free (web_search, read_file in safe dirs)
  HIGH  — writes, executes, sends data, or touches external services

In 'smart' mode: LOW tools run freely, HIGH tools are gated.
In 'manual' mode: every tool is gated.
In 'off' mode: nothing is gated (blocklist still enforced).
"""

from config import cfg

# Tools classified as HIGH risk — writes, external calls, code execution
_HIGH_RISK = {
    "write_file",
    "edit_file",
    "delete_file",
    "run_command",
    "execute_code",
    "shell",
    "send_email",
    "send_message",
    "http_request",
    "post_request",
    "create_record",
    "update_record",
    "delete_record",
    "deploy",
    "git_push",
    "git_commit",
    "queue_post",   # schedules a real publish to a live Instagram account
}


def is_blocklisted(tool_name: str) -> bool:
    return tool_name in cfg.tool_blocklist


def needs_approval(tool_name: str) -> bool:
    """Return True if this tool call must be approved before execution."""
    if is_blocklisted(tool_name):
        return False  # blocklisted = never runs, not gated
    mode = cfg.approval_mode
    if mode == "off":
        return False
    if mode == "manual":
        return True
    # smart: gate only HIGH risk tools
    return tool_name in _HIGH_RISK


def risk_level(tool_name: str) -> str:
    return "HIGH" if tool_name in _HIGH_RISK else "LOW"
