/*
 * Core8-AI customer demo — browser UI for the receptionist simulation.
 *
 * Renders engine state into the page. Uses textContent only (never HTML strings),
 * keeps all state in memory, writes nothing to storage or cookies, and performs
 * no network I/O. Downloads are generated in the page as Blobs.
 */
(function () {
  'use strict';

  var I18N = window.Core8DemoI18n;
  var ENGINE = window.Core8DemoEngine;
  var t = I18N.t;

  var engine = ENGINE.createEngine();
  var lang = 'en';
  var mobilePreview = false;

  function $(id) { return document.getElementById(id); }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === 'class') node.className = attrs[k];
      else if (k === 'text') node.textContent = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) node.appendChild(c); });
    return node;
  }

  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

  function initialLang() {
    var m = /[?&#]lang=(he|en)\b/.exec(window.location.search + window.location.hash);
    return m ? m[1] : 'en';
  }

  /* ---------- static chrome ---------- */

  function renderChrome() {
    var meta = I18N.LANGS[lang];
    document.documentElement.lang = lang;
    document.documentElement.dir = meta.dir;
    document.title = t(lang, 'ui.pageTitle');

    Array.prototype.forEach.call(document.querySelectorAll('[data-i18n]'), function (n) {
      n.textContent = t(lang, n.getAttribute('data-i18n'));
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-i18n-aria]'), function (n) {
      n.setAttribute('aria-label', t(lang, n.getAttribute('data-i18n-aria')));
    });
    Array.prototype.forEach.call(document.querySelectorAll('.lang__btn'), function (b) {
      b.setAttribute('aria-pressed', String(b.getAttribute('data-lang') === lang));
    });

    $('chat-input').setAttribute('placeholder', t(lang, 'ui.inputPlaceholder'));
    $('chat-input').setAttribute('dir', 'auto');

    var mt = $('mobile-toggle');
    mt.textContent = t(lang, mobilePreview ? 'ui.mobileOff' : 'ui.mobileOn');
    mt.setAttribute('aria-pressed', String(mobilePreview));
    $('stage').classList.toggle('stage--mobile', mobilePreview);
  }

  /* ---------- dynamic regions ---------- */

  function renderStepper() {
    var root = $('stepper');
    clear(root);
    engine.progress().forEach(function (s, i) {
      var li = el('li', {
        'class': 'stepper__item' + (s.done ? ' is-done' : ''),
        'data-stage': s.id,
        'data-done': String(s.done)
      }, [
        el('span', { 'class': 'stepper__num', 'aria-hidden': 'true', text: s.done ? '✓' : String(i + 1) }),
        el('span', { 'class': 'stepper__label', text: t(lang, 'ui.stage.' + s.id) }),
        el('span', { 'class': 'visually-hidden', text: ' — ' + t(lang, s.done ? 'ui.stageDone' : 'ui.stagePending') })
      ]);
      root.appendChild(li);
    });
  }

  function renderLog() {
    var log = $('chat-log');
    var state = engine.getState();
    // Append only new messages so screen readers announce additions, not the
    // whole transcript; a language switch or reset rebuilds the list.
    var rendered = log.querySelectorAll('.msg').length;
    if (log.getAttribute('data-lang') !== lang || rendered > state.transcript.length) {
      clear(log);
      rendered = 0;
      log.setAttribute('data-lang', lang);
    }
    state.transcript.slice(rendered).forEach(function (m) {
      var isUser = m.role === 'user';
      var text = m.text !== undefined ? m.text : t(lang, m.key, m.params);
      log.appendChild(el('div', {
        'class': 'msg ' + (isUser ? 'msg--user' : 'msg--agent'),
        'data-role': m.role
      }, [
        el('span', { 'class': 'msg__who', text: t(lang, isUser ? 'ui.you' : 'ui.agent') }),
        el('p', { 'class': 'msg__text', dir: 'auto', text: text })
      ]));
    });
    log.scrollTop = log.scrollHeight;
  }

  function renderChoices() {
    var root = $('choices');
    clear(root);
    engine.choices().forEach(function (c) {
      var cls = 'chip' + (c.primary ? ' chip--primary' : '') + (c.secondary ? ' chip--quiet' : '');
      var btn = el('button', { type: 'button', 'class': cls, 'data-choice': c.id }, [
        el('span', { text: t(lang, c.key, c.params) }),
        c.hypothetical ? el('span', { 'class': 'tag tag--sim', text: t(lang, 'ui.slotHypothetical') }) : null
      ]);
      root.appendChild(btn);
    });
    var handedOff = engine.getState().step === 'handed_off';
    root.hidden = handedOff;
  }

  function dlRow(label, value, testid) {
    return el('div', { 'class': 'dl__row' }, [
      el('dt', { text: label }),
      // <bdi> isolates mixed-direction values (Latin names inside Hebrew UI)
      // while the cell keeps the page's alignment.
      el('dd', { 'data-testid': testid || '' }, [el('bdi', { text: value })])
    ]);
  }

  function renderIntent() {
    var root = $('intent-body');
    var cls = engine.getState().classification;
    clear(root);
    if (!cls) {
      root.appendChild(el('p', { 'class': 'panel__empty', text: t(lang, 'ui.panelIntentEmpty') }));
      return;
    }
    var dl = el('dl', { 'class': 'dl' }, [
      dlRow(t(lang, 'ui.intentLabel'), t(lang, 'intent.' + cls.intent), 'intent-value'),
      dlRow(t(lang, 'ui.methodLabel'), t(lang, 'ui.method.' + cls.method), 'intent-method')
    ]);
    if (cls.matched.length) {
      dl.appendChild(dlRow(t(lang, 'ui.matchedLabel'), cls.matched.join(', '), 'intent-matched'));
    }
    root.appendChild(dl);
    root.firstChild.setAttribute('data-intent', cls.intent);
  }

  function renderSlots() {
    var root = $('slots-body');
    var state = engine.getState();
    clear(root);
    if (!state.slots.length) {
      root.appendChild(el('p', { 'class': 'panel__empty', text: t(lang, 'ui.panelSlotsEmpty') }));
      return;
    }
    var ul = el('ul', { 'class': 'slots' });
    state.slots.forEach(function (s) {
      var selected = s.id === state.slotId;
      ul.appendChild(el('li', { 'class': 'slots__item' + (selected ? ' is-selected' : ''), 'data-slot': s.id }, [
        el('span', { 'class': 'slots__when', text: I18N.fmtSlot(lang, s) }),
        el('span', { 'class': 'tag tag--sim', text: t(lang, 'ui.slotHypothetical') }),
        selected ? el('span', { 'class': 'tag tag--pick', text: t(lang, 'ui.slotSelected') }) : null
      ]));
    });
    root.appendChild(ul);
    root.appendChild(el('p', { 'class': 'panel__note', text: t(lang, 'ui.slotsNote') }));
  }

  function renderLead() {
    var root = $('lead-body');
    var state = engine.getState();
    var lead = state.lead;
    clear(root);
    if (!lead) {
      root.appendChild(el('p', { 'class': 'panel__empty', text: t(lang, 'ui.panelLeadEmpty') }));
      return;
    }
    var none = t(lang, 'ui.value.none');
    var notProvided = t(lang, 'ui.value.notProvided');
    var slot = engine.selectedSlot();
    var dl = el('dl', { 'class': 'dl', 'data-testid': 'lead-fields' }, [
      dlRow(t(lang, 'ui.field.leadId'), lead.leadId, 'lead-id'),
      dlRow(t(lang, 'ui.field.recordStatus'), t(lang, 'ui.status.' + lead.recordStatus), 'lead-record-status'),
      dlRow(t(lang, 'ui.field.name'), lead.name || notProvided, 'lead-name'),
      dlRow(t(lang, 'ui.field.contact'), lead.contact || notProvided, 'lead-contact'),
      dlRow(t(lang, 'ui.field.intent'), t(lang, 'intent.' + lead.intent), 'lead-intent'),
      dlRow(t(lang, 'ui.field.service'), lead.service ? t(lang, 'service.' + lead.service) : none, 'lead-service'),
      dlRow(t(lang, 'ui.field.slot'), slot ? I18N.fmtSlot(lang, slot) + ' · ' + t(lang, 'ui.slotHypothetical') : none, 'lead-slot'),
      dlRow(t(lang, 'ui.field.booking'), t(lang, 'ui.status.' + lead.bookingStatus), 'lead-booking-status'),
      dlRow(t(lang, 'ui.field.message'), t(lang, 'ui.status.' + lead.messageStatus), 'lead-message-status'),
      dlRow(t(lang, 'ui.field.handoff'),
        t(lang, 'ui.status.' + lead.handoffStatus) +
        (lead.handoffReason ? ' · ' + t(lang, 'reason.' + lead.handoffReason) : ''), 'lead-handoff-status')
    ]);
    root.appendChild(dl);
    root.firstChild.setAttribute('data-handoff', lead.handoffStatus);
    root.appendChild(el('p', { 'class': 'panel__note', text: t(lang, 'ui.leadNote') }));

    var group = el('div', { 'class': 'downloads', role: 'group', 'aria-label': t(lang, 'ui.downloads') }, [
      el('span', { 'class': 'downloads__label', text: t(lang, 'ui.downloads') }),
      el('button', { type: 'button', 'class': 'btn btn--small', 'data-download': 'csv', text: t(lang, 'ui.dlCsv') }),
      el('button', { type: 'button', 'class': 'btn btn--small', 'data-download': 'json', text: t(lang, 'ui.dlJson') }),
      state.draftPrepared
        ? el('button', { type: 'button', 'class': 'btn btn--small', 'data-download': 'txt', text: t(lang, 'ui.dlTxt') })
        : null
    ]);
    root.appendChild(group);
  }

  function renderAudit() {
    var root = $('audit-list');
    clear(root);
    engine.getState().audit.forEach(function (a) {
      root.appendChild(el('li', { 'class': 'audit__item', 'data-audit': a.key }, [
        el('span', { 'class': 'audit__time', dir: 'ltr', text: a.time }),
        el('span', { 'class': 'audit__text', text: t(lang, a.key, a.params) }),
        el('span', { 'class': 'tag tag--sim', text: t(lang, 'ui.auditSim') })
      ]));
    });
  }

  function renderDynamic() {
    renderStepper();
    renderLog();
    renderChoices();
    renderIntent();
    renderSlots();
    renderLead();
    renderAudit();
  }

  function renderAll() { renderChrome(); renderDynamic(); }

  /* ---------- downloads (generated locally) ---------- */

  function download(kind) {
    var state = engine.getState();
    if (!state.lead) return;
    var file;
    var body;
    var type;
    if (kind === 'csv') {
      file = 'or-clinic-demo-lead-DRAFT.csv'; type = 'text/csv;charset=utf-8';
      body = ENGINE.leadToCsv(state.lead);
    } else if (kind === 'json') {
      file = 'or-clinic-demo-lead-DRAFT.json'; type = 'application/json;charset=utf-8';
      body = ENGINE.leadToJson(state.lead);
    } else {
      file = 'or-clinic-demo-confirmation-DRAFT.txt'; type = 'text/plain;charset=utf-8';
      body = engine.confirmationText(lang);
      if (!body) return;
      body = '﻿' + body;
    }
    var url = URL.createObjectURL(new Blob([body], { type: type }));
    var a = el('a', { href: url, download: file });
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    engine.recordExport(file);
    renderAudit();
  }

  /* ---------- events ---------- */

  $('chat-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var input = $('chat-input');
    var value = input.value;
    input.value = '';
    engine.handleText(value);
    renderDynamic();
    input.focus();
  });

  $('choices').addEventListener('click', function (e) {
    var btn = e.target.closest ? e.target.closest('[data-choice]') : null;
    if (!btn) return;
    engine.handleChoice(btn.getAttribute('data-choice'), lang);
    renderDynamic();
    // The clicked chip no longer exists; keep keyboard users in the flow.
    var next = $('choices').querySelector('[data-choice]');
    (next && !$('choices').hidden ? next : $('chat-input')).focus();
  });

  $('lead-body').addEventListener('click', function (e) {
    var btn = e.target.closest ? e.target.closest('[data-download]') : null;
    if (btn) download(btn.getAttribute('data-download'));
  });

  Array.prototype.forEach.call(document.querySelectorAll('.lang__btn'), function (b) {
    b.addEventListener('click', function () {
      lang = b.getAttribute('data-lang');
      renderAll();
    });
  });

  $('mobile-toggle').addEventListener('click', function () {
    mobilePreview = !mobilePreview;
    renderChrome();
  });

  $('reset').addEventListener('click', function () {
    engine.reset();
    $('chat-input').value = '';
    renderAll();
    $('chat-input').focus();
  });

  lang = initialLang();
  renderAll();
})();
