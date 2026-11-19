/*
 * Core8-AI lead-triage pilot - review UI.
 * Talks only to its own 127.0.0.1 server. Renders with textContent; no HTML
 * strings, no storage, no third-party requests.
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
    return new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(iso));
  }
  function num(v, unit) { return v === null || v === undefined ? '—' : String(v) + (unit || ''); }
  function pct(v) { return v === null || v === undefined ? '—' : Math.round(v * 100) + '%'; }

  function call(method, path, body) {
    return fetch(path, {
      method: method,
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined
    }).then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok) throw new Error(data.error || 'Request failed');
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
      ? 'Engine: live model (' + c.model + ') — inquiry text is sent to the model API'
      : 'Engine: offline rules — nothing leaves this computer';
    $('engine').setAttribute('data-engine', c.engine);
    var chain = $('chain');
    chain.textContent = state.integrity.ok
      ? 'Audit log intact · ' + state.integrity.events + ' events'
      : 'AUDIT LOG BROKEN at event ' + state.integrity.brokenAt;
    chain.className = 'chain ' + (state.integrity.ok ? 'chain--ok' : 'chain--bad');

    var sel = $('f-channel');
    if (!sel.options.length) {
      c.channels.forEach(function (ch) { sel.appendChild(el('option', { value: ch, text: CHANNEL[ch] || ch })); });
    }
  }

  function renderMetrics() {
    var m = state.metrics;
    var root = $('metrics');
    clear(root);
    [
      ['Inquiries', num(m.leads), 'leads'],
      ['Awaiting review', num(m.awaitingReview), 'awaiting'],
      ['Approved as drafted', pct(m.approvedAsIsShare), 'asis'],
      ['Approved after edit', pct(m.editedShare), 'edited'],
      ['Rejected', pct(m.rejectedShare), 'rejected'],
      ['Median review time', num(m.medianReviewMinutes, ' min'), 'review'],
      ['Median received → sent', num(m.medianReceivedToSentMinutes, ' min'), 'sent']
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
        type: 'button', 'class': 'chip', 'data-filter': f[0], 'aria-pressed': String(filter === f[0]), text: f[1] + ' (' + count + ')'
      }));
    });

    var root = $('queue');
    clear(root);
    var list = state.leads.filter(function (l) { return filter === 'all' || l.status === filter; });
    if (!list.length) { root.appendChild(el('li', { 'class': 'empty', text: 'Nothing here.' })); return; }
    list.forEach(function (l) {
      var btn = el('button', {
        type: 'button', 'class': 'queue__item' + (l.id === selectedId ? ' is-selected' : ''), 'data-lead': l.id,
        'aria-current': l.id === selectedId ? 'true' : 'false'
      }, [
        el('span', { 'class': 'queue__top' }, [
          el('span', { 'class': 'queue__id', text: l.id }),
          l.triage ? el('span', { 'class': 'tag', text: CATEGORY[l.triage.category] }) : null,
          l.triage && l.triage.urgency === 'high' ? el('span', { 'class': 'tag tag--warn', text: 'Urgent' }) : null
        ]),
        el('span', { 'class': 'queue__text', dir: 'auto', text: (l.label ? l.label + ' — ' : '') + l.text.slice(0, 90) }),
        el('span', { 'class': 'queue__meta', text: STATUS[l.status] + ' · ' + (CHANNEL[l.channel] || l.channel) + ' · ' + when(l.addedAt) })
      ]);
      root.appendChild(el('li', {}, [btn]));
    });
  }

  function field(label, value, testid) {
    return el('div', { 'class': 'kv' }, [el('dt', { text: label }), el('dd', { 'data-testid': testid || '' }, [el('bdi', { text: value })])]);
  }

  function renderDetail() {
    var root = $('detail');
    var keepDraft = root.querySelector('#d-draft');
    var keepFor = root.getAttribute('data-lead');
    var typed = keepDraft && keepFor === selectedId ? keepDraft.value : null;
    clear(root);
    root.appendChild(el('h2', { id: 'h-detail', text: 'Review' }));
    var l = state.leads.filter(function (x) { return x.id === selectedId; })[0];
    root.setAttribute('data-lead', l ? l.id : '');
    if (!l) { root.appendChild(el('p', { 'class': 'empty', text: 'Select an inquiry from the queue.' })); return; }

    root.appendChild(el('dl', { 'class': 'kvs' }, [
      field('Reference', l.id, 'd-id'),
      field('Status', STATUS[l.status], 'd-status'),
      field('Channel', CHANNEL[l.channel] || l.channel),
      field('Received', when(l.receivedAt)),
      field('Category', l.triage ? CATEGORY[l.triage.category] : '—', 'd-category'),
      field('Urgency', l.triage ? l.triage.urgency : '—', 'd-urgency'),
      field('Drafted by', l.triage ? (l.triage.engine === 'anthropic' ? 'Live model (' + l.triage.model + ')' : 'Offline rules') : '—', 'd-engine'),
      field('Why', l.triage ? l.triage.rationale : '—')
    ]));

    root.appendChild(el('h3', { text: 'Inquiry' }));
    root.appendChild(el('p', { 'class': 'quote', dir: 'auto', 'data-testid': 'd-text', text: l.text }));

    if (l.triage && l.triage.fallbackReason) {
      root.appendChild(el('p', { 'class': 'warn', 'data-testid': 'd-fallback', text: 'The live model was not used for this draft (' + l.triage.fallbackReason + '). Offline rules drafted it instead.' }));
    }
    var flags = l.triage ? (l.triage.flags || []) : [];
    if (flags.length) {
      root.appendChild(el('ul', { 'class': 'flags', 'data-testid': 'd-flags' }, flags.map(function (f) { return el('li', { text: FLAG[f] || f }); })));
    }

    var decided = !!l.decision;
    root.appendChild(el('label', { 'for': 'd-draft', text: decided ? (l.decision.action === 'reject' ? 'Draft (rejected)' : 'Approved reply') : 'Draft reply — edit freely before approving' }));
    var ta = el('textarea', { id: 'd-draft', rows: '10', maxlength: '1500', dir: 'auto', 'data-testid': 'd-draft' });
    ta.value = decided ? (l.decision.finalText || l.triage.draft) : (typed !== null ? typed : (l.triage ? l.triage.draft : ''));
    if (decided) ta.setAttribute('readonly', '');
    root.appendChild(ta);

    var actions = el('div', { 'class': 'actions' });
    if (!decided) {
      actions.appendChild(el('button', { type: 'button', 'class': 'btn btn--primary', 'data-act': 'approve', text: 'Approve reply' }));
      actions.appendChild(el('button', { type: 'button', 'class': 'btn', 'data-act': 'retriage', text: 'Draft again' }));
      root.appendChild(actions);
      root.appendChild(el('div', { 'class': 'reject' }, [
        el('label', { 'for': 'd-reason', text: 'Reject instead — reason (required)' }),
        el('input', { id: 'd-reason', type: 'text', maxlength: '300', dir: 'auto', 'data-testid': 'd-reason' }),
        el('button', { type: 'button', 'class': 'btn btn--danger', 'data-act': 'reject', text: 'Reject draft' })
      ]));
    } else {
      if (l.decision.action === 'reject') {
        root.appendChild(el('p', { 'class': 'note', 'data-testid': 'd-decision', text: 'Rejected ' + when(l.decision.at) + ' — ' + l.decision.reason }));
      } else {
        root.appendChild(el('p', { 'class': 'note', 'data-testid': 'd-decision', text: (l.decision.action === 'edit' ? 'Approved after your edits ' : 'Approved as drafted ') + when(l.decision.at) + '.' }));
        actions.appendChild(el('button', { type: 'button', 'class': 'btn btn--primary', 'data-act': 'copy', text: 'Copy reply' }));
        if (l.status === 'approved') actions.appendChild(el('button', { type: 'button', 'class': 'btn', 'data-act': 'sent', text: 'I sent it myself' }));
        if (l.sentAt) actions.appendChild(el('span', { 'class': 'note', 'data-testid': 'd-sent', text: 'You marked this as sent ' + when(l.sentAt) + '.' }));
        root.appendChild(actions);
      }
    }
    root.appendChild(el('p', { 'class': 'error', id: 'd-error', role: 'alert' }));
  }

  function render() { renderChrome(); renderMetrics(); renderQueue(); renderDetail(); }

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
    else if (act === 'copy') {
      var ta = $('d-draft');
      ta.focus(); ta.select();
      var done = function () { b.textContent = 'Copied'; };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(ta.value).then(done, function () { b.textContent = 'Select and copy manually'; });
      else b.textContent = 'Press Ctrl+C to copy';
      return;
    }
    if (!p) return;
    p.then(function (r) { if (act !== 'retriage') filter = 'all'; return refresh(); })
      .catch(function (err) { fail('d-error', err); });
  });

  $('report').addEventListener('click', function () {
    call('GET', '/api/report').then(function (report) {
      var url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2) + '\n'], { type: 'application/json' }));
      var a = el('a', { href: url, download: 'core8-lead-pilot-evidence-' + report.generatedAt.slice(0, 10) + '.json' });
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    });
  });

  refresh();
})();
