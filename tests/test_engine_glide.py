"""Glide and the voice modes (engines/src/glide.h; engines/README.md, "Glide
and voice modes"): a per-note pitch slew in Macro, Macro Heavy, Six-Op FM,
FM6 and Shapes, with Poly, Mono and Legato.

Most checks are exact. A glide is a pitch offset each voice adds after the
key and the bend, the same path as a per-note pitch offset
(FM1_PARAM_NOTE_PITCH), moved once per control block. So a glide is
compared, byte for byte, with the same notes played without glide and the
glide's offsets sent as per-note pitch offsets, one per control block,
computed here in IEEE single precision as glide.h computes them. To land a
call on every control block the host runs at the engine's own rate with
blocks of its control block (Macro, Macro Heavy and Six-Op at 47,872.34 Hz,
where the resampler passes the mix through, in blocks of 12 and 16; Shapes
at 96 kHz in 24; FM6 at 44,118 Hz in msfa's 64). The Mono and Legato rules
are compared with the per-note pitch path the same way: a voice that moves
to another key is the first key's voice with the interval as its pitch
offset.

Then the rules a host relies on: glide Off (the minimum) and Poly are the
engine as before, which the default renders of every other engine test
hold to the byte, and which was checked against a build without glide
(engines/README.md); the same output at host blocks of 1, 7 and 64 and
from any instance memory; NaN and infinities clamp as set_param clamps;
and, at the FM-1's 44,118 Hz, a measured glide arrives on time.
"""
import json
import math
import struct
import subprocess
import wave

import pytest

from tests.engine_helpers import RATE, render, renderer  # noqa: F401

GLIDE = ["macro", "macro-heavy", "sixop", "dx7", "shapes"]
NOT_PITCHED = ["drums", "sw-sophie", "test-sine"]

# The host that puts one call on each control block, and a sustained voice
# (deterministic: notes rendered apart are the notes rendered together).
NATIVE = {
    "macro": dict(rate="47872.34", block=12, params=["Model=6", "Timbre=0"]),
    "macro-heavy": dict(rate="47872.34", block=12, params=["Model=4", "Decay=0.8"]),
    "sixop": dict(rate="47872.34", block=16, params=["Patch=40"]),
    "shapes": dict(rate="96000", block=24, params=["Shape=0", "Release=0.7"]),
    "dx7": dict(rate="44118", block=64, params=["Patch=14"]),
}
# Engines whose key change and pitch offset are the same numbers (FM6 moves
# the operators that follow the key in msfa's integer pitch, where a pitch
# offset of the interval is 4 units of 2^24 an octave off, and keeps the
# scaling of the note that started the envelopes).
SAME_PATH = ["macro", "macro-heavy", "sixop", "shapes"]


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def exact(x):
    return f"{f32(x):.9g}"


@pytest.fixture(scope="module")
def listing(renderer):
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True, text=True)
    return {e["id"]: e for e in json.loads(out.stdout)}


def param(listing, engine, name):
    return next(p for p in listing[engine]["params"] if p["name"] == name)


def native_render(renderer, tmp_path, engine, name, notes=(), extra=(), blocks=900):
    """Render at the engine's own rate in control blocks: (WAV bytes, left
    channel as int16). notes: (block, key, velocity, end block)."""
    cfg = NATIVE[engine]
    rate = float(cfg["rate"])
    wav = tmp_path / f"{name}.wav"
    cmd = [str(renderer), "--engine", engine, "--rate", cfg["rate"], "--frames", str(cfg["block"]),
           "--seconds", f"{blocks * cfg['block'] / rate:.9f}", "--out", str(wav)]
    for p in cfg["params"]:
        cmd += ["--param", p]
    for b0, key, vel, b1 in notes:
        cmd += ["--note", f"{at(engine, b0)}:{key}:{vel}:{at(engine, b1) - at(engine, b0):.9f}"]
    cmd += list(extra)
    res = subprocess.run(cmd, check=True, capture_output=True, text=True)
    assert json.loads(res.stdout)["nonfinite"] == 0
    with wave.open(str(wav), "rb") as w:
        raw = w.readframes(w.getnframes())
    left = [int.from_bytes(raw[i:i + 2], "little", signed=True) for i in range(0, len(raw), 4)]
    return wav.read_bytes(), left


