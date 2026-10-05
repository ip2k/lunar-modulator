"""Tests for Echo (engines/src/fx_echo.cc), the stereo ping-pong delay written
in this repository: registration and memory, delay time at the full clock and
beyond it, ping-pong, every parameter doing what it says, stability at maximum
feedback, decay to silence, the input guard, determinism and block-size
independence. engines/build/fm1-echo-selftest covers what a render cannot:
parameters turned while it runs, refused host rates, exact zeros.

The figures in the comments were measured on the desktop build (2026-10-02).
Impulse tests use Level 0.5 so the echo stays below the host's limiter.
"""
import json
import math
import subprocess
import wave

import pytest

from tests.engine_helpers import ENGINES, RATE, renderer, rms  # noqa: F401

SELFTEST = ENGINES / "build" / "fm1-echo-selftest"

# A plain delay: one echo, no modulation, no damping.
PLAIN = ["Feedback=0", "Ping-pong=0", "Mix=1", "Wow=0", "Tone=1", "Level=0.5"]
# Every parameter away from its default, the time beyond the full-rate line.
BUSY = ["Time=700", "Feedback=0.9", "Ping-pong=0.6", "Mix=0.7", "Tone=0.3", "Wow=1",
        "Level=0.8"]
BANNED = ("mutable", "plaits", "braids", "rings", "clouds", "elements")


def cli_fx(params, fx="echo"):
    args = ["--fx", fx]
    for p in params:
        args += ["--fx-param", p]
    return args


def run(renderer, tmp_path, args, name="out"):
    """Render; return (summary, left, right, rate)."""
    wav = tmp_path / f"{name}.wav"
    res = subprocess.run([str(renderer), *args, "--out", str(wav)], check=True,
                         capture_output=True, text=True)
    with wave.open(str(wav), "rb") as w:
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())
    samples = [int.from_bytes(raw[i:i + 2], "little", signed=True) / 32767.0
               for i in range(0, len(raw), 2)]
    return json.loads(res.stdout), samples[0::2], samples[1::2], rate


def impulse(renderer, tmp_path, params, seconds, rate=RATE, name="imp"):
    return run(renderer, tmp_path, ["--input", "impulse", "--seconds", str(seconds),
                                    "--rate", str(rate), *cli_fx(params)], name)


def window_sum(x, centre, half=60):
    return sum(x[max(0, centre - half):centre + half])


def centroid(x):
    return sum(i * v for i, v in enumerate(x)) / sum(x)


def brightness(seg):
    """RMS of the first difference over RMS: sqrt(2) for white noise."""
    diff = sum((b - a) ** 2 for a, b in zip(seg, seg[1:]))
    return math.sqrt(diff / sum(x * x for x in seg))


def pitch_cents(samples, rate, start, dur, ref=440.0):
    seg = samples[int(start * rate):int((start + dur) * rate)]
    crossings = [i - 1 + -seg[i - 1] / (seg[i] - seg[i - 1])
                 for i in range(1, len(seg)) if seg[i - 1] < 0.0 <= seg[i]]
    hz = (len(crossings) - 1) * rate / (crossings[-1] - crossings[0])
    return 1200.0 * math.log2(hz / ref)


def describe(renderer):
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True,
                         text=True).stdout
    return next(e for e in json.loads(out) if e["id"] == "echo")


def test_echo_is_registered(renderer):
    e = describe(renderer)
    assert e["kind"] == "audio_fx" and e["max_voices"] == 0 and e["name"] == "Echo"
    assert not any(b in (e["id"] + e["name"]).lower() for b in BANNED)
    assert "MIT" in e["credits"] and "Emilie Gillet" in e["credits"]
    table = [(p["name"], p["min"], p["max"], p["def"], p["page"]) for p in e["params"]]
    assert table == [
        ("Time", 10, 1000, 300, 0), ("Feedback", 0, 1, 0.4, 0),
        ("Ping-pong", 0, 1, 1, 0), ("Mix", 0, 1, 0.35, 0),
        ("Tone", 0, 1, 0.6, 1), ("Wow", 0, 1, 0.1, 1), ("Level", 0, 1, 1, 1),
    ]
    assert all(p["type"] == 0 and len(p["name"]) <= 12 for p in e["params"])


