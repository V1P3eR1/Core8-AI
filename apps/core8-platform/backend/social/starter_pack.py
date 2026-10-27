"""Starter pack — real sources, benchmark notes and original Hebrew content drafts.

Written by Claude during the 2026-10-27 build session from sources it read
that day. Unlike demo_data.py these are NOT fake records: the sources are
real URLs with what they actually say, and the drafts are original content
that still needs the owner's review (status='draft', origin='starter_pack').
They contain no customer, result, price or partnership claims.

Seed:  POST /api/social/starter-pack/seed   or   python -m social.starter_pack
"""

from .content import create_item, list_items, upsert_source
from .db import audit

SESSION_DATE = "2026-10-27"

REAL_SOURCES: list[dict] = [
    {
        "title": "Meta's AI agent for WhatsApp Business is now available globally",
        "url": "https://www.techcrunch.com/2026/06/03/metas-ai-agent-for-whatsapp-business-is-now-available-globally/",
        "publisher": "TechCrunch", "published_at": "2026-06-03 00:00:00", "event_at": "2026-06-03 00:00:00",
        "source_type": "reporting", "confidence": "high", "topic": "whatsapp_agents",
        "summary": "Meta הפכה את ה-Business Agent (בוט שירות לקוחות) לזמין גלובלית ב-WhatsApp אחרי כשנתיים של ניסויים "
                   "(הודו, מקסיקו). לפי Meta הסוכן עונה על שאלות, ממליץ על מוצרים, קובע פגישות, מסנן לידים ומעביר לאדם. "
                   "תמחור: תוכנית לכלול בחלק מחבילות WhatsApp Business Premium; לעסקים גדולים — לפי שימוש בטוקנים (תוכניות, לא מחירים סופיים).",
        "relevance": "Meta עצמה נכנסת לשכבת הסוכנים. ההזדמנות של Core8AI: להסביר מה הסוכן המובנה עושה ומה דורש התאמה, "
                     "אינטגרציה למערכות העסק וגבולות אישור אנושי.",
        "unknowns": "זמינות בישראל ובעברית, מחירים סופיים, מה בדיוק ניתן להתאים בלי פלטפורמת Enterprise.",
        "angle": "'Meta נתנה לכם סוכן חינם — אז מה בכלל צריך לבנות?' — ההבדל בין מענה גנרי לתהליך שמחובר לעסק שלכם.",
    },
    {
        "title": "Meta Conversations 2026 — Business Agent, Business Agent Platform, WhatsApp Business Discovery (vendor recap)",
        "url": "https://www.aichat.com/blog/meta-conversations-2026-announcements",
        "publisher": "AiChat (vendor blog)", "published_at": "2026-06-15 00:00:00", "event_at": "2026-06-03 00:00:00",
        "source_type": "opinion", "confidence": "medium", "topic": "ai_news",
        "summary": "סיכום ספק צד-שלישי של כנס Meta Conversations 2026 (לונדון, 3 ביוני): Business Agent חינמי ב-WhatsApp/Messenger/Instagram, "
                   "פלטפורמת Enterprise עם חיבורים ל-Shopify/Zendesk, ו-Discovery (חיפוש עסקים בתוך WhatsApp). כולל דעות של הספק — לא הצהרות Meta.",
        "relevance": "מפת הדרכים של Meta לסוכנים עסקיים. יש לצטט רק את מה שמופיע במקורות רשמיים של Meta.",
        "unknowns": "תאריכי השקה, מחירי חבילות בתשלום, זמינות אזורית. חלק מהטענות הן פרשנות של הספק.",
        "angle": "חדשות AI לבעלי עסקים: מה באמת הוכרז, מה דעה של ספקים, ומה לעשות עם זה השבוע.",
    },
    {
        "title": "Introducing Graph API v26.0 and Marketing API v26.0",
        "url": "https://developers.facebook.com/blog/post/2026/07/29/introducing-graph-api-v26-and-marketing-api-v26/",
        "publisher": "Meta for Developers", "published_at": "2026-07-29 00:00:00", "event_at": "2026-07-29 00:00:00",
        "source_type": "official", "confidence": "high", "topic": "saas_building",
        "summary": "גרסה v26 של Graph API: אין שינויים בפרסום תוכן/Insights של אינסטגרם; שינויים רוחביים (ביטול pretty/debug/date_format, ETag), "
                   "הסרת Commerce Order Management API, לוח הוצאה משימוש: v20 הוסרה 24.9.2026, v21 תוסר 21.1.2027.",
        "relevance": "המערכת שלנו משתמשת ב-Graph API — יש לנעול גרסה נתמכת ולעקוב אחרי לוח ההוצאה משימוש.",
        "unknowns": "אין.",
        "angle": "מאחורי הקלעים: למה מערכת שמפרסמת לאינסטגרם צריכה 'תאריך תפוגה' לגרסת ה-API.",
    },
    {
        "title": "Changelog for Instagram Platform",
        "url": "https://developers.facebook.com/documentation/instagram-platform/changelog",
        "publisher": "Meta for Developers", "published_at": "2026-07-30 00:00:00", "event_at": None,
        "source_type": "official", "confidence": "high", "topic": "ai_news",
        "summary": "עדכונים אחרונים: 30.7.2026 media_url מושמט במדיה עם הגנות זכויות; 22.6.2026 תווית AI Info — פרמטר is_ai_generated ביצירת קונטיינר; "
                   "22.6.2026 מדד link_clicks לסטורי (Facebook Login בלבד); 1.6.2026 Instagram Audio API ושדה media_audio_type; 15.5.2026 oEmbed ללא טוקן.",
        "relevance": "תוכן שנוצר ב-AI אפשר (וכדאי) לסמן דרך is_ai_generated. מדדי סטורי חדשים זמינים רק בנתיב Facebook Login — הנתיב שבחרנו.",
        "unknowns": "האם תווית ה-AI משפיעה על הפצה — Meta לא מפרטת.",
        "angle": "שקיפות: 'הפוסט הזה נוצר בעזרת AI' — למה אנחנו מסמנים את זה, ומה זה אומר לכם כצרכני תוכן.",
    },
    {
        "title": "Instagram Platform — Overview (login paths, permissions, access levels, rate limits)",
        "url": "https://developers.facebook.com/documentation/instagram-platform/overview",
        "publisher": "Meta for Developers", "published_at": None, "event_at": None,
        "source_type": "official", "confidence": "high", "topic": "saas_building",
        "summary": "שני נתיבי התחברות: Instagram Login (ללא דף פייסבוק, הרשאות instagram_business_*) ו-Facebook Login (דורש דף פייסבוק מקושר, "
                   "הרשאות instagram_basic / instagram_content_publish / instagram_manage_insights + pages_show_list, pages_read_engagement). "
                   "Unified Login מומלץ לאינטגרציות חדשות. Standard Access מספיק לחשבונות עם תפקיד באפליקציה; Advanced Access דורש App Review ואימות עסקי.",
        "relevance": "הבסיס לתיעוד META_SETUP.md ולבחירת הנתיב ל-MVP.",
        "unknowns": "מה בדיוק משתנה ב-Unified Login לעומת Facebook Login לפרסום — דורש קריאה נוספת לפני מעבר.",
        "angle": "למה 'לחבר את האינסטגרם' לוקח יותר מלחיצה אחת — הסבר לבעל עסק על הרשאות ואישורים.",
    },
    {
        "title": "AI Adoption Among Small Businesses: Qualitative Insights from the Small Business Credit Survey",
        "url": "https://www.frbsf.org/research-and-insights/publications/system-research-san-francisco-fed/2026/09/ai-adoption-among-small-businesses-qualitative-insights-small-business-credit-survey/",
        "publisher": "Federal Reserve Bank of San Francisco", "published_at": "2026-09-01 00:00:00", "event_at": None,
        "source_type": "official", "confidence": "high", "topic": "problem_workflow",
        "summary": "ממצאים איכותניים מסקר האשראי לעסקים קטנים (ארה\"ב, נתוני 2024): 'כמעט 40%' מהמשיבים משתמשים או מתכננים להשתמש ב-AI. "
                   "חסמים: רגולציה, עלות כלים, זמן וכוח אדם להדרכה, פערי ידע ביישום. סיבות לאי-אימוץ: דיוק, קניין רוחני, מרכזיות האינטראקציה האנושית.",
        "relevance": "החששות האמיתיים של בעלי עסקים — בסיס לפילר 'בעיה → תהליך → פתרון' ולתוכן שמכבד את החשש מדיוק ומאובדן המגע האנושי.",
        "unknowns": "נתוני ארה\"ב, לא ישראל. אין נתון ישראלי מקביל במקור זה.",
        "angle": "'AI לא מחליף את המגע האנושי — הוא מחליף את ההעתק-הדבק': איך לשמור אדם בלולאה.",
    },
    {
        "title": "The Briefing: Enterprise Agents (Anthropic event page)",
        "url": "https://anthropic.com/events/the-briefing-enterprise-agents",
        "publisher": "Anthropic", "published_at": None, "event_at": None,
        "source_type": "official", "confidence": "medium", "topic": "ai_plain",
        "summary": "דף אירוע של Anthropic בנושא סוכנים ארגוניים. תוכן האירוע לא נקרא בסשן זה — נשמר כמקור רשמי לבדיקה.",
        "relevance": "רקע ל'AI בשפה פשוטה': מה זה סוכן ארגוני ומה ההבדל מצ'אט.",
        "unknowns": "תאריך, תוכן ההרצאות, הכרזות — לא אומתו.",
        "angle": "לפני שמשתמשים: 'סוכן' זה לא 'צ'אט' — שלושת ההבדלים שחשובים לעסק.",
    },
    {
        "title": "Early Findings on Small Business Use of AI",
        "url": "https://frbsf.org/research-and-insights/publications/community-development-articles/2026/03/ai-and-small-businesses",
        "publisher": "Federal Reserve Bank of San Francisco", "published_at": "2026-03-01 00:00:00", "event_at": None,
        "source_type": "official", "confidence": "medium", "topic": "problem_workflow",
        "summary": "מאמר מוקדם יותר של אותו צוות על שימוש עסקים קטנים ב-AI. לא נקרא במלואו בסשן זה — נשמר לבדיקה.",
        "relevance": "משלים את מקור ספטמבר 2026; שימושי להשוואת מגמה לאורך זמן אם יש נתונים.",
        "unknowns": "ממצאים ספציפיים — לקרוא לפני ציטוט.",
        "angle": "נושא רלוונטי — טרנד לא מאומת.",
    },
]

