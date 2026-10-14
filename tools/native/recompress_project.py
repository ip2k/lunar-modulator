#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recompress LUNARB chunks with bounded raw DEFLATE; retain every raw chunk.

This offline host utility does not change records, enforce physical storage
ownership, or imply device/build admission. Python's standard-library zlib is
used only as an encoder; the target's existing fm1_state reader decodes the
result. Re-run under the desired host Python/zlib version for reproducibility.
"""
import argparse
import hashlib
from pathlib import Path
import struct
import sys
import zlib

# Allow direct invocation from any working directory, as used by image/profile
# preparation tools that execute this file rather than importing it.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools import lunar_state as ls

MAX_FILE = ls.BIN_MAX
DEFLATED = 1
WINDOW_BITS = -12
LEVEL = 6


def _raw_chunk(stored: bytes, flags: int, cap: int) -> bytes:
    if flags & ~DEFLATED:
        raise ValueError('unknown chunk flags')
    if flags & DEFLATED:
        if len(stored) < 5:
            raise ValueError('short DEFLATED chunk')
        expected = struct.unpack_from('<I', stored)[0]
        if expected > cap:
            raise ValueError('uncompressed chunk exceeds tag cap')
        dec = zlib.decompressobj(WINDOW_BITS)
        raw = dec.decompress(stored[4:], expected + 1)
        if len(raw) > expected or dec.unconsumed_tail:
            raise ValueError('DEFLATE output exceeds declared length')
        # A complete raw-DEFLATE stream reaches EOF during decompress(). Do
        # not call unbounded flush(): the declared size is the output budget.
        if len(raw) != expected or not dec.eof or dec.unused_data or dec.unconsumed_tail:
            raise ValueError('incomplete or trailing DEFLATE data')
        return raw
    if len(stored) > cap:
        raise ValueError('chunk exceeds tag cap')
    return stored


def recompress(data: bytes) -> tuple[bytes, dict]:
    # The canonical project parser applies header, directory, per-tag, record,
    # sequence, and decompression limits before any output is produced.
    records, _report = ls.read_bin(data)
    if len(data) > MAX_FILE:
        raise ValueError('input exceeds LUNARB bound')
    header_len, count, entry_size, _reserved, _old_total = struct.unpack_from('<HHHHI', data, 12)
    directory_end = header_len + count * entry_size
    old_entries = []
    previous = (directory_end + 4 + 3) & ~3
    for index in range(count):
        start = header_len + index * entry_size
        entry = data[start:start + entry_size]
        tag_bytes = entry[:4]
        version, flags, offset, length, _crc = struct.unpack_from('<HHIII', entry, 4)
        stored = data[offset:offset + length]
        tag = ls.TAGS.get(tag_bytes)
        if tag is None:
            # Preserve unknown ancillary chunks byte-for-byte. The canonical
            # reader already rejected unsupported critical chunks.
            raw, replacement, out_flags = None, stored, flags
        else:
            raw = _raw_chunk(stored, flags, ls.CAP[tag])
            # Never expand an already-compressed valid chunk merely because
            # this host zlib's output is larger. Keep the best known encoding.
            replacement, out_flags = raw, 0
            if flags & DEFLATED:
                replacement, out_flags = stored, DEFLATED
            if len(raw) >= 16:
                compressor = zlib.compressobj(LEVEL, zlib.DEFLATED, WINDOW_BITS)
                candidate = compressor.compress(raw) + compressor.flush()
                if not candidate:
                    raise ValueError('zlib returned an empty chunk')
                dec = zlib.decompressobj(WINDOW_BITS)
                check = dec.decompress(candidate, len(raw) + 1)
                if check != raw or not dec.eof or dec.unused_data or dec.unconsumed_tail:
                    raise ValueError('zlib round-trip failed')
                candidate_stored = struct.pack('<I', len(raw)) + candidate
                if len(candidate_stored) < len(replacement):
                    replacement = candidate_stored
                    out_flags = DEFLATED
        old_entries.append({
            'entry': entry, 'tag_bytes': tag_bytes, 'tag': tag,
            'version': version, 'flags': out_flags, 'old_flags': flags,
            'raw': raw, 'stored': replacement,
        })
    dir_end = header_len + count * entry_size
    base = (dir_end + 4 + 3) & ~3
    out_data = bytearray()
    out_entries = bytearray()
    offset = base
    for item in old_entries:
        out_data.extend(b'\0' * ((-len(out_data)) % 4))
        offset = base + len(out_data)
        stored = item['stored']
        prefix = struct.pack('<HHIII', item['version'], item['flags'], offset,
                             len(stored), zlib.crc32(stored) & 0xffffffff)
        out_entries.extend(item['tag_bytes'] + prefix + item['entry'][20:])
        out_data.extend(stored)
    total = base + len(out_data)
    if total > MAX_FILE:
        raise ValueError('recompressed container exceeds LUNARB bound')
    header = bytearray(data[:header_len])
    struct.pack_into('<I', header, 20, total)
    struct.pack_into('<I', header, 28, zlib.crc32(header[:28]) & 0xffffffff)
    result = bytes(header + out_entries + struct.pack('<I', zlib.crc32(out_entries) & 0xffffffff)
                   + b'\0' * (base - dir_end - 4) + out_data)
    if len(result) != total:
        raise AssertionError('internal output length mismatch')
    # Final validation also verifies raw chunk order and complete semantic
    # decoding, before caller writes anything.
    roundtrip, _ = ls.read_bin(result)
    if roundtrip != records:
        raise ValueError('decoded records changed')
    return result, {
        'input_bytes': len(data), 'output_bytes': len(result),
        'saved_bytes': len(data) - len(result),
        'input_sha256': hashlib.sha256(data).hexdigest(),
        'output_sha256': hashlib.sha256(result).hexdigest(),
        'chunks': count,
        'deflated_chunks': sum(bool(x['flags'] & DEFLATED) for x in old_entries),
        'previously_deflated_chunks': sum(bool(x['old_flags'] & DEFLATED) for x in old_entries),
        'records_equal': True, 'zlib_compile': zlib.ZLIB_VERSION,
        'zlib_runtime': zlib.ZLIB_RUNTIME_VERSION,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output already exists; refusing to overwrite')
    try:
        source = args.input.read_bytes()
        encoded, report = recompress(source)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('xb') as f:
            f.write(encoded)
    except (OSError, ValueError, ls.Refused, zlib.error) as exc:
        parser.error(str(exc))
    print(report)


if __name__ == '__main__':
    main()
