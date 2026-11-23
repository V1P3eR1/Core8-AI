"""Standalone FastAPI HTTP demo for signed intake.

NOT imported by production. Uses a disposable in-memory SQLite database and
synthetic credentials; suitable only for local tests, never public deployment.
"""
import sqlite3
from fastapi import FastAPI, Header, HTTPException, Request
from webhook_receipt_demo import receive_once, setup_receipts
from sqlite_atomic_ingest_demo import setup

app = FastAPI(title="Core8 Offline Webhook Intake Fixture", docs_url=None,
              redoc_url=None, openapi_url=None)
_SECRET = b"synthetic-fixture-only-never-production"
_REGISTRY = {"demo": {"active": True, "tenant_id": "tenant-demo",
                      "source_system": "synthetic-form", "secret": _SECRET}}

@app.post("/offline-fixture/intake")
async def intake(request: Request,
                 x_demo_timestamp: str = Header(default=""),
                 x_demo_signature: str = Header(default=""),
                 x_demo_delivery_id: str = Header(default=""),
                 x_demo_credential_id: str = Header(default="")):
    try:
        timestamp = int(x_demo_timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_timestamp")
    if request.headers.get("content-length"):
        try:
            if int(request.headers["content-length"]) > 65536:
                raise HTTPException(status_code=413, detail="request_too_large")
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid_content_length")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 65536:
            raise HTTPException(status_code=413, detail="request_too_large")
    body = bytes(body)
    # One database per application instance for tests. Never shared with prod.
    conn = request.app.state.fixture_db
    try:
        result = receive_once(
            conn, delivery_id=x_demo_delivery_id, raw_body=body,
            timestamp=timestamp, signature_hex=x_demo_signature,
            credential_id=x_demo_credential_id,
            credential_registry=_REGISTRY,
            now=request.app.state.fixture_now,
            lead_id="synthetic-" + x_demo_delivery_id)
    except (sqlite3.Error, ValueError, TypeError, OverflowError):
        raise HTTPException(status_code=500, detail="fixture_error")
    if result.get("ok"):
        return result
    reason = result.get("reason", "rejected")
    if reason in {"delivery_replayed", "payload_conflict"}:
        raise HTTPException(status_code=409, detail=reason)
    if reason in {"unknown_credential", "signature_mismatch", "invalid_signature",
                  "inactive_credential", "outside_replay_window"}:
        raise HTTPException(status_code=401, detail="unauthorized")
    raise HTTPException(status_code=400, detail=reason)

def create_test_app(*, now):
    # Explicit factory; module import does not create a DB.
    fixture = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    fixture.state.fixture_db = sqlite3.connect(":memory:", check_same_thread=False)
    fixture.state.fixture_now = now
    setup(fixture.state.fixture_db)
    setup_receipts(fixture.state.fixture_db)
    fixture.include_router(app.router)
    return fixture
