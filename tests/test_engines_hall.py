"""Tests for Hall (engines/src/fx_hall.cc), the eight-line feedback delay
network reverb written in this repository.

Through fm1-render: registration and pages, the host contracts
(deterministic renders, any block size, any prior memory contents, any
parameter value, NaN included, bad input guarded, silence in gives silence
out, Mix 0 passes the input bit for bit) and every parameter doing what it
says: the first arrival where Size and Pre-delay put it, Damping darkening
the tail, Diffusion smoothing the onset, Mod spreading a sine, Width
narrowing to mono, Low Cut thinning the lows, Freeze letting nothing in.
Through fm1-hall-selftest (engines/test/hall_selftest.cc): parameters
turned while it runs, sweeps of Size, Pre-delay and Freeze at three rates,
decay to exact zeros, the decay time against Decay, Freeze holding and
switching without a click, and the host rates it refuses.

The figures in the comments were measured on the desktop build (2026-10-05).
"""
import json
import math
import subprocess
import wave

import pytest

from tests.engine_helpers import ENGINES, RATE, renderer  # noqa: F401

SELFTEST = ENGINES / "build" / "fm1-hall-selftest"
LSB = 1 / 32767.0
BANNED = ("mutable", "plaits", "braids", "rings", "clouds", "elements", "lexicon", "valhalla")
# Every parameter away from its default.
BUSY = ["Decay=0.7", "Size=0.4", "Damping=0.6", "Mix=0.6", "Pre-delay=35", "Diffusion=0.5",
        "Mod=0.8", "Width=0.7", "Low Cut=0.4"]
# A static network: no modulation, no damping, no pre-delay, Size 1 (whole
# samples), the wet signal only.
STATIC = ["Mix=1", "Mod=0", "Damping=0", "Pre-delay=0", "Size=1"]


def cli_fx(params, fx="hall"):
    args = ["--fx", fx]
    for p in params:
        args += ["--fx-param", p]
    return args


def run(renderer, tmp_path, args, name="out"):  # noqa: F811
    """Render; return (summary, left, right)."""
    wav = tmp_path / f"{name}.wav"
    res = subprocess.run([str(renderer), *args, "--out", str(wav)], check=True,
                         capture_output=True, text=True)
    with wave.open(str(wav), "rb") as w:
        raw = w.readframes(w.getnframes())
    samples = [int.from_bytes(raw[i:i + 2], "little", signed=True) / 32767.0
               for i in range(0, len(raw), 2)]
    return json.loads(res.stdout), samples[0::2], samples[1::2]


def hall(renderer, tmp_path, params, seconds=1.0, input="noise", extra=(), name="out"):  # noqa: F811
    return run(renderer, tmp_path, ["--input", input, "--seconds", str(seconds), *extra,
                                    *cli_fx(params)], name)


def impulse(renderer, tmp_path, params, seconds=0.5, name="imp"):  # noqa: F811
    # Test Gain halves the impulse first, so nothing reaches the limiter.
    return run(renderer, tmp_path, ["--input", "impulse", "--seconds", str(seconds),
                                    *cli_fx(["Gain=0.5"], "test-gain"), *cli_fx(params)], name)


def rms(x, a, b):
    seg = x[int(a * RATE):int(b * RATE)]
    return math.sqrt(sum(v * v for v in seg) / max(1, len(seg)))


def brightness(seg):
    """RMS of the first difference over RMS: sqrt(2) for white noise."""
    diff = sum((b - a) ** 2 for a, b in zip(seg, seg[1:]))
    return math.sqrt(diff / sum(x * x for x in seg))


def first_nonzero(x):
    return next(i for i, v in enumerate(x) if v != 0.0)


def goertzel(seg, hz):
    w = 2 * math.pi * hz / RATE
    c = 2 * math.cos(w)
    s1 = s2 = 0.0
    for x in seg:
        s1, s2 = x + c * s1 - s2, s1
    re, im = s1 - s2 * math.cos(w), s2 * math.sin(w)
    return (re * re + im * im) / (len(seg) / 2) ** 2


