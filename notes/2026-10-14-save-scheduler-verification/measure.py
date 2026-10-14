#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline retained-SAVE link experiment; never an installable artifact."""
import hashlib
import json
import pathlib
import subprocess
import sys

SRC = pathlib.Path('/src')
BASE = pathlib.Path('/out/mixed-project-all13-stack-readout-v1/linked')
OUT = pathlib.Path('/out/save-scheduler-link-v1')
OUT.mkdir(exist_ok=False)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(BASE / 'lunar-app-probe.elf') == '35655a21de5c08d09fa19ef2fd4f253efbc107346c6e107a1988dca4e69dac29'
report = json.loads((BASE / 'verification.json').read_text())
objects = []
for entry in report['linked_objects']:
    obj = pathlib.Path(entry['path'])
    assert sha(obj) == entry['sha256'], str(obj)
    objects.append(obj)
replacements = {
    '/out/mixed-project-all13-stack-readout-v1/linked/app_probe.o': 'firmware/native/app_probe.c',
    '/catalogue/shard-00/obj/sim/src/fm1_app_state.o': 'sim/web/src/fm1_app_state.c',
    '/catalogue/shard-07/obj/c/seq/seq_persist.o': 'engines/seq/seq_persist.c',
    '/catalogue/shard-12/obj/state/state/state_bin.o': 'engines/state/state_bin.c',
}
flags = ['-target', 'pi32v2', '-mcpu=r3', '-mfprev1', '-Oz', '-flto',
         '-ffreestanding', '-fno-builtin', '-ffunction-sections', '-fdata-sections',
         '-DFM1_APP_EXTERNAL_ARENAS=1', '-DLUNAR_APP_PROBE=1', '-DNDEBUG',
         '-DFM1_TFT_INDEXED=1', '-DLUNAR_RETURN_TO_ROM_SECONDS=20',
         '-DLUNAR_STARTUP_PROJECT_INDEX=0', '-DLUNAR_STACK_WATERMARK=1',
         '-DLUNAR_COMPRESSED_WAVETABLES=1', '-DLUNAR_INSTANCE_MEMORY_BYTES=216064',
         '-DFM1_STATE_BIN_COMPACT_WRITER', '-DLUNAR_PROJECT_SAVE_SERVICE']
includes = [BASE / 'gen', SRC / 'engines/include', SRC / 'engines/mod',
            SRC / 'firmware/native', SRC / 'firmware/third_party/tlsf',
            SRC / 'firmware/third_party/tinf', SRC / 'engines/third_party/mutable',
            SRC / 'engines/host', SRC / 'engines/state', SRC / 'sim/web/src', BASE]
includes += [SRC / 'firmware/third_party/dinghy' / d for d in ('hal', 'src', 'gen')]
for path in includes:
    flags += ['-I', str(path)]
flags += ['-isystem', '/opt/jieli/pi32v2/include']
commands = []
for old, source in [*replacements.items(), (None, 'tests/native/project_save_app_target.c')]:
    dest = OUT / (pathlib.Path(source).stem + '.o')
    command = ['/opt/jieli/common/bin/clang', *flags, '-MMD', '-MF',
               str(dest.with_suffix('.d')), '-c', str(SRC / source), '-o', str(dest)]
    commands.append(command)
    result = subprocess.run(command, capture_output=True, text=True)
    (OUT / (dest.stem + '.compile.log')).write_text(result.stdout + result.stderr)
    if result.returncode:
        (OUT / 'commands.json').write_text(json.dumps(commands, indent=2))
        raise SystemExit(result.returncode)
    if old:
        index = objects.index(pathlib.Path(old))
        objects[index] = dest
    else:
        objects.append(dest)
roots = ('_start fm1_app_key fm1_app_button fm1_app_encoder fm1_app_master '
         'fm1_app_note_on fm1_app_note_off fm1_app_pitch_bend fm1_app_all_notes_off '
         'lunar_content_count lunar_content_catalogue lunar_content_load_set '
         'lunar_content_activate_set lunar_project_mod_stage lunar_project_seq_stage '
         'lunar_project_engines_stage lunar_project_engines_release lunar_project_engines_apply '
         'lunar_project_adopt_audio_units lunar_project_restore_midi_units '
         'lunar_project_restore_scalars lunar_project_restore_dx7 lunar_project_restore_mod '
         'fm1_app_mod_prepare_cold fm1_app_mod_adopt_cold lunar_project_start '
         'lunar_project_restore_view native_project_save_target native_project_save_poll native_project_save_ready').split()
elf = OUT / 'save-retained.elf'
command = ['/opt/jieli/pi32v2/bin/ld', '--plugin', '/opt/jieli/common/bin/LLVMgold.so',
           '--plugin-opt=mcpu=r3', '--plugin-opt=-mattr=+fprev1',
           '--plugin-opt=-pi32v2-large-program=true', '--gc-sections', '-T', str(BASE / 'app.ld')]
for root in roots:
    command += ['-u', root]
command += [*map(str, objects), '-Map', str(OUT / 'save-retained.map'), '-o', str(elf)]
commands.append(command)
(OUT / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
result = subprocess.run(command, capture_output=True, text=True)
(OUT / 'link.log').write_text(result.stdout + result.stderr)
receipt = dict(schema='lunar-retained-save-link-v1', baseline_elf_sha256=sha(BASE / 'lunar-app-probe.elf'),
               baseline_objects_verified=len(report['linked_objects']), replacements=replacements,
               link_exit=result.returncode, hardware_tested=False, installable=False,
               save_scheduling_integrated=False, physical_storage_admitted=False,
               driver_sha256=sha(pathlib.Path(__file__)),
               linked_objects=[dict(path=str(p), sha256=sha(p)) for p in objects])
if result.returncode == 0:
    sys.path.insert(0, str(SRC / 'tools/jieli'))
    from audit_link import Elf
    image = Elf(elf.read_bytes())
    assert image.symbol_value('native_project_save_target')
    receipt.update(elf_sha256=sha(elf), pool_end=image.symbol_value('_pool_end'),
                   guard=image.symbol_value('_guard0'),
                   global_arena_headroom=image.symbol_value('_guard0')-image.symbol_value('_pool_end'))
    for mode, name in [('-h', 'sections.txt'), ('-t', 'symbols.txt')]:
        with (OUT / name).open('w') as f:
            subprocess.run(['/opt/jieli/common/bin/objdump', mode, str(elf)], stdout=f, check=True)
(OUT / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({k:v for k,v in receipt.items() if k != 'linked_objects'}, indent=2))
raise SystemExit(result.returncode)
