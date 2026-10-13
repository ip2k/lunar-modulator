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
import sys

from build_probe import check_pins
from compile_catalogue import source_manifest
from compact_font import compact_header, compact_gfx
from prepare_wavetables import prepare

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


def checked_catalogue(root, compressed=False):
    objects, receipts, indices = [], [], set()
    inputs = source_manifest(ROOT)
    expected = json.loads((root / 'shard-00/objects.json').read_text())
    for shard in range(16):
        directory = root / ('shard-%02d' % shard)
        report = json.loads((directory / 'report.json').read_text())
        required = dict(shard=shard, chunks=16, catalogue_objects=len(expected),
                        gpl_mods=1, modules='all', optimization='-Oz', lto=True,
                        shared_resampler=True, closed_sdk_archives=[],
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--catalogue', type=Path, required=True)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--exclude', choices=ENGINE_IDS, action='append', default=[])
    parser.add_argument('--compressed-wavetables', action='store_true',
                        help='Startup decode fixed RAM tables; reduce instance pool accordingly')
    args = parser.parse_args()
    tc, catalogue, out = (p.resolve() for p in
                           (args.toolchain, args.catalogue, args.build))
    if len(set(args.exclude)) != len(args.exclude) or 'trio' in args.exclude:
        parser.error('Exclusions must be unique and retain the initial Trio engine')
    out.mkdir(parents=True, exist_ok=False)
    platform = ROOT / 'firmware/third_party/dinghy'
    for name in ('dinghy', 'compiler-rt', 'musl', 'printf', 'tlsf'):
        check_pins(ROOT / 'firmware/third_party' / name)
    wave_namespaces = (['plaits'] + ([] if 'shapes' in args.exclude else ['braids'])
                       if args.compressed_wavetables else [])
    objects, catalogue_receipts = checked_catalogue(catalogue, wave_namespaces)
    wave_records = []
    if args.compressed_wavetables:
        check_pins(ROOT / 'firmware/third_party/tinf')
        wave_records = prepare(out, wave_namespaces)
    instance_pool_bytes = 192000 - sum(r['raw_bytes'] for r in wave_records)
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
    source = header.read_text()
    for name in args.exclude:
        source = replace_once(source, '#define FM1_WITH_' + name.upper().replace('-', '_') + ' 1',
                              '#define FM1_WITH_' + name.upper().replace('-', '_') + ' 0')
    header.write_text(source)
    compiler = str(tc / 'common/bin/clang')
    flags = ['-target', 'pi32v2', '-mcpu=r3', '-mfprev1', '-Oz', '-flto',
             '-ffreestanding', '-fno-builtin', '-ffunction-sections', '-fdata-sections',
             '-DFM1_APP_EXTERNAL_ARENAS=1', '-DLUNAR_APP_PROBE=1', '-DNDEBUG']
    if args.compressed_wavetables:
        flags += ['-DLUNAR_COMPRESSED_WAVETABLES=1',
                  '-DLUNAR_INSTANCE_MEMORY_BYTES=' + str(instance_pool_bytes)]
    for directory in (gen, ROOT / 'engines/include', ROOT / 'engines/mod',
                      ROOT / 'firmware/native', ROOT / 'firmware/third_party/tlsf',
                      ROOT / 'firmware/third_party/tinf', ROOT / 'engines/third_party/mutable', ROOT / 'engines/host',
                      ROOT / 'engines/state', ROOT / 'sim/web/src', out,
                      platform / 'hal', platform / 'src', platform / 'gen'):
        flags += ['-I', str(directory)]
    flags += ['-isystem', str(tc / 'pi32v2/include')]
    for path in (out / 'crt0.S', platform / 'hal/fm1_vec.S', platform / 'hal/fm1_isr.S'):
        obj = out / (path.stem + '.o')
        subprocess.run([compiler, *[f for f in flags if f != '-flto'], '-c', str(path),
                        '-o', str(obj)], check=True)
        objects.append(obj)
    extra_sources = ([out / ('resources_' + n + '.cc') for n in wave_namespaces] + [
                      ROOT / 'firmware/native/wave_tables.c',
                      ROOT / 'firmware/third_party/tinf/tinflate.c']
                     if args.compressed_wavetables else [])
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
    elf = out / 'lunar-app-probe.elf'
    command = [str(tc / 'pi32v2/bin/ld'), '--plugin', str(tc / 'common/bin/LLVMgold.so'),
               '--plugin-opt=mcpu=r3', '--plugin-opt=-mattr=+fprev1',
               '--plugin-opt=-pi32v2-large-program=true', '--gc-sections',
               '-T', str(ROOT / 'firmware/native/app.ld')]
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
                    '--sources', str(ROOT / 'firmware/native'), '--json', str(receipt)], check=True)
    audit = json.loads(receipt.read_text())
    if not audit['passed'] or audit['n_pending']:
        raise SystemExit('SDK-free audit has failed or pending checks')
    disassembly = subprocess.check_output([objdump, '-d', '-j', '.ram_text', str(elf)], text=True)
    (out / 'ram-text.txt').write_text(disassembly)
    if re.search(r'\bcall\b', disassembly):
        raise SystemExit('RAM flash code contains a call')
    (out / 'sections.txt').write_text(subprocess.check_output([objdump, '-h', str(elf)], text=True))
    report = dict(excluded_engines=args.exclude, sdk_archives=[],
                  compressed_wave_tables=wave_records,
                  instance_pool_bytes=instance_pool_bytes,
                  catalogue_objects=catalogue_receipts,
                  linked_objects=[dict(path=str(p), sha256=digest(p)) for p in objects],
                  key_audit=audit, undefined_symbols=missing, flash_write_range='empty',
                  boot_ota_cleanup=False, entry_core=0, entry_boot_pointer='0x01c7fe08',
                  probe_return_to_rom_seconds=20, hardware_candidate=False,
                  catalogue_source_freshness_verified=True,
                  installable=False, hardware_tested=False, elf_sha256=digest(elf))
    (out / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    subprocess.run([sys.executable, str(ROOT / 'tools/native/probe_artifact.py'),
                    '--elf', str(elf), '--layout', 'combined',
                    '--out', str(out / 'artifact')], check=True)
    print('Audited private probe:', elf, report['elf_sha256'])


if __name__ == '__main__':
    main()
