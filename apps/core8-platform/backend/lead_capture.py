"""Public lead capture (issue #10) — a website form posts a lead into one tenant's CRM.

Safety design:
- **Tenant comes from the form, never the request.** A tenant owner creates a lead form; the
  public endpoint only knows the form's random key and writes to that form's tenant.
- **Explicit consent, with evidence of what was agreed to.** The tenant owner stores the exact
  disclosure text (per locale) as an immutable, hashed version and must approve it before the
  form goes live. The website renders that text from the public form endpoint; the submission
  must echo the version id it was shown, and a mismatch is refused (409). The consent record
  stores that version id and its SHA-256, the time, and a keyed hash of the IP (no raw IP).
- **Validation:** strict length limits and an email check; unknown fields are rejected.
- **Anti-spam:** a honeypot field (`website`) — bots that fill it get the same 202 but nothing is
  stored; a per-IP and a per-form rate limit (bounded memory, see MAX_TRACKED_KEYS).
- **Origin allow-list is not bot protection.** Browsers send `Origin`; any script can forge it or
  leave it out. It only stops other websites' pages from posting through visitors' browsers.
  Spam control rests on the rate limits and the honeypot, which apply with or without it.
- **No personal data in logs** — only the form key and the outcome.
- Submitted text is outside content: it reaches agents only through `list_leads` / `get_lead` /
  `search_leads`, whose output is wrapped and scanned as untrusted (security/tool_policy.py).
- The response never reveals whether a lead was stored, its id, or the tenant.
"""

import hashlib
import hmac
import json
import logging
import re
import secrets
import time
import uuid
from collections import OrderedDict, deque

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

import database
from business_brain.access import TenantAccess, tenant_role
from config import cfg
from security.auth import client_ip as _client_ip

log = logging.getLogger("core8.lead_capture")

_DDL = """
-- Versioned, immutable consent disclosures (review on PR #14, 2026-11-17). A form shows exactly
-- one approved version; every consent record points at the version the visitor was shown.
CREATE TABLE IF NOT EXISTS consent_texts (
    id           TEXT PRIMARY KEY,
    tenant_id    TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    locale       TEXT NOT NULL,
    text         TEXT NOT NULL,
    sha256       TEXT NOT NULL,
    created_by   TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    approved_by  TEXT,
    approved_at  TEXT,
    UNIQUE(tenant_id, locale, sha256)
);
CREATE INDEX IF NOT EXISTS idx_consent_texts_tenant ON consent_texts(tenant_id);
CREATE TRIGGER IF NOT EXISTS consent_texts_immutable
    BEFORE UPDATE OF id, tenant_id, locale, text, sha256, created_by, created_at ON consent_texts
    BEGIN SELECT RAISE(ABORT, 'consent text versions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS consent_texts_approval_once
    BEFORE UPDATE OF approved_by, approved_at ON consent_texts WHEN OLD.approved_by IS NOT NULL
    BEGIN SELECT RAISE(ABORT, 'consent text already approved'); END;

CREATE TABLE IF NOT EXISTS lead_forms (
    form_key         TEXT PRIMARY KEY,
    tenant_id        TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name             TEXT NOT NULL,
    allowed_origins  TEXT NOT NULL DEFAULT '[]',
    consent_text_id  TEXT NOT NULL REFERENCES consent_texts(id),
    enabled          INTEGER NOT NULL DEFAULT 1,
    created_by       TEXT NOT NULL,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_lead_forms_tenant ON lead_forms(tenant_id);

CREATE TABLE IF NOT EXISTS lead_consents (
    tenant_id        TEXT NOT NULL,
    lead_id          TEXT PRIMARY KEY,
    form_key         TEXT NOT NULL,
    consent_text_id  TEXT NOT NULL REFERENCES consent_texts(id),
    consent_sha256   TEXT NOT NULL,
    consented_at     TEXT NOT NULL DEFAULT (datetime('now')),
    ip_hash          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_lead_consents_tenant ON lead_consents(tenant_id);
"""


async def init_lead_capture_schema() -> None:
    async with database.get_db() as db:
        await db.executescript(_DDL)
        await db.commit()


# ── Rate limiting (in-process; one instance — see LAUNCH_READINESS residual risks) ────────────

