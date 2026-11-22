'use strict';
/*
 * Offline encrypted backup / restore prototype for the supervised lead pilot.
 * Requires a local key FILE, uses AES-256-GCM with scrypt and random salt/nonce.
 * No network, cron or production deployment. Operate on a stopped staging app.
 */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const os = require('node:os');
const { openStore, insideGitRepo } = require('../lib/store.cjs');

const FILES = ['events.jsonl', 'mailbox-state.json', 'password.hash'];
const MAX_FILE = 16 * 1024 * 1024;
const MAX_ARCHIVE = 64 * 1024 * 1024;
const MAGIC = 'CORE8-LEAD-BACKUP-v1';
const SCRYPT = { N: 1 << 15, r: 8, p: 1, maxmem: 64 * 1024 * 1024 };

function regularFile(file) {
  const st = fs.lstatSync(file);
  if (!st.isFile() || st.isSymbolicLink() || st.size > MAX_FILE) {
    throw new Error('Backup input is not a safe regular file or is oversized');
  }
  return st;
}

function keyFromFile(file) {
  if (insideGitRepo(file)) throw new Error('Backup key cannot live inside Git');
  const st = regularFile(file);
  if (process.platform !== 'win32' && (st.mode & 0o077) !== 0) {
    throw new Error('Backup key file must be owner-only (chmod 600)');
  }
  const key = fs.readFileSync(file);
  if (key.length < 32 || key.length > 4096) throw new Error('Backup key material length invalid');
  return key;
}

function validatedFiles(dir) {
  if (insideGitRepo(dir)) throw new Error('Backup source or destination cannot be inside Git');
  const st = fs.lstatSync(dir);
  if (!st.isDirectory() || st.isSymbolicLink()) throw new Error('Data path must be a real directory');
  const files = {};
  for (const name of FILES) {
    const p = path.join(dir, name);
    if (!fs.existsSync(p)) continue;
    regularFile(p);
    files[name] = fs.readFileSync(p).toString('base64');
  }
  if (!files['events.jsonl']) throw new Error('Missing event log: nothing to back up');
  // Fail if audit chain is broken, before producing an encrypted artifact.
  openStore(dir);
  return files;
}

function createBackup(dataDir, outputFile, keyFile) {
  const src = path.resolve(dataDir), dest = path.resolve(outputFile);
  if (insideGitRepo(dest)) throw new Error('Backup archive cannot be stored inside Git');
  if (fs.existsSync(dest)) throw new Error('Refusing to overwrite an existing backup');
  const files = validatedFiles(src);
  const salt = crypto.randomBytes(32), iv = crypto.randomBytes(12);
  const secret = keyFromFile(keyFile);
  const k = crypto.scryptSync(secret, salt, 32, SCRYPT);
  const cipher = crypto.createCipheriv('aes-256-gcm', k, iv);
  cipher.setAAD(Buffer.from(MAGIC));
  const plain = Buffer.from(JSON.stringify({ format: MAGIC, files }), 'utf8');
  if (plain.length > MAX_ARCHIVE) throw new Error('Backup payload too large');
  const ciphertext = Buffer.concat([cipher.update(plain), cipher.final()]);
  const archive = Buffer.from(JSON.stringify({
    format: MAGIC, kdf: 'scrypt-N32768-r8-p1', cipher: 'aes-256-gcm',
    salt: salt.toString('base64'), iv: iv.toString('base64'),
    tag: cipher.getAuthTag().toString('base64'), data: ciphertext.toString('base64')
  }), 'utf8');
  fs.writeFileSync(dest, archive, { flag: 'wx', mode: 0o600 });
  return { status: 'encrypted', fileCount: Object.keys(files).length };
}

function restoreBackup(archiveFile, targetDir, keyFile) {
  const target = path.resolve(targetDir);
  if (insideGitRepo(target)) throw new Error('Restore destination cannot be inside Git');
  if (fs.existsSync(target)) throw new Error('Restore destination already exists; refuse overwrite');
  if (insideGitRepo(archiveFile)) throw new Error('Backup archive cannot live inside Git');
  regularFile(archiveFile); // Also bounds the size read in memory.
  const record = JSON.parse(fs.readFileSync(archiveFile, 'utf8'));
  if (record.format !== MAGIC || record.kdf !== 'scrypt-N32768-r8-p1' ||
      record.cipher !== 'aes-256-gcm') throw new Error('Unsupported backup archive');
  const b64 = (s, len) => {
    if (typeof s !== 'string' || !/^[A-Za-z0-9+/]+={0,2}$/.test(s)) throw new Error('Malformed backup encoding');
    const b = Buffer.from(s, 'base64');
    if (len && b.length !== len) throw new Error('Malformed backup parameter');
    return b;
  };
  const key = crypto.scryptSync(keyFromFile(keyFile), b64(record.salt, 32), 32, SCRYPT);
  const decipher = crypto.createDecipheriv('aes-256-gcm', key, b64(record.iv, 12));
  decipher.setAAD(Buffer.from(MAGIC));
  decipher.setAuthTag(b64(record.tag, 16));
  // Invalid tag, ciphertext or password fails before creating any destination.
  const plaintext = Buffer.concat([decipher.update(b64(record.data)), decipher.final()]);
  if (plaintext.length > MAX_ARCHIVE) throw new Error('Backup payload too large');
  const data = JSON.parse(plaintext.toString('utf8'));
  if (data.format !== MAGIC || !data.files || !data.files['events.jsonl'] ||
      Object.keys(data.files).some(name => !FILES.includes(name))) throw new Error('Invalid backup manifest');

  const parent = path.dirname(target);
  if (!fs.existsSync(parent)) throw new Error('Restore parent directory does not exist');
  const scratch = fs.mkdtempSync(path.join(parent, '.core8-restore-'));
  try {
    fs.chmodSync(scratch, 0o700);
    for (const [name, body] of Object.entries(data.files)) {
      if (typeof body !== 'string' || !/^[A-Za-z0-9+/]*={0,2}$/.test(body)) throw new Error('Invalid backup file encoding');
      const buffer = Buffer.from(body, 'base64');
      if (buffer.length > MAX_FILE) throw new Error('Restore file oversized');
      fs.writeFileSync(path.join(scratch, name), buffer, { flag: 'wx', mode: 0o600 });
    }
    openStore(scratch); // Refuse tampered or structurally corrupted event chains.
    if (fs.existsSync(target)) throw new Error('Restore destination appeared during operation');
    fs.renameSync(scratch, target);
  } finally {
    if (fs.existsSync(scratch)) fs.rmSync(scratch, { recursive: true, force: true });
  }
  return { status: 'restored', directory: target };
}

module.exports = { createBackup, restoreBackup, MAGIC };
if (require.main === module) {
  const [operation, source, destination, keyFile] = process.argv.slice(2);
  if (!['backup', 'restore'].includes(operation) || !source || !destination || !keyFile) {
    console.error('Usage: node tools/secure-backup.cjs backup|restore <source> <destination> <owner-only-key-file>');
    process.exitCode = 2;
  } else {
    try {
      const result = operation === 'backup'
        ? createBackup(source, destination, keyFile)
        : restoreBackup(source, destination, keyFile);
      console.log(result.status.toUpperCase() + ' (no personal data printed)');
    } catch (e) {
      console.error('Backup operation refused: ' + e.message);
      process.exitCode = 1;
    }
  }
}
