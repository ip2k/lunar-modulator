"""Tests for Drive, the overdrive and saturation effect (engines/src/fx_drive.cc,
parameters in engines/README.md, "Drive").

The curves: engines/src/fx_drive.cc holds each Type's curve as a table of
quintic pieces generated here from the knots below (`python -m
tests.test_engines_drive` prints it); test_curve_table_is_the_documented_design
checks the source against them.

Through fm1-render: registration and pages, the host contracts (deterministic
renders, any block size, any prior memory contents, any parameter value,
NaN included, bad input guarded and not latched, silence in gives silence
out), and every parameter doing what it says. Through fm1-drive-test
(engines/test/drive_test.cc), which includes the effect's source to reach
its curves: the curves' shapes and continuity, the anti-aliased mean against
quadrature, aliasing against a plain per-sample curve, the tape emphasis,
parameters and Types changed while audio runs, the glide, and host rates.
"""
import json
import math
import re
import struct
import subprocess
from fractions import Fraction

import pytest

from tests.engine_helpers import ENGINES, RATE, render, renderer, rms  # noqa: F401
from tests.test_engines_mi_fx import BANNED, brightness, correlation, run

TOOL = ENGINES / "build" / "fm1-drive-test"
SOURCE = ENGINES / "src" / "fx_drive.cc"
LSB = 1 / 32767.0
TYPES = ["Soft", "Tube", "Diode", "Fuzz", "Tape"]

# --- the design ---------------------------------------------------------------

# Knots (x, f, f', f'') of each Type's curve, in its order: between knots a
# quintic Hermite piece, beyond the outer knots the constant there. Fuzz's
# outer slopes of 1 make corners (a hard clip); every other curve is C2.
KNOTS = [
    ("Soft", ["-2.5", "-1", "0", "0"], ["0", "0", "1", "0"], ["2.5", "1", "0", "0"]),
    ("Tube", ["-1.6", "-0.8", "0", "0"], ["0", "0", "1", "0.3"], ["2.2", "1", "0", "0"]),
    ("Diode", ["-1.35", "-1", "0", "0"], ["-0.6", "-0.6", "1", "0"], ["0.6", "0.6", "1", "0"],
     ["1.35", "1", "0", "0"]),
    ("Fuzz", ["-1", "-1", "1", "0"], ["1", "1", "1", "0"]),
    ("Tape", ["-5", "-2", "0", "0"], ["0", "0", "1", "0"], ["5", "2", "0", "0"]),
]
# Each Type's own dead zone and offset, added to Gate's and Bias's.
OWN = {"Fuzz": ("0.04", "0.25")}


def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def quintic(k0, k1):
    """The quintic q_0..q_5 in t = (v - x0) / w that has k0's value, slope and
    curvature at t = 0 and k1's at t = 1 (exact, in fractions)."""
    (x0, f0, d0, s0), (x1, f1, d1, s1) = [[Fraction(v) for v in k] for k in (k0, k1)]
    w = x1 - x0
    q0, q1, q2 = f0, w * d0, w * w * s0 / 2
    r0, r1, r2 = f1 - q0 - q1 - q2, w * d1 - q1 - 2 * q2, w * w * s1 - 2 * q2
    q5 = (r2 + 12 * r0 - 6 * r1) / 2
    q4 = r1 - 3 * r0 - 2 * q5
    q3 = r0 - q4 - q5
    return w, [q0, q1, q2, q3, q4, q5]


def curve(name):
    """The table row of fx_drive.cc's DriveCurve for one Type, as exact
    fractions: n, x[4], lo, hi, inv_w[3], r[3][6], area[3], gate, bias."""
    knots = next(k[1:] for k in KNOTS if k[0] == name)
    n = len(knots)
    xs = [Fraction(k[0]) for k in knots] + [Fraction(0)] * (4 - n)
    inv_w, r, area = [], [], []
    for j in range(n - 1):
        w, q = quintic(knots[j], knots[j + 1])
        rj = [qk / (k + 1) for k, qk in enumerate(q)]
        inv_w.append(1 / w)
        r.append(rj)
        area.append(w * sum(rj))
    while len(r) < 3:
        inv_w.append(Fraction(0))
        r.append([Fraction(0)] * 6)
        area.append(Fraction(0))
    gate, bias = (Fraction(v) for v in OWN.get(name, ("0", "0")))
    return {"n": n, "x": xs, "lo": Fraction(knots[0][1]), "hi": Fraction(knots[-1][1]),
            "inv_w": inv_w, "r": r, "area": area, "gate": gate, "bias": bias}


