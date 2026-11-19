/*
 * Minimal static file server for the customer demos. Binds to 127.0.0.1 only.
 * Usage: node tests/serve.cjs [port]   (default 4173)
 * The demos also work by opening receptionist/index.html directly from disk.
 */
'use strict';
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const TYPES = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.md': 'text/markdown; charset=utf-8', '.png': 'image/png', '.svg': 'image/svg+xml'
};

function createServer() {
  return http.createServer((req, res) => {
    let rel;
    try { rel = decodeURIComponent(new URL(req.url, 'http://127.0.0.1').pathname); }
    catch (e) { res.writeHead(400).end('Bad request'); return; }
    if (rel.endsWith('/')) rel += 'index.html';
    const file = path.resolve(ROOT, '.' + rel);
    // Never serve anything outside the demos folder.
    if (file !== ROOT && !file.startsWith(ROOT + path.sep)) { res.writeHead(403).end('Forbidden'); return; }
    fs.readFile(file, (err, data) => {
      if (err) { res.writeHead(404, { 'Content-Type': 'text/plain' }).end('Not found'); return; }
      res.writeHead(200, {
        'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream',
        'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff'
      }).end(data);
    });
  });
}

function listen(port) {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.once('error', reject);
    server.listen(port, '127.0.0.1', () => resolve(server));
  });
}

module.exports = { listen, ROOT };

if (require.main === module) {
  const port = Number(process.argv[2]) || 4173;
  listen(port).then(() => {
    console.log('Core8 customer demos (offline, mock data)');
    console.log('Receptionist demo: http://127.0.0.1:' + port + '/receptionist/');
    console.log('Press Ctrl+C to stop.');
  });
}
