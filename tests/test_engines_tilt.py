"""Tests for Tilt, the tilt equaliser (engines/src/fx_tilt.cc, parameters in
engines/README.md, "Tilt").

Through fm1-render: registration and the page, the host contracts
(deterministic renders, any block size, any prior memory contents, any
parameter value, NaN included, bad input guarded and not latched, silence in
gives silence out), the exact bypass at the defaults, and every knob doing
what it says. Through fm1-tilt-test (engines/test/tilt_test.cc): the
frequency response in float against an independent model of the design,
the bypass bit for bit, parameters changed while audio runs (jumps, a sweep
at the matrix's rate, every value at random), and the host rates.
"""
import cmath
import json
import math
import subprocess

import pytest

from tests.engine_helpers import ENGINES, RATE, render, renderer, rms  # noqa: F401
from tests.test_engines_mi_fx import BANNED, brightness, run

TOOL = ENGINES / "build" / "fm1-tilt-test"
LSB = 1 / 32767.0
STAGGER = 2 ** 1.5           # Slope's sections, 1.5 octaves either side of the pivot

# Every parameter away from its default.
BUSY = ["Tilt=-5", "Pivot=300", "Curve=1", "Level=-3"]


def fx(*params):
    return [("tilt", list(params))]


def cli(*params):
    args = ["--fx", "tilt"]
    for p in params:
        args += ["--fx-param", p]
    return args


@pytest.fixture(scope="module")
def tool(renderer):  # noqa: F811 -- the renderer fixture builds everything
    out = subprocess.run([str(TOOL)], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def model_db(tilt, pivot, curve, level, hz, rate=RATE):
    """The design, independently: the bilinear transform, prewarped at the
    pivot, of one first-order tilt section (Shelf) or two staggered ones
    (Slope), evaluated in double on the unit circle."""
    gp = math.tan(math.pi * min(pivot, 0.45 * rate) / rate)
    z1 = cmath.exp(-2j * math.pi * hz / rate)          # z^-1

    def section(t, g):
        lp = g * (1 + z1) / ((1 + g) + (g - 1) * z1)
        return t - (t - 1 / t) * lp

    if curve == 0:
        t = 10 ** (tilt / 20)
        h = section(t, t * gp)
    else:
        t = 10 ** (tilt / 40)
        h = section(t, t * gp / STAGGER) * section(t, t * gp * STAGGER)
    return 20 * math.log10(abs(h)) + level


def straightness(points, pivot):
    """Worst distance in dB of the response from its best straight line (dB
    against octaves, through 0 dB at the pivot), over the given points."""
    xs = [math.log2(f / pivot) for f, _ in points]
    ys = [db for _, db in points]
    slope = sum(x * y for x, y in zip(xs, ys)) / sum(x * x for x in xs)
    return max(abs(y - slope * x) for x, y in zip(xs, ys)), slope


def test_tilt_is_registered(renderer):  # noqa: F811
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True,
                         text=True).stdout
    e = {x["id"]: x for x in json.loads(out)}["tilt"]
    assert (e["name"], e["kind"], e["max_voices"]) == ("Tilt", "audio_fx", 0)
    assert not any(b in (e["id"] + e["name"]).lower() for b in BANNED)
    assert "MIT" in e["credits"]
    assert [p["name"] for p in e["params"] if p["page"] == 0] == ["Tilt", "Pivot", "Curve", "Level"]
    assert all(p["page"] == 0 for p in e["params"])
    p = {x["name"]: x for x in e["params"]}
    assert (p["Tilt"]["min"], p["Tilt"]["max"], p["Tilt"]["def"]) == (-9, 9, 0)
    assert (p["Pivot"]["min"], p["Pivot"]["max"], p["Pivot"]["def"]) == (200, 5000, 1000)
    assert (p["Level"]["min"], p["Level"]["max"], p["Level"]["def"]) == (-24, 12, 0)
    assert p["Curve"]["type"] == 1 and p["Curve"]["names"] == ["Shelf", "Slope"]
    assert p["Pivot"]["unit"] == "hz"


def test_instance_is_small(renderer, tmp_path, tool):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.05, fx=fx())
    assert s["fx_bytes"][0] % 16 == 0 and s["fx_bytes"][0] <= 256
    assert tool["instance_size"] == s["fx_bytes"][0]


# --- host contracts ---------------------------------------------------------

def test_rendering_is_deterministic(renderer, tmp_path):  # noqa: F811
    _, _, a = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY), name="a")
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY), name="b")
    assert a.read_bytes() == b.read_bytes()


