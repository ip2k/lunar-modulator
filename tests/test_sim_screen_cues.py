"""Cues on the virtual FM-1's screen that do not lean on colour or touch:
the sequencer's track strip carries each track's sound number on its tile
(audit L3: the number is the cue that needs no colour), and MATRIX's state
mark keeps a narrow gap from its source and its destination, so a
six-character source does not run into it ("S2RTRG > ENV4", not
"S2RTRG>ENV4"), and CHAIN's '>' keeps one from its destination
("-100 > ENV3 Sustain").

Read from the screen sweep's frames (fm1-sim-render --screens) and the
generated Spleen 6 x 12 table, not from the drawing code.
"""
import re
import subprocess
import sys

import pytest

from tests.engine_helpers import ROOT
from tests.test_sim_web import tools  # noqa: F401  (the native build of both tools)

sys.path.insert(0, str(ROOT / "sim" / "web" / "tools"))
import palette as P  # noqa: E402

SRC = ROOT / "sim" / "web" / "src"
STATUS_Y, STATUS_H = 28, 18          # the Track view's status line (CONTENT_Y, MAIN's height)
TEMPO_RIGHT = 6 + 82                 # MARGIN + "300 BPM" in MAIN
TRANSPORT_LEFT = 234 - 46            # RIGHT - four MAIN characters
ROW_Y0, ROW_PITCH, ROW_H = 28, 18, 14   # MATRIX's rows in MID
RIGHT = 234


