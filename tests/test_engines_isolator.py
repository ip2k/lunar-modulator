"""Tests for Isolator, the three-band kill EQ (engines/src/fx_isolator.cc,
parameters in engines/README.md, "Isolator").

Through fm1-render: registration and pages, the host contracts (deterministic
renders, any block size, any prior memory contents, any parameter value,
NaN included, bad input guarded and not latched, silence in gives silence
out), and unity passing the input bit for bit. Through fm1-isolator-test
(engines/test/isolator_test.cc): the frequency response, measured in float
(the bands' flat sum, the kill depths, the crossover points, the knob law),
parameters changed while audio runs, with block sizes that change between
calls, switching without clicks, and the host rates it accepts.
"""
import json
import subprocess

import pytest

from tests.engine_helpers import ENGINES, RATE, render, renderer, rms  # noqa: F401
from tests.test_engines_mi_fx import BANNED, run

TOOL = ENGINES / "build" / "fm1-isolator-test"
LSB = 1 / 32767.0

# Every parameter away from its default.
BUSY = ["Low=0.9", "Mid=0.4", "High=0.6", "Kill=2", "Low Xover=150", "High Xover=3500"]
KILL_NAMES = ["None", "Low", "Mid", "Low+Mid", "High", "Low+High", "Mid+High", "All"]


def fx(*params):
    return [("isolator", list(params))]


def cli(*params):
    args = ["--fx", "isolator"]
    for p in params:
        args += ["--fx-param", p]
    return args


@pytest.fixture(scope="module")
def tool(renderer):  # noqa: F811 -- the renderer fixture builds everything
    out = subprocess.run([str(TOOL)], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def db_at(response, hz):
    """The level in dB at hz from one of the tool's [hz, dB] lists."""
    return dict((f, d) for f, d in response)[hz]


def test_isolator_is_registered(renderer):  # noqa: F811
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True,
                         text=True).stdout
    e = {x["id"]: x for x in json.loads(out)}["isolator"]
    assert (e["name"], e["kind"], e["max_voices"]) == ("Isolator", "audio_fx", 0)
    assert not any(b in (e["id"] + e["name"]).lower() for b in BANNED)
    assert "MIT" in e["credits"] and "Linkwitz-Riley" in e["credits"]
    pages = [[p["name"] for p in e["params"] if p["page"] == k] for k in (0, 1)]
    assert pages == [["Low", "Mid", "High", "Kill"], ["Low Xover", "High Xover"]]
    assert all(len(p["name"]) <= 12 for p in e["params"])
    assert all(p["min"] <= p["def"] <= p["max"] for p in e["params"])
    kill = e["params"][3]
    assert kill["type"] == 1 and kill["names"] == KILL_NAMES
    assert kill["flags"] == ["mod"]                      # lockable, modulated rounded
    assert [p["unit"] for p in e["params"][4:]] == ["hz", "hz"]


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
    params = {x["id"]: x for x in json.loads(out)}["isolator"]["params"]
    bad = [f"{p['name']}={value}" for p in params]
    good = [] if same_as is None else [f"{p['name']}={p[same_as]}" for p in params]
    s, _, a = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*bad), name="bad")
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*good), name="good")
    assert s["nonfinite"] == 0
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("params", [
    [],
    BUSY,
    ["Low=1", "Mid=1", "High=1", "Low Xover=80", "High Xover=5000"],
    ["Kill=7"],
])
def test_silence_in_is_silence_out(renderer, tmp_path, params):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.5, fx=fx(*params))
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


BAD_INPUT = {"nan": "nan", "inf": "inf", "huge": "1e30"}


@pytest.mark.parametrize("bad", sorted(BAD_INPUT))
def test_bad_input_is_guarded_and_not_latched(renderer, tmp_path, bad):  # noqa: F811
    # The input guard reads NaN as 0 and clamps everything else to +/-16, so
    # no state is poisoned: half a second after the fault ends the output is
    # the fault-free output, within a 16-bit step.
    base = ["--input", "noise", "--seconds", "1.5", *cli(*BUSY)]
    _, clean_l, clean_r, _ = run(renderer, tmp_path, base, "clean")
    fault = ["--fault", f"0.2..0.5:{BAD_INPUT[bad]}"]
    s, left, right, _ = run(renderer, tmp_path, [*base, *fault], "fault")
    assert s["nonfinite"] == 0
    tail = slice(RATE, None)
    assert max(abs(a - b) for a, b in zip(left[tail], clean_l[tail])) <= LSB
    assert max(abs(a - b) for a, b in zip(right[tail], clean_r[tail])) <= LSB


def test_nan_input_reads_as_silence(renderer, tmp_path):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY),
                     extra=["--fault", "0..0.5:nan"])
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


# --- unity is the input -------------------------------------------------------

@pytest.mark.parametrize("params", [
    [],                                          # the defaults
    ["Low Xover=100", "High Xover=4500"],         # crossovers do not leave unity
    ["Low=0.75", "Mid=0.75", "High=0.75", "Kill=0"],
])
def test_unity_passes_the_input_bit_for_bit(renderer, tmp_path, params):  # noqa: F811
    ref, _, ref_wav = render(renderer, tmp_path, input="noise", seconds=1.0,
                             fx=[("test-gain", ["Gain=1"])], name="ref")
    out, _, out_wav = render(renderer, tmp_path, input="noise", seconds=1.0,
                             fx=fx(*params), name="unity")
    assert out["raw_peak"] == ref["raw_peak"]
    assert out_wav.read_bytes() == ref_wav.read_bytes()


def test_unity_passes_the_clamped_input(renderer, tmp_path):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(),
                     extra=["--fault", "0.1..0.2:inf"])
    assert s["nonfinite"] == 0 and s["raw_peak"] == 16.0