def describe(renderer):  # noqa: F811
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True,
                         text=True).stdout
    return next(e for e in json.loads(out) if e["id"] == "hall")


# --- registration -------------------------------------------------------------

def test_hall_is_registered(renderer):  # noqa: F811
    e = describe(renderer)
    assert e["kind"] == "audio_fx" and e["max_voices"] == 0 and e["name"] == "Hall"
    assert not any(b in (e["id"] + e["name"]).lower() for b in BANNED)
    assert "MIT" in e["credits"] and "Jot" in e["credits"] and "Emilie Gillet" in e["credits"]
    table = [(p["name"], p["type"], p["min"], p["max"], p["def"], p["page"]) for p in e["params"]]
    assert table == [
        ("Decay", 0, 0, 1, 0.5, 0), ("Size", 0, 0, 1, 0.7, 0), ("Damping", 0, 0, 1, 0.4, 0),
        ("Mix", 0, 0, 1, 0.3, 0),
        ("Pre-delay", 0, 0, 150, 20, 1), ("Diffusion", 0, 0, 1, 0.7, 1), ("Mod", 0, 0, 1, 0.3, 1),
        ("Freeze", 1, 0, 1, 0, 1),
        ("Width", 0, 0, 1, 1, 2), ("Low Cut", 0, 0, 1, 0.2, 2),
    ]
    freeze = next(p for p in e["params"] if p["name"] == "Freeze")
    assert freeze["names"] == ["Off", "On"]
    assert all(len(p["name"]) <= 12 for p in e["params"])


@pytest.mark.parametrize("rate,cells", [(44118, 16384 + 8192), (44100, 16384 + 8192),
                                        (48000, 32768 + 16384)])
def test_instance_size(renderer, tmp_path, rate, cells):  # noqa: F811
    # Two rings of 16-bit words, powers of two sized for the rate, and 736
    # bytes of state (no pointers, so the same on 32 bits): 49,888 bytes at
    # the FM-1's rate. At 48 kHz both rings need the next power of two.
    s, _, _ = run(renderer, tmp_path, ["--input", "silence", "--seconds", "0.01",
                                       "--rate", str(rate), *cli_fx([])])
    size = s["fx_bytes"][0]
    assert size % 16 == 0 and 2 * cells < size <= 2 * cells + 1024


# --- host contracts -------------------------------------------------------------

def test_rendering_is_deterministic(renderer, tmp_path):  # noqa: F811
    a = hall(renderer, tmp_path, BUSY, name="a")
    b = hall(renderer, tmp_path, BUSY, name="b")
    assert a[1] == b[1] and a[2] == b[2]


def test_block_size_does_not_change_the_output(renderer, tmp_path):  # noqa: F811
    outs = [hall(renderer, tmp_path, BUSY, extra=["--frames", f], name=f"b{f}")[1:]
            for f in ("64", "7", "1")]
    assert outs[0] == outs[1] == outs[2]


def test_output_ignores_initial_memory(renderer, tmp_path):  # noqa: F811
    outs = []
    for fill in ("0", "0xA5", "0xFF"):
        s, left, right = hall(renderer, tmp_path, BUSY, extra=["--fill", fill], name=f"f{fill}")
        assert s["nonfinite"] == 0
        outs.append((left, right))
    assert outs[0] == outs[1] == outs[2]


@pytest.mark.parametrize("value,same_as", [("nan", None), ("1e9", "max"), ("-1e9", "min"),
                                           ("inf", "max")])
def test_out_of_range_parameters_clamp(renderer, tmp_path, value, same_as):  # noqa: F811
    params = describe(renderer)["params"]
    bad = [f"{p['name']}={value}" for p in params]
    good = [] if same_as is None else [f"{p['name']}={p[same_as]}" for p in params]
    s, al, ar = hall(renderer, tmp_path, bad, seconds=0.5, name="bad")
    _, bl, br = hall(renderer, tmp_path, good, seconds=0.5, name="good")
    assert s["nonfinite"] == 0
    assert al == bl and ar == br


