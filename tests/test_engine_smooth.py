"""SMOOTH inside the engines (docs/15 stage S7b, engines/include/fm1_smooth.h).

A change to a SMOOTH parameter while an engine sounds ramps over 2.5 ms of
the engine's native samples, in steps of its own control block, and lands on
the new value exactly; while nothing sounds, and before an effect's first
render, it applies at once. The ramp is keyed to samples, so the output does
not depend on how the host cuts its render calls, with changes at any frame
(build/fm1-smooth-test, engines/test/smooth_test.cc, drives every engine and
effect where fm1-render cannot), and a repeated write changes nothing.
"""
import json
import math
import struct
import subprocess
import wave

import pytest

from tests.engine_helpers import ENGINES, renderer  # noqa: F401
from tests.test_seq_core import d1_frame

RATE = 44118
SMOOTH_TEST = ENGINES / "build" / "fm1-smooth-test"


@pytest.fixture(scope="module")
def units(renderer):
    """Every engine and effect fm1-render lists (the driver links the same
    objects; `make` built it with fm1-render)."""
    listed = json.loads(subprocess.run([str(renderer), "--list"], check=True,
                                       capture_output=True, text=True).stdout)
    return {e["id"]: e for e in listed}


def drive(tmp_path, engine, *args, name="d"):
    out = tmp_path / f"{name}.f32"
    res = subprocess.run([str(SMOOTH_TEST), "--engine", engine, *args, "--out", str(out)],
                         check=True, capture_output=True, text=True)
    summary = json.loads(res.stdout)
    assert summary["nonfinite"] == 0, (engine, args)
    return out.read_bytes()


def floats(raw):
    return struct.unpack(f"<{len(raw) // 4}f", raw)


UNITS = ["test-sine", "macro", "macro-heavy", "shapes", "sixop", "sw-sophie", "plate",
         "ensemble", "diffuse", "crush", "fold", "echo", "test-gain", "sw-psxverb",
         "drive", "filter", "comp", "limit"]


def test_the_driver_covers_every_engine_and_effect(units):
    assert sorted(UNITS) == sorted(i for i, e in units.items() if e["kind"] != "midi_fx")


@pytest.mark.parametrize("engine", UNITS)
def test_changes_at_any_frame_render_the_same_at_any_split(renderer, tmp_path, engine):
    """Every parameter but the NOLOCK ones changed while notes sound (an
    effect: while noise plays), turned again mid-ramp, back to its default,
    then NaN, infinity and beyond its range: the output is the same, bit for
    bit, when render calls are cut at 64, 1, 7 or random frames as well as at
    every change."""
    ref = drive(tmp_path, engine, "--split", "64", name="b64")
    for split in ("1", "7", "random"):
        assert drive(tmp_path, engine, "--split", split, name=f"b{split}") == ref, split
    assert ref != drive(tmp_path, engine, "--schedule", "none", name="none") or engine == "sw-sophie", \
        "the changes are heard (Sophie's edit pad 0, which these keys do not play)"


@pytest.mark.parametrize("engine", UNITS)
def test_a_repeated_write_changes_nothing(renderer, tmp_path, engine):
    """Each write sent again 5 and 20 frames later, mid-ramp: the same output
    as without the repeats. A host may resend the value it last sent (a knob
    that has not moved, a lock equal to the base) at no cost."""
    assert drive(tmp_path, engine, "--schedule", "repeat", name="rep") == drive(tmp_path, engine)


