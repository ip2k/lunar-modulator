"""Bind reviewed Schwung startup sites to the exact all13-v3 target tables."""
import hashlib
import json
import pathlib
import re
import struct
import sys

source, elf_path, dis_path, layout_path, inventory_path, output = map(pathlib.Path, sys.argv[1:7])
sys.path.insert(0, str(source / 'tools/jieli'))
from audit_link import Elf
elf = Elf(elf_path.read_bytes())
elf_hash = hashlib.sha256(elf.data).hexdigest()
assert elf_hash in {
        'df358a616de234c0263344cffda7d5fd626a4c1079dd5f352574cfe77fa93a8e',
        '4b340d1aa4f67737d102441680df5d28a2740d6a2eaa83feb028ea19a9f49e2b',
    }
inventory = json.loads(inventory_path.read_text())
assert inventory['elf_sha256'] == elf_hash
dis_hash = hashlib.sha256(dis_path.read_bytes()).hexdigest()
assert dis_hash == inventory['disassembly_sha256']
layout = json.loads(layout_path.read_text())
for path, digest in layout['header_sha256'].items():
    assert hashlib.sha256((source / path).read_bytes()).hexdigest() == digest, path
source_hashes = {
    'engines/src/schwung_shim.cc': '2117b5f494ea61e9c7f9fdd62c2983597b2a43e82c4b38dc66596eb1c0c65aad',
    'engines/src/sw_sophie.cc': '9296be7b54c0d4305ed58bf45d43a88992a7085735b02359b7ea376790061a19',
    'engines/src/sw_psxverb.cc': '1a1a31d8d7c7acdba701fe033911441b3bd52df6cf9ef64bf8acc520facdc00d',
    'engines/third_party/schwung-modules/sophie/sophie.c': '6a43cd14ca377e3ce9d0bf3e63e121a9f04146252bf21b8a5ccea2b09fc1e1b1',
    'engines/third_party/schwung-modules/psxverb/psxverb.c': '789bc7ed9f42fb0164651e986be585041b6b97305362aa9c7dcfc879b177f05b',
}
for path, digest in source_hashes.items():
    assert hashlib.sha256((source / path).read_bytes()).hexdigest() == digest, path
symbols = elf.symbols
def symbol(name):
    found = [s for s in symbols if s['name'] == name and s['shndx']]
    assert len(found) == 1, (name, found)
    return found[0]
def word(address):
    data = elf.read(address, 4)
    assert data is not None, hex(address)
    return struct.unpack('<I', data)[0]
def target(name):
    result = symbol(name)['value']
    assert name in inventory['functions'][hex(result)]['names'], name
    return hex(result)
offset = layout['values']
modules = {}
for name, mangled, kind, init, focus in [
    ('sophie', '_ZN3fm19sw_sophieL7kModuleE', 1, 'fm1_sw_sophie_init', '_ZN3fm19sw_sophie6PadKeyEPcmjPKc'),
    ('psxverb', '_ZN3fm110sw_psxverbL7kModuleE', 2, 'fm1_sw_psxverb_init', None)]:
    entry = symbol(mangled)
    assert entry['size'] == offset['module_size'] == 48
    address = entry['value']
    assert word(address + offset['module_kind']) == kind
    assert word(address + offset['module_sound_init']) == (int(target(init), 16) if kind == 1 else 0)
    assert word(address + offset['module_fx_init']) == (int(target(init), 16) if kind == 2 else 0)
    assert word(address + offset['module_focus_key']) == (int(target(focus), 16) if focus else 0)
    modules[name] = dict(address=hex(address), init=target(init), focus=target(focus) if focus else None)

sound = {}
api = symbol('g_api')
assert api['size'] == offset['sound_size'] == 32
assert word(api['value'] + offset['sound_api_version']) == 2
for role, name in [('create_instance', 'sophie_create'), ('destroy_instance', 'sophie_destroy'),
    ('on_midi', 'sophie_midi'), ('set_param', 'sophie_set'), ('get_param', 'sophie_get'),
    ('get_error', 'sophie_error'), ('render_block', 'sophie_render')]:
    sound[role] = target(name)
    assert word(api['value'] + offset['sound_' + role]) == int(sound[role], 16)

# PSX's older six-field v2 table is BSS, filled by its init. Do not read
# uninitialized ELF bytes as callbacks, or inspect the newer on_midi field.
fx_api = symbol('g_fx_api_v2')
assert fx_api['size'] == 24 and offset['fx_get_param'] + 4 == 24
fx = {role: target(name) for role, name in [
    ('create_instance', 'v2_create_instance'), ('destroy_instance', 'v2_destroy_instance'),
    ('process_block', 'v2_process_block'), ('set_param', 'v2_set_param'), ('get_param', 'v2_get_param')]}
instructions = {}
opcodes = {}
for line in dis_path.read_text().splitlines():
    match = re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2}\s+)+)\s*(.*)$', line)
    if match:
        pc = hex(int(match[1], 16))
        instructions[pc] = match[3].strip()
        opcodes[pc] = bytes.fromhex(match[2])

