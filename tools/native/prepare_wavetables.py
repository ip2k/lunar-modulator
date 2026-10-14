#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate private startup-decoded tables; keep upstream consumers unchanged."""
import json
from pathlib import Path
import re
import zlib

from evaluate_wavetables import ASSETS, ROOT, asset_bytes, delta_encode, digest


def prepare(out, namespaces=('plaits', 'braids'), *, storage_section='.pool.wavetable'):
    out = Path(out)
    records, declarations = [], []
    for relative, symbol, width, size in ASSETS:
        namespace = Path(relative).parent.name
        if namespace not in namespaces:
            continue
        source = (ROOT / relative).read_text()
        raw = asset_bytes(source, symbol, width, size)
        compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
        packed = compressor.compress(delta_encode(raw, width)) + compressor.flush()
        # Only the defining translation unit gets a mutable declaration.
        # Consumers retain their pinned extern-const views; decoding finishes
        # before any consumer runs and the samples never change afterward.
        mangled = f'_ZN{len(namespace)}{namespace}{len(symbol)}{symbol}E'
        kind = 'int16_t' if width == 2 else 'uint8_t'
        header_name = f'resources_{namespace}.h'
        header = (ROOT / relative).with_suffix('.h').read_text()
        declaration = f'extern const {kind} {symbol}[];'
        if header.count(declaration) != 1:
            raise ValueError('Pinned resource declaration changed: ' + symbol)
        (out / header_name).write_text(header.replace(declaration, f'extern {kind} {symbol}[];'))
        source = source.replace(f'"{namespace}/resources.h"', f'"{header_name}"')
        definition = (f'{kind} {symbol}[{size // width}] '
                      f'__attribute__((section("{storage_section}"), aligned(16), used));')
        pattern = r'const\s+\w+\s+' + symbol + r'\s*\[[^\]]*\]\s*=\s*\{[^}]+\};'
        source, count = re.subn(pattern, lambda _: definition, source, flags=re.S)
        if count != 1:
            raise ValueError('Expected one pinned resource definition: ' + symbol)
        path = out / f'resources_{namespace}.cc'
        path.write_text(source)
        values = ','.join(str(v) for v in packed)
        declarations += [f'extern unsigned char lunar_waves_{namespace}[{size}] __asm__("{mangled}");',
                         f'static const unsigned char packed_{namespace}[] = {{{values}}};']
        h = 2166136261
        for byte in raw:
            h = ((h ^ byte) * 16777619) & 0xffffffff
        records.append(dict(namespace=namespace, symbol=symbol, width=width,
                            raw_bytes=size, packed_bytes=len(packed), raw_sha256=digest(raw),
                            packed_sha256=digest(packed), fnv32=h,
                            generated_source_sha256=digest(path.read_bytes())))
    declarations += ['static const lunar_wave_table_t lunar_wave_tables[] = {']
    for record in records:
        n = record['namespace']
        declarations += [f'{{lunar_waves_{n}, {record["raw_bytes"]}u, packed_{n}, '
                         f'sizeof packed_{n}, {record["width"]}u, {record["fnv32"]}u}},']
    declarations += ['};']
    (out / 'wave_tables.inc').write_text('\n'.join(declarations) + '\n')
    (out / 'wave_tables.json').write_text(json.dumps(records, indent=2) + '\n')
    return records