BENCHMARKS: list[dict] = [
    {
        "title": "[Benchmark] GaryVee content strategy — one pillar piece → 30+ micro pieces",
        "url": "https://garyvaynerchuk.com/THE-GARYVEE-CONTENT-STRATEGY-HOW-TO-GROW-AND-DISTRIBUTE-YOUR-BRANDS-SOCIAL-MEDIA-CONTENT/",
        "publisher": "garyvaynerchuk.com", "published_at": None, "source_type": "benchmark", "confidence": "high",
        "topic": "founder_journey",
        "summary": "מודל מבני: פריט עוגן ארוך (וולוג/הרצאה/פודקאסט) → חיתוך לעשרות פריטים קצרים מותאמים לכל פלטפורמה → הפצה יומית → "
                   "המיקרו מחזיר תשומת לב לעוגן. מקרה הבוחן מדווח על 30+ פריטים מהרצאה אחת.",
        "relevance": "מה לאמץ: עוגן אחד בשבוע (למשל שיחה מוקלטת של לב על בעיה עסקית) → רילס, קרוסלה וסטורי מאותו חומר. מה לא: לא להעתיק סגנון או טקסט.",
        "unknowns": "המספרים (35M צפיות) הם של המקרה שלהם — לא מעידים על תוצאה צפויה לנו.",
        "angle": "תהליך הפקה: 'הקלטה אחת → שבוע תוכן' כשיטת עבודה, לא כהבטחה.",
    },
    {
        "title": "[Benchmark] Alex Hormozi — value equation as a positioning lens ($100M Offers summary)",
        "url": "https://www.supersummary.com/100m-offers/summary/",
        "publisher": "SuperSummary (secondary)", "published_at": None, "source_type": "benchmark", "confidence": "medium",
        "topic": "invitation",
        "summary": "עדשה מבנית: ערך נתפס עולה כשהתוצאה הרצויה והסבירות להשיגה עולות, וכשהזמן והמאמץ של הלקוח יורדים. "
                   "הצעה 'מאוגדת' קשה להשוואת מחיר. (מקור משני — סיכום ספר.)",
        "relevance": "לכל פוסט: לנסח את הבעיה במונחי הלקוח (זמן, מאמץ, סיכון) ולא במונחי טכנולוגיה. בלי הבטחות תוצאה.",
        "unknowns": "המקור הוא סיכום, לא הספר; אין לצטט כאילו ציטוט של הורמוזי.",
        "angle": "'מה זה חוסך לכם בפועל' — מסגור של זמן ומאמץ, לא של פיצ'רים.",
    },
    {
        "title": "[Benchmark] Dan Martell — SaaS education & authority positioning (public profile)",
        "url": "https://www.castmagic.io/creators/dan-martell",
        "publisher": "Castmagic (secondary profile)", "published_at": None, "source_type": "benchmark", "confidence": "low",
        "topic": "saas_building",
        "summary": "פרופיל משני בלבד. התוכן של מרטל נשען על הוראה שיטתית למייסדי SaaS (מערכות, האצלה, זמן). לא נקראו מקורות ראשוניים בסשן זה.",
        "relevance": "מבנה: 'עיקרון → דוגמה → צעד ליישום'. מתאים לפילר 'בניית SaaS'. אין לאמץ סגנון אישי.",
        "unknowns": "דורש קריאה של מקור ראשוני לפני הסקת מסקנות.",
        "angle": "נושא רלוונטי — טרנד לא מאומת.",
    },
    {
        "title": "[Benchmark] Meta — product communication for business AI (TechCrunch coverage of the global Business Agent launch)",
        "url": "https://www.techcrunch.com/2026/06/03/metas-ai-agent-for-whatsapp-business-is-now-available-globally/",
        "publisher": "TechCrunch", "published_at": "2026-06-03 00:00:00", "source_type": "benchmark", "confidence": "high",
        "topic": "ai_news",
        "summary": "איך Meta מתקשרת סוכן AI לעסקים: רשימת פעולות קונקרטיות (עונה, ממליץ, קובע פגישה, מסנן, מעביר לאדם) במקום הבטחות.",
        "relevance": "לאמץ: לתאר יכולות כפעולות יומיומיות. 'מעביר לאדם כשצריך' הוא חלק מההצעה, לא חולשה.",
        "unknowns": "אין.",
        "angle": "'מה הסוכן עושה ביום שלישי בשעה 22:00' — תיאור פעולות במקום תכונות.",
    },
]