def at(engine, block):
    """A time in seconds that fm1-render applies at the start of host block
    `block` (it applies an event once its time is <= the block's start)."""
    cfg = NATIVE[engine]
    if block == 0:
        return 0.0
    return (block * cfg["block"] - 0.5) / float(cfg["rate"])


def t(engine, block):
    return f"{at(engine, block):.9f}"


def smooth_steps(rate, stride):
    """fm1_smooth_steps."""
    hz = int(f32(rate) + 0.5)
    samples = (hz * 2500 + 500000) // 1000000
    return max(1, (samples + stride - 1) // stride)


def glide_offsets(engine, ms, span, start=0, changes=None, native_rate=None):
    """The per-block offsets of a glide of `span` semitones starting at
    block `start` (relative block 0 plays span), as glide.h computes them
    in single precision, ending with the block that plays 0. changes:
    {relative block: new Glide time}, a set_param before that block, which
    ramps over fm1_smooth_steps blocks (fm1_smooth.h)."""
    cfg = NATIVE[engine]
    rate = f32(native_rate or float(cfg["rate"]))
    block_ms = f32(f32(cfg["block"] * 1000.0) / rate)
    value = f32(ms)
    steps = smooth_steps(rate, cfg["block"])
    ramp = None                             # (target, step, left)
    changes = changes or {}
    left, offset, out = 1.0, f32(span), []
    j = 0
    while True:
        if j in changes:                    # set_param, then this block's tick
            target = f32(changes[j])
            if target != value:
                ramp = [target, f32(f32(target - value) / f32(steps)), steps]
        if ramp:
            ramp[2] -= 1
            if ramp[2]:
                v = f32(value + ramp[1])
                if (v > ramp[0]) if ramp[1] > 0 else (v < ramp[0]):
                    v = ramp[0]
                value = v
            else:
                value, ramp = ramp[0], None
        inc = f32(block_ms / value)
        out.append(offset)                  # what block j plays
        if offset == 0.0 and j > 0:
            return out
        left = f32(left - inc)
        offset = 0.0 if not left > 0.0 else f32(f32(span) * left)
        j += 1


def pitch_calls(engine, key, offsets, start):
    extra = []
    for j, o in enumerate(offsets):
        extra += ["--note-pitch-at", f"{t(engine, start + j)}:{key}:{exact(o)}"]
    return extra


def test_parameters(listing):
    """Glide: ms on the LOG law, 1 (Off, the default) to 5,000, SMOOTH and
    MOD, engine-wide (not POLY). Voice Mode: Poly (the default), Mono,
    Legato, LATCH and MOD. On the five pitched engines, after their other
    parameters; the kits and Test Sine have neither."""
    for e in GLIDE:
        names = [p["name"] for p in listing[e]["params"]]
        assert names[-2:] == ["Glide", "Voice Mode"], e
        g, m = param(listing, e, "Glide"), param(listing, e, "Voice Mode")
        assert (g["min"], g["max"], g["def"], g["unit"]) == (1, 5000, 1, "ms"), e
        assert g["flags"] == ["smooth", "mod", "log"] and g["abbr"] == "Glide", e
        assert m["names"] == ["Poly", "Mono", "Legato"] and m["def"] == 0, e
        assert m["flags"] == ["latch", "mod"] and m["abbr"] == "VMode", e
        assert g["page"] == m["page"], e
    assert param(listing, "macro", "Glide")["page"] == 3      # page 4, as on Macro Heavy
    assert param(listing, "macro-heavy", "Glide")["page"] == 3
    for e in NOT_PITCHED:
        assert not {"Glide", "Voice Mode"} & {p["name"] for p in listing[e]["params"]}, e


@pytest.mark.parametrize("engine", GLIDE)
@pytest.mark.parametrize("mode", ["0", "1"])
def test_a_glide_is_its_offsets_on_the_pitch_path(renderer, tmp_path, engine, mode):
    """Poly and Mono, Glide 30 ms: A3 held, then A4 struck while it sounds.
    The A4 voice (in Mono the A3 voice, which A4 takes over and restarts)
    starts on A3's pitch and moves to its own in a straight line in
    semitones: byte for byte the same notes with Glide Off and the glide's
    offsets sent to A4 as per-note pitch offsets, one per control block.
    It arrives within one control block of 30 ms."""
    k1 = 260
    notes = [(0, 57, 100, 700), (k1, 69, 90, 800)]   # A3 let go first: no return to it
    offs = glide_offsets(engine, 30.0, 57 - 69, k1)
    _, glide = native_render(renderer, tmp_path, engine, "glide", notes,
                             ["--param", "Glide=30", "--param", f"Voice Mode={mode}"])
    _, ref = native_render(renderer, tmp_path, engine, "ref", notes,
                           ["--param", f"Voice Mode={mode}"] + pitch_calls(engine, 69, offs, k1))
    assert glide == ref
    _, off = native_render(renderer, tmp_path, engine, "off", notes, ["--param", f"Voice Mode={mode}"])
    assert glide != off and glide[:k1 * NATIVE[engine]["block"]] == off[:k1 * NATIVE[engine]["block"]]
    cfg = NATIVE[engine]
    block_ms = cfg["block"] * 1000.0 / float(cfg["rate"])
    moving = len(offs) - 1                 # blocks off the target
    assert abs(moving * block_ms - 30.0) <= block_ms, (moving, block_ms)
    assert all(b > a for a, b in zip(offs, offs[1:])) and offs[-1] == 0.0   # -12 up to 0


@pytest.mark.parametrize("engine", GLIDE)
@pytest.mark.parametrize("mode", ["1", "2"])
def test_the_return_to_a_held_key_glides(renderer, tmp_path, engine, mode):
    """Mono and Legato, Glide 25 ms: A3 held, A4 played over it (a glide
    up) and let go once there (a glide back down to A3, without
    restarting). Byte for byte Glide Off with both glides' offsets sent as
    per-note pitch offsets: A4's from its note-on, then A3's from the
    note-off, where the voice returns to A3."""
    k1, k2 = 200, 600
    notes = [(0, 57, 100, 900), (k1, 69, 90, k2)]
    calls = (pitch_calls(engine, 69, glide_offsets(engine, 25.0, 57 - 69, k1), k1)
             + pitch_calls(engine, 57, glide_offsets(engine, 25.0, 69 - 57, k2), k2))
    _, glide = native_render(renderer, tmp_path, engine, "glide", notes,
                             ["--param", "Glide=25", "--param", f"Voice Mode={mode}"], blocks=1000)
    _, ref = native_render(renderer, tmp_path, engine, "ref", notes,
                           ["--param", f"Voice Mode={mode}"] + calls, blocks=1000)
    assert glide == ref


@pytest.mark.parametrize("engine", GLIDE)
def test_a_glide_follows_its_time_while_it_runs(renderer, tmp_path, engine):
    """Mono, Glide 200 ms, cut to 40 ms a quarter of the way in: Glide is
    SMOOTH, so the time ramps over 2.5 ms of control blocks and the glide
    covers what is left at the new rate (fm1_smooth.h and glide.h, computed
    here), byte for byte."""
    cfg = NATIVE[engine]
    block_ms = cfg["block"] * 1000.0 / float(cfg["rate"])
    k1 = 100
    cut = int(50.0 / block_ms)
    notes = [(0, 60, 100, 1100), (k1, 67, 90, 1000)]
    offs = glide_offsets(engine, 200.0, 60 - 67, k1, {cut: 40.0})
    _, glide = native_render(renderer, tmp_path, engine, "glide", notes,
                             ["--param", "Glide=200", "--param", "Voice Mode=1",
                              "--param-at", f"{t(engine, k1 + cut)}:Glide=40"], blocks=1200)
    _, ref = native_render(renderer, tmp_path, engine, "ref", notes,
                           ["--param", "Voice Mode=1", "--param-at", f"{t(engine, k1 + cut)}:Glide=40"]
                           + pitch_calls(engine, 67, offs, k1), blocks=1200)
    assert glide == ref
    # three quarters of the way left at 40 ms: about 30 ms more
    assert cut + 28.0 / block_ms < len(offs) <= cut + 33.0 / block_ms + 1


@pytest.mark.parametrize("engine", GLIDE)
def test_what_does_not_glide(renderer, tmp_path, engine):
    """Glide on (500 ms), Poly: a note with no key held, a chord struck in
    one block, and a note after the previous key was let go (its voice
    still releasing) start on their own pitch: the same bytes as Glide Off.
    Glide Off itself is the default, and every other engine test renders it."""
    notes = [(0, 60, 100, 150), (150, 64, 100, 300), (150, 67, 90, 300),
             (450, 55, 100, 600), (620, 62, 80, 800)]
    _, on = native_render(renderer, tmp_path, engine, "on", notes, ["--param", "Glide=500"])
    _, off = native_render(renderer, tmp_path, engine, "off", notes)
    assert on == off


@pytest.mark.parametrize("engine", GLIDE)
def test_a_chord_over_a_held_note_glides_from_it(renderer, tmp_path, engine):
    """Poly: a chord struck while a note is held glides from that note, each
    of its notes on its own (the chord's notes never glide from each other:
    neither has sounded yet), while the held note stays where it is."""
    k1 = 240
    notes = [(0, 60, 100, 800), (k1, 64, 90, 700), (k1, 67, 90, 700)]
    calls = (pitch_calls(engine, 64, glide_offsets(engine, 20.0, 60 - 64, k1), k1)
             + pitch_calls(engine, 67, glide_offsets(engine, 20.0, 60 - 67, k1), k1))
    _, glide = native_render(renderer, tmp_path, engine, "glide", notes, ["--param", "Glide=20"])
    _, ref = native_render(renderer, tmp_path, engine, "ref", notes, calls)
    assert glide == ref


@pytest.mark.parametrize("engine", SAME_PATH)
def test_mono_takes_the_voice_and_returns_to_the_held_key(renderer, tmp_path, engine):
    """Mono, Glide Off: A3 held, A4 struck and let go, then A3 let go. The
    one voice restarts on A4 (as a retrigger of A3's voice with the interval
    as its pitch offset and A4's velocity) and, when A4 is let go, returns
    to A3 without restarting (the offset back to 0): byte for byte."""
    k1, k2 = 200, 450
    mono = [(0, 57, 100, 800), (k1, 69, 80, k2)]
    ref = [(0, 57, 100, 800), (k1, 57, 80, 800)]
    _, a = native_render(renderer, tmp_path, engine, "a", mono, ["--param", "Voice Mode=1"])
    _, b = native_render(renderer, tmp_path, engine, "b", ref,
                         ["--note-pitch-at", f"{t(engine, k1)}:57:12",
                          "--note-pitch-at", f"{t(engine, k2)}:57:0"])
    assert a == b


@pytest.mark.parametrize("engine", SAME_PATH)
def test_legato_moves_the_voice_without_restarting(renderer, tmp_path, engine):
    """Legato, Glide Off: A3 held, A4 played over it and let go. The voice
    changes key without restarting anything and keeps A3's velocity: byte
    for byte A3 alone with the interval as its pitch offset while A4 is
    down. With no key held a Legato note restarts the voice, as Mono's
    does (the reference, in Legato too, has no note over another)."""
    k1, k2, k3 = 200, 450, 900
    legato = [(0, 57, 100, 800), (k1, 69, 60, k2), (k3, 62, 70, 1100)]
    ref = [(0, 57, 100, 800), (k3, 62, 70, 1100)]
    _, a = native_render(renderer, tmp_path, engine, "a", legato, ["--param", "Voice Mode=2"],
                         blocks=1200)
    _, b = native_render(renderer, tmp_path, engine, "b", ref,
                         ["--param", "Voice Mode=2", "--note-pitch-at", f"{t(engine, k1)}:57:12",
                          "--note-pitch-at", f"{t(engine, k2)}:57:0"], blocks=1200)
    assert a == b


def test_fm6_legato_does_not_restart_the_envelopes(renderer, tmp_path):
    """FM6's key change moves the operators that follow the key (msfa's
    integer pitch) and leaves the envelopes running: on a decaying electric
    piano, a Legato note over a held one carries on at the level the voice
    had reached, where Mono strikes it again."""
    notes = [(0, 57, 100, 1400), (700, 64, 100, 1300)]
    level = {}
    for mode in ("1", "2"):
        _, x = native_render(renderer, tmp_path, "dx7", f"m{mode}", notes,
                             ["--param", "Patch=0", "--param", f"Voice Mode={mode}"], blocks=1400)
        f = 700 * 64

        def rms(a, b):
            return math.sqrt(sum(v * v for v in x[a:b]) / (b - a))
        level[mode] = (rms(f - 2000, f), rms(f + 200, f + 2200))
    before, after = level["2"]
    assert 0.5 * before < after < 1.2 * before          # Legato: the decay goes on
    assert level["1"][1] > 1.5 * after                   # Mono: struck again


def period(x, start, n, guess):
    """The period near `guess` samples of x[start:start + n], from the peak
    of its autocorrelation, interpolated."""
    def r(lag):
        return sum(x[i] * x[i + lag] for i in range(start, start + n))
    lags = range(int(guess * 0.9), int(guess * 1.1) + 1)
    best = max(lags, key=r)
    a, b, c = r(best - 1), r(best), r(best + 1)
    return best + 0.5 * (a - c) / (a - 2 * b + c)


def test_fm6_legato_lands_on_the_keys_pitch(renderer, tmp_path):
    """FM6, Legato: after the key change, and after the return to the held
    key, the voice plays the key's pitch, within half a cent of a note
    struck on it."""
    notes = [(0, 57, 100, 1400), (500, 64, 100, 1000)]
    _, x = native_render(renderer, tmp_path, "dx7", "legato", notes,
                         ["--param", "Patch=14", "--param", "Voice Mode=2"], blocks=1400)
    for key, b0 in ((64, 500), (57, 1000)):
        _, y = native_render(renderer, tmp_path, "dx7", f"k{key}", [(0, key, 100, 1400)],
                             ["--param", "Patch=14"], blocks=400)
        guess = 44118 / (440 * 2 ** ((key - 69) / 12))
        moved = period(x, b0 * 64 + 3000, 3000, guess)
        struck = period(y, 3000, 3000, guess)
        assert abs(1200 * math.log2(moved / struck)) < 0.5, (key, moved, struck)


@pytest.mark.parametrize("engine", GLIDE)
def test_the_same_at_any_host_block_and_from_any_memory(renderer, tmp_path, engine):
    """Calls at frames every block size reaches (multiples of 448) give the
    same output at host blocks of 1, 7 and 64, and from instance memory
    filled with 0, 0xA5 or 0xFF: overlapping notes under Poly, then Mono and
    Legato (switched while notes sound), glides of 40 and 120 ms, the time
    turned mid-glide, a return to a held key."""
    def tt(frame):
        return 0.0 if frame == 0 else (frame - 0.5) / RATE
    f = [448 * k for k in range(0, 60, 5)]
    notes = [f"0:57:100:{tt(f[4]):.9f}", f"{tt(f[1]):.9f}:64:90:{tt(f[3]) - tt(f[1]):.9f}",
             f"{tt(f[2]):.9f}:60:80:{tt(f[6]) - tt(f[2]):.9f}",
             f"{tt(f[5]):.9f}:67:100:{tt(f[9]) - tt(f[5]):.9f}",
             f"{tt(f[6]):.9f}:72:70:{tt(f[8]) - tt(f[6]):.9f}",
             f"{tt(f[7]):.9f}:62:110:{tt(f[8]) - tt(f[7]):.9f}"]
    extra = ["--param", "Glide=40",
             "--param-at", f"{tt(f[2] + 448):.9f}:Glide=120",
             "--param-at", f"{tt(f[4]):.9f}:Voice Mode=1",
             "--param-at", f"{tt(f[7]):.9f}:Voice Mode=2",
             "--param-at", f"{tt(f[7] + 896):.9f}:Glide=15"]
    outs = []
    for frames, fill in (("64", "0"), ("7", "0"), ("1", "0"), ("64", "0xA5"), ("7", "0xFF")):
        s, _, wav = render(renderer, tmp_path, engine, params=NATIVE[engine]["params"],
                           notes=notes, seconds=0.6, name=f"b{frames}{fill}",
                           extra=extra + ["--frames", frames, "--fill", fill])
        assert s["nonfinite"] == 0
        outs.append(wav.read_bytes())
    assert all(o == outs[0] for o in outs[1:])


@pytest.mark.parametrize("engine", GLIDE)
def test_nan_and_infinities_clamp(renderer, tmp_path, engine):
    """set_param's clamp: NaN is the default (Glide Off, Poly), +inf the
    maximum (5,000 ms, Legato) and -inf the minimum, for a glide under way
    too. Every render finite."""
    notes = ["0:57:100:0.5", "0.1:64:90:0.3", "0.2:69:80:0.25"]

    def go(name, glide, mode):
        s, _, wav = render(renderer, tmp_path, engine, params=NATIVE[engine]["params"],
                           notes=notes, seconds=0.6, name=name,
                           extra=["--param", "Glide=100", "--param", "Voice Mode=1",
                                  "--param-at", f"0.15:Glide={glide}",
                                  "--param-at", f"0.15:Voice Mode={mode}"])
        assert s["nonfinite"] == 0
        return wav.read_bytes()
    assert go("nan", "nan", "nan") == go("def", "1", "0")
    assert go("inf", "inf", "inf") == go("max", "5000", "2")
    assert go("-inf", "-inf", "-inf") == go("min", "1", "0")


def test_a_glide_arrives_on_time_at_the_fm1_rate(renderer, tmp_path):
    """At 44,118 Hz, through the resampler: Macro's 2-op FM at Timbre 0 is a
    sine; Mono, A4 then A5 with Glide 200 ms. Measured from the output's
    zero crossings, one period at a time: the pitch passes the middle of the
    octave 100 ms after the key, is on a straight line in semitones (within
    0.15 semitone at a quarter and three quarters), and is on A5 (within 3
    cents) from 200 ms, not before, each to within 3 ms. The output follows
    the key by about 1.5 ms: the note lands on the next 12-sample block, and
    the resampler delays it [measured 2026-10-06: the middle at 101.6 ms,
    A5 from 202.3 ms]."""
    on = 0.3
    _, x, _ = render(renderer, tmp_path, "macro",
                     params=["Model=6", "Timbre=0", "Glide=200", "Voice Mode=1"],
                     notes=["0:69:100:0.9", f"{on}:81:100:0.5"], seconds=0.8, name="g")
    rate = RATE
    c = []
    for i in range(int(0.25 * rate), int(0.7 * rate)):
        if x[i - 1] < 0.0 <= x[i]:
            c.append(i - 1 + -x[i - 1] / (x[i] - x[i - 1]))
    track = [((a + b) / 2 / rate - on, 12 * math.log2(rate / (b - a) / 440.0) + 69)
             for a, b in zip(c, c[1:])]

    def semi_at(ms):
        return min(track, key=lambda p: abs(p[0] * 1000 - ms))[1]
    mid = next(tm for tm, s in track if s >= 75.0) * 1000
    assert 100.0 <= mid <= 103.0, mid
    assert abs(semi_at(51.5) - 72.0) < 0.15 and abs(semi_at(151.5) - 78.0) < 0.15
    assert all(abs(s - 81) * 100 < 3 for tm, s in track if 0.203 <= tm <= 0.45)
    assert all(abs(s - 81) * 100 > 3 for tm, s in track if 0.19 <= tm <= 0.199)
