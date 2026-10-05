"""Tests for Plate's Freeze (engines/src/mi_fx.cc, notes in engines/mi-fx.md,
"Freeze"): Elements' recipe (loop gain 1, no damping, no input) behind a
5 ms ramp, appended as uid 5 on page 1.

Through fm1-render: registration, Freeze set before the first block (an
empty loop held: the dry alone), Mix 0 still a bit-exact bypass, the switch
rounding at 0.5, bad input guarded. Through fm1-plate-test
(engines/test/plate_test.cc): Freeze turned while audio runs, at any block
size and from any memory fill; the level held on engaging and over a minute;
how long a frozen tail lasts in the 16-bit loop; that a frozen loop ignores
its input; the owner's clean-switch test; release to exact zeros; Decay and
Damping waiting while frozen; host rates.

That Freeze Off leaves every render byte-identical to the build before it is
shown by comparing the two builds (engines/mi-fx.md, "Freeze"); here,
tests/test_engines_reference_braids_fx.py keeps holding Plate to upstream.
"""
import json
import subprocess

import pytest

from tests.engine_helpers import ENGINES, render, renderer  # noqa: F401
from tests.test_engines_mi_fx import run

TOOL = ENGINES / "build" / "fm1-plate-test"


def cli(*params):
    args = ["--fx", "plate"]
    for p in params:
        args += ["--fx-param", p]
    return args


