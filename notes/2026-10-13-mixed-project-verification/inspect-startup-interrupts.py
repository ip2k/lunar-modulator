"""Bind stack reservations and interrupt exposure to the exact native candidate.

Usage: SOURCE ELF DISASSEMBLY OUTPUT. This is not a stack safety verdict.
"""
import hashlib
import json
import pathlib
import re
import sys

source, elf_path, dis_path, output = map(pathlib.Path, sys.argv[1:5])
sys.path.insert(0, str(source / 'tools/jieli'))
from audit_link import Elf

digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert digest(elf_path) == 'df358a616de234c0263344cffda7d5fd626a4c1079dd5f352574cfe77fa93a8e'
assert digest(dis_path) == '46ff199b5288a37be1f7e3f155cf93bce765b9cf888d31cb8110648740de6e38'
elf = Elf(elf_path.read_bytes())

def symbol(name):
    matches = [s['value'] for s in elf.symbols if s['name'] == name and s['shndx']]
    assert len(matches) == 1, (name, matches)
    return matches[0]

instructions = {}
for line in dis_path.read_text().splitlines():
    match = re.match(r'\s*([0-9a-f]+):\s+(?:[0-9a-f]{2} )+\s*(.*)', line)
    if match:
        instructions[int(match[1], 16)] = match[2].strip()

expected = {
    0x2000158: 'sp = 29859840',
    0x200015e: 'ssp = 29868032',
    0x205f3b2: 'r0 = 11', 0x205f3b4: 'r2 = 3',
    0x205f3e6: 'r0 = 63', 0x205f3e8: 'r2 = 4',
    0x205f416: 'r0 = icfg', 0x205f41a: 'r0 |= 256',
    0x205f41c: 'icfg = r0', 0x205f420: 'csync', 0x205f422: 'sti',
}
for pc, assembly in expected.items():
    assert instructions.get(pc) == assembly, (hex(pc), instructions.get(pc), assembly)
for pc in (0x205f3b6, 0x205f3ea):
    assert '<fm1_irq_attach : 204edf8 >' in instructions[pc]
assert '<isr_alnk0 : 206a0f4 >' in instructions[0x205f3ac]
assert '<isr_timer5 : 206a0e4 >' in instructions[0x205f3e0]
assert '<lunar_project_start : 20547be >' in instructions[0x205fde2]
assert symbol('fm1_cstart') <= 0x205f422 < 0x205fde2

wrappers = []
for name, body, entry in [('isr_timer5', 'fm1_timer5_irq', 0x206a0e4),
                          ('isr_alnk0', 'fm1_alnk0_irq', 0x206a0f4)]:
    assert symbol(name) == entry
    assert instructions[entry] == '[--sp] = {psr, rets, reti}'
    assert instructions[entry + 2] == '[--sp] = {r3-r0}'
    assert f'<{body} :' in instructions[entry + 4]
    assert instructions[entry + 8] == '{r3-r0} = [sp++]'
    assert instructions[entry + 10] == '{psr, rets, reti} = [sp++]'
    assert instructions[entry + 12] == 'csync'
    assert instructions[entry + 14] == 'rti'
    wrappers.append({'name': name, 'entry': hex(entry), 'body': body,
                     'explicit_saved_bytes': (3 + 4) * 4})

stacks = {}
for name, expected_bytes in [('u', 24320), ('s', 7936)]:
    lo, top = symbol(f'_{name}stack_lo'), symbol(f'_{name}stack_top')
    assert top - lo == expected_bytes
    stacks[name] = {'low': hex(lo), 'top': hex(top), 'reserved_bytes': top - lo}
assert symbol('_ustack_top') == 29859840
assert symbol('_sstack_top') == 29868032
paths = ['firmware/native/app.ld', 'firmware/native/app_probe.c',
         'firmware/third_party/dinghy/hal/fm1_isr.S',
         'firmware/third_party/dinghy/hal/fm1_irq.h']
receipt = {
    'scope': 'exact stack reservations, explicit ISR saves and interrupt-enable ordering',
    'elf_sha256': digest(elf_path), 'disassembly_sha256': digest(dis_path),
    'reviewed_source_sha256': {p: digest(source / p) for p in paths},
    'stacks': stacks, 'wrappers': wrappers,
    'interrupt_enable_pc': '0x205f422', 'project_start_call_pc': '0x205fde2',
    'enabled_sources': [{'vector': 11, 'priority': 3, 'wrapper': 'isr_alnk0'},
                        {'vector': 63, 'priority': 4, 'wrapper': 'isr_timer5'}],
    'compiled_instruction_assertions': {hex(p): a for p, a in expected.items()},
    'limits': ['ordering is exact compiled-layout evidence; not exhaustive path analysis',
               'CPU interrupt stack selection and nesting require independent evidence',
               'C handler frames, callees and hardware entry overhead are not bounded here',
               'no full startup stack margin, audio timing or physical acceptance conclusion'],
    'hardware_admitted': False,
}
output.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'stacks': stacks, 'wrapper_bytes': 28, 'hardware_admitted': False}))
