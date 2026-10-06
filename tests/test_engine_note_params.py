"""Per-note offsets (engine API v2, set_param_note in
engines/include/fm1_engine.h; engines/README.md, "Per-note offsets"): a
host moves one sounding note's POLY parameters and pitch without touching
the other notes.

The renderer scripts them with --note-param-at T:KEY:NAME=OFFSET and
--note-pitch-at T:KEY:SEMITONES, applied after the note-ons of the block, as
a host sends a new note's offsets right after its note-on.

Most checks are exact: for a note sounding alone, an offset is the same as
moving the parameter's base by that much (and a pitch offset the same as a
pitch bend), byte for byte, because the voice computes its values with the
engine's own code. Where two notes sound, the offset on one leaves the other
as it was: the two-note render is the sum of the two notes rendered apart.

SMOOTH (docs/15 S7b, engines/README.md "SMOOTH"): a base change while a
voice sounds ramps over 2.5 ms, and a voice plays the ramped base plus its
offset; an offset itself applies at the next internal block, unramped. So an
offset is compared with a base change only where no ramp runs (a base set
before the note), and mid-note with other offsets or with a base that ramps
under the offset just as it ramps alone.
"""
import json
import math
import struct
import subprocess
import wave

import pytest

from tests.engine_helpers import GPL_MODS, RATE, cents, pitch_hz, render, renderer  # noqa: F401

PER_NOTE = ["macro", "macro-heavy", "shapes", "sixop", "dx7"]
# Drums takes per-note offsets too, on its pads' notes only (36-51), which
# the pitched scripts here do not play: tests/test_engine_drums.py checks it.
PER_NOTE_KITS = ["drums"]
# Acid Bass (a GPL module) takes them on its one voice, which moves from key
# to key: tests/test_engine_acid_bass.py checks it.
PER_NOTE_MONO = ["acid-bass"] if GPL_MODS else []
# Felucca's engines (GPL modules) take them on their voices' own values; a
# voice's phases and noise are its slot's, so two notes are not the two
# played apart: tests/test_engine_felucca.py checks them on lone notes.
PER_NOTE_FELUCCA = ["drawbar", "trio", "phase-bend"] if GPL_MODS else []

# A sustained, deterministic voice per engine (no shared random numbers, so
# notes rendered apart are the notes rendered together), and a parameter
# whose offset is loud.
TONE = {
    "macro": dict(params=["Model=0", "Decay=0.8"], loud="Timbre"),
    "macro-heavy": dict(params=["Model=4", "Decay=0.8"], loud="Timbre"),
    "shapes": dict(params=["Shape=0", "Release=0.7"], loud="Timbre"),
    "sixop": dict(params=["Patch=40"], loud="Brightness"),
    "dx7": dict(params=["Patch=14"], loud="Brightness"),   # BRASS: held, no LFO depth
}


@pytest.fixture(scope="module")
def listing(renderer):
    out = subprocess.run([str(renderer), "--list"], check=True, capture_output=True, text=True)
    return {e["id"]: e for e in json.loads(out.stdout)}


def poly(listing, engine):
    return [p for p in listing[engine]["params"] if "poly" in p["flags"]]


def offset_for(p, share=0.3, base=None):
    """An offset that moves p's base (its default unless given) by share of
    its range, staying inside it."""
    span = share * (p["max"] - p["min"])
    base = p["def"] if base is None else base
    return span if base + span <= p["max"] else -span


def base_of(engine, p):
    """p's base under TONE[engine]'s parameters."""
    for kv in TONE[engine]["params"]:
        name, value = kv.split("=")
        if name == p["name"]:
            return float(value)
    return p["def"]


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def moved(base, offset):
    """base + offset as the engine adds them, in float, both parsed as the
    renderer parses them; printed so that it parses back to that float."""
    return f"{f32(f32(float(f'{base:.6g}')) + f32(float(f'{offset:.6g}'))):.9g}"


def f32_add(a, b):
    return f32(f32(a) + f32(b))


