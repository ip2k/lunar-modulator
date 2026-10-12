"""Focused native persistence/API/arena check, without building DSP engines."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_native_track_names(tmp_path):
    cc = shutil.which('cc')
    if not cc:
        pytest.skip('no C compiler')
    exe = tmp_path / 'seq-track-names'
    sources = ['seq_clip.c', 'seq_engine.c', 'seq_cmd.c', 'seq_persist.c', 'seq_capture.c']
    subprocess.run([cc, '-std=c99', '-Wall', '-Wextra', '-Wpedantic', '-Werror',
                    '-Iengines/include', '-Iengines/seq', '-Iengines/state',
                    'engines/test/seq_track_name_test.c', 'engines/state/state_movy1.c',
                    *[f'engines/seq/{s}' for s in sources], '-lm', '-o', str(exe)],
                   cwd=ROOT, check=True)
    result = subprocess.run([str(exe)], check=True, capture_output=True, text=True)
    assert 'budget 36620/36864 B' in result.stdout
