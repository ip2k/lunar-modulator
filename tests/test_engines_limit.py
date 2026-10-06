"""Tests for the Limiter, the look-ahead brickwall limiter
(engines/src/fx_limit.cc, parameters in engines/README.md, "Limiter").

Through fm1-render: registration and pages, the host contracts (deterministic
renders, any block size, any prior memory contents, any parameter value,
NaN included, bad input guarded and not latched, silence in gives silence
out), the ceiling on the raw effect output, transparency below it, and every
parameter doing what it says. Through fm1-limit-test
(engines/test/limit_test.cc), which reads the effect's float output with no
16-bit WAV and no bus limiter after it: the ceiling on hostile input (square
waves, impulses, full-scale and clamped noise, DC steps, onsets, a chirp)
under 1,980 settings, latency against Lookahead at four host rates, exact
transparency, the release time, Link, parameters changed while audio runs at
block sizes that change between calls, the Lookahead and Mode crossfades
(the ceiling held by the gain path, not the final clamp, while they are
turned under limiting, and no click while they are turned every few
blocks), ROUND against ClipOnly2's recurrence, host rates and instance
sizes.

The figures in the comments were measured on the desktop build (2026-10-02;
ROUND's, 2026-10-05).
"""
import json
import math
import subprocess

import pytest

from tests.engine_helpers import ENGINES, RATE, render, renderer, rms  # noqa: F401
from tests.test_engines_mi_fx import BANNED, run

TOOL = ENGINES / "build" / "fm1-limit-test"
LSB = 1 / 32767.0
D_DEFAULT = 88                       # 2 ms at 44,118 Hz, rounded to a frame


def db(x):
    return 10 ** (x / 20)


# Every parameter away from its default, and loud enough to limit: the
# host's +/-0.5 noise at +12 dB.
BUSY = ["Ceiling=-4", "Drive=12", "Release=40", "Lookahead=3.3", "Link=0.6", "Mix=0.9"]


def fx(*params):
    return [("limit", list(params))]


def cli(*params):
    args = ["--fx", "limit"]
    for p in params:
        args += ["--fx-param", p]
    return args


@pytest.fixture(scope="module")
def tool(renderer):  # noqa: F811 -- the renderer fixture builds everything
    out = subprocess.run([str(TOOL)], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def test_limiter_is_registered(renderer):  # noqa: F811
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True,
                         text=True).stdout
    e = {x["id"]: x for x in json.loads(out)}["limit"]
    assert (e["name"], e["kind"], e["max_voices"]) == ("Limiter", "audio_fx", 0)
    assert not any(b in (e["id"] + e["name"]).lower() for b in BANNED)
    assert "MIT" in e["credits"] and "Luff" in e["credits"]
    pages = [[p["name"] for p in e["params"] if p["page"] == k] for k in (0, 1)]
    assert pages == [["Ceiling", "Drive", "Release", "Lookahead"], ["Mode", "Link", "Mix"]]
    mode = [p for p in e["params"] if p["name"] == "Mode"][0]
    assert mode["type"] == 1 and mode["names"] == ["Brickwall", "Soft Clip", "Round"]
    assert all(len(p["name"]) <= 12 for p in e["params"])
    assert all(p["min"] <= p["def"] <= p["max"] for p in e["params"])


def test_instance_size_follows_the_rate(renderer, tmp_path, tool):  # noqa: F811
    # 5 ms of frames, at most 510: 11,952 bytes at the FM-1's rate, 29,008
    # at the cap (102 kHz and above), with a second set of box filters for a
    # Lookahead crossfade. A refused rate still gets a size. ROUND (2026-10-05)
    # added a fourth float to each frame of the line (ROUND's share of Mode)
    # and its stage's state: 11,008 and 26,912 bytes before.
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.05, fx=fx())
    assert s["fx_bytes"] == [11952]
    sizes = {rate: size for rate, _, size in tool["rates"]}
    assert sizes["44118"] == 11952 and sizes["48000"] == 12928 and sizes["96000"] == 25408
    assert sizes["102000"] == sizes["192000"] == sizes["384000"] == 29008
    assert all(size % 16 == 0 for size in sizes.values())


