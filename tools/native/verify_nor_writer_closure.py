#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Link an analysis-only full app with the retained bounded NOR writer path.

Creates a temporary source overlay and modifies only the copied probe builder.
It does not produce app.bin or a normal verification receipt.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
# Hypothetical, discontiguous 48 KiB VM/USR slices; not an admitted profile.
EXTENTS = ((0x000D9000, 0x000E5000), (0x000EA000, 0x000F6000))
MACRO = "#define FL_RANGE_OK(off, n) (FL_IN(off, n, 0x000D9000u, 0x000E5000u) || FL_IN(off, n, 0x000EA000u, 0x000F6000u))"
FORCE_FUNCTION = r'''/* Analysis-only link root; never called by startup or exposed as an API. */
__attribute__((used, noinline)) int lunar_nor_closure_analysis_force_retain(void)
{
    uint8_t bytes[16] = {0};
    uint32_t took = 0;
    int erased = fl_erase4k(0x000D9000u, &took);
    int programmed = fl_write(0x000D9000u, bytes, sizeof bytes);
    return erased | programmed;
}

'''


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected one exact anchor, found {count}')
    return text.replace(old, new)


def in_extent(off, size):
    if type(off) is not int or type(size) is not int or off < 0 or size < 0:
        return False
    return any(off >= lo and off <= hi and size <= hi - off for lo, hi in EXTENTS)


def audit_ram_calls(ram_text):
    calls = []
    current_function = None
    seen_functions = set()
    function_instructions = {}
    instruction_count = 0
    for line in ram_text.splitlines():
        match = re.fullmatch(r'([A-Za-z_.$][A-Za-z0-9_.$@-]*):', line)
        if match:
            current_function = match.group(1)
            if current_function in seen_functions:
                raise ValueError(f'duplicate RAM function label: {current_function}')
            seen_functions.add(current_function)
            function_instructions[current_function] = 0
        elif re.match(r'^\s*[0-9a-fA-F]+:', line):
            instruction_count += 1
            if current_function is not None:
                function_instructions[current_function] += 1
            if re.search(r'\bcall\b', line):
                target = re.search(r'<([^<>]+)>', line)
                if current_function is None:
                    raise ValueError('RAM call has no containing function label')
                if not target or not target.group(1).strip():
                    raise ValueError(f'RAM call target is malformed in {current_function}')
                calls.append({'function': current_function, 'instruction': line.strip(),
                              'target': target.group(1).strip()})
        elif re.search(r'\bcall\b', line):
            raise ValueError('malformed RAM call instruction without an address')
    if instruction_count == 0:
        raise ValueError('RAM disassembly contains no instructions')
    required = {'fl_erase4k_ram', 'fl_prog_ram'}
    missing = required - seen_functions
    if missing:
        raise ValueError('RAM disassembly missing writer function(s): ' +
                         ', '.join(sorted(missing)))
    empty_writers = {name for name in required if function_instructions.get(name) == 0}
    if empty_writers:
        raise ValueError('RAM disassembly has empty writer function(s): ' +
                         ', '.join(sorted(empty_writers)))
    writer_calls = [call for call in calls if call['function'] in required]
    return calls, writer_calls


def validate_extents():
    assert EXTENTS == ((0xD9000, 0xE5000), (0xEA000, 0xF6000))
    assert all(lo < hi and lo % 0x1000 == 0 and hi % 0x1000 == 0
               for lo, hi in EXTENTS)
    assert EXTENTS[0][1] <= EXTENTS[1][0]
    assert in_extent(0xD9000, 0x1000) and in_extent(0xD9000, 0xC000)
    assert in_extent(0xEA000, 0xC000)
    assert not in_extent(0xD8FFF, 1)
    assert not in_extent(0xE4FFF, 2)
    assert not in_extent(0xE5000, 1)
    assert not in_extent(0xE8FFF, 2)  # BTIF boundary
    assert not in_extent(0xE9FFF, 2)  # VM/USR gap boundary
    assert not in_extent(0xF5FFF, 2)
    assert not in_extent(0xF6000, 1)
    assert not in_extent(0xFC000, 0x1000)  # settings/globals
    assert not in_extent(0xFF000, 0x1000)  # key_mac
    assert not in_extent(0xFFFFFFFF, 2)


def copy_tracked_source(destination, manifest=None):
    destination.mkdir(parents=True, exist_ok=False)
    if manifest is None:
        try:
            listing = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z'],
                                     check=True, capture_output=True).stdout
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise SystemExit('git ls-files unavailable; supply --tracked-files manifest') from exc
    else:
        listing = Path(manifest).read_bytes()
    tracked = listing.split(b'\0')
    if not tracked or tracked == [b'']:
        raise SystemExit('git ls-files returned no tracked source files')
    for raw_path in tracked:
        if not raw_path:
            continue
        relative = Path(os.fsdecode(raw_path))
        if relative.is_absolute() or '..' in relative.parts:
            raise SystemExit(f'invalid tracked path in manifest: {relative}')
        source = ROOT / relative
        target = destination / relative
        if source.is_symlink():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(os.readlink(source))
        elif source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        else:
            raise SystemExit(f'tracked source file is missing: {relative}')
    if not (destination / 'tools/native/build_application_probe.py').is_file():
        raise SystemExit('tracked source overlay is missing the probe builder')


