#!/usr/bin/env python3
"""Task-local adaptation of the retained native app probe; source stays read-only."""
import os
from pathlib import Path
import sys

ROOT = Path('/src')
sys.path.insert(0, str(ROOT / 'tools/native'))
source_path = ROOT / 'tools/native/build_application_probe.py'
text = source_path.read_text()
opt = os.environ.get('LUNAR_OPT')
if opt not in ('s', 'z'):
    raise SystemExit('LUNAR_OPT must be s or z')
runtime = os.environ.get('LUNAR_RUNTIME', 'diagnostic')
if runtime not in ('diagnostic', 'continuous'):
    raise SystemExit('LUNAR_RUNTIME must be diagnostic or continuous')
watermark = os.environ.get('LUNAR_WATERMARK', '1')
if watermark not in ('0', '1'):
    raise SystemExit('LUNAR_WATERMARK must be 0 or 1')
text = text.replace("optimization='-Oz', lto=True,",
                    "optimization='-O' + OPT, lto=True,")
text = text.replace("'-mfprev1', '-Oz', '-flto',",
                    "'-mfprev1', '-O' + OPT, '-flto',")
text = text.replace("'-DFM1_APP_EXTERNAL_ARENAS=1', '-DLUNAR_APP_PROBE=1', '-DNDEBUG',",
                    "'-DFM1_APP_EXTERNAL_ARENAS=1', '-DLUNAR_APP_PROBE=1', '-DLUNAR_PROJECT_SAVE_SERVICE=1', '-DFM1_STATE_BIN_COMPACT_WRITER=1', '-DNDEBUG',")
text = text.replace("ROOT / 'firmware/native/tlsf_runtime.c', ROOT / 'engines/src/registry.cc'",
                    "ROOT / 'firmware/native/tlsf_runtime.c', ROOT / 'tests/native/project_save_app_target.c', ROOT / 'engines/src/registry.cc'")
text = text.replace("'fm1_app_pitch_bend', 'fm1_app_all_notes_off')",
                    "'fm1_app_pitch_bend', 'fm1_app_all_notes_off', 'native_project_save_target',\n             'native_project_save_poll', 'native_project_save_ready')")
expected = 1
for needle in ("optimization='-O' + OPT, lto=True,",
               "'-mfprev1', '-O' + OPT, '-flto',",
               "'-DLUNAR_PROJECT_SAVE_SERVICE=1'",
               "'-DFM1_STATE_BIN_COMPACT_WRITER=1'",
               "ROOT / 'tests/native/project_save_app_target.c'",
               "'native_project_save_target'"):
    if text.count(needle) != expected:
        raise SystemExit('task adaptation drift: ' + needle)
sys.argv = [str(source_path), *sys.argv[1:]]
sys.argv += ['--runtime-mode', runtime]
if watermark == '1':
    sys.argv.append('--stack-watermark')
namespace = {'__name__': '__main__', '__file__': str(source_path), 'OPT': opt}
exec(compile(text, str(source_path), 'exec'), namespace)
