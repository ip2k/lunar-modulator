// SPDX-License-Identifier: MIT
// Bounded envelope and known nested-profile inspection; never release admission.
// Successful CRC checks are not a release or installation capability.
const PREFIX = 960;
const LOGICAL_PREFIX = 940;
const PLAIN_TYPES = new Set([0, 2, 100, 255]);
const ENCRYPTED_TYPES = new Set([50, 52, 251, 161]);

function crc16(bytes) {
  let state = 0;
  for (const byte of bytes) {
    state ^= byte << 8;
    for (let bit = 0; bit < 8; bit += 1) state = ((state << 1) ^ (state & 0x8000 ? 0x1021 : 0)) & 0xffff;
  }
  return state;
}

function decode(bytes, initial = 0xffff) {
  let state = initial;
  return Uint8Array.from(bytes, (byte) => {
    const result = byte ^ (state & 0xff);
    state = ((state << 1) ^ (state & 0x8000 ? 0x1021 : 0)) & 0xffff;
    return result;
  });
}

function cstring(bytes) {
  const end = bytes.indexOf(0);
  if (end < 0 || bytes.slice(end).some((byte) => byte !== 0)) throw new Error('unterminated or nonzero-padded name');
  if (bytes.slice(0, end).some((byte) => byte > 127)) throw new Error('non-ASCII name');
  return String.fromCharCode(...bytes.slice(0, end));
}

function payloadCrc(bytes, kind, offset) {
  if (!ENCRYPTED_TYPES.has(kind)) return crc16(bytes);
  if (offset % 32) throw new Error('unaligned SFC auxiliary payload');
  const plain = new Uint8Array(bytes.length);
  for (let index = 0; index < bytes.length; index += 32) {
    plain.set(decode(bytes.subarray(index, index + 32), 0x980f ^ ((offset + index) >>> 2)), index);
  }
  return crc16(plain);
}

