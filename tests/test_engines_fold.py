"""Tests for Fold, the wavefolder effect (engines/src/fx_fold.cc, parameters
in engines/README.md, "Fold").

Through fm1-render: registration and pages, the host contracts (deterministic
renders, any block size, any prior memory contents, any parameter value,
NaN included, bad input guarded and not latched, silence in gives silence
out), every parameter doing what it says, and aliasing against a plain
per-sample fold of the same sine. Through fm1-fold-test
(engines/test/fold_test.cc): parameters changed while audio runs, with block
sizes that change between calls, the glide, and the host rates it accepts.
"""
import json
import math
import subprocess

import pytest

from tests.engine_helpers import ENGINES, RATE, render, renderer, rms  # noqa: F401
from tests.test_engines_mi_fx import BANNED, brightness, correlation, run

TOOL = ENGINES / "build" / "fm1-fold-test"
LSB = 1 / 32767.0

# Every parameter away from its default, Mix included.
BUSY = ["Fold=0.8", "Symmetry=0.35", "Shape=0.4", "Mix=0.8", "Tone=0.6", "Level=0.9"]


def fx(*params):
    return [("fold", list(params))]


def cli(*params):
    args = ["--fx", "fold"]
    for p in params:
        args += ["--fx-param", p]
    return args


def goertzel(seg, hz):
    """Amplitude squared of the component at hz (an exact bin of seg)."""
    w = 2 * math.pi * hz / RATE
    c = 2 * math.cos(w)
    s1 = s2 = 0.0
    for x in seg:
        s1, s2 = x + c * s1 - s2, s1
    re, im = s1 - s2 * math.cos(w), s2 * math.sin(w)
    return (re * re + im * im) / (len(seg) / 2) ** 2


def steady(samples):
    """0.5 to 1.0 s: 220 whole cycles of the renderer's 440 Hz sine, so every
    harmonic and every alias of one falls on an exact bin (2 Hz apart)."""
    return samples[RATE // 2:RATE]


@pytest.fixture(scope="module")
def tool(renderer):  # noqa: F811 -- the renderer fixture builds everything
    out = subprocess.run([str(TOOL)], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def test_fold_is_registered(renderer):  # noqa: F811
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True,
                         text=True).stdout
    e = {x["id"]: x for x in json.loads(out)}["fold"]
    assert (e["name"], e["kind"], e["max_voices"]) == ("Fold", "audio_fx", 0)
    assert not any(b in (e["id"] + e["name"]).lower() for b in BANNED)
    assert "MIT" in e["credits"] and "Parker" in e["credits"]
    pages = [[p["name"] for p in e["params"] if p["page"] == k] for k in (0, 1)]
    assert pages == [["Fold", "Symmetry", "Shape", "Mix"], ["Tone", "Level"]]
    assert all(len(p["name"]) <= 12 and p["type"] == 0 for p in e["params"])
    assert all(p["min"] <= p["def"] <= p["max"] for p in e["params"])


def test_instance_is_small(renderer, tmp_path):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.05, fx=fx())
    assert s["fx_bytes"][0] % 16 == 0 and s["fx_bytes"][0] <= 256


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
    params = {x["id"]: x for x in json.loads(out)}["fold"]["params"]
    bad = [f"{p['name']}={value}" for p in params]
    good = [] if same_as is None else [f"{p['name']}={p[same_as]}" for p in params]
    s, _, a = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*bad), name="bad")
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*good), name="good")
    assert s["nonfinite"] == 0
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("params", [
    [],
    ["Symmetry=1", "Shape=0.3", "Fold=1"],
    ["Symmetry=-0.6", "Shape=1", "Tone=0", "Level=1"],
    ["Symmetry=0.25", "Shape=0.5", "Mix=0.5"],
])
def test_silence_in_is_silence_out(renderer, tmp_path, params):  # noqa: F811
    # The fold of silence is f(Symmetry), not 0; the effect subtracts it,
    # computed by the same code on the same values, so the difference is
    # exactly zero rather than a DC step for the blocker to remove.
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.5, fx=fx(*params))
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