@pytest.mark.parametrize("params", [[], ["Mix=1", "Decay=1", "Mod=1"], ["Freeze=1", "Mix=1"],
                                    ["Size=0", "Diffusion=1", "Pre-delay=150", "Low Cut=1"]])
def test_silence_in_is_silence_out(renderer, tmp_path, params):  # noqa: F811
    s, _, _ = hall(renderer, tmp_path, params, input="silence", seconds=0.5)
    assert s["nonfinite"] == 0 and s["raw_peak"] == 0.0


def test_mix_zero_passes_the_input_through(renderer, tmp_path):  # noqa: F811
    ref = run(renderer, tmp_path, ["--input", "noise", "--seconds", "1",
                                   *cli_fx(["Gain=1"], "test-gain")], "ref")
    out = hall(renderer, tmp_path, [*BUSY, "Mix=0"], name="dry")
    assert out[0]["raw_peak"] == ref[0]["raw_peak"]
    assert out[1] == ref[1] and out[2] == ref[2]


def test_nan_input_reads_as_silence(renderer, tmp_path):  # noqa: F811
    # The guard turns NaN into 0 before anything sees it: the render with
    # NaN faults is the render with zeros there, bit for bit.
    _, nl, nr = hall(renderer, tmp_path, BUSY, extra=["--fault", "0.2..0.5:nan"], name="nan")
    _, zl, zr = hall(renderer, tmp_path, BUSY, extra=["--fault", "0.2..0.5:0"], name="zero")
    assert nl == zl and nr == zr


@pytest.mark.parametrize("bad", ["inf", "1e30"])
def test_bad_input_is_guarded(renderer, tmp_path, bad):  # noqa: F811
    # Clamped to +/-16, the dry path included. The wet side is at most 8: four
    # words of at most 2.0 per side.
    s, left, _ = hall(renderer, tmp_path, ["Mix=0.5", "Decay=1"], seconds=1.5,
                      extra=["--fault", f"0.2..0.5:{bad}"])
    assert s["nonfinite"] == 0 and s["raw_peak"] <= 16.0 + 8.0
    assert rms(left, 1.0, 1.5) > 0.01                       # still playing after it


@pytest.mark.parametrize("mix,dry", [(0.25, 1.0), (0.5, 1.0), (0.75, 0.5), (1.0, 0.0)])
def test_mix_law(renderer, tmp_path, mix, dry):  # noqa: F811
    # The dry stays at full level up to Mix 0.5, where the reverb reaches it
    # (Echo's law). The wet side starts after the shortest line, so the
    # impulse's own sample is the dry alone.
    _, left, _ = impulse(renderer, tmp_path, [*STATIC, f"Mix={mix}"], 0.1)
    assert left[0] == pytest.approx(0.5 * dry, abs=LSB)
    assert all(v == 0.0 for v in left[1:1301])


# --- every knob does what it says --------------------------------------------------

@pytest.mark.parametrize("size,arrival", [("1", 1301), ("0.5", 650), ("0", 325)])
def test_size_sets_the_first_arrival(renderer, tmp_path, size, arrival):  # noqa: F811
    # Size scales every line by 1/4 (0) to 1 (1) on a log scale; the shortest
    # line is 1,301 samples (29.5 ms) at Size 1. With the input all-passes'
    # immediate part, the first reflection lands after that line.
    _, left, right = impulse(renderer, tmp_path, [*STATIC, f"Size={size}"], 0.1)
    assert first_nonzero(left) == arrival
    assert first_nonzero(right) > arrival                  # the right side's lines are longer


@pytest.mark.parametrize("ms", [10, 100, 150])
def test_pre_delay_moves_the_onset(renderer, tmp_path, ms):  # noqa: F811
    _, base, _ = impulse(renderer, tmp_path, STATIC, 0.3, name="p0")
    _, late, _ = impulse(renderer, tmp_path, [*STATIC, f"Pre-delay={ms}"], 0.3, name="p")
    assert first_nonzero(late) - first_nonzero(base) == int(ms * RATE / 1000)