@pytest.fixture(scope="module")
def tool(renderer):  # noqa: F811 -- the renderer fixture builds everything
    out = subprocess.run([str(TOOL)], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def test_freeze_is_appended_as_a_modulatable_switch(renderer):  # noqa: F811
    listed = json.loads(subprocess.run([str(renderer), "--list"], check=True,
                                       capture_output=True, text=True).stdout)
    params = {e["id"]: e for e in listed}["plate"]["params"]
    assert [p["uid"] for p in params] == [1, 2, 3, 4, 5]     # appended: no uid moved
    freeze = params[4]
    assert freeze["name"] == "Freeze" and freeze["type"] == 1
    assert (freeze["min"], freeze["max"], freeze["def"]) == (0, 1, 0)
    assert freeze["names"] == ["Off", "On"]
    assert freeze["page"] == 1 and freeze["abbr"] == "Freeze"
    assert freeze["flags"] == ["mod"]                       # lockable (no nolock), rounded


def test_freeze_off_equals_freeze_unset(renderer, tmp_path):  # noqa: F811
    _, _, a = render(renderer, tmp_path, input="noise", seconds=1.0,
                     fx=[("plate", ["Mix=0.6", "Decay=0.8"])], name="unset")
    _, _, b = render(renderer, tmp_path, input="noise", seconds=1.0,
                     fx=[("plate", ["Mix=0.6", "Decay=0.8", "Freeze=0"])], name="off")
    _, _, c = render(renderer, tmp_path, input="noise", seconds=1.0,
                     fx=[("plate", ["Mix=0.6", "Decay=0.8", "Freeze=0.49"])], name="low")
    assert a.read_bytes() == b.read_bytes() == c.read_bytes()


def test_freeze_from_the_start_holds_an_empty_loop(renderer, tmp_path):  # noqa: F811
    # Set before the first block, Freeze ramps from the first sample and
    # holds what the loop had: nothing. At Mix 1 that is exact silence for
    # any input, at Mix 0 the input bit for bit, and in between the dry at
    # 1 - Mix. 0.51 rounds to On.
    s, left, _ = render(renderer, tmp_path, input="noise", seconds=1.0,
                        fx=[("plate", ["Mix=1", "Freeze=0.51"])], name="wet")
    assert s["nonfinite"] == 0
    assert all(x == 0.0 for x in left[300:])                # after the 5 ms ramp
    ref, _, ref_wav = render(renderer, tmp_path, input="noise", seconds=1.0,
                             fx=[("test-gain", ["Gain=1"])], name="ref")
    _, _, dry_wav = render(renderer, tmp_path, input="noise", seconds=1.0,
                           fx=[("plate", ["Mix=0", "Freeze=1", "Decay=1"])], name="dry")
    assert dry_wav.read_bytes() == ref_wav.read_bytes()      # Mix 0 is still a bypass
    _, half, _ = render(renderer, tmp_path, input="noise", seconds=1.0,
                        fx=[("plate", ["Mix=0.25", "Freeze=1"])], name="half")
    _, src, _ = render(renderer, tmp_path, input="noise", seconds=1.0,
                       fx=[("test-gain", ["Gain=0.75"])], name="src")
    assert max(abs(a - b) for a, b in zip(half[300:], src[300:])) <= 1.5 / 32767


@pytest.mark.parametrize("fault", ["0..0.5:nan", "0..0.5:inf", "0.1:1e30"])
def test_bad_input_is_guarded_while_frozen(renderer, tmp_path, fault):  # noqa: F811
    for mix in ("0", "0.5", "1"):
        s, _, _, _ = run(renderer, tmp_path,
                         ["--input", "noise", "--seconds", "0.6", "--fault", fault,
                          *cli("Freeze=1", f"Mix={mix}", "Decay=1")], f"bad_{mix}")
        assert s["nonfinite"] == 0


def test_freeze_mid_stream_stays_finite(tool):
    # Every parameter, Freeze included (5,542 sets), at min, max, default,
    # random, beyond the range, NaN and infinities, between blocks of random
    # size, over noise with NaN, infinities and 1e6 mixed in. The peak is
    # the input guard's 16, passed on the dry path.
    s = tool["sweep"]
    assert s["samples"] >= 20 * 44118 and s["freeze_sets"] > 1000
    assert s["nonfinite"] == 0 and s["peak"] <= 16.0


def test_block_size_and_memory_fill_do_not_change_the_output(tool):
    # Freeze on and off, toggled again half way through a ramp, Decay,
    # Damping and Mix turned while frozen: blocks of 64, 7, 1 and random
    # sizes, and instance memory filled with 0xA5 and 0xFF, all identical.
    assert tool["blocks"] == {"block_independent": True, "fill_independent": True}


def test_engaging_holds_the_level(tool):
    # Freeze at 1.2 s in a falling tail. The wet does not jump when the loop
    # gain goes to 1: the all-passes and delays carry the louder recent past.
    # Measured -0.67, -0.51 and -0.13 dB from the 30 ms before to the 30 ms
    # after (the tail's own fall over that time) at Decay 0, 0.5 and 1.
    for h in tool["hold"]:
        assert -1.5 < h["step_db"] < 0.5, h


def test_the_body_of_the_tail_is_held(tool):
    # Unfrozen, Decay 0 falls 43 dB a second. Frozen, below about 300 Hz the
    # tail measured -0.8/-0.6/-0.4 dB after 10 s and -6.2/-3.9/-2.2 dB after
    # 60 s (Decay 0/0.5/1). Broadband it falls faster (-5.7/-4.7/-3.6 dB at
    # 10 s): the loop's linearly interpolated, modulated reads low-pass every
    # pass, so the highs fade first, as in Elements.
    for h in tool["hold"]:
        assert h["low_db_10s"] > -2.0 and h["low_db_60s"] > -9.0, h
        assert h["db_10s"] > -8.0, h
        assert h["db_60s"] < h["db_10s"] < 0.0, h            # it does wear away


def test_a_frozen_tail_lasts_minutes_not_forever(tool):
    # The loop's 16-bit stores truncate towards zero, so a frozen tail loses
    # a little on every pass, relatively more the quieter it is, and finally
    # stops: measured 167 s for a tail held at -18.7 dBFS and 26 s at
    # -38.9 dBFS (engines/mi-fx.md, "Freeze"). This pins the limit so a
    # change to it is noticed.
    loud, quiet = tool["lifetime"]
    assert loud["frozen_dbfs"] > quiet["frozen_dbfs"] + 15
    assert 100 < loud["lasts_s"] < 300
    assert 15 < quiet["lasts_s"] < 60


def test_a_frozen_loop_ignores_its_input(tool):
    # Two renders alike until the ramp ends; then one is silent and the
    # other plays noise with NaN, infinities and 1e6. At Mix 1 every output
    # sample is equal.
    assert tool["ignores_input"]["differ"] == 0 and tool["ignores_input"]["rms"] > 0.05


def test_switching_is_clean(tool):
    # The owner's test for a switch: toggled every third 64-frame block for
    # 2 s over a 440 Hz sine at Mix 0.5, no output step beyond the held
    # renders' largest plus a 5 ms crossfade's 2P/220. Measured 0.0485
    # against 0.0453 + 0.0071. Switching at once, as Elements does, measured
    # 0.116 against 0.064 + 0.0085 and fails.
    c = tool["clean"]
    assert c["toggles"] > 400
    assert c["toggled_step"] <= c["held_step"] + c["allowance"], c
    assert c["engage_step"] <= c["held_step"] + c["allowance"], c


def test_release_decays_to_exact_zeros(tool):
    # Frozen for 2 s, then off with silence in: the tail decays as Decay 0.5
    # says (-16 dB in the first second) and the output is exact zeros 4.4 s
    # after release.
    r = tool["release"]
    assert r["frozen_rms"] > 0.05
    assert r["after_1s_db"] < -10
    assert 0 < r["zero_after_s"] < 8


def test_decay_and_damping_wait_while_frozen(tool):
    # Turned while frozen, Decay and Damping change nothing until release,
    # and then do; Diffusion stays live, as in Elements.
    w = tool["waits"]
    assert w["differ_frozen"] == 0
    assert w["differ_after_release"] > 0 and w["differ_diffusion"] > 0


def test_freeze_at_other_host_rates(tool):
    # The ramp is 5 ms at any rate; the hold measured -0.9 to -2.6 dB over
    # the next two seconds at 8, 32, 48 and 96 kHz.
    for r in tool["rates"]:
        assert r["nonfinite"] == 0 and -4.0 < r["db_2s"] < 0.0, r
