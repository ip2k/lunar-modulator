// SPDX-License-Identifier: MIT
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { FakeTransporter, LOADER } from './recovery-fake-port.mjs';
import {
  TransporterLink, RecoverySession, RecoveryError, ALLOWED_COMMANDS, FLASH_SIZE, WRITE_MIN, WRITE_END, SECTOR,
  LOADER_SHA256, STOCK_V15_SHA256, sha256Hex, crc32, hex8, parseStatus, extractFwscFlashImage,
  REQUEST_TEMPLATES, checkRequest, describeImage, assertWritableSectors,
} from '../www/recovery-transporter.js';
import { inspectFwscEnvelope } from '../www/native-fwsc-inspection.js';

const LOADER_SHA = await sha256Hex(LOADER);

function rig({ confirmedOff = true, confirm = true, timeoutMs = 400, ...opts } = {}) {
  const fake = new FakeTransporter(opts);
  const link = new TransporterLink(fake, { timeoutMs });
  const saved = [], progress = [];
  const session = new RecoverySession(link, {
    save: async (n, b) => { saved.push([n, b]); }, progress: (s, d, t) => progress.push([s, d, t]),
    confirm: async () => confirm, loaderSha256: LOADER_SHA,
  });
  session.setConfirmedOff(confirmedOff);
  return { fake, link, session, saved, progress };
}
async function code(promise) {
  try { await promise; } catch (e) { assert.ok(e instanceof RecoveryError, `unexpected ${e && e.stack}`); return e.code; }
  return 'no-error';
}
async function ready(opts) {
  const r = rig(opts);
  await r.session.connect();
  await r.session.uploadLoader(LOADER);
  return r;
}
/** A flash and an image differing from it in two application sectors. */
function imagePair(fake) {
  const image = fake.flash.slice();
  for (const a of [0x10000, 0x52000]) image.fill(0xa5, a, a + SECTOR);
  return { kind: 'backup', name: 'x', data: image, sha256: '' };
}
const noV15 = (r) => assert.equal(r.fake.received.some((l) => l.startsWith('uboot')), false, 'soft key was sent');

// --- protocol basics -------------------------------------------------------
test('crc32 matches zlib and status parsing tolerates extra fields', () => {
  assert.equal(hex8(crc32(new TextEncoder().encode('123456789'))), 'CBF43926');
  const s = parseStatus('OK uboot=1 v15=0 loader=1 loader_running=0 future=7');
  assert.deepEqual([s.uboot, s.v15, s.loader, s.loaderRunning], [true, false, true, false]);
  assert.throws(() => parseStatus('ERR x'), /status/);
});

test('ping, status and info work with output fragmented to 1 and 7 byte pieces', async () => {
  for (const chunk of [[1], [7], [3, 1, 5]]) {
    const { session, fake } = rig({ chunk });
    assert.equal(await session.connect(), true);
    fake.flash; // loader is needed only for read
    assert.equal(await session.identify(), 'OK key=980F type=3 id=856014');
  }
});

test('read reply survives fragmentation across the DATA, payload and END boundaries', async () => {
  const { link, fake } = rig({ chunk: [5, 1, 4096, 3, 65, 1] });
  fake.state.loader = true;
  const out = await link.readReply('read 0x1000 9000', 9000);
  assert.deepEqual(out, fake.flash.slice(0x1000, 0x1000 + 9000));
});

test('wrong port: no PONG is reported as wrong-port', async () => {
  const { session } = rig({ faults: { pingSilent: true } });
  assert.equal(await code(session.connect()), 'wrong-port');
});

test('the command allowlist refuses the soft key and every other verb outside it', async () => {
  assert.deepEqual([...ALLOWED_COMMANDS].sort(), ['info', 'ldr', 'ping', 'read', 'rekey', 'status', 'wsec']);
  const { link, fake } = rig();
  for (const verb of ['uboot', 'runapp', 'jump', 'memw', 'memr', 'selftest-write', 'k']) {
    assert.equal(await code(link.request(`${verb} 1 2`)), 'command-refused', verb);
  }
  assert.equal(fake.received.length, 0, 'refused commands must not reach the wire');
});

