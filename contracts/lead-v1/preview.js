'use strict';
// Pure browser demonstration using the same validator as Node.
// Synthetic fixtures only; no network, storage, contact or production actions.
const scenarios = Object.freeze({
  valid: {title:'בדיקת פנייה סינתטית',expectedTenant:'demo-tenant-A'},
  tenant: {title:'בדיקת גישה של Tenant אחר',expectedTenant:'demo-tenant-B'},
  unsigned: {title:'בדיקת מקור לא מאומת',expectedTenant:'demo-tenant-A'},
  consent: {title:'בדיקת פנייה ללא הסכמה',expectedTenant:'demo-tenant-A'}
});
const select = document.getElementById('scenario');
const status = document.getElementById('status');
const checks = document.getElementById('checks');
function fixture(key) {
  return {
    schema_version:'core8.lead.v1', tenant_id:'demo-tenant-A', lead_id:'synthetic-lead-01',
    source:{system:'lead_triage',source_submission_id:'fake-submission-01',verified:key!=='unsigned'},
    received_at:'2026-11-23T00:00:00Z',language:'he',
    contact:{name:'Fictional Demo Customer',email:'demo@example.test',phone:null,company:'Example Clinic'},
    inquiry:{message:'Synthetic inquiry',intent:'unknown',service:null},
    consent:{given:key!=='consent',text_id:'demo-v1',recorded_at:null},
    workflow:{state:'needs_review',human_approved:false},
    simulation:true
  };
}
function runScenario(key) {
  const scenario = scenarios[key] || scenarios.tenant;
  const envelope = fixture(key);
  const validation = Core8LeadContract.validateEnvelope(envelope,{expectedTenantId:scenario.expectedTenant});
  const blockers = validation.errors.slice();
  // Additional workflow gate: validator checks structural validity, while
  // contact/promotion policy is deliberately more restrictive.
  if (!envelope.source.verified) blockers.push('source_unverified_for_contact');
  if (!envelope.consent.given) blockers.push('consent_missing_for_contact');
  const pass = validation.ok && blockers.length===0;
  return {pass,title:(pass?'PASS · ':'BLOCKED · ')+scenario.title,checks:[
    'בדיקת מבנה: '+(validation.ok?'PASS':'FAIL'),
    'Tenant: '+(validation.errors.includes('tenant_mismatch')?'MISMATCH':'MATCH'),
    'מקור מאומת: '+(envelope.source.verified?'YES':'NO'),
    'הסכמה: '+(envelope.consent.given?'YES':'NO'),
    'פעולות חיצוניות: NONE',
    ...blockers.map(code=>'חסימה: '+code)
  ]};
}
function render(result) {
  status.textContent=result.title;
  status.className='result '+(result.pass?'pass':'fail');
  checks.replaceChildren();
  for (const message of result.checks) {
    const item=document.createElement('li');item.textContent=message;checks.appendChild(item);
  }
}
document.getElementById('run').addEventListener('click',()=>render(runScenario(select.value)));
document.getElementById('reset').addEventListener('click',()=>{
  select.value='valid';status.textContent='בחר תרחיש ולחץ על הרצת בדיקה.';
  status.className='result';checks.replaceChildren();
  const item=document.createElement('li');item.textContent='ממתין להפעלה';checks.appendChild(item);
});