# --- host contracts ---------------------------------------------------------

def test_rendering_is_deterministic(renderer, tmp_path):  # noqa: F811
    _, _, a = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY), name="a")
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY), name="b")
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("extra", [[], ["Lookahead=0"], ["Mode=1"]])
def test_block_size_does_not_change_the_output(renderer, tmp_path, extra):  # noqa: F811
    wavs = []
    for frames in ("64", "7", "1"):
        _, _, wav = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx(*BUSY, *extra),
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
    params = {x["id"]: x for x in json.loads(out)}["limit"]["params"]
    bad = [f"{p['name']}={value}" for p in params]
    good = [] if same_as is None else [f"{p['name']}={p[same_as]}" for p in params]
    s, _, a = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*bad), name="bad")
    _, _, b = render(renderer, tmp_path, input="noise", seconds=0.3, fx=fx(*good), name="good")
    assert s["nonfinite"] == 0
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("params", [
    [],
    ["Drive=24", "Ceiling=-24", "Lookahead=0"],
    ["Mode=1", "Drive=24", "Link=0", "Mix=0.3"],
    BUSY,
])
def test_silence_in_is_silence_out(renderer, tmp_path, params):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="silence", seconds=0.5, fx=fx(*params))
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


BAD_INPUT = {"nan": "nan", "inf": "inf", "huge": "1e30"}


@pytest.mark.parametrize("bad", sorted(BAD_INPUT))
def test_bad_input_is_guarded_and_not_latched(renderer, tmp_path, bad):  # noqa: F811
    # The input guard reads NaN as 0 and clamps everything else to +/-16, the
    # dry path included. A clamped sample pulls the gain down, and Release
    # 10 ms brings it back: half a second after the fault ends the output is
    # the fault-free output, sample for sample.
    base = ["--input", "noise", "--seconds", "1.5", *cli(*BUSY, "Release=10")]
    _, clean_l, clean_r, _ = run(renderer, tmp_path, base, "clean")
    fault = ["--fault", f"0.2..0.5:{BAD_INPUT[bad]}"]
    s, left, right, _ = run(renderer, tmp_path, [*base, *fault], "fault")
    assert s["nonfinite"] == 0
    assert s["raw_peak"] <= 0.1 * 16 + 0.9 * db(-4) + 1e-5   # Mix 0.9: 10 % of the clamped dry
    tail = slice(RATE, None)
    assert left[tail] == clean_l[tail] and right[tail] == clean_r[tail]


def test_nan_input_reads_as_silence(renderer, tmp_path):  # noqa: F811
    s, _, _ = render(renderer, tmp_path, input="noise", seconds=0.5, fx=fx("Drive=24"),
                     extra=["--fault", "0..0.5:nan"])
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


# --- the ceiling and transparency through fm1-render --------------------------

@pytest.mark.parametrize("params,ceiling", [
    (["Drive=24"], -1),
    (["Drive=24", "Ceiling=-12", "Lookahead=0.5", "Release=1"], -12),
    (["Drive=18", "Ceiling=0", "Lookahead=0", "Link=0"], 0),
    (["Drive=24", "Ceiling=-6", "Mode=1"], -6),
])
def test_raw_output_never_exceeds_the_ceiling(renderer, tmp_path, params, ceiling):  # noqa: F811
    # raw_peak is the effect's output before the bus limiter, at six decimals.
    for source in ("noise", "impulse", "sine"):
        s, _, _ = render(renderer, tmp_path, input=source, seconds=0.5, fx=fx(*params),
                         name=source)
        assert s["raw_peak"] <= db(ceiling) + 1e-6, source
    assert s["raw_peak"] > 0.5 * db(ceiling)


