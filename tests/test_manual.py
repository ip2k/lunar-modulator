"""The user manual's build (tools/manual/, manual/).

Runs without the manual's own dependencies where it can: the palette, the
reference tables, the sequencer parsing and the figures need only the
standard library. The full build needs Markdown (manual/requirements.txt)
and is skipped without it; the Pages workflow runs it on every change.
"""
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from tests.engine_helpers import renderer  # noqa: F401  (fixture)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "manual"))

import figures  # noqa: E402
import policy  # noqa: E402
import reference  # noqa: E402

# Rosé Pine Dawn as published (rosepinetheme.com/palette and
# rose-pine/rose-pine-palette palette.json, checked 2026-10-01).
DAWN = {
    "base": "#faf4ed", "surface": "#fffaf3", "overlay": "#f2e9e1", "muted": "#9893a5",
    "subtle": "#797593", "text": "#464261", "love": "#b4637a", "gold": "#ea9d34",
    "rose": "#d7827e", "pine": "#286983", "foam": "#56949f", "iris": "#907aa9",
    "highlight-low": "#f4ede8", "highlight-med": "#dfdad9", "highlight-high": "#cecacd",
}


def css_tokens():
    css = (ROOT / "manual" / "theme" / "manual.css").read_text()
    return dict(re.findall(r"--rp-([a-z-]+):\s*(#[0-9a-f]{6})", css))


def luminance(hex_colour):
    c = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_palette_is_rose_pine_dawn():
    assert css_tokens() == DAWN


def test_text_colours_meet_wcag_aa():
    """Words are set only in text and pine; both reach 4.5:1 on every
    background the theme uses."""
    t = css_tokens()
    for fg in ("text", "pine"):
        for bg in ("base", "surface", "overlay", "highlight-low"):
            assert contrast(t[fg], t[bg]) >= 4.5, (fg, bg)


def test_figure_colours_come_from_the_palette():
    used = set(re.findall(r"#[0-9a-f]{6}", figures.panel_svg() + figures.edge_svg()))
    assert used <= set(DAWN.values())


def test_figures_are_well_formed():
    import xml.dom.minidom
    for draw, _caption, _alt in figures.FIGURES.values():
        xml.dom.minidom.parseString(draw())


def test_figures_match_the_simulator():
    """figures.py draws the panel from the simulator's measurements; keep them
    in step (sim/web/www/app.js, when the simulator is in the tree)."""
    app = ROOT / "sim" / "web" / "www" / "app.js"
    if not app.is_file():
        pytest.skip("sim/web is not in this tree")
    js = app.read_text()

    def floats(name):
        m = re.search(rf"const {name} = \[([^\]]*)\]", js)
        return [float(x) for x in re.findall(r"-?\d+\.?\d*", m.group(1))]

    assert floats("FN_X") == figures.FN_X
    assert floats("WHITE_STEPS") == figures.WHITE_STEPS
    for name, x, y in figures.KNOBS:
        assert re.search(rf"enc: '{name}', x: {x}, y: (ROW_TOP|{y})", js), name
    for row_y, ids in figures.FN_ROWS:
        quoted = ", ".join(f"'{i}'" for i in ids)
        assert f"y: {row_y:.2f}, ids: [{quoted}]" in js, row_y
    assert re.search(rf"WHITE_X0 = {figures.WHITE_X0}, WHITE_PITCH = {figures.WHITE_PITCH}", js)


FAKE_LIST = [
    {"id": "demo", "name": "Demo", "credits": "Tests (MIT)", "kind": "sound", "max_voices": 6,
     "params": [
         {"name": "Shape", "type": 1, "min": 0, "max": 2, "def": 1, "page": 0,
          "names": ["Saw", "Square", "Sine"]},
         {"name": "Tone", "type": 0, "min": -1, "max": 1, "def": 0, "page": 0},
         {"name": "Level", "type": 0, "min": 0, "max": 1, "def": 0.7, "page": 1},
         {"name": "Cutoff", "type": 0, "min": 20, "max": 18000, "def": 2000, "page": 1,
          "flags": ["smooth", "mod", "log"], "unit": "hz"},
         {"name": "Gain", "type": 0, "min": -12, "max": 12, "def": 0, "page": 1,
          "flags": ["smooth", "mod"], "unit": "db"}]},
    {"id": "verb", "name": "Verb", "credits": "Tests (MIT)", "kind": "audio_fx", "max_voices": 0,
     "params": [{"name": "Mode", "type": 1, "min": 0, "max": 1, "def": 0, "page": 0}]},
]


