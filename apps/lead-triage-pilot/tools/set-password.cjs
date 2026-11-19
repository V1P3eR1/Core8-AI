'use strict';
/*
 * Sets or changes the sign-in password on the server itself.
 *   node tools/set-password.cjs
 * Writes only the scrypt hash to CORE8_PILOT_PASSWORD_HASH_FILE (owner-readable
 * only). The password is typed at a hidden prompt, twice, or piped on stdin.
 * Takes effect at the next sign-in; no restart needed. Existing sessions stay.
 */
const fs = require('node:fs');
const { hashPassword } = require('../lib/auth.cjs');
const { readHidden } = require('./hash-password.cjs');

const file = process.env.CORE8_PILOT_PASSWORD_HASH_FILE;
if (!file) { console.error('CORE8_PILOT_PASSWORD_HASH_FILE is not set.'); process.exit(1); }

(async () => {
  const pw = await readHidden('New password (12+ characters, not shown): ');
  if (process.stdin.isTTY) {
    const again = await readHidden('Type it again: ');
    if (again !== pw) { console.error('The two entries do not match. Nothing was changed.'); process.exit(1); }
  }
  let hash;
  try { hash = hashPassword(pw); } catch (e) { console.error(e.message + '. Nothing was changed.'); process.exit(1); }
  const tmp = file + '.tmp';
  fs.writeFileSync(tmp, hash + '\n', { mode: 0o600 });
  fs.renameSync(tmp, file);
  console.log('Password set. You can sign in now.');
})();