assert instructions['0x2014304'] == 'r2 = 24'
assert instructions['0x20142fc'].startswith('r4 = r5 + 180')
assert 29410288 + 180 == fx_api['value']
assert instructions['0x2014310'] == '[++r5=180] = r0'
assert instructions['0x201430e'] == 'r0 = 2'
stores = {}
for role, load_pc, store_pc in [('create_instance', '0x2014314', '0x201431a'),
    ('destroy_instance', '0x201431c', '0x2014322'), ('process_block', '0x2014324', '0x201432a'),
    ('set_param', '0x201432c', '0x2014332'), ('get_param', '0x2014334', '0x201433a')]:
    assert instructions[load_pc].startswith('r0 = ' + str(int(fx[role], 16)) + ' ')
    assert instructions[store_pc] == '[r5+' + str(offset['fx_' + role]) + '] = r0'
    stores[role] = dict(load_pc=load_pc, store_pc=store_pc, target=fx[role])

sites = []
def site(caller, pc, role, targets):
    row = inventory['functions'][caller]
    assert any(s['kind'] == 'indirect' and s['pc'] == pc for s in row['unresolved']), pc
    sites.append(dict(caller=caller, pc=pc, role=role, targets=targets))
# The immutable shim installs these host hooks before module initialization.
# Check actual compiled store/load offsets rather than assuming host ABI size.
host_hooks = {}
for role, name, load_pc, store_pc, field, caller, call_pc, read_pc, read_insn in [
    ('log', '_ZN3fm17schwung12_GLOBAL__N_17HostLogEPKc',
     '0x202f69c', '0x202f6a2', 24, '0x20142c0', '0x20142ee', '0x20142ec', 'r1 = [r0+24]'),
    ('get_clock_status', '_ZN3fm17schwung12_GLOBAL__N_115HostClockStatusEv',
     '0x202f6ae', '0x202f6b4', 36, '0x201b0f2', '0x201b7c4', '0x201b7be', 'r0 = [r0+36]')]:
    destination = target(name)
    assert instructions[load_pc].startswith('r1 = ' + str(int(destination, 16)) + ' ')
    assert instructions[store_pc] == '[r7+' + str(field) + '] = r1'
    assert instructions[read_pc] == read_insn
    host_hooks[role] = dict(target=destination, field_offset=field,
        load_pc=load_pc, store_pc=store_pc, read_pc=read_pc)
    site(caller, call_pc, 'host.' + role, [destination])
site('0x202b20e', '0x202b220', 'sound.destroy_instance', [sound['destroy_instance']])
site('0x202b20e', '0x202b22c', 'fx.destroy_instance', [fx['destroy_instance']])
site('0x202b234', '0x202b256', 'sound.on_midi', [sound['on_midi']])
site('0x202b30a', '0x202b3e0', 'sound/fx.set_param', [sound['set_param'], fx['set_param']])
for pc, role, targets in [
    ('0x202f6f4', 'module.sound_init', [modules['sophie']['init']]),
    ('0x202f714', 'module.fx_init', [modules['psxverb']['init']]),
    ('0x202f92e', 'sound/fx.create_instance', [sound['create_instance'], fx['create_instance']]),
    ('0x202f94a', 'sound.destroy_instance', [sound['destroy_instance']]),
    ('0x202f958', 'fx.destroy_instance', [fx['destroy_instance']]),
    ('0x202f9b8', 'module.focus_key', [modules['sophie']['focus']]),
    ('0x202f9c8', 'sound/fx.get_param', [sound['get_param'], fx['get_param']])]:
    site('0x202f618', pc, role, targets)
# objdump also prints literal/data regions; validate only the instructions
# that this receipt claims, including every selected indirect call.
checked_pcs = {'0x2014304', '0x20142fc', '0x2014310', '0x201430e'}
for row in stores.values():
    checked_pcs.update([row['load_pc'], row['store_pc']])
for row in host_hooks.values():
    checked_pcs.update([row['load_pc'], row['store_pc'], row['read_pc']])
checked_pcs.update(row['pc'] for row in sites)
for pc in checked_pcs:
    assert elf.read(int(pc, 16), len(opcodes[pc])) == opcodes[pc], ('ELF opcode mismatch', pc)
receipt = dict(scope='source/table-reviewed candidate targets; no runtime provenance or stack bound',
    elf_sha256=elf_hash, disassembly_sha256=dis_hash,
    inventory_sha256=hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
    layout_sha256=hashlib.sha256(layout_path.read_bytes()).hexdigest(),
    reviewed_source_sha256=source_hashes, modules=modules, sound=sound, fx=fx,
    psx_initializer_stores=stores, host_hooks=host_hooks, site_rules=sites, hardware_admitted=False)
output.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(dict(modules=len(modules), startup_sites=len(sites), hardware_admitted=False)))
