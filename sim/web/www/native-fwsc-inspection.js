// SPDX-License-Identifier: MIT
// Outer-envelope inspection, aligned with tools/jieli/inspect_fwsc.py.
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
  return Object.freeze({ identity, chip: 'AC791N', physicalBytes: raw.length, logicalBytes: logical.length,
    headerCrcVerified: true, entryListCrcVerified: true, entries: Object.freeze(entries),
    admissible: false, nestedFlashVerified: false, releaseAccepted: false });
}
