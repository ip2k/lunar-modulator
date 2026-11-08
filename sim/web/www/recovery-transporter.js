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
    const verb = line.split(/\s+/)[0];
    if (!ALLOWED_COMMANDS.includes(verb)) fail('command-refused', `command "${verb}" is not allowed from this page`);
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
    this.backup = null; // { data, sha256 }
    this.wroteStarted = false;
  }
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
    let reply = '';
    try { reply = await this.link.request('rekey', 3000); } catch (e) { if (!['port-closed', 'timeout'].includes(e.code)) throw e; }
    this.log(`rekey: ${reply || 'port closed'}`);
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
    const st = await this.status();
    if (st.v15) fail('v15-attached', GUIDE.v15);
    if (st.loader) return 'already-loaded';
    for (let off = 0; off < bytes.length; off += SECTOR) {
      const chunk = bytes.subarray(off, off + SECTOR);
      const r = await this.link.request(`ldr ${off} ${chunk.length} ${hex8(crc32(chunk))}`, 5000, chunk);
      if (r !== 'OK') fail('loader-upload', `loader upload failed at ${off}: ${r}`);
    }
    return 'loaded';
  }

  async identify() {
    await this.requireUboot();
    const r = await this.link.request('info', 30000);
    if (r !== EXPECTED_INFO) fail('not-fm1', `Not an FM-1 (expected "${EXPECTED_INFO}", got "${r}"). Stop.`);
    return r;
  }

  async readFlash(addr = 0, len = FLASH_SIZE, stage = 'read') {
    await this.requireUboot();
    return this.link.readReply(`read 0x${addr.toString(16)} ${len}`, len, (n) => this.progress(stage, n, len));
  }

  /** Two full reads, byte-compared and hashed; both saved to the user's disk. */
  async backupFlash() {
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
   */
  async plan(image) {
    if (!this.backup) fail('no-backup', 'Take the backup (two matching dumps) in this session first.');
    if (image.data.length < WRITE_END) fail('image-too-small', 'image shorter than the write window');
    const now = await this.readFlash(0, FLASH_SIZE, 'pre-write read');
    return this.#planFrom(image, now);
  }
  #planFrom(image, now) {
    const ref = this.backup.data;
    const bad = [];
    for (let a = 0; a < WRITE_END; a += SECTOR) if (!bytesEqual(now.subarray(a, a + SECTOR), ref.subarray(a, a + SECTOR))) bad.push(a);
    if (bad.length) fail('flash-differs-from-backup', `Flash differs from the backup in sectors ${bad.map((a) => `0x${a.toString(16)}`).join(' ')}; not writing. Take a fresh backup.`);
    const sectors = [], protectedDiff = [];
    for (let a = 0; a < WRITE_END; a += SECTOR) {
      if (!bytesEqual(image.data.subarray(a, a + SECTOR), now.subarray(a, a + SECTOR))) (a < WRITE_MIN ? protectedDiff : sectors).push(a);
    }
    if (protectedDiff.length) fail('protected-sector', `The image changes the protected boot area (${protectedDiff.map((a) => `0x${a.toString(16)}`).join(' ')}). The boot area 0x0-0x4000 is never written; image refused.`);
    const beyond = [];
    for (let a = WRITE_END; a + SECTOR <= Math.min(image.data.length, FLASH_SIZE); a += SECTOR) {
      if (!bytesEqual(image.data.subarray(a, a + SECTOR), now.subarray(a, a + SECTOR))) beyond.push(a);
    }
    return { sectors, beyondWindow: beyond, now, image };
  }

  /**
   * Write. Requires a plan from plan() and the user's explicit confirmation.
   * Re-reads the flash first (the unit may have dropped out meanwhile).
   */
  async write(plan) {
    if (!plan.sectors.length) return { written: 0, note: 'already holds this image' };
    const ok = await this.confirm(`Write ${plan.sectors.length} sector(s) of 0x4000-0x92FFF to the FM-1? Keep it on and the wires still until the final read finishes.`);
    if (!ok) fail('not-confirmed', 'Write not confirmed; nothing was written.');
    const again = await this.readFlash(0, FLASH_SIZE, 'recheck read');
    if (!bytesEqual(again, plan.now)) fail('flash-changed', 'Flash changed since the dry run; nothing was written. Run the dry run again.');
    this.wroteStarted = true;
    for (const [i, a] of plan.sectors.entries()) {
      const sec = plan.image.data.subarray(a, a + SECTOR);
      let r;
      try { r = await this.link.request(`wsec 0x${a.toString(16)} ${hex8(crc32(sec))}`, 20000, sec); } catch (e) { r = `(${e.code})`; }
      this.progress('write', i + 1, plan.sectors.length);
      if (r !== 'OK') fail('write-failed', `Sector 0x${a.toString(16)} failed: ${r}. DO NOT power-cycle the FM-1. Keep this output, take a fresh dump and write against that.`);
    }
    const expect = new Uint8Array(FLASH_SIZE);
    expect.set(plan.image.data.subarray(0, WRITE_END));
    expect.set(plan.now.subarray(WRITE_END), WRITE_END);
    const fin = await this.readFlash(0, FLASH_SIZE, 'final read');
    if (!bytesEqual(fin, expect)) fail('verify-failed', 'Final read does not equal the expected image. DO NOT power-cycle; write again against a fresh dump.');
    return { written: plan.sectors.length, finalSha256: await sha256Hex(fin) };
  }
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
