# SPDX-License-Identifier: MIT
"""Offline FM-1_092 expanded geometry, without provenance or write admission.

This does not support V15 VM relocation, emit an OTA package, validate an ELF,
or establish settings migration. Physical callers need those separate gates.
"""
import struct

import raw_flash_profile as stock
from inspect_stock_flash import record, payload_crc

AREA_END = 0xD9000
APP_ORIGIN = 0x4120
APP_BUDGET = AREA_END - APP_ORIGIN - 384 - 2940


def align4(value):
    return (value + 3) & ~3


def extents(app):
    if not isinstance(app, bytes) or not 0 < len(app) <= APP_BUDGET or len(app) % 4:
        raise ValueError('Expanded application must fit the aligned named budget')
    tool_start = align4(APP_ORIGIN + len(app))
    cfg_start = align4(tool_start + 383)
    end = align4(cfg_start + stock.CFG_BYTES)
    if end > AREA_END:
        raise ValueError('Expanded records overlap VM')
    return tool_start, cfg_start, end


def _patch_record(data, offset, **fields):
    formats = {'crc16': ('<H', 2), 'address': ('<I', 4), 'bytes': ('<I', 8)}
    for name, value in fields.items():
        fmt, delta = formats[name]
        struct.pack_into(fmt, data, offset + delta, value)
    struct.pack_into('<H', data, offset, stock.crc16(data[offset + 2:offset + 32]))


def construct_geometry(baseline_a, baseline_b, reference, app):
    """Return a private candidate; matching inputs alone are not backup admission."""
    if baseline_a != baseline_b:
        raise ValueError('Baseline copies differ')
    decoded, _ = stock._parse(baseline_a, reference)
    tool_start, cfg_start, end = extents(app)
    candidate = bytearray(decoded)
    candidate[stock.APP_BASE:AREA_END] = b'\xff' * (AREA_END - stock.APP_BASE)
    candidate[stock.APP_BASE:APP_ORIGIN] = decoded[stock.APP_BASE:APP_ORIGIN]
    candidate[APP_ORIGIN:APP_ORIGIN + len(app)] = app
    candidate[tool_start:tool_start + 383] = decoded[stock.CFG_TOOL_OFFSET:stock.CFG_OFFSET]
    candidate[cfg_start:cfg_start + stock.CFG_BYTES] = decoded[stock.CFG_OFFSET:stock.CFG_OFFSET + stock.CFG_BYTES]
    _patch_record(candidate, stock.APP_BASE + 32, bytes=len(app), crc16=stock.crc16(app))
    _patch_record(candidate, stock.APP_BASE + 64, address=tool_start - stock.APP_BASE)
    _patch_record(candidate, stock.APP_BASE, bytes=cfg_start - stock.APP_BASE,
                  crc16=stock.crc16(candidate[stock.APP_BASE + 32:cfg_start]))
    # Preserve physical boot headers/loader and VM/BTIF/USR/key banks exactly.
    target = (baseline_a[:stock.APP_BASE]
              + stock.sfc_decode(candidate[stock.APP_BASE:AREA_END], 0)
              + baseline_a[AREA_END:])
    return target, validate_geometry(baseline_a, target, reference, app)


def validate_geometry(baseline, target, reference, app):
    """Independently parse records, extents, CRCs and immutable raw ranges."""
    original, components = stock._parse(baseline, reference)
    tool_start, cfg_start, end = extents(app)
    if not isinstance(target, bytes) or len(target) != stock.FLASH_BYTES:
        raise ValueError('Complete expanded raw image required')
    if target[:stock.APP_BASE] != baseline[:stock.APP_BASE] or target[AREA_END:] != baseline[AREA_END:]:
        raise ValueError('Protected physical boot or reserved bank bytes differ')
    decoded = bytearray(target)
    decoded[stock.APP_BASE:AREA_END] = stock.sfc_decode(target[stock.APP_BASE:AREA_END], 0)
    area = record(decoded, stock.APP_BASE)
    original_area = record(original, stock.APP_BASE)
    # Only the area's CRC and extent may change; entry/flags/terminal/name stay.
    for field in ('name', 'address', 'flags', 'reserved', 'terminal', 'name_tail_hex'):
        if area[field] != original_area[field]:
            raise ValueError('Expanded area descriptor differs: ' + field)
    if area['bytes'] != cfg_start - stock.APP_BASE:
        raise ValueError('Expanded area extent differs')
    payload_crc(area, decoded[stock.APP_BASE + 32:cfg_start])
    children = [record(decoded, stock.APP_BASE + 32 + i * 32) for i in range(6)]
    original_children = [record(original, stock.APP_BASE + 32 + i * 32) for i in range(6)]
    for i, (item, before) in enumerate(zip(children, original_children)):
        for field in ('name', 'flags', 'reserved', 'terminal', 'name_tail_hex'):
            if item[field] != before[field]:
                raise ValueError('Expanded child descriptor differs')
        if i >= 2 and item != before:
            raise ValueError('Reserved descriptor changed')
    application, tool = children[:2]
    if (application['address'], application['bytes']) != (0x120, len(app)):
        raise ValueError('Expanded application entry/extent differs')
    if (tool['address'], tool['bytes']) != (tool_start - stock.APP_BASE, 383):
        raise ValueError('Expanded tool extent differs')
    payload_crc(application, decoded[APP_ORIGIN:APP_ORIGIN + len(app)])
    payload_crc(tool, decoded[tool_start:tool_start + 383])
    if decoded[APP_ORIGIN:APP_ORIGIN + len(app)] != app:
        raise ValueError('Expanded application contents differ')
    if decoded[tool_start:tool_start + 383] != original[stock.CFG_TOOL_OFFSET:stock.CFG_OFFSET]:
        raise ValueError('Preserved configuration tool differs')
    if decoded[cfg_start:cfg_start + stock.CFG_BYTES] != original[stock.CFG_OFFSET:stock.CFG_OFFSET + stock.CFG_BYTES]:
        raise ValueError('Preserved configuration contents differ')
    # Unnamed bytes are deterministic erased padding, except the pinned directory gap.
    if decoded[0x40E0:APP_ORIGIN] != original[0x40E0:APP_ORIGIN]:
        raise ValueError('Pinned directory gap differs')
    for lo, hi in ((APP_ORIGIN + len(app), tool_start),
                   (tool_start + 383, cfg_start),
                   (cfg_start + stock.CFG_BYTES, AREA_END)):
        if decoded[lo:hi] != b'\xff' * (hi - lo):
            raise ValueError('Expanded padding differs')
    return dict(profile='expanded-d9000-recorded-092', app_bytes=len(app),
                app_sha256=stock.digest(app), target_sha256=stock.digest(target),
                tool_start=tool_start, cfg_start=cfg_start, records_end=end,
                protected_raw_ranges_identical=True, configuration_contents_identical=True,
                baseline_components=components, geometry_verified=True,
                provenance_verified=False, elf_verified=False, ota_package_verified=False,
                settings_migration_verified=False, hardware_admitted=False, installable=False)
