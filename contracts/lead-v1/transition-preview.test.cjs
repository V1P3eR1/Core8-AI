'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {transitionPreview}=require('./transition-preview.cjs');
const fixture=()=>({
 schema_version:'core8.lead.v1',tenant_id:'trusted-A',lead_id:'synthetic-1',
 source:{system:'lead_triage',source_submission_id:'fake-1',verified:true},
 received_at:'2026-11-23T00:00:00Z',language:'he',
 contact:{name:'Fictional Person',email:'demo@example.test',phone:null,company:null},
 inquiry:{message:'Synthetic inquiry',intent:'unknown',service:null},
 consent:{given:true,text_id:'demo-v1',recorded_at:null},
 workflow:{state:'needs_review',human_approved:false},simulation:true
});
const context=()=>({expectedTenantId:'trusted-A',simulationOnly:true,actorRole:'reviewer'});
test('reviewer can approve verified synthetic lead with consent without mutating input',()=>{
 const x=fixture();const before=JSON.stringify(x);
 const r=transitionPreview(x,'approved',context());
 assert.equal(r.ok,true);assert.equal(r.envelope.workflow.state,'approved');
 assert.equal(r.envelope.workflow.human_approved,true);assert.equal(JSON.stringify(x),before);
});
test('non-reviewer cannot approve',()=>{
 const c=context();c.actorRole='viewer';
 assert.ok(transitionPreview(fixture(),'approved',c).errors.includes('reviewer_required'));
});
test('cross-tenant transition rejected',()=>{
 const c=context();c.expectedTenantId='trusted-B';
 assert.ok(transitionPreview(fixture(),'approved',c).errors.includes('tenant_mismatch'));
});
test('unsigned lead cannot be approved',()=>{
 const x=fixture();x.source.verified=false;
 assert.ok(transitionPreview(x,'approved',context()).errors.includes('verified_source_required_for_approval'));
});
test('lead without consent cannot be approved',()=>{
 const x=fixture();x.consent.given=false;
 assert.ok(transitionPreview(x,'approved',context()).errors.includes('consent_required_for_approval'));
});
test('sent is forbidden from any demo state',()=>{
 for(const state of ['needs_review','approved','rejected']){
  const x=fixture();x.workflow.state=state;
  assert.ok(transitionPreview(x,'sent',context()).errors.includes('transition_not_allowed'));
 }
});
test('production lead is rejected even with explicit simulation context',()=>{
 const x=fixture();x.simulation=false;
 assert.ok(transitionPreview(x,'approved',context()).errors.includes('simulation_only'));
});
test('missing simulation context fails closed',()=>{
 const c=context();delete c.simulationOnly;
 assert.ok(transitionPreview(fixture(),'approved',c).errors.includes('simulation_context_required'));
});
test('rejected lead may return to review, never automatically approved',()=>{
 const x=fixture();x.workflow.state='rejected';
 const r=transitionPreview(x,'needs_review',context());
 assert.equal(r.ok,true);assert.equal(r.envelope.workflow.human_approved,false);
});
test('malformed envelope fails without exception',()=>{
 assert.equal(transitionPreview(null,'approved',context()).ok,false);
});
