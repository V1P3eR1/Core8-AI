"""Calendar planner — turns the editable content mix into proposed slots.

A proposal is just a list of (local datetime, format, pillar hint). Items are
NOT created or scheduled here; the owner picks a draft for a slot in the
dashboard (or the planning job attaches shortlisted drafts, still as
`needs_review`). No reach or growth is implied by the schedule.
"""

import datetime

from .db import LOCAL_TZ, fetch_all, now_utc, parse_utc
from .settings import PILLARS, get_setting

# Default local posting hours (editable in content_mix.slot_hours)
DEFAULT_SLOT_HOURS = {"reel": "18:00", "carousel": "12:00", "story": "10:00", "image": "12:00"}
# Default weekdays: 0=Mon … 6=Sun (Israel work week is Sun–Thu)
DEFAULT_DAYS = {"reel": [6, 2], "carousel": [1], "story": [6, 1, 3]}


async def propose_calendar(days: int = 30, start: datetime.date | None = None) -> list[dict]:
    mix = await get_setting("content_mix")
    hours = {**DEFAULT_SLOT_HOURS, **(mix.get("slot_hours") or {})}
    day_map = {**DEFAULT_DAYS, **(mix.get("days") or {})}
    reels = int(mix.get("reels_per_week", 2))
    carousels = int(mix.get("carousels_per_week", 1))
    stories = int(mix.get("story_days_per_week", 3))
    start = start or now_utc().astimezone(LOCAL_TZ).date() + datetime.timedelta(days=1)
    pillars = [p["key"] for p in PILLARS if p["key"] != "demos"]
    taken = {parse_utc(r["scheduled_for"]).astimezone(LOCAL_TZ).date() if parse_utc(r["scheduled_for"]) else None
             for r in await fetch_all("SELECT scheduled_for FROM sm_content_items WHERE scheduled_for IS NOT NULL "
                                      "AND status IN ('scheduled','approved','needs_review')")}
    slots: list[dict] = []
    pi = 0
    for d in range(days):
        day = start + datetime.timedelta(days=d)
        wd = day.weekday()
        for fmt, per_week in (("reel", reels), ("carousel", carousels), ("story", stories)):
            allowed = (day_map.get(fmt) or [])[:per_week]
            if wd in allowed:
                h, m = hours[fmt].split(":")
                local = datetime.datetime(day.year, day.month, day.day, int(h), int(m), tzinfo=LOCAL_TZ)
                slots.append({"local": local.isoformat(), "date": day.isoformat(), "format": fmt,
                              "pillar_hint": pillars[pi % len(pillars)] if fmt != "story" else "founder_journey",
                              "occupied": day in taken, "note": "היפותזה לעריכה — לא הבטחת חשיפה"})
                if fmt != "story":
                    pi += 1
    return slots
