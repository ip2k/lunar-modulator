"""Tests for DJ Filter, the one-knob low-pass / high-pass effect
(engines/src/fx_djfilter.cc, parameters in engines/README.md, "DJ Filter";
design in notes/2026-10-02-delay-reverb-eq-gates-options.md §4.3).

Through fm1-render: registration and pages, the host contracts (deterministic
renders, any block size, any prior memory contents, any parameter value,
NaN included, bad input guarded and not latched, silence in gives silence
out), the exact bypass at the defaults, in the dead zone and at Mix 0, and
that each side darkens or thins the sound. Through fm1-djfilter-test
(engines/test/djfilter_test.cc): the frequency response against the
filter's analytic response at points across the sweep; parameters changed
while audio runs, at host blocks of 64, 12, 7 and 1; a sweep written every
32 frames (as the modulation matrix will) checked for zipper noise against a
filter whose coefficients step; entering, leaving and crossing sides and
switching the slope on a bass note without a click or a thump; tails that
end in exact zeros; host rates. And no libm in the object file.
"""
import cmath
import json
import math
import shutil
import struct
import subprocess

import pytest

from tests.engine_helpers import ENGINES, RATE, render, renderer, rms  # noqa: F401
from tests.test_engines_mi_fx import BANNED, brightness, run

TOOL = ENGINES / "build" / "fm1-djfilter-test"
OBJECT = ENGINES / "build" / "our" / "src" / "fx_djfilter.o"
LSB = 1 / 32767.0

# Every parameter away from its default: the low-pass side, resonant, 24 dB.
BUSY = ["Sweep=-0.6", "Resonance=0.7", "Slope=1", "Mix=0.85", "Dead Zone=0.1", "Range=0.8"]

# The law (fx_djfilter.cc): cutoffs over the host rate at travel u = 0, and
# the octaves to the far end (60 Hz for the low-pass, 8 kHz for the
# high-pass).
LP_OPEN, LP_OCTAVES = 20000.0, math.log2(20000 / 60)
HP_OPEN, HP_OCTAVES = 20.0, math.log2(8000 / 20)
Q0, QMAX, ENTRY = 1 / math.sqrt(2), 8.0, 0.08


def fx(*params):
    return [("djfilter", list(params))]


def cli(*params):
    args = ["--fx", "djfilter"]
    for p in params:
        args += ["--fx-param", p]
    return args


@pytest.fixture(scope="module")
def tool(renderer, tmp_path_factory):  # noqa: F811 -- the renderer fixture builds everything
    out_dir = tmp_path_factory.mktemp("djfilter")
    out = subprocess.run([str(TOOL), str(out_dir)], check=True, capture_output=True,
                         text=True).stdout
    data = json.loads(out)
    data["dir"] = out_dir
    return data


def test_djfilter_is_registered(renderer):  # noqa: F811
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True,
                         text=True).stdout
    e = {x["id"]: x for x in json.loads(out)}["djfilter"]
    assert (e["name"], e["kind"], e["max_voices"]) == ("DJ Filter", "audio_fx", 0)
    assert not any(b in (e["id"] + e["name"]).lower() for b in BANNED)
    assert "MIT" in e["credits"] and "Simper" in e["credits"] and "Zavalishin" in e["credits"]
    pages = [[p["name"] for p in e["params"] if p["page"] == k] for k in (0, 1)]
    assert pages == [["Sweep", "Resonance", "Slope", "Mix"], ["Dead Zone", "Range"]]
    assert all(len(p["name"]) <= 12 for p in e["params"])
    assert all(p["min"] <= p["def"] <= p["max"] for p in e["params"])
    slope = next(p for p in e["params"] if p["name"] == "Slope")
    assert slope["type"] == 1 and slope["names"] == ["12 dB", "24 dB"]
    sweep = next(p for p in e["params"] if p["name"] == "Sweep")
    assert (sweep["min"], sweep["max"], sweep["def"]) == (-1, 1, 0)


def test_instance_is_small(renderer, tmp_path):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.05, fx=fx())
    assert s["fx_bytes"][0] % 16 == 0 and s["fx_bytes"][0] <= 256


