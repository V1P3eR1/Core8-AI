'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {validateEnvelope:nodeValidate}=require('./validate.cjs');
const script=fs.readFileSync(path.join(__dirname,'validator-universal.js'),'utf8');
const browser={};vm.createContext(browser);vm.runInContext(script,browser);
const browserValidate=browser.Core8LeadContract.validateEnvelope;
const fixture=()=>({
 schema_version:'core8.lead.v1',tenant_id:'tenant-A',lead_id:'synthetic-01',
 source:{system:'lead_triage',source_submission_id:'fake-01',verified:false},
 received_at:'2026-11-23T00:00:00Z',language:'he',
 contact:{name:'Fictional Person',email:null,phone:null,company:null},
 inquiry:{message:'Demo',intent:'unknown',service:null},
 consent:{given:false,text_id:null,recorded_at:null},
 workflow:{state:'needs_review',human_approved:false},simulation:true
});
test('Node and browser use identical validator outputs across positive and negative cases',()=>{
 const cases=[
  [fixture(),{expectedTenantId:'tenant-A'}],
  [fixture(),{expectedTenantId:'tenant-B'}],
  [fixture(),{}],
  [{...fixture(),simulation:false},{expectedTenantId:'tenant-A'}],
  [{...fixture(),source:{system:'social',source_submission_id:'fake-02',verified:true}},{expectedTenantId:'tenant-A'}],
  [{...fixture(),workflow:{state:'sent',human_approved:false}},{expectedTenantId:'tenant-A'}],
  [null,{expectedTenantId:'tenant-A'}]
 ];
 for(const [lead,opts] of cases){
   const expected=nodeValidate(lead,opts);
   const actual=browserValidate(lead,opts);
   assert.equal(JSON.stringify(actual),JSON.stringify(expected));
 }
});