@pytest.mark.parametrize("rate,samples", [(44118, 110), (48000, 120), (22050, 55)])
def test_a_ramp_takes_2_5_ms_and_lands_on_the_value(renderer, tmp_path, rate, samples):
    """Test Gain on 0.5 DC, Gain 1 -> 2 at frame 1,000: 2.5 ms of samples
    (rounded to the nearest one) in equal steps, monotonic, never past the
    target, and exactly the target from the last one on."""
    x = floats(drive(tmp_path, "test-gain", "--source", "dc", "--schedule", "none", "--rate", str(rate),
                     "--set", "Gain=2@1000", "--seconds", "0.05"))[0::2]
    f = 1000
    assert set(x[:f]) == {0.5}
    ramp = x[f:f + samples]
    assert ramp[-1] == 1.0 and all(v < 1.0 for v in ramp[:-1])
    assert set(x[f + samples - 1:]) == {1.0}
    steps = [b - a for a, b in zip((0.5,) + ramp, ramp)]
    assert all(s > 0 for s in steps)
    assert max(steps) - min(steps) < 1e-6 and abs(sum(steps) - 0.5) < 1e-6


def test_a_change_before_the_first_render_applies_at_once(renderer, tmp_path):
    x = floats(drive(tmp_path, "test-gain", "--source", "dc", "--schedule", "none",
                     "--set", "Gain=2@0", "--seconds", "0.01"))
    assert set(x) == {1.0}


def test_a_ramp_turned_back_mid_way_starts_from_where_it_stands(renderer, tmp_path):
    """Gain 1 -> 2 at frame 1,000, then 2 -> 1 at 1,050: the second ramp
    starts from the value the first had reached and takes its own 110
    samples; it never jumps."""
    x = floats(drive(tmp_path, "test-gain", "--source", "dc", "--schedule", "none",
                     "--set", "Gain=2@1000", "--set", "Gain=1@1050", "--seconds", "0.05"))[0::2]
    peak = x[1049]
    assert 0.7 < peak < 0.8 and x[1050] < peak
    assert max(abs(b - a) for a, b in zip(x[999:1300], x[1000:1301])) < 0.0046
    assert x[1050 + 109] == 0.5 and x[1050 + 108] > 0.5


def wav_left(path):
    with wave.open(str(path), "rb") as w:
        raw = w.readframes(w.getnframes())
    return [int.from_bytes(raw[i:i + 2], "little", signed=True) for i in range(0, len(raw), 4)]


def seq_render(renderer, tmp_path, script, name, engine="test-sine"):
    path = tmp_path / f"{name}.verbs"
    path.write_text(script)
    wav = tmp_path / f"{name}.wav"
    res = subprocess.run([str(renderer), "--cmd", str(path), "--engine", engine, "--out", str(wav)],
                         check=True, capture_output=True, text=True)
    return json.loads(res.stdout), wav_left(wav)


HELD = (f"#! rate={RATE} block=64 tracks=1 end={RATE // 2}\n"
        "@0 tog 0 0 69 127;slen 0 0 0 -1 380\n"
        "@0 alabel 0 0 synth:Volume;abase 0 0 {base}{lock}\n@0 play\n")


def test_a_volume_lock_under_a_held_note_does_not_click(renderer, tmp_path):
    """docs/15 S7b's zipper test, on Test Sine's Volume, where amplitude is
    the parameter itself: a 0 -> 127 lock under a held A4 moves the output by
    no more than the sine's own slope plus 1/110 of its amplitude per sample,
    where a jump at that frame would move it by most of the amplitude; and
    from the 110th sample on the output is that of Volume 127 throughout."""
    step = 3                                  # its lock frame falls near a crest
    s, locked = seq_render(renderer, tmp_path, HELD.format(base=0, lock=f";aset 0 0 {step} 127 1"),
                           "locked")
    _, full = seq_render(renderer, tmp_path, HELD.format(base=127, lock=""), "full")
    assert s["seq_locks_to_engine"] == 3      # the base at Play and at the note, then the lock
    f = d1_frame(0, 24 * step - 1)            # a lock goes out one tick before its step
    amp = 0.25 * 32767                        # Test Sine at velocity 127 and Volume 1
    bound = amp * (2 * math.pi * 440 / RATE + 1 / 110) + 2
    assert set(locked[:f]) == {0}
    assert abs(full[f]) > 0.9 * amp > 10 * bound, "a jump here would be a full-scale click"
    assert max(abs(b - a) for a, b in zip(locked[f - 1:f + 200], locked[f:f + 201])) <= bound
    assert locked[f + 109:] == full[f + 109:]
    assert locked[f + 108] != full[f + 108]


