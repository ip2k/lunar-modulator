#!/usr/bin/env python3
"""Validate the known stock V15 nested flash offline; output reports only.

Independently authored from the MIT jl-misctools format description, checked
against stock bytes. This is an inspection profile, not a firmware packager.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from inspect_fwsc import crc16, header_decode, inspect, sfc_decode


FLASH_BYTES = 0x100000
APP_BASE = 0x4000
XIP_BASE = 0x02000000
EXPECTED_RESERVED = {
    'key_mac': (0xff000, 0x1000, 0x12),
    'VM': (0x93000, 0x56000, 0x12),
    'PRCT': (0, 0x93000, 0x92),
    'BTIF': (0xe9000, 0x1000, 0x92),
    'USR': (0xea000, 0x12000, 0x92),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def bounded(data, offset, size):
    if offset < 0 or size < 0 or offset + size > len(data):
        raise ValueError('nested data outside containing image')
    return data[offset:offset + size]


def record(data, offset):
    raw = bounded(data, offset, 32)
    hcrc, dcrc, address, size, flags, reserved, terminal, name = struct.unpack('<HHIIBBH16s', raw)
    if crc16(raw[2:]) != hcrc:
        raise ValueError('JLFS header CRC mismatch')
    name, zero, padding = name.partition(b'\0')
    if not zero or (not flags & 0x10 and any(value not in (0, 255) for value in padding)):
        raise ValueError('invalid JLFS name')
    name = name.decode('ascii')
    return dict(name=name, header_offset=offset, address=address, bytes=size,
                flags=flags, reserved=reserved, terminal=terminal, crc16=dcrc,
                header_crc_verified=True, name_tail_hex=padding.hex())


def payload_crc(item, data):
    if crc16(data) != item['crc16']:
        raise ValueError(f"JLFS data CRC mismatch: {item['name']}")
    item['data_crc_verified'] = True
    item['decoded_sha256'] = digest(data)


def reserved(item, found):
    if item['name'] in found or item['name'] not in EXPECTED_RESERVED:
        raise ValueError('unexpected/duplicate stock reserved descriptor')
    expected = EXPECTED_RESERVED[item['name']]
    if (item['address'], item['bytes'], item['flags']) != expected or item['crc16'] != 0xffff:
        raise ValueError('stock reserved descriptor differs')
    if item['address'] + item['bytes'] > FLASH_BYTES:
        raise ValueError('stock reservation outside physical flash')
    found.add(item['name'])
    item['data_crc_verified'] = False
    item['data_crc_reason'] = 'reserved descriptor with sentinel FFFF, not a stored payload'


def stock_key(data):
    blob = bounded(data, 0, 32)
    if crc16(blob) != int.from_bytes(bounded(data, 32, 2), 'little'):
        raise ValueError('stock chip-key blob CRC mismatch')
    threshold = sum(blob[:16]) & 255
    threshold = 0xaa if threshold >= 0xe0 else 0x55 if threshold <= 0x10 else threshold
    value = sum(1 << index for index in range(16)
                if (blob[16 + index] ^ blob[15 - index]) < threshold)
    if value != 0x980f:
        raise ValueError('unsupported stock chip key')
    return value


def inspect_nested(raw, stock):
    """Strict stock-only entry point; never accepts a replacement app."""
    return _inspect_nested(raw, stock)


def _inspect_app_replacement(raw, stock, app):
    """Private model verifier; a modified result can never be labelled stock."""
    return _inspect_nested(raw, stock, app)


def _inspect_nested(raw, stock, replacement=None):
    outer = inspect(raw, stock)
    if outer['identity'] != 'FM-1_015':
        raise ValueError('nested inspection profile supports stock FM-1_015 only')
    logical = b''.join(raw[offset:offset + 47] for offset in range(0, 960, 48)) + raw[960:]
    flash_item = next(item for item in outer['entries'] if item['name'] == 'flash.bin')
    flash_offset = flash_item['offset']
    flash = bounded(logical, flash_offset, flash_item['bytes'])
    if len(flash) != 0x93000:
        raise ValueError('stock V15 flash payload size differs')
    decoded = bytearray(flash)
    decoded[:32] = header_decode(flash[:32])
    if crc16(decoded[2:32]) != int.from_bytes(decoded[:2], 'little'):
        raise ValueError('flash header CRC mismatch')
    top, found_reserved = [], set()
    for index in range(4):
        offset = 32 + index * 32
        decoded[offset:offset + 32] = header_decode(flash[offset:offset + 32])
        item = record(decoded, offset)
        if bool(item['terminal']) != (index == 3):
            raise ValueError('unexpected stock top-directory terminator')
        top.append(item)
    if [item['name'] for item in top] != ['uboot.boot', 'isd_config.ini', 'app_dir_head', 'key_mac']:
        raise ValueError('unexpected stock top directory')
    spl, config, app, reserve = top
    if ((spl['address'], spl['bytes'], spl['flags']) != (0xa0, 14384, 0)
            or (config['address'], config['bytes'], config['flags']) != (0x38d0, 699, 2)
            or (app['address'], app['bytes'], app['flags'], app['crc16']) != (APP_BASE, 0xffffffff, 0x81, 0xffff)):
        raise ValueError('stock top placement differs')
    reserved(reserve, found_reserved)
    config_data = bounded(flash, config['address'], config['bytes'])
    payload_crc(config, config_data)
    stock_key(config_data)
    spl_data = bytearray(bounded(flash, spl['address'], spl['bytes']))
    spl_data[:16] = header_decode(spl_data[:16])
    count, bank_size, bank_load, bank_offset, bank_crc, bank_hcrc = struct.unpack('<HHIIHH', spl_data[:16])
    if crc16(spl_data[:14]) != bank_hcrc:
        raise ValueError('SPL bank header CRC mismatch')
    if (count, bank_offset, bank_size, bank_load) != (1, 16, 14368, 0x01c02000):
        raise ValueError('unsupported SPL bank layout')
    spl_data[bank_offset:] = header_decode(spl_data[bank_offset:])
    if crc16(spl_data[bank_offset:]) != bank_crc:
        raise ValueError('SPL bank data CRC mismatch')
    payload_crc(spl, spl_data)
    decoded[spl['address']:spl['address'] + spl['bytes']] = spl_data
    # Decode the whole aligned app region once; directory boundaries need not
    # be aligned. The trailing bytes are preserved, with no claimed semantics.
    decoded[APP_BASE:] = sfc_decode(flash[APP_BASE:], 0)
    blocks, files = [], {}
    cursor = APP_BASE
    for block_index in range(2):
        item = record(decoded, cursor)
        if item['flags'] != 0x83 or item['bytes'] < 32 or bool(item['terminal']) != (block_index == 1):
            raise ValueError('unsupported stock app/resource directory')
        body = bounded(decoded, cursor + 32, item['bytes'] - 32)
        payload_crc(item, body)
        children, file_ranges = [], []
        for child_index in range(6 if block_index == 0 else 1):
            child_offset = cursor + 32 + child_index * 32
            if child_offset + 32 > cursor + item['bytes']:
                raise ValueError('child table outside directory')
            child = record(decoded, child_offset)
            if bool(child['terminal']) != (child_index == (5 if block_index == 0 else 0)):
                raise ValueError('unexpected child-directory terminator')
            if child['flags'] & 0x10:
                reserved(child, found_reserved)
            elif child['flags'] == 0x82:
                if child['name'] in files:
                    raise ValueError('duplicate nested filename')
                data_start = cursor + child['address']
                table_end = cursor + 32 + (6 if block_index == 0 else 1) * 32
                if data_start < table_end or data_start + child['bytes'] > cursor + item['bytes']:
                    raise ValueError('nested file outside directory data')
                data_end = data_start + child['bytes']
                if any(data_start < right and left < data_end for left, right in file_ranges):
                    raise ValueError('overlapping nested files')
                file_ranges.append((data_start, data_end))
                data = bounded(decoded, data_start, child['bytes'])
                payload_crc(child, data)
                files[child['name']] = data
            else:
                raise ValueError('unsupported nested file flags')
            children.append(child)
        item['children'] = children
        blocks.append(item)
        cursor += item['bytes']
    if ([item['name'] for item in blocks] != ['app_area_head', 'cfg']
            or blocks[0]['address'] != 0x02000120
            or set(files) != {'app.bin', 'cfg_tool.bin', 'eq_cfg_hw.bin'}
            or found_reserved != set(EXPECTED_RESERVED)):
        raise ValueError('unexpected stock application/reservation tree')
    application = next(child for child in blocks[0]['children'] if child['name'] == 'app.bin')
    if blocks[0]['address'] != XIP_BASE + application['address']:
        raise ValueError('stock entry disagrees with app.bin XIP placement')
    stock = Path(stock)
    components = {'top/uboot.boot': bytes(spl_data), 'top/isd_config.ini': bytes(config_data),
                  'files/cfg': bytes(decoded[blocks[1]['header_offset']:cursor])}
    components.update({f'files/{name}': data for name, data in files.items()})
    for path, data in components.items():
        expected = replacement if path == 'files/app.bin' and replacement is not None else (stock / path).read_bytes()
        if data != expected:
            raise ValueError(f'guarded decoded component differs: {path}')
    # No candidate is written: invert every decoded region in memory, retaining
    # unknown padding/metadata exactly, then compare the full original FWSC.
    reconstructed = bytearray(decoded)
    reconstructed[:32] = header_decode(decoded[:32])
    for item in top:
        offset = item['header_offset']
        reconstructed[offset:offset + 32] = header_decode(decoded[offset:offset + 32])
    encoded_spl = bytearray(spl_data)
    encoded_spl[:16] = header_decode(spl_data[:16])
    encoded_spl[16:] = header_decode(spl_data[16:])
    reconstructed[spl['address']:spl['address'] + spl['bytes']] = encoded_spl
    reconstructed[APP_BASE:] = sfc_decode(decoded[APP_BASE:], 0)
    if reconstructed != flash:
        raise ValueError('nested no-op reconstruction differs')
    rebuilt = bytearray(logical)
    rebuilt[flash_offset:flash_offset + len(flash)] = reconstructed
    header = header_decode(logical[:64])
    rebuilt[:64] = header_decode(header)
    for index in range(len(outer['entries'])):
        offset = 64 + index * 80
        rebuilt[offset:offset + 80] = header_decode(header_decode(logical[offset:offset + 80]))
    restored = bytearray()
    identity = outer['identity'].encode('ascii')
    for index in range(20):
        restored += rebuilt[index * 47:(index + 1) * 47]
        restored.append(identity[index] + index + 1 if index < len(identity) else 125)
    restored += rebuilt[940:]
    if restored != raw:
        raise ValueError('full FWSC no-op reconstruction differs')
    return dict(status='stock-inspected-noop-identical' if replacement is None else 'modified-app-inspected-model-only',
                packaging_ready=False,
                device_execution='unverified', identity=outer['identity'],
                flash_header_crc_verified=True, top=top, app_resource_blocks=blocks,
                spl_bank=dict(bytes=bank_size, load_address=bank_load,
                              header_crc_verified=True, data_crc_verified=True),
                bound_component_sha256={path: digest(data) for path, data in components.items()},
                nested_file_sha256={name: digest(data) for name, data in files.items()},
                stock_xip=dict(image_app_directory_offset=APP_BASE,
                               virtual_directory_base=XIP_BASE,
                               entry=blocks[0]['address'],
                               app_image_offset=APP_BASE + application['address'],
                               app_bytes=application['bytes'],
                               physical_image_base='ROM supplied; inspector has no device dump input',
                               evidence='stock metadata and static SPL trace; no device execution'),
                full_container_noop_identical=True, sha256=digest(raw),
                flash_payload_sha256=digest(flash), preserved_uninterpreted_app_tail_bytes=len(flash) - cursor,
                pending=['modified-image repack/CRC/address rules not implemented',
                         'auxiliary metadata/trailer/version and runtime XIP behavior require explanation',
                         'SPL handover/observable runtime and candidate/range recovery review unresolved; full-image/broken-app recovery unproven'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fwsc', type=Path)
    parser.add_argument('--stock', type=Path, required=True)
    parser.add_argument('--json', type=Path, help='new report; refuses overwrite')
    args = parser.parse_args()
    try:
        result = inspect_nested(args.fwsc.read_bytes(), args.stock)
        if args.json:
            with args.json.open('x') as output:
                json.dump(result, output, indent=2)
                output.write('\n')
    except (OSError, ValueError, UnicodeError, struct.error) as exc:
        parser.exit(1, f'inspect_stock_flash: {exc}\n')
    print(f"{result['identity']}: nested CRCs and guarded components checked, "
          'full FWSC no-op identical; packaging_ready=false')


if __name__ == '__main__':
    main()
