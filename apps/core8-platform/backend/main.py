import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager

import aiosqlite
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import cfg
from database import init_db, get_db
from security.auth import _verify_token
from security.headers import SecurityHeadersMiddleware
from security.approval import is_blocklisted, needs_approval, risk_level
from security.jwt_auth import (
    require_jwt, require_admin,
    create_access_token, create_refresh_token,
    store_refresh_token, consume_refresh_token, revoke_all_refresh_tokens,
    get_user_by_email, create_user, user_count, touch_last_login,
    verify_password,
)
from agents.orchestrator import load_agent, get_agent, list_agents
from tools.leads import register_leads_tools
from tools.calendar_tools import register_calendar_tools
from tools.design import register_design_tools
from tools.plan_artifacts import register_plan_artifact_tools
from tools.instagram_steps import register_instagram_step_tools
from tools.instagram_accounts import register_instagram_account_tools
from tools.instagram_publish import register_instagram_publish_tools
from tools.media_gen import register_media_tools, MEDIA_DIR
from instagram_oauth import router as instagram_oauth_router
from instagram_routes import router as instagram_api_router
from media_routes import router as media_router
from scheduler import start_scheduler
from business_brain.schema import init_brain_schema
from business_brain.routes import router as business_brain_router
from business_brain.access import resolve_access
from business_brain.context import get_agent_context, render_context_block
from token_refresher import start_token_refresher

# In-memory kill switch — starts from env var but can be toggled at runtime
_kill_switch_active: bool = cfg.kill_switch

# Force UTF-8 on stdout/stderr so emoji-bearing tool results (Instagram
# captions) don't crash the logger when output is piped on Windows (cp1252).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, Exception):
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("core8")


def startup_guard():
    public_hosts = {"0.0.0.0", "::", ""}
    if cfg.dev_mode and cfg.bind_host in public_hosts:
        raise RuntimeError(
            f"Refusing to start with DEV_MODE=true AND public bind ({cfg.bind_host}). "
            "Either set DEV_MODE=false or rebind to 127.0.0.1."
        )
    if not cfg.jwt_secret:
        logger.warning("JWT_SECRET is not set — tokens will fail! Set it in .env")
    if not cfg.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY is not set — agents will not work!")


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup_guard()
    register_leads_tools()
    register_calendar_tools()
    register_design_tools()
    register_plan_artifact_tools()
    register_instagram_step_tools()
    register_instagram_account_tools()
    register_instagram_publish_tools()
    register_media_tools()
    await init_db()
    await init_brain_schema()
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM agents") as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                load_agent(dict(row))
    logger.info("Core8-AI started — %d agent(s) loaded", len(list_agents()))
    _is_killed = lambda: _kill_switch_active
    scheduler_task = start_scheduler(_is_killed)
    refresher_task = start_token_refresher(_is_killed)
    yield
    scheduler_task.cancel()
    refresher_task.cancel()
    for t in (scheduler_task, refresher_task):
        try:
            await t
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Core8-AI", version="0.1.0", lifespan=lifespan)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(instagram_oauth_router)
app.include_router(instagram_api_router)
app.include_router(media_router)
app.include_router(business_brain_router)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")


# ── REST endpoints ────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "kill_switch": _kill_switch_active}


# ── Auth endpoints ────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    setup_key: str = ""  # required when no users exist yet (first-time setup)


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


@app.post("/api/auth/setup")
async def setup_first_user(req: RegisterRequest):
    """One-time endpoint to create the first admin. Disabled once any user exists."""
    if await user_count() > 0:
        raise HTTPException(status_code=403, detail="Setup already complete")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    user = await create_user(req.email, req.password, role="admin")
    access = create_access_token(user["id"], user["email"], user["role"])
    raw_refresh, refresh_hash = create_refresh_token()
    await store_refresh_token(user["id"], refresh_hash)
    return {"access_token": access, "refresh_token": raw_refresh, "user": user}


@app.post("/api/auth/login")
async def login(req: LoginRequest):
    user = await get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    await touch_last_login(user["id"])
    access = create_access_token(user["id"], user["email"], user["role"])
    raw_refresh, refresh_hash = create_refresh_token()
    await store_refresh_token(user["id"], refresh_hash)
    return {
        "access_token": access,
        "refresh_token": raw_refresh,
        "user": {"id": user["id"], "email": user["email"], "role": user["role"]},
    }