// Inspection profile derived from model_092_app_replacement._flash_parse.
// Fixed extent bounds every allocation; no decoded bytes escape this function.
function inspect092(flash) {
  const fail = (message) => { throw new Error(`092 nested ${message}`); };
  if (flash.length !== 0xd7000) fail('D7000 extent mismatch');
  const bounded = (data, offset, size) => {
    if (offset < 0 || size < 0 || offset + size > data.length) fail('record/data bounds');
    return data.subarray(offset, offset + size);
  };
  const record = (data, offset) => {
    const raw = bounded(data, offset, 32);
    const v = new DataView(raw.buffer, raw.byteOffset, raw.byteLength);
    if (crc16(raw.subarray(2)) !== v.getUint16(0, true)) fail('JLFS header CRC mismatch');
    const flags = raw[12], nameBytes = raw.subarray(16), end = nameBytes.indexOf(0);
    if (end < 0 || nameBytes.subarray(0, end).some((x) => x > 127)
        || (!(flags & 0x10) && nameBytes.subarray(end + 1).some((x) => x !== 0 && x !== 255))) fail('record name');
    return { name: String.fromCharCode(...nameBytes.subarray(0, end)), address: v.getUint32(4, true),
      bytes: v.getUint32(8, true), flags, reserved: raw[13], terminal: v.getUint16(14, true),
      crc: v.getUint16(2, true) };
  };
  const expect = (r, name, address, bytes, flags, terminal, sentinel = false) => {
    if (r.name !== name || r.address !== address || r.bytes !== bytes || r.flags !== flags
        || r.reserved !== 0 || r.terminal !== terminal || (sentinel && r.crc !== 65535)) fail(`profile geometry: ${name}`);
  };
  const check = (r, data) => { if (crc16(data) !== r.crc) fail(`data CRC: ${r.name}`); };
  const head = decode(flash.subarray(0, 32));
  if (crc16(head.subarray(2)) !== new DataView(head.buffer).getUint16(0, true)) fail('flash header CRC mismatch');
  const top = [32, 64, 96, 128].map((offset) => record(decode(flash.subarray(offset, offset + 32)), 0));
  const [spl, config, appDirectory, key] = top;
  expect(spl, 'uboot.boot', 0xa0, 14384, 0, 0);
  expect(config, 'isd_config.ini', 0x38d0, 699, 2, 0);
  expect(appDirectory, 'app_dir_head', 0x4000, 0xffffffff, 0x81, 0, true);
  expect(key, 'key_mac', 0xff000, 0x1000, 0x12, 0xffff, true);
  const configData = bounded(flash, config.address, config.bytes);
  check(config, configData);
  if (crc16(configData.subarray(0, 32)) !== new DataView(configData.buffer, configData.byteOffset).getUint16(32, true)) fail('chip-key CRC');
  let threshold = configData.subarray(0, 16).reduce((sum, x) => sum + x, 0) & 255;
  threshold = threshold >= 0xe0 ? 0xaa : threshold <= 0x10 ? 0x55 : threshold;
  let chipKey = 0;
  for (let i = 0; i < 16; i += 1) if ((configData[16 + i] ^ configData[15 - i]) < threshold) chipKey |= 1 << i;
  if (chipKey !== 0x980f) fail('unsupported chip key');
  const splData = new Uint8Array(spl.bytes);
  splData.set(decode(flash.subarray(0xa0, 0xb0)));
  splData.set(decode(flash.subarray(0xb0, 0x38d0)), 16);
  const bank = new DataView(splData.buffer);
  if (crc16(splData.subarray(0, 14)) !== bank.getUint16(14, true)
      || bank.getUint16(0, true) !== 1 || bank.getUint16(2, true) !== 14368
      || bank.getUint32(4, true) !== 0x01c02000 || bank.getUint32(8, true) !== 16
      || crc16(splData.subarray(16)) !== bank.getUint16(12, true)) fail('SPL bank geometry/CRC');
  check(spl, splData);
  const region = new Uint8Array(flash.length - 0x4000);
  for (let i = 0; i < region.length; i += 32) region.set(decode(flash.subarray(0x4000 + i, 0x4020 + i), chipKey ^ (i >>> 2)), i);
  const area = record(region, 0);
  if (area.name !== 'app_area_head' || area.flags !== 0x83 || area.address !== 0x02000120
      || area.reserved !== 0 || area.terminal !== 0 || area.bytes < 224) fail('application area geometry');
  check(area, bounded(region, 32, area.bytes - 32));
  const children = Array.from({ length: 6 }, (_, i) => record(region, 32 + i * 32));
  const [app, tool] = children;
  expect(app, 'app.bin', 0x120, app.bytes, 0x82, 0);
  if (!app.bytes) fail('empty app');
  expect(tool, 'cfg_tool.bin', 0x120 + app.bytes, 383, 0x82, 0);
  const reserved = [['VM', 0xd9000, 0x10000, 0x12], ['PRCT', 0, 0xd9000, 0x92],
    ['BTIF', 0xe9000, 0x1000, 0x92], ['USR', 0xea000, 0x12000, 0x92]];
  reserved.forEach(([name, address, size, flags], i) => expect(children[i + 2], name, address, size, flags, i === 3 ? 1 : 0, true));
  if (area.bytes !== tool.address + tool.bytes) fail('app/tool extent or overlap');
  check(app, bounded(region, app.address, app.bytes));
  check(tool, bounded(region, tool.address, tool.bytes));
  const cfg = record(region, area.bytes);
  expect(cfg, 'cfg', 32, 2937, 0x83, 1);
  check(cfg, bounded(region, area.bytes + 32, cfg.bytes - 32));
  const cfgEnd = 0x4000 + area.bytes + cfg.bytes;
  bounded(region, area.bytes + cfg.bytes, 968);
  const summary = (r) => Object.freeze({ name: r.name, address: r.address, bytes: r.bytes,
    flags: r.flags, headerCrcVerified: true, dataCrcVerified: !['app_dir_head', 'key_mac', 'VM', 'PRCT', 'BTIF', 'USR'].includes(r.name) });
  return Object.freeze({ profile: 'FM-1_092-D7000', status: 'structure-crc-verified',
    flashBytes: flash.length, appBytes: app.bytes, cfgEnd, opaqueSuffixBytes: flash.length - cfgEnd,
    records: Object.freeze([...top, area, ...children, cfg].map(summary)),
    protectedStockCorrespondence: 'unverified', opaqueSuffixSemantics: 'unverified',
    deviceBehavior: 'unverified', admissible: false, releaseAccepted: false });
}

