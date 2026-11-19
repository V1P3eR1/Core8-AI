"""Regression checks for viewer access and scheduler starvation."""
from tests.test_tenancy import (
    A, B, PAST, INTERNAL_TENANT_ID, as_tenant, run, _chat, _token,
    tenants, enc_key, lead_creating_agent, leads, instagram_accounts, instagram_publish,
)
import pytest

@pytest.mark.parametrize("internal", [False, True])
def test_ws_viewer_cannot_start_mutating_agent(api, lead_creating_agent, internal):
    from starlette.websockets import WebSocketDisconnect
    viewer = api.user("viewer-regression@t.test")
    tid = INTERNAL_TENANT_ID if internal else api.tenant("Viewer regression")
    response = api.c.post(f"/api/tenants/{tid}/members",
                         json={"email": "viewer-regression@t.test", "role": "viewer"},
                         headers=api.admin)
    assert response.status_code == 200
    suffix = "" if internal else f"&tenant_id={tid}"
    with pytest.raises(WebSocketDisconnect) as exc:
        _chat(api.c, f"/ws/leads?token={_token(viewer)}{suffix}", "Forbidden lead")
    assert exc.value.code == 4003
    assert as_tenant(tid, leads.list_leads) == []
    assert api.c.get(f"/api/agents/leads/conversations?tenant_id={tid}",
                     headers=viewer).json() == []


def test_ws_editor_can_start_agent(api, lead_creating_agent):
    editor = api.user("editor-regression@t.test")
    tid = api.tenant("Editor regression")
    assert api.c.post(f"/api/tenants/{tid}/members",
                     json={"email": "editor-regression@t.test", "role": "editor"},
                     headers=api.admin).status_code == 200
    _chat(api.c, f"/ws/leads?token={_token(editor)}&tenant_id={tid}", "Allowed lead")
    assert [lead["name"] for lead in as_tenant(tid, leads.list_leads)] == ["Allowed lead"]


@pytest.mark.parametrize("blocked_reason", ["no_account", "daily_cap"])
def test_scheduler_blocked_tenant_cannot_starve_next_tenant(tenants, enc_key, monkeypatch, blocked_reason):
    import scheduler
    as_tenant(B, instagram_accounts.save_ig_account, "ig-b", "fb-b", "b", "tok-b", None)
    if blocked_reason == "daily_cap":
        as_tenant(A, instagram_accounts.save_ig_account, "ig-a", "fb-a", "a", "tok-a", None)
        previous = as_tenant(A, instagram_publish.queue_post, PAST, media_url="https://x/old.jpg")
        as_tenant(A, instagram_publish.mark_published, previous["id"], "already-published")
        monkeypatch.setattr(scheduler, "DAILY_PUBLISH_CAP", 1)
    for _ in range(12):
        as_tenant(A, instagram_publish.queue_post, PAST, media_url="https://x/a.jpg")
    as_tenant(B, instagram_publish.queue_post, "2020-01-02T09:00:00", media_url="https://x/b.jpg")
    published = []

    async def fake_publish(**kw):
        published.append(kw["ig_user_id"])
        return "published-b"

    monkeypatch.setattr(scheduler.instagram_api, "publish_post", fake_publish)
    run(scheduler.run_scheduler_tick(lambda: False))
    assert published == ["ig-b"]
    assert as_tenant(B, instagram_publish.list_scheduled_posts)[0]["status"] == "published"


def test_due_batch_limit_is_per_tenant_and_excludes_future_cancelled(tenants):
    for tid in (A, B):
        for _ in range(12):
            as_tenant(tid, instagram_publish.queue_post, PAST, media_url="https://x/post.jpg")
        as_tenant(tid, instagram_publish.queue_post, "2999-01-01T00:00:00", media_url="https://x/future.jpg")
        cancelled = as_tenant(tid, instagram_publish.queue_post, PAST, media_url="https://x/cancel.jpg")
        as_tenant(tid, instagram_publish.cancel_scheduled_post, cancelled["id"])
    batch = run(instagram_publish.claim_due_posts(limit=3))
    assert len(batch) == 6
    assert sum(p["tenant_id"] == A for p in batch) == 3
    assert sum(p["tenant_id"] == B for p in batch) == 3
    assert all(p["status"] == "pending" and p["scheduled_for"].startswith("2020") for p in batch)

