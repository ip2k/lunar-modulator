#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Link a private timed shared-app probe; never install or access a device.

Consumes the sixteen compile_catalogue.py -Oz/LTO/shared-resampler outputs.
Cached object hashes and source manifests are checked against current inputs.
Hardware admission remains a separate operation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from module_selection import resolve_modules, wavetable_namespaces
import sys

from build_probe import check_pins
from compile_catalogue import source_manifest
from compact_font import compact_header, compact_gfx
from prepare_wavetables import prepare
from embed_image_content import content_source
from verify_image_profile import load_prepared_profile
from flash_layout import FLASH_LAYOUTS, app_budget, linker_script

ROOT = Path(__file__).resolve().parents[2]
ENGINE_IDS = ('macro', 'shapes', 'macro-heavy', 'sixop', 'dx7', 'sw-sophie',
              'drums', 'acid-bass', 'comet', 'crater', 'drawbar', 'trio',
              'phase-bend', 'test-sine')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise SystemExit('Pinned adaptation no longer matches: ' + old)
    return text.replace(old, new)


def checked_catalogue(root, compressed=False, indexed_tft=False, shapes_voices=12):
    objects, receipts, indices = [], [], set()
    inputs = source_manifest(ROOT)
    expected = json.loads((root / 'shard-00/objects.json').read_text())
    for shard in range(16):
        directory = root / ('shard-%02d' % shard)
        report = json.loads((directory / 'report.json').read_text())
        required = dict(shard=shard, chunks=16, catalogue_objects=len(expected),
                        gpl_mods=1, modules='all', optimization='-Oz', lto=True,
                        shared_resampler=True, indexed_tft=indexed_tft, shapes_voices=shapes_voices,
                        closed_sdk_archives=[],
                        device_sdk_headers=[])
        if any(report.get(k) != v for k, v in required.items()):
            raise SystemExit('Incompatible catalogue report: ' + str(directory))
        if report.get('source_manifest') != inputs:
            raise SystemExit('Catalogue source manifest is stale or absent')
        if json.loads((directory / 'objects.json').read_text()) != expected:
            raise SystemExit('Catalogue object lists differ')
        if digest(directory / 'cxx/__config') != report['configured_sha256']:
            raise SystemExit('Catalogue C++ configuration hash mismatch')
        for item in report['results']:
            index = item['index']
            if (index in indices or index % 16 != shard or
                    not 0 <= index < len(expected) or
                    item['object'] != expected[index] or item['exit']):
                raise SystemExit('Invalid catalogue result')
            indices.add(index)
            relative = Path(item['object'])
            if relative.is_absolute() or '..' in relative.parts:
                raise SystemExit('Invalid catalogue object path')
            obj = directory / 'obj' / relative
            if digest(obj) != item['sha256']:
                raise SystemExit('Catalogue object hash mismatch: ' + str(obj))
            receipts.append(dict(path=str(obj), sha256=item['sha256']))
            if item['object'] not in ('sim/src/fm1_web.o', 'sim/src/fm1_app.o',
                                       'our/src/registry.o') and not (compressed and
                                       item['object'] in tuple('tp/' + n + '/resources.o' for n in compressed)):
                objects.append(obj)
    if indices != set(range(len(expected))):
        raise SystemExit('Incomplete catalogue')
    return objects, receipts



