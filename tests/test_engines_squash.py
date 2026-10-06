"""Tests for dynamics pack 3's new effects (engines/README.md, "Squash" and
"Transient"): Squash (engines/src/fx_squash.cc), three compressors after
Airwindows Pop3, Pressure4 and ButterComp2 (MIT), and Transient
(engines/src/fx_shaper.cc), a transient shaper of our own.

Through fm1-render: registration and pages, the host contracts
(deterministic renders, any block size, any prior memory contents, any
parameter value, NaN included, bad input guarded, silence in gives silence
out). Through fm1-squash-test (engines/test/squash_test.cc), which reads the
effects' float output: each Type against the upstream loops in double
(tests/fixtures/squash-oracle.json, rendered in a container by
engines/third_party/airwindows/oracle/run-on-aeon.sh), and the Limiter's
Round mode against ClipOnly2 the same way; parameters and Types changed at
fixed frames at any block size and memory fill; silence; hostile input;
host rates; what Squash, Snap's gate and a Type change do; Transient's
centre, attack and sustain.

The figures in the comments were measured on the desktop build (Apple
clang, arm64, 2026-10-05).
"""
import json
import math
import subprocess
from pathlib import Path

import pytest

from tests.engine_helpers import ENGINES, render, renderer  # noqa: F401
from tests.test_engines_mi_fx import BANNED

TOOL = ENGINES / "build" / "fm1-squash-test"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "squash-oracle.json"

BUSY = {
    "squash": ["Type=0", "Squash=0.7", "Attack=3", "Release=80", "Ratio=0.8", "Output=6",
               "Mix=0.8", "Gate=-30", "Gate Depth=0.9", "Hold=0.2", "Gate Rel=40"],
    "shaper": ["Attack=80", "Sustain=-70", "Window=8", "Tail=900", "Output=-4", "Mix=0.8"],
}
MORE = {
    "squash": [["Type=1", "Squash=0.9", "Release=200", "Shape=-0.6", "Output=12"],
               ["Type=2", "Squash=1", "Output=-3", "Mix=0.6"]],
    "shaper": [["Attack=-100", "Sustain=100", "Window=100", "Tail=50"]],
}


@pytest.fixture(scope="module")
def tool(renderer):  # noqa: F811 -- the renderer fixture builds everything
    out = subprocess.run([str(TOOL)], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


@pytest.fixture(scope="module")
def listed(renderer):  # noqa: F811
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True,
                         text=True).stdout
    return {x["id"]: x for x in json.loads(out)}


def test_squash_is_registered(listed):
    e = listed["squash"]
    assert (e["name"], e["kind"], e["max_voices"]) == ("Squash", "audio_fx", 0)
    assert not any(b in (e["id"] + e["name"]).lower() for b in BANNED)
    assert "Airwindows" in e["credits"] and "MIT" in e["credits"]
    pages = [[p["name"] for p in e["params"] if p["page"] == k] for k in (0, 1, 2)]
    assert pages == [["Type", "Squash", "Attack", "Release"], ["Ratio", "Shape", "Output", "Mix"],
                     ["Gate", "Gate Depth", "Hold", "Gate Rel"]]
    by = {p["name"]: p for p in e["params"]}
    assert by["Type"]["names"] == ["Snap", "Mu", "Split"]
    assert all(len(p["name"]) <= 10 for p in e["params"])
    assert all(p["min"] <= p["def"] <= p["max"] for p in e["params"])
    assert (by["Output"]["unit"], by["Gate"]["unit"], by["Attack"]["unit"]) == ("db", "db", "ms")


def test_transient_is_registered(listed):
    e = listed["shaper"]
    assert (e["name"], e["kind"], e["max_voices"]) == ("Transient", "audio_fx", 0)
    assert "MIT" in e["credits"]
    pages = [[p["name"] for p in e["params"] if p["page"] == k] for k in (0, 1)]
    assert pages == [["Attack", "Sustain", "Window", "Tail"], ["Output", "Mix"]]
    by = {p["name"]: p for p in e["params"]}
    assert (by["Attack"]["min"], by["Attack"]["max"], by["Attack"]["unit"]) == (-100, 100, "pct")
    assert all(p["min"] <= p["def"] <= p["max"] for p in e["params"])


@pytest.mark.parametrize("fx", ["squash", "shaper"])
def test_instances_are_small(renderer, tmp_path, fx):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.05, fx=[(fx, [])])
    assert s["fx_bytes"][0] % 16 == 0 and s["fx_bytes"][0] <= 512   # 400 and 144 on the desktop


# --- host contracts through fm1-render --------------------------------------------

@pytest.mark.parametrize("fx", ["squash", "shaper"])
def test_block_size_and_memory_do_not_change_the_output(renderer, tmp_path, fx):  # noqa: F811
    for params in [BUSY[fx], *MORE[fx]]:
        wavs = []
        for extra in (["--frames", "64"], ["--frames", "7"], ["--frames", "1"],
                      ["--fill", "0xA5"], ["--fill", "0xFF"]):
            s, _, wav = render(renderer, tmp_path, input="noise", seconds=0.5,
                               fx=[(fx, params)], name="x".join(extra), extra=extra)
            assert s["nonfinite"] == 0
            wavs.append(wav.read_bytes())
        assert all(w == wavs[0] for w in wavs), params