# Note: `url` duplicates are detected by hash — the TechCrunch benchmark entry shares a URL with
# the news entry, so only the first insert wins. We keep it in the list for documentation
# and the seed function reports it as a duplicate.

_DEMO_NOTE = "דוגמה להמחשה — לא לקוח אמיתי"


def _reel(title, pillar, audience, hooks, script, shots, on_screen, cover, caption, cta, sources):
    return {
        "format": "reel", "title": title, "pillar": pillar, "audience": audience, "caption": caption,
        "package": {
            "origin": "starter_pack", "label": "טיוטה מקורית מסשן ההקמה — דורשת אישור של לב",
            "hooks": hooks, "audience": audience, "script": script, "duration_s": 40,
            "shot_list": shots, "on_screen_text": on_screen, "subtitles": "כתוביות בעברית לפי התסריט",
            "cover_text": cover, "caption": caption, "cta": cta, "sources": sources,
            "required_assets": ["וידאו 9:16 1080×1920 MP4 (H.264/AAC), 30–45 שניות — טרם צולם", "תמונת כריכה 1080×1920 JPEG"],
            "production_status": "script_only", "is_ai_generated": False,
            "notes": "תסריט בלבד — אינו וידאו. הצילום/ההפקה הם של לב (ללא דימוי פנים/קול מיוצר).",
        },
    }


