"""Dashboard-managed credentials (social/keystore.py): encrypted at rest, never
echoed, switch the LLM provider to live without a restart, admin-only."""

import pytest

from social import keystore as store
from social.db import fetch_one
from social.providers.llm import llm
from tests.conftest import Api

FAKE_KEY = "sk-ant-api03-" + "A" * 60  # format-valid, not a real key


def _social(client):
    api = Api(client)
    return api


def test_status_reports_env_fallback_without_exposing_value(client):
    api = _social(client)
    r = client.get("/api/social/secrets", headers=api.admin)
    assert r.status_code == 200, r.text
    body = r.json()
    item = body["items"]["anthropic_api_key"]
    # conftest sets ANTHROPIC_API_KEY=test-key-not-real → env fallback, mock mode
    assert item["configured"] is True and item["source"] == "env"
    assert "test-key-not-real" not in r.text
    assert body["llm_mode"] == "mock"
    assert body["encryption_ready"] is True


def test_put_encrypts_and_switches_llm_to_live_then_delete_restores(client):
    api = _social(client)
    assert llm.mode == "mock"
    r = client.put("/api/social/secrets/anthropic_api_key", json={"value": FAKE_KEY}, headers=api.admin)
    assert r.status_code == 200, r.text
    item = r.json()["item"]
    assert item["source"] == "db" and item["hint"] == "…AAAA" and item["updated_by"] == "admin@core8.test"
    assert FAKE_KEY not in r.text
    # stored ciphertext, not plaintext
    import asyncio
    row = asyncio.run(fetch_one("SELECT value FROM sm_settings WHERE key='secret:anthropic_api_key'"))
    assert FAKE_KEY not in row["value"] and '"enc"' in row["value"]
    # provider flips to live immediately (no restart) and reads the DB value
    assert r.json()["llm_mode"] == "live"
    assert llm.mode == "live" and store.cached("anthropic_api_key") == FAKE_KEY
    # audit log carries only the hint
    log = client.get("/api/social/audit", headers=api.admin)
    if log.status_code == 200:
        assert FAKE_KEY not in log.text
    # delete → env fallback → mock again
    r = client.delete("/api/social/secrets/anthropic_api_key", headers=api.admin)
    assert r.status_code == 200 and r.json()["item"]["source"] == "env"
    assert llm.mode == "mock"


@pytest.mark.parametrize("bad,msg", [
    ("sk-ant-usr-" + "x" * 80, "לא מפתח API"),
    (FAKE_KEY + FAKE_KEY, "יותר מפעם אחת"),
    ("hello", "פורמט"),
    ("   ", "ריק"),
])
def test_put_rejects_wrong_or_double_pasted_keys(client, bad, msg):
    api = _social(client)
    r = client.put("/api/social/secrets/anthropic_api_key", json={"value": bad}, headers=api.admin)
    assert r.status_code in (400, 422), r.text
    if r.status_code == 400:
        assert msg in r.json()["detail"]
    assert llm.mode == "mock"


def test_whitespace_and_newlines_are_stripped(client):
    api = _social(client)
    r = client.put("/api/social/secrets/anthropic_api_key", json={"value": f"  {FAKE_KEY}\n"}, headers=api.admin)
    assert r.status_code == 200, r.text
    assert store.cached("anthropic_api_key") == FAKE_KEY
    client.delete("/api/social/secrets/anthropic_api_key", headers=api.admin)


def test_meta_credentials_enable_connect_button(client):
    api = _social(client)
    assert client.get("/api/social/instagram/status", headers=api.admin).json()["app_configured"] is False
    r = client.put("/api/social/secrets/meta_app_id", json={"value": "123456789012345"}, headers=api.admin)
    assert r.status_code == 200, r.text
    r = client.put("/api/social/secrets/meta_app_secret", json={"value": "a" * 32}, headers=api.admin)
    assert r.status_code == 200, r.text
    assert client.get("/api/social/instagram/status", headers=api.admin).json()["app_configured"] is True
    r = client.post("/api/social/instagram/connect-url", headers=api.admin)
    assert r.status_code == 200 and "client_id=123456789012345" in r.json()["connect_url"]
    assert "a" * 32 not in r.json()["connect_url"]
    client.delete("/api/social/secrets/meta_app_id", headers=api.admin)
    client.delete("/api/social/secrets/meta_app_secret", headers=api.admin)


def test_non_admin_is_forbidden(client):
    api = _social(client)
    user = api.user("viewer@core8.test")
    assert client.get("/api/social/secrets", headers=user).status_code == 403
    assert client.put("/api/social/secrets/anthropic_api_key", json={"value": FAKE_KEY}, headers=user).status_code == 403
    assert client.get("/api/social/secrets").status_code == 401


def test_unknown_secret_name_404(client):
    api = _social(client)
    assert client.put("/api/social/secrets/other", json={"value": "x"}, headers=api.admin).status_code == 404


def test_anthropic_test_endpoint_classifies_errors_without_network(client, monkeypatch):
    """The test call is mocked: a 401 from the SDK must come back as a readable Hebrew message."""
    api = _social(client)

    class FakeErr(Exception):
        status_code = 401

    class FakeMessages:
        async def create(self, **kw):
            raise FakeErr("invalid x-api-key: should-not-leak")

    class FakeClient:
        def __init__(self, api_key):
            assert api_key == FAKE_KEY
            self.messages = FakeMessages()

    import anthropic
    monkeypatch.setattr(anthropic, "AsyncAnthropic", FakeClient)
    r = client.post("/api/social/secrets/anthropic_api_key/test", json={"value": FAKE_KEY}, headers=api.admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is False and body["status_code"] == 401 and "401" in body["message"]
    assert "should-not-leak" not in r.text
    # a candidate value is tested but never stored
    assert client.get("/api/social/secrets", headers=api.admin).json()["items"]["anthropic_api_key"]["source"] == "env"


def test_anthropic_test_explains_monthly_usage_cap(client, monkeypatch):
    """Seen in production 2026-11-20: a valid key + account spend cap → 400 'usage limits'."""
    api = _social(client)

    class CapErr(Exception):
        status_code = 400

    class FakeMessages:
        async def create(self, **kw):
            raise CapErr("Error code: 400 - You have reached your specified API usage limits. You will regain access on 2026-12-01")

    class FakeClient:
        def __init__(self, api_key):
            self.messages = FakeMessages()

    import anthropic
    monkeypatch.setattr(anthropic, "AsyncAnthropic", FakeClient)
    r = client.post("/api/social/secrets/anthropic_api_key/test", json={"value": FAKE_KEY}, headers=api.admin)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False and body["error"] == "usage_limit" and "מגבלת השימוש החודשית" in body["message"]