@pytest.mark.parametrize("fx", ["squash", "shaper"])
@pytest.mark.parametrize("value,same_as", [("nan", None), ("1e9", "max"), ("-1e9", "min"),
                                           ("inf", "max")])
def test_out_of_range_parameters_clamp(renderer, tmp_path, listed, fx, value, same_as):  # noqa: F811
    e = listed[fx]
    bad = [f"{p['name']}={value}" for p in e["params"]]
    good = [] if same_as is None else [f"{p['name']}={p[same_as]}" for p in e["params"]]
    s, _, a = render(renderer, tmp_path, input="noise", seconds=0.3, fx=[(fx, bad)], name="bad")
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.3, fx=[(fx, good)], name="good")
    assert s["nonfinite"] == 0
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("fx", ["squash", "shaper"])
def test_silence_and_bad_input(renderer, tmp_path, fx):  # noqa: F811
    for params in [BUSY[fx], *MORE[fx]]:
        s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.5, fx=[(fx, params)])
        assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0
        s, _, _ = render(renderer, tmp_path, input="noise", seconds=0.5, fx=[(fx, params)],
                         extra=["--fault", "0..0.5:nan"], name="nan")
        assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0           # NaN reads as 0
        for bad in ("inf", "1e30"):
            s, _, _ = render(renderer, tmp_path, input="noise", seconds=0.5, fx=[(fx, params)],
                             extra=["--fault", f"0.1..0.2:{bad}"], name=bad)
            assert s["nonfinite"] == 0 and s["raw_peak"] <= 16 * 10 ** (24 / 20)


# --- against the upstream loops ------------------------------------------------------

# The residual (RMS of ours - theirs over the RMS of theirs, every 61st frame
# of 1.5 s, both channels) each case must stay under, in dB, and what was
# measured (2026-10-05): float against double, with every change of the port
# (fx_squash.cc's header). snap_c sits apart: with a fast attack and release
# Pop3's stereo link holds the gain at rel / (atk + rel) until the two
# channels' states are equal to the last bits of a double, which can take
# any time from a few milliseconds to for ever; Snap ends that hold when the
# gap is under 1e-14 of the state, so the two holds end at different times.
RESIDUAL_DB = {
    "snap_a": -55, "snap_b": -70, "snap_c": -25,       # measured -62.9, -78.2, -29.2
    "mu_a": -95, "mu_b": -105,                          # -102.5, -117.3
    "split_a": -95, "split_b": -105,                    # -104.1, -116.2
    "round": -120,                                      # -140.1
}


def test_the_oracle_fixture_is_the_pinned_upstream():
    ref = json.loads(FIXTURE.read_text())
    assert ref["upstream"] == "airwindows/airwindows@e718c9bcfcdd736deeddb08bffe6bce2aa8e0eea"
    assert ref["rate"] == 44100 and ref["decimate"] == 61
    assert sorted(ref["cases"]) == sorted(RESIDUAL_DB)


@pytest.mark.parametrize("case", sorted(RESIDUAL_DB))
def test_each_type_follows_its_upstream_loop(tool, case):
    ref = json.loads(FIXTURE.read_text())["cases"][case]["frames"]
    ours = tool["oracle"][case]
    assert tool["oracle"]["decimate"] == 61 and len(ours) == len(ref)
    if case == "round":
        ours, ref = ours[2:-8], ref[2:-8]   # the first frame and the last 4 ms are the lookahead's
    num = math.sqrt(sum((a - b) ** 2 for a, b in zip(ours, ref)) / len(ref))
    den = math.sqrt(sum(b * b for b in ref) / len(ref))
    assert 20 * math.log10(num / den + 1e-30) < RESIDUAL_DB[case], case


# --- fm1-squash-test: the contracts ---------------------------------------------------

def test_any_block_and_memory_with_changes_gives_the_same_bits(tool):
    # Every parameter changed every 50 ms (one write in seven NaN), Squash's
    # Type round the three, in blocks of 64, 1, 7 and random sizes and from
    # memory filled four ways: 60 renders, every one the 64-frame render's
    # bits, all finite.
    assert tool["contracts_tried"] == 60 and tool["contracts_same"] == 60
    assert tool["contracts_finite"]


def test_the_output_is_the_same_bits_on_every_build(tool):
    # No libm and no fused multiply-adds, so these renders hash the same on
    # every build that keeps FP_CONTRACT off; the browser's parity scenarios
    # (sim/web/test/scenarios.json) check the WebAssembly module. A
    # deliberate change to the DSP moves these: check it there, then pin.
    assert tool["contracts"] == ["c088893e", "bf108f80", "6a28efae", "ed36e4bd"]


