"""Supplement callback coverage with compiled table-branch review obligations."""
import hashlib
import json
import pathlib
import re
import struct
import sys

source, elf_path, dis_path, inventory_path, candidates_path, asm_path, output = map(
    pathlib.Path, sys.argv[1:8])
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
sys.path.insert(0, str(source / 'tools/jieli'))
from audit_link import Elf

elf = Elf(elf_path.read_bytes())
inventory = json.loads(inventory_path.read_text())
candidates = json.loads(candidates_path.read_text())
assert digest(elf_path) == inventory['elf_sha256'] == candidates['elf_sha256']
assert digest(dis_path) == inventory['disassembly_sha256']
assert digest(inventory_path) == candidates['inventory_sha256']
graph = inventory['functions']
edges = {address: set(row['direct']) for address, row in graph.items()}
for address, rule in candidates['applied_rules'].items():
    edges[address].update(rule['targets'])
root, = [a for a, row in graph.items() if 'lunar_project_start' in row['names']]
seen, todo = set(), [root]
while todo:
    address = todo.pop()
    if address not in seen:
        seen.add(address)
        todo.extend(edges[address])
assert len(seen) == candidates['reachable_functions']
symbols = [s for s in elf.symbols if s['type'] == 2 and s['shndx'] and s['size']]
# Retained vendor compiler assembly expresses halfword table offsets relative
# to the label immediately following tbh, divided by two. This is format
# evidence, not execution or a proof that a runtime index is in bounds.
assembly = asm_path.read_text()
assert re.search(r'tbh \[r\d+\]\s+\.GJTIL\w+:\s+\.short\s+\(\.LBB\w+-\.GJTIL\w+\)/2', assembly)
sites = []
for line in dis_path.read_text().splitlines():
    match = re.match(r'\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(tb[bh] \[r\d+\])$', line)
    if not match:
        continue
    pc = int(match[1], 16)
    encoded = bytes.fromhex(match[2])
    assert elf.read(pc, len(encoded)) == encoded, hex(pc)
    register = int(re.search(r'r(\d+)', match[3])[1])
    assert encoded == bytes([register + (16 if match[3].startswith('tbh') else 0), 1]), hex(pc)
    owners = {s['value'] for s in symbols if s['value'] <= pc < s['value'] + s['size']}
    assert len(owners) == 1, (hex(pc), owners)
    owner = hex(owners.pop())
    assert owner in graph
    prefix = '.GJTIS' if match[3].startswith('tbb') else '.GJTIL'
    table, = [s for s in elf.symbols if s['value'] == pc + len(encoded)
              and s['name'].startswith(prefix)]
    end, = [s for s in elf.symbols
            if s['name'] == table['name'].replace(prefix, '.GJTIE', 1)]
    width = 1 if prefix == '.GJTIS' else 2
    size = end['value'] - table['value']
    assert size > 0 and size % width == 0
    raw = elf.read(table['value'], size)
    assert raw is not None
    offsets = list(raw) if width == 1 else list(struct.unpack('<' + 'H' * (size // 2), raw))
    targets = [table['value'] + 2 * offset for offset in offsets]
    owner_end = max(s['value'] + s['size'] for s in symbols if hex(s['value']) == owner)
    assert all(int(owner, 16) <= target < owner_end for target in targets), hex(pc)
    sites.append({'pc': hex(pc), 'caller': owner, 'names': graph[owner]['names'],
                  'instruction': match[3], 'candidate_reachable': owner in seen,
                  'table_start': hex(table['value']), 'table_end': hex(end['value']),
                  'entry_bytes': width, 'entry_count': len(offsets),
                  'encoded_offsets': offsets, 'modeled_targets': [hex(t) for t in targets],
                  'all_modeled_targets_inside_caller': True,
                  'runtime_index_bounds_verified': False})
assert sites, 'no table branches found; inspect input parsing'
receipt = {
    'scope': 'table-branch obligations supplementary to candidate call coverage',
    'elf_sha256': digest(elf_path), 'disassembly_sha256': digest(dis_path),
    'inventory_sha256': digest(inventory_path),
    'candidate_receipt_sha256': digest(candidates_path),
    'compiler_assembly_sha256': digest(asm_path),
    'table_target_model': 'table_start + 2 * unsigned encoded offset; conditional on valid aligned index',
    'reachable_functions': len(seen), 'table_branch_sites': sites,
    'total_table_branches': len(sites),
    'candidate_reachable_table_branches': sum(s['candidate_reachable'] for s in sites),
    'limits': ['runtime index bounds and alignment require separate review',
               'modeled table destinations are internal; arbitrary out-of-table reads are not covered',
               'zero decoder errors do not establish complete control-flow coverage',
               'candidate graph remains conditional on callback provenance',
               'no stack bound, interrupt overlap, timing or hardware admission'],
    'hardware_admitted': False,
}
output.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({k: receipt[k] for k in ('total_table_branches',
    'candidate_reachable_table_branches', 'hardware_admitted')}))