// --- D2 gate: four combinations of confirmation and uboot -------------------
test('D2 gate: confirmed off and uboot=1 is the only combination that passes', async () => {
  const cases = [
    { confirmedOff: true, uboot: true, want: 'no-error' },
    { confirmedOff: false, uboot: true, want: 'not-confirmed-off' },
    { confirmedOff: true, uboot: false, want: 'no-uboot' },
    { confirmedOff: false, uboot: false, want: 'not-confirmed-off' },
  ];
  for (const c of cases) {
    const r = rig({ confirmedOff: c.confirmedOff, uboot: c.uboot });
    r.fake.state.loader = true;
    assert.equal(await code(r.session.identify()), c.want, JSON.stringify(c));
    assert.equal(await code(r.session.readFlash(0, 16)), c.want, `read ${JSON.stringify(c)}`);
    noV15(r);
  }
});

test('D2 gate: a running V15 is refused outright, checkbox or not, for every flash command', async () => {
  for (const confirmedOff of [true, false]) {
    const r = rig({ confirmedOff, v15: true, uboot: false });
    r.fake.state.loader = true;
    assert.equal(await code(r.session.identify()), 'v15-attached');
    assert.equal(await code(r.session.readFlash(0, 16)), 'v15-attached');
    assert.equal(await code(r.session.backupFlash()), 'v15-attached');
    assert.equal(await code(r.session.rekey()), confirmedOff ? 'v15-attached' : 'not-confirmed-off');
    assert.equal(await code(r.session.uploadLoader(LOADER)), 'v15-attached');
    assert.equal(r.fake.received.some((l) => /^(info|read|wsec|ldr|rekey|uboot)/.test(l)), false);
    noV15(r);
  }
});

test('uboot=0 with no V15 gives key-mode guidance and never sends the soft key', async () => {
  const r = rig({ uboot: false });
  const e = await r.session.requireUboot().catch((x) => x);
  assert.equal(e.code, 'no-uboot');
  assert.match(e.message, /Start key mode/);
  noV15(r);
});

test('rekey needs the off confirmation, then the transporter closes the port', async () => {
  const off = rig({ confirmedOff: false });
  assert.equal(await code(off.session.rekey()), 'not-confirmed-off');
  assert.equal(off.fake.received.includes('rekey'), false);
  const r = rig();
  const msg = await r.session.rekey();
  assert.match(msg, /switch the FM-1 ON only after/);
  await new Promise((res) => setTimeout(res, 20));
  assert.ok(r.fake.rekeyed);
  assert.equal(await code(r.session.status()), 'port-closed');
});

test('waitUboot polls until the FM-1 appears in boot mode, and gives up', async () => {
  const r = rig({ uboot: false });
  setTimeout(() => { r.fake.state.uboot = true; }, 120);
  assert.equal(await r.session.waitUboot(2000, 20), true);
  const never = rig({ uboot: false });
  assert.equal(await code(never.session.waitUboot(150, 20)), 'no-uboot');
});

// --- loader ------------------------------------------------------------------
test('loader upload: sizes, hash, chunking, idempotence', async () => {
  const r = rig();
  assert.equal(await r.session.uploadLoader(LOADER), 'loaded');
  assert.equal(r.fake.received.filter((l) => l.startsWith('ldr')).length, 6);
  assert.equal(await r.session.uploadLoader(LOADER), 'already-loaded');
  assert.equal(await code(rig().session.uploadLoader(LOADER.slice(1))), 'loader-size');
  const bad = LOADER.slice(); bad[0] ^= 1;
  assert.equal(await code(rig().session.uploadLoader(bad)), 'loader-sha');
  // the shipped constant is the real loader's hash: a synthetic blob must not pass it
  const strict = rig(); strict.session.loaderSha256 = LOADER_SHA256;
  assert.equal(await code(strict.session.uploadLoader(LOADER)), 'loader-sha');
});

test('loader upload failures: ERR crc and ERR loader-running', async () => {
  assert.equal(await code(rig({ faults: { ldrReply: 'ERR crc 00000000' } }).session.uploadLoader(LOADER)), 'loader-upload');
  const run = rig(); run.fake.state.loaderRunning = true;
  assert.equal(await code(run.session.uploadLoader(LOADER)), 'loader-upload');
});