def test_no_libm_in_the_object():
    # Every maths function is written in the file: libm's differ in their
    # last bits between C libraries, which would break the browser's
    # bit-exact parity (sim/web/README.md, "Parity").
    if not shutil.which("nm"):
        pytest.skip("no nm")
    out = subprocess.run(["nm", "-u", str(OBJECT)], check=True, capture_output=True,
                         text=True).stdout
    names = {line.split()[-1].lstrip("_") for line in out.splitlines() if line.strip()}
    libm = {n for n in names if n.rstrip("f") in
            ("sin", "cos", "tan", "exp", "exp2", "log", "log2", "log10", "pow", "sqrt",
             "atan", "atan2", "sinh", "cosh", "tanh", "floor", "ceil", "fmod", "round")}
    assert not libm, libm


# --- host contracts ---------------------------------------------------------

def test_rendering_is_deterministic(renderer, tmp_path):  # noqa: F811
    _, _, a = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY), name="a")
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY), name="b")
    assert a.read_bytes() == b.read_bytes()


def test_block_size_does_not_change_the_output(renderer, tmp_path):  # noqa: F811
    wavs = []
    for frames in ("64", "12", "7", "1"):
        _, _, wav = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY),
                           name=f"f{frames}", extra=["--frames", frames])
        wavs.append(wav.read_bytes())
    assert wavs[0] == wavs[1] == wavs[2] == wavs[3]


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
    params = {x["id"]: x for x in json.loads(out)}["djfilter"]["params"]
    bad = [f"{p['name']}={value}" for p in params]
    good = [] if same_as is None else [f"{p['name']}={p[same_as]}" for p in params]
    s, _, a = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*bad), name="bad")
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*good), name="good")
    assert s["nonfinite"] == 0
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("params", [
    [],
    ["Sweep=-0.5", "Resonance=1", "Slope=1"],
    ["Sweep=0.7", "Resonance=1"],
    ["Sweep=-1", "Mix=0.5", "Range=0.1"],
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
    tail = slice(RATE, None)
    assert max(abs(a - b) for a, b in zip(left[tail], clean_l[tail])) <= LSB
    assert max(abs(a - b) for a, b in zip(right[tail], clean_r[tail])) <= LSB


def test_nan_input_reads_as_silence(renderer, tmp_path):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="noise", seconds=0.5,
                     fx=fx("Sweep=-0.5", "Resonance=1"), extra=["--fault", "0..0.5:nan"])
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


@pytest.mark.parametrize("bad", ["inf", "1e30"])
def test_the_bypass_passes_the_clamped_input(renderer, tmp_path, bad):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(),
                     extra=["--fault", f"0.1..0.2:{bad}"])
    assert s["nonfinite"] == 0 and s["raw_peak"] == 16.0


# --- the exact bypass ---------------------------------------------------------

@pytest.mark.parametrize("params", [
    [],                                             # the defaults: Sweep 0
    ["Sweep=0.049", "Resonance=1", "Slope=1"],     # inside the dead zone
    ["Sweep=-0.19", "Dead Zone=0.2"],
    ["Sweep=-0.8", "Mix=0", "Slope=1"],            # Mix 0 anywhere
])
def test_neutral_settings_pass_the_input_bit_for_bit(renderer, tmp_path, params):  # noqa: F811
    ref, _, ref_wav = render(renderer, tmp_path, input="noise", seconds=1.0,
                             fx=[("test-gain", ["Gain=1"])], name="ref")
    out, _, out_wav = render(renderer, tmp_path, input="noise", seconds=1.0, fx=fx(*params),
                             name="dj")
    assert out["raw_peak"] == ref["raw_peak"]
    assert out_wav.read_bytes() == ref_wav.read_bytes()


def test_bypass_is_exact_on_floats(tool):
    # On the floats themselves, not 16-bit WAVs: negative zero, subnormals,
    # values next to the guard's limit, all kept bit for bit.
    b = tool["bypass"]
    for case in ("defaults", "inside_dead_zone_left", "inside_dead_zone_right",
                 "wide_dead_zone", "mix_zero_left", "mix_zero_right"):
        assert b[case] is True, case
    # Back to the centre after a visit to either side: the sweep glides
    # (about 10 ms), the travel leaves the entry zone in no less than 3 ms,
    # then the filter stops and the output is the input again, exactly.
    assert 10 < b["visit_left_exact_after_ms"] < 30
    assert 10 < b["visit_right_exact_after_ms"] < 30


# --- every knob does what it says ---------------------------------------------