PER_IP_LIMIT, PER_IP_WINDOW = 5, 600.0        # 5 submissions per IP per form per 10 min
PER_FORM_LIMIT, PER_FORM_WINDOW = 200, 3600.0  # 200 submissions per form per hour
# Hard cap on tracked keys so the limiter's memory is bounded whatever the traffic. Keys are
# only created for existing, enabled forms, and the per-form limit is checked first, so a form
# adds at most PER_FORM_LIMIT per-IP keys per hour; the cap is a backstop on top of that.
MAX_TRACKED_KEYS = 20_000
_hits: "OrderedDict[str, deque]" = OrderedDict()


def _prune(now: float) -> None:
    """Drop keys whose newest hit is older than the longest window, then the least recently
    used keys while still over the cap."""
    longest = max(PER_IP_WINDOW, PER_FORM_WINDOW)
    for key in [k for k, dq in _hits.items() if not dq or dq[-1] <= now - longest]:
        del _hits[key]
    while len(_hits) >= MAX_TRACKED_KEYS:
        _hits.popitem(last=False)


def _allow(key: str, limit: int, window: float) -> bool:
    now = time.monotonic()
    dq = _hits.get(key)
    if dq is None:
        if len(_hits) >= MAX_TRACKED_KEYS:
            _prune(now)
        dq = _hits[key] = deque()
    _hits.move_to_end(key)
    while dq and dq[0] <= now - window:
        dq.popleft()
    if len(dq) >= limit:
        return False
    dq.append(now)
    return True


def reset_rate_limits() -> None:
    _hits.clear()


def _ip_hash(ip: str) -> str:
    return hmac.new(cfg.jwt_secret.encode(), ip.encode(), hashlib.sha256).hexdigest()


# ── Schemas ──────────────────────────────────────────────────────────────────────────────────

_EMAIL = re.compile(r"^[^@\s<>]{1,64}@[^@\s<>]{1,190}\.[A-Za-z]{2,24}$")
_PHONE = re.compile(r"^[0-9+()\-.\s]{6,40}$")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean(v: str) -> str:
    return _CONTROL.sub("", v).strip()


class LeadSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    email: str = Field(default="", max_length=254)
    phone: str = Field(default="", max_length=40)
    company: str = Field(default="", max_length=120)
    message: str = Field(default="", max_length=2000)
    consent: bool
    consent_text_id: str = Field(min_length=1, max_length=64)  # the version the visitor was shown
    website: str = Field(default="", max_length=200)  # honeypot: humans never see or fill it

    @field_validator("name", "email", "phone", "company", "message", "website")
    @classmethod
    def _strip(cls, v: str) -> str:
        return _clean(v)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not v:
            raise ValueError("name is required")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        if v and not _EMAIL.match(v):
            raise ValueError("invalid email")
        return v.lower()

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        if v and not _PHONE.match(v):
            raise ValueError("invalid phone")
        return v


LOCALES = ("en", "he", "ru")


class ConsentTextIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consent_text: str = Field(min_length=20, max_length=5000)
    locale: str = Field(default="en")

    @field_validator("consent_text")
    @classmethod
    def _text(cls, v: str) -> str:
        v = _clean(v)
        if len(v) < 20:
            raise ValueError("consent text is too short")
        return v

    @field_validator("locale")
    @classmethod
    def _locale(cls, v: str) -> str:
        if v not in LOCALES:
            raise ValueError(f"locale must be one of {LOCALES}")
        return v


