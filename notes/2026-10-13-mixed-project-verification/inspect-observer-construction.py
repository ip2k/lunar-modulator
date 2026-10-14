"""Verify native initialization covers the optional modulation observer slot."""
import hashlib
import json
import pathlib
import re
import sys

source, elf_path, dis_path, output = map(pathlib.Path, sys.argv[1:5])
sys.path.insert(0, str(source / 'tools/jieli'))
from audit_link import Elf

elf = Elf(elf_path.read_bytes())
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
profiles = {
    'df358a616de234c0263344cffda7d5fd626a4c1079dd5f352574cfe77fa93a8e':
        '46ff199b5288a37be1f7e3f155cf93bce765b9cf888d31cb8110648740de6e38',
    '4b340d1aa4f67737d102441680df5d28a2740d6a2eaa83feb028ea19a9f49e2b':
        '6bcbad133dc5bab573c7c5da744032b6c83142f64f00a7403a6c8c44485c61c9',
}
assert digest(elf_path) in profiles
assert digest(dis_path) == profiles[digest(elf_path)]
instructions = {}
opcodes = {}
for line in dis_path.read_text().splitlines():
    match = re.match(r'\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.*)', line)
    if match:
        pc = hex(int(match[1], 16))
        instructions[pc] = match[3].strip()
        opcodes[pc] = bytes.fromhex(match[2])
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
    assert elf.read(int(pc, 16), len(opcodes[pc])) == opcodes[pc], ('ELF opcode mismatch', pc)
assert '<memset : 206b742 >' in instructions['0x205f796']
assert elf.read(0x205f796, len(opcodes['0x205f796'])) == opcodes['0x205f796']
observer_offset, zero_bytes = 7710 * 4, 38468
assert observer_offset + 4 <= zero_bytes
paths = ['firmware/native/app_probe.c', 'sim/web/src/fm1_app.c',
         'sim/web/src/fm1_app_state.c', 'sim/web/src/fm1_app.h']
reviewed_sources = {
    'firmware/native/app_probe.c': 'b8cab2498d7cc585518c4558d52f5ee874aa964007b0942ea26635d6ab2ccf41',
    'sim/web/src/fm1_app.c': '903b50f83a8611dcb764745ac9f11d5c9bc8bff2910ca6c9dd2df190e4d25189',
    'sim/web/src/fm1_app_state.c': '24812821b1e7f4afd08ff4456dbf66ced641d7a36de08ceecdbf082f283cbbda',
    'sim/web/src/fm1_app.h': 'aa883d5b57fed102de94a897e931f315572de8d5ccb7e29728a717d730cb73c0',
}
assert {p: digest(source / p) for p in paths} == reviewed_sources, 'unreviewed observer source'
state_source = (source / 'sim/web/src/fm1_app_state.c').read_text()
load_source = state_source[state_source.index('int fm1_app_state_load('):]
preservation_steps = ['on_mod = a->on_mod;', 'on_mod_ctx = a->on_mod_ctx;',
                      'a->on_mod = NULL;', 'a->on_mod = on_mod;',
                      'a->on_mod_ctx = on_mod_ctx;']
positions = [load_source.index(step) for step in preservation_steps]
assert positions == sorted(positions)
receipt = {
    'scope': 'native initialization and observer-load evidence; not full pointer-flow proof',
    'elf_sha256': digest(elf_path), 'disassembly_sha256': digest(dis_path),
    'source_sha256': {p: digest(source / p) for p in paths},
    'app_address': '0x1c0ea10', 'zero_start': 0, 'zero_bytes': zero_bytes,
    'observer_offset': observer_offset, 'observer_initial_value': 0,
    'compiled_instruction_assertions': expected,
    'compiled_assertions_match_elf_bytes': True,
    'reviewed_state_load_preservation_steps': preservation_steps,
    'limits': ['source save-clear-restore order is checked; compiled preservation and aliasing remain open',
               'applies only after this native initialization, not arbitrary host applications',
               'no stack, interrupt overlap, timing or hardware admission conclusion'],
    'hardware_admitted': False,
}
output.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'observer_offset': observer_offset, 'covered_by_zero_bytes': zero_bytes,
                  'hardware_admitted': False}))
