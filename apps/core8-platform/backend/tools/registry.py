import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Callable, Any

from security.log_redact import redact


@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: dict
    handler: Callable
    rate_limit: int = 0          # max calls per window (0 = unlimited)
    rate_window: float = 3600.0  # window in seconds


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDef] = {}
        self._call_times: dict[str, deque] = defaultdict(deque)

    def register(self, tool: ToolDef):
        self._tools[tool.name] = tool

    def get_schemas(self, allowed: list[str] | None = None) -> list[dict]:
        """Tool schemas for the Anthropic API. If `allowed` is given, only those
        tools are returned; `None` returns every registered tool."""
        return [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in self._tools.values()
            if allowed is None or t.name in allowed
        ]

    async def dispatch(self, name: str, inputs: dict) -> Any:
        tool = self._tools.get(name)
        if not tool:
            return {"error": f"Unknown tool: {name}"}

        if tool.rate_limit > 0:
            now = time.monotonic()
            dq = self._call_times[name]
            while dq and dq[0] < now - tool.rate_window:
                dq.popleft()
            if len(dq) >= tool.rate_limit:
                return {
                    "status": "anomaly_gate_blocked",
                    "tool": name,
                    "count": len(dq),
                    "limit": tool.rate_limit,
                    "window_seconds": tool.rate_window,
                }
            dq.append(now)

        result = await tool.handler(**inputs)
        return result


registry = ToolRegistry()