def test_unity_passes_float_input_exactly(tool):
    # In float, every sample of both channels, from any memory fill; and in
    # the glide script, before the first change and from 5 ms (the
    # crossfade, 221 samples at 44,118 Hz) after every band is back at unity.
    assert tool["defaults"]["exact"]
    g = tool["glide"]
    assert g["exact_before"]
    assert g["unity_at"] < g["exact_from"] <= g["unity_at"] + 221


# --- the response (fm1-isolator-test, float, 32,768-sample impulse responses) --

def test_bands_sum_flat(tool):
    # low + mid + high at unity is AP2(f1) AP2(f2): flat in magnitude. Over
    # 301 log-spaced points from 20 Hz to 20 kHz the worst deviation is float
    # rounding: 2.7e-5 dB measured (2026-10-05).
    assert tool["response"]["sum_worst_db"] < 1e-3


def test_crossovers_are_linkwitz_riley(tool):
    r = tool["response"]
    # Each band is -6.02 dB (half amplitude) at its crossover: the LR4 point.
    for band, hz in (("low_only", 250), ("mid_only", 250), ("mid_only", 2500),
                     ("high_only", 2500), ("low_only_80", 80), ("low_only_400", 400),
                     ("high_only_1500", 1500), ("high_only_5000", 5000)):
        assert db_at(r[band], hz) == pytest.approx(-6.02, abs=0.02), (band, hz)
    # 24 dB per octave beyond: two octaves past f1 the low band is down 30+ dB.
    assert db_at(r["low_only"], 1000) < -45


def test_kills_are_deep(tool):
    # The figures of the research note (§4.4, lane 2 numerics), reproduced:
    # kill low -64 dB at 40 Hz, kill high -80 dB at 15 kHz, kill mid -30 dB
    # at 600 Hz and only -19 dB at 1.5 kHz (the mid band is three octaves
    # wide, and the crossovers' skirts overlap).
    r = tool["response"]
    assert db_at(r["kill_low"], 40) < -63
    assert db_at(r["kill_low"], 1000) == pytest.approx(0.0, abs=0.05)
    assert db_at(r["kill_high"], 15000) < -80
    assert db_at(r["kill_high"], 150) == pytest.approx(0.0, abs=0.01)
    assert db_at(r["kill_mid"], 600) < -29
    assert db_at(r["kill_mid"], 1000) < -30
    assert db_at(r["kill_mid"], 1500) == pytest.approx(-19.0, abs=0.3)
    assert db_at(r["kill_mid"], 40) == pytest.approx(0.0, abs=0.02)
    assert db_at(r["kill_mid"], 15000) == pytest.approx(0.0, abs=0.02)
    assert r["kill_mask_is_zero_gain"]


def test_knob_law(tool):
    # 0.75 is unity, 1 is x2 (+6.02 dB), 0.5 is (0.5 / 0.75)^3 (-10.57 dB).
    r = tool["response"]
    assert db_at(r["boost_low"], 20) == pytest.approx(6.02, abs=0.01)
    assert db_at(r["half_low"], 20) == pytest.approx(-10.57, abs=0.01)
    assert all(d == pytest.approx(6.0206, abs=0.001) for _, d in r["boost_all"])


# --- fm1-isolator-test: what fm1-render cannot drive ---------------------------

def test_any_parameter_change_mid_stream_stays_finite(tool):
    # 20 s of noise (peaks 0.5); between blocks of 1-64 frames, up to two
    # parameters jump to their minimum, maximum, default, a random value,
    # beyond the range, NaN or an infinity. Measured peak 1.82 (2026-10-05):
    # every band can reach x2. Then 20 s of silence under the same changes:
    # exact silence.
    s = tool["sweep"]
    assert s["samples"] > 40 * RATE
    assert s["nonfinite"] == 0 and s["peak"] < 3.0
    assert s["silence_peak"] == 0.0


def test_glides_are_block_size_independent(tool):
    assert tool["glide"]["block_independent"]


@pytest.mark.parametrize("kind", ["kill", "xover", "unity"])
def test_switching_does_not_click(tool, kind):
    # Kill through every mask, the crossovers between their extremes, and
    # Low in and out of unity, every third block, on a 100 Hz sine at 0.5:
    # the output's largest step stays within 1.4x the sine's own (0.0071;
    # measured 1.15x, 1.10x and 1.31x). A hard switch would step by up to 0.5.
    s = tool["switching"]
    assert s[kind] < 1.4 * s["in_step"]


def test_host_rates(tool):
    accepted = {rate: (ok, finite) for rate, ok, finite in tool["rates"]}
    assert {r: ok for r, (ok, _) in accepted.items()} == {
        "0": False, "7999": False, "8000": True, "44118": True, "48000": True, "96000": True,
        "384000": True, "400000": False, "nan": False, "inf": False, "-44118": False}
    assert all(finite for _, finite in accepted.values())   # High Xover capped at 0.45 fs


def test_after_an_engine_and_before_a_reverb(renderer, tmp_path):  # noqa: F811
    summary, left, right, _ = run(
        renderer, tmp_path,
        ["--engine", "macro", "--param", "Model=0", "--note", "0:45:100:0.5",
         "--note", "0:52:100:0.5", "--seconds", "1.5", *cli("Low=0.2", "Kill=4"),
         "--fx", "plate", "--fx-param", "Mix=0.3"], "chain")
    assert summary["fx"] == ["isolator", "plate"]
    assert summary["nonfinite"] == 0
    assert rms(left, 0.1, 0.5) > 1e-2 and rms(left, 1.0, 1.4) > 1e-4
