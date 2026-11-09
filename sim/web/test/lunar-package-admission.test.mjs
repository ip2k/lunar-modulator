// SPDX-License-Identifier: MIT
// Offline tests for the flasher's package admission (lunar-package-admission.js).
// Packages are synthetic: a small FWSC with V15's structure, built here, so no
// vendor byte is needed. tests/test_build_fwsc.py checks the same module
// against packages made by tools/jieli/build_fwsc.py. Set
// LUNAR_PRIVATE_FWSC (and optionally LUNAR_PRIVATE_FWSC_MANIFEST) to also admit
// a real package with the pinned V15 profile. Nothing is sent anywhere.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import {
  ADMISSION_FORMAT, V15_PROFILE, canonicalJson, crc16, describeLunarPackage, logicalImage,
  markersIdentity, sfcDecode, sha256Hex, verifyNativePackage, xorStream,
} from '../www/lunar-package-admission.js';

const AREA = 0x400;     // flash head [0, AREA); app area after it (V15: 0x4000)
const REC = 0x20;
const ADDR = 0x120;
const SLOT = 0x200;
const AREA_RECORD = 0x400;
const AREA_BYTES = 0x800;
const FB = AREA + AREA_BYTES;
const FO = 0x200;
const COUNT = 3;
const KEY = 0x980f;

const u16 = (b, at) => b[at] | (b[at + 1] << 8);
const put16 = (b, at, v) => { b[at] = v & 255; b[at + 1] = (v >>> 8) & 255; };
const put32 = (b, at, v) => { for (let i = 0; i < 4; i += 1) b[at + i] = (v >>> (8 * i)) & 255; };
const ascii = (text) => Uint8Array.from(text, (c) => c.charCodeAt(0));
const pattern = (n, mul, add = 0) => Uint8Array.from({ length: n }, (_, i) => (i * mul + add) & 255);

function physical(log, identity) {
  const out = new Uint8Array(log.length + 20);
  for (let i = 0; i < 20; i += 1) {
    out.set(log.subarray(i * 47, (i + 1) * 47), i * 48);
    out[i * 48 + 47] = i < identity.length ? identity.charCodeAt(i) + i + 1 : 125;
  }
  out.set(log.subarray(940), 960);
  return out;
}

/** Re-derive every CRC in a logical image, after `edit(area)` / `editLog(log)`. */
function repack(log, { area: editArea, log: editLog, appRecord = true } = {}) {
  const out = log.slice();
  const flash = out.subarray(FO, FO + FB);
  const area = sfcDecode(flash.subarray(AREA), KEY);
  editArea?.(area);
  if (appRecord) {
    const size = area[REC + 8] | (area[REC + 9] << 8) | (area[REC + 10] << 16) | (area[REC + 11] << 24);
    put16(area, REC + 2, crc16(area.subarray(ADDR, ADDR + size)));
    put16(area, REC, crc16(area.subarray(REC + 2, REC + 32)));
  }
  put16(area, 2, crc16(area.subarray(32, AREA_RECORD)));
  put16(area, 0, crc16(area.subarray(2, 32)));
  flash.set(sfcDecode(area, KEY), AREA);
  editLog?.(out);
  const rec = xorStream(out.subarray(64, 144));
  put16(rec, 4, crc16(out.subarray(FO, FO + FB)));
  out.set(xorStream(rec), 64);
  const header = xorStream(out.subarray(0, 64));
  put16(header, 2, crc16(out.subarray(64, 64 + COUNT * 80)));
  put16(header, 0, crc16(header.subarray(2)));
  out.set(xorStream(header), 0);
  return out;
}

