"""Verify native initialization covers the optional modulation observer slot."""
import hashlib
import json
import pathlib
import re
import sys

source, elf_path, dis_path, output = map(pathlib.Path, sys.argv[1:5])
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert digest(elf_path) == 'df358a616de234c0263344cffda7d5fd626a4c1079dd5f352574cfe77fa93a8e'
assert digest(dis_path) == '46ff199b5288a37be1f7e3f155cf93bce765b9cf888d31cb8110648740de6e38'
instructions = {}
for line in dis_path.read_text().splitlines():
    match = re.match(r'\s*([0-9a-f]+):\s+(?:[0-9a-f]{2} )+\s*(.*)', line)
    if match:
        instructions[hex(int(match[1], 16))] = match[2].strip()
expected = {
    '0x205f786': 'r7 = 29420048 <app : 1c0ea10 >',
    '0x205f78c': 'r2 = 38468 </src/firmware/third_party/printf/printf/printf.c+0x9644 : 9644 >',
    '0x205f792': 'r1 = 0',
    '0x205f794': 'r0 = r7',
    '0x203a7ee': 'r0 = 7710 </src/firmware/third_party/printf/printf/printf.c+0x1E1E : 1e1e >',
    '0x203a7f2': 'r5 = [r4+r0<<2]',
    '0x203a80c': 'call r5',
}
for pc, assembly in expected.items():
    assert instructions.get(pc) == assembly, (pc, instructions.get(pc), assembly)
assert '<memset : 206b742 >' in instructions['0x205f796']
observer_offset, zero_bytes = 7710 * 4, 38468
assert observer_offset + 4 <= zero_bytes
paths = ['firmware/native/app_probe.c', 'sim/web/src/fm1_app.c',
         'sim/web/src/fm1_app_state.c', 'sim/web/src/fm1_app.h']
receipt = {
    'scope': 'native initialization and observer-load evidence; not full pointer-flow proof',
    'elf_sha256': digest(elf_path), 'disassembly_sha256': digest(dis_path),
    'source_sha256': {p: digest(source / p) for p in paths},
    'app_address': '0x1c0ea10', 'zero_start': 0, 'zero_bytes': zero_bytes,
    'observer_offset': observer_offset, 'observer_initial_value': 0,
    'compiled_instruction_assertions': expected,
    'limits': ['later stores, aliasing and state-reset preservation require separate review',
               'applies only after this native initialization, not arbitrary host applications',
               'no stack, interrupt overlap, timing or hardware admission conclusion'],
    'hardware_admitted': False,
}
output.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'observer_offset': observer_offset, 'covered_by_zero_bytes': zero_bytes,
                  'hardware_admitted': False}))
