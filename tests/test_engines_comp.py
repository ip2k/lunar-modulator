"""Tests for Comp, the feed-forward compressor (engines/src/fx_comp.cc,
parameters in engines/README.md, "Comp").

Through fm1-render: registration and pages, the host contracts (deterministic
renders, any block size, any prior memory contents, any parameter value,
NaN included, bad input guarded and not latched, silence in gives silence
out), and every parameter doing what it says on the renderer's sine and
noise. Through fm1-comp-test (engines/test/comp_test.cc): the static curve
against the formula at several thresholds, ratios and knees; attack and
release time constants measured on exact steps, per Character, and Auto
Release's two releases; release to exact zeros with no pumping; the ripple
on a steady tone; the hand-over when Character or Auto Rel changes;
parameters changed while audio runs at any block size; the gain-reduction
accessor; host rates; the accuracy of its log2 and exp2 against libm.

The figures in the comments were measured on the desktop build (Apple
clang, arm64, 2026-10-02).
"""
import json
import math
import subprocess

import pytest

from tests.engine_helpers import ENGINES, RATE, render, renderer, rms  # noqa: F401
from tests.test_engines_mi_fx import BANNED, correlation, run

TOOL = ENGINES / "build" / "fm1-comp-test"
LSB = 1 / 32767.0
SINE_DB = 20 * math.log10(0.5)          # the renderer's sine, -6.02 dBFS

# Every parameter away from its default.
BUSY = ["Threshold=-30", "Ratio=6", "Attack=3", "Release=80", "Knee=9", "Makeup=4",
        "Mix=0.8", "Character=2", "Auto Rel=1", "Auto Gain=0"]


def fx(*params):
    return [("comp", list(params))]


def cli(*params):
    args = ["--fx", "comp"]
    for p in params:
        args += ["--fx-param", p]
    return args


def curve(level, threshold, ratio, knee):
    """The static curve, written independently of fx_comp.cc: the reduction
    in dB asked for at `level` dB (Giannoulis, Massberg and Reiss 2012, the
    soft-knee gain computer, with the slope going on to 1 between 20:1 and
    21)."""
    slope = 1 - 1 / ratio if ratio <= 20 else 0.95 + 0.05 * (ratio - 20)
    d = level - threshold
    if 2 * d <= -knee:
        return 0.0
    if 2 * d >= knee:
        return slope * d
    return slope * (d + knee / 2) ** 2 / (2 * knee)


def db(x):
    return 20 * math.log10(x)


def window_db(samples, start_s, end_s):
    return db(rms(samples, start_s, end_s))


@pytest.fixture(scope="module")
def tool(renderer):  # noqa: F811 -- the renderer fixture builds everything
    out = subprocess.run([str(TOOL)], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


@pytest.fixture(scope="module")
def entry(renderer):  # noqa: F811
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True,
                         text=True).stdout
    return {x["id"]: x for x in json.loads(out)}["comp"]


def test_comp_is_registered(entry):
    e = entry
    assert (e["name"], e["kind"], e["max_voices"]) == ("Comp", "audio_fx", 0)
    assert not any(b in (e["id"] + e["name"]).lower() for b in BANNED)
    assert "MIT" in e["credits"] and "Giannoulis" in e["credits"]
    pages = [[p["name"] for p in e["params"] if p["page"] == k] for k in (0, 1, 2)]
    assert pages == [["Threshold", "Ratio", "Attack", "Release"],
                     ["Knee", "Makeup", "Mix", "Character"],
                     ["Auto Rel", "Auto Gain"]]
    by = {p["name"]: p for p in e["params"]}
    assert all(len(p["name"]) <= 10 for p in e["params"])   # the screen's label width
    assert all(p["min"] <= p["def"] <= p["max"] for p in e["params"])
    assert by["Character"]["names"] == ["Peak", "RMS", "Glue", "Punch"]
    assert by["Auto Rel"]["names"] == by["Auto Gain"]["names"] == ["Off", "On"]
    assert (by["Attack"]["unit"], by["Release"]["unit"]) == ("ms", "ms")
    assert (by["Ratio"]["min"], by["Ratio"]["max"]) == (1, 21)


def test_instance_is_small(renderer, tmp_path):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.05, fx=fx())
    assert s["fx_bytes"][0] % 16 == 0 and s["fx_bytes"][0] <= 256   # 160 on the desktop


