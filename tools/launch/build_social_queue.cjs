'use strict';
// Offline preview of Social Manager POST /api/social/items request bodies.
// Never sends data to any endpoint. Human review required before any import.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.resolve(__dirname, '../../docs/launch/CORE8_SOCIAL_DRAFTS_HE_EN.md'), 'utf8');
const parts = source.split(/^## (0[1-7])\s+—\s+/m);
const kinds = { '01':'carousel', '02':'reel', '03':'image', '04':'carousel', '05':'image', '06':'carousel', '07':'story' };
const items = [];
for (let i = 1; i < parts.length; i += 2) {
  const id = parts[i];
  const body = parts[i + 1];
  const heading = body.slice(0, body.indexOf('\n')).trim();
  const heMatch = /\*\*HE caption:\*\*\s*([\s\S]*?)\n\*\*EN caption:\*\*/.exec(body);
  const enMatch = /\*\*EN caption:\*\*\s*([\s\S]*?)\n\*\*Format:\*\*/.exec(body);
  assert.ok(heMatch && enMatch, 'Missing complete bilingual caption for ' + id);
  const sanitize = (s) => s.replace(/\*\*CTA:\*\*/g, '').trim();
  const hebrew = sanitize(heMatch[1]);
  const english = sanitize(enMatch[1]);
  assert.ok(hebrew.length > 50 && english.length > 50, 'Caption too short: ' + id);
  const format = kinds[id];
  assert.ok(format, 'Unexpected post ID: ' + id);
  items.push({
    format, title: 'Core8-AI ' + id + ': ' + heading, audience: 'smb',
    caption: hebrew,
    package: {
      source: 'launch-draft-pr53', draft_only: true,
      locale: 'he', english_caption_for_review: english,
      owner_review_required: true,
      visual_status: 'not_produced',
      post_ref: 'core8-own-brand-' + id,
      utm_content: 'post' + id,
      client_data: false,
      review_note: 'Sample draft; verify language, source claims, brand media and lead destination before use.'
    }
  });
}
assert.equal(items.length, 7, 'Exactly seven draft payloads expected');
assert.equal(new Set(items.map((p) => p.package.post_ref)).size, 7);
assert.ok(items.every((p) => !('scheduled_for' in p) && !('account_id' in p) && !('status' in p)));
const out = {
  schema: 'core8-social-item-preview-v1',
  destination_api: '/api/social/items',
  imported: false, published: false,
  note: 'Preview only. Creation requires separately authenticated, owner-reviewed action. No network is used.',
  items
};
process.stdout.write(JSON.stringify(out, null, 2) + '\n');