def test_silence_hostile_input_and_rates(tool):
    assert tool["silence"]["peak"] == 0.0
    # NaN, infinities, 1e30 and +32 dBFS noise for 0.3 s: guarded to +/-16,
    # so the most is 16 x the busiest Output (+12 dB) and Mu's gain.
    assert tool["hostile"]["finite"] and tool["hostile"]["peak"] <= 16 * 10 ** (12 / 20)
    accepted = {rate: (a, b) for rate, a, b in tool["rates"]}
    for rate, ok in {"0": False, "7999": False, "8000": True, "44100": True, "44118": True,
                     "48000": True, "96000": True, "384000": True, "400000": False,
                     "nan": False, "inf": False, "-44118": False}.items():
        assert accepted[rate] == (ok, ok), rate
    assert tool["bytes"]["squash"] <= 512 and tool["bytes"]["shaper"] <= 256


# --- what the knobs do ---------------------------------------------------------------

def test_squash_turns_down_more_as_it_is_turned_up(tool):
    # A -6 dBFS sine, settled: the gain (dB) at Squash 0, 0.25, 0.5, 0.75, 1.
    # Measured: Snap 0, -1.7, -7.2, -11.3, -12.0 (Ratio 0.5 caps it at 1 -
    # 0.75 = -12 dB); Mu 0, 0, -6.8, -17.9, -49.1 (no makeup: Output brings
    # it back); Split 0, +0.4, -0.8, -3.8, -8.1.
    snap, mu, split = tool["reduction"]
    for curve in (snap, mu, split):
        assert abs(curve[0]) < 0.01
        assert curve[4] < curve[2] < curve[1] + 0.5
    assert snap[4] == pytest.approx(20 * math.log10(0.25), abs=0.2)
    assert mu[3] < -12 and split[4] < -6


def test_snap_and_mu_only_turn_down_and_split_lifts_a_little(tool):
    # On bursts at five settings, the largest output / input of any sample:
    # Snap and Mu never above 0 dB; Split's lift (into its own detector, then
    # divided by its makeup) at most +3 dB (measured +2.70).
    snap, mu, split = tool["most_gain"]
    assert snap <= 1e-5 and mu <= 1e-5
    assert 0 < split <= 3.0


def test_snaps_gate_shuts_and_opens(tool):
    # 0.5 s of -6 dBFS, then -50 dBFS under a -30 dB Gate at full depth: shut
    # (measured -219 dB, a quarter-sine to nothing); with Gate at its left
    # end (off) the quiet part passes at -50 dBFS.
    g = tool["gate"]
    assert g["shut_db"] < -120
    assert g["open_db"] == pytest.approx(-50.0, abs=0.2)


def test_a_type_change_starts_from_the_gain_in_force(tool):
    # Squash 0.8 on a loud sine and on bursts, the Type changed every 1,984
    # frames round the three: no step between samples larger than with any
    # Type held (measured 0.44 against 2.13).
    t = tool["types"]
    assert t["moving_step"] <= t["held_step"]


def test_transient_centre_is_a_true_bypass(tool):
    # Attack, Sustain and Output at 0: the input, bit for bit, at any Window,
    # Tail and Mix, and again once knobs turned away have come back.
    assert tool["shaper"]["centre_exact"]


def test_transient_shapes_attack_and_sustain(tool):
    # A 60 Hz hit (1 ms rise, 150 ms decay) every 0.5 s at -6 dBFS, the
    # second one: its first 10 ms (peak) and 100-300 ms after (RMS) against
    # the dry. Measured: Attack +100 % +8.1 dB on the onset, the tail
    # untouched; -100 % -4.9 dB; Sustain +100 % +4.8 dB on the tail, -100 %
    # -3.7 dB, the onset untouched; 50 / -50 % +4.1 / -2.0 dB.
    s = tool["shaper"]
    assert s["attack_up"]["onset_db"] > 6 and abs(s["attack_up"]["tail_db"]) < 0.3
    assert s["attack_down"]["onset_db"] < -3 and abs(s["attack_down"]["tail_db"]) < 0.3
    assert s["sustain_up"]["tail_db"] > 3 and abs(s["sustain_up"]["onset_db"]) < 0.3
    assert s["sustain_down"]["tail_db"] < -2.5 and abs(s["sustain_down"]["onset_db"]) < 0.3
    assert s["both"]["onset_db"] > 2 and s["both"]["tail_db"] < -1
    # Never more than 12 dB either way (the clamp): 0.5 x 10^(12/20) = 2.0.
    assert all(s[k]["peak"] <= 0.5 * 10 ** (12 / 20) for k in
               ("attack_up", "attack_down", "sustain_up", "sustain_down", "both"))


def test_transient_leaves_a_steady_tone_nearly_alone(tool):
    # Attack and Sustain at +100 %, a steady sine settled: within half a dB
    # (measured +0.27 dB at 1 kHz and at 100 Hz: the fast follower's ripple).
    s = tool["shaper"]
    assert abs(s["steady_1k_db"]) < 0.5 and abs(s["steady_100_db"]) < 0.5