# --- host contracts ---------------------------------------------------------

def test_rendering_is_deterministic(renderer, tmp_path):  # noqa: F811
    _, _, a = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY), name="a")
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY), name="b")
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("params", [BUSY, ["Character=3", "Attack=40", "Threshold=-40"]])
def test_block_size_does_not_change_the_output(renderer, tmp_path, params):  # noqa: F811
    wavs = []
    for frames in ("64", "7", "1"):
        _, _, wav = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*params),
                           name=f"f{frames}", extra=["--frames", frames])
        wavs.append(wav.read_bytes())
    assert wavs[0] == wavs[1] == wavs[2]


def test_output_ignores_initial_memory(renderer, tmp_path):  # noqa: F811
    wavs = []
    for fill in ("0", "0xA5", "0xFF"):
        s, _, wav = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY),
                           name=f"fill{fill}", extra=["--fill", fill])
        assert s["nonfinite"] == 0
        wavs.append(wav.read_bytes())
    assert wavs[0] == wavs[1] == wavs[2]


@pytest.mark.parametrize("value,same_as", [
    ("nan", None),            # NaN is the default (fm1_param_clamp)
    ("1e9", "max"),
    ("-1e9", "min"),
    ("inf", "max"),
])
def test_out_of_range_parameters_clamp(renderer, tmp_path, entry, value, same_as):  # noqa: F811
    bad = [f"{p['name']}={value}" for p in entry["params"]]
    good = [] if same_as is None else [f"{p['name']}={p[same_as]}" for p in entry["params"]]
    s, _, a = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*bad), name="bad")
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*good), name="good")
    assert s["nonfinite"] == 0
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("params", [
    [],
    BUSY,
    ["Makeup=24", "Auto Gain=1", "Threshold=-60", "Ratio=21"],   # +84 dB of makeup
    ["Character=1", "Mix=0.5", "Auto Rel=1"],
])
def test_silence_in_is_silence_out(renderer, tmp_path, params):  # noqa: F811
    # The gain multiplies the input, so no makeup can lift silence.
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.5, fx=fx(*params))
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


BAD_INPUT = {"nan": "nan", "inf": "inf", "huge": "1e30"}


@pytest.mark.parametrize("bad", sorted(BAD_INPUT))
def test_bad_input_is_guarded_and_not_latched(renderer, tmp_path, bad):  # noqa: F811
    # The guard reads NaN as 0 and clamps everything else to +/-16, so no
    # state is poisoned. A clamped over (+24 dBFS) asks for a deep reduction
    # that then releases (80 ms); a second after the fault the output is the
    # fault-free output within one 16-bit step (the states converge
    # geometrically, to within rounding).
    base = ["--input", "noise", "--seconds", "2.0", *cli(*BUSY)]
    _, clean_l, clean_r, _ = run(renderer, tmp_path, base, "clean")
    fault = ["--fault", f"0.2..0.5:{BAD_INPUT[bad]}"]
    s, left, right, _ = run(renderer, tmp_path, [*base, *fault], "fault")
    assert s["nonfinite"] == 0
    assert s["raw_peak"] < 16
    tail = slice(int(1.5 * RATE), None)
    assert max(abs(a - b) for a, b in zip(left[tail], clean_l[tail])) <= 1.01 * LSB
    assert max(abs(a - b) for a, b in zip(right[tail], clean_r[tail])) <= 1.01 * LSB


def test_nan_input_reads_as_silence(renderer, tmp_path):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="noise", seconds=0.5,
                     fx=fx("Makeup=12", "Auto Gain=1"), extra=["--fault", "0..0.5:nan"])
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


@pytest.mark.parametrize("bad", ["inf", "1e30"])
def test_mix_zero_passes_the_clamped_input(renderer, tmp_path, bad):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="noise", seconds=0.3,
                     fx=fx("Mix=0", "Threshold=-60", "Makeup=24"),
                     extra=["--fault", f"0.1..0.2:{bad}"])
    assert s["nonfinite"] == 0 and s["raw_peak"] == 16.0


