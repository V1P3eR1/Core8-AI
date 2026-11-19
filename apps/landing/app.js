/*
 * Core8-AI landing prototype - language switch and form validation.
 * Preview mode: with no form endpoint configured the form validates and then
 * says plainly that nothing was sent. There is no network code in this file;
 * wiring the form to the platform's lead endpoint is a separate, reviewed step.
 */
(function () {
  'use strict';
  var C = window.Core8Landing;
  var lang = /[?&#]lang=en\b/.test(location.search + location.hash) ? 'en' : 'he';
  var statusKey = null;

  function t(key) { return C.strings[lang][key] || C.strings.he[key] || key; }

  function render() {
    document.documentElement.lang = lang;
    document.documentElement.dir = C.langs[lang].dir;
    document.title = t('meta.title');
    Array.prototype.forEach.call(document.querySelectorAll('[data-i18n]'), function (n) { n.textContent = t(n.getAttribute('data-i18n')); });
    Array.prototype.forEach.call(document.querySelectorAll('[data-i18n-content]'), function (n) { n.setAttribute('content', t(n.getAttribute('data-i18n-content'))); });
    Array.prototype.forEach.call(document.querySelectorAll('[data-lang]'), function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-lang') === lang)); });
    var status = document.getElementById('form-status');
    status.textContent = statusKey ? t(statusKey) : '';
  }

  function setStatus(key, kind) {
    statusKey = key;
    var status = document.getElementById('form-status');
    status.textContent = key ? t(key) : '';
    status.className = 'status' + (kind ? ' status--' + kind : '');
  }

  function validEmail(v) { return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v); }
  function validPhone(v) { return /^\+?[\d\s().-]{7,20}$/.test(v) && (v.match(/\d/g) || []).length >= 7; }

  Array.prototype.forEach.call(document.querySelectorAll('[data-lang]'), function (b) {
    b.addEventListener('click', function () { lang = b.getAttribute('data-lang'); render(); });
  });

  document.getElementById('lead-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var f = e.target;
    var name = f.elements.name.value.trim();
    var email = f.elements.email.value.trim();
    var phone = f.elements.phone.value.trim();
    var fields = [f.elements.name, f.elements.email, f.elements.phone, f.elements.consent];
    fields.forEach(function (x) { x.removeAttribute('aria-invalid'); });

    if (!name) { f.elements.name.setAttribute('aria-invalid', 'true'); f.elements.name.focus(); return setStatus('form.err.name', 'error'); }
    var emailOk = email && validEmail(email);
    var phoneOk = phone && validPhone(phone);
    if ((email && !emailOk) || (phone && !phoneOk) || (!emailOk && !phoneOk)) {
      var bad = (email && !emailOk) || !phone ? f.elements.email : f.elements.phone;
      bad.setAttribute('aria-invalid', 'true'); bad.focus();
      return setStatus('form.err.contact', 'error');
    }
    if (!f.elements.consent.checked) { f.elements.consent.setAttribute('aria-invalid', 'true'); f.elements.consent.focus(); return setStatus('form.err.consent', 'error'); }

    // Bots fill the hidden field; show the same message and do nothing.
    setStatus('form.preview', 'info');
  });

  render();
})();
