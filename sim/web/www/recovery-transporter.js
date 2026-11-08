// SPDX-License-Identifier: MIT
// Browser driver for the FM-1 Transporter's data-port protocol (docs/17).
// Protocol and write policy follow kurogedelic's FM-1-transporter (MIT) at
// a7fb5e8: src/transporter_proto.c, tools/fm1t.py and web/index.html.
// No DOM and no navigator.serial here: a transport is injected, so tests
// replay the protocol against a fake port.
//
// Owner decision D2: this module NEVER emits `uboot` (the soft key), and the
// command allowlist below refuses it at the lowest layer. The only way into
// UBOOT is `rekey`, then the user switching a keyed-off FM-1 on.
import { inspectFwscEnvelope } from './native-fwsc-inspection.js';

export const FLASH_SIZE = 0x100000;
export const WRITE_MIN = 0x4000;
export const WRITE_END = 0x93000;
export const SECTOR = 0x1000;
export const LOADER_SIZE = 24064;
export const LOADER_SHA256 = 'd41da6126760c9d66660bcc0cac8d27d221806c5e369a8036921efe68dca5376';
export const STOCK_V15_SHA256 = 'db1642b2b6fa5c2cccb11ffd13878068bb28601678d3644049f99dc40e7edb8a';
export const EXPECTED_INFO = 'OK key=980F type=3 id=856014';
// Only these verbs may leave this page. `uboot` (soft key), `runapp`, `jump`,
// `memw`, `memr` are deliberately absent.
export const ALLOWED_COMMANDS = Object.freeze(['ping', 'status', 'rekey', 'info', 'read', 'ldr', 'wsec']);
// Every request line must match one of these whole-line templates (no `m`
// flag, so an embedded newline or a second command fails); checking the first
// token alone would let `ping\nuboot` or `read 0x0 16 uboot` through.
export const REQUEST_TEMPLATES = Object.freeze({
  ping: /^ping$/,
  status: /^status$/,
  rekey: /^rekey$/,
  info: /^info$/,
  read: /^read 0x[0-9a-f]{1,6} [0-9]{1,7}$/,
  ldr: /^ldr [0-9]{1,5} [0-9]{1,4} [0-9A-F]{8}$/,
  wsec: /^wsec 0x[0-9a-f]{1,6} [0-9A-F]{8}$/,
});
/** Throws command-refused unless `line` (and its payload) fits a template. */
export function checkRequest(line, payload = null) {
  const refuse = (why) => fail('command-refused', `request "${String(line).slice(0, 40)}" is not allowed from this page (${why})`);
  if (typeof line !== 'string') refuse('not text');
  const verb = line.split(' ')[0];
  if (!ALLOWED_COMMANDS.includes(verb) || !Object.hasOwn(REQUEST_TEMPLATES, verb)) refuse('verb not allowlisted');
  if (!REQUEST_TEMPLATES[verb].test(line)) refuse('does not match the fixed template');
  const a = line.split(' ');
  const plen = payload ? payload.length : 0;
  if (verb === 'read') {
    const addr = Number(a[1]), len = Number(a[2]);
    if (len < 1 || addr + len > FLASH_SIZE) refuse('outside the flash');
  }
  if (verb === 'ldr') {
    const off = Number(a[1]), len = Number(a[2]);
    if (len < 1 || len > SECTOR || off % SECTOR || off + len > LOADER_SIZE || plen !== len) refuse('loader chunk out of range');
  }
  if (verb === 'wsec') {
    const addr = Number(a[1]);
    if (addr < WRITE_MIN || addr >= WRITE_END || addr % SECTOR || plen !== SECTOR) refuse('sector outside 0x4000-0x92FFF');
  }
  if (verb !== 'ldr' && verb !== 'wsec' && plen) refuse('unexpected payload');
}

export class RecoveryError extends Error {
  constructor(code, message) { super(message); this.name = 'RecoveryError'; this.code = code; }
}
const fail = (code, message) => { throw new RecoveryError(code, message); };

const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let i = 0; i < 256; i += 1) { let c = i; for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[i] = c >>> 0; }
  return t;
})();
export function crc32(data) {
  let c = 0xffffffff;
  for (let i = 0; i < data.length; i += 1) c = CRC_TABLE[(c ^ data[i]) & 255] ^ (c >>> 8);
  return (~c) >>> 0;
}
export const hex8 = (n) => n.toString(16).toUpperCase().padStart(8, '0');
export async function sha256Hex(data) {
  const digest = await globalThis.crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('');
}
export const bytesEqual = (a, b) => {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) if (a[i] !== b[i]) return false;
  return true;
};

