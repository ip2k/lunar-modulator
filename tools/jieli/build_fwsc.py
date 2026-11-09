#!/usr/bin/env python3
"""tools/jieli/build_fwsc.py -- build a Lunar install package, or a roll-back
package, from the user's OWN stock V15 `.fwsc` (docs/18 milestone M12).

Nothing here downloads, bundles or transmits anything. The stock package is a
path the user supplies; the outputs are files next to it. No device is opened.

install   stock V15 + a Lunar `app.bin` -> `<out>.fwsc` + `<out>.fwsc.manifest.json`
rollback  stock V15 -> a verified, byte-identical copy + its manifest
verify    re-check a package (and optionally its manifest) against the pinned
          profile, exactly as the browser's admission verifier does
profile   print the profile computed from a stock package, for review of the pin

What an install package is (every rule is checked again on the output):

  * The input is the stock V15 package, pinned by SHA-256 (`STOCK_PROFILES`):
    the M-VAVE CDN copy and Baud Girl's saved reference copy are the same
    file, `db1642b2...` [verified: both hashed 2026-11-08]. Any other input is
    refused, so every byte the output keeps is known in advance and the
    browser can check it from pinned hashes alone.
  * The stock tree is decoded in memory, staged, passed through
    `package_guard.check_package` (SPL pin 730e54f0..., isd_config.ini,
    ota.bin and cfg) and `inspect_stock_flash.inspect_nested` (every nested
    CRC and a byte-exact no-op rebuild of the whole container).
  * Only the application changes. `app.bin` is written over V15's app slot
    (flash 0x4120, 581,564 B, ending where `cfg_tool.bin` begins at 0x920DC
    [verified: V15 directory]); the rest of the slot is filled with 0xFF
    (decoded), so no stock application code is left in it. The app child
    record (size, data CRC, header CRC), the `app_area_head` record (data and
    header CRC), the outer `flash.bin` CRC, the entry-list CRC and the UFW
    header CRC are recomputed; nothing else in the container changes.
  * The flash head [0, 0x4000) (SPL, isd_config, top directory) is
    byte-identical, so the OTA loader cannot rewrite the bootloader with
    anything new (docs/03 §5, docs/07 §4 rule 2). Every changed flash byte
    lies in [0x4000, 0x93000). `flash.bin` is exactly 0x93000 bytes, so the
    package holds nothing for VM at 0x93000 and up, and the JLFS descriptors
    for VM, PRCT, BTIF, USR and key_mac are unchanged.
  * The package identity (the 20 marker bytes of the FWSC header, no CRC)
    becomes the Lunar identity, `FM-1_5xx` (the range DEVELOPERS.md plans,
    clear of M-VAVE <= 019, Baud Girl 020+ and Felucca/SLOOP 9xx [reported:
    docs/03 §5]). The app must carry that identity exactly once as a
    NUL-terminated literal and no other `FM-1_nnn` literal: the stock step-1
    verifier refuses a package of the running version and accepts a new one
    [reported: Baud Girl measured FM-1_078 <-> FM-1_079 both ways; Echomatter
    FM-1_016, docs/03 §5], and Baud Girl's FM-1_092 renamed the app's
    identity in place with cfg unchanged [verified: package diff,
    notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md §3]. Device acceptance
    of a Lunar package is not verified: no package has been sent.
  * The app must fit the slot by `fm1_budget.measure` (with `--elf`, also the
    SRAM and cache-RAM checks).

A roll-back package is the user's stock V15 itself, verified as above and
copied byte-for-byte: a device running a Lunar identity takes a stock
FM-1_015 package as a new version [reported: Echomatter rolled back FM-1_016
to V15; Baud Girl rolls back to V15]. It works only while the running Lunar
app answers the stock update protocol.

Facts on the version bump come from Felucca/SLOOP's documentation and
AL-255's notes (docs/03 §5); no GPL code is used here. MIT licence.
"""
import argparse
import hashlib
import json
import re
import struct
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fm1_budget  # noqa: E402
import inspect_stock_flash as nested  # noqa: E402
from audit_link import Elf  # noqa: E402
from inspect_fwsc import STOCK_CHIP_KEY, crc16, header_decode, inspect, sfc_decode  # noqa: E402
from model_app_replacement import checksum_record, logical, physical, repair_outer  # noqa: E402
from package_guard import STOCK_SPL_SHA256, STOCK_SPL_SIZE, check_package  # noqa: E402

