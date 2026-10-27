"""Instagram adapter — Meta Graph API (live) or an in-memory mock.

Official references (checked 2026-10-27):
- Content publishing flow, status codes, 100 posts / 24 h:
  https://developers.facebook.com/documentation/instagram-platform/content-publishing
- /<IG_ID>/media parameters and media specs:
  https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-user/media

Error classification drives the publication state machine:
- ProviderError(retryable=True)  → network / 5xx / rate limit → retry with backoff
- ProviderError(retryable=False) → bad media, permission, token → fail
- ProviderTimeout                → outcome UNKNOWN → reconcile, never blind retry
"""

import asyncio
import datetime
import logging
import time
import uuid

import httpx

from tools.instagram_accounts import get_account_summary, get_ig_account

from ..config import scfg

logger = logging.getLogger("core8.social.instagram")

GRAPH_VERSION = "v22.0"
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"

# Meta: 100 API-published posts per rolling 24 h (carousel = 1).
META_DAILY_PUBLISH_LIMIT = 100


class ProviderError(RuntimeError):
    def __init__(self, message: str, retryable: bool = False, code: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.code = code


class ProviderTimeout(ProviderError):
    """Request sent, no answer — the real outcome is unknown."""
    def __init__(self, message: str):
        super().__init__(message, retryable=False)


# Graph error codes that are safe to retry (transient) per Meta docs.
_RETRYABLE_CODES = {1, 2, 4, 17, 32, 341, 613}   # unknown, service, throttling
_TOKEN_CODES = {190, 102}                        # invalid / expired token


def _classify(err: dict) -> ProviderError:
    code = err.get("code")
    msg = err.get("message", str(err))
    if code in _TOKEN_CODES:
        return ProviderError(f"Token error ({code}): {msg}", retryable=False, code=code)
    if code in _RETRYABLE_CODES or err.get("is_transient"):
        return ProviderError(f"Transient Graph error ({code}): {msg}", retryable=True, code=code)
    return ProviderError(f"Graph error ({code}): {msg}", retryable=False, code=code)


class BaseInstagramProvider:
    mode = "mock"

    async def account(self) -> dict | None: ...
    async def create_container(self, ig_user_id, token, **params) -> str: ...
    async def container_status(self, container_id, token) -> str: ...
    async def publish(self, ig_user_id, token, container_id) -> str: ...
    async def media_info(self, media_id, token) -> dict: ...
    async def recent_media(self, ig_user_id, token, limit=10) -> list[dict]: ...
    async def publishing_limit(self, ig_user_id, token) -> dict: ...


class LiveInstagramProvider(BaseInstagramProvider):
    mode = "live"

    async def _get(self, path: str, params: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=30.0) as c:
                r = await c.get(f"{GRAPH}/{path}", params=params)
        except httpx.TimeoutException as e:
            raise ProviderError(f"Timeout reading {path}", retryable=True) from e
        except httpx.HTTPError as e:
            raise ProviderError(f"Network error: {type(e).__name__}", retryable=True) from e
        return self._parse(r)

    async def _post(self, path: str, data: dict, ambiguous_on_timeout: bool = False) -> dict:
        try:
            async with httpx.AsyncClient(timeout=60.0) as c:
                r = await c.post(f"{GRAPH}/{path}", data=data)
        except httpx.TimeoutException as e:
            if ambiguous_on_timeout:
                raise ProviderTimeout(f"Timeout after sending {path}") from e
            raise ProviderError(f"Timeout posting {path}", retryable=True) from e
        except httpx.HTTPError as e:
            if ambiguous_on_timeout:
                raise ProviderTimeout(f"Connection lost after sending {path}: {type(e).__name__}") from e
            raise ProviderError(f"Network error: {type(e).__name__}", retryable=True) from e
        return self._parse(r)

    @staticmethod
    def _parse(r: httpx.Response) -> dict:
        try:
            data = r.json()
        except ValueError:
            raise ProviderError(f"Non-JSON Graph response HTTP {r.status_code}",
                                retryable=r.status_code >= 500)
        if isinstance(data, dict) and "error" in data:
            raise _classify(data["error"] if isinstance(data["error"], dict) else {"message": str(data["error"])})
        if r.status_code >= 500:
            raise ProviderError(f"Graph HTTP {r.status_code}", retryable=True)
        if r.status_code >= 400:
            raise ProviderError(f"Graph HTTP {r.status_code}", retryable=False)
        return data

    async def account(self) -> dict | None:
        return await get_account_summary()

    async def create_container(self, ig_user_id, token, **params) -> str:
        data = {k: v for k, v in params.items() if v is not None}
        data["access_token"] = token
        resp = await self._post(f"{ig_user_id}/media", data)
        cid = resp.get("id")
        if not cid:
            raise ProviderError("No container id returned", retryable=False)
        return cid

    async def container_status(self, container_id, token) -> str:
        data = await self._get(container_id, {"fields": "status_code,status", "access_token": token})
        return data.get("status_code", "UNKNOWN")

    async def publish(self, ig_user_id, token, container_id) -> str:
        resp = await self._post(f"{ig_user_id}/media_publish",
                                {"creation_id": container_id, "access_token": token},
                                ambiguous_on_timeout=True)
        mid = resp.get("id")
        if not mid:
            raise ProviderError("No media id after publish", retryable=False)
        return mid

    async def media_info(self, media_id, token) -> dict:
        return await self._get(media_id, {"fields": "id,permalink,timestamp,caption,media_type",
                                          "access_token": token})

    async def recent_media(self, ig_user_id, token, limit=10) -> list[dict]:
        data = await self._get(f"{ig_user_id}/media", {
            "fields": "id,permalink,timestamp,caption,media_type", "limit": limit,
            "access_token": token})
        return data.get("data", [])

    async def publishing_limit(self, ig_user_id, token) -> dict:
        data = await self._get(f"{ig_user_id}/content_publishing_limit",
                               {"fields": "quota_usage,config", "access_token": token})
        return (data.get("data") or [{}])[0]


class MockInstagramProvider(BaseInstagramProvider):
    """Simulates the container → publish flow without touching Meta.

    Failure injection (for tests and the demo flow) via `behaviour`:
      None | 'timeout_on_publish' | 'retryable_error' | 'permanent_error' | 'container_error'
    """
    mode = "mock"

    def __init__(self):
        self.containers: dict[str, dict] = {}
        self.published: list[dict] = []
        self.behaviour: str | None = None
        self.account_override: dict | None = None
        self.calls: list[tuple] = []

    async def account(self) -> dict | None:
        if self.account_override is not None:
            return self.account_override
        return {
            "ig_user_id": "mock_ig_17841400000000000",
            "username": "core8ai.demo",
            "fb_page_id": "mock_page_1",
            "token_expires_at": (datetime.datetime.utcnow()
                                 + datetime.timedelta(days=45)).isoformat(),
            "connected_at": datetime.datetime.utcnow().isoformat(),
            "account_type": "BUSINESS",
            "mock": True,
        }

    async def create_container(self, ig_user_id, token, **params) -> str:
        self.calls.append(("create_container", params))
        if self.behaviour == "container_error":
            raise ProviderError("Mock: invalid media (simulated)", retryable=False, code=352)
        cid = f"mock_c_{uuid.uuid4().hex[:10]}"
        self.containers[cid] = {"params": params, "status": "FINISHED", "created": time.time()}
        return cid

    async def container_status(self, container_id, token) -> str:
        c = self.containers.get(container_id)
        return c["status"] if c else "UNKNOWN"

    async def publish(self, ig_user_id, token, container_id) -> str:
        self.calls.append(("publish", container_id))
        if self.behaviour == "retryable_error":
            self.behaviour = None  # succeed next time
            raise ProviderError("Mock: service temporarily unavailable", retryable=True, code=2)
        if self.behaviour == "permanent_error":
            raise ProviderError("Mock: permission denied (simulated)", retryable=False, code=10)
        c = self.containers.get(container_id)
        if not c:
            raise ProviderError("Mock: unknown container", retryable=False)
        mid = f"mock_m_{uuid.uuid4().hex[:10]}"
        c["status"] = "PUBLISHED"
        c["media_id"] = mid
        self.published.append({
            "id": mid, "container_id": container_id,
            "permalink": f"https://www.instagram.com/p/mock_{mid[-6:]}/",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "caption": c["params"].get("caption", ""),
        })
        if self.behaviour == "timeout_on_publish":
            self.behaviour = None
            raise ProviderTimeout("Mock: timeout after media_publish was sent")
        return mid

    async def media_info(self, media_id, token) -> dict:
        for m in self.published:
            if m["id"] == media_id:
                return m
        raise ProviderError("Mock: media not found", retryable=False)

    async def recent_media(self, ig_user_id, token, limit=10) -> list[dict]:
        return list(reversed(self.published))[:limit]

    async def publishing_limit(self, ig_user_id, token) -> dict:
        return {"quota_usage": len([p for p in self.published]), "config": {"quota_total": META_DAILY_PUBLISH_LIMIT}}


_live = LiveInstagramProvider()
_mock = MockInstagramProvider()


def get_provider(mode: str | None = None) -> BaseInstagramProvider:
    m = mode or scfg.instagram_mode
    return _live if m == "live" else _mock


def mock_provider() -> MockInstagramProvider:
    return _mock


async def live_account_with_token() -> dict | None:
    """Decrypted token for live calls only. Never returned to the API layer."""
    return await get_ig_account()


async def wait_until_ready(provider: BaseInstagramProvider, container_id: str, token: str,
                           attempts: int = 5, delay: float = 60.0) -> str:
    """Meta recommends polling once a minute for at most ~5 minutes."""
    last = "UNKNOWN"
    for _ in range(attempts):
        last = await provider.container_status(container_id, token)
        if last in ("FINISHED", "PUBLISHED"):
            return last
        if last in ("ERROR", "EXPIRED"):
            raise ProviderError(f"Container {last}", retryable=False)
        await asyncio.sleep(delay if provider.mode == "live" else 0)
    raise ProviderError(f"Container not ready after polling (last={last})", retryable=True)