def test_block_size_does_not_change_the_output(renderer, tmp_path):  # noqa: F811
    wavs = []
    for frames in ("64", "7", "1"):
        _, _, wav = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY),
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
def test_out_of_range_parameters_clamp(renderer, tmp_path, value, same_as):  # noqa: F811
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True,
                         text=True).stdout
    params = {x["id"]: x for x in json.loads(out)}["tilt"]["params"]
    bad = [f"{p['name']}={value}" for p in params]
    good = [] if same_as is None else [f"{p['name']}={p[same_as]}" for p in params]
    s, _, a = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*bad), name="bad")
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*good), name="good")
    assert s["nonfinite"] == 0
    assert a.read_bytes() == b.read_bytes()


def test_curve_rounds_to_the_nearest_value(renderer, tmp_path):  # noqa: F811
    # An ENUM set between its values (as a rounded modulation route would
    # not, but a careless host might) takes the nearest one.
    _, _, a = render(renderer, tmp_path, input="noise", seconds=0.3, name="a",
                     fx=fx("Tilt=6", "Curve=0.7"))
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.3, name="b",
                     fx=fx("Tilt=6", "Curve=1"))
    _, _, c = render(renderer, tmp_path, input="noise", seconds=0.3, name="c",
                     fx=fx("Tilt=6", "Curve=0.3"))
    _, _, d = render(renderer, tmp_path, input="noise", seconds=0.3, name="d",
                     fx=fx("Tilt=6", "Curve=0"))
    assert a.read_bytes() == b.read_bytes() and c.read_bytes() == d.read_bytes()
    assert a.read_bytes() != c.read_bytes()


@pytest.mark.parametrize("params", [
    [],
    ["Tilt=9", "Pivot=5000", "Curve=1", "Level=12"],
    ["Tilt=-9", "Pivot=200", "Level=-24"],
    BUSY,
])
def test_silence_in_is_silence_out(renderer, tmp_path, params):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.5, fx=fx(*params))
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


BAD_INPUT = {"nan": "nan", "inf": "inf", "huge": "1e30"}


@pytest.mark.parametrize("bad", sorted(BAD_INPUT))
def test_bad_input_is_guarded_and_not_latched(renderer, tmp_path, bad):  # noqa: F811
    # The input guard reads NaN as 0 and clamps everything else to +/-16, so
    # no state is poisoned: half a second after the fault ends the output is
    # the fault-free output, sample for sample.
    base = ["--input", "noise", "--seconds", "1.5", *cli(*BUSY)]
    _, clean_l, clean_r, _ = run(renderer, tmp_path, base, "clean")
    fault = ["--fault", f"0.2..0.5:{BAD_INPUT[bad]}"]
    s, left, right, _ = run(renderer, tmp_path, [*base, *fault], "fault")
    assert s["nonfinite"] == 0
    # The guard's 16, held, through BUSY's gain at DC (+5 dB, Level -3 dB):
    # 20.14 (measured).
    assert s["raw_peak"] < 16 * 10 ** (2 / 20) * 1.001
    tail = slice(RATE, None)
    assert max(abs(a - b) for a, b in zip(left[tail], clean_l[tail])) <= LSB
    assert max(abs(a - b) for a, b in zip(right[tail], clean_r[tail])) <= LSB


def test_nan_input_reads_as_silence(renderer, tmp_path):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY),
                     extra=["--fault", "0..0.5:nan"])
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


@pytest.mark.parametrize("bad", ["inf", "1e30"])
def test_flat_passes_the_clamped_input(renderer, tmp_path, bad):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx("Pivot=200"),
                     extra=["--fault", f"0.1..0.2:{bad}"])
    assert s["nonfinite"] == 0 and s["raw_peak"] == 16.0


@pytest.mark.parametrize("params", [
    [],                                                    # the defaults
    ["Pivot=200", "Curve=1"],
    ["Pivot=5000", "Curve=1"],
    ["Pivot=2500"],
])
def test_flat_is_the_input_exactly(renderer, tmp_path, params):  # noqa: F811
    # Tilt 0 and Level 0 dB: the output is the input, whatever the Pivot and
    # the Curve (fm1-tilt-test checks it bit for bit in float; here the
    # renderer's peak, a float, and its WAV).
    ref, _, ref_wav = render(renderer, tmp_path, input="noise", seconds=1.0,
                             fx=[("test-gain", ["Gain=1"])], name="ref")
    out, _, out_wav = render(renderer, tmp_path, input="noise", seconds=1.0, fx=fx(*params),
                             name="flat")
    assert out["raw_peak"] == ref["raw_peak"]
    assert out_wav.read_bytes() == ref_wav.read_bytes()


# --- every knob does what it says ---------------------------------------------