BAD_INPUT = {"nan": "nan", "inf": "inf", "huge": "1e30"}


@pytest.mark.parametrize("bad", sorted(BAD_INPUT))
def test_bad_input_is_guarded_and_not_latched(renderer, tmp_path, bad):  # noqa: F811
    # The input guard reads NaN as 0 and clamps everything else to +/-16, the
    # dry path included, so no state is poisoned: half a second after the
    # fault ends the output is the fault-free output, sample for sample.
    base = ["--input", "noise", "--seconds", "1.5", *cli(*BUSY)]
    _, clean_l, clean_r, _ = run(renderer, tmp_path, base, "clean")
    fault = ["--fault", f"0.2..0.5:{BAD_INPUT[bad]}"]
    s, left, right, _ = run(renderer, tmp_path, [*base, *fault], "fault")
    assert s["nonfinite"] == 0
    assert s["raw_peak"] < 4.5
    tail = slice(RATE, None)
    assert max(abs(a - b) for a, b in zip(left[tail], clean_l[tail])) <= LSB
    assert max(abs(a - b) for a, b in zip(right[tail], clean_r[tail])) <= LSB


def test_nan_input_reads_as_silence(renderer, tmp_path):  # noqa: F811
    s, left, _ = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx("Symmetry=0.5"),
                        extra=["--fault", "0..0.5:nan"])
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


@pytest.mark.parametrize("bad", ["inf", "1e30"])
def test_mix_zero_passes_the_clamped_input(renderer, tmp_path, bad):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx("Mix=0", "Fold=1"),
                     extra=["--fault", f"0.1..0.2:{bad}"])
    assert s["nonfinite"] == 0 and s["raw_peak"] == 16.0


def test_mix_zero_passes_the_input_through(renderer, tmp_path):  # noqa: F811
    ref, _, ref_wav = render(renderer, tmp_path, input="noise", seconds=1.0,
                             fx=[("test-gain", ["Gain=1"])], name="ref")
    out, _, out_wav = render(renderer, tmp_path, input="noise", seconds=1.0,
                             fx=fx(*BUSY[:3], "Mix=0", *BUSY[4:]), name="dry")
    assert out["raw_peak"] == ref["raw_peak"]
    assert out_wav.read_bytes() == ref_wav.read_bytes()


# --- every knob does what it says ---------------------------------------------

def test_fold_zero_is_nearly_transparent(renderer, tmp_path):  # noqa: F811
    # Gain 1 keeps the 0.5 sine inside the triangle's straight segment: the
    # wet path is the input, less ADAA's half-sample average (cos(pi f / fs):
    # -0.004 dB at 440 Hz) and the open tone filter. Together they delay it
    # by about a quarter of a sample (the filter near Nyquist leads a little).
    _, dry, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="dry",
                       fx=[("test-gain", ["Gain=1"])])
    _, wet, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="wet",
                       fx=fx("Fold=0", "Shape=0", "Tone=1", "Level=1"))
    assert rms(wet, 0.5, 1.0) / rms(dry, 0.5, 1.0) == pytest.approx(1.0, abs=0.01)
    assert correlation(steady(wet), steady(dry)) > 0.9995


def test_fold_adds_harmonics(renderer, tmp_path):  # noqa: F811
    bright = []
    for amount in ("0", "0.5", "1"):
        _, left, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name=f"fold{amount}",
                            fx=fx(f"Fold={amount}", "Tone=1"))
        bright.append(brightness(left, 0.5, 1.0))
    # A 440 Hz sine scores 2 sin(pi 440 / 44118) = 0.063; folds raise it.
    assert bright[0] == pytest.approx(0.0627, abs=0.002)
    assert bright[0] * 2 < bright[1] < bright[2]   # measured 0.063, 0.170, 0.593