REEL_PACKAGES = [
    _reel(
        "פנייה ב-22:00 — מה קורה איתה עד הבוקר?", "problem_workflow", "smb",
        ["לקוח כתב לכם ב-22:00. מה קרה להודעה הזו עד 8 בבוקר?",
         "ההודעה הכי יקרה בעסק היא זו שלא נענתה.",
         "לא צריך לענות בלילה. צריך תהליך שלא שוכח."],
        [{"t": "0–3s", "text": "לקוח כתב לכם ב-22:00. מה קרה להודעה עד 8 בבוקר?"},
         {"t": "3–12s", "text": "ברוב העסקים: היא נקברת מתחת לעוד 30 הודעות, ובבוקר מישהו מנסה להיזכר מי זה היה."},
         {"t": "12–30s", "text": "תהליך אפשרי (דוגמה להמחשה): הודעה נכנסת → מענה קצר ואמיתי: 'קיבלנו, נחזור בבוקר' → 2–3 שאלות סינון "
                                 "(מה הצורך, מתי נוח) → רישום בטבלה אחת → התראה לבעל העסק ב-8:00 עם סיכום."},
         {"t": "30–38s", "text": "האדם עדיין מחליט מה לענות. המערכת רק דואגת שלא ישכחו."},
         {"t": "38–42s", "text": "רוצים לראות איך זה נראה אצלכם? כתבו 'לילה' בתגובות."}],
        ["לב מדבר למצלמה, תאורה טבעית, 9:16", "מסך טלפון עם צ'אט פיקטיבי (ללא שמות אמיתיים)", "מסך: טבלה פשוטה עם 3 שורות דוגמה"],
        ["22:00", "'קיבלנו, נחזור בבוקר'", "סינון: צורך · זמן נוח", "התראה 08:00", "דוגמה להמחשה"],
        "ההודעה מ-22:00",
        "לקוח כתב לכם ב-22:00. מה קרה להודעה הזו עד הבוקר?\n\nלא צריך לענות בלילה. צריך תהליך שלא שוכח: קבלה → שאלות סינון → רישום → "
        "התראה בבוקר. האדם עדיין מחליט מה לענות.\n\nדוגמה להמחשה, לא לקוח אמיתי.\n\nרוצים לראות איך זה נראה אצלכם? כתבו 'לילה'.\n\n"
        "#סוכניAI #WhatsApp #עסקיםקטנים #אוטומציה",
        "לכתוב 'לילה' בתגובות", [],
    ),
    _reel(
        "Meta נתנה לכם סוכן חינם — אז מה בכלל צריך לבנות?", "whatsapp_agents", "smb",
        ["Meta הכריזה על סוכן AI חינמי ב-WhatsApp. אז למה בכלל לבנות משהו?",
         "סוכן גנרי עונה. תהליך מחובר לעסק — מבצע.",
         "השאלה היא לא 'יש סוכן?' אלא 'הסוכן יודע מה קורה אצלכם?'"],
        [{"t": "0–3s", "text": "Meta הכריזה על סוכן AI חינמי לעסקים ב-WhatsApp. אז למה לבנות משהו משלכם?"},
         {"t": "3–12s", "text": "לפי הדיווחים, הסוכן המובנה עונה על שאלות, ממליץ על מוצרים, קובע פגישות ומסנן לידים. זה הרבה — לעסק שכל המידע שלו כבר ב-Meta."},
         {"t": "12–30s", "text": "ההבדל: האם הסוכן יודע מה יש במלאי, מי הלקוח החוזר, מה כתוב ביומן, ומה אסור לו להבטיח? חיבור למערכות העסק וגבולות אישור — זה החלק שצריך לבנות."},
         {"t": "30–38s", "text": "התחילו מהסוכן החינמי. כשתרגישו את התקרה — תדעו בדיוק מה חסר."},
         {"t": "38–42s", "text": "יש לכם שאלה על זה? כתבו 'סוכן'."}],
        ["לב מדבר למצלמה", "מסך: כותרת הכתבה (צילום מסך הוגן, עם קרדיט)", "תרשים פשוט: סוכן ← יומן/מלאי/CRM"],
        ["סוכן חינמי של Meta", "עונה · ממליץ · קובע · מסנן", "מה הוא לא יודע?", "מלאי · יומן · גבולות", "התחילו מהחינמי"],
        "סוכן חינם של Meta?",
        "Meta הכריזה (יוני 2026) שה-Business Agent שלה זמין גלובלית ב-WhatsApp. לפי הדיווח הוא עונה, ממליץ, קובע פגישות ומסנן לידים.\n\n"
        "אז מה בכלל צריך לבנות? את החיבור לעסק שלכם: מלאי, יומן, לקוחות חוזרים — ואת הגבולות: מה אסור לו להבטיח.\n\n"
        "התחילו מהחינמי. כשתרגישו את התקרה, תדעו מה חסר.\n\nמקור: TechCrunch, 3.6.2026.\n\n#WhatsApp #Meta #סוכניAI #עסקים",
        "לכתוב 'סוכן' בתגובות",
        [{"title": "Meta's AI agent for WhatsApp Business is now available globally (TechCrunch, 2026-06-03)",
          "url": "https://www.techcrunch.com/2026/06/03/metas-ai-agent-for-whatsapp-business-is-now-available-globally/"}],
    ),
    _reel(
        "למה המערכת שלי מפרסמת רק אחרי אישור", "saas_building", "founders",
        ["בניתי מערכת שמפרסמת לאינסטגרם לבד. ואז הוספתי לה שלושה בלמים.",
         "אוטומציה בלי בלם זה לא פיצ'ר, זה סיכון.",
         "הדבר הכי חשוב במערכת האוטומטית שלי הוא הכפתור שעוצר אותה."],
        [{"t": "0–3s", "text": "בניתי מערכת שמפרסמת לאינסטגרם לבד. ואז הוספתי לה שלושה בלמים."},
         {"t": "3–14s", "text": "בלם 1: אישור קשור לגרסה. אם שיניתי מילה בכיתוב אחרי האישור — האישור נמחק. הקוד בודק, לא ה-AI."},
         {"t": "14–26s", "text": "בלם 2: כשהבקשה לפרסום נשלחה ולא חזרה תשובה — המערכת לא שולחת שוב. היא בודקת מה באמת קרה, ואם לא בטוח — עוצרת ומבקשת אדם."},
         {"t": "26–36s", "text": "בלם 3: השהיית חירום. כפתור אחד שעוצר כל פרסום עתידי."},
         {"t": "36–42s", "text": "ככה אני בונה אוטומציה לעסקים: קודם הבלמים. רוצים לראות את הקוד? כתבו 'קוד'."}],
        ["מסך: דשבורד עם סטטוסים (ללא נתוני לקוחות)", "לב מדבר למצלמה", "קלוז-אפ על כפתור 'השהיית חירום'"],
        ["3 בלמים", "אישור = גרסה", "לא שולחים פעמיים", "השהיית חירום", "מאחורי הקלעים"],
        "3 בלמים",
        "בניתי מערכת שמפרסמת לאינסטגרם לבד — ואז הוספתי לה שלושה בלמים.\n\n1. אישור קשור לגרסה: שינוי אחרי אישור מבטל את האישור.\n"
        "2. תשובה לא ודאית מהספק → לא שולחים שוב, בודקים, ואם לא בטוח — אדם מחליט.\n3. השהיית חירום.\n\n"
        "ככה אני בונה אוטומציה לעסקים: קודם הבלמים.\n\n#SaaS #מאחוריהקלעים #אוטומציה #AI",
        "לכתוב 'קוד' בתגובות", [],
    ),
]


