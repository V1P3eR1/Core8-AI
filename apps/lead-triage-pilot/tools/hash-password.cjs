'use strict';
/*
 * Creates the value for CORE8_PILOT_PASSWORD_HASH.
 *   node tools/hash-password.cjs
 * The password is typed at a hidden prompt (or piped on stdin); it is never
 * taken from the command line, so it does not end up in shell history.
 */
const { hashPassword } = require('../lib/auth.cjs');

module.exports = { readHidden };

function readHidden(prompt) {
  return new Promise((resolve) => {
    if (!process.stdin.isTTY) {
      let data = ''; process.stdin.setEncoding('utf8');
      process.stdin.on('data', (c) => { data += c; });
      process.stdin.on('end', () => resolve(data.replace(/\r?\n$/, '')));
      return;
    }
    process.stderr.write(prompt);
    process.stdin.setRawMode(true); process.stdin.resume(); process.stdin.setEncoding('utf8');
    let value = '';
    process.stdin.on('data', function onData(ch) {
      if (ch === '\r' || ch === '\n' || ch === '\u0004') { process.stdin.setRawMode(false); process.stdin.pause(); process.stdin.removeListener('data', onData); process.stderr.write('\n'); resolve(value); }
      else if (ch === '\u0003') { process.stderr.write('\n'); process.exit(130); }
      else if (ch === '\u007f') value = value.slice(0, -1);
      else value += ch;
    });
  });
}

if (require.main === module) {
  readHidden('New password (12+ characters, not shown): ').then((pw) => {
    try { console.log(hashPassword(pw)); }
    catch (e) { console.error(e.message); process.exit(1); }
  });
}
