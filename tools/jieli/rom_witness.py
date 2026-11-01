#!/usr/bin/env python3
"""MIT. Offline-only builder/auditor for one fixed PA2 ROM witness candidate.

No device/protocol implementation. An audit pass never admits hardware use.
Exact native instructions are pinned, not decoded by a substitute host ISA.
"""
import argparse
import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'firmware/rom-witness/manifest.json'
MANIFEST_SHA256 = 'f6bc573b17825f024aac7145699c909e79d5a0493f56ca264b76c6181ee2b8ca'
ROW = re.compile(r'\s*([0-9a-fA-F]+):\s*((?:[0-9a-fA-F]{2}\s+)+)(\S.*?)\s*')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def manifest():
    raw = MANIFEST.read_bytes()
    if sha(raw) != MANIFEST_SHA256:
        raise ValueError('manifest changed: independent review and repin required')
    return json.loads(raw)


def check_sources():
    for relative, expected in manifest()['sources'].items():
        if sha((ROOT / relative).read_bytes()) != expected:
            raise ValueError('source differs from frozen candidate: ' + relative)


def audit_listing(listing, code):
    m = manifest()
    rows, sections = [], []
    for line in listing.splitlines():
        if line.startswith('Disassembly of section '):
            sections.append(line)
        match = ROW.fullmatch(line)
        if match:
            address, encoded, operation = match.groups()
            parts = operation.split('<', 1)
            target = None
            if len(parts) == 2:
                annotation = re.fullmatch(r'[^<>:]+\s*:\s*([0-9a-fA-F]+)\s*>', parts[1])
                if annotation is None:
                    raise ValueError('malformed branch annotation')
                target = int(annotation[1], 16)
            rows.append(dict(offset=int(address, 16) - m['entry'],
                             hex=bytes.fromhex(encoded).hex(),
                             operation=' '.join(parts[0].split()), target=target))
        elif re.match(r'\s*[0-9a-fA-F]+:', line):
            raise ValueError('unparsed native instruction')
    if sections != ['Disassembly of section .witness:'] or rows != m['instructions']:
        raise ValueError('native instruction/branch/MMIO contract changed')
    if b''.join(bytes.fromhex(row['hex']) for row in rows) != code:
        raise ValueError('listing and exported bytes differ')


def audit_elf(data, code):
    """Require exact native ELF32 geometry; program headers are not a load API."""
    from audit_link import Elf, ET_EXEC, EM_PI32V2
    m = manifest()
    if len(data) < 52 or data[:16] != bytes.fromhex('7f454c46010101000000000000000000'):
        raise ValueError('not the expected native ELF32 format')
    if struct.unpack_from('<I', data, 24)[0] != m['entry']:
        raise ValueError('wrong ELF entry')
    if struct.unpack_from('<I', data, 36)[0] != 0:
        raise ValueError('unexpected ELF flags')
    shoff = struct.unpack_from('<I', data, 32)[0]
    shentsize, shnum, shstr = struct.unpack_from('<HHH', data, 46)
    if shentsize != 40 or shnum != 5 or shstr != 2 or shoff + shnum * 40 != len(data):
        raise ValueError('unexpected ELF section table')
    e = Elf(data)
    if e.e_type != ET_EXEC or e.e_machine != EM_PI32V2:
        raise ValueError('not linked pi32v2 code')
    if [s['name'] for s in e.sections] != ['', '.witness', '.shstrtab', '.symtab', '.strtab']:
        raise ValueError('unexpected sections')
    if [s['type'] for s in e.sections] != [0, 1, 3, 2, 3]:
        raise ValueError('unexpected section types')
    for i, s in enumerate(e.sections):
        if s['flags'] != (6 if i == 1 else 0):
            raise ValueError('unexpected writable/allocated section')
        if s['offset'] + s['size'] > len(data):
            raise ValueError('section outside ELF')
    s = e.sections[1]
    if (s['addr'], s['size']) != (m['entry'], m['code_size']):
        raise ValueError('wrong loaded range')
    if data[s['offset']:s['offset'] + s['size']] != code:
        raise ValueError('ELF and exported bytes differ')
    symbols = [s for s in e.symbols if s['name']]
    if len(symbols) != 4 or {s['name']: s['value'] for s in symbols} != m['symbols']:
        raise ValueError('unexpected linked symbols')
    if any(s['shndx'] != 1 for s in symbols) or e.undefined_symbols() or e.relocation_symbol_names():
        raise ValueError('foreign/undefined/relocated symbol')
    start = next(s for s in symbols if s['name'] == '_start')
    if start['type'] != 2 or start['size'] != len(code):
        raise ValueError('unexpected function extent')


