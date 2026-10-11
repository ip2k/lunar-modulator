#!/usr/bin/env python3
"""MIT. Validate recorded FM-1_092 raw NOR dumps/targets offline; JSON only.

No transport, container builder, image output or hardware approval. Reuses
strict stock parser primitives; the FM-1_015 outer/container profile remains
unchanged. This profile supports only the recorded 092 base-zero payload,
not arbitrary devices whose caller-supplied identity happens to say 092.
"""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

from audit_link import Elf, audit
from diagnostic_report import report, layout_profile
from inspect_fwsc import crc16, header_decode, sfc_decode
from inspect_stock_flash import bounded, record, payload_crc, stock_key
from package_guard import STOCK_SPL_SHA256, STOCK_SPL_SIZE

FLASH_BYTES = 0x100000
APP_BASE = 0x4000
PAYLOAD_END = 0xAE000
RECORDED_PAYLOAD_SHA256 = 'e054fdc557a6c2690367c0090d16c21c4d5c07d0eec3f4e796812bbbfe96fc27'
LOADER_SHA256 = 'd41da6126760c9d66660bcc0cac8d27d221806c5e369a8036921efe68dca5376'
FIXED_LOADER_SHA256 = 'fe6d1bd36c8ffe4674e4a05ee748fe87480b5867fac58230b14ff089d411012c'
FIXED_PROFILE_SHA256 = '3c03e413b9df29d85e4c07d886d9bfb9b3ab2fc66845d5220f82998dd44f4afe'
FIXED_PROFILE_SOURCE_SHA256 = '9664e1329d8259362da78c047ce2d6003dfe8df2850f02703f98e8b6bf277cd8'
FIXED_READER_SHA256 = '28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57'
FIXED_REQUEST_INVENTORY_SHA256 = 'f99b6e738d19d24442ad4d056985e6f4dc200d0b09059b80428f4ff989838017'
APP_BYTES = 691744
AREA_BYTES = 692415
CFG_TOOL_OFFSET = APP_BASE + 692032
CFG_OFFSET = APP_BASE + AREA_BYTES
CFG_BYTES = 2937
RESERVED = {'key_mac': (0xFF000, 0x1000, 0x12),
            'VM': (0xD9000, 0x10000, 0x12),
            'PRCT': (0, 0xD9000, 0x92),
            'BTIF': (0xE9000, 0x1000, 0x92),
            'USR': (0xEA000, 0x12000, 0x92)}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def _reservation(item, name):
    if ((item['address'], item['bytes'], item['flags']) != RESERVED[name]
            or item['crc16'] != 0xFFFF):
        raise ValueError('Unsupported FM-1_092 reserved layout')


def _file(data, item, start, end):
    lo, hi = start + item['address'], start + item['address'] + item['bytes']
    if item['flags'] != 0x82 or not start + 32 <= lo < hi <= end:
        raise ValueError('Unsupported nested file allocation')
    payload = bounded(data, lo, hi - lo)
    payload_crc(item, payload)
    return payload


