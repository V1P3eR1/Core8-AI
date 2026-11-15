"""CORE8-005: one shared database, every operational row labelled by tenant."""

import asyncio
import os
import sqlite3

import pytest
from cryptography.fernet import Fernet

import database
from tenancy import INTERNAL_TENANT_ID, TenantContextError, use_tenant
from tools import calendar_tools, design, instagram_accounts, instagram_api, instagram_publish
from tools import leads, media_gen, plan_artifacts

A, B = "tenant-a", "tenant-b"
PAST = "2020-01-01T09:00:00"


def run(coro):
    return asyncio.run(coro)


def as_tenant(tenant_id, fn, *args, **kwargs):
    async def _go():
        with use_tenant(tenant_id):
            return await fn(*args, **kwargs)
    return run(_go())


@pytest.fixture
def tenants(client):
    """Two client tenants in the shared DB (the app fixture has already created the schema)."""
    con = sqlite3.connect(database.DB_PATH)
    con.executemany("INSERT INTO tenants (id, name, created_by) VALUES (?, ?, 'test')", [(A, "A"), (B, "B")])
    con.commit()
    con.close()
    return A, B


@pytest.fixture
def enc_key(monkeypatch):
    from config import cfg
    monkeypatch.setattr(cfg, "ig_token_enc_key", Fernet.generate_key().decode())


# ── No tenant context → refuse ───────────────────────────────────────────────

@pytest.mark.parametrize("call", [
    lambda: leads.list_leads(),
    lambda: leads.create_lead(name="x"),
    lambda: calendar_tools.list_events(),
    lambda: design.list_design_projects(),
    lambda: plan_artifacts.list_content_plans(),
    lambda: instagram_publish.list_scheduled_posts(),
    lambda: media_gen.list_media_assets(),
    lambda: instagram_accounts.get_ig_account(),
])
def test_tools_refuse_without_tenant_context(client, call):
    with pytest.raises(TenantContextError):
        run(call())


# ── Per-tool isolation ───────────────────────────────────────────────────────

def test_leads_isolated(tenants):
    lead = as_tenant(A, leads.create_lead, name="Dana", email="dana@a.test", company="A Co")
    assert [x["id"] for x in as_tenant(A, leads.list_leads)] == [lead["id"]]
    assert as_tenant(B, leads.list_leads) == []
    assert as_tenant(B, leads.search_leads, "Dana") == []
    assert "error" in as_tenant(B, leads.get_lead, lead["id"])
    assert "error" in as_tenant(B, leads.update_lead, lead["id"], status="won")
    assert "error" in as_tenant(B, leads.add_note, lead["id"], "hijack")
    assert as_tenant(A, leads.get_lead, lead["id"])["status"] == "new"


def test_events_isolated(tenants):
    ev = as_tenant(A, calendar_tools.create_event, "Demo", "2030-01-01T10:00:00", "2030-01-01T11:00:00")
    assert len(as_tenant(A, calendar_tools.list_events)) == 1
    assert as_tenant(B, calendar_tools.list_events) == []
    assert "error" in as_tenant(B, calendar_tools.update_event, ev["id"], title="x")
    assert "error" in as_tenant(B, calendar_tools.delete_event, ev["id"])
    assert len(as_tenant(A, calendar_tools.list_events)) == 1


def test_design_docs_isolated_and_unique_per_tenant(tenants):
    as_tenant(A, design.write_design_doc, "site", "brief.md", "A's brief")
    as_tenant(B, design.write_design_doc, "site", "brief.md", "B's brief")  # same path, other tenant
    assert as_tenant(A, design.read_design_doc, "site", "brief.md")["content"] == "A's brief"
    assert as_tenant(B, design.read_design_doc, "site", "brief.md")["content"] == "B's brief"
    as_tenant(B, design.delete_design_doc, "site", "brief.md")
    assert as_tenant(A, design.read_design_doc, "site", "brief.md")["content"] == "A's brief"


