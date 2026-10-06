"""The manual's diagrams (manual/diagrams/, tools/manual/diagrams.py).

Standard library only: the layout is pure Python, so every check runs
everywhere. The committed SVGs must be what the sources give today, and no
drawing may let a word touch another word, a box, a line or the edge.
"""
import importlib.util
import itertools
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "manual"))

import diagram_check  # noqa: E402
import diagram_metrics  # noqa: E402
import diagram_theme as theme  # noqa: E402
import diagrams  # noqa: E402

SOURCES = diagrams.sources()


def test_there_are_diagrams():
    assert {s.stem for s in SOURCES} >= {"signal-flow", "modulation", "per-voice", "recipes",
                                         "effect-chain", "transport", "launch", "arpeggiator"}


@pytest.mark.parametrize("src", SOURCES, ids=lambda p: p.stem)
def test_committed_svg_is_current(src):
    _d, svg = diagrams.build(src)
    out = src.with_suffix(".svg")
    assert out.is_file(), f"no {out.name}: run tools/manual/diagrams.py --write"
    assert out.read_text(encoding="utf-8") == svg, \
        f"{out.name} is stale: run tools/manual/diagrams.py --write"


@pytest.mark.parametrize("src", SOURCES, ids=lambda p: p.stem)
def test_nothing_touches(src):
    _d, svg = diagrams.build(src)
    assert diagram_check.check(svg) == []


@pytest.mark.parametrize("src", SOURCES, ids=lambda p: p.stem)
def test_layout_is_deterministic(src):
    assert diagrams.build(src)[1] == diagrams.build(src)[1]


@pytest.mark.parametrize("src", SOURCES, ids=lambda p: p.stem)
def test_svg_carries_its_own_styles(src):
    """Presentation attributes only (no <style>, no class), the theme's
    colours only, and the words a reader needs."""
    d, svg = diagrams.build(src)
    assert "<style" not in svg and "class=" not in svg
    allowed = {c for r in theme.THEME.roles.values() for c in (r.stroke, r.fill, r.wash, r.text)}
    allowed |= {theme.THEME.page, theme.THEME.ink}
    assert set(re.findall(r"#[0-9a-f]{6}", svg)) <= allowed
    assert f"<title>{d.title}</title>" in svg
    assert d.caption and d.alt and len(d.alt) > len(d.caption) / 2


def test_text_is_legible_in_print():
    """At the manual's scale a diagram's smallest words are at least 6.5 pt in
    the A5 book (a 118 mm column) and no diagram is shrunk below that."""
    column_pt = 118 / 25.4 * 72
    for src in SOURCES:
        _d, svg = diagrams.build(src)
        width = float(svg.split("viewBox='")[1].split("'")[0].split()[2])
        scale = column_pt * diagrams.view_width(svg) / 100 / width
        sizes = {float(s) for s in re.findall(r"font-size='([\d.]+)'", svg)}
        assert min(sizes) * scale >= 6.5, (src.stem, min(sizes) * scale)


def test_every_diagram_fits_a_page():
    """In the A5 book a diagram and its caption share a page: the drawing is
    at most 150 mm tall (the text block is 175 mm)."""
    for src in SOURCES:
        _d, svg = diagrams.build(src)
        w, h = (float(v) for v in svg.split("viewBox='")[1].split("'")[0].split()[2:4])
        tall = 118 * diagrams.view_width(svg) / 100 * h / w
        assert tall <= 150, (src.stem, round(tall))


# ---- the checker finds what it should --------------------------------------------

HEAD = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 100'>"
        "<rect data-kind='bg' x='0' y='0' width='200' height='100' fill='#fff'/>")


def text(x, y, s, owner="a"):
    return (f"<text x='{x}' y='{y}' font-size='12' font-weight='400' text-anchor='start' "
            f"data-owner='{owner}'>{s}</text>")


def test_checker_accepts_clear_space():
    svg = HEAD + text(20, 30, "Clear") + text(20, 70, "Also clear", "b") + "</svg>"
    assert diagram_check.check(svg) == []


def test_checker_finds_words_on_words():
    svg = HEAD + text(20, 30, "Overlap") + text(40, 33, "here", "b") + "</svg>"
    assert any("apart" in p for p in diagram_check.check(svg))


def test_checker_finds_words_on_lines():
    svg = (HEAD + text(20, 30, "Crossed") +
           "<path data-kind='edge' data-id='e0' data-from='x' data-to='y' d='M10 26 L180 26' "
           "stroke='#000' stroke-width='1.5' fill='none'/></svg>")
    assert any("from the line" in p for p in diagram_check.check(svg))


def test_checker_finds_words_near_an_outline():
    svg = (HEAD + "<rect data-kind='node' data-id='n' x='18' y='18' width='60' height='16' "
           "stroke='#000' stroke-width='1' fill='none'/>" + text(20, 30, "Tight", "n") + "</svg>")
    assert any("outline of node n" in p for p in diagram_check.check(svg))


def test_checker_finds_words_past_the_edge():
    svg = HEAD + text(170, 30, "Clipped") + "</svg>"
    assert any("edge" in p for p in diagram_check.check(svg))


def test_checker_finds_a_line_through_a_box():
    svg = (HEAD + "<rect data-kind='node' data-id='n' x='60' y='40' width='40' height='20' "
           "stroke='#000' stroke-width='1' fill='none'/>"
           "<path data-kind='edge' data-id='e0' data-from='a' data-to='b' d='M10 50 L190 50' "
           "stroke='#000' stroke-width='1' fill='none'/></svg>")
    assert any("from kind node n" in p or "from node n" in p for p in diagram_check.check(svg))


