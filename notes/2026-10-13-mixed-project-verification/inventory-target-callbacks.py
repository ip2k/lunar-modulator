"""Address-based callback/direct-call inventory; never a hardware admission."""
import bisect
import hashlib
import json
import pathlib
import re
import struct
import sys

source, elf_path, dis_path, layout_path, output = map(pathlib.Path, sys.argv[1:6])
sys.path.insert(0, str(source / 'tools/jieli'))
from audit_link import Elf

elf = Elf(elf_path.read_bytes())
layout = json.loads(layout_path.read_text())
offset = layout['values']
for name, digest in layout['header_sha256'].items():
    assert hashlib.sha256((source / name).read_bytes()).hexdigest() == digest, name
functions = {}
for symbol in elf.symbols:
    if symbol['type'] == 2 and symbol['shndx'] and symbol['size']:
        entry = functions.setdefault(symbol['value'], {'names': [], 'size': 0})
        entry['names'].append(symbol['name'])
        entry['size'] = max(entry['size'], symbol['size'])
for entry in functions.values():
    entry['names'] = sorted(set(entry['names']))

def word(address):
    data = elf.read(address, 4)
    assert data is not None, hex(address)
    return struct.unpack('<I', data)[0]

def string(address):
    result = bytearray()
    for i in range(128):
        byte = elf.read(address + i, 1)
        assert byte is not None, hex(address)
        if byte == b'\0':
            return result.decode('ascii')
        result.extend(byte)
    raise ValueError('unterminated descriptor id')

registries = {}
for registry, group, magic in [('fm1_engines', 'engine', 0x464D3145),
    ('fm1_midi_fxs', 'midi', 0x464D3145), ('fm1_mod_kinds', 'mod', 0x464D314D)]:
    symbols = [s for s in elf.symbols if s['name'] == registry and s['shndx']]
    assert len(symbols) == 1, (registry, symbols)
    symbol = symbols[0]
    assert symbol['size'] % 4 == 0
    entries = []
    for i in range(symbol['size'] // 4):
        address = word(symbol['value'] + 4 * i)
        if not address:
            assert i == symbol['size'] // 4 - 1, 'early sentinel'
            break
        base = 'engine' if group == 'midi' else group
        assert word(address + offset[base + '_magic']) == magic
        callbacks = {}
        groups = [base] + (['midi'] if group == 'midi' else [])
        for prefix in groups:
            for key, value in offset.items():
                if not key.startswith(prefix + '_'):
                    continue
                member = key[len(prefix) + 1:]
                if member in ('size', 'magic', 'id', 'kind'):
                    continue
                target = word(address + value)
                if target:
                    assert target in functions, (registry, i, member, hex(target))
                    callbacks[member] = {'address': hex(target),
                        'names': functions[target]['names']}
        entries.append({'id': string(word(address + offset[base + '_id'])),
            'address': hex(address), 'callbacks': callbacks})
    registries[registry] = entries

instructions = []
for line in dis_path.read_text().splitlines():
    match = re.match(r'\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.*)', line)
    if match:
        instructions.append((int(match[1], 16), len(match[2].split()), match[3]))
instructions.sort()
addresses = [row[0] for row in instructions]
graph = {}
for address, entry in functions.items():
    rows = instructions[bisect.bisect_left(addresses, address):
        bisect.bisect_left(addresses, address + entry['size'])]
    direct, unresolved, stack, decoding_limits = set(), [], [], []
    for pc, length, assembly in rows:
        # Vendor objdump splits some FPU instructions into unknown prefixes
        # followed by apparent conditional branches. Keep these as decoding
        # limitations, never invent external call edges from those fragments.
        if '<unknown instruction>' in assembly:
            decoding_limits.append({'pc': hex(pc), 'instruction': assembly})
        conditional = re.search(r'\bif .*\bgoto (-?\d+)', assembly)
        if conditional:
            target = pc + length + int(conditional[1])
            if not address <= target < address + entry['size']:
                decoding_limits.append({'pc': hex(pc), 'instruction': assembly,
                    'apparent_external_branch': hex(target)})
        match = re.match(r'(call|goto) (-?\d+)', assembly)
        if match:
            target = pc + length + int(match[2])
            if match[1] == 'goto' and address <= target < address + entry['size']:
                continue
            if target in functions:
                direct.add(target)
            else:
                unresolved.append({'pc': hex(pc), 'kind': 'direct', 'target': hex(target)})
        elif re.search(r'\b(?:call|goto) r\d+', assembly):
            unresolved.append({'pc': hex(pc), 'kind': 'indirect', 'instruction': assembly})
        if re.search(r'\bsp\b', assembly):
            stack.append({'pc': hex(pc), 'instruction': assembly})
    graph[address] = {'names': entry['names'], 'direct': sorted(direct),
        'unresolved': unresolved, 'stack': stack, 'decoding_limits': decoding_limits}

roots = {}
for root in ['lunar_project_start', 'fm1_cstart']:
    matches = [a for a, f in functions.items() if root in f['names']]
    assert len(matches) == 1, root
    seen, todo = set(), matches[:]
    while todo:
        current = todo.pop()
        if current not in seen:
            seen.add(current)
            todo.extend(graph[current]['direct'])
    roots[root] = {'direct_reachable_functions': len(seen), 'unresolved': [
        dict(caller=hex(a), names=graph[a]['names'], **site)
        for a in sorted(seen) for site in graph[a]['unresolved']]}
receipt = {'scope': 'address-based inventory; no callback edges or stack bound; not admitted',
    'elf_sha256': hashlib.sha256(elf.data).hexdigest(),
    'disassembly_sha256': hashlib.sha256(dis_path.read_bytes()).hexdigest(),
    'layout_sha256': hashlib.sha256(layout_path.read_bytes()).hexdigest(),
    'registries': registries, 'roots': roots,
    'functions': {hex(a): dict(row, direct=[hex(t) for t in row['direct']])
        for a, row in sorted(graph.items())}, 'hardware_admitted': False}
output.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'elf_sha256': receipt['elf_sha256'],
    'registry_counts': {k: len(v) for k, v in registries.items()},
    'roots': {k: {'direct_reachable_functions': v['direct_reachable_functions'],
        'unresolved_sites': len(v['unresolved'])} for k, v in roots.items()}}, indent=2))
