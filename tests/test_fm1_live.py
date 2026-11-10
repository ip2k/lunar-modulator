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


def build(tmp_path, sanitize, full=False, ref=False):
    cc, cxx = shutil.which('clang'), shutil.which('clang++')
    if not cc or not cxx or not shutil.which('make'):
        pytest.skip('native clang toolchain unavailable')
    out = tmp_path / (('ref-' if ref else 'full-' if full else '') + ('asan' if sanitize else 'plain'))
    flags = '-O2 -ffp-contract=off -DFM1_APP_EXTERNAL_ARENAS=1'
    if not ref:
        flags += ' -DFM1_APP_RENDER_PIPELINE=1'
    if full or ref:
        flags += ' -DLUNAR_FM1_FULL_UI=1'
    if ref:
        flags += ' -DREPLAY_REF=1'
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


# ---- the full-UI image (LUNAR_FM1_FULL_UI=1): every control, behind a drain barrier ----

@pytest.fixture(scope='module')
def full_exes(tmp_path_factory):
    base = tmp_path_factory.mktemp('fm1full')
    return (build(base, False, full=True), build(base, True, full=True),
            build(base, False, ref=True))


def state_lines(text):
    return [line for line in text.splitlines() if line.startswith(('t', 'state'))]


def test_full_ui_matches_the_unpipelined_app_at_every_checkpoint(full_exes):
    """The same script of 68 events (all 14 buttons, 5 encoders both ways, SEL
    combos, PLAY/REC, ARP tap and hold, keys, bend, MASTER, panic) goes to the
    pipelined adapter through the drain barrier and to the same arrangement
    with no pipeline. Mode, page, sound, octave, popup, the 41 LEDs, a hash of
    the 240x240 screen and a hash of every PCM word agree at 13 checkpoints."""
    live, _, ref = full_exes
    a = run(live, 'full')
    b = run(ref, 'ref')
    assert a.returncode == 0, a.stderr
    assert b.returncode == 0, b.stderr
    a_lines, b_lines = state_lines(a.stdout), state_lines(b.stdout)
    assert len(a_lines) == len(b_lines) == 13
    assert a_lines == b_lines
    # The screens and PCM actually moved: a differential of constants proves nothing.
    assert len({line.split('screen=')[1].split()[0] for line in a_lines}) >= 8
    assert len({line.split('pcm=')[1].split()[0] for line in a_lines}) == 13
    assert 'popup_lines=0' in a_lines[-1]       # the popup expired after the last event


def test_full_ui_events_wait_for_a_drained_app(full_exes):
    live, asan, _ = full_exes
    for exe in (live, asan):                    # the app's fence would exit 72 otherwise
        result = run(exe, 'full')
        assert result.returncode == 0, result.stderr
        n = {k: int(v) for k, v in (i.split('=') for i in
                                  next(l for l in result.stdout.splitlines()
                                       if l.startswith('pushed=')).split())}
        assert n['pushed'] == n['events'] == n['applied'] == 68
        assert n['barrier_events'] == 67        # all but the MASTER, the fast path
        assert n['barrier_holds'] >= 60         # the producer held back, then drained
        assert n['services'] >= 2               # the popup expiry and the ARP hold ran


def test_full_ui_soft_locks_refuse_swaps_once_blocks_run(full_exes):
    live, _, _ = full_exes
    result = run(live, 'refuse')
    assert result.returncode == 0, result.stderr
    assert 'refused=1' in result.stdout


def test_full_ui_fence_is_still_live(full_exes):
    live, _, _ = full_exes
    result = run(live, 'guard')
    assert result.returncode == 72
    assert 'pipeline refusal' in result.stderr


def test_full_ui_gestures_that_diverge_from_r0_do_not_trip_the_guard(full_exes):
    """PRESETS and ALGORITHM turns, SEL+PRESETS (Macro current), keys on Macro,
    the FX-mode effect swap and pick, and channel-2 MIDI notes, through the
    live adapter and the barrier, plain and under ASan, with 1,400 blocks
    after the popups. A guard trip would exit 72 (a warm-reset loop on the
    device). The engines stay as they were and Macro stays on VA."""
    live, asan, _ = full_exes
    for exe in (live, asan):
        result = run(exe, 'gestures')
        assert result.returncode == 0, result.stderr
        assert 'gestures=1' in result.stdout
        assert 'Effect order' in result.stdout          # the swap was refused, with a popup
        n = {k: int(v) for k, v in (i.split('=') for i in
                                      next(l for l in result.stdout.splitlines()
                                           if l.startswith('pushed=')).split())}
        assert n['pushed'] == n['events'] == n['applied'] == 28 and n['barrier_events'] == 28
        assert 'popup_lines=0' in state_lines(result.stdout)[-1]