def patch_builder(builder_path):
    original = builder_path.read_text()
    text = original
    old_macro = "'#define FL_RANGE_OK(off, n) (FL_IN(off, n, FL_OTA_LO, FL_OTA_HI) || FL_IN(off, n, SETTINGS_AT, SETTINGS_AT + 0x1000u))':\n            '#define FL_RANGE_OK(off, n) (0) /* Timed probe: no NOR writes. */',"
    new_macro = "'#define FL_RANGE_OK(off, n) (FL_IN(off, n, FL_OTA_LO, FL_OTA_HI) || FL_IN(off, n, SETTINGS_AT, SETTINGS_AT + 0x1000u))':\n            '" + MACRO + "',"
    text = replace_once(text, old_macro, new_macro, 'bounded NOR range adaptation')
    text = replace_once(text, "    (out / 'platform.c').write_text(source)",
                        "    force_marker = '#include \"fm1_flash.h\"' + chr(10)\n"
                        "    force_source = " + repr(FORCE_FUNCTION) + "\n"
                        "    source = replace_once(source, force_marker, force_marker + force_source)\n"
                        "    (out / 'platform.c').write_text(source)",
                        'analysis root injection point')
    text = replace_once(text,
        "             'fm1_app_pitch_bend', 'fm1_app_all_notes_off')",
        "             'fm1_app_pitch_bend', 'fm1_app_all_notes_off',\n"
        "             'lunar_nor_closure_analysis_force_retain')",
        'analysis linker root')
    text = replace_once(text, "flash_write_range='empty',",
        "flash_write_range='ANALYSIS ONLY: VM 0xD9000..0xE5000; USR 0xEA000..0xF6000',",
        'analysis report marker')
    text = replace_once(text,
        "(out / 'verification.json').write_text(json.dumps(report, indent=2) + '\\n')",
        "(out / 'analysis-only.json').write_text(json.dumps(report, indent=2) + '\\n')",
        'non-receipt output path')
    audit_block = """    try:
        ram_call_audit = audit_ram_call_allowlist(disassembly, symbols)
    except ValueError as exc:
        raise SystemExit('RAM call audit failed: ' + str(exc)) from exc
    (out / 'ram-call-audit.json').write_text(json.dumps(ram_call_audit, indent=2) + '\\n')"""
    capture_code = """    # Analysis only: retain all call evidence without applying the normal allowlist.
    ram_calls = [line for line in disassembly.splitlines() if re.search(r'\\bcall\\b', line)]
    (out / 'ram-call-audit.txt').write_text('\\n'.join(ram_calls) + '\\n')"""
    text = replace_once(text, audit_block, capture_code, 'analysis call audit capture')
    artifact_block = """    subprocess.run([sys.executable, str(ROOT / 'tools/native/probe_artifact.py'),
                    '--elf', str(elf), '--layout', 'combined',
                    '--flash-layout', args.flash_layout,
                    '--objdump', objdump,
                    '--out', str(out / 'artifact')], check=True)
    print('Audited private probe:', elf, report['elf_sha256'])"""
    text = replace_once(text, artifact_block,
        "    print('ANALYSIS ONLY; no package emitted:', elf, report['elf_sha256'])",
        'package suppression')
    builder_path.write_text(text)
    return original, text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--catalogue', type=Path, required=True)
    parser.add_argument('--prepared-profile', type=Path, required=True)
    parser.add_argument('--expected-profile-sha256', required=True)
    parser.add_argument('--build', type=Path, required=True,
                        help='New private output directory; must not already exist')
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--tracked-files', type=Path,
                        help='NUL-delimited git ls-files output created outside a container')
    args = parser.parse_args()
    validate_extents()
    build = args.build.resolve()
    build.mkdir(parents=True, exist_ok=False)
    overlay = build / 'source'
    copy_tracked_source(overlay, args.tracked_files)
    # The assigned base intentionally includes the ICFG-preservation fix in a
    # vendored file. Refresh only that copied pin so the builder still checks
    # every other vendored file against the original inventory.
    inventory = overlay / 'firmware/third_party/dinghy/inventory.json'
    vendor = overlay / 'firmware/third_party/dinghy/hal/fm1_flash.h'
    inventory_data = json.loads(inventory.read_text())
    expected_vendor = inventory_data['files']['hal/fm1_flash.h']
    current_vendor = sha256(vendor)
    if current_vendor == expected_vendor:
        raise SystemExit('expected assigned ICFG source delta, but pin is already current')
    inventory_data['files']['hal/fm1_flash.h'] = current_vendor
    inventory.write_text(json.dumps(inventory_data, indent=2) + '\n')
    (build / 'inventory-overlay.json').write_text(json.dumps({
        'analysis_only': True, 'path': 'firmware/third_party/dinghy/hal/fm1_flash.h',
        'base_inventory_sha256': sha256(ROOT / 'firmware/third_party/dinghy/inventory.json'),
        'base_pinned_sha256': expected_vendor, 'current_source_sha256': current_vendor,
        'overlay_inventory_sha256': sha256(inventory),
    }, indent=2) + '\n')
    builder = overlay / 'tools/native/build_application_probe.py'
    builder_before, builder_after = patch_builder(builder)
    (build / 'builder-overlay.diff').write_text(''.join(difflib.unified_diff(
        builder_before.splitlines(keepends=True), builder_after.splitlines(keepends=True),
        fromfile='build_application_probe.py (base)', tofile='build_application_probe.py (analysis overlay)')))
    command = [sys.executable, str(builder), '--toolchain', str(args.toolchain.resolve()),
               '--catalogue', str(args.catalogue.resolve()), '--build', str(build / 'linked'),
               '--runtime-mode', 'song-diagnostic', '--stack-watermark',
               '--flash-layout', 'expanded-d7000', '--prepared-profile',
               str(args.prepared_profile.resolve()), '--expected-profile-sha256',
               args.expected_profile_sha256, '--link-project-loader',
               '--link-project-save-service', '--startup-project-index', '0',
               '--shapes-voices', '8', '--indexed-tft', '--compressed-wavetables']
    result = subprocess.run(command, text=True, capture_output=True)
    (build / 'builder.stdout').write_text(result.stdout)
    (build / 'builder.stderr').write_text(result.stderr)
    if result.returncode:
        raise SystemExit('analysis target build failed; see builder.stdout/stderr')
    linked = build / 'linked'
    objdump = args.toolchain.resolve() / 'common/bin/objdump'
    for name, options in (('full-disassembly.txt', ['-d', '-mcpu=r3']),
                          ('linked-relocations.txt', ['-r'])):
        completed = subprocess.run([str(objdump), *options, str(linked / 'lunar-app-probe.elf')],
                                   check=True, capture_output=True, text=True)
        (linked / name).write_text(completed.stdout + completed.stderr)
    # Attribute every call instruction in the final .ram_text disassembly to
    # its containing function. The only expected call may be a separate RAM
    # compatibility wrapper; erase/program entry paths must have no outcalls.
    ram_text = (linked / 'ram-text.txt').read_text()
    calls, writer_calls = audit_ram_calls(ram_text)
    if writer_calls:
        raise SystemExit('writer entry has RAM call; inspect closure audit')
    (linked / 'ram-closure-audit.json').write_text(json.dumps({
        'analysis_only': True, 'writer_entries': ['fl_erase4k_ram', 'fl_prog_ram'],
        'writer_entry_calls': writer_calls, 'all_ram_calls': calls,
        'relocations': (linked / 'linked-relocations.txt').read_text(),
    }, indent=2) + '\n')
    generated = linked / 'platform.c'
    base_platform = ROOT / 'firmware/third_party/dinghy/src/platform.c'
    (build / 'platform-analysis.diff').write_text(''.join(difflib.unified_diff(
        base_platform.read_text().splitlines(keepends=True), generated.read_text().splitlines(keepends=True),
        fromfile='platform.c (base)', tofile='platform.c (analysis generated)')))
    report = json.loads((linked / 'analysis-only.json').read_text())
    manifest = {
        'analysis_only': True, 'installable': False, 'physical_writes_performed': False,
        'packaging_invoked': False, 'source_commit': args.source_commit,
        'source_platform_sha256': sha256(base_platform),
        'generated_platform_sha256': sha256(generated),
        'builder_overlay_sha256': sha256(builder),
        'toolchain_clang': str(args.toolchain.resolve() / 'common/bin/clang'),
        'catalogue_shards': 16, 'prepared_profile_sha256': args.expected_profile_sha256,
        'extents': [{'start': lo, 'end_exclusive': hi, 'bytes': hi-lo} for lo, hi in EXTENTS],
        'root': 'lunar_nor_closure_analysis_force_retain', 'build_command': command,
        'linked_elf_sha256': sha256(linked / 'lunar-app-probe.elf'),
        'map_sha256': sha256(linked / 'lunar-app-probe.map'),
        'ram_disassembly_sha256': sha256(linked / 'ram-text.txt'),
        'ram_sections_report': (linked / 'sections.txt').read_text(),
        'save_service': report.get('project_save_service'),
    }
    (build / 'analysis-inputs.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Analysis-only full application linked:', linked / 'lunar-app-probe.elf')
    print('No app.bin or ordinary verification receipt was emitted.')


if __name__ == '__main__':
    main()
