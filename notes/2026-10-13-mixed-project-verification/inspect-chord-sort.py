"""Verify the four-note chord caller uses the bounded small-sort path."""
import hashlib
import json
import pathlib
import re
import sys

source, dis_path, inventory_path, tables_path, output = map(pathlib.Path, sys.argv[1:6])
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
inventory = json.loads(inventory_path.read_text())
tables = json.loads(tables_path.read_text())
assert digest(inventory_path) == tables['inventory_sha256']
assert digest(dis_path) == tables['disassembly_sha256'] == inventory['disassembly_sha256']
header = source / 'engines/third_party/mutable/plaits/dsp/chords/chord_bank.h'
assert digest(header) == '3333c617479285188887caf55bb9fbc0f9854db973d8909298d052ec7d410119'
assert 'const int kChordNumNotes = 4;' in header.read_text()
graph = inventory['functions']
sort, caller, sort4, sort3 = '0x206332a', '0x2063548', '0x20631da', '0x2063192'
assert {a for a, row in graph.items() if sort in row['direct']} == {sort, caller}
assert graph[sort4]['direct'] == [sort3] and not graph[sort4]['unresolved']
assert not graph[sort3]['direct'] and not graph[sort3]['unresolved']
instructions = {}
for line in dis_path.read_text().splitlines():
    match = re.match(r'\s*([0-9a-f]+):\s+(?:[0-9a-f]{2} )+\s*(.*)', line)
    if match:
        instructions[hex(int(match[1], 16))] = match[2].strip()
expected = {
    '0x2063578': 'r1 = r5 + 16', '0x206357a': 'r0 = r5',
    '0x206332e': 'r14 = r1', '0x2063330': 'r15 = r0',
    '0x2063346': 'r7 = r15', '0x2063352': 'r15 = r7',
    '0x20633b2': 'r1 = r14 - r15', '0x20633b6': 'r0 = r1 >>> 2',
    '0x2063498': 'tbb [r0]',
    '0x206351a': 'r1 = r15 + 4', '0x206351e': 'r2 = r15 + 8',
    '0x2063522': 'r0 = r15', '0x2063524': 'r3 = r8',
    '0x2063506': 'sp += 4', '0x2063508': '{pc, r15-r4} = [sp++]',
    '0x206332a': '[--sp] = {rets, r15-r4}', '0x206332c': 'sp += -4',
    '0x20631da': '[--sp] = {rets, r6-r4}',
    '0x2063192': '[--sp] = {rets, r6-r4}',
    '0x2063548': '[--sp] = {rets, r7-r4}',
}
for pc, value in expected.items():
    assert instructions.get(pc) == value, (pc, instructions.get(pc), value)
branches = {'0x2063348': '2063352', '0x2063354': '20633b2',
            '0x20633b8': '2063498', '0x206352c': '2063506'}
for pc, target in branches.items():
    assert re.search(r'goto -?\d+ <.* : ' + target + r' >$', instructions[pc]), pc
assert instructions['0x20633b8'].startswith('if (r0 <= 5) ')
assert instructions['0x206357c'].endswith(': 206332a >')
assert instructions['0x2063526'].endswith(': 20631da >')
table, = [s for s in tables['table_branch_sites'] if s['pc'] == '0x2063498']
assert table['entry_bytes'] == 1 and table['entry_count'] == 6
assert table['modeled_targets'][4] == '0x206351a'
# Reject additional stack adjustments in the small helper bodies. Stores to
# stack are not allocations; these helpers currently have only push/pop rows.
for address in (sort4, sort3):
    assert all(re.fullmatch(r'\[--sp\] = \{rets, r6-r4\}|\{pc, r6-r4\} = \[sp\+\+\]',
                           row['instruction']) for row in graph[address]['stack'])
receipt = {
    'scope': 'four-element ChordBank call context; not a whole startup bound',
    'elf_sha256': inventory['elf_sha256'], 'disassembly_sha256': digest(dis_path),
    'inventory_sha256': digest(inventory_path), 'table_receipt_sha256': digest(tables_path),
    'header_sha256': digest(header), 'caller': caller, 'sort': sort,
    'element_count': 4, 'compiled_instruction_assertions': expected,
    'entry_path': ['0x2063348', '0x2063352', '0x2063354', '0x20633b2',
                   '0x20633b6', '0x20633b8', '0x2063498', '0x206351a'],
    'recursive_sort_frames_in_this_context': 1,
    'small_sort_frame_bytes': {'sort': 56, 'sort4': 16, 'sort3': 16},
    'small_sort_chain_bytes': 88, 'chord_caller_frame_bytes': 20,
    'limits': ['conditional on valid chord storage and the recorded table-target model',
               'direct caller inventory does not exclude address-taken or external entry paths',
               'ratio normalization path, outer callers and IRQ overlap require separate bounds',
               'no complete startup stack bound, timing or hardware admission'],
    'hardware_admitted': False,
}
output.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({k: receipt[k] for k in ('element_count',
    'recursive_sort_frames_in_this_context', 'small_sort_chain_bytes', 'hardware_admitted')}))
