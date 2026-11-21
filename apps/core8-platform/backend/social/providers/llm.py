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


# ── Health: what the dashboard shows next to "LLM" ─────────────────────────
# A provider can have a valid key and still fail every call (account spend cap,
# revoked key). Without this the header said "LLM: live" while every agent run
# silently fell back to templates (production, 2026-11-20).

HEALTH_KEY = "llm_health"
BLOCKING = {"usage_limit", "auth", "permission"}


def classify_error(e: Exception) -> tuple[str, str]:
    """(code, Hebrew message). Never echoes the exception body, which may carry headers."""
    raw = str(e)
    status_code = getattr(e, "status_code", None)
    if "usage limits" in raw or "spend limit" in raw or "credit balance" in raw:
        return "usage_limit", ("חשבון Anthropic הגיע למגבלת השימוש שהוגדרה בו — הגדל את המגבלה או הוסף קרדיט "
                               "ב-console.anthropic.com → Settings → Limits/Billing. עד אז הסוכנים עובדים בתבניות (mock).")
    if status_code == 401:
        return "auth", "המפתח נדחה על-ידי Anthropic (401) — החלף אותו בלשונית מפתחות"
    if status_code == 403:
        return "permission", "אין הרשאה (403) — בדוק חיוב/הרשאות בחשבון Anthropic"
    if status_code == 404:
        return "model", "המודל לא נמצא (404) — בדוק SOCIAL_LLM_MODEL"
    if status_code == 429:
        return "rate_limit", "חריגה ממגבלת קצב (429) — המערכת תנסה שוב בריצה הבאה"
    if status_code == 400:
        return "bad_request", "Anthropic דחה את הבקשה (400) — בדוק את המודל והגדרות החשבון"
    return "network", f"שגיאת חיבור: {type(e).__name__}"


async def get_health() -> dict:
    row = await fetch_one("SELECT value FROM sm_settings WHERE key=?", (HEALTH_KEY,))
    try:
        return json.loads(row["value"]) if row else {"state": "unknown"}
    except (TypeError, ValueError):
        return {"state": "unknown"}


async def set_health(state: str, code: str | None = None, message: str | None = None) -> None:
    from ..db import utc_str
    current = await get_health()
    if current.get("state") == state and current.get("code") == code:
        return  # no write per call when nothing changed
    value = json.dumps({"state": state, "code": code, "message": message, "at": utc_str()}, ensure_ascii=False)
    await execute("INSERT INTO sm_settings (key, value, updated_at) VALUES (?,?,datetime('now')) "
                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now')",
                  (HEALTH_KEY, value))
    if state == "blocked":
        logger.error("LLM blocked (%s): %s", code, message)


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
    """`mode` is evaluated on every access so a key saved in the dashboard
    (social.keystore) switches the provider to live without a restart."""

    def __init__(self):
        self.model = scfg.llm_model

    @staticmethod
    def _api_key() -> str:
        from .. import keystore as secrets  # local import: avoids an import cycle at module load
        return secrets.cached("anthropic_api_key")

    @property
    def mode(self) -> str:
        if scfg.llm_mode == "mock":
            return "mock"
        key = self._api_key()
        if not key:
            return "mock"
        if scfg.llm_mode == "auto" and key.startswith("test-"):
            return "mock"
        return "live"

    async def display_mode(self) -> tuple[str, dict]:
        """Mode for the dashboard: 'blocked' overrides 'live' when the last call hit a blocking error."""
        mode = self.mode
        health = await get_health() if mode == "live" else {"state": "n/a"}
        if mode == "live" and health.get("state") == "blocked":
            return "blocked", health
        return mode, health

    async def complete_json(self, task: str, system: str, user: str,
                            mock_result, job_id: str | None = None, max_tokens: int | None = None):
        """Return a JSON-decoded object. In mock mode returns `mock_result`
        (callable or value) and records zero usage, so the pipeline works
        end-to-end without credentials."""
        from .. import keystore as secrets
        await secrets.refresh()
        if self.mode != "live":
            await record_usage(task, "mock", None, 0, 0, job_id)
            return mock_result() if callable(mock_result) else mock_result

        used = await tokens_used_today()
        if used >= scfg.ai_daily_token_budget:
            raise BudgetExceeded(
                f"AI daily token budget reached ({used}/{scfg.ai_daily_token_budget}).")

        import anthropic  # imported lazily so mock mode has no SDK dependency at runtime
        client = anthropic.AsyncAnthropic(api_key=self._api_key())
        try:
            resp = await client.messages.create(
                model=self.model,
                max_tokens=max_tokens or scfg.ai_max_tokens_per_call,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as e:
            code, message = classify_error(e)
            await set_health("blocked" if code in BLOCKING else "degraded", code, message)
            raise
        await set_health("ok")
        text = "".join(getattr(b, "text", "") for b in resp.content)
        usage = getattr(resp, "usage", None)
        await record_usage(task, "anthropic", self.model,
                           getattr(usage, "input_tokens", 0) or 0,
                           getattr(usage, "output_tokens", 0) or 0, job_id)
        try:
            return _extract_json(text)
        except ValueError:
            if getattr(resp, "stop_reason", None) == "max_tokens":
                logger.warning("LLM reply for task %s was truncated at max_tokens=%s — ask for less per call",
                               task, max_tokens or scfg.ai_max_tokens_per_call)
            else:
                logger.warning("LLM returned non-JSON for task %s: %s", task, redact(text, 200))
            raise


llm = LLMProvider()