def quad_sines():
    """sin((k + 0.5) pi / 32), k = 0..15: Auto's quadrature."""
    return [math.sin((k + 0.5) * math.pi / 32) for k in range(16)]


def c_float(x):
    v = f32(x)
    if v == int(v) and abs(v) < 1e6:
        return f"{v:.1f}f"
    return f"{float(f'{v:.9g}')!r}f".replace("e-0", "e-")


def c_curves():
    """The C initialiser of kCurves, as fx_drive.cc holds it."""
    rows = []
    for name, *_ in KNOTS:
        c = curve(name)
        vals = lambda xs: ", ".join(c_float(v) for v in xs)  # noqa: E731
        rs = ",\n      ".join("{ %s }" % vals(rj) for rj in c["r"])
        rows.append(f"  {{ {c['n']}, {{ {vals(c['x'])} }}, {c_float(c['lo'])}, {c_float(c['hi'])}, "
                    f"{{ {vals(c['inv_w'])} }},\n    {{ {rs} }},\n"
                    f"    {{ {vals(c['area'])} }}, {c_float(c['gate'])}, {c_float(c['bias'])} }},")
    return "static const DriveCurve kCurves[T_COUNT] = {\n" + "\n".join(rows) + "\n};"


def c_quad():
    vals = [c_float(v) for v in quad_sines()]
    lines = ["  " + ", ".join(vals[i:i + 6]) + "," for i in range(0, 16, 6)]
    return "static const float kQuadSin[16] = {\n" + "\n".join(lines) + "\n};"


def evaluate(name, v):
    """The curve, plainly evaluated (double precision): for the checks."""
    c = curve(name)
    n, xs = c["n"], [float(x) for x in c["x"]]
    if v < xs[0]:
        return float(c["lo"])
    if v >= xs[n - 1]:
        return float(c["hi"])
    j = max(i for i in range(n - 1) if v >= xs[i])
    t = (v - xs[j]) * float(c["inv_w"][j])
    return sum(float(rk) * (k + 1) * t ** k for k, rk in enumerate(c["r"][j]))



def test_curve_table_is_the_documented_design():
    """fx_drive.cc's kCurves and kQuadSin are what the knots above generate,
    to the last bit of every float."""
    src = SOURCE.read_text()
    for gen, start in ((c_curves(), "static const DriveCurve kCurves"),
                       (c_quad(), "static const float kQuadSin")):
        body = src[src.index(start):]
        body = body[:body.index("\n};") + 3]
        number = r"-?\d+(?:\.\d*)?(?:e-?\d+)?f"
        have = [f32(x[:-1]) for x in re.findall(number, body.split("=", 1)[1])]
        want = [f32(x[:-1]) for x in re.findall(number, gen.split("=", 1)[1])]
        ints = r"(?<=\{ )\d(?=, \{)"
        assert re.findall(ints, body) == re.findall(ints, gen)
        assert have == want


# --- the curves, from the design (exact fractions) -----------------------------

def piece_derivatives(c, j, t):
    """Value, slope and curvature (per unit of v) of piece j at t, exactly."""
    q = [rk * (k + 1) for k, rk in enumerate(c["r"][j])]
    iw = c["inv_w"][j]
    value = sum(qk * t ** k for k, qk in enumerate(q))
    slope = sum(k * qk * t ** (k - 1) for k, qk in enumerate(q) if k >= 1) * iw
    curv = sum(k * (k - 1) * qk * t ** (k - 2) for k, qk in enumerate(q) if k >= 2) * iw * iw
    return value, slope, curv