def _parse(raw, reference, replacement=None):
    """Parse physical offsets directly; never consumes a FWSC container."""
    if not isinstance(raw, bytes) or len(raw) != FLASH_BYTES:
        raise ValueError('Complete 1 MiB raw NOR image required')
    headers = []
    for address in (0, 0x1000, 0x10000, 0x80000):
        head = header_decode(raw[address:address + 32])
        if crc16(head[2:]) == int.from_bytes(head[:2], 'little'):
            headers.append(address)
    if headers != [0]:
        raise ValueError('Unsupported or ambiguous raw flash image base')
    decoded = bytearray(raw)
    decoded[:32] = header_decode(raw[:32])
    top = []
    for index in range(4):
        offset = 32 + 32 * index
        decoded[offset:offset + 32] = header_decode(raw[offset:offset + 32])
        item = record(decoded, offset)
        if bool(item['terminal']) != (index == 3):
            raise ValueError('Unsupported top terminator')
        top.append(item)
    if [item['name'] for item in top] != ['uboot.boot', 'isd_config.ini', 'app_dir_head', 'key_mac']:
        raise ValueError('Unsupported top directory')
    spl, config, directory, key = top
    if ((spl['address'], spl['bytes'], spl['flags']) != (0xA0, STOCK_SPL_SIZE, 0)
            or (config['address'], config['bytes'], config['flags']) != (0x38D0, 699, 2)
            or (directory['address'], directory['bytes'], directory['flags'], directory['crc16'])
            != (APP_BASE, 0xFFFFFFFF, 0x81, 0xFFFF)):
        raise ValueError('Unsupported top placement')
    _reservation(key, 'key_mac')
    spl_data = bytearray(raw[0xA0:0x38D0])
    spl_data[:16] = header_decode(spl_data[:16])
    count, size, load, offset, dcrc, hcrc = struct.unpack('<HHIIHH', spl_data[:16])
    if ((count, size, load, offset) != (1, 14368, 0x01C02000, 16)
            or crc16(spl_data[:14]) != hcrc):
        raise ValueError('Unsupported SPL bank/header')
    spl_data[16:] = header_decode(spl_data[16:])
    if crc16(spl_data[16:]) != dcrc or digest(spl_data) != STOCK_SPL_SHA256:
        raise ValueError('Stock SPL pin/CRC mismatch')
    payload_crc(spl, spl_data)
    config_data = raw[config['address']:config['address'] + config['bytes']]
    payload_crc(config, config_data)
    stock_key(config_data)
    # SFC origin is the image's app directory, established by saved dumps and
    # static SPL evidence, not the outer FWSC flash.bin placement.
    decoded[APP_BASE:PAYLOAD_END] = sfc_decode(raw[APP_BASE:PAYLOAD_END], 0)
    area = record(decoded, APP_BASE)
    cfg = record(decoded, CFG_OFFSET)
    if ((area['name'], area['address'], area['bytes'], area['flags'], area['terminal'])
            != ('app_area_head', 0x02000120, AREA_BYTES, 0x83, 0)
            or (cfg['name'], cfg['address'], cfg['bytes'], cfg['flags'], cfg['terminal'])
            != ('cfg', 32, CFG_BYTES, 0x83, 1)):
        raise ValueError('Unsupported FM-1_092 app/config allocation')
    payload_crc(area, bounded(decoded, APP_BASE + 32, AREA_BYTES - 32))
    payload_crc(cfg, bounded(decoded, CFG_OFFSET + 32, CFG_BYTES - 32))
    children = [record(decoded, APP_BASE + 32 + i * 32) for i in range(6)]
    if [item['name'] for item in children] != ['app.bin', 'cfg_tool.bin', 'VM', 'PRCT', 'BTIF', 'USR']:
        raise ValueError('Unsupported app children')
    if any(bool(item['terminal']) != (i == 5) for i, item in enumerate(children)):
        raise ValueError('Unsupported app terminator')
    app, tool = children[:2]
    expected_size = APP_BYTES if replacement is None else len(replacement)
    if (app['address'] != 0x120 or app['bytes'] != expected_size
            or not 0 < expected_size <= APP_BYTES
            or (tool['address'], tool['bytes']) != (692032, 383)):
        raise ValueError('Unsupported app entry/extent or cfg_tool allocation')
    for item in children[2:]:
        _reservation(item, item['name'])
    app_data = _file(decoded, app, APP_BASE, CFG_TOOL_OFFSET)
    tool_data = _file(decoded, tool, APP_BASE, CFG_OFFSET)
    eq = record(decoded, CFG_OFFSET + 32)
    if (eq['name'], eq['address'], eq['bytes'], eq['terminal']) != ('eq_cfg_hw.bin', 64, 2873, 1):
        raise ValueError('Unsupported config child allocation')
    eq_data = _file(decoded, eq, CFG_OFFSET, CFG_OFFSET + CFG_BYTES)
    components = {'top/uboot.boot': bytes(spl_data), 'top/isd_config.ini': config_data,
                  'files/app.bin': app_data, 'files/cfg_tool.bin': tool_data,
                  'files/cfg': bytes(decoded[CFG_OFFSET:CFG_OFFSET + CFG_BYTES]),
                  'files/cfg-extracted/eq_cfg_hw.bin': eq_data}
    for name, data in components.items():
        expected = replacement if name == 'files/app.bin' and replacement is not None else (Path(reference) / name).read_bytes()
        if data != expected:
            raise ValueError('Guarded reference component differs: ' + name)
    return bytes(decoded), {name: digest(data) for name, data in components.items()}


def profile_dump(baseline_a, baseline_b, manifest, identity, reference):
    """Report this recorded payload's layout and bind two private raw dumps."""
    return _profile_dump(baseline_a, baseline_b, manifest, identity, reference, LOADER_SHA256)


