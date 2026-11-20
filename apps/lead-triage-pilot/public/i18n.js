/*
 * Core8-AI lead-triage pilot - Hebrew / English interface text.
 * English source strings are the keys; anything missing here shows in English.
 * The only thing stored in the browser is the chosen language ("c8lang").
 */
(function (root) {
  'use strict';

  var HE = {
    // page chrome
    'Core8-AI — lead-triage pilot (local)': 'Core8-AI — פיילוט מיון לידים (מקומי)',
    'PILOT · DRAFTS ONLY': 'פיילוט · טיוטות בלבד',
    'This tool cannot send anything. You copy an approved reply and send it yourself.': 'הכלי הזה לא יכול לשלוח דבר. מעתיקים תשובה מאושרת ושולחים אותה לבד.',
    'Lead-triage pilot · local': 'פיילוט מיון לידים · מקומי',
    'Download evidence report': 'הורדת דוח ראיות',
    'Sign out': 'יציאה',
    'Pilot metrics': 'מדדי הפיילוט',
    'Engine: live model ({model}) — inquiry text is sent to the model API': 'מנוע: מודל חי ({model}) — נוסח הפנייה נשלח ל-API של המודל',
    'Engine: offline rules — nothing leaves this computer': 'מנוע: כללים לא-מקוונים — שום דבר לא יוצא מהמחשב הזה',
    'Audit log intact · {n} events': 'יומן הביקורת תקין · {n} אירועים',
    'AUDIT LOG BROKEN at event {n}': 'יומן הביקורת פגום באירוע {n}',

    // add an inquiry
    'Add an inquiry': 'הוספת פנייה',
    'Inquiry text, as received': 'נוסח הפנייה, כפי שהתקבל',
    'Channel': 'ערוץ',
    'Received at': 'התקבל בתאריך',
    'Your own short label (optional, stays local)': 'תווית קצרה משלך (לא חובה, נשארת מקומית)',
    'Stored only in a file on this computer. With the offline engine nothing leaves it.': 'נשמר רק בקובץ במחשב הזה. במנוע הלא-מקוון שום דבר לא יוצא ממנו.',
    'Add and draft a reply': 'הוספה וניסוח תשובה',

    // website-form e-mail and mailbox
    'Add a website-form e-mail': 'הוספת אימייל מטופס האתר',
    'Paste the full text of a [CORE8-LEAD] e-mail': 'הדביקו את הטקסט המלא של אימייל [CORE8-LEAD]',
    'Import lead': 'ייבוא ליד',
    'Check mailbox now': 'בדיקת תיבת הדואר עכשיו',
    'Only e-mails signed by the website form handler are accepted.': 'מתקבלים רק אימיילים שנחתמו על ידי טופס האתר.',
    'No shared secret is set, so unsigned e-mails are accepted and marked as such.': 'לא הוגדר סוד משותף, ולכן אימיילים לא חתומים מתקבלים ומסומנים ככאלה.',
    'Mailbox check failed at {when}: {error}': 'בדיקת תיבת הדואר נכשלה ב-{when}: {error}',
    'Mailbox reading is on (read-only). Not checked yet.': 'קריאת תיבת הדואר פעילה (קריאה בלבד). עדיין לא נבדקה.',
    'Mailbox checked {when} (read-only): {created} new, {duplicates} already imported, {rejected} rejected.': 'תיבת הדואר נבדקה ב-{when} (קריאה בלבד): {created} חדשים, {duplicates} כבר יובאו, {rejected} נדחו.',
    'This submission was already imported.': 'הפנייה הזו כבר יובאה.',

    // queue
    'Queue': 'תור',
    'Filter by status': 'סינון לפי סטטוס',
    'Approved': 'אושר',
    'Sent': 'נשלח',
    'All': 'הכול',
    'Nothing here.': 'אין כאן כלום.',
    'Urgent': 'דחוף',

    // statuses, categories, channels, sources
    'Needs review': 'ממתין לבדיקה',
    'Approved — not sent': 'אושר — לא נשלח',
    'Sent by you': 'נשלח על ידך',
    'Rejected': 'נדחה',
    'Drafting': 'בניסוח',
    'Demo / meeting': 'הדגמה / פגישה',
    'Pricing': 'מחיר',
    'Support': 'תמיכה',
    'Partnership': 'שותפות',
    'Not a lead': 'לא ליד',
    'Other': 'אחר',
    'Website form': 'טופס האתר',
    'Email': 'אימייל',
    'WhatsApp': 'WhatsApp',
    'Phone note': 'רישום שיחת טלפון',
    'Social': 'רשתות חברתיות',
    'Typed in': 'הוקלד ידנית',
    'signature verified': 'חתימה אומתה',
    'unsigned': 'לא חתום',
    'low': 'נמוכה',
    'normal': 'רגילה',
    'high': 'גבוהה',

    // metrics
    'Inquiries': 'פניות',
    'Awaiting review': 'ממתינות לבדיקה',
    'Approved as drafted': 'אושרו כפי שנוסחו',
    'Approved after edit': 'אושרו אחרי עריכה',
    'Median review time': 'זמן בדיקה חציוני',
    'Median received → sent': 'חציון מקבלה עד שליחה',
    ' min': ' דק׳',

    // review panel
    'Review': 'בדיקה',
    'Select an inquiry from the queue.': 'בחרו פנייה מהתור.',
    'Reference': 'מספר פנייה',
    'Status': 'סטטוס',
    'Received': 'התקבל',
    'Category': 'קטגוריה',
    'Urgency': 'דחיפות',
    'Drafted by': 'נוסח על ידי',
    'Live model ({model})': 'מודל חי ({model})',
    'Offline rules': 'כללים לא-מקוונים',
    'Why': 'נימוק',
    'Source': 'מקור',
    'Matched keywords: ': 'מילות מפתח שזוהו: ',
    'No keyword rule matched': 'אף כלל מילות מפתח לא התאים',
    'Contact (from the form)': 'פרטי קשר (מהטופס)',
    'Name': 'שם',
    'Business': 'עסק',
    'E-mail': 'אימייל',
    'Phone': 'טלפון',
    'Consent': 'הסכמה',
    'Given': 'ניתנה',
    'Given (text {id})': 'ניתנה (נוסח {id})',
    'Inquiry': 'הפנייה',
    'The live model was not used for this draft ({reason}). Offline rules drafted it instead.': 'המודל החי לא שימש לטיוטה הזו ({reason}). הכללים הלא-מקוונים ניסחו אותה במקומו.',
    'Draft mentions a price or percentage': 'הטיוטה מזכירה מחיר או אחוזים',
    'Draft makes a promise': 'הטיוטה כוללת הבטחה',
    'Draft contains a link': 'הטיוטה כוללת קישור',
    'Draft has a placeholder to fill in': 'בטיוטה יש שדה שצריך להשלים',
    'Suggested meeting times': 'מועדי פגישה מוצעים',
    'Add to reply': 'הוספה לתשובה',
    'Built from fixed working hours only. This tool cannot see your calendar: check you are free before offering a time.': 'נבנה משעות עבודה קבועות בלבד. הכלי לא רואה את היומן שלך: בדקו שאתם פנויים לפני שמציעים מועד.',
    'Draft (rejected)': 'טיוטה (נדחתה)',
    'Approved reply': 'תשובה מאושרת',
    'Draft reply — edit freely before approving': 'טיוטת תשובה — אפשר לערוך חופשי לפני האישור',
    'Approve reply': 'אישור התשובה',
    'Draft again': 'ניסוח מחדש',
    'Reject instead — reason (required)': 'לדחות במקום — סיבה (חובה)',
    'Reject draft': 'דחיית הטיוטה',
    'Rejected {when} — {reason}': 'נדחה ב-{when} — {reason}',
    'Approved after your edits {when}.': 'אושר אחרי העריכות שלך ב-{when}.',
    'Approved as drafted {when}.': 'אושר כפי שנוסח ב-{when}.',
    'Copy reply': 'העתקת התשובה',
    'I sent it myself': 'שלחתי בעצמי',
    'You marked this as sent {when}.': 'סימנת כנשלח ב-{when}.',
    'Copied': 'הועתק',
    'Select and copy manually': 'סמנו והעתיקו ידנית',
    'Press Ctrl+C to copy': 'לחצו Ctrl+C להעתקה',

    // leads table
    'Leads table': 'טבלת לידים',
    'Download table (CSV)': 'הורדת הטבלה (CSV)',
    'Stays on this computer. The CSV contains names and contact details: treat it as personal data.': 'נשאר במחשב הזה. קובץ ה-CSV מכיל שמות ופרטי קשר: יש להתייחס אליו כמידע אישי.',
    'Ref': 'מס׳',
    'Contact': 'פרטי קשר',
    'No leads yet.': 'אין לידים עדיין.',

    // sign-in page
    'Core8-AI — sign in': 'Core8-AI — כניסה',
    'Lead agent — sign in': 'סוכן הלידים — כניסה',
    'Password': 'סיסמה',
    'Sign in': 'כניסה',
    'One user. Five wrong passwords lock sign-in for fifteen minutes.': 'משתמש אחד. חמש סיסמאות שגויות נועלות את הכניסה לרבע שעה.',
    'Sign-in failed': 'הכניסה נכשלה',
    'Could not reach the server': 'אין חיבור לשרת',

    // messages the server sends back
    'Request failed': 'הבקשה נכשלה',
    'Internal error': 'שגיאה פנימית',
    'Wrong password': 'סיסמה שגויה',
    'Too many wrong passwords. Try again later.': 'יותר מדי סיסמאות שגויות. נסו שוב מאוחר יותר.',
    'No password has been set yet. The owner sets it on the server.': 'עדיין לא הוגדרה סיסמה. הבעלים מגדיר אותה בשרת.',
    'Inquiry text is required': 'חובה להזין את נוסח הפנייה',
    'Invalid received time': 'זמן הקבלה לא תקין',
    'Received time cannot be in the future': 'זמן הקבלה לא יכול להיות בעתיד',
    'A reason is required to reject': 'חובה לציין סיבה לדחייה',
    'Cannot approve an empty reply': 'אי אפשר לאשר תשובה ריקה',
    'Fill in or remove the [placeholder] before approving': 'יש להשלים או למחוק את השדה שבסוגריים המרובעים לפני האישור',
    'Request too large': 'הבקשה גדולה מדי',
    'Login required': 'נדרשת כניסה',
    'Unknown lead': 'ליד לא מוכר',
    'Mailbox reading is not configured': 'קריאת תיבת הדואר לא מוגדרת',
    'A decision is already recorded for this lead': 'כבר נרשמה החלטה לליד הזה',
    'Lead has no draft yet': 'לליד עדיין אין טיוטה',
    'Only an approved reply can be marked as sent': 'אפשר לסמן כנשלח רק תשובה מאושרת',
    'Submission time is in the future':'זמן השליחה של הפנייה נמצא בעתיד',
    'No CORE8 LEAD v1 block found': 'לא נמצא בלוק CORE8 LEAD v1',
    'More than one lead block in the message': 'יש יותר מבלוק ליד אחד בהודעה',
    'Lead block is not valid base64url': 'בלוק הליד אינו base64url תקין',
    'Lead is not signed, and this tool requires a signature': 'הליד לא חתום, והכלי הזה דורש חתימה',
    'Signature does not match: not from the form handler, or altered': 'החתימה לא תואמת: ההודעה לא הגיעה מטופס האתר, או ששונתה',
    'Lead block does not contain valid JSON': 'בלוק הליד לא מכיל JSON תקין',
    'Unsupported lead format version': 'גרסת פורמט הליד לא נתמכת',
    'Missing or invalid submission id': 'מזהה הפנייה חסר או לא תקין',
    'Missing or invalid submission time': 'זמן השליחה חסר או לא תקין',
    'Submission has no consent; it must not be processed': 'לפנייה אין הסכמה; אסור לעבד אותה',
    'Name is missing': 'השם חסר',
    'Invalid e-mail address': 'כתובת אימייל לא תקינה',
    'Invalid phone number': 'מספר טלפון לא תקין',
    'Neither e-mail nor phone was provided': 'לא נמסרו אימייל או טלפון',
    'The mail server refused the login. Check the address and the app password.': 'שרת הדואר דחה את הכניסה. בדקו את הכתובת ואת סיסמת האפליקציה.',
    'Could not open the inbox': 'לא ניתן לפתוח את תיבת הדואר הנכנס',
    'Mail connection failed': 'החיבור לשרת הדואר נכשל'
  };

  if (typeof module !== 'undefined' && module.exports) { module.exports = { HE: HE }; return; }

  var doc = root.document;
  var KEY = 'c8lang';
  var lang = 'en';
  // Private windows or blocked site data can make storage throw: the page must still work.
  try { lang = root.localStorage.getItem(KEY) || ''; } catch (e) { lang = ''; }
  if (lang !== 'he' && lang !== 'en') lang = 'he'; // Hebrew first; English is one click away and remembered

  function t(key, vars) {
    var s = lang === 'he' && Object.prototype.hasOwnProperty.call(HE, key) ? HE[key] : key;
    return vars ? s.replace(/\{(\w+)\}/g, function (m, k) { return k in vars ? String(vars[k]) : m; }) : s;
  }

  // Static markup: the English text (or attribute) in the HTML is the key, remembered on first pass.
  function apply() {
    doc.documentElement.lang = lang;
    doc.documentElement.dir = lang === 'he' ? 'rtl' : 'ltr';
    Array.prototype.forEach.call(doc.querySelectorAll('[data-i18n]'), function (n) {
      var k = n.getAttribute('data-i18n') || n.textContent.trim();
      n.setAttribute('data-i18n', k);
      n.textContent = t(k);
    });
    Array.prototype.forEach.call(doc.querySelectorAll('[data-i18n-aria]'), function (n) {
      var k = n.getAttribute('data-i18n-aria') || n.getAttribute('aria-label');
      n.setAttribute('data-i18n-aria', k);
      n.setAttribute('aria-label', t(k));
    });
    var b = doc.getElementById('lang');
    if (b) { b.textContent = lang === 'he' ? 'English' : 'עברית'; b.setAttribute('lang', lang === 'he' ? 'en' : 'he'); }
  }

  var api = { t: t, lang: function () { return lang; }, locale: function () { return lang === 'he' ? 'he-IL' : 'en-GB'; }, onChange: null };
  root.I18N = api;

  apply();
  var btn = doc.getElementById('lang');
  if (btn) btn.addEventListener('click', function () {
    lang = lang === 'he' ? 'en' : 'he';
    try { root.localStorage.setItem(KEY, lang); } catch (e) { /* the choice lasts for this page only */ }
    apply();
    if (api.onChange) api.onChange();
  });
})(typeof window !== 'undefined' ? window : globalThis);