/** Parse `OK key=value key=value ...`; tolerates extra fields. */
export function parseStatus(line) {
  if (!line.startsWith('OK')) fail('status-error', `status: ${line}`);
  const out = {};
  for (const kv of line.split(/\s+/).slice(1)) { const [k, v] = kv.split('='); if (k) out[k] = v; }
  return { uboot: out.uboot === '1', v15: out.v15 === '1', loader: out.loader === '1', loaderRunning: out.loader_running === '1', raw: line };
}

/**
 * Request/response link. transport = { write(Uint8Array): Promise, onData(cb),
 * onClose(cb), close(): Promise }. One request at a time (the firmware drops
 * extras).
 */
export class TransporterLink {
  constructor(transport, { timeoutMs = 30000 } = {}) {
    this.transport = transport;
    this.timeoutMs = timeoutMs;
    this.buf = new Uint8Array(0);
    this.closed = false;
    this.waiter = null;
    this.busy = false;
    this.sent = [];
    transport.onData((chunk) => { this.#append(chunk); this.#wake(); });
    transport.onClose(() => { this.closed = true; this.#wake(); });
  }
  #append(chunk) { const m = new Uint8Array(this.buf.length + chunk.length); m.set(this.buf); m.set(chunk, this.buf.length); this.buf = m; }
  #wake() { const w = this.waiter; this.waiter = null; if (w) w(); }
  async #until(predicate, ms, what) {
    const end = Date.now() + Math.min(ms, this.timeoutMs);
    for (;;) {
      const v = predicate();
      if (v !== undefined) return v;
      if (this.closed) fail('port-closed', `serial port closed while waiting for ${what}`);
      const left = end - Date.now();
      if (left <= 0) fail('timeout', `timeout waiting for ${what}`);
      await new Promise((resolve) => { const t = setTimeout(resolve, left); this.waiter = () => { clearTimeout(t); resolve(); }; });
    }
  }
  takeLine(ms = this.timeoutMs) {
    return this.#until(() => {
      const i = this.buf.indexOf(10);
      if (i < 0) return undefined;
      const line = new TextDecoder().decode(this.buf.subarray(0, i)).trim();
      this.buf = this.buf.slice(i + 1);
      return line;
    }, ms, 'a reply line');
  }
  takeBytes(n, ms = this.timeoutMs) {
    return this.#until(() => {
      if (this.buf.length < n) return undefined;
      const out = this.buf.slice(0, n);
      this.buf = this.buf.slice(n);
      return out;
    }, ms, `${n} payload bytes`);
  }
  async #send(line, payload) {
    checkRequest(line, payload);
    if (this.closed) fail('port-closed', 'the serial port is closed');
    if (this.busy) fail('busy', 'a request is already in flight');
    this.busy = true;
    this.buf = new Uint8Array(0);
    this.sent.push(line);
    const head = new TextEncoder().encode(`${line}\n`);
    const msg = new Uint8Array(head.length + (payload ? payload.length : 0));
    msg.set(head);
    if (payload) msg.set(payload, head.length);
    try { await this.transport.write(msg); } catch (e) { this.busy = false; fail('port-closed', `write failed: ${e.message}`); }
  }
  /** One text reply line. */
  async request(line, ms = this.timeoutMs, payload = null) {
    await this.#send(line, payload);
    try { return await this.takeLine(ms); } finally { this.busy = false; }
  }
  /** `read` reply: DATA n, n raw bytes, END crc. */
  async readReply(line, length, onProgress) {
    await this.#send(line);
    try {
      const head = await this.takeLine();
      if (!head.startsWith('DATA ')) fail('read-error', `read refused: ${head}`);
      if (Number(head.slice(5)) !== length) fail('read-error', `read length ${head} != ${length}`);
      const out = new Uint8Array(length);
      for (let o = 0; o < length;) {
        const n = Math.min(65536, length - o);
        out.set(await this.takeBytes(n, 10000), o);
        o += n;
        if (onProgress) onProgress(o);
      }
      const end = await this.takeLine(10000);
      if (end === 'END FAIL') fail('read-failed', 'the transporter reported a failed flash read (END FAIL)');
      if (end !== `END ${hex8(crc32(out))}`) fail('read-crc', `transfer check failed (${end}, local ${hex8(crc32(out))})`);
      return out;
    } finally { this.busy = false; }
  }
  async close() { try { await this.transport.close(); } catch { /* already gone */ } this.closed = true; }
}

