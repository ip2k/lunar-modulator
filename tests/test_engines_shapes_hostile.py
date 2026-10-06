"""A reviewer's hostile checks of Shapes at Braids' edges (engines/README.md,
"Shapes: where Braids is held"), driven by build/fm1-shapes-hostile
(engines/test/shapes_hostile.cc). tests/test_engines_shapes_edges.py sweeps
the knob ends and whole semitones; these scripts reach the values between,
turn the knobs, bends and per-note offsets while notes sound, and switch
Shape mid-note. Under CI's sanitizer build (ASan and UBSan, halting on the
first report) the tool exits non-zero on any report, so every check here
also says Braids stayed inside what its code handles.
"""
import json
import subprocess

import pytest

from tests.engine_helpers import ENGINES, renderer  # noqa: F401

TOOL = ENGINES / "build" / "fm1-shapes-hostile"
NUM_SHAPES = 47
COMB, WAVE_LINE = 15, 39


@pytest.fixture(scope="module")
def tool(renderer):  # noqa: F811 -- the renderer fixture builds everything
    out = subprocess.run([str(TOOL)], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def test_any_script_any_blocks_any_fill_same_bits(tool):
    # One script a shape: about 120 notes, knob turns (NaN and infinities
    # included), bends and pitch offsets anywhere in +/-48 (offsets +/-inf
    # and NaN too), per-note Timbre and Color offsets, and Shape switched
    # while notes sound, mostly to the shapes with edges. Blocks of 1, 7 and
    # random 1-64 frames, and memory filled with 0xFF and 0xA5 before create,
    # give the 64-frame render's bits exactly.
    rows = tool["schedule"]
    assert [r["shape"] for r in rows] == list(range(NUM_SHAPES))
    for r in rows:
        assert r["finite"] and r["events"] > 100, r
        assert r["same"] == r["tried"] == 5, r
        assert 0.01 < r["peak"] < 4.0, r


def test_every_note_above_midi_127_99_plays_as_one_at_it(tool):
    # Every voice at MIDI 128 or above (keys 81-127 under bends of 47-48,
    # pitch offsets 0-48), Timbre, Color and the envelope turning: the same
    # bits as each note held at MIDI 127.9921875, Braids' 16,383, on every
    # shape. The build before the clamp fails 23 shapes here.
    rows = tool["above"]
    assert [r["shape"] for r in rows] == list(range(NUM_SHAPES))
    for r in rows:
        assert r["finite"] and r["same"], r
    # Harmonic (24) is silent up there: Braids drops every partial above
    # 12 kHz (RenderHarmonics), and MIDI 127.99 is 13.3 kHz.
    assert sum(r["peak"] > 0.001 for r in rows) >= NUM_SHAPES - 1


def test_comb_timbre_below_the_clamp_plays_as_the_clamp(tool):
    # Every voice at Braids pitch 0 (keys 0-47 bent and offset down), Timbre
    # turning anywhere in 0-0.375 with per-note offsets down to -inf: the
    # bits of Timbre held at 12,288, where the comb's own pitch is MIDI -16.
    rows = tool["comb"]
    assert len(rows) == 6 and all(r["shape"] == COMB for r in rows)
    for r in rows:
        assert r["finite"] and r["same"] and r["peak"] > 0.01, r


def test_wave_line_timbre_above_the_clamp_plays_as_the_clamp(tool):
    # Any key, bend and pitch offset, Timbre turning anywhere in 0.9845-1
    # with per-note offsets up to +inf: the bits of Timbre held at 32,255,
    # the line's last wave.
    rows = tool["wave_line"]
    assert len(rows) == 6 and all(r["shape"] == WAVE_LINE for r in rows)
    for r in rows:
        assert r["finite"] and r["same"] and r["peak"] > 0.01, r