function stockLogical() {
  const tail = pattern(96, 11, 3);
  const log = new Uint8Array(FO + FB + tail.length);
  log.set(pattern(FO - 304, 5, 1), 304);                       // between the entry list and flash.bin
  const flash = log.subarray(FO, FO + FB);
  flash.set(pattern(AREA, 7, 9));                                // stand-in boot area
  const area = new Uint8Array(AREA_BYTES).fill(0);
  put32(area, 4, 0x02000120);
  put32(area, 8, AREA_RECORD);
  put32(area, REC + 4, ADDR);
  put32(area, REC + 8, SLOT);
  area.set(ascii('app.bin'), REC + 16);
  const app = pattern(SLOT, 13, 1);
  app.set(ascii('STOCK-APP:FM-1_015\0'), 0);
  area.set(app, ADDR);
  area.set(ascii('CFG-AND-RESERVED-DESCRIPTORS'), ADDR + SLOT);
  area.set(ascii('UNREFERENCED-TAIL'), AREA_RECORD + 0x100);
  flash.set(sfcDecode(area, KEY), AREA);
  log.set(tail, FO + FB);
  const entries = [[0, 'flash.bin', FO, FB], [100, 'ota.bin', FO + FB, 32], [255, 'tail.bin', FO + FB + 32, 64]];
  entries.forEach(([kind, name, start, length], index) => {
    const rec = new Uint8Array(80);
    put16(rec, 0, kind);
    put16(rec, 2, index);
    put16(rec, 4, crc16(log.subarray(start, start + length)));
    put32(rec, 8, start);
    put32(rec, 12, length);
    put32(rec, 16, length);
    rec.set(ascii(name), 64);
    log.set(xorStream(rec), 64 + index * 80);
  });
  const header = new Uint8Array(64);
  put32(header, 4, log.length);
  put16(header, 8, COUNT);
  put16(header, 10, 4);
  put32(header, 12, 512);
  header.set(ascii('AC791N'), 16);
  log.set(xorStream(header), 0);
  return repack(log);
}

/** The profile build_fwsc.stock_profile would pin for this synthetic stock package. */
async function profileFor(pkg) {
  const log = logicalImage(pkg);
  const header = xorStream(log.subarray(0, 64));
  const records = new Uint8Array(COUNT * 80);
  for (let i = 0; i < COUNT; i += 1) records.set(xorStream(log.subarray(64 + i * 80, 144 + i * 80)), i * 80);
  records.fill(0, 4, 6);
  const flash = log.subarray(FO, FO + FB);
  const masked = sfcDecode(flash.subarray(AREA), KEY);
  masked.fill(0, 0, 4);
  masked.fill(0, REC, REC + 4);
  masked.fill(0, REC + 8, REC + 12);
  masked.fill(0, ADDR, ADDR + SLOT);
  return {
    ...JSON.parse(JSON.stringify(V15_PROFILE)),
    id: 'synthetic-test',
    package_sha256: await sha256Hex(pkg),
    package_bytes: pkg.length,
    logical_bytes: log.length,
    entry_count: COUNT,
    flash_entry_index: 0,
    flash_offset: FO,
    flash_bytes: FB,
    header_meta_sha256: await sha256Hex(header.subarray(4)),
    entry_table_masked_sha256: await sha256Hex(records),
    pre_flash_sha256: await sha256Hex(log.subarray(64 + COUNT * 80, FO)),
    post_flash_sha256: await sha256Hex(log.subarray(FO + FB)),
    flash_head_sha256: await sha256Hex(flash.subarray(0, AREA)),
    app_area_offset: AREA,
    app_area_record_bytes: AREA_RECORD,
    app_record_offset: REC,
    app_offset: ADDR,
    app_slot_bytes: SLOT,
    app_area_masked_sha256: await sha256Hex(masked),
    vm_base: FB,
    sfc_key: KEY,
  };
}

function lunarApp(identity = 'FM-1_501', size = 0x80) {
  const app = pattern(size, 29, 7);
  app.set(ascii(`LUNAR\0${identity}\0`), 0);
  return app;
}

function install(stockLog, app, identity = 'FM-1_501') {
  const log = repack(stockLog, {
    area(area) {
      area.fill(0xff, ADDR, ADDR + SLOT);
      area.set(app, ADDR);
      put32(area, REC + 8, app.length);
    },
  });
  return physical(log, identity);
}

const STOCK_LOG = stockLogical();
const STOCK = physical(STOCK_LOG, 'FM-1_015');
const PROFILE = await profileFor(STOCK);
const LUNAR = install(STOCK_LOG, lunarApp());
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