def exact(x):
    """x as text that parses back to the same float."""
    return f"{f32(x):.9g}"


def run(renderer, tmp_path, name, engine, params=(), notes=(), extra=(), seconds=0.7):
    """(summary, WAV bytes, left channel as int16)."""
    s, _, wav = render(renderer, tmp_path, engine, params=list(params), notes=list(notes),
                       seconds=seconds, name=name, extra=list(extra))
    with wave.open(str(wav), "rb") as w:
        raw = w.readframes(w.getnframes())
    left = [int.from_bytes(raw[i:i + 2], "little", signed=True) for i in range(0, len(raw), 4)]
    assert s["nonfinite"] == 0
    return s, wav.read_bytes(), left


def at(name, value):
    return f"{name}={value:.6g}"


def test_which_engines_take_per_note_offsets(listing):
    """Sophie keeps its voices inside the module, out of the shim's reach;
    effects have no notes; Test Sine stays the engine without them."""
    assert sorted(e for e, v in listing.items() if v["per_note"]) == \
        sorted(PER_NOTE + PER_NOTE_KITS + PER_NOTE_MONO + PER_NOTE_FELUCCA)
    assert [p["name"] for p in poly(listing, "sixop")] == ["Brightness", "Envelope", "Volume"]
    assert [p["name"] for p in poly(listing, "dx7")] == ["Brightness", "Env Time", "Feedback",
                                                         "Volume"]
    assert [p["name"] for p in poly(listing, "shapes")] == \
        ["Timbre", "Color", "Attack", "Release", "Volume"]
    for e in ("macro", "macro-heavy"):   # every FLOAT but Glide, which is engine-wide
        assert poly(listing, e) == [p for p in listing[e]["params"]
                                    if p["type"] == 0 and p["name"] != "Glide"]
    for e in PER_NOTE:                   # glide.h: a glide is between notes, not of one
        assert "poly" not in next(p for p in listing[e]["params"] if p["name"] == "Glide")["flags"]


def test_renderer_refuses_what_an_engine_cannot_take(renderer, tmp_path):
    def rc(*args):
        return subprocess.run([str(renderer), *args, "--seconds", "0.05",
                               "--out", str(tmp_path / "x.wav")], capture_output=True,
                              text=True)
    r = rc("--engine", "sw-sophie", "--note-pitch-at", "0:60:2")
    assert r.returncode == 1 and "no per-note offsets" in r.stderr
    r = rc("--engine", "macro", "--note-param-at", "0:60:Model=1")
    assert r.returncode == 1 and "not POLY" in r.stderr
    r = rc("--engine", "macro", "--note-param-at", "0:128:Timbre=1")
    assert r.returncode == 2
    r = rc("--note-pitch-at", "0:60:2")
    assert r.returncode == 2


@pytest.mark.parametrize("engine", PER_NOTE)
def test_zero_offsets_are_a_no_op(renderer, tmp_path, listing, engine):
    """0 (and -0) on every POLY parameter and the pitch, on every note, at
    the note-on and while the notes sound, renders what no call renders."""
    notes = [f"{0.02 * i:.2f}:{48 + 3 * i}:{70 + 4 * i}:0.3" for i in range(6)]
    extra = []
    for i in range(6):
        key = 48 + 3 * i
        for t in (0.02 * i, 0.25):
            for p in poly(listing, engine):
                extra += ["--note-param-at", f"{t:.2f}:{key}:{p['name']}={'-0' if i % 2 else '0'}"]
            extra += ["--note-pitch-at", f"{t:.2f}:{key}:0"]
    _, plain, _ = run(renderer, tmp_path, "plain", engine, TONE[engine]["params"], notes)
    _, zero, _ = run(renderer, tmp_path, "zero", engine, TONE[engine]["params"], notes, extra)
    assert zero == plain


