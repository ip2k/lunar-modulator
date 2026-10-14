"""Source-reviewed callback candidates, retaining unresolved sites and limits."""
import hashlib
import json
import pathlib
import struct
import sys

assert len(sys.argv) in (3, 5, 6), 'usage: INVENTORY OUTPUT [ELF SOURCE [SCHWUNG_RECEIPT]]'
inventory_path, output = map(pathlib.Path, sys.argv[1:3])
inventory = json.loads(inventory_path.read_text())
graph = inventory['functions']

def names(*wanted):
    return {address for address, row in graph.items()
        if any(name in wanted for name in row['names'])}

def callbacks(registry, *members):
    return {callback['address'] for entry in inventory['registries'][registry]
        for member, callback in entry['callbacks'].items() if member in members}

eng = lambda *m: callbacks('fm1_engines', *m)
mod = lambda *m: callbacks('fm1_mod_kinds', *m)
midi = lambda *m: callbacks('fm1_midi_fxs', *m)
readers = names('read_bytes', 'read_bytes.5244', 'read_bytes.5270',
    'read_bytes.5278', 'read_bytes.5296', 'read_bytes.5310', 'scalar_read')
sinks = names('set_record', 'record', 'seed_record', 'base_record',
    'sequence_record', 'parameter_record', 'scalar_record', 'dx7_record',
    'view_record', 'fm1_state_mod_sink')
