"""Public lead capture (issue #10) — a website form posts a lead into one tenant's CRM.

Safety design:
- **Tenant comes from the form, never the request.** A tenant owner creates a lead form; the
  public endpoint only knows the form's random key and writes to that form's tenant.
- **Explicit consent** is required (`consent: true`) and recorded with the consent-text version
  the tenant configured, the time, and a keyed hash of the IP (no raw IP stored).
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
CREATE TABLE IF NOT EXISTS lead_forms (
    form_key              TEXT PRIMARY KEY,
    tenant_id             TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name                  TEXT NOT NULL,
    allowed_origins       TEXT NOT NULL DEFAULT '[]',
    consent_text_version  TEXT NOT NULL,
    enabled               INTEGER NOT NULL DEFAULT 1,
    created_by            TEXT NOT NULL,
    created_at            TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_lead_forms_tenant ON lead_forms(tenant_id);

CREATE TABLE IF NOT EXISTS lead_consents (
    tenant_id             TEXT NOT NULL,
    lead_id               TEXT PRIMARY KEY,
    form_key              TEXT NOT NULL,
    consent_text_version  TEXT NOT NULL,
    consented_at          TEXT NOT NULL DEFAULT (datetime('now')),
    ip_hash               TEXT NOT NULL
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


class LeadFormCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    consent_text_version: str = Field(min_length=1, max_length=40)
    allowed_origins: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("allowed_origins")
    @classmethod
    def _origins(cls, v: list[str]) -> list[str]:
        for o in v:
            if not re.match(r"^https?://[A-Za-z0-9.\-]+(:\d+)?$", o):
                raise ValueError(f"invalid origin {o!r} (expected scheme://host[:port])")
        return v


# ── Routes ───────────────────────────────────────────────────────────────────────────────────

_CONSENT_SQL = """INSERT INTO lead_consents (tenant_id, lead_id, form_key, consent_text_version, ip_hash)
                  VALUES (?, ?, ?, ?, ?)"""

router = APIRouter(tags=["lead-capture"])
_owner = tenant_role("owner")
_viewer = tenant_role("viewer")
_RECEIVED = {"status": "received"}


@router.post("/api/tenants/{tenant_id}/lead-forms", status_code=201)
async def create_lead_form(req: LeadFormCreate, access: TenantAccess = Depends(_owner)):
    form_key = "lf_" + secrets.token_urlsafe(18)
    async with database.get_db() as db:
        await db.execute(
            """INSERT INTO lead_forms (form_key, tenant_id, name, allowed_origins,
                                       consent_text_version, created_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (form_key, access.tenant_id, req.name, json.dumps(req.allowed_origins),
             req.consent_text_version, access.user_id),
        )
        await db.commit()
    return {"form_key": form_key, "name": req.name, "allowed_origins": req.allowed_origins,
            "consent_text_version": req.consent_text_version, "enabled": True,
            "submit_path": f"/api/public/lead-forms/{form_key}/submit"}


@router.get("/api/tenants/{tenant_id}/lead-forms")
async def list_lead_forms(access: TenantAccess = Depends(_viewer)):
    async with database.get_db() as db:
        async with db.execute(
            """SELECT form_key, name, allowed_origins, consent_text_version, enabled, created_at
               FROM lead_forms WHERE tenant_id=? ORDER BY created_at""",
            (access.tenant_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [{"form_key": r[0], "name": r[1], "allowed_origins": json.loads(r[2]),
             "consent_text_version": r[3], "enabled": bool(r[4]), "created_at": r[5]} for r in rows]


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
    async with database.get_db() as db:
        async with db.execute(
            """SELECT tenant_id, name, allowed_origins, consent_text_version
               FROM lead_forms WHERE form_key=? AND enabled=1""",
            (form_key,),
        ) as cur:
            row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Form not found")
    tenant_id, form_name, origins_json, consent_version = row

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
            await db.execute(_CONSENT_SQL,
                             (tenant_id, lead_id, form_key, consent_version, _ip_hash(ip)))
            await db.commit()
        except Exception:
            await db.rollback()
            log.error("lead form %s: store failed, rolled back", form_key)
            raise
    log.info("lead form %s: lead stored", form_key)
    return _RECEIVED