@pytest.mark.parametrize("engine", PER_NOTE)
def test_an_offset_on_a_lone_note_is_a_base_change(renderer, tmp_path, listing, engine):
    """For a note sounding alone, each POLY parameter's offset from the
    note-on is the base moved by as much, byte for byte (a base set before
    the note applies at once). Mid-note an offset applies at the next
    internal block, unramped, where a base change would ramp, so there it is
    compared with offsets: a later offset replaces the first, and 0 puts the
    base back, the same as those moves sent against a base that already
    holds the first offset. Offsets of a quarter and an eighth of the range
    keep every sum exact in float (checked)."""
    base = TONE[engine]["params"]
    note = ["0:60:100:0.35"]
    for p in poly(listing, engine):
        b0 = base_of(engine, p)
        span = p["max"] - p["min"]
        sign = 1 if b0 + span / 4 <= p["max"] else -1
        x, y = sign * span / 4, sign * span / 8
        assert f32_add(f32_add(b0, x), y - x) == f32_add(b0, y), p["name"]
        assert f32_add(f32_add(b0, x), -x) == f32(b0), p["name"]
        _, a, _ = run(renderer, tmp_path, "a", engine, base, note,
                      ["--note-param-at", f"0:60:{p['name']}={exact(x)}",
                       "--note-param-at", f"0.2:60:{p['name']}={exact(y)}",
                       "--note-param-at", f"0.5:60:{p['name']}=0"])
        _, b, _ = run(renderer, tmp_path, "b", engine, base, note,
                      ["--param-at", f"0:{p['name']}={moved(b0, x)}",
                       "--note-param-at", f"0.2:60:{p['name']}={exact(y - x)}",
                       "--note-param-at", f"0.5:60:{p['name']}={exact(-x)}"])
        assert a == b, p["name"]


@pytest.mark.parametrize("engine", PER_NOTE)
def test_a_base_that_moves_keeps_the_offset_on_top(renderer, tmp_path, listing, engine):
    """set_param under an offset moves the sum, clamped as set_param clamps:
    for a lone note, the base at 30 % of the range with an offset of half
    the range is the base at their sum, byte for byte, and the base at 80 %
    with the same offset (the sum past the maximum) is the base at the
    maximum. The bases are set before the note, so no ramp runs; a base
    that moves under a sounding offset is the next test."""
    base = TONE[engine]["params"]
    note = ["0:60:100:0.45"]
    for p in poly(listing, engine):
        span = p["max"] - p["min"]
        x = 0.5 * span
        for share, want in ((0.3, None), (0.8, p["max"])):
            b0 = p["min"] + share * span
            _, a, _ = run(renderer, tmp_path, "a", engine, base, note,
                          ["--param-at", f"0:{at(p['name'], b0)}",
                           "--note-param-at", f"0:60:{at(p['name'], x)}"])
            target = moved(b0, x) if want is None else f"{want:.9g}"
            _, b, _ = run(renderer, tmp_path, "b", engine, base, note,
                          ["--param-at", f"0:{p['name']}={target}"])
            assert a == b, (p["name"], share)


@pytest.mark.parametrize("engine", PER_NOTE)
def test_an_offset_rides_on_a_ramping_base(renderer, tmp_path, listing, engine):
    """docs/15 S7b with per-note offsets: a base change while a voice with
    an offset sounds ramps over 2.5 ms (the engine's SMOOTH ramp, shared by
    all voices), and the voice plays the ramped base plus its offset at every
    control block. For a lone note, the base moving from 1/8 to 3/4 of the
    range under an offset of 1/8 is, byte for byte, the base moving from 1/4
    to 7/8 with no offset, which ramps the same way; the values and the
    ramp's steps (5/8 of the range over 10 or 8 blocks) are exact in float,
    so both sides add the same numbers. The move is heard on the loud
    parameter and Volume: the render differs from the one without it (some
    others act only at a note's start or on another model)."""
    base = TONE[engine]["params"]
    note = ["0:60:100:0.45"]
    for p in poly(listing, engine):
        lo, span = p["min"], p["max"] - p["min"]
        b0, b1, x = lo + span / 8, lo + 3 * span / 4, span / 8
        _, a, _ = run(renderer, tmp_path, "a", engine, base, note,
                      ["--param-at", f"0:{p['name']}={exact(b0)}",
                       "--note-param-at", f"0:60:{p['name']}={exact(x)}",
                       "--param-at", f"0.2:{p['name']}={exact(b1)}"])
        _, b, _ = run(renderer, tmp_path, "b", engine, base, note,
                      ["--param-at", f"0:{p['name']}={exact(b0 + x)}",
                       "--param-at", f"0.2:{p['name']}={exact(b1 + x)}"])
        assert a == b, p["name"]
        if p["name"] in (TONE[engine]["loud"], "Volume"):
            _, still, _ = run(renderer, tmp_path, "still", engine, base, note,
                              ["--param-at", f"0:{p['name']}={exact(b0)}",
                               "--note-param-at", f"0:60:{p['name']}={exact(x)}"])
            assert a != still, p["name"]