// --- identify ---------------------------------------------------------------
test('info must be exactly the FM-1 chip key and flash id', async () => {
  assert.equal(await code(rig({ faults: { infoReply: 'ERR info' } }).session.identify()), 'not-fm1');
  assert.equal(await code(rig({ faults: { infoReply: 'OK key=1234 type=3 id=856014' } }).session.identify()), 'not-fm1');
  assert.equal(await code(rig({ faults: { infoReply: 'OK key=980F type=3 id=EF4015' } }).session.identify()), 'not-fm1');
});

// --- backup -----------------------------------------------------------------
test('backup: two dumps are compared by hash, saved, and read-only', async () => {
  const r = await ready();
  const b = await r.session.backupFlash();
  assert.equal(b.sha256, await sha256Hex(r.fake.flash));
  assert.deepEqual(r.saved.map(([n]) => n), ['fm1-dumpA.bin', 'fm1-dumpB.bin']);
  assert.deepEqual(r.saved[0][1], r.fake.flash);
  assert.equal(r.fake.received.filter((l) => l.startsWith('read')).length, 2);
  assert.equal(r.fake.received.some((l) => l.startsWith('wsec')), false);
  assert.ok(r.progress.some(([s, d, t]) => s === 'dump B' && d === t));
  noV15(r);
});

test('backup failure paths: dumps differ, END crc, END FAIL, stall, read errors', async () => {
  const differ = await ready({ faults: { corruptReadAt: 2 } });
  assert.equal(await code(differ.session.backupFlash()), 'read-crc'); // corrupt payload vs END of the true bytes
  const crc = await ready({ faults: { badEndCrc: 1 } });
  assert.equal(await code(crc.session.backupFlash()), 'read-crc');
  const endFail = await ready({ faults: { endFail: 1 } });
  assert.equal(await code(endFail.session.backupFlash()), 'read-failed');
  const stall = await ready({ timeoutMs: 250, faults: { stallAfter: 5000 } });
  assert.equal(await code(stall.session.backupFlash()), 'timeout');
  const noLoader = rig(); // loader never uploaded
  assert.equal(await code(noLoader.session.backupFlash()), 'read-error');
  assert.equal(differ.saved.length, 0);
});

test('backup: two internally consistent but different dumps are refused by the hash comparison', async () => {
  const r = await ready();
  // flip a flash byte between the two reads without the transporter noticing
  const real = r.fake.flash;
  let reads = 0;
  const orig = r.session.readFlash.bind(r.session);
  r.session.readFlash = async (...a) => { const out = await orig(...a); reads += 1; if (reads === 1) real[0x30000] ^= 1; return out; };
  assert.equal(await code(r.session.backupFlash()), 'dump-mismatch');
  assert.equal(r.saved.length, 0);
});

// --- images -----------------------------------------------------------------
test('image parsing: too small, wrong package hash, 1 MiB backup accepted', async () => {
  assert.equal(await code(RecoverySession.parseImage(new Uint8Array(1000))), 'image-too-small');
  assert.equal(await code(RecoverySession.parseImage(new Uint8Array(WRITE_END + 10))), 'fwsc-not-stock');
  const img = await RecoverySession.parseImage(new Uint8Array(FLASH_SIZE).fill(7), 'b.bin');
  assert.equal(img.kind, 'backup');
  assert.equal(img.data.length, FLASH_SIZE);
  assert.equal(await code(RecoverySession.parseImage('nope')), 'image-type');
});

