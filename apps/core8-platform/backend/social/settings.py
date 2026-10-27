"""Settings store (sm_settings, JSON values) with typed defaults.

Keys:
  brand            — editable brand knowledge (seeded only with facts from the owner's brief)
  publishing       — mode + auto-publish boundaries + emergency pause
  content_mix      — editable weekly mix hypothesis
  schedules        — handled in sm_schedules (see scheduler.py)
  demo             — whether demo records are shown
"""

import copy

from .db import execute, fetch_all, fetch_one, jdump, jload, utc_str

UNKNOWN = "לא אושר עדיין — דורש אישור של לב"

DEFAULT_BRAND: dict = {
    "brand_name": "Core8AI",
    "owner_name": "Lev Shoihat",
    "website": "https://core8-ai.com",
    "market": "ישראל (ברירת מחדל)",
    "language": "עברית טבעית",
    "timezone": "Asia/Jerusalem",
    "description": "סוכני AI לעסקים: סוכני WhatsApp לשירות לקוחות, סינון לידים ותמיכה במכירות; "
                   "מזכירה ומנהלת משרד מבוססות AI; אוטומציה של תהליכים עסקיים; חיבור בין כלים "
                   "ומערכות מידע; מוצרי SaaS ופתרונות AI מותאמים לעסקים קטנים, בינוניים וגדולים.",
    "positioning": "מותג אישי ועסקי אמין סביב פתרונות AI פרקטיים.",
    "approved_services": [
        {"name": "סוכני WhatsApp (שירות לקוחות, סינון לידים, תמיכה במכירות)", "status": "מוזכר בברִיף — זמינות בפועל: " + UNKNOWN},
        {"name": "מזכירה ומנהלת משרד AI", "status": "מוזכר בברִיף — זמינות בפועל: " + UNKNOWN},
        {"name": "אוטומציה של תהליכים עסקיים", "status": "מוזכר בברִיף — זמינות בפועל: " + UNKNOWN},
        {"name": "חיבור כלים ומערכות מידע", "status": "מוזכר בברִיף — זמינות בפועל: " + UNKNOWN},
        {"name": "מוצרי SaaS ופתרונות AI מותאמים", "status": "מוזכר בברִיף — זמינות בפועל: " + UNKNOWN},
    ],
    "services_in_development": [],
    "target_audiences": [
        {"key": "smb", "label": "עסקים קטנים ובינוניים"},
        {"key": "enterprise", "label": "צוותי הנהלה וחברות גדולות"},
        {"key": "founders", "label": "מייסדים ויזמים"},
    ],
    "tone_of_voice": [
        "עברית טבעית, ישירה, מקצועית, ללא הגזמות שיווקיות",
        "מסביר בפשטות, מדגים בעיה → תהליך → פתרון אפשרי",
        "ללא הפחדות, ללא הבטחות תוצאה",
    ],
    "approved_claims": [
        "Core8AI עוסקת בסוכני AI לעסקים (לפי הברִיף של הבעלים)",
        "אתר החברה: https://core8-ai.com",
    ],
    "prohibited_claims": [
        "לקוחות, עדויות, תוצאות עסקיות, אחוזי שיפור, חיסכון כספי — אסור ללא אישור ומקור כתוב",
        "מחירים, הנחות, הבטחות חוזיות",
        "הסמכות, שותפויות, אינטגרציות שלא אושרו",
        "ייעוץ משפטי / רפואי / פיננסי",
        "טענות על מתחרים",
    ],
    "approved_links": ["https://core8-ai.com"],
    "contact_details": {"note": "פרטי קשר לפרסום: " + UNKNOWN},
    "topics_to_cover": [
        "AI בשפה פשוטה", "בעיה עסקית → תהליך → פתרון", "סוכני WhatsApp",
        "מזכירה AI ותהליכי משרד חכמים", "חדשות AI לבעלי עסקים", "בניית SaaS ומוצרים דיגיטליים",
        "המסע של לב כמייסד", "הדגמות ופרויקטים אמיתיים (רק באישור)", "הזמנה לשיחה על צורך עסקי",
    ],
    "topics_to_avoid": ["פוליטיקה", "השוואות שליליות למתחרים", "הבטחות תשואה", "מידע סודי של לקוחות"],
    "assumptions": [
        "שלב המוצרים, מספר הלקוחות, מקרי בוחן, מחירים ואינטגרציות — לא ידועים עד אישור הבעלים",
        "כל תרחיש בתוכן הוא הדגמה ומסומן כך",
        "פני/קול של לב — לא מיוצרים ולא מדומים ללא הסכמה מפורשת",
    ],
}

DEFAULT_PUBLISHING: dict = {
    "mode": "approval_required",       # draft_only | approval_required | automatic
    "emergency_pause": False,
    "auto": {
        "allowed_categories": [],        # pillar keys allowed for automatic publication
        "allowed_account_id": None,      # ig_user_id
        "max_posts_per_day": 1,
        "window_start": "09:00",         # local time, Asia/Jerusalem
        "window_end": "20:00",
        "review_topics": ["customers", "prices", "personal", "legal_medical_financial",
                          "availability", "likeness", "controversial"],
    },
    "demo_mode": True,                   # demo data visible; live publish blocked while True
}

DEFAULT_CONTENT_MIX: dict = {
    "note": "היפותזה ניסיונית לעריכה — לא התחייבות אלגוריתמית ולא הבטחת חשיפה.",
    "reels_per_week": 2,
    "carousels_per_week": 1,
    "story_days_per_week": 3,
}

PILLARS: list[dict] = [
    {"key": "ai_plain", "label": "AI בשפה פשוטה"},
    {"key": "problem_workflow", "label": "בעיה עסקית → תהליך → פתרון אפשרי"},
    {"key": "whatsapp_agents", "label": "סוכני WhatsApp"},
    {"key": "ai_office", "label": "מזכירה AI ותהליכי משרד חכמים"},
    {"key": "ai_news", "label": "חדשות AI לבעלי עסקים"},
    {"key": "saas_building", "label": "בניית SaaS ומוצרים דיגיטליים"},
    {"key": "founder_journey", "label": "המסע של לב ומאחורי הקלעים"},
    {"key": "demos", "label": "הדגמות ופרויקטים אמיתיים (רק באישור)"},
    {"key": "invitation", "label": "הזמנה לשיחה על צורך עסקי"},
]

DEFAULTS = {
    "brand": DEFAULT_BRAND,
    "publishing": DEFAULT_PUBLISHING,
    "content_mix": DEFAULT_CONTENT_MIX,
}


async def get_setting(key: str) -> dict:
    row = await fetch_one("SELECT value FROM sm_settings WHERE key=?", (key,))
    base = copy.deepcopy(DEFAULTS.get(key, {}))
    if row:
        stored = jload(row["value"], {})
        if isinstance(stored, dict):
            base.update(stored)
    return base


async def set_setting(key: str, value: dict) -> dict:
    await execute(
        "INSERT INTO sm_settings (key, value, updated_at) VALUES (?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (key, jdump(value), utc_str()),
    )
    return await get_setting(key)


async def all_settings() -> dict:
    rows = await fetch_all("SELECT key, value FROM sm_settings")
    out = {k: copy.deepcopy(v) for k, v in DEFAULTS.items()}
    for r in rows:
        v = jload(r["value"], {})
        if r["key"] in out and isinstance(v, dict):
            out[r["key"]].update(v)
        else:
            out[r["key"]] = v
    return out
