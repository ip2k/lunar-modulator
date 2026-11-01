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
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.jieli.audit_link import Elf, SHF_ALLOC, SHT_NOBITS, audit, collect_sources
MODULES = 'dx7,arp,lfo,env,chance'
TOOLCHAIN_SHA256 = 'f686586bcfb45e0f0bb27fd2b39c7a7f313cb4f0e88a66a14da621ffa8225958'
DEFINES = ['-DFM1_APP_EXTERNAL_ARENAS=1', '-DFM1_SHAPES_VOICES=8',
           '-DNDEBUG', '-D_GNU_SOURCE', '-D_XOPEN_SOURCE=700']

def stream_digest(stream):
    result = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        result.update(chunk)
    return result.hexdigest()

def digest(p):
    with p.open('rb') as stream:
        return stream_digest(stream)

def toolchain_tree(root):
    """Record the actual read-only input tree, including executable/link identity."""
    result = {}
    if not root.is_dir():
        raise ValueError('toolchain must be an extracted directory')
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in sorted(dirs + files):
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                try:
                    target = path.resolve(strict=True)
                except (OSError, RuntimeError) as error:
                    raise ValueError('unresolvable toolchain link: ' + relative) from error
                if not target.is_relative_to(root):
                    raise ValueError('toolchain link escapes tree: ' + relative)
                result[relative] = dict(kind='symlink', target=os.readlink(path))
            elif stat.S_ISDIR(mode):
                result[relative] = dict(kind='directory')
            elif stat.S_ISREG(mode):
                result[relative] = dict(kind='file', bytes=path.stat().st_size,
                                        execute_bits=mode & 0o111, sha256=digest(path))
            else:
                raise ValueError('nonregular toolchain input: ' + relative)
    return result

def bind_toolchain(root, archive):
    """Compare every extracted input with the pinned archive, without extracting it.

    A hash of an unrelated archive is not provenance for --toolchain. Directory,
    file bytes, executable bits and internal symlink identities must all match.
    Inputs must remain read-only throughout the build; a final snapshot detects
    ordinary changes, not a hostile filesystem changing and restoring inputs.
    """
    actual = toolchain_tree(root)
    expected, hardlinks, archive_root = {}, {}, None

    def parts(name):
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or not path.parts:
            raise ValueError('unsafe toolchain archive path: ' + name)
        return path.parts

    try:
        with archive.open('rb') as stream:
            if stream_digest(stream) != TOOLCHAIN_SHA256:
                raise ValueError('toolchain archive differs from pinned source')
            stream.seek(0)
            with tarfile.open(fileobj=stream, mode='r|*') as contents:
                for member in contents:
                    path = parts(member.name)
                    if archive_root is None:
                        archive_root = path[0]
                    if path[0] != archive_root:
                        raise ValueError('toolchain archive has multiple roots')
                    if len(path) == 1:
                        if not member.isdir():
                            raise ValueError('toolchain archive root must be a directory')
                        continue
                    name = '/'.join(path[1:])
                    if name in expected or name in hardlinks:
                        raise ValueError('duplicate toolchain archive member: ' + name)
                    if member.isdir():
                        expected[name] = dict(kind='directory')
                    elif member.isfile() and not member.issparse():
                        with contents.extractfile(member) as data:
                            expected[name] = dict(kind='file', bytes=member.size,
                                execute_bits=member.mode & 0o111, sha256=stream_digest(data))
                    elif member.issym():
                        expected[name] = dict(kind='symlink', target=member.linkname)
                    elif member.islnk():
                        target = parts(member.linkname)
                        if target[0] != archive_root or len(target) < 2:
                            raise ValueError('toolchain hardlink escapes archive root: ' + name)
                        hardlinks[name] = '/'.join(target[1:])
                    else:
                        raise ValueError('unsupported toolchain archive member: ' + name)
            # Recheck this same open file after parsing; no path replacement can
            # substitute the archive between pin validation and member reads.
            stream.seek(0)
            if stream_digest(stream) != TOOLCHAIN_SHA256:
                raise ValueError('toolchain archive changed during verification')
    except (OSError, tarfile.TarError) as error:
        raise ValueError('cannot verify toolchain archive: ' + str(error)) from error
    if not expected and not hardlinks:
        raise ValueError('empty toolchain archive')
    while hardlinks:
        resolved = [name for name, target in hardlinks.items() if target in expected]
        if not resolved:
            raise ValueError('unresolved toolchain hardlink')
        for name in resolved:
            target = expected[hardlinks.pop(name)]
            if target['kind'] != 'file':
                raise ValueError('toolchain hardlink must refer to a regular file: ' + name)
            expected[name] = target.copy()
    # Tar producers may omit directory entries. Reject conflicting ancestors
    # instead of treating an archive path through a symlink as a real directory.
    for name in list(expected):
        for ancestor in PurePosixPath(name).parents:
            if ancestor == PurePosixPath('.'):
                continue
            parent = expected.setdefault(str(ancestor), dict(kind='directory'))
            if parent['kind'] != 'directory':
                raise ValueError('non-directory toolchain archive ancestor: ' + str(ancestor))
    different = sorted(name for name in expected.keys() | actual.keys()
                       if expected.get(name) != actual.get(name))
    if different:
        raise ValueError('toolchain tree differs from pinned archive: ' + ', '.join(different[:8]))
    tree_hash = hashlib.sha256(json.dumps(actual, sort_keys=True,
                                         separators=(',', ':')).encode()).hexdigest()
    return dict(schema=1, archive_sha256=TOOLCHAIN_SHA256,
                archive_root=archive_root, tree_sha256=tree_hash, tree_manifest=actual)

