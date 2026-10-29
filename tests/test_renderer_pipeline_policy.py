"""cap8 policy and worst-block stage marks on the host replay; no target timing claim."""
# Keep the ASan leak-detection default: enabled on Linux, unsupported on macOS.
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import pytest
ROOT = Path(__file__).resolve().parents[1]
MODULES = 'dx7,macro,drums,filter,drive,echo,comp,arp,lfo,env,chance'
CASE_BYTES = 5513 * 256 * 2   # one eight-second case of int16 4-channel PCM
TOTAL_BYTES = 22581248        # 44,104 blocks: two four-case cycles


def build(tmp_path, name, flags, sanitize):
    cc = shutil.which('clang'); cxx = shutil.which('clang++')
    dev = tmp_path/('devkit-' + name)
    shutil.copytree(ROOT/'firmware/devkit', dev)
    live = dev/'renderer_live.c'
    live.write_text(live.read_text() + '\n' + (ROOT/'tests/fixtures/renderer_pipeline/live_replay.c').read_text())
    (dev/'renderer_pipeline_sdk.c').write_text('/* hooks supplied by live replay */\n')
    (dev/'renderer_reference.c').write_text('/* main supplied by live_replay.c */\n')
    out = tmp_path/name
    extra = '-O2 -ffp-contract=off -DFM1_APP_EXTERNAL_ARENAS=1 ' + flags
    if sanitize:
        extra += ' -fsanitize=address,undefined -fno-sanitize=shift -fno-omit-frame-pointer'
    exe = out/'fm1-devkit-renderer-ref'
    subprocess.run(['make', '-s', '-C', str(ROOT/'engines'), '-f', 'Makefile', '-f',
                    str(ROOT/'sim/web/mk/sim.mk'), '-f', str(ROOT/'tools/jieli/renderer.mk'),
                    f'DEVKIT={dev}', f'SIM={ROOT / "sim/web"}', f'BUILD={out}',
                    'FM1_GPL_MODS=0', f'FM1_MODULES={MODULES}', f'CC={cc}', f'CXX={cxx}',
                    f'EXTRA={extra}', '-j4', str(exe)], check=True, stdout=subprocess.DEVNULL)
    return exe


def run(exe, tmp_path, mode):
    env = dict(os.environ, ASAN_OPTIONS='halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1')
    pcm = tmp_path/(mode + '.pcm')
    result = subprocess.run([str(exe), str(pcm), mode], check=True, env=env, timeout=120,
                            capture_output=True, text=True)
    data = pcm.read_bytes(); pcm.unlink()
    assert len(data) == TOTAL_BYTES
    cases = [hashlib.sha256(data[i:i + CASE_BYTES]).hexdigest() for i in range(0, len(data), CASE_BYTES)]
    return hashlib.sha256(data).hexdigest(), cases, result.stdout, result.stderr


@pytest.mark.parametrize('sanitize', [False, True])
def test_cap8_replays_exactly_and_marks_do_not_change_pcm(tmp_path, sanitize):
    if not shutil.which('clang') or not shutil.which('clang++') or not shutil.which('make'):
        pytest.skip('native clang toolchain unavailable')
    pipe = '-DFM1_APP_RENDER_PIPELINE=1 -DLUNAR_DEVKIT_RENDERER_PIPELINE=1'
    cap8 = '-DLUNAR_RENDERER_POLICY_CAP8=1'
    marks = '-DFM1_APP_PIPELINE_MARKS=1'
    fixed_serial = run(build(tmp_path, 'fixed12-serial', '', sanitize), tmp_path, 'baseline')
    fixed_marked = build(tmp_path, 'fixed12-marked', pipe + ' ' + marks, sanitize)
    cap8_serial = run(build(tmp_path, 'cap8-serial', cap8, sanitize), tmp_path, 'baseline')
    cap8_pipe = build(tmp_path, 'cap8-marked', ' '.join((pipe, cap8, marks)), sanitize)
    # Marks are timer reads only: the fixed12 pipeline with marks stays exact.
    for mode in ('immediate', 'delayed'):
        whole, _, report, err = run(fixed_marked, tmp_path, mode)
        assert whole == fixed_serial[0] and report == fixed_serial[2]
        assert 'marks_blocks=44104' in err and 'policy_voices=12 ' in err and 'stolen=0' in err
    # cap8: serial and pipelined replay agree sample for sample.
    for mode in ('immediate', 'delayed'):
        whole, cases, report, err = run(cap8_pipe, tmp_path, mode)
        assert whole == cap8_serial[0] and report == cap8_serial[2]
        assert 'marks_blocks=44104' in err
        stats = dict(re.findall(r'(\w+)=(\d+)', err))
        assert stats['policy_voices'] == '8' and stats['limit'] == '8'
        assert int(stats['stolen']) + int(stats['retired']) > 0
    # Above eight voices the cap changes audio; it must not be silent fixed12.
    assert cap8_serial[0] != fixed_serial[0]
    # Host replay 2026-10-28: the first cycle's 1- and 4-note cases stay within
    # eight voices and are bit-exact; from the 8-note case on (eight held plus
    # the sequencer's notes and release tails) the cap steals, and the carried
    # state keeps every later case different.
    assert cap8_serial[1][:2] == fixed_serial[1][:2]
    assert all(c != f for c, f in zip(cap8_serial[1][2:], fixed_serial[1][2:]))