MODELS = {
    "macro": [f"Model={m}" for m in range(8)],
    "macro-heavy": [f"Model={m}" for m in range(13)],
    "shapes": [f"Shape={s}" for s in range(0, 47, 3)],
    "sixop": [f"Patch={p}" for p in (0, 11, 32, 49, 62, 77, 95)],
    "dx7": [f"Patch={p}" for p in (0, 6, 11, 14, 18, 21, 25, 28, 31, 32)],
}


@pytest.mark.parametrize("engine", PER_NOTE)
def test_every_offset_at_once_on_every_model(renderer, tmp_path, listing, engine):
    """All POLY parameters moved at once on a lone note, on every model (a
    sample of shapes and patches), against the same bases set engine-wide.
    Speech keeps Harmonics engine-wide (it picks the shared word bank), so
    there its offset is left out here."""
    for model in MODELS[engine]:
        speech = engine == "macro-heavy" and model == "Model=2"
        a_args, b_params = [], [model]
        for p in poly(listing, engine):
            if speech and p["name"] == "Harmonics":
                continue
            x = offset_for(p, 0.4)
            a_args += ["--note-param-at", f"0:57:{at(p['name'], x)}"]
            b_params.append(f"{p['name']}={moved(p['def'], x)}")
        _, a, _ = run(renderer, tmp_path, "a", engine, [model], ["0:57:110:0.3"], a_args,
                      seconds=0.5)
        _, b, _ = run(renderer, tmp_path, "b", engine, b_params, ["0:57:110:0.3"], seconds=0.5)
        assert a == b, model


@pytest.mark.parametrize("engine", PER_NOTE)
def test_a_pitch_offset_on_a_lone_note_is_a_bend(renderer, tmp_path, engine):
    base = TONE[engine]["params"]
    for semis in (7, -12, 0.5):
        _, a, _ = run(renderer, tmp_path, "a", engine, base, ["0:60:100:0.35"],
                      ["--note-pitch-at", f"0:60:{semis}", "--note-pitch-at", "0.25:60:-3"])
        _, b, _ = run(renderer, tmp_path, "b", engine, base, ["0:60:100:0.35"],
                      ["--bend", f"0:{semis}", "--bend", "0.25:-3"])
        assert a == b, semis


# A steady tone per engine for pitch measurement (tests/test_engine_host.py's).
PITCH_TONES = {
    "macro": ["Model=6", "Timbre=0", "Morph=0.5", "Harmonics=0.5"],
    "shapes": ["Shape=3", "Timbre=0", "Color=0"],
    "macro-heavy": ["Model=4", "Harmonics=0", "Timbre=0"],
    "sixop": ["Patch=40"],
    "dx7": ["Patch=31"],              # PURE SINE
}


@pytest.mark.parametrize("engine", PER_NOTE)
def test_a_pitch_offset_moves_the_pitch(renderer, tmp_path, engine):
    _, _, left = run(renderer, tmp_path, "p", engine, PITCH_TONES[engine], ["0:57:100:2.4"],
                     ["--note-pitch-at", "0.8:57:7", "--note-pitch-at", "1.6:57:0"], seconds=2.4)
    left = [x / 32767.0 for x in left]
    before, moved, after = (pitch_hz(left, a, 0.5) for a in (0.2, 1.0, 1.8))
    assert cents(moved, before) == pytest.approx(700, abs=1.0)
    assert cents(after, before) == pytest.approx(0, abs=1.0)