def _carousel(title, pillar, audience, slides, caption, cta, sources, notes):
    return {
        "format": "carousel", "title": title, "pillar": pillar, "audience": audience, "caption": caption,
        "package": {"origin": "starter_pack", "label": "טיוטה מקורית מסשן ההקמה — דורשת אישור של לב",
                    "hook": slides[0]["title"], "structure": "הוק → תוכן → CTA", "slides": slides,
                    "visual_direction": "תבנית Core8 (כהה או בהירה), כותרת אחת לשקופית, עד שתי שורות טקסט.",
                    "caption": caption, "cta": cta, "sources": sources, "verification_notes": notes, "template": None,
                    "production_status": "assets_missing"},
    }


CAROUSEL_PACKAGES = [
    _carousel(
        "6 שאלות שלקוחות שואלים שוב ושוב — ואפשר להכין להן תשובות", "whatsapp_agents", "smb",
        [{"kicker": "דוגמה להמחשה", "title": "6 שאלות שלקוחות שואלים שוב ושוב", "body": "ואפשר להכין להן תשובה מראש — לפני שמדברים על AI בכלל."},
         {"title": "1. מתי אתם פתוחים?", "body": "תשובה קבועה + חריגים (חגים). עדכון במקום אחד."},
         {"title": "2. איפה אתם?", "body": "כתובת, חניה, איך מגיעים. קישור לניווט."},
         {"title": "3. כמה זה עולה?", "body": "רק מה שאושר לפרסום. כל השאר — 'נשמח לתאם שיחה'."},
         {"title": "4. יש מקום השבוע?", "body": "בלי יומן מחובר — 'בודקים וחוזרים'. עם יומן — תשובה אמיתית."},
         {"title": "5. איך מזמינים?", "body": "שלושה צעדים, לא עשרה. קישור אחד."},
         {"title": "6. מה להביא / להכין?", "body": "רשימה קצרה. חוסכת שיחת טלפון."},
         {"title": "הצעד הראשון", "body": "לכתוב את 6 התשובות במסמך אחד. רק אז לדבר על אוטומציה."}],
        "6 שאלות שלקוחות שואלים שוב ושוב — ואפשר להכין להן תשובות עוד לפני שמדברים על AI.\n\n"
        "שעות · מיקום · מחיר (רק מה שאושר) · זמינות · איך מזמינים · מה להביא.\n\n"
        "הצעד הראשון: לכתוב את 6 התשובות במסמך אחד. דוגמה להמחשה.\n\nשמרו לפעם הבאה שמישהו שואל.\n\n#עסקיםקטנים #שירותלקוחות #WhatsApp",
        "לשמור את הפוסט", [], "ללא טענות מספריות או תוצאות. כל השאלות גנריות.",
    ),
    _carousel(
        "לפני פרויקט AI: 5 שאלות לשיחת ההיכרות", "invitation", "enterprise",
        [{"kicker": "לצוותי הנהלה", "title": "לפני פרויקט AI: 5 שאלות", "body": "אם אין תשובה לאחת מהן — עדיין מוקדם להתחיל."},
         {"title": "1. איזה תהליך?", "body": "אחד. עם התחלה וסוף ברורים. לא 'לשפר את השירות'."},
         {"title": "2. מי הבעלים?", "body": "אדם אחד שמחליט מה הסוכן רשאי לעשות — ומה לא."},
         {"title": "3. אילו נתונים?", "body": "איפה הם יושבים, מי רשאי לגשת, מה אסור שייצא החוצה."},
         {"title": "4. מה דורש אישור אנושי?", "body": "הצעות מחיר? החזרים? הבטחות ללקוח? — כותבים את זה מראש."},
         {"title": "5. איך נדע שזה עובד?", "body": "מדד אחד, נמדד לפני ואחרי. בלי מדד — אין פרויקט."},
         {"title": "יש תשובות ל-5?", "body": "אז יש על מה לדבר. כתבו לנו 'שיחה'."}],
        "לפני שמתחילים פרויקט AI בארגון — חמש שאלות לשיחת ההיכרות:\n\nאיזה תהליך · מי הבעלים · אילו נתונים · מה דורש אישור אנושי · איך נדע שזה עובד.\n\n"
        "אם אין תשובה לאחת מהן, עדיין מוקדם להתחיל — וזה בסדר.\n\nיש תשובות לחמש? כתבו 'שיחה'.\n\n#AI #ארגונים #תהליכים #Core8AI",
        "לכתוב 'שיחה'", [], "ללא הבטחות תוצאה. ללא אזכור לקוחות.",
    ),
]

