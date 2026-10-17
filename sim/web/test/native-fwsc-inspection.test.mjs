// SPDX-License-Identifier: MIT
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { inspectFwscEnvelope } from '../www/native-fwsc-inspection.js';
import { inspectNativePackage, verifyNativePackage } from '../www/native-package-admission.js';

function crc(bytes) {
  let state = 0;
  for (const byte of bytes) {
    state ^= byte << 8;
    for (let bit = 0; bit < 8; bit += 1) state = ((state << 1) ^ (state & 0x8000 ? 0x1021 : 0)) & 65535;
  }
  return state;
}
function encode(bytes, seed = 65535) {
  return Uint8Array.from(bytes, (byte) => {
    const value = byte ^ (seed & 255);
    seed = ((seed << 1) ^ (seed & 32768 ? 4129 : 0)) & 65535;
    return value;
  });
}
function fixture(mutate = () => {}) {
  const logical = new Uint8Array(0x4a0);
  const tail = new Uint8Array(64);
  tail.set(new TextEncoder().encode('JLUFW'), 48);
  const rows = [[0, 'flash.bin', 0x400, new TextEncoder().encode('FLASH')],
    [100, 'ota.bin', 0x420, new TextEncoder().encode('OTA')],
    [251, 'script.ver', 0x440, new TextEncoder().encode('encrypted')],
    [255, 'tail.bin', 0x460, tail]];
  rows.forEach(([kind, name, offset, payload], ordinal) => {
    const item = new Uint8Array(80);
    const view = new DataView(item.buffer);
    view.setUint16(0, kind, true); view.setUint16(2, ordinal, true); view.setUint16(4, crc(payload), true);
    view.setUint32(8, offset, true); view.setUint32(12, payload.length, true); view.setUint32(16, payload.length, true);
    item.set(new TextEncoder().encode(name), 64);
    mutate(ordinal, view, item);
    logical.set(encode(item), 64 + ordinal * 80);
    logical.set(kind === 251 ? encode(payload, 0x980f ^ (offset >>> 2)) : payload, offset);
  });
  const header = new Uint8Array(64);
  const view = new DataView(header.buffer);
  view.setUint16(2, crc(logical.subarray(64, 384)), true);
  view.setUint32(4, logical.length, true); view.setUint16(8, 4, true);
  view.setUint16(10, 4, true); view.setUint32(12, 512, true);
  header.set(new TextEncoder().encode('AC791N'), 16);
  view.setUint16(0, crc(header.subarray(2)), true);
  logical.set(encode(header));
  const raw = new Uint8Array(logical.length + 20);
  for (let index = 0; index < 20; index += 1) {
    raw.set(logical.subarray(index * 47, (index + 1) * 47), index * 48);
    raw[index * 48 + 47] = index < 8 ? 'FM-1_015'.charCodeAt(index) + index + 1 : 125;
  }
  raw.set(logical.subarray(940), 960);
  return raw;
}

test('synthetic raw and encrypted entries agree with the established Python inspector', () => {
  const raw = fixture();
  const result = inspectFwscEnvelope(raw);
  const script = 'import sys,json;sys.path.insert(0,sys.argv[1]);from inspect_fwsc import inspect;print(json.dumps(inspect(sys.stdin.buffer.read())))';
  const python = spawnSync(process.env.LUNAR_PYTHON || 'python3', ['-c', script,
    fileURLToPath(new URL('../../../tools/jieli', import.meta.url))], { input: raw, encoding: 'utf8' });
  assert.equal(python.status, 0, python.stderr);
  const oracle = JSON.parse(python.stdout);
  assert.equal(result.identity, oracle.identity);
  assert.equal(result.logicalBytes, oracle.logical_bytes);
  assert.deepEqual(result.entries.map(({ name, type, offset, bytes, allocatedBytes }) => [name, type, offset, bytes, allocatedBytes]),
    oracle.entries.map(({ name, type, offset, bytes, allocated_bytes }) => [name, type, offset, bytes, allocated_bytes]));
  assert.equal(result.entries.every((entry) => entry.crcVerified), true);
  assert.equal(result.admissible, false);
  assert.equal(result.nestedFlashVerified, false);
  assert.equal('logicalImage' in result, false);
});

test('corruption of each checked layer is rejected', () => {
  for (const [offset, pattern] of [[0, /header CRC/], [68, /entry-list CRC/], [0x414, /payload CRC/], [0x454, /payload CRC/]]) {
    const raw = fixture(); raw[offset] ^= 1;
    assert.throws(() => inspectFwscEnvelope(raw), pattern);
  }
});