const GUIDE = Object.freeze({
  notOff: 'Confirm that the FM-1 was switched OFF (check the switch itself; a black screen proves nothing) before the transporter keys it.',
  v15: 'A running stock V15 is attached to the transporter. This page will not put it into boot mode (the soft key is off limits, docs/17 section 8). Disconnect the Pico from the FM-1, switch the FM-1 off, then press "Start key mode".',
  noUboot: 'The FM-1 is not in boot mode. Switch it OFF, press "Start key mode", wait for the transporter to come back (reconnect its data port), and only then switch the FM-1 ON.',
});

export class RecoverySession {
  /**
   * hooks: { save(name, bytes), progress(stage, done, total), log(msg), confirm(msg) -> Promise<bool> }
   */
  constructor(link, hooks = {}) {
    this.link = link;
    this.save = hooks.save || (async () => {});
    this.progress = hooks.progress || (() => {});
    this.log = hooks.log || (() => {});
    this.confirm = hooks.confirm || (async () => false);
    this.loaderSha256 = hooks.loaderSha256 || LOADER_SHA256; // tests only
    this.confirmedOff = false;
    // Provenance: what THIS session has done on THIS link. A page that
    // reconnects gets a new session with none of it, so a plan or a backup
    // from an earlier connection can never drive a write.
    this.identified = false;  // identify() returned the FM-1's chip key and flash id
    this.loaderReady = false; // uploadLoader() checked the loader file and the transporter holds a loader
    this.backup = null;       // { data, sha256 } from two matching dumps
    this.wroteStarted = false;
  }
  #token = Symbol('session'); // stamps plans made by this session
  #plans = new WeakMap();     // plan -> the backup it was computed against
  #forget() { this.identified = false; this.loaderReady = false; this.backup = null; this.#plans = new WeakMap(); }
  setConfirmedOff(v) { this.confirmedOff = Boolean(v); }

  async connect() {
    let reply;
    try { reply = await this.link.request('ping', 1500); } catch (e) {
      if (e.code === 'timeout') fail('wrong-port', 'No PONG. This is probably the console port; pick the transporter\'s other (second) serial port.');
      throw e;
    }
    if (reply !== 'PONG') fail('wrong-port', `Unexpected reply to ping: "${reply}"`);
    return true;
  }
  async status() { return parseStatus(await this.link.request('status', 5000)); }

  /** Reboot the transporter into key mode. Needs the user's "FM-1 is off" confirmation. */
  async rekey() {
    if (!this.confirmedOff) fail('not-confirmed-off', GUIDE.notOff);
    const st = await this.status();
    if (st.v15) fail('v15-attached', GUIDE.v15);
    this.#forget();
    let reply = '';
    try { reply = await this.link.request('rekey', 3000); } catch (e) { if (!['port-closed', 'timeout'].includes(e.code)) throw e; }
    this.log(`rekey: ${reply || 'port closed'}`);
    await this.link.close(); // the transporter reboots; release the port before anyone reconnects
    return 'The transporter is rebooting and will close this port. Reconnect its data port within about 10 s, then switch the FM-1 ON only after the console shows the key running.';
  }

  /** Gate for every command that touches the loader or flash. */
  async requireUboot() {
    const st = await this.status();
    if (st.v15) fail('v15-attached', GUIDE.v15);
    if (!this.confirmedOff) fail('not-confirmed-off', GUIDE.notOff);
    if (!st.uboot) fail('no-uboot', GUIDE.noUboot);
    return st;
  }
  async waitUboot(ms = 60000, intervalMs = 500) {
    const end = Date.now() + ms;
    for (;;) {
      try { await this.requireUboot(); return true; } catch (e) {
        if (e.code !== 'no-uboot' || Date.now() > end) throw e;
      }
      await new Promise((r) => setTimeout(r, intervalMs));
    }
  }

