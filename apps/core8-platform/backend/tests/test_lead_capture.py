"""Issue #10 — public lead capture: tenant from the form, consent, validation, anti-spam."""

import sqlite3

import pytest

import database
import lead_capture

GOOD = {"name": "Dana Levi", "email": "Dana@Example.com", "company": "Acme",
        "message": "We want a demo", "consent": True}


@pytest.fixture(autouse=True)
def _fresh_limits():
    lead_capture.reset_rate_limits()
    yield
    lead_capture.reset_rate_limits()


CONSENT = "I agree that Core8 may contact me about my enquiry and store my details for that purpose."


def _form(api, tid, h, approve=True, **kw):
    body = {"name": "Website", "consent_text": CONSENT, "locale": "en", **kw}
    r = api.c.post(f"/api/tenants/{tid}/lead-forms", json=body, headers=h)
    assert r.status_code == 201, r.text
    form = r.json()
    assert form["active"] is False  # never live before the text is approved
    if approve:
        ct = form["consent_text"]["id"]
        assert api.c.post(f"/api/tenants/{tid}/consent-texts/{ct}/approve", headers=h).status_code == 200
    return form["form_key"]


def _rows(sql, args=()):
    with sqlite3.connect(database.DB_PATH) as db:
        return db.execute(sql, args).fetchall()


def _shown(api, key):
    """What the website renders before the visitor submits."""
    r = api.c.get(f"/api/public/lead-forms/{key}")
    return r.json()["consent_text_id"] if r.status_code == 200 else "ct_unknown"


def _submit(api, key, body=None, **headers):
    body = dict(body or GOOD)
    body.setdefault("consent_text_id", _shown(api, key))
    return api.c.post(f"/api/public/lead-forms/{key}/submit", json=body, headers=headers)


def test_submission_lands_in_the_forms_tenant_only_with_consent_record(api):
    owner = api.user("owner@acme.test")
    a = api.tenant("Acme", "owner@acme.test")
    b = api.tenant("Beta", "owner@acme.test")
    key = _form(api, a, owner)

    r = _submit(api, key)
    assert r.status_code == 202 and r.json() == {"status": "received"}

    leads = _rows("SELECT tenant_id, name, email, source FROM leads")
    assert leads == [(a, "Dana Levi", "dana@example.com", "web-form:Website")]
    assert not _rows("SELECT 1 FROM leads WHERE tenant_id=?", (b,))
    consents = _rows("SELECT c.tenant_id, t.text, c.consent_sha256, c.ip_hash FROM lead_consents c "
                     "JOIN consent_texts t ON t.id = c.consent_text_id")
    assert len(consents) == 1 and consents[0][:2] == (a, CONSENT)
    import hashlib
    assert consents[0][2] == hashlib.sha256(CONSENT.encode()).hexdigest()
    assert "testclient" not in consents[0][3]  # IP is hashed, not stored raw


def test_request_cannot_choose_the_tenant(api):
    owner = api.user("o@a.test")
    a = api.tenant("A", "o@a.test")
    key = _form(api, a, owner)
    r = _submit(api, key, {**GOOD, "tenant_id": "someone-else"})
    assert r.status_code == 422  # unknown fields are rejected
    assert not _rows("SELECT 1 FROM leads")


def test_consent_is_required(api):
    owner = api.user("o@a.test")
    key = _form(api, api.tenant("A", "o@a.test"), owner)
    assert _submit(api, key, {**GOOD, "consent": False}).status_code == 422
    body = {k: v for k, v in GOOD.items() if k != "consent"}
    assert _submit(api, key, body).status_code == 422
    assert not _rows("SELECT 1 FROM leads")


@pytest.mark.parametrize("patch", [
    {"name": ""}, {"name": "x" * 121}, {"email": "not-an-email"}, {"message": "m" * 2001},
    {"phone": "call me maybe"}, {"email": "", "phone": ""},
])
def test_invalid_input_is_rejected(api, patch):
    owner = api.user("o@a.test")
    key = _form(api, api.tenant("A", "o@a.test"), owner)
    assert _submit(api, key, {**GOOD, **patch}).status_code == 422
    assert not _rows("SELECT 1 FROM leads")


def test_honeypot_is_silently_dropped(api):
    owner = api.user("o@a.test")
    key = _form(api, api.tenant("A", "o@a.test"), owner)
    r = _submit(api, key, {**GOOD, "website": "http://spam.example"})
    assert r.status_code == 202 and r.json() == {"status": "received"}
    assert not _rows("SELECT 1 FROM leads")


def test_per_ip_rate_limit(api):
    owner = api.user("o@a.test")
    key = _form(api, api.tenant("A", "o@a.test"), owner)
    codes = [_submit(api, key).status_code for _ in range(lead_capture.PER_IP_LIMIT + 1)]
    assert codes[:-1] == [202] * lead_capture.PER_IP_LIMIT and codes[-1] == 429


def test_spoofed_forwarded_for_does_not_bypass_rate_limit_by_default(api):
    owner = api.user("o@a.test")
    key = _form(api, api.tenant("A", "o@a.test"), owner)
    codes = [_submit(api, key, **{"X-Forwarded-For": f"10.0.0.{i}"}).status_code
             for i in range(lead_capture.PER_IP_LIMIT + 1)]
    assert codes[-1] == 429