def test_symmetry_adds_even_harmonics(renderer, tmp_path):  # noqa: F811
    ratios = {}
    for sym in ("0", "0.5", "-0.5"):
        _, left, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name=f"sym{sym}",
                            fx=fx("Fold=0.5", f"Symmetry={sym}", "Tone=1"))
        seg = steady(left)
        ratios[sym] = 10 * math.log10(goertzel(seg, 880) / goertzel(seg, 440))
    # Both curves are odd functions: an unshifted fold of a sine has no even
    # harmonics (only the 16-bit floor). Offsetting it makes them.
    assert ratios["0"] < -70
    assert ratios["0.5"] > -30 and ratios["-0.5"] > -30


def test_shape_rounds_the_fold(renderer, tmp_path):  # noqa: F811
    bright = []
    for shape in ("0", "0.5", "1"):
        _, left, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name=f"shape{shape}",
                            fx=fx("Fold=0.6", f"Shape={shape}", "Tone=1"))
        bright.append(brightness(left, 0.5, 1.0))
    assert bright[0] > bright[1] > bright[2]       # measured 0.217, 0.204, 0.199


def test_tone_darkens_the_fold(renderer, tmp_path):  # noqa: F811
    bright = []
    for tone in ("1", "0.5", "0"):
        _, left, _ = render(renderer, tmp_path, input="noise", seconds=0.5, name=f"tone{tone}",
                            fx=fx("Fold=0.8", f"Tone={tone}"))
        bright.append(brightness(left, 0.1, 0.5))
    assert bright[0] > bright[1] > bright[2]       # measured 1.20, 0.242, 0.030
    assert bright[2] < 0.2 * bright[0]


def test_level_scales_the_wet_signal(renderer, tmp_path):  # noqa: F811
    _, full, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="full",
                        fx=fx("Fold=0.7", "Level=1"))
    _, half, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="half",
                        fx=fx("Fold=0.7", "Level=0.5"))
    s, _, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="none",
                     fx=fx("Fold=0.7", "Level=0"))
    assert rms(half, 0.2, 1.0) / rms(full, 0.2, 1.0) == pytest.approx(0.5, rel=0.002)
    assert s["raw_peak"] == 0.0                          # Mix 1, Level 0: nothing


def test_mix_blends_dry_and_wet(renderer, tmp_path):  # noqa: F811
    common = ["Fold=0.7", "Tone=1", "Level=1"]
    _, dry, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="m0",
                       fx=fx(*common, "Mix=0"))
    _, wet, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="m1",
                       fx=fx(*common, "Mix=1"))
    _, mid, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="m5",
                       fx=fx(*common, "Mix=0.5"))
    worst = max(abs(m - 0.5 * (d + w)) for m, d, w in zip(mid, dry, wet))
    assert worst <= 1.5 * LSB


# --- aliasing ---------------------------------------------------------------

def alias_bins(band=5000.0, kmax=1000):
    """Where harmonics 1..kmax of 440 Hz land once reflected about the
    output's Nyquist, below band and off the harmonics themselves."""
    out = set()
    for k in range(1, kmax + 1):
        f = (440 * k) % RATE
        if f > RATE / 2:
            f = RATE - f
        if 20 < f < band and f % 440:
            out.add(f)
    return sorted(out)


def alias_db(samples):
    seg = steady(samples)
    return 10 * math.log10(sum(goertzel(seg, f) for f in alias_bins()) / goertzel(seg, 440))


