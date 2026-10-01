"""Background job: refresh the long-lived Instagram access token before it
expires. Runs alongside the publishing scheduler in lifespan.

Long-lived FB/IG tokens last ~60 days. We refresh when fewer than 7 days
remain by exchanging the current long-lived token for a new one — the same
fb_exchange_token endpoint used at initial connect.
"""

import asyncio
import datetime
import logging

from tools import instagram_api
from tools.instagram_accounts import get_ig_account, save_ig_account

logger = logging.getLogger("core8.token_refresher")

CHECK_INTERVAL = 3600.0           # poll once an hour
REFRESH_WHEN_DAYS_LEFT = 7.0      # refresh if expiry < 7 days away


async def run_token_refresher_tick(is_killed) -> None:
    """One refresh check. Safe to call directly (used by tests)."""
    if is_killed():
        return
    acct = await get_ig_account()
    if acct is None:
        return
    expires_at_str = acct.get("token_expires_at")
    if not expires_at_str:
        return
    try:
        expires_at = datetime.datetime.fromisoformat(expires_at_str)
    except ValueError:
        logger.warning("Could not parse token_expires_at=%r", expires_at_str)
        return
    days_left = (expires_at - datetime.datetime.utcnow()).total_seconds() / 86400.0
    if days_left > REFRESH_WHEN_DAYS_LEFT:
        return
    logger.info("Refreshing Instagram token (%.1f days left)", days_left)
    try:
        new_token, expires_in = await instagram_api.get_long_lived_token(acct["access_token"])
    except Exception as e:
        logger.error("Token refresh failed: %s", e)
        return
    new_expiry = (datetime.datetime.utcnow()
                  + datetime.timedelta(seconds=expires_in)).isoformat()
    await save_ig_account(
        ig_user_id=acct["ig_user_id"],
        fb_page_id=acct["fb_page_id"],
        username=acct["username"] or "",
        access_token=new_token,
        token_expires_at=new_expiry,
    )
    logger.info("Instagram token refreshed; new expiry %s", new_expiry)


async def _loop(is_killed) -> None:
    logger.info("Token refresher started (every %.0fs)", CHECK_INTERVAL)
    while True:
        try:
            await asyncio.sleep(CHECK_INTERVAL)
            await run_token_refresher_tick(is_killed)
        except asyncio.CancelledError:
            logger.info("Token refresher stopped")
            raise
        except Exception as e:
            logger.error("Token refresher tick error: %s", e)


def start_token_refresher(is_killed) -> asyncio.Task:
    """Start the loop as a background task. Cancel the returned task to stop."""
    return asyncio.create_task(_loop(is_killed))
