"""Metrics — only what the API returns or the owner typed in. Nothing is estimated.

Account metrics (Instagram Insights, Facebook-Login path, checked 2026-10-27):
reach, accounts_engaged, total_interactions, profile_views, views
(`impressions` was deprecated for v22+). Post metrics: reach, likes, comments,
saved, shares, total_interactions, views.
In mock mode nothing is fetched and the UI shows "ספק לא מחובר".
"""

import datetime

from tools import instagram_api

from .db import audit, execute, fetch_all, fetch_one, new_id, utc_str
from .providers.instagram import get_provider, live_account_with_token

ACCOUNT_METRICS = ("reach", "views", "accounts_engaged", "total_interactions", "profile_views")
POST_METRICS = ("reach", "views", "likes", "comments", "saved", "shares", "total_interactions")
METRIC_LABELS = {"reach": "הגעה", "views": "צפיות", "accounts_engaged": "חשבונות שהגיבו",
                 "total_interactions": "אינטראקציות", "profile_views": "צפיות בפרופיל", "likes": "לייקים",
                 "comments": "תגובות", "saved": "שמירות", "shares": "שיתופים", "leads": "לידים (ידני)",
                 "relevant_replies": "תגובות רלוונטיות (ידני)"}


async def record(scope: str, metric: str, value: float, source: str, content_item_id: str | None = None,
                 provider_media_id: str | None = None, period_start: str | None = None,
                 period_end: str | None = None, note: str | None = None) -> dict:
    mid = new_id()
    await execute(
        "INSERT INTO sm_metrics (id, scope, content_item_id, provider_media_id, metric, value, period_start, period_end, "
        "source, note) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (mid, scope, content_item_id, provider_media_id, metric, float(value), period_start, period_end, source, note))
    return await fetch_one("SELECT * FROM sm_metrics WHERE id=?", (mid,))


async def refresh_metrics(period_days: int = 7) -> dict:
    """Pull account + per-post insights for published live items. Mock mode: no-op with a clear reason."""
    provider = get_provider()
    if provider.mode != "live":
        return {"fetched": 0, "reason": "ספק Instagram במצב mock — לא נמשכו מדדים (אין נתונים מומצאים)"}
    acct = await live_account_with_token()
    if not acct:
        return {"fetched": 0, "reason": "אין חשבון מחובר"}
    fetched, errors = 0, []
    until = utc_str()
    since = utc_str(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=period_days))
    try:
        raw = await instagram_api.fetch_account_insights(acct["ig_user_id"], acct["access_token"], period_days)
        for m in raw.get("data", []):
            val = (m.get("total_value") or {}).get("value")
            if val is not None:
                await record("account", m.get("name"), val, "api", period_start=since, period_end=until)
                fetched += 1
    except Exception as e:
        errors.append(f"account: {type(e).__name__}")
    pubs = await fetch_all("SELECT content_item_id, provider_media_id FROM sm_publications WHERE state='published' "
                           "AND mode='live' AND provider_media_id IS NOT NULL ORDER BY published_at DESC LIMIT 30")
    for p in pubs:
        try:
            raw = await instagram_api.fetch_post_insights(p["provider_media_id"], acct["access_token"])
            for m in raw.get("data", []):
                values = m.get("values") or []
                val = values[0].get("value") if values else (m.get("total_value") or {}).get("value")
                if val is not None:
                    await record("post", m.get("name"), val, "api", content_item_id=p["content_item_id"],
                                 provider_media_id=p["provider_media_id"], period_end=until)
                    fetched += 1
        except Exception as e:
            errors.append(f"post {p['provider_media_id']}: {type(e).__name__}")
    await audit("worker", "metrics_refreshed", "metrics", None, {"fetched": fetched, "errors": errors[:5]})
    return {"fetched": fetched, "errors": errors}


async def latest_account_metrics(include_demo: bool) -> dict:
    """Latest value per account metric with its source; names missing metrics explicitly."""
    rows = await fetch_all(
        "SELECT metric, value, source, fetched_at, period_start, period_end, note FROM sm_metrics WHERE scope='account' "
        + ("" if include_demo else "AND source!='demo' ") + "ORDER BY fetched_at DESC")
    latest: dict = {}
    for r in rows:
        latest.setdefault(r["metric"], r)
    missing = [m for m in ACCOUNT_METRICS if m not in latest]
    return {"metrics": latest, "missing": missing, "labels": METRIC_LABELS}


async def post_metrics(include_demo: bool) -> list[dict]:
    return await fetch_all(
        "SELECT m.*, i.title FROM sm_metrics m LEFT JOIN sm_content_items i ON i.id=m.content_item_id "
        "WHERE m.scope='post' " + ("" if include_demo else "AND m.source!='demo' ") + "ORDER BY m.fetched_at DESC LIMIT 300")
