"""Shapes at Braids' edges (engines/src/mi_shapes.cc; engines/README.md,
"Shapes: where Braids is held").

Braids' vendored code shifts by a negative count or by 32, or reads past a
table, at some edges: Comb at a low Timbre on low keys, Wave Line at the top
of Timbre, Flute above MIDI 127.99 and the four filter shapes there at a
high Timbre. The vendored code stays as upstream wrote it; the wrapper holds
every voice inside what it handles. These tests:

- sweep every shape over every key, Timbre and Color at both ends and the
  middle, and the note from MIDI -96 to 223 (bends of -48, 0 and +48, with
  pitch offsets of +/-48 on top), one render per shape: finite output here,
  and under CI's sanitizer build (ASan and UBSan, halting on the first
  report; .github/workflows/ci.yml) no report at all, which is the proof
  that matters;
- show each clamp holding without a sanitizer: a note above MIDI 127.99
  renders byte for byte as one at 127.99, on every shape; Wave Line's Timbre
  stops at 32,255 of 32,767; Comb's Timbre stops where the comb's own pitch
  would fall below MIDI -16.

tests/test_engines_reference_braids_fx.py checks that at those edges Shapes
plays what upstream's oscillator plays at the clamped values.
"""
import struct

import pytest

from tests.engine_helpers import render, renderer  # noqa: F401

NUM_SHAPES = 47
COMB, WAVE_LINE = 15, 39

# Braids' own units: 1/128 semitone, and the int16 the wrapper passes for a
# 0..1 knob (value * 32767, truncated).
HIGHEST_PITCH = 16383                  # MIDI 127.99
COMB_LOWEST_PITCH = -2048              # MIDI -16
WAVE_LINE_HIGHEST_TIMBRE = 32255


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def knob(timbre16):
    """A 0..1 knob value, as text, that the wrapper turns into exactly
    timbre16 (value * 32767 in float, truncated)."""
    text = f"{(timbre16 + 0.5) / 32767.0:.9f}"
    assert int(f32(f32(float(text)) * 32767.0)) == timbre16
    return text


def comb_lowest_timbre(key):
    return 16384 + 2 * (COMB_LOWEST_PITCH - key * 128)


# The sweep: segments of SEGMENT seconds, each playing one group of keys
# (0, 11, 22 ... then 1, 12, 23 ...: 11 groups of up to 12, the voice count)
# at one Timbre/Color corner and one bend and pitch offset. Timbre and Color
# move at each segment's start while the last segment's notes release, so
# they ramp (SMOOTH) through the values between, and voices are stolen.
SEGMENT = 0.012
CORNERS = ((0, 0), (0, 1), (1, 0), (1, 1), (0.5, 0.5))
# (bend, pitch offset): the note runs from key - 96 to key + 96.
PITCHES = ((-48, -48), (-48, 0), (0, 0), (48, 0), (48, 48))
GROUPS = [list(range(g, 128, 11)) for g in range(11)]


def sweep_args():
    params, notes, extra = [], [], []
    t = 0.0
    for bend, offset in PITCHES:
        for timbre, color in CORNERS:
            for keys in GROUPS:
                at = f"{t:.4f}"
                extra += ["--param-at", f"{at}:Timbre={timbre}",
                          "--param-at", f"{at}:Color={color}", "--bend", f"{at}:{bend}"]
                for k in keys:
                    notes.append(f"{at}:{k}:127:{SEGMENT * 0.75:.4f}")
                    if offset:
                        extra += ["--note-pitch-at", f"{at}:{k}:{offset}"]
                t += SEGMENT
    return notes, extra, t + 0.01


@pytest.mark.parametrize("shape", range(NUM_SHAPES))
def test_every_key_knob_end_and_bend_renders_clean(renderer, tmp_path, shape):  # noqa: F811
    """Every key at every Timbre/Color corner, from MIDI -96 to 223. Finite
    and sounding; under the sanitizer build, no report (fm1-render exits
    non-zero on the first, and render() checks the exit status)."""
    notes, extra, seconds = sweep_args()
    s, left, _ = render(renderer, tmp_path, "shapes", [f"Shape={shape}", "Release=0.1"], notes,
                        seconds=seconds, extra=extra + ["--frames", "64"])
    assert s["nonfinite"] == 0
    assert max(abs(x) for x in left) > 0.001, "a silent sweep proves nothing"


def wav_bytes(renderer, tmp_path, name, params, notes, extra=(), seconds=0.15):  # noqa: F811
    _, _, wav = render(renderer, tmp_path, "shapes", params, notes, seconds=seconds,
                       name=name, extra=list(extra))
    return wav.read_bytes()


@pytest.mark.parametrize("shape", range(NUM_SHAPES))
def test_a_note_above_midi_127_99_plays_as_one_at_it(renderer, tmp_path, shape):  # noqa: F811
    """Key 127 bent up 48 renders byte for byte as key 127 bent up 127/128,
    Braids' pitch 16,383, the highest braids.cc passes its oscillator at the
    default octave. A pitch offset on top changes nothing either."""
    params = [f"Shape={shape}", "Timbre=1", "Color=0.75"]
    top = wav_bytes(renderer, tmp_path, "top", params, ["0:127:127:0.1"],
                    ["--bend", f"0:{HIGHEST_PITCH / 128 - 127}"])
    assert wav_bytes(renderer, tmp_path, "bent", params, ["0:127:127:0.1"],
                     ["--bend", "0:48"]) == top
    assert wav_bytes(renderer, tmp_path, "offset", params, ["0:127:127:0.1"],
                     ["--bend", "0:48", "--note-pitch-at", "0:127:48"]) == top


def test_wave_line_timbre_stops_at_the_last_wave(renderer, tmp_path):  # noqa: F811
    """Above 32,255 of 32,767 Braids' scan would read wave_line[64]: Timbre 1
    and 32,256 render as 32,255, and 32,254 still differs from it."""
    def at(timbre, name):
        return wav_bytes(renderer, tmp_path, name, [f"Shape={WAVE_LINE}", f"Timbre={timbre}",
                                                   "Color=0.3"], ["0:45:127:0.1", "0:93:127:0.1"])
    last = at(knob(WAVE_LINE_HIGHEST_TIMBRE), "last")
    assert at("1", "one") == last
    assert at(knob(WAVE_LINE_HIGHEST_TIMBRE + 1), "above") == last
    assert at(knob(WAVE_LINE_HIGHEST_TIMBRE - 1), "below") != last


@pytest.mark.parametrize("key", [0, 24, 36, 47])
def test_comb_timbre_keeps_the_comb_at_midi_minus_16(renderer, tmp_path, key):  # noqa: F811
    """With the comb's own pitch, key + (Timbre - 0.5) x 64 semitones, below
    MIDI -16, Braids' ComputeDelay shifts by a negative count. Timbre 0 on
    keys 0..47 renders as the lowest Timbre that keeps it at MIDI -16, also
    through a per-note offset to the bottom."""
    lowest = comb_lowest_timbre(key)
    assert 0 < lowest <= 12288
    note = [f"0:{key}:127:0.1"]
    clamped = wav_bytes(renderer, tmp_path, "clamped", [f"Shape={COMB}", f"Timbre={knob(lowest)}",
                                                        "Color=0.8"], note)
    assert wav_bytes(renderer, tmp_path, "zero", [f"Shape={COMB}", "Timbre=0", "Color=0.8"],
                     note) == clamped
    assert wav_bytes(renderer, tmp_path, "offset", [f"Shape={COMB}", "Timbre=0.5", "Color=0.8"],
                     note, ["--note-param-at", f"0:{key}:Timbre=-inf"]) == clamped