  async uploadLoader(bytes) {
    if (bytes.length !== LOADER_SIZE) fail('loader-size', `wl82loader.bin must be ${LOADER_SIZE} bytes, got ${bytes.length}`);
    const sha = await sha256Hex(bytes);
    if (sha !== this.loaderSha256) fail('loader-sha', `wl82loader.bin SHA-256 ${sha} does not match the expected ${this.loaderSha256}`);
    const st = await this.requireUboot(); // V15 refused, FM-1 confirmed off, boot mode
    // A loader the transporter already holds (this page reloaded without a
    // rekey) is accepted: the file was still checked above in this session.
    if (st.loader) { this.loaderReady = true; return 'already-loaded'; }
    for (let off = 0; off < bytes.length; off += SECTOR) {
      const chunk = bytes.subarray(off, off + SECTOR);
      const r = await this.link.request(`ldr ${off} ${chunk.length} ${hex8(crc32(chunk))}`, 5000, chunk);
      if (r !== 'OK') fail('loader-upload', `loader upload failed at ${off}: ${r}`);
    }
    this.loaderReady = true;
    return 'loaded';
  }

  async identify() {
    await this.requireUboot();
    const r = await this.link.request('info', 30000);
    if (r !== EXPECTED_INFO) { this.identified = false; fail('not-fm1', `Not an FM-1 (expected "${EXPECTED_INFO}", got "${r}"). Stop.`); }
    this.identified = true;
    return r;
  }

  async readFlash(addr = 0, len = FLASH_SIZE, stage = 'read') {
    await this.requireUboot();
    return this.link.readReply(`read 0x${addr.toString(16)} ${len}`, len, (n) => this.progress(stage, n, len));
  }

  /** Two full reads, byte-compared and hashed; both saved to the user's disk. */
  async backupFlash() {
    this.backup = null; // a failed backup leaves none, and invalidates older plans
    await this.identify();
    const a = await this.readFlash(0, FLASH_SIZE, 'dump A');
    const b = await this.readFlash(0, FLASH_SIZE, 'dump B');
    const [ha, hb] = [await sha256Hex(a), await sha256Hex(b)];
    if (ha !== hb || !bytesEqual(a, b)) fail('dump-mismatch', `The two dumps differ (${ha} vs ${hb}). Check the wiring and retry; nothing was written.`);
    await this.save('fm1-dumpA.bin', a);
    await this.save('fm1-dumpB.bin', b);
    this.backup = { data: a, sha256: ha };
    return { sha256: ha };
  }

  /** Turn a user-supplied file into an image for [0, WRITE_END). */
  static async parseImage(bytes, name = '') {
    if (!(bytes instanceof Uint8Array)) fail('image-type', 'image must be bytes');
    if (bytes.length === FLASH_SIZE) {
      return { kind: 'backup', name, data: bytes.slice(0, FLASH_SIZE), sha256: await sha256Hex(bytes) };
    }
    if (bytes.length < WRITE_END) fail('image-too-small', `Image is ${bytes.length} bytes: need a 1 MiB backup or the stock V15 .fwsc.`);
    const sha = await sha256Hex(bytes);
    if (sha !== STOCK_V15_SHA256) fail('fwsc-not-stock', `Package SHA-256 ${sha} is not stock V15 (${STOCK_V15_SHA256}); only stock V15 packages are accepted.`);
    let flash;
    try { flash = extractFwscFlashImage(bytes); } catch (e) { fail('fwsc-malformed', `Malformed package: ${e.message}`); }
    return { kind: 'fwsc', name, data: flash, sha256: sha };
  }

