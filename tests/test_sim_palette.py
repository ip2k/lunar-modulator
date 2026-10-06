"""The virtual FM-1's palette (sim/web/PALETTE.md): the screen's tokens and
roles (src/fm1_look.h) and the page's (www/style.css) agree, every colour
keeps its contrast after the RGB565 round trip as app.js expands it, the
colours that mean different things stay apart in CIEDE2000, the four sound
colours stay apart under simulated colour-vision deficiencies, and each role
has one colour (sim/web/tools/palette.py). Also: the colour science itself,
against the audit's figures (notes/2026-10-06-ui-audit.md §3) and published
test values, and that the checker catches what it is meant to.
"""
import re
import subprocess
import sys

import pytest

from tests.engine_helpers import ROOT

sys.path.insert(0, str(ROOT / "sim" / "web" / "tools"))
import palette as P  # noqa: E402

SIM = ROOT / "sim" / "web"


@pytest.fixture(scope="module")
def files():
    return P.load(ROOT)


def test_every_rule_holds(files):
    assert P.check(*files) == []


def test_the_command_line_checks(files):
    res = subprocess.run([sys.executable, str(SIM / "tools" / "palette.py"), str(ROOT)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "every rule holds" in res.stdout


def test_palette_md_carries_the_report(files):
    """PALETTE.md's tables are the checker's report, word for word; rerun
    `palette.py --report` and paste it when the palette changes."""
    doc = (SIM / "PALETTE.md").read_text(encoding="utf-8")
    block = re.search(r"<!-- palette.py --report -->\n(.*?)<!-- end of report -->", doc, re.S)
    assert block, "PALETTE.md has no report block"
    assert block.group(1) == P.report(*files)


# ---- the colour science ----------------------------------------------------

def test_the_round_trip_is_app_js():
    """drawScreen's three lines, and Uint8ClampedArray's rounding (half to
    even); FM1_RGB565 keeps the top bits."""
    app = (SIM / "www" / "app.js").read_text(encoding="utf-8")
    assert "d[4 * i] = ((p >> 11) & 31) * 255 / 31;" in app
    assert "d[4 * i + 1] = ((p >> 5) & 63) * 255 / 63;" in app
    assert "d[4 * i + 2] = (p & 31) * 255 / 31;" in app
    tft = (SIM / "src" / "fm1_tft.h").read_text(encoding="utf-8")
    assert "((((r) & 0xF8) << 8) | (((g) & 0xFC) << 3) | ((b) >> 3))" in tft
    assert [P.u8_clamp(v) for v in (2.5, 3.5, 254.6, -3, 300, float("nan"))] == [2, 4, 255, 0, 255, 0]
    assert P.rgb565((0xff, 0xff, 0xff)) == 0xFFFF and P.expand565(0xFFFF) == (255, 255, 255)
    assert P.screen((0x90, 0x8c, 0xaa)) == (0x94, 0x8e, 0xad)   # subtle, 4.78:1 on surface


def test_the_audit_figures(files):
    """§3's contrast table, computed after the round trip, and its hue
    distances, computed on the sRGB values."""
    pal = P.palette(*files)

    def cr(a, b):
        return round(P.contrast(pal[a]["screen"], pal[b]["screen"]), 2)
    assert cr("text", "base") == 12.36 and cr("text", "highlight-med") == 7.62
    assert cr("subtle", "surface") == 4.78 and cr("subtle", "overlay") == 3.72
    assert cr("muted", "base") == 3.02 and cr("love", "overlay") == 4.02
    assert cr("pine", "highlight-med") == 2.68 and cr("iris", "base") == 7.58

    def de(a, b):
        return round(P.delta_e(pal[a]["page"], pal[b]["page"]), 1)
    assert (de("love", "rose"), de("iris", "subtle"), de("iris", "text")) == (13.1, 14.4, 16.9)


@pytest.mark.parametrize("lab1, lab2, want", [
    # Sharma, Wu and Dalal (2005), table 1: pairs 1, 7, 17, 25 and 34
    ((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
    ((50.0, 0.0, 0.0), (50.0, -1.0, 2.0), 2.3669),
    ((50.0, 2.5, 0.0), (73.0, 25.0, -18.0), 27.1492),
    ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
    ((2.0776, 0.0795, -1.1350), (0.9033, -0.0636, -0.5514), 0.9082),
])
def test_ciede2000_matches_sharma(lab1, lab2, want):
    assert P.ciede2000(lab1, lab2) == pytest.approx(want, abs=1e-4)
    assert P.ciede2000(lab2, lab1) == pytest.approx(want, abs=1e-4)


def test_oklch_round_trips(files):
    for name, c in P.palette(*files).items():
        assert P.oklch_rgb(*P.oklch(c["page"])) == c["page"], name
    assert P.oklch_rgb(0.9, 0.4, 150) is None   # far outside sRGB
    # Ottosson's reference: white is L 1, C 0
    L, C, _ = P.oklch((255, 255, 255))
    assert L == pytest.approx(1.0, abs=1e-4) and C == pytest.approx(0.0, abs=1e-4)


def test_machado_keeps_greys_and_moves_hues():
    for kind in P.MACHADO:
        for g in (0, 64, 128, 255):
            assert all(abs(v - g) <= 1 for v in P.simulate((g, g, g), kind)), kind
    red, green = (220, 40, 40), (40, 160, 40)
    assert P.delta_e(P.simulate(red, "deuteranopia"), P.simulate(green, "deuteranopia")) < \
        0.5 * P.delta_e(red, green)


def test_the_swatch_draws(files):
    px = P.swatch(*files)
    assert len(px) == 240 and all(len(row) == 240 for row in px)
    pal = P.palette(*files)
    for s in P.SOUNDS:
        assert any(pal[s]["screen"] in row for row in px), s


# ---- the checker fails where it should -------------------------------------

def _fails(header, css, needle):
    out = P.check(header, css)
    assert any(needle in f for f in out), out
    return out


def test_it_catches_the_files_disagreeing(files):
    header, css = files
    _fails(header, css.replace("--lunar-nova: #ef8a4a;", "--lunar-nova: #ef8a4b;"), "nova")
    _fails(header.replace("#define LUNAR_COMET", "#define LUNAR_COMET_X"), css, "--lunar-comet")
    _fails(header.replace("#define RP_ROSE", "#define RP_PINE FM1_RGB565(0x3e, 0x8f, 0xb0)\n"
                                             "#define RP_ROSE"), css, "RP_PINE")


def test_it_catches_a_broken_rule(files, monkeypatch):
    header, css = files
    # a sound colour moved next to love
    monkeypatch.setitem(P.DERIVED, "nova", (0.70, 0.15, 10))
    nova = P.screen(P.oklch_rgb(0.70, 0.15, 10))
    hexa = "%02x%02x%02x" % nova
    h2 = re.sub(r"#define LUNAR_NOVA FM1_RGB565\([^)]*\)",
                "#define LUNAR_NOVA FM1_RGB565(0x%s, 0x%s, 0x%s)" % (hexa[:2], hexa[2:4], hexa[4:]), header)
    c2 = css.replace("--lunar-nova: #ef8a4a;", f"--lunar-nova: #{hexa};")
    _fails(h2, c2, "love-nova")


def test_it_catches_a_role_out_of_place(files):
    header, css = files
    _fails(header.replace("#define C_CONTEXT RP_ROSE", "#define C_CONTEXT RP_GOLD"), css, "C_CONTEXT")
    _fails(header, css.replace("--focus: var(--select);", "--focus: var(--held);"), "--focus")
    _fails(header, css.replace(".help dt { font-weight: 600; color: var(--accent); }",
                               ".help dt { font-weight: 600; color: var(--rp-gold); }"), "var(--rp-gold)")
    _fails(header, css.replace("--held: var(--rp-gold);", "--held: var(--rp-iris);"), "--held")


def test_it_wants_a_reason_for_a_close_pair(files, monkeypatch):
    monkeypatch.delitem(P.JUSTIFIED, ("foam", "nebula"))
    _fails(*files, "foam-nebula")


# ---- the project's own token names -----------------------------------------

# The project's short form is "Lunar" (CLAUDE.md, the name): its own hues
# are LUNAR_* in the header and --lunar-* on the page. The names they had,
# by the project's two-letter initials (_OLD, spelt in pieces so that the
# tree never holds them), stay out of sim/web: the review's git grep
# pattern, upper case for the macros and lower case for the stylesheet.
_OLD = "L" + "M"
_OLD_TOKEN = re.compile(rf"(?<![A-Za-z0-9_])(?:{_OLD}_|{_OLD.lower()}-)|--{_OLD.lower()}-")
_TEXT = {".c", ".h", ".css", ".js", ".mjs", ".html", ".md", ".py", ".sh", ".mk", ".json", ".txt"}


def test_no_old_token_names_in_the_simulator():
    seen, hits = 0, []
    for path in sorted(SIM.rglob("*")):
        if not path.is_file() or path.suffix not in _TEXT or "third_party" in path.parts:
            continue
        seen += 1
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            hits += [f"{path.relative_to(ROOT)}:{lineno}: {m}" for m in _OLD_TOKEN.findall(line)]
    assert seen > 20, seen
    assert hits == [], hits


def test_the_old_token_pattern_catches_both_forms():
    old, low = _OLD, _OLD.lower()
    assert len(_OLD_TOKEN.findall(f"#define {old}_NOVA x; color: var(--{low}-nova); .{low}-x")) == 3
    assert _OLD_TOKEN.findall(f"#define LUNAR_NOVA x; --lunar-nova; HE{old}_X; -{low}\n") == []