@pytest.mark.parametrize("engine", PER_NOTE)
def test_an_offset_reaches_only_its_note(renderer, tmp_path, listing, engine):
    """Two notes, an offset and a pitch offset on the first: the render is
    the first note with its offsets plus the second as it was, rendered
    apart (to rounding: at most 3 LSB at 16 bits), while either offset on
    its own moves a note by far more than that."""
    base = TONE[engine]["params"]
    loud = next(p for p in poly(listing, engine) if p["name"] == TONE[engine]["loud"])
    a, b = "0:57:100:0.5", "0:64:90:0.5"

    def offsets(key):
        return ["--note-param-at", f"0:{key}:{at(loud['name'], offset_for(loud, 0.45))}",
                "--note-pitch-at", f"0.15:{key}:5"]
    _, _, both = run(renderer, tmp_path, "both", engine, base, [a, b], offsets(57))
    _, _, a_moved = run(renderer, tmp_path, "a1", engine, base, [a], offsets(57))
    _, _, a_plain = run(renderer, tmp_path, "a0", engine, base, [a])
    _, _, b_plain = run(renderer, tmp_path, "b0", engine, base, [b])
    _, _, b_moved = run(renderer, tmp_path, "b1", engine, base, [b], offsets(64))
    assert max(abs(x) for x in both) < 0.9 * 32767       # the bus limiter stays out
    worst = max(abs(s - (p + q)) for s, p, q in zip(both, a_moved, b_plain))
    assert worst <= 3, worst
    assert max(abs(p - q) for p, q in zip(a_moved, a_plain)) > 300
    assert max(abs(p - q) for p, q in zip(b_moved, b_plain)) > 300


@pytest.mark.parametrize("engine", PER_NOTE)
def test_offsets_move_the_release_and_survive_note_off(renderer, tmp_path, listing, engine):
    """An offset set before note-off goes on through the release, the same
    as the base moved by as much for a lone note, and one sent during the
    release moves it: audibly (the voice was still sounding), and on top of
    the first, as on a base that already holds the first. (A base change
    there would ramp, SMOOTH; an offset does not.)"""
    base = TONE[engine]["params"]
    loud = next(p for p in poly(listing, engine) if p["name"] == TONE[engine]["loud"])
    vol = next(p for p in poly(listing, engine) if p["name"] == "Volume")
    x = offset_for(loud, 0.45)
    note = ["0:60:100:0.15"]
    first = ["--note-param-at", f"0:60:{at(loud['name'], x)}"]
    _, a, _ = run(renderer, tmp_path, "a", engine, base, note,
                  first + ["--note-param-at", "0.25:60:Volume=-0.35"])
    _, b, _ = run(renderer, tmp_path, "b", engine, base, note,
                  ["--param-at", f"0:{loud['name']}={moved(loud['def'], x)}",
                   "--note-param-at", "0.25:60:Volume=-0.35"])
    _, c, _ = run(renderer, tmp_path, "c", engine, base, note, first)
    assert vol["def"] - 0.35 >= vol["min"]
    assert a == b
    tail = 44 + 4 * int(0.26 * RATE)   # WAV header, then frames from 0.26 s on
    assert a[tail:] != c[tail:]


