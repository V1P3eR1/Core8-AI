"""Sandbox-only Stripe webhook ingestion. No charges, payments, or fiscal receipts."""
from __future__ import annotations
import os
from fastapi import FastAPI, Header, HTTPException, Request, status
from event_policy import parse_event
from merchant_binding import resolve_single_merchant
from webhook_security import InvalidWebhook, MAX_PAYLOAD_BYTES, verify_stripe_event

app = FastAPI(title="Core8 Finance OS (sandbox)", version="0.4.0", docs_url=None, redoc_url=None)

def safe_configuration():
    if os.getenv("APP_ENV", "sandbox").lower() not in {"sandbox", "development", "test"}:
        raise RuntimeError("Finance OS is sandbox-only")
    if os.getenv("ENABLE_STRIPE_WRITES", "false").lower() != "false":
        raise RuntimeError("Finance OS cannot write to Stripe")
    if os.getenv("STRIPE_EXPECT_LIVEMODE", "false").lower() != "false":
        raise RuntimeError("Live Stripe events forbidden")

@app.on_event("startup")
def startup():
    safe_configuration()

@app.get("/health")
def health():
    safe_configuration()
    return {"status": "ok", "stripe_writes_enabled": False, "production_ready": False}

def persist_event(record):
    # Keep PostgreSQL import lazy so pure signature/unit tests need no database.
    import psycopg
    dsn = os.environ.get("DATABASE_URL")
    if not dsn or not dsn.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("DATABASE_URL must point to PostgreSQL")
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        row = conn.execute("""
            INSERT INTO finance_stripe_event_inbox
              (event_id, organization_id, event_type, source_object_id, event_created)
            VALUES (%s, %s, %s, %s, to_timestamp(%s))
            ON CONFLICT (event_id) DO NOTHING RETURNING event_id
        """, (record.event_id,record.organization_id,record.event_type,
              record.source_object_id,record.event_created)).fetchone()
        return row is not None

@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request, stripe_signature: str | None = Header(default=None)):
    safe_configuration()
    # Bound read before decoding so oversized messages cannot exhaust memory.
    if request.headers.get("content-length"):
        try:
            if int(request.headers["content-length"]) > MAX_PAYLOAD_BYTES:
                raise HTTPException(status_code=413, detail="Payload too large")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length")
    payload = await request.body()
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Payload too large")
    try:
        event = verify_stripe_event(payload, stripe_signature or "",
                                    os.environ.get("STRIPE_WEBHOOK_SECRET", ""))
        account_id, merchant_map = resolve_single_merchant(event)
        record = parse_event(event, organization_id=merchant_map[account_id])
    except (InvalidWebhook, ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid sandbox Stripe webhook") from exc
    if record is None:
        return {"received": True, "ignored": True}
    try:
        created = persist_event(record)
    except Exception as exc:
        # Fail with non-2xx; Stripe retries. Never log customer payloads.
        raise HTTPException(status_code=503, detail="Event inbox temporarily unavailable") from exc
    return {"received": True, "duplicate": not created, "queued": created}

@app.get("/finance/overview")
def finance_overview():
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Finance overview disabled until OIDC and tenant-scoped RBAC")
