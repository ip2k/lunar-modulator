// SPDX-License-Identifier: MIT
// Release admission for FM-1 packages made by tools/jieli/build_fwsc.py.
//
// Admits exactly two kinds of package and rejects everything else:
//   * stock-rollback: the user's own stock V15 package, byte for byte
//     (SHA-256 pinned in V15_PROFILE);
//   * lunar-install: a package that is that same V15 with only the
//     application replaced, as build_fwsc.py makes it: identity FM-1_5xx,
//     app.bin inside V15's app slot with the rest of the slot 0xFF, every CRC
//     recomputed, and every other byte equal to stock (checked through pinned
//     hashes of the unchanged parts, so no vendor byte is needed here).
//
// The rules are the ones in build_fwsc.describe_package; both build the same
// manifest, and a manifest supplied with the package must equal it. Pure
// computation over the bytes given: no network, no storage, no device. The
// returned record has the shape native-ota-adapter.js expects from
// `packageAdmission.verify`.

export const ADMISSION_FORMAT = 'lunar-native-package-admission-v1';
export const MANIFEST_SCHEMA = 'lunar-fwsc-manifest-v1';
export const PROFILE_SCHEMA = 'lunar-fwsc-stock-profile-v1';
export const LUNAR_PRODUCT_RE = /^FM-1_5[0-9]{2}$/;
const FILL = 0xff;
const HEADER_SLOTS = 20;
const SLOT_BYTES = 48;

function deepFreeze(value) {
  if (value && typeof value === 'object') {
    for (const item of Object.values(value)) deepFreeze(item);
    Object.freeze(value);
  }
  return value;
}

// BEGIN V15_PROFILE (strict JSON; tests/test_build_fwsc.py checks it equals build_fwsc.V15_PROFILE)
export const V15_PROFILE = deepFreeze({
  "schema": "lunar-fwsc-stock-profile-v1",
  "id": "fm1-v15-stock",
  "product": "FM-1_015",
  "package_sha256": "db1642b2b6fa5c2cccb11ffd13878068bb28601678d3644049f99dc40e7edb8a",
  "package_bytes": 699956,
  "logical_bytes": 699936,
  "entry_count": 8,
  "flash_entry_index": 0,
  "flash_offset": 1024,
  "flash_bytes": 602112,
  "header_meta_sha256": "57c6d19ec0c84838824b1b458eb7a9b3dbda5dc0389d7f4edef253d26da64177",
  "entry_table_masked_sha256": "dc195f60dfb3e16a03eb39e03855f4cc8fce881c2a13d2afd5c220ab6144b168",
  "pre_flash_sha256": "1f34be94c0f6303063808553c7e906fedaf542afe7fc5d52040008ebfbe35038",
  "post_flash_sha256": "761a8be80e9a57f0ec2f76275ab996aca272c864f8832e230454f42ce6501160",
  "flash_head_sha256": "d9f43191777656de01c7bed4f9e9ba2e34e94832c5d2ed02c3fc7ab7a6d9bd67",
  "app_area_offset": 16384,
  "app_area_record_bytes": 582235,
  "app_record_offset": 32,
  "app_offset": 288,
  "app_slot_bytes": 581564,
  "app_area_masked_sha256": "d75f6e1a03e99fbf9242d00b35da8abdd4b7aeacfb0d307297be03fb35ca4876",
  "xip_entry": 33554720,
  "vm_base": 602112,
  "sfc_key": 38927,
  "spl_bytes": 14384,
  "components_sha256": {
    "top/uboot.boot": "730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef",
    "top/isd_config.ini": "0952afd96f533dd0fba72a8fab9cb4a4336f55424a1a89eecb13ff8a51a0eff0",
    "files/cfg": "962b3cbe3520502cf9ccd6a475b60e366b762ead371f0975a386c09c46201766",
    "ota.bin": "ef1f2db89b011fa53e71df363f0122de0ea896618c53fb53e8da676322004541",
    "files/cfg_tool.bin": "276579954f076886a6a7694f65dc71c034a63a2c204b76749065c0ac7b010d1b",
    "files/eq_cfg_hw.bin": "697b4fd0a82dae4a80f83180101a61de7d9e1fc951188e671350b18403c97007"
  }
});
// END V15_PROFILE

