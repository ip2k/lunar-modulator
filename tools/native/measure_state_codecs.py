#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Measure codec translation units on pi32v2 in sixteen independent chunks.

Reports fixed entry-frame reservations, not a complete stack high-water mark.
Callback frames, nested calls, interrupts and dynamic reservations require
separate analysis. Does not link firmware, allocate device memory or access USB.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ('state_bin', 'fm1_deflate', 'state_movy1', 'fm1_num',
           'state_names', 'fm1_json', 'state_json_read', 'state_json_write')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def entry_frames(assembly):
    """Recognize the pinned compiler's fixed register-save/SP entry sequence.

    Preserve the sequence for inspection. A function with a different entry
    sequence is marked unmeasured rather than assigned a zero-byte frame.
    Positive or computed SP changes are not accepted as fixed reservations.
    """
    functions = {}
    for match in re.finditer(r'^([A-Za-z_][\w.$]*):\s*; @[^\n]+\n(.*?)(?=^\.Lfunc_end|\Z)',
                             assembly, re.M | re.S):
        name, body = match.groups()
        instructions = [s.strip() for s in body.splitlines()
                        if s.strip() and not s.lstrip().startswith((';', '.'))]
        saved = reserved = 0
        prologue = []
        for line in instructions:
            if line.startswith('[--sp] = {'):
                regs = re.fullmatch(r'\[--sp\] = \{([^}]+)\}', line)
                if not regs:
                    break
                count = 0
                for reg in regs[1].split(','):
                    reg = reg.strip()
                    span = re.fullmatch(r'r(\d+)-r(\d+)', reg)
                    if span:
                        count += abs(int(span[1]) - int(span[2])) + 1
                    elif re.fullmatch(r'r\d+|rets', reg):
                        count += 1
                    else:
                        count = None
                        break
                if count is None:
                    break
                saved += 4 * count
                prologue.append(line)
            elif re.fullmatch(r'sp \+= -\d+', line):
                reserved += -int(line.split('+=')[1])
                prologue.append(line)
            else:
                break
        functions[name] = dict(
            fixed_entry_bytes=saved + reserved if prologue else None,
            register_save_bytes=saved if prologue else None,
            local_reservation_bytes=reserved if prologue else None,
            prologue=prologue,
            calls=sorted(set(re.findall(r'^\s*call\s+(\S+)', body, re.M))),
            complete_call_chain_verified=False)
        # Target-ABI workspace queries are leaf functions reduced to constants.
        constant = re.fullmatch(r'r0 = (\d+)\s+rts', ' '.join(instructions))
        if name.endswith('_writer_size') and constant:
            functions[name]['workspace_bytes'] = int(constant[1])
    if not functions:
        raise ValueError('No pinned-toolchain assembly function entries recognized')
    return functions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--shard', type=int, choices=range(16), required=True)
    args = parser.parse_args()
    tc = args.toolchain.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = ROOT / 'engines/state' / (SOURCES[args.shard % 8] + '.c')
    optimization = ('-Os', '-Oz')[args.shard // 8]
    # Include every local header which may change the codec ABI or constants.
    inputs = sorted(set([source, Path(__file__).resolve(),
                         *(ROOT / 'engines/state').glob('*.h'),
                         *(ROOT / 'engines/include').glob('*.h')]))
    manifest = {str(p.relative_to(ROOT)): digest(p) for p in inputs}
    compiler = tc / 'common/bin/clang'
    flags = ['-target', 'pi32v2', '-mcpu=r3', '-mfprev1', optimization,
             '-std=c99', '-ffreestanding', '-fno-builtin',
             '-ffunction-sections', '-fdata-sections', '-ffp-contract=off',
             '-I', str(ROOT / 'engines/include'),
             '-isystem', str(tc / 'pi32v2/include')]
    asm, obj = out / 'codec.s', out / 'codec.o'
    for mode, output in (('-S', asm), ('-c', obj)):
        subprocess.run([str(compiler), *flags, mode, str(source), '-o', str(output)],
                       check=True, capture_output=True, text=True)
    functions = entry_frames(asm.read_text())
    if source.stem == 'state_bin' and not functions.get('fm1_state_bin_read', {}).get('prologue'):
        raise SystemExit('Binary reader entry frame could not be measured')
    symbols = subprocess.check_output([str(tc / 'pi32v2/bin/nm'), '-u', str(obj)], text=True)
    sizes = subprocess.check_output([str(tc / 'common/bin/objdump'), '-h', str(obj)], text=True)
    (out / 'undefined.txt').write_text(symbols)
    (out / 'sections.txt').write_text(sizes)
    if manifest != {str(p.relative_to(ROOT)): digest(p) for p in inputs}:
        raise SystemExit('Codec inputs changed during compilation')
    report = dict(shard=args.shard, chunks=16, source=str(source.relative_to(ROOT)),
                  optimization=optimization, flags=flags, source_manifest=manifest,
                  compiler_sha256=digest(compiler), assembly_sha256=digest(asm),
                  object_sha256=digest(obj), functions=functions,
                  undefined_symbols=symbols.splitlines(),
                  linked_firmware=False, device_access=False,
                  complete_call_chain_verified=False, runtime_stack_verified=False)
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(shard=args.shard, source=report['source'],
                          optimization=optimization, functions=len(functions))))


if __name__ == '__main__':
    main()