def test_the_left_side_darkens_and_the_right_thins(renderer, tmp_path):  # noqa: F811
    bright = {}
    for sweep in ("-0.9", "-0.5", "-0.2", "0", "0.2", "0.5", "0.9"):
        _, left, _ = render(renderer, tmp_path, input="noise", seconds=0.5, name=f"s{sweep}",
                            fx=fx(f"Sweep={sweep}", "Resonance=0"))
        bright[float(sweep)] = brightness(left, 0.1, 0.5)
    # White noise scores sqrt(2); the low-pass lowers it, the high-pass
    # raises it towards 2 (a first difference of a signal with only highs).
    assert bright[0.0] == pytest.approx(math.sqrt(2), abs=0.01)
    assert bright[-0.9] < bright[-0.5] < bright[-0.2] < bright[0.0]
    assert bright[0.0] < bright[0.2] < bright[0.5] < bright[0.9]


def expected_db(sweep, resonance, dead, span, slope24, hz):
    """The analytic gain: the trapezoidal SVF is the bilinear transform of
    the analog state-variable filter prewarped at its cutoff, so at hz its
    response is the analog one at W = tan(pi hz / fs), with g = tan(pi fc /
    fs); the entry fade blends it with the dry input."""
    low = sweep < 0
    u = min(1.0, max(0.0, (abs(sweep) - dead) / (1 - dead)))
    octaves = u * span
    ratio = (LP_OPEN * 2 ** (-LP_OCTAVES * octaves) if low else
             HP_OPEN * 2 ** (HP_OCTAVES * octaves)) / RATE
    g = math.tan(math.pi * min(ratio, 0.45))
    q = Q0 + resonance * (QMAX - Q0) * 4 * u * (1 - u)
    w = math.tan(math.pi * hz / RATE)

    def svf(r):
        return (g * g if low else -w * w) / complex(g * g - w * w, r * g * w)

    h = svf(1 / q) * (svf(math.sqrt(2)) if slope24 else 1)
    e = min(1.0, u / ENTRY)
    wet = e * e * (3 - 2 * e)
    return 20 * math.log10(abs(1 + wet * (h - 1)))


def test_frequency_response_matches_the_analytic_filter(tool):
    # The law, the resonance window, both slopes, Range and Dead Zone, at 24
    # points; within 0.01 dB (measured: 2e-5 dB at worst).
    worst = 0.0
    for p in tool["response"]:
        want = expected_db(p["sweep"], p["resonance"], p["dead"], p["range"], p["slope24"],
                           p["hz"])
        worst = max(worst, abs(p["db"] - want))
        assert p["db"] == pytest.approx(want, abs=0.01), p
    assert worst < 0.01


def test_the_named_points_of_the_sweep(tool):
    r = {(p["sweep"], p["resonance"], p["dead"], p["range"], p["slope24"], round(p["hz"])):
         p["db"] for p in tool["response"]}
    # The ends: low-pass at 60 Hz and high-pass at 8 kHz, -3.01 dB there.
    assert r[(-1, 1, 0.05, 1, 0, 60)] == pytest.approx(-3.01, abs=0.01)   # no peak at the end
    assert r[(1, 0, 0.05, 1, 0, 8000)] == pytest.approx(-3.01, abs=0.01)
    # 12 and 24 dB per octave: two octaves past 60 Hz, -24 and -48 dB.
    assert r[(-1, 0, 0.05, 1, 0, 240)] == pytest.approx(-24.1, abs=0.1)
    assert r[(-1, 0, 0.05, 1, 1, 240)] == pytest.approx(-48.2, abs=0.1)
    # Mid travel (1,095 Hz): Resonance 1 is Q 8, +18.06 dB; at 24 dB the
    # second stage (Q 0.707) takes 3 dB of it.
    assert r[(-0.525, 1, 0.05, 1, 0, 1095)] == pytest.approx(18.06, abs=0.01)
    assert r[(-0.525, 1, 0.05, 1, 1, 1095)] == pytest.approx(15.05, abs=0.01)
    assert r[(0.525, 1, 0.05, 1, 0, 400)] == pytest.approx(18.06, abs=0.01)
    # Range 0.5 reaches half way; a wider dead zone moves the same law.
    assert r[(-1, 0, 0.05, 0.5, 0, 1095)] == pytest.approx(-3.01, abs=0.01)
    assert r[(-0.6, 0, 0.2, 1, 0, 1095)] == pytest.approx(-3.01, abs=0.01)
    # Just past the dead zone the filter has barely faded in.
    assert abs(r[(-0.06, 1, 0.05, 1, 0, 1000)]) < 0.01
    assert abs(r[(0.06, 1, 0.05, 1, 1, 1000)]) < 0.01