def profile_dump_fixed_loader(baseline_a, baseline_b, manifest, identity, reference):
    """Distinct read-only provenance; never masquerades as the original loader.

    This is offline classification. Adapter approval and live session binding
    remain the physical campaign's gates, not privileges supplied by this JSON.
    """
    if (not isinstance(manifest, dict) or manifest.get('schema') != 1
            or manifest.get('kind') != 'fm1-fixed-loader-backup'
            or manifest.get('original_loader_sha256') != LOADER_SHA256
            or manifest.get('loader_profile_sha256') != FIXED_PROFILE_SHA256
            or manifest.get('profile_source_sha256') != FIXED_PROFILE_SOURCE_SHA256
            or manifest.get('dependency_sha256') != {'fm1_uboot_read.py': FIXED_READER_SHA256}
            or manifest.get('unit_identity') != 'FM-1_092'
            or manifest.get('command_completions') is not True
            or manifest.get('flash_readback_only') is not True
            or manifest.get('request_inventory_sha256') != FIXED_REQUEST_INVENTORY_SHA256
            or type(manifest.get('commands')) is not int or manifest['commands'] != 8757):
        raise ValueError('Pinned fixed-loader complete read-only manifest required')
    for field in ('adapter_sha256', 'campaign_sha256', 'entry_log_sha256', 'request_inventory_sha256'):
        value = manifest.get(field)
        if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('Fixed-loader provenance digest missing: ' + field)
    binding = manifest.get('usb_binding')
    if (not isinstance(binding, dict) or set(binding) != {'path', 'busnum', 'devnum', 'vid', 'pid'}
            or not all(isinstance(value, str) for value in binding.values())
            or not re.fullmatch(r'[1-9][0-9]*-[1-9][0-9]*(?:\.[1-9][0-9]*)*', binding['path'])
            or not re.fullmatch(r'[1-9][0-9]*', binding['busnum'])
            or not re.fullmatch(r'[1-9][0-9]*', binding['devnum'])
            or binding['path'].split('-')[0] != binding['busnum']
            or binding.get('vid') != '4c4a' or binding.get('pid') != '8057'
            or not isinstance(identity, dict) or identity.get('usb_binding') != binding
            or identity.get('entry_log_sha256') != manifest['entry_log_sha256']):
        raise ValueError('Fixed-loader identity/entry/USB binding mismatch')
    dumps = manifest.get('dumps')
    if not isinstance(dumps, list) or len(dumps) != 2 or any(item.get('complete') is not True for item in dumps if isinstance(item, dict)):
        raise ValueError('Two complete fixed-loader dumps required')
    return _profile_dump(baseline_a, baseline_b, manifest, identity, reference, FIXED_LOADER_SHA256)


def _profile_dump(baseline_a, baseline_b, manifest, identity, reference, loader_sha256):
    if (not isinstance(baseline_a, bytes) or baseline_a != baseline_b
            or len(baseline_a) != FLASH_BYTES):
        raise ValueError('Two identical complete raw backups required')
    if (not isinstance(manifest, dict) or manifest.get('identical') is not True or manifest.get('flash_bytes') != FLASH_BYTES
            or manifest.get('loader_sha256') != loader_sha256):
        raise ValueError('Audited-loader full-backup manifest required')
    for name in ('dumpA.bin', 'dumpB.bin'):
        entries = [item for item in manifest.get('dumps', []) if isinstance(item, dict) and item.get('file') == name]
        if (len(entries) != 1 or entries[0].get('bytes') != FLASH_BYTES
                or entries[0].get('sha256') != digest(baseline_a)):
            raise ValueError('Backup manifest hash/size mismatch')
    if (not isinstance(identity, dict) or identity.get('firmware') != 'FM-1_092' or not isinstance(identity.get('unit_id'), str)
            or not identity['unit_id'] or identity.get('simulated') is not False):
        raise ValueError('Explicit non-simulated FM-1_092 identity evidence required')
    # This is recorded prefix content classification, not a general outer092
    # parser or a guarantee of serial-number identity across different units.
    if digest(baseline_a[:PAYLOAD_END]) != RECORDED_PAYLOAD_SHA256:
        raise ValueError('Unsupported FM-1_092 raw payload fingerprint')
    _, components = _parse(baseline_a, reference)
    result = dict(schema=1, status='recorded-fm1-092-raw-profile-verified-offline',
                  hardware_validated=False, physical_writer_ready=False, binary_emitted=False,
                  identity=json.loads(encoded(identity)), identity_binding='caller evidence plus exact flash content; no silicon serial proof',
                  baseline_sha256=digest(baseline_a), backup_manifest_sha256=digest(encoded(manifest)),
                  loader_sha256=loader_sha256, image_base=0, coordinates='raw NOR byte offsets',
                  app_directory_offset=APP_BASE, app_image_offset=0x4120,
                  app_extent_bytes=APP_BYTES, entry=0x02000120,
                  recorded_payload_sha256=RECORDED_PAYLOAD_SHA256,
                  protected_ranges=[[0, APP_BASE], [CFG_TOOL_OFFSET, FLASH_BYTES]],
                  reserved={name: list(values) for name, values in RESERVED.items()},
                  prct_is_descriptor_not_writable_permission=True,
                  component_sha256=components,
                  unknown_bytes='preserved exactly; no OTA/outer cipher semantics inferred')
    result['profile_sha256'] = digest(encoded(result))
    return result


