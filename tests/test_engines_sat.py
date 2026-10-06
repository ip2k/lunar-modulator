"""Tests for Master Sat, the bus saturation effect (engines/src/fx_sat.cc,
parameters in engines/README.md, "Master Sat"; the design is §6 of
notes/2026-10-02-delay-reverb-eq-gates-options.md).

Through fm1-render: registration and pages, the host contracts
(deterministic renders, any block size, any prior memory contents, any
parameter value, NaN included, bad input guarded and not latched, silence in
gives silence out), the defaults and Mix 0 as an exact bypass. Through
fm1-sat-test (engines/test/sat_test.cc): parameters changed while audio runs,
with block sizes that change between calls, the Shape crossfade, Glue's
envelope, float-exact bypass, small signals, the host rates, a digest of the
output's bits that every build must reproduce, and tones of any frequency
for what each knob does and for aliasing.
"""
import json
import math
import subprocess

import pytest

from tests.engine_helpers import ENGINES, RATE, render, renderer, rms  # noqa: F401
from tests.test_engines_mi_fx import run

TOOL = ENGINES / "build" / "fm1-sat-test"
LSB = 1 / 32767.0

# Every parameter away from its default, Mix included.
BUSY = ["Drive=12", "Clean Lo=60", "Glue=0.7", "Mix=0.9", "Shape=1", "Asymmetry=0.4",
        "Clean Hi=9000", "Level=-2"]
# Names that stay in the credits, never on a label: the products whose
# constants and idea the effect uses (the effects note's §10.16).
NOT_LABELS = ("airwindows", "purest", "tapehack", "compresaturator")


def fx(*params):
    return [("sat", list(params))]


def cli(*params):
    args = ["--fx", "sat"]
    for p in params:
        args += ["--fx-param", p]
    return args


@pytest.fixture(scope="module")
def tool(renderer):  # noqa: F811 -- the renderer fixture builds everything
    out = subprocess.run([str(TOOL)], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def tone(hz, amp, *params):
    """fm1-sat-test's tone probe: the last second of a 1.5 s sine, analysed
    at 1 Hz resolution."""
    out = subprocess.run([str(TOOL), "tone", str(hz), str(amp), *params], check=True,
                         capture_output=True, text=True).stdout
    return json.loads(out)


def listed(renderer):  # noqa: F811
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True,
                         text=True).stdout
    return {x["id"]: x for x in json.loads(out)}["sat"]


def test_sat_is_registered(renderer):  # noqa: F811
    e = listed(renderer)
    assert (e["name"], e["kind"], e["max_voices"]) == ("Master Sat", "audio_fx", 0)
    assert "MIT" in e["credits"] and "Airwindows" in e["credits"]
    assert "Chris Johnson" in e["credits"]
    pages = [[p["name"] for p in e["params"] if p["page"] == k] for k in (0, 1)]
    assert pages == [["Drive", "Clean Lo", "Glue", "Mix"],
                     ["Shape", "Asymmetry", "Clean Hi", "Level"]]
    assert all(len(p["name"]) <= 12 for p in e["params"])
    assert all(p["min"] <= p["def"] <= p["max"] for p in e["params"])
    shape = next(p for p in e["params"] if p["name"] == "Shape")
    assert shape["type"] == 1 and shape["names"] == ["Smooth", "Dense"]
    labels = " ".join([e["name"]] + [p["name"] for p in e["params"]] + shape["names"]).lower()
    assert not any(n in labels for n in NOT_LABELS)


def test_instance_is_small_and_pointer_free(renderer, tmp_path, tool):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.05, fx=fx())
    assert s["fx_bytes"][0] % 16 == 0 and s["fx_bytes"][0] <= 512
    # No pointers in the struct: the same on 64-bit and 32-bit builds
    # (336 bytes on arm64, x86-64 and wasm32, 2026-10-05; 352 with the idle
    # path's counters, 2026-10-06).
    assert s["fx_bytes"][0] == tool["instance_bytes"] == 352


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
    params = listed(renderer)["params"]
    bad = [f"{p['name']}={value}" for p in params]
    good = [] if same_as is None else [f"{p['name']}={p[same_as]}" for p in params]
    s, _, a = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*bad), name="bad")
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*good), name="good")
    assert s["nonfinite"] == 0
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("params", [
    ["Mix=1"],
    ["Mix=1", "Drive=18", "Glue=1", "Asymmetry=1", "Shape=1"],
    ["Mix=1", "Asymmetry=-0.6", "Clean Lo=20", "Clean Hi=1000", "Level=12"],
    BUSY,
])
def test_silence_in_is_silence_out(renderer, tmp_path, params):  # noqa: F811
    # The residual is a polynomial with no constant term about the offset,
    # so silence makes exactly 0 whatever Asymmetry is: no DC step for the
    # blocker to remove.
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.5, fx=fx(*params))
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


