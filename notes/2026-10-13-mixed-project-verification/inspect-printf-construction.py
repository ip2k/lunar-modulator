"""Record exact compiled buffer-gadget construction; not hardware admission."""
import hashlib
import json
import pathlib
import re
import sys

source, elf_path, dis_path, inventory_path, output = map(pathlib.Path, sys.argv[1:6])
sys.path.insert(0, str(source / 'tools/jieli'))
from audit_link import Elf

digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
elf_hash = digest(elf_path)
assert elf_hash == 'df358a616de234c0263344cffda7d5fd626a4c1079dd5f352574cfe77fa93a8e'
inventory = json.loads(inventory_path.read_text())
assert inventory['elf_sha256'] == elf_hash
assert inventory['disassembly_sha256'] == digest(dis_path)
elf = Elf(elf_path.read_bytes())
graph = inventory['functions']

def address(name):
    matches = [s for s in elf.symbols if s['name'] == name and s['shndx'] and s['type'] == 2]
    assert len(matches) == 1, (name, matches)
    return hex(matches[0]['value'])

absent = ['printf', 'vprintf', 'sprintf', 'vsprintf', 'vfctprintf', 'fctprintf',
          'printf_', 'vprintf_', 'sprintf_', 'vsprintf_', 'vfctprintf_',
          'putchar_wrapper', 'function_gadget', 'extern_putchar_gadget']
defined = {s['name'] for s in elf.symbols if s['shndx'] and s['type'] == 2}
assert not defined.intersection(absent), sorted(defined.intersection(absent))
impl, entry, hook = map(address, ['vsnprintf_impl', 'vsnprintf', 'putchar_via_gadget'])
callers = sorted(a for a, row in graph.items() if impl in row['direct'])
assert callers == [entry], callers
assert graph[hook]['unresolved'] == [
    {'pc': '0x206d8e6', 'kind': 'indirect', 'instruction': 'goto r3'}]

instructions = {}
for line in dis_path.read_text().splitlines():
    match = re.match(r'\s*([0-9a-f]+):\s+(?:[0-9a-f]{2} )+\s*(.*)', line)
    if match:
        instructions[hex(int(match[1], 16))] = match[2].strip()
expected = {
    '0x206ea8c': 'r4 = 0',
    '0x206ea9e': '[sp] = r4',
    '0x206eaa0': '[sp+4] = r4',
    '0x206eaa2': '[sp+8] = r0',
    '0x206eaa4': '[sp+12] = r4',
    '0x206eaaa': 'r0 = sp + 0',
    '0x206d8dc': 'r3 = [r0+0]',
    '0x206d8de': 'if (r3 == 0) goto 8 <putchar_via_gadget+0x18 : 206d8e8 >',
    '0x206d8e6': 'goto r3',
}
for pc, assembly in expected.items():
    assert instructions.get(pc) == assembly, (pc, instructions.get(pc), assembly)
assert '<vsnprintf_impl : 206e502 >' in instructions['0x206eaae']
printf_path = 'firmware/third_party/printf/printf/printf.c'
assert digest(source / printf_path) == '19acedf4294faa4961b8ae4bb4ed313497612f6f485af462674021faacaa5e00'
text = (source / printf_path).read_text()
assert 'gadget.function = NULL;' in text
assert 'output_gadget_t result = discarding_gadget();' in text
assert 'output_gadget_t gadget = buffer_gadget(s, n);' in text
receipt = {
    'scope': 'exact buffer constructor and direct entry coverage; source flow review required',
    'elf_sha256': elf_hash, 'disassembly_sha256': digest(dis_path),
    'inventory_sha256': digest(inventory_path),
    'reviewed_source_sha256': {printf_path: digest(source / printf_path)},
    'entry': entry, 'formatter': impl, 'formatter_direct_callers': callers,
    'absent_function_entries': absent, 'compiled_instruction_assertions': expected,
    'hook': {'caller': hook, 'pc': '0x206d8e6', 'offset': 0, 'constructed_value': 0},
    'limits': ['direct-call inventory alone does not exclude address-taken entry paths',
               'constructor zero requires preserved gadget.function through formatting',
               'no startup stack, interrupt overlap or hardware admission conclusion'],
    'hardware_admitted': False,
}
output.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'entry': entry, 'formatter_direct_callers': callers,
                  'constructed_callback': 0, 'hardware_admitted': False}))
