"""Operator-managed credentials stored encrypted in the database.

Why: the owner enters the Anthropic key and the Meta app credentials in the
dashboard instead of editing `.env.production` over SSH. Values are
Fernet-encrypted with IG_TOKEN_ENC_KEY (the same key that protects Instagram
access tokens) and decrypted only transiently in memory when a provider call
needs them. Environment variables remain a fallback so existing deployments
keep working unchanged.

Rules enforced here:
- A value is never returned by the API, written to logs, or included in audit
  details; only a hint (last 4 characters) and metadata are exposed.
- Every process (API, worker) keeps a small cache refreshed from the DB at
  most every CACHE_TTL seconds, so a key saved in the dashboard reaches the
  worker without a restart.
"""

import logging
import re
import time

from config import cfg as platform_cfg
from security.token_crypto import decrypt_token, encrypt_token

from .db import execute, fetch_all, jdump, jload, utc_str

logger = logging.getLogger("core8.social.secrets")

CACHE_TTL = 20.0
_PREFIX = "secret:"

# name -> (label, env attribute on platform cfg, validator regex, description)
SECRET_SPECS: dict[str, dict] = {
    "anthropic_api_key": {
        "label": "מפתח Anthropic API",
        "env_attr": "anthropic_api_key",
        "pattern": r"^sk-ant-api\d{2}-[A-Za-z0-9_\-]{40,}$",
        "help": "נוצר ב-console.anthropic.com → API Keys. מתחיל ב-sk-ant-api03-. מפעיל את הסוכנים (LLM: live).",
        "testable": True,
    },
    "meta_app_id": {
        "label": "Meta App ID",
        "env_attr": "meta_app_id",
        "pattern": r"^\d{8,25}$",
        "help": "מזהה האפליקציה מ-developers.facebook.com → App settings → Basic.",
        "testable": False,
    },
    "meta_app_secret": {
        "label": "Meta App Secret",
        "env_attr": "meta_app_secret",
        "pattern": r"^[a-f0-9]{24,64}$",
        "help": "ה-App Secret מאותו מסך (Show). נדרש להחלפת קוד OAuth בטוקן.",
        "testable": False,
    },
}


class SecretError(ValueError):
    pass


_cache: dict[str, dict] = {}
_cache_at: float = 0.0


def _normalise(name: str, value: str) -> str:
    value = re.sub(r"\s+", "", value or "")
    spec = SECRET_SPECS.get(name)
    if not spec:
        raise SecretError("secret לא מוכר")
    if not value:
        raise SecretError("ערך ריק")
    if name == "anthropic_api_key" and value.count("sk-ant-") > 1:
        raise SecretError("המפתח הודבק יותר מפעם אחת — הדבק אותו פעם אחת בלבד")
    if name == "anthropic_api_key" and value.startswith("sk-ant-") and not value.startswith("sk-ant-api"):
        raise SecretError("זה לא מפתח API (sk-ant-api03-…). טוקן של אפליקציית Claude אינו מתאים — צור מפתח ב-console.anthropic.com")
    if not re.match(spec["pattern"], value):
        raise SecretError(f"הפורמט של {spec['label']} אינו תקין")
    return value


async def refresh(force: bool = False) -> None:
    """Reload the encrypted rows into the process cache (ciphertext only)."""
    global _cache, _cache_at
    if not force and time.monotonic() - _cache_at < CACHE_TTL:
        return
    rows = await fetch_all("SELECT key, value, updated_at FROM sm_settings WHERE key LIKE ?", (_PREFIX + "%",))
    fresh: dict[str, dict] = {}
    for r in rows:
        name = r["key"][len(_PREFIX):]
        if name in SECRET_SPECS:
            fresh[name] = {**(jload(r["value"]) or {}), "updated_at": r["updated_at"]}
    _cache, _cache_at = fresh, time.monotonic()


def _env_value(name: str) -> str:
    return getattr(platform_cfg, SECRET_SPECS[name]["env_attr"], "") or ""


