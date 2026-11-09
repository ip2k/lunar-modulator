"""The FM-1 audio adapter (firmware/fm1/fm1_live.c) on the host, with the
pipelined shared app and a synchronous stand-in for the native pipeline
(tests/fixtures/fm1_live/replay.c). It checks the claims the FM-1 image
rests on: every action the router emits is accepted by the app's pipeline
fence while a block is in flight; the fence itself is live (a direct
fm1_app_key refuses); each consumed result keeps the tag the worker set
(renderer_pipeline_sdk.c worker_step refuses the block otherwise); the
output words are L, R, L, R; nothing sounds before the first note. No SDK,
no IRQ, no timing and no device."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULES = 'dx7,macro,drums,filter,drive,echo,comp,arp,lfo,env,chance'


def build(tmp_path, sanitize):
    cc, cxx = shutil.which('clang'), shutil.which('clang++')
    if not cc or not cxx or not shutil.which('make'):
        pytest.skip('native clang toolchain unavailable')
    out = tmp_path / ('asan' if sanitize else 'plain')
    flags = '-O2 -ffp-contract=off -DFM1_APP_EXTERNAL_ARENAS=1 -DFM1_APP_RENDER_PIPELINE=1'
    if sanitize:
        flags += ' -fsanitize=address,undefined -fno-sanitize=shift -fno-omit-frame-pointer'
    exe = out / 'fm1-live-replay'
    subprocess.run(['make', '-s', '-C', str(ROOT / 'engines'), '-f', 'Makefile',
                    '-f', str(ROOT / 'sim/web/mk/sim.mk'),
                    '-f', str(ROOT / 'tests/fixtures/fm1_live/host.mk'),
                    f'SIM={ROOT / "sim/web"}', f'BUILD={out}', 'FM1_GPL_MODS=0',
                    f'FM1_MODULES={MODULES}', f'CC={cc}', f'CXX={cxx}', f'EXTRA={flags}',
                    '-j4', str(exe)], check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    return exe


@pytest.fixture(scope='module', params=[False, True], ids=['plain', 'asan'])
def replay(request, tmp_path_factory):
    return request.param, build(tmp_path_factory.mktemp('fm1live'), request.param)


def run(exe, mode):
    env = dict(os.environ, ASAN_OPTIONS='halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')
    return subprocess.run([str(exe), mode], env=env, capture_output=True, text=True, timeout=120)


def test_fm1_live_controls_under_the_pipeline_fence(replay):
    _, exe = replay
    result = run(exe, 'delayed')
    assert result.returncode == 0, result.stderr
    fields = dict(item.split('=') for item in result.stdout.split())
    n = {k: float(v) for k, v in fields.items()}
    assert n['blocks'] == n['out'] == 600
    assert n['init_error'] == 0 and n['dx7_voices'] == 8
    # Every scripted event was routed; none lost.
    assert n['pushed'] == n['events'] == 19 and n['dropped'] == 0
    # Applied under the fence: MASTER x2, OCT+, KNOB1, KNOB2, keys on/off (3),
    # MIDI notes on channels 1, 3, 4 and the off for channel 1, and the
    # panic's three note-offs (drums, sound 4, the second key).
    assert n['applied'] == 15
    # Deferred: channel 2 on and off, pitch bend, FX, SELECT.
    assert n['deferred'] == 5
    assert n['ignored'] == 1          # the OCT+ release
    assert n['octave'] == 1
    assert abs(n['cutoff'] - 2400 * 2 ** (3 / 12)) < 0.01
    assert abs(n['resonance'] - 0.15) < 1e-6
    assert n['invalid'] == 0 and n['clipped'] == 0
    assert n['dup_ok'] == 1
    assert n['peak_silent'] == 0      # nothing plays before the first note
    assert n['peak_sound'] > 100      # the notes are heard


def test_fm1_live_fence_is_live(replay):
    """Negative control: the full panel path is refused while a block is in
    flight, so the passing test above is not passing with the fence off."""
    _, exe = replay
    result = run(exe, 'guard')
    assert result.returncode == 72, (result.returncode, result.stderr)
    assert 'pipeline refusal' in result.stderr