@pytest.mark.parametrize("engine", PER_NOTE)
def test_a_new_note_on_starts_at_no_offset(renderer, tmp_path, listing, engine):
    """A key played again starts at the base: the retrigger drops the
    offsets its voice had (here the same voice, retriggered in place), as
    sending each of them back to 0 right after it does. (The base moved
    back there instead would ramp, SMOOTH; dropped offsets do not.) The
    offsets kept would be heard: the render without the retrigger's drop
    differs."""
    base = TONE[engine]["params"]
    loud = next(p for p in poly(listing, engine) if p["name"] == TONE[engine]["loud"])
    x = offset_for(loud, 0.45)
    notes = ["0:60:100:0.6", "0.3:60:100:0.3"]
    first = ["--note-param-at", f"0:60:{at(loud['name'], x)}", "--note-pitch-at", "0:60:3"]
    _, a, _ = run(renderer, tmp_path, "a", engine, base, notes, first)
    _, b, _ = run(renderer, tmp_path, "b", engine, base, notes,
                  first + ["--note-param-at", f"0.3:60:{loud['name']}=0",
                           "--note-pitch-at", "0.3:60:0"])
    _, kept, _ = run(renderer, tmp_path, "kept", engine, base, notes,
                     first + ["--note-param-at", f"0.3:60:{at(loud['name'], x)}",
                              "--note-pitch-at", "0.3:60:3"])
    assert a == b
    assert a != kept


# Voices that end quickly once released, so a later call finds no voice.
SHORT = {
    "macro": ["Model=0", "Decay=0.1"],
    "macro-heavy": ["Model=4", "Decay=0.1"],
    "shapes": ["Shape=0", "Release=0.1"],
    "sixop": ["Patch=49", "Envelope=0.3"],
    "dx7": ["Patch=5"],               # MARIMBA
}


@pytest.mark.parametrize("engine", PER_NOTE)
def test_an_ended_voice_drops_its_offsets(renderer, tmp_path, listing, engine):
    """Calls for a key no voice sounds (one that has ended, one never
    played) are ignored, not kept for a later note: the key played again
    starts at the base."""
    loud = next(p for p in poly(listing, engine) if p["name"] == TONE[engine]["loud"])
    x = offset_for(loud, 0.45)
    notes = ["0:60:100:0.1", "2.2:60:100:0.2"]
    _, a, _ = run(renderer, tmp_path, "a", engine, SHORT[engine], notes,
                  ["--note-param-at", f"0:60:{at(loud['name'], x)}",
                   "--note-param-at", f"2.0:60:{at(loud['name'], -x)}",
                   "--note-param-at", f"2.0:72:{at(loud['name'], -x)}",
                   "--note-pitch-at", "2.0:60:5"], seconds=2.6)
    _, b, _ = run(renderer, tmp_path, "b", engine, SHORT[engine], notes,
                  ["--param-at", f"0:{loud['name']}={moved(loud['def'], x)}",
                   "--param-at", f"1.9:{at(loud['name'], loud['def'])}"], seconds=2.6)
    assert a == b


@pytest.mark.parametrize("engine", PER_NOTE)
def test_a_stolen_voice_drops_its_offsets(renderer, tmp_path, listing, engine):
    """Every voice holds a note turned down to silence by a Volume offset;
    one more note steals the oldest voice and sounds at the base volume,
    while the others stay silent (were their offsets dropped too, the steal
    would bring back every voice)."""
    n = listing[engine]["max_voices"]
    base = TONE[engine]["params"]
    keys = [40 + 2 * i for i in range(n)]
    held = [f"0:{k}:100:1.0" for k in keys]
    mute = sum((["--note-param-at", f"0:{k}:Volume=-1"] for k in keys), [])
    _, _, out = run(renderer, tmp_path, "steal", engine, base, held + ["0.3:79:100:0.7"], mute,
                    seconds=0.8)
    _, _, alone = run(renderer, tmp_path, "alone", engine, base, ["0.3:79:100:0.7"], seconds=0.8)
    _, _, muted = run(renderer, tmp_path, "muted", engine, base, held + ["0.3:79:100:0.7"],
                      mute + ["--note-param-at", "0.3:79:Volume=-1"], seconds=0.8)
    steal = int(0.3 * RATE)
    assert not any(out[:steal - 64]) and not any(muted)

    def rms(x):
        return math.sqrt(sum(v * v for v in x) / len(x))
    after = rms(out[steal + 2000:])
    assert after > 100
    assert after == pytest.approx(rms(alone[steal + 2000:]), rel=0.5)


