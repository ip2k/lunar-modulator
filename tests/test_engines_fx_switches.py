"""The switch-like controls of Filter, Drive, Comp, the Limiter, DJ Filter,
Tilt, Master Sat, Isolator and Squash, modulated fast (engines/README.md,
"Parameters": switch-like controls that change cleanly are lockable and
modulatable).

Each of them is turned every third host block (192 frames, 4.4 ms: faster
than the 5 ms crossfades and hand-overs, so changes also land while one is
running) through fm1-render's --fx-param-at, on a steady sine and on notes
with sharp onsets, for about 200 changes a render. The output must stay
finite, keep each effect's ceiling where it has one (the Limiter's, and
Comp's 0 dBFS with Auto Gain on), and step from one sample to the next by no
more than it does with the control held at any of its values, from the
effect's own start (so a Filter type's start from rest, such as a Comb's
first echo a delay later, is in the reference), plus the crossfade bound:
two outputs of peak P blended over 5 ms (220 frames) can add at most
2P / 220 to a step. A switch that cut instead of crossfading would step by
up to 2P. The 16-bit WAV after the bus limiter is what is measured, so
every case stays under the bus limiter's 0.98.

The figures in the comments were measured on the desktop build (Apple
clang, arm64, 2026-10-02).
"""
import random

import pytest

from tests.engine_helpers import RATE, renderer  # noqa: F401
from tests.test_engines_mi_fx import run

LSB = 1 / 32767.0
FADE = 220                    # 5 ms at 44,118 Hz
EVERY = 3 * 64                # frames between changes
SECONDS = 1.0
START = 0.1                   # the first change, s

SINE = ["--input", "sine"]
# Plucks with sharp onsets every 60 ms, loud enough to limit and compress.
NOTES = ["--engine", "macro", "--param", "Model=0"]
for k in range(16):
    NOTES += ["--note", f"{0.02 + 0.06 * k:.3f}:{45 + 7 * (k % 4)}:127:0.03"]


def values_for(values, seed):
    """About 200 values, each different from the one before: ENUM indices
    in a shuffled order, or Lookahead anywhere in 1..5 ms, or in 0..5 ms
    with 0 now and then."""
    rng = random.Random(seed)
    out, last = [], None
    n = int((SECONDS - START) * RATE / EVERY)
    for _ in range(n):
        if values == "lookahead":
            v = round(1 + 4 * rng.random(), 3)
        elif values == "lookahead0":
            v = 0.0 if rng.random() < 0.2 else round(5 * rng.random(), 3)
        else:
            v = rng.choice([x for x in values if x != last])
        out.append(v)
        last = v
    return out


def render_case(renderer, tmp_path, fx, base, source, name, schedule=()):  # noqa: F811
    args = [*source, "--seconds", str(SECONDS), "--fx", fx]
    for p in base:
        args += ["--fx-param", p]
    for t, param, value in schedule:
        args += ["--fx-param-at", f"{t:.6f}:1:{param}={value}"]
    return run(renderer, tmp_path, args, name)


def max_step(samples, start):
    return max(abs(samples[i] - samples[i - 1]) for i in range(start + 1, len(samples)))


