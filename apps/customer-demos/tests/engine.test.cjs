'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const ENGINE = require('../receptionist/engine.js');
const I18N = require('../receptionist/i18n.js');
const FX = require('../receptionist/fixtures.js');

// Thursday 19 Nov 2026, 10:00 local time.
const fixedClock = () => new Date(2026, 10, 19, 10, 0, 0);
const newEngine = () => ENGINE.createEngine({ clock: fixedClock });
const auditKeys = (e) => e.getState().audit.map((a) => a.key);

function bookToDraft(e) {
  e.handleChoice('intent:booking', 'en');
  e.handleChoice('service:general', 'en');
  e.handleChoice('name:sample', 'en');
  e.handleChoice('contact:sample', 'en');
  e.handleChoice('slot:slot-2', 'en');
}

test('classifies English and Hebrew inquiries', () => {
  const cases = [
    ["I'd like to book an appointment", 'booking'],
    ['Can I schedule a visit next week?', 'booking'],
    ['שלום, אפשר לקבוע תור?', 'booking'],
    ['What are your opening hours?', 'hours'],
    ['מתי אתם פתוחים?', 'hours'],
    ['How much does it cost?', 'pricing'],
    ['כמה עולה ביקור?', 'pricing'],
    ['I need to cancel my appointment', 'cancel'],
    ['אני צריך לבטל את התור', 'cancel'],
    ['Can I talk to a real person?', 'human'],
    ['אני רוצה לדבר עם נציג', 'human'],
    ['It is urgent, I am in pain', 'urgent'],
    ['דחוף! כואב לי מאוד', 'urgent'],
    ['Tell me a joke', 'unknown'],
    ['בא לי פיצה', 'unknown']
  ];
  for (const [text, intent] of cases) {
    assert.equal(ENGINE.classify(text).intent, intent, text);
  }
});

test('urgent outranks booking; keywords need a word start', () => {
  assert.equal(ENGINE.classify('I need an appointment, it is an emergency').intent, 'urgent');
  assert.equal(ENGINE.classify('can I reopen this').intent, 'unknown');
  assert.equal(ENGINE.classify('I feel fine').intent, 'unknown');
  assert.deepEqual(ENGINE.classify('book appointments').matched, ['book', 'appointment']);
});

test('generates exactly three hypothetical slots on upcoming working days', () => {
  const slots = ENGINE.generateSlots(fixedClock());
  assert.equal(slots.length, 3);
  // Thursday -> skips Friday and Saturday.
  assert.deepEqual(slots.map((s) => s.date), ['2026-11-22', '2026-11-23', '2026-11-24']);
  assert.deepEqual(slots.map((s) => s.time), FX.slotTimes);
  assert.ok(slots.every((s) => s.hypothetical === true));
  for (let offset = 0; offset < 14; offset++) {
    const now = new Date(2026, 10, 19 + offset, 23, 59, 0);
    const out = ENGINE.generateSlots(now);
    assert.equal(out.length, 3);
    for (const s of out) {
      const [y, m, d] = s.date.split('-').map(Number);
      const day = new Date(y, m - 1, d, 12);
      assert.ok(FX.workingDays.includes(day.getDay()), s.date + ' is a working day');
      assert.ok(day > now, s.date + ' is after today');
    }
  }
});

test('happy path with suggested replies ends in a draft, not a booking', () => {
  const e = newEngine();
  bookToDraft(e);
  const s = e.getState();
  assert.equal(s.step, 'draft_ready');
  assert.equal(s.lead.recordStatus, 'DRAFT');
  assert.equal(s.lead.bookingStatus, 'NOT_CREATED');
  assert.equal(s.lead.messageStatus, 'NOT_SENT');
  assert.equal(s.lead.handoffStatus, 'NOT_REQUESTED');
  assert.equal(s.lead.storage, 'IN_MEMORY_ONLY');
  assert.equal(s.lead.fictional, true);
  assert.deepEqual(s.lead.requestedSlot, { date: '2026-11-23', time: '13:00', hypothetical: true });
  assert.equal(s.lead.contact, 'dana@example.invalid');

  e.handleChoice('draft:handoff', 'en');
  assert.equal(e.getState().step, 'handed_off');
  assert.equal(e.getState().lead.handoffStatus, 'SIMULATED_PENDING_HUMAN_REVIEW');
  assert.equal(e.getState().lead.handoffReason, 'booking_review');
  // Still never booked or sent after the handoff.
  assert.equal(e.getState().lead.bookingStatus, 'NOT_CREATED');
  assert.equal(e.getState().lead.messageStatus, 'NOT_SENT');
  assert.ok(e.progress().every((p) => p.done));
  assert.deepEqual(e.choices(), []);
});

