'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { runDemo } = require('./demo.cjs');
test('end-to-end synthetic lead demo passes and rejects cross-tenant access', () => {
  const r = runDemo();
  assert.equal(r.adapter, 'PASS');
  assert.equal(r.contract, 'PASS');
  assert.equal(r.cross_tenant_rejected, true);
  assert.equal(r.simulated_only, true);
  assert.equal(r.approved, false);
  assert.equal(r.status, 'needs_review');
  assert.equal(r.source_verified, false);
  assert.equal(r.side_effects, 'NONE');
});