def shifted(samples, d):
    return [0.0] * d + samples[:len(samples) - d]


def test_below_the_ceiling_it_only_delays(renderer, tmp_path):  # noqa: F811
    # The host's noise peaks at 0.5, under the default -1 dB ceiling: the
    # output is the input 88 frames (2 ms) later, bit for bit in the WAV.
    _, ref, _ = render(renderer, tmp_path, input="noise", seconds=1.0, name="ref",
                       fx=[("test-gain", ["Gain=1"])])
    s, out, _ = render(renderer, tmp_path, input="noise", seconds=1.0, name="out", fx=fx())
    assert out == shifted(ref, D_DEFAULT)
    _, out0, _ = render(renderer, tmp_path, input="noise", seconds=1.0, name="out0",
                        fx=fx("Lookahead=0"))
    assert out0 == ref


def test_mix_zero_passes_the_delayed_input(renderer, tmp_path):  # noqa: F811
    _, ref, _ = render(renderer, tmp_path, input="noise", seconds=1.0, name="ref",
                       fx=[("test-gain", ["Gain=1"])])
    _, out, _ = render(renderer, tmp_path, input="noise", seconds=1.0, name="dry",
                       fx=fx("Drive=24", "Ceiling=-20", "Mix=0"))
    assert out == shifted(ref, D_DEFAULT)


# --- every knob does what it says ---------------------------------------------

def test_ceiling_sets_the_peak(renderer, tmp_path):  # noqa: F811
    for ceiling in (-1, -6, -18):
        s, _, _ = render(renderer, tmp_path, input="noise", seconds=0.5, name=f"c{ceiling}",
                         fx=fx(f"Ceiling={ceiling}", "Drive=12"))
        assert s["raw_peak"] == pytest.approx(db(ceiling), rel=1e-4)


def test_drive_makes_it_louder_under_the_same_ceiling(renderer, tmp_path):  # noqa: F811
    levels = []
    for drive in (0, 12, 24):
        s, left, _ = render(renderer, tmp_path, input="noise", seconds=1.0, name=f"d{drive}",
                            fx=fx(f"Drive={drive}", "Ceiling=-6"))
        assert s["raw_peak"] <= db(-6) + 1e-6
        levels.append(rms(left, 0.2, 1.0))
    assert levels[0] < levels[1] < levels[2]               # measured 0.237, 0.354, 0.47
    _, quiet, _ = render(renderer, tmp_path, input="noise", seconds=1.0, name="dm",
                         fx=fx("Drive=-12", "Ceiling=0"))
    assert rms(quiet, 0.2, 1.0) == pytest.approx(db(-12) * levels[0] * 1.0, rel=0.25)


def test_release_sets_how_fast_the_gain_recovers(tool):
    # Measured from the probe's first frame out: the release time plus half
    # the lookahead (the hold and the boxes centre the gain curve D/2 late).
    for release, look, start_gain, t63 in tool["release"]:
        expected = release + look / 2
        assert t63 == pytest.approx(expected, abs=0.05 + 0.005 * release), (release, look)
        assert start_gain == pytest.approx(0.25 if look else 0.25 * db(-1), rel=1e-3)


def test_lookahead_is_the_latency(tool):
    # [rate, ms, measured frames, expected frames, nothing else came out]
    for rate, ms, got, want, clean in tool["latency"]:
        assert got == want and clean, (rate, ms)
    by = {(rate, ms): got for rate, ms, got, _, _ in tool["latency"]}
    assert by[(44118, 2)] == 88 and by[(44118, 5)] == 221 and by[(44118, 0)] == 0
    assert by[(192000, 5)] == 510                  # the cap: 2.66 ms at 192 kHz


