"""Tests for EQ, the three-band parametric equaliser (engines/src/fx_eq.cc,
parameters in engines/README.md, "EQ").

Through fm1-render: registration and pages, the host contracts (deterministic
renders, any block size, any prior memory contents, any parameter value,
NaN included, bad input guarded and not latched, silence in gives silence
out), the exact pass-through at 0 dB, and a chain. Through fm1-eq-test
(engines/test/eq_test.cc): the frequency response, measured in float
precision against the RBJ Audio EQ Cookbook's biquads computed here in double
precision; 0 dB passed bit for bit; parameters changed while audio runs at
any block size; clicks while bands jump; decay to exact silence; host rates;
the accuracy of fx_eq_math.h; and a hash of the output that every build
without fused multiply-adds must reproduce.
"""
import cmath
import json
import math
import subprocess

import pytest

from tests.engine_helpers import ENGINES, RATE, render, renderer, rms  # noqa: F401
from tests.test_engines_mi_fx import BANNED, run

TOOL = ENGINES / "build" / "fm1-eq-test"
LSB = 1 / 32767.0

NAMES = ["Low Freq", "Low Gain", "Low Q", "Mid Freq", "Mid Gain", "Mid Q",
         "High Freq", "High Gain", "High Q", "Level"]
DEFAULTS = {"Low Freq": 100, "Low Gain": 0, "Low Q": 0.7071, "Mid Freq": 1000, "Mid Gain": 0,
            "Mid Q": 1, "High Freq": 8000, "High Gain": 0, "High Q": 0.7071, "Level": 0}

# Every parameter away from its default.
BUSY = ["Low Freq=150", "Low Gain=5", "Low Q=1.2", "Mid Freq=1800", "Mid Gain=-7",
        "Mid Q=3", "High Freq=5000", "High Gain=4", "High Q=0.5", "Level=-3"]


def fx(*params):
    return [("eq", list(params))]


def cli(*params):
    args = ["--fx", "eq"]
    for p in params:
        args += ["--fx-param", p]
    return args


@pytest.fixture(scope="module")
def tool(renderer):  # noqa: F811 -- the renderer fixture builds everything
    out = subprocess.run([str(TOOL)], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def catalog(renderer):  # noqa: F811
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True,
                         text=True).stdout
    return {x["id"]: x for x in json.loads(out)}


def test_eq_is_registered(renderer):  # noqa: F811
    e = catalog(renderer)["eq"]
    assert (e["name"], e["kind"], e["max_voices"]) == ("EQ", "audio_fx", 0)
    assert not any(b in (e["id"] + e["name"]).lower() for b in BANNED)
    assert "MIT" in e["credits"] and "Simper" in e["credits"] and "public domain" in e["credits"]
    pages = [[p["name"] for p in e["params"] if p["page"] == k] for k in (0, 1, 2)]
    assert pages == [NAMES[0:3], NAMES[3:6], NAMES[6:10]]
    assert all(len(p["name"]) <= 12 and p["type"] == 0 for p in e["params"])
    assert all(p["min"] <= p["def"] <= p["max"] for p in e["params"])
    assert {p["name"]: p["def"] for p in e["params"]} == pytest.approx(DEFAULTS)
    units = {p["name"]: p["unit"] for p in e["params"]}
    assert [n for n in NAMES if units[n] == "hz"] == ["Low Freq", "Mid Freq", "High Freq"]


def test_instance_is_small(renderer, tmp_path):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.05, fx=fx())
    assert s["fx_bytes"][0] % 16 == 0 and s["fx_bytes"][0] <= 512


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
    params = catalog(renderer)["eq"]["params"]
    bad = [f"{p['name']}={value}" for p in params]
    good = [] if same_as is None else [f"{p['name']}={p[same_as]}" for p in params]
    s, _, a = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*bad), name="bad")
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*good), name="good")
    assert s["nonfinite"] == 0
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("params", [
    [],
    BUSY,
    ["Low Gain=15", "Low Freq=20", "Low Q=2", "Mid Gain=15", "Mid Q=10", "Level=15"],
    ["Low Gain=-15", "Mid Gain=-15", "High Gain=-15", "High Freq=18000", "High Q=0.3"],
])
def test_silence_in_is_silence_out(renderer, tmp_path, params):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.5, fx=fx(*params))
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


BAD_INPUT = {"nan": "nan", "inf": "inf", "huge": "1e30"}


