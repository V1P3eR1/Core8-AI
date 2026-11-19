'use strict';
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');

const tmpDir = () => fs.mkdtempSync(path.join(os.tmpdir(), 'core8-pilot-test-'));

// A clock that advances by a fixed step on every read, for stable durations.
function steppingClock(startIso, stepSeconds) {
  let t = new Date(startIso).getTime() - stepSeconds * 1000;
  return () => { t += stepSeconds * 1000; return new Date(t); };
}

// Raw request so tests can set Host / Origin headers that fetch() refuses to override.
function raw(port, opts) {
  return new Promise((resolve, reject) => {
    const body = opts.body === undefined ? null : JSON.stringify(opts.body);
    const req = http.request({
      host: '127.0.0.1', port, method: opts.method || 'GET', path: opts.path,
      headers: Object.assign({ Host: '127.0.0.1:' + port }, body ? { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) } : {}, opts.headers || {})
    }, (res) => {
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => {
        const text = Buffer.concat(chunks).toString('utf8');
        let json = null;
        try { json = JSON.parse(text); } catch (e) { /* not JSON */ }
        resolve({ status: res.statusCode, headers: res.headers, text, json });
      });
    });
    req.on('error', reject);
    if (opts.rawBody !== undefined) req.end(opts.rawBody); else req.end(body || undefined);
  });
}

module.exports = { tmpDir, steppingClock, raw };
