/*
 * Core8-AI customer demo — Hebrew / English strings and formatting helpers.
 * The transcript and audit trail store message KEYS, not rendered text, so the
 * whole conversation re-renders when the language is switched.
 */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.Core8DemoI18n = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  var LANGS = {
    en: { dir: 'ltr', locale: 'en-GB', label: 'English' },
    he: { dir: 'rtl', locale: 'he-IL', label: 'עברית' }
  };

  var S = {
    en: {
      'ui.pageTitle': 'Core8-AI — AI receptionist demo (simulation)',
      'ui.skip': 'Skip to the conversation',
      'ui.banner': 'DEMO / SIMULATION — no messages sent · no bookings created · fictional clinic and people',
      'ui.brandTag': 'Customer demo',
      'ui.controls': 'Demo controls',
      'ui.language': 'Language',
      'ui.reset': 'Reset demo',
      'ui.mobileOn': 'Mobile preview',
      'ui.mobileOff': 'Desktop view',
      'ui.h1': 'AI receptionist for a clinic',
      'ui.lead': 'Role-play a patient contacting the fictional Or Clinic. The receptionist classifies the inquiry, offers three hypothetical appointment slots, prepares a draft request and hands it to a human — all inside this browser tab.',
      'ui.progress': 'Demo progress',
      'ui.stage.inquiry': 'Inquiry',
      'ui.stage.classified': 'Classified',
      'ui.stage.slots': 'Slots offered',
      'ui.stage.draft': 'Draft request',
      'ui.stage.lead': 'Lead preview',
      'ui.stage.handoff': 'Human handoff',
      'ui.stageDone': 'done',
      'ui.stagePending': 'not yet',
      'ui.chatTitle': 'Conversation',
      'ui.clinicName': 'Or Clinic (fictional)',
      'ui.clinicSub': 'Virtual receptionist · simulated',
      'ui.agent': 'Receptionist',
      'ui.you': 'You',
      'ui.choices': 'Suggested replies',
      'ui.inputLabel': 'Your message',
      'ui.inputPlaceholder': 'Type a message — made-up details only',
      'ui.inputHint': 'Do not enter real personal or medical details. Nothing you type leaves this page.',
      'ui.send': 'Send',
      'ui.panelIntent': 'Inquiry classification',
      'ui.panelIntentEmpty': 'Send a message to see how the inquiry is classified.',
      'ui.intentLabel': 'Detected intent',
      'ui.methodLabel': 'How it was decided',
      'ui.matchedLabel': 'Matched keywords',
      'ui.method.keyword_rules': 'Local keyword rules (demo stand-in for the production AI model)',
      'ui.method.quick_reply': 'Customer tapped a suggested reply',
      'ui.method.none': 'No rule matched',
      'ui.panelSlots': 'Hypothetical appointment slots',
      'ui.panelSlotsEmpty': 'Slots appear after a booking request.',
      'ui.slotsNote': 'Mock availability generated from a fixture. No real calendar was read.',
      'ui.slotHypothetical': 'hypothetical',
      'ui.slotSelected': 'selected for draft',
      'ui.panelLead': 'Lead preview (local draft)',
      'ui.panelLeadEmpty': 'A lead preview is created when a slot is chosen or the conversation is handed off.',
      'ui.leadNote': 'Kept in this tab\'s memory only. Not saved to a CRM. Cleared on reset or reload.',
      'ui.field.leadId': 'Reference',
      'ui.field.recordStatus': 'Record status',
      'ui.field.name': 'Name',
      'ui.field.contact': 'Contact',
      'ui.field.intent': 'Intent',
      'ui.field.service': 'Visit type',
      'ui.field.slot': 'Requested slot',
      'ui.field.booking': 'Booking',
      'ui.field.message': 'Confirmation message',
      'ui.field.handoff': 'Human handoff',
      'ui.value.none': '—',
      'ui.value.notProvided': 'not provided',
      'ui.status.DRAFT': 'DRAFT',
      'ui.status.NOT_CREATED': 'NOT CREATED',
      'ui.status.NOT_SENT': 'NOT SENT',
      'ui.status.NOT_REQUESTED': 'Not requested',
      'ui.status.SIMULATED_PENDING_HUMAN_REVIEW': 'Simulated — pending human review (nobody was notified)',
      'ui.downloads': 'Download draft files',
      'ui.dlCsv': 'Lead (CSV)',
      'ui.dlJson': 'Lead (JSON)',
      'ui.dlTxt': 'Draft confirmation (TXT)',
      'ui.panelAudit': 'Step-by-step audit trail',
      'ui.auditNote': 'Every step below ran locally in this browser. None of it is evidence of a real operation.',
      'ui.auditSim': 'simulated',
      'ui.footer1': 'Core8-AI demonstrates how an AI receptionist can handle inquiries and prepare a booking request, with escalation to a human. The mockup uses fictitious availability; production integrations and results require separate configuration and validation.',
      'ui.footer2': 'Or Clinic, its staff, patients, hours and slots are invented for illustration. Any resemblance to a real clinic or person is coincidental.',

      'intent.booking': 'Book an appointment',
      'intent.hours': 'Opening hours',
      'intent.pricing': 'Prices',
      'intent.cancel': 'Change or cancel an appointment',
      'intent.urgent': 'Urgent / medical',
      'intent.human': 'Talk to a person',
      'intent.unknown': 'Unclear',

      'service.general': 'General consultation',
      'service.followup': 'Follow-up visit',
      'service.hygiene': 'Routine check-up',

      'reason.booking_review': 'booking request needs staff confirmation',
      'reason.urgent': 'urgent or medical inquiry',
      'reason.user_request': 'customer asked for a person',
      'reason.cancel_request': 'existing appointment change',
      'reason.unclear': 'inquiry not understood after two attempts',

      'choice.intent.booking': 'I\'d like to book an appointment',
      'choice.intent.hours': 'What are your opening hours?',
      'choice.intent.pricing': 'How much does a visit cost?',
      'choice.intent.urgent': 'It\'s urgent',
      'choice.handoff': 'Talk to a person',
      'choice.name.sample': 'Use fictional sample: {name}',
      'choice.contact.sample': 'Use fictional sample: {contact}',
      'choice.contact.skip': 'Skip',
      'choice.draft.handoff': 'Send to human review',
      'choice.draft.change_slot': 'Pick another slot',
      'choice.slot': '{slot}',
      'choice.service': '{service}',

      'bot.greeting': 'Hi! I\'m the virtual receptionist of Or Clinic — a fictional clinic created for this demo. How can I help?',
      'bot.ask_service': 'Happy to help with an appointment. What kind of visit do you need?',
      'bot.service_retry': 'Please pick one of the three visit types below (or type 1, 2 or 3).',
      'bot.ask_name': 'Noted: {service}. What name should I put on the request? Please use a made-up name — this is a demo.',
      'bot.ask_contact': 'Thanks, {name}. How should the clinic get back to you? Use made-up details, or skip.',
      'bot.ask_slot': 'Here are three hypothetical openings (mock availability, not a real calendar). Which one works best?',
      'bot.slot_retry': 'Please choose one of the three hypothetical slots below (or type 1, 2 or 3).',
      'bot.draft_confirmation': 'I prepared a draft request for {slot}. Nothing was booked and nothing was sent — a staff member has to review and confirm it.',
      'bot.draft_hint': 'The draft is ready. You can send it to human review or pick another slot using the buttons below.',
      'bot.hours_answer': 'Or Clinic\'s sample opening hours are Sunday–Thursday, {open}–{close} (fictional). Would you like to book a visit?',
      'bot.pricing_answer': 'Prices are not part of this demo. In a real setup I would answer only from the clinic\'s approved price list, or pass the question to staff. Would you like to book a visit or talk to a person?',
      'bot.cancel_answer': 'Changing or cancelling an existing appointment needs a staff member.',
      'bot.urgent_answer': 'This sounds urgent. I can\'t give medical advice. In a real emergency, contact your local emergency services right away.',
      'bot.unknown_retry': 'I\'m not sure I understood. You can pick one of the options below or rephrase.',
      'bot.unclear_escalate': 'I still couldn\'t understand, and I\'d rather not guess.',
      'bot.handoff_notice': 'I\'m passing this conversation to a human team member. (Simulation: in this demo nobody was actually notified.)',
      'bot.paused_after_handoff': 'This conversation is waiting for a human in the simulation. Use “Reset demo” to start again.',

      'audit.session_started': 'Demo session started — state lives in this tab\'s memory only',
      'audit.message_received': 'Customer message received locally ({chars} characters)',
      'audit.quick_reply': 'Customer tapped a suggested reply: “{label}”',
      'audit.intent_classified_rules': 'Inquiry classified as “{intent}” by local keyword rules (matched: {matched})',
      'audit.intent_classified_quick': 'Inquiry classified as “{intent}” from the suggested reply',
      'audit.intent_unknown': 'No keyword rule matched — inquiry marked “Unclear” (attempt {attempt} of 2)',
      'audit.service_selected': 'Visit type recorded: {service}',
      'audit.name_captured': 'Name added to the draft (held in memory only)',
      'audit.contact_captured': 'Contact detail added to the draft (held in memory only)',
      'audit.contact_skipped': 'Customer skipped the contact detail',
      'audit.slots_generated': '3 hypothetical slots generated from the mock fixture — no calendar was queried',
      'audit.slot_selected': 'Customer chose the hypothetical slot {slot}',
      'audit.slot_cleared': 'Customer asked to pick another slot — previous choice cleared',
      'audit.draft_prepared': 'Draft confirmation prepared — NOT sent to anyone',
      'audit.lead_preview_created': 'Lead preview created locally — NOT saved to any CRM; no booking created',
      'audit.handoff_simulated': 'Human handoff requested ({reason}) — simulated; nobody was notified',
      'audit.file_exported': 'Draft file generated in the browser and downloaded to this device: {file}',

      'export.title': 'DRAFT CONFIRMATION — DEMO / SIMULATION',
      'export.notSent': 'This text was NOT sent to anyone. No booking was created.',
      'export.greeting': 'Hello {name},',
      'export.body': 'We received your request for a {service} at Or Clinic (fictional) on {slot}.',
      'export.pending': 'A team member will review the request and confirm it with you. The slot is hypothetical until then.',
      'export.footer': 'Or Clinic is a fictional clinic used for a Core8-AI demonstration.'
    },

    he: {
      'ui.pageTitle': 'Core8-AI — הדגמת פקידת קבלה AI (סימולציה)',
      'ui.skip': 'דילוג אל השיחה',
      'ui.banner': 'הדגמה / סימולציה — לא נשלחות הודעות · לא נקבעים תורים · המרפאה והדמויות בדיוניות',
      'ui.brandTag': 'הדגמה ללקוחות',
      'ui.controls': 'בקרת ההדגמה',
      'ui.language': 'שפה',
      'ui.reset': 'איפוס ההדגמה',
      'ui.mobileOn': 'תצוגת מובייל',
      'ui.mobileOff': 'תצוגת מחשב',
      'ui.h1': 'פקידת קבלה AI למרפאה',
      'ui.lead': 'שחקו מטופל שפונה אל ״מרפאת אור״ הבדיונית. פקידת הקבלה מסווגת את הפנייה, מציעה שלושה מועדים היפותטיים, מכינה טיוטת בקשה ומעבירה אותה לאיש צוות — הכול בתוך לשונית הדפדפן הזו.',
      'ui.progress': 'התקדמות ההדגמה',
      'ui.stage.inquiry': 'פנייה',
      'ui.stage.classified': 'סיווג',
      'ui.stage.slots': 'הצעת מועדים',
      'ui.stage.draft': 'טיוטת בקשה',
      'ui.stage.lead': 'תצוגת ליד',
      'ui.stage.handoff': 'העברה לאדם',
      'ui.stageDone': 'בוצע',
      'ui.stagePending': 'טרם',
      'ui.chatTitle': 'שיחה',
      'ui.clinicName': 'מרפאת אור (בדיונית)',
      'ui.clinicSub': 'פקידת קבלה וירטואלית · סימולציה',
      'ui.agent': 'פקידת הקבלה',
      'ui.you': 'את/ה',
      'ui.choices': 'תשובות מוצעות',
      'ui.inputLabel': 'ההודעה שלך',
      'ui.inputPlaceholder': 'כתבו הודעה — פרטים בדויים בלבד',
      'ui.inputHint': 'אין להזין פרטים אישיים או רפואיים אמיתיים. שום דבר שמוקלד כאן לא יוצא מהעמוד.',
      'ui.send': 'שליחה',
      'ui.panelIntent': 'סיווג הפנייה',
      'ui.panelIntentEmpty': 'שלחו הודעה כדי לראות איך הפנייה מסווגת.',
      'ui.intentLabel': 'כוונה שזוהתה',
      'ui.methodLabel': 'איך זה נקבע',
      'ui.matchedLabel': 'מילות מפתח שזוהו',
      'ui.method.keyword_rules': 'כללי מילות מפתח מקומיים (תחליף הדגמה למודל ה-AI שבמערכת אמיתית)',
      'ui.method.quick_reply': 'הלקוח/ה בחר/ה בתשובה מוצעת',
      'ui.method.none': 'אף כלל לא התאים',
      'ui.panelSlots': 'מועדים היפותטיים',
      'ui.panelSlotsEmpty': 'המועדים יופיעו אחרי בקשה לקביעת תור.',
      'ui.slotsNote': 'זמינות לדוגמה שנוצרה מנתוני דמה. לא נקרא שום יומן אמיתי.',
      'ui.slotHypothetical': 'היפותטי',
      'ui.slotSelected': 'נבחר לטיוטה',
      'ui.panelLead': 'תצוגת ליד (טיוטה מקומית)',
      'ui.panelLeadEmpty': 'תצוגת הליד נוצרת כשנבחר מועד או כשהשיחה מועברת לאדם.',
      'ui.leadNote': 'נשמר בזיכרון הלשונית בלבד. לא נשמר ב-CRM. נמחק באיפוס או ברענון.',
      'ui.field.leadId': 'מספר אסמכתה',
      'ui.field.recordStatus': 'סטטוס הרשומה',
      'ui.field.name': 'שם',
      'ui.field.contact': 'פרטי קשר',
      'ui.field.intent': 'כוונה',
      'ui.field.service': 'סוג הביקור',
      'ui.field.slot': 'מועד מבוקש',
      'ui.field.booking': 'תור',
      'ui.field.message': 'הודעת אישור',
      'ui.field.handoff': 'העברה לאדם',
      'ui.value.none': '—',
      'ui.value.notProvided': 'לא נמסר',
      'ui.status.DRAFT': 'טיוטה',
      'ui.status.NOT_CREATED': 'לא נקבע',
      'ui.status.NOT_SENT': 'לא נשלחה',
      'ui.status.NOT_REQUESTED': 'לא התבקשה',
      'ui.status.SIMULATED_PENDING_HUMAN_REVIEW': 'סימולציה — ממתין לבדיקת אדם (אף אחד לא קיבל הודעה)',
      'ui.downloads': 'הורדת קובצי טיוטה',
      'ui.dlCsv': 'ליד (CSV)',
      'ui.dlJson': 'ליד (JSON)',
      'ui.dlTxt': 'טיוטת אישור (TXT)',
      'ui.panelAudit': 'יומן פעולות שלב אחר שלב',
      'ui.auditNote': 'כל השלבים שלמטה רצו מקומית בדפדפן הזה. אין בהם הוכחה לפעולה אמיתית כלשהי.',
      'ui.auditSim': 'סימולציה',
      'ui.footer1': 'Core8-AI מדגימה כיצד פקידת קבלה מבוססת AI יכולה לטפל בפניות ולהכין בקשה לקביעת תור, עם העברה לאדם בעת הצורך. ההדגמה משתמשת בזמינות בדיונית; חיבורים למערכות אמיתיות ותוצאות בפועל מחייבים הגדרה ואימות נפרדים.',
      'ui.footer2': 'מרפאת אור, הצוות, המטופלים, שעות הפעילות והמועדים הומצאו לצורך המחשה. כל דמיון למרפאה או לאדם אמיתיים מקרי בהחלט.',

      'intent.booking': 'קביעת תור',
      'intent.hours': 'שעות פעילות',
      'intent.pricing': 'מחירים',
      'intent.cancel': 'שינוי או ביטול תור',
      'intent.urgent': 'דחוף / רפואי',
      'intent.human': 'שיחה עם נציג',
      'intent.unknown': 'לא ברור',

      'service.general': 'ייעוץ כללי',
      'service.followup': 'ביקור מעקב',
      'service.hygiene': 'בדיקה תקופתית',

      'reason.booking_review': 'בקשת תור דורשת אישור של הצוות',
      'reason.urgent': 'פנייה דחופה או רפואית',
      'reason.user_request': 'הלקוח/ה ביקש/ה נציג',
      'reason.cancel_request': 'שינוי בתור קיים',
      'reason.unclear': 'הפנייה לא הובנה אחרי שני ניסיונות',

      'choice.intent.booking': 'אני רוצה לקבוע תור',
      'choice.intent.hours': 'מה שעות הפעילות?',
      'choice.intent.pricing': 'כמה עולה ביקור?',
      'choice.intent.urgent': 'זה דחוף',
      'choice.handoff': 'לדבר עם נציג',
      'choice.name.sample': 'שם בדוי לדוגמה: {name}',
      'choice.contact.sample': 'פרט בדוי לדוגמה: {contact}',
      'choice.contact.skip': 'דילוג',
      'choice.draft.handoff': 'שליחה לבדיקת איש צוות',
      'choice.draft.change_slot': 'בחירת מועד אחר',
      'choice.slot': '{slot}',
      'choice.service': '{service}',

      'bot.greeting': 'שלום! אני פקידת הקבלה הווירטואלית של מרפאת אור — מרפאה בדיונית שנוצרה לצורך ההדגמה. במה אפשר לעזור?',
      'bot.ask_service': 'אשמח לעזור בקביעת תור. לאיזה סוג ביקור?',
      'bot.service_retry': 'נא לבחור אחד משלושת סוגי הביקור שלמטה (או להקליד 1, 2 או 3).',
      'bot.ask_name': 'רשמתי: {service}. על איזה שם לרשום את הבקשה? נא להשתמש בשם בדוי — זו הדגמה.',
      'bot.ask_contact': 'תודה, {name}. איך המרפאה תחזור אליך? אפשר להזין פרטים בדויים או לדלג.',
      'bot.ask_slot': 'הנה שלושה מועדים היפותטיים (זמינות לדוגמה, לא יומן אמיתי). איזה מועד הכי מתאים?',
      'bot.slot_retry': 'נא לבחור אחד משלושת המועדים ההיפותטיים שלמטה (או להקליד 1, 2 או 3).',
      'bot.draft_confirmation': 'הכנתי טיוטת בקשה למועד {slot}. לא נקבע תור ולא נשלחה שום הודעה — איש צוות צריך לבדוק ולאשר את הבקשה.',
      'bot.draft_hint': 'הטיוטה מוכנה. אפשר לשלוח אותה לבדיקת איש צוות או לבחור מועד אחר בעזרת הכפתורים שלמטה.',
      'bot.hours_answer': 'שעות הפעילות לדוגמה של מרפאת אור: ימים א׳–ה׳, {open}–{close} (בדיוני). לקבוע תור?',
      'bot.pricing_answer': 'מחירים אינם חלק מההדגמה. במערכת אמיתית הייתי עונה רק מתוך מחירון שהמרפאה אישרה, או מעבירה את השאלה לצוות. לקבוע תור או לדבר עם נציג?',
      'bot.cancel_answer': 'שינוי או ביטול של תור קיים דורשים טיפול של איש צוות.',
      'bot.urgent_answer': 'זה נשמע דחוף. אינני יכולה לתת ייעוץ רפואי. במקרה חירום אמיתי יש לפנות מיד לשירותי החירום.',
      'bot.unknown_retry': 'לא בטוחה שהבנתי. אפשר לבחור באחת האפשרויות שלמטה או לנסח מחדש.',
      'bot.unclear_escalate': 'עדיין לא הצלחתי להבין, ואני מעדיפה לא לנחש.',
      'bot.handoff_notice': 'אני מעבירה את השיחה לאיש צוות אנושי. (סימולציה: בהדגמה הזו אף אחד לא קיבל הודעה בפועל.)',
      'bot.paused_after_handoff': 'השיחה ממתינה לאיש צוות במסגרת הסימולציה. כדי להתחיל מחדש לחצו על ״איפוס ההדגמה״.',

      'audit.session_started': 'סשן הדגמה התחיל — המצב נשמר בזיכרון הלשונית בלבד',
      'audit.message_received': 'הודעת לקוח התקבלה מקומית ({chars} תווים)',
      'audit.quick_reply': 'הלקוח/ה בחר/ה בתשובה מוצעת: ״{label}״',
      'audit.intent_classified_rules': 'הפנייה סווגה כ״{intent}״ לפי כללי מילות מפתח מקומיים (זוהו: {matched})',
      'audit.intent_classified_quick': 'הפנייה סווגה כ״{intent}״ לפי התשובה המוצעת שנבחרה',
      'audit.intent_unknown': 'אף כלל לא התאים — הפנייה סומנה ״לא ברור״ (ניסיון {attempt} מתוך 2)',
      'audit.service_selected': 'סוג הביקור נרשם: {service}',
      'audit.name_captured': 'השם נוסף לטיוטה (נשמר בזיכרון בלבד)',
      'audit.contact_captured': 'פרט הקשר נוסף לטיוטה (נשמר בזיכרון בלבד)',
      'audit.contact_skipped': 'הלקוח/ה דילג/ה על פרטי הקשר',
      'audit.slots_generated': 'נוצרו 3 מועדים היפותטיים מנתוני הדמה — לא בוצעה פנייה לשום יומן',
      'audit.slot_selected': 'הלקוח/ה בחר/ה במועד ההיפותטי {slot}',
      'audit.slot_cleared': 'הלקוח/ה ביקש/ה לבחור מועד אחר — הבחירה הקודמת נוקתה',
      'audit.draft_prepared': 'טיוטת אישור הוכנה — לא נשלחה לאף אחד',
      'audit.lead_preview_created': 'תצוגת ליד נוצרה מקומית — לא נשמרה בשום CRM; לא נקבע תור',
      'audit.handoff_simulated': 'התבקשה העברה לאדם ({reason}) — סימולציה; אף אחד לא קיבל הודעה',
      'audit.file_exported': 'קובץ טיוטה נוצר בדפדפן והורד למכשיר הזה: {file}',

      'export.title': 'טיוטת אישור — הדגמה / סימולציה',
      'export.notSent': 'הטקסט הזה לא נשלח לאף אחד. לא נקבע תור.',
      'export.greeting': 'שלום {name},',
      'export.body': 'קיבלנו את בקשתך ל{service} במרפאת אור (בדיונית) במועד {slot}.',
      'export.pending': 'איש צוות יבדוק את הבקשה ויאשר אותה מולך. עד אז המועד היפותטי בלבד.',
      'export.footer': 'מרפאת אור היא מרפאה בדיונית המשמשת להדגמה של Core8-AI.'
    }
  };

  function has(lang, key) {
    return Object.prototype.hasOwnProperty.call(S[lang] || {}, key);
  }

  // Slot dates are built from local Y/M/D parts so the label never shifts a day.
  function fmtSlot(lang, slot) {
    var p = slot.date.split('-').map(Number);
    var d = new Date(p[0], p[1] - 1, p[2], 12, 0, 0);
    var day = new Intl.DateTimeFormat(LANGS[lang].locale, {
      weekday: 'long', day: 'numeric', month: 'long'
    }).format(d);
    // U+2066/U+2069 isolate the LTR time so it reads correctly inside RTL text.
    return day + ', ⁦' + slot.time + '⁩';
  }

  // Params may be plain values or typed references resolved per language:
  //   { t: 'intent.booking' }  -> translated string
  //   { slot: {date, time} }   -> formatted hypothetical slot
  //   { byLang: {en, he} }     -> per-language literal
  //   { list: [...] }          -> comma-joined list
  function resolve(lang, v) {
    if (v === null || v === undefined) return '';
    if (typeof v !== 'object') return String(v);
    if (v.t) return t(lang, v.t, v.params);
    if (v.slot) return fmtSlot(lang, v.slot);
    if (v.byLang) return String(v.byLang[lang]);
    if (v.list) return v.list.map(function (x) { return resolve(lang, x); }).join(', ');
    return '';
  }

  function t(lang, key, params) {
    var str = has(lang, key) ? S[lang][key] : (has('en', key) ? S.en[key] : key);
    if (!params) return str;
    return str.replace(/\{(\w+)\}/g, function (m, name) {
      return Object.prototype.hasOwnProperty.call(params, name) ? resolve(lang, params[name]) : m;
    });
  }

  return { LANGS: LANGS, STRINGS: S, t: t, resolve: resolve, fmtSlot: fmtSlot };
});
