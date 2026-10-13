#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate and flatten the native probe; this does not admit a hardware write."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'jieli'))
from audit_link import Elf, EM_PI32V2, ET_EXEC, audit, collect_sources, relative_call_payloads, stub_call_boundary_patterns

FLASH = 0x02000120
ENTRY_GUARD = bytes.fromhex('04818000600064e00036835fc3ff08fec70183e81a00')
REGIONS = {
    '.text': (FLASH, FLASH + 0x8DFBC, 1, 6),
    '.ram_text': (0x01C00000, 0x01C06000, 1, 6),
    '.data': (0x01C08000, 0x01C20000, 1, 3),
    '.bss': (0x01C08000, 0x01C20000, 8, 3),
    '.pool': (0x01C20000, 0x01C74000, 8, 3),
    '.noinit': (0x01C7C000, 0x01C7FD50, 8, 3),
}


def flatten(data, layout='legacy'):
    if layout not in ('legacy', 'combined'):
        raise ValueError('Unknown RAM layout')
    regions = dict(REGIONS)
    if layout == 'combined':
        for name in ('.data', '.bss', '.pool'):
            lo, _, kind, flags = regions[name]
            regions[name] = (0x01C08000, 0x01C74000, kind, flags)
    image = Elf(data)
    if (image.e_type, image.e_machine) != (ET_EXEC, EM_PI32V2):
        raise ValueError('Requires linked pi32v2 executable')
    if struct.unpack_from('<I', data, 24)[0] != FLASH or image.symbol_value('_start') != FLASH:
        raise ValueError('Wrong entry address')
    if image.undefined_symbols():
        raise ValueError('Unresolved symbols')
    if (image.read(FLASH, len(ENTRY_GUARD)) != ENTRY_GUARD
            or image.symbol_value('lunar_entry_rejected') != FLASH + 0x4A
            or image.read(FLASH + 0x4A, 2) != bytes.fromhex('f79f')):
        raise ValueError('Missing exact stack-free core/pointer entry guard')
    for name, value in {'_guard0': 0x01C74000, '_ustack_lo': 0x01C74100,
                        '_ustack_top': 0x01C7A000, '_guard1': 0x01C7A000,
                        '_sstack_lo': 0x01C7A100, '_sstack_top': 0x01C7C000}.items():
        if image.symbol_value(name) != value:
            raise ValueError('Wrong stack reservation: ' + name)
    phoff = struct.unpack_from('<I', data, 28)[0]
    phsize, count = struct.unpack_from('<HH', data, 42)
    if phsize != 32 or phoff + phsize * count > len(data):
        raise ValueError('Invalid program headers')
    segments = [struct.unpack_from('<8I', data, phoff + i * phsize) for i in range(count)]
    loads, ram, seen, used_segments = [], [], set(), set()
    for section in image.sections:
        if not section['flags'] & 2 or not section['size']:
            continue
        name, address, size = section['name'], section['addr'], section['size']
        if name not in regions or name in seen:
            raise ValueError('Unexpected allocated section: ' + name)
        seen.add(name)
        lo, hi, kind, flags = regions[name]
        if not lo <= address < address + size <= hi or (section['type'], section['flags']) != (kind, flags):
            raise ValueError('Invalid section bounds/type/permissions: ' + name)
        if name == '.text' and address != FLASH:
            raise ValueError('Text does not begin at entry')
        bounds = {'.text': ('_start', '_etext'), '.ram_text': ('_rt_start', '_rt_end'),
                  '.data': ('_data_start', '_data_end'), '.bss': ('_bss_start', '_bss_end'),
                  '.pool': ('_pool_start', '_pool_end')}.get(name)
        if bounds and (image.symbol_value(bounds[0]), image.symbol_value(bounds[1])) != (address, address + size):
            raise ValueError('Startup copy/zero bounds disagree: ' + name)
        ram.append((address, address + size))
        if kind == 8:
            continue
        offset = section['offset']
        if offset + size > len(data):
            raise ValueError('Truncated section')
        matches = [p for p in segments if p[0] == 1 and p[1] <= offset
                   and offset + size <= p[1] + p[4]
                   and p[2] + offset - p[1] == address]
        if len(matches) != 1:
            raise ValueError('Section lacks unique load segment: ' + name)
        p = matches[0]
        if p[1] != offset or p[4] != size:
            raise ValueError('Load segment contains unaccounted bytes')
        used_segments.add(segments.index(p))
        load = p[3] + offset - p[1]
        symbol = {'.text': '_start', '.ram_text': '_rt_load', '.data': '_data_load'}[name]
        if load != image.symbol_value(symbol) or not FLASH <= load < load + size <= FLASH + 0x8DFBC:
            raise ValueError('Invalid flash load address: ' + name)
        if p[5] < p[4] or p[6] != (6 if name == '.data' else 5):
            raise ValueError('Invalid load segment permissions/size')
        loads.append((load, load + size, data[offset:offset + size]))
    if seen != set(regions):
        raise ValueError('Missing required sections')
    if layout == 'combined':
        pool = image.symbol_value('_pool_start')
        if pool & 15 or pool < image.symbol_value('_bss_end'):
            raise ValueError('Combined pool alignment/order is invalid')
    if used_segments != {i for i, p in enumerate(segments) if p[0] == 1 and p[4]}:
        raise ValueError('Unaccounted file-backed load segment')
    for ranges in (ram, [(lo, hi) for lo, hi, _ in loads]):
        ordered = sorted(ranges)
        if any(a[1] > b[0] for a, b in zip(ordered, ordered[1:])):
            raise ValueError('Overlapping section ranges')
    loads.sort()
    cursor = FLASH
    for lo, hi, _ in loads:
        if lo != cursor:
            raise ValueError('Non-contiguous flash image')
        cursor = hi
    app = b''.join(payload for _, _, payload in loads)
    return image, app


