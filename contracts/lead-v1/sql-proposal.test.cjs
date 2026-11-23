'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const sql=fs.readFileSync(path.join(__dirname,'postgres-idempotency.proposal.sql'),'utf8');
test('proposal has atomic tenant-scoped uniqueness',()=>{
 assert.match(sql,/PRIMARY KEY\s*\(tenant_id,\s*source_system,\s*source_submission_id\)/i);
 assert.match(sql,/UNIQUE\s*\(tenant_id,\s*lead_id\)/i);
});
test('proposal stores only digest rather than full payload',()=>{
 assert.match(sql,/payload_sha256 char\(64\)/i);
 assert.doesNotMatch(sql,/\b(payload_json|email_address|phone_number)\s+(jsonb|text|varchar)/i);
});
test('proposal is explicitly not deployed and uses transactional boundaries',()=>{
 assert.match(sql,/PROPOSAL ONLY/i);
 assert.match(sql,/BEGIN;/);
 assert.match(sql,/COMMIT;/);
 assert.match(sql,/ON CONFLICT/i);
});
