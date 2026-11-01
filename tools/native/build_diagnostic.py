#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build one source-bound SDK-free FM6 diagnostic. Never package/install/run it.

Run in a bounded Linux build container with the pinned JieLi toolchain and
LLVM libc++ headers mounted read-only. No SDK archives/device headers are used.
Every build uses new output storage; no engine object cache is accepted.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
MODULES = 'dx7,arp,lfo,env,chance'
TOOLCHAIN_SHA256 = 'f686586bcfb45e0f0bb27fd2b39c7a7f313cb4f0e88a66a14da621ffa8225958'
DEFINES = ['-DFM1_APP_EXTERNAL_ARENAS=1', '-DFM1_SHAPES_VOICES=8',
           '-DNDEBUG', '-D_GNU_SOURCE', '-D_XOPEN_SOURCE=700']

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def check_inventory(directory):
    record = json.loads((directory / 'inventory.json').read_text())
    for name, expected in record['files'].items():
        if digest(directory / name) != expected:
            raise ValueError('source pin mismatch: ' + str(directory / name))

def manifest():
    roots = ['engines', 'sim/web/src', 'sim/web/mk', 'sim/web/third_party',
             'firmware/native', 'firmware/third_party/dinghy',
             'firmware/third_party/compiler-rt', 'firmware/third_party/musl',
             'firmware/third_party/printf', 'tools/jieli/objects.mk',
             'tools/native/build_diagnostic.py']
    result = {}
    for name in roots:
        p = ROOT / name
        paths = [p] if p.is_file() else p.rglob('*')
        for f in sorted(paths):
            if f.is_file() and not any(x.startswith('build') or x == '__pycache__'
                                       for x in f.relative_to(ROOT).parts):
                result[str(f.relative_to(ROOT))] = digest(f)
    return result