# Whole-function unions deliberately overapproximate multiple call sites.
# These candidates do not prove callback provenance or dynamic wrapper coverage.
rules = {
    'layout.2775': mod('instance_size'),
    'mod_plan_build': mod('destroy'),
    'voice_drop_with': mod('destroy'),
    'fm1_mod_destroy': mod('destroy'),
    'fm1_mod_set_kind': mod('instance_size', 'create', 'destroy'),
    'fm1_state_mod_sink': mod('set_data'),
    'parameter_record': eng('set_param'),
    'mod_release': eng('set_param', 'pitch_bend', 'set_param_note'),
    'seq_release_sound': eng('note_off'),
    'mfx_ram': midi('instance_size'),
    'lunar_project_units_plan': eng('instance_size') | mod('instance_size') | midi('instance_size'),
    'lunar_project_engines_release': eng('destroy'),
    'lunar_project_engines_stage': eng('create', 'instance_size'),
    'lunar_project_engines_apply': eng('set_param'),
    'lunar_project_adopt_audio_units': eng('destroy', 'set_param', 'pitch_bend', 'set_param_note'),
    'lunar_project_restore_midi_units': midi('instance_size', 'create', 'destroy', 'set_param'),
    'fm1_state_bin_read': readers,
    'cs_get': readers,
    'cs_src': readers,
    'in_byte': names('cs_src'),
    'bemit': sinks,
    'kv_each': names('info_kv', 'proj_kv', 'view_kv', 'setg_kv', 'level_kv'),
    'ib': names('pull_byte'),
    'tflush': names('line_text'),
}
vtables = {}
virtual_sites = []
source_hashes = {}
if len(sys.argv) > 3:
    # Optional ELF and source arguments add only the model classes constructed
    # by these two wrappers. This remains a whole-function candidate union.
    elf_path, source = map(pathlib.Path, sys.argv[3:5])
    sys.path.insert(0, str(source / 'tools/jieli'))
    from audit_link import Elf
    assert hashlib.sha256(elf_path.read_bytes()).hexdigest() == inventory['elf_sha256']
    elf = Elf(elf_path.read_bytes())
    models = {
        '_ZN3fm15macro8Instance12BuildEnginesEv': [
            'VirtualAnalogVCFEngine', 'PhaseDistortionEngine', 'WaveTerrainEngine',
            'ChiptuneEngine', 'VirtualAnalogEngine', 'WaveshapingEngine',
            'FMEngine', 'WavetableEngine'],
        '_ZN3fm111macro_heavy8Instance12BuildEnginesEv': [
            'StringMachineEngine', 'ChordEngine', 'SpeechVoiceEngine', 'GrainEngine',
            'AdditiveEngine', 'SwarmEngine', 'NoiseEngine', 'ParticleEngine',
            'StringEngine', 'ModalEngine', 'BassDrumEngine', 'SnareDrumEngine',
            'HiHatEngine'],
    }
    # PCs and field loads inspected in the matching vendor disassembly.
    # Require this exact artifact for these call-site claims.
    assert inventory['elf_sha256'] == 'df358a616de234c0263344cffda7d5fd626a4c1079dd5f352574cfe77fa93a8e'
    sites = {
        '_ZN3fm15macro8Instance12BuildEnginesEv': [
            ('0x2061562', 'Init'), ('0x206156e', 'LoadUserData'), ('0x2061578', 'Reset')],
        '_ZN3fm111macro_heavy8Instance12BuildEnginesEv': [
            ('0x2062014', 'Init'), ('0x2062054', 'LoadUserData'), ('0x206205e', 'Reset')],
    }
    for caller, classes in models.items():
        targets = set()
        by_role = {role: set() for role in ('Init', 'Reset', 'LoadUserData')}
        for cls in classes:
            namespace = '3fm111macro_heavy' if cls == 'SpeechVoiceEngine' else '6plaits'
            symbol_name = f'_ZTVN{namespace}{len(cls)}{cls}E'
            matches = [s for s in elf.symbols if s['name'] == symbol_name and s['shndx']]
            assert len(matches) == 1, symbol_name
            symbol = matches[0]
            assert symbol['size'] == 24, symbol_name
            words = struct.unpack('<6I', elf.read(symbol['value'], 24))
            assert words[:2] == (0, 0), symbol_name
            methods = {}
            for slot, (role, suffix) in enumerate([
                ('Init', '4InitE'), ('Reset', '5ResetEv'),
                ('LoadUserData', '12LoadUserDataE'), ('Render', '6RenderE')], 2):
                address = hex(words[slot])
                assert address in graph, (symbol_name, role, address)
                assert any(suffix in n for n in graph[address]['names']), (symbol_name, role)
                methods[role] = {'address': address, 'names': graph[address]['names']}
                if role != 'Render':
                    targets.add(address)
                    by_role[role].add(address)
            vtables[symbol_name] = {'address': hex(symbol['value']), 'methods': methods}
        rules[caller] = targets
        caller_addresses = names(caller)
        assert len(caller_addresses) == 1, caller
        caller_address = next(iter(caller_addresses))
        indirect_pcs = {site['pc'] for site in graph[caller_address]['unresolved']
            if site['kind'] == 'indirect'}
        assert indirect_pcs == {pc for pc, _ in sites[caller]}, caller
        for pc, role in sites[caller]:
            virtual_sites.append({'caller': caller_address, 'name': caller, 'pc': pc,
                'role': role, 'vptr_offset': {'Init': 0, 'Reset': 4, 'LoadUserData': 8}[role],
                'targets': sorted(by_role[role])})
    modal = '_ZN6plaits11ModalEngine4InitEPN6stmlib15BufferAllocatorE'
    reset = vtables['_ZTVN6plaits11ModalEngineE']['methods']['Reset']['address']
    rules[modal] = {reset}
    modal_address = next(iter(names(modal)))
    assert graph[modal_address]['unresolved'] == [
        {'pc': '0x202b71a', 'kind': 'indirect', 'instruction': 'call r1'}]
    virtual_sites.append({'caller': modal_address, 'name': modal, 'pc': '0x202b71a',
        'role': 'Reset', 'vptr_offset': 4, 'targets': [reset]})
    expected_source = {
        'engines/src/mi_macro.cc': '4ebb991023229043183d07d2d741359552d2f1dee13e3be1b9e6acad459ed98a',
        'engines/src/mi_macro_heavy.cc': '4b82ba327114348b8e775af97ff0163cba2610b351da2a15a6f96aafea65fe0e',
        'engines/third_party/mutable/plaits/dsp/engine/engine.h': 'c31fa0ad1585c4fff9451d844dab4bfaff1823dc677cebf182957827518a43ef',
        'engines/third_party/mutable/plaits/dsp/engine/modal_engine.cc': '6fb8374b32378bd7b99cd4cc7421b12af681ce973de03a7148ae901c99c71a7a',
    }
    for path, expected in expected_source.items():
        source_hashes[path] = hashlib.sha256((source / path).read_bytes()).hexdigest()
        assert source_hashes[path] == expected, ('reviewed source changed', path)
    # Exact-source candidate edges for the PROJECT catalogue and MIDI flush.
    # record's +44 load is names->known, not engine->note_on: identical offsets
    # in unrelated structs must not be assigned the same callback role.
    application_sources = {
        'engines/state/state_names.c': '023be58014b9c4d62cfd2822bb270cea923dd5d37f80ed0bce52ad651e04be57',
        'engines/state/state_registry.c': 'bd1e579c57f445ff041722ae6157bb91b5f20703d202d341b99f7f8922e2674a',
        'firmware/native/project_units.c': 'd7617ca904dbfc271cd24b6b023bba3f54124be782d55ae808906546cf6bf1c9',
        'engines/seq/mfx_host.c': '459ab6163676fc7a5bc772ac04c75a26f294f626269ed941dab182c238f320a4',
        'sim/web/src/fm1_app.c': '903b50f83a8611dcb764745ac9f11d5c9bc8bff2910ca6c9dd2df190e4d25189',
    }
    # Keep historical receipts reproducible: these candidates are enabled only
    # in the newer full expansion that supplies the Schwung receipt.
    if len(sys.argv) == 6:
        for path, digest in application_sources.items():
            source_hashes[path] = hashlib.sha256((source / path).read_bytes()).hexdigest()
            assert source_hashes[path] == digest, ('reviewed application changed', path)
        for caller, pcs in [('record', ['0x2060d08']),
                            ('run_quiet', ['0x2042bcc', '0x2042c20']),
                            ('mfx_off', ['0x203a888'])]:
            found = names(caller)
            assert len(found) == 1, caller
            row = graph[next(iter(found))]
            assert [s['pc'] for s in row['unresolved'] if s['kind'] == 'indirect'] == pcs, caller
        assert len(names('fm1_absent_find')) == len(names('mfx_off')) == 1
        rules['record'] = names('fm1_absent_find')
        rules['run_quiet'] = midi('process') | names('mfx_off')
        rules['mfx_off'] = eng('note_off')
