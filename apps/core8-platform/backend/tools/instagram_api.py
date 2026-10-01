"""Meta Graph API client for the Instagram connect flow.

Covers OAuth URL building, CSRF state, the code -> token exchange, and
resolving the Facebook Page's linked Instagram Business account. Publishing
and insights calls arrive in later phases. All HTTP calls are async (httpx).
"""

import asyncio
import secrets
import time
import urllib.parse

import httpx

from config import cfg

GRAPH_API_VERSION = "v21.0"
_GRAPH = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
_DIALOG = f"https://www.facebook.com/{GRAPH_API_VERSION}/dialog/oauth"

# Permissions required to manage and publish to an Instagram Business account.
OAUTH_SCOPES = [
    "instagram_basic",
    "instagram_content_publish",
    "instagram_manage_insights",
    "pages_show_list",
    "pages_read_engagement",
    "business_management",
]

# Pending CSRF states: state token -> created (monotonic) timestamp. In-memory
# is fine — the connect flow completes within seconds.
_PENDING_STATES: dict[str, float] = {}
_STATE_TTL = 600.0  # seconds


class GraphAPIError(RuntimeError):
    """A Meta Graph API call failed, or the integration is misconfigured."""


def _prune_states() -> None:
    now = time.monotonic()
    for s in [s for s, ts in _PENDING_STATES.items() if now - ts > _STATE_TTL]:
        _PENDING_STATES.pop(s, None)


def build_oauth_url() -> str:
    """Generate a CSRF state and return the Meta OAuth consent URL."""
    if not cfg.meta_app_id:
        raise GraphAPIError("META_APP_ID is not set — create a Meta app first.")
    _prune_states()
    state = secrets.token_urlsafe(24)
    _PENDING_STATES[state] = time.monotonic()
    params = {
        "client_id": cfg.meta_app_id,
        "redirect_uri": cfg.meta_redirect_uri,
        "state": state,
        "scope": ",".join(OAUTH_SCOPES),
        "response_type": "code",
    }
    return f"{_DIALOG}?{urllib.parse.urlencode(params)}"


def consume_oauth_state(state: str) -> bool:
    """True if `state` is a valid, unexpired, pending state. Removes it (one-shot)."""
    _prune_states()
    return _PENDING_STATES.pop(state, None) is not None


def _parse_graph(resp) -> dict:
    try:
        data = resp.json()
    except Exception:
        raise GraphAPIError(f"Graph API returned non-JSON (HTTP {resp.status_code}).")
    if isinstance(data, dict) and "error" in data:
        err = data["error"]
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        raise GraphAPIError(f"Graph API error: {msg}")
    if resp.status_code >= 400:
        raise GraphAPIError(f"Graph API HTTP {resp.status_code}.")
    return data


async def _graph_get(path: str, params: dict) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{_GRAPH}/{path}", params=params)
    return _parse_graph(resp)


async def _graph_post(path: str, data: dict) -> dict:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{_GRAPH}/{path}", data=data)
    return _parse_graph(resp)


async def exchange_code_for_token(code: str) -> str:
    """OAuth code -> short-lived user access token."""
    data = await _graph_get("oauth/access_token", {
        "client_id": cfg.meta_app_id,
        "client_secret": cfg.meta_app_secret,
        "redirect_uri": cfg.meta_redirect_uri,
        "code": code,
    })
    token = data.get("access_token")
    if not token:
        raise GraphAPIError("No access_token in the code-exchange response.")
    return token


async def get_long_lived_token(short_token: str) -> tuple[str, int]:
    """Short-lived token -> (long-lived token, expires_in seconds, ~60 days)."""
    data = await _graph_get("oauth/access_token", {
        "grant_type": "fb_exchange_token",
        "client_id": cfg.meta_app_id,
        "client_secret": cfg.meta_app_secret,
        "fb_exchange_token": short_token,
    })
    token = data.get("access_token")
    if not token:
        raise GraphAPIError("No access_token in the long-lived-token response.")
    return token, int(data.get("expires_in", 0))


async def resolve_ig_account(token: str) -> dict:
    """Find the Facebook Page and its linked Instagram Business account.

    Returns {ig_user_id, fb_page_id, username}. Raises GraphAPIError if the
    account has no Page, or no Page has a linked IG Business account.
    """
    pages = await _graph_get("me/accounts", {"access_token": token})
    page_list = pages.get("data", [])
    if not page_list:
        raise GraphAPIError(
            "No Facebook Page found. An Instagram Business account must be "
            "linked to a Facebook Page you manage."
        )
    for page in page_list:
        page_id = page.get("id")
        detail = await _graph_get(page_id, {
            "fields": "instagram_business_account",
            "access_token": token,
        })
        ig = detail.get("instagram_business_account")
        if ig and ig.get("id"):
            ig_user_id = ig["id"]
            prof = await _graph_get(ig_user_id, {
                "fields": "username",
                "access_token": token,
            })
            return {
                "ig_user_id": ig_user_id,
                "fb_page_id": page_id,
                "username": prof.get("username", ""),
            }
    raise GraphAPIError(
        "No Instagram Business account is linked to any of your Facebook Pages. "
        "Link one in Meta Business settings, then reconnect."
    )