# (effect, control, its values, the other settings, the source, the ceiling
# the raw output keeps, or None)
CASES = [
    ("filter", "Type", list(range(7)), ["Cutoff=1200", "Resonance=0.5", "Drive=0.2"], "sine", None),
    ("filter", "Type", list(range(7)), ["Cutoff=900", "Resonance=0.7", "Mode=1.5"], "notes", None),
    # Low and resonant, in high-pass and notch modes: a type started from
    # rest rings at its cutoff, and a Comb's first echo comes 350 frames
    # later. Faded straight in (before 2026-10-02) they stepped 24 times the
    # crossfade bound here; now they start unheard with their input faded in.
    ("filter", "Type", list(range(7)), ["Cutoff=126", "Resonance=0.79", "Mode=2.87", "Morph=0.32"],
     "sine", None),
    ("filter", "Type", list(range(7)), ["Cutoff=847", "Resonance=0.92", "Drive=0.28", "Mode=0.71"],
     "sine", None),
    ("drive", "Type", list(range(5)), ["Drive=12", "Level=-6"], "sine", None),
    ("drive", "Type", list(range(5)), ["Drive=18", "Level=-9", "Bias=0.3"], "notes", None),
    ("drive", "Auto", [0, 1], ["Drive=24", "Level=-6", "Type=3"], "sine", None),
    ("drive", "Auto", [0, 1], ["Drive=-6", "Type=1"], "notes", None),
    ("comp", "Character", list(range(4)), ["Threshold=-30", "Attack=5", "Makeup=6"], "sine", None),
    ("comp", "Character", list(range(4)), ["Threshold=-30", "Attack=20", "Release=60"], "notes", None),
    ("comp", "Auto Rel", [0, 1], ["Threshold=-30", "Ratio=10", "Release=400"], "notes", None),
    ("comp", "Auto Gain", [0, 1], ["Threshold=-30", "Ratio=4", "Character=1"], "sine", 1.0),
    ("comp", "Auto Gain", [0, 1], ["Threshold=-60", "Ratio=21", "Knee=0", "Attack=50"], "notes",
     1.0),
    ("limit", "Mode", [0, 1], ["Drive=12", "Ceiling=-6"], "sine", 10 ** (-6 / 20)),
    ("limit", "Mode", [0, 1], ["Drive=12", "Ceiling=-6", "Release=30"], "notes", 10 ** (-6 / 20)),
    # ROUND (2026-10-05) among the Modes: its share glides like SOFT CLIP's.
    ("limit", "Mode", [0, 1, 2], ["Drive=12", "Ceiling=-6"], "sine", 10 ** (-6 / 20)),
    ("limit", "Mode", [0, 1, 2], ["Drive=12", "Ceiling=-6", "Release=30"], "notes",
     10 ** (-6 / 20)),
    ("limit", "Lookahead", "lookahead", ["Drive=12", "Ceiling=-6", "Release=30"], "notes",
     10 ** (-6 / 20)),
    ("limit", "Lookahead", "lookahead0", ["Drive=12", "Ceiling=-6", "Release=30"], "notes",
     10 ** (-6 / 20)),
    ("limit", "Lookahead", "lookahead", ["Drive=12", "Ceiling=-6"], "sine", 10 ** (-6 / 20)),
    ("limit", "Lookahead", "lookahead0", ["Drive=12", "Ceiling=-6", "Mode=1"], "sine",
     10 ** (-6 / 20)),
    # The master-bus pack (2026-10-03): Slope crossfades over 5 ms, Curve
    # glides its coefficients, Shape crossfades over 5 ms, Kill glides the
    # band gains over 5 ms.
    ("djfilter", "Slope", [0, 1], ["Sweep=-0.5", "Resonance=0.8", "Dead Zone=0"], "sine", None),
    ("djfilter", "Slope", [0, 1], ["Sweep=0.45", "Resonance=1"], "notes", None),
    ("tilt", "Curve", [0, 1], ["Tilt=9", "Pivot=600"], "sine", None),
    ("tilt", "Curve", [0, 1], ["Tilt=-9", "Pivot=2000", "Level=-6"], "notes", None),
    ("sat", "Shape", [0, 1], ["Mix=1", "Drive=18", "Glue=0.5", "Asymmetry=0.5"], "sine", None),
    ("sat", "Shape", [0, 1], ["Mix=1", "Drive=12", "Clean Lo=20", "Clean Hi=20000"], "notes", None),
    ("isolator", "Kill", list(range(8)), ["Low=0.9", "Mid=0.6", "High=1"], "sine", None),
    ("isolator", "Kill", list(range(8)), [], "notes", None),
    # Dynamics pack 3 (2026-10-05): Squash's Type starts the new Type from the
    # gain in force and crossfades over 5 ms.
    ("squash", "Type", [0, 1, 2], ["Squash=0.8", "Release=120"], "sine", None),
    ("squash", "Type", [0, 1, 2], ["Squash=0.7", "Gate=-40", "Output=6"], "notes", None),
]


@pytest.mark.parametrize("fx,param,values,base,source,ceiling", CASES,
                         ids=[f"{k}-{c[0]}-{c[1]}-{c[4]}" for k, c in enumerate(CASES)])
def test_fast_modulation_is_clean(renderer, tmp_path, fx, param, values, base, source,
                                  ceiling):  # noqa: F811
    src = SINE if source == "sine" else NOTES
    start = int(START * RATE)
    # The control held at each value: its own steps and peaks.
    held = values
    if values == "lookahead":
        held = [1.0, 2.5, 5.0]
    elif values == "lookahead0":
        held = [0.0, 0.1, 0.5, 1.0, 2.5, 5.0]
    steady_step = peak = 0.0
    for v in held:
        s, left, right, _ = render_case(renderer, tmp_path, fx, [*base, f"{param}={v}"], src,
                                        f"held{v}")
        assert s["nonfinite"] == 0
        steady_step = max(steady_step, max_step(left, 0), max_step(right, 0))
        peak = max(peak, max(abs(x) for x in left[start:]), max(abs(x) for x in right[start:]))
    # Modulated: a change every third block, from 0.1 s.
    seq = values_for(values, 7)
    schedule = [((start + k * EVERY - 0.5) / RATE, param, v) for k, v in enumerate(seq)]
    s, left, right, _ = render_case(renderer, tmp_path, fx, [*base, f"{param}={seq[0]}"], src,
                                    "moving", schedule)
    assert s["nonfinite"] == 0
    assert peak < 0.98                                 # the bus limiter never acts
    moving = max(max_step(left, start), max_step(right, start))
    bound = steady_step + 2 * peak / FADE + 2 * LSB
    assert moving <= bound, (moving, steady_step, bound)
    if ceiling is not None:
        assert s["raw_peak"] <= ceiling + 1e-6
