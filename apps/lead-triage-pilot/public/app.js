/*
 * Core8-AI lead-triage pilot - review UI.
 * Talks only to its own 127.0.0.1 server. Renders with textContent; no HTML
 * strings, no third-party requests. Interface text comes from i18n.js; the
 * only thing kept in the browser is the chosen language.
 */
(function () {
  'use strict';

  var state = { config: null, leads: [], metrics: null, integrity: null };
  var selectedId = null;
  var filter = 'needs_review';

  var STATUS = { needs_review: 'Needs review', approved: 'Approved — not sent', sent: 'Sent by you', rejected: 'Rejected', 'new': 'Drafting' };
  var CATEGORY = { demo_request: 'Demo / meeting', pricing: 'Pricing', support: 'Support', partnership: 'Partnership', not_a_lead: 'Not a lead', other: 'Other' };
  var CHANNEL = { website_form: 'Website form', email: 'Email', whatsapp: 'WhatsApp', phone_note: 'Phone note', social: 'Social', other: 'Other' };
  var FLAG = {
    mentions_price_or_percentage: 'Draft mentions a price or percentage',
    makes_a_promise: 'Draft makes a promise',
    contains_link: 'Draft contains a link',
    has_placeholder_to_fill: 'Draft has a placeholder to fill in'
  };

  var SOURCE = { manual: 'Typed in', form_email: 'Website form (e-mail)', form_direct: 'Website form' };
  var VERIFIED = { verified: 'signature verified', unsigned: 'unsigned', 'null': '' };

  var t = window.I18N.t;
  // Look a server code up in one of the maps above, then translate the English label.
  function L(map, k) { return t(map[k] || k); }

  function $(id) { return document.getElementById(id); }
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === 'class') n.className = attrs[k];
      else if (k === 'text') n.textContent = attrs[k];
      else n.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (c) { if (c) n.appendChild(c); });
    return n;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function when(iso) {
    if (!iso) return '—';
    return new Intl.DateTimeFormat(window.I18N.locale(), { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(iso));
  }
  function num(v, unit) { return v === null || v === undefined ? '—' : String(v) + (unit || ''); }
  function pct(v) { return v === null || v === undefined ? '—' : Math.round(v * 100) + '%'; }

  function call(method, path, body) {
    return fetch(path, {
      method: method,
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined
    }).then(function (res) {
      if (res.status === 401) { window.location.replace('/login.html'); return new Promise(function () {}); }
      return res.json().then(function (data) {
        if (!res.ok) throw new Error(t(data.error || 'Request failed'));
        return data;
      });
    });
  }

  function refresh() {
    return call('GET', '/api/state').then(function (s) { state = s; render(); });
  }

  /* ---------- rendering ---------- */

  function renderChrome() {
    var c = state.config;
    $('engine').textContent = c.engine === 'anthropic'
      ? t('Engine: live model ({model}) — inquiry text is sent to the model API', { model: c.model })
      : t('Engine: offline rules — nothing leaves this computer');
    $('engine').setAttribute('data-engine', c.engine);
    var chain = $('chain');
    chain.textContent = state.integrity.ok
      ? t('Audit log intact · {n} events', { n: state.integrity.events })
      : t('AUDIT LOG BROKEN at event {n}', { n: state.integrity.brokenAt });
    chain.className = 'chain ' + (state.integrity.ok ? 'chain--ok' : 'chain--bad');

    $('logout').hidden = !c.loginRequired;
    var mb = c.mailbox || {};
    $('mailbox').hidden = !mb.enabled;
    if (mb.enabled) {
      var r = mb.lastResult;
      $('mailbox-status').textContent = mb.lastError
        ? t('Mailbox check failed at {when}: {error}', { when: when(mb.lastCheckAt), error: t(mb.lastError) })
        : !mb.lastCheckAt ? t('Mailbox reading is on (read-only). Not checked yet.')
        : t('Mailbox checked {when} (read-only): {created} new, {duplicates} already imported, {rejected} rejected.', { when: when(mb.lastCheckAt), created: r.created, duplicates: r.duplicates, rejected: r.rejected });
    }

    $('intake-mode').textContent = c.signedIntake
      ? t('Only e-mails signed by the website form handler are accepted.')
      : t('No shared secret is set, so unsigned e-mails are accepted and marked as such.');

    var sel = $('f-channel');
    var chosen = sel.value; // rebuilt every time so the labels follow the language
    clear(sel);
    c.channels.forEach(function (ch) { sel.appendChild(el('option', { value: ch, text: L(CHANNEL, ch) })); });
    if (chosen) sel.value = chosen;
  }

  function renderMetrics() {
    var m = state.metrics;
    var root = $('metrics');
    clear(root);
    [
      [t('Inquiries'), num(m.leads), 'leads'],
      [t('Awaiting review'), num(m.awaitingReview), 'awaiting'],
      [t('Approved as drafted'), pct(m.approvedAsIsShare), 'asis'],
      [t('Approved after edit'), pct(m.editedShare), 'edited'],
      [t('Rejected'), pct(m.rejectedShare), 'rejected'],
      [t('Median review time'), num(m.medianReviewMinutes, t(' min')), 'review'],
      [t('Median received → sent'), num(m.medianReceivedToSentMinutes, t(' min')), 'sent']
    ].forEach(function (row) {
      root.appendChild(el('div', { 'class': 'metric', 'data-metric': row[2] }, [
        el('span', { 'class': 'metric__value', text: row[1] }),
        el('span', { 'class': 'metric__label', text: row[0] })
      ]));
    });
  }

  function renderQueue() {
    var filters = $('filters');
    clear(filters);
    [['needs_review', 'Needs review'], ['approved', 'Approved'], ['sent', 'Sent'], ['rejected', 'Rejected'], ['all', 'All']].forEach(function (f) {
      var count = f[0] === 'all' ? state.leads.length : state.leads.filter(function (l) { return l.status === f[0]; }).length;
      filters.appendChild(el('button', {
        type: 'button', 'class': 'chip', 'data-filter': f[0], 'aria-pressed': String(filter === f[0]), text: t(f[1]) + ' (' + count + ')'
      }));
    });

    var root = $('queue');
    clear(root);
    var list = state.leads.filter(function (l) { return filter === 'all' || l.status === filter; });
    if (!list.length) { root.appendChild(el('li', { 'class': 'empty', text: t('Nothing here.') })); return; }
    list.forEach(function (l) {
      var btn = el('button', {
        type: 'button', 'class': 'queue__item' + (l.id === selectedId ? ' is-selected' : ''), 'data-lead': l.id,
        'aria-current': l.id === selectedId ? 'true' : 'false'
      }, [
        el('span', { 'class': 'queue__top' }, [
          el('span', { 'class': 'queue__id', text: l.id }),
          l.triage ? el('span', { 'class': 'tag', text: L(CATEGORY, l.triage.category) }) : null,
          l.triage && l.triage.urgency === 'high' ? el('span', { 'class': 'tag tag--warn', text: t('Urgent') }) : null
        ]),
        el('span', { 'class': 'queue__text', dir: 'auto', text: (l.label ? l.label + ' — ' : '') + l.text.slice(0, 90) }),
        el('span', { 'class': 'queue__meta', text: L(STATUS, l.status) + ' · ' + L(CHANNEL, l.channel) + ' · ' + when(l.addedAt) })
      ]);
      root.appendChild(el('li', {}, [btn]));
    });
  }

  function field(label, value, testid) {
    return el('div', { 'class': 'kv' }, [el('dt', { text: label }), el('dd', { 'data-testid': testid || '' }, [el('bdi', { text: value })])]);
  }

  // A slot goes into the reply, so it is written in the reply's language, not the interface's.
  function slotLabel(s, language) {
    var p = s.date.split('-').map(Number);
    var d = new Date(p[0], p[1] - 1, p[2], 12);
    return new Intl.DateTimeFormat(language === 'he' ? 'he-IL' : 'en-GB', { weekday: 'long', day: 'numeric', month: 'long' }).format(d) + ', ' + s.time;
  }

  // The offline engine writes its reason in English; the model writes its own.
  function rationale(r) {
    var head = 'Matched keywords: ';
    return r.indexOf(head) === 0 ? t(head) + r.slice(head.length) : t(r);
  }

  function contactLine(l) {
    if (!l.contact) return '—';
    return [l.contact.email, l.contact.phone].filter(Boolean).join(' · ') || '—';
  }

  function renderCrm() {
    var body = $('crm-body');
    clear(body);
    if (!state.leads.length) {
      body.appendChild(el('tr', {}, [el('td', { colspan: '8', 'class': 'empty', text: t('No leads yet.') })]));
      return;
    }
    state.leads.forEach(function (l) {
      var cell = function (text, dirAuto) { return el('td', {}, [el('bdi', { text: text })]); };
      var row = el('tr', { 'data-row': l.id }, [
        el('td', {}, [el('button', { type: 'button', 'class': 'link', 'data-open': l.id, text: l.id })]),
        cell(when(l.receivedAt || l.addedAt)),
        cell(l.contact ? l.contact.name : (l.label || '—')),
        cell(l.contact && l.contact.company ? l.contact.company : '—'),
        cell(contactLine(l)),
        cell(l.triage ? L(CATEGORY, l.triage.category) : '—'),
        cell(L(STATUS, l.status)),
        cell(L(SOURCE, l.source) + (l.verified ? ' (' + L(VERIFIED, l.verified) + ')' : ''))
      ]);
      body.appendChild(row);
    });
  }

  function csvCell(v) {
    var s = v === null || v === undefined ? '' : String(v);
    if (/^[=+\-@\t\r]/.test(s)) s = "'" + s; // neutralise spreadsheet formulas
    return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }

  function crmCsv() {
    var head = ['ref', 'received_at', 'name', 'business', 'email', 'phone', 'channel', 'category', 'urgency', 'status', 'source', 'signature', 'consent_text_id', 'decision', 'sent_at'];
    var rows = state.leads.map(function (l) {
      var c = l.contact || {};
      return [l.id, l.receivedAt || l.addedAt, c.name || l.label, c.company, c.email, c.phone, l.channel,
        l.triage ? l.triage.category : '', l.triage ? l.triage.urgency : '', l.status, l.source, l.verified,
        l.consent ? l.consent.textId : '', l.decision ? l.decision.action : '', l.sentAt];
    });
    return '\ufeff' + [head].concat(rows).map(function (r) { return r.map(csvCell).join(','); }).join('\r\n') + '\r\n';
  }

  function saveFile(name, body, type) {
    var url = URL.createObjectURL(new Blob([body], { type: type }));
    var a = el('a', { href: url, download: name });
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  function renderDetail() {
    var root = $('detail');
    var keepDraft = root.querySelector('#d-draft');
    var keepFor = root.getAttribute('data-lead');
    var typed = keepDraft && keepFor === selectedId ? keepDraft.value : null;
    clear(root);
    root.appendChild(el('h2', { id: 'h-detail', text: t('Review') }));
    var l = state.leads.filter(function (x) { return x.id === selectedId; })[0];
    root.setAttribute('data-lead', l ? l.id : '');
    if (!l) { root.appendChild(el('p', { 'class': 'empty', text: t('Select an inquiry from the queue.') })); return; }

    root.appendChild(el('dl', { 'class': 'kvs' }, [
      field(t('Reference'), l.id, 'd-id'),
      field(t('Status'), L(STATUS, l.status), 'd-status'),
      field(t('Channel'), L(CHANNEL, l.channel)),
      field(t('Received'), when(l.receivedAt)),
      field(t('Category'), l.triage ? L(CATEGORY, l.triage.category) : '—', 'd-category'),
      field(t('Urgency'), l.triage ? t(l.triage.urgency) : '—', 'd-urgency'),
      field(t('Drafted by'), l.triage ? (l.triage.engine === 'anthropic' ? t('Live model ({model})', { model: l.triage.model }) : t('Offline rules')) : '—', 'd-engine'),
      field(t('Why'), l.triage ? rationale(l.triage.rationale) : '—'),
      field(t('Source'), L(SOURCE, l.source) + (l.verified ? ' — ' + L(VERIFIED, l.verified) : ''), 'd-source')
    ]));

    if (l.contact) {
      root.appendChild(el('h3', { text: t('Contact (from the form)') }));
      root.appendChild(el('dl', { 'class': 'kvs', 'data-testid': 'd-contact' }, [
        field(t('Name'), l.contact.name, 'd-name'),
        field(t('Business'), l.contact.company || '—'),
        field(t('E-mail'), l.contact.email || '—', 'd-email'),
        field(t('Phone'), l.contact.phone || '—'),
        field(t('Consent'), l.consent && l.consent.given ? (l.consent.textId ? t('Given (text {id})', { id: l.consent.textId }) : t('Given')) : '—', 'd-consent')
      ]));
    }

    root.appendChild(el('h3', { text: t('Inquiry') }));
    root.appendChild(el('p', { 'class': 'quote', dir: 'auto', 'data-testid': 'd-text', text: l.text }));

    if (l.triage && l.triage.fallbackReason) {
      root.appendChild(el('p', { 'class': 'warn', 'data-testid': 'd-fallback', text: t('The live model was not used for this draft ({reason}). Offline rules drafted it instead.', { reason: l.triage.fallbackReason }) }));
    }
    var flags = l.triage ? (l.triage.flags || []) : [];
    if (flags.length) {
      root.appendChild(el('ul', { 'class': 'flags', 'data-testid': 'd-flags' }, flags.map(function (f) { return el('li', { text: L(FLAG, f) }); })));
    }

    var slots = l.triage ? (l.triage.proposedSlots || []) : [];
    var decided = !!l.decision;
    if (slots.length && !decided) {
      root.appendChild(el('h3', { text: t('Suggested meeting times') }));
      root.appendChild(el('ul', { 'class': 'slotlist', 'data-testid': 'd-slots' }, slots.map(function (s, i) {
        return el('li', {}, [
          el('span', { text: slotLabel(s, l.triage.language) }),
          el('button', { type: 'button', 'class': 'btn btn--tiny', 'data-act': 'slot', 'data-slot': String(i), text: t('Add to reply') })
        ]);
      })));
      root.appendChild(el('p', { 'class': 'note', text: t('Built from fixed working hours only. This tool cannot see your calendar: check you are free before offering a time.') }));
    }
    root.appendChild(el('label', { 'for': 'd-draft', text: decided ? (l.decision.action === 'reject' ? t('Draft (rejected)') : t('Approved reply')) : t('Draft reply — edit freely before approving') }));
    var ta = el('textarea', { id: 'd-draft', rows: '10', maxlength: '1500', dir: 'auto', 'data-testid': 'd-draft' });
    ta.value = decided ? (l.decision.finalText || l.triage.draft) : (typed !== null ? typed : (l.triage ? l.triage.draft : ''));
    if (decided) ta.setAttribute('readonly', '');
    root.appendChild(ta);

    var actions = el('div', { 'class': 'actions' });
    if (!decided) {
      actions.appendChild(el('button', { type: 'button', 'class': 'btn btn--primary', 'data-act': 'approve', text: t('Approve reply') }));
      actions.appendChild(el('button', { type: 'button', 'class': 'btn', 'data-act': 'retriage', text: t('Draft again') }));
      root.appendChild(actions);
      root.appendChild(el('div', { 'class': 'reject' }, [
        el('label', { 'for': 'd-reason', text: t('Reject instead — reason (required)') }),
        el('input', { id: 'd-reason', type: 'text', maxlength: '300', dir: 'auto', 'data-testid': 'd-reason' }),
        el('button', { type: 'button', 'class': 'btn btn--danger', 'data-act': 'reject', text: t('Reject draft') })
      ]));
    } else {
      if (l.decision.action === 'reject') {
        root.appendChild(el('p', { 'class': 'note', 'data-testid': 'd-decision', text: t('Rejected {when} — {reason}', { when: when(l.decision.at), reason: l.decision.reason }) }));
      } else {
        root.appendChild(el('p', { 'class': 'note', 'data-testid': 'd-decision', text: l.decision.action === 'edit' ? t('Approved after your edits {when}.', { when: when(l.decision.at) }) : t('Approved as drafted {when}.', { when: when(l.decision.at) }) }));
        actions.appendChild(el('button', { type: 'button', 'class': 'btn btn--primary', 'data-act': 'copy', text: t('Copy reply') }));
        if (l.status === 'approved') actions.appendChild(el('button', { type: 'button', 'class': 'btn', 'data-act': 'sent', text: t('I sent it myself') }));
        if (l.sentAt) actions.appendChild(el('span', { 'class': 'note', 'data-testid': 'd-sent', text: t('You marked this as sent {when}.', { when: when(l.sentAt) }) }));
        root.appendChild(actions);
      }
    }
    root.appendChild(el('p', { 'class': 'error', id: 'd-error', role: 'alert' }));
  }

  function render() { renderChrome(); renderMetrics(); renderQueue(); renderDetail(); renderCrm(); }

  /* ---------- events ---------- */

  function fail(id, err) { $(id).textContent = err.message; }

  $('add-form').addEventListener('submit', function (e) {
    e.preventDefault();
    $('add-error').textContent = '';
    var received = $('f-received').value;
    call('POST', '/api/leads', {
      text: $('f-text').value, channel: $('f-channel').value, label: $('f-label').value,
      receivedAt: received ? new Date(received).toISOString() : null
    }).then(function (r) {
      $('f-text').value = ''; $('f-label').value = ''; $('f-received').value = '';
      selectedId = r.lead.id; filter = 'needs_review';
      return refresh();
    }).then(function () { var d = $('d-draft'); if (d) d.focus(); })
      .catch(function (err) { fail('add-error', err); });
  });

  $('filters').addEventListener('click', function (e) {
    var b = e.target.closest('[data-filter]');
    if (!b) return;
    filter = b.getAttribute('data-filter');
    renderQueue();
  });

  $('queue').addEventListener('click', function (e) {
    var b = e.target.closest('[data-lead]');
    if (!b) return;
    selectedId = b.getAttribute('data-lead');
    renderQueue(); renderDetail();
  });

  $('detail').addEventListener('click', function (e) {
    var b = e.target.closest('[data-act]');
    if (!b) return;
    var act = b.getAttribute('data-act');
    var base = '/api/leads/' + encodeURIComponent(selectedId) + '/';
    var p;
    if (act === 'approve') p = call('POST', base + 'decision', { action: 'approve', finalText: $('d-draft').value });
    else if (act === 'reject') p = call('POST', base + 'decision', { action: 'reject', reason: $('d-reason').value });
    else if (act === 'retriage') { $('d-draft').value = ''; $('detail').setAttribute('data-lead', ''); p = call('POST', base + 'retriage', {}); }
    else if (act === 'sent') p = call('POST', base + 'sent', {});
    else if (act === 'slot') {
      var lead = state.leads.filter(function (x) { return x.id === selectedId; })[0];
      var s = lead.triage.proposedSlots[Number(b.getAttribute('data-slot'))];
      var box = $('d-draft');
      box.value = box.value.replace(/\s+$/, '') + '\n' + slotLabel(s, lead.triage.language);
      box.focus();
      return;
    }
    else if (act === 'copy') {
      var ta = $('d-draft');
      ta.focus(); ta.select();
      var done = function () { b.textContent = t('Copied'); };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(ta.value).then(done, function () { b.textContent = t('Select and copy manually'); });
      else b.textContent = t('Press Ctrl+C to copy');
      return;
    }
    if (!p) return;
    p.then(function (r) { if (act !== 'retriage') filter = 'all'; return refresh(); })
      .catch(function (err) { fail('d-error', err); });
  });

  $('report').addEventListener('click', function () {
    call('GET', '/api/report').then(function (report) {
      saveFile('core8-lead-pilot-evidence-' + report.generatedAt.slice(0, 10) + '.json', JSON.stringify(report, null, 2) + '\n', 'application/json');
    });
  });

  $('intake-form').addEventListener('submit', function (e) {
    e.preventDefault();
    $('intake-error').textContent = '';
    call('POST', '/api/intake/email', { raw: $('i-raw').value }).then(function (r) {
      if (r.duplicate) { $('intake-error').textContent = t('This submission was already imported.'); return null; }
      $('i-raw').value = '';
      selectedId = r.lead.id; filter = 'needs_review';
      return refresh();
    }).catch(function (err) { fail('intake-error', err); });
  });

  $('logout').addEventListener('click', function () {
    call('POST', '/api/logout', {}).then(function () { window.location.replace('/login.html'); });
  });

  $('mailbox-check').addEventListener('click', function () {
    var b = $('mailbox-check');
    b.disabled = true;
    call('POST', '/api/mailbox/check', {}).then(refresh).catch(function (err) { $('mailbox-status').textContent = err.message; })
      .then(function () { b.disabled = false; });
  });

  $('crm-csv').addEventListener('click', function () {
    saveFile('core8-leads-' + new Date().toISOString().slice(0, 10) + '.csv', crmCsv(), 'text/csv;charset=utf-8');
  });

  $('crm-body').addEventListener('click', function (e) {
    var b = e.target.closest('[data-open]');
    if (!b) return;
    selectedId = b.getAttribute('data-open'); filter = 'all';
    renderQueue(); renderDetail();
    $('detail').scrollIntoView({ block: 'start' });
  });

  window.I18N.onChange = function () { if (state.config) render(); };

  refresh();
})();