def test_content_plans_and_artifacts_isolated(tenants):
    plan = as_tenant(A, plan_artifacts.create_content_plan, "fitness")
    as_tenant(A, plan_artifacts.save_plan_artifact, plan["id"], "niche", "A's niche research")
    assert "error" in as_tenant(B, plan_artifacts.get_content_plan, plan["id"])
    assert "error" in as_tenant(B, plan_artifacts.save_plan_artifact, plan["id"], "niche", "overwrite")
    assert "error" in as_tenant(B, plan_artifacts.read_plan_artifact, plan["id"], "niche")
    assert "error" in as_tenant(B, plan_artifacts.update_content_plan, plan["id"], status="active")
    assert as_tenant(B, plan_artifacts.list_content_plans) == []
    assert as_tenant(A, plan_artifacts.read_plan_artifact, plan["id"], "niche")["content"] == "A's niche research"


def test_scheduled_posts_isolated(tenants):
    post = as_tenant(A, instagram_publish.queue_post, PAST, media_url="https://x/a.jpg")
    assert as_tenant(B, instagram_publish.list_scheduled_posts) == []
    assert "error" in as_tenant(B, instagram_publish.cancel_scheduled_post, post["id"])
    # B cannot attach a post to A's content plan.
    plan = as_tenant(A, plan_artifacts.create_content_plan, "x")
    assert "error" in as_tenant(B, instagram_publish.queue_post, PAST, media_url="https://x/b.jpg",
                                plan_id=plan["id"])


def test_media_assets_isolated_and_stored_per_tenant(tenants, tmp_path, monkeypatch):
    monkeypatch.setattr(media_gen, "MEDIA_DIR", str(tmp_path))
    asset = as_tenant(A, media_gen.save_media_asset, b"img", "jpg", "upload", "image")
    assert asset["filename"].startswith(f"{A}/")
    assert os.path.exists(tmp_path / asset["filename"])
    assert as_tenant(B, media_gen.list_media_assets) == []
    assert len(as_tenant(A, media_gen.list_media_assets)) == 1


def test_instagram_account_one_per_tenant(tenants, enc_key):
    as_tenant(A, instagram_accounts.save_ig_account, "ig-a", "fb-a", "a_user", "tok-a", None)
    assert as_tenant(B, instagram_accounts.get_ig_account) is None
    as_tenant(B, instagram_accounts.save_ig_account, "ig-b", "fb-b", "b_user", "tok-b", None)
    assert as_tenant(A, instagram_accounts.get_ig_account)["access_token"] == "tok-a"
    assert as_tenant(B, instagram_accounts.get_ig_account)["access_token"] == "tok-b"


# ── Background jobs ──────────────────────────────────────────────────────────

def test_scheduler_publishes_each_post_with_its_own_tenants_account(tenants, enc_key, monkeypatch):
    import scheduler
    as_tenant(A, instagram_accounts.save_ig_account, "ig-a", "fb-a", "a_user", "tok-a", None)
    as_tenant(B, instagram_accounts.save_ig_account, "ig-b", "fb-b", "b_user", "tok-b", None)
    pa = as_tenant(A, instagram_publish.queue_post, PAST, media_url="https://x/a.jpg")
    pb = as_tenant(B, instagram_publish.queue_post, PAST, media_url="https://x/b.jpg")
    calls = []

    async def fake_publish(**kw):
        calls.append((kw["ig_user_id"], kw["token"], kw["media_url"]))
        return f"media-{kw['ig_user_id']}"

    monkeypatch.setattr(scheduler.instagram_api, "publish_post", fake_publish)
    run(scheduler.run_scheduler_tick(lambda: False))
    assert sorted(calls) == [("ig-a", "tok-a", "https://x/a.jpg"), ("ig-b", "tok-b", "https://x/b.jpg")]
    a_posts = as_tenant(A, instagram_publish.list_scheduled_posts)
    assert [(p["id"], p["status"], p["ig_media_id"]) for p in a_posts] == [(pa["id"], "published", "media-ig-a")]
    assert as_tenant(B, instagram_publish.list_scheduled_posts)[0]["id"] == pb["id"]


