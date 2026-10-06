"""List popups in the virtual FM-1 (sim/web): PRESETS, ALGORITHM (the
sound's first list parameter, or in FX mode the slot's effect), a knob on
a list parameter, SHIFT + PRESETS, SHIFT + 16's quantize, the modulation
kind picker and MATRIX's destination picker show as many entries as the
screen's middle holds in the face each list is drawn in (fm1_panel.h,
audit D9): MAIN six of 18 characters, MID eight of 27, SMALL nine of 36,
under the list's title and the chosen entry's place, the chosen one on the
third row where it can be and the window never past either end
(fm1_list_first). Entries go by their full names where an engine only
offers a short form ("Phase Distortion" for "PhaseDist"). Until 2026-10-06
they showed three lines, then six in MAIN.

The harness's summary has the window: `popup` its entries, `popup_list`
the title, the first entry shown, the list's length and the marked line
(null for a message), `popup_face` and `popup_rows` the face and the most
entries it shows; a message has `popup_tone` (a refusal or not) and, when
it draws as a banner over the page (audit L1), `popup_banner`.
`fm1-sim-render --screens` draws every entry of every list and checks
each screen's layout (tests/test_sim_web.py).
"""
import json
import subprocess

import pytest

from tests.test_sim_web import run, tools  # noqa: F401  (the native build)

ROWS = {"MAIN": 6, "MID": 8, "SMALL": 9}
CHARS = {"MAIN": 18, "MID": 27, "SMALL": 36}
PICKER_ROWS = ROWS["MID"]   # fm1_mod_ui fills a picker's window for the MID face the app draws it in

# The full names the lists show for an engine's short forms (fm1_app.c's
# kFullNames, each from the engine's own source).
FULL = {
    "Comp": "Compressor", "Master Sat": "Master Saturation", "EQ": "Equaliser",
    "Transient": "Transient Shaper", "PhaseDist": "Phase Distortion", "Terrain": "Wave Terrain",
    "Chip": "Chiptune", "Shaper": "Waveshaping", "2-op FM": "Two-Operator FM",
    "Str Machine": "String Machine", "Filt Noise": "Filtered Noise", "Saw/Sqr": "Saw/Square",
    "Sine/Tri": "Sine/Triangle", "Sqr Sub": "Square Sub", "Sqr Sync": "Square Sync",
    "3x Saw": "Triple Saw", "3x Sqr": "Triple Square", "3x Tri": "Triple Triangle",
    "3x Sine": "Triple Sine", "3x Ring": "Triple Ring Mod", "LP Flt": "LP Filter",
    "Peak Flt": "Peak Filter", "BP Flt": "BP Filter", "HP Flt": "HP Filter", "FB FM": "Feedback FM",
    "Chaos FM": "Chaotic Feedback FM", "Wavetbl": "Wavetables", "Twin Peak": "Twin Peaks Noise",
    "Clk Noise": "Clocked Noise", "Granular": "Granular Cloud", "Particle": "Particle Noise",
    "Digital": "Digital Modulation", "Studio S": "Studio Small", "Studio M": "Studio Medium",
    "Studio L": "Studio Large", "SK Mixed": "Sallen-Key Mixed",
    # Sophie's and Drums' pads by General MIDI's drum names, and the arp's.
    "7 Closed HH": "7 Closed Hi-Hat", "9 Pedal HH": "9 Pedal Hi-Hat", "11 Open HH": "11 Open Hi-Hat",
    "12 Low-Mid": "12 Low-Mid Tom", "13 High-Mid": "13 High-Mid Tom",
    "Conv-Div": "Converge-Diverge", "Up Top Oct": "Up Top Octave", "Down Low Oct": "Down Low Octave",
    "Up Alt Oct": "Up Alternate Octave", "Down Alt Oct": "Down Alternate Octave", "TRG": "Trigger",
}


def full(name):
    return FULL.get(name, name)


def sim(tools, *args, engine="macro", seconds="0.3"):
    return run(tools["sim"], ["--engine", engine, "--seconds", seconds, *args])


def catalog(tools):
    return json.loads(subprocess.run([str(tools["sim"]), "--list"], check=True, capture_output=True,
                                     text=True).stdout)


