"""WebSocket auth: legacy bearer is permitted only in local DEV_MODE (P11).

Regression tests carried over from PR #22. The behaviour itself is on main
(PR #13); these tests pin it so the static token can never authenticate a
production WebSocket again.
"""
import pytest
from starlette.websockets import WebSocketDisconnect

from agents.orchestrator import get_agent
from config import cfg

STATIC = "static-test-token-" + "z" * 24
UNAUTHENTICATED = 4001


@pytest.fixture(autouse=True)
def _quiet_agent(monkeypatch, client):
    async def fake_run(self, messages, on_event=None, approval_gate=None, system_context=None):
        await on_event({"type": "done"})
        return "ok", "end_turn"

    monkeypatch.setattr(type(get_agent("leads")), "run", fake_run)
    monkeypatch.setattr(cfg, "bearer_token", STATIC)
    monkeypatch.setattr(cfg, "bearer_token_prev", "")


def _hello(client, token):
    """Open the socket and return the first frame (the handshake greeting)."""
    with client.websocket_connect(f"/ws/leads?token={token}") as ws:
        return ws.receive_json()


def _assert_accepted(client, token):
    hello = _hello(client, token)
    assert hello["type"] == "connected", hello
    assert hello["agent"] == "leads"
    # Without a tenant_id the session runs in the internal tenant and names none.
    assert hello["tenant_id"] is None


def _assert_rejected(client, token):
    with pytest.raises(WebSocketDisconnect) as e:
        _hello(client, token)
    assert e.value.code == UNAUTHENTICATED


def test_static_bearer_rejected_outside_dev(api, monkeypatch):
    monkeypatch.setattr(cfg, "dev_mode", False)
    _assert_rejected(api.c, STATIC)


def test_static_bearer_allowed_in_dev_only(api, monkeypatch):
    monkeypatch.setattr(cfg, "dev_mode", True)
    _assert_accepted(api.c, STATIC)


def test_jwt_still_accepted_outside_dev(api, monkeypatch):
    monkeypatch.setattr(cfg, "dev_mode", False)
    jwt = api.admin["Authorization"].split(" ", 1)[1]
    _assert_accepted(api.c, jwt)


@pytest.mark.parametrize("dev_mode", [True, False])
@pytest.mark.parametrize("token", ["not-the-token", ""])
def test_wrong_or_empty_token_rejected(api, monkeypatch, dev_mode, token):
    monkeypatch.setattr(cfg, "dev_mode", dev_mode)
    _assert_rejected(api.c, token)
