# Core8-AI – הגדרת מחשב נייד עסקי
**יעד: עסק של מיליון דולר תוך שנה | גרסה מקצועית**

שם החברה: **Core8-AI**

---

## 1. מיקום קובץ הקונפיג (Windows)

**נתיב סטנדרטי:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**אם Claude מותקן כ-MSIX:**
הקובץ האמיתי עלול להיות תחת:
```
%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\claude_desktop_config.json
```

המלצה: Claude Desktop → Settings → Developer → Edit Config

**חובה:** החלף `YOUR_USERNAME` ואת ה-GitHub Token.

---

## 2. מבנה תיקיות מומלץ ל-Core8-AI

```
C:\Users\YOUR_USERNAME\
├── Documents\Core8-AI\          ← חוזים, פיננסים, לקוחות, מסמכים משפטיים
├── Projects\Core8-AI\           ← כל הקוד, סוכנים, RAG, מוצרים
│   ├── agents\
│   ├── rag-systems\
│   ├── client-deliverables\
│   └── internal-tools\
├── Desktop\Core8-AI-Work\       ← עבודה יומיומית פעילה
└── .claude\skills\              ← Skills של Core8-AI
```

---

## 3. MCP Servers שנבחרו (Least Privilege)

- **filesystem** – מוגבל רק לתיקיות Core8-AI
- **github** – ניהול ריפוזיטוריז של החברה
- **playwright** – בדיקות אוטומטיות ו-QA
- **memory** – זיכרון מתמשך לסוכנים

---

## 4. אבטחה (חובה – יש לכם מומחה סייבר)

- GitHub PAT עם הרשאות מינימליות + תאריך תפוגה קצר
- Secrets רק ב-1Password / Bitwarden
- אין הרצת MCP כ-Administrator
- BitLocker מופעל
- גיבוי יומי מוצפן של Documents\Core8-AI + Projects\Core8-AI
- הפרדת חשבונות: פיתוח ≠ פיננסים ≠ לקוחות

---

## 5. הערות לגבי מבנה משפטי עתידי (Trust + LLCs)

המבנה של Trust אמריקאי שמחזיק מספר LLCs (אחת מהן Core8-AI) הוא אפשרי בארה"ב, אך עבור תושב ישראל הוא מורכב מאוד מבחינת מיסוי ודיווח.

**אין לבצע שום פעולה** לפני ייעוץ מקצועי משולב (ארה"ב + ישראל).

בינתיים – כל הפעילות העסקית והפיתוח מתנהלים תחת שם **Core8-AI**.

---

## 6. צעדים מיידיים

1. החלף YOUR_USERNAME + Token בקובץ הקונפיג
2. העתק את הקובץ לנתיב הנכון והפעל מחדש את Claude
3. צור את מבנה התיקיות
4. התקן Claude Code:
   ```powershell
   irm https://claude.ai/install.ps1 | iex
   ```
5. צור Skills ראשונים תחת `.claude\skills\` (למשל: weekly-status, security-review, client-delivery)

---

**Core8-AI – בנה חזק, אבטח הכל, תגדל מהר.**