def test_mix_zero_passes_the_input_through(renderer, tmp_path):  # noqa: F811
    ref, _, ref_wav = render(renderer, tmp_path, input="noise", seconds=1.0,
                             fx=[("test-gain", ["Gain=1"])], name="ref")
    out, _, out_wav = render(renderer, tmp_path, input="noise", seconds=1.0,
                             fx=fx(*[p for p in BUSY if not p.startswith("Mix")], "Mix=0"),
                             name="dry")
    assert out["raw_peak"] == ref["raw_peak"]
    assert out_wav.read_bytes() == ref_wav.read_bytes()


def test_below_the_threshold_it_is_bit_transparent(renderer, tmp_path):  # noqa: F811
    # No reduction and no makeup: the gain is 2^0, exactly 1, every sample.
    _, _, ref = render(renderer, tmp_path, input="sine", seconds=0.5,
                       fx=[("test-gain", ["Gain=1"])], name="ref")
    for character in range(4):
        _, _, out = render(renderer, tmp_path, input="sine", seconds=0.5, name=f"c{character}",
                           fx=fx("Threshold=0", "Knee=0", f"Character={character}"))
        assert out.read_bytes() == ref.read_bytes(), character


# --- every knob does what it says ---------------------------------------------

def reduction_db(renderer, tmp_path, *params, input="sine", name="out"):  # noqa: F811
    """How far below the dry signal the output sits, 0.5-1.0 s, in dB."""
    _, dry, _ = render(renderer, tmp_path, input=input, seconds=1.0, name=f"{name}-dry",
                       fx=[("test-gain", ["Gain=1"])])
    _, wet, _ = render(renderer, tmp_path, input=input, seconds=1.0, name=name, fx=fx(*params))
    return window_db(dry, 0.5, 1.0) - window_db(wet, 0.5, 1.0)


@pytest.mark.parametrize("threshold,ratio", [(-30, 4), (-12, 4), (-30, 2), (-30, 21)])
def test_threshold_and_ratio_follow_the_curve(renderer, tmp_path, threshold,
                                              ratio):  # noqa: F811
    # RMS reads the sine's peak level (it is sine-calibrated), so the steady
    # reduction is the curve's at -6.02 dB, within the detector's ripple
    # (measured +0.05 dB at 4:1).
    got = reduction_db(renderer, tmp_path, f"Threshold={threshold}", f"Ratio={ratio}", "Knee=0",
                       "Character=1")
    assert got == pytest.approx(curve(SINE_DB, threshold, ratio, 0), abs=0.12)


def test_knee_rounds_the_corner(renderer, tmp_path):  # noqa: F811
    # The threshold at the sine's level: a hard knee does (almost) nothing,
    # a 12 dB knee already reduces by S W / 8 = 1.1 dB there.
    hard = reduction_db(renderer, tmp_path, "Threshold=-6", "Knee=0", "Character=1", name="h")
    soft = reduction_db(renderer, tmp_path, "Threshold=-6", "Knee=12", "Character=1", name="s")
    assert hard == pytest.approx(curve(SINE_DB, -6, 4, 0), abs=0.12)
    assert soft == pytest.approx(curve(SINE_DB, -6, 4, 12), abs=0.12)
    assert soft > hard + 0.8


@pytest.mark.parametrize("makeup", [3, -12])
def test_makeup_is_a_gain_in_db(renderer, tmp_path, makeup):  # noqa: F811
    got = reduction_db(renderer, tmp_path, "Threshold=0", "Knee=0", f"Makeup={makeup}")
    assert -got == pytest.approx(makeup, abs=0.01)


def test_auto_makeup_restores_full_scale(renderer, tmp_path):  # noqa: F811
    # Auto adds the curve's reduction at 0 dBFS (0.75 x 30 = 22.5 dB at
    # -30 dB, 4:1), so the sine's -6 dB come out 22.5 - 17.98 dB louder.
    got = reduction_db(renderer, tmp_path, "Threshold=-30", "Knee=0", "Character=1",
                       "Auto Gain=1")
    assert -got == pytest.approx(curve(0, -30, 4, 0) - curve(SINE_DB, -30, 4, 0), abs=0.12)
    trim = reduction_db(renderer, tmp_path, "Threshold=-30", "Knee=0", "Character=1",
                        "Auto Gain=1", "Makeup=-6", name="trim")
    assert trim - got == pytest.approx(6, abs=0.01)                 # Makeup trims it