SILENT_TRIG = (f"#! rate={RATE} block=64 tracks=1 end={2 * RATE}\n"
               "@0 tog 0 0 69 127;tog 0 8 69 127;slen 0 0 0 -1 40\n"
               "@0 alabel 0 0 synth:Volume;abase 0 0 {base}{lock}\n@0 play\n")


def test_a_lock_on_a_silent_engines_trig_plays_from_the_notes_first_sample(renderer, tmp_path):
    """Nothing sounds when step 8's lock arrives (step 0's short note has
    ended), so it applies at once: the note plays at the locked value from
    its first sample, as with that value set throughout."""
    s, locked = seq_render(renderer, tmp_path, SILENT_TRIG.format(base=127, lock=";aset 0 0 8 40 1"),
                           "locked")
    _, plain = seq_render(renderer, tmp_path, SILENT_TRIG.format(base=40, lock=""), "plain")
    on = d1_frame(0, 24 * 8)
    assert s["seq_locks_to_engine"] >= 2
    assert set(locked[on - 200:on]) == {0}, "step 0's note has ended"
    assert locked[on:on + 4000] == plain[on:on + 4000] and max(plain[on:on + 4000]) > 1000


@pytest.mark.parametrize("engine,name", [("macro", "Timbre"), ("shapes", "Color"),
                                         ("sixop", "Brightness"), ("macro-heavy", "Morph")])
def test_a_lock_under_a_held_note_reaches_the_native_engines_at_its_frame(renderer, tmp_path,
                                                                          engine, name):
    """On the engines that run at their own rate the lock ramps in their
    control blocks (12 or 16 samples at 47,872.34 Hz, 24 at 96 kHz): the
    output up to the lock's frame is untouched, and it differs after."""
    script = HELD.replace("synth:Volume", f"synth:{name}")
    _, a = seq_render(renderer, tmp_path, script.format(base=0, lock=";aset 0 0 3 127 1"), "a", engine)
    _, b = seq_render(renderer, tmp_path, script.format(base=0, lock=""), "b", engine)
    f = d1_frame(0, 24 * 3 - 1)
    assert a[:f] == b[:f] and a[f:] != b[f:]


@pytest.mark.parametrize("tone0,tone1", [("0", "1"), ("1", "0")])
def test_echos_tone_ramps_its_loop_filter(renderer, tmp_path, tone0, tone1):
    """Echo's own glides cover Time, Wow and its gains; Tone's in-loop
    low-pass coefficient takes the shared ramp. Under noise at full feedback,
    a Tone change enters the loop gradually: the first eight samples in which
    it is heard, one 10 ms echo later, differ from the unchanged render by
    under a tenth of what they differ by a ramp later (a jump of the
    coefficient measured 0.42 and 0.84 of it; the ramp, 0.03)."""
    base = ["--source", "noise", "--schedule", "none", "--seconds", "0.2",
            "--set", "Time=10@0", "--set", "Feedback=1@0", "--set", "Mix=1@0",
            "--set", "Wow=0@0", "--set", "Ping-pong=0@0", "--set", f"Tone={tone0}@0"]
    a = floats(drive(tmp_path, "echo", *base, "--set", f"Tone={tone1}@4000", name="a"))[0::2]
    b = floats(drive(tmp_path, "echo", *base, name="b"))[0::2]
    d = [x - y for x, y in zip(a, b)]
    first = next(i for i, v in enumerate(d) if v != 0)
    assert first == 4000 + 441                # Tone acts on the repeats only
    early = max(abs(v) for v in d[first:first + 8])
    late = max(abs(v) for v in d[first + 200:first + 600])
    assert late > 0.3 and early < 0.1 * late