@pytest.mark.parametrize("engine", PER_NOTE)
def test_nan_and_infinite_offsets(renderer, tmp_path, listing, engine):
    """NaN is no offset (set_param's NaN is the default); +/-inf pin the
    parameter at its maximum or minimum, as set_param's do; a pitch offset
    is cut to +/-48 semitones, the pitch bend's range."""
    base = TONE[engine]["params"]
    note = ["0:60:100:0.3"]
    loud = TONE[engine]["loud"]
    p = next(q for q in poly(listing, engine) if q["name"] == loud)
    _, plain, _ = run(renderer, tmp_path, "plain", engine, base, note)
    _, nan, _ = run(renderer, tmp_path, "nan", engine, base, note,
                    ["--note-param-at", f"0:60:{loud}=nan", "--note-pitch-at", "0:60:nan"])
    assert nan == plain
    for value, end in (("inf", p["max"]), ("-inf", p["min"]), ("1e30", p["max"])):
        _, a, _ = run(renderer, tmp_path, "a", engine, base, note,
                      ["--note-param-at", f"0:60:{loud}={value}"])
        _, b, _ = run(renderer, tmp_path, "b", engine, base + [f"{loud}={end}"], note)
        assert a == b, value
    for value, bend in (("inf", 48), ("-inf", -48), ("100", 48), ("-1e9", -48)):
        _, a, _ = run(renderer, tmp_path, "a", engine, base, note,
                      ["--note-pitch-at", f"0:60:{value}"])
        _, b, _ = run(renderer, tmp_path, "b", engine, base, note, ["--bend", f"0:{bend}"])
        assert a == b, value


IGNORED = {   # indices that are not POLY: the ENUMs, past the table, and far past it
    "macro": ["#0", "#10", "#11", "#999", "#65534"],
    "macro-heavy": ["#0", "#11", "#12", "#999", "#65534"],
    "shapes": ["#0", "#6", "#999", "#65534"],
    "sixop": ["#0", "#4", "#999", "#65534"],
    "dx7": ["#0", "#5", "#999", "#65534"],
}


@pytest.mark.parametrize("engine", PER_NOTE)
def test_other_indices_and_silent_keys_are_ignored(renderer, tmp_path, engine):
    base = TONE[engine]["params"]
    notes = ["0:60:100:0.3", "0.1:67:100:0.3"]
    extra = []
    for idx in IGNORED[engine]:
        extra += ["--note-param-at", f"0:60:{idx}=0.7", "--note-param-at", f"0.2:67:{idx}=-1e9"]
    extra += ["--note-param-at", f"0.1:99:{TONE[engine]['loud']}=0.4",
              "--note-pitch-at", "0.1:99:12"]
    _, plain, _ = run(renderer, tmp_path, "plain", engine, base, notes)
    _, a, _ = run(renderer, tmp_path, "a", engine, base, notes, extra)
    assert a == plain


def test_speech_keeps_harmonics_engine_wide(renderer, tmp_path):
    """On Speech, Harmonics picks the word bank all voices share, so its
    per-note offset is ignored there; the other offsets apply."""
    base = ["Model=2", "Harmonics=0.75", "Morph=0.3"]
    note = ["0:57:100:0.6"]
    _, plain, _ = run(renderer, tmp_path, "plain", "macro-heavy", base, note, seconds=0.8)
    _, harm, _ = run(renderer, tmp_path, "harm", "macro-heavy", base, note,
                     ["--note-param-at", "0:57:Harmonics=-0.6"], seconds=0.8)
    _, timb, _ = run(renderer, tmp_path, "timb", "macro-heavy", base, note,
                     ["--note-param-at", "0:57:Timbre=0.4"], seconds=0.8)
    assert harm == plain and timb != plain


