"""Tracked links — attribute a visit or a sale to the post that sent it.

A tracked link is the tenant's landing URL plus UTM parameters that name the channel, the
campaign and the content item. It is derived, never stored on the item and never written into
the caption, so building one cannot change an approved publication.

Instagram feed captions do not make links clickable: use these in the bio link, Story link
stickers and Facebook Page posts, and on the landing page read `utm_content` to credit the post.
"""

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

CHANNELS = ("instagram", "facebook")
PLACEMENTS = ("post", "story", "reel", "bio")
_SLUG = re.compile(r"[^a-z0-9]+")
_DROP = ("utm_", "fbclid", "gclid")


class TrackedLinkError(ValueError):
    """The landing URL or a parameter cannot produce a safe tracked link."""


def slug(value: str, limit: int = 60) -> str:
    """Lower-case ASCII slug for a UTM value; empty when nothing usable remains."""
    return _SLUG.sub("-", (value or "").lower()).strip("-")[:limit].strip("-")


def tracked_url(landing_url: str, *, channel: str, campaign: str, content_id: str,
                placement: str = "post") -> str:
    """Return `landing_url` with utm_source/medium/campaign/content set.

    Existing non-tracking query parameters and the fragment are kept; any utm_*, fbclid or gclid
    already on the URL is replaced so a link is never double-tagged."""
    if channel not in CHANNELS:
        raise TrackedLinkError(f"channel must be one of {CHANNELS}")
    if placement not in PLACEMENTS:
        raise TrackedLinkError(f"placement must be one of {PLACEMENTS}")
    parts = urlsplit((landing_url or "").strip())
    if parts.scheme != "https" or not parts.netloc or parts.username or parts.password:
        raise TrackedLinkError("landing_url must be an https URL without credentials")
    campaign_slug, content_slug = slug(campaign), slug(content_id)
    if not campaign_slug:
        raise TrackedLinkError("campaign is required (letters or digits)")
    if not content_slug:
        raise TrackedLinkError("content_id is required")
    kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not k.lower().startswith(_DROP)]
    kept += [("utm_source", channel), ("utm_medium", f"social-{placement}"),
             ("utm_campaign", campaign_slug), ("utm_content", content_slug)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", urlencode(kept), parts.fragment))


def validate_tracking(value: dict) -> dict:
    """Normalise the `tracking` setting. Empty landing_url means tracking is not configured."""
    landing = str(value.get("landing_url") or "").strip()
    campaign = slug(str(value.get("campaign") or ""))
    if landing:
        if not campaign:
            raise TrackedLinkError("campaign is required when landing_url is set")
        tracked_url(landing, channel="instagram", campaign=campaign, content_id="check")
    return {"landing_url": landing, "campaign": campaign}
