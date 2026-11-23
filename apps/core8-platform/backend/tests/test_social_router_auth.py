"""Regression coverage for router-wide Social Manager JWT/admin authorization.

Uses only the synthetic TestClient fixture. No Meta/Anthropic network calls.
"""
import pytest


@pytest.mark.parametrize("path", [
    "/api/social/items",
    "/api/social/items/nonexistent-synthetic-id",
    "/api/social/items/nonexistent-synthetic-id/gates",
    "/api/social/items/nonexistent-synthetic-id/tracked-links",
])
def test_social_content_reads_reject_anonymous_and_non_admin(api, path):
    # Route-level dependency must run before any DB/content handler.
    anonymous = api.c.get(path)
    assert anonymous.status_code == 401, (path, anonymous.status_code, anonymous.text)

    operator_headers = api.user("operator-social-auth@core8.test")
    operator = api.c.get(path, headers=operator_headers)
    assert operator.status_code == 403, (path, operator.status_code, operator.text)


def test_social_content_list_allows_admin(api):
    response = api.c.get("/api/social/items", headers=api.admin)
    assert response.status_code == 200, response.text
    assert isinstance(response.json().get("items"), list)


def test_social_content_detail_admin_missing_item_returns_404(api):
    response = api.c.get("/api/social/items/nonexistent-synthetic-id", headers=api.admin)
    assert response.status_code == 404, response.text


@pytest.mark.parametrize("headers_kind,expected", [
    ("anonymous", 401),
    ("operator", 403),
    ("admin", 409),
])
def test_schedule_does_not_implicitly_approve_when_date_supplied(api, headers_kind, expected):
    """Reject combined schedule+approval before touching any content or publication."""
    headers = None if headers_kind == "anonymous" else (
        api.admin if headers_kind == "admin" else api.user("operator-social-schedule@core8.test")
    )
    response = api.c.post(
        "/api/social/items/nonexistent-synthetic-id/schedule",
        json={"scheduled_for": "2026-12-03T10:00"},
        headers=headers,
    )
    assert response.status_code == expected, response.text


@pytest.mark.parametrize("headers_kind,expected", [
    ("anonymous", 401),
    ("operator", 403),
    ("admin", 400),
])
def test_schedule_without_date_cannot_queue_nonexistent_item(api, headers_kind, expected):
    """Scheduling an unknown item cannot bypass JWT/admin or create a queue entry."""
    headers = None if headers_kind == "anonymous" else (
        api.admin if headers_kind == "admin" else api.user("operator-social-queue@core8.test")
    )
    response = api.c.post(
        "/api/social/items/nonexistent-synthetic-id/schedule",
        json={},
        headers=headers,
    )
    assert response.status_code == expected, response.text


def test_combined_schedule_request_does_not_mutate_existing_synthetic_item(api):
    """A rejected combined request cannot silently edit the schedule or create approval."""
    created = api.c.post(
        "/api/social/items",
        json={"format": "image", "title": "Synthetic schedule review", "caption": "Test only"},
        headers=api.admin,
    )
    assert created.status_code == 201, created.text
    item_id = created.json()["id"]
    before = api.c.get(f"/api/social/items/{item_id}", headers=api.admin)
    assert before.status_code == 200, before.text

    rejected = api.c.post(
        f"/api/social/items/{item_id}/schedule",
        json={"scheduled_for": "2026-12-03T10:00"},
        headers=api.admin,
    )
    assert rejected.status_code == 409, rejected.text

    after = api.c.get(f"/api/social/items/{item_id}", headers=api.admin)
    assert after.status_code == 200, after.text
    assert after.json()["scheduled_for"] == before.json()["scheduled_for"]
    assert after.json()["status"] == before.json()["status"]
    assert after.json()["approval"] == before.json()["approval"]
    assert after.json()["publications"] == before.json()["publications"]


def test_auto_scheduler_never_creates_worker_approvals(monkeypatch):
    """Even automatic mode must not mint approvals without human review."""
    from social import publishing

    async def forbidden(*args, **kwargs):
        raise AssertionError("automatic scheduler attempted a database or approval operation")

    monkeypatch.setattr(publishing, "create_approval", forbidden)
    monkeypatch.setattr(publishing, "schedule_item", forbidden)
    monkeypatch.setattr(publishing, "_pub_settings", forbidden)
    import asyncio
    assert asyncio.run(publishing.auto_schedule_candidates()) == []


