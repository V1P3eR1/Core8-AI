/*
 * Core8-AI landing page - DRAFT copy, Hebrew (primary) and English.
 * Headline, supporting copy and primary CTA are verbatim from
 * docs/LEV_CORE8_BRAND_BRIEF.md (PR #21), chosen by Lev (recorded in PR #32).
 * The remaining sections are Claude's draft and still need Lev's review.
 * Rules applied (from Lev's recorded decisions and docs/LEV_CORE8_BRAND_BRIEF.md):
 * no prices, no figures or percentages, no "24/7", no guarantees, no client
 * names, no claims of live integrations or results.
 */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.Core8Landing = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  return {
    langs: { he: { dir: 'rtl', label: 'עברית' }, en: { dir: 'ltr', label: 'English' } },
    // Set by the owner before launch. Empty formEndpoint = the form stays in
    // preview mode and sends nothing. On PHP hosting use 'server/lead.php', and
    // set consentTextId to the version of the approved consent wording (e.g. 'v1').
    // The page sends '<language>-<version>', e.g. 'he-v1'; the handler must list both.
    config: { formEndpoint: '', consentTextId: '', email: 'office.core8ai@gmail.com' },
    strings: {
      he: {
        'meta.title': 'Core8-AI — פחות עבודה חוזרת. יותר זמן לעסק שלך.',
        'meta.description': 'אנחנו ממפים תהליכים שחוזרים על עצמם, בוחנים היכן AI ואוטומציה יכולים לעזור, ובונים הדגמה ממוקדת לפני החלטה על הטמעה.',
        'draft.banner': 'טיוטת אב-טיפוס לאישור — הנוסח אינו סופי והטופס אינו מחובר',
        'nav.how': 'איך זה עובד', 'nav.control': 'שליטה', 'nav.process': 'התהליך', 'nav.founder': 'מי אנחנו', 'nav.faq': 'שאלות', 'nav.cta': 'קביעת שיחת אפיון',
        'skip': 'דילוג לתוכן',
        'hero.eyebrow': 'AI ואוטומציה לעסקים',
        'hero.title': 'פחות עבודה חוזרת. יותר זמן לעסק שלך.',
        'hero.lead': 'אנחנו ממפים תהליכים שחוזרים על עצמם, בוחנים היכן AI ואוטומציה יכולים לעזור, ובונים הדגמה ממוקדת לפני החלטה על הטמעה. היקף היכולות, המחיר והאינטגרציות נקבעים לאחר אפיון.',
        'hero.cta': 'קביעת שיחת אפיון', 'hero.cta2': 'איך זה עובד',
        'mock.label': 'המחשה בלבד — לא נתונים אמיתיים',
        'mock.title': 'ממתין לאישורך',
        'mock.item1.kind': 'פנייה חדשה מהאתר', 'mock.item1.text': 'בקשה לשיחת היכרות. הסוכן הכין תשובה והציע שני מועדים.',
        'mock.item2.kind': 'מעקב', 'mock.item2.text': 'ליד שלא נענה. הסוכן ניסח הודעת המשך לאישור.',
        'mock.approve': 'אישור', 'mock.edit': 'עריכה', 'mock.reject': 'דחייה',
        'mock.log': 'יומן: כל פעולה מתועדת עם מועד, מקור והחלטה',
        'how.title': 'דוגמה: איך סוכן מטפל בפניות נכנסות',
        'how.1.t': 'קולט את הפנייה', 'how.1.d': 'פנייה מטופס האתר נכנסת ישר לתור של הסוכן, עם ההסכמה שהלקוח נתן.',
        'how.2.t': 'מבין וממיין', 'how.2.d': 'הסוכן מזהה במה מדובר, מה דחוף ומה לא רלוונטי, ומסביר למה החליט כך.',
        'how.3.t': 'מכין החלטה', 'how.3.d': 'תשובה מנוסחת והצעה למועד פגישה מחכות לך, מוכנות לאישור, לעריכה או לדחייה.',
        'how.4.t': 'מבצע אחרי אישור', 'how.4.d': 'רק אחרי שאישרת, הפעולה מתבצעת ונרשמת ביומן.',
        'control.title': 'סוכן שאפשר לבקר',
        'control.lead': 'אוטומציה חוסכת עבודה חוזרת רק אם אפשר לסמוך עליה. לכן כל סוכן שאנחנו בונים נבנה כך שאפשר לבדוק מה הוא עשה ולמה.',
        'control.1.t': 'אישור אנושי', 'control.1.d': 'אתה קובע אילו פעולות דורשות אישור. פעולה מול לקוח לא יוצאת בלעדיו.',
        'control.2.t': 'יומן פעולות', 'control.2.d': 'כל צעד נרשם: מה נכנס, מה הסוכן הציע, מי אישר ומתי.',
        'control.3.t': 'הרשאות מינימליות', 'control.3.d': 'הסוכן מקבל גישה רק למה שהמשימה דורשת, ולא יותר.',
        'control.4.t': 'מתחילים בקטן', 'control.4.d': 'תהליך אחד, תקופת ניסיון מוגדרת, ומדדים שמסכימים עליהם מראש.',
        'process.title': 'איך מתחילים',
        'process.1.t': 'שיחת אפיון', 'process.1.d': 'ממפים יחד את התהליך שחוזר על עצמו ובודקים אם סוכן מתאים לו.',
        'process.2.t': 'הדגמה ממוקדת', 'process.2.d': 'בונים הדגמה על התהליך שלך, עם נתוני דוגמה, לפני כל התחייבות.',
        'process.3.t': 'פיילוט מבוקר', 'process.3.d': 'הסוכן עובד על פניות אמיתיות, ואתה מאשר כל פעולה.',
        'process.4.t': 'הרחבה', 'process.4.d': 'מרחיבים רק מה שהוכיח את עצמו בפיילוט.',
        'process.price': 'אין מחירון באתר. היקף העבודה, החיבורים והמחיר נקבעים אחרי האפיון, בהצעה כתובה.',
        'founder.title': 'מי עומד מאחורי Core8-AI',
        'founder.body': 'Core8-AI הוקמה על ידי לב שויחט, מהנדס מערכות מתחום הביטחון והתעופה. בתחומים האלה מערכת נבחנת לפי מה שקורה כשמשהו משתבש: מי מאשר, מה מתועד ואיך מתקנים. את אותה משמעת אנחנו מביאים לסוכני AI בעסק.',
        'faq.title': 'שאלות נפוצות',
        'faq.1.q': 'האם הסוכן שולח הודעות ללקוחות שלי לבד?', 'faq.1.a': 'לא כברירת מחדל. הסוכן מכין, ואתה מאשר. אילו פעולות יוכלו להתבצע בלי אישור זו החלטה שלך, והיא מתקבלת רק אחרי פיילוט.',
        'faq.2.q': 'לאילו מערכות הסוכן מתחבר?', 'faq.2.a': 'זה נקבע באפיון. אנחנו לא מבטיחים חיבור למערכת לפני שבדקנו אותה אצלך.',
        'faq.3.q': 'מה קורה עם המידע של הלקוחות שלי?', 'faq.3.a': 'הסוכן מקבל רק את המידע שהמשימה דורשת. לפני כל חיבור אמיתי מסכמים בכתב אילו נתונים עוברים, לאן ולכמה זמן.',
        'faq.4.q': 'כמה זה עולה?', 'faq.4.a': 'ההצעה ניתנת אחרי שיחת האפיון, כשברור מה היקף העבודה.',
        'form.title': 'קביעת שיחת אפיון',
        'form.lead': 'השאירו פרטים ונחזור אליכם לתיאום שיחה קצרה.',
        'form.name': 'שם מלא', 'form.company': 'שם העסק', 'form.email': 'אימייל', 'form.phone': 'טלפון', 'form.message': 'איזה תהליך הייתם רוצים לייעל?',
        'form.contactHint': 'נדרש אימייל או טלפון.',
        'form.consent': 'אני מסכים/ה ש-Core8-AI תשמור את הפרטים שמסרתי ותיצור איתי קשר בנוגע לפנייה זו, כמפורט במדיניות הפרטיות.',
        'form.privacyLink': 'למדיניות הפרטיות', 'footer.privacy': 'מדיניות פרטיות', 'footer.accessibility': 'הצהרת נגישות',
        'form.submit': 'שליחה',
        'form.err.name': 'נא למלא שם.', 'form.err.contact': 'נא למלא אימייל או טלפון תקינים.', 'form.err.consent': 'נדרשת הסכמה כדי לשלוח.',
        'form.preview': 'מצב תצוגה מקדימה: הטופס עדיין לא מחובר, ושום דבר לא נשלח.',
        'form.sending': 'שולח…', 'form.sent': 'תודה, הפנייה התקבלה. נחזור אליך בהקדם.',
        'form.err.send': 'לא הצלחנו לשלוח את הפנייה. אפשר לנסות שוב או לכתוב לנו במייל.',
        'form.err.rate': 'נשלחו יותר מדי פניות בזמן קצר. נא לנסות שוב מאוחר יותר.',
        'contact.or': 'אפשר גם לכתוב לנו:',
        'footer.rights': 'Core8-AI', 'footer.note': 'האתר אינו מציג תוצאות של לקוחות או נתוני ביצועים עד שיהיו כאלה, עם מקור ושיטת מדידה.'
      },
      en: {
        'meta.title': 'Core8-AI — Less repetitive work. More time for your business.',
        'meta.description': 'We map repetitive workflows, identify where AI and automation may help, and propose a scoped demonstration before implementation.',
        'draft.banner': 'Draft prototype for approval — copy is not final and the form is not connected',
        'nav.how': 'How it works', 'nav.control': 'Control', 'nav.process': 'Process', 'nav.founder': 'About', 'nav.faq': 'FAQ', 'nav.cta': 'Book a discovery conversation',
        'skip': 'Skip to content',
        'hero.eyebrow': 'AI and automation for business',
        'hero.title': 'Less repetitive work. More time for your business.',
        'hero.lead': 'We map repetitive workflows, identify where AI and automation may help, and propose a scoped demonstration before implementation. Capabilities, integrations, and pricing are confirmed during discovery.',
        'hero.cta': 'Book a discovery conversation', 'hero.cta2': 'How it works',
        'mock.label': 'Illustration only — not real data',
        'mock.title': 'Waiting for your approval',
        'mock.item1.kind': 'New website inquiry', 'mock.item1.text': 'Request for an intro call. The agent drafted a reply and proposed two times.',
        'mock.item2.kind': 'Follow-up', 'mock.item2.text': 'A lead with no reply yet. The agent drafted a follow-up for approval.',
        'mock.approve': 'Approve', 'mock.edit': 'Edit', 'mock.reject': 'Reject',
        'mock.log': 'Log: every action recorded with time, source and decision',
        'how.title': 'Example: how an agent handles incoming inquiries',
        'how.1.t': 'Takes in the inquiry', 'how.1.d': 'An inquiry from the website form goes straight into the agent\'s queue, with the consent the customer gave.',
        'how.2.t': 'Understands and sorts', 'how.2.d': 'The agent works out what it is about, what is urgent and what is not relevant, and explains why.',
        'how.3.t': 'Prepares a decision', 'how.3.d': 'A drafted reply and a proposed meeting time wait for you, ready to approve, edit or reject.',
        'how.4.t': 'Acts after approval', 'how.4.d': 'Only after you approve is the action carried out and recorded in the log.',
        'control.title': 'An agent you can audit',
        'control.lead': 'Automation only saves repetitive work if you can rely on it. So every agent we build is built so that you can check what it did and why.',
        'control.1.t': 'Human approval', 'control.1.d': 'You decide which actions need approval. Nothing customer-facing goes out without it.',
        'control.2.t': 'Action log', 'control.2.d': 'Every step is recorded: what came in, what the agent proposed, who approved and when.',
        'control.3.t': 'Least privilege', 'control.3.d': 'The agent gets access only to what the task needs, and no more.',
        'control.4.t': 'Start small', 'control.4.d': 'One process, a defined trial period, and measures agreed in advance.',
        'process.title': 'How we start',
        'process.1.t': 'Discovery call', 'process.1.d': 'Together we map the repetitive process and check whether an agent fits it.',
        'process.2.t': 'Focused demo', 'process.2.d': 'We build a demo on your process, with sample data, before any commitment.',
        'process.3.t': 'Controlled pilot', 'process.3.d': 'The agent works on real inquiries and you approve each action.',
        'process.4.t': 'Expansion', 'process.4.d': 'We extend only what proved itself in the pilot.',
        'process.price': 'There is no price list on this site. Scope, integrations and price are set after discovery, in a written proposal.',
        'founder.title': 'Who is behind Core8-AI',
        'founder.body': 'Core8-AI was founded by Lev Shoihat, a systems engineer from the defense and aerospace sector. In those fields a system is judged by what happens when something goes wrong: who approves, what is recorded and how it is corrected. We bring the same discipline to AI agents in a business.',
        'faq.title': 'Common questions',
        'faq.1.q': 'Does the agent message my customers on its own?', 'faq.1.a': 'Not by default. The agent prepares and you approve. Which actions may run without approval is your decision, taken only after a pilot.',
        'faq.2.q': 'Which systems does the agent connect to?', 'faq.2.a': 'That is settled in discovery. We do not promise an integration before we have checked it in your setup.',
        'faq.3.q': 'What happens to my customers\' information?', 'faq.3.a': 'The agent receives only what the task needs. Before any real connection we agree in writing which data moves, where to and for how long.',
        'faq.4.q': 'What does it cost?', 'faq.4.a': 'The proposal comes after the discovery call, once the scope of work is clear.',
        'form.title': 'Book a discovery call',
        'form.lead': 'Leave your details and we will get back to you to set up a short call.',
        'form.name': 'Full name', 'form.company': 'Business name', 'form.email': 'Email', 'form.phone': 'Phone', 'form.message': 'Which process would you like to improve?',
        'form.contactHint': 'An email or a phone number is required.',
        'form.consent': 'I agree that Core8-AI may keep the details I provided and contact me about this inquiry, as described in the privacy policy.',
        'form.privacyLink': 'Read the privacy policy', 'footer.privacy': 'Privacy policy', 'footer.accessibility': 'Accessibility statement',
        'form.submit': 'Send',
        'form.err.name': 'Please enter your name.', 'form.err.contact': 'Please enter a valid email or phone number.', 'form.err.consent': 'Consent is required to send.',
        'form.preview': 'Preview mode: the form is not connected yet, and nothing was sent.',
        'form.sending': 'Sending…', 'form.sent': 'Thank you, we received your inquiry and will get back to you soon.',
        'form.err.send': 'We could not send your inquiry. Please try again or write to us by email.',
        'form.err.rate': 'Too many inquiries were sent in a short time. Please try again later.',
        'contact.or': 'אפשר גם לכתוב לנו:',
        'contact.or': 'You can also write to us:',
        'footer.rights': 'Core8-AI', 'footer.note': 'This site shows no customer results or performance figures until they exist, with a source and a method.'
      }
    }
  };
});
