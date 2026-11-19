"""Tracked links: URL construction, setting validation, and that they never touch an approval."""
from urllib.parse import parse_qs, urlsplit

import pytest

from social import links
from tests.test_social import Social


@pytest.fixture
def s(api):
    return Social(api)


def _q(url: str) -> dict:
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


def test_tracked_url_sets_utm_and_keeps_other_params():
    url = links.tracked_url("https://example.test/book?lang=he&utm_source=old&fbclid=x#buy",
                            channel="facebook", campaign="Launch 2027!", content_id="Item_42",
                            placement="story")
    parts = urlsplit(url)
    assert (parts.scheme, parts.netloc, parts.path, parts.fragment) == ("https", "example.test", "/book", "buy")
    assert _q(url) == {"lang": "he", "utm_source": "facebook", "utm_medium": "social-story",
                       "utm_campaign": "launch-2027", "utm_content": "item-42"}


@pytest.mark.parametrize("landing", [
    "http://example.test/", "javascript:alert(1)", "https://user:pw@example.test/", "example.test", "",
])
def test_tracked_url_rejects_unsafe_landing(landing):
    with pytest.raises(links.TrackedLinkError):
        links.tracked_url(landing, channel="instagram", campaign="c", content_id="i")


def test_tracked_url_rejects_unknown_channel_and_empty_campaign():
    with pytest.raises(links.TrackedLinkError):
        links.tracked_url("https://example.test/", channel="tiktok", campaign="c", content_id="i")
    with pytest.raises(links.TrackedLinkError):
        links.tracked_url("https://example.test/", channel="instagram", campaign="!!!", content_id="i")


def test_tracking_setting_is_validated(s):
    s.req("put", "/api/social/settings/tracking", 400, json={"value": {"landing_url": "http://x.test"}})
    s.req("put", "/api/social/settings/tracking", 400, json={"value": {"landing_url": "https://x.test/"}})
    saved = s.req("put", "/api/social/settings/tracking", 200,
                  json={"value": {"landing_url": "https://x.test/", "campaign": "Book One"}}).json()
    assert saved == {"landing_url": "https://x.test/", "campaign": "book-one"}


def test_item_tracked_links_and_approval_unchanged(s):
    item, _ = s.image_item()
    assert s.req("get", f"/api/social/items/{item['id']}/tracked-links", 200).json() == {
        "configured": False, "links": {}}
    s.approve(item["id"])
    s.req("put", "/api/social/settings/tracking", 200,
          json={"value": {"landing_url": "https://x.test/", "campaign": "book-one"}})
    out = s.req("get", f"/api/social/items/{item['id']}/tracked-links", 200).json()
    assert out["configured"] is True and set(out["links"]) == set(links.CHANNELS)
    q = _q(out["links"]["facebook"]["post"])
    assert q["utm_source"] == "facebook" and q["utm_campaign"] == "book-one"
    assert q["utm_content"] == out["utm_content"] == links.slug(item["id"])
    # configuring tracking and reading links must not invalidate the approval
    assert s.req("get", f"/api/social/items/{item['id']}", 200).json()["approval"]["valid"] is True
    s.req("get", "/api/social/items/does-not-exist/tracked-links", 404)