/** Validate established outer FWSC fields without exposing bytes to a flasher. */
export function inspectFwscEnvelope(raw) {
  if (!(raw instanceof Uint8Array)) throw new TypeError('package must be supplied as Uint8Array');
  // The FM1 has 1 MiB flash. Bound parsing/allocation before copying input.
  if (raw.length < PREFIX || raw.length > 2 * 1024 * 1024) throw new Error('FWSC size outside inspection bounds');
  const markers = Array.from({ length: 20 }, (_, index) => raw[index * 48 + 47]);
  const end = markers.indexOf(125);
  if (end < 0 || markers.slice(end).some((byte) => byte !== 125)) throw new Error('noncontiguous identity markers');
  const identity = markers.slice(0, end).map((byte, index) => String.fromCharCode((byte - index - 1) & 0xff)).join('');
  if (!/^FM-1_[0-9]{3}$/.test(identity)) throw new Error('unsupported FWSC identity');
  const logical = new Uint8Array(raw.length - 20);
  for (let index = 0; index < 20; index += 1) logical.set(raw.subarray(index * 48, index * 48 + 47), index * 47);
  logical.set(raw.subarray(PREFIX), LOGICAL_PREFIX);
  const header = decode(logical.subarray(0, 64));
  const view = new DataView(header.buffer);
  if (crc16(header.subarray(2)) !== view.getUint16(0, true)) throw new Error('UFW header CRC mismatch');
  if (view.getUint32(4, true) !== logical.length) throw new Error('UFW logical size mismatch');
  if (cstring(header.subarray(16)) !== 'AC791N') throw new Error('unsupported UFW chip');
  const count = view.getUint16(8, true);
  if (count < 1 || count > Math.floor((LOGICAL_PREFIX - 64) / 80)) throw new Error('entry list exceeds established FWSC header slots');
  const table = logical.subarray(64, 64 + count * 80);
  if (crc16(table) !== view.getUint16(2, true)) throw new Error('UFW stored entry-list CRC mismatch');
  const entries = [];
  for (let index = 0; index < count; index += 1) {
    const item = decode(table.subarray(index * 80, (index + 1) * 80));
    const fields = new DataView(item.buffer);
    const kind = fields.getUint16(0, true);
    const checksum = fields.getUint16(4, true);
    const offset = fields.getUint32(8, true);
    const size = fields.getUint32(12, true);
    const allocated = fields.getUint32(16, true);
    const name = cstring(item.subarray(64));
    if (fields.getUint16(2, true) !== index || entries.some((entry) => entry.name === name)) throw new Error('duplicate name or unexpected entry index');
    if (!PLAIN_TYPES.has(kind) && !ENCRYPTED_TYPES.has(kind)) throw new Error('unsupported payload type');
    if (allocated < size || offset < LOGICAL_PREFIX || offset + allocated > logical.length) throw new Error('entry allocation outside logical image');
    if (allocated && entries.some((entry) => entry.allocatedBytes && offset < entry.offset + entry.allocatedBytes && entry.offset < offset + allocated)) throw new Error('overlapping entry allocations');
    if (payloadCrc(logical.subarray(offset, offset + size), kind, offset) !== checksum) throw new Error(`payload CRC mismatch: ${name}`);
    entries.push(Object.freeze({ name, type: kind, offset, bytes: size, allocatedBytes: allocated, crcVerified: true }));
  }
  const byName = new Map(entries.map((entry) => [entry.name, entry]));
  if (byName.get('flash.bin')?.type !== 0 || byName.get('ota.bin')?.type !== 100) throw new Error('missing established flash/OTA entries');
  const tail = byName.get('tail.bin');
  if (tail?.type !== 255 || tail.offset + tail.bytes !== logical.length || String.fromCharCode(...logical.subarray(logical.length - 16, logical.length - 11)) !== 'JLUFW') throw new Error('missing UFW trailer');
  const flash = byName.get('flash.bin');
  // Source 092 and Lunar 5xx identities match the trusted Python tuple policy.
  // Identity selects an inspection profile; it establishes no source provenance.
  const nestedInspection = (identity === 'FM-1_092' || /^FM-1_5[0-9]{2}$/.test(identity)) ? inspect092(logical.subarray(flash.offset, flash.offset + flash.bytes))
    : Object.freeze({ status: 'unsupported-profile', protectedStockCorrespondence: 'unverified', admissible: false, releaseAccepted: false });
  return Object.freeze({ identity, chip: 'AC791N', physicalBytes: raw.length, logicalBytes: logical.length,
    headerCrcVerified: true, entryListCrcVerified: true, entries: Object.freeze(entries),
    admissible: false, nestedFlashVerified: nestedInspection.status === 'structure-crc-verified', nestedInspection, releaseAccepted: false });
}
