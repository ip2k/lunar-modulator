"""Constant-scratch export matches buffered text and stops after any sink failure."""
import os
from pathlib import Path
import subprocess
import pytest
from tests.native_test_toolchain import configured_target_toolchain

ROOT = Path(__file__).resolve().parents[1]
INPUTS = [ROOT / 'tests/fixtures/state/1.0/orbit.set.movy1'] + sorted(
    (ROOT / 'tests/fixtures/movy').glob('*.out.movy1'))[:14]

@pytest.fixture(scope='session')
def stream_probe(tmp_path_factory):
    tmp = tmp_path_factory.mktemp('seq-export-stream')
    exe = tmp / 'probe'
    sources = [ROOT / 'tests/native/seq_export_stream.c'] + [
        ROOT / 'engines/seq' / (name + '.c') for name in
        ('seq_clip', 'seq_engine', 'seq_cmd', 'seq_persist', 'seq_capture')] + [
        ROOT / 'engines/state' / name for name in
        ('state_bin.c', 'state_names.c', 'state_movy1.c', 'fm1_num.c', 'fm1_deflate.c')]
    subprocess.run(['cc', '-DFM1_STATE_BIN_COMPACT_WRITER', '-std=c99', '-Oz', '-Wall', '-Wextra', '-Werror',
                    '-ffunction-sections', '-fdata-sections', '-fsanitize=address,undefined',
                    '-fno-pie', '-no-pie', '-I', str(ROOT / 'engines/include'), '-I', str(ROOT / 'engines/state'),
                    *map(str, sources), '-Wl,--gc-sections', '-lm', '-o', str(exe)], check=True)
    return exe

def test_seq_export_target_compile(tmp_path):
    tc = configured_target_toolchain()
    common = [str(tc / 'pi32v2/bin/clang'), '-target', 'pi32v2', '-mcpu=r3',
              '-mfprev1', '-Oz', '-std=c99', '-Wall', '-Wextra', '-Werror',
              '-ffreestanding', '-fno-builtin', '-I', str(ROOT / 'engines/include'),
              '-I', str(ROOT / 'engines/state'), '-isystem', str(tc / 'pi32v2/include'), '-c']
    for source, output in [('engines/seq/seq_persist.c', 'seq_persist.o'),
                           ('tests/native/seq_record_target.c', 'seq_record.o')]:
        subprocess.run([*common, str(ROOT / source), '-o', str(tmp_path / output)],
                       check=True, capture_output=True)


@pytest.mark.parametrize('records', [0, 1])
@pytest.mark.parametrize('case', range(16))
@pytest.mark.parametrize('compat', [0, 1])
def test_stream_export(stream_probe, case, compat, records, tmp_path):
    if case < 15:
        subprocess.run([str(stream_probe), str(INPUTS[case]), str(compat), '0', str(records)], check=True)
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
    subprocess.run([str(stream_probe), str(dense), str(compat), '1', str(records)], check=True)