def test_attack_lets_the_onset_through(renderer, tmp_path):  # noqa: F811
    # The renderer's sine starts at full level: with Attack 0 the first
    # peaks are already limited; with 50 ms they pass almost untouched.
    peaks = {}
    for attack in ("0", "50"):
        _, left, _ = render(renderer, tmp_path, input="sine", seconds=0.2, name=f"a{attack}",
                            fx=fx("Threshold=-30", "Ratio=21", "Knee=0", f"Attack={attack}"))
        peaks[attack] = max(abs(x) for x in left[:int(0.005 * RATE)])
    assert peaks["0"] < 0.06                                     # measured 0.033
    assert peaks["50"] > 0.4                                     # measured 0.47


def test_release_sets_the_recovery(renderer, tmp_path):  # noqa: F811
    # A loud over (+24 dBFS, 0.2 s) pushes the reduction 30 dB past the
    # sine's; afterwards the sine comes back at the release's pace: within
    # 3 dB of its steady level after 1.4 time constants (the reduction falls
    # towards the curve's mean over each cycle, below its peaks, so sooner
    # than ln 10). Measured 72 and 705 ms. Exact time constants: below,
    # through fm1-comp-test.
    recovered = {}
    for release_ms in (50, 500):
        params = ["Threshold=-30", "Ratio=21", "Knee=0", "Attack=1", f"Release={release_ms}"]
        _, left, _ = render(renderer, tmp_path, input="sine", seconds=4.0, fx=fx(*params),
                            name=f"r{release_ms}", extra=["--fault", "0.5..0.7:16"])
        steady = window_db(left, 3.5, 4.0)
        t = 0.7
        while window_db(left, t, t + 0.005) < steady - 3 and t < 3.5:
            t += 0.001
        recovered[release_ms] = 1000 * (t - 0.7)
        assert release_ms < recovered[release_ms] < 2.3 * release_ms
    assert 8 < recovered[500] / recovered[50] < 12


def test_mix_blends_dry_and_compressed(renderer, tmp_path):  # noqa: F811
    # Attack 0 keeps the compressed noise under the host's limiter, which
    # would otherwise bend the sum.
    common = ["Threshold=-30", "Ratio=8", "Attack=0", "Makeup=6"]
    _, dry, _ = render(renderer, tmp_path, input="noise", seconds=1.0, name="m0",
                       fx=fx(*common, "Mix=0"))
    _, wet, _ = render(renderer, tmp_path, input="noise", seconds=1.0, name="m1",
                       fx=fx(*common, "Mix=1"))
    _, mid, _ = render(renderer, tmp_path, input="noise", seconds=1.0, name="m5",
                       fx=fx(*common, "Mix=0.5"))
    worst = max(abs(m - 0.5 * (d + w)) for m, d, w in zip(mid, dry, wet))
    assert worst <= 1.5 * LSB
    assert correlation(mid, dry) > 0.9 and rms(wet, 0.2, 1.0) < rms(dry, 0.2, 1.0)


def test_character_changes_the_detector(renderer, tmp_path):  # noqa: F811
    # On the 440 Hz sine, RMS and Glue sit on the curve (17.98 dB: they read
    # the sine's peak level). Peak, with its 10 ms attack, catches only part
    # of each peak and settles about 1 dB under it (16.98); Punch's faster
    # first stage catches more (17.31). Attack 0 puts Peak on the curve. On
    # noise all four differ (measured 15.96, 16.75, 16.73, 16.49 dB).
    want = curve(SINE_DB, -30, 4, 0)
    sine = {c: reduction_db(renderer, tmp_path, "Threshold=-30", "Ratio=4", "Knee=0",
                            f"Character={c}", name=f"s{c}") for c in range(4)}
    assert sine[1] == pytest.approx(want, abs=0.12) and sine[2] == pytest.approx(want, abs=0.12)
    assert want - 1.5 < sine[0] < sine[3] < want - 0.3
    instant = reduction_db(renderer, tmp_path, "Threshold=-30", "Ratio=4", "Knee=0", "Attack=0",
                           name="instant")
    assert instant == pytest.approx(want, abs=0.05)
    noise = [reduction_db(renderer, tmp_path, "Threshold=-30", "Ratio=4", "Knee=0",
                          f"Character={c}", input="noise", name=f"n{c}") for c in range(4)]
    assert min(abs(a - b) for i, a in enumerate(noise) for b in noise[i + 1:]) > 0.01
    assert noise[0] == min(noise)