def test_tilt_brightens_and_darkens(renderer, tmp_path):  # noqa: F811
    bright = {}
    for tilt in ("-9", "0", "9"):
        _, left, _ = render(renderer, tmp_path, input="noise", seconds=0.5, name=f"t{tilt}",
                            fx=fx(f"Tilt={tilt}", "Level=-9"))
        bright[tilt] = brightness(left, 0.1, 0.5)
    # White noise scores sqrt(2) = 1.41; measured 0.90, 1.41, 1.52.
    assert bright["0"] == pytest.approx(math.sqrt(2), abs=0.01)
    assert bright["-9"] < 0.75 * bright["0"] < bright["9"]


@pytest.mark.parametrize("params", [
    ["Tilt=9"], ["Tilt=-9"], ["Tilt=9", "Curve=1"], ["Tilt=-9", "Curve=1"],
])
def test_the_pivot_stays_at_unity(renderer, tmp_path, params):  # noqa: F811
    # The renderer's sine is 440 Hz: with the pivot there it passes at 0 dB
    # whatever the tilt (a phase shift only).
    _, dry, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="dry",
                       fx=[("test-gain", ["Gain=1"])])
    _, wet, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="wet",
                       fx=fx(*params, "Pivot=440"))
    assert rms(wet, 0.2, 1.0) / rms(dry, 0.2, 1.0) == pytest.approx(1.0, abs=5e-4)


def test_level_scales_the_output(renderer, tmp_path):  # noqa: F811
    _, full, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="full",
                        fx=fx("Tilt=4"))
    _, half, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="half",
                        fx=fx("Tilt=4", "Level=-6.0206"))
    assert rms(half, 0.2, 1.0) / rms(full, 0.2, 1.0) == pytest.approx(0.5, abs=5e-4)


def test_after_an_engine_and_before_a_reverb(renderer, tmp_path):  # noqa: F811
    summary, left, right, _ = run(
        renderer, tmp_path,
        ["--engine", "macro", "--param", "Model=0", "--note", "0:45:100:0.5",
         "--note", "0:52:100:0.5", "--seconds", "1.5", *cli("Tilt=6", "Curve=1"),
         "--fx", "plate", "--fx-param", "Mix=0.3"], "chain")
    assert summary["fx"] == ["tilt", "plate"]
    assert summary["nonfinite"] == 0
    assert rms(left, 0.1, 0.5) > 1e-2 and rms(left, 1.0, 1.4) > 1e-4


# --- fm1-tilt-test: the response, in float ------------------------------------

def test_response_matches_the_design(tool):
    # 38 settings: Tilt +/-3, 6 and 9 at pivots of 200 Hz, 1 kHz and 5 kHz,
    # both curves, and one with Level -6 dB; 18 frequencies each, DC and
    # Nyquist included. The model is the design's own equations in double;
    # the effect runs in float, with libm-free tan and exponentials.
    worst = 0.0
    for r in tool["response"]:
        assert r["stereo"] and r["tail"] < 1e-12
        for hz, db in r["db"]:
            want = model_db(r["tilt"], r["pivot"], r["curve"], r["level"], hz)
            worst = max(worst, abs(db - want))
    assert worst < 1e-4                    # measured 4.7e-6 dB


def test_pivot_dc_and_nyquist_are_exact(tool):
    for r in tool["response"]:
        level = r["level"]
        db = dict((round(f), v) for f, v in r["db"])
        assert r["pivot_db"] == pytest.approx(level, abs=1e-4), r
        assert db[0] == pytest.approx(level - r["tilt"], abs=1e-4), r
        assert db[round(RATE / 2)] == pytest.approx(level + r["tilt"], abs=1e-4), r


def test_slope_is_straighter_and_gentler_than_shelf(tool):
    # From 200 Hz to 5 kHz about 1 kHz at +/-9 dB: Slope stays within 0.13 dB
    # of a straight line (2.9 dB an octave), Shelf strays by 1.1 dB (3.8 dB
    # an octave, levelling off at the ends).
    for tilt in (9, -9):
        rows = {r["curve"]: r for r in tool["response"]
                if r["tilt"] == tilt and r["pivot"] == 1000 and r["level"] == 0}
        band = {c: [(f, db) for f, db in rows[c]["db"] if 200 <= f <= 5000] for c in (0, 1)}
        slope_dev, slope = straightness(band[1], 1000)
        shelf_dev, shelf = straightness(band[0], 1000)
        assert slope_dev < 0.13 and shelf_dev > 0.7      # nine measured points
        # Finely, on the model the effect matches (test_response_matches_the_design):
        fine = [200 * 25 ** (i / 80) for i in range(81)]
        fit = [straightness([(f, model_db(tilt, 1000, c, 0, f)) for f in fine], 1000)
               for c in (0, 1)]
        assert fit[1][0] < 0.13 and fit[0][0] > 1.05      # 0.12 and 1.10 dB
        assert abs(fit[1][1]) == pytest.approx(2.9, abs=0.05)
        assert abs(fit[0][1]) == pytest.approx(3.85, abs=0.05)
        assert 0 < slope / shelf < 0.85 and (slope > 0) == (tilt > 0)


