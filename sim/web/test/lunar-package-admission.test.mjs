// SPDX-License-Identifier: MIT
// Offline tests for the flasher's package admission (lunar-package-admission.js).
// Packages are synthetic (lunar-package-fixture.mjs): a small FWSC with V15's
// structure, so no vendor byte is needed. tests/test_build_fwsc.py checks the same module
// against packages made by tools/jieli/build_fwsc.py. Set
// LUNAR_PRIVATE_FWSC (and optionally LUNAR_PRIVATE_FWSC_MANIFEST) to also admit
// a real package with the pinned V15 profile. Nothing is sent anywhere.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import {
  ADMISSION_FORMAT, V15_PROFILE, canonicalJson, describeLunarPackage, logicalImage,
  markersIdentity, sfcDecode, sha256Hex, verifyNativePackage, xorStream,
} from '../www/lunar-package-admission.js';
import {
  AREA, AREA_RECORD, ADDR, FB, FO, KEY, LUNAR, PROFILE, REC, SLOT, STOCK, STOCK_LOG,
  ascii, install, lunarApp, pattern, physical, put32, repack, u16,
} from './lunar-package-fixture.mjs';

const opts = (extra = {}) => ({ profiles: [PROFILE], ...extra });

async function blocked(bytes, pattern, extra) {
  await assert.rejects(verifyNativePackage(bytes, opts(extra)), (error) => {
    assert.match(error.message, /^package admission blocked: /);
    assert.match(error.message, pattern);
    return true;
  });
}

test('the synthetic stock package is internally consistent', () => {
  assert.equal(markersIdentity(STOCK), 'FM-1_015');
  assert.equal(markersIdentity(LUNAR), 'FM-1_501');
  assert.equal(STOCK.length, LUNAR.length);
  assert.deepEqual(physical(logicalImage(STOCK), 'FM-1_015'), STOCK);
  assert.deepEqual(repack(STOCK_LOG), STOCK_LOG);   // re-deriving every CRC changes nothing
});

test('admits a Lunar install package and returns the adapter record', async () => {
  const got = await verifyNativePackage(LUNAR, opts());
  assert.equal(got.format, ADMISSION_FORMAT);
  assert.equal(got.kind, 'lunar-install');
  assert.equal(got.product, 'FM-1_501');
  assert.equal(got.model, 'FM-1');
  assert.equal(got.version, 501);
  assert.equal(got.packageSha256, await sha256Hex(LUNAR));
  assert.deepEqual(got.logicalImage, logicalImage(LUNAR));
  assert.equal(got.logicalImageSha256, await sha256Hex(logicalImage(LUNAR)));
  assert.ok(Object.isFrozen(got) && Object.isFrozen(got.manifest));
  const m = got.manifest;
  assert.equal(m.app.bytes, 0x80);
  assert.equal(m.app.spare_bytes, SLOT - 0x80);
  assert.equal(m.app.flash_offset, AREA + ADDR);
  assert.equal(m.app.identity_offset, 6);
  assert.equal(m.app.sha256, await sha256Hex(lunarApp()));
  assert.deepEqual(m.flash.write_range, [AREA, FB]);
  for (const [lo, hi] of m.flash.mutable_ranges) assert.ok(AREA <= lo && lo < hi && hi <= FB);
});

test('admits the stock package byte for byte as the roll-back', async () => {
  const got = await verifyNativePackage(STOCK, opts());
  assert.equal(got.kind, 'stock-rollback');
  assert.equal(got.product, 'FM-1_015');
  assert.equal(got.manifest.app, null);
  assert.deepEqual(got.manifest.flash.mutable_ranges, []);
});

test('a supplied manifest must equal the computed one, in any accepted form', async () => {
  const manifest = await describeLunarPackage(LUNAR, PROFILE);
  const text = JSON.stringify(manifest);
  for (const form of [manifest, text, new TextEncoder().encode(text)]) {
    assert.equal((await verifyNativePackage(LUNAR, opts({ manifest: form }))).kind, 'lunar-install');
  }
  const rollback = await describeLunarPackage(STOCK, PROFILE);
  await blocked(LUNAR, /manifest does not match/, { manifest: rollback });
  await blocked(LUNAR, /manifest does not match/, { manifest: { ...manifest, product: 'FM-1_502' } });
  await blocked(LUNAR, /not valid JSON/, { manifest: '{' });
  assert.equal(canonicalJson({ b: 1, a: [2, { d: 3, c: 4 }] }), '{"a":[2,{"c":4,"d":3}],"b":1}');
});

test('a full-slot app leaves no fill and is admitted', async () => {
  const got = await verifyNativePackage(install(STOCK_LOG, lunarApp('FM-1_501', SLOT)), opts());
  assert.equal(got.manifest.app.spare_bytes, 0);
});