edges = {address: set(row['direct']) for address, row in graph.items()}
applied = {}
for address, row in graph.items():
    for name in row['names']:
        if name in rules and any(site['kind'] == 'indirect' for site in row['unresolved']):
            edges[address].update(rules[name])
            applied[address] = {'names': row['names'], 'targets': sorted(rules[name]),
                'empty_static_role': not bool(rules[name])}
schwung_sites = []
if len(sys.argv) == 6:
    schwung = json.loads(pathlib.Path(sys.argv[5]).read_text())
    assert schwung['elf_sha256'] == inventory['elf_sha256']
    assert schwung['inventory_sha256'] == hashlib.sha256(inventory_path.read_bytes()).hexdigest()
    for path, digest in schwung['reviewed_source_sha256'].items():
        assert hashlib.sha256((source / path).read_bytes()).hexdigest() == digest, path
    schwung_sites = schwung['site_rules']
    callers = {site['caller'] for site in schwung_sites}
    for caller in sorted(callers):
        sites = [site for site in schwung_sites if site['caller'] == caller]
        assert {s['pc'] for s in sites} == {s['pc'] for s in graph[caller]['unresolved']
            if s['kind'] == 'indirect'}, ('incomplete Schwung caller coverage', caller)
        targets = {t for site in sites for t in site['targets']}
        assert all(t in graph for t in targets)
        edges[caller].update(targets)
        applied[caller] = {'names': graph[caller]['names'], 'targets': sorted(targets),
            'empty_static_role': not bool(targets)}
root = next(a for a, row in graph.items() if 'lunar_project_start' in row['names'])
seen, todo = set(), [root]
while todo:
    address = todo.pop()
    if address not in seen:
        seen.add(address)
        todo.extend(edges[address])
unresolved = [dict(caller=a, names=graph[a]['names'], **site)
    for a in sorted(seen) for site in graph[a]['unresolved']
    if site['kind'] != 'indirect' or a not in applied]
receipt = {'scope': 'candidate callback expansion; no stack bound or hardware admission',
    'elf_sha256': inventory['elf_sha256'],
    'inventory_sha256': hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
    'reachable_functions': len(seen), 'applied_rules': applied,
    'vtables': vtables, 'reviewed_source_sha256': source_hashes,
    'virtual_call_sites': virtual_sites,
    'unresolved': unresolved,
    'decoding_limit_instructions': sum(len(graph[a]['decoding_limits']) for a in seen),
    'limits': ['whole-function role unions are candidate edges, not proven per-site targets',
        'application DX7 wrapper callbacks require separate coverage',
        ('optional mod_emit observer and printf gadget need provenance checks'
         if len(sys.argv) == 6 else
         'run_quiet MIDI sink, mod_emit observer and printf gadget remain unresolved'),
        'new engine-internal callbacks need source review',
        'recursion, dynamic stack and IRQ overlap are not bounded'],
    'hardware_admitted': False}
if len(sys.argv) == 6:
    receipt['schwung_call_sites'] = schwung_sites
output.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'reachable_functions': len(seen), 'applied_rules': len(applied),
    'unresolved_sites': len(unresolved), 'unresolved_callers': sorted({
        n for site in unresolved for n in site['names']})}, indent=2))
