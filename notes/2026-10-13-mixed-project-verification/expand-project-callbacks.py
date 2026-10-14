"""Source-reviewed callback candidates, retaining unresolved sites and limits."""
import hashlib
import json
import pathlib
import sys

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
edges = {address: set(row['direct']) for address, row in graph.items()}
applied = {}
for address, row in graph.items():
    for name in row['names']:
        if name in rules and any(site['kind'] == 'indirect' for site in row['unresolved']):
            edges[address].update(rules[name])
            applied[address] = {'names': row['names'], 'targets': sorted(rules[name]),
                'empty_static_role': not bool(rules[name])}
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
    'unresolved': unresolved,
    'decoding_limit_instructions': sum(len(graph[a]['decoding_limits']) for a in seen),
    'limits': ['whole-function role unions are candidate edges, not proven per-site targets',
        'application DX7 wrapper callbacks require separate coverage',
        'run_quiet MIDI sink, mod_emit observer and printf gadget remain unresolved',
        'new engine-internal callbacks need source review',
        'recursion, dynamic stack and IRQ overlap are not bounded'],
    'hardware_admitted': False}
output.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'reachable_functions': len(seen), 'applied_rules': len(applied),
    'unresolved_sites': len(unresolved), 'unresolved_callers': sorted({
        n for site in unresolved for n in site['names']})}, indent=2))