def test_the_stagger_is_the_straightest(tool):
    # Over staggers of 0.6 to 2 octaves, 1.5 octaves (2^1.5) keeps the Slope
    # curve straightest from 200 Hz to 5 kHz at +/-9 dB about 1 kHz (the
    # search behind the constant, rerun on the model).
    def dev(r):
        pts = []
        for i in range(41):
            f = 200 * 25 ** (i / 40)
            t = 10 ** (9 / 40)
            gp = math.tan(math.pi * 1000 / RATE)
            z1 = cmath.exp(-2j * math.pi * f / RATE)
            h = 1
            for g in (t * gp / r, t * gp * r):
                h *= t - (t - 1 / t) * g * (1 + z1) / ((1 + g) + (g - 1) * z1)
            pts.append((f, 20 * math.log10(abs(h))))
        return straightness(pts, 1000)[0]
    candidates = [2 ** (k / 20) for k in range(12, 41)]
    best = min(candidates, key=dev)
    assert abs(math.log2(best) - 1.5) <= 0.1


# --- fm1-tilt-test: the bypass, changes while it runs -------------------------

def test_flat_is_bit_exact_in_float(tool):
    # Random floats, +/-0, subnormals and values near the guard, at random
    # block sizes, through four flat settings: not one bit differs.
    b = tool["bypass"]
    assert b["mismatches"] == [0, 0, 0, 0]
    # Moved away (Tilt +9, Slope, Pivot 300, Level -5) and back to Tilt 0 and
    # Level 0: once the glide lands the output is the input again, bit for
    # bit (measured 36 ms after the change).
    assert b["away_moved"] and b["tail_mismatches"] == 0
    assert 0 < b["exact_again_after_ms"] < 50


def test_glide_is_block_size_independent(tool):
    assert tool["glide"]["block_independent"]


@pytest.mark.parametrize("jump", ["tilt", "pivot", "curve", "curve_back", "level"])
def test_jumps_do_not_click(tool, jump):
    # One control turned end to end in one step while a sine plays. A hard
    # switch between the two steady outputs puts a step in the waveform. The
    # glide keeps the output's second difference (its curvature, which a
    # click or a kink drives up) within 1.6 times the steady sine's own, its
    # excess over the steady sine under a tenth of the hard switch's, and
    # 50 ms later the output is the new setting's.
    j = tool["jumps"][jump]
    assert j["ours"] <= 1.6 * j["steady"]
    assert j["hard"] - j["steady"] > 10 * max(0.0, j["ours"] - j["steady"])
    assert j["settled_err"] < 1e-6


def test_modulation_at_the_matrix_rate_has_no_zipper(tool):
    # Tilt swept end to end at 1 Hz, set every 32 frames as the modulation
    # matrix will, over a 100 Hz sine: the third difference (zipper noise
    # would show there) is the same as with Tilt set every frame, the sine's
    # own floor (-110.7 dB).
    z = tool["zipper"]
    assert z["every_1"] < -110
    assert z["every_32"] < z["every_1"] + 0.5


def test_any_parameter_change_mid_stream_stays_finite(tool):
    # 20 s of noise; between blocks of 1-64 frames, up to two parameters jump
    # to their minimum, maximum, default, a random value, beyond the range,
    # NaN or an infinity. The output is bounded by the gain at the top (+9 dB)
    # times Level's (+12 dB) and the filters' overshoot: measured 12.2 times
    # the input's peak, at 0.5 and at the guard's 16.
    for name, amplitude in (("sweep", 0.5), ("sweep_hot", 16.0)):
        s = tool[name]
        assert s["samples"] > 20 * RATE
        assert s["nonfinite"] == 0 and s["peak"] < 13 * amplitude


def test_silence_and_tails(tool):
    s = tool["silence"]
    assert s["moving_peak"] == 0.0         # silence in, exact silence out, while it moves
    assert 0 < s["zero_after_ms"] < 250    # the slowest tail flushes (measured 160 ms)
    assert s["last_block_peak"] == 0.0


def test_host_rates(tool):
    accepted = {rate: (ok, finite) for rate, ok, finite in tool["rates"]}
    assert {r: ok for r, (ok, _) in accepted.items()} == {
        "0": False, "7999": False, "8000": True, "44118": True, "48000": True, "96000": True,
        "384000": True, "400000": False, "nan": False, "inf": False, "-44118": False}
    assert all(finite for _, finite in accepted.values())