@pytest.mark.parametrize("name", TYPES)
def test_curves_are_continuous_and_monotonic(name):
    """Every curve is C2 everywhere (Fuzz C0 at its two corners, by design),
    meets its ceilings exactly at the outer knots, and never falls."""
    c = curve(name)
    n = c["n"]
    inner = n - 1
    # Outer knots: the constants, flat (Fuzz: a corner, slope 1 inside).
    first, last = piece_derivatives(c, 0, 0), piece_derivatives(c, inner - 1, 1)
    assert first[0] == c["lo"] and last[0] == c["hi"]
    if name == "Fuzz":
        assert first[1] == last[1] == 1 and first[2] == last[2] == 0
    else:
        assert first[1:] == (0, 0) and last[1:] == (0, 0)
    # Inner knots: value, slope and curvature agree on both sides.
    for j in range(inner - 1):
        assert piece_derivatives(c, j, 1) == piece_derivatives(c, j + 1, 0)
    # Never falling: the slope sampled finely across every piece.
    for j in range(inner):
        assert min(piece_derivatives(c, j, Fraction(i, 400))[1] for i in range(401)) >= 0


def test_curve_shapes():
    # Soft: tanh-like, within 0.047 of tanh everywhere (0.046 at u = 1.49,
    # where it bends a little sooner).
    worst = max(abs(evaluate("Soft", u / 100) - math.tanh(u / 100)) for u in range(-400, 401))
    assert worst < 0.047
    # Soft, Diode, Tape and Fuzz are odd; Tube is not: a curvature of 0.3 at
    # 0, and ceilings of +1 and -0.8.
    for name in ("Soft", "Diode", "Tape", "Fuzz"):
        assert all(evaluate(name, -u / 50) == pytest.approx(-evaluate(name, u / 50), abs=1e-12)
                   for u in range(200))
    assert piece_derivatives(curve("Tube"), 1, 0) == (0, 1, Fraction("0.3"))
    assert evaluate("Tube", 3) == 1 and evaluate("Tube", -3) == -0.8
    assert evaluate("Tube", 1) + evaluate("Tube", -1) > 0.09         # 0.823 against -0.724
    # Diode: linear to 0.6, then a knee to 1 at 1.35; harder than Soft.
    assert evaluate("Diode", 0.5) == pytest.approx(0.5, abs=1e-12)
    assert evaluate("Diode", 1.35) == 1
    assert evaluate("Diode", 1) > evaluate("Soft", 1) + 0.1          # 0.931 against 0.793
    # Tape: Soft at twice the scale, 6 dB more headroom.
    assert all(evaluate("Tape", u / 25) == pytest.approx(2 * evaluate("Soft", u / 50), abs=1e-12)
               for u in range(-200, 201))


# --- the effect through fm1-render ----------------------------------------------

# Every parameter away from its default, Mix included.
BUSY = ["Type=1", "Drive=24", "Tone=0.35", "Mix=0.8", "Bias=0.3", "Gate=0.15", "Level=-3",
        "Auto=0"]


def fx(*params):
    return [("drive", list(params))]


def cli(*params):
    args = ["--fx", "drive"]
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
    re_, im = s1 - s2 * math.cos(w), s2 * math.sin(w)
    return (re_ * re_ + im * im) / (len(seg) / 2) ** 2


