#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Measure one of sixteen lossless storage profiles; no firmware/device I/O.

Uses a pinned, unmodified tinf checkout supplied separately. The C decoder,
not Python's inflater, must reconstruct every retained wavetable byte.
Decoder object size is measured separately, not claimed as a full-app fit.
"""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zlib

ROOT = Path(__file__).resolve().parents[2]
TINF_REVISION = '57ffa1f1d5e3dde19011b2127bd26d01689b694b'
TINF_PINS = {
    'src/tinf.h': 'e5c3a9e9d54ed69c5b36c1b09c78defac1ea1f83cf97abeb4fdf16853dcd7f68',
    'src/tinflate.c': 'b3240fa0c9e8ef385667680a321dd5b0bfefb9871996366c0a7d5f6a0309cb6e',
    'LICENSE': 'f39b507b81b9ba1edce7fe742bbd68fda4b852063ce7299274ae97991d48814b',
}
ASSETS = (
    ('engines/third_party/mutable/plaits/resources.cc', 'wav_integrated_waves', 2, 50688),
    ('engines/third_party/mutable/braids/resources.cc', 'wt_waves', 1, 33024),
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def asset_bytes(source, symbol, width, expected_size):
    matches = re.findall(r'\b' + re.escape(symbol) + r'\s*\[[^\]]*\]\s*=\s*\{([^}]+)\}',
                         source, re.S)
    if len(matches) != 1:
        raise ValueError('Expected one table definition: ' + symbol)
    body = re.sub(r'/\*.*?\*/|//[^\n]*', '', matches[0], flags=re.S)
    values = [int(v.strip(), 0) for v in body.split(',') if v.strip()]
    if any(not -(1 << (8 * width - 1)) <= v < (1 << (8 * width)) for v in values):
        raise ValueError('Table value out of range: ' + symbol)
    raw = b''.join((v & ((1 << (8 * width)) - 1)).to_bytes(width, 'little') for v in values)
    if len(raw) != expected_size:
        raise ValueError('Table size changed: ' + symbol)
    return raw


def delta_encode(raw, width):
    mask, previous, result = (1 << (width * 8)) - 1, 0, bytearray()
    for n in range(0, len(raw), width):
        value = int.from_bytes(raw[n:n + width], 'little')
        result += ((value - previous) & mask).to_bytes(width, 'little')
        previous = value
    return bytes(result)


def delta_decode(raw, width):
    mask, value, result = (1 << (width * 8)) - 1, 0, bytearray()
    for n in range(0, len(raw), width):
        value = (value + int.from_bytes(raw[n:n + width], 'little')) & mask
        result += value.to_bytes(width, 'little')
    return bytes(result)


def decode_checked(decode, packed, expected):
    # Surround output with sentinels, including tests where capacity is too small.
    storage = ctypes.create_string_buffer(len(expected) + 32)
    ctypes.memset(storage, 0xA5, len(storage))
    destination = ctypes.byref(storage, 16)
    count = ctypes.c_uint(len(expected))
    status = decode(destination, ctypes.byref(count), packed, len(packed))
    if status != 0 or count.value != len(expected):
        raise ValueError('C inflate rejected valid block')
    if storage.raw[:16] != b'\xA5' * 16 or storage.raw[-16:] != b'\xA5' * 16:
        raise ValueError('C inflate overwrote output guards')
    result = storage.raw[16:-16]
    if result != expected:
        raise ValueError('C inflate changed table bytes')
    ctypes.memset(storage, 0xA5, len(storage))
    count = ctypes.c_uint(len(expected) - 1)
    if decode(destination, ctypes.byref(count), packed, len(packed)) == 0:
        raise ValueError('C inflate accepted insufficient output capacity')
    if storage.raw[:16] != b'\xA5' * 16 or storage.raw[16 + len(expected) - 1:] != b'\xA5' * 17:
        raise ValueError('C inflate exceeded declared capacity')
    count = ctypes.c_uint(len(expected))
    if decode(destination, ctypes.byref(count), packed, 0) == 0:
        raise ValueError('C inflate accepted empty compressed input')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tinf', type=Path, required=True)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--shard', type=int, choices=range(16), required=True)
    args = parser.parse_args()
    tinf, tc, out = (p.resolve() for p in (args.tinf, args.toolchain, args.out))
    for name, expected in TINF_PINS.items():
        if digest((tinf / name).read_bytes()) != expected:
            parser.error('Pinned tinf source mismatch: ' + name)
    out.mkdir(parents=True, exist_ok=False)
    source = tinf / 'src/tinflate.c'
    shared = out / 'libtinf.so'
    subprocess.run(['cc', '-O2', '-DNDEBUG', '-shared', '-fPIC', str(source), '-o', str(shared)],
                   check=True)
    library = ctypes.CDLL(str(shared))
    decode = library.tinf_uncompress
    decode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint), ctypes.c_void_p, ctypes.c_uint]
    decode.restype = ctypes.c_int
    obj = out / 'tinf.o'
    flags = ['-target', 'pi32v2', '-mcpu=r3', '-mfprev1', '-Oz', '-DNDEBUG',
             '-ffreestanding', '-fno-builtin', '-ffunction-sections', '-fdata-sections',
             '-isystem', str(tc / 'pi32v2/include')]
    subprocess.run([str(tc / 'common/bin/clang'), *flags, '-c', str(source), '-o', str(obj)],
                   check=True)
    linked = out / 'tinf-linked.o'
    subprocess.run([str(tc / 'pi32v2/bin/ld'), '-r', '--gc-sections', '-u', 'tinf_uncompress',
                    str(obj), '-o', str(linked)], check=True)
    sections = subprocess.check_output([str(tc / 'common/bin/objdump'), '-h', str(linked)], text=True)
    (out / 'decoder-sections.txt').write_text(sections)
    sizes = {name: int(size, 16) for name, size in
             re.findall(r'^\s*\d+\s+(\S+)\s+([0-9a-fA-F]+)\s', sections, re.M)}
    undefined = subprocess.check_output([str(tc / 'pi32v2/bin/nm'), '-u', str(linked)], text=True)
    if undefined.strip():
        raise ValueError('Unexpected decoder runtime dependency: ' + undefined)
    block_size = (512, 1024, 4096, 65536)[args.shard % 4]
    delta, level = bool(args.shard & 4), (9 if args.shard & 8 else 1)
    rows = []
    for relative, symbol, width, expected_size in ASSETS:
        source_bytes = (ROOT / relative).read_bytes()
        raw = asset_bytes(source_bytes.decode(), symbol, width, expected_size)
        payload, offsets, compressed_blocks = bytearray(), [0], 0
        for start in range(0, len(raw), block_size):
            block = raw[start:start + block_size]
            encoded = delta_encode(block, width) if delta else block
            compressor = zlib.compressobj(level, wbits=-15)
            packed = compressor.compress(encoded) + compressor.flush()
            decoded = decode_checked(decode, packed, encoded)
            if (delta_decode(decoded, width) if delta else decoded) != block:
                raise ValueError('Delta reconstruction changed samples')
            compressed = len(packed) < len(encoded)
            payload += packed if compressed else encoded
            # Top bit marks raw blocks; offsets need four bytes at these sizes.
            offsets[-1] |= 0 if compressed else 0x80000000
            offsets.append(len(payload))
            compressed_blocks += compressed
        (out / (symbol + '.deflate-or-raw')).write_bytes(payload)
        index = b''.join(v.to_bytes(4, 'little') for v in offsets)
        (out / (symbol + '.index')).write_bytes(index)
        rows.append(dict(symbol=symbol, source_sha256=digest(source_bytes), raw_sha256=digest(raw),
                         raw_bytes=len(raw), payload_bytes=len(payload), index_bytes=len(index),
                         blocks=len(offsets) - 1, compressed_blocks=compressed_blocks,
                         largest_output_block=min(block_size, len(raw)),
                         bytes_saved=len(raw) - len(payload) - len(index)))
    decoder_bytes = sum(size for name, size in sizes.items()
                        if name.startswith(('.text', '.rodata', '.data', '.sdata')))
    report = dict(shard=args.shard, block_bytes=block_size, delta=delta, level=level,
                  tinf_revision=TINF_REVISION, tinf_source_sha256=TINF_PINS,
                  target_flags=flags, target_decoder_sections=sizes,
                  target_decoder_object_sha256=digest(linked.read_bytes()),
                  isolated_decoder_bytes=decoder_bytes, assets=rows,
                  table_savings_less_isolated_decoder=sum(r['bytes_saved'] for r in rows) - decoder_bytes,
                  all_c_roundtrips_and_capacity_checks_passed=True,
                  full_application_fit_verified=False, device_timing_verified=False,
                  hardware_candidate=False, installable=False)
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
