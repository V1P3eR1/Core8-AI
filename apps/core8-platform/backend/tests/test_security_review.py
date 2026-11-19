"""Security review pass (2026-11-19): admin-only global controls, login lockout, setup key,
no public API docs or exception text outside dev mode."""

import pytest

import main
from config import cfg
from security import auth


@pytest.fixture(autouse=True)
def _fresh_lockouts():
    auth._fail_times.clear()
    auth._lockout_until.clear()
    yield
    auth._fail_times.clear()
    auth._lockout_until.clear()


def test_only_admins_control_the_kill_switch(api):
    user = api.user("member@t.test")
    assert api.c.post("/api/admin/kill-switch", json={"active": True}, headers=user).status_code == 403
    assert api.c.get("/api/health").json()["kill_switch"] is False
    assert api.c.get("/api/admin/security-status", headers=user).status_code == 403
    try:
        assert api.c.post("/api/admin/kill-switch", json={"active": True}, headers=api.admin).status_code == 200
        assert api.c.get("/api/health").json()["kill_switch"] is True
        # A non-admin cannot switch the emergency stop back off.
        assert api.c.post("/api/admin/kill-switch", json={"active": False}, headers=user).status_code == 403
        assert api.c.get("/api/health").json()["kill_switch"] is True
    finally:
        api.c.post("/api/admin/kill-switch", json={"active": False}, headers=api.admin)
    assert api.c.get("/api/admin/security-status", headers=api.admin).status_code == 200


def test_only_admins_create_global_agents(api):
    user = api.user("member@t.test")
    before = len(api.c.get("/api/agents", headers=user).json())
    r = api.c.post("/api/agents", json={"name": "Rogue", "system_prompt": "x"}, headers=user)
    assert r.status_code == 403
    assert len(api.c.get("/api/agents", headers=user).json()) == before
    assert api.c.post("/api/agents", json={"name": "Ok"}, headers=api.admin).status_code == 200


def test_admin_endpoints_require_login(client):
    assert client.post("/api/admin/kill-switch", json={"active": True}).status_code in (401, 403)
    assert client.post("/api/agents", json={"name": "x"}).status_code in (401, 403)


def test_require_admin_rejects_missing_payload():
    from fastapi import HTTPException
    from security.jwt_auth import require_admin
    with pytest.raises(HTTPException):
        require_admin(None)
    with pytest.raises(HTTPException):
        require_admin({"role": "user"})
    require_admin({"role": "admin"})


def test_login_locks_out_after_repeated_failures(api):
    api.user("victim@t.test")
    bad = {"email": "victim@t.test", "password": "wrong-password"}
    codes = [api.c.post("/api/auth/login", json=bad).status_code for _ in range(auth._N)]
    assert set(codes) == {401}
    r = api.c.post("/api/auth/login", json=bad)
    assert r.status_code == 429 and "Retry-After" in r.headers
    # Even the right password is refused while locked out.
    good = {"email": "victim@t.test", "password": "user-pass-123"}
    assert api.c.post("/api/auth/login", json=good).status_code == 429


def test_successful_logins_are_not_throttled(api):
    api.user("busy@t.test")
    good = {"email": "busy@t.test", "password": "user-pass-123"}
    assert all(api.c.post("/api/auth/login", json=good).status_code == 200 for _ in range(auth._N + 5))


def test_first_admin_setup_needs_setup_key_outside_dev_mode(client, monkeypatch):
    monkeypatch.setattr(cfg, "dev_mode", False)
    body = {"email": "first@core8.test", "password": "admin-pass-123"}
    monkeypatch.setattr(cfg, "setup_key", "")
    assert client.post("/api/auth/setup", json=body).status_code == 403   # not configured -> closed
    monkeypatch.setattr(cfg, "setup_key", "s3tup-" + "k" * 30)
    assert client.post("/api/auth/setup", json=body).status_code == 403
    assert client.post("/api/auth/setup", json={**body, "setup_key": "guess"}).status_code == 403
    r = client.post("/api/auth/setup", json={**body, "setup_key": cfg.setup_key})
    assert r.status_code == 200 and r.json()["user"]["role"] == "admin"
    # One-time only.
    assert client.post("/api/auth/setup", json={**body, "email": "b@c.test", "setup_key": cfg.setup_key}).status_code == 403


def test_setup_key_guessing_is_locked_out(client, monkeypatch):
    monkeypatch.setattr(cfg, "dev_mode", False)
    monkeypatch.setattr(cfg, "setup_key", "s3tup-" + "k" * 30)
    body = {"email": "first@core8.test", "password": "admin-pass-123", "setup_key": "guess"}
    for _ in range(auth._N):
        assert client.post("/api/auth/setup", json=body).status_code == 403
    assert client.post("/api/auth/setup", json={**body, "setup_key": cfg.setup_key}).status_code == 429


def test_api_docs_are_only_served_in_dev_mode():
    assert main._docs == {}  # tests run with DEV_MODE=true
    import importlib
    import subprocess
    import sys
    import os
    code = ("import os; os.environ['DEV_MODE']='false'; os.environ['JWT_SECRET']='x'*40; "
            "os.environ['BIND_HOST']='127.0.0.1'; import main; "
            "print(sorted(r.path for r in main.app.routes if r.path in ('/docs','/redoc','/openapi.json')))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         env={**os.environ, "DEV_MODE": "false"})
    assert out.stdout.strip().splitlines()[-1] == "[]", out.stderr[-500:]
    del importlib


def test_websocket_errors_do_not_leak_exception_text(api, monkeypatch):
    from agents.orchestrator import get_agent

    async def boom(self, *a, **kw):
        raise RuntimeError("secret internal path /data/core8.db")

    monkeypatch.setattr(type(get_agent("general")), "run", boom)
    token = api.admin["Authorization"].split(" ", 1)[1]
    with api.c.websocket_connect(f"/ws/general?token={token}") as ws:
        ws.receive_json()
        ws.send_json({"message": "hi"})
        event = ws.receive_json()
    assert event == {"type": "error", "message": "Internal error"}