BAD_INPUT = {"nan": "nan", "inf": "inf", "huge": "1e30"}


@pytest.mark.parametrize("bad", sorted(BAD_INPUT))
def test_bad_input_is_guarded_and_not_latched(renderer, tmp_path, bad):  # noqa: F811
    # The input guard reads NaN as 0 and clamps everything else to +/-16, the
    # dry path included, so no state is poisoned. A clamped fault drives
    # Glue's envelope to the top; it releases over about 200 ms, so a second
    # after the fault ends the output is the fault-free output again.
    base = ["--input", "noise", "--seconds", "2", *cli(*BUSY)]
    _, clean_l, clean_r, _ = run(renderer, tmp_path, base, "clean")
    fault = ["--fault", f"0.2..0.5:{BAD_INPUT[bad]}"]
    s, left, right, _ = run(renderer, tmp_path, [*base, *fault], "fault")
    assert s["nonfinite"] == 0
    assert s["raw_peak"] < 16.0
    tail = slice(int(1.5 * RATE), None)
    assert max(abs(a - b) for a, b in zip(left[tail], clean_l[tail])) <= LSB
    assert max(abs(a - b) for a, b in zip(right[tail], clean_r[tail])) <= LSB


def test_nan_input_reads_as_silence(renderer, tmp_path):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="noise", seconds=0.5,
                     fx=fx("Mix=1", "Asymmetry=0.5", "Glue=1"),
                     extra=["--fault", "0..0.5:nan"])
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


@pytest.mark.parametrize("bad", ["inf", "1e30"])
def test_mix_zero_passes_the_clamped_input(renderer, tmp_path, bad):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="noise", seconds=0.3,
                     fx=fx("Mix=0", "Drive=18"), extra=["--fault", f"0.1..0.2:{bad}"])
    assert s["nonfinite"] == 0 and s["raw_peak"] == 16.0


@pytest.mark.parametrize("params", [[], [p for p in BUSY if not p.startswith("Mix")] + ["Mix=0"]])
def test_defaults_and_mix_zero_are_an_exact_bypass(renderer, tmp_path, params):  # noqa: F811
    # The master-bus rule (the note's §5): the default is an exact bypass.
    # Mix's default is 0, and at Mix 0 the input passes bit for bit however
    # the other knobs are set.
    ref, _, ref_wav = render(renderer, tmp_path, input="noise", seconds=1.0,
                             fx=[("test-gain", ["Gain=1"])], name="ref")
    out, _, out_wav = render(renderer, tmp_path, input="noise", seconds=1.0,
                             fx=fx(*params), name="dry")
    assert out["raw_peak"] == ref["raw_peak"]
    assert out_wav.read_bytes() == ref_wav.read_bytes()


def test_bypass_is_float_exact(tool):
    # Any finite input within the guard, signed zeros, subnormals and +/-16
    # included, comes out with the same bits at the defaults and at Mix 0
    # with every other knob turned.
    b = tool["bypass"]
    assert b["samples"] >= 500000
    assert b["differ_default"] == 0 and b["differ_busy"] == 0


def test_mix_blends_dry_and_wet(renderer, tmp_path):  # noqa: F811
    common = ["Drive=12", "Glue=0.5"]
    _, dry, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="m0",
                       fx=fx(*common, "Mix=0"))
    _, wet, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="m1",
                       fx=fx(*common, "Mix=1"))
    _, mid, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="m5",
                       fx=fx(*common, "Mix=0.5"))
    worst = max(abs(m - 0.5 * (d + w)) for m, d, w in zip(mid, dry, wet))
    assert worst <= 1.5 * LSB


# --- every knob does what it says ---------------------------------------------