def test_allowed_origins_enforced(api):
    owner = api.user("o@a.test")
    key = _form(api, api.tenant("A", "o@a.test"), owner, allowed_origins=["https://core8-ai.com"])
    assert _submit(api, key, Origin="https://evil.example").status_code == 403
    assert _submit(api, key).status_code == 403  # no Origin header
    assert _submit(api, key, Origin="https://core8-ai.com").status_code == 202


def test_unknown_or_disabled_form_is_404(api):
    owner = api.user("o@a.test")
    tid = api.tenant("A", "o@a.test")
    key = _form(api, tid, owner)
    assert _submit(api, "lf_doesnotexist").status_code == 404
    assert api.c.delete(f"/api/tenants/{tid}/lead-forms/{key}", headers=owner).status_code == 204
    assert _submit(api, key).status_code == 404


def test_only_tenant_owner_manages_forms(api):
    owner = api.user("o@a.test")
    outsider = api.user("x@b.test")
    tid = api.tenant("A", "o@a.test")
    body = {"name": "W", "consent_text": CONSENT}
    assert api.c.post(f"/api/tenants/{tid}/lead-forms", json=body, headers=outsider).status_code == 404
    key = _form(api, tid, owner)
    assert api.c.get(f"/api/tenants/{tid}/lead-forms", headers=outsider).status_code == 404
    assert api.c.delete(f"/api/tenants/{tid}/lead-forms/{key}", headers=outsider).status_code == 404
    listed = api.c.get(f"/api/tenants/{tid}/lead-forms", headers=owner).json()
    assert [f["form_key"] for f in listed] == [key]


def test_form_admin_requires_login(api):
    assert api.c.post("/api/tenants/x/lead-forms", json={"name": "W", "consent_text": CONSENT}).status_code in (401, 403)


def test_no_personal_data_in_logs(api, caplog):
    owner = api.user("o@a.test")
    key = _form(api, api.tenant("A", "o@a.test"), owner)
    with caplog.at_level("DEBUG", logger="core8.lead_capture"):
        _submit(api, key)
    text = caplog.text.lower()
    assert "dana" not in text and "example.com" not in text and "demo" not in text


def test_behind_trusted_proxy_only_proxy_written_ip_counts(api, monkeypatch):
    from config import cfg
    monkeypatch.setattr(cfg, "trust_proxy_headers", True)
    owner = api.user("o@a.test")
    key = _form(api, api.tenant("A", "o@a.test"), owner)
    # Client forges the first X-Forwarded-For hop; nginx appends the real address last.
    codes = [_submit(api, key, **{"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.7"}).status_code
             for i in range(lead_capture.PER_IP_LIMIT + 1)]
    assert codes[-1] == 429
    lead_capture.reset_rate_limits()
    codes = [_submit(api, key, **{"X-Real-IP": "198.51.100.9"}).status_code
             for _ in range(lead_capture.PER_IP_LIMIT + 1)]
    assert codes[-1] == 429


# ── Review on PR #14 (2026-11-14) ─────────────────────────────────────────────

def test_consent_write_failure_leaves_no_orphan_lead(api, monkeypatch):
    owner = api.user("o@a.test")
    key = _form(api, api.tenant("A", "o@a.test"), owner)
    monkeypatch.setattr(lead_capture, "_CONSENT_SQL", "INSERT INTO no_such_table VALUES (?, ?, ?, ?, ?)")
    with pytest.raises(Exception):
        _submit(api, key)
    assert not _rows("SELECT 1 FROM leads")
    assert not _rows("SELECT 1 FROM lead_consents")


def test_every_stored_lead_has_a_consent_record(api):
    owner = api.user("o@a.test")
    key = _form(api, api.tenant("A", "o@a.test"), owner)
    for i in range(3):
        assert _submit(api, key, {**GOOD, "email": f"p{i}@example.com"}).status_code == 202
    orphans = _rows("SELECT l.id FROM leads l LEFT JOIN lead_consents c ON c.lead_id = l.id "
                    "WHERE c.lead_id IS NULL")
    assert orphans == [] and len(_rows("SELECT 1 FROM leads")) == 3


def test_rate_limiter_memory_is_bounded(monkeypatch):
    monkeypatch.setattr(lead_capture, "MAX_TRACKED_KEYS", 100)
    for i in range(5000):
        lead_capture._allow(f"ip:f:{i}", 5, 600.0)
    assert len(lead_capture._hits) <= 100


def test_rate_limits_apply_without_origin_header_and_without_allow_list(api):
    # Origin is not a bot control: spam limits must hold when it is absent or not configured.
    owner = api.user("o@a.test")
    key = _form(api, api.tenant("A", "o@a.test"), owner)  # no allowed_origins
    codes = [_submit(api, key).status_code for _ in range(lead_capture.PER_IP_LIMIT + 1)]
    assert codes[-1] == 429