def audit(elf, code, listing, payload):
    m = manifest()
    expected = b''.join(bytes.fromhex(row['hex']) for row in m['instructions'])
    if code != expected or len(code) != m['code_size'] or sha(code) != m['code_sha256']:
        raise ValueError('exact code bytes changed')
    if payload != code + bytes(m['footprint'] - len(code)) or sha(payload) != m['payload_sha256']:
        raise ValueError('exact 512-byte plaintext/padding changed')
    audit_listing(listing, code)
    audit_elf(elf, code)
    return dict(schema=1, offline_audit_passed=True, hardware_admitted=False,
                manifest_sha256=MANIFEST_SHA256, entry=m['entry'], footprint=m['footprint'],
                code_size=len(code), elf_sha256=sha(elf), code_sha256=sha(code),
                payload_sha256=sha(payload), signature=m['signature'])


def build(toolchain, output):
    """Compile only the frozen assembly; no SDK headers/archives or libraries."""
    check_sources()
    m = manifest()
    tc = Path(toolchain).resolve()
    for relative, expected in m['tools'].items():
        if sha((tc / relative).read_bytes()) != expected:
            raise ValueError('tool differs from pinned compiler/binutils: ' + relative)
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    cc, ld, copy, dump = [tc / name for name in m['tools']]
    src = ROOT / 'firmware/rom-witness'
    commands = [
        [cc, '-target', 'pi32v2', '-mcpu=r3', '-mfprev1', '-Werror', '-c', src / 'witness.S', '-o', out / 'witness.o'],
        [ld, '-T', src / 'witness.ld', '--orphan-handling=error', out / 'witness.o', '-o', out / 'witness.elf'],
        [copy, '-O', 'binary', '-j', '.witness', out / 'witness.elf', out / 'witness.code'],
    ]
    for command in commands:
        subprocess.run([str(x) for x in command], check=True, capture_output=True)
    result = subprocess.run([str(dump), '-d', '-mcpu=r3', '-mattr=+fprev1', str(out / 'witness.elf')],
                            check=True, capture_output=True, text=True)
    (out / 'witness.listing').write_text(result.stdout)
    code = (out / 'witness.code').read_bytes()
    if len(code) > m['footprint']:
        raise ValueError('candidate exceeds fixed block')
    payload = code + bytes(m['footprint'] - len(code))
    (out / 'witness.payload').write_bytes(payload)
    receipt = audit((out / 'witness.elf').read_bytes(), code, result.stdout, payload)
    receipt['source_sha256'] = m['sources']
    receipt['tool_sha256'] = m['tools']
    receipt['commands'] = [[str(x) for x in c] for c in commands]
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    (out / 'witness.o').unlink()
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    b = sub.add_parser('build')
    b.add_argument('--toolchain', required=True)
    b.add_argument('--out', required=True, help='new private ignored output directory')
    a = sub.add_parser('audit')
    a.add_argument('directory', type=Path)
    args = parser.parse_args()
    if args.mode == 'build':
        result = build(args.toolchain, args.out)
    else:
        p = args.directory
        check_sources()
        result = audit((p / 'witness.elf').read_bytes(), (p / 'witness.code').read_bytes(),
                       (p / 'witness.listing').read_text(), (p / 'witness.payload').read_bytes())
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
