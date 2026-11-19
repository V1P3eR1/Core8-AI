/*
 * Core8-AI customer demo — mock fixtures for the fictional "Or Clinic".
 * Everything here is invented sample data. No real clinic, person, calendar,
 * price list or contact detail is represented. Loaded as a classic script so
 * the demo also works when index.html is opened directly from disk (file://).
 */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.Core8DemoFixtures = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  return {
    // Sunday–Thursday, the fictional clinic's sample working week.
    workingDays: [0, 1, 2, 3, 4],
    hours: { open: '08:00', close: '19:00' },

    // Exactly three hypothetical slots are offered: one per upcoming working day.
    slotTimes: ['09:30', '13:00', '17:15'],

    services: ['general', 'followup', 'hygiene'],

    // Sample identity for the "use fictional details" shortcut.
    // example.invalid can never resolve (RFC 2606 reserved TLD).
    samplePersona: {
      name: { en: 'Dana Example', he: 'דנה לדוגמה' },
      contact: 'dana@example.invalid'
    },

    // Keyword rules, checked in this priority order. Deliberately simple and
    // deterministic: the demo does not call a language model.
    intentOrder: ['urgent', 'human', 'cancel', 'booking', 'hours', 'pricing'],
    keywords: {
      urgent: {
        en: ['urgent', 'emergency', 'pain', 'painful', 'hurt', 'bleeding', 'bleed', 'chest'],
        he: ['דחוף', 'חירום', 'כאב', 'כואב', 'דימום', 'מדמם']
      },
      human: {
        en: ['human', 'person', 'representative', 'staff', 'someone real'],
        he: ['נציג', 'בן אדם', 'אדם אמיתי', 'מזכירה', 'איש צוות']
      },
      cancel: {
        en: ['cancel', 'reschedule', 'move my'],
        he: ['לבטל', 'ביטול', 'לדחות', 'להזיז', 'לשנות תור']
      },
      booking: {
        en: ['book', 'appointment', 'schedule', 'visit', 'slot'],
        he: ['תור', 'לקבוע', 'פגישה', 'להזמין', 'זימון']
      },
      hours: {
        en: ['hours', 'open', 'close', 'closing', 'opening'],
        he: ['שעות', 'פתוח', 'פתיחה', 'סגור']
      },
      pricing: {
        en: ['price', 'cost', 'how much', 'fee'],
        he: ['מחיר', 'עלות', 'כמה עולה', 'תשלום']
      }
    },

    skipWords: ['skip', 'no', 'none', 'דלג', 'לדלג', 'לא', 'בלי']
  };
});