@pytest.mark.parametrize("rate", [22050, 44118, 48000])
def test_instance_size_is_modest_and_fixed(renderer, tmp_path, rate):
    # 16,384 stereo cells of 16-bit words (65,536 bytes) and 208 bytes of
    # state (192 before Tone's SMOOTH ramp, docs/15 S7b): 65,744 on the
    # desktop. No pointers, so the same on 32-bit.
    summary, _, _, _ = run(renderer, tmp_path, ["--input", "silence", "--seconds", "0.01",
                                                "--rate", str(rate), *cli_fx([])])
    size = summary["fx_bytes"][0]
    assert 65536 < size <= 65536 + 256 and size % 16 == 0


@pytest.mark.parametrize("rate", [44118, 48000])
@pytest.mark.parametrize("ms", [10, 50, 200, 340])
def test_delay_time_at_the_full_clock(renderer, tmp_path, rate, ms):
    # Up to 16,380 cells (371 ms at 44,118 Hz, 341 ms at 48 kHz) the line is
    # a plain fractional delay: the echo lands where Time says, to a few
    # thousandths of a sample, at the input's level.
    _, left, right, _ = impulse(renderer, tmp_path, [f"Time={ms}", *PLAIN], ms / 1000 + 0.05,
                                rate)
    assert centroid(left) == pytest.approx(ms * rate / 1000, abs=0.02)
    assert sum(left) == pytest.approx(0.5, abs=1e-3)
    assert left == right


@pytest.mark.parametrize("rate", [44118, 48000])
@pytest.mark.parametrize("ms", [500, 800, 1000])
def test_delay_time_beyond_the_line(renderer, tmp_path, rate, ms):
    # Beyond the line the clock slows; its filters add a few samples of
    # group delay (measured 0.02-0.13 ms late at 500-1,000 ms). The echo is
    # smeared, so the centroid stands for its time.
    _, left, _, _ = impulse(renderer, tmp_path, [f"Time={ms}", *PLAIN], ms / 1000 + 0.1, rate)
    late_ms = (centroid(left) - ms * rate / 1000) / rate * 1000
    assert 0.0 <= late_ms < 0.2


def test_long_echoes_keep_their_level_and_lose_their_highs(renderer, tmp_path):
    # Like a bucket-brigade delay: a 440 Hz sine comes back at its level
    # (measured -0.19 dB at 1,000 ms), noise comes back darker as the clock
    # slows (brightness 1.03, 0.56, 0.25 at 200, 600, 1,000 ms).
    sine, bright = {}, {}
    for ms in (200, 600, 1000):
        params = [f"Time={ms}", "Feedback=0", "Ping-pong=0", "Mix=1", "Wow=0"]
        _, s, _, _ = run(renderer, tmp_path, ["--input", "sine", "--seconds", "1.6",
                                              *cli_fx(params)], f"sine_{ms}")
        _, n, _, _ = run(renderer, tmp_path, ["--input", "noise", "--seconds", "1.6",
                                              *cli_fx(params)], f"noise_{ms}")
        sine[ms] = 20 * math.log10(rms(s, 1.05, 1.55) / (0.5 / math.sqrt(2)))
        bright[ms] = brightness(n[int(1.05 * RATE):int(1.55 * RATE)])
    assert all(-0.5 < db < 0.1 for db in sine.values())
    assert bright[200] > bright[600] > bright[1000]
    assert bright[1000] < 0.35 * bright[200]


def test_ping_pong_alternates_sides(renderer, tmp_path):
    # Ping-pong 1: the mono sum enters the left line only, and each line feeds
    # the other, so the echoes go left, right, left at T, 2T, 3T.
    params = ["Time=100", "Feedback=0.5", "Ping-pong=1", "Mix=1", "Wow=0", "Tone=1",
              "Level=0.5"]
    _, left, right, _ = impulse(renderer, tmp_path, params, 0.45)
    t = round(0.1 * RATE)
    g = 0.95 * 0.5
    assert window_sum(left, t) == pytest.approx(0.5, abs=1e-3)
    assert window_sum(right, 2 * t) == pytest.approx(0.5 * g, abs=2e-3)
    assert window_sum(left, 3 * t) == pytest.approx(0.5 * g * g, abs=2e-3)
    for side, k in ((right, 1), (left, 2), (right, 3)):
        assert all(x == 0.0 for x in side[k * t - 60:k * t + 60])