def test_nginx_overwrites_the_ip_header_the_backend_trusts():
    """TRUST_PROXY_HEADERS=true is only safe because nginx sets X-Real-IP to the socket address
    (overwriting any client value) and the backend is reachable only through nginx."""
    import os
    import re
    app = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    conf = open(os.path.join(app, "nginx", "nginx.conf"), encoding="utf-8").read()
    api_block = re.search(r"location /api/ \{(.*?)\}", conf, re.S).group(1)
    assert re.search(r"proxy_set_header\s+X-Real-IP\s+\$remote_addr;", api_block)
    compose = open(os.path.join(app, "docker-compose.yml"), encoding="utf-8").read()
    backend = compose.split("\n  frontend:")[0]
    assert "TRUST_PROXY_HEADERS=true" in backend
    assert "ports:" not in backend  # not published to the host; only nginx can reach it


# ── Consent evidence (review on PR #14, 2026-11-17) ───────────────────────────

NEW = "Updated: I agree that Core8 may contact me and keep my details for up to 24 months."


def test_form_is_not_live_until_its_consent_text_is_approved(api):
    owner = api.user("o@a.test")
    tid = api.tenant("A", "o@a.test")
    key = _form(api, tid, owner, approve=False)
    assert api.c.get(f"/api/public/lead-forms/{key}").status_code == 404
    assert _submit(api, key, {**GOOD, "consent_text_id": "anything"}).status_code == 404
    assert not _rows("SELECT 1 FROM leads")


def test_public_form_serves_the_exact_approved_text(api):
    owner = api.user("o@a.test")
    key = _form(api, api.tenant("A", "o@a.test"), owner)
    shown = api.c.get(f"/api/public/lead-forms/{key}").json()
    assert shown["consent_text"] == CONSENT and shown["locale"] == "en"
    assert "tenant" not in str(shown).lower()


def test_changing_the_disclosure_creates_a_new_version_and_old_submissions_are_refused(api):
    owner = api.user("o@a.test")
    tid = api.tenant("A", "o@a.test")
    key = _form(api, tid, owner)
    old_id = _shown(api, key)

    r = api.c.put(f"/api/tenants/{tid}/lead-forms/{key}/consent-text",
                  json={"consent_text": NEW, "locale": "en"}, headers=owner)
    assert r.status_code == 200 and r.json()["active"] is False
    new_id = r.json()["consent_text"]["id"]
    assert new_id != old_id
    # Not live again until the new text is approved.
    assert _submit(api, key, {**GOOD, "consent_text_id": old_id}).status_code == 404
    assert api.c.post(f"/api/tenants/{tid}/consent-texts/{new_id}/approve", headers=owner).status_code == 200

    # A visitor who saw the old text cannot be recorded as agreeing to the new one.
    assert _submit(api, key, {**GOOD, "consent_text_id": old_id}).status_code == 409
    assert _submit(api, key, {**GOOD, "consent_text_id": "ct_forged"}).status_code == 409
    assert not _rows("SELECT 1 FROM leads")
    assert _submit(api, key, {**GOOD, "consent_text_id": new_id}).status_code == 202
    assert _rows("SELECT t.text FROM lead_consents c JOIN consent_texts t ON t.id=c.consent_text_id") == [(NEW,)]

    history = api.c.get(f"/api/tenants/{tid}/consent-texts", headers=owner).json()
    assert [h["text"] for h in history] == [CONSENT, NEW]
    assert all(h["approved_by"] for h in history)


def test_consent_text_versions_are_immutable_and_approved_once(api):
    owner = api.user("o@a.test")
    tid = api.tenant("A", "o@a.test")
    key = _form(api, tid, owner)
    ct = _shown(api, key)
    with sqlite3.connect(database.DB_PATH) as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE consent_texts SET text='something else' WHERE id=?", (ct,))
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE consent_texts SET approved_by='someone' WHERE id=?", (ct,))
    assert api.c.post(f"/api/tenants/{tid}/consent-texts/{ct}/approve", headers=owner).status_code == 409


def test_only_the_tenant_owner_approves_and_other_tenants_cannot_see_texts(api):
    owner = api.user("o@a.test")
    editor = api.user("e@a.test")
    outsider = api.user("x@b.test")
    tid = api.tenant("A", "o@a.test")
    api.c.post(f"/api/tenants/{tid}/members", json={"email": "e@a.test", "role": "editor"}, headers=owner)
    key = _form(api, tid, owner, approve=False)
    ct = api.c.get(f"/api/tenants/{tid}/lead-forms", headers=owner).json()[0]["consent_text"]["id"]
    assert api.c.post(f"/api/tenants/{tid}/consent-texts/{ct}/approve", headers=editor).status_code == 403
    assert api.c.post(f"/api/tenants/{tid}/consent-texts/{ct}/approve", headers=outsider).status_code == 404
    assert api.c.get(f"/api/tenants/{tid}/consent-texts", headers=outsider).status_code == 404
    other = api.tenant("B", "x@b.test")
    assert api.c.post(f"/api/tenants/{other}/consent-texts/{ct}/approve", headers=outsider).status_code == 404
    assert api.c.get(f"/api/public/lead-forms/{key}").status_code == 404
