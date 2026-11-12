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

from security import tool_policy


def is_blocklisted(tool_name: str) -> bool:
    return tool_name in cfg.tool_blocklist


def needs_approval(tool_name: str, tainted: bool = False) -> bool:
    """Return True if this tool call must be approved before execution (see tool_policy)."""
    if is_blocklisted(tool_name):
        return False  # blocklisted = never runs, not gated
    return tool_policy.needs_approval(tool_name, cfg.approval_mode, tainted)


def risk_level(tool_name: str) -> str:
    """Label shown in the approval prompt."""
    risk = tool_policy.risk_of(tool_name)
    return {"read": "LOW", "write": "MEDIUM"}.get(risk, "HIGH")