test('happy path works with typed messages only', () => {
  const e = newEngine();
  e.handleText('Hi, can I book an appointment?');
  assert.equal(e.getState().classification.method, 'keyword_rules');
  e.handleText('pizza');
  assert.equal(e.getState().step, 'await_service', 'invalid service keeps the step');
  e.handleText('3');
  e.handleText('Test Person');
  e.handleText('skip');
  assert.equal(e.getState().contact, null);
  e.handleText('9');
  assert.equal(e.getState().step, 'await_slot', 'out-of-range slot keeps the step');
  e.handleText('1');
  assert.equal(e.getState().step, 'draft_ready');
  assert.equal(e.getState().lead.service, 'hygiene');
  assert.equal(e.getState().lead.name, 'Test Person');
});

test('audit trail records each step in order', () => {
  const e = newEngine();
  bookToDraft(e);
  e.handleChoice('draft:handoff', 'en');
  const keys = auditKeys(e).filter((k) => k !== 'audit.quick_reply');
  assert.deepEqual(keys, [
    'audit.session_started', 'audit.intent_classified_quick', 'audit.service_selected',
    'audit.name_captured', 'audit.contact_captured', 'audit.slots_generated',
    'audit.slot_selected', 'audit.draft_prepared', 'audit.lead_preview_created',
    'audit.handoff_simulated'
  ]);
  const ns = e.getState().audit.map((a) => a.n);
  assert.deepEqual(ns, ns.map((_, i) => i + 1));
  for (const a of e.getState().audit) {
    for (const lang of ['en', 'he']) {
      const text = I18N.t(lang, a.key, a.params);
      assert.ok(text && !/\{\w+\}/.test(text) && !text.startsWith('audit.'), `${lang} ${a.key}: ${text}`);
    }
  }
});

test('escalates urgent, human, cancel and repeatedly unclear inquiries', () => {
  let e = newEngine();
  e.handleText('דחוף, כואב לי');
  assert.equal(e.getState().handoff.reason, 'urgent');
  assert.equal(e.getState().slots.length, 0, 'no slots offered for urgent inquiries');
  assert.ok(e.getState().transcript.some((m) => m.key === 'bot.urgent_answer'));

  e = newEngine();
  e.handleText('I want to talk to a human');
  assert.equal(e.getState().handoff.reason, 'user_request');

  e = newEngine();
  e.handleText('please cancel my appointment');
  assert.equal(e.getState().handoff.reason, 'cancel_request');

  e = newEngine();
  e.handleText('asdf');
  assert.equal(e.getState().handoff, null);
  e.handleText('qwerty');
  assert.equal(e.getState().handoff.reason, 'unclear');

  e = newEngine();
  e.handleChoice('handoff', 'en');
  assert.equal(e.getState().handoff.reason, 'user_request');
  assert.equal(e.getState().lead.handoffStatus, 'SIMULATED_PENDING_HUMAN_REVIEW');
});

test('urgent message interrupts mid-booking; a typed name is not misread as an escalation', () => {
  let e = newEngine();
  e.handleChoice('intent:booking', 'en');
  e.handleChoice('service:general', 'en');
  e.handleText('אדם אמיתי');
  assert.equal(e.getState().step, 'await_contact', 'name step accepts any name');
  assert.equal(e.getState().handoff, null);
  e.handleText('actually this is an emergency');
  assert.equal(e.getState().handoff.reason, 'urgent');

  e = newEngine();
  e.handleText('urgent');
  const before = e.getState().transcript.length;
  e.handleText('hello?');
  assert.equal(e.getState().transcript[before + 1].key, 'bot.paused_after_handoff');
});

test('hours and pricing answers stay in the conversation and make no promises', () => {
  const e = newEngine();
  e.handleChoice('intent:hours', 'en');
  e.handleChoice('intent:pricing', 'en');
  assert.equal(e.getState().step, 'await_intent');
  assert.equal(e.getState().handoff, null);
  const pricing = I18N.t('en', 'bot.pricing_answer');
  assert.ok(!/[₪$€]|\d/.test(pricing), 'pricing answer quotes no figures');
});

test('picking another slot clears the draft until a new slot is chosen', () => {
  const e = newEngine();
  bookToDraft(e);
  e.handleChoice('draft:change_slot', 'en');
  assert.equal(e.getState().step, 'await_slot');
  assert.equal(e.getState().lead.requestedSlot, null);
  assert.equal(e.confirmationText('en'), null);
  assert.equal(e.getState().slots.length, 3, 'slots are not regenerated');
  e.handleChoice('slot:slot-3', 'en');
  assert.equal(e.getState().lead.requestedSlot.time, '17:15');
});