def test_small_signals_pass_unchanged(tool):
    # A -60 dBFS sine at Drive 18 and Glue 1, the band wide open: the curve's
    # residual falls as the cube of the level (the square with Asymmetry),
    # measured as the largest difference from the input over its peak.
    lin = tool["linear"]
    assert lin["shape0_asym0"] < 2e-5 and lin["shape1_asym0"] < 2e-5    # -94 dB
    assert lin["shape0_asym1"] < 3e-3 and lin["shape1_asym1"] < 3e-3    # -50 dB


def test_drive_bends_the_curve_harder():
    # 440 Hz at 0.5 peak, Glue 0. Measured (2026-10-05): -42.1, -30.1, -17.9
    # and -11.6 dB of distortion, the fundamental -0.2, -0.8, -3.0, -7.3 dB.
    thd, gain = [], []
    for drive in ("0", "6", "12", "18"):
        t = tone(440, 0.5, "Mix=1", "Glue=0", f"Drive={drive}")
        thd.append(t["thd_db"])
        gain.append(t["gain_db"])
    assert thd == sorted(thd) and gain == sorted(gain, reverse=True)
    assert thd[0] == pytest.approx(-42.1, abs=1) and thd[3] == pytest.approx(-11.6, abs=1)
    assert gain[3] == pytest.approx(-7.3, abs=0.5)


def test_the_curves_are_odd_and_shape_picks_one():
    # An odd curve of a sine makes no even harmonic (h_db[0] is the 2nd).
    smooth = tone(440, 0.5, "Mix=1", "Glue=0", "Drive=6")
    dense = tone(440, 0.5, "Mix=1", "Glue=0", "Drive=6", "Shape=1")
    assert smooth["h_db"][0] < -150 and dense["h_db"][0] < -150
    # Dense bends sooner (a cubic of -1/6 against -1/8): more distortion at
    # the same drive (measured -27.6 against -30.1 dB)...
    assert dense["thd_db"] > smooth["thd_db"] + 1.5
    # ...and tops out lower: ceilings 1.0821 and 1.2212 over Drive's 7.94.
    smooth18 = tone(440, 0.5, "Mix=1", "Glue=0", "Drive=18")
    dense18 = tone(440, 0.5, "Mix=1", "Glue=0", "Drive=18", "Shape=1")
    assert dense18["peak"] < smooth18["peak"]


def test_asymmetry_adds_even_harmonics_and_no_dc():
    h2 = {}
    for a in ("0.5", "1", "-1"):
        t = tone(440, 0.5, "Mix=1", "Glue=0", "Drive=6", f"Asymmetry={a}")
        h2[a] = t["h_db"][0]
        assert abs(t["dc"]) < 1e-6          # the residual's DC blocker
    # Measured -26.7 and -20.4 dB; the sign of the offset does not matter
    # to their level.
    assert -30 < h2["0.5"] < -23 and -23 < h2["1"] < -18
    assert h2["1"] == pytest.approx(h2["-1"], abs=0.01)


def test_clean_bass_keeps_the_lows_clean_and_out_of_glue():
    # A 50 Hz sine at 0.5, Drive 12: saturated with Clean Lo at 20 Hz,
    # untouched at 300 Hz, where Glue does not hear it either.
    low = tone(50, 0.5, "Mix=1", "Glue=0", "Drive=12", "Clean Lo=20")
    high = tone(50, 0.5, "Mix=1", "Glue=0", "Drive=12", "Clean Lo=300")
    glued = tone(50, 0.5, "Mix=1", "Glue=1", "Drive=12", "Clean Lo=300")
    assert low["thd_db"] > -25 and high["thd_db"] < -100
    assert abs(glued["gain_db"]) < 0.01


def test_clean_highs_keeps_the_highs_clean():
    # A 5 kHz sine at 0.5, Drive 12: untouched with Clean Hi at 1 kHz,
    # saturated (and aliasing) with it open.
    shut = tone(5000, 0.5, "Mix=1", "Glue=0", "Drive=12", "Clean Hi=1000")
    open_ = tone(5000, 0.5, "Mix=1", "Glue=0", "Drive=12", "Clean Hi=20000")
    assert shut["thd_db"] < -100 and shut["alias_db"] < -150
    assert open_["thd_db"] > -25


