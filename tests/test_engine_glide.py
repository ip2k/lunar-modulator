"""Glide and the voice modes (engines/src/glide.h; engines/README.md, "Glide
and voice modes"): a per-note pitch slew in Macro, Macro Heavy, Six-Op FM,
FM6 and Shapes, with Poly, Mono and Legato, Glide Mode Off, Legato and
Always, and Time Mode Time and Rate.

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

Then the rules a host relies on: Glide Mode Off and Poly (the defaults)
are the engine as before, whatever Glide and Time Mode say, which the default renders of every other engine test
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

# Glide Mode Legato (fingered portamento), which every glide here used until
# Glide Mode came (2026-10-06), and Always (full-time).
LEGATO = ["--param", "Glide Mode=1"]
ALWAYS = ["--param", "Glide Mode=2"]
RATE_MODE = ["--param", "Time Mode=1"]


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
    """Glide: ms on the LOG law, 1 to 5,000, default 100, SMOOTH and MOD,
    engine-wide (not POLY). Voice Mode: Poly (the default), Mono, Legato;
    Glide Mode: Off (the default), Legato, Always; Time Mode: Time (the
    default), Rate; the three LATCH and MOD. On the five pitched engines,
    after their other parameters, the four together on the last page; the
    kits and Test Sine have none of them."""
    four = ["Glide", "Voice Mode", "Glide Mode", "Time Mode"]
    for e in GLIDE:
        names = [p["name"] for p in listing[e]["params"]]
        assert names[-4:] == four, e
        g, m = param(listing, e, "Glide"), param(listing, e, "Voice Mode")
        gm, tm = param(listing, e, "Glide Mode"), param(listing, e, "Time Mode")
        assert (g["min"], g["max"], g["def"], g["unit"]) == (1, 5000, 100, "ms"), e
        assert g["flags"] == ["smooth", "mod", "log"] and g["abbr"] == "Glide", e
        assert m["names"] == ["Poly", "Mono", "Legato"] and m["def"] == 0, e
        assert m["flags"] == ["latch", "mod"] and m["abbr"] == "VMode", e
        assert gm["names"] == ["Off", "Legato", "Always"] and gm["def"] == 0, e
        assert gm["flags"] == ["latch", "mod"] and gm["abbr"] == "GMode", e
        assert tm["names"] == ["Time", "Rate"] and tm["def"] == 0, e
        assert tm["flags"] == ["latch", "mod"] and tm["abbr"] == "TMode", e
        pages = {p["page"] for p in listing[e]["params"]}
        assert {param(listing, e, n)["page"] for n in four} == {max(pages)}, e
        assert sum(p["page"] == max(pages) for p in listing[e]["params"]) == 4, e
    assert param(listing, "macro", "Glide")["page"] == 3      # page 4, as on Macro Heavy
    assert param(listing, "macro-heavy", "Glide")["page"] == 3
    for e in ("shapes", "sixop", "dx7"):                      # page 3
        assert param(listing, e, "Glide")["page"] == 2, e
    for e in NOT_PITCHED:
        assert not set(four) & {p["name"] for p in listing[e]["params"]}, e


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
                             LEGATO + ["--param", "Glide=30", "--param", f"Voice Mode={mode}"])
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
@pytest.mark.parametrize("gmode", ["1", "2"])
def test_the_return_to_a_held_key_glides(renderer, tmp_path, engine, mode, gmode):
    """Mono and Legato, Glide 25 ms, Glide Mode Legato and Always: A3 held,
    A4 played over it (a glide up) and let go once there (a glide back down
    to A3, without restarting). Byte for byte Glide Mode Off with both
    glides' offsets sent as per-note pitch offsets: A4's from its note-on,
    then A3's from the note-off, where the voice returns to A3."""
    k1, k2 = 200, 600
    notes = [(0, 57, 100, 900), (k1, 69, 90, k2)]
    calls = (pitch_calls(engine, 69, glide_offsets(engine, 25.0, 57 - 69, k1), k1)
             + pitch_calls(engine, 57, glide_offsets(engine, 25.0, 69 - 57, k2), k2))
    _, glide = native_render(renderer, tmp_path, engine, "glide", notes,
                             ["--param", "Glide=25", "--param", f"Voice Mode={mode}",
                              "--param", f"Glide Mode={gmode}"], blocks=1000)
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
                             LEGATO + ["--param", "Glide=200", "--param", "Voice Mode=1",
                                       "--param-at", f"{t(engine, k1 + cut)}:Glide=40"], blocks=1200)
    # The reference turns Glide Mode to Legato where the glide's time is cut,
    # so the return to the held key at the end glides in both.
    _, ref = native_render(renderer, tmp_path, engine, "ref", notes,
                           ["--param", "Voice Mode=1", "--param-at", f"{t(engine, k1 + cut)}:Glide=40",
                            "--param-at", f"{t(engine, k1 + cut)}:Glide Mode=1"]
                           + pitch_calls(engine, 67, offs, k1), blocks=1200)
    assert glide == ref
    # three quarters of the way left at 40 ms: about 30 ms more
    assert cut + 28.0 / block_ms < len(offs) <= cut + 33.0 / block_ms + 1