@pytest.mark.parametrize("bad", sorted(BAD_INPUT))
def test_bad_input_is_guarded_and_not_latched(renderer, tmp_path, bad):  # noqa: F811
    # The input guard reads NaN as 0 and clamps everything else to +/-16, so
    # no state is poisoned: the filters are linear, so the fault's effect is
    # a tail that dies away, and a second after the fault ends the output is
    # the fault-free output within one LSB.
    base = ["--input", "noise", "--seconds", "2.0", *cli(*BUSY)]
    _, clean_l, clean_r, _ = run(renderer, tmp_path, base, "clean")
    fault = ["--fault", f"0.2..0.5:{BAD_INPUT[bad]}"]
    s, left, right, _ = run(renderer, tmp_path, [*base, *fault], "fault")
    assert s["nonfinite"] == 0
    tail = slice(int(1.5 * RATE), None)
    assert max(abs(a - b) for a, b in zip(left[tail], clean_l[tail])) <= LSB
    assert max(abs(a - b) for a, b in zip(right[tail], clean_r[tail])) <= LSB


def test_nan_input_reads_as_silence(renderer, tmp_path):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY),
                     extra=["--fault", "0..0.5:nan"])
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


@pytest.mark.parametrize("params", [
    [],
    ["Low Freq=20", "Low Q=2", "Mid Freq=18000", "Mid Q=0.3", "High Freq=1000", "High Q=2"],
])
def test_zero_db_passes_the_input_through(renderer, tmp_path, params):  # noqa: F811
    # Every gain and Level at 0 dB: the WAV is byte for byte the one a plain
    # Gain=1 effect writes, whatever the frequencies and Qs.
    ref, _, ref_wav = render(renderer, tmp_path, input="noise", seconds=1.0,
                             fx=[("test-gain", ["Gain=1"])], name="ref")
    out, _, out_wav = render(renderer, tmp_path, input="noise", seconds=1.0, fx=fx(*params),
                             name="eq")
    assert out["raw_peak"] == ref["raw_peak"]
    assert out_wav.read_bytes() == ref_wav.read_bytes()


def test_level_scales_the_output(renderer, tmp_path):  # noqa: F811
    _, full, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="full",
                        fx=fx(*BUSY[:9], "Level=0"))
    _, cut, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="cut",
                       fx=fx(*BUSY[:9], "Level=-12"))
    assert 20 * math.log10(rms(cut, 0.2, 1.0) / rms(full, 0.2, 1.0)) == pytest.approx(-12, abs=0.01)


def test_after_an_engine_and_before_a_reverb(renderer, tmp_path):  # noqa: F811
    summary, left, right, _ = run(
        renderer, tmp_path,
        ["--engine", "macro", "--param", "Model=0", "--note", "0:45:100:0.5",
         "--note", "0:52:100:0.5", "--seconds", "1.5", *cli("Low Gain=6", "High Gain=-6"),
         "--fx", "plate", "--fx-param", "Mix=0.3"], "chain")
    assert summary["fx"] == ["eq", "plate"]
    assert summary["nonfinite"] == 0
    assert rms(left, 0.1, 0.5) > 1e-2 and rms(left, 1.0, 1.4) > 1e-4


# --- the response, against the RBJ Audio EQ Cookbook -------------------------------

def rbj(kind, f0, db, q):
    """The cookbook's peakingEQ, lowShelf and highShelf (with Q), as
    (b, a): Robert Bristow-Johnson, "Audio EQ Cookbook", W3C Note
    2021-06-08. Computed independently of the effect."""
    a_ = 10 ** (db / 40)
    w0 = 2 * math.pi * f0 / RATE
    c, alpha = math.cos(w0), math.sin(w0) / (2 * q)
    s = 2 * math.sqrt(a_) * alpha
    if kind == "bell":
        return ([1 + alpha * a_, -2 * c, 1 - alpha * a_], [1 + alpha / a_, -2 * c, 1 - alpha / a_])
    if kind == "low":
        return ([a_ * ((a_ + 1) - (a_ - 1) * c + s), 2 * a_ * ((a_ - 1) - (a_ + 1) * c),
                 a_ * ((a_ + 1) - (a_ - 1) * c - s)],
                [(a_ + 1) + (a_ - 1) * c + s, -2 * ((a_ - 1) + (a_ + 1) * c),
                 (a_ + 1) + (a_ - 1) * c - s])
    return ([a_ * ((a_ + 1) + (a_ - 1) * c + s), -2 * a_ * ((a_ - 1) + (a_ + 1) * c),
             a_ * ((a_ + 1) + (a_ - 1) * c - s)],
            [(a_ + 1) - (a_ - 1) * c + s, 2 * ((a_ - 1) - (a_ + 1) * c),
             (a_ + 1) - (a_ - 1) * c - s])