def check_inventory(directory):
    record = json.loads((directory / 'inventory.json').read_text())
    for name, expected in record['files'].items():
        if digest(directory / name) != expected:
            raise ValueError('source pin mismatch: ' + str(directory / name))

def header_manifest(root):
    return {p.relative_to(root).as_posix(): digest(p)
            for p in sorted(root.rglob('*')) if p.is_file()}

def manifest():
    roots = ['engines', 'sim/web/src', 'sim/web/mk', 'sim/web/third_party',
             'firmware/native', 'firmware/third_party/dinghy',
             'firmware/third_party/compiler-rt', 'firmware/third_party/musl',
             'firmware/third_party/printf', 'tools/jieli/objects.mk',
             'tools/native/build_diagnostic.py', 'tools/jieli/audit_link.py']
    result = {}
    for name in roots:
        p = ROOT / name
        paths = [p] if p.is_file() else p.rglob('*')
        for f in sorted(paths):
            if f.is_file() and not any(x.startswith('build') or x == '__pycache__'
                                       for x in f.relative_to(ROOT).parts[:-1]):
                result[str(f.relative_to(ROOT))] = digest(f)
    return result

def build(args):
    tc, out, headers = args.toolchain.resolve(), args.out.resolve(), args.cxx_headers.resolve()
    if out.exists():
        raise ValueError('output must be a fresh directory; preserve reports then remove your old build')
    toolchain_binding = bind_toolchain(tc, args.toolchain_archive)
    original_headers = header_manifest(headers)
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
    configured_headers = header_manifest(configured)
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
    objects.append(objdir / 'c/host/mod_script.o')
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
    units.append([compiler, *flags, '-I', printf.parent.parent, '-DPRINTF_ALIAS_STANDARD_FUNCTION_NAMES_HARD=1',
                  '-DPRINTF_SUPPORT_WRITEBACK_SPECIFIER=0', '-c', printf, '-o', obj])
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        list(pool.map(run, units))
    elf = out / 'lunar-diagnostic.elf'
    run([tc / 'pi32v2/bin/ld', '--gc-sections', '-T', ROOT / 'firmware/native/diagnostic.ld',
         *objects, '-Map', out / 'lunar-diagnostic.map', '-o', elf])
    symbols = run([tc / 'pi32v2/bin/nm', '-S', elf], True)
    (out / 'symbols.txt').write_text(symbols)
    if re.search(r'\bU\s+\S+', symbols): raise ValueError('unresolved target helper')
    forbidden = r'(?:fl_(?:erase|write|prog)\w*|ota_\w*|sdk_\w*|mkey_\w*|putchar_|_putchar|malloc|free|fm1_(?:enter_|reboot|core_reset)\w*)'
    hits = [line for line in symbols.splitlines()
            if line.split() and re.fullmatch(forbidden, line.split()[-1])]
    if hits: raise ValueError('forbidden diagnostic closure symbol: ' + repr(hits))
    listing = run([tc / 'common/bin/objdump', '-d', '-mcpu=r3', '-mattr=+fprev1', elf], True)
    (out / 'listing.txt').write_text(listing)
    image = Elf(elf.read_bytes(), str(elf))
    sections = {s['name']: dict(address=s['addr'], bytes=s['size'])
                for s in image.sections if s['flags'] & SHF_ALLOC}
    def sym(name):
        matches = [s for s in image.symbols if s['name'] == name and s['shndx']]
        if len(matches) != 1: raise ValueError('ambiguous memory symbol: ' + name)
        return dict(address=matches[0]['value'], bytes=matches[0]['size'])
    size = dict(sections=sections, app=sym('app'), arena=sym('sound'),
                descriptors=sym('arenas'), user_stack_bytes=0x5f00,
                supervisor_stack_bytes=0x1f00,
                globals_to_stack_guard_bytes=0x01c74000-image.symbol_value('_bss_end'),
                flash_bytes=sections['.text']['bytes']+sections['.data']['bytes'])
    (out / 'size.json').write_text(json.dumps(size, indent=2) + '\n')
    # This linker contract has contiguous XIP text/data load bytes. Export
    # through the existing ELF reader: vendor objcopy requires a different
    # section-selection CLI from GNU objcopy. Reject unexpected load sections.
    if set(sections) != {'.text', '.data', '.bss', '.noinit'}:
        raise ValueError('unexpected allocated diagnostic section')
    if image.symbol_value('_data_load') != sections['.text']['address'] + sections['.text']['bytes']:
        raise ValueError('noncontiguous diagnostic XIP load image')
    flat = b''.join(image.data[s['offset']:s['offset']+s['size']]
                    for name in ['.text', '.data'] for s in image.sections
                    if s['name'] == name and s['type'] != SHT_NOBITS)
    if len(flat) != size['flash_bytes']: raise ValueError('incomplete XIP image')
    (out / 'app.bin').write_bytes(flat)
    sources = collect_sources([str(ROOT / 'firmware/native'),
                               str(ROOT / 'firmware/third_party/dinghy')])
    link_audit = audit([(str(elf), image)], [('app.bin', flat)], True,
                       sources=sources, runtime='sdk-free')
    (out / 'audit.json').write_text(json.dumps(link_audit, indent=2) + '\n')
    if link_audit['n_fail']: raise ValueError('audit_link failure; see audit.json')
    compiler_version = run([compiler, '--version'], True)
    if manifest() != before: raise ValueError('source inputs changed while building')
    if toolchain_tree(tc) != toolchain_binding['tree_manifest']:
        raise ValueError('toolchain inputs changed while building')
    if header_manifest(headers) != original_headers or header_manifest(configured) != configured_headers:
        raise ValueError('libc++ header inputs changed while building')
    report = dict(profile='sdk-free-single-fm6-diagnostic-v1', hardware_admitted=False,
        release_candidate=False, sdk_archives=[], modules=MODULES.split(','), voices=8,
        dx7_sine='trunc12', shapes_voices=8, external_arenas=True,
        arena_bytes=65536, cpu1=False, usb=False, persistence=False, fail_open=False,
        toolchain_archive_sha256=TOOLCHAIN_SHA256,
        toolchain_binding=toolchain_binding, compiler_version=compiler_version,
        cxx_headers_manifest=original_headers, configured_cxx_headers_manifest=configured_headers,
        source_manifest=before, compile_flags=flags,
        objects=[dict(path=str(p.relative_to(out)), sha256=digest(p)) for p in objects],
        elf_sha256=digest(elf), app_sha256=digest(out / 'app.bin'), sizes=size,
        audit_link=link_audit,
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