test('repaired CRCs cannot hide invalid allocations, names, types or ordinals', () => {
  const cases = [
    [(view) => view.setUint32(8, 0x400, true), /overlapping/],
    [(view) => view.setUint32(8, 0xfffffff0, true), /outside/],
    [(view) => view.setUint32(16, 1, true), /outside/],
    [(view) => view.setUint16(0, 123, true), /unsupported/],
    [(view) => view.setUint16(2, 9, true), /index/],
    [(view, item) => { item.fill(0, 64); item.set(new TextEncoder().encode('flash.bin'), 64); }, /duplicate/],
    [(view, item) => item.fill(65, 64), /unterminated/],
  ];
  for (const [mutation, pattern] of cases) assert.throws(() => inspectFwscEnvelope(fixture((ordinal, view, item) => {
    if (ordinal === 1) mutation(view, item);
  })), pattern);
});

test('successful inspection remains immutable and cannot enable the OTA adapter', async () => {
  const raw = fixture();
  const report = inspectNativePackage(raw);
  assert.equal(report.envelope.headerCrcVerified, true);
  assert.equal(report.admissible, false);
  assert.equal(Object.isFrozen(report.envelope.entries[0]), true);
  await assert.rejects(verifyNativePackage(raw), /release admission/);
  assert.throws(() => inspectFwscEnvelope(new Uint8Array(2 * 1024 * 1024 + 1)), /size/);
});

function nestedFixture(mode = 'valid', identity = 'FM-1_500') {
  const generated = spawnSync(process.env.LUNAR_PYTHON || 'python3', [fileURLToPath(new URL('./nested-092-fixture.py', import.meta.url)), mode]);
  assert.equal(generated.status, 0, generated.stderr.toString());
  const flash = new Uint8Array(generated.stdout);
  const tail = new Uint8Array(64); tail.set(new TextEncoder().encode('JLUFW'), 48);
  const logical = new Uint8Array(0x400 + flash.length + 96);
  const rows = [[0, 'flash.bin', 0x400, flash], [100, 'ota.bin', 0x400 + flash.length, new Uint8Array(32)],
    [255, 'tail.bin', 0x420 + flash.length, tail]];
  rows.forEach(([kind, name, offset, payload], i) => {
    const row = new Uint8Array(80), v = new DataView(row.buffer);
    v.setUint16(0, kind, true); v.setUint16(2, i, true); v.setUint16(4, crc(payload), true);
    v.setUint32(8, offset, true); v.setUint32(12, payload.length, true); v.setUint32(16, payload.length, true);
    row.set(new TextEncoder().encode(name), 64); logical.set(encode(row), 64 + i * 80); logical.set(payload, offset);
  });
  const header = new Uint8Array(64), v = new DataView(header.buffer);
  v.setUint16(2, crc(logical.subarray(64, 304)), true); v.setUint32(4, logical.length, true); v.setUint16(8, 3, true);
  header.set(new TextEncoder().encode('AC791N'), 16); v.setUint16(0, crc(header.subarray(2)), true); logical.set(encode(header));
  const raw = new Uint8Array(logical.length + 20);
  for (let i = 0; i < 20; i += 1) { raw.set(logical.subarray(i * 47, (i + 1) * 47), i * 48); raw[i * 48 + 47] = i < 8 ? identity.charCodeAt(i) + i + 1 : 125; }
  raw.set(logical.subarray(940), 960); return raw;
}

test('092 D7000 synthetic structure agrees with Python model and stays non-admissible', async () => {
  for (const identity of ['FM-1_092', 'FM-1_500', 'FM-1_503']) {
    const raw = nestedFixture('valid', identity), report = inspectFwscEnvelope(raw);
    assert.equal(report.nestedFlashVerified, true);
    assert.equal(report.nestedInspection.profile, 'FM-1_092-D7000');
    assert.equal(report.nestedInspection.appBytes, 13);
    assert.equal(report.nestedInspection.cfgEnd, 0x4120 + 13 + 383 + 2937);
    assert.equal(report.nestedInspection.protectedStockCorrespondence, 'unverified');
    assert.equal(report.admissible, false); assert.equal(report.releaseAccepted, false);
    assert.equal(Object.isFrozen(report.nestedInspection.records[0]), true);
    assert.equal('logicalImage' in report, false);
    assert.match(inspectNativePackage(raw).reason, /structure and CRC checks passed/);
    assert.equal(inspectNativePackage(raw).admissible, false);
    await assert.rejects(verifyNativePackage(raw), /release admission/);
  }
});

test('repaired outer and area CRCs cannot hide nested malformed geometry, CRC or wrong SFC origin', () => {
  for (const mode of ['overlap', 'reserved', 'length', 'data', 'header', 'decryption', 'top-header', 'config-crc', 'spl-crc', 'cfg-crc', 'truncated', 'oversized']) {
    assert.throws(() => inspectFwscEnvelope(nestedFixture(mode)), /092 nested/);
  }
});

test('unknown identity keeps nested inspection explicitly incomplete', () => {
  const report = inspectFwscEnvelope(nestedFixture('valid', 'FM-1_600'));
  assert.equal(report.nestedFlashVerified, false);
  assert.equal(report.nestedInspection.status, 'unsupported-profile');
});