def build(args):
    tc, out, headers = args.toolchain.resolve(), args.out.resolve(), args.cxx_headers.resolve()
    if out.exists():
        raise ValueError('output must be a fresh directory; preserve reports then remove your old build')
    if digest(args.toolchain_archive) != TOOLCHAIN_SHA256:
        raise ValueError('toolchain archive differs from pinned source')
    for name in ['dinghy', 'compiler-rt', 'musl', 'printf']:
        check_inventory(ROOT / 'firmware/third_party' / name)
    before = manifest()
    out.mkdir(parents=True)
    log = (out / 'build.log').open('w')
    def run(command, capture=False):
        p = subprocess.run([str(x) for x in command], text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log.write('$ ' + ' '.join(map(str, command)) + '\n' + p.stdout); log.flush()
        if p.returncode:
            raise RuntimeError('command failed; see ' + str(out / 'build.log') + '\n' + p.stdout[-3000:])
        return p.stdout if capture else None
    configured = out / 'cxx'
    shutil.copytree(headers, configured)
    p = configured / '__config'
    config = p.read_text()
    pthread = '#define _LIBCPP_HAS_THREAD_API_PTHREAD\n'
    if config.count(pthread) != 1:
        raise ValueError('libc++ expected exactly one generated pthread configuration')
    p.chmod(0o600)
    p.write_text(config.replace(pthread, '/* Diagnostic: no thread API. */\n'))
    flags = ['-target', 'pi32v2', '-mcpu=r3', '-mfprev1', '-Oz', '-ffreestanding',
             '-fno-builtin', '-ffunction-sections', '-fdata-sections', *DEFINES,
             '-D_LIBCPP_HAS_NO_THREADS', '-D_LIBCPP_DISABLE_EXTERN_TEMPLATE',
             '-isystem', str(configured), '-isystem', str(tc / 'pi32v2/include')]
    compiler = tc / 'common/bin/clang'
    objdir = out / 'obj'
    make = ['make', '-s', '-C', ROOT / 'engines', '-f', 'Makefile',
            '-f', ROOT / 'sim/web/mk/sim.mk', '-f', ROOT / 'tools/jieli/objects.mk',
            'SIM=' + str(ROOT / 'sim/web'), 'BUILD=' + str(objdir),
            'FM1_GPL_MODS=1', 'FM1_MODULES=' + MODULES, 'FM1_DX7_SINE=trunc12',
            'OPT=-Oz', 'CC=' + str(compiler), 'CXX=' + str(compiler),
            'EXTRA=' + ' '.join(flags)]
    objects = [Path(s) for s in run([*make, 'print-objs'], True).splitlines()
               if not s.endswith('/fm1_web.o')]
    run([*make, '-j' + str(args.jobs), *objects])
    objects.append(objdir / 'our/host/mod_script.o')
    run([*make, objects[-1]])
    includes = [ROOT / 'engines/include', ROOT / 'engines/host', ROOT / 'engines/state',
                ROOT / 'engines/mod', ROOT / 'sim/web/src', ROOT / 'firmware/native',
                ROOT / 'firmware/third_party/dinghy/hal', ROOT / 'firmware/third_party/dinghy/src',
                objdir / 'gen']
    appflags = flags + [x for d in includes for x in ['-I', str(d)]]
    extra = [ROOT / 'firmware/native/diagnostic_app.c',
             ROOT / 'firmware/native/diagnostic_platform.c',
             ROOT / 'firmware/native/diagnostic_crt0.S',
             ROOT / 'firmware/third_party/dinghy/hal/fm1_vec.S',
             ROOT / 'firmware/third_party/dinghy/hal/fm1_isr.S']
    units = []
    for src in extra:
        obj = out / (src.stem + '.o'); objects.append(obj)
        units.append([compiler, *appflags, '-c', src, '-o', obj])
    musl = ROOT / 'firmware/third_party/musl'
    compat = ROOT / 'firmware/native/libc_compat'
    for name in json.loads((musl / 'inventory.json').read_text())['files']:
        if not name.endswith('.c'): continue
        src = musl / name; obj = out / ('musl_' + src.stem + '.o'); objects.append(obj)
        units.append([compiler, *flags, '-Dhidden=__attribute__((visibility("hidden")))',
                      '-D__fpclassify=__fpclassifyd', '-include', compat / 'declarations.h',
                      '-I', compat, '-I', musl / 'src/internal', '-I', musl / 'src/math',
                      '-I', musl / 'arch/generic', '-c', src, '-o', obj])
    rt = ROOT / 'firmware/third_party/compiler-rt'
    for name in json.loads((rt / 'inventory.json').read_text())['files']:
        if not name.endswith('.c'): continue
        src = rt / name; obj = out / ('rt_' + src.stem + '.o'); objects.append(obj)
        units.append([compiler, *flags, '-c', src, '-o', obj])
    printf = ROOT / 'firmware/third_party/printf/printf/printf.c'
    obj = out / 'printf.o'; objects.append(obj)
    units.append([compiler, *flags, '-DPRINTF_ALIAS_STANDARD_FUNCTION_NAMES_HARD=1',
                  '-DPRINTF_SUPPORT_WRITEBACK_SPECIFIER=0', '-c', printf, '-o', obj])
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        list(pool.map(run, units))
    elf = out / 'lunar-diagnostic.elf'
    run([tc / 'pi32v2/bin/ld', '--gc-sections', '-T', ROOT / 'firmware/native/diagnostic.ld',
         *objects, '-Map', out / 'lunar-diagnostic.map', '-o', elf])
    symbols = run([tc / 'pi32v2/bin/nm', '-S', elf], True)
    (out / 'symbols.txt').write_text(symbols)
    if re.search(r'\bU\s+\S+', symbols): raise ValueError('unresolved target helper')
    forbidden = r'\b(?:fl_(?:erase|write|prog)|ota_|sdk_|mkey_|putchar_|malloc|free|fm1_(?:enter_|reboot|core_reset))\w*\b'
    if re.search(forbidden, symbols): raise ValueError('forbidden diagnostic closure symbol')
    listing = run([tc / 'common/bin/objdump', '-d', '-mcpu=r3', '-mattr=+fprev1', elf], True)
    (out / 'listing.txt').write_text(listing)
    size = run([tc / 'pi32v2/bin/size', '-A', elf], True)
    (out / 'size.txt').write_text(size)
    if manifest() != before: raise ValueError('source inputs changed while building')
    report = dict(profile='sdk-free-single-fm6-diagnostic-v1', hardware_admitted=False,
        release_candidate=False, sdk_archives=[], modules=MODULES.split(','), voices=8,
        dx7_sine='trunc12', shapes_voices=8, external_arenas=True,
        arena_bytes=65536, cpu1=False, usb=False, persistence=False, fail_open=False,
        toolchain_archive_sha256=TOOLCHAIN_SHA256,
        compiler_version=run([compiler, '--version'], True),
        cxx_headers_manifest={str(p.relative_to(headers)):digest(p) for p in headers.rglob('*') if p.is_file()},
        source_manifest=before, compile_flags=flags,
        objects=[dict(path=str(p.relative_to(out)), sha256=digest(p)) for p in objects],
        elf_sha256=digest(elf), sizes=size,
        audit_limit='Symbol closure scan is additional evidence, not audit_link admission or a complete MMIO/callgraph audit.')
    (out / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n')
    log.close()
    return report

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--toolchain', type=Path, required=True)
    p.add_argument('--toolchain-archive', type=Path, required=True)
    p.add_argument('--cxx-headers', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--jobs', type=int, choices=range(1,5), default=4)
    args = p.parse_args()
    try: result = build(args)
    except (ValueError, RuntimeError) as e: p.exit(1, str(e) + '\n')
    print(json.dumps({k:v for k,v in result.items() if k in ['profile','hardware_admitted','elf_sha256','sizes']}))
if __name__ == '__main__': main()
