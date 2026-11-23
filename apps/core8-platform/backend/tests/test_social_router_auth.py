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