def test_link_shares_the_gain(tool):
    # [link, right channel's gain, left peak, right untouched]. The left is a
    # square at +12 dB over a 0 dB ceiling (gain 0.25), the right a quiet sine.
    rows = {link: (gain, left, exact) for link, gain, left, exact in tool["link"]}
    assert rows[0] == (1.0, 1.0, True)
    assert rows[0.5][0] == pytest.approx(0.5, abs=1e-5)    # its peak is half the left's
    assert rows[1][0] == pytest.approx(0.25, abs=1e-5)
    assert all(left <= 1.0 for _, left, _ in rows.values())


def test_mode_soft_clip_rounds_the_peaks(renderer, tmp_path):  # noqa: F811
    # SOFT CLIP lets peaks reach +12 dB into a curve from -6 dB to the
    # ceiling c, y = c - c^2 / (4 v) for v > c / 2: the renderer's 0.5 sine
    # at +6 dB (v = 1.0, under 4c, so no gain reduction) peaks there, and
    # gains odd harmonics that the gain-riding BRICKWALL does not add.
    c, v = db(-3), 0.5 * db(6)
    s, soft, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="soft",
                        fx=fx("Mode=1", "Ceiling=-3", "Drive=6"))
    _, hard, _ = render(renderer, tmp_path, input="sine", seconds=1.0, name="hard",
                        fx=fx("Mode=0", "Ceiling=-3", "Drive=6"))
    assert s["raw_peak"] == pytest.approx(c - c * c / (4 * v), rel=1e-4)   # 0.582

    def third(x):
        seg = x[RATE // 2:RATE]
        w = 2 * math.pi * 1320 / RATE
        re = sum(v * math.cos(w * i) for i, v in enumerate(seg))
        im = sum(v * math.sin(w * i) for i, v in enumerate(seg))
        return math.hypot(re, im) / len(seg)
    assert third(soft) > 10 * third(hard)


@pytest.mark.parametrize("lookahead", ["2", "0.02", "5", "0"])
def test_round_is_clip_only_2_with_no_added_delay(tool, lookahead):
    # ROUND (2026-10-05), after Airwindows ClipOnly2 (MIT): a sine of +1.9 dB
    # with noise on it, into a 0 dB ceiling, where ROUND's 3 dB of headroom
    # leaves the gain at exactly 1. The output is ClipOnly2's recurrence,
    # written out in double in the test, delayed by the lookahead alone
    # (looking one frame ahead takes up ClipOnly2's own sample of delay; at
    # Lookahead 0, its causal form): within 7e-8 (float against double).
    # Every frame under the ceiling passes bit for bit; the overs (about
    # 18,000 of 44,098 frames) are replaced by values at most the ceiling.
    r = tool["round"][lookahead]
    assert r["diff"] < 2e-7, r
    assert r["over"] > 15000 and r["others_exact"] and r["peak"] <= 1.0


def test_round_rounds_overs_and_limits_beyond_3_db(renderer, tmp_path):  # noqa: F811
    # The renderer's 0.5 sine into a -6 dB ceiling: at +2 dB of Drive its
    # peaks (0.63) are 2 dB over the ceiling, inside ROUND's headroom, so the
    # gain stays at 1 and only the tops of the wave are rounded (harmonics
    # BRICKWALL does not add); at +12 dB the envelope holds the peaks at 3 dB
    # over and ROUND rounds those. Either way nothing passes the ceiling.
    c = db(-6)
    outs = {}
    for mode in (0, 2):
        for drive in (2, 12):
            s, x, _ = render(renderer, tmp_path, input="sine", seconds=1.0,
                             name=f"m{mode}d{drive}",
                             fx=fx(f"Mode={mode}", "Ceiling=-6", f"Drive={drive}"))
            assert s["raw_peak"] <= c + 1e-6
            outs[mode, drive] = x

    def third(x):
        seg = x[RATE // 2:RATE]
        w = 2 * math.pi * 1320 / RATE
        re = sum(v * math.cos(w * i) for i, v in enumerate(seg))
        im = sum(v * math.sin(w * i) for i, v in enumerate(seg))
        return math.hypot(re, im) / len(seg)
    assert third(outs[2, 2]) > 10 * third(outs[0, 2])
    assert third(outs[2, 12]) > 10 * third(outs[0, 12])
    # ROUND is louder than BRICKWALL for the same Drive: it keeps the wave's
    # body where BRICKWALL turns the whole of it down.
    assert rms(outs[2, 12], 0.5, 1.0) > rms(outs[0, 12], 0.5, 1.0) * db(1)


def test_mix_blends_the_limited_and_the_dry(renderer, tmp_path):  # noqa: F811
    common = ["Drive=12", "Ceiling=-6"]
    _, dry, _ = render(renderer, tmp_path, input="noise", seconds=0.5, name="m0",
                       fx=fx(*common, "Mix=0"))
    _, wet, _ = render(renderer, tmp_path, input="noise", seconds=0.5, name="m1",
                       fx=fx(*common, "Mix=1"))
    _, mid, _ = render(renderer, tmp_path, input="noise", seconds=0.5, name="m5",
                       fx=fx(*common, "Mix=0.5"))
    worst = max(abs(m - 0.5 * (d + w)) for m, d, w in zip(mid, dry, wet))
    assert worst <= 1.5 * LSB


def test_after_an_engine_and_before_a_reverb(renderer, tmp_path):  # noqa: F811
    summary, left, _, _ = run(
        renderer, tmp_path,
        ["--engine", "macro", "--param", "Model=0", "--note", "0:45:120:0.5",
         "--note", "0:52:120:0.5", "--note", "0:57:120:0.5", "--seconds", "1.5",
         *cli("Drive=12", "Ceiling=-3"), "--fx", "plate", "--fx-param", "Mix=0.3"], "chain")
    assert summary["fx"] == ["limit", "plate"]
    assert summary["nonfinite"] == 0
    assert rms(left, 0.1, 0.5) > 1e-2 and rms(left, 1.0, 1.4) > 1e-4


# --- fm1-limit-test: the float output ------------------------------------------

def test_ceiling_holds_on_hostile_input(tool):
    c = tool["ceiling"]
    assert c["runs"] == 1980 and c["frames"] > 21_000_000
    # |output| / 10^(Ceiling/20) in double: never above 1 in BRICKWALL (the
    # final clamp is exact; the ratio is 1 where it holds peaks at the
    # ceiling), nor with Lookahead 0's soft clip, in SOFT CLIP or in ROUND
    # (its overs are replaced by values that reach the ceiling at most).
    assert c["over"] == 0
    assert c["brickwall"] <= 1.0 + 2e-7
    assert c["peak_at_0db"] <= 1.0                          # exactly, at 0 dB
    assert c["brickwall_zero"] < 1.0 and c["soft_zero"] < 1.0
    assert c["soft"] <= 15 / 16 + 2e-7                      # SOFT CLIP tops out at -0.56 dB
    assert c["round"] <= 1.0 + 2e-7 and c["round_zero"] <= 1.0 + 2e-7
    # The envelope does the work, not the clamp: before it, |u x a| / c is
    # at most an ulp or two over 1 (measured 1 + 1.2e-7).
    assert c["envelope"] <= 1.0 + 3e-7


def test_transparent_below_the_ceiling(tool):
    # Noise under the ceiling (and under the stage's knee: -1 dB at
    # Lookahead 0, -6 dB in SOFT CLIP) comes out as the input, delayed,
    # bit for bit.
    assert all(tool["transparent"].values()), tool["transparent"]
    # After 0.3 s of limiting at +12 dB, Release 50 ms: exact again once the
    # reduction is under the gain path's step (2^-22), measured 747 ms on.
    assert 0 < tool["exact_again_after_ms"] < 900


def test_changes_mid_stream_are_block_size_independent(tool):
    c = tool["changes"]
    assert c["block_independent"] and c["finite"]
    assert c["peak"] < 1.5


def test_lookahead_and_mode_changes_do_not_click(tool):
    # Lookahead 2 -> 4.5 ms crossfades the delay over 5 ms: no step larger
    # than the 440 Hz sine's own (without it, up to 0.9), and exact after.
    m = tool["lookahead_move"]
    assert m["moving_step"] <= 1.05 * m["steady_step"] and m["exact_after"]
    # Mode glides its stage over 5 ms (a loud sine, -3 dB ceiling).
    m = tool["mode_move"]
    assert m["moving_step"] <= 1.05 * m["steady_step"]
    assert m["peak"] <= db(-3) + 1e-6
    # BRICKWALL -> ROUND -> SOFT CLIP -> ROUND -> BRICKWALL, the same sine.
    m = tool["round_move"]
    assert m["moving_step"] <= 1.05 * m["steady_step"]
    assert m["peak"] <= db(-3) + 1e-6


def test_turning_lookahead_and_mode_never_needs_the_clamp(tool):
    # Lookahead (0 included), Mode and Link turned again and again while loud
    # bursts are limited, at 8, 44.1, 96 and 384 kHz: before the final clamp,
    # the envelope (BRICKWALL) and the stage (either Mode, gliding included)
    # stay within a float step of the ceiling. Before the Lookahead crossfade
    # and the stage's Mode were fixed (2026-10-02 review), a crossfade let
    # replayed or unseen peaks through and a SOFT CLIP -> BRICKWALL change
    # kept +12 dB gains on the frames in the line: up to 41x (+32 dB) here,
    # flattened by the clamp.
    k = tool["knobs"]
    assert k["changes"] > 1000
    assert k["envelope"] <= 1.0 + 3e-7 and k["stage"] <= 1.0 + 3e-7
    assert k["out"] <= 1.0 + 3e-7
    # Steady limiting (+12 dB into -6 dB) while Lookahead moves 2 -> 4.5 ->
    # 1 ms: no step larger than the sine's own.
    assert k["moving_step"] <= 1.05 * k["steady_step"]


def test_lookahead_and_mode_modulated_fast_do_not_click(tool):
    # Lookahead (1-5 ms, and 0-5 ms with 0 among them) and Mode turned every
    # third block, Mode every 64th too (its glide then completes), and both
    # every second block, while a sine swells and fades into the ceiling, so
    # the gain is often ramping when a change lands: no step between samples
    # beyond the largest with the control held (at 1-6 values, over the same
    # six inputs) plus the crossfade bound 2c / 220. Measured: 0.20 of that
    # allowance with Lookahead at 1-5 ms, none elsewhere. Before each tap of
    # a crossfade had its own gain path (2026-10-02) it was 2.6 and 16 times
    # the allowance, and the stage passed the ceiling by 18 % before the
    # clamp.
    m = tool["modulated"]
    for name in ("lookahead", "lookahead0", "mode", "mode_slow", "both",
                 "mode3", "mode3_slow", "both3"):         # with ROUND among the Modes
        assert m[name]["excess"] <= 1.0, (name, m[name])
    assert m["peak"] <= 1.0
    assert m["envelope"] <= 1.0 + 3e-7 and m["stage"] <= 1.0 + 3e-7


def test_any_parameter_change_mid_stream_stays_finite(tool):
    # 20 s of input at +6 dB with NaN, infinities and 1e30 mixed in; up to
    # two parameters jump between blocks of 1-64 frames to any value. The
    # bound is the clamped dry path's 16 at Mix 0.
    s = tool["sweep"]
    assert s["samples"] > 20 * RATE
    assert s["nonfinite"] == 0 and s["peak"] <= 16.0


def test_silence_while_parameters_move(tool):
    assert tool["silence"]["peak"] == 0.0


def test_host_rates(tool):
    accepted = {rate: ok for rate, ok, _ in tool["rates"]}
    assert accepted == {"0": False, "7999": False, "8000": True, "44118": True,
                        "48000": True, "96000": True, "102000": True, "192000": True,
                        "384000": True, "400000": False, "nan": False, "inf": False,
                        "-44118": False}
