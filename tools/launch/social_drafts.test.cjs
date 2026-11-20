'use strict';
// Static editorial completeness checks; no API calls and no publication.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const file = path.resolve(__dirname, '../../docs/launch/CORE8_SOCIAL_DRAFTS_HE_EN.md');
const text = fs.readFileSync(file, 'utf8');
assert.match(text, /DRAFT \/ NOT SCHEDULED \/ NOT PUBLISHED/i);
const sections = text.split(/^## (0[1-7])\s+—\s+/m);
const seen = new Set();
for (let i = 1; i < sections.length; i += 2) {
  const id = sections[i];
  const content = sections[i + 1] || '';
  assert.ok(!seen.has(id), 'Duplicate post ID: ' + id);
  seen.add(id);
  assert.match(content, /\*\*HE caption:\*\*/i, 'Hebrew caption missing in ' + id);
  assert.match(content, /\*\*EN caption:\*\*/i, 'English caption missing in ' + id);
  assert.match(content, /\*\*CTA:\*\*/i, 'Call to action missing in ' + id);
  assert.match(content, /\*\*Format:\*\*/i, 'Format missing in ' + id);
  assert.match(content, /\*\*Media:\*\*/i, 'Media requirement missing in ' + id);
  assert.match(content, /\*\*Claim check:\*\*/i, 'Fact claim check missing in ' + id);
  assert.match(content, new RegExp('utm_content=post' + id), 'UTM placeholder missing in ' + id);
}
assert.deepEqual([...seen].sort(), ['01','02','03','04','05','06','07'], 'Exactly seven posts needed');
assert.match(text, /mock.*approval|approval.*mock/i, 'Mock approval gate missing');
process.stdout.write('PASS: seven complete bilingual drafts with CTA, format, assets, claim checks and traceable UTM placeholders.\n');
