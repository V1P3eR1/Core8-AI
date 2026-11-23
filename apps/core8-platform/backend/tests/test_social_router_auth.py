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
