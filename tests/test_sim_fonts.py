"""The virtual FM-1's three text faces (sim/web/src/fm1_tft.h; audit D7):
MAIN, the hand-made 5 x 9 at x2, and Spleen 8 x 16 (MID) and 6 x 12 (SMALL)
at x1, vendored unmodified from fcambus/spleen 2.2.0
(sim/web/third_party/spleen/).

fm1-sim-render --font-check draws every character of every face and prints
it as drawn; these tests read the BDF files and font5x9.txt here, without
gen_font.py, and compare. They also check each face's metrics and logged
boxes, the 4 px layout rule between faces, and the multi-colour run (one
box, several colours) that MATRIX's columns need (audit L2).
"""
import hashlib
import json
import re
import subprocess

import pytest

from tests.engine_helpers import ROOT
from tests.test_sim_web import tools  # noqa: F401  (the native build of both tools)

SIM = ROOT / "sim" / "web"
SPLEEN = SIM / "third_party" / "spleen"
ASCII = range(0x20, 0x7F)
MARGINS = 240 - 2 * 6                       # between the screen's 6 px margins

# Git blob hashes of Spleen 2.2.0 (tag 2.2.0, commit 0493c34e, 2026-02-01):
# the files are upstream's, byte for byte.
SPLEEN_FILES = {
    "LICENSE": "6928cd0fc323641bac9f0abc1268ed063d782edb",
    "spleen-6x12.bdf": "26dc8b5adf89db6d23ded1403c49d723435e0f2c",
    "spleen-8x16.bdf": "ebd9ed0562b9132a15862454bc82ffcdc05da7a2",
}

# face: (advance, box height, ink width, cap height, baseline, characters a
# line, line pitch with the 4 px gap)
METRICS = {
    "MAIN": (12, 18, 10, 14, 14, 19, 22),
    "MID": (8, 14, 8, 10, 11, 28, 18),
    "SMALL": (6, 12, 6, 8, 9, 38, 16),
}


