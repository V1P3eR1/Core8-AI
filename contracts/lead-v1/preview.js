'use strict';
// Browser-only demonstration. No network, storage, customer data or side effects.
const scenarios = Object.freeze({
  valid: {pass:true,title:'PASS · הפנייה עברה בדיקות דמו',checks:['מבנה הפנייה תקין','מזהה Tenant תואם להקשר המהימן','הפנייה נשמרת כסימולציה בלבד','נדרש אישור אנושי לפני פעולה']},
  tenant: {pass:false,title:'BLOCKED · ניסיון גישה בין לקוחות נדחה',checks:['מבנה הפנייה תקין','מזהה Tenant אינו תואם','הגישה נדחית; אין פעולת המשך']},
  unsigned: {pass:false,title:'REVIEW · מקור הפנייה אינו מאומת',checks:['מבנה הפנייה תקין','חתימת מקור לא אומתה','מותרת בדיקת דמו בלבד; אין קידום אוטומטי']},
  consent: {pass:false,title:'BLOCKED · אין הסכמה מתועדת',checks:['מבנה הפנייה תקין','לא קיימת הסכמה מפורשת','אין יצירת קשר או עיבוד ייצור']}
});
const select = document.getElementById('scenario');
const status = document.getElementById('status');
const checks = document.getElementById('checks');
function render(result) {
  status.textContent = result.title;
  status.className = 'result ' + (result.pass ? 'pass' : 'fail');
  checks.replaceChildren();
  for (const message of result.checks) {
    const item = document.createElement('li');
    item.textContent = message;
    checks.appendChild(item);
  }
}
document.getElementById('run').addEventListener('click', () => render(scenarios[select.value] || scenarios.tenant));
document.getElementById('reset').addEventListener('click', () => {
  select.value = 'valid';
  status.textContent = 'בחר תרחיש ולחץ על הרצת בדיקה.';
  status.className = 'result';
  checks.replaceChildren();
  const item = document.createElement('li');
  item.textContent = 'ממתין להפעלה';
  checks.appendChild(item);
});