def test_engine_table_shows_pages_knobs_ranges_and_values():
    demo, verb = reference.parse_list(FAKE_LIST)
    out = reference.engine_table(demo)
    assert "<th scope='row'>Page 1</th><td>Shape</td><td>Tone</td>" in out
    assert "Page 2 · KNOB1" in out                       # Level opens page 2
    assert "List, 3 values" in out and "1 <span class='vname'>Square</span>" in out
    assert "−1 – 1" in out                               # a real minus sign
    assert "<span class='vnum'>2</span> Sine" in out
    # LOG (engine API v3) and the units fm1-render names
    assert "Continuous, logarithmic</td><td class='num nowrap'>20 – 18000 Hz</td>" in out
    assert "<td>Continuous</td><td class='num nowrap'>−12 – 12 dB</td><td class='num'>0 dB</td>" in out
    assert "6 voices" in out and "<code>demo</code>" in out
    assert reference.check_engine(demo) == []
    assert "appear here once" in reference.engine_table(verb)  # no names reported
    assert reference.check_engine(verb) == ["verb: Mode: fm1-render --list reports no value names"]


def test_engine_summary_links_described_engines():
    engines = reference.parse_list(FAKE_LIST)
    out = reference.engine_summary(engines, "sound", {"demo": "#demo"})
    assert "<a href='#demo'>Demo</a>" in out and "Verb" not in out


def test_sequencer_tables_skip_without_the_sequencer(tmp_path):
    assert reference.load_seq(tmp_path, None) is None


def test_sequencer_tables_from_the_header(tmp_path):
    inc, seq = tmp_path / "engines" / "include", tmp_path / "engines" / "seq"
    inc.mkdir(parents=True)
    seq.mkdir()
    (inc / "fm1_seq.h").write_text(
        "#define FM1_SEQ_PPQN 96u\n#define FM1_SEQ_TICKS_PER_STEP 24u\n"
        "#define FM1_SEQ_STEPS_PER_BAR 16u\n#define FM1_SEQ_MAX_STEPS 256u  /* 16 bars */\n"
        "#define FM1_SEQ_MAX_TRACKS 16u\n#define FM1_SEQ_BPM_X100_MIN 2000u\n"
        "#define FM1_SEQ_BPM_X100_MAX 30000u\n  uint8_t tracks;  /* 1..16; the FM-1 build uses 4..8 */\n")
    (seq / "seq_cmd.c").write_text('{ "play", FM1_SEQ_V_PLAY }, { "zap", FM1_SEQ_V_ZAP },\n')
    info = reference.load_seq(tmp_path, None)
    assert info.verbs == ["play", "zap"]
    glance = reference.seq_glance(info)
    assert "up to 16 bars" in glance and "20 – 300 BPM" in glance and "4 to 8" in glance
    warnings = []
    notes = {"verb": {"play": {"group": "Transport", "does": "Plays."},
                      "gone": {"group": "Transport", "does": "Removed."}}}
    verbs = reference.seq_verbs(info, notes, warnings)
    assert "Plays." in verbs and "Not described yet." in verbs
    assert len(warnings) == 2                              # zap undescribed, gone stale


def test_memory_reads_as_a_share_of_the_budget():
    """The manual shows memory only as a share of the FM-1's budget, never
    in bytes (owner, 2026-10-06), rounded up as the screen's meter rounds
    and "under 1 %" below one; the sequencer's table puts the instance
    without its Capture buffer in the first column, with it in the second."""
    assert reference.memory_share(387924, 387924) == "100\u00a0%"
    assert reference.memory_share(387925, 387924) == "101\u00a0%"
    assert reference.memory_share(3879, 387924) == "under 1\u00a0%"
    info = reference.SeqInfo({}, {}, [], {"tracks": {"8": 31880}, "no_capture": {"8": 28808}}, 387924)
    out = reference.seq_memory(info)
    assert "<td class='num'>8\u00a0%</td><td class='num'>9\u00a0%</td>" in out and "KB" not in out
    assert reference.seq_memory(reference.SeqInfo({}, {}, [], info.sizes, None)) == ""
    if (ROOT / "sim" / "web" / "src" / "fm1_app.h").is_file():
        assert reference.ram_budget(ROOT) > 0