def window(total, sel, rows):
    """fm1_list_first: the choice on the third row where it can be."""
    return max(0, min(sel - (rows - 1) // 2, total - rows))


def assert_window(s, title, names, sel, face="MID", rows=None):
    rows = rows or ROWS[face]
    first = window(len(names), sel, rows)
    assert s["popup_list"] == {"title": title, "first": first, "total": len(names),
                               "mark": sel - first}
    assert s["popup_face"] == face and s["popup_rows"] == ROWS[face]
    assert s["popup"] == names[first:first + rows]
    assert all(len(n) <= CHARS[face] for n in s["popup"]), "an entry longer than its face's line"


def test_every_short_form_is_in_a_list_and_stands_for_a_longer_name(tools):
    """Each short form the lists expand is one an engine offers, as a list
    entry or a name, and its full name is longer and fits a MID line."""
    names = set()
    for e in catalog(tools):
        names.add(e["name"])
        for p in e["params"]:
            names.update(p.get("names", []))
    assert set(FULL) <= names
    assert all(len(v) > len(k) and len(v) <= CHARS["MID"] for k, v in FULL.items())


@pytest.mark.parametrize("start,turn,sel", [(1, -1, 0), (47, 1, 48), (95, 1, 95), (94, 1, 95)],
                         ids=["top", "middle", "end", "to-the-end"])
def test_algorithm_shows_eight_of_six_op_fms_96_patches(tools, start, turn, sel):
    """ALGORITHM on Six-Op FM, the longest list (96 patches), in MID: at the
    top the first patch is chosen on the first row; in the middle the
    chosen one is on the third, two before it and five after; at the end
    the window stops at the last patch, which stays chosen past it."""
    params = next(e for e in catalog(tools) if e["id"] == "sixop")["params"]
    patch = next(dict(p, index=i) for i, p in enumerate(params) if p["name"] == "Patch")
    s = sim(tools, "--param", f"Patch={start}", "--turn", f"0.1:ALGORITHM:{turn}", engine="sixop")
    assert s["values0"][patch["index"]] == sel
    assert_window(s, "Patch", patch["names"], sel)


def test_algorithm_spells_macros_models_out(tools):
    """Macro's models by their full names: PhaseDist is Phase Distortion,
    2-op FM Two-Operator FM."""
    params = next(e for e in catalog(tools) if e["id"] == "macro")["params"]
    s = sim(tools, "--turn", "0.1:ALGORITHM:1")
    assert_window(s, "Model", [full(n) for n in params[0]["names"]], 1)
    assert s["popup"][1] == "Phase Distortion" and "Two-Operator FM" in s["popup"]


@pytest.mark.parametrize("at,turn", [(1, -1), (3, 1), (-2, 1)], ids=["top", "middle", "end"])
def test_presets_shows_the_engines(tools, at, turn):
    """PRESETS on Sound 1: every sound engine (no Empty), the new one
    chosen, under "Engine" and its place: back to the first engine, on to
    the fifth, and on to the last; all eight fit MID at once."""
    engines = [e for e in catalog(tools) if e["kind"] == "sound"]
    ids = [e["id"] for e in engines]
    sel = at % len(ids) + turn
    s = sim(tools, "--turn", f"0.1:PRESETS:{turn}", engine=ids[sel - turn])
    assert s["engine"] == ids[sel]
    assert_window(s, "Engine", [full(e["name"]) for e in engines], sel)


@pytest.mark.parametrize("turn", [1, 12, -1], ids=["top", "middle", "end"])
def test_algorithm_in_fx_mode_shows_the_effects(tools, turn):
    """ALGORITHM in FX mode on an empty M1: Empty slot (dim on the screen)
    and every effect by its full name (Compressor, Master Saturation), the
    slot's highlighted, under "Master 1 effect"; turning back from Empty
    wraps to the last effect, and the window shows the list's end."""
    effects = [e for e in catalog(tools) if e["kind"] == "audio_fx"]
    names = ["Empty slot"] + [full(e["name"]) for e in effects]
    sel = turn % len(names)                              # -1: the last effect
    s = sim(tools, "--button", "0.05:FX", "--turn", f"0.1:ALGORITHM:{turn}")
    assert s["fx"][0] == effects[sel - 1]["id"]
    assert_window(s, "Master 1 effect", names, sel)
    assert "Compressor" in names and "Master Saturation" in names


def test_shift_presets_lists_the_four_sounds(tools):
    """SHIFT + PRESETS: the four sounds and what each holds, the current
    one chosen; four entries and their names fit MAIN, the largest face."""
    s = sim(tools, "--sound", "1:shapes", "--button", "0.1:SEL:0.2", "--turn", "0.15:PRESETS:1",
            seconds="0.5")
    assert s["current"] == 1
    assert_window(s, "Current sound", ["S1 Macro", "S2 Shapes", "S3 Empty", "S4 Empty"], 1, face="MAIN")


@pytest.mark.parametrize("engine,knob,name,entries", [
    ("dx7", 1, "Patch", 64), ("shapes", 1, "Shape", 47), ("drums", 1, "Pad", 16),
    ("macro-heavy", 1, "Model", 13)])
def test_a_knob_on_a_list_parameter_opens_its_list(tools, engine, knob, name, entries):
    """D1: KNOB1 on FM6's Patch, Shapes' Shape, Drums' Pad or Macro Heavy's
    Model opens the same list ALGORITHM does, in MID, the knob's value
    chosen, for as long as ALGORITHM's (about a second)."""
    s = sim(tools, "--turn", f"0.1:KNOB{knob}:3", engine=engine)
    p = next(p for p in next(e for e in catalog(tools) if e["id"] == engine)["params"]
             if p["name"] == name)
    assert len(p["names"]) == entries
    assert_window(s, name, [full(n) for n in p["names"]], 3)
    later = sim(tools, "--turn", f"0.1:KNOB{knob}:3", engine=engine, seconds="1.4")
    assert later["popup"] == []


def test_a_knob_on_a_short_list_changes_in_place(tools):
    """A list parameter of fewer than five entries (Macro's LPG: Gate, Ping,
    Off) changes on its row, with no popup over the page."""
    s = sim(tools, "--turn", "0.05:SELECT:2", "--turn", "0.1:KNOB4:1")
    assert s["popup"] == [] and s["popup_list"] is None


def test_a_knob_on_an_effects_list_opens_it_in_fx_mode(tools):
    """In FX mode a knob on the slot's effect's list parameter (the Filter's
    Type, six) opens its list too, by full names (SK Mixed is
    Sallen-Key Mixed); the six fit MAIN, the largest face, whole (D9)."""
    p = next(e for e in catalog(tools) if e["id"] == "filter")["params"][0]
    to = 4 - int(p["def"])                               # from its default to SK Mixed, the fifth
    s = sim(tools, "--fx", "filter", "--button", "0.05:FX", "--turn", f"0.1:KNOB1:{to}", engine="test-sine")
    assert_window(s, "Type", [full(n) for n in p["names"]], 4, face="MAIN")
    assert s["popup"][s["popup_list"]["mark"]] == "Sallen-Key Mixed"


def test_the_kind_picker_shows_seventeen_entries_in_mid(tools):
    """RACK's kind picker on LFO1: Empty, then the sixteen kinds, drawn in
    MID (FM1_LIST_FACE_KIND) with the window fm1_mod_ui fills. One turn
    forward from LFO puts Envelope on the third row with Empty and LFO
    above it; two back from LFO wraps to the last kind, and the window
    shows the end of the list."""
    fwd = sim(tools, "--button", "0.05:LFO", "--turn", "0.1:ALGORITHM:1")
    names = ["Empty", "LFO", "Envelope"]
    assert fwd["popup_list"] == {"title": "Mod1 kind", "first": 0, "total": 17, "mark": 2}
    assert fwd["popup"][:3] == names and len(fwd["popup"]) == PICKER_ROWS
    assert fwd["popup_face"] == "MID"
    back = sim(tools, "--button", "0.05:LFO", "--turn", "0.1:ALGORITHM:-2")
    first = 17 - PICKER_ROWS
    assert back["popup_list"] == {"title": "Mod1 kind", "first": first, "total": 17,
                                  "mark": 16 - first}


@pytest.mark.parametrize("more,where", [(None, "top"), (20, "middle"), (999, "end")])
def test_the_destination_picker_shows_full_names_in_mid(tools, more, where):
    """MATRIX's destination picker (KNOB2) on slot 1, in MID
    (FM1_LIST_FACE_DEST: every full name fits its 27 characters): the
    chosen one on the first row at the top of the list, on the fourth of
    MID's eight in its middle and on the last at its end."""
    turns = ["--turn", "0.1:KNOB2:-999"] + (["--turn", f"0.15:KNOB2:{more}"] if more else [])
    s = sim(tools, "--button", "0.05:EDIT", *turns)
    w = s["popup_list"]
    rows = PICKER_ROWS
    assert w["title"] == "Destination" and w["total"] > 2 * rows and len(s["popup"]) == rows
    assert s["popup_face"] == "MID"
    sel = {"top": 0, "middle": 20, "end": w["total"] - 1}[where]
    assert w["first"] == window(w["total"], sel, rows) and w["first"] + w["mark"] == sel
    assert w["mark"] == {"top": 0, "middle": (rows - 1) // 2, "end": rows - 1}[where]
    if where == "top":
        assert s["popup"][0] == "S1 Harmonics"           # the current sound's first
        assert s["popup_tags"][:2] == [1, 1]             # its "S1" in Sound 1's colour (L3)
    if where == "end":
        assert s["popup"][-1].startswith("CHN5 ")        # the rack's last module


def test_quantize_walks_its_list(tools):
    """SHIFT + 16 walks the clip's quantize through 0, the set's default
    and 100 (0 and 100 with the default at 0): its toast is that list, in
    MAIN, the clip's new value chosen (D1)."""
    s = sim(tools, "--button", "0.05:SEQ", "--button", "0.1:SEL:0.3", "--key", "0.15:26:100:0.05")
    assert s["popup_list"] == {"title": "Clip quantize", "first": 0, "total": 2, "mark": 1}
    assert s["popup"] == ["0%", "100%"] and s["popup_face"] == "MAIN"


def test_a_message_is_no_list(tools):
    """SAVE's popup without a store and the gesture's stay messages: no
    title, no window. SAVE's is a refusal (audit Q2): the full popup, its
    reason in love.
    The gesture's amount is a confirmation: one line, a banner over the
    page (audit L1), in MID since it needs more than MAIN's 18 characters."""
    stub = sim(tools, "--button", "0.1:SAVE", seconds="0.2")
    assert stub["popup"] == ["SAVE", "no store in", "this host"] and stub["popup_list"] is None
    assert stub["popup_tone"] == "refuse" and "popup_banner" not in stub
    cable = sim(tools, "--button", "0.1:LFO:0.2", "--turn", "0.15:KNOB3:25", seconds="0.4")
    assert cable["popup"] == ["LFO1 > S1 Timbre", "+25%"] and cable["popup_list"] is None
    assert cable["popup_tone"] == "say"
    assert (cable["popup_banner"], cable["popup_banner_face"]) == ("LFO1 > S1 Timbre +25%", "MID")


@pytest.mark.parametrize("args,banner,face", [
    (["--master", "0.5"], None, None),
    (["--button", "0.1:OCT+"], "Octave +1", "MAIN"),
    (["--button", "0.1:OCT+:0.2", "--turn", "0.15:ALGORITHM:-5"], "Transpose -5", "MAIN"),
    (["--button", "0.1:OCT+:0.2", "--button", "0.15:OCT-:0.1"], "Octave 0, Transpose 0", "MID"),
])
def test_one_line_confirmations_are_banners(tools, args, banner, face):
    """L1: a confirmation that joins into one line of at most 18 characters
    is a banner in MAIN over the page's bottom; up to 27, in MID; the page
    stays in view. A line that starts with a capital joins after a comma.
    (--master sets the start position, with no popup.)"""
    s = sim(tools, *args, seconds="0.4")
    if banner is None:
        assert s["popup"] == []
        return
    assert s["popup_tone"] == "say"
    assert (s["popup_banner"], s["popup_banner_face"]) == (banner, face)


def test_refusals_keep_the_popup_in_love(tools):
    """Q2: a refusal is never a banner: a held LFO turning a knob on a
    parameter that takes no cable (Macro's Model), and the RAM meter's
    refusal of an engine past the budget."""
    s = sim(tools, "--button", "0.1:LFO:0.2", "--turn", "0.15:KNOB1:5", seconds="0.4")
    assert s["popup"][1] == "takes no cable" and s["popup_tone"] == "refuse"
    assert "popup_banner" not in s
