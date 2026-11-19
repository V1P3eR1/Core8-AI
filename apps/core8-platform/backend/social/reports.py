"""Analyst — weekly report from real database records only.

Observation (facts from the DB) and recommendation (judgement, clearly
separated) never mix. Missing metrics are named, never estimated. Demo
records are excluded unless the report itself is a demo report.
"""

import datetime

from .db import LOCAL_TZ, execute, fetch_all, fetch_one, jdump, jload, new_id, now_utc, utc_str
from .metrics import ACCOUNT_METRICS, METRIC_LABELS
from .settings import get_setting


async def build_weekly_report(days: int = 7, include_demo: bool | None = None) -> dict:
    pub = await get_setting("publishing")
    include_demo = pub.get("demo_mode", True) if include_demo is None else include_demo
    end = now_utc()
    start = end - datetime.timedelta(days=days)
    s, e = utc_str(start), utc_str(end)
    demo_sql = "" if include_demo else " AND is_demo=0"

    jobs = await fetch_all("SELECT type, status, COUNT(*) AS n FROM sm_jobs WHERE created_at BETWEEN ? AND ? "
                           "GROUP BY type, status", (s, e))
    drafts = await fetch_one(f"SELECT COUNT(*) AS n FROM sm_content_items WHERE created_at BETWEEN ? AND ?{demo_sql}", (s, e))
    approvals = await fetch_one("SELECT COUNT(*) AS n FROM sm_approvals WHERE approved_at BETWEEN ? AND ?", (s, e))
    sources = await fetch_all(f"SELECT title, url, publisher, source_type, confidence, relevance, trend_verified FROM sm_sources "
                              f"WHERE discovered_at BETWEEN ? AND ?{demo_sql} ORDER BY discovered_at DESC LIMIT 25", (s, e))
    pubs = await fetch_all(
        "SELECT p.state, p.mode, p.provider_media_id, p.permalink, p.last_error, p.published_at, i.title, i.format, i.is_demo "
        "FROM sm_publications p JOIN sm_content_items i ON i.id=p.content_item_id "
        f"WHERE p.updated_at BETWEEN ? AND ?{' AND i.is_demo=0' if not include_demo else ''}", (s, e))
    metrics = await fetch_all("SELECT scope, metric, value, source, content_item_id FROM sm_metrics WHERE fetched_at BETWEEN ? AND ? "
                              + ("" if include_demo else "AND source!='demo' "), (s, e))
    leads = await fetch_all(f"SELECT name, source, business_type, status, lead_date FROM sm_leads WHERE created_at BETWEEN ? AND ?{demo_sql}",
                            (s, e))
    present = {m["metric"] for m in metrics if m["scope"] == "account"}
    missing = [METRIC_LABELS.get(m, m) for m in ACCOUNT_METRICS if m not in present]
    for manual in ("leads", "relevant_replies"):
        if manual not in present:
            missing.append(METRIC_LABELS[manual])

    published = [p for p in pubs if p["state"] == "published"]
    failed = [p for p in pubs if p["state"] in ("failed", "needs_manual_review")]
    observations = [
        f"{drafts['n'] if drafts else 0} טיוטות נוצרו, {approvals['n'] if approvals else 0} אישורים ניתנו.",
        f"{len(published)} פרסומים הושלמו ({sum(1 for p in published if p['mode'] == 'live')} אמיתיים, "
        f"{sum(1 for p in published if p['mode'] == 'mock')} בסימולציה), {len(failed)} נכשלו/דורשים בדיקה.",
        f"{len(sources)} מקורות חדשים נאספו; {sum(1 for x in sources if x['trend_verified'])} עם טרנד מאומת.",
        f"{len(leads)} לידים נרשמו (ידנית/שהתקבלו כדין).",
    ]
    recommendations = []
    if not metrics:
        recommendations.append("אין מדדים השבוע — לחבר חשבון אמיתי או להזין מדדים ידנית לפני שמסיקים מסקנות.")
    if failed:
        recommendations.append("לטפל בפרסומים שנכשלו/דורשים בדיקה לפני תזמון חדש.")
    if len(sources) < 3:
        recommendations.append("לבדוק שהמחקר היומי רץ (worker) — מעט מקורות נאספו.")
    recommendations.append("לבחור ניסוי אחד לשבוע הבא (למשל פורמט או שעת פרסום) ולמדוד רק אותו.")
    caveats = [
        "אין ייחוס ROI או לידים לפוסטים — הנתונים לא תומכים בכך.",
        "מדדים חסרים: " + (", ".join(missing) if missing else "אין"),
        "רשומות demo " + ("נכללות ומסומנות" if include_demo else "לא נכללות"),
    ]
    content = {
        "period": {"start_local": start.astimezone(LOCAL_TZ).isoformat(), "end_local": end.astimezone(LOCAL_TZ).isoformat()},
        "include_demo": include_demo,
        "work_completed": {"jobs": jobs, "drafts": drafts["n"] if drafts else 0, "approvals": approvals["n"] if approvals else 0},
        "research": sources,
        "publications": {"published": published, "failed": failed},
        "metrics": metrics, "missing_metrics": missing, "leads": leads,
        "observations": observations, "recommendations": recommendations,
        "lessons_next_week": ["למלא אחרי סקירת הבעלים — המערכת לא ממציאה לקחים."],
        "caveats": caveats,
    }
    rid = new_id()
    await execute("INSERT INTO sm_reports (id, kind, period_start, period_end, content) VALUES (?,?,?,?,?)",
                  (rid, "weekly", s, e, jdump(content)))
    return {"id": rid, "kind": "weekly", "period_start": s, "period_end": e, "content": content}


async def list_reports(limit: int = 20) -> list[dict]:
    rows = await fetch_all("SELECT * FROM sm_reports ORDER BY created_at DESC LIMIT ?", (limit,))
    for r in rows:
        r["content"] = jload(r["content"], {})
    return rows


async def get_report(rid: str) -> dict | None:
    r = await fetch_one("SELECT * FROM sm_reports WHERE id=?", (rid,))
    if r:
        r["content"] = jload(r["content"], {})
    return r