MANIFEST_SCHEMA = 'lunar-fwsc-manifest-v1'
PROFILE_SCHEMA = 'lunar-fwsc-stock-profile-v1'
LUNAR_PRODUCT_RE = re.compile(r'FM-1_5[0-9]{2}')
ANY_PRODUCT_LITERAL = re.compile(rb'FM-1_[0-9]{3}\x00')
APP_AREA = nested.APP_BASE          # 0x4000: the first byte the package may change
VM_BASE = 0x93000                   # V15's VM partition [verified: V15 directory]
WRITE_RANGE = (APP_AREA, VM_BASE)
FILL = 0xFF

# The pinned stock profile. Every value is computed by `stock_profile()` from
# the stock V15 package (SHA-256 db1642b2...) and checked against it by the
# opt-in real-file test; sim/web/www/lunar-package-admission.js carries the
# same object (tests/test_build_fwsc.py compares them). Hashes, offsets and
# sizes only: no vendor bytes.
V15_PROFILE = {
    'schema': 'lunar-fwsc-stock-profile-v1',
    'id': 'fm1-v15-stock',
    'product': 'FM-1_015',
    'package_sha256': 'db1642b2b6fa5c2cccb11ffd13878068bb28601678d3644049f99dc40e7edb8a',
    'package_bytes': 699956,
    'logical_bytes': 699936,
    'entry_count': 8,
    'flash_entry_index': 0,
    'flash_offset': 0x400,
    'flash_bytes': 602112,
    'header_meta_sha256': '57c6d19ec0c84838824b1b458eb7a9b3dbda5dc0389d7f4edef253d26da64177',
    'entry_table_masked_sha256': 'dc195f60dfb3e16a03eb39e03855f4cc8fce881c2a13d2afd5c220ab6144b168',
    'pre_flash_sha256': '1f34be94c0f6303063808553c7e906fedaf542afe7fc5d52040008ebfbe35038',
    'post_flash_sha256': '761a8be80e9a57f0ec2f76275ab996aca272c864f8832e230454f42ce6501160',
    'flash_head_sha256': 'd9f43191777656de01c7bed4f9e9ba2e34e94832c5d2ed02c3fc7ab7a6d9bd67',
    'app_area_offset': 0x4000,
    'app_area_record_bytes': 582235,
    'app_record_offset': 0x20,
    'app_offset': 0x120,
    'app_slot_bytes': 581564,
    'app_area_masked_sha256': 'd75f6e1a03e99fbf9242d00b35da8abdd4b7aeacfb0d307297be03fb35ca4876',
    'xip_entry': 0x2000120,
    'vm_base': 0x93000,
    'sfc_key': 0x980f,
    'spl_bytes': 14384,
    'components_sha256': {
        'top/uboot.boot': '730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef',
        'top/isd_config.ini': '0952afd96f533dd0fba72a8fab9cb4a4336f55424a1a89eecb13ff8a51a0eff0',
        'files/cfg': '962b3cbe3520502cf9ccd6a475b60e366b762ead371f0975a386c09c46201766',
        'ota.bin': 'ef1f2db89b011fa53e71df363f0122de0ea896618c53fb53e8da676322004541',
        'files/cfg_tool.bin': '276579954f076886a6a7694f65dc71c034a63a2c204b76749065c0ac7b010d1b',
        'files/eq_cfg_hw.bin': '697b4fd0a82dae4a80f83180101a61de7d9e1fc951188e671350b18403c97007',
    },
}
STOCK_PROFILES = {V15_PROFILE['package_sha256']: V15_PROFILE}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    """The manifest's comparison form; the browser builds the same string."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def markers_identity(raw):
    markers = [raw[i * 48 + 47] for i in range(20)]
    end = next((i for i, value in enumerate(markers) if value == 125), 20)
    if any(value != 125 for value in markers[end:]):
        raise ValueError('FWSC identity markers are not contiguous')
    return bytes((value - i - 1) & 255 for i, value in enumerate(markers[:end])).decode('ascii')


def set_identity(raw, identity):
    """The FWSC identity is the 20 marker bytes; no CRC covers them."""
    if not re.fullmatch(r'FM-1_[0-9]{3}', identity):
        raise ValueError(f'unsupported identity {identity!r}: expected FM-1_nnn')
    out = bytearray(raw)
    for i in range(20):
        out[i * 48 + 47] = (ord(identity[i]) + i + 1) & 255 if i < len(identity) else 125
    if markers_identity(out) != identity:
        raise ValueError('identity does not round-trip through the marker encoding')
    return bytes(out)


def _app_geometry(area):
    """Locate app.bin in the decoded app area: (area record, child offset, child)."""
    head = nested.record(area, 0)
    if head['name'] != 'app_area_head' or head['flags'] != 0x83:
        raise ValueError('app area does not start with app_area_head')
    for index in range(6):
        child = nested.record(area, 32 + index * 32)
        if child['name'] == 'app.bin' and child['flags'] == 0x82:
            return head, 32 + index * 32, child
        if child['terminal']:
            break
    raise ValueError('app.bin not found in the app directory')


def stock_profile(raw, components):
    """Compute the pinnable profile of a stock package from its own bytes."""
    outer = inspect(raw, None)
    log = logical(raw)
    flash = next(item for item in outer['entries'] if item['name'] == 'flash.bin')
    count = len(outer['entries'])
    fo, fb = flash['offset'], flash['bytes']
    table_end = 64 + count * 80
    records = bytearray()
    for index in range(count):
        rec = bytearray(header_decode(log[64 + index * 80:144 + index * 80]))
        if index == flash['index']:
            rec[4:6] = b'\0\0'
        records += rec
    area = bytearray(sfc_decode(log[fo + APP_AREA:fo + fb], 0))
    head, rec_off, child = _app_geometry(area)
    masked = bytearray(area)
    masked[0:4] = bytes(4)
    masked[rec_off:rec_off + 4] = bytes(4)
    masked[rec_off + 8:rec_off + 12] = bytes(4)
    masked[child['address']:child['address'] + child['bytes']] = bytes(child['bytes'])
    return {
        'schema': PROFILE_SCHEMA,
        'id': 'fm1-v15-stock',
        'product': outer['identity'],
        'package_sha256': sha256(raw),
        'package_bytes': len(raw),
        'logical_bytes': len(log),
        'entry_count': count,
        'flash_entry_index': flash['index'],
        'flash_offset': fo,
        'flash_bytes': fb,
        'header_meta_sha256': sha256(header_decode(log[:64])[4:]),
        'entry_table_masked_sha256': sha256(records),
        'pre_flash_sha256': sha256(log[table_end:fo]),
        'post_flash_sha256': sha256(log[fo + fb:]),
        'flash_head_sha256': sha256(log[fo:fo + APP_AREA]),
        'app_area_offset': APP_AREA,
        'app_area_record_bytes': head['bytes'],
        'app_record_offset': rec_off,
        'app_offset': child['address'],
        'app_slot_bytes': child['bytes'],
        'app_area_masked_sha256': sha256(masked),
        'xip_entry': head['address'],
        'vm_base': VM_BASE,
        'sfc_key': STOCK_CHIP_KEY,
        'spl_bytes': len(components['top/uboot.boot']),
        'components_sha256': {path: sha256(components[path]) for path in
                              ('top/uboot.boot', 'top/isd_config.ini', 'files/cfg', 'ota.bin',
                               'files/cfg_tool.bin', 'files/eq_cfg_hw.bin')},
    }


def _check_geometry(profile):
    """The rules below assume V15's geometry and SFC key; refuse any other.

    `sfc_decode` always uses `STOCK_CHIP_KEY`, while the browser reads
    `profile.sfc_key`, so a profile with another key would make the two
    verifiers disagree silently."""
    if profile['flash_bytes'] != profile['vm_base'] or profile['app_area_offset'] != APP_AREA:
        raise ValueError('profile geometry differs from V15: flash.bin must end where VM begins')
    if profile['sfc_key'] != STOCK_CHIP_KEY:
        raise ValueError(f"profile SFC key {profile['sfc_key']:#06x} is not the stock key {STOCK_CHIP_KEY:#06x}")


def _profile_for(raw, profiles):
    digest = sha256(raw)
    profile = profiles.get(digest)
    if profile is None:
        raise ValueError(f'stock package sha256 {digest[:12]}... is not a pinned stock V15 '
                         '(expected db1642b2...; use your own unmodified FM-1_015 package)')
    _check_geometry(profile)
    return profile


def _write_tree(root, components):
    for path, data in components.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return root


def stage_stock(raw, work, profiles=None, stock_unpack=None):
    """Verify the stock package and stage its reference tree under `work`."""
    profiles = STOCK_PROFILES if profiles is None else profiles
    profile = _profile_for(raw, profiles)
    components = nested.extract_stock_components(raw)
    tree = _write_tree(Path(work) / 'stock', components)
    guard = check_package(tree, tree, spl_sha256=profile['components_sha256']['top/uboot.boot'],
                          spl_size=profile['spl_bytes'])
    if not guard['passed']:
        raise ValueError('stock package failed package_guard: '
                         + '; '.join(str(c['detail']) for c in guard['checks'] if c['status'] == 'fail'))
    nested.inspect_nested(raw, tree)
    computed = stock_profile(raw, components)
    if canonical(computed) != canonical(profile):
        raise ValueError('stock package decodes to a profile other than the pinned one')
    if stock_unpack is not None:
        _cross_check_unpack(Path(stock_unpack), components)
    return profile, components, tree


def _cross_check_unpack(unpack, components):
    """Compare with an independent unpack (kagaimiq's fwunpack_newfw.py)."""
    alias = {'files/eq_cfg_hw.bin': ('files/eq_cfg_hw.bin', 'files/cfg-extracted/eq_cfg_hw.bin')}
    compared = 0
    for path, data in components.items():
        for candidate in alias.get(path, (path,)):
            other = unpack / candidate
            if other.is_file():
                if other.read_bytes() != data:
                    raise ValueError(f'independent unpack differs: {candidate}')
                compared += 1
                break
    if compared < 5:
        raise ValueError(f'independent unpack has only {compared} comparable components')


def check_app(app, identity, profile, elf=None, margin=0):
    if not LUNAR_PRODUCT_RE.fullmatch(identity or ''):
        raise ValueError(f'identity {identity!r} is outside the Lunar range FM-1_500..FM-1_599')
    if identity == profile['product']:
        raise ValueError('a package with the stock identity is refused by step 1 (same version)')
    if not app:
        raise ValueError('app.bin is empty')
    budget = fm1_budget.measure(len(app), Elf(elf) if elf is not None else None,
                                slot=profile['app_slot_bytes'], margin=margin)
    if not budget['pass']:
        failed = [c['detail'] for c in budget['checks'] if not c['ok']]
        raise ValueError('app fails the fm1_budget gate: ' + '; '.join(failed))
    literals = [m for m in ANY_PRODUCT_LITERAL.finditer(app)]
    names = sorted({m.group()[:-1].decode('ascii') for m in literals})
    if len(literals) != 1 or names != [identity]:
        raise ValueError(f'app must contain {identity}\\0 exactly once and no other FM-1_nnn '
                         f'literal (found {len(literals)}: {", ".join(names) or "none"})')
    return budget, literals[0].start()


def assemble(raw, app, identity, profile):
    """Write `app` over the stock app slot; recompute the CRCs; set the identity."""
    _check_geometry(profile)
    log = logical(raw)
    fo, fb = profile['flash_offset'], profile['flash_bytes']
    flash = bytearray(log[fo:fo + fb])
    area = bytearray(sfc_decode(flash[APP_AREA:], 0))
    rec, addr, slot = profile['app_record_offset'], profile['app_offset'], profile['app_slot_bytes']
    if len(app) > slot:
        raise ValueError('app exceeds the slot')
    area[addr:addr + slot] = app + bytes([FILL]) * (slot - len(app))
    checksum_record(area, rec, app, len(app))
    checksum_record(area, 0, area[32:profile['app_area_record_bytes']])
    flash[APP_AREA:] = sfc_decode(area, 0)
    log[fo:fo + fb] = flash
    repair_outer(log, profile['flash_entry_index'], flash)
    return set_identity(physical(log, raw), identity)


def mutable_flash_ranges(profile):
    base, rec = profile['app_area_offset'], profile['app_record_offset']
    addr, slot = profile['app_offset'], profile['app_slot_bytes']
    return sorted([[base, base + 4], [base + rec, base + rec + 4], [base + rec + 8, base + rec + 12],
                   [base + addr, base + addr + slot]])


def describe_package(pkg, profile):
    """Verify a package against the pinned profile alone and return its manifest.

    The browser's `describeLunarPackage` implements the same rules; both must
    produce the same canonical JSON. Raises ValueError on any departure."""
    common = {
        'schema': MANIFEST_SCHEMA,
        'profile': profile['id'],
        'stock': {'product': profile['product'], 'package_sha256': profile['package_sha256']},
        'stock_components_sha256': dict(profile['components_sha256']),
    }
    _check_geometry(profile)
    if len(pkg) != profile['package_bytes']:
        raise ValueError(f'package is {len(pkg)} B; the pinned profile has {profile["package_bytes"]} B')
    product = markers_identity(pkg)
    log = logical(pkg)
    fo, fb = profile['flash_offset'], profile['flash_bytes']
    flash_info = {'payload_bytes': fb, 'write_range': [profile['app_area_offset'], profile['vm_base']],
                  'head_range': [0, profile['app_area_offset']],
                  'head_sha256': profile['flash_head_sha256'], 'vm_base': profile['vm_base']}
    package_info = {'bytes': len(pkg), 'sha256': sha256(pkg), 'logical_bytes': len(log),
                    'logical_sha256': sha256(log)}
    if sha256(pkg) == profile['package_sha256']:
        # Unreachable while the pin is honest (the SHA covers the identity
        # markers); kept as a defence against a mistyped profile.
        if product != profile['product']:
            raise ValueError('stock bytes with a foreign identity')
        return dict(common, kind='stock-rollback', product=product, model='FM-1',
                    version=int(product[5:]), package=package_info,
                    flash=dict(flash_info, mutable_ranges=[]), app=None)
    if not LUNAR_PRODUCT_RE.fullmatch(product):
        raise ValueError(f'identity {product} is neither the pinned stock package nor a Lunar FM-1_5xx')
    header = header_decode(log[:64])
    hcrc, listcrc, image_size, count = struct.unpack_from('<HHIH', header)
    if crc16(header[2:]) != hcrc:
        raise ValueError('UFW header CRC mismatch')
    if sha256(header[4:]) != profile['header_meta_sha256']:
        raise ValueError('UFW header metadata differs from stock')
    if image_size != len(log) or count != profile['entry_count']:
        raise ValueError('UFW size or entry count differs from stock')
    table_end = 64 + count * 80
    if crc16(log[64:table_end]) != listcrc:
        raise ValueError('UFW entry-list CRC mismatch')
    records = bytearray()
    flash_crc = None
    for index in range(count):
        rec = bytearray(header_decode(log[64 + index * 80:144 + index * 80]))
        if index == profile['flash_entry_index']:
            flash_crc = struct.unpack_from('<H', rec, 4)[0]
            rec[4:6] = b'\0\0'
        records += rec
    if sha256(records) != profile['entry_table_masked_sha256']:
        raise ValueError('UFW entry records differ from stock beyond the flash.bin CRC')
    if sha256(log[table_end:fo]) != profile['pre_flash_sha256']:
        raise ValueError('bytes between the entry list and flash.bin differ from stock')
    if sha256(log[fo + fb:]) != profile['post_flash_sha256']:
        raise ValueError('entries after flash.bin (USR, isd_config, ota.bin, tail) differ from stock')
    flash = log[fo:fo + fb]
    if crc16(flash) != flash_crc:
        raise ValueError('flash.bin CRC mismatch')
    if sha256(flash[:APP_AREA]) != profile['flash_head_sha256']:
        raise ValueError('flash head [0, 0x4000) differs from stock: the bootloader would change')
    area = bytearray(sfc_decode(flash[APP_AREA:], 0))
    rec, addr, slot = profile['app_record_offset'], profile['app_offset'], profile['app_slot_bytes']
    area_bytes = profile['app_area_record_bytes']
    head_hcrc, head_dcrc = struct.unpack_from('<HH', area, 0)
    if crc16(area[2:32]) != head_hcrc or crc16(area[32:area_bytes]) != head_dcrc:
        raise ValueError('app_area_head CRC mismatch')
    c_hcrc, c_dcrc, c_addr, size = struct.unpack_from('<HHII', area, rec)
    if crc16(area[rec + 2:rec + 32]) != c_hcrc:
        raise ValueError('app.bin record CRC mismatch')
    if c_addr != addr or not 0 < size <= slot:
        raise ValueError('app.bin record placement or size outside the stock slot')
    app = bytes(area[addr:addr + size])
    if crc16(app) != c_dcrc:
        raise ValueError('app.bin data CRC mismatch')
    if any(value != FILL for value in area[addr + size:addr + slot]):
        raise ValueError('unused app slot is not 0xFF fill')
    masked = bytearray(area)
    masked[0:4] = bytes(4)
    masked[rec:rec + 4] = bytes(4)
    masked[rec + 8:rec + 12] = bytes(4)
    masked[addr:addr + slot] = bytes(slot)
    if sha256(masked) != profile['app_area_masked_sha256']:
        raise ValueError('app directory, cfg or reserved descriptors differ from stock')
    literals = list(ANY_PRODUCT_LITERAL.finditer(app))
    if len(literals) != 1 or literals[0].group()[:-1].decode('ascii') != product:
        raise ValueError(f'app must carry {product}\\0 exactly once and no other FM-1_nnn literal')
    return dict(common, kind='lunar-install', product=product, model='FM-1', version=int(product[5:]),
                package=package_info, flash=dict(flash_info, mutable_ranges=mutable_flash_ranges(profile)),
                app={'bytes': size, 'sha256': sha256(app), 'flash_offset': addr + APP_AREA,
                     'slot_bytes': slot, 'spare_bytes': slot - size, 'fill': FILL,
                     'identity_offset': literals[0].start(), 'xip_entry': profile['xip_entry']})


def changed_logical_ranges(before, after):
    ranges, start = [], None
    for index in range(len(before) + 1):
        differs = index < len(before) and before[index] != after[index]
        if differs and start is None:
            start = index
        elif not differs and start is not None:
            ranges.append((start, index))
            start = None
    return ranges


def verify_install(raw, pkg, app, identity, tree, profile, work):
    """Independent re-check of an assembled package; returns the manifest."""
    manifest = describe_package(pkg, profile)
    if (manifest['kind'], manifest['product'], manifest['app']['sha256']) != \
            ('lunar-install', identity, sha256(app)):
        raise ValueError('assembled package does not describe the requested app and identity')
    # Bind the decoded package to the guarded stock tree, with the app replaced.
    restored = set_identity(pkg, profile['product'])
    nested._inspect_app_replacement(restored, tree, app)
    parts = nested.extract_stock_components(restored)
    if parts['files/app.bin'] != app:
        raise ValueError('decoded package app differs from the input app')
    pkg_tree = _write_tree(Path(work) / 'package', {k: v for k, v in parts.items() if k != 'files/app.bin'})
    guard = check_package(pkg_tree, tree, spl_sha256=profile['components_sha256']['top/uboot.boot'],
                          spl_size=profile['spl_bytes'])
    if not guard['passed']:
        raise ValueError('package failed package_guard')
    # Every changed logical byte is a UFW header CRC, the flash.bin record CRC
    # or inside one of the manifest's mutable flash ranges, all of which lie in
    # [0x4000, 0x93000).
    fo = profile['flash_offset']
    record = 64 + profile['flash_entry_index'] * 80
    allowed = manifest['flash']['mutable_ranges']
    if not all(WRITE_RANGE[0] <= lo < hi <= WRITE_RANGE[1] for lo, hi in allowed):
        raise ValueError('a mutable range leaves the app area')
    changed, low, high = 0, None, None
    for lo, hi in changed_logical_ranges(logical(raw), logical(restored)):
        if hi <= 4 or (record + 4 <= lo and hi <= record + 6):
            continue
        flo, fhi = lo - fo, hi - fo
        if not any(a <= flo and fhi <= b for a, b in allowed):
            raise ValueError(f'logical bytes [{lo:#x}, {hi:#x}) changed outside the mutable ranges')
        changed += hi - lo
        low = flo if low is None else min(low, flo)
        high = fhi if high is None else max(high, fhi)
    if not changed:
        raise ValueError('package does not differ from stock')
    flash_changes = dict(changed_bytes=changed, hull=[low, high])
    return manifest, guard, flash_changes


def _write_outputs(package_path, package, manifest_path, manifest):
    """Write the package and its manifest, both new files, or neither."""
    package_path, manifest_path = Path(package_path), Path(manifest_path)
    if package_path.resolve() == manifest_path.resolve():
        raise ValueError('the package and its manifest need different paths')
    for path in (package_path, manifest_path):
        if path.exists():
            raise FileExistsError(f'{path} exists; refusing to overwrite')
    text = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode()
    with open(package_path, 'xb') as handle:
        handle.write(package)
    try:
        with open(manifest_path, 'xb') as handle:
            handle.write(text)
    except BaseException:
        package_path.unlink()
        raise


def build_install(stock_path, app_path, identity, out, manifest_path=None, elf_path=None, margin=0,
                  stock_unpack=None, profiles=None):
    raw = Path(stock_path).read_bytes()
    app = Path(app_path).read_bytes()
    elf = Path(elf_path).read_bytes() if elf_path else None
    with tempfile.TemporaryDirectory(prefix='build_fwsc-') as work:
        profile, _, tree = stage_stock(raw, work, profiles, stock_unpack)
        budget, identity_offset = check_app(app, identity, profile, elf, margin)
        pkg = assemble(raw, app, identity, profile)
        manifest, guard, flash_changes = verify_install(raw, pkg, app, identity, tree, profile, work)
    manifest_path = Path(manifest_path or f'{out}.manifest.json')
    _write_outputs(out, pkg, manifest_path, manifest)
    return dict(manifest=manifest, guard=guard, budget=budget, flash_changes=flash_changes,
                out=str(out), manifest_path=str(manifest_path))


def build_rollback(stock_path, out, manifest_path=None, running=None, stock_unpack=None, profiles=None):
    raw = Path(stock_path).read_bytes()
    with tempfile.TemporaryDirectory(prefix='build_fwsc-') as work:
        profile, _, _ = stage_stock(raw, work, profiles, stock_unpack)
    if running is not None and running == profile['product']:
        raise ValueError(f'the unit already runs {running}; step 1 refuses the same version')
    manifest = describe_package(raw, profile)
    if manifest['kind'] != 'stock-rollback':
        raise ValueError('stock package did not verify as the roll-back package')
    manifest_path = Path(manifest_path or f'{out}.manifest.json')
    _write_outputs(out, raw, manifest_path, manifest)
    return dict(manifest=manifest, out=str(out), manifest_path=str(manifest_path))


def verify_file(package_path, manifest_path=None, profiles=None):
    profiles = STOCK_PROFILES if profiles is None else profiles
    pkg = Path(package_path).read_bytes()
    errors = []
    for profile in profiles.values():
        try:
            manifest = describe_package(pkg, profile)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if manifest_path is not None:
            supplied = json.loads(Path(manifest_path).read_text())
            if canonical(supplied) != canonical(manifest):
                raise ValueError('manifest does not match the package')
        return manifest
    raise ValueError('; '.join(errors) or 'no pinned profile')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='command', required=True)
    p = sub.add_parser('install', help='stock V15 + Lunar app.bin -> install package')
    p.add_argument('--stock', required=True, help="your own stock V15 .fwsc (FM-1_015)")
    p.add_argument('--app', required=True, help='the Lunar app.bin')
    p.add_argument('--identity', required=True, help='the Lunar package identity, FM-1_5xx')
    p.add_argument('--out', required=True, help='new package path; refuses overwrite')
    p.add_argument('--manifest', help='new manifest path (default <out>.manifest.json)')
    p.add_argument('--elf', help='the linked ELF of app.bin, for the SRAM budget checks')
    p.add_argument('--margin', type=int, default=0, help='spare slot bytes to require')
    p.add_argument('--stock-unpack', help='fwunpack_newfw.py output of the same package, cross-checked')
    r = sub.add_parser('rollback', help='stock V15 -> verified roll-back package')
    r.add_argument('--stock', required=True)
    r.add_argument('--out', required=True)
    r.add_argument('--manifest')
    r.add_argument('--running', help='the identity the unit runs now (must not be FM-1_015)')
    r.add_argument('--stock-unpack')
    v = sub.add_parser('verify', help='check a package (and manifest) against the pinned profile')
    v.add_argument('package')
    v.add_argument('--manifest')
    f = sub.add_parser('profile', help='print the profile computed from a stock package')
    f.add_argument('--stock', required=True)
    args = ap.parse_args(argv)
    try:
        if args.command == 'install':
            result = build_install(args.stock, args.app, args.identity, args.out, args.manifest,
                                   args.elf, args.margin, args.stock_unpack)
            m, c = result['manifest'], result['flash_changes']
            print(f"build_fwsc: {m['product']} written to {result['out']}: app {m['app']['bytes']} B, "
                  f"{m['app']['spare_bytes']} B spare; {c['changed_bytes']} flash bytes changed within "
                  f"[{c['hull'][0]:#x}, {c['hull'][1]:#x}); package_guard PASS; manifest {result['manifest_path']}")
        elif args.command == 'rollback':
            result = build_rollback(args.stock, args.out, args.manifest, args.running, args.stock_unpack)
            print(f"build_fwsc: roll-back package {result['manifest']['product']} written to {result['out']} "
                  f"(byte-identical to the input); manifest {result['manifest_path']}")
        elif args.command == 'verify':
            m = verify_file(args.package, args.manifest)
            print(f"build_fwsc: {m['kind']} {m['product']} verifies against {m['profile']}"
                  + (' and its manifest' if args.manifest else ''))
        else:
            raw = Path(args.stock).read_bytes()
            print(json.dumps(stock_profile(raw, nested.extract_stock_components(raw)), indent=2))
    except (OSError, ValueError, KeyError, IndexError, StopIteration, struct.error) as exc:
        print(f'build_fwsc: refused: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