def test_checker_finds_lines_along_lines():
    svg = (HEAD + "<path data-kind='edge' data-id='e0' data-from='a' data-to='b' d='M10 50 L190 50' "
           "stroke='#000' stroke-width='1' fill='none'/>"
           "<path data-kind='edge' data-id='e1' data-from='c' data-to='d' d='M50 51 L150 51' "
           "stroke='#000' stroke-width='1' fill='none'/></svg>")
    assert any("runs" in p for p in diagram_check.check(svg))


def test_checker_finds_boxes_on_boxes():
    svg = (HEAD + "<rect data-kind='node' data-id='a' x='10' y='10' width='50' height='30' fill='none'/>"
           "<rect data-kind='node' data-id='b' x='58' y='20' width='50' height='30' fill='none'/></svg>")
    assert any("boxes a and b" in p for p in diagram_check.check(svg))


# ---- the source format refuses what it cannot draw ------------------------------------

def test_a_line_to_itself_is_refused(tmp_path):
    src = tmp_path / "loop.toml"
    src.write_text("title = 't'\ncaption = 'c'\nalt = 'a'\n"
                   "[[node]]\nid = 'a'\nlabel = 'A'\ncol = 0\nrow = 0\n"
                   "[[edge]]\nfrom = 'a'\nto = 'a'\n", encoding="utf-8")
    with pytest.raises(ValueError, match="itself"):
        diagrams.load(src)


def test_unknown_characters_are_refused(tmp_path):
    src = tmp_path / "glyph.toml"
    src.write_text("title = 't'\ncaption = 'c'\nalt = 'a'\n"
                   "[[node]]\nid = 'a'\nlabel = 'A ☃'\ncol = 0\nrow = 0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="widths"):
        diagrams.load(src)


# ---- the colours -------------------------------------------------------------------------

def test_theme_starts_from_the_manuals_palette():
    css = (ROOT / "manual" / "theme" / "manual.css").read_text(encoding="utf-8")
    assert dict(re.findall(r"--rp-([a-z-]+):\s*(#[0-9a-f]{6})", css)) == theme.DAWN


def test_written_colours_are_the_derived_ones():
    """DERIVED is what derive() gives, to within one step of a channel."""
    got = theme.derive()
    assert set(got) == set(theme.DERIVED)
    for role, colours in theme.DERIVED.items():
        for want, have in zip(colours, got[role]):
            assert max(abs(a - b) for a, b in zip(theme.hex_rgb(want), theme.hex_rgb(have))) <= 1, role


def test_role_colours_carry_text_and_marks():
    """Every role's tone reads as text (4.5:1) on Dawn's base and surface and on
    its own fills; every stroke reads as a mark (3:1) there; ink reads on every
    fill."""
    t = theme.THEME
    pages = (theme.DAWN["base"], theme.DAWN["surface"])
    for name, role in t.roles.items():
        for bg in pages + (role.fill, role.wash):
            assert theme.contrast(role.stroke, bg) >= theme.MARK_MIN, (name, bg)
            assert theme.contrast(role.text, bg) >= theme.TEXT_MIN, (name, bg)
            assert theme.contrast(t.ink, bg) >= 7.0, (name, bg)
    for role in theme.ROLE_TOKENS:
        assert theme.contrast(t.roles[role].stroke, theme.DAWN["base"]) >= theme.TEXT_MIN


def test_role_hues_are_dawns():
    for role, token in theme.ROLE_TOKENS.items():
        assert abs(theme.oklch(theme.THEME.roles[role].stroke)[2] - theme.oklch(theme.DAWN[token])[2]) < 4


def test_sound_hues_are_the_screens():
    for role, (_name, h) in theme.SOUND_HUES.items():
        hue = theme.oklch(theme.THEME.roles[role].stroke)[2]
        assert min(abs(hue - h), 360 - abs(hue - h)) < 3, role


def _palette_module():
    path = ROOT / "sim" / "web" / "tools" / "palette.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("sim_palette", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod if hasattr(mod, "DERIVED") else None


def test_sound_hues_match_the_palette_lane():
    pal = _palette_module()
    if pal is None:
        pytest.skip("sim/web/tools/palette.py (palette v2) is not in this tree")
    for role, (name, h) in theme.SOUND_HUES.items():
        assert pal.DERIVED[name][2] == h, name
    assert [theme.SOUND_HUES[r][0] for r in ("s1", "s2", "s3", "s4")] == list(pal.SOUNDS)


def test_sound_colours_stay_apart():
    """As palette.py asks of the screen's: 20 CIEDE2000 between any two sound
    colours, and 9 under each colour-vision deficiency."""
    pal = _palette_module()
    if pal is None:
        pytest.skip("sim/web/tools/palette.py (palette v2) is not in this tree")
    tones = {r: theme.hex_rgb(theme.THEME.roles[r].stroke) for r in theme.SOUND_HUES}
    for a, b in itertools.combinations(tones, 2):
        assert pal.delta_e(tones[a], tones[b]) >= pal.SOUND_MIN, (a, b)
        for kind in pal.MACHADO:
            assert pal.delta_e(pal.simulate(tones[a], kind), pal.simulate(tones[b], kind)) >= pal.CVD_FLOOR


def test_metrics_know_every_character_in_the_sources():
    for src in SOURCES:
        d = diagrams.load(src)      # refuses any label it cannot measure
        words = [ln.text for n in d.nodes.values() for ln in n.lines]
        words += [ln.text for e in d.edges for ln in e.label] + [ln.text for g in d.groups for ln in g.label]
        assert all(diagram_metrics.missing(w) == [] for w in words)