# --- fm1-djfilter-test: what fm1-render cannot drive ----------------------------

def test_any_parameter_change_mid_stream_stays_finite(tool):
    # 20 s of noise at 0.5; between blocks of 1-64 frames, up to two
    # parameters jump to their minimum, maximum, default, a random value,
    # beyond the range, NaN or an infinity. Measured peak 1.33: resonance at
    # Q 8 on the noise, never a runaway.
    s = tool["sweep"]
    assert s["samples"] > 20 * RATE
    assert s["nonfinite"] == 0 and s["peak"] < 3.0
    assert s["blocks_not_bypassed_after"] == 0      # the defaults again: exact
    b = tool["sweep_bad_input"]                     # the same, with NaN, inf, 1e30 mixed in
    assert b["bad_inputs"] > 100 and b["nonfinite"] == 0
    assert b["peak"] < 48.0                          # the guard's 16, rung by the filter
    assert b["blocks_not_bypassed_after"] == 0


def test_changes_mid_stream_are_block_size_independent(tool):
    b = tool["blocks"]
    assert b["changes"] > 500                        # ten jumps, then an LFO every 32 frames
    assert b["block_independent"] is True            # 64, 12, 7 and 1 frames, three fills
    assert b["tail_bypassed"] is True


def fft(a):
    """In-place iterative radix-2 transform of a list of complex numbers."""
    n = len(a)
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    size = 2
    while size <= n:
        half = size // 2
        tw = [cmath.exp(-2j * math.pi * k / size) for k in range(half)]
        for start in range(0, n, size):
            for k in range(half):
                u = a[start + k]
                v = a[start + k + half] * tw[k]
                a[start + k] = u + v
                a[start + k + half] = u - v
        size *= 2
    return a


N_FFT = 32768
TONE_BIN = 743                                       # 1000.3 Hz