def test_glue_lowers_the_drive_and_the_level():
    # Drive 12, 440 Hz at 0.5: Glue turns the level down (measured -0.8 dB
    # more at Glue 1) and with it the distortion (-17.9 to -21.5 dB).
    off = tone(440, 0.5, "Mix=1", "Drive=12", "Glue=0")
    on = tone(440, 0.5, "Mix=1", "Drive=12", "Glue=1")
    assert on["gain_db"] < off["gain_db"] - 0.5
    assert on["thd_db"] < off["thd_db"] - 2
    # Bounded: the gain never falls more than 6 dB below Glue 0's.
    hard_off = tone(440, 0.9, "Mix=1", "Drive=18", "Glue=0")
    hard_on = tone(440, 0.9, "Mix=1", "Drive=18", "Glue=1")
    assert hard_off["gain_db"] - 6 < hard_on["gain_db"] < hard_off["gain_db"]
    # Quiet signals are left nearly alone: under 0.01 dB at -26 dBFS.
    quiet_off = tone(440, 0.05, "Mix=1", "Drive=6", "Glue=0")
    quiet_on = tone(440, 0.05, "Mix=1", "Drive=6", "Glue=1")
    assert abs(quiet_on["gain_db"] - quiet_off["gain_db"]) < 0.01


def test_glue_catches_fast_and_lets_go(tool):
    # The peak ratio of Glue 1 to Glue 0 per window, a sine stepping from
    # 0.05 to 0.5 at 0.5 s and back at 1.0 s. Measured: 0.998 before, 0.921
    # 5-15 ms after the step up, 0.892 at its end, 0.935 200 ms after the
    # step down, 0.998 a second after it.
    g = tool["glue"]
    assert g["quiet_before"] > 0.99
    assert g["loud_end"] < 0.95
    assert g["loud_5ms"] < 1 - 0.5 * (1 - g["loud_end"])     # half of it within 15 ms
    assert g["loud_end"] < g["after_200ms"] < g["quiet_before"]
    assert g["after_1s"] == pytest.approx(g["quiet_before"], abs=0.002)


def test_level_scales_the_wet_signal():
    flat = tone(440, 0.05, "Mix=1", "Drive=0", "Glue=0")
    down = tone(440, 0.05, "Mix=1", "Drive=0", "Glue=0", "Level=-6")
    assert down["gain_db"] - flat["gain_db"] == pytest.approx(-6.0, abs=0.01)


# --- aliasing ---------------------------------------------------------------

def alias_db_tanh(hz, peak, harmonics=60):
    """Aliases of a plain per-sample tanh of a sine, as fm1-sat-test counts
    them (every distinct reflected bin off the harmonics), over 0.5 s."""
    n = RATE // 2                                   # 2 Hz bins: hz must be even
    seg = [math.tanh(peak * math.sin(2 * math.pi * hz * i / RATE)) for i in range(n)]

    def power(f):
        w = 2 * math.pi * f / RATE
        c = 2 * math.cos(w)
        s1 = s2 = 0.0
        for x in seg:
            s1, s2 = x + c * s1 - s2, s1
        return (s1 * s1 + s2 * s2 - c * s1 * s2) / (n / 2) ** 2

    bins = set()
    for k in range(2, harmonics + 1):
        f = (k * hz) % RATE
        f = RATE - f if f > RATE // 2 else f
        if k * hz > RATE // 2 and f > 20 and f % hz:
            bins.add(f)
    return 10 * math.log10(sum(power(f) for f in bins) / power(hz))


def test_aliasing_against_a_plain_tanh():
    # The research's case (§6): a 3 kHz sine driven to a peak of about 1.5 in
    # the curve's units (0.5 x Drive 10 dB, less the band's -0.3 dB at
    # 3 kHz). The 11th-degree polynomial makes nothing above 33 kHz to
    # reflect: measured -125.8 dB (Smooth) and -125.0 dB (Dense), as the note
    # found, against -66.2 dB for tanh at the same peak.
    theirs = alias_db_tanh(3000, 1.5)
    assert theirs == pytest.approx(-66, abs=3)
    for shape in ("0", "1"):
        ours = tone(3000, 0.5, "Mix=1", "Glue=0", "Drive=10", f"Shape={shape}")["alias_db"]
        assert ours < -120