# ── Publishing — the two-step container flow ────────────────────────────────

async def create_media_container(ig_user_id: str, token: str, media_url: str,
                                  caption: str, post_type: str) -> str:
    """Create a media container. Returns the container (creation) id."""
    data = {"caption": caption or "", "access_token": token}
    if post_type == "reel":
        data["media_type"] = "REELS"
        data["video_url"] = media_url
    else:  # image
        data["image_url"] = media_url
    resp = await _graph_post(f"{ig_user_id}/media", data)
    container_id = resp.get("id")
    if not container_id:
        raise GraphAPIError("Graph API returned no media container id.")
    return container_id


async def wait_for_container(container_id: str, token: str,
                             attempts: int = 20, delay: float = 5.0) -> None:
    """Poll a container until status_code is FINISHED. Reels need processing time."""
    for _ in range(attempts):
        data = await _graph_get(container_id, {
            "fields": "status_code", "access_token": token,
        })
        status = data.get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise GraphAPIError(f"Media container failed processing: {status}.")
        await asyncio.sleep(delay)
    raise GraphAPIError("Media container did not finish processing in time.")


async def publish_container(ig_user_id: str, token: str, container_id: str) -> str:
    """Publish a finished container. Returns the published Instagram media id."""
    resp = await _graph_post(f"{ig_user_id}/media_publish", {
        "creation_id": container_id, "access_token": token,
    })
    media_id = resp.get("id")
    if not media_id:
        raise GraphAPIError("Graph API returned no media id after publish.")
    return media_id


async def _publish_carousel(ig_user_id: str, token: str, caption: str,
                            media_urls: list[str]) -> str:
    """Carousel publish — image-only in v1. Creates child containers
    (is_carousel_item=true), a carousel container (media_type=CAROUSEL),
    then publishes; returns the published Instagram media id."""
    if not (2 <= len(media_urls) <= 10):
        raise GraphAPIError(f"Carousel needs 2-10 items, got {len(media_urls)}.")
    child_ids: list[str] = []
    for url in media_urls:
        resp = await _graph_post(f"{ig_user_id}/media", {
            "image_url": url,
            "is_carousel_item": "true",
            "access_token": token,
        })
        cid = resp.get("id")
        if not cid:
            raise GraphAPIError("Graph API returned no child container id for carousel.")
        child_ids.append(cid)
    carousel = await _graph_post(f"{ig_user_id}/media", {
        "media_type": "CAROUSEL",
        "caption": caption or "",
        "children": ",".join(child_ids),
        "access_token": token,
    })
    carousel_id = carousel.get("id")
    if not carousel_id:
        raise GraphAPIError("Graph API returned no carousel container id.")
    return await publish_container(ig_user_id, token, carousel_id)


async def publish_post(ig_user_id: str, token: str, caption: str, post_type: str,
                       media_url: str | None = None,
                       media_urls: list[str] | None = None) -> str:
    """Full publish flow. For image/reel pass media_url; for carousel pass
    media_urls. Returns the published Instagram media id."""
    if post_type == "carousel":
        return await _publish_carousel(ig_user_id, token, caption, media_urls or [])
    if not media_url:
        raise GraphAPIError("media_url is required for image and reel posts.")
    container_id = await create_media_container(
        ig_user_id, token, media_url, caption, post_type)
    if post_type == "reel":
        await wait_for_container(container_id, token)
    return await publish_container(ig_user_id, token, container_id)


# ── Insights ────────────────────────────────────────────────────────────────

async def fetch_account_profile(ig_user_id: str, token: str) -> dict:
    """Current profile: username, followers_count, media_count."""
    return await _graph_get(ig_user_id, {
        "fields": "username,followers_count,media_count",
        "access_token": token,
    })


async def fetch_account_insights(ig_user_id: str, token: str,
                                 period_days: int = 7) -> dict:
    """Account-level insights totals for the last `period_days` days."""
    until = int(time.time())
    since = until - max(1, period_days) * 86400
    return await _graph_get(f"{ig_user_id}/insights", {
        "metric": "reach,accounts_engaged,total_interactions,profile_views",
        "metric_type": "total_value",
        "period": "day",
        "since": since,
        "until": until,
        "access_token": token,
    })


async def fetch_post_insights(ig_media_id: str, token: str) -> dict:
    """Lifetime per-post insights for a published Instagram media id."""
    return await _graph_get(f"{ig_media_id}/insights", {
        "metric": "reach,likes,comments,saves,shares,total_interactions",
        "access_token": token,
    })
