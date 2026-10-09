#!/usr/bin/env python3
"""Inspect the stock FM-1 FWSC/UFW envelope offline; never build or transmit.

Format evidence: kagaimiq's MIT jl-misctools fwunpack_newfw.py and
AL-255's FM-1-RE fm1_ota.py, checked against the local stock V15 package.
This independently authored reader validates only established outer layers.
Nested flash rewrite and remaining metadata rules remain packing gates.
"""
import argparse
import binascii
import hashlib
import json
import re
import struct
from pathlib import Path

from package_guard import check_package


PREFIX = 20 * 48
LOGICAL_PREFIX = 20 * 47
PLAIN_TYPES = {0, 2, 100, 255}
ENCRYPTED_TYPES = {50, 52, 251, 161}
STOCK_CHIP_KEY = 0x980f


def crc16(data):
    """Poly 0x1021, initial 0, no reflection/XOR (CRC-16/XMODEM)."""
    return binascii.crc_hqx(data, 0)


def header_decode(data, initial=0xffff):
    """Symmetric ENC XOR stream; restart 0xffff at each header/entry."""
    state = initial
    output = bytearray()
    for value in data:
        output.append(value ^ (state & 255))
        state = ((state << 1) ^ (0x1021 if state & 0x8000 else 0)) & 0xffff
    return bytes(output)


def sfc_decode(data, logical_offset):
    """Stock auxiliary SFC blocks use container origin zero, not entry origin."""
    if logical_offset % 32:
        raise ValueError("unaligned SFC auxiliary payload")
    return b''.join(header_decode(data[index:index + 32],
                                 STOCK_CHIP_KEY ^ ((logical_offset + index) >> 2))
                    for index in range(0, len(data), 32))


def cstring(data):
    name, separator, padding = data.partition(b'\0')
    if not separator or any(padding):
        raise ValueError("unterminated or nonzero-padded name")
    return name.decode('ascii')


def inspect(raw, stock=None):
    if len(raw) < PREFIX:
        raise ValueError("truncated 20-slot FWSC header")
    markers = [raw[index * 48 + 47] for index in range(20)]
    end = next((index for index, value in enumerate(markers) if value == 125), 20)
    if any(value != 125 for value in markers[end:]):
        raise ValueError("noncontiguous identity markers")
    identity = bytes((value - index - 1) & 255 for index, value in enumerate(markers[:end])).decode('ascii')
    if not re.fullmatch(r'FM-1_[0-9]{3}', identity):
        raise ValueError("unsupported FWSC identity")
    logical = b''.join(raw[offset:offset + 47] for offset in range(0, PREFIX, 48)) + raw[PREFIX:]
    header = header_decode(logical[:64])
    hcrc, listcrc, image_size, count, unknown16, unknown32, chip = struct.unpack('<HHIHHI48s', header)
    if crc16(header[2:]) != hcrc:
        raise ValueError("UFW header CRC mismatch")
    if image_size != len(logical):
        raise ValueError("UFW logical size mismatch")
    if cstring(chip) != 'AC791N':
        raise ValueError("unsupported UFW chip")
    if not 1 <= count <= (LOGICAL_PREFIX - 64) // 80:
        raise ValueError("entry list exceeds established FWSC header slots")
    table_end = 64 + count * 80
    table = logical[64:table_end]
    if crc16(table) != listcrc:
        raise ValueError("UFW stored entry-list CRC mismatch")
    entries, ranges, pending = [], [], []
    for index in range(count):
        item = header_decode(table[index * 80:(index + 1) * 80])
        kind, ordinal, checksum, unknown, offset, size, allocated, extra, name = struct.unpack('<HHHHIII44s16s', item)
        name = cstring(name)
        if ordinal != index or any(entry['name'] == name for entry in entries):
            raise ValueError("duplicate name or unexpected entry index")
        if kind not in PLAIN_TYPES | ENCRYPTED_TYPES:
            raise ValueError("unsupported payload type")
        if allocated < size or offset < LOGICAL_PREFIX or offset + allocated > len(logical):
            raise ValueError("entry allocation outside logical image")
        if allocated:
            if any(offset < right and left < offset + allocated for left, right in ranges):
                raise ValueError("overlapping entry allocations")
            ranges.append((offset, offset + allocated))
        payload = logical[offset:offset + size]
        decoded = sfc_decode(payload, offset) if kind in ENCRYPTED_TYPES else payload
        if crc16(decoded) != checksum:
            raise ValueError(f"payload CRC mismatch: {name}")
        entries.append(dict(name=name, type=kind, index=ordinal, offset=offset,
                            physical_offset=offset + 20, bytes=size, allocated_bytes=allocated,
                            crc16=checksum, crc_verified=True,
                            encoding='sfc-stock-key-logical-origin-zero' if kind in ENCRYPTED_TYPES else 'raw',
                            sha256=hashlib.sha256(payload).hexdigest(),
                            decoded_sha256=hashlib.sha256(decoded).hexdigest()))
    by_name = {entry['name']: entry for entry in entries}
    if by_name.get('flash.bin', {}).get('type') != 0 or by_name.get('ota.bin', {}).get('type') != 100:
        raise ValueError("missing established flash/OTA entries")
    tail = by_name.get('tail.bin', {})
    if (tail.get('type') != 255 or tail.get('offset', 0) + tail.get('bytes', 0) != len(logical)
            or logical[-16:-11] != b'JLUFW'):
        raise ValueError("missing UFW trailer")
    if stock is not None:
        guard = check_package(stock, stock)
        if not guard['passed']:
            raise ValueError("stock reference failed package_guard")
        ota = by_name['ota.bin']
        if logical[ota['offset']:ota['offset'] + ota['bytes']] != (Path(stock) / 'ota.bin').read_bytes():
            raise ValueError("container OTA differs from guarded stock reference")
    pending.extend([
        "nested flash/JLFS/SFC repack and all nested CRCs not verified by this reader",
        "container flash/config/SPL correspondence with unpacked guarded components not established",
        "remaining UFW metadata/trailer fields and device version-acceptance rules not established",
    ])
    return dict(status='inspected-incomplete', packaging_ready=False, device_execution='unverified',
                identity=identity, chip='AC791N', physical_bytes=len(raw), logical_bytes=len(logical),
                crc='CRC-16/XMODEM (poly 0x1021, init 0)',
                header_crc_verified=True, entry_list_crc_verified=True,
                unknown_header_fields=[unknown16, unknown32], entries=entries,
                sha256=hashlib.sha256(raw).hexdigest(), pending=pending,
                stock_ota_guard_verified=stock is not None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fwsc', type=Path)
    parser.add_argument('--stock', type=Path, help='optional guarded unpacked stock tree with ota.bin')
    parser.add_argument('--json', type=Path, help='new report file; refuses overwrite')
    args = parser.parse_args()
    try:
        result = inspect(args.fwsc.read_bytes(), args.stock)
        if args.json:
            with args.json.open('x') as output:
                json.dump(result, output, indent=2)
                output.write('\n')
    except (OSError, ValueError, UnicodeError, struct.error) as exc:
        parser.exit(1, f'inspect_fwsc: {exc}\n')
    print(f"{result['identity']}: outer header/list and all payload CRCs checked; "
          f"{len(result['pending'])} pending gates, packaging_ready=false")


if __name__ == '__main__':
    main()