STORY_CONCEPTS = [
    {"title": "סקר: איזו משימה הייתם מאצילים ל-AI קודם?", "pillar": "problem_workflow", "audience": "smb",
     "frames": [{"text": "איזו משימה הייתם מאצילים ל-AI קודם?", "sticker": "poll: תיאום פגישות / מענה להודעות / סיכומים / מעקב פניות"},
                {"text": "התשובות עוזרות לי להחליט על מה לכתוב השבוע.", "sticker": None}]},
    {"title": "מאחורי הקלעים: לוח הפרסומים (ללא נתוני לקוחות)", "pillar": "founder_journey", "audience": "founders",
     "frames": [{"text": "ככה נראה לוח הפרסומים שבניתי — כל פוסט עובר אישור לפני שהוא יוצא.", "sticker": None},
                {"text": "שאלות? שלחו.", "sticker": "question box"}]},
    {"title": "חדשות AI במשפט אחד", "pillar": "ai_news", "audience": "smb",
     "frames": [{"text": "Meta: סוכן AI לעסקים זמין גלובלית ב-WhatsApp (יוני 2026). מה זה אומר לכם? מחר ברילס.", "sticker": "link (אם נתמך)"}]},
    {"title": "שאלה אחת: מה הדבר שאתם עושים ידנית כל יום?", "pillar": "invitation", "audience": "smb",
     "frames": [{"text": "מה הדבר שאתם עושים ידנית כל יום ושונאים?", "sticker": "question box"},
                {"text": "אענה על כמה מהם בפומבי (בלי שמות).", "sticker": None}]},
    {"title": "מושג ביום: 'סוכן' vs 'צ'אט'", "pillar": "ai_plain", "audience": "founders",
     "frames": [{"text": "צ'אט עונה. סוכן מבצע — ומבקש אישור כשצריך.", "sticker": None},
                {"text": "רוצים עוד מושגים? הצביעו.", "sticker": "poll: כן / מספיק לי"}]},
]


