/* Core8-AI lead-triage pilot - sign-in page. The session is an HttpOnly cookie set by the server. */
(function () {
  'use strict';
  var form = document.getElementById('login-form');
  var error = document.getElementById('login-error');
  var input = document.getElementById('password');
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    error.textContent = '';
    fetch('/api/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: input.value })
    }).then(function (res) {
      return res.json().then(function (data) {
        if (res.ok) { window.location.replace('/'); return; }
        input.value = '';
        input.focus();
        error.textContent = window.I18N.t(data.error || 'Sign-in failed');
      });
    }).catch(function () { error.textContent = window.I18N.t('Could not reach the server'); });
  });
})();