def artifact_call_payloads(image, app, disassembly):
    """Map proven ELF calls into the independently validated flattened image."""
    proofs = relative_call_payloads('native-probe.elf', image, disassembly)
    loads = {'.text': '_start', '.ram_text': '_rt_load', '.data': '_data_load'}
    for (source, offset), proof in list(proofs.items()):
        section = source.split(':', 1)[1]
        if section not in loads:
            continue
        flat_offset = image.symbol_value(loads[section]) - FLASH + offset
        instruction = bytes.fromhex(proof['bytes'])
        if flat_offset < 2 or app[flat_offset - 2:flat_offset + 4] != instruction:
            raise ValueError('Relative-call proof does not match flattened image')
        proofs[('app.bin', flat_offset)] = proof
    return proofs



def artifact_stub_boundaries(image, app, disassembly):
    """Carry byte-exact two-instruction proofs through validated load mapping."""
    proofs = stub_call_boundary_patterns('native-probe.elf', image, disassembly)
    loads = {'.text': '_start', '.ram_text': '_rt_load'}
    for (source, offset), proof in list(proofs.items()):
        section = source.split(':', 1)[1]
        if section not in loads:
            continue
        flat_offset = image.symbol_value(loads[section]) - FLASH + offset
        instructions = bytes.fromhex(proof['call']['bytes'] + proof['following_bytes'])
        if flat_offset < 3 or app[flat_offset - 3:flat_offset + 5] != instructions:
            raise ValueError('Call-boundary proof does not match flattened image')
        proofs[('app.bin', flat_offset)] = proof
    return proofs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--layout', choices=('legacy', 'combined'), default='legacy')
    parser.add_argument('--objdump', help='vendor pi32v2 objdump for direct-call proofs')
    args = parser.parse_args()
    data = args.elf.read_bytes()
    image, app = flatten(data, args.layout)
    decoded = subprocess.check_output([args.objdump, '-d', str(args.elf)], text=True) if args.objdump else ''
    proofs = artifact_call_payloads(image, app, decoded)
    boundaries = artifact_stub_boundaries(image, app, decoded)
    root = Path(__file__).resolve().parents[2]
    receipt = audit([('native-probe.elf', image)], [('app.bin', app)], True,
                    sources=collect_sources([root / 'firmware/native']), runtime='sdk-free',
                    call_payloads=proofs, stub_boundaries=boundaries)
    if not receipt['passed'] or receipt['n_pending']:
        raise ValueError('Requires complete SDK-free key audit')
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'app.bin').write_bytes(app)
    if args.objdump:
        (args.out / 'disassembly.txt').write_text(decoded)
    report = {'elf_sha256': hashlib.sha256(data).hexdigest(),
              'app_sha256': hashlib.sha256(app).hexdigest(), 'app_bytes': len(app),
              'layout_passed': True, 'ram_layout': args.layout, 'key_audit': receipt,
              'disassembly_sha256': hashlib.sha256(decoded.encode()).hexdigest() if args.objdump else None,
              'hardware_admitted': False, 'hardware_tested': False,
              'installable': False}
    (args.out / 'artifact.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