def test_scheduler_skips_tenant_without_account_and_caps_per_tenant(tenants, enc_key, monkeypatch):
    import scheduler
    as_tenant(A, instagram_accounts.save_ig_account, "ig-a", "fb-a", "a_user", "tok-a", None)
    for _ in range(3):
        as_tenant(A, instagram_publish.queue_post, PAST, media_url="https://x/a.jpg")
    as_tenant(B, instagram_publish.queue_post, PAST, media_url="https://x/b.jpg")  # B: no account
    published = []

    async def fake_publish(**kw):
        published.append(kw["ig_user_id"])
        return "m"

    monkeypatch.setattr(scheduler.instagram_api, "publish_post", fake_publish)
    monkeypatch.setattr(scheduler, "DAILY_PUBLISH_CAP", 2)
    run(scheduler.run_scheduler_tick(lambda: False))
    assert published == ["ig-a", "ig-a"]          # cap applies to A only
    assert as_tenant(B, instagram_publish.list_scheduled_posts)[0]["status"] == "pending"


def test_token_refresher_refreshes_each_tenant(tenants, enc_key, monkeypatch):
    import token_refresher
    soon = "2000-01-01T00:00:00"
    as_tenant(A, instagram_accounts.save_ig_account, "ig-a", "fb-a", "a", "old-a", soon)
    as_tenant(B, instagram_accounts.save_ig_account, "ig-b", "fb-b", "b", "old-b", soon)

    async def fake_refresh(token):
        return f"new-{token}", 3600

    monkeypatch.setattr(token_refresher.instagram_api, "get_long_lived_token", fake_refresh)
    run(token_refresher.run_token_refresher_tick(lambda: False))
    assert as_tenant(A, instagram_accounts.get_ig_account)["access_token"] == "new-old-a"
    assert as_tenant(B, instagram_accounts.get_ig_account)["access_token"] == "new-old-b"


def test_oauth_state_binds_connection_to_starting_tenant(api, tenants, enc_key, monkeypatch):
    from config import cfg
    import instagram_oauth
    monkeypatch.setattr(cfg, "meta_app_id", "app")
    monkeypatch.setattr(cfg, "meta_app_secret", "secret")
    url = as_tenant(B, instagram_accounts.connect_instagram)["connect_url"]
    state = url.split("state=")[1].split("&")[0]

    async def fake_exchange(code):
        return "short"

    async def fake_long(token):
        return "long-token", 3600

    async def fake_resolve(token):
        return {"ig_user_id": "ig-b", "fb_page_id": "fb-b", "username": "b_user"}

    monkeypatch.setattr(instagram_oauth, "exchange_code_for_token", fake_exchange)
    monkeypatch.setattr(instagram_oauth, "get_long_lived_token", fake_long)
    monkeypatch.setattr(instagram_oauth, "resolve_ig_account", fake_resolve)
    # A tenant_id in the query string is ignored; the state decides.
    r = api.c.get(f"/api/instagram/oauth/callback?code=c&state={state}&tenant_id={A}")
    assert r.status_code == 200
    assert as_tenant(B, instagram_accounts.get_ig_account)["ig_user_id"] == "ig-b"
    assert as_tenant(A, instagram_accounts.get_ig_account) is None
    # One-shot state.
    assert instagram_api.consume_oauth_state(state) is None


# ── Chat sessions and REST ───────────────────────────────────────────────────

@pytest.fixture
def lead_creating_agent(monkeypatch, client):
    """Replace the agent loop with one that calls the create_lead tool via the registry."""
    from agents.orchestrator import get_agent
    from tools.registry import registry

    async def fake_run(self, messages, on_event=None, approval_gate=None, system_context=None):
        await registry.dispatch("create_lead", {"name": messages[-1]["content"]})
        await on_event({"type": "text_delta", "text": "ok"})
        await on_event({"type": "done"})
        return "ok", "end_turn"

    monkeypatch.setattr(type(get_agent("leads")), "run", fake_run)