@pytest.fixture(scope="module")
def frames(tools, tmp_path_factory):  # noqa: F811
    out = tmp_path_factory.mktemp("screens")
    res = subprocess.run([str(tools["sim"]), "--screens", str(out)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    return out


def ppm(path):
    data = path.read_bytes()
    head = data.split(b"\n", 3)
    w, h = map(int, head[1].split())
    px = head[3]
    return [[tuple(px[(y * w + x) * 3:(y * w + x) * 3 + 3]) for x in range(w)] for y in range(h)]


def ppm_colour(rgb):
    """A colour as the harness's PPM writes it: the RGB565 word, each field
    scaled to 0-255 by integer division (write_ppm in fm1_sim_render.c)."""
    w = P.rgb565(rgb)
    return ((w >> 11) * 255 // 31, ((w >> 5) & 63) * 255 // 63, (w & 31) * 255 // 31)


@pytest.fixture(scope="module")
def colours():
    return {name: ppm_colour(v["page"]) for name, v in P.palette(*P.load(ROOT)).items()}


def small_glyph(ch):
    """The ink of `ch` in Spleen 6 x 12 (fm1_font_small.h), trimmed to its
    bounding box: a tuple of strings of '#' and '.'."""
    text = (SRC / "fm1_font_small.h").read_text(encoding="utf-8")
    rows = int(re.search(r"FM1_FONT_SMALL_ROWS (\d+)", text).group(1))
    cols = int(re.search(r"FM1_FONT_SMALL_COLS (\d+)", text).group(1))
    table = re.findall(r"\{ ((?:0x[0-9A-Fa-f]{2}, ){%d}0x[0-9A-Fa-f]{2}) \}" % (rows - 1), text)
    bits = [int(v, 16) for v in table[ord(ch) - 0x20].split(", ")]
    grid = ["".join("#" if b & (1 << (cols - 1 - c)) else "." for c in range(cols)) for b in bits]
    return trim(grid)


def trim(grid):
    rows = [r for r in grid if "#" in r]
    if not rows:
        return ()
    lo = min(r.index("#") for r in rows)
    hi = max(r.rindex("#") for r in rows)
    top = next(i for i, r in enumerate(grid) if "#" in r)
    bottom = max(i for i, r in enumerate(grid) if "#" in r)
    return tuple(r[lo:hi + 1] for r in grid[top:bottom + 1])


def strip_tracks(img, base):
    """The status line's tracks, left to right: for each, the columns it
    covers and its pixels, between the tempo and the transport."""
    band = img[STATUS_Y:STATUS_Y + STATUS_H]
    used = [x for x in range(TEMPO_RIGHT + 1, TRANSPORT_LEFT)
            if any(row[x] != base for row in band)]
    groups = []
    for x in used:
        if groups and x == groups[-1][-1] + 1:
            groups[-1].append(x)
        else:
            groups.append([x])
    return [(g[0], g[-1], [row[g[0]:g[-1] + 1] for row in band]) for g in groups]


def number_on(cells, base, colour, muted):
    """The number a track shows: on a lit tile, the base-coloured pixels
    inside the tile; on a muted (unlit) one, the pixels in the sound's
    colour, the rows of a focused one's bars aside. Also the rows the tile
    covers, or the bars' rows."""
    if not muted:
        rows = [i for i, r in enumerate(cells) if any(p == colour for p in r)]
        top, bottom = rows[0], rows[-1]
        grid = ["".join("#" if p == base else "." for p in r) for r in cells[top:bottom + 1]]
        return trim(grid), (top, bottom)
    bars = tuple(i for i, r in enumerate(cells) if all(p == colour for p in r) and len(r) > 6)
    grid = ["".join("#" if p == colour and i not in bars else "." for p in r) for i, r in enumerate(cells)]
    return trim(grid), bars


@pytest.mark.parametrize("frame,tracks", [
    # the sweep's routes: track t on sound t % 4 + 1, tracks 2 and 5 muted,
    # track 3 focused (then muted too); the default: track 1 on Sound 1, the
    # others MIDI out
    ("seq-tracks-sounds", [("1", "nebula", 0, 0), ("2", "nova", 1, 0), ("3", "aurora", 0, 1),
                           ("4", "comet", 0, 0), ("1", "nebula", 1, 0), ("2", "nova", 0, 0),
                           ("3", "aurora", 0, 0), ("4", "comet", 0, 0)]),
    ("seq-tracks-sounds-focused-muted", [("1", "nebula", 0, 0), ("2", "nova", 1, 0),
                                         ("3", "aurora", 1, 1), ("4", "comet", 0, 0),
                                         ("1", "nebula", 1, 0), ("2", "nova", 0, 0),
                                         ("3", "aurora", 0, 0), ("4", "comet", 0, 0)]),
    ("seq-tracks-eight", [("1", "nebula", 0, 1)] + [("M", "subtle", 0, 0)] * 7),
])
def test_each_track_shows_its_sounds_number(frames, colours, frame, tracks):
    """Each tile carries the number of the sound its track plays ('M' for
    MIDI out) in the face's own glyph, knocked out of the tile; a muted
    track's number stands alone in the sound's colour. The focused tile is
    the line's full height (a muted focused one keeps the bars it adds), the
    others 12 px, and every number keeps 2 px of tile round its ink."""
    img = ppm(frames / f"{frame}.ppm")
    base = colours["base"]
    got = strip_tracks(img, base)
    assert len(got) == len(tracks), [(a, b) for a, b, _ in got]
    for (x0, x1, cells), (ch, name, muted, focused) in zip(got, tracks):
        shape, rows = number_on(cells, base, colours[name], muted)
        assert shape == small_glyph(ch), (frame, ch, shape)
        if not muted:                    # a tile, solid down both sides
            top, bottom = rows
            assert (top, bottom) == ((0, STATUS_H - 1) if focused else (3, STATUS_H - 4)), (frame, ch)
            assert all(r[0] == r[-1] == colours[name] for r in cells[top:bottom + 1]), (frame, ch)
            ink = [i for i, r in enumerate(cells[top:bottom + 1]) if any(p == base for p in r)]
            cols = [c for c in range(x1 - x0 + 1) if any(r[c] == base for r in cells[top:bottom + 1])]
            assert ink[0] >= 2 and (bottom - top) - ink[-1] >= 2, (frame, ch, ink)
            assert cols[0] >= 2 and (x1 - x0) - cols[-1] >= 2, (frame, ch, cols)
        elif focused:                    # the bars a focused tile adds, and the number between
            assert rows == (0, 1, 2, STATUS_H - 3, STATUS_H - 2, STATUS_H - 1), (frame, rows)
        else:                            # the number alone: no tile
            assert rows == () and x1 - x0 + 1 <= 6, (frame, ch, x0, x1)
    gaps = [b[0] - a[1] - 1 for a, b in zip(got, got[1:])]
    assert min(gaps) >= 2, gaps


def ink_columns(row, colour):
    return [x for x in range(len(row[0])) if any(r[x] == colour for r in row)]


@pytest.mark.parametrize("frame,rows", [("matrix-voices-a", 6), ("matrix-seven", 5), ("matrix-seven-b", 1),
                                        ("matrix-full-slot31-a", 8), ("matrix-default", 1)])
def test_matrix_marks_keep_their_gaps(frames, colours, frame, rows):
    """In every row drawn in its fields' colours, the mark's ink (subtle)
    keeps at least 4 px from the source's (the modulation colour, or a
    sound's for S1NOTE ... S4RTRG) and from what follows it; no row reaches
    past the right margin. `rows` is how many rows of the frame have the
    three fields in their colours (page B's VIA "--" takes the mark's)."""
    img = ppm(frames / f"{frame}.ppm")
    base, mark = colours["base"], colours["subtle"]
    srcs = {colours["foam"]} | {colours[s] for s in P.SOUNDS}
    checked = 0
    for r in range(9):
        y = ROW_Y0 + r * ROW_PITCH
        row = img[y:y + ROW_H]
        if row[0][0] != base:                  # the selected row, on the selection's bar
            continue
        assert all(p == base for line in row for p in line[RIGHT:]), (frame, r)
        m = ink_columns(row, mark)
        if not m or m[-1] - m[0] > 8:          # no mark, or a row in subtle whole (off, empty)
            continue
        before = [x for x in range(m[0]) if any(line[x] in srcs for line in row)]
        after = [x for x in range(m[-1] + 1, len(row[0]))
                 if any(line[x] not in (base, mark) for line in row)]
        if not before or not after:
            continue
        assert m[0] - before[-1] - 1 >= 4, (frame, r, before[-1], m)
        assert after[0] - m[-1] - 1 >= 4, (frame, r, m, after[0])
        checked += 1
    assert checked == rows, (frame, checked)


@pytest.mark.parametrize("frame,rows", [("chain-slot3", 3), ("chain-07", None)])
def test_chains_arrow_keeps_its_gap_from_the_destination(frames, colours, frame, rows):
    """CHAIN's cable lines ("-100 >ENV3 Sustain"): the '>' (subtle) keeps
    at least 4 px from the destination's ink after it, as MATRIX's mark
    does, and no line reaches past the right margin. `rows` is how many
    unselected cable lines the frame has (None: at least one)."""
    img = ppm(frames / f"{frame}.ppm")
    base, mark = colours["base"], colours["subtle"]
    checked = 0
    for r in range(9):
        y = ROW_Y0 + r * ROW_PITCH
        row = img[y:y + ROW_H]
        if row[0][0] != base:                  # the selected line, on the selection's bar
            continue
        assert all(p == base for line in row for p in line[RIGHT:]), (frame, r)
        m = [x for x in ink_columns(row, mark) if x < 60]
        if not m or m[-1] - m[0] > 8:          # a node line: no arrow near the left
            continue
        before = [x for x in range(m[0]) if any(line[x] not in (base, mark) for line in row)]
        after = [x for x in range(m[-1] + 1, len(row[0])) if any(line[x] not in (base, mark) for line in row)]
        if not before or not after:
            continue
        assert after[0] - m[-1] - 1 >= 4, (frame, r, m, after[0])
        assert m[0] - before[-1] - 1 >= 4, (frame, r, before[-1], m)
        checked += 1
    assert checked == rows if rows is not None else checked >= 1, (frame, checked)


def test_the_six_character_source_row_reads_apart(frames, colours):
    """The audit's case: S2RTRG into ENV4's gate, its mark 4 px clear of the
    G and of the E, on page A, the amount ending at the right margin."""
    img = ppm(frames / "matrix-voices-a.ppm")
    base = colours["base"]
    y = ROW_Y0 + 4 * ROW_PITCH                   # the fifth row: "S2RTRG>ENV4 Gate +100"
    row = img[y:y + ROW_H]
    nova = ink_columns(row, colours["nova"])
    assert nova and nova[0] < 20, nova            # the "S2" in Sound 2's colour
    m = ink_columns(row, colours["subtle"])
    src = ink_columns(row, colours["foam"])
    dst = [x for x in ink_columns(row, colours["text"]) if x > m[-1]]
    assert m[0] - [x for x in src if x < m[0]][-1] - 1 >= 4
    assert dst[0] - m[-1] - 1 >= 4
    assert dst[-1] == RIGHT - 1 or dst[-1] >= RIGHT - 2, dst[-1]   # "+100" ends at the margin
    assert all(p == base for line in row for p in line[RIGHT:])


ROWS_TOP, BOTTOM_Y = 68, 216         # under FX mode's context line; the bottom bar


def ink(img, colour, top, bottom):
    return sum(p == colour for line in img[top:bottom] for p in line)


def test_a_refused_cable_marks_nothing(frames, colours):
    """Only a live cable marks its destination (the label in the
    modulation colour and the bracket): M1's Mix, reached by one cable per
    voice, which is refused (an effect is mono; MATRIX's `!`), is drawn as
    any other row; the same cable made global marks it."""
    foam = colours["foam"]
    assert ink(ppm(frames / "fx-voice-refused-m1.ppm"), foam, ROWS_TOP, BOTTOM_Y) == 0
    assert ink(ppm(frames / "fx-voice-global-m1.ppm"), foam, ROWS_TOP, BOTTOM_Y) > 0


def test_glo_shows_memory_as_a_percentage_red_past_the_budget(frames, colours):
    """GLO's RAM line is the meter's percentage (never kilobytes, owner
    2026-10-06), in the refusal colour past 100 % as the meter is, and in
    text below it."""
    love, text = colours["love"], colours["text"]
    line = (28 + 2 * 23, 28 + 2 * 23 + 18)       # the third line: Rate, Block, RAM
    over, under = ppm(frames / "multi-global-over.ppm"), ppm(frames / "multi-global.ppm")
    assert ink(over, love, *line) > 0 and ink(under, love, *line) == 0
    assert ink(under, text, *line) > 0
