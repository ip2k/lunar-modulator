"""Constant-scratch export matches buffered text and stops after any sink failure."""
import os
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
INPUTS = [ROOT / 'tests/fixtures/state/1.0/orbit.set.movy1'] + sorted(
    (ROOT / 'tests/fixtures/movy').glob('*.out.movy1'))[:14]

@pytest.fixture(scope='session')
def stream_probe(tmp_path_factory):
    tmp = tmp_path_factory.mktemp('seq-export-stream')
    exe = tmp / 'probe'
    sources = [ROOT / 'tests/native/seq_export_stream.c'] + [
        ROOT / 'engines/seq' / (name + '.c') for name in
        ('seq_clip', 'seq_engine', 'seq_cmd', 'seq_persist', 'seq_capture')]
    subprocess.run(['cc', '-std=c99', '-Oz', '-Wall', '-Wextra', '-Werror',
                    '-ffunction-sections', '-fdata-sections', '-fsanitize=address,undefined',
                    '-fno-pie', '-no-pie', '-I', str(ROOT / 'engines/include'),
                    *map(str, sources), '-Wl,--gc-sections', '-lm', '-o', str(exe)], check=True)
    tc = Path(os.environ['FM1_NATIVE_TOOLCHAIN'])
    subprocess.run([str(tc / 'pi32v2/bin/clang'), '-target', 'pi32v2', '-mcpu=r3',
                    '-mfprev1', '-Oz', '-std=c99', '-Wall', '-Wextra', '-Werror',
                    '-ffreestanding', '-fno-builtin', '-I', str(ROOT / 'engines/include'),
                    '-isystem', str(tc / 'pi32v2/include'), '-c',
                    str(ROOT / 'engines/seq/seq_persist.c'), '-o', str(tmp / 'seq_persist.o')],
                   check=True)
    return exe

@pytest.mark.parametrize('case', range(16))
@pytest.mark.parametrize('compat', [0, 1])
def test_stream_export(stream_probe, case, compat, tmp_path):
    if case < 15:
        subprocess.run([str(stream_probe), str(INPUTS[case]), str(compat)], check=True)
        return
    # Fill the eight-track default pools with long numeric fields. This exercises
    # a large whole-set export without requiring exporter scratch; sample faults to keep it bounded.
    lines = ['movy1', 'bpm 30000', 'swing 99', 'link 1']
    for track in range(8):
        notes = ';'.join(f'{i * 24}:65535:127:127:{i}' for i in range(192))
        locks = ';'.join(f'{i % 8}:{i // 8}:127' for i in range(192))
        trigs = ';'.join(f'{i}:-1:127:255:255:1' for i in range(32))
        lines += [f'tk {track} 0 0', f'cl {track} 0 256 0 {notes}',
                  f'cp {track} 0 24 1 -127 100', f'lk {track} 0 {locks}',
                  f'tg {track} 0 {trigs}']
    dense = tmp_path / 'dense.movy1'
    dense.write_text('\n'.join(lines) + '\n')
    subprocess.run([str(stream_probe), str(dense), str(compat), 'sample-faults'], check=True)