def steady(samples):
    """0.5 to 1.0 s: 220 whole cycles of the renderer's 440 Hz sine."""
    return samples[RATE // 2:RATE]


def db(x):
    return 20 * math.log10(x)


REF_RMS = 0.5 / math.sqrt(2)      # the renderer's sine


@pytest.fixture(scope="module")
def tool(renderer):  # noqa: F811 -- the renderer fixture builds everything
    out = subprocess.run([str(TOOL)], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


@pytest.fixture(scope="module")
def listed(renderer):  # noqa: F811
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True,
                         text=True).stdout
    return {x["id"]: x for x in json.loads(out)}["drive"]


def test_drive_is_registered(listed):
    e = listed
    assert (e["name"], e["kind"], e["max_voices"]) == ("Drive", "audio_fx", 0)
    assert not any(b in (e["id"] + e["name"]).lower() for b in BANNED)
    assert "MIT" in e["credits"] and "Parker" in e["credits"]
    pages = [[p["name"] for p in e["params"] if p["page"] == k] for k in (0, 1)]
    assert pages == [["Type", "Drive", "Tone", "Mix"], ["Bias", "Gate", "Level", "Auto"]]
    by_name = {p["name"]: p for p in e["params"]}
    assert by_name["Type"]["names"] == TYPES
    assert by_name["Auto"]["names"] == ["Off", "On"]
    assert all(len(p["name"]) <= 12 for p in e["params"])
    assert all(p["min"] <= p["def"] <= p["max"] for p in e["params"])
    assert (by_name["Drive"]["min"], by_name["Drive"]["max"]) == (-12, 36)
    assert (by_name["Level"]["min"], by_name["Level"]["max"]) == (-24, 12)


def test_instance_is_small(renderer, tmp_path):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.05, fx=fx())
    assert s["fx_bytes"][0] % 16 == 0 and s["fx_bytes"][0] <= 256


# --- host contracts ---------------------------------------------------------

def test_rendering_is_deterministic(renderer, tmp_path):  # noqa: F811
    _, _, a = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY), name="a")
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY), name="b")
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("kind", range(5))
def test_block_size_does_not_change_the_output(renderer, tmp_path, kind):  # noqa: F811
    wavs = []
    for frames in ("64", "7", "1"):
        _, _, wav = render(renderer, tmp_path, input="noise", seconds=0.5,
                           fx=fx(*BUSY, f"Type={kind}"), name=f"f{frames}",
                           extra=["--frames", frames])
        wavs.append(wav.read_bytes())
    assert wavs[0] == wavs[1] == wavs[2]


@pytest.mark.parametrize("kind", range(5))
def test_output_ignores_initial_memory(renderer, tmp_path, kind):  # noqa: F811
    wavs = []
    for fill in ("0", "0xA5", "0xFF"):
        s, _, wav = render(renderer, tmp_path, input="noise", seconds=0.5,
                           fx=fx(*BUSY, f"Type={kind}", "Auto=1"), name=f"fill{fill}",
                           extra=["--fill", fill])
        assert s["nonfinite"] == 0
        wavs.append(wav.read_bytes())
    assert wavs[0] == wavs[1] == wavs[2]


@pytest.mark.parametrize("value,same_as", [
    ("nan", None),            # NaN is the default (fm1_param_clamp)
    ("1e9", "max"),
    ("-1e9", "min"),
    ("inf", "max"),
])
def test_out_of_range_parameters_clamp(renderer, tmp_path, listed, value, same_as):  # noqa: F811
    params = listed["params"]
    bad = [f"{p['name']}={value}" for p in params]
    good = [] if same_as is None else [f"{p['name']}={p[same_as]}" for p in params]
    s, _, a = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*bad), name="bad")
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*good), name="good")
    assert s["nonfinite"] == 0
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("params", [
    [],
    ["Type=1", "Bias=1", "Drive=36"],
    ["Type=3", "Bias=-0.6", "Gate=1", "Tone=0", "Level=12"],
    ["Type=4", "Bias=0.25", "Gate=0.3", "Mix=0.5", "Auto=0"],
    ["Type=2", "Bias=-1", "Tone=1", "Drive=-12"],
])
def test_silence_in_is_silence_out(renderer, tmp_path, params):  # noqa: F811
    # The shaper of silence is c(Bias), not 0; the effect subtracts it,
    # computed by the same code on the same values, so the difference is
    # exactly zero rather than a DC step for the blocker to remove.
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.5, fx=fx(*params))
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


BAD_INPUT = {"nan": "nan", "inf": "inf", "huge": "1e30"}