def test_aliasing_once_the_curve_clamps():
    # At full Drive the curve's plateau flat-tops the peaks, and harmonics
    # run on. Measured (2026-10-05), 3 kHz at 0.5: -49 dB with Clean Hi
    # at 6 kHz, -43 dB with it open; a 440 Hz sine stays near -85 dB.
    six = tone(3000, 0.5, "Mix=1", "Glue=0", "Drive=18", "Clean Hi=6000")["alias_db"]
    wide = tone(3000, 0.5, "Mix=1", "Glue=0", "Drive=18", "Clean Hi=20000")["alias_db"]
    low = tone(440, 0.5, "Mix=1", "Glue=0", "Drive=18")["alias_db"]
    assert six == pytest.approx(-49.3, abs=1.5) and wide == pytest.approx(-42.9, abs=1.5)
    assert low < -80


def test_after_an_engine_and_before_a_reverb(renderer, tmp_path):  # noqa: F811
    summary, left, right, _ = run(
        renderer, tmp_path,
        ["--engine", "macro", "--param", "Model=0", "--note", "0:45:100:0.5",
         "--note", "0:52:100:0.5", "--seconds", "1.5", *cli("Mix=1", "Drive=12", "Glue=0.5"),
         "--fx", "plate", "--fx-param", "Mix=0.3"], "chain")
    assert summary["fx"] == ["sat", "plate"]
    assert summary["nonfinite"] == 0
    assert rms(left, 0.1, 0.5) > 1e-2 and rms(left, 1.0, 1.4) > 1e-4


# --- fm1-sat-test: what fm1-render cannot drive ---------------------------------

def test_any_parameter_change_mid_stream_stays_finite(tool):
    # 20 s of noise at 0.5 with now and then a NaN, an infinity or -1e30 on
    # one channel; between blocks of 1-64 frames, up to two parameters jump
    # to their minimum, maximum, default, a random value, beyond the range,
    # NaN or an infinity. The guard's +/-16 at Level's +12 dB bounds it;
    # measured 15.9, the curve only pulls peaks in.
    s = tool["sweep"]
    assert s["samples"] > 20 * RATE
    assert s["nonfinite"] == 0 and s["peak"] < 64


def test_glide_is_block_size_independent_and_bypass_returns(tool):
    g = tool["glide"]
    assert g["block_independent"]
    assert g["wet_before"] > 0.1             # it was doing something...
    assert g["bypass_differ"] == 0           # ...and Mix back at 0 is the input


def test_silence_stays_silent_while_knobs_move_and_tails_end(tool):
    s = tool["silence"]
    assert s["moving_peak"] == 0.0           # every knob, Shape too, on silence
    assert s["last_block_peak"] == 0.0       # after loud noise: exact zeros...
    assert 0 < s["zero_after_ms"] < 1000     # ...within a second (657 ms)


def test_shape_crossfades(tool):
    # At full drive the switch bends the waveform no more than either shape's
    # own steady curve does (the largest second difference); an instant
    # switch would bend it 2.2 times as much.
    f = tool["fade"]
    assert f["before"] == 0.0
    assert f["curve_fade"] <= f["curve_steady"] * 1.001
    assert f["curve_hard"] > 2 * f["curve_steady"]
    assert f["settled"] < 1e-5               # Dense's own output 50 ms on


def test_every_build_computes_the_same_bits(tool):
    # 3 s of noise with bursts, every knob turned, blocks of 1-64 frames. No
    # libm and no fused multiply-adds: Apple clang on arm64, GCC 13 on x86-64
    # and Emscripten's wasm32 printed this digest (2026-10-05). A deliberate
    # change to the effect's arithmetic updates it.
    assert tool["digest"] == "3ff4720a"


def test_host_rates(tool):
    accepted = {rate: ok for rate, ok in tool["rates"]}
    assert accepted == {"0": False, "7999": False, "8000": True, "44118": True,
                        "48000": True, "96000": True, "384000": True, "400000": False,
                        "nan": False, "inf": False, "-44118": False}


def test_no_libm_in_the_object(renderer):  # noqa: F811
    # The effect's object calls nothing from the maths library: no symbol it
    # leaves undefined is one.
    obj = ENGINES / "build" / "our" / "src" / "fx_sat.o"
    out = subprocess.run(["nm", "-u", str(obj)], check=True, capture_output=True,
                         text=True).stdout
    names = {line.split()[-1].lstrip("_") for line in out.splitlines() if line.strip()}
    maths = {"sin", "cos", "tan", "exp", "exp2", "log", "log2", "log10", "pow", "sqrt",
             "tanh", "atan", "floor", "ceil", "fabs", "fmod", "round", "lrint"}
    assert not {n.rstrip("f") for n in names} & maths, names
