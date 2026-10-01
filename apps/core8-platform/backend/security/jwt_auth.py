"""
JWT-based authentication.

Access tokens:  short-lived (default 15 min), passed in Authorization: Bearer header.
Refresh tokens: long-lived (default 7 days), stored hashed in DB, exchanged for new access tokens.
"""

import hashlib
import hmac
import uuid
import datetime
import logging

import jwt
import bcrypt
import aiosqlite
from fastapi import Request, HTTPException

from config import cfg
from database import get_db

logger = logging.getLogger("core8.auth")

_ALGORITHM = "HS256"


# ── Password helpers ─────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── Token generation ─────────────────────────────────────────────────────────

def _require_secret() -> str:
    if not cfg.jwt_secret:
        raise RuntimeError("JWT_SECRET is not configured")
    return cfg.jwt_secret


def create_access_token(user_id: str, email: str, role: str) -> str:
    now = datetime.datetime.utcnow()
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + datetime.timedelta(minutes=cfg.jwt_access_ttl_minutes),
        "type": "access",
    }
    return jwt.encode(payload, _require_secret(), algorithm=_ALGORITHM)


def create_refresh_token() -> tuple[str, str]:
    """Return (raw_token, hash_for_db)."""
    raw = str(uuid.uuid4())
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, token_hash


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, _require_secret(), algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ── DB helpers ───────────────────────────────────────────────────────────────

async def get_user_by_email(email: str) -> dict | None:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE email=?", (email,)) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def get_user_by_id(user_id: str) -> dict | None:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE id=?", (user_id,)) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None


async def create_user(email: str, password: str, role: str = "operator") -> dict:
    user_id = str(uuid.uuid4())
    password_hash = hash_password(password)
    async with get_db() as db:
        await db.execute(
            "INSERT INTO users (id, email, password_hash, role) VALUES (?,?,?,?)",
            (user_id, email, password_hash, role),
        )
        await db.commit()
    return {"id": user_id, "email": email, "role": role}


async def user_count() -> int:
    async with get_db() as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            row = await cur.fetchone()
    return row[0] if row else 0


async def store_refresh_token(user_id: str, token_hash: str):
    expires_at = (
        datetime.datetime.utcnow() + datetime.timedelta(days=cfg.jwt_refresh_ttl_days)
    ).isoformat()
    async with get_db() as db:
        await db.execute(
            "INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at) VALUES (?,?,?,?)",
            (str(uuid.uuid4()), user_id, token_hash, expires_at),
        )
        await db.commit()


async def consume_refresh_token(raw_token: str) -> dict | None:
    """Validate + delete the refresh token; return the owning user or None."""
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    now = datetime.datetime.utcnow().isoformat()
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT rt.id as rt_id, u.*
               FROM refresh_tokens rt
               JOIN users u ON u.id = rt.user_id
               WHERE rt.token_hash=? AND rt.expires_at > ?""",
            (token_hash, now),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        # Rotate: delete used token
        await db.execute("DELETE FROM refresh_tokens WHERE id=?", (row["rt_id"],))
        await db.commit()
    return dict(row)


async def revoke_all_refresh_tokens(user_id: str):
    async with get_db() as db:
        await db.execute("DELETE FROM refresh_tokens WHERE user_id=?", (user_id,))
        await db.commit()


async def touch_last_login(user_id: str):
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET last_login=datetime('now') WHERE id=?", (user_id,)
        )
        await db.commit()


# ── FastAPI dependency ───────────────────────────────────────────────────────

async def require_jwt(request: Request) -> dict:
    """FastAPI dependency — returns decoded token payload."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = auth[len("Bearer "):]
    payload = decode_access_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    return payload


def require_admin(payload: dict = None):
    """Use after require_jwt to enforce admin role."""
    if payload and payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