@pytest.mark.parametrize("kind", ["1", "4"])
@pytest.mark.parametrize("bad", sorted(BAD_INPUT))
def test_bad_input_is_guarded_and_not_latched(renderer, tmp_path, bad, kind):  # noqa: F811
    # The input guard reads NaN as 0 and clamps everything else to +/-16, the
    # dry path included, so no state is poisoned: half a second after the
    # fault ends the output is the fault-free output, sample for sample (Tape
    # too, whose emphasis filters have state).
    base = ["--input", "noise", "--seconds", "1.5", *cli(*BUSY, f"Type={kind}")]
    _, clean_l, clean_r, _ = run(renderer, tmp_path, base, "clean")
    fault = ["--fault", f"0.2..0.5:{BAD_INPUT[bad]}"]
    s, left, right, _ = run(renderer, tmp_path, [*base, *fault], "fault")
    assert s["nonfinite"] == 0
    assert s["raw_peak"] < 16.5
    tail = slice(RATE, None)
    assert max(abs(a - b) for a, b in zip(left[tail], clean_l[tail])) <= LSB
    assert max(abs(a - b) for a, b in zip(right[tail], clean_r[tail])) <= LSB


def test_nan_input_reads_as_silence(renderer, tmp_path):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="noise", seconds=0.5,
                     fx=fx("Type=3", "Bias=0.5", "Gate=0.2"), extra=["--fault", "0..0.5:nan"])
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


@pytest.mark.parametrize("bad", ["inf", "1e30"])
def test_mix_zero_passes_the_clamped_input(renderer, tmp_path, bad):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="noise", seconds=0.3,
                     fx=fx("Mix=0", "Drive=36", "Type=3"), extra=["--fault", f"0.1..0.2:{bad}"])
    assert s["nonfinite"] == 0 and s["raw_peak"] == 16.0


def test_mix_zero_passes_the_input_through(renderer, tmp_path):  # noqa: F811
    ref, _, ref_wav = render(renderer, tmp_path, input="noise", seconds=1.0,
                             fx=[("test-gain", ["Gain=1"])], name="ref")
    out, _, out_wav = render(renderer, tmp_path, input="noise", seconds=1.0,
                             fx=fx(*BUSY[:3], "Mix=0", *BUSY[4:]), name="dry")
    assert out["raw_peak"] == ref["raw_peak"]
    assert out_wav.read_bytes() == ref_wav.read_bytes()


# --- every knob does what it says ---------------------------------------------

def test_low_drive_is_nearly_transparent(renderer, tmp_path):  # noqa: F811
    # At -12 dB the 0.5 sine reaches 0.125 into the curve: Soft is within
    # 0.5 % of linear there. Auto restores the level; what remains is ADAA's
    # half-sample average (-0.004 dB at 440 Hz) and the flat tilt.
    _, dry, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="dry",
                       fx=[("test-gain", ["Gain=1"])])
    _, wet, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="wet",
                       fx=fx("Drive=-12"))
    assert db(rms(wet, 0.5, 1.0) / rms(dry, 0.5, 1.0)) == pytest.approx(0.0, abs=0.02)
    assert correlation(steady(wet), steady(dry)) > 0.9995


@pytest.mark.parametrize("kind,drives", [
    # Brightness of the 440 Hz sine, measured: Soft 0.063, 0.070, 0.200;
    # Tube 0.063, 0.073, 0.207; Diode 0.063, 0.075, 0.210; Fuzz (gated at
    # -12 dB: crossover spikes) 0.078, 0.077, 0.209; Tape 0.063, 0.063, 0.091.
    (0, (-12, 12, 36)), (1, (-12, 12, 36)), (2, (-12, 12, 36)), (3, (12, 24, 36)),
    (4, (-12, 12, 36)),
])
def test_drive_adds_harmonics(renderer, tmp_path, kind, drives):  # noqa: F811
    bright = []
    for d in drives:
        _, left, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name=f"d{d}",
                            fx=fx(f"Type={kind}", f"Drive={d}"))
        bright.append(brightness(left, 0.5, 1.0))
    assert bright[0] < bright[1] < bright[2]
    assert bright[2] > 1.4 * bright[0]


