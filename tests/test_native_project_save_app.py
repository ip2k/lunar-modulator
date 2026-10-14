"""Actual app -> compact framebuffer writer -> two NOR slots -> app reload.

Host scheduling is synchronous; physical storage admission and device RAM fit
remain separate gates. The pinned target compilation covers the adapter ABI.
"""
import os
from pathlib import Path
import subprocess
import pytest
from tests import state_canon as canon
from tests.test_sim_web import tools  # noqa: F401
from tests.test_app_state import sim, EX, DX7
from tools import lunar_state as ls

ROOT = Path(__file__).resolve().parents[1]
ENGINES = ('macro', 'shapes', 'macro-heavy', 'sixop', 'dx7', 'sw-sophie',
           'drums', 'acid-bass', 'comet', 'crater', 'drawbar', 'trio', 'phase-bend')
CASES = [(engine, variant) for engine in ENGINES for variant in range(2)] + [
    ('first-orbit', 0), ('first-orbit', 1), ('dx7-user', 0), ('default-chain', 0)]

@pytest.fixture(scope='session')
def target_adapter(tmp_path_factory):
    assert 'FM1_STATE_BIN_COMPACT_WRITER' in os.environ.get('FM1_SIM_EXTRA', '')
    assert 'FM1_TFT_INDEXED=1' in os.environ.get('FM1_SIM_EXTRA', '')
    tc = Path(os.environ['FM1_NATIVE_TOOLCHAIN'])
    output = tmp_path_factory.mktemp('native-app-adapter')/'adapter.o'
    subprocess.run([str(tc/'pi32v2/bin/clang'), '-target', 'pi32v2', '-mcpu=r3',
        '-mfprev1', '-Oz', '-std=c99', '-Wall', '-Wextra', '-Werror',
        '-DFM1_TFT_INDEXED=1', '-DFM1_STATE_BIN_COMPACT_WRITER',
        *['-I'+str(ROOT/p) for p in ('firmware/native','engines/include',
            'engines/mod','engines/state','sim/web/src')], '-isystem',
        str(tc/'pi32v2/include'), '-c', str(ROOT/'tests/native/project_save_app_target.c'),
        '-o', str(output)], check=True)

@pytest.mark.parametrize('engine,variant', CASES)
def test_native_project_save_app(tools, target_adapter, engine, variant, tmp_path):
    if engine == 'first-orbit':
        start = ['--load', EX/'first-orbit.lunar']
    elif engine == 'dx7-user':
        start = ['--engine','dx7','--sysex',DX7,'--param','Patch=34']
    elif engine == 'default-chain':
        start = ['--start']
    else:
        start = ['--engine',engine]
    if variant:
        # The extra unit tests per-sound records and level alongside the engine.
        start += ['--sound','1:trio','--level','1:67']
    original, saved, restored = [tmp_path/n for n in
        ('original.lunar','project.native-save.lunarb','restored.lunar')]
    # Both saves share one actual app instance; the second borrows its pixels.
    sim(tools, *start, '--save', f'project:{original}', '--save', f'project:{saved}')
    sim(tools, '--load', saved, '--save', f'project:{restored}')
    expected, actual = canon.loads(original.read_text()), canon.loads(restored.read_text())
    assert expected['made']['by'] == 'simulator'
    # Re-export is a new simulator save, so its producer is the simulator.
    # Verify native provenance in the stored binary with the independent reader.
    binary = saved.read_bytes()
    records, _ = ls.read_bin(binary)
    assert binary[24] == 2  # FM1_STATE_WRITER_FIRMWARE
    assert [r['text'] for r in records
            if r['rec'] == 'info' and r['key'] == 'by'] == ['firmware']
    assert actual['made']['by'] == 'simulator'
    assert actual == expected
    assert saved.stat().st_size <= 98304
