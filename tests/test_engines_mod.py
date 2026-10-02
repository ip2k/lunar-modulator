"""The modulation primitives (engines/mod/fm1_mp.h, engines/mod/README.md),
driven through engines/build/fm1-mod: shapes against their formulas, ranges,
NaN safety, determinism per seed, block-size independence (every value a
chunked `process` returns equals the per-sample `render` at that sample), the
S&H wrap fix, the envelope's Peaks behaviour, the slew, S&H, Turing register
and clock helper, no heap or libm, and independence from prior memory.
"""
import json
import math
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENGINES = ROOT / "engines"
TOOL = ENGINES / "build" / "fm1-mod"
RATE = 44118
TWO32 = 1 << 32
SHAPES = ["sine", "triangle", "saw_up", "saw_down", "square", "smooth", "sh", "walk"]


@pytest.fixture(scope="session")
def mod_tool():
    if not shutil.which("make") or not (shutil.which("cc") or shutil.which("gcc")):
        pytest.skip("no make / C compiler")
    subprocess.run(["make", "-C", str(ENGINES), "-j4", "build/fm1-mod"], check=True,
                   stdout=subprocess.DEVNULL)
    return TOOL


def run(tool, lines, fill=None):
    args = [str(tool)] + (["--fill", fill] if fill else []) + ["-"]
    p = subprocess.run(args, input="\n".join(lines) + "\n", capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return [json.loads(line) for line in p.stdout.splitlines()]


def finite(xs):
    return all(x is not None and math.isfinite(x) for x in xs)


def chunks(total, rng, hi=300):
    out = []
    while total:
        n = min(total, rng.randint(1, hi))
        out.append(n)
        total -= n
    return out


# ---- LFO ---------------------------------------------------------------------------------------

def inc64(state):
    """The LFO's 32.32 increment per sample."""
    return (state["inc"] << 32) | state["inc_frac"]


def phase_after(state, k):
    """Phase after k samples from phase 0 and fraction 0."""
    return (k * inc64(state) >> 32) % TWO32


def wraps_after(state, k):
    return k * inc64(state) >> 64

def expected_shape(shape, p, pw=0.5):
    x = p / TWO32
    if shape == "sine":
        return math.sin(2 * math.pi * x)
    if shape == "triangle":
        return 4 * x if x < 0.25 else (2 - 4 * x if x < 0.75 else 4 * x - 4)
    if shape == "saw_up":
        return 2 * x - 1
    if shape == "saw_down":
        return 1 - 2 * x
    if shape == "square":
        return 1.0 if x < pw else -1.0
    raise ValueError(shape)


@pytest.mark.parametrize("shape", ["sine", "triangle", "saw_up", "saw_down", "square"])
def test_lfo_shapes_follow_their_formulas(mod_tool, shape):
    out = run(mod_tool, ["lfo a 3", f"shape a {shape}", "pw a 0.3", "hz a 7.3", "state a",
                         "render a 20000"])
    inc = out[0]["inc"]
    for i, v in enumerate(out[1]["r"]):
        p = phase_after(out[0], i + 1)
        if shape == "square" and min(abs(p - 0.3 * TWO32), p, TWO32 - p) < 2 * inc:
            continue
        assert v == pytest.approx(expected_shape(shape, p, 0.3), abs=2e-6), (i, p)


def test_lfo_ranges_and_extremes(mod_tool):
    lines = []
    for s in SHAPES:
        for hz in ("0.01", "7", "300", "22059", "1e9"):
            lines += [f"lfo {s}{hz} 11", f"shape {s}{hz} {s}", f"walk {s}{hz} 1",
                      f"hz {s}{hz} {hz}", f"render {s}{hz} 3000"]
    out = run(mod_tool, lines)
    for o in out:
        assert finite(o["r"]) and all(-1.0 <= v <= 1.0 for v in o["r"])
    out = run(mod_tool, ["lfo a", "shape a square", "hz a 50", "pw a 0", "render a 2000",
                         "pw a 1", "render a 2000"])
    assert set(out[0]["r"]) == {-1.0} and set(out[1]["r"]) == {1.0}


def lfo_setup(name, shape, mode, hz, seed=5):
    return [f"lfo {name} {seed}", f"shape {name} {shape}", f"mode {name} {mode}",
            f"hz {name} {hz}", f"start {name} 0.3", "walk " + name + " 0.6", f"reset {name}"]


@pytest.mark.parametrize("shape", SHAPES)
@pytest.mark.parametrize("mode,hz", [("free", "3.7"), ("free", "2900"), ("one", "11"),
                                     ("half", "11")])
def test_lfo_block_size_independence(mod_tool, shape, mode, hz):
    """Every value a chunked process() returns equals the per-sample render at
    that sample, for blocks of 1, 7 and 64 and random splits, with a retrigger
    at sample 9,000 in every run."""
    total, event = 17920, 9000
    lines = lfo_setup("ref", shape, mode, hz) + [f"render ref {event}", "reset ref",
                                                 f"render ref {total - event}", "state ref"]
    out = run(mod_tool, lines)
    ref = out[0]["r"] + out[1]["r"]
    ref_state = out[2]
    rng = random.Random(f"{shape}{mode}{hz}")
    for scheme in ("7", "64", "random"):
        lines = lfo_setup("x", shape, mode, hz)
        ends = []
        for lo, hi in ((0, event), (event, total)):
            if lo:
                lines.append("reset x")
            n = hi - lo
            parts = (chunks(n, rng) if scheme == "random"
                     else [int(scheme)] * (n // int(scheme)) + ([n % int(scheme)] if n % int(scheme) else []))
            pos = lo
            for c in parts:
                lines.append(f"proc x {c}")
                pos += c
                ends.append(pos)
        lines.append("state x")
        out = run(mod_tool, lines)
        for pos, o in zip(ends, out):
            assert o["v"] == ref[pos - 1], (scheme, pos)
        assert out[-1] == ref_state, scheme


def test_lfo_sample_hold_draws_on_every_wrap(mod_tool):
    """The Schwung S&H fix. At 30 Hz in 128-sample calls a call advances 0.087
    of a cycle, more than Schwung's 0.05 window, so re-rolling only when
    phase < 0.05 misses wraps. Counting the accumulator's carries draws once
    per wrap, every time."""
    blocks = 2000
    out = run(mod_tool, ["lfo a 1", "shape a sh", "hz a 30", "state a"]
              + ["proc a 128"] * blocks + ["state a"])
    inc = out[0]["inc"]
    values = [o["v"] for o in out[1:-1]]
    expected = wraps_after(out[0], 128 * blocks)
    changes = sum(1 for a, b in zip(values, values[1:]) if a != b)
    first = 1 if values[0] != out[0]["v"] else 0
    assert out[-1]["wraps"] == expected
    assert changes + first == expected
    # Schwung's rule on the same phases: a new value only if the phase after
    # the call is below 0.05 of a cycle.
    schwung = sum(1 for k in range(1, blocks + 1) if phase_after(out[0], 128 * k) < 0.05 * TWO32)
    assert inc * 128 / TWO32 > 0.05
    assert schwung < 0.75 * expected, (schwung, expected)


def test_lfo_several_wraps_in_one_call_draw_several_times(mod_tool):
    out = run(mod_tool, ["lfo a 2", "shape a sh", "hz a 2000", "state a", "proc a 64",
                         "state a", "lfo b 2", "shape b sh", "hz b 2000", "render b 64",
                         "state b"])
    assert out[2]["wraps"] == wraps_after(out[0], 64) >= 2
    assert out[1]["v"] == out[3]["r"][-1]
    assert out[4]["wraps"] == out[2]["wraps"]


GOLDEN_SH_SEED1_1KHZ = [0.718086243, -0.74809289, -0.645334482, 0.451751113]


def test_lfo_determinism_per_seed(mod_tool):
    """A seed fixes the random shapes on every platform: the draws are integer
    (xorshift64*) and land on multiples of 2^-23, so these values are exact."""
    out = run(mod_tool, ["lfo a 1", "shape a sh", "hz a 1000"] + ["proc a 64"] * 4)
    assert [o["v"] for o in out] == GOLDEN_SH_SEED1_1KHZ
    for shape in ("sh", "smooth", "walk"):
        lines = []
        for name, seed in (("a", 7), ("b", 7), ("c", 8)):
            lines += [f"lfo {name} {seed}", f"shape {name} {shape}", f"hz {name} 40",
                      f"render {name} 5000"]
        lines += ["lfo d 99", "seed d 7", f"shape d {shape}", "hz d 40", "render d 5000"]
        a, b, c, d = (o["r"] for o in run(mod_tool, lines))
        assert a == b == d
        assert a != c


def test_lfo_one_shot_and_half_hold_then_retrigger(mod_tool):
    out = run(mod_tool, [
        "lfo a", "shape a saw_up", "mode a one", "hz a 100", "reset a",
        "proc a 200", "proc a 1000", "state a",            # 441 samples a cycle: done
        "reset a", "value a", "proc a 10",
        "lfo b", "shape b saw_up", "mode b half", "hz b 100", "reset b", "proc b 1000", "state b",
        "lfo c", "shape c sine", "mode c one", "start c 0.25", "hz c 100", "reset c",
        "proc c 5000", "state c",
        "mode a free", "proc a 1000", "state a"])
    assert out[0]["v"] < 0.9 and out[1]["v"] == 1.0 and out[2]["done"] == 1
    assert out[3]["v"] == -1.0 and out[4]["v"] > -1.0
    assert out[6]["done"] == 1 and out[6]["v"] == pytest.approx(0.0, abs=1e-6)
    assert out[8]["done"] == 1 and out[8]["v"] == pytest.approx(1.0, abs=1e-6)
    # Back to free: two resets drew two cycles; 1,010 samples at 441 a cycle
    # cross two more wraps.
    assert out[10]["done"] == 0 and out[10]["wraps"] == 4


def test_lfo_rate_is_a_ratio(mod_tool):
    """120 BPM is 2 beats a second; ratio 0.25 is one cycle per 4/4 bar, 2 s."""
    out = run(mod_tool, ["lfo a", "hz a 2 0.25", "state a", "lfo b", "hz b 0.5", "state b",
                         f"proc a {2 * RATE - 1}", "state a", "proc a 1", "state a",
                         "hz b 1e9", "state b", "hz b nan", "state b", "hz b -5", "state b",
                         "hz b inf 0", "state b"])
    assert inc64(out[0]) == inc64(out[1]) and out[0]["hz"] == 0.5
    # 2 s is 88,236 samples exactly: the rounded-up increment wraps on the
    # last one, not one late.
    assert out[3]["wraps"] == 0 and out[5]["wraps"] == 1
    assert out[5]["phase"] < 2
    assert out[6]["hz"] == RATE / 2 and inc64(out[6]) == 1 << 63
    assert inc64(out[7]) == inc64(out[8]) == inc64(out[9]) == 0


def test_lfo_sync_counts_each_wrap_once(mod_tool):
    """sync() moves by the shorter way. A forward move across the wrap draws;
    a backward one owes, and the next forward crossing pays instead of drawing,
    so jitter around the wrap point draws once per cycle."""
    end, past = TWO32 - 1000, 1000
    out = run(mod_tool, ["lfo a 3", "shape a sh", "hz a 0", "state a",
                         "sync a 100000", "state a",                    # forward, inside the cycle
                         f"sync a {end}", "state a",                    # back across the wrap: owe
                         f"sync a {past}", "state a",                   # forward across: pay
                         f"sync a {end}", f"sync a {past}", "state a",  # jitter: pay again
                         "sync a 2147483647", "sync a 4294967291", "sync a 5", "state a"])
    w0 = out[0]["wraps"]
    assert (out[1]["wraps"], out[1]["owed"]) == (w0, 0)
    assert (out[2]["wraps"], out[2]["owed"]) == (w0, 1)
    assert (out[3]["wraps"], out[3]["owed"]) == (w0, 0)
    assert (out[4]["wraps"], out[4]["owed"]) == (w0, 0)
    assert (out[5]["wraps"], out[5]["owed"]) == (w0 + 1, 0)
    assert out[5]["v"] != out[4]["v"]


def test_lfo_survives_nan_and_inf(mod_tool):
    lines = []
    for i, s in enumerate(SHAPES):
        n = f"l{i}"
        lines += [f"lfo {n} {i}", f"shape {n} {s}", f"hz {n} nan", f"pw {n} nan",
                  f"walk {n} inf", f"start {n} -inf", f"reset {n}", f"render {n} 100",
                  f"hz {n} 5 nan", f"render {n} 100", f"hz {n} inf", f"pw {n} -inf",
                  f"walk {n} nan", f"start {n} nan", f"render {n} 3000",
                  f"shape {n} 99", f"mode {n} -4", f"render {n} 100", f"state {n}"]
    out = run(mod_tool, lines)
    for o in out:
        vals = o["r"] if "r" in o else [o["v"]]
        assert finite(vals) and all(-1 <= v <= 1 for v in vals)
    assert out[0]["r"] == [out[0]["r"][0]] * 100     # NaN rate: stopped


# ---- Envelope ------------------------------------------------------------------------------------

def env_lines(name, cfg):
    return [f"env {name}"] + [c.replace("{n}", name) for c in cfg]


def test_env_adsr_shape(mod_tool):
    out = run(mod_tool, env_lines("e", ["adsr {n} 0.01 0.1 0.5 0.2 linear off", "state {n}",
                                        "gate {n} 1", "render {n} 10000", "state {n}",
                                        "gate {n} 0", "render {n} 10000", "state {n}"]))
    inc0 = out[0]["inc0"]
    assert out[0]["done"] == 1 and out[0]["v"] == 0.0
    up = out[1]["r"]
    n_attack = -(-TWO32 // inc0)                 # samples to the attack's overflow
    assert up[n_attack - 1] == 1.0 and max(up[:n_attack - 1]) < 1.0
    assert all(b > a for a, b in zip(up[:n_attack - 1], up[1:n_attack]))
    assert up[-1] == 0.5 and out[2]["seg"] == 2 and out[2]["done"] == 0
    down = out[3]["r"]
    assert all(b <= a for a, b in zip(down, down[1:]))
    assert down[-1] == 0.0 and out[4]["done"] == 1
    assert n_attack == pytest.approx(0.01 * RATE, abs=1)
    released = next(i for i, v in enumerate(down) if v == 0.0)
    assert released + 1 == pytest.approx(0.2 * RATE, abs=1)


@pytest.mark.parametrize("curve,formula", [
    ("linear", lambda t: t),
    ("expo", lambda t: (1 - math.exp(-4 * t)) / (1 - math.exp(-4))),
    ("quartic", lambda t: t ** 3.32)])
def test_env_curves_are_peaks(mod_tool, curve, formula):
    """Mid-segment values against Peaks' formulas at the segment's own phase.
    The tolerance is the 257-point table's interpolation error, as in Peaks."""
    lines = env_lines("e", [f"adsr {{n}} 1 1 1 1 {curve} off", "hard {n} 1"])
    for k in (1, 5000, 11000, 22059, 30000, 44000):
        lines += ["trigger e", f"proc e {k}", "state e"]
    out = run(mod_tool, lines)
    for proc, st in zip(out[0::2], out[1::2]):
        assert st["seg"] == 0
        assert proc["v"] == pytest.approx(formula(st["phase"] / TWO32), abs=4e-5)


def test_env_loops(mod_tool):
    out = run(mod_tool, env_lines("e", [
        "adsr {n} 0.005 0.005 0.5 0.05 linear ad", "gate {n} 1", "render {n} 5000",
        "gate {n} 0", "render {n} 5000", "state {n}"]))
    held, rel = out[0]["r"], out[1]["r"]
    peaks = sum(1 for v in held if v == 1.0)
    troughs = sum(1 for v in held if v == 0.0)
    assert peaks >= 10 and troughs >= 10            # 0 -> 1 -> 0 while held
    assert rel[-1] == 0.0 and out[2]["done"] == 1
    out = run(mod_tool, env_lines("e", [
        "adsr {n} 0.005 0.005 0.25 0.005 linear adr", "gate {n} 1", "render {n} 10000",
        "gate {n} 0", "render {n} 5000", "state {n}"]))
    held = out[0]["r"]
    assert held.count(1.0) >= 10 and held.count(0.25) >= 10 and held.count(0.0) >= 10
    assert out[2]["done"] == 1
    # AD: the gate's fall does not cut it; with loop it runs on with the gate low.
    out = run(mod_tool, env_lines("e", [
        "ad {n} 0.01 0.01 linear 0", "gate {n} 1", "proc {n} 10", "gate {n} 0",
        "render {n} 2000", "state {n}",
        "ad {n} 0.01 0.01 linear 1", "trigger {n}", "gate {n} 0", "render {n} 5000", "state {n}"]))
    assert max(out[1]["r"]) == 1.0 and out[2]["done"] == 1
    assert out[3]["r"].count(1.0) >= 5 and out[4]["done"] == 0


def test_env_retrigger_from_current_value_or_hard_reset(mod_tool):
    cfg = ["adsr {n} 0.01 0.2 0.0 0.2 linear off", "gate {n} 1", "proc {n} 2000",
           "gate {n} 0", "gate {n} 1", "render {n} 3"]
    soft = run(mod_tool, env_lines("e", cfg))
    hard = run(mod_tool, env_lines("e", ["hard {n} 1"] + cfg))
    before = soft[0]["v"]
    assert 0.2 < before < 0.9
    assert soft[1]["r"][0] == pytest.approx(before, abs=1e-3) and soft[1]["r"][0] > before
    assert hard[1]["r"][0] < 0.01


ENV_CONFIGS = [
    ["adsr {n} 0.003 0.02 0.6 0.01 expo off"],
    ["adsr {n} 0.004 0.003 0.3 0.006 quartic ad"],
    ["adsr {n} 0.002 0.004 0.5 0.003 linear adr"],
    ["ad {n} 0.002 0.003 expo 1"],
    ["config {n} 8 5 2 7", "startlevel {n} -0.5"]
    + [f"segment {{n}} {i} {(-1) ** i * 0.1 * i} {0.0005 * (i + 1)} {['linear', 'expo', 'quartic'][i % 3]}"
       for i in range(8)],
]


@pytest.mark.parametrize("cfg", range(len(ENV_CONFIGS)))
def test_env_block_size_independence(mod_tool, cfg):
    """Gate events at fixed samples; every chunked process() value equals the
    per-sample render there, whatever the split."""
    events = [(0, "gate {n} 1"), (2500, "gate {n} 0"), (4000, "trigger {n}"),
              (4100, "gate {n} 0"), (6000, "gate {n} 1"), (9000, "gate {n} 0")]
    total = 12000
    bounds = [e[0] for e in events] + [total]
    lines = env_lines("ref", ENV_CONFIGS[cfg])
    for (at, ev), end in zip(events, bounds[1:]):
        lines += [ev.replace("{n}", "ref"), f"render ref {end - at}"]
    lines.append("state ref")
    out = run(mod_tool, lines)
    ref = [v for o in out[:-1] for v in o["r"]]
    rng = random.Random(cfg)
    for scheme in ("7", "64", "random"):
        lines = env_lines("x", ENV_CONFIGS[cfg])
        ends = []
        for (at, ev), end in zip(events, bounds[1:]):
            lines.append(ev.replace("{n}", "x"))
            n = end - at
            parts = chunks(n, rng, 500) if scheme == "random" else (
                [int(scheme)] * (n // int(scheme)) + ([n % int(scheme)] if n % int(scheme) else []))
            pos = at
            for c in parts:
                lines.append(f"proc x {c}")
                pos += c
                ends.append(pos)
        lines.append("state x")
        res = run(mod_tool, lines)
        for pos, o in zip(ends, res):
            assert o["v"] == ref[pos - 1], (scheme, pos)
        assert res[-1] == out[-1]


def test_env_survives_nan_and_bad_shapes(mod_tool):
    out = run(mod_tool, env_lines("e", [
        "adsr {n} nan inf -inf nan 99 -3", "gate {n} 1", "render {n} 200", "gate {n} 0",
        "render {n} 200", "config {n} 0 9 5 2", "segment {n} 0 nan nan 7", "segment {n} 9 1 1 0",
        "startlevel {n} inf", "trigger {n}", "render {n} 200",
        "config {n} 99 -1 -1 99", "segment {n} 3 -inf 0.001 1", "trigger {n}", "render {n} 2000",
        "state {n}"]))
    for o in out[:-1]:
        assert finite(o["r"]) and all(-1 <= v <= 1 for v in o["r"])
    assert out[-1]["segments"] == 8


def test_env_minimum_segment_is_two_samples(mod_tool):
    out = run(mod_tool, env_lines("e", ["adsr {n} 0 0 1 0 linear off", "gate {n} 1",
                                        "proc {n} 1", "state {n}", "proc {n} 1", "state {n}"]))
    assert out[1]["seg"] == 0 and out[3]["seg"] == 1 and out[2]["v"] == 1.0


def test_env_time_from_knob_is_peaks_curve(mod_tool):
    ks = [i / 64 for i in range(65)]
    out = run(mod_tool, [f"knob {k}" for k in ks] + ["knob nan", "knob -1", "knob 9"])
    vals = [o["v"] for o in out]
    g = 0.175
    for k, v in zip(ks, vals):
        want = (0.0005 ** g + k * (8 ** g - 0.0005 ** g)) ** (1 / g)
        assert v == pytest.approx(want, rel=2e-3), k
    assert vals[0] == pytest.approx(0.0005) and vals[64] == 8.0
    assert all(b > a for a, b in zip(vals[:65], vals[1:65]))
    assert vals[65] == vals[0] and vals[66] == vals[0] and vals[67] == 8.0


# ---- Slew ------------------------------------------------------------------------------------------

def test_slew_linear_rise_and_fall_times(mod_tool):
    out = run(mod_tool, ["slew s", "times s 0.1 0.2", "render s 10000 1", "render s 10000 0"])
    up, down = out[0]["r"], out[1]["r"]
    t_up = up.index(1.0) + 1
    t_down = down.index(0.0) + 1
    assert t_up == pytest.approx(0.1 * RATE, abs=1) and t_down == pytest.approx(0.2 * RATE, abs=1)
    assert all(0 <= v <= 1 for v in up + down)
    assert all(b >= a for a, b in zip(up, up[1:])) and all(b <= a for a, b in zip(down, down[1:]))


def test_slew_expo_time_constant_and_exact_arrival(mod_tool):
    tc = 0.01
    n = round(tc * RATE)
    out = run(mod_tool, ["slew s", "mode s expo", f"times s {tc} {tc * 3}", f"proc s {n} 1",
                         f"proc s {200 * n} 1", f"proc s {3 * n} 0", f"proc s {2000 * n} 0"])
    assert out[0]["v"] == pytest.approx(1 - math.exp(-1), abs=3e-3)
    assert out[1]["v"] == 1.0
    assert out[2]["v"] == pytest.approx(math.exp(-1), abs=3e-3)
    assert out[3]["v"] == 0.0


@pytest.mark.parametrize("mode", ["linear", "expo"])
def test_slew_block_size_independence(mod_tool, mode):
    targets = [(0, "0.8"), (3000, "-0.6"), (3500, "0.1"), (9000, "1.5"), (15000, "-3")]
    total = 20000
    bounds = [t[0] for t in targets] + [total]
    setup = ["slew {n}", f"mode {{n}} {mode}", "times {n} 0.05 0.02"]
    lines = [s.replace("{n}", "ref") for s in setup]
    for (at, x), end in zip(targets, bounds[1:]):
        lines.append(f"render ref {end - at} {x}")
    ref = [v for o in run(mod_tool, lines) for v in o["r"]]
    rng = random.Random(mode)
    for scheme in ("7", "64", "random"):
        lines = [s.replace("{n}", "x") for s in setup]
        ends = []
        for (at, x), end in zip(targets, bounds[1:]):
            n = end - at
            parts = chunks(n, rng, 700) if scheme == "random" else (
                [int(scheme)] * (n // int(scheme)) + ([n % int(scheme)] if n % int(scheme) else []))
            pos = at
            for c in parts:
                lines.append(f"proc x {c} {x}")
                pos += c
                ends.append(pos)
        for pos, o in zip(ends, run(mod_tool, lines)):
            assert o["v"] == ref[pos - 1], (scheme, pos)


def test_slew_ignores_non_finite_input(mod_tool):
    out = run(mod_tool, ["slew s", "times s nan inf", "proc s 10 0.5", "proc s 10 nan",
                         "proc s 10 inf", "proc s 44118 0", "times s nan -inf",
                         "render s 5 nan -inf 0.25", "mode s 7", "reset s nan",
                         "value s", "reset s 100", "value s"])
    # NaN rise is instant; an infinite fall is the longest, 3,600 s.
    assert out[0]["v"] == 0.5 and out[1]["v"] == 0.5 and out[2]["v"] == 0.5
    assert 0.4998 < out[3]["v"] < 0.5
    assert out[4]["r"] == [0.0, 0.0, 0.25, 0.25, 0.25]   # the target 0 stays through NaN, -inf
    assert out[5]["v"] == 0.0 and out[6]["v"] == pytest.approx(8.0, abs=1e-6)


# ---- Sample-and-hold ------------------------------------------------------------------------------

def test_sah_sample_and_track(mod_tool):
    out = run(mod_tool, ["sah h", "step h 0.25 0", "step h 0.5 1", "step h 0.75 1",
                         "step h 0.125 0", "step h nan 1", "step h 0.625 0", "step h 0.875 1",
                         "mode h track", "step h 0.25 1", "step h 0.375 1", "step h 0.5 0",
                         "step h inf 1", "step h -0.875 1", "mode h 9", "step h 0.5 1"])
    assert [o["v"] for o in out] == [0.0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.875,
                                     0.25, 0.375, 0.375, 0.375, -0.875, -0.875]


# ---- Turing register ----------------------------------------------------------------------------

def turing_gates(tool, seed, length, flip, n):
    out = run(tool, [f"turing t {seed}", f"length t {length}", f"flip t {flip}"]
              + ["clock t", "state t"] * n)
    return [o["gate"] for o in out[1::2]], [o["r"][0] for o in out[0::2]]


@pytest.mark.parametrize("length", [1, 5, 8, 16, 32])
def test_turing_locked_loop_repeats(mod_tool, length):
    gates, values = turing_gates(mod_tool, 4, length, 0, 200)
    assert all(gates[i] == gates[i + length] for i in range(len(gates) - length))
    assert all(values[i] == values[i + length] for i in range(32, len(values) - length))
    assert all(round(v * 255) == pytest.approx(v * 255, abs=1e-4) and 0 <= v <= 1 for v in values)


@pytest.mark.parametrize("length", [3, 8, 32])
def test_turing_flip_one_inverts_each_pass(mod_tool, length):
    gates, _ = turing_gates(mod_tool, 6, length, 1, 200)
    assert all(gates[i + length] == 1 - gates[i] for i in range(len(gates) - length))


def test_turing_half_is_random_and_seeded(mod_tool):
    a, va = turing_gates(mod_tool, 9, 8, 0.5, 600)
    b, vb = turing_gates(mod_tool, 9, 8, 0.5, 600)
    c, _ = turing_gates(mod_tool, 10, 8, 0.5, 600)
    assert a == b and va == vb and a != c
    assert 0.4 < sum(a) / len(a) < 0.6
    assert any(a[i] != a[i + 8] for i in range(len(a) - 8))
    out = run(mod_tool, ["turing t 1", "state t", "clock t 4", "length t 0", "state t",
                         "length t 99", "flip t nan", "state t"])
    assert out[0]["bits"] == 1262921053                      # golden: seed 1
    assert out[1]["r"] == [0.733333349, 0.46274513, 0.929411829, 0.854902029]
    assert out[2]["length"] == 1 and out[3]["length"] == 32


# ---- Clock divider and multiplier --------------------------------------------------------------

def expected_pulses(t, period, mul):
    if t == 0:
        return 1
    return t * mul // period - (t - 1) * mul // period


@pytest.mark.parametrize("ref,mul,div", [(96, 1, 4), (96, 3, 1), (96, 5, 1), (96, 3, 2),
                                         (24, 7, 3), (1, 4, 1), (96, 1, 1)])
def test_clkdiv_pulses(mod_tool, ref, mul, div):
    n = 3000
    out = run(mod_tool, [f"clkdiv c {ref} {mul} {div}", f"clock c {n}", "state c"])
    p = out[0]["p"]
    assert p == [expected_pulses(t, ref * div, mul) for t in range(n)]
    assert out[1]["phase"] == ((n - 1) * mul % (ref * div)) * TWO32 // (ref * div)
    if (ref, mul, div) == (96, 5, 1):
        assert [t for t in range(200) if p[t]] == [0, 20, 39, 58, 77, 96, 116, 135, 154, 173, 192]


def test_clkdiv_advance_matches_ticks_and_clamps(mod_tool):
    rng = random.Random(3)
    parts = chunks(5000, rng, 400)
    out = run(mod_tool, ["clkdiv c 96 5 3"] + [f"advance c {k}" for k in parts]
              + ["state c", "clkdiv d 96 5 3", "clock d 5000", "state d", "reset c",
                 "clock c 1", "clkdiv z 0 0 0", "state z", "clkdiv b 99999 999 999", "state b"])
    total = sum(o["n"] for o in out[:len(parts)])
    assert total == sum(out[len(parts) + 1]["p"])
    assert out[len(parts)] == out[len(parts) + 2]
    assert out[len(parts) + 3]["p"] == [1]
    assert out[-2]["period"] == 1 and out[-2]["mul"] == 1
    assert out[-1]["period"] == 65535 * 256 and out[-1]["mul"] == 256


def test_lfo_locked_to_clkdiv_never_drifts(mod_tool):
    """The intended use: one LFO cycle per bar, its phase taken from the tick
    clock on every tick. Over 30 bars the LFO starts exactly one cycle per bar
    after the first, as the clock counts them."""
    ticks = 384 * 30
    lines = ["clkdiv c 96 1 4", "lfo l 1", "shape l sh", "hz l 0", "state l"]
    for _ in range(ticks):
        lines += ["clock c", "state c"]
    out = run(mod_tool, lines)
    lfo0 = out[0]
    lines = ["clkdiv c 96 1 4", "lfo l 1", "shape l sh", "hz l 0"]
    phases = [o["phase"] for o in out[2::2]]
    for ph in phases:
        lines.append(f"sync l {ph}")
    lines.append("state l")
    lfo = run(mod_tool, lines)[-1]
    pulses = sum(o["p"][0] for o in out[1::2])
    assert pulses == 30
    assert lfo["wraps"] - lfo0["wraps"] == pulses - 1


# ---- Whole-library contracts -------------------------------------------------------------------------

FORBIDDEN = {"malloc", "calloc", "realloc", "free", "posix_memalign", "aligned_alloc", "strdup",
             "printf", "fprintf", "snprintf", "sprintf", "puts", "fputs", "fopen", "fwrite",
             "rand", "srand", "random"}
FORBIDDEN |= {f + s for f in ("sin", "cos", "tan", "exp", "exp2", "expm1", "log", "log2",
                              "log10", "pow", "sqrt", "floor", "ceil", "fmod", "round",
                              "lround", "trunc", "modf", "frexp", "ldexp", "tanh", "atan",
                              "atan2") for s in ("", "f", "l")}


def test_no_heap_no_stdio_no_libm(mod_tool):
    nm = shutil.which("nm")
    if not nm:
        pytest.skip("no nm")
    objs = sorted(p for p in (ENGINES / "build" / "mod" / "mod").glob("*.o")
                  if p.name != "mp_tool.o")
    assert len(objs) == 8
    for o in objs:
        out = subprocess.check_output([nm, "-u", str(o)], text=True)
        names = {line.split()[-1] for line in out.splitlines() if line.strip()}
        names = {n[1:] if sys.platform == "darwin" and n.startswith("_") else n for n in names}
        bad = names & FORBIDDEN
        assert not bad, f"{o.name} imports {sorted(bad)}"


def test_init_does_not_depend_on_prior_memory(mod_tool):
    lines = []
    for i, s in enumerate(SHAPES):
        lines += [f"lfo l{i} {i}", f"shape l{i} {s}", f"hz l{i} 13", f"render l{i} 500",
                  f"state l{i}"]
    lines += ["env e", "gate e 1", "render e 3000", "state e", "slew s", "times s 0.01 0.01",
              "mode s expo", "render s 300 1", "sah h", "step h 0.5 1", "turing t 3",
              "clock t 20", "clkdiv c 96 3 1", "clock c 200", "state c"]
    outs = [run(mod_tool, lines, fill) for fill in ("0", "0xA5", "0xFF")]
    assert outs[0] == outs[1] == outs[2]


def test_tables_are_generated(mod_tool):
    subprocess.run([sys.executable, str(ENGINES / "mod" / "gen_tables.py"), "--check"], check=True)


def test_struct_sizes_stay_small(mod_tool):
    sizes = json.loads(subprocess.check_output([str(mod_tool), "--sizes"], text=True))
    assert sizes["lfo"] <= 96 and sizes["env"] <= 112 and sizes["slew"] <= 48
    assert sizes["sah"] <= 8 and sizes["turing"] <= 32 and sizes["clkdiv"] <= 16