// Synthetic package, same construction as native-fwsc-inspection.test.mjs.
function crc16(bytes) { let s = 0; for (const b of bytes) { s ^= b << 8; for (let i = 0; i < 8; i += 1) s = ((s << 1) ^ (s & 0x8000 ? 0x1021 : 0)) & 0xffff; } return s; }
function encode(bytes, seed = 0xffff) { return Uint8Array.from(bytes, (b) => { const v = b ^ (seed & 255); seed = ((seed << 1) ^ (seed & 0x8000 ? 0x1021 : 0)) & 0xffff; return v; }); }
function syntheticPackage(flashPayload) {
  const logical = new Uint8Array(0x4a0 + flashPayload.length);
  const tail = new Uint8Array(64); tail.set(new TextEncoder().encode('JLUFW'), 48);
  const off0 = 0x400, offOta = off0 + flashPayload.length;
  const rows = [[0, 'flash.bin', off0, flashPayload], [100, 'ota.bin', offOta, new TextEncoder().encode('OTA')],
    [255, 'tail.bin', logical.length - 64, tail]];
  rows.forEach(([kind, name, offset, payload], i) => {
    const item = new Uint8Array(80); const v = new DataView(item.buffer);
    v.setUint16(0, kind, true); v.setUint16(2, i, true); v.setUint16(4, crc16(payload), true);
    v.setUint32(8, offset, true); v.setUint32(12, payload.length, true); v.setUint32(16, payload.length, true);
    item.set(new TextEncoder().encode(name), 64);
    logical.set(encode(item), 64 + i * 80); logical.set(payload, offset);
  });
  const header = new Uint8Array(64); const v = new DataView(header.buffer);
  v.setUint16(2, crc16(logical.subarray(64, 64 + 240)), true); v.setUint32(4, logical.length, true); v.setUint16(8, 3, true);
  header.set(new TextEncoder().encode('AC791N'), 16); v.setUint16(0, crc16(header.subarray(2)), true);
  logical.set(encode(header));
  const raw = new Uint8Array(logical.length + 20);
  for (let i = 0; i < 20; i += 1) { raw.set(logical.subarray(i * 47, (i + 1) * 47), i * 48); raw[i * 48 + 47] = i < 8 ? 'FM-1_015'.charCodeAt(i) + i + 1 : 125; }
  raw.set(logical.subarray(940), 960);
  return raw;
}

test('package extraction returns the type-0 flash entry; malformed packages are rejected', () => {
  const payload = Uint8Array.from({ length: 5000 }, (_, i) => (i * 13) & 255);
  const raw = syntheticPackage(payload);
  assert.deepEqual(extractFwscFlashImage(raw), payload);
  const bad = raw.slice(); bad[0x600] ^= 1;
  assert.throws(() => extractFwscFlashImage(bad), /CRC/);
  assert.throws(() => extractFwscFlashImage(new Uint8Array(100)), /size/);
});

const V15_PATH = new URL('../../../scratch/FM-1_v15_cdn.fwsc', import.meta.url);
const V15_ALT = process.env.FM1_V15_FWSC;
const v15File = [V15_ALT, V15_PATH.pathname].find((p) => p && fs.existsSync(p));
test('stock V15 package: hash gate, image equals the shim\'s raw slice (needs the vendor package; skipped if absent)',
  { skip: v15File ? false : 'stock V15 package not present (git-ignored vendor file)' }, async () => {
    const raw = new Uint8Array(fs.readFileSync(v15File));
    assert.equal(await sha256Hex(raw), STOCK_V15_SHA256);
    const img = await RecoverySession.parseImage(raw, 'FM-1.fwsc');
    assert.equal(img.kind, 'fwsc');
    assert.equal(img.data.length, WRITE_END);
    assert.deepEqual(img.data, raw.slice(0x414, 0x414 + WRITE_END)); // fm1t's package_image via the research shim
    assert.equal(inspectFwscEnvelope(raw).identity, 'FM-1_015');
  });

// --- plan / write ------------------------------------------------------------
test('dry run lists the differing sectors, writes nothing', async () => {
  const r = await ready();
  await r.session.backupFlash();
  const plan = await r.session.plan(imagePair(r.fake));
  assert.deepEqual(plan.sectors, [0x10000, 0x52000]);
  assert.equal(r.fake.received.some((l) => l.startsWith('wsec')), false);
  noV15(r);
});

test('plan needs a backup from this session', async () => {
  const r = await ready();
  assert.equal(await code(r.session.plan(imagePair(r.fake))), 'no-backup');
});

test('plan refuses an image that changes the boot area', async () => {
  const r = await ready();
  await r.session.backupFlash();
  const img = imagePair(r.fake); img.data[0x20] ^= 1;
  assert.equal(await code(r.session.plan(img)), 'protected-sector');
  const last = imagePair(r.fake); last.data[WRITE_MIN - 1] ^= 1;
  assert.equal(await code(r.session.plan(last)), 'protected-sector');
});

