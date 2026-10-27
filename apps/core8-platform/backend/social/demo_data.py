"""Demo records — ALWAYS labelled (is_demo=1), removable with one click.

Nothing here is a real client, result, price or verified trend. Sources are
real public URLs of official publishers (so the research inbox shows what a
record looks like), but their summaries are illustrative and dated as
"demo"; they are never presented as current research.
"""

from .db import execute, fetch_one, new_id, utc_str

DEMO_LABEL = "דוגמה להמחשה (demo)"

DEMO_SOURCES: list[dict] = [
    {
        "title": "[DEMO] WhatsApp Business Platform — official documentation",
        "url": "https://developers.facebook.com/docs/whatsapp/",
        "publisher": "Meta for Developers",
        "published_at": None,
        "summary": "דוגמת רשומה: תיעוד רשמי של פלטפורמת WhatsApp Business. רשומת demo — לא מחקר עדכני.",
        "relevance": "בסיס לפוסטים על סוכני WhatsApp: מה אפשר לעשות דרך ה-API הרשמי.",
        "unknowns": "אילו יכולות Core8AI מיישמת בפועל — דורש אישור של לב.",
        "source_type": "official", "confidence": "high", "trend_verified": 0,
        "angle": "'מה באמת אפשר לעשות עם WhatsApp API' — הסבר בשפה פשוטה לבעל עסק.",
        "topic": "whatsapp_agents", "provider": "demo",
    },
    {
        "title": "[DEMO] Instagram Platform — content publishing (official)",
        "url": "https://developers.facebook.com/documentation/instagram-platform/content-publishing",
        "publisher": "Meta for Developers",
        "published_at": None,
        "summary": "דוגמת רשומה: תיעוד רשמי של פרסום תוכן באינסטגרם דרך API. רשומת demo.",
        "relevance": "מסביר מה מערכת כמו Core8AI Social Manager יכולה ולא יכולה לפרסם אוטומטית.",
        "unknowns": "אין.",
        "source_type": "official", "confidence": "high", "trend_verified": 0,
        "angle": "מאחורי הקלעים: איך בניתי מערכת שמפרסמת רק אחרי אישור.",
        "topic": "founder_journey", "provider": "demo",
    },
    {
        "title": "[DEMO] Anthropic — Claude developer documentation",
        "url": "https://docs.claude.com/",
        "publisher": "Anthropic",
        "published_at": None,
        "summary": "דוגמת רשומה: תיעוד למפתחים של מודלי Claude. רשומת demo.",
        "relevance": "רקע ל'AI בשפה פשוטה': מה זה סוכן, מה זה כלי, למה צריך אישור אנושי.",
        "unknowns": "מחירים ומגבלות — להתעדכן במקור לפני פרסום.",
        "source_type": "official", "confidence": "high", "trend_verified": 0,
        "angle": "'סוכן AI זה לא צ'אט' — ההבדל בין צ'אטבוט לסוכן שמבצע פעולות.",
        "topic": "ai_plain", "provider": "demo",
    },
]

DEMO_IDEAS: list[dict] = [
    {"title": "[DEMO] למה סוכן WhatsApp לא מחליף את המזכירה — הוא מחזיר לה זמן",
     "pillar": "whatsapp_agents", "audience": "smb",
     "problem": "פניות ב-WhatsApp נענות באיחור אחרי שעות העבודה",
     "core_message": "סוכן עונה על שאלות חוזרות ומעביר לאדם כשצריך",
     "desired_action": "לשלוח הודעה 'רוצה לראות דוגמה'",
     "format": "reel", "business_goal": "פניות מוסמכות", "measurement": "תגובות/הודעות רלוונטיות (ידני)",
     "notes": DEMO_LABEL},
    {"title": "[DEMO] 5 משימות משרדיות שאפשר להפוך לתהליך אוטומטי",
     "pillar": "ai_office", "audience": "smb",
     "problem": "זמן הולך לאיבוד על תיאום, מעקב ותזכורות",
     "core_message": "בעיה → תהליך → פתרון אפשרי, בלי הבטחות",
     "desired_action": "לשמור את הפוסט",
     "format": "carousel", "business_goal": "מודעות למותג", "measurement": "שמירות ושיתופים (אם זמינים ב-API)",
     "notes": DEMO_LABEL},
]