const CRC_TABLE = (() => {
  const table = new Uint16Array(256);
  for (let n = 0; n < 256; n += 1) {
    let crc = n << 8;
    for (let bit = 0; bit < 8; bit += 1) crc = crc & 0x8000 ? ((crc << 1) ^ 0x1021) & 0xffff : (crc << 1) & 0xffff;
    table[n] = crc;
  }
  return table;
})();

/** CRC-16/XMODEM (poly 0x1021, init 0), as inspect_fwsc.crc16. */
export function crc16(bytes) {
  let crc = 0;
  for (let i = 0; i < bytes.length; i += 1) crc = ((crc << 8) & 0xffff) ^ CRC_TABLE[((crc >>> 8) ^ bytes[i]) & 0xff];
  return crc;
}

/** The symmetric ENC XOR stream (inspect_fwsc.header_decode). */
export function xorStream(bytes, initial = 0xffff) {
  const out = new Uint8Array(bytes.length);
  let state = initial;
  for (let i = 0; i < bytes.length; i += 1) {
    out[i] = bytes[i] ^ (state & 0xff);
    state = ((state << 1) ^ (state & 0x8000 ? 0x1021 : 0)) & 0xffff;
  }
  return out;
}

/** SFC blocks of 32 bytes keyed key ^ (offset >> 2), origin zero (inspect_fwsc.sfc_decode). */
export function sfcDecode(bytes, key) {
  const out = new Uint8Array(bytes.length);
  for (let block = 0; block < bytes.length; block += 32) {
    out.set(xorStream(bytes.subarray(block, block + 32), key ^ (block >>> 2)), block);
  }
  return out;
}

export async function sha256Hex(bytes) {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) throw new Error('Web Crypto SHA-256 is required');
  const digest = new Uint8Array(await subtle.digest('SHA-256', bytes));
  return [...digest].map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