test('plan refuses when the flash no longer equals the backup', async () => {
  const r = await ready();
  await r.session.backupFlash();
  r.fake.flash[0x20000] ^= 1;
  assert.equal(await code(r.session.plan(imagePair(r.fake))), 'flash-differs-from-backup');
});

test('plan reports (does not write) differences beyond the writable window', async () => {
  const r = await ready();
  await r.session.backupFlash();
  const img = imagePair(r.fake); img.data[WRITE_END + 10] ^= 1;
  const plan = await r.session.plan(img);
  assert.deepEqual(plan.beyondWindow, [WRITE_END]);
  assert.deepEqual(plan.sectors, [0x10000, 0x52000]);
});

test('write: only differing sectors, boot area untouched, final read verified', async () => {
  const r = await ready();
  await r.session.backupFlash();
  const img = imagePair(r.fake);
  const before = r.fake.flash.slice();
  const res = await r.session.write(await r.session.plan(img));
  assert.equal(res.written, 2);
  assert.deepEqual(r.fake.writtenSectors, [0x10000, 0x52000]);
  assert.deepEqual(r.fake.flash.subarray(0, WRITE_MIN), before.subarray(0, WRITE_MIN));
  assert.deepEqual(r.fake.flash.subarray(WRITE_END), before.subarray(WRITE_END));
  assert.deepEqual(r.fake.flash.subarray(0, WRITE_END), img.data.subarray(0, WRITE_END));
  assert.equal(res.finalSha256, await sha256Hex(r.fake.flash));
  noV15(r);
});

test('write: restoring the session backup after a write returns the original flash', async () => {
  const r = await ready();
  await r.session.backupFlash();
  const original = r.session.backup.data.slice();
  await r.session.write(await r.session.plan(imagePair(r.fake)));
  // new backup of the modified flash, then restore the original
  await r.session.backupFlash();
  const restore = { kind: 'backup', name: 'orig', data: original, sha256: '' };
  const res = await r.session.write(await r.session.plan(restore));
  assert.equal(res.written, 2);
  assert.deepEqual(r.fake.flash, original);
});

test('write: nothing to do, and declined confirmation writes nothing', async () => {
  const same = await ready();
  await same.session.backupFlash();
  const res = await same.session.write(await same.session.plan({ kind: 'backup', data: same.fake.flash.slice(), name: '', sha256: '' }));
  assert.equal(res.written, 0);
  const declined = await ready({ confirm: false });
  await declined.session.backupFlash();
  const plan = await declined.session.plan(imagePair(declined.fake));
  assert.equal(await code(declined.session.write(plan)), 'not-confirmed');
  assert.equal(declined.fake.received.some((l) => l.startsWith('wsec')), false);
});

test('write: flash changed after the dry run is caught by the recheck read', async () => {
  const r = await ready({ faults: { flashChangesAfterReads: 3 } });
  await r.session.backupFlash();         // reads 1, 2
  const plan = await r.session.plan(imagePair(r.fake)); // read 3
  assert.equal(await code(r.session.write(plan)), 'flash-changed'); // read 4 sees the change
  assert.equal(r.fake.received.some((l) => l.startsWith('wsec')), false);
});

test('write: the D2 gate is re-checked before the write (FM-1 dropped out of boot mode)', async () => {
  const r = await ready();
  await r.session.backupFlash();
  const plan = await r.session.plan(imagePair(r.fake));
  r.fake.state.uboot = false;
  assert.equal(await code(r.session.write(plan)), 'no-uboot');
  assert.equal(r.fake.received.some((l) => l.startsWith('wsec')), false);
});

test('write failures stop at once with do-not-power-cycle advice', async () => {
  for (const faults of [{ wsecErrAt: 2 }, { wsecNoReplyAt: 1 }]) {
    const r = await ready({ faults, timeoutMs: 300 });
    await r.session.backupFlash();
    const e = await r.session.write(await r.session.plan(imagePair(r.fake))).catch((x) => x);
    assert.equal(e.code, 'write-failed', JSON.stringify(faults));
    assert.match(e.message, /DO NOT power-cycle/);
    assert.equal(r.fake.wsecCount, faults.wsecErrAt || faults.wsecNoReplyAt, 'no sector sent after the failure');
  }
});