def test_historical_worker_approval_cancels_before_provider_calls(monkeypatch):
    """Historical automatic approval cannot trigger a provider call on retry."""
    import asyncio
    from social import publishing

    async def is_auto(pub):
        return True

    async def get_item(item_id):
        return None

    async def set_state(pub_id, state, **fields):
        assert pub_id == "synthetic-publication"
        assert state == "cancelled"
        assert fields["last_error"] == "human_approval_required"

    async def fetch_one(query, args):
        return {"id": args[0], "state": "cancelled"}

    async def forbidden(*args, **kwargs):
        raise AssertionError("unexpected publishing or provider operation")

    monkeypatch.setattr(publishing, "_is_auto", is_auto)
    monkeypatch.setattr(publishing, "get_item", get_item)
    monkeypatch.setattr(publishing, "_set_state", set_state)
    monkeypatch.setattr(publishing, "fetch_one", fetch_one)
    monkeypatch.setattr(publishing, "set_status", forbidden)
    monkeypatch.setattr(publishing, "gate_report", forbidden)
    monkeypatch.setattr(publishing, "_credentials", forbidden)
    monkeypatch.setattr(publishing, "_create_containers", forbidden)
    monkeypatch.setattr(publishing, "get_provider", lambda mode: object())
    result = asyncio.run(publishing.run_publication({
        "id": "synthetic-publication", "content_item_id": "synthetic-item",
        "mode": "mock", "approval_id": "synthetic-worker-approval",
    }))
    assert result["state"] == "cancelled"


def test_publication_rejects_approval_id_mismatch_before_provider(monkeypatch):
    """A newer valid approval cannot authorize a queued publication using another ID."""
    import asyncio
    from social import publishing

    async def no_auto(pub):
        return False
    async def item(item_id):
        return {"id": item_id}
    async def raw(item_id):
        return {"id": item_id}
    async def approval(row):
        return {"valid": True, "approval": {"id": "new-human-approval", "approved_by": "admin"}}
    async def state(pub_id, value, **fields):
        assert value == "cancelled"
        assert fields["last_error"] == "human_approval_required"
    async def status(*args, **kwargs):
        return None
    async def row(query, args):
        return {"id": args[0], "state": "cancelled"}
    async def forbidden(*args, **kwargs):
        raise AssertionError("provider operation or gate report reached")

    monkeypatch.setattr(publishing, "_is_auto", no_auto)
    monkeypatch.setattr(publishing, "get_item", item)
    monkeypatch.setattr(publishing, "get_item_raw", raw)
    monkeypatch.setattr(publishing, "check_item_approval", approval)
    monkeypatch.setattr(publishing, "_set_state", state)
    monkeypatch.setattr(publishing, "set_status", status)
    monkeypatch.setattr(publishing, "fetch_one", row)
    monkeypatch.setattr(publishing, "gate_report", forbidden)
    monkeypatch.setattr(publishing, "get_provider", lambda mode: object())
    result = asyncio.run(publishing.run_publication({
        "id": "queued-publication", "content_item_id": "synthetic-item",
        "approval_id": "old-human-approval", "mode": "mock",
    }))
    assert result["state"] == "cancelled"


def test_worker_approval_detection_covers_all_worker_prefixes(monkeypatch):
    """No worker identity can count as a human approval, including legacy names."""
    import asyncio
    from social import publishing

    for actor, expected in [
        ("worker:auto", True), ("worker:publisher", True),
        ("worker:legacy-agent", True), ("admin", False),
    ]:
        async def approval_row(query, args, approved_by=actor):
            return {"approved_by": approved_by}
        monkeypatch.setattr(publishing, "fetch_one", approval_row)
        assert asyncio.run(publishing._is_auto({"approval_id": "synthetic-approval"})) is expected


@pytest.mark.parametrize("actor", ["worker:auto", "worker:legacy", "system:publisher", ""])
def test_approval_service_rejects_nonhuman_actor_before_db(monkeypatch, actor):
    """A background job cannot bypass the API and manufacture approval."""
    import asyncio
    from social import publishing

    async def forbidden(*args, **kwargs):
        raise AssertionError("database reached before actor validation")

    monkeypatch.setattr(publishing, "get_item", forbidden)
    with pytest.raises(publishing.GateError) as exc:
        asyncio.run(publishing.approve_item("synthetic-item", actor))
    assert exc.value.code == "human_approval_required"