def test_ping_pong_zero_is_two_straight_delays(renderer, tmp_path):
    _, left, right, _ = impulse(renderer, tmp_path,
                                ["Time=100", "Feedback=0.5", "Ping-pong=0", "Mix=1", "Level=0.5"],
                                0.45)
    assert left == right and window_sum(left, 2 * round(0.1 * RATE)) > 0.2


def test_ping_pong_half_spreads_both_ways(renderer, tmp_path):
    _, left, right, _ = impulse(renderer, tmp_path,
                                ["Time=100", "Feedback=0.5", "Ping-pong=0.5", "Mix=1", "Wow=0",
                                 "Tone=1", "Level=0.5"], 0.25)
    t = round(0.1 * RATE)
    assert window_sum(left, t) == pytest.approx(0.5, abs=1e-3)
    assert window_sum(right, t) == pytest.approx(0.25, abs=1e-3)


@pytest.mark.parametrize("feedback", [0.5, 1.0])
def test_feedback_is_the_loop_gain(renderer, tmp_path, feedback):
    # Feedback 1 is a loop gain of 0.95. Tone and interpolation keep the
    # repeats' sum (their DC gain is 1), so each repeat sums to 0.95 x
    # Feedback of the one before (measured 0.4747 and 0.9498).
    _, left, _, _ = impulse(renderer, tmp_path, ["Time=100", *PLAIN[1:], f"Feedback={feedback}"],
                            0.45)
    t = round(0.1 * RATE)
    sums = [window_sum(left, k * t) for k in (1, 2, 3)]
    for a, b in zip(sums, sums[1:]):
        assert b / a == pytest.approx(0.95 * feedback, abs=0.003)


def test_feedback_zero_gives_one_echo(renderer, tmp_path):
    _, left, _, _ = impulse(renderer, tmp_path, ["Time=100", *PLAIN], 0.45)
    t = round(0.1 * RATE)
    assert window_sum(left, t) > 0.49
    assert all(x == 0.0 for x in left[t + 60:])


@pytest.mark.parametrize("params", [
    ["Time=10", "Ping-pong=0"], ["Time=10", "Ping-pong=1"],
    ["Time=372", "Ping-pong=0.5"], ["Time=1000", "Ping-pong=1"],
])
def test_maximum_feedback_on_noise_stays_bounded(renderer, tmp_path, params):
    # Ten seconds of noise into the loop at its longest-ringing setting. The
    # soft clip holds the line within +/-2 (measured peaks 0.5-1.42), and the
    # level settles instead of growing. At 1,000 ms the loop is only ten
    # passes old at the end, still filling (0.95 per pass), so it is checked
    # for its bound alone.
    summary, left, right, _ = run(renderer, tmp_path,
                                  ["--input", "noise", "--seconds", "10",
                                   *cli_fx([*params, "Feedback=1", "Mix=1", "Wow=1", "Tone=1"])])
    assert summary["nonfinite"] == 0 and summary["raw_peak"] <= 2.0
    if params[0] != "Time=1000":
        for ch in (left, right):
            assert rms(ch, 8, 10) < 1.05 * rms(ch, 6, 8)


def test_impulse_tail_decays_to_silence(renderer, tmp_path):
    # Magnitude truncation in the 16-bit store: no small signal recirculates
    # for ever, even at Feedback 1. At 10 ms the tail is gone within 3 s.
    _, left, right, _ = impulse(renderer, tmp_path,
                                ["Time=10", "Feedback=1", "Tone=1", "Mix=1", "Wow=1",
                                 "Ping-pong=1", "Level=0.5"], 4.0)
    assert rms(left, 0.0, 0.5) > 1e-3
    tail = int(3.0 * RATE)
    assert all(x == 0.0 for x in left[tail:]) and all(x == 0.0 for x in right[tail:])