MEMORY_IN_BYTES = re.compile(
    r"kilobyte|over budget|\d\s?K/\d|"
    r"\b(?:takes?|keeps? to|needs?)\s+(?:about |under |roughly |only )?[\d,.]+\s?(?:KB|K|kB|bytes|B)\b|"
    r"[\d,.]+\s?(?:KB|K|kB|bytes|B)\s+of\s+(?:the\s+)?(?:memory|RAM)\b(?! on the chip)",
    re.I)


def test_the_manual_never_gives_memory_in_bytes():
    """Memory a reader sees is a share of the FM-1's budget only (owner,
    2026-10-06): no chapter says an engine, effect or chain takes so many
    kilobytes or bytes, and no refusal reads "K over budget". Sizes of
    files and of the chip itself are not memory figures and may stay."""
    hits = [f"{p.name}:{n}: {m.group(0)}"
            for p in sorted((ROOT / "manual" / "chapters").glob("*.md"))
            for n, line in enumerate(p.read_text().splitlines(), 1)
            for m in MEMORY_IN_BYTES.finditer(line)]
    assert not hits, hits
    assert MEMORY_IN_BYTES.search("It takes under half a kilobyte.")
    assert MEMORY_IN_BYTES.search("PSX Verb takes about 131 KB of memory")
    assert MEMORY_IN_BYTES.search("the effect keeps to 64 KB of memory")
    assert not MEMORY_IN_BYTES.search("Files of up to 64 KB are read.")
    assert not MEMORY_IN_BYTES.search("578 KB of RAM on the chip")


def test_verb_descriptions_cover_the_code():
    """Every verb the sequencer parses is described, and nothing else."""
    if not (ROOT / "engines" / "seq" / "seq_cmd.c").is_file():
        pytest.skip("the sequencer is not in this tree")
    info = reference.load_seq(ROOT, None)
    notes = tomllib.loads((ROOT / "manual" / "data" / "seq-verbs.toml").read_text())
    assert sorted(info.verbs) == sorted(notes["verb"])
    order = notes["groups"]["order"]
    assert all(v["group"] in order for v in notes["verb"].values())


def test_sources_carry_no_private_names_or_forbidden_marks():
    for f in sorted((ROOT / "manual").rglob("*")):
        if f.is_file() and f.suffix in (".md", ".toml", ".html", ".css", ".txt"):
            assert policy.problems(f.read_text()) == [], f


def test_policy_catches_what_it_should():
    assert [why for _, why in policy.problems("ssh someone@10.0.0.7")] == [
        "a private network address", "a login to a machine"]
    assert policy.problems("log in as someone@192.168.0.2")
    assert policy.problems("open /Users/someone/x") and policy.problems("see box.lan")
    assert policy.problems("a Lunar Module") and not policy.problems("Lunar Modulator, v10.2")


def test_full_build(renderer, tmp_path):  # noqa: F811
    """The whole manual builds in strict mode: every directive resolves, every
    link and anchor exists, every feature section says where it runs."""
    pytest.importorskip("markdown")
    site = tmp_path / "site"
    res = subprocess.run([sys.executable, str(ROOT / "tools" / "manual" / "build.py"),
                          "--site", str(site), "--strict", "--renderer", str(renderer)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    manual = site / "manual"
    cfg = tomllib.loads((ROOT / "manual" / "manual.toml").read_text())
    for entry in cfg["chapter"] + cfg["backmatter"]:
        assert (manual / entry["file"].replace(".md", ".html")).is_file()
    assert (site / "index.html").is_file()
    index = (manual / "index-of-controls.html").read_text()
    assert "<kbd class='ctl'>SELECT</kbd>" in index and "Not described yet" not in index
    # A heading's smart apostrophe reaches the index as itself, not as
    # Python-Markdown's stash placeholder (the build also refuses one).
    assert "wzxhzdk" not in index
    # Each control's entry starts at its own section of the panel tour.
    assert ("<dt><kbd class='ctl'>SELECT</kbd></dt><dd><a class='xref home' "
            "href='03-panel-tour.html#knobs'>") in index
    # The firmware's screens come from the simulator's screenshots, when present.
    if (ROOT / "assets" / "screenshots" / "screen-params.png").is_file():
        assert (manual / "assets" / "screens" / "screen-params.png").is_file()
        assert "assets/screens/screen-params.png" in (manual / "03-panel-tour.html").read_text()
    engines = json.loads((manual / "reference.json").read_text())["engines"]
    ch5 = (manual / "05-sound-engines.html").read_text()
    for e in engines:
        if e["kind"] == "sound":
            assert f"data-engine='{e['id']}'" in ch5, e["id"]
    assert "Generated on" in (manual / "index.html").read_text()
