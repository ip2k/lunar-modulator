"""Measure callback offsets with the target compiler, without executing code."""
import hashlib
import json
import pathlib
import re
import subprocess
import sys

source, toolchain, output = map(pathlib.Path, sys.argv[1:4])
output.mkdir(parents=True, exist_ok=True)
fields = {
    'engine': ('fm1_engine_t', ['magic', 'id', 'kind', 'instance_size', 'create',
        'destroy', 'note_on', 'note_off', 'pitch_bend', 'set_param', 'render',
        'set_param_note', 'render_ext', 'get_param']),
    'midi': ('fm1_midi_fx_t', ['process']),
    'mod': ('fm1_mod_kind_t', ['magic', 'id', 'instance_size', 'create',
        'destroy', 'reset', 'process', 'get_data', 'set_data', 'view']),
}
code = ['#include <stddef.h>', '#include "fm1_engine.h"', '#include "fm1_mod.h"',
        'unsigned pointer_size(void) { return sizeof(void *); }']
for group, (ctype, members) in fields.items():
    code.append(f'unsigned {group}_size(void) {{ return sizeof({ctype}); }}')
    for member in members:
        code.append(f'unsigned {group}_{member}(void) {{ return offsetof({ctype}, {member}); }}')
cfile, irfile = output / 'callback-layout.c', output / 'callback-layout.ll'
cfile.write_text('\n'.join(code) + '\n')
command = [str(toolchain / 'common/bin/clang'), '-target', 'pi32v2', '-mcpu=r3',
    '-mfprev1', '-Oz', '-ffreestanding', '-fno-builtin', '-std=c99', '-S',
    '-emit-llvm', '-I' + str(source / 'engines/include'), '-isystem',
    str(toolchain / 'pi32v2/include'), str(cfile), '-o', str(irfile)]
subprocess.run(command, check=True)
ir = irfile.read_text()
values = {name: int(value) for name, value in re.findall(
    r'define[^\n]*@([a-z_]+)\([^\n]*\)[^{]*\{\s*ret i32 (\d+)\s*\}', ir)}
expected = {'pointer_size'} | {g + '_size' for g in fields} | {
    g + '_' + m for g, (_, members) in fields.items() for m in members}
assert set(values) == expected, (expected - set(values), set(values) - expected)
assert values['pointer_size'] == 4
receipt = {'command': command, 'values': values,
    'source_sha256': hashlib.sha256(cfile.read_bytes()).hexdigest(),
    'ir_sha256': hashlib.sha256(irfile.read_bytes()).hexdigest(),
    'header_sha256': {p: hashlib.sha256((source / p).read_bytes()).hexdigest()
        for p in ['engines/include/fm1_engine.h', 'engines/include/fm1_mod.h']},
    'hardware_admitted': False}
(output / 'callback-layout.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
