#!/usr/bin/env python3
"""Run the bounded MATRIX oracle. Baseline source is an explicit input, saved
from the reviewed pre-change commit; generated files live in the supplied build.
Run after building fm1-sim-render with the same OPT/EXTRA/compiler flags.
"""
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

root = Path(__file__).resolve().parents[3]
build, baseline = map(lambda s: Path(s).resolve(), sys.argv[1:])
cc = shlex.split(os.environ.get('CC', 'cc'))
cxx = shlex.split(os.environ.get('CXX', 'c++'))
flags = shlex.split(os.environ.get('FLAGS', '-O2'))
incs = [f'-I{root / p}' for p in ('engines/include', 'engines/mod', 'engines/host', 'sim/web/src')]
incs += [f'-I{build / "gen"}']
# Rename functions, leaving public struct/typedef names identical.
src = re.sub(r'\bfm1_mod_ui_\w+(?=\s*\()', lambda m: 'old_' + m[0], baseline.read_text())
old = build / 'mod_ui_before.c'
header = (root / 'sim/web/src/fm1_mod_ui.h').read_text()
header = re.sub(r'\bfm1_mod_ui_\w+(?=\s*\()', lambda m: 'old_' + m[0], header)
(build / 'mod_ui_before.h').write_text(header)
old.write_text(src.replace('#include \"fm1_mod_ui.h\"', '#include \"mod_ui_before.h\"'))
for source, out in [(old, build / 'mod_ui_before.o'),
                    (root / 'sim/web/test/fm1_mod_ui_diff.c', build / 'mod_ui_diff.o')]:
    subprocess.run(cc + ['-std=c99'] + flags + incs + ['-c', str(source), '-o', str(out)], check=True)
# Reuse exactly the native harness's engine/core objects, excluding its main.
objects = [p for p in build.rglob('*.o') if p.name not in
           ('fm1_sim_render.o', 'fm1_edit_check.o', 'render.o', 'mod_ui_before.o', 'mod_ui_diff.o')]
exe = build / 'mod-ui-diff'
subprocess.run(cxx + flags + [str(build / 'mod_ui_before.o'), str(build / 'mod_ui_diff.o')]
               + list(map(str, objects)) + ['-lm', '-o', str(exe)], check=True)
subprocess.run([str(exe)], check=True)
