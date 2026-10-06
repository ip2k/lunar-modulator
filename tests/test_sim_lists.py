"""List popups in the virtual FM-1 (sim/web): PRESETS, ALGORITHM (the
sound's first list parameter, or in FX mode the slot's effect), SHIFT +
PRESETS, the modulation kind picker and MATRIX's destination picker show
as many entries as the screen's middle holds (FM1_LIST_ROWS, six), under
the list's title and the chosen entry's place, the chosen one on the third
row where it can be and the window never past either end (fm1_list_first,
fm1_panel.h). Until 2026-10-06 they showed three lines, the previous, the
chosen and the next entry.

The harness's summary has the window: `popup` its entries, `popup_list`
the title, the first entry shown, the list's length and the marked line
(null for a message). `fm1-sim-render --screens` draws every entry of
every list and checks each screen's layout (tests/test_sim_web.py).
"""
import json
import subprocess

import pytest

from tests.test_sim_web import run, tools  # noqa: F401  (the native build)

ROWS = 6


def sim(tools, *args, engine="macro", seconds="0.3"):
    return run(tools["sim"], ["--engine", engine, "--seconds", seconds, *args])


def catalog(tools):
    return json.loads(subprocess.run([str(tools["sim"]), "--list"], check=True, capture_output=True,
                                     text=True).stdout)


def window(total, sel):
    """fm1_list_first: the choice on the third row where it can be."""
    return max(0, min(sel - (ROWS - 1) // 2, total - ROWS))


def assert_window(s, title, names, sel):
    first = window(len(names), sel)
    assert s["popup_list"] == {"title": title, "first": first, "total": len(names),
                               "mark": sel - first}
    assert s["popup"] == names[first:first + ROWS]


@pytest.mark.parametrize("start,turn,sel", [(1, -1, 0), (47, 1, 48), (95, 1, 95), (94, 1, 95)],
                         ids=["top", "middle", "end", "to-the-end"])
def test_algorithm_shows_six_of_six_op_fms_96_patches(tools, start, turn, sel):
    """ALGORITHM on Six-Op FM, the longest list (96 patches): at the top the
    first patch is chosen on the first row; in the middle the chosen one is
    on the third, two before it and three after; at the end the window
    stops at the last patch, which stays chosen past it."""
    params = next(e for e in catalog(tools) if e["id"] == "sixop")["params"]
    patch = next(dict(p, index=i) for i, p in enumerate(params) if p["name"] == "Patch")
    s = sim(tools, "--param", f"Patch={start}", "--turn", f"0.1:ALGORITHM:{turn}", engine="sixop")
    assert s["values0"][patch["index"]] == sel
    assert_window(s, "Patch", patch["names"], sel)


@pytest.mark.parametrize("at,turn", [(1, -1), (3, 1), (-2, 1)], ids=["top", "middle", "end"])
def test_presets_shows_the_engines(tools, at, turn):
    """PRESETS on Sound 1: every sound engine (no Empty), the new one
    chosen, under "Engine" and its place: back to the first engine, on to
    the fifth, and on to the last."""
    engines = [e for e in catalog(tools) if e["kind"] == "sound"]
    ids = [e["id"] for e in engines]
    sel = at % len(ids) + turn
    s = sim(tools, "--turn", f"0.1:PRESETS:{turn}", engine=ids[sel - turn])
    assert s["engine"] == ids[sel]
    assert_window(s, "Engine", [e["name"] for e in engines], sel)


@pytest.mark.parametrize("turn", [1, 12, -1], ids=["top", "middle", "end"])
def test_algorithm_in_fx_mode_shows_the_effects(tools, turn):
    """ALGORITHM in FX mode on an empty M1: Empty slot (dim on the screen) and
    every effect, the slot's highlighted; turning back from Empty wraps to
    the last effect, and the window shows the list's end."""
    effects = [e for e in catalog(tools) if e["kind"] == "audio_fx"]
    names = ["Empty slot"] + [e["name"] for e in effects]
    sel = turn % len(names)                              # -1: the last effect
    s = sim(tools, "--button", "0.05:FX", "--turn", f"0.1:ALGORITHM:{turn}")
    assert s["fx"][0] == effects[sel - 1]["id"]
    assert_window(s, "M1 effect", names, sel)


def test_shift_presets_lists_the_four_sounds(tools):
    """SHIFT + PRESETS: the four sounds and what each holds, the current
    one chosen."""
    s = sim(tools, "--sound", "1:shapes", "--button", "0.1:SEL:0.2", "--turn", "0.15:PRESETS:1",
            seconds="0.5")
    assert s["current"] == 1
    assert_window(s, "Sound", ["S1 Macro", "S2 Shapes", "S3 Empty", "S4 Empty"], 1)


def test_the_kind_picker_shows_seventeen_entries_six_at_a_time(tools):
    """RACK's kind picker on LFO1: Empty, then the sixteen kinds. One turn
    forward from LFO puts Envelope on the third row with Empty and LFO
    above it; two back from LFO wraps to the last kind, and the window
    shows the end of the list."""
    fwd = sim(tools, "--button", "0.05:LFO", "--turn", "0.1:ALGORITHM:1")
    names = ["Empty", "LFO", "Envelope"]
    assert fwd["popup_list"] == {"title": "Mod1 kind", "first": 0, "total": 17, "mark": 2}
    assert fwd["popup"][:3] == names and len(fwd["popup"]) == ROWS
    back = sim(tools, "--button", "0.05:LFO", "--turn", "0.1:ALGORITHM:-2")
    assert back["popup_list"] == {"title": "Mod1 kind", "first": 11, "total": 17, "mark": 5}


@pytest.mark.parametrize("more,where", [(None, "top"), (20, "middle"), (999, "end")])
def test_the_destination_picker_shows_six_destinations(tools, more, where):
    """MATRIX's destination picker (KNOB2) on slot 1: six full names, the
    chosen one on the first row at the top of the list, on the third in
    its middle and on the last at its end."""
    turns = ["--turn", "0.1:KNOB2:-999"] + (["--turn", f"0.15:KNOB2:{more}"] if more else [])
    s = sim(tools, "--button", "0.05:EDIT", *turns)
    w = s["popup_list"]
    assert w["title"] == "Destination" and w["total"] > 2 * ROWS and len(s["popup"]) == ROWS
    sel = {"top": 0, "middle": 20, "end": w["total"] - 1}[where]
    assert w["first"] == window(w["total"], sel) and w["first"] + w["mark"] == sel
    assert w["mark"] == {"top": 0, "middle": 2, "end": ROWS - 1}[where]
    if where == "top":
        assert s["popup"][0] == "S1 Harmonics"           # the current sound's first
    if where == "end":
        assert s["popup"][-1].startswith("CHN5 ")        # the rack's last module


def test_a_message_is_no_list(tools):
    """A stub's popup and the gesture's stay messages: centred lines, no
    title, no window."""
    stub = sim(tools, "--button", "0.1:SAVE", seconds="0.2")
    assert stub["popup"] == ["SAVE", "not in the", "simulator yet"] and stub["popup_list"] is None
    cable = sim(tools, "--button", "0.1:LFO:0.2", "--turn", "0.15:KNOB3:25", seconds="0.4")
    assert cable["popup"] == ["LFO1 > S1Tmbre", "+25%"] and cable["popup_list"] is None
