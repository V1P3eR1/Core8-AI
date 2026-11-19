/*
 * Core8-AI customer demo — receptionist conversation engine.
 *
 * Pure, deterministic, in-memory state machine. It performs no I/O of any kind:
 * no network, no storage, no timers. The browser UI (app.js) renders its state;
 * the Node tests exercise it directly.
 */
(function (root, factory) {
  var api;
  if (typeof module === 'object' && module.exports) {
    api = factory(require('./fixtures.js'), require('./i18n.js'));
    module.exports = api;
  } else {
    api = factory(root.Core8DemoFixtures, root.Core8DemoI18n);
    root.Core8DemoEngine = api;
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function (FX, I18N) {
  'use strict';

  var MAX_INPUT = 200;
  var STAGES = ['inquiry', 'classified', 'slots', 'draft', 'lead', 'handoff'];

  function pad(n) { return (n < 10 ? '0' : '') + n; }

  function localDate(d) {
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
  }

  function cleanText(raw) {
    return String(raw === null || raw === undefined ? '' : raw)
      // Strip control and bidi-override characters; keep ordinary text.
      .replace(/[\u0000-\u001f\u007f‪-‮⁦-⁩]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .slice(0, MAX_INPUT);
  }

  function escapeRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

  // Keyword classifier. English keywords must start at a word boundary and may
  // carry a simple suffix ("book" -> "booking", "appointment" -> "appointments").
  // Hebrew keywords match as substrings because prefixes attach to words.
  function classify(text) {
    var lower = cleanText(text).toLowerCase();
    for (var i = 0; i < FX.intentOrder.length; i++) {
      var intent = FX.intentOrder[i];
      var kw = FX.keywords[intent];
      var matched = [];
      kw.en.forEach(function (w) {
        if (new RegExp('(^|[^a-z])' + escapeRe(w) + '(s|es|d|ed|ing)?([^a-z]|$)').test(lower)) matched.push(w);
      });
      kw.he.forEach(function (w) {
        if (lower.indexOf(w) !== -1) matched.push(w);
      });
      if (matched.length) return { intent: intent, matched: matched, method: 'keyword_rules' };
    }
    return { intent: 'unknown', matched: [], method: 'none' };
  }

  // Three hypothetical slots: the next three working days after `now`.
  function generateSlots(now) {
    var slots = [];
    var d = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 12, 0, 0);
    while (slots.length < FX.slotTimes.length) {
      d.setDate(d.getDate() + 1);
      if (FX.workingDays.indexOf(d.getDay()) === -1) continue;
      slots.push({
        id: 'slot-' + (slots.length + 1),
        date: localDate(d),
        time: FX.slotTimes[slots.length],
        hypothetical: true
      });
    }
    return slots;
  }

  function csvCell(v) {
    var s = v === null || v === undefined ? '' : String(v);
    // Neutralise spreadsheet formula injection from typed names/contacts.
    if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
    return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }

  var LEAD_COLUMNS = [
    'lead_id', 'record_status', 'storage', 'fictional_demo', 'business', 'name', 'contact',
    'intent', 'service', 'requested_date', 'requested_time', 'slot_hypothetical',
    'booking_status', 'message_status', 'handoff_status', 'handoff_reason', 'created_at_local'
  ];

  function leadToRow(lead) {
    var slot = lead.requestedSlot || {};
    return [
      lead.leadId, lead.recordStatus, lead.storage, 'true', lead.business, lead.name, lead.contact,
      lead.intent, lead.service, slot.date, slot.time, lead.requestedSlot ? 'true' : '',
      lead.bookingStatus, lead.messageStatus, lead.handoffStatus, lead.handoffReason, lead.createdAtLocal
    ];
  }

  function leadToCsv(lead) {
    // BOM so spreadsheet apps read Hebrew names as UTF-8.
    return '﻿' + LEAD_COLUMNS.join(',') + '\r\n' + leadToRow(lead).map(csvCell).join(',') + '\r\n';
  }

  function leadToJson(lead) {
    return JSON.stringify({
      notice: 'DEMO / SIMULATION - fictional data, nothing was sent, booked or saved to a CRM.',
      lead: lead
    }, null, 2) + '\n';
  }

  function createEngine(opts) {
    opts = opts || {};
    var clock = opts.clock || function () { return new Date(); };
    var state;

    function audit(key, params) {
      var at = clock();
      state.audit.push({
        n: state.audit.length + 1,
        time: pad(at.getHours()) + ':' + pad(at.getMinutes()) + ':' + pad(at.getSeconds()),
        key: 'audit.' + key,
        params: params || null
      });
    }

    function say(key, params) {
      state.transcript.push({ role: 'agent', key: 'bot.' + key, params: params || null });
    }

    function userSaid(entry) {
      entry.role = 'user';
      state.transcript.push(entry);
    }

    function reset() {
      state = {
        step: 'await_intent',
        classification: null,
        unknownCount: 0,
        service: null,
        name: null,
        contact: null,
        slots: [],
        slotId: null,
        lead: null,
        handoff: null,
        draftPrepared: false,
        transcript: [],
        audit: []
      };
      audit('session_started');
      say('greeting');
      return state;
    }

    function selectedSlot() {
      for (var i = 0; i < state.slots.length; i++) {
        if (state.slots[i].id === state.slotId) return state.slots[i];
      }
      return null;
    }

    function buildLead() {
      var slot = selectedSlot();
      var at = clock();
      state.lead = {
        leadId: 'DEMO-0001',
        recordStatus: 'DRAFT',
        storage: 'IN_MEMORY_ONLY',
        fictional: true,
        business: 'Or Clinic (fictional)',
        name: state.name,
        contact: state.contact,
        intent: state.classification ? state.classification.intent : 'unknown',
        service: state.service,
        requestedSlot: slot ? { date: slot.date, time: slot.time, hypothetical: true } : null,
        bookingStatus: 'NOT_CREATED',
        messageStatus: 'NOT_SENT',
        handoffStatus: state.handoff ? state.handoff.status : 'NOT_REQUESTED',
        handoffReason: state.handoff ? state.handoff.reason : null,
        createdAtLocal: (state.lead && state.lead.createdAtLocal) ||
          (localDate(at) + 'T' + pad(at.getHours()) + ':' + pad(at.getMinutes()) + ':' + pad(at.getSeconds()))
      };
    }

    function handoff(reason) {
      if (state.handoff) return;
      state.handoff = { reason: reason, status: 'SIMULATED_PENDING_HUMAN_REVIEW' };
      var hadLead = !!state.lead;
      buildLead();
      if (!hadLead) audit('lead_preview_created');
      say('handoff_notice');
      audit('handoff_simulated', { reason: { t: 'reason.' + reason } });
      state.step = 'handed_off';
    }

    function setClassification(cls) {
      state.classification = cls;
      if (cls.intent === 'unknown') {
        state.unknownCount += 1;
        audit('intent_unknown', { attempt: state.unknownCount });
      } else if (cls.method === 'quick_reply') {
        audit('intent_classified_quick', { intent: { t: 'intent.' + cls.intent } });
      } else {
        audit('intent_classified_rules', {
          intent: { t: 'intent.' + cls.intent },
          matched: { list: cls.matched }
        });
      }
    }

    function routeIntent(cls) {
      setClassification(cls);
      switch (cls.intent) {
        case 'booking':
          state.step = 'await_service';
          say('ask_service');
          break;
        case 'hours':
          say('hours_answer', { open: FX.hours.open, close: FX.hours.close });
          break;
        case 'pricing':
          say('pricing_answer');
          break;
        case 'cancel':
          say('cancel_answer');
          handoff('cancel_request');
          break;
        case 'urgent':
          say('urgent_answer');
          handoff('urgent');
          break;
        case 'human':
          handoff('user_request');
          break;
        default:
          if (state.unknownCount >= 2) {
            say('unclear_escalate');
            handoff('unclear');
          } else {
            say('unknown_retry');
          }
      }
    }

    function chooseService(id) {
      state.service = id;
      audit('service_selected', { service: { t: 'service.' + id } });
      state.step = 'await_name';
      say('ask_name', { service: { t: 'service.' + id } });
    }

    function setName(name) {
      state.name = name;
      audit('name_captured');
      state.step = 'await_contact';
      say('ask_contact', { name: name });
    }

    function setContact(contact) {
      state.contact = contact;
      audit(contact ? 'contact_captured' : 'contact_skipped');
      offerSlots();
    }

    function offerSlots() {
      if (!state.slots.length) {
        state.slots = generateSlots(clock());
        audit('slots_generated');
      }
      state.step = 'await_slot';
      say('ask_slot');
    }

    function chooseSlot(id) {
      state.slotId = id;
      var slot = selectedSlot();
      audit('slot_selected', { slot: { slot: slot } });
      state.draftPrepared = true;
      say('draft_confirmation', { slot: { slot: slot } });
      audit('draft_prepared');
      var hadLead = !!state.lead;
      buildLead();
      if (!hadLead) audit('lead_preview_created');
      state.step = 'draft_ready';
    }

    function pickByNumber(text, list) {
      var m = /^\s*([1-9])\s*$/.exec(text);
      if (!m) return null;
      return list[Number(m[1]) - 1] || null;
    }

    function handleText(raw) {
      var text = cleanText(raw);
      if (!text) return state;
      userSaid({ text: text });
      audit('message_received', { chars: text.length });

      if (state.step === 'handed_off') { say('paused_after_handoff'); return state; }

      var cls = classify(text);
      // An urgent message interrupts any step. A request for a person does too,
      // except while typing a name/contact, where "אדם" may simply be a name.
      var collecting = state.step === 'await_name' || state.step === 'await_contact';
      if (cls.intent === 'urgent' || (cls.intent === 'human' && !collecting)) {
        routeIntent(cls);
        return state;
      }

      switch (state.step) {
        case 'await_intent':
          routeIntent(cls);
          break;
        case 'await_service': {
          var svc = pickByNumber(text, FX.services);
          if (svc) chooseService(svc); else say('service_retry');
          break;
        }
        case 'await_name':
          setName(text);
          break;
        case 'await_contact':
          setContact(FX.skipWords.indexOf(text.toLowerCase()) !== -1 ? null : text);
          break;
        case 'await_slot': {
          var slot = pickByNumber(text, state.slots);
          if (slot) chooseSlot(slot.id); else say('slot_retry');
          break;
        }
        case 'draft_ready':
          if (cls.intent === 'cancel') routeIntent(cls); else say('draft_hint');
          break;
      }
      return state;
    }

    // Suggested replies valid for the current step.
    function choices() {
      var list = [];
      var persona = FX.samplePersona;
      switch (state.step) {
        case 'await_intent':
          ['booking', 'hours', 'pricing', 'urgent'].forEach(function (i) {
            list.push({ id: 'intent:' + i, key: 'choice.intent.' + i });
          });
          break;
        case 'await_service':
          FX.services.forEach(function (s) {
            list.push({ id: 'service:' + s, key: 'choice.service', params: { service: { t: 'service.' + s } } });
          });
          break;
        case 'await_name':
          list.push({ id: 'name:sample', key: 'choice.name.sample', params: { name: { byLang: persona.name } } });
          break;
        case 'await_contact':
          list.push({ id: 'contact:sample', key: 'choice.contact.sample', params: { contact: persona.contact } });
          list.push({ id: 'contact:skip', key: 'choice.contact.skip' });
          break;
        case 'await_slot':
          state.slots.forEach(function (s) {
            list.push({ id: 'slot:' + s.id, key: 'choice.slot', params: { slot: { slot: s } }, hypothetical: true });
          });
          break;
        case 'draft_ready':
          list.push({ id: 'draft:handoff', key: 'choice.draft.handoff', primary: true });
          list.push({ id: 'draft:change_slot', key: 'choice.draft.change_slot' });
          break;
      }
      if (state.step !== 'handed_off' && state.step !== 'draft_ready') {
        list.push({ id: 'handoff', key: 'choice.handoff', secondary: true });
      }
      return list;
    }

    function handleChoice(id, lang) {
      var valid = choices().filter(function (c) { return c.id === id; })[0];
      if (!valid) return state;
      userSaid({ key: valid.key, params: valid.params || null });
      audit('quick_reply', { label: { t: valid.key, params: valid.params || null } });

      var parts = id.split(':');
      var kind = parts[0];
      var arg = parts[1];
      if (kind === 'intent') {
        routeIntent({ intent: arg, matched: [], method: 'quick_reply' });
      } else if (kind === 'service') {
        chooseService(arg);
      } else if (kind === 'name') {
        setName(FX.samplePersona.name[lang === 'he' ? 'he' : 'en']);
      } else if (kind === 'contact') {
        setContact(arg === 'sample' ? FX.samplePersona.contact : null);
      } else if (kind === 'slot') {
        chooseSlot(arg);
      } else if (kind === 'draft' && arg === 'handoff') {
        handoff('booking_review');
      } else if (kind === 'draft' && arg === 'change_slot') {
        state.slotId = null;
        state.draftPrepared = false;
        audit('slot_cleared');
        buildLead();
        offerSlots();
      } else if (kind === 'handoff') {
        setClassification({ intent: 'human', matched: [], method: 'quick_reply' });
        handoff('user_request');
      }
      return state;
    }

    function progress() {
      var done = {
        inquiry: state.transcript.some(function (m) { return m.role === 'user'; }),
        classified: !!state.classification && state.classification.intent !== 'unknown',
        slots: state.slots.length > 0,
        draft: state.draftPrepared,
        lead: !!state.lead,
        handoff: !!state.handoff
      };
      return STAGES.map(function (id) { return { id: id, done: done[id] }; });
    }

    function confirmationText(lang) {
      var slot = selectedSlot();
      if (!slot || !state.draftPrepared) return null;
      var t = I18N.t;
      return [
        t(lang, 'export.title'),
        t(lang, 'export.notSent'),
        '',
        t(lang, 'export.greeting', { name: state.name || t(lang, 'ui.value.notProvided') }),
        t(lang, 'export.body', { service: { t: 'service.' + state.service }, slot: { slot: slot } }),
        t(lang, 'export.pending'),
        '',
        t(lang, 'export.footer'),
        ''
      ].join('\r\n').replace(/[\u2066\u2069]/g, '');
    }

    function recordExport(file) { audit('file_exported', { file: file }); }

    reset();

    return {
      reset: reset,
      getState: function () { return state; },
      handleText: handleText,
      handleChoice: handleChoice,
      choices: choices,
      progress: progress,
      selectedSlot: selectedSlot,
      confirmationText: confirmationText,
      recordExport: recordExport
    };
  }

  return {
    createEngine: createEngine,
    classify: classify,
    generateSlots: generateSlots,
    leadToCsv: leadToCsv,
    leadToJson: leadToJson,
    cleanText: cleanText,
    LEAD_COLUMNS: LEAD_COLUMNS,
    STAGES: STAGES,
    MAX_INPUT: MAX_INPUT
  };
});
