'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {makeDedupKey,previewDedup}=require('./dedup-preview.cjs');
const lead=(tenant='tenant-A',system='lead_triage',submission='synthetic-1',id='L-1')=>({
 tenant_id:tenant,lead_id:id,source:{system,source_submission_id:submission}
});
test('same source submission within tenant is a duplicate',()=>{
 const r=previewDedup([lead()],lead('tenant-A','lead_triage','synthetic-1','L-2'),'tenant-A');
 assert.deepEqual(r,{ok:true,duplicate:true,existingLeadId:'L-1'});
});
test('same submission ID in different tenant is not a duplicate',()=>{
 assert.equal(previewDedup([lead('tenant-B')],lead(),'tenant-A').duplicate,false);
});
test('same submission ID from different source is not a duplicate',()=>{
 assert.equal(previewDedup([lead('tenant-A','social')],lead(),'tenant-A').duplicate,false);
});
test('different submission IDs are not duplicates',()=>{
 assert.equal(previewDedup([lead()],lead('tenant-A','lead_triage','synthetic-2'),'tenant-A').duplicate,false);
});
test('caller cannot request a tenant other than trusted context',()=>{
 assert.equal(previewDedup([],lead('tenant-B'),'tenant-A').error,'invalid_input_or_tenant');
});
test('dedup keys cannot collide across separator boundaries',()=>{
 const a=makeDedupKey({tenantId:'a:b',sourceSystem:'c',sourceSubmissionId:'d'});
 const b=makeDedupKey({tenantId:'a',sourceSystem:'b:c',sourceSubmissionId:'d'});
 assert.equal(a.ok,true);assert.equal(b.ok,true);assert.notEqual(a.key,b.key);
});
test('rejects empty, unsafe and oversized identifiers',()=>{
 for(const id of ['', 'a|b','hello world','x'.repeat(257)]){
  assert.equal(makeDedupKey({tenantId:'tenant-A',sourceSystem:'social',sourceSubmissionId:id}).ok,false);
 }
});
test('malformed records are ignored safely',()=>{
 assert.equal(previewDedup([null,{},lead('tenant-B')],lead(),'tenant-A').duplicate,false);
});
test('unbounded input is rejected',()=>{
 assert.equal(previewDedup(Array(1001).fill(lead()),lead(),'tenant-A').ok,false);
});
test('no mutation of input records',()=>{
 const records=[lead()];const candidate=lead('tenant-A','lead_triage','synthetic-2');
 const before=JSON.stringify([records,candidate]);
 previewDedup(records,candidate,'tenant-A');
 assert.equal(JSON.stringify([records,candidate]),before);
});