def validate_target(baseline_a, baseline_b, target, manifest, identity, reference,
                    app, elf, diagnostic_profile='inert', expected_audit=None):
    """Validate a supplied target; construct/emit no firmware image."""
    profile = profile_dump(baseline_a, baseline_b, manifest, identity, reference)
    link = audit([('diagnostic.elf', Elf(elf))], [('diagnostic.bin', app)], True, runtime='sdk-free')
    if expected_audit is not None and encoded(expected_audit) != encoded(link):
        raise ValueError('Supplied audit differs from independently recomputed audit')
    layout = report(elf, app, link, profile=layout_profile(diagnostic_profile))
    result = _validate_target_geometry(profile, baseline_a, target, reference, app)
    result.update(app_sha256=digest(app), elf_sha256=digest(elf),
                  link_audit_sha256=digest(encoded(link)), diagnostic_layout_sha256=digest(encoded(layout)),
                  diagnostic_profile=diagnostic_profile, diagnostic_layout=layout)
    return result


def _validate_target_geometry(profile, baseline_a, target, reference, app):
    """Shared raw-byte gate; callers must independently validate their runtime."""
    before, _ = _parse(baseline_a, reference)
    after, _ = _parse(target, reference, replacement=app)
    if target[:APP_BASE] != baseline_a[:APP_BASE] or target[CFG_TOOL_OFFSET:] != baseline_a[CFG_TOOL_OFFSET:]:
        raise ValueError('Protected raw flash changed')
    # The strict parser checks all CRCs. Only the directory CRCs, child CRCs/
    # length, and exact supplied app bytes may differ in decoded space.
    masked = bytearray(before)
    permitted = [(APP_BASE, APP_BASE + 4), (APP_BASE + 32, APP_BASE + 36),
                 (APP_BASE + 40, APP_BASE + 44), (0x4120, 0x4120 + len(app))]
    for lo, hi in permitted:
        masked[lo:hi] = after[lo:hi]
    if masked != after:
        raise ValueError('Decoded bytes outside exact app/CRC/length contract changed')
    sectors = sorted({i // 4096 * 4096 for i, (a, b) in enumerate(zip(baseline_a, target)) if a != b})
    if not sectors:
        raise ValueError('Target has no application changes')
    for address in sectors:
        for lo, hi in profile['protected_ranges']:
            if address < hi and lo < address + 4096:
                raise ValueError('Changed sector crosses protected allocation')
    return dict(schema=1, status='exact-raw-app-target-verified-offline',
                hardware_validated=False, physical_writer_ready=False, binary_emitted=False,
                baseline_sha256=profile['baseline_sha256'], target_sha256=digest(target),
                profile_sha256=profile['profile_sha256'], profile=profile,
                allowed_sectors=sectors,
                writable_ranges=[[address, address + 4096] for address in sectors],
                protected_ranges=profile['protected_ranges'], protected_raw_bytes_identical=True,
                original_app_tail_identical=True,
                next_gate='Independent bound-adapter/candidate/recovery review; no hardware authorization')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-a', type=Path, required=True)
    parser.add_argument('--baseline-b', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--identity', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--target', type=Path)
    parser.add_argument('--app', type=Path)
    parser.add_argument('--elf', type=Path)
    parser.add_argument('--audit', type=Path)
    parser.add_argument('--diagnostic-profile', default='inert')
    parser.add_argument('--json', type=Path, help='new JSON report only; refuses overwrite')
    args = parser.parse_args()
    if bool(args.target) != bool(args.app) or bool(args.target) != bool(args.elf) or (args.audit and not args.target):
        parser.error('--target, --app and --elf must be supplied together; --audit requires them')
    values = (args.baseline_a.read_bytes(), args.baseline_b.read_bytes(),
              json.loads(args.manifest.read_text()), json.loads(args.identity.read_text()), args.reference)
    if args.target:
        result = validate_target(values[0], values[1], args.target.read_bytes(), *values[2:],
                                 args.app.read_bytes(), args.elf.read_bytes(), args.diagnostic_profile,
                                 json.loads(args.audit.read_text()) if args.audit else None)
    else:
        result = profile_dump(*values)
    if args.json:
        with args.json.open('x') as fp:
            json.dump(result, fp, indent=2)
            fp.write('\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