def test_each_type_has_its_own_sound(renderer, tmp_path):  # noqa: F811
    wavs = []
    for kind in range(5):
        _, _, wav = render(renderer, tmp_path, input="noise", seconds=0.3, name=f"t{kind}",
                           fx=fx(f"Type={kind}", "Drive=24"))
        wavs.append(wav.read_bytes())
    assert len(set(wavs)) == 5


@pytest.mark.parametrize("kind,even", [(0, False), (1, True), (2, False), (3, True), (4, False)])
def test_even_harmonics_where_the_curve_is_uneven(renderer, tmp_path, kind, even):  # noqa: F811
    # Soft, Diode and Tape are odd curves: a sine through them has no second
    # harmonic (measured below -126 dB, float noise). Tube's curvature at 0
    # and Fuzz's own offset make one (-27 and -19 dB at Drive 12).
    _, left, _ = render(renderer, tmp_path, input="sine", seconds=1.0,
                        fx=fx(f"Type={kind}", "Drive=12"))
    seg = steady(left)
    h2 = 10 * math.log10(goertzel(seg, 880) / goertzel(seg, 440))
    assert (h2 > -35) if even else (h2 < -90)


@pytest.mark.parametrize("bias", ["0.5", "-0.5"])
def test_bias_adds_even_harmonics(renderer, tmp_path, bias):  # noqa: F811
    _, left, _ = render(renderer, tmp_path, input="sine", seconds=1.0,
                        fx=fx("Type=0", "Drive=12", f"Bias={bias}"))
    seg = steady(left)
    assert 10 * math.log10(goertzel(seg, 880) / goertzel(seg, 440)) > -20   # -14.5 dB


def test_gate_silences_what_stays_inside_it(renderer, tmp_path):  # noqa: F811
    # At Drive -12 dB the 0.5 sine reaches +/-0.125 into the curve. A dead
    # zone of +/-0.15 (Gate 0.3) holds all of it: exact silence. One of
    # +/-0.1 (Gate 0.2) lets the tops through, as crossover distortion.
    s, _, _ = render(renderer, tmp_path, input="sine", seconds=0.5, name="shut",
                     fx=fx("Drive=-12", "Gate=0.3"))
    assert s["raw_peak"] == 0.0
    _, left, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="open",
                        fx=fx("Drive=-12", "Gate=0.2", "Auto=0"))
    _, full, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="full",
                        fx=fx("Drive=-12", "Auto=0"))
    assert 0 < rms(left, 0.5, 1.0) < 0.15 * rms(full, 0.5, 1.0)
    assert brightness(left, 0.5, 1.0) > 2 * brightness(full, 0.5, 1.0)   # 0.147, 0.063


def test_tone_tilts(renderer, tmp_path):  # noqa: F811
    bright = []
    for tone in ("0", "0.25", "0.5", "0.75", "1"):
        _, left, _ = render(renderer, tmp_path, input="noise", seconds=0.5, name=f"tone{tone}",
                            fx=fx("Drive=12", f"Tone={tone}"))
        bright.append(brightness(left, 0.1, 0.5))
    # Measured 0.450, 0.784, 1.001, 1.047, 1.053: the dark side cuts the
    # highs by up to 18 dB, the bright side the lows below 800 Hz.
    assert bright == sorted(bright) and len(set(bright)) == 5
    assert bright[0] < 0.5 * bright[2]


@pytest.mark.parametrize("level", ["-6", "-24"])
def test_level_scales_the_wet_signal(renderer, tmp_path, level):  # noqa: F811
    _, full, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="full",
                        fx=fx("Type=1", "Drive=24"))
    _, less, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="less",
                        fx=fx("Type=1", "Drive=24", f"Level={level}"))
    assert db(rms(less, 0.2, 1.0) / rms(full, 0.2, 1.0)) == pytest.approx(float(level), abs=0.02)


