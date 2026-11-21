'use strict';
/*
 * Builds the folder that gets uploaded to the web host.
 *
 *   node tools/package.cjs            preview build: draft banner and noindex stay
 *   node tools/package.cjs --launch   launch build: refuses unless the page is ready
 *   options for a launch build:
 *     --static-only   leave out the PHP form handler (the form posts to the lead
 *                     agent instead, through the reverse proxy on the same server)
 *     --noindex       keep the search-engine block (for an interim domain)
 *     --out <dir>     write somewhere other than out/site
 *
 * The launch build removes the draft banners and the search-engine block. It
 * refuses to run while required items are missing, so an unfinished page
 * cannot be published by accident. Output: apps/landing/out/site/ (git-ignored).
 * This script only copies files; it does not upload or publish anything.
 */
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const PHP_FILES = ['server/lead.php', 'server/.htaccess'];
const SITE_FILES = ['index.html', 'privacy.html', 'accessibility.html', 'styles.css', 'app.js', 'content.js',
  'assets/logo-mark.svg', 'assets/favicon.svg', 'server/lead.php', 'server/.htaccess'];

function launchProblems(root) {
  const problems = [];
  const read = (f) => fs.readFileSync(path.join(root, f), 'utf8');
  delete require.cache[require.resolve(path.join(root, 'content.js'))];
  const C = require(path.join(root, 'content.js'));
  if (!C.config.formEndpoint) problems.push('content.js: formEndpoint is empty (the form would stay in preview mode)');
  if (!C.config.consentTextId) problems.push('content.js: consentTextId is empty (no approved consent wording is referenced)');
  for (const f of ['privacy.html', 'accessibility.html']) {
    if (/\[(?:להשלים|to complete|To complete|to be completed)/.test(read(f))) problems.push(f + ': still contains [to complete] placeholders');
  }
  for (const lang of Object.keys(C.strings)) {
    for (const [k, v] of Object.entries(C.strings[lang])) if (/\[[^\]]*(?:ממתינ|awaiting)[^\]]*\]/.test(v)) problems.push(`content.js: ${lang}.${k} is still a placeholder`);
  }
  return problems;
}

const esc = (t) => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

// Writes the Hebrew text straight into the HTML. Without this the page is
// empty for anything that does not run JavaScript: link previews in WhatsApp
// and social networks, some search and AI crawlers, and visitors with scripts
// blocked. app.js still takes over in the browser and handles the language switch.
function prerender(html, strings) {
  let missing = [];
  const text = (k) => { if (!(k in strings)) { missing.push(k); return ''; } return esc(strings[k]); };
  html = html.replace(/(<[a-z0-9]+\b[^>]*\sdata-i18n="([^"]+)"[^>]*>)(<\/)/g, (m, open, key, close) => open + text(key) + close);
  html = html.replace(/content=""(\s+data-i18n-content="([^"]+)")/g, (m, rest, key) => 'content="' + text(key) + '"' + rest);
  html = html.replace(/<title>[^<]*<\/title>/, '<title>' + text('meta.title') + '</title>');
  if (missing.length) throw new Error('prerender: unknown text keys: ' + missing.join(', '));
  return html;
}

function build(opts) {
  const root = opts.root || ROOT;
  const out = opts.out || path.join(root, 'out', 'site');
  if (opts.launch) {
    const problems = launchProblems(root);
    if (problems.length) return { ok: false, problems };
  }
  fs.rmSync(out, { recursive: true, force: true });
  const files = opts.staticOnly ? SITE_FILES.filter((f) => !PHP_FILES.includes(f)) : SITE_FILES;
  for (const f of files) {
    const dest = path.join(out, f);
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    let data = fs.readFileSync(path.join(root, f));
    if (f === 'index.html') {
      delete require.cache[require.resolve(path.join(root, 'content.js'))];
      data = Buffer.from(prerender(data.toString('utf8'), require(path.join(root, 'content.js')).strings.he), 'utf8');
    }
    if (opts.launch && f.endsWith('.html')) {
      data = Buffer.from(data.toString('utf8')
        .replace(/^\s*<!-- Prototype:[^\n]*-->\n/m, '')
        .replace(opts.noindex ? /(?!)/ : /^\s*<meta name="robots" content="noindex, nofollow">\n/m, '')
        .replace(/^\s*<div class="draft"[^\n]*<\/div>\n/m, ''), 'utf8');
    }
    fs.writeFileSync(dest, data);
  }
  if (!opts.staticOnly) {
    // Keep the handler's real config out of the web-readable bundle by default.
    fs.writeFileSync(path.join(out, 'server', 'README.txt'),
      'Create lead-config.php in this folder on the host (see lead-config.example.php in the repository). Never commit it.\n');
  }
  return { ok: true, out, files, launch: !!opts.launch };
}

module.exports = { build, launchProblems, prerender, SITE_FILES };

if (require.main === module) {
  const a = process.argv;
  const launch = a.includes('--launch');
  const outAt = a.indexOf('--out');
  const r = build({ launch, staticOnly: a.includes('--static-only'), noindex: a.includes('--noindex'),
    out: outAt !== -1 && a[outAt + 1] ? path.resolve(a[outAt + 1]) : undefined });
  if (!r.ok) {
    console.error('Not ready to launch:\n- ' + r.problems.join('\n- '));
    process.exit(1);
  }
  console.log((launch ? 'LAUNCH' : 'PREVIEW') + ' build written to ' + path.relative(process.cwd(), r.out));
  console.log(r.files.length + ' files. Upload the CONTENTS of that folder to the site\'s public folder on the host.');
  if (!launch) console.log('Preview build: draft banner and search-engine block are still in place.');
}
