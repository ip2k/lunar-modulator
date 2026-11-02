#!/usr/bin/env python3
"""MIT. Offline fixed-geometry return-only ROM candidate builder/auditor.

No device or transport API. A structural pass never admits hardware use or
qualifies the inherited return register, ROM ABI, fetch coherence or watchdog.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

from audit_link import Elf, ET_EXEC, EM_PI32V2

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'firmware/rom-witness-return/manifest.json'
MANIFEST_SHA256 = 'e03ef5e05b1b8161bde6efc1fe4507a6bc2a743d5647f65f2fcd6ad79716800c'
ENTRY = 0x01c02000
FOOTPRINT = 512
# Prospective encoding, checked against actual vendor output before acceptance.
CODE = bytes.fromhex('8000')
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
    sections, rows = [], []
    for line in listing.splitlines():
        if line.startswith('Disassembly of section '):
            sections.append(line)
        match = ROW.fullmatch(line)
        if match:
            address, encoded, operation = match.groups()
            rows.append((int(address, 16), bytes.fromhex(encoded), operation))
        elif re.match(r'\s*[0-9a-fA-F]+:', line):
            raise ValueError('unparsed native instruction')
    if sections != ['Disassembly of section .witness_return:'] or rows != [(ENTRY, CODE, 'rts')]:
        raise ValueError('exact one-return native listing required')
    if rows[0][1] != code:
        raise ValueError('listing and exported bytes differ')


def audit_elf(data, code):
    """ELF is inspected, never used as a target loading interface."""
    if len(data) < 52 or data[:16] != bytes.fromhex('7f454c46010101000000000000000000'):
        raise ValueError('not the expected native ELF32 format')
    if struct.unpack_from('<I', data, 24)[0] != ENTRY:
        raise ValueError('wrong ELF entry')
    if struct.unpack_from('<I', data, 36)[0] != 0:
        raise ValueError('unexpected ELF flags')
    if struct.unpack_from('<I', data, 20)[0] != 1 or struct.unpack_from('<H', data, 40)[0] != 52:
        raise ValueError('unexpected ELF version/header size')
    shoff = struct.unpack_from('<I', data, 32)[0]
    shentsize, shnum, shstr = struct.unpack_from('<HHH', data, 46)
    if shoff < 52 or shentsize != 40 or shnum != 5 or shstr != 2 or shoff + shnum * 40 != len(data):
        raise ValueError('unexpected ELF section table')
    # Bound tables before invoking the existing shared ELF reader.
    headers = [struct.unpack_from('<IIIIIIIIII', data, shoff + 40 * i) for i in range(5)]
    if headers[0] != (0,) * 10:
        raise ValueError('unexpected null section')
    if [h[1] for h in headers] != [0, 1, 3, 2, 3]:
        raise ValueError('unexpected section types or relocation')
    for i, h in enumerate(headers):
        if h[2] != (6 if i == 1 else 0):
            raise ValueError('unexpected writable/allocated section')
        if i and (h[4] < 52 or h[4] + h[5] > shoff):
            raise ValueError('section outside file data')
    symtab = headers[3]
    if symtab[6] != 4 or symtab[9] != 16 or symtab[5] % 16:
        raise ValueError('unexpected symbol table geometry')
    try:
        e = Elf(data)
    except (IndexError, struct.error) as exc:
        raise ValueError('malformed ELF tables') from exc
    if e.e_type != ET_EXEC or e.e_machine != EM_PI32V2:
        raise ValueError('not linked pi32v2 code')
    if [s['name'] for s in e.sections] != ['', '.witness_return', '.shstrtab', '.symtab', '.strtab']:
        raise ValueError('unexpected sections')
    section = e.sections[1]
    if (section['addr'], section['size']) != (ENTRY, len(CODE)):
        raise ValueError('wrong loaded range or extra code')
    if data[section['offset']:section['offset'] + section['size']] != code:
        raise ValueError('ELF and exported bytes differ')
    named = [s for s in e.symbols if s['name']]
    if len(named) != 2 or {s['name']: s['value'] for s in named} != {'_start': ENTRY, '__image_end': ENTRY + 2}:
        raise ValueError('unexpected linked symbols')
    if any(s['shndx'] != 1 or s['bind'] != 1 for s in named) or e.undefined_symbols() or e.relocation_symbol_names():
        raise ValueError('foreign/undefined/relocated symbol')
    start = next(s for s in named if s['name'] == '_start')
    if start['type'] != 2 or start['size'] != 2:
        raise ValueError('unexpected function extent')


def audit(elf, code, listing, payload):
    manifest()  # Refuse altered admission metadata even for a direct audit.
    if code != CODE:
        raise ValueError('exact two-byte code required')
    if payload != CODE + bytes(FOOTPRINT - len(CODE)):
        raise ValueError('exact 512-byte plaintext/padding required')
    audit_listing(listing, code)
    audit_elf(elf, code)
    return dict(schema=1, candidate='return-r01', offline_audit_passed=True,
                hardware_admitted=False, rom_abi_qualified=False,
                watchdog_lease_qualified=False, fetch_coherence_qualified=False,
                manifest_sha256=MANIFEST_SHA256, entry=ENTRY, footprint=FOOTPRINT,
                code_size=len(code), elf_sha256=sha(elf), code_sha256=sha(code),
                payload_sha256=sha(payload))


def build(toolchain, output):
    """Compile only the pinned assembly, without SDK headers or libraries."""
    check_sources()
    m = manifest()
    tc = Path(toolchain).resolve()
    for relative, expected in m['tools'].items():
        if sha((tc / relative).read_bytes()) != expected:
            raise ValueError('tool differs from pinned compiler/binutils: ' + relative)
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    cc, ld, copy, dump = [tc / name for name in m['tools']]
    src = ROOT / 'firmware/rom-witness-return'
    commands = [
        [cc, '-target', 'pi32v2', '-mcpu=r3', '-mfprev1', '-Werror', '-c', src / 'witness.S', '-o', out / 'witness.o'],
        [ld, '-T', src / 'witness.ld', '--orphan-handling=error', out / 'witness.o', '-o', out / 'witness.elf'],
        [copy, '-O', 'binary', '-j', '.witness_return', out / 'witness.elf', out / 'witness.code'],
        [dump, '-d', '-mcpu=r3', '-mattr=+fprev1', out / 'witness.elf'],
    ]
    for i, command in enumerate(commands):
        try:
            result = subprocess.run([str(x) for x in command], check=True, capture_output=True,
                                    timeout=30)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            (out / f'command-{i}.stdout').write_bytes(exc.stdout or b'')
            (out / f'command-{i}.stderr').write_bytes(exc.stderr or b'')
            raise
        else:
            (out / f'command-{i}.stdout').write_bytes(result.stdout)
            (out / f'command-{i}.stderr').write_bytes(result.stderr)
    listing = result.stdout.decode('utf-8')
    (out / 'witness.listing').write_text(listing)
    code = (out / 'witness.code').read_bytes()
    if code != CODE:
        raise ValueError('vendor output differs from prospective return encoding')
    payload = code + bytes(FOOTPRINT - len(code))
    (out / 'witness.payload').write_bytes(payload)
    receipt = audit((out / 'witness.elf').read_bytes(), code, listing, payload)
    receipt.update(source_sha256=m['sources'], tool_sha256=m['tools'],
                   commands=[[str(x) for x in c] for c in commands])
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
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