def _chat(client, url, text):
    with client.websocket_connect(url) as ws:
        hello = ws.receive_json()
        ws.send_json({"message": text})
        while ws.receive_json().get("type") != "done":
            pass
        return hello


def _token(h):
    return h["Authorization"].split(" ", 1)[1]


def test_ws_tools_run_in_the_sessions_tenant(api, lead_creating_agent):
    owner = api.user("o@t.test")
    tid = api.tenant("Client", owner_email="o@t.test")
    hello = _chat(api.c, f"/ws/leads?token={_token(owner)}&tenant_id={tid}", "Client Lead")
    _chat(api.c, f"/ws/leads?token={_token(api.admin)}", "Internal Lead")
    assert [x["name"] for x in as_tenant(tid, leads.list_leads)] == ["Client Lead"]
    assert [x["name"] for x in as_tenant(INTERNAL_TENANT_ID, leads.list_leads)] == ["Internal Lead"]

    # Conversation history is per tenant too.
    convs = api.c.get(f"/api/agents/leads/conversations?tenant_id={tid}", headers=owner).json()
    assert [c["id"] for c in convs] == [hello["conversation_id"]]
    internal = api.c.get("/api/agents/leads/conversations", headers=api.admin).json()
    assert hello["conversation_id"] not in [c["id"] for c in internal]
    msgs = api.c.get(f"/api/conversations/{hello['conversation_id']}/messages", headers=api.admin).json()
    assert msgs == []  # asked through the internal tenant → nothing


def test_internal_tenant_requires_membership_for_non_admins(api, lead_creating_agent):
    from starlette.websockets import WebSocketDisconnect
    operator = api.user("staff@core8.test")
    assert api.c.get("/api/agents/leads/conversations", headers=operator).status_code == 404
    with pytest.raises(WebSocketDisconnect) as e:
        with api.c.websocket_connect(f"/ws/leads?token={_token(operator)}") as ws:
            ws.receive_json()
    assert e.value.code == 4004
    # Admin grants access to Core8's own workspace → works.
    assert api.c.post(f"/api/tenants/{INTERNAL_TENANT_ID}/members",
                      json={"email": "staff@core8.test", "role": "editor"}, headers=api.admin).status_code == 200
    assert api.c.get("/api/agents/leads/conversations", headers=operator).status_code == 200


def test_instagram_and_media_routes_are_tenant_scoped(api, tmp_path, monkeypatch):
    monkeypatch.setattr(media_gen, "MEDIA_DIR", str(tmp_path))
    owner = api.user("o@t.test")
    outsider = api.user("x@t.test")
    tid = api.tenant("Client", owner_email="o@t.test")
    as_tenant(tid, instagram_publish.queue_post, PAST, media_url="https://x/c.jpg")
    c = api.c
    assert len(c.get(f"/api/instagram/scheduled-posts?tenant_id={tid}", headers=owner).json()) == 1
    assert c.get("/api/instagram/scheduled-posts", headers=api.admin).json() == []
    assert c.get(f"/api/instagram/scheduled-posts?tenant_id={tid}", headers=outsider).status_code == 404
    r = c.post(f"/api/instagram/media?tenant_id={tid}", headers=owner,
               files={"file": ("p.jpg", b"jpeg-bytes", "image/jpeg")})
    assert r.status_code == 200 and r.json()["filename"].startswith(f"{tid}/")
    assert c.post(f"/api/instagram/media?tenant_id={tid}", headers=outsider,
                  files={"file": ("p.jpg", b"x", "image/jpeg")}).status_code == 404


# ── Migration of a pre-multi-tenancy database ────────────────────────────────