async def seed_demo() -> dict:
    """Insert demo records if they are not already present."""
    from .content import create_idea, create_item, upsert_source
    created = {"sources": 0, "ideas": 0, "items": 0, "leads": 0, "metrics": 0, "inbound": 0}
    source_ids = []
    for s in DEMO_SOURCES:
        row, new = await upsert_source(dict(s, is_demo=1, status="new"))
        source_ids.append(row["id"])
        created["sources"] += int(new)
    existing = await fetch_one("SELECT COUNT(*) AS n FROM sm_ideas WHERE is_demo=1")
    if not existing or existing["n"] == 0:
        for i in DEMO_IDEAS:
            await create_idea(dict(i, is_demo=1, source_ids=source_ids[:1]))
            created["ideas"] += 1
    existing = await fetch_one("SELECT COUNT(*) AS n FROM sm_content_items WHERE is_demo=1")
    if not existing or existing["n"] == 0:
        await create_item({
            "format": "carousel", "title": "[DEMO] 5 משימות משרדיות שאפשר להפוך לתהליך",
            "pillar": "ai_office", "audience": "smb", "status": "draft", "is_demo": 1,
            "caption": "דוגמה להמחשה (demo). חמש משימות משרדיות שחוזרות על עצמן — ואיך תהליך אוטומטי יכול לעזור. "
                       "זו המחשה, לא תוצאה של לקוח.\n\n#AI #אוטומציה #עסקים",
            "package": {
                "hook": "חמש משימות שאוכלות לכם שעה ביום",
                "slides": [
                    {"title": "חמש משימות שאוכלות לכם שעה ביום", "body": "דוגמה להמחשה"},
                    {"title": "1. תיאום פגישות", "body": "הלוך-חזור של הודעות → טופס + יומן"},
                    {"title": "2. תזכורות ללקוחות", "body": "ידני → הודעה אוטומטית יום לפני"},
                    {"title": "3. סיכום שיחות", "body": "כתיבה ידנית → תמלול + סיכום לאישור"},
                    {"title": "4. מעקב אחרי פניות", "body": "אקסל → רשימה אחת עם סטטוס"},
                    {"title": "5. שאלות חוזרות", "body": "אותה תשובה שוב ושוב → מאגר תשובות"},
                    {"title": "מה הצעד הראשון?", "body": "לבחור משימה אחת. רק אחת."},
                ],
                "visual_direction": "רקע כהה, כותרת גדולה, מספר בולט, טקסט קצר.",
                "cta": "רוצים לדבר על משימה אחת אצלכם? כתבו 'משימה'.",
                "sources": [], "verification_notes": "ללא טענות מספריות. דוגמה להמחשה.",
            },
            "production_status": "assets_missing",
        }, actor="demo")
        created["items"] += 1
    existing = await fetch_one("SELECT COUNT(*) AS n FROM sm_leads WHERE is_demo=1")
    if not existing or existing["n"] == 0:
        await execute(
            "INSERT INTO sm_leads (id, name, handle, lead_date, source, business_type, need, status, next_action, notes, is_demo) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,1)",
            (new_id(), "[DEMO] בעל קליניקה", "@demo_clinic", utc_str()[:10], "הודעה באינסטגרם (דוגמה)",
             "קליניקה", "מענה אוטומטי לשאלות על שעות פעילות", "new", "לקבוע שיחת היכרות", DEMO_LABEL))
        created["leads"] += 1
    existing = await fetch_one("SELECT COUNT(*) AS n FROM sm_metrics WHERE source='demo'")
    if not existing or existing["n"] == 0:
        for metric, value in (("reach", 0), ("views", 0), ("saves", 0), ("shares", 0)):
            await execute(
                "INSERT INTO sm_metrics (id, scope, metric, value, source, note) VALUES (?,?,?,?,?,?)",
                (new_id(), "account", metric, value, "demo", "רשומת demo — ערכים מאופסים בכוונה; אין נתוני אמת"))
            created["metrics"] += 1
    existing = await fetch_one("SELECT COUNT(*) AS n FROM sm_inbound_messages WHERE is_demo=1")
    if not existing or existing["n"] == 0:
        await execute(
            "INSERT INTO sm_inbound_messages (id, kind, author, text, draft_reply, is_demo) VALUES (?,?,?,?,?,1)",
            (new_id(), "comment", "demo_user", "[DEMO] מעניין! זה עובד גם לעסק קטן?",
             "תודה! כן, הרעיון מתאים גם לעסקים קטנים — נשמח לשמוע על הצורך שלך בהודעה פרטית. (טיוטה — לא נשלחת אוטומטית)"))
        created["inbound"] += 1
    return created


async def clear_demo() -> dict:
    """Remove every demo record. Never touches live data."""
    from .media import delete_asset
    from .db import fetch_all
    removed = {}
    for aid in [r["id"] for r in await fetch_all("SELECT id FROM sm_assets WHERE is_demo=1")]:
        await delete_asset(aid)
    await execute("DELETE FROM sm_publications WHERE content_item_id IN (SELECT id FROM sm_content_items WHERE is_demo=1)")
    await execute("DELETE FROM sm_approvals WHERE content_item_id IN (SELECT id FROM sm_content_items WHERE is_demo=1)")
    for table, where in (("sm_content_items", "is_demo=1"), ("sm_ideas", "is_demo=1"), ("sm_sources", "is_demo=1"),
                         ("sm_leads", "is_demo=1"), ("sm_metrics", "source='demo'"),
                         ("sm_inbound_messages", "is_demo=1")):
        removed[table] = await execute(f"DELETE FROM {table} WHERE {where}")
    return removed