def blob(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def bdf_cells(path):
    """Each character's cell as rows of '#'/'.', ascent rows above the
    baseline: read here, independently of gen_font.py."""
    text = path.read_text(encoding="ascii")
    w, h, _, y0 = map(int, re.search(r"^FONTBOUNDINGBOX (.+)$", text, re.M).group(1).split())
    ascent = h + y0
    cells = {}
    for m in re.finditer(r"^ENCODING (\d+)$(.*?)^BITMAP$(.*?)^ENDCHAR$", text, re.M | re.S):
        bw, bh, bx, by = map(int, re.search(r"^BBX (.+)$", m.group(2), re.M).group(1).split())
        grid = [["."] * w for _ in range(h)]
        for r, hexrow in enumerate(m.group(3).split()):
            bits = bin(int(hexrow, 16))[2:].zfill(4 * len(hexrow))
            for col in range(bw):
                if bits[col] == "1":
                    grid[ascent - by - bh + r][bx + col] = "#"
        cells[int(m.group(1))] = ["".join(row) for row in grid]
    return cells


def main_cells():
    """font5x9.txt's glyphs at x2, as MAIN draws them."""
    cells, cur = {}, None
    for line in (SIM / "tools" / "font5x9.txt").read_text().splitlines():
        if line.startswith("= "):
            name = line[2:]
            cur = cells.setdefault(ord(" " if name == "space" else name), [])
        elif cur is not None and line.strip():      # '#' starts comments only before the glyphs
            cur += ["".join(ch * 2 for ch in line)] * 2
    return {c: rows + ["." * 10] * (18 - len(rows)) for c, rows in cells.items()}


@pytest.fixture(scope="module")
def check(tools):  # noqa: F811
    res = subprocess.run([str(tools["sim"]), "--font-check"], capture_output=True, text=True)
    assert res.returncode == 0, res.stdout[-3000:] + res.stderr
    out = json.loads(res.stdout)
    assert out["errors"] == 0
    return out


def face(check, name):
    return next(f for f in check["fonts"] if f["name"] == name)


def test_spleen_is_vendored_unmodified_with_its_licence():
    for name, want in SPLEEN_FILES.items():
        assert blob((SPLEEN / name).read_bytes()) == want, name
    licence = (SPLEEN / "LICENSE").read_text()
    assert "Copyright (c) 2018-2026, Frederic Cambus" in licence
    assert "Redistributions in binary form must reproduce" in licence
    upstream = (SPLEEN / "UPSTREAM.md").read_text()
    assert "2.2.0" in upstream and "0493c34e22791824767c618fed42c434b477662c" in upstream
    for header in ("fm1_font_mid.h", "fm1_font_small.h"):
        head = (SIM / "src" / header).read_text()[:700]
        assert "do not edit" in head and "Frederic Cambus" in head and "BSD 2-Clause" in head
    # The page names Spleen and serves its licence with the module.
    page = (SIM / "www" / "index.html").read_text(encoding="utf-8")
    assert "Spleen" in page and 'href="fonts/spleen/LICENSE"' in page
    assert (SIM / "www" / "fonts" / "spleen" / "LICENSE").read_bytes() == (SPLEEN / "LICENSE").read_bytes()


def test_the_tables_cost_what_upstream_md_says():
    """Each face's flash cost: one byte a glyph row, 95 glyphs."""
    res = subprocess.run(["python3", str(SIM / "tools" / "gen_font.py"), "--sizes"],
                         capture_output=True, text=True, check=True)
    assert json.loads(res.stdout) == {"MAIN": 95 * 9, "MID": 95 * 14, "SMALL": 95 * 12}
    upstream = (SPLEEN / "UPSTREAM.md").read_text()
    assert "1,330" in upstream and "1,140" in upstream and "855" in upstream


@pytest.mark.parametrize("name,bdf", [("MID", "spleen-8x16.bdf"), ("SMALL", "spleen-6x12.bdf")])
def test_spleen_glyphs_are_drawn_as_the_bdf_has_them(check, name, bdf):
    """Every printable ASCII character, pixel for pixel, inside its box; the
    rows of the cell left out of the box are blank in every one of them."""
    f = face(check, name)
    cells = bdf_cells(SPLEEN / bdf)
    inked = [y for c in ASCII for y, row in enumerate(cells[c]) if "#" in row]
    top = min(inked)
    assert max(inked) - top + 1 == f["height"]
    for c in ASCII:
        cell = cells[c]
        assert f["glyphs"][c - 0x20] == [row[:f["ink_w"]] for row in cell[top:top + f["height"]]], chr(c)
        assert "#" not in "".join(cell[:top] + cell[top + f["height"]:]), chr(c)
        assert "#" not in "".join(row[f["ink_w"]:] for row in cell), chr(c)


def test_main_glyphs_are_font5x9_at_twice_the_size(check):
    f = face(check, "MAIN")
    cells = main_cells()
    for c in ASCII:
        assert f["glyphs"][c - 0x20] == cells[c], chr(c)


@pytest.mark.parametrize("name", list(METRICS))
def test_each_faces_metrics(check, name):
    """Advance, box, capitals and baseline from the characters as drawn, and
    the characters a line holds between the 6 px margins (fm1_look.h's
    LINE_CHARS, MID_LINE_CHARS, SMALL_LINE_CHARS)."""
    f = face(check, name)
    adv, height, ink_w, cap_h, baseline, line_chars, pitch = METRICS[name]
    assert (f["advance"], f["height"], f["ink_w"], f["cap_h"], f["baseline"],
            f["line_chars"], f["line_pitch"]) == METRICS[name]
    capital = [y for y, row in enumerate(f["glyphs"][ord("H") - 0x20]) if "#" in row]
    assert (max(capital) + 1, max(capital) - min(capital) + 1) == (baseline, cap_h)
    assert line_chars == max(n for n in range(1, 60) if (n - 1) * adv + ink_w <= MARGINS)
    assert pitch == height + 4


@pytest.mark.parametrize("name", list(METRICS))
def test_a_runs_box_is_what_its_face_can_paint(check, name):
    """The logged box holds every pixel a character paints and nothing
    outside it is touched; some character reaches each of its four edges, so
    the box is no larger than the face. Widths, fit counts and the one-box
    log agree with FM1_TFT_RUN_W."""
    f = face(check, name)
    assert (f["box_errors"], f["outside"], f["width_errors"], f["fit_errors"]) == (0, 0, 0, 0)
    ink = [(y, x) for g in f["glyphs"] for y, row in enumerate(g) for x, v in enumerate(row) if v == "#"]
    assert min(y for y, _ in ink) == 0 and max(y for y, _ in ink) == f["height"] - 1
    assert min(x for _, x in ink) == 0 and max(x for _, x in ink) == f["ink_w"] - 1


def test_the_4px_rule_is_the_same_for_every_face(check):
    """Two runs in any two faces, or a run and a graphic, side by side or one
    above the other: 3 px apart is a fault, 4 px is not."""
    gaps = check["gaps"]
    assert len(gaps) == 3 * 4 * 2 * 2
    for g in gaps:
        assert g["faults"] == (1 if g["gap"] < 4 else 0), g


@pytest.mark.parametrize("name", list(METRICS))
def test_runs_cut_short_off_screen_and_in_several_colours(check, name):
    """A run cut by max_chars is a fault; a box one pixel past the right edge
    is, one at it is not. MATRIX's row as spans (source in foam, mark in
    subtle, destination and amount in text, and a NULL span) is one box,
    each character in its span's colour; cut at six characters it is one
    truncated run. MAIN in a face draws what fm1_tft_text draws at x2."""
    r = next(r for r in check["runs"] if r["font"] == name)
    adv, _, ink_w, *_ = METRICS[name]
    assert r["cut_faults"] == 1 and r["edge_faults"] == [0, 1]
    assert (r["span_boxes"], r["span_faults"], r["colour_errors"], r["painted"]) == (1, 0, 0, 17)
    assert r["span_w"] == r["span_want_w"] == 18 * adv + ink_w
    assert (r["cut6"], r["w6"]) == (1, 5 * adv + ink_w)
    assert r["main_same"] == 1


@pytest.mark.parametrize("name", list(METRICS))
def test_a_runs_leads_are_narrow_gaps_inside_it(check, name):
    """fm1_tft_span_text_lead: the same row with 4 px before the mark and 4
    before the destination is still one box, 8 px wider, each character in
    its span's colour where the leads put it; a lead before the first span,
    a NULL one or one max_chars leaves out adds nothing."""
    r = next(r for r in check["runs"] if r["font"] == name)
    adv, _, ink_w, *_ = METRICS[name]
    assert r["lead_w"] == r["lead_box_w"] == 18 * adv + ink_w + 8
    assert (r["lead_boxes"], r["lead_colour_errors"], r["lead_painted"]) == (1, 0, 17)
    assert r["lead_w4"] == 3 * adv + ink_w and r["lead_w6"] == 5 * adv + ink_w + 8


def test_the_font_sheet_passes_the_layout_check(tools, tmp_path):  # noqa: F811
    """Both Spleen faces' characters and a few names on one screen."""
    out = tmp_path / "fonts.ppm"
    res = subprocess.run([str(tools["sim"]), "--font-sheet", str(out)], capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
    summary = json.loads(res.stdout)
    assert summary["faults"] == 0 and summary["boxes"] <= 96 and summary["bottom"] <= 240
    assert out.stat().st_size == 15 + 240 * 240 * 3