test('final readback mismatch is reported (a sector acknowledged OK but not written)', async () => {
  const r = await ready({ faults: { wsecSilentDropAt: 1 } });
  await r.session.backupFlash();
  const e = await r.session.write(await r.session.plan(imagePair(r.fake))).catch((x) => x);
  assert.equal(e.code, 'verify-failed');
  assert.match(e.message, /DO NOT power-cycle/);
});

test('final readback corruption in transit is caught', async () => {
  const r = await ready({ faults: { finalReadCorrupt: 5 } }); // dump A, B, plan, recheck, final
  await r.session.backupFlash();
  const plan = await r.session.plan(imagePair(r.fake));
  const e = await r.session.write(plan).catch((x) => x);
  assert.ok(['read-crc', 'verify-failed'].includes(e.code), e.code);
});

test('port closing mid-run surfaces as port-closed', async () => {
  const r = await ready();
  r.session.progress = (stage, done) => { if (done >= 0x20000) r.fake.close(); };
  const p = r.session.readFlash(0, FLASH_SIZE);
  assert.equal(await code(p), 'port-closed');
});

test('wsec payloads are sector sized and CRC-bound, addresses stay in the window', async () => {
  const r = await ready();
  await r.session.backupFlash();
  await r.session.write(await r.session.plan(imagePair(r.fake)));
  for (const line of r.fake.received.filter((l) => l.startsWith('wsec'))) {
    const [, addr] = line.split(' ');
    assert.ok(Number(addr) >= WRITE_MIN && Number(addr) < WRITE_END && Number(addr) % SECTOR === 0, line);
  }
});

// --- review hardening (PR #173) -------------------------------------------
// (a) a write needs this session's identify, loader, backup and its own plan.
test('(a) a plan from an earlier connection cannot drive a write on a new one', async () => {
  const a = await ready();
  await a.session.backupFlash();
  const planA = await a.session.plan(imagePair(a.fake));
  // reconnect: new link and session on a transporter with the same flash
  const b = rig({ flash: a.fake.flash });
  await b.session.connect();
  assert.equal(await code(b.session.write(planA)), 'not-identified');
  await b.session.uploadLoader(LOADER);
  await b.session.identify();
  assert.equal(await code(b.session.write(planA)), 'no-backup');
  await b.session.backupFlash();
  assert.equal(await code(b.session.write(planA)), 'plan-foreign');
  // a forged copy with the right shape is not this session's plan either
  assert.equal(await code(b.session.write({ ...planA })), 'plan-foreign');
  assert.equal(b.fake.received.some((l) => l.startsWith('wsec')), false);
  assert.equal(a.fake.received.some((l) => l.startsWith('wsec')), false);
  noV15(b);
});

test('(a) identify alone, or a loader without identify, is not enough to write', async () => {
  const r = rig();
  await r.session.connect();
  await r.session.identify();
  assert.equal(await code(r.session.write({ sectors: [0x10000] })), 'no-loader');
  const s = rig();
  await s.session.connect();
  await s.session.uploadLoader(LOADER);
  assert.equal(await code(s.session.write({ sectors: [0x10000] })), 'not-identified');
  assert.equal(r.fake.received.concat(s.fake.received).some((l) => /^(wsec|read)/.test(l)), false);
});

test('(a) a new backup after the dry run makes the plan stale; a plan writes once', async () => {
  const r = await ready();
  await r.session.backupFlash();
  const plan = await r.session.plan(imagePair(r.fake));
  await r.session.backupFlash();
  assert.equal(await code(r.session.write(plan)), 'plan-stale');
  const fresh = await r.session.plan(imagePair(r.fake));
  assert.equal((await r.session.write(fresh)).written, 2);
  assert.equal(await code(r.session.write(fresh)), 'plan-foreign');
  assert.equal(r.fake.wsecCount, 2);
});