def reference_db(settings, hz):
    p = dict(DEFAULTS, **settings)
    z = cmath.exp(-2j * math.pi * hz / RATE)
    h = 1
    for kind, band in (("low", "Low"), ("bell", "Mid"), ("high", "High")):
        b, a = rbj(kind, p[f"{band} Freq"], p[f"{band} Gain"], p[f"{band} Q"])
        h *= (b[0] + b[1] * z + b[2] * z * z) / (a[0] + a[1] * z + a[2] * z * z)
    return 20 * math.log10(abs(h)) + p["Level"]


# The settings eq_test.cc measures (kSettings), by name.
SETTINGS = {
    "low_p12_100": {"Low Gain": 12, "Low Freq": 100},
    "low_m9_300_q15": {"Low Gain": -9, "Low Freq": 300, "Low Q": 1.5},
    "low_p15_20_q2": {"Low Gain": 15, "Low Freq": 20, "Low Q": 2},
    "bell_p9_1k": {"Mid Gain": 9},
    "bell_m15_5k_q8": {"Mid Gain": -15, "Mid Freq": 5000, "Mid Q": 8},
    "bell_p15_15k_q05": {"Mid Gain": 15, "Mid Freq": 15000, "Mid Q": 0.5},
    "bell_p6_60_q10": {"Mid Gain": 6, "Mid Freq": 60, "Mid Q": 10},
    "high_p6_8k": {"High Gain": 6},
    "high_m12_2k_q2": {"High Gain": -12, "High Freq": 2000, "High Q": 2},
    "high_p15_18k_q03": {"High Gain": 15, "High Freq": 18000, "High Q": 0.3},
    "all_three": {"Low Gain": 4, "Low Freq": 80, "Mid Gain": -6, "Mid Freq": 700, "Mid Q": 2,
                  "High Gain": 5, "High Freq": 6000, "High Q": 1, "Level": -6},
}


def test_response_matches_the_cookbook(tool):
    # The trapezoidal SVF bands are the cookbook's filters, prewarped at the
    # same frequency, in another structure: the measured response (the DFT
    # of each impulse response, in float) agrees with the cookbook's biquads
    # in double precision within 0.001 dB at every frequency from 20 Hz to
    # 21 kHz (measured 2026-10-05: worst 8e-4 dB, the 60 Hz Q 10 bell; the
    # rest under 3e-4 dB).
    assert set(tool["response"]) == set(SETTINGS)
    for name, settings in SETTINGS.items():
        r = tool["response"][name]
        assert r["tail"] < 1e-6, name                 # the impulse response has died out
        for hz, db in r["db"]:
            assert db == pytest.approx(reference_db(settings, hz), abs=0.002), (name, hz)


def test_each_band_does_what_it_says(tool):
    db = {name: dict((hz, v) for hz, v in r["db"]) for name, r in tool["response"].items()}
    # The bell: its gain at its frequency, exactly; a cut as deep as a boost.
    assert db["bell_p9_1k"][1000] == pytest.approx(9.0, abs=1e-4)
    assert db["bell_m15_5k_q8"][5000] == pytest.approx(-15.0, abs=1e-4)
    assert db["bell_p15_15k_q05"][15000] == pytest.approx(15.0, abs=1e-4)
    # A narrow bell (Q 8) leaves an octave away nearly alone; a wide one does not.
    assert abs(db["bell_m15_5k_q8"][2500]) < 0.2 and db["bell_p9_1k"][2000] > 1.5
    # The shelves: the full gain far into the shelf, half of it (in dB) at
    # the band's frequency, nothing far outside it.
    assert db["low_p12_100"][20] == pytest.approx(12.0, abs=0.05)
    assert db["low_p12_100"][100] == pytest.approx(6.0, abs=1e-4)
    assert abs(db["low_p12_100"][2000]) < 0.001
    assert db["high_p6_8k"][8000] == pytest.approx(3.0, abs=1e-4)
    assert db["high_p6_8k"][21000] == pytest.approx(6.0, abs=0.01)
    assert abs(db["high_p6_8k"][200]) < 0.001
    assert db["high_m12_2k_q2"][2000] == pytest.approx(-6.0, abs=1e-4)
    # Q on a shelf: 0.7071 does not overshoot; 2 overshoots on both sides
    # of the corner (the bump and dip of a resonant shelf).
    assert max(db["low_p12_100"].values()) <= 12.0 + 1e-4
    assert db["high_m12_2k_q2"][1250] > 4.0 and db["high_m12_2k_q2"][5000] < -13.5
    # Level adds its dB to everything.
    assert db["all_three"][700] == pytest.approx(reference_db(SETTINGS["all_three"], 700),
                                                 abs=1e-3)


# --- fm1-eq-test: what fm1-render cannot drive ---------------------------------

