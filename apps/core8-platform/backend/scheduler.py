"""The Instagram publishing scheduler.

A background asyncio loop, started in the FastAPI lifespan — in-process, no
extra worker or dependency. Each tick polls scheduled_posts for due posts and
runs the publish flow. Respects the kill switch and Meta's 25-posts/24h cap.
"""

import asyncio
import logging

from tools import instagram_api
from tenancy import use_tenant
from tools.instagram_accounts import get_ig_account
from tools.instagram_publish import (
    claim_due_posts, count_published_last_24h,
    mark_attempt_failed, mark_published, mark_publishing,
)

logger = logging.getLogger("core8.scheduler")

POLL_INTERVAL = 60.0      # seconds between ticks
MAX_ATTEMPTS = 3          # publish attempts before a post is marked 'failed'
DAILY_PUBLISH_CAP = 25    # Meta's hard ceiling: 25 API posts / 24h per account


async def _publish_one(post: dict, account: dict) -> bool:
    """Publish one post. Returns True only if it actually published."""
    post_id = post["id"]
    await mark_publishing(post_id)
    try:
        if post["post_type"] == "carousel":
            media_id = await instagram_api.publish_post(
                ig_user_id=account["ig_user_id"],
                token=account["access_token"],
                caption=post["caption"] or "",
                post_type="carousel",
                media_urls=post.get("media_urls") or [],
            )
        else:
            media_id = await instagram_api.publish_post(
                ig_user_id=account["ig_user_id"],
                token=account["access_token"],
                caption=post["caption"] or "",
                post_type=post["post_type"],
                media_url=post["media_url"],
            )
    except Exception as e:
        give_up = post["attempts"] + 1 >= MAX_ATTEMPTS
        logger.error("Publish failed for post %s (attempt %d): %s",
                     post_id, post["attempts"] + 1, e)
        await mark_attempt_failed(post_id, str(e), give_up=give_up)
        return False
    await mark_published(post_id, media_id)
    logger.info("Published post %s -> ig_media %s", post_id, media_id)
    return True


async def run_scheduler_tick(is_killed) -> None:
    """One poll cycle. Safe to call directly (used by tests)."""
    if is_killed():
        return
    due = await claim_due_posts()
    if not due:
        return
    # Group by tenant: each tenant has its own Instagram account and its own daily cap.
    by_tenant: dict[str, list[dict]] = {}
    for post in due:
        by_tenant.setdefault(post["tenant_id"], []).append(post)
    for tenant_id, posts in by_tenant.items():
        if is_killed():
            break
        with use_tenant(tenant_id):
            account = await get_ig_account()
            if account is None:
                logger.warning("tenant=%s: %d post(s) due but no Instagram account is connected",
                               tenant_id, len(posts))
                continue
            published_today = await count_published_last_24h()
            for post in posts:
                if is_killed():
                    break
                if published_today >= DAILY_PUBLISH_CAP:
                    logger.warning("tenant=%s: daily publish cap (%d) reached — deferring the rest",
                                   tenant_id, DAILY_PUBLISH_CAP)
                    break
                if await _publish_one(post, account):
                    published_today += 1


async def _scheduler_loop(is_killed) -> None:
    logger.info("Publishing scheduler started (poll every %.0fs)", POLL_INTERVAL)
    while True:
        try:
            await asyncio.sleep(POLL_INTERVAL)
            await run_scheduler_tick(is_killed)
        except asyncio.CancelledError:
            logger.info("Publishing scheduler stopped")
            raise
        except Exception as e:
            logger.error("Scheduler tick error: %s", e)


def start_scheduler(is_killed) -> asyncio.Task:
    """Start the scheduler loop. `is_killed` is called each tick to check the
    kill switch. Returns the task — cancel it to stop the scheduler."""
    return asyncio.create_task(_scheduler_loop(is_killed))
