import pytest
from starlette.websockets import WebSocketDisconnect

from agents.orchestrator import get_agent
from tests.conftest import INTAKE, SALES


@pytest.fixture
def captured(monkeypatch, client):
    calls = []

    async def fake_run(self, messages, on_event=None, approval_gate=None, system_context=None):
        calls.append({"agent": self.config.id, "system_context": system_context})
        await on_event({"type": "text_delta", "text": "ok"})
        await on_event({"type": "done"})
        return "ok", "end_turn"

    monkeypatch.setattr(type(get_agent("leads")), "run", fake_run)
    return calls


def _token(h):
    return h["Authorization"].split(" ", 1)[1]


def _chat(client, url):
    with client.websocket_connect(url) as ws:
        hello = ws.receive_json()
        ws.send_json({"message": "hi"})
        while ws.receive_json().get("type") != "done":
            pass
        return hello


def test_ws_with_tenant_injects_scoped_context(api, captured):
    owner = api.user("o@t.test")
    tid = api.tenant("T", owner_email="o@t.test")
    aid = api.assessment(tid, owner)
    api.answer(tid, aid, INTAKE, owner)
    api.answer(tid, aid, SALES, owner)

    hello = _chat(api.c, f"/ws/leads?token={_token(owner)}&tenant_id={tid}")
    assert hello["tenant_id"] == tid
    ctx = captured[-1]["system_context"]
    assert "<business_context>" in ctx and "Acme Dental Clinics" in ctx
    assert "Slow lead follow-up" in ctx  # sales domain visible to leads


def test_ws_without_tenant_is_unchanged(api, captured):
    hello = _chat(api.c, f"/ws/leads?token={_token(api.admin)}")
    assert hello["tenant_id"] is None
    assert captured[-1]["system_context"] is None


def test_ws_rejects_tenant_without_membership(api, captured):
    outsider = api.user("x@x.test")
    tid = api.tenant("T")
    with pytest.raises(WebSocketDisconnect) as e:
        with api.c.websocket_connect(f"/ws/leads?token={_token(outsider)}&tenant_id={tid}") as ws:
            ws.receive_json()
    assert e.value.code == 4004
    assert captured == []
