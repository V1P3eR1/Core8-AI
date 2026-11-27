'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = __dirname;
const html = fs.readFileSync(path.join(root,'preview.html'),'utf8');
const js = fs.readFileSync(path.join(root,'preview.js'),'utf8');
const css = fs.readFileSync(path.join(root,'preview.css'),'utf8');
test('preview is Hebrew RTL, accessible and explicitly simulation only', () => {
  assert.match(html, /lang="he" dir="rtl"/);
  assert.match(html, /role="status" aria-live="polite"/);
  assert.match(html, /DEMO ONLY/);
  assert.match(html, /NO LIVE DATA/);
});
test('preview has a no-network CSP and local assets only', () => {
  assert.match(html, /default-src 'none'/);
  assert.match(html, /connect-src 'none'/);
  assert.match(html, /script-src 'self'/);
  assert.match(html, /\.\/preview\.js/);
  assert.match(html, /\.\/preview\.css/);
  assert.doesNotMatch(html, /https?:\/\//);
});
test('browser logic does not call network, storage or unsafe DOM HTML APIs', () => {
  assert.doesNotMatch(js, /\b(fetch|XMLHttpRequest|WebSocket|sendBeacon|localStorage|sessionStorage|indexedDB|innerHTML|outerHTML|eval)\b/);
  assert.match(js, /textContent/);
  assert.match(js, /replaceChildren/);
});
test('all four simulation scenarios are represented', () => {
  for (const name of ['valid','tenant','unsigned','consent']) {
    assert.match(html,new RegExp('value="'+name+'"'));
    assert.match(js,new RegExp('\\b'+name+':'));
  }
  assert.match(js,/BLOCKED/);
});
test('responsive preview stylesheet exists', () => {
  assert.match(css, /@media/);
  assert.match(css, /grid-template-columns/);
});