def test_migration_assigns_existing_rows_to_internal_tenant(tmp_path, monkeypatch):
    path = str(tmp_path / "old.db")
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE leads (id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT, company TEXT,
            status TEXT NOT NULL DEFAULT 'new', source TEXT, notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT NOT NULL DEFAULT (datetime('now')));
        INSERT INTO leads (id, name) VALUES ('old-1', 'Legacy Lead');
        CREATE TABLE design_docs (id TEXT PRIMARY KEY, project TEXT NOT NULL, path TEXT NOT NULL,
            content TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')), UNIQUE(project, path));
        INSERT INTO design_docs (id, project, path, content) VALUES ('d1', 'site', 'a.md', 'old');
        CREATE TABLE ig_accounts (id TEXT PRIMARY KEY, ig_user_id TEXT NOT NULL, fb_page_id TEXT NOT NULL,
            username TEXT, access_token TEXT NOT NULL, token_expires_at TEXT,
            connected_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT NOT NULL DEFAULT (datetime('now')));
        INSERT INTO ig_accounts (id, ig_user_id, fb_page_id, access_token) VALUES ('primary', 'ig', 'fb', 'enc');
    """)
    con.commit()
    con.close()
    monkeypatch.setattr(database, "DB_PATH", path)
    run(database.init_db())
    from business_brain.schema import init_brain_schema
    run(init_brain_schema())

    assert [x["name"] for x in as_tenant(INTERNAL_TENANT_ID, leads.list_leads)] == ["Legacy Lead"]
    assert as_tenant(INTERNAL_TENANT_ID, design.read_design_doc, "site", "a.md")["content"] == "old"
    con = sqlite3.connect(path)
    assert con.execute("SELECT id, tenant_id FROM ig_accounts").fetchall() == [(INTERNAL_TENANT_ID, INTERNAL_TENANT_ID)]
    assert con.execute("SELECT name FROM tenants WHERE id=?", (INTERNAL_TENANT_ID,)).fetchone() is not None
    con.close()
    # Another tenant may now reuse the same design-doc path.
    sqlite3.connect(path).executescript("INSERT INTO tenants (id, name, created_by) VALUES ('t2','T2','x');")
    as_tenant("t2", design.write_design_doc, "site", "a.md", "new")
    assert as_tenant(INTERNAL_TENANT_ID, design.read_design_doc, "site", "a.md")["content"] == "old"


# ── Upgraded databases fail closed (review on PR #8, 2026-11-15) ─────────────

def _legacy_db(tmp_path, monkeypatch):
    """A real pre-multi-tenancy database, created by the old schema code, with one row per table."""
    import importlib
    legacy = importlib.import_module("tests.fixtures.legacy_database_v0")
    path = str(tmp_path / "legacy.db")
    monkeypatch.setattr(legacy, "DB_PATH", path)
    run(legacy.init_db())
    con = sqlite3.connect(path)
    con.executescript("""
        INSERT INTO conversations (id, agent_id) VALUES ('c1', 'general');
        INSERT INTO messages (id, conversation_id, role, content) VALUES ('m1', 'c1', 'user', 'hi');
        INSERT INTO leads (id, name) VALUES ('l1', 'Legacy Lead');
        INSERT INTO events (id, title, start_time, end_time) VALUES ('e1', 'Meet', '2026-01-01T10:00', '2026-01-01T11:00');
        INSERT INTO design_docs (id, project, path, content) VALUES ('d1', 'site', 'a.md', 'old');
    """)
    con.commit()
    con.close()
    return path


def _defaults(con, table):
    return {r[1]: r[4] for r in con.execute(f"PRAGMA table_info({table})")}


def test_upgraded_database_rejects_inserts_without_tenant(tmp_path, monkeypatch):
    path = _legacy_db(tmp_path, monkeypatch)
    before = {t: sqlite3.connect(path).execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in database._TENANT_SCOPED_TABLES}
    monkeypatch.setattr(database, "DB_PATH", path)
    run(database.init_db())

    con = sqlite3.connect(path)
    for table in database._TENANT_SCOPED_TABLES:
        cols = _defaults(con, table)
        assert "tenant_id" in cols, table
        assert cols["tenant_id"] is None, f"{table}.tenant_id still has a DEFAULT"
        # Legacy data survived and belongs to the internal tenant.
        assert con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == before[table], table
        assert con.execute(f"SELECT COUNT(*) FROM {table} WHERE tenant_id != ?",
                           (INTERNAL_TENANT_ID,)).fetchone()[0] == 0, table
        # Tenant index survived the rebuild.
        idx = [r[1] for r in con.execute(f"PRAGMA index_list({table})")]
        assert f"ix_{table}_tenant" in idx, table
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO leads (id, name) VALUES ('l2', 'No tenant')")
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO messages (id, conversation_id, role, content) VALUES ('m2','c1','user','x')")
    assert con.execute("SELECT name FROM leads WHERE id='l1'").fetchone() == ("Legacy Lead",)
    con.close()


def test_repeated_initialisation_of_upgraded_database_is_safe(tmp_path, monkeypatch):
    path = _legacy_db(tmp_path, monkeypatch)
    monkeypatch.setattr(database, "DB_PATH", path)
    run(database.init_db())
    schema = sqlite3.connect(path).execute("SELECT name, sql FROM sqlite_master ORDER BY name").fetchall()
    run(database.init_db())
    run(database.init_db())
    con = sqlite3.connect(path)
    assert con.execute("SELECT name, sql FROM sqlite_master ORDER BY name").fetchall() == schema
    assert con.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 1
    assert con.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []


def test_fresh_database_has_no_tenant_default(tmp_path, monkeypatch):
    path = str(tmp_path / "fresh.db")
    monkeypatch.setattr(database, "DB_PATH", path)
    run(database.init_db())
    con = sqlite3.connect(path)
    for table in database._TENANT_SCOPED_TABLES:
        assert _defaults(con, table)["tenant_id"] is None, table


# ── Backup and rollback (review on PR #8, 2026-11-15) ───────────────────────

def _dump(path):
    con = sqlite3.connect(path)
    try:
        return list(con.iterdump())
    finally:
        con.close()


def test_backup_is_taken_once_before_migration_and_restores_legacy_db(tmp_path, monkeypatch):
    import glob
    import importlib
    import shutil
    path = _legacy_db(tmp_path, monkeypatch)
    original = _dump(path)
    monkeypatch.setattr(database, "DB_PATH", path)
    run(database.init_db())

    backups = glob.glob(path + ".pre-core8-005-*.bak")
    assert len(backups) == 1
    assert _dump(backups[0]) == original          # exact pre-migration content
    assert oct(os.stat(backups[0]).st_mode & 0o777) == "0o600"
    run(database.init_db())                        # already migrated → no second backup
    assert len(glob.glob(path + ".pre-core8-005-*.bak")) == 1

    # Rollback: restore the backup; the previous build's schema code runs on it unchanged.
    shutil.copy(backups[0], path)
    assert _dump(path) == original
    legacy = importlib.import_module("tests.fixtures.legacy_database_v0")
    monkeypatch.setattr(legacy, "DB_PATH", path)
    run(legacy.init_db())
    con = sqlite3.connect(path)
    assert con.execute("SELECT name FROM leads").fetchall() == [("Legacy Lead",)]
    assert "tenant_id" not in [r[1] for r in con.execute("PRAGMA table_info(leads)")]
    con.close()
    # And the upgrade can be re-run after a rollback.
    run(database.init_db())
    assert sqlite3.connect(path).execute("SELECT tenant_id FROM leads").fetchall() == [(INTERNAL_TENANT_ID,)]


def test_no_backup_for_fresh_database(tmp_path, monkeypatch):
    import glob
    path = str(tmp_path / "fresh.db")
    monkeypatch.setattr(database, "DB_PATH", path)
    run(database.init_db())
    run(database.init_db())
    assert glob.glob(path + ".pre-core8-005-*.bak") == []
