"""Measure the native Schwung ABI with the actual pi32v2 C++ compiler."""
import hashlib
import json
import pathlib
import re
import subprocess
import sys

source, toolchain, output = map(pathlib.Path, sys.argv[1:4])
output.mkdir(parents=True, exist_ok=True)
fields = {
    'module': ('fm1::schwung::Module', ['kind', 'sound_init', 'fx_init', 'focus_key']),
    'sound': ('plugin_api_v2_t', ['api_version', 'create_instance', 'destroy_instance',
        'on_midi', 'set_param', 'get_param', 'get_error', 'render_block']),
    'fx': ('audio_fx_api_v2_t', ['api_version', 'create_instance', 'destroy_instance',
        'process_block', 'set_param', 'get_param', 'on_midi']),
}
code = ['#include <stddef.h>', '#include "schwung_shim.h"',
        'extern "C" {', 'unsigned pointer_size() { return sizeof(void *); }']
for group, (ctype, members) in fields.items():
    code.append(f'unsigned {group}_size() {{ return sizeof({ctype}); }}')
    for member in members:
        code.append(f'unsigned {group}_{member}() {{ return offsetof({ctype}, {member}); }}')
code.append('}')
cfile, irfile = output / 'schwung-layout.cc', output / 'schwung-layout.ll'
cfile.write_text('\n'.join(code) + '\n')
command = [str(toolchain / 'common/bin/clang'), '-x', 'c++', '-target', 'pi32v2', '-mcpu=r3',
    '-mfprev1', '-Oz', '-ffreestanding', '-fno-builtin', '-fno-exceptions',
    '-fno-rtti', '-std=c++11', '-S', '-emit-llvm',
    *['-I' + str(source / p) for p in ['engines/include', 'engines/src',
        'engines/third_party/schwung']], '-isystem', str(toolchain / 'pi32v2/include'),
    str(cfile), '-o', str(irfile)]
subprocess.run(command, check=True)
ir = irfile.read_text()
values = {name: int(value) for name, value in re.findall(
    r'define[^\n]*@([a-z_]+)\([^\n]*\)[^{]*\{\s*ret i32 (\d+)\s*\}', ir)}
expected = {'pointer_size'} | {g + '_size' for g in fields} | {
    g + '_' + m for g, (_, members) in fields.items() for m in members}
assert set(values) == expected, (expected - set(values), set(values) - expected)
assert values['pointer_size'] == 4
headers = ['engines/include/fm1_engine.h', 'engines/src/schwung_shim.h',
    'engines/src/schwung_abi.h', 'engines/third_party/schwung/plugin_api_v1.h',
    'engines/third_party/schwung/audio_fx_api_v2.h']
receipt = {'command': command, 'values': values,
    'source_sha256': hashlib.sha256(cfile.read_bytes()).hexdigest(),
    'ir_sha256': hashlib.sha256(irfile.read_bytes()).hexdigest(),
    'header_sha256': {p: hashlib.sha256((source / p).read_bytes()).hexdigest()
        for p in headers}, 'hardware_admitted': False}
(output / 'schwung-layout.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