@app.post("/api/auth/refresh")
async def refresh_token(req: RefreshRequest):
    user = await consume_refresh_token(req.refresh_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    access = create_access_token(user["id"], user["email"], user["role"])
    raw_refresh, refresh_hash = create_refresh_token()
    await store_refresh_token(user["id"], refresh_hash)
    return {"access_token": access, "refresh_token": raw_refresh}


@app.post("/api/auth/logout", dependencies=[Depends(require_jwt)])
async def logout(payload: dict = Depends(require_jwt)):
    await revoke_all_refresh_tokens(payload["sub"])
    return {"status": "logged_out"}


@app.get("/api/auth/me", dependencies=[Depends(require_jwt)])
async def me(payload: dict = Depends(require_jwt)):
    return {"id": payload["sub"], "email": payload["email"], "role": payload["role"]}


@app.post("/api/auth/register", dependencies=[Depends(require_jwt)])
async def register_user(req: RegisterRequest, payload: dict = Depends(require_jwt)):
    """Admin-only: create additional user accounts."""
    require_admin(payload)
    if await get_user_by_email(req.email):
        raise HTTPException(status_code=409, detail="Email already registered")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    user = await create_user(req.email, req.password)
    return {"id": user["id"], "email": user["email"], "role": user["role"]}


# ── Admin endpoints ───────────────────────────────────────────────────────────

class KillSwitchRequest(BaseModel):
    active: bool


@app.post("/api/admin/kill-switch", dependencies=[Depends(require_jwt)])
async def set_kill_switch(req: KillSwitchRequest):
    global _kill_switch_active
    _kill_switch_active = req.active
    logger.warning("Kill switch set to %s", _kill_switch_active)
    return {"kill_switch": _kill_switch_active}


@app.get("/api/admin/security-status", dependencies=[Depends(require_jwt)])
async def security_status():
    return {
        "kill_switch": _kill_switch_active,
        "approval_mode": cfg.approval_mode,
        "tool_blocklist": cfg.tool_blocklist,
        "agent_count": len(list_agents()),
        "bearer_rotation_active": bool(cfg.bearer_token_prev),
    }


@app.get("/api/agents", dependencies=[Depends(require_jwt)])
async def get_agents():
    return [
        {"id": a.config.id, "name": a.config.name, "description": a.config.description}
        for a in list_agents()
    ]


class CreateAgentRequest(BaseModel):
    name: str
    description: str = ""
    system_prompt: str = ""
    model: str = "claude-sonnet-4-6"


@app.post("/api/agents", dependencies=[Depends(require_jwt)])
async def create_agent(req: CreateAgentRequest):
    agent_id = req.name.lower().replace(" ", "-") + "-" + uuid.uuid4().hex[:6]
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "INSERT INTO agents (id, name, description, model, system_prompt) VALUES (?,?,?,?,?)",
            (agent_id, req.name, req.description, req.model, req.system_prompt),
        )
        await db.commit()
        async with db.execute("SELECT * FROM agents WHERE id=?", (agent_id,)) as cur:
            row = await cur.fetchone()
    agent = load_agent(dict(row))
    return {"id": agent.config.id, "name": agent.config.name}