/** Keys sorted at every level: equal to Python json.dumps(sort_keys=True, separators=(',', ':')). */
export function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(',')}}`;
  }
  if (typeof value === 'number' && !Number.isSafeInteger(value)) throw new TypeError('manifest numbers are integers');
  return JSON.stringify(value);
}

export function markersIdentity(bytes) {
  if (bytes.length < HEADER_SLOTS * SLOT_BYTES) throw new Error('truncated FWSC header');
  const markers = [];
  for (let i = 0; i < HEADER_SLOTS; i += 1) markers.push(bytes[i * SLOT_BYTES + SLOT_BYTES - 1]);
  let end = markers.indexOf(125);
  if (end < 0) end = HEADER_SLOTS;
  if (markers.slice(end).some((value) => value !== 125)) throw new Error('FWSC identity markers are not contiguous');
  const text = String.fromCharCode(...markers.slice(0, end).map((value, i) => (value - i - 1) & 0xff));
  if (!/^FM-1_[0-9]{3}$/.test(text)) throw new Error('not an FM-1 FWSC identity');
  return text;
}

export function logicalImage(bytes) {
  const keep = SLOT_BYTES - 1;
  const out = new Uint8Array(bytes.length - HEADER_SLOTS);
  for (let i = 0; i < HEADER_SLOTS; i += 1) out.set(bytes.subarray(i * SLOT_BYTES, i * SLOT_BYTES + keep), i * keep);
  out.set(bytes.subarray(HEADER_SLOTS * SLOT_BYTES), HEADER_SLOTS * keep);
  return out;
}

const u16 = (bytes, at) => bytes[at] | (bytes[at + 1] << 8);
const u32 = (bytes, at) => (bytes[at] | (bytes[at + 1] << 8) | (bytes[at + 2] << 16) | (bytes[at + 3] << 24)) >>> 0;

function productLiterals(app) {
  // FM-1_ddd\0, as build_fwsc's rb'FM-1_[0-9]{3}\x00'.
  const found = [];
  const prefix = [0x46, 0x4d, 0x2d, 0x31, 0x5f];
  for (let i = 0; i + 9 <= app.length; i += 1) {
    if (!prefix.every((byte, k) => app[i + k] === byte)) continue;
    const digits = [app[i + 5], app[i + 6], app[i + 7]];
    if (digits.every((d) => d >= 0x30 && d <= 0x39) && app[i + 8] === 0) {
      found.push({ offset: i, product: String.fromCharCode(...prefix, ...digits) });
      i += 8;
    }
  }
  return found;
}

function mutableRanges(profile) {
  const base = profile.app_area_offset;
  const rec = profile.app_record_offset;
  const ranges = [[base, base + 4], [base + rec, base + rec + 4], [base + rec + 8, base + rec + 12],
    [base + profile.app_offset, base + profile.app_offset + profile.app_slot_bytes]];
  return ranges.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
}

/**
 * Check a package against one pinned stock profile and return its manifest
 * (the same object build_fwsc.describe_package returns). Throws on any
 * departure from the builder's rules.
 */
export async function describeLunarPackage(input, profile = V15_PROFILE) {
  if (!(input instanceof Uint8Array)) throw new TypeError('package must be supplied as Uint8Array');
  if (profile?.schema !== PROFILE_SCHEMA) throw new TypeError('unsupported stock profile');
  const pkg = input;
  if (pkg.length !== profile.package_bytes) {
    throw new Error(`package is ${pkg.length} B; the pinned profile has ${profile.package_bytes} B`);
  }
  const product = markersIdentity(pkg);
  const log = logicalImage(pkg);
  const fo = profile.flash_offset;
  const fb = profile.flash_bytes;
  const packageSha = await sha256Hex(pkg);
  const common = {
    schema: MANIFEST_SCHEMA,
    profile: profile.id,
    stock: { product: profile.product, package_sha256: profile.package_sha256 },
    stock_components_sha256: { ...profile.components_sha256 },
    model: 'FM-1',
    product,
    version: Number(product.slice(5)),
    package: { bytes: pkg.length, sha256: packageSha, logical_bytes: log.length, logical_sha256: await sha256Hex(log) },
  };
  const flash = { payload_bytes: fb, write_range: [profile.app_area_offset, profile.vm_base],
    head_range: [0, profile.app_area_offset], head_sha256: profile.flash_head_sha256, vm_base: profile.vm_base };
  if (packageSha === profile.package_sha256) {
    if (product !== profile.product) throw new Error('stock bytes with a foreign identity');
    return { ...common, kind: 'stock-rollback', flash: { ...flash, mutable_ranges: [] }, app: null };
  }
  if (!LUNAR_PRODUCT_RE.test(product)) {
    throw new Error(`identity ${product} is neither the pinned stock package nor a Lunar FM-1_5xx`);
  }
  if (fb !== profile.vm_base) throw new Error('profile flash.bin does not end where VM begins');
  const header = xorStream(log.subarray(0, 64));
  if (crc16(header.subarray(2)) !== u16(header, 0)) throw new Error('UFW header CRC mismatch');
  if (await sha256Hex(header.subarray(4)) !== profile.header_meta_sha256) throw new Error('UFW header metadata differs from stock');
  const count = u16(header, 8);
  if (u32(header, 4) !== log.length || count !== profile.entry_count) throw new Error('UFW size or entry count differs from stock');
  const tableEnd = 64 + count * 80;
  if (crc16(log.subarray(64, tableEnd)) !== u16(header, 2)) throw new Error('UFW entry-list CRC mismatch');
  const records = new Uint8Array(count * 80);
  let flashCrc = null;
  for (let index = 0; index < count; index += 1) {
    const rec = xorStream(log.subarray(64 + index * 80, 144 + index * 80));
    if (index === profile.flash_entry_index) {
      flashCrc = u16(rec, 4);
      rec[4] = 0;
      rec[5] = 0;
    }
    records.set(rec, index * 80);
  }
  if (await sha256Hex(records) !== profile.entry_table_masked_sha256) {
    throw new Error('UFW entry records differ from stock beyond the flash.bin CRC');
  }
  if (await sha256Hex(log.subarray(tableEnd, fo)) !== profile.pre_flash_sha256) {
    throw new Error('bytes between the entry list and flash.bin differ from stock');
  }
  if (await sha256Hex(log.subarray(fo + fb)) !== profile.post_flash_sha256) {
    throw new Error('entries after flash.bin (USR, isd_config, ota.bin, tail) differ from stock');
  }
  const payload = log.subarray(fo, fo + fb);
  if (crc16(payload) !== flashCrc) throw new Error('flash.bin CRC mismatch');
  if (await sha256Hex(payload.subarray(0, profile.app_area_offset)) !== profile.flash_head_sha256) {
    throw new Error('flash head differs from stock: the bootloader would change');
  }
  const area = sfcDecode(payload.subarray(profile.app_area_offset), profile.sfc_key);
  const rec = profile.app_record_offset;
  const addr = profile.app_offset;
  const slot = profile.app_slot_bytes;
  if (crc16(area.subarray(2, 32)) !== u16(area, 0) ||
      crc16(area.subarray(32, profile.app_area_record_bytes)) !== u16(area, 2)) {
    throw new Error('app_area_head CRC mismatch');
  }
  if (crc16(area.subarray(rec + 2, rec + 32)) !== u16(area, rec)) throw new Error('app.bin record CRC mismatch');
  const size = u32(area, rec + 8);
  if (u32(area, rec + 4) !== addr || !(size > 0 && size <= slot)) {
    throw new Error('app.bin record placement or size outside the stock slot');
  }
  const app = area.slice(addr, addr + size);
  if (crc16(app) !== u16(area, rec + 2)) throw new Error('app.bin data CRC mismatch');
  for (let i = addr + size; i < addr + slot; i += 1) {
    if (area[i] !== FILL) throw new Error('unused app slot is not 0xFF fill');
  }
  const masked = area.slice();
  masked.fill(0, 0, 4);
  masked.fill(0, rec, rec + 4);
  masked.fill(0, rec + 8, rec + 12);
  masked.fill(0, addr, addr + slot);
  if (await sha256Hex(masked) !== profile.app_area_masked_sha256) {
    throw new Error('app directory, cfg or reserved descriptors differ from stock');
  }
  const literals = productLiterals(app);
  if (literals.length !== 1 || literals[0].product !== product) {
    throw new Error(`app must carry ${product}\\0 exactly once and no other FM-1_nnn literal`);
  }
  return {
    ...common,
    kind: 'lunar-install',
    flash: { ...flash, mutable_ranges: mutableRanges(profile) },
    app: { bytes: size, sha256: await sha256Hex(app), flash_offset: addr + profile.app_area_offset,
      slot_bytes: slot, spare_bytes: slot - size, fill: FILL, identity_offset: literals[0].offset,
      xip_entry: profile.xip_entry },
  };
}

function manifestObject(manifest) {
  if (manifest === undefined || manifest === null) return null;
  if (typeof manifest === 'string') return JSON.parse(manifest);
  if (manifest instanceof Uint8Array) return JSON.parse(new TextDecoder().decode(manifest));
  if (typeof manifest === 'object') return manifest;
  throw new TypeError('manifest must be JSON text, bytes or an object');
}

/**
 * Admission for native-ota-adapter.js: resolves to an admission record, or
 * rejects with "package admission blocked: <reason>". `manifest`, when given,
 * must equal the manifest computed from the bytes. `profiles` exists for
 * offline tests; the installer passes nothing and gets the pinned V15 only.
 */
export async function verifyNativePackage(input, { manifest, profiles = [V15_PROFILE] } = {}) {
  if (!(input instanceof Uint8Array)) throw new TypeError('package must be supplied as Uint8Array');
  const bytes = Uint8Array.from(input);
  const reasons = [];
  for (const profile of profiles) {
    let described;
    try {
      described = await describeLunarPackage(bytes, profile);
    } catch (error) {
      reasons.push(error instanceof Error ? error.message : String(error));
      continue;
    }
    let supplied;
    try {
      supplied = manifestObject(manifest);
    } catch (error) {
      throw new Error(`package admission blocked: manifest is not valid JSON (${error.message})`);
    }
    if (supplied !== null && canonicalJson(supplied) !== canonicalJson(described)) {
      throw new Error('package admission blocked: the manifest does not match the package');
    }
    const image = logicalImage(bytes);
    return Object.freeze({
      format: ADMISSION_FORMAT,
      kind: described.kind,
      product: described.product,
      model: described.model,
      version: described.version,
      packageSha256: described.package.sha256,
      logicalImage: image,
      logicalImageSha256: described.package.logical_sha256,
      manifest: deepFreeze(described),
    });
  }
  throw new Error(`package admission blocked: ${reasons.join('; ') || 'no pinned stock profile'}`);
}