test('invalid or out-of-step choices are ignored', () => {
  const e = newEngine();
  const before = JSON.stringify(e.getState());
  e.handleChoice('slot:slot-1', 'en');
  e.handleChoice('draft:handoff', 'en');
  e.handleChoice('nonsense', 'en');
  assert.equal(JSON.stringify(e.getState()), before);
});

test('input is trimmed, length-limited and stripped of control characters', () => {
  assert.equal(ENGINE.cleanText('  a\u0000b‮ c\n'), 'a b c');
  assert.equal(ENGINE.cleanText('x'.repeat(500)).length, ENGINE.MAX_INPUT);
  const e = newEngine();
  const n = e.getState().transcript.length;
  e.handleText('   ');
  assert.equal(e.getState().transcript.length, n, 'blank input is ignored');
});

test('lead CSV has a header and exactly one row, and neutralises formulas', () => {
  const e = newEngine();
  e.handleChoice('intent:booking', 'en');
  e.handleChoice('service:general', 'en');
  e.handleText('=HYPERLINK("x","y"), Dana');
  e.handleText('+1 "quoted"');
  e.handleText('1');
  const csv = ENGINE.leadToCsv(e.getState().lead);
  assert.ok(csv.startsWith('﻿'));
  const lines = csv.replace('﻿', '').trim().split('\r\n');
  assert.equal(lines.length, 2);
  assert.equal(lines[0], ENGINE.LEAD_COLUMNS.join(','));
  assert.ok(lines[1].includes('"\'=HYPERLINK(""x"",""y""), Dana"'));
  assert.ok(lines[1].includes('"\'+1 ""quoted"""'));
  assert.ok(lines[1].includes('DRAFT') && lines[1].includes('NOT_CREATED') && lines[1].includes('NOT_SENT'));

  const json = JSON.parse(ENGINE.leadToJson(e.getState().lead));
  assert.match(json.notice, /DEMO \/ SIMULATION/);
  assert.equal(json.lead.recordStatus, 'DRAFT');
});

test('draft confirmation text says it was not sent, in both languages', () => {
  const e = newEngine();
  bookToDraft(e);
  const en = e.confirmationText('en');
  const he = e.confirmationText('he');
  assert.match(en, /NOT sent/);
  assert.match(en, /Monday,? 23 November, 13:00/);
  assert.match(he, /לא נשלח/);
  assert.match(he, /היפותטי/);
});

test('reset returns to a clean greeting with no carried-over data', () => {
  const e = newEngine();
  bookToDraft(e);
  e.reset();
  const s = e.getState();
  assert.equal(s.step, 'await_intent');
  assert.equal(s.lead, null);
  assert.equal(s.name, null);
  assert.equal(s.slots.length, 0);
  assert.equal(s.transcript.length, 1);
  assert.deepEqual(auditKeys(e), ['audit.session_started']);
});

test('Hebrew and English string tables have identical keys and no blanks', () => {
  const en = Object.keys(I18N.STRINGS.en).sort();
  const he = Object.keys(I18N.STRINGS.he).sort();
  assert.deepEqual(he, en);
  for (const lang of ['en', 'he']) {
    for (const k of en) assert.ok(I18N.STRINGS[lang][k].trim().length > 0, `${lang}.${k}`);
  }
  // Placeholders must match across languages.
  for (const k of en) {
    const ph = (s) => (s.match(/\{\w+\}/g) || []).sort().join();
    assert.equal(ph(I18N.STRINGS.he[k]), ph(I18N.STRINGS.en[k]), k);
  }
  assert.equal(I18N.LANGS.he.dir, 'rtl');
  assert.equal(I18N.LANGS.en.dir, 'ltr');
});

test('every suggested reply and bot message renders in both languages', () => {
  const e = newEngine();
  const seen = [];
  const collect = () => { for (const c of e.choices()) seen.push(c); };
  collect(); e.handleChoice('intent:booking', 'he');
  collect(); e.handleChoice('service:followup', 'he');
  collect(); e.handleChoice('name:sample', 'he');
  assert.equal(e.getState().name, FX.samplePersona.name.he);
  collect(); e.handleChoice('contact:skip', 'he');
  collect(); e.handleChoice('slot:slot-1', 'he');
  collect();
  assert.equal(e.choices().filter((c) => c.id.startsWith('slot:')).length, 0);
  for (const lang of ['en', 'he']) {
    for (const c of seen) assert.ok(!/\{\w+\}/.test(I18N.t(lang, c.key, c.params)), c.id);
    for (const m of e.getState().transcript) {
      if (m.key) assert.ok(!/\{\w+\}|^(bot|choice)\./.test(I18N.t(lang, m.key, m.params)), m.key);
    }
  }
});