  /**
   * Read-only dry run: fresh full read must equal the in-session backup over
   * [0, WRITE_END); list differing sectors; refuse any below WRITE_MIN.
   * Returns a frozen summary for display. What write() uses (the sectors, a
   * private copy of the image and of the flash read) stays inside the session,
   * keyed by that summary, so neither a caller's buffers nor a forged or
   * earlier connection's plan can change what is written.
   */
  async plan(image) {
    if (!this.backup) fail('no-backup', 'Take the backup (two matching dumps) in this session first.');
    if (!(image?.data instanceof Uint8Array) || image.data.length < WRITE_END) fail('image-too-small', 'image shorter than the write window');
    const backup = this.backup;
    const data = image.data.slice(0, Math.min(image.data.length, FLASH_SIZE));
    const now = await this.readFlash(0, FLASH_SIZE, 'pre-write read');
    if (this.backup !== backup) fail('plan-stale', 'The backup changed during the dry run; run it again.');
    const { sectors, beyondWindow } = this.#planFrom(data, now);
    const plan = Object.freeze({
      sectors: Object.freeze(sectors.slice()), beyondWindow: Object.freeze(beyondWindow),
      imageSha256: image.sha256, backupSha256: backup.sha256, token: this.#token,
    });
    this.#plans.set(plan, Object.freeze({ backup, sectors: Object.freeze(sectors), data, now }));
    return plan;
  }
  #planFrom(data, now) {
    const ref = this.backup.data;
    const bad = [];
    for (let a = 0; a < WRITE_END; a += SECTOR) if (!bytesEqual(now.subarray(a, a + SECTOR), ref.subarray(a, a + SECTOR))) bad.push(a);
    if (bad.length) fail('flash-differs-from-backup', `Flash differs from the backup in sectors ${bad.map((a) => `0x${a.toString(16)}`).join(' ')}; not writing. Take a fresh backup.`);
    const sectors = [], protectedDiff = [];
    for (let a = 0; a < WRITE_END; a += SECTOR) {
      if (!bytesEqual(data.subarray(a, a + SECTOR), now.subarray(a, a + SECTOR))) (a < WRITE_MIN ? protectedDiff : sectors).push(a);
    }
    if (protectedDiff.length) fail('protected-sector', `The image changes the protected boot area (${protectedDiff.map((a) => `0x${a.toString(16)}`).join(' ')}). The boot area 0x0-0x4000 is never written; image refused. A unit whose boot area was replaced (Felucca and SLOOP install a different uboot.boot) cannot be restored to stock this way, by design.`);
    const beyond = [];
    for (let a = WRITE_END; a + SECTOR <= data.length; a += SECTOR) {
      if (!bytesEqual(data.subarray(a, a + SECTOR), now.subarray(a, a + SECTOR))) beyond.push(a);
    }
    return { sectors, beyondWindow: beyond };
  }

  /** Refuses unless `plan` came from this session's plan() against its current backup; returns the session's record of it. */
  #checkPlan(plan) {
    if (this.link.closed) fail('port-closed', 'The serial port is closed; reconnect, identify and back up again.');
    if (!this.identified) fail('not-identified', 'This connection has not identified the FM-1. Wait for boot mode and identify first.');
    if (!this.loaderReady) fail('no-loader', 'This connection has not uploaded the loader. Wait for boot mode and identify first.');
    if (!this.backup) fail('no-backup', 'Take the backup (two matching dumps) in this connection first.');
    const rec = plan && typeof plan === 'object' ? this.#plans.get(plan) : undefined;
    if (!rec || plan.token !== this.#token) fail('plan-foreign', 'This dry run was not made on the current connection. Run the dry run again.');
    if (rec.backup !== this.backup || plan.backupSha256 !== this.backup.sha256) fail('plan-stale', 'The backup changed after this dry run. Run the dry run again.');
    assertWritableSectors(rec.sectors);
    if (!bytesEqual(rec.data.subarray(0, WRITE_MIN), rec.now.subarray(0, WRITE_MIN))) fail('protected-sector', 'The image changes the protected boot area 0x0-0x4000; nothing was written.');
    return rec;
  }

  /**
   * Write. Requires a plan from this session's plan() against its current
   * backup, after identify() and uploadLoader() on this connection, and the
   * user's explicit confirmation. Re-reads the flash first (the unit may have
   * dropped out meanwhile).
   */
  async write(plan) {
    const rec = this.#checkPlan(plan);
    this.#plans.delete(plan); // one write per dry run
    const { sectors, data, now } = rec;
    if (!sectors.length) return { written: 0, note: 'already holds this image' };
    const ok = await this.confirm(`Write ${sectors.length} sector(s) of 0x4000-0x92FFF to the FM-1? Keep it on and the wires still until the final read finishes.`);
    if (!ok) fail('not-confirmed', 'Write not confirmed; nothing was written.');
    const again = await this.readFlash(0, FLASH_SIZE, 'recheck read');
    if (!bytesEqual(again, now)) fail('flash-changed', 'Flash changed since the dry run; nothing was written. Run the dry run again.');
    this.wroteStarted = true;
    for (const [i, a] of sectors.entries()) {
      assertWritableSectors([a]);
      const sec = data.subarray(a, a + SECTOR);
      let r;
      try { r = await this.link.request(`wsec 0x${a.toString(16)} ${hex8(crc32(sec))}`, 20000, sec); } catch (e) { r = `(${e.code})`; }
      this.progress('write', i + 1, sectors.length);
      if (r !== 'OK') fail('write-failed', `Sector 0x${a.toString(16)} failed: ${r}. DO NOT power-cycle the FM-1. Keep this output, take a fresh dump and write against that.`);
    }
    const expect = new Uint8Array(FLASH_SIZE);
    expect.set(data.subarray(0, WRITE_END));
    expect.set(now.subarray(WRITE_END), WRITE_END);
    const fin = await this.readFlash(0, FLASH_SIZE, 'final read');
    if (!bytesEqual(fin, expect)) fail('verify-failed', 'Final read does not equal the expected image. DO NOT power-cycle; write again against a fresh dump.');
    return { written: sectors.length, finalSha256: await sha256Hex(fin) };
  }
}

