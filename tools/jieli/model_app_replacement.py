#!/usr/bin/env python3
"""MIT. Model a bounded stock V15 app replacement in memory; emit JSON only.

Preserves identity/version, allocations, auxiliary bytes, stock components and
unused app tail. A model with the stock running identity is not installable.
No binary output, transport, device access or arbitrary version override.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from audit_link import Elf, audit
from diagnostic_report import report
from inspect_fwsc import crc16, header_decode, inspect, sfc_decode
from inspect_stock_flash import APP_BASE, inspect_nested, _inspect_app_replacement


def logical(raw):
    return bytearray(b''.join(raw[i:i + 47] for i in range(0, 960, 48)) + raw[960:])


def physical(image, original):
    out = bytearray()
    for index in range(20):
        out += image[index * 47:(index + 1) * 47]
        out.append(original[index * 48 + 47])
    return bytes(out + image[940:])


def checksum_record(data, offset, payload, size=None):
    struct.pack_into('<H', data, offset + 2, crc16(payload))
    if size is not None:
        struct.pack_into('<I', data, offset + 8, size)
    struct.pack_into('<H', data, offset, crc16(data[offset + 2:offset + 32]))


def repair_outer(image, flash_index, flash):
    offset = 64 + flash_index * 80
    entry = bytearray(header_decode(image[offset:offset + 80]))
    struct.pack_into('<H', entry, 4, crc16(flash))
    image[offset:offset + 80] = header_decode(entry)
    header = bytearray(header_decode(image[:64]))
    count, = struct.unpack_from('<H', header, 8)
    struct.pack_into('<H', header, 2, crc16(image[64:64 + count * 80]))
    struct.pack_into('<H', header, 0, crc16(header[2:]))
    image[:64] = header_decode(header)


def _build(raw, stock, app):
    """Private in-memory construction; the public tool returns no image bytes."""
    baseline = inspect_nested(raw, stock)
    area = baseline['app_resource_blocks'][0]
    child = next(item for item in area['children'] if item['name'] == 'app.bin')
    if not 0 < len(app) <= child['bytes']:
        raise ValueError('replacement must be nonempty and fit original app extent')
    outer = inspect(raw, stock)
    item = next(item for item in outer['entries'] if item['name'] == 'flash.bin')
    image = logical(raw)
    start, length = item['offset'], item['bytes']
    flash = bytearray(image[start:start + length])
    decoded = bytearray(sfc_decode(flash[APP_BASE:], 0))
    app_offset = child['address']
    decoded[app_offset:app_offset + len(app)] = app
    checksum_record(decoded, child['header_offset'] - APP_BASE, app, len(app))
    checksum_record(decoded, 0, decoded[32:area['bytes']])
    flash[APP_BASE:] = sfc_decode(decoded, 0)
    image[start:start + length] = flash
    repair_outer(image, item['index'], flash)
    return physical(image, raw)


def changed_ranges(before, after):
    if len(before) != len(after):
        raise ValueError('model length changed')
    ranges, start = [], None
    for index, (left, right) in enumerate(zip(before, after)):
        if left != right and start is None:
            start = index
        elif left == right and start is not None:
            ranges.append([start, index])
            start = None
    if start is not None:
        ranges.append([start, len(before)])
    return ranges


def verify_replacement(raw, modeled, stock, app):
    """Check modified layers and exact allowed mutations, without rebuilding."""
    before = inspect_nested(raw, stock)
    after = _inspect_app_replacement(modeled, stock, app)
    old_outer, new_outer = inspect(raw, stock), inspect(modeled, stock)
    old, new = logical(raw), logical(modeled)
    old_item = next(item for item in old_outer['entries'] if item['name'] == 'flash.bin')
    new_item = next(item for item in new_outer['entries'] if item['name'] == 'flash.bin')
    if len(old) != len(new):
        raise ValueError('model length changed')
    if any(raw[i * 48 + 47] != modeled[i * 48 + 47] for i in range(20)):
        raise ValueError('identity markers changed')
    if header_decode(old[:64])[4:] != header_decode(new[:64])[4:]:
        raise ValueError('outer metadata changed')
    for left, right in zip(old_outer['entries'], new_outer['entries']):
        offset = 64 + left['index'] * 80
        a, b = header_decode(old[offset:offset + 80]), header_decode(new[offset:offset + 80])
        if left['name'] == 'flash.bin':
            if a[:4] != b[:4] or a[6:] != b[6:]:
                raise ValueError('flash allocation metadata changed')
        elif a != b:
            raise ValueError('non-flash entry changed')
    start, size = old_item['offset'], old_item['bytes']
    if (start, size) != (new_item['offset'], new_item['bytes']):
        raise ValueError('flash placement changed')
    # Everything except encrypted outer header/list and flash payload is exact.
    table_end = 64 + len(old_outer['entries']) * 80
    if old[table_end:start] != new[table_end:start] or old[start + size:] != new[start + size:]:
        raise ValueError('outer padding/auxiliary/trailer bytes changed')
    if old[start:start + APP_BASE] != new[start:start + APP_BASE]:
        raise ValueError('SPL/config/top bytes changed')
    a = bytearray(sfc_decode(old[start + APP_BASE:start + size], 0))
    b = bytearray(sfc_decode(new[start + APP_BASE:start + size], 0))
    area = before['app_resource_blocks'][0]
    child = next(item for item in area['children'] if item['name'] == 'app.bin')
    if not 0 < len(app) <= child['bytes']:
        raise ValueError('replacement must be nonempty and fit original app extent')
    entry = after['stock_xip']
    if entry['entry'] != before['stock_xip']['entry'] or entry['app_image_offset'] != before['stock_xip']['app_image_offset']:
        raise ValueError('app placement changed')
    # Mask only changed CRC words, app length, and supplied replacement bytes.
    child_offset = child['header_offset'] - APP_BASE
    allowed = [(0, 4), (child_offset, child_offset + 4),
               (child_offset + 8, child_offset + 12),
               (child['address'], child['address'] + len(app))]
    for lo, hi in allowed:
        a[lo:hi] = b[lo:hi]
    if a != b:
        raise ValueError('decoded bytes outside replacement contract changed')
    ranges = changed_ranges(raw, modeled)
    return dict(status='offline-app-replacement-model-verified', packaging_ready=False,
                binary_emitted=False, device_execution='unverified',
                identity=old_outer['identity'], identity_changed=False,
                stock_extent_bytes=child['bytes'], replacement_bytes=len(app),
                preserved_unused_app_tail_bytes=child['bytes'] - len(app),
                app_image_offset=entry['app_image_offset'], entry=entry['entry'],
                resource_and_partition_positions_unchanged=True,
                stock_boot_config_resource_components_unchanged=True,
                auxiliary_and_trailer_bytes_unchanged=True,
                original_sha256=hashlib.sha256(raw).hexdigest(),
                modeled_sha256=hashlib.sha256(modeled).hexdigest(),
                app_sha256=hashlib.sha256(app).hexdigest(),
                changed_physical_ranges_end_exclusive=ranges,
                changed_physical_bytes=sum(hi - lo for lo, hi in ranges),
                modified_nested_check=after,
                next_gates=['identity/version and remaining trailer semantics before emitting a container',
                            'observable startup and explicit clock/core/IRQ/watchdog/exception policy',
                            'reviewed device range/candidate and fresh backups; full-image/broken-app recovery unproven'])


def model(raw, stock, elf, app):
    link = audit([('diagnostic.elf', Elf(elf))], [('diagnostic.bin', app)], True, runtime='sdk-free')
    layout = report(elf, app, link)
    modeled = _build(raw, stock, app)
    result = verify_replacement(raw, modeled, stock, app)
    result.update(link_audit=link, diagnostic_layout=layout)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fwsc', type=Path)
    parser.add_argument('--stock', type=Path, required=True)
    parser.add_argument('--elf', type=Path, required=True)
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--json', type=Path, required=True, help='new report; refuses overwrite')
    args = parser.parse_args()
    try:
        result = model(args.fwsc.read_bytes(), args.stock, args.elf.read_bytes(), args.app.read_bytes())
        with args.json.open('x') as output:
            json.dump(result, output, indent=2)
            output.write('\n')
    except (OSError, ValueError, KeyError, UnicodeError, struct.error) as exc:
        parser.exit(1, f'model_app_replacement: {exc}\n')
    print(f"{result['identity']}: bounded app model independently revalidated; JSON only, packaging_ready=false")


if __name__ == '__main__':
    main()
