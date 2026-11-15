// SPDX-License-Identifier: MIT
// Synthetic FWSC packages for offline admission tests: a small package with
// V15's structure, built here, so no vendor byte is needed. Shared by
// lunar-package-admission.test.mjs and the install-panel tests. Pure
// computation; nothing is sent anywhere.
import {
  V15_PROFILE, crc16, logicalImage, sfcDecode, sha256Hex, xorStream,
} from '../www/lunar-package-admission.js';

export const AREA = 0x400;     // flash head [0, AREA); app area after it (V15: 0x4000)
export const REC = 0x20;
export const ADDR = 0x120;
export const SLOT = 0x200;
export const AREA_RECORD = 0x400;
export const AREA_BYTES = 0x800;
export const FB = AREA + AREA_BYTES;
export const FO = 0x200;
export const COUNT = 3;
export const KEY = 0x980f;

export const u16 = (b, at) => b[at] | (b[at + 1] << 8);
export const put16 = (b, at, v) => { b[at] = v & 255; b[at + 1] = (v >>> 8) & 255; };
export const put32 = (b, at, v) => { for (let i = 0; i < 4; i += 1) b[at + i] = (v >>> (8 * i)) & 255; };
export const ascii = (text) => Uint8Array.from(text, (c) => c.charCodeAt(0));
export const pattern = (n, mul, add = 0) => Uint8Array.from({ length: n }, (_, i) => (i * mul + add) & 255);

export function physical(log, identity) {
  const out = new Uint8Array(log.length + 20);
  for (let i = 0; i < 20; i += 1) {
    out.set(log.subarray(i * 47, (i + 1) * 47), i * 48);
    out[i * 48 + 47] = i < identity.length ? identity.charCodeAt(i) + i + 1 : 125;
  }
  out.set(log.subarray(940), 960);
  return out;
}

/** Re-derive every CRC in a logical image, after `edit(area)` / `editLog(log)`. */
export function repack(log, { area: editArea, log: editLog, appRecord = true } = {}) {
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

export function stockLogical() {
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
export async function profileFor(pkg) {
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

export function lunarApp(identity = 'FM-1_501', size = 0x80) {
  const app = pattern(size, 29, 7);
  app.set(ascii(`LUNAR\0${identity}\0`), 0);
  return app;
}

export function install(stockLog, app, identity = 'FM-1_501') {
  const log = repack(stockLog, {
    area(area) {
      area.fill(0xff, ADDR, ADDR + SLOT);
      area.set(app, ADDR);
      put32(area, REC + 8, app.length);
    },
  });
  return physical(log, identity);
}

export const STOCK_LOG = stockLogical();
export const STOCK = physical(STOCK_LOG, 'FM-1_015');
export const PROFILE = await profileFor(STOCK);
export const LUNAR = install(STOCK_LOG, lunarApp());