/** Every sector a write may touch: whole 4 KiB sectors inside [WRITE_MIN, WRITE_END). */
export function assertWritableSectors(sectors) {
  if (!Array.isArray(sectors)) fail('sector-out-of-window', 'sector list is not a list; nothing was written.');
  for (const a of sectors) {
    if (!Number.isInteger(a) || a % SECTOR || a < WRITE_MIN || a >= WRITE_END) fail('sector-out-of-window', `Sector ${a} lies outside 0x4000-0x92FFF; nothing was written.`);
  }
}

/**
 * What a chosen image is, for the page. The application is SFC-encrypted in
 * flash (docs/02), so a raw dump carries no readable FM-1_0xx string: its
 * "identity" here is its hashes, and how it compares with this connection's
 * backup. warn is true when it differs from that backup (or there is none).
 */
export async function describeImage(image, backup = null) {
  const sec = (a, b) => sha256Hex(image.data.subarray(a, b));
  const lines = [
    `${image.kind === 'fwsc' ? 'Stock V15 package' : '1 MiB flash image'} ${image.name || ''}`.trim(),
    `File SHA-256 ${image.sha256}`,
    `0x0-0x92FFF SHA-256 ${await sec(0, WRITE_END)}`,
    `Boot area 0x0-0x3FFF SHA-256 ${await sec(0, WRITE_MIN)}`,
  ];
  if (image.kind === 'backup') lines.push('A raw dump has no readable FM-1_0xx identity (the application is encrypted in flash); compare these hashes with the files you saved.');
  if (!backup) {
    lines.push('No backup in this connection yet: take it before the dry run; the image is compared with it then.');
    return { lines, warn: true, sameAsBackup: false, bootAreaDiffers: null, differingSectors: null };
  }
  let differing = 0;
  for (let a = 0; a < WRITE_END; a += SECTOR) if (!bytesEqual(image.data.subarray(a, a + SECTOR), backup.data.subarray(a, a + SECTOR))) differing += 1;
  const bootAreaDiffers = !bytesEqual(image.data.subarray(0, WRITE_MIN), backup.data.subarray(0, WRITE_MIN));
  const sameAsBackup = image.data.length === backup.data.length && bytesEqual(image.data, backup.data);
  if (sameAsBackup) lines.push(`Identical to this connection's backup (SHA-256 ${backup.sha256}).`);
  else {
    lines.push(`WARNING: differs from this connection's backup (SHA-256 ${backup.sha256}) in ${differing} sector(s) of 0x0-0x92FFF${differing ? '' : ' (only above 0x93000, which is never written)'}.`);
    if (bootAreaDiffers) lines.push('WARNING: its boot area 0x0-0x3FFF differs from this FM-1\'s; the dry run will refuse it (that area is never written).');
    else if (image.kind === 'backup') lines.push('Check that this is a backup of THIS unit before writing it.');
  }
  return { lines, warn: !sameAsBackup, sameAsBackup, bootAreaDiffers, differingSectors: differing };
}

/** Type-0 `flash.bin` entry of a package, in flash coordinates from 0. */
export function extractFwscFlashImage(raw) {
  const info = inspectFwscEnvelope(raw); // validates structure and CRCs, throws on anything odd
  const entry = info.entries.find((e) => e.name === 'flash.bin' && e.type === 0);
  if (!entry) throw new Error('no type-0 flash entry');
  const logical = new Uint8Array(raw.length - 20);
  for (let i = 0; i < 20; i += 1) logical.set(raw.subarray(i * 48, i * 48 + 47), i * 47);
  logical.set(raw.subarray(960), 940);
  return logical.slice(entry.offset, entry.offset + entry.bytes);
}

export const AFTER_WRITE_GUIDE = [
  'Switch the FM-1 off.',
  'Disconnect the Pico from the FM-1 (a transporter that reboots with the FM-1 off will key it back into boot mode).',
  'Switch the FM-1 on; stock V15 should boot.',
  'Plug the FM-1 into the computer with a data cable and read its identity (tools/fm1_identify.py): expect FM-1_015.',
];