async def seed_starter_pack(actor: str = "system") -> dict:
    out = {"sources": 0, "benchmarks": 0, "duplicates": 0, "reels": 0, "carousels": 0, "stories": 0}
    for s in REAL_SOURCES:
        _, created = await upsert_source({**s, "provider": "claude-session", "is_demo": 0, "trend_verified": 0,
                                          "raw": {"collected_on": SESSION_DATE}})
        out["sources" if created else "duplicates"] += 1
    for b in BENCHMARKS:
        _, created = await upsert_source({**b, "provider": "claude-session", "is_demo": 0, "trend_verified": 0,
                                          "raw": {"collected_on": SESSION_DATE}})
        out["benchmarks" if created else "duplicates"] += 1
    existing = {i["title"] for i in await list_items(limit=1000)}
    for r in REEL_PACKAGES:
        if r["title"] not in existing:
            await create_item({**r, "status": "draft", "production_status": "script_only",
                               "review_notes": "טיוטה מסשן ההקמה (Claude). לבדוק עובדות, לערוך, לצלם."}, actor=actor)
            out["reels"] += 1
    for c in CAROUSEL_PACKAGES:
        if c["title"] not in existing:
            await create_item({**c, "status": "draft", "production_status": "assets_missing",
                               "review_notes": "טיוטה מסשן ההקמה (Claude). לערוך שקופיות ולרנדר."}, actor=actor)
            out["carousels"] += 1
    for st in STORY_CONCEPTS:
        if st["title"] not in existing:
            await create_item({"format": "story", "title": st["title"], "pillar": st["pillar"], "audience": st["audience"],
                               "caption": "", "status": "draft", "production_status": "assets_missing",
                               "package": {"origin": "starter_pack", "frames": st["frames"], "story_text": st["frames"][0]["text"],
                                           "cta": st["frames"][-1].get("sticker") or "", "required_assets": ["פריים 9:16"],
                                           "notes": "סקרים/מדבקות/לינקים — ידנית באפליקציה; ה-API מפרסם תמונה/וידאו בלבד."},
                               "review_notes": "קונספט סטורי מסשן ההקמה."}, actor=actor)
            out["stories"] += 1
    await audit(actor, "starter_pack_seeded", "starter_pack", None, out)
    return out


if __name__ == "__main__":
    import asyncio
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from database import init_db
    from social.schema import init_social_schema

    async def _main():
        await init_db()
        await init_social_schema()
        print(await seed_starter_pack("cli"))

    asyncio.run(_main())