@pytest.mark.parametrize("amount,naive_db,margin,ceiling", [
    # Measured (2026-10-02): the triangle fold of the renderer's 0.5 sine,
    # aliases below 5 kHz against the fundamental: -75.3 dB here against
    # -51.8 dB for a plain per-sample fold at Fold 0.5 (gain 4), and -49.5
    # against -28.5 dB at Fold 1 (gain 16).
    ("0.5", -51.8, 20, -70),
    ("1", -28.5, 18, -45),
])
def test_antialiasing_beats_a_plain_fold(renderer, tmp_path, amount, naive_db, margin,
                                         ceiling):  # noqa: F811
    gain = 2 ** (4 * float(amount))

    def tri(u):
        s = ((u + 1) % 4) - 2
        return 1 - abs(s)

    plain = [tri(gain * 0.5 * math.sin(2 * math.pi * 440 * n / RATE)) for n in range(RATE)]
    _, left, _ = render(renderer, tmp_path, input="sine", seconds=1.0,
                        fx=fx(f"Fold={amount}", "Shape=0", "Tone=1", "Level=0.5"))
    ours, theirs = alias_db(left), alias_db(plain)
    assert theirs == pytest.approx(naive_db, abs=1.0)
    assert ours < theirs - margin and ours < ceiling


def test_sine_shape_of_a_sine_does_not_alias(renderer, tmp_path):  # noqa: F811
    # sin(pi g x / 2) of a sine is a Bessel series that has died out long
    # before Nyquist at 440 Hz: nothing to alias even at Fold 1.
    _, left, _ = render(renderer, tmp_path, input="sine", seconds=1.0,
                        fx=fx("Fold=1", "Shape=1", "Tone=1", "Level=0.5"))
    assert alias_db(left) < -90


def test_after_an_engine_and_before_a_reverb(renderer, tmp_path):  # noqa: F811
    summary, left, right, _ = run(
        renderer, tmp_path,
        ["--engine", "macro", "--param", "Model=0", "--note", "0:45:100:0.5",
         "--note", "0:52:100:0.5", "--seconds", "1.5", *cli("Fold=0.7", "Symmetry=0.2"),
         "--fx", "plate", "--fx-param", "Mix=0.3"], "chain")
    assert summary["fx"] == ["fold", "plate"]
    assert summary["nonfinite"] == 0
    assert rms(left, 0.1, 0.5) > 1e-2 and rms(left, 1.0, 1.4) > 1e-4


# --- fm1-fold-test: what fm1-render cannot drive ---------------------------------

def test_any_parameter_change_mid_stream_stays_finite(tool):
    # 20 s of noise; between blocks of 1-64 frames, up to two parameters jump
    # to their minimum, maximum, default, a random value, beyond the range,
    # NaN or an infinity. The bound: |wet| <= 2 (fold minus the fold of
    # silence) x 2 (the DC blocker's gain at worst) x 1.05 (the low-pass's
    # overshoot), at Level 1.
    s = tool["sweep"]
    assert s["samples"] > 20 * RATE
    assert s["nonfinite"] == 0 and s["peak"] < 4.2


def test_glide_is_block_size_independent_and_reaches_its_target(tool):
    g = tool["glide"]
    assert g["block_independent"]
    # Level 1 -> 0 (and Mix 0.6 -> 1) fades over ~5 ms instead of cutting:
    # within the first millisecond the output is still there...
    assert g["first_ms"] > 0.25 * g["before"]
    # ...and 50 ms later the glide has snapped to its target: exact silence.
    assert g["tail"] == 0.0


def test_moving_symmetry_does_not_thump(tool):
    s = tool["silence"]
    assert s["moving_peak"] < 0.01       # f(Symmetry) alone would step by up to 1
    assert s["settled_peak"] < 1e-5      # the DC blocker's tail, 145 ms on
    assert s["last_block_peak"] == 0.0   # flushed: no subnormals, exact silence


def test_host_rates(tool):
    accepted = {rate: ok for rate, ok in tool["rates"]}
    assert accepted == {"0": False, "7999": False, "8000": True, "44118": True,
                        "48000": True, "96000": True, "384000": True, "400000": False,
                        "nan": False, "inf": False, "-44118": False}