@pytest.mark.parametrize("engine", GLIDE)
def test_what_does_not_glide(renderer, tmp_path, engine):
    """Glide Mode Legato (500 ms), Poly: a note with no key held, a chord
    struck in one block, and a note after the previous key was let go (its
    voice still releasing) start on their own pitch: the same bytes as
    Glide Mode Off. Off itself is the default, and every other engine test
    renders it; under Off neither Glide nor Time Mode changes a byte."""
    notes = [(0, 60, 100, 150), (150, 64, 100, 300), (150, 67, 90, 300),
             (450, 55, 100, 600), (620, 62, 80, 800)]
    _, on = native_render(renderer, tmp_path, engine, "on", notes, LEGATO + ["--param", "Glide=500"])
    _, off = native_render(renderer, tmp_path, engine, "off", notes)
    assert on == off
    over = notes + [(700, 67, 90, 750)]                     # a note over a held one too
    _, plain = native_render(renderer, tmp_path, engine, "plain", over)
    for extra in (["--param", "Glide=1"], ["--param", "Glide=5000", "--param", "Time Mode=1"],
                  ["--param", "Glide Mode=0", "--param", "Voice Mode=0", "--param-at",
                   f"{t(engine, 200)}:Glide=20"]):
        _, x = native_render(renderer, tmp_path, engine, "x", over, extra)
        assert x == plain, extra


