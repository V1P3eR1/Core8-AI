"""LLM adapter — Anthropic (live) or deterministic mock.

The LLM only *proposes* text. Every security decision (approval state,
publishing permission, account selection) is made by application code.
Untrusted content is wrapped by the caller with `security.injection_gate.gate`.
"""

import json
import logging
import re

from config import cfg as platform_cfg
from security.log_redact import redact

from ..config import scfg
from ..db import execute, fetch_one, new_id

logger = logging.getLogger("core8.social.llm")


class BudgetExceeded(RuntimeError):
    pass


async def tokens_used_today() -> int:
    row = await fetch_one(
        "SELECT COALESCE(SUM(input_tokens + output_tokens), 0) AS t FROM sm_ai_usage "
        "WHERE created_at >= datetime('now', '-1 day')")
    return int(row["t"]) if row else 0


async def record_usage(task: str, provider: str, model: str | None,
                       input_tokens: int, output_tokens: int, job_id: str | None = None) -> None:
    await execute(
        "INSERT INTO sm_ai_usage (id, job_id, task, provider, model, input_tokens, output_tokens) "
        "VALUES (?,?,?,?,?,?,?)",
        (new_id(), job_id, task, provider, model, input_tokens, output_tokens))


def _extract_json(text: str):
    """Best-effort: find the first JSON object/array in a model reply."""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0] or [-1])
    if start >= 0:
        try:
            return json.loads(text[start:])
        except ValueError:
            pass
    raise ValueError("Model reply did not contain valid JSON")


class LLMProvider:
    def __init__(self):
        self.mode = "live" if scfg.llm_live else "mock"
        self.model = scfg.llm_model

    async def complete_json(self, task: str, system: str, user: str,
                            mock_result, job_id: str | None = None):
        """Return a JSON-decoded object. In mock mode returns `mock_result`
        (callable or value) and records zero usage, so the pipeline works
        end-to-end without credentials."""
        if self.mode != "live":
            await record_usage(task, "mock", None, 0, 0, job_id)
            return mock_result() if callable(mock_result) else mock_result

        used = await tokens_used_today()
        if used >= scfg.ai_daily_token_budget:
            raise BudgetExceeded(
                f"AI daily token budget reached ({used}/{scfg.ai_daily_token_budget}).")

        import anthropic  # imported lazily so mock mode has no SDK dependency at runtime
        client = anthropic.AsyncAnthropic(api_key=platform_cfg.anthropic_api_key)
        resp = await client.messages.create(
            model=self.model,
            max_tokens=scfg.ai_max_tokens_per_call,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(getattr(b, "text", "") for b in resp.content)
        usage = getattr(resp, "usage", None)
        await record_usage(task, "anthropic", self.model,
                           getattr(usage, "input_tokens", 0) or 0,
                           getattr(usage, "output_tokens", 0) or 0, job_id)
        try:
            return _extract_json(text)
        except ValueError:
            logger.warning("LLM returned non-JSON for task %s: %s", task, redact(text, 200))
            raise


llm = LLMProvider()
