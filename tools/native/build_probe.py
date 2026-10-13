#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build a non-installable native Trio integration probe, without SDK archives."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def check_pins(directory):
    manifest = json.loads((directory / 'inventory.json').read_text())
    for name, expected in manifest['files'].items():
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != expected:
            raise SystemExit('Source pin mismatch: ' + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--build', type=Path, required=True)
    args = parser.parse_args()
    tc, out = args.toolchain.resolve(), args.build.resolve()
    platform = ROOT / 'firmware/third_party/dinghy'
    check_pins(platform)
    check_pins(ROOT / 'firmware/third_party/compiler-rt')
    out.mkdir(parents=True, exist_ok=True)
    # This copy shadows only platform.c. All included HAL sources remain pinned.
    source = (platform / 'src/platform.c').read_text()
    cleanup = '    ota_boot_cleanup();'
    range_line = '#define FL_RANGE_OK(off, n) (FL_IN(off, n, FL_OTA_LO, FL_OTA_HI) || FL_IN(off, n, SETTINGS_AT, SETTINGS_AT + 0x1000u))'
    if source.count(cleanup) != 1 or source.count(range_line) != 1:
        raise SystemExit('Upstream probe adaptation no longer matches')
    source = source.replace(cleanup, '    /* Probe: retain stock OTA staging bytes. */')
    source = source.replace(range_line, '#define FL_RANGE_OK(off, n) (0) /* Probe: no NOR writes. */')
    (out / 'platform.c').write_text(source)
    flags = ['-target', 'pi32v2', '-mcpu=r3', '-mfprev1', '-Os', '-ffreestanding',
             '-fno-builtin', '-ffunction-sections', '-fdata-sections']
    includes = [out, ROOT / 'firmware/native', platform / 'hal', platform / 'src',
                platform / 'gen', ROOT / 'engines/include',
                tc / 'pi32v2/include']
    extra = flags + ['-D_GNU_SOURCE', '-D_XOPEN_SOURCE=700', '-DFM1_FREESTANDING=1',
                     '-I' + str(tc / 'pi32v2/include')]
    engine_build = out / 'engines'
    engine_objects = [engine_build / 'our/src/felucca_shim.o',
                      engine_build / 'gpl/felucca/felucca_bridge.o']
    compiler = str(tc / 'common/bin/clang')
    subprocess.run(['make', '-C', str(ROOT / 'engines'), '-j16',
                    'BUILD=' + str(engine_build), 'FM1_GPL_MODS=1', 'FM1_MODULES=trio',
                    'OPT=-Os', 'CC=' + compiler + ' -target pi32v2 -mcpu=r3 -mfprev1',
                    'CXX=' + compiler + ' -target pi32v2 -mcpu=r3 -mfprev1',
                    'EXTRA=' + ' '.join(extra), *map(str, engine_objects)], check=True)
    runtime = out / 'arithmetic'
    subprocess.run(['make', '-C', str(ROOT / 'tools/native'), '-j16',
                    'BUILD=' + str(runtime), 'JIELI_TOOLCHAIN=' + str(tc)], check=True)
    objects = []
    for path in [platform / 'crt0.S', platform / 'hal/fm1_vec.S',
                 platform / 'hal/fm1_isr.S', ROOT / 'firmware/native/engine_probe.c',
                 ROOT / 'firmware/native/engine_adapter.c']:
        obj = out / (path.stem + '.o')
        subprocess.run([compiler, *flags, *['-I' + str(p) for p in includes],
                        '-c', str(path), '-o', str(obj)], check=True)
        objects.append(obj)
    objects += engine_objects
    objects += [p for p in sorted(runtime.glob('*.o'))
                if p.name not in ('arithmetic-probe.o', 'arithmetic-linked.o')]
    elf = out / 'lunar-probe.elf'
    subprocess.run([str(tc / 'pi32v2/bin/ld'), '--gc-sections', '-e', '_start',
                    '-T', str(platform / 'app.ld'), *map(str, objects),
                    '-Map', str(out / 'lunar-probe.map'), '-o', str(elf)], check=True)
    symbols = subprocess.check_output([str(tc / 'common/bin/objdump'), '-t', str(elf)], text=True)
    (out / 'symbols.txt').write_text(symbols)
    missing = re.findall(r'^.*\*UND\*[ \t]+00000000[ \t]+(\S+)[ \t]*$', symbols, re.M)
    if missing:
        raise SystemExit('Undefined symbols: ' + repr(missing))
    key_receipt = out / 'key-audit.json'
    subprocess.run([sys.executable, str(ROOT / 'tools/jieli/audit_link.py'),
                    '--elf', str(elf), '--runtime', 'sdk-free',
                    '--sources', str(ROOT / 'firmware/native'),
                    '--json', str(key_receipt)], check=True)
    key_audit = json.loads(key_receipt.read_text())
    if not key_audit['passed'] or key_audit['n_pending']:
        raise SystemExit('SDK-free key audit must pass without pending checks')
    ram_dis = subprocess.check_output([str(tc / 'common/bin/objdump'), '-d', '-j', '.ram_text', str(elf)], text=True)
    (out / 'ram-text.txt').write_text(ram_dis)
    if re.search(r'\bcall\b', ram_dis):
        raise SystemExit('RAM flash code contains a call')
    sections = subprocess.check_output([str(tc / 'common/bin/objdump'), '-h', str(elf)], text=True)
    (out / 'sections.txt').write_text(sections)
    report = {'sdk_archives': [], 'undefined_symbols': missing,
              'key_audit': key_audit,
              'flash_write_range': 'empty', 'boot_ota_cleanup': False,
              'standard_headers': str(tc / 'pi32v2/include'), 'sdk_source_headers': [],
              'installable': False,
              'hardware_tested': False, 'elf_sha256': hashlib.sha256(elf.read_bytes()).hexdigest()}
    (out / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