def cached(name: str) -> str:
    """Synchronous accessor: DB value (decrypted on the fly) or env fallback.
    Callers on async paths should `await refresh()` first."""
    entry = _cache.get(name)
    if entry and entry.get("enc"):
        try:
            return decrypt_token(entry["enc"])
        except RuntimeError as e:  # key rotated — fall back to env, never crash the request
            logger.error("cannot decrypt secret %s: %s", name, e)
    return _env_value(name)


async def get(name: str) -> str:
    await refresh()
    return cached(name)


def source(name: str) -> str | None:
    if _cache.get(name, {}).get("enc"):
        return "db"
    if _env_value(name):
        return "env"
    return None


async def status() -> dict:
    await refresh(force=True)
    out = {}
    for name, spec in SECRET_SPECS.items():
        entry = _cache.get(name) or {}
        src = source(name)
        env_v = _env_value(name)
        out[name] = {
            "label": spec["label"], "help": spec["help"], "testable": spec["testable"],
            "configured": src is not None, "source": src,
            "hint": entry.get("hint") if src == "db" else (("…" + env_v[-4:]) if env_v else None),
            "updated_at": entry.get("updated_at") if src == "db" else None,
            "updated_by": entry.get("updated_by") if src == "db" else None,
        }
    return out


async def set_value(name: str, value: str, actor: str) -> dict:
    clean = _normalise(name, value)
    enc = encrypt_token(clean)
    record = {"enc": enc, "hint": "…" + clean[-4:], "updated_by": actor, "set_at": utc_str()}
    await execute(
        "INSERT INTO sm_settings (key, value, updated_at) VALUES (?,?,datetime('now')) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now')",
        (_PREFIX + name, jdump(record)))
    await refresh(force=True)
    return (await status())[name]


async def delete(name: str) -> dict:
    if name not in SECRET_SPECS:
        raise SecretError("secret לא מוכר")
    await execute("DELETE FROM sm_settings WHERE key=?", (_PREFIX + name,))
    await refresh(force=True)
    return (await status())[name]


async def test_anthropic(value: str | None = None) -> dict:
    """Minimal live call to confirm the key works. Returns a safe result only."""
    key = _normalise("anthropic_api_key", value) if value else await get("anthropic_api_key")
    if not key:
        return {"ok": False, "error": "no_key", "message": "אין מפתח מוגדר"}
    try:
        import anthropic
        from .config import scfg
        client = anthropic.AsyncAnthropic(api_key=key)
        resp = await client.messages.create(model=scfg.llm_model, max_tokens=8,
                                            messages=[{"role": "user", "content": "Reply with the single word OK"}])
        text = "".join(getattr(b, "text", "") for b in resp.content).strip()
        return {"ok": True, "model": scfg.llm_model, "reply": text[:20]}
    except Exception as e:  # noqa: BLE001 — classify, never echo the exception body (may contain headers)
        kind = type(e).__name__
        status_code = getattr(e, "status_code", None)
        raw = str(e)
        if "usage limits" in raw or "spend limit" in raw or "credit balance" in raw:
            # Anthropic returns 400 for an account-level monthly cap; the key itself is valid.
            message = ("המפתח תקין, אבל חשבון Anthropic הגיע למגבלת השימוש החודשית שהוגדרה בו — "
                       "הגדל את המגבלה או הוסף קרדיט ב-console.anthropic.com → Settings → Limits/Billing. "
                       "עד אז הסוכנים עובדים בתבניות (mock).")
            return {"ok": False, "error": "usage_limit", "status_code": status_code, "message": message}
        message = {
            400: "Anthropic דחה את הבקשה (400) — בדוק את המודל (SOCIAL_LLM_MODEL) והגדרות החשבון",
            401: "המפתח נדחה על-ידי Anthropic (401) — בדוק שהעתקת מפתח API תקין",
            403: "אין הרשאה (403) — בדוק חיוב/הרשאות בחשבון Anthropic",
            404: "המודל לא נמצא (404) — בדוק SOCIAL_LLM_MODEL",
            429: "חריגה ממגבלת קצב (429) — נסה שוב בעוד דקה",
        }.get(status_code, f"שגיאת חיבור: {kind}")
        return {"ok": False, "error": kind, "status_code": status_code, "message": message}