def test_decay_lengthens_the_tail(renderer, tmp_path):  # noqa: F811
    # The decay time itself is the selftest's (Schroeder's integral, within
    # 2 %); here only its direction.
    tails = []
    for d in ("0.2", "0.5", "0.8"):
        _, left, _ = hall(renderer, tmp_path, ["Mix=1", f"Decay={d}"], seconds=2.0,
                          extra=["--fault", "0.3..2:0"], name=f"d{d}")
        tails.append(rms(left, 1.2, 1.8) / rms(left, 0.2, 0.3))
    assert tails[0] < 1e-3 < tails[1] < tails[2]


def test_damping_darkens_the_tail(renderer, tmp_path):  # noqa: F811
    # The shelf in each line: highs decay up to 32 x faster than the lows,
    # above a crossover from 10 kHz (Damping 0) down to 1 kHz (Damping 1).
    # Measured brightness 0.40, 0.17, 0.031 at 0, 0.5, 1 (white noise: 1.41).
    bright = []
    for d in ("0", "0.5", "1"):
        _, left, _ = hall(renderer, tmp_path, ["Mix=1", f"Damping={d}", "Decay=0.6"],
                          seconds=1.2, extra=["--fault", "0.3..2:0"], name=f"dmp{d}")
        bright.append(brightness(left[int(0.6 * RATE):int(1.0 * RATE)]))
    assert bright[0] > 1.5 * bright[1] > 2.25 * bright[2]


def test_diffusion_smooths_the_onset(renderer, tmp_path):  # noqa: F811
    # Without the all-passes the first 50 ms are a few sharp reflections; with
    # them, a dense wash: the peak over RMS falls (measured 20.8 and 6.4).
    crest = []
    for d in ("0", "1"):
        _, left, _ = impulse(renderer, tmp_path, [*STATIC, f"Diffusion={d}"], 0.2, name=f"df{d}")
        start = first_nonzero(left)
        seg = left[start:start + int(0.05 * RATE)]
        crest.append(max(abs(v) for v in seg) / math.sqrt(sum(v * v for v in seg) / len(seg)))
    assert crest[0] > 2 * crest[1]