test('(a) rekey forgets identity, loader and backup; a closed link refuses the write', async () => {
  const r = await ready();
  await r.session.backupFlash();
  const plan = await r.session.plan(imagePair(r.fake));
  r.fake.faults.closeOnRekey = false;
  await r.session.rekey();
  assert.equal(r.session.identified, false);
  assert.equal(r.session.loaderReady, false);
  assert.equal(r.session.backup, null);
  assert.equal(await code(r.session.write(plan)), 'port-closed');
  assert.equal(r.fake.received.some((l) => l.startsWith('wsec')), false);
});

test('(a) write re-checks every sector against [0x4000, 0x93000) itself', async () => {
  for (const bad of [0x0, 0x3000, WRITE_MIN - 1, WRITE_END, 0x10001, -SECTOR, '0x10000', 16384.5, null]) {
    assert.throws(() => assertWritableSectors([0x10000, bad]), (e) => e.code === 'sector-out-of-window', String(bad));
  }
  assert.throws(() => assertWritableSectors('0x10000'), (e) => e.code === 'sector-out-of-window');
  assert.doesNotThrow(() => assertWritableSectors([WRITE_MIN, 0x10000, WRITE_END - SECTOR]));
  // write() runs it on the session's own record; plans are frozen summaries,
  // and a caller-built plan with a bad sector never reaches it or the wire.
  const r = await ready();
  await r.session.backupFlash();
  const plan = await r.session.plan(imagePair(r.fake));
  assert.ok(Object.isFrozen(plan) && Object.isFrozen(plan.sectors));
  assert.throws(() => { plan.sectors.push(0); }, TypeError);
  for (const bad of [0x0, 0x3000, WRITE_END]) {
    assert.equal(await code(r.session.write({ ...plan, sectors: [bad] })), 'plan-foreign');
  }
  assert.equal(r.fake.received.some((l) => l.startsWith('wsec')), false);
  const src = fs.readFileSync(new URL('../www/recovery-transporter.js', import.meta.url), 'utf8');
  const body = src.slice(src.indexOf('  async write(plan) {'), src.indexOf('export function assertWritableSectors'));
  assert.match(body, /assertWritableSectors\(\[a\]\)/, 'write() checks each sector before sending it');
});

test('(a) the dry run copies the image: changing the caller\'s buffer changes nothing written', async () => {
  const r = await ready();
  await r.session.backupFlash();
  const img = imagePair(r.fake);
  const plan = await r.session.plan(img);
  img.data.fill(0x11, 0, WRITE_END); // includes the boot area
  assert.equal(plan.image, undefined, 'the plan exposes no buffers');
  await r.session.write(plan);
  assert.deepEqual(r.fake.writtenSectors, [0x10000, 0x52000]);
  assert.equal(r.fake.flash[0x10000], 0xa5);
  assert.notEqual(r.fake.flash[0], 0x11);
});

// (b) rekey closes the link itself before anyone reconnects.
test('(b) rekey closes the old link even when the transporter keeps the port open', async () => {
  const r = rig();
  r.fake.faults.closeOnRekey = false;
  let closes = 0;
  const orig = r.fake.close.bind(r.fake);
  r.fake.close = async () => { closes += 1; return orig(); };
  await r.session.rekey();
  assert.equal(closes, 1);
  assert.equal(r.link.closed, true);
  assert.equal(await code(r.link.request('ping', 100)), 'port-closed');
  assert.deepEqual(r.fake.received, ['status', 'rekey']);
});

// (c) the loader goes up only in boot mode, with the FM-1 confirmed off.
test('(c) uploadLoader needs the off confirmation and uboot=1', async () => {
  const off = rig({ confirmedOff: false });
  assert.equal(await code(off.session.uploadLoader(LOADER)), 'not-confirmed-off');
  const noUboot = rig({ uboot: false });
  assert.equal(await code(noUboot.session.uploadLoader(LOADER)), 'no-uboot');
  for (const r of [off, noUboot]) {
    assert.equal(r.fake.received.some((l) => l.startsWith('ldr')), false);
    assert.equal(r.session.loaderReady, false);
  }
  const ok = rig();
  assert.equal(await ok.session.uploadLoader(LOADER), 'loaded');
  assert.equal(ok.session.loaderReady, true);
});