def test_mix_blends_dry_and_wet(renderer, tmp_path):  # noqa: F811
    common = ["Type=3", "Drive=24", "Tone=0.4"]
    _, dry, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="m0",
                       fx=fx(*common, "Mix=0"))
    _, wet, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="m1",
                       fx=fx(*common, "Mix=1"))
    _, mid, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="m5",
                       fx=fx(*common, "Mix=0.5"))
    worst = max(abs(m - 0.5 * (d + w)) for m, d, w in zip(mid, dry, wet))
    assert worst <= 1.5 * LSB


@pytest.mark.parametrize("kind", range(5))
def test_auto_keeps_the_level(renderer, tmp_path, kind):  # noqa: F811
    # Auto divides by what the static curve does to a 0.5 sine's level, so
    # from -12 to +36 dB of Drive the 440 Hz sine comes out at its own level:
    # within 0.1 dB for four Types (measured), and within 1.6 dB for Tape,
    # whose de-emphasis lowers the harmonics the curve makes (-0.4, -1.3 and
    # -1.6 dB at 12, 24 and 36 dB), which a static quadrature cannot see.
    # Off, Drive raises the level by up to 8.5 dB (Fuzz: -16 dB at -12, its
    # own gate taking a third of the quiet sine).
    on, off = [], []
    for d in (-12, 0, 12, 24, 36):
        for auto, out in (("1", on), ("0", off)):
            _, left, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name=f"a{d}{auto}",
                                fx=fx(f"Type={kind}", f"Drive={d}", f"Auto={auto}"))
            out.append(db(rms(left, 0.5, 1.0) / REF_RMS))
    bound = 1.7 if kind == 4 else 0.12
    assert max(abs(x) for x in on) < bound
    assert off == sorted(off) and off[-1] - off[0] > 19


def test_after_an_engine_and_before_a_reverb(renderer, tmp_path):  # noqa: F811
    summary, left, right, _ = run(
        renderer, tmp_path,
        ["--engine", "macro", "--param", "Model=0", "--note", "0:45:100:0.5",
         "--note", "0:52:100:0.5", "--seconds", "1.5", *cli("Type=3", "Drive=24", "Gate=0.2"),
         "--fx", "plate", "--fx-param", "Mix=0.3"], "chain")
    assert summary["fx"] == ["drive", "plate"]
    assert summary["nonfinite"] == 0
    assert rms(left, 0.1, 0.5) > 1e-2 and rms(left, 1.0, 1.4) > 1e-4


# --- fm1-drive-test: the curves, aliasing, and what fm1-render cannot drive ------

@pytest.mark.parametrize("name", TYPES)
def test_antialiased_mean_is_exact(tool, name):
    # 3,000 random steps per Type, from 0.01 to 30 wide (across every piece
    # and the dead zone), against Simpson's rule in double; and steps of
    # 1e-6 to 1e-3 at the knots and the dead zone's edges, where a formula
    # dividing a difference of antiderivatives by the step would be off by
    # about 0.1 at 1e-6. Measured: 1.4e-6 at worst (Tape, ceiling 2).
    m = tool["means"][name]
    assert m["vs_quadrature"] < 2e-6 and m["tiny_steps"] < 2e-6


def alias_rows(tool):
    return [a for a in tool["alias"] if a["plain_5k"] > -120]   # some aliasing to remove


def test_antialiasing_beats_a_plain_curve(tool):
    # A 0.5 sine at 440 and 1,760 Hz, Drive 12, 24 and 36 dB, each Type, in
    # the 26 cases where the plain curve aliases above -120 dB: aliases below
    # 5 kHz against the fundamental come out 20.6-29.3 dB lower than a plain
    # per-sample curve's, and 4.8-10.5 dB lower over the whole band, where
    # ADAA's one-sample average does little near Nyquist (measured).
    rows = alias_rows(tool)
    assert len(rows) == 26
    for a in rows:
        assert a["adaa_5k"] < a["plain_5k"] - 20, a
        assert a["adaa_all"] < a["plain_all"] - 4.5, a