def measure_app_storage(compiler, flags, out):
    """Use target ABI constants, not host sizeof, for framebuffer pool credit."""
    source = out / 'measure_app_storage.c'
    source.write_text('#include "fm1_app.h"\n'
                      'unsigned lunar_app_storage(void) { return sizeof(fm1_app_t); }\n')
    sizes = []
    common = [flag for flag in flags if not flag.startswith('-DFM1_TFT_INDEXED=')]
    for indexed in (0, 1):
        ir = out / ('app-storage-%d.ll' % indexed)
        subprocess.run([compiler, *common, '-DFM1_TFT_INDEXED=' + str(indexed),
                        '-std=c99', '-S', '-emit-llvm', str(source), '-o', str(ir)],
                       check=True, capture_output=True, text=True)
        match = re.search(r'define[^\n]*@lunar_app_storage\([^}]*?ret i32 (\d+)',
                          ir.read_text(), re.S)
        if not match:
            raise SystemExit('Target application sizeof did not reduce to one constant')
        sizes.append(int(match.group(1)))
    if sizes[1] > sizes[0]:
        raise SystemExit('Indexed application unexpectedly exceeds RGB565 storage')
    return dict(rgb565_bytes=sizes[0], indexed_bytes=sizes[1],
                pool_credit_bytes=(sizes[0] - sizes[1]) // 16 * 16)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--catalogue', type=Path, required=True)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--flash-layout', choices=FLASH_LAYOUTS, default='protected',
                        help='Explicit link budget only; does not admit packaging or installation')
    parser.add_argument('--exclude', choices=ENGINE_IDS, action='append', default=[])
    parser.add_argument('--modules', help='Literal comma-separated engine/effect/MIDI/mod IDs; '
                        'timed probe must retain trio; incompatible with --exclude')
    parser.add_argument('--prepared-profile', type=Path,
                        help='Checked builder input directory; replaces --modules/--exclude')
    parser.add_argument('--expected-profile-sha256',
                        help='Controller-retained prepared manifest digest')
    parser.add_argument('--link-set-loader', action='store_true',
                        help='Retain the standalone streaming set loader; does not activate content')
    parser.add_argument('--link-project-loader', action='store_true',
                        help='Retain disposable project modulation/sequence staging; does not activate a project')
    parser.add_argument('--startup-set-index', type=int,
                        help='Opt-in timed probe: stage this embedded SET before Trio allocation; '
                        'requires --link-set-loader and a prepared profile')
    parser.add_argument('--shapes-voices', type=int, choices=range(1, 13), default=12,
                        help='Require the selected Shapes polyphony in the catalogue')
    parser.add_argument('--indexed-tft', action='store_true',
                        help='Require a uniformly indexed catalogue and application')
    parser.add_argument('--compressed-wavetables', action='store_true',
                        help='Startup decode fixed RAM tables; reduce instance pool accordingly')
    parser.add_argument('--flash-plaits-wavetables', action='store_true',
                        help='With compressed tables, retain original Plaits wave bank in flash '
                        'to recover RAM; decode Braids only when Shapes is selected')
    args = parser.parse_args()
    if bool(args.prepared_profile) != bool(args.expected_profile_sha256):
        parser.error('--prepared-profile and --expected-profile-sha256 require each other')
    if args.prepared_profile and (args.modules is not None or args.exclude):
        parser.error('--prepared-profile cannot be combined with --modules or --exclude')
    content_inputs, generated_content = None, None
    if args.prepared_profile:
        try:
            content_inputs = load_prepared_profile(args.prepared_profile,
                                                  args.expected_profile_sha256)
            generated_content = content_source(content_inputs)
            args.modules = ','.join(content_inputs.report['module_selection']['selected'])
        except (ValueError, OSError, KeyError, TypeError) as error:
            parser.error(str(error))
    if args.startup_set_index is not None:
        if not args.link_set_loader or not content_inputs:
            parser.error('--startup-set-index requires --link-set-loader and --prepared-profile')
        assets = content_inputs.report['content']
        if not 0 <= args.startup_set_index < len(assets):
            parser.error('--startup-set-index is outside the embedded catalogue')
        if assets[args.startup_set_index]['kind'] != 'set':
            parser.error('--startup-set-index must identify a SET, not a project')
    if args.flash_plaits_wavetables and not args.compressed_wavetables:
        parser.error('--flash-plaits-wavetables requires --compressed-wavetables')
    tc, catalogue, out = (p.resolve() for p in
                           (args.toolchain, args.catalogue, args.build))
    if len(set(args.exclude)) != len(args.exclude) or 'trio' in args.exclude:
        parser.error('Exclusions must be unique and retain the initial Trio engine')
    if args.modules is not None and args.exclude:
        parser.error('--modules and --exclude cannot be combined')
    out.mkdir(parents=True, exist_ok=False)
    # Generate both registry flags and omitted-module metadata together.
    # Reuse the canonical catalogue rather than editing engine flags alone.
    try:
        _, all_modules = resolve_modules(ROOT, out / 'module-all', 'all')
        specification = (args.modules if args.modules is not None else
                         ','.join(x for x in all_modules['selected'] if x not in args.exclude)
                         if args.exclude else 'all')
        module_header, module_selection = resolve_modules(ROOT, out / 'module-selection', specification)
    except ValueError as error:
        parser.error(str(error))
    if 'trio' not in module_selection['selected']:
        parser.error('Timed probe must retain the initial Trio engine')
    if content_inputs and module_header != content_inputs.module_header:
        parser.error('Prepared module header differs from current module selection')
    args.exclude = [x for x in ENGINE_IDS if x not in module_selection['selected']]
    platform = ROOT / 'firmware/third_party/dinghy'
    for name in ('dinghy', 'compiler-rt', 'musl', 'printf', 'tlsf'):
        check_pins(ROOT / 'firmware/third_party' / name)
    wave_namespaces = (wavetable_namespaces(module_selection['selected'], args.flash_plaits_wavetables)
                       if args.compressed_wavetables else [])
    objects, catalogue_receipts = checked_catalogue(catalogue, wave_namespaces, args.indexed_tft, args.shapes_voices)
    wave_records = []
    if args.compressed_wavetables:
        check_pins(ROOT / 'firmware/third_party/tinf')
        wave_records = prepare(out, wave_namespaces)
    # Keep crash/recovery text while eliminating redundant four-bit storage
    # for the pinned small face, whose alpha is strictly binary.
    (out / 'felucca_font.h').write_text(compact_header(
        (platform / 'gen/felucca_font.h').read_text()))
    (out / 'gfx.c').write_text(compact_gfx((platform / 'src/gfx.c').read_text()))
    source = (platform / 'src/platform.c').read_text()
    replacements = {
        '    ota_boot_cleanup();': '    /* Timed probe: retain OTA staging bytes. */',
        '#define FL_RANGE_OK(off, n) (FL_IN(off, n, FL_OTA_LO, FL_OTA_HI) || FL_IN(off, n, SETTINGS_AT, SETTINGS_AT + 0x1000u))':
            '#define FL_RANGE_OK(off, n) (0) /* Timed probe: no NOR writes. */',
        '#define CV_MAX (240u * 64u)': '#define CV_MAX (240u * 16u)',
        'static volatile int32_t master_q12 = 2048;':
            'static volatile int32_t master_q12 = 4096;',
        'master_q12 = (int32_t)((k10 * k10) >> 8);':
            'lunar_master_raw = (int32_t)k10;',
    }
    for old, new in replacements.items():
        source = replace_once(source, old, new)
    (out / 'platform.c').write_text(source)
    source = (platform / 'src/libc.c').read_text()
    for name in ('memset', 'memcpy', 'memcmp'):
        # Keep private HAL definitions; common calls use the pinned C runtime.
        source = replace_once(source, name + '(', 'dinghy_' + name + '(')
    (out / 'libc.c').write_text(source)
    source = replace_once((platform / 'crt0.S').read_text(), '1:\tr1 = icfg',
                         '1:\tcli\n\tr3 = cnum\n\tif (r3 != 0) goto lunar_entry_rejected\n'
                         '\tr3 = 0x01C7FE08\n\tif (r0 != r3) goto lunar_entry_rejected\n\tr1 = icfg')
    (out / 'crt0.S').write_text(source + '\nlunar_entry_rejected:\n\tgoto lunar_entry_rejected\n')
    gen = out / 'gen'
    shutil.copytree(catalogue / 'shard-00/obj/gen', gen)
    header = gen / 'fm1_modules.h'
    header.write_bytes(module_header)
    compiler = str(tc / 'common/bin/clang')
    flags = ['-target', 'pi32v2', '-mcpu=r3', '-mfprev1', '-Oz', '-flto',
             '-ffreestanding', '-fno-builtin', '-ffunction-sections', '-fdata-sections',
             '-DFM1_APP_EXTERNAL_ARENAS=1', '-DLUNAR_APP_PROBE=1', '-DNDEBUG',
             '-DFM1_TFT_INDEXED=' + str(int(args.indexed_tft))]
    if args.startup_set_index is not None:
        flags += ['-DLUNAR_STARTUP_SET_INDEX=' + str(args.startup_set_index)]
    if args.compressed_wavetables:
        flags += ['-DLUNAR_COMPRESSED_WAVETABLES=1']
    for directory in (gen, ROOT / 'engines/include', ROOT / 'engines/mod',
                      ROOT / 'firmware/native', ROOT / 'firmware/third_party/tlsf',
                      ROOT / 'firmware/third_party/tinf', ROOT / 'engines/third_party/mutable', ROOT / 'engines/host',
                      ROOT / 'engines/state', ROOT / 'sim/web/src', out,
                      platform / 'hal', platform / 'src', platform / 'gen'):
        flags += ['-I', str(directory)]
    flags += ['-isystem', str(tc / 'pi32v2/include')]
    app_storage = measure_app_storage(compiler, flags, out)
    instance_pool_bytes = (192000 +
                           (app_storage['pool_credit_bytes'] if args.indexed_tft else 0) -
                           sum(r['raw_bytes'] for r in wave_records))
    flags += ['-DLUNAR_INSTANCE_MEMORY_BYTES=' + str(instance_pool_bytes)]
    for path in (out / 'crt0.S', platform / 'hal/fm1_vec.S', platform / 'hal/fm1_isr.S'):
        obj = out / (path.stem + '.o')
        subprocess.run([compiler, *[f for f in flags if f != '-flto'], '-c', str(path),
                        '-o', str(obj)], check=True)
        objects.append(obj)
    extra_sources = ([out / ('resources_' + n + '.cc') for n in wave_namespaces] + [
                      ROOT / 'firmware/native/wave_tables.c',
                      ROOT / 'firmware/third_party/tinf/tinflate.c']
                     if args.compressed_wavetables else [])
    if content_inputs:
        content_path = out / 'content_catalogue.c'
        content_path.write_bytes(generated_content)
        extra_sources.append(content_path)
    if args.link_set_loader:
        # The freshness-checked catalogue already contains the state codecs.
        extra_sources.append(ROOT / 'firmware/native/content_set.c')
    if args.link_project_loader:
        # Shared state codecs/applier are already in the checked catalogue.
        extra_sources += [ROOT / 'firmware/native/project_units.c',
                          ROOT / 'firmware/native/project_mod.c',
                          ROOT / 'firmware/native/project_seq.c',
                          ROOT / 'firmware/native/project_engines.c',
                          ROOT / 'firmware/native/project_start.c']
    for path in [ROOT / 'sim/web/src/fm1_app.c', ROOT / 'engines/host/mod_script.c',
                 ROOT / 'firmware/native/app_probe.c', ROOT / 'firmware/native/instance_pool.c',
                 ROOT / 'firmware/native/tlsf_runtime.c', ROOT / 'engines/src/registry.cc', *extra_sources]:
        obj = out / (path.stem + '.o')
        cxx = (['-std=c++11', '-fno-exceptions', '-fno-rtti', '-DTEST',
                '-I', str(ROOT / 'engines/src'), '-isystem', str(catalogue / 'shard-00/cxx'),
                '-D_LIBCPP_HAS_NO_THREADS', '-D_LIBCPP_DISABLE_EXTERN_TEMPLATE']
               if path.suffix == '.cc' else [])
        subprocess.run([compiler, *flags, *cxx, '-c', str(path), '-o', str(obj)], check=True)
        objects.append(obj)
    # Rebuild the small runtimes from checked sources instead of trusting globbed objects.
    runtime = out / 'runtime'
    subprocess.run([sys.executable, str(ROOT / 'tools/native/build_libc.py'),
                    '--toolchain', str(tc), '--build', str(runtime / 'musl')],
                   check=True, stdout=(out / 'libc-build.json').open('w'))
    objects += sorted((runtime / 'musl').glob('*.o'))
    subprocess.run(['make', '-s', '-C', str(ROOT / 'tools/native'), '-j16',
                    'BUILD=' + str(runtime / 'arithmetic'), 'JIELI_TOOLCHAIN=' + str(tc)], check=True)
    objects += [p for p in sorted((runtime / 'arithmetic').glob('*.o'))
                if p.name not in ('arithmetic-probe.o', 'arithmetic-linked.o')]
    printf = runtime / 'printf.o'
    subprocess.run([compiler, *[f for f in flags if f != '-flto'],
                    '-DPRINTF_ALIAS_STANDARD_FUNCTION_NAMES_HARD=1',
                    '-I', str(ROOT / 'firmware/third_party/printf'), '-c',
                    str(ROOT / 'firmware/third_party/printf/printf/printf.c'),
                    '-o', str(printf)], check=True)
    objects.append(printf)
    roots = ('_start', 'fm1_app_key', 'fm1_app_button', 'fm1_app_encoder',
             'fm1_app_master', 'fm1_app_note_on', 'fm1_app_note_off',
             'fm1_app_pitch_bend', 'fm1_app_all_notes_off')
    if content_inputs:
        roots += ('lunar_content_count', 'lunar_content_catalogue')
    if args.link_set_loader:
        roots += ('lunar_content_load_set', 'lunar_content_activate_set')
    if args.link_project_loader:
        roots += ('lunar_project_mod_stage', 'lunar_project_seq_stage',
                  'lunar_project_engines_stage', 'lunar_project_engines_release',
                  'lunar_project_engines_apply', 'lunar_project_adopt_audio_units',
                  'lunar_project_restore_midi_units', 'lunar_project_restore_scalars',
                  'lunar_project_restore_dx7')
    elf = out / 'lunar-app-probe.elf'
    script = out / 'app.ld'
    script.write_text(linker_script((ROOT / 'firmware/native/app.ld').read_text(), args.flash_layout))
    command = [str(tc / 'pi32v2/bin/ld'), '--plugin', str(tc / 'common/bin/LLVMgold.so'),
               '--plugin-opt=mcpu=r3', '--plugin-opt=-mattr=+fprev1',
               '--plugin-opt=-pi32v2-large-program=true', '--gc-sections',
               '-T', str(script)]
    for symbol in roots:
        command += ['-u', symbol]
    command += [*map(str, objects), '-Map', str(out / 'lunar-app-probe.map'), '-o', str(elf)]
    result = subprocess.run(command, capture_output=True, text=True)
    (out / 'link.log').write_text(result.stdout + result.stderr)
    if result.returncode:
        raise SystemExit(result.stdout + result.stderr)
    objdump = str(tc / 'common/bin/objdump')
    symbols = subprocess.check_output([objdump, '-t', str(elf)], text=True)
    (out / 'symbols.txt').write_text(symbols)
    missing = re.findall(r'^.*\*UND\*[ \t]+00000000[ \t]+(\S+)[ \t]*$', symbols, re.M)
    if missing:
        raise SystemExit('Undefined symbols: ' + repr(missing))
    receipt = out / 'key-audit.json'
    subprocess.run([sys.executable, str(ROOT / 'tools/jieli/audit_link.py'),
                    '--elf', str(elf), '--runtime', 'sdk-free',
                    '--objdump', objdump,
                    '--sources', str(ROOT / 'firmware/native'), '--json', str(receipt)], check=True)
    audit = json.loads(receipt.read_text())
    if not audit['passed'] or audit['n_pending']:
        raise SystemExit('SDK-free audit has failed or pending checks')
    disassembly = subprocess.check_output([objdump, '-d', '-j', '.ram_text', str(elf)], text=True)
    (out / 'ram-text.txt').write_text(disassembly)
    if re.search(r'\bcall\b', disassembly):
        raise SystemExit('RAM flash code contains a call')
    (out / 'sections.txt').write_text(subprocess.check_output([objdump, '-h', str(elf)], text=True))
    report = dict(excluded_engines=args.exclude, module_selection=module_selection, sdk_archives=[],
                  flash_layout=args.flash_layout, app_budget_bytes=app_budget(args.flash_layout),
                  linker_script_sha256=digest(script),
                  compressed_wave_tables=wave_records, indexed_tft=args.indexed_tft,
                  flash_plaits_wavetables=args.flash_plaits_wavetables,
                  shapes_voices=args.shapes_voices,
                  instance_pool_bytes=instance_pool_bytes, target_app_storage=app_storage,
                  catalogue_objects=catalogue_receipts,
                  linked_objects=[dict(path=str(p), sha256=digest(p)) for p in objects],
                  key_audit=audit, undefined_symbols=missing, flash_write_range='empty',
                  boot_ota_cleanup=False, entry_core=0, entry_boot_pointer='0x01c7fe08',
                  probe_return_to_rom_seconds=20, hardware_candidate=False,
                  catalogue_source_freshness_verified=True,
                  installable=False, hardware_tested=False, elf_sha256=digest(elf))
    if content_inputs:
        report['embedded_content'] = dict(
            prepared_sha256=args.expected_profile_sha256,
            source_sha256=hashlib.sha256(generated_content).hexdigest(),
            asset_count=len(content_inputs.packed_content),
            packed_content_bytes=sum(map(len, content_inputs.packed_content)),
            packed_sha256=[hashlib.sha256(p).hexdigest() for p in content_inputs.packed_content],
            sequence_semantics_verified=False, native_playback_verified=False)
    if args.link_set_loader:
        report['set_loader'] = dict(native_link_verified=True, activation_api_link_verified=True, activated=False,
                                   stack_margin_verified=False, hardware_tested=False,
                                   sequence_semantics_verified=False)
    if args.link_project_loader:
        report['project_loader'] = dict(modulation_staging_link_verified=True,
                                       sequence_staging_link_verified=True,
                                       engine_staging_link_verified=True, engine_parameter_link_verified=True, audio_adoption_link_verified=True,
                                       midi_restore_link_verified=True, scalar_restore_link_verified=True, dx7_restore_link_verified=True,
                                       activated=False, stack_margin_verified=False,
                                       timing_verified=False, hardware_tested=False,
                                       sequence_semantics_verified=False)
    if args.startup_set_index is not None:
        report['startup_set'] = dict(index=args.startup_set_index, runtime_hook_linked=True,
                                    staging_reclaimed_before_engine_allocation=True,
                                    runtime_verified=False, stack_margin_verified=False,
                                    hardware_tested=False)
    (out / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    subprocess.run([sys.executable, str(ROOT / 'tools/native/probe_artifact.py'),
                    '--elf', str(elf), '--layout', 'combined',
                    '--flash-layout', args.flash_layout,
                    '--objdump', objdump,
                    '--out', str(out / 'artifact')], check=True)
    print('Audited private probe:', elf, report['elf_sha256'])


if __name__ == '__main__':
    main()