def test_mix_zero_passes_the_input_through(renderer, tmp_path):
    ref = run(renderer, tmp_path, ["--input", "noise", "--seconds", "1",
                                   *cli_fx(["Gain=1"], "test-gain")], "ref")
    out = run(renderer, tmp_path, ["--input", "noise", "--seconds", "1",
                                   *cli_fx([*BUSY, "Mix=0"])], "out")
    assert out[0]["raw_peak"] == ref[0]["raw_peak"]
    assert out[1] == ref[1] and out[2] == ref[2]


@pytest.mark.parametrize("mix,dry,echo", [(0.25, 0.5, 0.25), (0.5, 0.5, 0.5),
                                          (0.75, 0.25, 0.5), (1.0, 0.0, 0.5)])
def test_mix_law(renderer, tmp_path, mix, dry, echo):
    # The dry stays at full level up to Mix 0.5, where the echo reaches it;
    # Test Gain halves the impulse first so nothing reaches the limiter.
    _, left, _, _ = run(renderer, tmp_path,
                        ["--input", "impulse", "--seconds", "0.15",
                         *cli_fx(["Gain=0.5"], "test-gain"),
                         *cli_fx(["Time=100", *PLAIN[:-2], "Level=1", f"Mix={mix}"])])
    t = round(0.1 * RATE)
    assert left[0] == pytest.approx(dry, abs=1e-4)
    assert all(x == 0.0 for x in left[1:t - 60])
    assert window_sum(left, t) == pytest.approx(echo, abs=1e-3)


def test_level_sets_what_enters_the_echo(renderer, tmp_path):
    summary, _, _, _ = run(renderer, tmp_path, ["--input", "noise", "--seconds", "1",
                                                *cli_fx(["Level=0", "Mix=1", "Feedback=1"])])
    assert summary["raw_peak"] == 0.0
    sums = {}
    for level in ("0.25", "0.5"):
        _, left, _, _ = impulse(renderer, tmp_path, ["Time=100", *PLAIN[:-1], f"Level={level}"],
                                0.15, name=f"level_{level}")
        sums[level] = window_sum(left, round(0.1 * RATE))
    assert sums["0.25"] == pytest.approx(0.25, abs=1e-3)
    assert sums["0.5"] == pytest.approx(0.5, abs=1e-3)


def test_tone_darkens_the_repeats(renderer, tmp_path):
    # Tone is a low-pass inside the loop (400 Hz at 0, six octaves up at 1):
    # the first echo is the input's copy, each repeat is filtered once more.
    # Brightness of the first repeat of an impulse rises with Tone (measured
    # 0.28, 0.73 and 1.23 at Tone 0, 0.5 and 1).
    bright = []
    t = round(0.05 * RATE)
    for tone in ("0", "0.5", "1"):
        _, left, _, _ = impulse(renderer, tmp_path,
                                ["Time=50", "Feedback=0.5", "Ping-pong=0", "Mix=1", "Wow=0",
                                 f"Tone={tone}", "Level=0.5"], 0.15, name=f"tone_{tone}")
        first = left[t - 10:t + 10]
        assert window_sum(left, t, 10) == pytest.approx(0.5, abs=1e-3)   # undamped
        bright.append(brightness(left[2 * t - 10:2 * t + 1000]))
        assert brightness(first) > 1.0
    assert bright[0] < bright[1] < bright[2]
    assert bright[0] < 0.3 * bright[2]


def test_wow_bends_the_pitch(renderer, tmp_path):
    # A 440 Hz sine through the echo alone: the pitch over 0.1 s windows
    # stays put at Wow 0 and swings with Wow (measured +/-0, +/-10, +/-20
    # cents at 0, 0.5, 1: a 0.55 Hz sine and a slow random walk, +/-3 ms).
    spread = {}
    for wow in ("0", "0.5", "1"):
        _, left, _, _ = run(renderer, tmp_path,
                            ["--input", "sine", "--seconds", "4",
                             *cli_fx(["Time=300", "Feedback=0", "Mix=1", "Ping-pong=0",
                                      f"Wow={wow}"])], f"wow_{wow}")
        cents = [pitch_cents(left, RATE, 0.4 + 0.1 * k, 0.1) for k in range(35)]
        spread[wow] = max(cents) - min(cents)
    assert spread["0"] < 0.2
    assert 12 < spread["0.5"] < 30
    assert 1.8 < spread["1"] / spread["0.5"] < 2.2