def test_zero_db_is_bit_exact(tool):
    e = tool["exact"]
    # Negative zero, subnormals, +/-15.9 and noise: no output sample differs
    # from its input in any bit, at the defaults, at extreme frequencies and
    # Qs, and while every frequency and Q glides with the gains at 0 dB.
    assert e["defaults"] == 0 and e["odd"] == 0 and e["sweep_at_zero"] == 0
    # Three bands and Level turned up at frame 2000 and back to 0 dB at
    # 6000-6001: exact again once the glides land (5 ms time constant; 0 dB
    # is reached exactly, not approached), at any block size.
    assert 6001 < e["round_trip_last"] < 6001 + 0.08 * RATE
    assert e["round_trip_last_7"] == e["round_trip_last"]


def test_any_parameter_change_mid_stream_stays_finite(tool):
    # 20 s of noise at 0.5; between blocks of 1-64 frames, up to two
    # parameters jump to their minimum, maximum, default, a random value,
    # beyond the range, NaN or an infinity. Measured peak 9.5: three bands
    # and Level can each add 15 dB (a gain of 5.6), on noise at 0.5.
    s = tool["sweep"]
    assert s["samples"] > 20 * RATE
    assert s["nonfinite"] == 0 and s["peak"] < 50


def test_glide_is_block_size_independent_and_reaches_its_target(tool):
    g = tool["glide"]
    assert g["block_independent"]
    # Level 0 -> -15 dB fades over ~5 ms instead of cutting: within the
    # first millisecond the output is still near its level...
    assert g["first_ms"] > 0.5 * g["before"]
    # ...and 50 ms later it is exactly the 0 dB output times 10^(-15/20).
    assert g["tail_exact"]
    assert g["level"] == pytest.approx(10 ** (-15 / 20), rel=1e-6)


def test_jumps_do_not_click(tool):
    # A 100 Hz sine through a band whose frequency, gain or Q jumps every
    # 50 ms (Level too). Switching at once between the two settled filters
    # would bend the waveform by 0.02-1.7 (second difference) at the
    # switch; the glide and the SVF's charge-carrying states keep the
    # largest bend 52-280 times smaller (measured 2026-10-05), within a few
    # times what the gain change itself must make.
    for name, c in tool["clicks"].items():
        assert c["moving"] * 30 < c["switch"], name
        assert c["moving"] < 0.05, name


def test_tails_decay_to_exact_silence(tool):
    s = tool["silence"]
    assert s["peak"] == 0.0                   # silence in, from any memory, any setting
    # After a second of noise, every band at its lowest frequency and
    # highest Q: the slowest tail is the 20 Hz bell at Q 10 boosted 15 dB
    # (a pole Q of 23.7, time constant 0.38 s), measured exact zero after
    # 12.3 s; cut, after 2.0 s. Both states of a band flush together, so a
    # low band's tail decays at the filter's own rate down to the flush.
    assert 0 < s["zero_after_boost"] < 15 * RATE
    assert 0 < s["zero_after_cut"] < 3 * RATE


def test_host_rates(tool):
    accepted = {rate: ok for rate, ok, _ in tool["rates"]}
    assert accepted == {"0": False, "7999": False, "8000": True, "44118": True,
                        "48000": True, "96000": True, "384000": True, "400000": False,
                        "nan": False, "inf": False, "-44118": False}
    # A +9 dB bell at 1 kHz peaks at +9 dB at every accepted rate.
    for rate, ok, peak_db in tool["rates"]:
        if ok:
            assert peak_db == pytest.approx(9.0, abs=0.01), rate


def test_math_without_libm_is_accurate(tool):
    a = tool["approx"]
    assert a["exp2_rel"] < 2e-7               # measured 8.7e-8
    assert a["exp2_0"] == 1.0                 # 0 dB is a gain of exactly 1
    assert a["exp2_nan"] == a["exp2_low"] == pytest.approx(2.0 ** -100)
    assert a["log2_abs"] < 2e-6               # measured 1.0e-6, at 9.3e4 (log2 ~ 16.5)
    assert a["tan_rel"] < 2e-6                # measured 6.5e-7, near 0.45 pi


def test_output_hash_is_pinned(tool):
    # FNV-1a over every float of three renders (eq_test.cc, Hash): the same
    # on every build that keeps to IEEE single precision without fused
    # multiply-adds [verified 2026-10-05: Apple clang arm64; GCC x86-64 and
    # i386 (SSE), Emscripten WebAssembly, in containers]. A change here is a
    # change of sound: re-pin only on purpose.
    assert tool["hash"] == ["f6feae6f", "c41215f3", "d6ac4aa9"]