test('rejects departures from the builder rules even with every CRC repaired', async () => {
  const lunarLog = logicalImage(LUNAR);
  const cases = {
    'flash head': [{ log: (l) => { l[FO + 0x10] ^= 1; } }, /flash head/],
    'fill': [{ area: (a) => { a[ADDR + SLOT - 1] = 0; } }, /not 0xFF fill/],
    'cfg/reserved': [{ area: (a) => { a[ADDR + SLOT + 2] ^= 1; } }, /cfg or reserved/],
    'unreferenced tail': [{ area: (a) => { a[AREA_RECORD + 0x100] ^= 1; } }, /cfg or reserved/],
    'area record fields': [{ area: (a) => { a[12] ^= 1; } }, /cfg or reserved/],
    'app placement': [{ area: (a) => put32(a, REC + 4, ADDR + 1) }, /placement or size/],
    'app oversize': [{ area: (a) => put32(a, REC + 8, SLOT + 1) }, /placement or size/],
    'app empty': [{ area: (a) => put32(a, REC + 8, 0) }, /placement or size/],
    'app record CRC': [{ area: (a) => put32(a, REC + 8, 0x40), appRecord: false }, /app.bin record CRC/],
    'after flash.bin': [{ log: (l) => { l[l.length - 1] ^= 1; } }, /entries after flash.bin|entry records/],
    'before flash.bin': [{ log: (l) => { l[FO - 1] ^= 1; } }, /between the entry list/],
    'entry record': [{ log: (l) => { l[64 + 80 + 20] ^= 1; } }, /entry records/],
  };
  for (const [name, [edit, pattern]] of Object.entries(cases)) {
    await blocked(physical(repack(lunarLog, edit), 'FM-1_501'), pattern).catch((error) => {
      throw new Error(`${name}: ${error.message}`);
    });
  }
});

test('rejects CRC damage, wrong identities and wrong sizes', async () => {
  const damaged = LUNAR.slice();
  damaged[960 + FO + AREA + 0x40] ^= 1;
  await blocked(damaged, /CRC mismatch/);
  const header = LUNAR.slice();
  header[5] ^= 1;
  await blocked(header, /CRC mismatch|header/);
  const relabel = (bytes, identity) => physical(logicalImage(bytes), identity);
  await blocked(relabel(LUNAR, 'FM-1_015'), /neither the pinned stock/);
  await blocked(relabel(LUNAR, 'FM-1_092'), /neither the pinned stock/);
  await blocked(relabel(LUNAR, 'FM-1_901'), /neither the pinned stock/);
  await blocked(relabel(LUNAR, 'FM-1_502'), /exactly once/);
  await blocked(relabel(STOCK, 'FM-1_501'), /exactly once|foreign identity/);
  await blocked(install(STOCK_LOG, lunarApp('FM-1_502'), 'FM-1_501'), /exactly once/);
  const two = lunarApp();
  two.set(ascii('FM-1_501\0'), 0x40);
  await blocked(install(STOCK_LOG, two), /exactly once/);
  const other = lunarApp();
  other.set(ascii('FM-1_015\0'), 0x40);
  await blocked(install(STOCK_LOG, other), /no other FM-1_nnn/);
  await blocked(LUNAR.subarray(0, LUNAR.length - 1), /package is/);
  await blocked(new Uint8Array(LUNAR.length), /identity|FWSC/);
  await assert.rejects(verifyNativePackage([...LUNAR], opts()), TypeError);
});

test('a profile with another SFC key or geometry is refused, as in build_fwsc', async () => {
  await blocked(LUNAR, /SFC key/, { profiles: [{ ...PROFILE, sfc_key: KEY ^ 1 }] });
  await blocked(STOCK, /SFC key/, { profiles: [{ ...PROFILE, sfc_key: KEY ^ 1 }] });
  await blocked(LUNAR, /does not end where VM begins/, { profiles: [{ ...PROFILE, vm_base: FB + 0x1000 }] });
});

test('the pinned V15 profile is frozen and admits nothing synthetic', async () => {
  assert.ok(Object.isFrozen(V15_PROFILE) && Object.isFrozen(V15_PROFILE.components_sha256));
  assert.equal(V15_PROFILE.components_sha256['top/uboot.boot'],
    '730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef');
  await assert.rejects(verifyNativePackage(LUNAR), /package admission blocked: package is/);
  await assert.rejects(verifyNativePackage(STOCK), /package admission blocked/);
});

test('the module stays self-contained', async () => {
  const source = await readFile(new URL('../www/lunar-package-admission.js', import.meta.url), 'utf8');
  assert.doesNotMatch(source, /https?:\/\//);
  assert.doesNotMatch(source, /^\s*import\b/m);
  assert.doesNotMatch(source, /\bfetch\(|XMLHttpRequest|WebSocket|navigator\.(usb|requestMIDIAccess|serial)/);
});

const PRIVATE = process.env.LUNAR_PRIVATE_FWSC;
test('opt-in: a real package admits with the pinned V15 profile', { skip: !PRIVATE && 'set LUNAR_PRIVATE_FWSC' }, async () => {
  const bytes = new Uint8Array(await readFile(PRIVATE));
  const manifestPath = process.env.LUNAR_PRIVATE_FWSC_MANIFEST;
  const manifest = manifestPath ? await readFile(manifestPath, 'utf8') : undefined;
  const got = await verifyNativePackage(bytes, { manifest });
  assert.ok(['lunar-install', 'stock-rollback'].includes(got.kind));
  assert.equal(got.packageSha256, await sha256Hex(bytes));
});

// Keep the helper honest: the XOR stream is its own inverse, which repack relies on.
test('xorStream and sfcDecode are involutions', () => {
  const data = pattern(100, 37, 5);
  assert.deepEqual(xorStream(xorStream(data)), data);
  assert.deepEqual(sfcDecode(sfcDecode(data, KEY), KEY), data);
  assert.equal(u16(Uint8Array.of(0x34, 0x12), 0), 0x1234);
});