// (d) whole-line templates, not just the first word.
test('(d) request lines must match a fixed template as a whole', async () => {
  const { link, fake } = rig();
  const sec = new Uint8Array(SECTOR);
  const cases = [
    ['ping\nuboot'], ['ping uboot'], ['ping;uboot'], ['ping '], [' ping'], ['status\n'], ['info x'], ['rekey now'],
    ['read 0x1000 16 uboot'], ['read 0x1000'], ['read 4096 16'], ['read 0xFFFFF 16'], ['read 0xff000 8192'], ['read 0x0 0'],
    ['ldr 0 4096 ZZZZZZZZ', sec], ['ldr 0 4096 0000000'], ['ldr 0 10 00000000', sec], ['ldr 24576 4096 00000000', sec],
    ['wsec 0x10000 00000000', new Uint8Array(10)], ['wsec 0x10000 00000000'], ['wsec 0x0 00000000', sec],
    ['wsec 0x3000 00000000', sec], ['wsec 0x93000 00000000', sec], ['wsec 0x10001 00000000', sec],
    ['wsec 0x10000 00000000\nuboot', sec], ['ping', sec], ['uboot'], ['', null],
  ];
  for (const [line, payload = null] of cases) {
    assert.equal(await code(link.request(line, 100, payload)), 'command-refused', JSON.stringify(line));
  }
  assert.equal(fake.received.length, 0, 'refused lines must not reach the wire');
  // the templates still admit what the session sends
  assert.equal(await link.request('ping', 500), 'PONG');
  assert.match(await link.request('status', 500), /^OK uboot=/);
});

test('(d) templates are exported, one per allowlisted verb', () => {
  assert.deepEqual(Object.keys(REQUEST_TEMPLATES).sort(), [...ALLOWED_COMMANDS].sort());
  assert.doesNotThrow(() => checkRequest('wsec 0x4000 DEADBEEF', new Uint8Array(SECTOR)));
  assert.doesNotThrow(() => checkRequest('wsec 0x92000 DEADBEEF', new Uint8Array(SECTOR)));
  assert.doesNotThrow(() => checkRequest('read 0x0 1048576'));
  assert.doesNotThrow(() => checkRequest('ldr 20480 3584 00000000', new Uint8Array(3584)));
});

// (e) image description
test('(e) describeImage: hashes, and a warning when the image differs from the backup', async () => {
  const r = await ready();
  const same = { kind: 'backup', name: 'mine.bin', data: r.fake.flash.slice(), sha256: await sha256Hex(r.fake.flash) };
  const none = await describeImage(same, null);
  assert.equal(none.warn, true);
  assert.ok(none.lines.some((l) => l.includes(same.sha256)));
  assert.ok(none.lines.some((l) => /No backup in this connection/.test(l)));
  await r.session.backupFlash();
  const eq = await describeImage(same, r.session.backup);
  assert.equal(eq.warn, false);
  assert.equal(eq.sameAsBackup, true);
  const other = imagePair(r.fake);
  const d = await describeImage(other, r.session.backup);
  assert.equal(d.warn, true);
  assert.equal(d.differingSectors, 2);
  assert.equal(d.bootAreaDiffers, false);
  assert.ok(d.lines.some((l) => /WARNING: differs/.test(l)));
  other.data[0x10] ^= 1;
  const boot = await describeImage(other, r.session.backup);
  assert.equal(boot.bootAreaDiffers, true);
  assert.ok(boot.lines.some((l) => /boot area 0x0-0x3FFF differs/.test(l)));
  // the stock package: differing app sectors are expected, a boot-area difference is not
  const pkg = { kind: 'fwsc', name: 'FM-1.fwsc', data: imagePair(r.fake).data.slice(0, WRITE_END), sha256: 'x' };
  const p = await describeImage(pkg, r.session.backup);
  assert.equal(p.warn, false);
  assert.equal(p.differingSectors, 2);
  assert.ok(!p.lines.some((l) => /WARNING/.test(l)));
  pkg.data[0x10] ^= 1;
  const pb = await describeImage(pkg, r.session.backup);
  assert.equal(pb.warn, true);
  assert.equal(pb.bootAreaDiffers, true);
});
