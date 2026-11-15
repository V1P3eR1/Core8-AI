"""WebSocket auth: legacy bearer is permitted only in local DEV_MODE (P11)."""
import pytest
from starlette.websockets import WebSocketDisconnect

from agents.orchestrator import get_agent
from config import cfg

STATIC = "static-test-token-" + "z" * 24


@pytest.fixture(autouse=True)
def _quiet_agent(monkeypatch, client):
    async def fake_run(self, messages, on_event=None, approval_gate=None, system_context=None):
        await on_event({"type": "done"})
        return "ok", "end_turn"

    monkeypatch.setattr(type(get_agent("leads")), "run", fake_run)
    monkeypatch.setattr(cfg, "bearer_token", STATIC)


def _connects(client, token):
    try:
        with client.websocket_connect(f"/ws/leads?token={token}") as ws:
            ws.receive_json()
        return True
    except WebSocketDisconnect:
        return False


def test_static_bearer_rejected_outside_dev(api, monkeypatch):
    monkeypatch.setattr(cfg, "dev_mode", False)
    assert _connects(api.c, STATIC) is False


def test_static_bearer_allowed_in_dev_only(api, monkeypatch):
    monkeypatch.setattr(cfg, "dev_mode", True)
    assert _connects(api.c, STATIC) is True


def test_jwt_still_accepted_outside_dev(api, monkeypatch):
    monkeypatch.setattr(cfg, "dev_mode", False)
    jwt = api.admin["Authorization"].split(" ", 1)[1]
    assert _connects(api.c, jwt) is True


def test_wrong_or_empty_token_rejected(api, monkeypatch):
    monkeypatch.setattr(cfg, "dev_mode", True)
    assert _connects(api.c, "not-the-token") is False
    assert _connects(api.c, "") is False