@app.get("/api/agents/{agent_id}/conversations", dependencies=[Depends(require_jwt)])
async def get_agent_conversations(agent_id: str):
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        # Return conversations that have at least one message, most recent first
        async with db.execute(
            """
            SELECT c.id, c.created_at,
                   COUNT(m.id) as message_count,
                   MAX(m.created_at) as last_message_at,
                   (SELECT content FROM messages
                    WHERE conversation_id = c.id AND role = 'user'
                    ORDER BY created_at ASC LIMIT 1) as preview
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE c.agent_id = ?
            GROUP BY c.id
            HAVING message_count > 0
            ORDER BY last_message_at DESC
            LIMIT 50
            """,
            (agent_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


@app.get("/api/conversations/{conversation_id}/messages", dependencies=[Depends(require_jwt)])
async def get_messages(conversation_id: str):
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at",
            (conversation_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws/{agent_id}")
async def websocket_endpoint(websocket: WebSocket, agent_id: str):
    token = websocket.query_params.get("token", "")
    # Accept either a valid JWT access token or the legacy bearer token (dev fallback)
    ws_user = None
    try:
        from security.jwt_auth import decode_access_token
        ws_user = decode_access_token(token)
    except Exception:
        # Fall back to legacy bearer token for local dev convenience
        if not _verify_token(token):
            await websocket.close(code=4001)
            return

    # Optional Business Brain context: requires a JWT user who has access to the tenant.
    tenant_id = websocket.query_params.get("tenant_id")
    tenant_access = None
    if tenant_id:
        if ws_user is None or ws_user.get("type") != "access":
            await websocket.close(code=4001)
            return
        tenant_access = await resolve_access(tenant_id, ws_user)
        if tenant_access is None:
            await websocket.close(code=4004)
            return

    await websocket.accept()

    if _kill_switch_active:
        await websocket.send_json({"type": "error", "message": "Kill switch is active. Agent is paused."})
        await websocket.close()
        return

    agent = get_agent(agent_id)
    if not agent:
        await websocket.send_json({"type": "error", "message": f"Agent '{agent_id}' not found"})
        await websocket.close()
        return

    conversation_id = str(uuid.uuid4())
    async with get_db() as db:
        await db.execute(
            "INSERT INTO conversations (id, agent_id) VALUES (?,?)",
            (conversation_id, agent_id),
        )
        await db.commit()

    await websocket.send_json({"type": "connected", "conversation_id": conversation_id, "agent": agent_id,
                               "tenant_id": tenant_access.tenant_id if tenant_access else None})
    logger.info("WebSocket connected: agent=%s conv=%s", agent_id, conversation_id)

    history: list[dict] = []
    # Incoming messages from client (user text + approval responses)
    incoming: asyncio.Queue[dict | None] = asyncio.Queue()
    # Pending approval futures keyed by request_id
    approval_futures: dict[str, asyncio.Future] = {}

    async def receiver():
        """Pump all incoming WS frames into the queue; None signals disconnect."""
        try:
            while True:
                data = await websocket.receive_json()
                await incoming.put(data)
        except WebSocketDisconnect:
            await incoming.put(None)
        except Exception:
            await incoming.put(None)

    async def approval_gate(tool_name: str, tool_input: dict) -> bool:
        request_id = str(uuid.uuid4())
        await websocket.send_json({
            "type": "tool_approval_request",
            "request_id": request_id,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "risk": risk_level(tool_name),
        })
        loop = asyncio.get_event_loop()
        fut: asyncio.Future = loop.create_future()
        approval_futures[request_id] = fut
        try:
            return await asyncio.wait_for(asyncio.shield(fut), timeout=120.0)
        except asyncio.TimeoutError:
            logger.warning("Approval timeout for tool %s — denying", tool_name)
            return False
        finally:
            approval_futures.pop(request_id, None)

    receiver_task = asyncio.create_task(receiver())

    try:
        while True:
            data = await incoming.get()
            if data is None:
                break  # client disconnected

            # Route approval responses to waiting futures
            if data.get("type") == "tool_approval_response":
                req_id = data.get("request_id", "")
                fut = approval_futures.get(req_id)
                if fut and not fut.done():
                    fut.set_result(data.get("approved", False))
                continue

            user_message = data.get("message", "").strip()
            if not user_message:
                continue

            if _kill_switch_active:
                await websocket.send_json({"type": "error", "message": "Kill switch is active."})
                continue

            async with get_db() as db:
                await db.execute(
                    "INSERT INTO messages (id, conversation_id, role, content) VALUES (?,?,?,?)",
                    (str(uuid.uuid4()), conversation_id, "user", user_message),
                )
                await db.commit()

            history.append({"role": "user", "content": user_message})
            full_response = ""

            async def on_event(event: dict):
                nonlocal full_response
                if event["type"] == "text_delta":
                    full_response += event["text"]
                await websocket.send_json(event)

            gate = approval_gate if cfg.approval_mode != "off" else None
            system_context = None
            if tenant_access is not None:
                # Re-read each turn so Brain updates and scope changes apply immediately.
                ctx = await get_agent_context(tenant_access.repo, agent_id)
                system_context = render_context_block(ctx)
            await agent.run(history, on_event=on_event, approval_gate=gate, system_context=system_context)

            if full_response:
                history.append({"role": "assistant", "content": full_response})
                async with get_db() as db:
                    await db.execute(
                        "INSERT INTO messages (id, conversation_id, role, content) VALUES (?,?,?,?)",
                        (str(uuid.uuid4()), conversation_id, "assistant", full_response),
                    )
                    await db.commit()

    except Exception as e:
        logger.error("WebSocket error: %s", e)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        receiver_task.cancel()
        logger.info("WebSocket disconnected: conv=%s", conversation_id)