def test_mod_spreads_a_sine(renderer, tmp_path):  # noqa: F811
    # Each line's slow random walk moves its delay by up to +/-1 ms: the
    # reverb of a steady sine is no longer one pure line. Energy away from
    # 440 Hz, relative to it, over 1 s of steady state (a short decay, so the
    # modes the onset rang have gone): measured 8e-8 at Mod 0, 0.89 at Mod 1.
    spread = {}
    for m in ("0", "1"):
        _, left, _ = hall(renderer, tmp_path, ["Mix=1", f"Mod={m}", "Decay=0.3"], input="sine",
                          seconds=2.6, name=f"mod{m}")
        seg = left[int(1.6 * RATE):int(1.6 * RATE) + RATE // 2 * 2]
        total = sum(v * v for v in seg) / len(seg) * 2
        on = goertzel(seg, 440)
        spread[m] = (total - on) / on
    assert spread["0"] < 1e-6
    assert spread["1"] > 0.1


def test_width_zero_is_mono_and_one_is_wide(renderer, tmp_path):  # noqa: F811
    _, left, right = hall(renderer, tmp_path, ["Mix=1", "Width=0"], name="w0")
    assert left == right
    _, left, right = hall(renderer, tmp_path, ["Mix=1", "Width=1"], name="w1")
    a, b = int(0.3 * RATE), RATE
    corr = sum(x * y for x, y in zip(left[a:b], right[a:b])) / math.sqrt(
        sum(x * x for x in left[a:b]) * sum(y * y for y in right[a:b]))
    assert abs(corr) < 0.2                                  # measured -0.05


def test_low_cut_thins_the_lows(renderer, tmp_path):  # noqa: F811
    # A one-pole high-pass on the input, 10 Hz (0) to 1 kHz (1): the lows of
    # the reverb, seen through a one-pole low-pass at 100 Hz (which lets some
    # mids through), fall by more than 10 dB (measured 11.6).
    lows = {}
    for c in ("0", "1"):
        _, left, _ = hall(renderer, tmp_path, ["Mix=1", f"Low Cut={c}"], seconds=1.5,
                          name=f"lc{c}")
        k = 1 - math.exp(-2 * math.pi * 100 / RATE)
        lp, acc = 0.0, 0.0
        for v in left[int(0.5 * RATE):int(1.5 * RATE)]:
            lp += k * (v - lp)
            acc += lp * lp
        lows[c] = acc
    assert 10 * math.log10(lows["1"] / lows["0"]) < -10


def test_freeze_from_the_start_lets_nothing_in(renderer, tmp_path):  # noqa: F811
    # Frozen before the first block, the input gain is exactly 0: at Mix 1
    # nothing at all comes out, and at Mix 0.5 the dry signal alone.
    s, _, _ = hall(renderer, tmp_path, ["Freeze=1", "Mix=1"], name="frozen")
    assert s["raw_peak"] == 0.0
    ref = run(renderer, tmp_path, ["--input", "noise", "--seconds", "1",
                                   *cli_fx(["Gain=1"], "test-gain")], "ref")
    out = hall(renderer, tmp_path, ["Freeze=1", "Mix=0.5"], name="dry")
    assert out[1] == ref[1] and out[2] == ref[2]


def test_long_decay_on_loud_noise_stays_bounded(renderer, tmp_path):  # noqa: F811
    # Ten seconds of noise into the longest decay, brightest and largest
    # setting, Mod at full: bounded by the words' range, and settled
    # (measured peak 1.65, RMS 0.296 then 0.299).
    s, left, right = hall(renderer, tmp_path, ["Mix=1", "Decay=1", "Size=1", "Damping=0",
                                               "Mod=1", "Low Cut=0"], seconds=10)
    assert s["nonfinite"] == 0 and s["raw_peak"] <= 8.0
    for ch in (left, right):
        assert rms(ch, 8, 10) < 1.1 * rms(ch, 6, 8)


def test_tail_after_an_engine(renderer, tmp_path):  # noqa: F811
    note = ["--engine", "macro", "--param", "Decay=0.2", "--note", "0:60:100:0.3",
            "--seconds", "2.0"]
    _, dry, _ = run(renderer, tmp_path, note, "dry")
    s, left, right = run(renderer, tmp_path, [*note, *cli_fx(["Decay=0.6", "Mix=0.5"]),
                                              "--fx", "plate", "--fx-param", "Mix=0.2"], "wet")
    assert s["fx"] == ["hall", "plate"] and s["nonfinite"] == 0
    assert rms(dry, 1.2, 1.6) < 1e-4
    assert rms(left, 1.2, 1.6) > 1e-3 and rms(right, 1.2, 1.6) > 1e-3
    assert left != right                         # a mono engine comes out stereo


# --- fm1-hall-selftest: what fm1-render cannot drive ------------------------------

def test_selftest(renderer):  # noqa: F811
    # `make` in the renderer fixture builds the selftest too.
    res = subprocess.run([str(SELFTEST)], capture_output=True, text=True)
    lines = {}
    for line in res.stdout.splitlines():
        if line:
            d = json.loads(line)
            lines[d["check"]] = d
    assert set(lines) == {
        "refuses_bad_rates", "size_follows_the_rate", "abuse_stays_finite_and_bounded",
        "ignores_prior_memory", "block_sizes_do_not_matter", "sweeps_stay_bounded",
        "decays_to_exact_zero", "decay_time_is_decay", "freeze_lets_nothing_in",
        "freeze_holds_then_lets_go", "freeze_switches_cleanly"}
    assert all(d["ok"] for d in lines.values()), [d for d in lines.values() if not d["ok"]]
    assert res.returncode == 0
    assert lines["size_follows_the_rate"]["bytes_44118"] == 49888
