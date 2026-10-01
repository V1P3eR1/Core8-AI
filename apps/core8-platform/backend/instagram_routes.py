"""Read-only REST endpoints for the Instagram calendar / queue UI.

The frontend uses these to render the connected account, the content plans,
the scheduled-posts queue, and live insights. The same data is reachable via
LLM tools — these endpoints just wrap them for a non-chat client.

All routes are JWT-protected via the router-level dependency.
"""

from fastapi import APIRouter, Depends

from security.jwt_auth import require_jwt
from tools.instagram_accounts import get_account_insights, get_account_summary
from tools.instagram_publish import list_scheduled_posts
from tools.plan_artifacts import get_content_plan, list_content_plans

router = APIRouter(prefix="/api/instagram", dependencies=[Depends(require_jwt)])


@router.get("/account")
async def api_account():
    summary = await get_account_summary()
    return {"connected": summary is not None, "account": summary}


@router.get("/plans")
async def api_list_plans(limit: int = 50):
    return await list_content_plans(limit=limit)


@router.get("/plans/{plan_id}")
async def api_get_plan(plan_id: str):
    return await get_content_plan(plan_id)


@router.get("/scheduled-posts")
async def api_list_scheduled_posts(status: str = "", limit: int = 100):
    return await list_scheduled_posts(status=status, limit=limit)


@router.get("/insights")
async def api_get_insights(days: int = 7):
    return await get_account_insights(period_days=days)