@pytest.mark.parametrize("kind,drive,hz,adaa,plain", [
    # Measured (2026-10-02), below 5 kHz: the worst of each Type.
    ("Soft", 36, 1760, -48.2, -24.5),
    ("Tube", 36, 1760, -47.8, -24.0),
    ("Diode", 36, 1760, -47.6, -23.8),
    ("Fuzz", 36, 1760, -47.8, -23.8),
    ("Tape", 36, 1760, -51.3, -22.0),
    ("Fuzz", 24, 440, -76.3, -51.4),
])
def test_alias_levels_as_documented(tool, kind, drive, hz, adaa, plain):
    a = next(a for a in tool["alias"] if (a["type"], a["drive"], a["hz"]) == (kind, drive, hz))
    assert a["adaa_5k"] == pytest.approx(adaa, abs=1.0)
    assert a["plain_5k"] == pytest.approx(plain, abs=1.0)


def test_tape_softens_loud_highs(tool):
    # The fundamental's gain at 200 Hz and 5 kHz: quiet (0.05 at -12 dB), Tape
    # is Soft exactly, flat but for ADAA's -0.55 dB at 5 kHz; loud (0.5 at
    # +24 dB), Soft stays flat within 0.2 dB while Tape's 5 kHz saturates
    # 10.5 dB more than its 200 Hz (measured +13.7 against +3.2 dB).
    soft, tape = tool["emphasis"]["Soft"], tool["emphasis"]["Tape"]
    for key in ("quiet_200", "quiet_5k"):
        assert tape[key] == pytest.approx(soft[key], abs=0.005)
    assert soft["quiet_200"] - soft["quiet_5k"] == pytest.approx(0.55, abs=0.05)
    assert abs(soft["loud_200"] - soft["loud_5k"]) < 0.3
    assert tape["loud_200"] - tape["loud_5k"] > 9


def test_any_parameter_change_mid_stream_stays_finite(tool):
    # 20 s of noise; between blocks of 1-64 frames, up to two parameters jump
    # to their minimum, maximum, default, a random value, beyond the range,
    # NaN or an infinity. The bound: |shaper - its silence| <= 4 (Tape's
    # ceiling of 2, Bias), x 2 (the DC blocker at worst), x 4 (Level +12 dB),
    # x 8 (Auto's largest gain); measured 0.61.
    s = tool["sweep"]
    assert s["samples"] > 20 * RATE
    assert s["nonfinite"] == 0 and s["peak"] < 4


def test_glide_is_block_size_independent_and_lands(tool):
    g = tool["glide"]
    assert g["block_independent"]
    # Two Type changes 80 samples apart: the second waits for the first
    # crossfade, and wins.
    assert g["final_type"] == "Fuzz"
    # Level 0 -> -24 dB fades over ~5 ms instead of cutting: within the first
    # millisecond the output is still there...
    assert g["first_ms"] > 0.5 * g["before"]
    # ...and within 50 ms the glide has landed: the output is then the one
    # of a run that had -24 dB all along, bit for bit.
    assert g["lands_ms"] < 50


def test_type_change_crossfades(tool):
    # Nine Type changes on a 440 Hz sine at Drive 24: the largest step
    # between samples at a change is no larger than in steady playing
    # (measured 0.190 against 0.196); switched at once it would be 2.2 times
    # that (0.435).
    s = tool["switch"]
    assert s["change_step"] <= 1.05 * s["steady_step"]
    assert s["at_once_step"] > 1.5 * s["steady_step"]


def test_moving_controls_in_silence_stay_silent(tool):
    # Type, Drive, Bias and Gate all moving: the shaper of silence moves with
    # them and is subtracted, so the output stays exactly zero.
    s = tool["silence"]
    assert s["moving_peak"] == 0.0 and s["settled_peak"] == 0.0 and s["last_block_peak"] == 0.0


def test_host_rates(tool):
    accepted = {rate: ok for rate, ok in tool["rates"]}
    assert accepted == {"0": False, "7999": False, "8000": True, "44118": True,
                        "48000": True, "96000": True, "384000": True, "400000": False,
                        "nan": False, "inf": False, "-44118": False}


if __name__ == "__main__":
    print(c_curves())
    print(c_quad())