class LeadFormCreate(ConsentTextIn):
    name: str = Field(min_length=1, max_length=80)
    allowed_origins: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("allowed_origins")
    @classmethod
    def _origins(cls, v: list[str]) -> list[str]:
        for o in v:
            if not re.match(r"^https?://[A-Za-z0-9.\-]+(:\d+)?$", o):
                raise ValueError(f"invalid origin {o!r} (expected scheme://host[:port])")
        return v


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def _consent_version(db, tenant_id: str, user_id: str, req: ConsentTextIn) -> str:
    """Id of the immutable version holding exactly this text (created if new)."""
    digest = _sha256(req.consent_text)
    async with db.execute(
        "SELECT id FROM consent_texts WHERE tenant_id=? AND locale=? AND sha256=?",
        (tenant_id, req.locale, digest),
    ) as cur:
        row = await cur.fetchone()
    if row:
        return row[0]
    ct_id = "ct_" + uuid.uuid4().hex
    await db.execute(
        """INSERT INTO consent_texts (id, tenant_id, locale, text, sha256, created_by)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (ct_id, tenant_id, req.locale, req.consent_text, digest, user_id),
    )
    return ct_id


# ── Routes ───────────────────────────────────────────────────────────────────────────────────

_CONSENT_SQL = """INSERT INTO lead_consents
                  (tenant_id, lead_id, form_key, consent_text_id, consent_sha256, ip_hash)
                  VALUES (?, ?, ?, ?, ?, ?)"""

router = APIRouter(tags=["lead-capture"])
_owner = tenant_role("owner")
_viewer = tenant_role("viewer")
_RECEIVED = {"status": "received"}


_FORM_SELECT = """SELECT f.form_key, f.name, f.allowed_origins, f.enabled, f.created_at,
                         c.id, c.locale, c.sha256, c.approved_by IS NOT NULL
                  FROM lead_forms f JOIN consent_texts c ON c.id = f.consent_text_id"""


def _form_out(r) -> dict:
    return {"form_key": r[0], "name": r[1], "allowed_origins": json.loads(r[2]),
            "enabled": bool(r[3]), "created_at": r[4],
            "consent_text": {"id": r[5], "locale": r[6], "sha256": r[7], "approved": bool(r[8])},
            # A form accepts submissions only once its current consent text is approved.
            "active": bool(r[3]) and bool(r[8]),
            "public_path": f"/api/public/lead-forms/{r[0]}"}


async def _get_form(tenant_id: str, form_key: str) -> dict:
    async with database.get_db() as db:
        async with db.execute(_FORM_SELECT + " WHERE f.form_key=? AND f.tenant_id=?",
                              (form_key, tenant_id)) as cur:
            row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Form not found")
    return _form_out(row)


@router.post("/api/tenants/{tenant_id}/lead-forms", status_code=201)
async def create_lead_form(req: LeadFormCreate, access: TenantAccess = Depends(_owner)):
    form_key = "lf_" + secrets.token_urlsafe(18)
    async with database.get_db() as db:
        ct_id = await _consent_version(db, access.tenant_id, access.user_id, req)
        await db.execute(
            """INSERT INTO lead_forms (form_key, tenant_id, name, allowed_origins,
                                       consent_text_id, created_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (form_key, access.tenant_id, req.name, json.dumps(req.allowed_origins),
             ct_id, access.user_id),
        )
        await db.commit()
    return await _get_form(access.tenant_id, form_key)


@router.get("/api/tenants/{tenant_id}/lead-forms")
async def list_lead_forms(access: TenantAccess = Depends(_viewer)):
    async with database.get_db() as db:
        async with db.execute(_FORM_SELECT + " WHERE f.tenant_id=? ORDER BY f.created_at",
                              (access.tenant_id,)) as cur:
            rows = await cur.fetchall()
    return [_form_out(r) for r in rows]


@router.put("/api/tenants/{tenant_id}/lead-forms/{form_key}/consent-text")
async def change_consent_text(form_key: str, req: ConsentTextIn,
                              access: TenantAccess = Depends(_owner)):
    """Point the form at a new disclosure. Old versions are kept; a new, unapproved version
    deactivates the form until it is approved."""
    async with database.get_db() as db:
        ct_id = await _consent_version(db, access.tenant_id, access.user_id, req)
        cur = await db.execute(
            "UPDATE lead_forms SET consent_text_id=? WHERE form_key=? AND tenant_id=?",
            (ct_id, form_key, access.tenant_id),
        )
        if cur.rowcount == 0:
            await db.rollback()
            raise HTTPException(status_code=404, detail="Form not found")
        await db.commit()
    return await _get_form(access.tenant_id, form_key)


@router.get("/api/tenants/{tenant_id}/consent-texts")
async def consent_text_history(access: TenantAccess = Depends(_viewer)):
    async with database.get_db() as db:
        async with db.execute(
            """SELECT id, locale, text, sha256, created_by, created_at, approved_by, approved_at
               FROM consent_texts WHERE tenant_id=? ORDER BY created_at, id""",
            (access.tenant_id,),
        ) as cur:
            rows = await cur.fetchall()
    keys = ("id", "locale", "text", "sha256", "created_by", "created_at", "approved_by", "approved_at")
    return [dict(zip(keys, r)) for r in rows]


@router.post("/api/tenants/{tenant_id}/consent-texts/{consent_text_id}/approve")
async def approve_consent_text(consent_text_id: str, access: TenantAccess = Depends(_owner)):
    """Record the tenant owner's explicit approval of this exact text (once, immutable)."""
    async with database.get_db() as db:
        async with db.execute(
            "SELECT approved_by FROM consent_texts WHERE id=? AND tenant_id=?",
            (consent_text_id, access.tenant_id),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Consent text not found")
        if row[0] is not None:
            raise HTTPException(status_code=409, detail="Already approved")
        await db.execute(
            "UPDATE consent_texts SET approved_by=?, approved_at=datetime('now') WHERE id=?",
            (access.user_id, consent_text_id),
        )
        await db.commit()
    return {"id": consent_text_id, "approved": True}


_ACTIVE_FORM = """SELECT f.tenant_id, f.name, f.allowed_origins, c.id, c.locale, c.text, c.sha256
                  FROM lead_forms f JOIN consent_texts c ON c.id = f.consent_text_id
                  WHERE f.form_key=? AND f.enabled=1 AND c.approved_by IS NOT NULL"""


async def _active_form(form_key: str):
    async with database.get_db() as db:
        async with db.execute(_ACTIVE_FORM, (form_key,)) as cur:
            return await cur.fetchone()


@router.get("/api/public/lead-forms/{form_key}")
async def public_form(form_key: str):
    """What the website renders: the exact approved disclosure and its version id, which the
    submission must echo back. No tenant information is exposed."""
    row = await _active_form(form_key)
    if row is None:
        raise HTTPException(status_code=404, detail="Form not found")
    return {"consent_text_id": row[3], "locale": row[4], "consent_text": row[5], "sha256": row[6],
            "submit_path": f"/api/public/lead-forms/{form_key}/submit"}


@router.delete("/api/tenants/{tenant_id}/lead-forms/{form_key}", status_code=204)
async def disable_lead_form(form_key: str, access: TenantAccess = Depends(_owner)):
    async with database.get_db() as db:
        cur = await db.execute(
            "UPDATE lead_forms SET enabled=0 WHERE form_key=? AND tenant_id=?",
            (form_key, access.tenant_id),
        )
        await db.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Form not found")


@router.post("/api/public/lead-forms/{form_key}/submit", status_code=202)
async def submit_lead(form_key: str, sub: LeadSubmission, request: Request):
    row = await _active_form(form_key)
    if row is None:
        raise HTTPException(status_code=404, detail="Form not found")
    tenant_id, form_name, origins_json, consent_text_id, _locale, _text, consent_sha = row

    origins = json.loads(origins_json)
    if origins and request.headers.get("origin") not in origins:
        log.info("lead form %s: rejected origin", form_key)
        raise HTTPException(status_code=403, detail="Origin not allowed")

    ip = _client_ip(request)
    if not _allow(f"form:{form_key}", PER_FORM_LIMIT, PER_FORM_WINDOW) or \
            not _allow(f"ip:{form_key}:{ip}", PER_IP_LIMIT, PER_IP_WINDOW):
        log.info("lead form %s: rate limited", form_key)
        raise HTTPException(status_code=429, detail="Too many submissions, try again later")

    if sub.website:
        log.info("lead form %s: honeypot hit, dropped", form_key)
        return _RECEIVED

    if not sub.consent:
        raise HTTPException(status_code=422, detail="Consent is required")
    if sub.consent_text_id != consent_text_id:
        # The visitor saw a different (older or unknown) disclosure: never attribute this consent
        # to text they were not shown.
        raise HTTPException(status_code=409, detail="The consent text has changed; reload the form")
    if not (sub.email or sub.phone):
        raise HTTPException(status_code=422, detail="An email or phone number is required")

    notes = sub.message
    if sub.phone:
        notes = f"Phone: {sub.phone}\n{notes}".strip()
    # Lead and consent record are written in ONE transaction: a lead never exists without its
    # consent audit row (review on PR #14).
    lead_id = str(uuid.uuid4())
    async with database.get_db() as db:
        try:
            await db.execute(
                """INSERT INTO leads (tenant_id, id, name, email, company, status, source, notes)
                   VALUES (?, ?, ?, ?, ?, 'new', ?, ?)""",
                (tenant_id, lead_id, sub.name, sub.email, sub.company, f"web-form:{form_name}", notes),
            )
            await db.execute(_CONSENT_SQL, (tenant_id, lead_id, form_key, consent_text_id,
                                            consent_sha, _ip_hash(ip)))
            await db.commit()
        except Exception:
            await db.rollback()
            log.error("lead form %s: store failed, rolled back", form_key)
            raise
    log.info("lead form %s: lead stored", form_key)
    return _RECEIVED

