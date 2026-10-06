"""The idle paths of EQ, Isolator and Master Sat (engines/include/fm1_fx_idle.h;
engines/README.md, "Idle at pass-through"; owner's decision, 2026-10-05).

At its pass-through settings each of the three stops processing after two
seconds and outputs its guarded input; a knob that leaves pass-through wakes
it, its filters warm up from rest while the output stays the input, and then
the knob glides as it always has. fm1-idle-test (engines/test/idle_test.cc)
checks this against the same effects built without the idle paths
(-DFM1_FX_IDLE=0: the code as it was before them).
"""
import json
import subprocess

import pytest

from tests.engine_helpers import ENGINES, render, renderer  # noqa: F401

TOOL = ENGINES / "build" / "fm1-idle-test"
EFFECTS = ["eq", "isolator", "sat"]


@pytest.fixture(scope="module")
def report(renderer):  # noqa: F811 -- the renderer fixture builds everything
    out = subprocess.run([str(TOOL)], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


@pytest.mark.parametrize("fx", EFFECTS)
def test_away_from_pass_through_the_output_is_unchanged(report, fx):
    # Random settings that never sit at pass-through, changed at random
    # frames for 6 s (12 streams): bit for bit the output of the build
    # without the idle path.
    r = report["same"][fx]
    assert r["runs"] == 12 and r["mismatch"] == 0


@pytest.mark.parametrize("fx", EFFECTS)
def test_rests_and_wakes_do_not_depend_on_blocks_or_memory(report, fx):
    # The same streams with 3 s rests at pass-through among them (so the
    # effect idles and wakes), in blocks of 64, 7, 1 and 4,096 frames and
    # from memory filled with 0, 0xA5, 0xFF and 0x7F: the same bits.
    r = report["same"][fx]
    assert r["block_mismatch"] == 0 and r["fill_mismatch"] == 0
    assert report["wake_blocks_mismatch"] == 0


@pytest.mark.parametrize("fx", EFFECTS)
def test_idle_passes_the_guarded_input_bit_for_bit(report, fx):
    # 10 s at pass-through (idle from 2 s) on input with -0, subnormals,
    # FLT_MIN, +/-16, 1e30, NaN and infinities, every other knob turned to
    # its ends while idle: the guarded input, and the old build's output.
    r = report["neutral"][fx]
    assert r["exact"] and r["last_inexact"] == 0 and r["same_as_ref"]


def wake_cases(report, fx):
    return {k.split("/")[1]: v for k, v in report["wake"].items() if k.startswith(fx + "/")}


@pytest.mark.parametrize("fx", EFFECTS)
def test_a_wake_holds_the_input_then_fades_in_cleanly(report, fx):
    # After 3 s at pass-through a knob leaves it: the output stays the input
    # bit for bit until the release, then follows the old build's output with
    # the knob turned at the release, within -90 dB of the input's peak, and
    # matches it bit for bit within 1.5 s. Measured 2026-10-06: -92.5 dB at
    # worst (a +15 dB bell at 500 Hz, Q 10, on a 500 Hz sine).
    for label, c in wake_cases(report, fx).items():
        assert c["exact_before"], label
        if not (fx == "sat" and label in ("mix_defaults", "mix_hot_glue_1")):
            assert c["resid_db"] < -90, (label, c)
        assert c["same_after_s"] < 1.5, (label, c)


def test_glue_is_the_only_memory_a_wake_loses(report):
    # Master Sat's Glue envelope starts from rest: it attacks in 2 ms, but the
    # 200 ms release of a peak older than the wake is missing. With Glue at 0
    # the wake is as clean as the filters'; with Glue up the difference stays
    # under -70 dB (Glue 1, Drive 18 dB, Asymmetry 1: -73.8 dB measured).
    w = wake_cases(report, "sat")
    assert w["mix_glue_0"]["resid_db"] < -120 and w["mix_hot_glue_0"]["resid_db"] < -120
    assert w["mix_defaults"]["resid_db"] < -90
    assert w["mix_hot_glue_1"]["resid_db"] < -70


def test_warm_ups_are_as_long_as_the_filters_need(report):
    # The warm-up is the time the slowest filter mode at the new settings
    # takes to decay by e^-12, rounded up (EQ: to its 8-sample control
    # step). EQ warms each band on its own, so a bell or a treble shelf
    # answers in a few ms while a low shelf takes tens.
    eq, iso, sat = (wake_cases(report, fx) for fx in EFFECTS)
    ms = {k: v["warm_ms"] for k, v in eq.items()}
    assert ms["low_shelf_up"] == pytest.approx(27.2, abs=0.2)     # 100 Hz, Q 0.71
    assert ms["low_shelf_35"] == pytest.approx(77.2, abs=0.2)     # 35 Hz
    assert ms["bell"] == pytest.approx(3.9, abs=0.2)              # 1 kHz, Q 1
    assert ms["bell_200_q4"] < 100 and ms["high_18k_q03"] < 2
    assert ms["three_bands"] < 1                                  # the 8 kHz shelf first
    assert iso["kill_low"]["warm_ms"] == pytest.approx(10.8, abs=0.1)      # 250 Hz
    assert iso["kill_low_80"]["warm_ms"] == pytest.approx(33.8, abs=0.1)   # 80 Hz
    assert iso["kill_high_400_5k"]["warm_ms"] < iso["kill_low"]["warm_ms"]
    # Master Sat's 10 Hz DC blocker sets its warm-up whatever the knobs.
    assert all(c["warm_ms"] == pytest.approx(191.0, abs=0.1) for c in sat.values())


def test_level_and_settings_that_never_idle_answer_at_once(report):
    # EQ's Level needs no filter: it glides at once, bit for bit as before.
    # A band too low and narrow to warm within 0.1 s (here a bell at 300 Hz,
    # Q 10) keeps EQ running, so turning its gain is as before too.
    eq = wake_cases(report, "eq")
    for label in ("level", "never_idles_300_q10"):
        assert eq[label]["warm_ms"] < 0.2 and eq[label]["resid_db"] == -999.0, label


@pytest.mark.parametrize("fx", EFFECTS)
def test_a_short_rest_does_not_idle(report, fx):
    # The same moves after 1 s at pass-through, before the 2 s rest is up:
    # the old build's output, bit for bit, with no warm-up.
    for label, c in wake_cases(report, fx).items():
        assert c["early_same"], label


def test_silence_stays_silent_through_rests_and_wakes(report):
    assert report["wake_silence_nonzero"] == 0


def test_hostile_wakes_never_click(report):
    # Review, 2026-10-06: a band retuned in its own warm-up, a band tuned
    # from idle where EQ never idles with its gain raised 0.12 s later, DC
    # and loud low sines at the slowest settings that still idle, Glue after
    # a loud burst that ends 5 ms before the wake. In every case the output's
    # largest second difference, from 10 ms before the release to 200 ms
    # after it, is the old build's (to within 1 %): no click and no jump.
    h = report["hostile"]
    assert len(h) == 11
    for label, c in h.items():
        assert c["bend_ratio"] < 1.01, (label, c)


def test_hostile_wakes_stay_within_the_residue(report):
    # Where the settings were steady before the rest, or a band is retuned
    # after the wake, the output follows the old build's within -90 dB of the
    # input's peak, DC and full-scale low sines included (worst measured
    # -92.2 dB: a 100 Hz bell at Q 10 retuned 64 frames into its warm-up).
    h = report["hostile"]
    for label in ("eq/retune_400_q10_in_warm_up", "eq/retune_100_q10_in_warm_up",
                  "eq/low_shelf_dc", "eq/low_shelf_35_dc", "eq/bell_400_q10_on_400",
                  "isolator/kill_high_80_dc", "isolator/low_up_80_on_80", "sat/asym_drive_dc"):
        assert h[label]["resid_db"] < -90, (label, h[label])


def test_what_a_wake_cannot_restore(report):
    # Documented limits (engines/README.md, "Idle at pass-through"), pinned
    # so that a change to them is deliberate:
    # - EQ tuned from idle to where it never idles warms for at most 0.1 s;
    #   a gain raised after that answers at once, from a filter that started
    #   at the wake rather than one carried over from the old tuning: a
    #   different transient (-23 dB of the peak for a 30 Hz bell at Q 10 on a
    #   30 Hz sine, -38 dB for a 20 Hz shelf on DC), no click (above);
    # - Master Sat's Glue starts from rest: after a burst that ended 5 ms
    #   before the wake the old build's Glue is still releasing, -43 dB of
    #   the burst's peak (about -18 dB of the quiet tone after it), a level
    #   difference that fades with the 200 ms release, no click.
    h = report["hostile"]
    for label in ("eq/never_idles_bell_30_q10_gain_after",
                  "eq/never_idles_low_20_q03_gain_after_dc"):
        assert h[label]["release_ms"] == pytest.approx(120.0, abs=0.2), label
        assert h[label]["resid_db"] < -20, label
    assert -46 < h["sat/glue_after_burst"]["resid_db"] < -40


def test_a_lock_shorter_than_the_warm_up_after_a_rest_is_not_heard(report):
    # The trade-off of a clean wake: after more than 2 s at pass-through, a
    # lock that leaves it and comes back within the warm-up is not heard at
    # all (Master Sat's Mix for 0.1 s, under its 191 ms; Isolator's Kill
    # for 5 ms; EQ's Low Gain for 20 ms, under the 27 ms of a 100 Hz shelf).
    # The old build plays each, and so does the idle build within 2 s of the
    # last change.
    for label, c in report["short_lock"].items():
        assert c["lost_after_rest"] and c["heard_by_ref"] and c["early_same"], label


def test_resent_knobs_and_a_swept_frequency_leave_the_input_alone(report):
    # Every knob sent again every block at pass-through, and EQ's Mid Freq
    # swept at Q 10 through 200-400 Hz, in and out of the settings where it
    # never idles (so it wakes and idles again): the guarded input, bit for
    # bit, for 6 s.
    assert report["resend"] == {fx: True for fx in EFFECTS}


@pytest.mark.parametrize("rate", [8000, 96000, 384000])
def test_rests_and_wakes_at_other_rates(report, rate):
    # The busy setting after 2.5 s at pass-through: the same bits at blocks
    # of 64, 1, 7 and 4,096 frames and from other fills, exact silence on
    # silence, finite output, and Master Sat's 191 ms warm-up at any rate.
    for fx in EFFECTS:
        c = report["rates"][f"{fx}@{rate}"]
        assert c["block_mismatch"] == 0 and c["silence_peak"] == 0 and c["nonfinite"] == 0, (fx, c)
        assert c["release_ms"] < 200, (fx, c)
    assert report["rates"][f"sat@{rate}"]["release_ms"] == pytest.approx(191.0, abs=0.1)


def test_the_decay_bound_is_a_lower_bound(report):
    # fm1_idle_svf_decay against the exact decay per sample of the slowest
    # pole of the bilinear-transformed section, over g in 1e-4..10 and
    # k in 0.05..4: never above it (so a warm-up is never too short), and
    # within a factor of about 3.3 of it.
    b = report["bound"]
    assert b["points"] == 401 * 201 and b["over"] == 0
    assert b["max_ratio"] <= 1.0 + 1e-6 and b["min_ratio"] > 0.29


@pytest.mark.parametrize("fx,params", [
    ("eq", []),
    ("isolator", ["Low Xover=100"]),
    ("sat", ["Drive=18", "Glue=1"]),
])
def test_the_renderer_passes_long_idle_runs_through(renderer, tmp_path, fx, params):  # noqa: F811
    # Through fm1-render: 4 s of noise at pass-through, idle from 2 s, is the
    # input, as test-gain at unity gives it.
    ref, _, ref_wav = render(renderer, tmp_path, input="noise", seconds=4.0,
                             fx=[("test-gain", ["Gain=1"])], name="ref")
    out, _, out_wav = render(renderer, tmp_path, input="noise", seconds=4.0,
                             fx=[(fx, params)], name=fx)
    assert out["nonfinite"] == 0 and out_wav.read_bytes() == ref_wav.read_bytes()


def test_output_hash_is_pinned(renderer):  # noqa: F811
    # Each effect through 3 s at pass-through (idle from 2 s), a wake to a
    # busy setting, back to pass-through, idle again and another wake, on
    # integer noise: every output float hashed. Apple clang (arm64), GCC 12
    # and 13 (x86-64), GCC 14 (i386, SSE) and Emscripten 6.0.10 (wasm32,
    # Node) printed these [verified 2026-10-06, the last four in containers on
    # the LAN build host]: the warm-up lengths, integers from float maths, are
    # the same on every build, and so is every sample.
    out = subprocess.run([str(TOOL), "--hash"], check=True, capture_output=True,
                         text=True).stdout
    assert json.loads(out) == {"eq": "46aea318", "isolator": "a6bac972", "sat": "698b50c7"}