def test_after_an_engine_and_before_a_reverb(renderer, tmp_path):  # noqa: F811
    summary, left, right, _ = run(
        renderer, tmp_path,
        ["--engine", "macro", "--param", "Model=0", "--note", "0:45:100:0.5",
         "--note", "0:52:100:0.5", "--seconds", "1.5",
         *cli("Threshold=-24", "Character=2", "Auto Gain=1"),
         "--fx", "plate", "--fx-param", "Mix=0.3"], "chain")
    assert summary["fx"] == ["comp", "plate"]
    assert summary["nonfinite"] == 0
    assert rms(left, 0.1, 0.5) > 1e-2 and rms(left, 1.0, 1.4) > 1e-4


# --- fm1-comp-test: what fm1-render cannot drive ---------------------------------

def test_static_curve_matches_the_formula(tool):
    # A constant input, Peak, Attack 0: the accessor's reduction and the
    # measured gain are the curve's, at three thresholds, eight ratios
    # (20.5 and 21 included) and four knees, from -60 to +20 dB: 3,168
    # points, worst 3.8e-6 dB (accessor) and 7.6e-6 dB (gain).
    worst_accessor = worst_gain = 0.0
    for t, ratio, knee, level, accessor, gain in tool["curve"]:
        want = curve(level, t, ratio, knee)
        worst_accessor = max(worst_accessor, abs(accessor - want))
        worst_gain = max(worst_gain, abs(gain - want))
    assert len(tool["curve"]) == 3 * 8 * 4 * 33
    assert worst_accessor < 1e-4 and worst_gain < 1e-4


def test_ratio_21_is_a_flat_line(tool):
    above = [p for p in tool["curve"] if p[1] == 21 and p[2] == 0 and p[3] > p[0]]
    assert above and all(p[3] - p[5] == pytest.approx(p[0], abs=1e-4) for p in above)


@pytest.mark.parametrize("character", ["peak", "punch"])
def test_attack_and_release_time_constants(tool, character):
    # The reduction is smoothed in dB by one-pole lags: a step reaches 63.2 %
    # after Attack and falls to 36.8 % after Release. Punch's two half-length
    # attack stages reach 63.2 % at 1.073 Attack (1 - e^-u (1 + u) = 1 - 1/e
    # at u = 2.146).
    factor = 1.0 if character == "peak" else 1.0734
    for set_ms, got_ms in tool["times"][character]["attack"]:
        assert got_ms == pytest.approx(factor * set_ms, rel=0.01, abs=0.03)
    for set_ms, got_ms, settled in tool["times"][character]["release"]:
        assert settled == pytest.approx(40, abs=1e-3)
        assert got_ms == pytest.approx(set_ms, rel=0.002, abs=0.03)


def test_rms_and_glue_add_their_averaging(tool):
    # The RMS detectors' own lag (10 and 30 ms) adds to the smoothing on a
    # step; Glue's decoupled release passes through its attack stage too.
    # Measured: RMS attack 2.7/10.6/46 ms and release 111/266/1,123 ms; Glue
    # 3.4/12.4/50 and 246/383/1,227 ms.
    for c in ("rms", "glue"):
        t = tool["times"][c]
        for set_ms, got_ms in t["attack"]:
            assert 0.85 * set_ms < got_ms < 1.8 * set_ms + 2
        for set_ms, got_ms, settled in t["release"]:
            assert settled == pytest.approx(43.01, abs=0.01)   # DC reads +3 dB (sine-calibrated)
            assert set_ms < got_ms < set_ms + 300


def test_auto_release_depends_on_the_programme(tool):
    # Release 500 ms. Off: 500 ms after a 10 ms burst and after a 2 s one.
    # On: after the burst the first stage (500 / 5 = 100 ms) lets go; after
    # the long one the slow envelope holds it (603 ms, its lag on top).
    got = {(b, on): ms for b, on, _, ms in tool["times"]["auto"]}
    assert got[(0.01, 0)] == pytest.approx(500, rel=0.01)
    assert got[(2, 0)] == pytest.approx(500, rel=0.01)
    assert got[(0.01, 1)] == pytest.approx(100, rel=0.02)
    assert 500 < got[(2, 1)] < 700