BAD_INPUT = {
    "nan": ["--fault", "0..0.5:nan"],
    "huge": [a for _ in range(24) for a in cli_fx(["Gain=2"], "test-gain")],
    "inf": [a for _ in range(160) for a in cli_fx(["Gain=2"], "test-gain")],
}


@pytest.mark.parametrize("bad", ["nan", "huge", "inf"])
@pytest.mark.parametrize("mix", ["0", "1"])
def test_bad_input_is_guarded(renderer, tmp_path, bad, mix):
    # The guard of mi_fx.cc: NaN reads as 0, anything else is clamped to
    # +/-16, dry path included. Half a second of nothing but bad input
    # leaves the output finite.
    params = ["Time=10", "Feedback=1", "Wow=1", f"Mix={mix}"]
    summary, _, _, _ = run(renderer, tmp_path, ["--input", "noise", "--seconds", "0.5",
                                                *BAD_INPUT[bad], *cli_fx(params)])
    assert summary["nonfinite"] == 0
    if bad == "nan":
        assert summary["raw_peak"] == 0.0
    elif mix == "0":
        assert summary["raw_peak"] == 16.0
    else:
        assert 0.0 < summary["raw_peak"] <= 2.0


def test_effect_recovers_after_bad_input(renderer, tmp_path):
    summary, left, right, _ = run(renderer, tmp_path,
                                  ["--input", "noise", "--seconds", "1", "--fault", "0..0.2:nan",
                                   "--fault", "0.25:inf", *cli_fx(["Feedback=0.9", "Time=50"])])
    assert summary["nonfinite"] == 0             # the guard caught them...
    assert rms(left, 0.5, 1.0) > 0.1 and rms(right, 0.5, 1.0) > 0.1   # ...and it still plays


def test_tail_after_an_engine(renderer, tmp_path):
    note = ["--engine", "macro", "--param", "Decay=0.2", "--note", "0:60:100:0.3",
            "--seconds", "2.0"]
    _, dry, _, _ = run(renderer, tmp_path, note, "dry")
    summary, left, right, _ = run(renderer, tmp_path,
                                  [*note, *cli_fx(["Time=400", "Feedback=0.6"])], "wet")
    assert summary["fx"] == ["echo"] and summary["nonfinite"] == 0 and summary["clipped"] == 0
    assert rms(dry, 1.2, 1.6) < 1e-4
    assert rms(left, 1.2, 1.6) > 1e-3 and rms(right, 1.2, 1.6) > 1e-3
    assert left != right                         # a mono engine comes out stereo


def test_rendering_is_deterministic(renderer, tmp_path):
    a = run(renderer, tmp_path, ["--input", "noise", "--seconds", "1", *cli_fx(BUSY)], "a")
    b = run(renderer, tmp_path, ["--input", "noise", "--seconds", "1", *cli_fx(BUSY)], "b")
    assert a[1] == b[1] and a[2] == b[2]


@pytest.mark.parametrize("time", ["200", "700"])
def test_block_size_does_not_change_the_output(renderer, tmp_path, time):
    outs = []
    for frames in ("64", "7", "1"):
        outs.append(run(renderer, tmp_path,
                        ["--input", "noise", "--seconds", "1", "--frames", frames,
                         *cli_fx([*BUSY, f"Time={time}"])], f"b{frames}")[1:3])
    assert outs[0] == outs[1] == outs[2]


def test_selftest(renderer):
    # `make` in the renderer fixture builds the selftest too.
    res = subprocess.run([str(SELFTEST)], capture_output=True, text=True)
    lines = [json.loads(line) for line in res.stdout.splitlines() if line]
    assert {line["check"] for line in lines} == {
        "refuses_bad_rates", "size_is_fixed", "abuse_stays_finite_and_bounded",
        "ignores_prior_memory", "block_sizes_do_not_matter", "time_sweeps_stay_bounded",
        "decays_to_exact_zero"}
    assert all(line["ok"] for line in lines), [line for line in lines if not line["ok"]]
    assert res.returncode == 0