def zipper_db(samples):
    """Power within 10 bins of each place zipper noise lands, against the
    tone's: the tone's images about every multiple of the 32-frame write rate
    (1,378.7 Hz, which covers the 16-frame tick too), Blackman-Harris
    window, last 32,768 samples."""
    seg = samples[-N_FFT:]
    a0, a1, a2, a3 = 0.35875, 0.48829, 0.14128, 0.01168
    win = [a0 - a1 * math.cos(2 * math.pi * i / N_FFT) + a2 * math.cos(4 * math.pi * i / N_FFT)
           - a3 * math.cos(6 * math.pi * i / N_FFT) for i in range(N_FFT)]
    spec = fft([complex(s * w) for s, w in zip(seg, win)])
    p = [abs(c) ** 2 for c in spec[:N_FFT // 2]]
    tone = sum(p[TONE_BIN - 200:TONE_BIN + 201])
    bins = set()
    f0 = TONE_BIN * RATE / N_FFT
    for k in range(1, 16):
        for f in (k * RATE / 32 + f0, abs(k * RATE / 32 - f0)):
            if f >= RATE / 2:
                f = RATE - f
            c = round(f * N_FFT / RATE)
            bins.update(range(max(0, c - 10), min(N_FFT // 2, c + 11)))
    return 10 * math.log10(sum(p[b] for b in bins) / tone)


def stepped(centre, depth, resonance, slope24):
    """The same sweep through a plain trapezoidal SVF whose coefficients
    jump at each 32-frame write: no glide, no ramp (double precision)."""
    low = centre < 0
    f0 = TONE_BIN * RATE / N_FFT
    states = [0.0] * 4
    out = []
    for pos in range(0, 2 * N_FFT, 32):
        sweep = centre + depth * math.sin(2 * math.pi * 0.7 * pos / RATE)
        u = (abs(sweep) - 0.05) / 0.95
        ratio = (LP_OPEN * 2 ** (-LP_OCTAVES * u) if low else HP_OPEN * 2 ** (HP_OCTAVES * u)) / RATE
        g = math.tan(math.pi * min(ratio, 0.45))
        q = Q0 + resonance * (QMAX - Q0) * 4 * u * (1 - u)
        stages = [1 / q, math.sqrt(2)][:2 if slope24 else 1]
        for i in range(32):
            y = 0.25 * math.sin(2 * math.pi * f0 * (pos + i) / RATE)
            for k, r in enumerate(stages):
                s1, s2 = states[2 * k], states[2 * k + 1]
                hp = (y - (r + g) * s1 - s2) / (1 + r * g + g * g)
                bp = g * hp + s1
                lp = g * bp + s2
                states[2 * k], states[2 * k + 1] = g * hp + bp, g * bp + lp
                y = lp if low else hp
            out.append(y)
    return out


@pytest.mark.parametrize("leg,centre,slope24,ceiling", [
    # Measured (2026-10-03): -82.0 dB (low-pass) and -115.7 dB (high-pass)
    # against -44.8 and -78.3 dB for the stepped filter. What is left in the
    # low-pass leg is the resonant filter's own ringing as it sweeps past the
    # tone, spread across the spectrum, not lines at the write rate.
    ("lp", -0.5, 0, -75.0),
    ("hp", 0.5, 1, -105.0),
])
def test_a_matrix_sweep_makes_no_zipper_noise(tool, leg, centre, slope24, ceiling):
    raw = (tool["dir"] / f"zipper-{leg}.f32").read_bytes()
    ours = zipper_db(list(struct.unpack(f"<{len(raw) // 4}f", raw)))
    theirs = zipper_db(stepped(centre, 0.35, 0.6, slope24))
    assert ours < ceiling
    assert ours < theirs - 30


def test_transitions_neither_click_nor_thump(tool):
    # A 0.8 sine at 60 Hz, each change at a positive peak. A click shows
    # above 4 kHz: what passes a 4th-order high-pass there, against 0.8.
    # Measured (2026-10-03): at most 1.9e-4 (-72 dB), on the fastest
    # crossings (a jump from one side to the other); 4.2e-5 (-85 dB) or less
    # entering a side. Switching the filter's tap outright would step the
    # output by up to the note's own size.
    t = tool["transitions"]
    events = {k: v for k, v in t.items() if isinstance(v, dict)}
    assert len(events) == 12
    for name, e in events.items():
        assert e["hf_before"] < 1e-6, name
        assert e["hf_after"] < 3e-4, name
        assert e["d2_after"] < 1e-3, name               # input: 5.8e-5
    for name in ("enter_lp", "enter_hp", "lp_to_hp", "hp_to_lp", "lp_to_hp_no_dead_zone",
                 "leave_lp", "leave_hp"):
        # No thump: never more than the bass note itself, give or take the
        # default Resonance's bump (0.2: at most +8 % on the way through).
        assert events[name]["peak_after"] < 0.8 * 1.1, name
    for name in ("enter_lp", "enter_hp", "enter_lp_24_reso", "slope_up", "slope_down",
                 "leave_lp", "mix_up"):
        assert events[name]["hf_after"] < 1e-4, name


def test_tails_end_in_exact_zeros(tool):
    # After full-scale noise into the most resonant settings, silence:
    # the states ring down and flush, so the output is exact zeros, not
    # subnormals. Measured 106-474 ms (the 20 Hz high-pass at 24 dB longest).
    for name, ms in tool["tails"].items():
        assert 0 < ms < 1000, name


def test_host_rates(tool):
    accepted = {rate: (ok, finite) for rate, ok, finite in tool["rates"]}
    assert {r: ok for r, (ok, _) in accepted.items()} == {
        "0": False, "7999": False, "8000": True, "44118": True, "48000": True,
        "96000": True, "384000": True, "400000": False, "nan": False, "inf": False,
        "-44118": False}
    assert all(finite for _, finite in accepted.values())


def test_after_an_engine_and_before_a_reverb(renderer, tmp_path):  # noqa: F811
    summary, left, right, _ = run(
        renderer, tmp_path,
        ["--engine", "macro", "--param", "Model=0", "--note", "0:45:100:0.5",
         "--note", "0:52:100:0.5", "--seconds", "1.5", *cli("Sweep=-0.55", "Resonance=0.6"),
         "--fx", "plate", "--fx-param", "Mix=0.3"], "chain")
    assert summary["fx"] == ["djfilter", "plate"]
    assert summary["nonfinite"] == 0
    assert rms(left, 0.1, 0.5) > 1e-2 and rms(left, 1.0, 1.4) > 1e-4