def test_silence_releases_to_exact_zero_without_pumping(tool):
    # After a second of loud noise, 8.7 s of silence: no output at all (with
    # 18 dB of makeup and Auto Gain on), the reduction never rises, and it
    # reaches exactly 0 (flushed below 1e-6 dB) after about 5.2-5.4 s.
    for name, s in tool["silence"].items():
        assert s["start"] > 20, name
        assert s["out_peak"] == 0 and s["rises"] == 0, name
        assert s["end"] == 0 and 0 < s["zero_ms"] < 8000, name


def test_steady_tone_does_not_pump(tool):
    # A steady sine 24 dB over the threshold (4:1): the reduction's ripple
    # over 0.5 s, at 440 and 100 Hz. Peak follows each half cycle a little
    # (0.02 / 0.09 dB); the RMS detectors hardly at all.
    s = tool["steady"]
    for name, rows in s.items():
        for hz, mean, ripple in rows:
            assert ripple < (0.15 if name in ("peak", "punch") else 0.01), (name, hz)
    want = curve(SINE_DB, -30, 4, 0)                          # 17.98 dB
    for hz, mean, _ in s["rms"] + s["glue"]:
        assert mean == pytest.approx(want, abs=0.25)         # RMS reads the sine's peak
    for hz, mean, _ in s["peak"] + s["punch"]:
        assert want - 1.2 < mean < want                       # catches each peak only in part


def test_handover_does_not_step(tool):
    # Turning Auto Rel off, or Punch into Peak, mid-compression moves the
    # reduction by 8-15 dB, over about 5 ms: no frame steps by more than
    # 0.08 dB (measured 0.073 and 0.052).
    for name, h in tool["handover"].items():
        assert abs(h["at_25ms"] - h["control_at_25ms"]) > 5, name
        assert h["max_step"] < 0.1, name
        assert h["control_max_step"] < 0.01, name


def test_glide_is_block_size_independent_and_reaches_its_target(tool):
    g = tool["glide"]
    assert g["block_independent"]
    assert g["before"] == pytest.approx(0.25, abs=1e-4)
    # Makeup 0 -> +12 dB glides: after 1 ms it is not there yet...
    assert g["first_ms"] < 0.35
    # ...and 50 ms later it is, exactly (2^(12 log2(10) / 20) x 0.25).
    assert g["tail"] == pytest.approx(0.25 * 10 ** (12 / 20), rel=2e-5)


def test_any_parameter_change_mid_stream_stays_finite(tool):
    # 20 s of noise (some of it +12 dBFS); between blocks of 1-64 frames, up
    # to two parameters jump to their minimum, maximum, default, a random
    # value, beyond the range, NaN or an infinity. The accessor stays finite
    # and non-negative; NULL reads 0.
    s = tool["sweep"]
    assert s["samples"] > 20 * RATE
    assert s["nonfinite"] == 0 and s["peak"] < 16 * 10 ** (84 / 20)
    assert s["bad_reduction"] == 0 and s["null_reads"] == 0


def test_host_rates(tool):
    accepted = {rate: ok for rate, ok in tool["rates"]}
    assert accepted == {"0": False, "7999": False, "8000": True, "44118": True,
                        "48000": True, "96000": True, "384000": True, "400000": False,
                        "nan": False, "inf": False, "-44118": False}


def test_log2_and_exp2_are_accurate(tool):
    # fx_comp_math.h, no libm: log2 within 2e-7 near 0 dB and 2.1 ulp of its
    # result anywhere (about 1e-5 dB at -200 dB); exp2 within 2.4e-7
    # relative. Out of range: 0 below -126, 2^126 above, 0 for NaN.
    a = tool["approx"]
    assert a["log2_abs_near_1"] < 3e-7 and a["log2_ulps"] < 2.5
    assert a["exp2_rel"] < 4e-7
    assert a["exp2_0"] == 1.0 and a["exp2_low"] == 0.0 and a["exp2_nan"] == 0.0
    assert a["exp2_high"] == pytest.approx(2.0 ** 126, rel=1e-6)


def test_output_is_the_same_bits_on_every_build(tool):
    # No libm and no fused multiply-adds (fx_comp.cc), so every float of
    # these renders is the same on Apple clang/arm64, GCC/i386 (SSE),
    # GCC/x86-64 and Emscripten's WebAssembly [verified 2026-10-02], which
    # is what keeps the browser bit-exact. A deliberate change to the DSP
    # moves these: check it in the browser's module, then pin the new ones.
    assert tool["hash"] == ["87350847", "d24bcc95", "0bb3b225"]
