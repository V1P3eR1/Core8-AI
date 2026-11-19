"""Deterministic fact checker — flags sentences that always need human review.

Runs on captions and packages before review and on every edit. The result
is stored on the item (`sensitive_flags`, `fact_check`) and consulted by the
publishing gates: a flagged item can never be auto-published.
"""

import re

FLAG_LABELS = {
    "numbers": "מספרים/אחוזים — דורש מקור כתוב",
    "customers": "טענות על לקוחות או תוצאות",
    "prices": "מחירים, הנחות או הבטחות חוזיות",
    "personal": "מידע אישי או סודי",
    "legal_medical_financial": "ייעוץ משפטי/רפואי/פיננסי",
    "availability": "זמינות מוצר/שירות לא מאומתת",
    "likeness": "דמות/פנים/קול של אדם",
    "controversial": "טענה שלילית או שנויה במחלוקת",
    "unsourced_claim": "טענה ללא מקור",
}

_RULES: list[tuple[str, re.Pattern]] = [
    ("numbers", re.compile(r"(\d+(?:[.,]\d+)?\s*%|\b\d{2,}\b\s*(?:לקוחות|עסקים|שעות|ימים|לידים|אחוז))")),
    ("customers", re.compile(r"(הלקוח(?:ות)? שלנו|לקוח(?:ות)? (?:מרוצ|חוסכ|הרוויח)|מקרה בוחן|case study|עדות|המלצה של)", re.I)),
    ("prices", re.compile(r"(₪|\$|\bש\"ח\b|מחיר|הנחה|חינם לחלוטין|בחינם|אחריות מלאה|הבטחה|מובטח)", re.I)),
    ("personal", re.compile(r"(ת\.?ז\.?|תעודת זהות|מספר טלפון|כתובת מגורים|סודי|confidential)", re.I)),
    ("legal_medical_financial", re.compile(r"(ייעוץ משפטי|עצה משפטית|רפואי|תרופה|אבחנה|השקעה|תשואה|הלוואה|מס הכנסה|עו\"ד ממליץ)", re.I)),
    ("availability", re.compile(r"(זמין (?:עכשיו|היום|מיידית)|כבר אצלנו|השקנו|יצא לשוק|available now)", re.I)),
    ("likeness", re.compile(r"(הפנים של|קול של|דיפ-?פייק|deepfake|avatar של לב|voice clone)", re.I)),
    ("controversial", re.compile(r"(גרוע|נוכל|שקרן|מתחרה(?:ים)? (?:גרוע|משקר|נכשל)|הכי גרוע|הונאה)", re.I)),
]

_CLAIM_WORDS = re.compile(r"(מחקר(?:ים)? מראה|לפי נתונים|הוכח|מוכח|הסטטיסטיקה|רוב העסקים|כל העסקים)", re.I)


def check_text(text: str, sources: list[dict] | None = None) -> dict:
    """Return {flags: [...], findings: [{flag, label, excerpt}], ok_for_auto: bool}."""
    findings: list[dict] = []
    for flag, pat in _RULES:
        for m in pat.finditer(text or ""):
            start = max(0, m.start() - 30)
            findings.append({"flag": flag, "label": FLAG_LABELS[flag],
                             "excerpt": (text[start:m.end() + 30]).strip()})
    if _CLAIM_WORDS.search(text or "") and not sources:
        m = _CLAIM_WORDS.search(text)
        findings.append({"flag": "unsourced_claim", "label": FLAG_LABELS["unsourced_claim"],
                         "excerpt": text[max(0, m.start() - 30): m.end() + 30].strip()})
    flags = sorted({f["flag"] for f in findings})
    return {"flags": flags, "findings": findings, "ok_for_auto": not flags}


def check_item(caption: str, package: dict) -> dict:
    """Checks caption + every text field of the package."""
    texts = [caption or ""]
    for key in ("hooks", "script", "on_screen_text", "cover_text", "slides", "story_text", "cta"):
        v = package.get(key)
        if isinstance(v, str):
            texts.append(v)
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, str):
                    texts.append(x)
                elif isinstance(x, dict):
                    texts.extend(str(t) for t in x.values() if isinstance(t, str))
    sources = package.get("sources") or []
    return check_text("\n".join(texts), sources)