@pytest.mark.parametrize("engine", PER_NOTE)
def test_any_initial_memory_with_offsets(renderer, tmp_path, listing, engine):
    """The offsets live in instance memory the engine initialises itself."""
    extra = ["--note-pitch-at", "0.05:57:-2"]
    for p in poly(listing, engine):
        extra += ["--note-param-at", f"0:57:{at(p['name'], offset_for(p))}",
                  "--note-param-at", f"0.1:64:{at(p['name'], -offset_for(p, 0.2))}"]
    outs = []
    for fill in ("0", "0xA5", "0xFF"):
        _, w, _ = run(renderer, tmp_path, f"f{fill}", engine, TONE[engine]["params"],
                      ["0:57:100:0.3", "0.1:64:90:0.3"], extra + ["--fill", fill], seconds=0.6)
        outs.append(w)
    assert outs[1] == outs[0] and outs[2] == outs[0]


@pytest.mark.parametrize("engine", PER_NOTE)
def test_offsets_do_not_depend_on_the_host_block(renderer, tmp_path, listing, engine):
    """Calls at the same frames give the same output at host blocks of 1, 7
    and 64: notes, offsets and pitch offsets at frames all three reach
    (multiples of 448), a note-off and a retrigger among them."""
    def t(frame):
        return 0.0 if frame == 0 else (frame - 0.5) / RATE
    f1, f2, f3, f4 = 4480, 8960, 13440, 17920
    notes = [f"0:57:100:{t(f2):.9f}", f"{t(f1):.9f}:64:90:{t(f3) - t(f1):.9f}",
             f"{t(f3):.9f}:57:80:{t(f4) - t(f3):.9f}"]
    ps = poly(listing, engine)
    extra = ["--note-pitch-at", "0:57:2", f"--note-pitch-at", f"{t(f1):.9f}:64:-5"]
    for i, p in enumerate(ps):
        extra += ["--note-param-at", f"0:57:{at(p['name'], offset_for(p))}",
                  "--note-param-at", f"{t(f1):.9f}:64:{at(p['name'], offset_for(p, 0.2))}",
                  "--note-param-at", f"{t(f2):.9f}:{57 if i % 2 else 64}:"
                                     f"{at(p['name'], -offset_for(p, 0.1))}"]
    outs = []
    for frames in ("1", "7", "64"):
        _, w, _ = run(renderer, tmp_path, f"b{frames}", engine, TONE[engine]["params"], notes,
                      extra + ["--frames", frames], seconds=0.45)
        outs.append(w)
    assert outs[1] == outs[0] and outs[2] == outs[0]


# Shapes holds Braids inside the range its code handles (MIDI 0..127.99, and
# Comb's and Wave Line's Timbre ends; engines/README.md, "Shapes: where
# Braids is held"), so every shape takes the full extremes here too.
EXTREME_MODELS = {
    "macro": [f"Model={m}" for m in range(8)],
    "macro-heavy": [f"Model={m}" for m in range(13)],
    "shapes": [f"Shape={s}" for s in range(47)],
    "sixop": [f"Patch={p}" for p in range(0, 96, 5)],
    "dx7": [f"Patch={p}" for p in range(0, 33, 2)],
}


@pytest.mark.parametrize("engine", PER_NOTE)
@pytest.mark.parametrize("sign", ["inf", "-inf"])
def test_extreme_offsets_render_finite(renderer, tmp_path, listing, engine, sign):
    """Every POLY parameter pinned at an end and the pitch offset at +/-48
    on top of a +/-48 bend, on the lowest and highest keys, every model
    (Six-Op: every fifth patch). Finite output; under the sanitizer build,
    no undefined behaviour or out-of-bounds read either."""
    keys = (0, 127)
    for model in EXTREME_MODELS[engine]:
        extra = ["--bend", f"0:{'' if sign == 'inf' else '-'}48", "--frames", "7"]
        for key in keys:
            extra += ["--note-pitch-at", f"0:{key}:{sign}"]
            for p in poly(listing, engine):
                extra += ["--note-param-at", f"0:{key}:{p['name']}={sign}"]
        s, _, _ = run(renderer, tmp_path, "x", engine, [model],
                      [f"0:{key}:127:0.1" for key in keys], extra, seconds=0.2)
        assert s["nonfinite"] == 0, model
