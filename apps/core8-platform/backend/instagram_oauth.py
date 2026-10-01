"""Instagram OAuth callback — completes the Meta connect flow.

The browser is redirected here by Meta after the user grants consent. This
route validates the CSRF state, exchanges the code for a long-lived token,
resolves the linked Instagram Business account, and stores it (token encrypted).

The flow is *started* by the connect_instagram tool, which builds the consent
URL — so only the callback needs to be an HTTP route.
"""

import datetime
import html
import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from tools.instagram_api import (
    GraphAPIError, consume_oauth_state, exchange_code_for_token,
    get_long_lived_token, resolve_ig_account,
)
from tools.instagram_accounts import save_ig_account

logger = logging.getLogger("core8.instagram.oauth")

router = APIRouter()


def _page(title: str, body_html: str, ok: bool) -> HTMLResponse:
    """Render a minimal result page. body_html must already be escaped/safe."""
    color = "#16a34a" if ok else "#dc2626"
    doc = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{html.escape(title)}</title></head>
<body style="font-family:system-ui,sans-serif;max-width:32rem;margin:4rem auto;padding:0 1rem">
  <h2 style="color:{color}">{html.escape(title)}</h2>
  <p>{body_html}</p>
  <p style="color:#777">You can close this tab and return to Core8-AI.</p>
</body></html>"""
    return HTMLResponse(doc, status_code=200 if ok else 400)


@router.get("/api/instagram/oauth/callback")
async def instagram_oauth_callback(request: Request):
    params = request.query_params

    # The user denied consent, or Meta returned an error.
    if params.get("error"):
        desc = params.get("error_description") or params.get("error") or "Unknown error"
        return _page("Instagram connection cancelled", html.escape(desc), ok=False)

    code = params.get("code", "")
    state = params.get("state", "")
    if not code or not state:
        return _page("Connection failed",
                     "Missing code or state in the callback.", ok=False)

    if not consume_oauth_state(state):
        logger.warning("Instagram OAuth callback with an invalid or expired state")
        return _page(
            "Connection failed",
            "The connection link was invalid or expired. Start again from Core8-AI.",
            ok=False,
        )

    try:
        short_token = await exchange_code_for_token(code)
        long_token, expires_in = await get_long_lived_token(short_token)
        account = await resolve_ig_account(long_token)
    except GraphAPIError as e:
        logger.error("Instagram OAuth failed: %s", e)
        return _page("Connection failed", html.escape(str(e)), ok=False)

    expires_at = None
    if expires_in > 0:
        expires_at = (datetime.datetime.utcnow()
                      + datetime.timedelta(seconds=expires_in)).isoformat()

    await save_ig_account(
        ig_user_id=account["ig_user_id"],
        fb_page_id=account["fb_page_id"],
        username=account["username"],
        access_token=long_token,
        token_expires_at=expires_at,
    )
    logger.info("Instagram account connected: @%s", account["username"])
    return _page(
        "Instagram connected",
        f"Connected as <b>@{html.escape(account['username'])}</b>. "
        "Core8-AI can now manage this account.",
        ok=True,
    )