@pytest.mark.parametrize("engine", GLIDE)
def test_a_chord_over_a_held_note_glides_from_it(renderer, tmp_path, engine):
    """Poly: a chord struck while a note is held glides from that note, each
    of its notes on its own (the chord's notes never glide from each other:
    neither has sounded yet), while the held note stays where it is."""
    k1 = 240
    notes = [(0, 60, 100, 800), (k1, 64, 90, 700), (k1, 67, 90, 700)]
    calls = (pitch_calls(engine, 64, glide_offsets(engine, 20.0, 60 - 64, k1), k1)
             + pitch_calls(engine, 67, glide_offsets(engine, 20.0, 60 - 67, k1), k1))
    _, glide = native_render(renderer, tmp_path, engine, "glide", notes,
                             LEGATO + ["--param", "Glide=20"])
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
    turned mid-glide, a return to a held key, Time Mode Rate and back,
    Glide Mode Always, then Poly again under Always."""
    def tt(frame):
        return 0.0 if frame == 0 else (frame - 0.5) / RATE
    f = [448 * k for k in range(0, 60, 5)]
    notes = [f"0:57:100:{tt(f[4]):.9f}", f"{tt(f[1]):.9f}:64:90:{tt(f[3]) - tt(f[1]):.9f}",
             f"{tt(f[2]):.9f}:60:80:{tt(f[6]) - tt(f[2]):.9f}",
             f"{tt(f[5]):.9f}:67:100:{tt(f[9]) - tt(f[5]):.9f}",
             f"{tt(f[6]):.9f}:72:70:{tt(f[8]) - tt(f[6]):.9f}",
             f"{tt(f[7]):.9f}:62:110:{tt(f[8]) - tt(f[7]):.9f}"]
    extra = LEGATO + ["--param", "Glide=40",
                      "--param-at", f"{tt(f[2] + 448):.9f}:Glide=120",
                      "--param-at", f"{tt(f[3]):.9f}:Time Mode=1",
                      "--param-at", f"{tt(f[4]):.9f}:Voice Mode=1",
                      "--param-at", f"{tt(f[5] + 448):.9f}:Glide Mode=2",
                      "--param-at", f"{tt(f[7]):.9f}:Voice Mode=2",
                      "--param-at", f"{tt(f[7] + 896):.9f}:Glide=15",
                      "--param-at", f"{tt(f[8]):.9f}:Time Mode=0",
                      "--param-at", f"{tt(f[9]):.9f}:Voice Mode=0"]
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
    """set_param's clamp: NaN is the default (Glide 100 ms, Poly, Glide
    Mode Off, Time Mode Time), +inf the maximum (5,000 ms, Legato, Always,
    Rate) and -inf the minimum (1 ms, Poly, Off, Time), for a glide under
    way too. Every render finite."""
    notes = ["0:57:100:0.5", "0.1:64:90:0.3", "0.2:69:80:0.25", "0.3:52:100:0.2"]

    def go(name, glide, mode, gmode, tmode):
        s, _, wav = render(renderer, tmp_path, engine, params=NATIVE[engine]["params"],
                           notes=notes, seconds=0.6, name=name,
                           extra=["--param", "Glide=150", "--param", "Voice Mode=1",
                                  "--param", "Glide Mode=1",
                                  "--param-at", f"0.15:Glide={glide}",
                                  "--param-at", f"0.15:Voice Mode={mode}",
                                  "--param-at", f"0.15:Glide Mode={gmode}",
                                  "--param-at", f"0.15:Time Mode={tmode}"])
        assert s["nonfinite"] == 0
        return wav.read_bytes()
    assert go("nan", "nan", "nan", "nan", "nan") == go("def", "100", "0", "0", "0")
    assert go("inf", "inf", "inf", "inf", "inf") == go("max", "5000", "2", "2", "1")
    assert go("-inf", "-inf", "-inf", "-inf", "-inf") == go("min", "1", "0", "0", "0")


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
                     params=["Model=6", "Timbre=0", "Glide=200", "Voice Mode=1", "Glide Mode=1"],
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


# Review (2026-10-06): the cases a player or a host reaches that the tests
# above do not, each exact unless said.

VOICES = {"macro": 12, "macro-heavy": 4, "sixop": 8, "shapes": 12, "dx7": 12}


@pytest.mark.parametrize("engine", SAME_PATH)
def test_a_stack_of_three_keys(renderer, tmp_path, engine):
    """Mono and Legato, Glide Off: A3 held, C4 over it, E4 over both; C4 let
    go while E4 sounds moves nothing, and letting go of E4 then returns to
    A3, the newest key still held, not to C4. Mono restarts on C4 and E4
    (A3's voice retriggered with the interval as its pitch offset); Legato
    restarts nothing."""
    notes = [(0, 57, 100, 900), (200, 60, 80, 500), (400, 64, 70, 700)]
    moves = ["--note-pitch-at", f"{t(engine, 200)}:57:3", "--note-pitch-at", f"{t(engine, 400)}:57:7",
             "--note-pitch-at", f"{t(engine, 700)}:57:0"]
    _, mono = native_render(renderer, tmp_path, engine, "mono", notes, ["--param", "Voice Mode=1"],
                            blocks=1000)
    _, mono_ref = native_render(renderer, tmp_path, engine, "mono-ref",
                                [(0, 57, 100, 900), (200, 57, 80, 900), (400, 57, 70, 900)], moves,
                                blocks=1000)
    assert mono == mono_ref
    _, leg = native_render(renderer, tmp_path, engine, "leg", notes, ["--param", "Voice Mode=2"],
                           blocks=1000)
    _, leg_ref = native_render(renderer, tmp_path, engine, "leg-ref", [(0, 57, 100, 900)],
                               ["--param", "Voice Mode=2"] + moves, blocks=1000)
    assert leg == leg_ref


@pytest.mark.parametrize("engine", GLIDE)
@pytest.mark.parametrize("mode", ["1", "2"])
def test_a_glide_cut_short_by_another_key_under_bends(renderer, tmp_path, engine, mode):
    """Mono and Legato, Glide 60 ms, the bend moving: A3 held, C4 over it,
    and E4 a third of the way into C4's glide, which starts from where that
    glide had reached (not from C4); C4 let go, then E4, which returns to
    A3 from E4. Byte for byte the glides' offsets on the pitch path."""
    n = len(glide_offsets(engine, 60.0, 57 - 60)) - 1
    m = n // 3
    kb, kc, kbu, kcu = 200, 200 + m, 200 + m + 2 * n, 200 + m + 4 * n
    end = kcu + 2 * n
    notes = [(0, 57, 100, end), (kb, 60, 80, kbu), (kc, 64, 70, kcu)]
    off_b = glide_offsets(engine, 60.0, 57 - 60)
    off_c = glide_offsets(engine, 60.0, f32(f32(60 + off_b[m]) - 64))
    off_a = glide_offsets(engine, 60.0, 64 - 57)
    assert 0.0 < 60 + off_b[m] - 57 < 3.0          # E4 starts between A3 and C4
    bends = ["--bend", f"{t(engine, kb + 5)}:0.37", "--bend", f"{t(engine, kcu + 3)}:-1.25"]
    _, glide = native_render(renderer, tmp_path, engine, "glide", notes,
                             LEGATO + ["--param", "Glide=60", "--param", f"Voice Mode={mode}"] + bends,
                             blocks=end + 50)
    calls = (pitch_calls(engine, 60, off_b[:m], kb) + pitch_calls(engine, 64, off_c, kc)
             + pitch_calls(engine, 57, off_a, kcu))
    _, ref = native_render(renderer, tmp_path, engine, "ref", notes,
                           ["--param", f"Voice Mode={mode}"] + bends + calls, blocks=end + 50)
    assert glide == ref


@pytest.mark.parametrize("engine", GLIDE)
def test_the_shortest_glide(renderer, tmp_path, engine):
    """Glide at its minimum, 1 ms, under Legato glides (it was Off until
    Glide Mode came, 2026-10-06): a control block or a few play the held
    note's pitch (FM6's 1.45 ms block: one), then the note's own, as glide.h
    computes, byte for byte. Glide Mode Off never glides, whatever the
    time."""
    notes = [(0, 57, 100, 500), (200, 69, 90, 500)]
    offs = glide_offsets(engine, 1.0, 57 - 69)
    assert offs[0] == -12.0 and offs[-1] == 0.0 and len(offs) <= 6
    _, glide = native_render(renderer, tmp_path, engine, "glide", notes,
                             LEGATO + ["--param", "Glide=1"], blocks=500)
    _, ref = native_render(renderer, tmp_path, engine, "ref", notes, pitch_calls(engine, 69, offs, 200),
                           blocks=500)
    _, off = native_render(renderer, tmp_path, engine, "off", notes,
                           ["--param", "Glide=1", "--param", "Glide Mode=0"], blocks=500)
    _, plain = native_render(renderer, tmp_path, engine, "plain", notes, blocks=500)
    assert glide == ref and off == plain and glide != plain


@pytest.mark.parametrize("engine", GLIDE)
def test_a_switch_to_mono_never_doubles_a_key(renderer, tmp_path, engine):
    """A chord held in Poly, then Voice Mode switched to Mono (and to
    Legato): letting go of its newest note must not move that voice onto a
    key another voice already sounds (two voices on one key); every note
    ends as in Poly, byte for byte."""
    chord = [(0, 60, 100, 700), (0, 64, 100, 500), (0, 67, 100, 300)]
    _, poly = native_render(renderer, tmp_path, engine, "poly", chord)
    for mode in ("1", "2"):
        _, switched = native_render(renderer, tmp_path, engine, f"m{mode}", chord,
                                    LEGATO + ["--param", "Glide=30",
                                              "--param-at", f"{t(engine, 200)}:Voice Mode={mode}"])
        assert switched == poly, mode


@pytest.mark.parametrize("engine", SAME_PATH)
def test_more_keys_held_than_the_list_keeps(renderer, tmp_path, engine):
    """Mono, Glide Off, twenty keys pressed one after another and let go
    newest first: each release returns the voice to the key before it,
    down to the oldest of the sixteen the list keeps, whose release ends the
    note although four older keys are still down (glide.h: the oldest are
    dropped); letting go of those four changes nothing, and nothing sticks.
    Byte for byte the first key retriggered with each interval as its
    pitch offset, every one of its notes ending at that release."""
    keys = list(range(40, 60))
    on = {k: 10 + 10 * i for i, k in enumerate(keys)}
    off = {k: 300 + 10 * (59 - k) for k in keys}          # 59 first, at 300
    notes = [(on[k], k, 100, off[k]) for k in keys]
    _, mono = native_render(renderer, tmp_path, engine, "mono", notes, ["--param", "Voice Mode=1"],
                            blocks=1400)
    end = off[44]                                          # the sixteenth newest key
    ref_notes = [(on[k], 40, 100, end) for k in keys]
    moves = []
    for k in keys[1:]:
        moves += ["--note-pitch-at", f"{t(engine, on[k])}:40:{k - 40}"]
    for k in range(59, 44, -1):                            # back to k - 1
        moves += ["--note-pitch-at", f"{t(engine, off[k])}:40:{k - 1 - 40}"]
    _, ref = native_render(renderer, tmp_path, engine, "ref", ref_notes, moves, blocks=1400)
    assert mono == ref                 # every reference note ends at the sixteenth's release


@pytest.mark.parametrize("engine", GLIDE)
def test_a_velocity_zero_note_on_is_the_note_off(renderer, tmp_path, engine):
    """Mono with Glide 25 ms: a note-on at velocity 0 for the sounding key
    (MIDI's running-status note-off) returns the voice to the held key,
    gliding, as the note-off does; the later note-off of a key no longer
    down changes nothing."""
    k1, k2 = 200, 500
    _, zero = native_render(renderer, tmp_path, engine, "zero",
                            [(0, 57, 100, 900), (k1, 69, 90, 800), (k2, 69, 0, 600)],
                            LEGATO + ["--param", "Glide=25", "--param", "Voice Mode=1"])
    _, real = native_render(renderer, tmp_path, engine, "real",
                            [(0, 57, 100, 900), (k1, 69, 90, k2)],
                            LEGATO + ["--param", "Glide=25", "--param", "Voice Mode=1"])
    assert zero == real


@pytest.mark.parametrize("engine", SAME_PATH + ["dx7"])
def test_legato_on_the_key_already_sounding(renderer, tmp_path, engine):
    """Legato: a second note-on for the key already down (a host that sends
    two) restarts nothing, and the first note-off of that key ends the note:
    the same bytes as the key played once until then."""
    _, twice = native_render(renderer, tmp_path, engine, "twice",
                             [(0, 57, 100, 800), (200, 57, 60, 500)],
                             LEGATO + ["--param", "Glide=40", "--param", "Voice Mode=2"])
    _, once = native_render(renderer, tmp_path, engine, "once", [(0, 57, 100, 500)],
                            LEGATO + ["--param", "Glide=40", "--param", "Voice Mode=2"])
    assert twice == once


def test_poly_glide_survives_a_steal(renderer, tmp_path):
    """Macro Heavy has four voices: in Poly with Glide 20 ms, five keys held
    one after another each glide from the one before, and the fifth takes
    the first key's voice: byte for byte the glides' offsets on the pitch
    path, steal and all."""
    e = "macro-heavy"
    keys = [48, 52, 55, 59, 62]
    notes = [(100 + 150 * i, k, 100, 1100) for i, k in enumerate(keys)]
    calls = []
    for i in range(1, 5):
        calls += pitch_calls(e, keys[i], glide_offsets(e, 20.0, keys[i - 1] - keys[i]),
                             100 + 150 * i)
    _, glide = native_render(renderer, tmp_path, e, "glide", notes,
                             LEGATO + ["--param", "Glide=20"], blocks=1200)
    _, ref = native_render(renderer, tmp_path, e, "ref", notes, calls, blocks=1200)
    assert glide == ref and VOICES[e] < len(keys)


@pytest.mark.parametrize("mode", ["0", "1", "2"])
def test_fm6_keys_above_127_end(renderer, tmp_path, mode):
    """FM6 clamps a key above 127 at note-on: its note-off must clamp too,
    or the voice (and in Mono and Legato the held keys, to which a later
    release returns) keep a key no note-off can end. Key 200 plays and ends
    as key 127, alone and over a held key."""
    for name, notes in (("alone", [(0, 200, 100, 300)]),
                        ("over", [(0, 60, 100, 600), (100, 200, 100, 300)])):
        _, high = native_render(renderer, tmp_path, "dx7", f"{name}-high", notes,
                                ["--param", f"Voice Mode={mode}"], blocks=1500)
        _, top = native_render(renderer, tmp_path, "dx7", f"{name}-127",
                               [(b0, min(k, 127), v, b1) for b0, k, v, b1 in notes],
                               ["--param", f"Voice Mode={mode}"], blocks=1500)
        assert high == top, name
        assert not any(high[-100 * 64:]), name


def test_a_five_second_glide_arrives_on_time(renderer, tmp_path):
    """The longest glide, 5,000 ms, is 19,949 control blocks of Macro's
    12-sample block in single precision, each taking 1/19,949th or so off
    the share still to go: measured on Macro's sine at 44,118 Hz (Mono, A4
    to A5), the middle of the octave comes 2,500 ms after the key and A5 at
    5,000 ms, each within 5 ms, and the path is a straight line in
    semitones (within 0.05 semitone at a quarter and three quarters)."""
    on = 0.2
    _, x, _ = render(renderer, tmp_path, "macro",
                     params=["Model=6", "Timbre=0", "Glide=5000", "Voice Mode=1", "Glide Mode=1"],
                     notes=["0:69:100:5.6", f"{on}:81:100:5.3"], seconds=5.5, name="g5")
    rate = RATE
    c = []
    for i in range(int(0.15 * rate), int(5.45 * rate)):
        if x[i - 1] < 0.0 <= x[i]:
            c.append(i - 1 + -x[i - 1] / (x[i] - x[i - 1]))
    track = [((a + b) / 2 / rate - on, 12 * math.log2(rate / (b - a) / 440.0) + 69)
             for a, b in zip(c, c[1:])]

    def semi_at(ms):
        near = [s for tm, s in track if abs(tm * 1000 - ms) < 5]
        return sum(near) / len(near)
    mid = next(tm for tm, s in track if tm > 0 and s >= 75.0) * 1000
    assert abs(mid - 2501.5) <= 5.0, mid
    assert abs(semi_at(1251.5) - 72.0) < 0.05 and abs(semi_at(3751.5) - 78.0) < 0.05
    arrive = next(tm for tm, s in track if tm > 0 and abs(s - 81) * 100 < 1) * 1000
    assert abs(arrive - 5001.5) <= 5.0, arrive


# Glide Mode and Time Mode (owner's decisions, 2026-10-06): Off, Legato and
# Always; constant time and constant rate. Exact unless said.

def rate_offsets(engine, ms, span, native_rate=None):
    """The per-block offsets of a Rate glide of `span` semitones at `ms` an
    octave, as glide.h computes them in single precision: each block moves
    the offset 12 x (block_ms / ms) semitones toward 0, and the block that
    would reach or pass 0 plays 0, which ends it."""
    cfg = NATIVE[engine]
    rate = f32(native_rate or float(cfg["rate"]))
    block_ms = f32(f32(cfg["block"] * 1000.0) / rate)
    d = f32(f32(block_ms / f32(ms)) * 12.0)
    offset, out = f32(span), []
    while True:
        out.append(offset)
        if offset == 0.0 and len(out) > 1:
            return out
        if span > 0:
            offset = f32(offset - d)
            offset = offset if offset > 0.0 else 0.0
        else:
            offset = f32(offset + d)
            offset = offset if offset < 0.0 else 0.0


@pytest.mark.parametrize("engine", GLIDE)
@pytest.mark.parametrize("mode", ["0", "1"])
def test_always_glides_from_the_last_note(renderer, tmp_path, engine, mode):
    """Always, Poly and Mono, Glide 30 ms: the first note starts on its own
    pitch; A4, struck after A3 was let go (no key held), glides from A3;
    after a long rest, in which the voice may have ended, D4 glides from
    A4; and a chord of two struck together glides from D4, each note on its
    own (never from each other). Byte for byte the offsets on the pitch
    path; Legato, with no key held, glides none of them."""
    k1, k2, k3 = 150, 500, 650
    notes = [(0, 57, 100, 100), (k1, 69, 90, 300), (k2, 62, 80, k2 + 30),
             (k3, 64, 90, k3 + 150), (k3, 67, 90, k3 + 150)]
    if mode == "1":                          # Mono: one voice, so no chord
        notes = notes[:-1]
    calls = (pitch_calls(engine, 69, glide_offsets(engine, 30.0, 57 - 69), k1)
             + pitch_calls(engine, 62, glide_offsets(engine, 30.0, 69 - 62), k2)
             + pitch_calls(engine, 64, glide_offsets(engine, 30.0, 62 - 64), k3))
    if mode == "0":
        calls += pitch_calls(engine, 67, glide_offsets(engine, 30.0, 62 - 67), k3)
    vm = ["--param", f"Voice Mode={mode}"]
    _, glide = native_render(renderer, tmp_path, engine, "always", notes,
                             ALWAYS + vm + ["--param", "Glide=30"], blocks=900)
    _, ref = native_render(renderer, tmp_path, engine, "ref", notes, vm + calls, blocks=900)
    assert glide == ref
    _, legato = native_render(renderer, tmp_path, engine, "legato", notes,
                              LEGATO + vm + ["--param", "Glide=30"], blocks=900)
    _, plain = native_render(renderer, tmp_path, engine, "plain", notes, vm, blocks=900)
    assert legato == plain and glide != plain


@pytest.mark.parametrize("engine", GLIDE)
def test_always_glides_from_where_a_glide_had_reached(renderer, tmp_path, engine):
    """Always, Poly, Glide 80 ms: A3, then A4 (gliding up from A3, and let
    go at once), then C4 a quarter of the way into A4's glide: C4 starts
    from the pitch A4 had reached, not from A4's key, while A4 rings on and
    finishes its own glide."""
    n = len(glide_offsets(engine, 80.0, 57 - 69)) - 1
    m = n // 4
    k1, k2 = 100, 100 + m
    notes = [(0, 57, 100, 50), (k1, 69, 90, k1 + 2), (k2, 60, 80, k2 + 200)]
    off_a4 = glide_offsets(engine, 80.0, 57 - 69)
    start = f32(f32(69 + off_a4[m]) - 60)
    calls = (pitch_calls(engine, 69, off_a4, k1)
             + pitch_calls(engine, 60, glide_offsets(engine, 80.0, start), k2))
    _, glide = native_render(renderer, tmp_path, engine, "glide", notes,
                             ALWAYS + ["--param", "Glide=80"], blocks=700)
    _, ref = native_render(renderer, tmp_path, engine, "ref", notes, calls, blocks=700)
    assert 57 < 69 + off_a4[m] < 69
    assert glide == ref


@pytest.mark.parametrize("engine", GLIDE)
@pytest.mark.parametrize("gmode", ["1", "2"])
def test_rate_takes_the_time_per_octave(renderer, tmp_path, engine, gmode):
    """Time Mode Rate, Glide 40 ms: Glide is the time an octave takes, so an
    octave up takes 40 ms, two octaves down 80 ms and a fifth up 23 ms or
    so, each moving the same number of semitones a block (glide.h's
    arithmetic, computed here), byte for byte on the pitch path, under
    Legato and Always alike (overlapping notes, so each glides from the one
    before under both)."""
    k1, k2, k3 = 150, 450, 800
    notes = [(0, 60, 100, k1 + 10), (k1, 72, 90, k2 + 10), (k2, 48, 90, k3 + 10), (k3, 55, 90, 950)]
    calls = (pitch_calls(engine, 72, rate_offsets(engine, 40.0, 60 - 72), k1)
             + pitch_calls(engine, 48, rate_offsets(engine, 40.0, 72 - 48), k2)
             + pitch_calls(engine, 55, rate_offsets(engine, 40.0, 48 - 55), k3))
    _, glide = native_render(renderer, tmp_path, engine, "rate", notes,
                             RATE_MODE + ["--param", f"Glide Mode={gmode}", "--param", "Glide=40"],
                             blocks=1000)
    _, ref = native_render(renderer, tmp_path, engine, "ref", notes, calls, blocks=1000)
    assert glide == ref
    cfg = NATIVE[engine]
    block_ms = cfg["block"] * 1000.0 / float(cfg["rate"])
    for span, ms in ((-12, 40.0), (24, 80.0), (-7, 40.0 * 7 / 12)):
        blocks = len(rate_offsets(engine, 40.0, span)) - 1
        assert abs(blocks * block_ms - ms) <= block_ms, (span, blocks * block_ms, ms)


@pytest.mark.parametrize("engine", GLIDE)
def test_the_switches_are_read_when_a_glide_starts(renderer, tmp_path, engine):
    """Glide Mode and Time Mode are LATCH: switching Glide Mode to Off, or
    Time Mode to Rate, during a glide lets that glide finish as it began
    (Legato, constant time, 60 ms), and the next note follows the new
    setting: under Off it does not glide, and switched back to Legato and
    Rate the next one glides at a constant rate."""
    k1, k2, k3 = 100, 400, 700
    notes = [(0, 57, 100, 1000), (k1, 69, 90, 350), (k2, 64, 90, 650), (k3, 45, 80, 900)]
    mid = k1 + 20
    extra = LEGATO + ["--param", "Glide=60", "--param-at", f"{t(engine, mid)}:Glide Mode=0",
                      "--param-at", f"{t(engine, mid)}:Time Mode=1",
                      "--param-at", f"{t(engine, k3 - 10)}:Glide Mode=1"]
    calls = (pitch_calls(engine, 69, glide_offsets(engine, 60.0, 57 - 69), k1)
             + pitch_calls(engine, 45, rate_offsets(engine, 60.0, 57 - 45), k3))
    _, glide = native_render(renderer, tmp_path, engine, "glide", notes, extra, blocks=1100)
    _, ref = native_render(renderer, tmp_path, engine, "ref", notes, calls, blocks=1100)
    assert glide == ref


def test_rate_arrives_on_time_at_the_fm1_rate(renderer, tmp_path):
    """At 44,118 Hz, through the resampler, Macro's sine, Mono, Rate at
    100 ms an octave: A3 to A5, two octaves, passes A4 100 ms after the key
    and is on A5 (within 3 cents) from 200 ms, each within 3 ms (the output
    follows the key by about 1.5 ms, as for a constant-time glide)."""
    on = 0.3
    _, x, _ = render(renderer, tmp_path, "macro",
                     params=["Model=6", "Timbre=0", "Glide=100", "Voice Mode=1", "Glide Mode=1",
                             "Time Mode=1"],
                     notes=["0:57:100:0.9", f"{on}:81:100:0.5"], seconds=0.8, name="r")
    rate = RATE
    c = []
    for i in range(int(0.25 * rate), int(0.7 * rate)):
        if x[i - 1] < 0.0 <= x[i]:
            c.append(i - 1 + -x[i - 1] / (x[i] - x[i - 1]))
    track = [((a + b) / 2 / rate - on, 12 * math.log2(rate / (b - a) / 440.0) + 69)
             for a, b in zip(c, c[1:])]
    mid = next(tm for tm, s in track if tm > 0 and s >= 69.0) * 1000
    assert 100.0 <= mid <= 103.0, mid
    arrive = next(tm for tm, s in track if tm > 0 and abs(s - 81) * 100 < 3) * 1000
    assert 200.0 <= arrive <= 203.5, arrive
