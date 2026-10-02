"""The sequencer on the virtual FM-1's panel (docs/15 stages S3 to S5),
behind the lab switch: golden gesture traces with two-step parity (§6.3),
the typed commands' text round trip, the demo pattern, the switch itself,
step entry (taps, holds, the Step pages, SHIFT, bar paging and the LEDs),
and record and Capture (REC, step record, SHIFT + REC, live input from the
keys and MIDI IN, and REC's LED).

A gesture trace is a .panel file (one --key, --button, --turn or --note per
line) and its golden .verbs, what `fm1-sim-render --lab --log-cmds` writes
for it: the script lines as applied and every command the panel sent, at
the block it led. Two-step parity: fm1-render replaying that file, with the
sidecar of arguments the harness writes next to it (.args: the engine, the
notes the keys and MIDI IN played, the knob turns on the sound), renders
the same bytes as the panel run. Every trace here plays Test Sine; S3's
start from tests/fixtures/seq-ui/input.verbs, S4's (step-*) from
steps.verbs, a bar at 240 BPM, S5's (rec-*, capture-*) from rec.verbs, the
same with two notes and 4 s long, or the input TRACE_INPUT names. A note
played that no step takes is live input, logged as `non` and `nof` ops at
the block it led, so the replay records and captures the same. The parity
scenarios under sim/web/test/seq/ play Macro and Plate
(tests/test_sim_web.py, and in WebAssembly on the build host).
"""
import json
import re
import subprocess

import pytest

from tests.engine_helpers import ROOT
from tests.test_sim_web import run, tools  # noqa: F401  (the native build of both tools)

TRACES = ROOT / "tests" / "fixtures" / "seq-ui"
PANELS = sorted(TRACES.glob("*.panel"))
TRACE_INPUT = {"step-hidden-tail": "tail.verbs", "step-record-grow": "empty.verbs",
               "rec-empty-clip-waits": "empty.verbs", "capture-stopped-picker": "empty.verbs"}
WHITE = [0, 2, 4, 6, 7, 9, 11, 12, 14, 16, 18, 19, 21, 23, 24, 26]   # white key n -> key index
BUTTONS = ["OCT-", "OCT+", "FX", "SEL", "ENV", "LFO", "EDIT", "GLO", "HOME", "SAVE", "ARP", "SEQ",
           "PLAY/STOP", "REC"]


def trace_input(stem):
    default = ("steps.verbs" if stem.startswith("step-") else
               "rec.verbs" if stem.startswith(("rec-", "capture-")) else "input.verbs")
    return TRACES / TRACE_INPUT.get(stem, default)


def two_step(tools, tmp_path, name, panel, cmd, *args, lab=True):
    """The panel run and its replay: (panel summary, replay summary, the
    logged script, the panel run's WAV, the replay's WAV)."""
    log, a, b = tmp_path / f"{name}.verbs", tmp_path / f"{name}-panel.wav", tmp_path / f"{name}-replay.wav"
    s = run(tools["sim"], [*(["--lab"] if lab else []), *args, "--cmd", str(cmd), "--panel", str(panel),
                           "--log-cmds", str(log), "--out", str(a)])
    sidecar = (tmp_path / f"{name}.args").read_text().splitlines()
    r = run(tools["render"], ["--cmd", str(log), "--frames", "64", *sidecar, "--out", str(b)])
    return s, r, log.read_text(), a.read_bytes(), b.read_bytes()


def test_there_are_the_s3_and_s4_traces():
    stems = {p.stem for p in PANELS}
    assert stems >= {"seq-enter-exit", "play-stop-from-home", "play-stop-from-fx",
                     "play-stop-from-seq", "play-twice"}
    s4 = {"step-tap", "step-hold", "step-length", "step-several-held", "step-oct", "step-bar-paging",
          "step-full-velocity", "step-velocity", "step-length-knob", "step-probability",
          "step-condition", "step-invert", "step-add-pitch", "step-clear", "step-nudge",
          "step-chord-from-keys", "step-chord-from-midi", "step-midi-adds-pitch", "step-shift-play",
          "step-co-press", "step-hold-then-home", "step-hidden-tail"}
    assert stems >= s4 and len(s4) >= 15
    s5 = {"rec-count-in", "rec-seq-tap", "rec-overdub", "rec-empty-clip-waits", "rec-hold-untouched",
          "step-record", "step-record-grow", "capture-playing", "capture-stopped-picker",
          "capture-stopped-fitted", "capture-nothing"}
    assert stems >= s5


@pytest.mark.parametrize("panel", PANELS, ids=lambda p: p.stem)
def test_a_trace_logs_its_golden_verbs_and_replays_byte_for_byte(tools, tmp_path, panel):
    s, r, log, a, b = two_step(tools, tmp_path, panel.stem, panel, trace_input(panel.stem),
                               "--engine", "test-sine")
    assert log == panel.with_suffix(".verbs").read_text(), "not the golden trace"
    assert s["replayable"] == 1
    assert a == b, "two-step parity: the replay differs"
    assert s["seq_dropped"] == r["seq_dropped"] == 0 and s["seq_busy"] == s["seq_held"] == 0
    assert s["seq_notes_to_engine"] == r["seq_notes_to_engine"]
    played = [t for _, t in s["seq_ui_cmds"]]
    if panel.stem != "seq-enter-exit":
        # Something starts the transport: PLAY/STOP, REC from stopped, or a
        # stopped Capture.
        assert {"play", "rec 0", "cap 0"} & set(played) and s["peak"] > 0.01
    if panel.stem.startswith("play-"):
        assert played[0] == "play"


@pytest.mark.parametrize("panel,mode,leds", [
    ("seq-enter-exit", 3, {"SEQ"}),             # ends in SEQ mode, stopped
    ("play-stop-from-home", 0, set()),
    ("play-stop-from-fx", 1, {"FX"}),           # FX mode stays; PLAY off after the stop
    ("play-stop-from-seq", 3, {"SEQ", "PLAY/STOP"}),
    ("play-twice", 0, {"PLAY/STOP"}),
])
def test_a_trace_ends_in_its_mode_with_its_button_leds(tools, tmp_path, panel, mode, leds):
    s = run(tools["sim"], ["--lab", "--engine", "test-sine", "--cmd", str(TRACES / "input.verbs"),
                           "--panel", str(TRACES / f"{panel}.panel")])
    lit = {n for n, c in zip(BUTTONS, s["leds"][27:]) if c == "1"}
    assert (s["mode"], lit) == (mode, leds)
    assert s["popup"] == []


def test_the_parity_scenarios_panels_replay_byte_for_byte(tools, tmp_path):
    """The WebAssembly parity scenarios' own traces, natively, with Macro
    and Plate: S3's knob turns on two sound pages replayed as --param-at;
    S4's step entry with its MIDI IN notes replayed as --note."""
    scen = json.loads((ROOT / "sim/web/test/scenarios.json").read_text())["scenarios"]
    panels = [x for x in scen if "panel" in x]
    assert {x["name"] for x in panels} >= {"seq-panel-play-stop", "seq-panel-step-entry",
                                           "seq-panel-record", "seq-panel-capture-stopped"}
    for sc in panels:
        seq = ROOT / "sim" / "web" / "test"
        args = ["--engine", sc["engine"], "--seconds", str(sc["seconds"])]
        for p in sc.get("params", []):
            args += ["--param", p]
        for fx, ps in sc.get("fx", []):
            args += ["--fx", fx]
            for p in ps:
                args += ["--fx-param", p]
        s, r, log, a, b = two_step(tools, tmp_path, sc["name"], seq / sc["panel"], seq / sc["cmd"],
                                   *args, lab=sc.get("lab", False))
        assert s["replayable"] == 1 and a == b and s["peak"] > 0.01
        sidecar = (tmp_path / f"{sc['name']}.args").read_text()
        played = [t for _, t in s["seq_ui_cmds"]]
        if sc["name"] == "seq-panel-play-stop":
            assert sidecar.count("--param-at") == 2, "the two knob turns"
            assert played == ["play", "stop", "play"]
        if sc["name"] == "seq-panel-step-entry":
            assert sidecar.count("--note") == 3, "the chord at MIDI IN"
            verbs = {t.split()[0] for t in played}
            # The chord at MIDI IN is live input too (S5): three `non`, three `nof`.
            assert verbs == {"tog", "eprob", "econd", "einv", "enudge", "addp", "del", "play", "non",
                             "nof"}
            assert sum(t.startswith("non ") for t in played) == 3
            assert any(t.startswith("tog 0 16 ") for t in played), "the clip's second bar"
        if sc["name"] == "seq-panel-record":
            verbs = [t.split()[0] for t in played]
            assert verbs.count("rec") == 2 and "cap" in verbs and "slen" in verbs
            assert verbs.count("non") == verbs.count("nof") == 5, "two keys recorded, three captured"
            assert sidecar.count("--note") == 9, "eight keys and the MIDI IN note"
        if sc["name"] == "seq-panel-capture-stopped":
            assert played[-3:] == ["cap 0", "capsel 1", "capdone"]


def test_every_verb_round_trips_through_its_text(tools):
    """fm1_seq_cmd_format writes a typed command as the text fm1_seq_parse
    reads back to the same record, for every verb, as parsed from several
    shapes of text and as the panel makes them (fm1_seq_cmd_make): the
    replay of a logged trace applies exactly what the panel applied."""
    res = subprocess.run([str(tools["sim"]), "--format-check"], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    names = re.findall(r'\{ "(\w+)", FM1_SEQ_V_\w+ \}',
                       (ROOT / "engines" / "seq" / "seq_cmd.c").read_text(encoding="utf-8"))
    assert out["failures"] == 0
    assert out["verbs"] == len(names) == 67
    assert out["records"] >= 67 * 30


def test_with_the_lab_switch_off_nothing_changes(tools, tmp_path):
    """Off (the public page): SEQ and PLAY/STOP say they are not in the
    simulator yet, send nothing and light nothing, and a script that plays
    the sequencer leaves the PLAY LED to the button."""
    script = tmp_path / "p.verbs"
    script.write_text("#! rate=44118 block=64 tracks=8 end=44118\n@0 tog 0 0 60 100;play\n")
    s = run(tools["sim"], ["--engine", "test-sine", "--cmd", str(script), "--button", "0.1:SEQ",
                           "--button", "0.5:PLAY/STOP"])
    assert s["lab"] == 0 and s["mode"] == 0
    assert s["popup"] == ["PLAY/STOP", "not in the", "simulator yet"]
    assert s["seq_ui_cmds"] == [] and s["seq_notes_to_engine"] > 0
    assert s["leds"] == "0" * 41
    seq = run(tools["sim"], ["--engine", "test-sine", "--seconds", "0.2", "--button", "0.1:SEQ"])
    assert seq["mode"] == 0 and seq["popup"] == ["SEQ", "not in the", "simulator yet"]
    # REC too (S5), with SEL held as SHIFT would be; and keys and MIDI IN are
    # no live input: nothing reaches the sequencer, nothing is captured.
    rec = run(tools["sim"], ["--engine", "test-sine", "--cmd", str(script), "--key", "0.1:7:100:0.2",
                             "--note", "0.15:64:100:0.2", "--button", "0.5:SEL:0.2",
                             "--button", "0.55:REC"])
    assert rec["popup"] == ["REC", "not in the", "simulator yet"]
    assert rec["seq_ui_cmds"] == [] and "rec" not in rec and rec["leds"][27 + 13] == "0"


def test_the_demo_pattern_plays_on_the_browsers_start_only(tools):
    """The demo pattern (owner decision O4) comes with the browser's start
    chain and the lab switch: PLAY/STOP then plays it. Without the switch,
    or without the start chain (every test and parity run), the sequencer
    starts empty."""
    demo = run(tools["sim"], ["--lab", "--start", "--seconds", "2", "--button", "0.1:PLAY/STOP"])
    assert demo["engine"] == "macro" and demo["fx"] == ["plate", ""]
    assert demo["peak"] > 0.05 and demo["seq_view"]["clip_playing"] == 1
    assert demo["leds"][27 + 12] == "1"
    empty = run(tools["sim"], ["--lab", "--engine", "macro", "--seconds", "2",
                               "--button", "0.1:PLAY/STOP"])
    assert empty["peak"] == 0 and empty["seq_view"]["clip_playing"] == 0
    off = run(tools["sim"], ["--start", "--seconds", "1", "--button", "0.1:PLAY/STOP"])
    assert off["peak"] == 0 and off["popup"][0] == "PLAY/STOP"


def test_a_change_of_sound_from_the_panel_is_not_replayable(tools, tmp_path):
    """PRESETS changes the sound, which fm1-render cannot replay (§6.3's
    exclusion): the harness says so instead of logging a wrong replay."""
    panel = tmp_path / "p.panel"
    panel.write_text("--button 0.1:PLAY/STOP\n--turn 0.3:PRESETS:1\n")
    s = run(tools["sim"], ["--lab", "--engine", "test-sine", "--cmd", str(TRACES / "input.verbs"),
                           "--panel", str(panel), "--log-cmds", str(tmp_path / "c.verbs")])
    assert s["replayable"] == 0


def test_the_ui_state_fits_its_bound(tools):
    z = json.loads(subprocess.run([str(tools["sim"]), "--sizes"], check=True, capture_output=True,
                                  text=True).stdout)
    assert z["seq_ui_size"] <= z["seq_ui_bytes"] == 1024


# ---- Step entry (docs/15 S4) -----------------------------------------------------------------

def step_run(tools, tmp_path, panel_lines, *extra, script=None, seconds=None):
    """A panel run from steps.verbs (or `script`), the lab switch on, Test
    Sine; `seconds` ends it early (a key still held at the end stays held)."""
    panel = tmp_path / "p.panel"
    panel.write_text("\n".join(panel_lines) + "\n")
    cmd = TRACES / "steps.verbs"
    if script is not None:
        cmd = tmp_path / "in.verbs"
        cmd.write_text(script)
    args = ["--lab", "--engine", "test-sine", "--cmd", str(cmd), "--panel", str(panel), *extra]
    if seconds is not None:
        args += ["--seconds", str(seconds)]
    return run(tools["sim"], args)


@pytest.mark.parametrize("seconds,view", [(0.38, 0), (0.42, 1)])
def test_a_hold_opens_the_step_page_at_its_threshold(tools, tmp_path, seconds, view):
    """ceil(0.3 x 44,118) = 13,236 frames after the press (block 4,416): the
    Track view before, the Step page from the first block past it, which
    changes only the screen."""
    s = step_run(tools, tmp_path, ["--button 0.05:SEQ", "--key 0.10:7:100:5"], seconds=seconds)
    v = s["seq_view"]
    assert v["held"] == 1 and v["view"] == view and s["seq_ui_cmds"] == []
    assert s["hold"] == {"step": 4, "notes": 1, "tick": 96, "gate": 24, "vel": 90, "pitch": 55,
                         "gate_mixed": 0, "prob": 100, "cond": [1, 1], "inv": 0}


def test_the_step_page_reads_back_what_the_knobs_set(tools, tmp_path):
    s = step_run(tools, tmp_path, ["--button 0.05:SEQ", "--key 0.10:7:100:5",
                                   "--turn 0.20:KNOB1:3", "--turn 0.25:KNOB2:2",
                                   "--turn 0.30:KNOB3:-4", "--turn 0.35:KNOB4:5",
                                   "--turn 0.40:SELECT:1", "--turn 0.45:KNOB1:1"], seconds=0.6)
    assert s["seq_view"]["view"] == 1 and s["seq_view"]["step_page"] == 1
    assert s["hold"] == {"step": 4, "notes": 1, "tick": 96, "gate": 96, "vel": 102,
                         "pitch": 55, "gate_mixed": 0, "prob": 60, "cond": [3, 3], "inv": 1}


def test_a_chord_with_two_lengths_shows_as_mixed(tools, tmp_path):
    script = ("#! rate=44118 block=64 tracks=8 end=44118\n"
              "@0 tog 0 2 60 100 64 90;slen 0 2 2 64 48\n")
    s = step_run(tools, tmp_path, ["--button 0.05:SEQ", "--key 0.10:4:100:5"], script=script,
                 seconds=0.5)
    assert s["hold"]["notes"] == 2 and s["hold"]["gate_mixed"] == 1 and s["hold"]["vel"] == 100


def lit_keys(s):
    return {k for k in range(27) if s["leds"][k] == "1"}


def test_the_keys_leds_in_seq_mode(tools, tmp_path):
    """Stopped, in bar 1: the four steps with notes; the bar keys F#3 (back)
    dark and A#3 (on) lit, since a second, empty bar can be reached. A held
    step is lit, the steps under its note blink at the 1 s rate, and both bar
    keys light (they nudge)."""
    s = step_run(tools, tmp_path, ["--button 0.05:SEQ"], seconds=0.3)
    assert lit_keys(s) == {WHITE[0], WHITE[4], WHITE[8], WHITE[12], 5}
    assert s["seq_view"]["role_leds"] == 0b100 and s["seq_view"]["key_leds"] == 0x1111
    # Step 1 held with its note 4 steps long: steps 2-4 blink, on for the
    # first half of each second (frame % 44118 < 22059).
    hold = ["--button 0.05:SEQ", "--key 0.10:0:100:5", "--turn 0.15:KNOB2:2"]
    on = step_run(tools, tmp_path, hold, seconds=1.2)
    off = step_run(tools, tmp_path, hold, seconds=1.6)
    assert on["hold"]["gate"] == 96
    assert lit_keys(on) == {WHITE[0], WHITE[1], WHITE[2], WHITE[3], WHITE[4], WHITE[8], WHITE[12],
                            1, 5}
    assert lit_keys(off) == {WHITE[0], WHITE[4], WHITE[8], WHITE[12], 1, 5}


def test_bar_paging_stops_at_the_loops_bars_and_one_more(tools, tmp_path):
    empty = "#! rate=44118 block=64 tracks=8 end=44118\n@0 bpm 24000\n"
    s = step_run(tools, tmp_path, ["--button 0.05:SEQ", "--key 0.10:5:100:0.02"], script=empty,
                 seconds=0.3)
    assert s["seq_view"]["bar"] == 0 and s["seq_view"]["role_leds"] == 0, "no clip: bar 1 only"
    s = step_run(tools, tmp_path, ["--button 0.05:SEQ"] + [f"--key {0.1 + 0.05 * k:.2f}:5:100:0.02"
                                                         for k in range(4)], seconds=0.5)
    assert s["seq_view"]["bar"] == 1 and s["seq_view"]["role_leds"] == 0b001
    assert s["seq_view"]["hint"] == 2, "the hint line names the bar"


def test_sixteen_held_steps_each_get_the_edit(tools, tmp_path):
    """Every white key held (the first empty, so all are steps), then KNOB1:
    one `evel` per held step, in press order, every one applied."""
    keys = [f"--key {0.10 + 0.01 * n:.2f}:{WHITE[(n + 1) % 16]}:100:0.8" for n in range(16)]
    s = step_run(tools, tmp_path, ["--button 0.05:SEQ", *keys, "--turn 0.40:KNOB1:1"])
    cmds = [t for _, t in s["seq_ui_cmds"]]
    assert cmds == [f"evel 0 {(n + 1) % 16} {(n + 1) % 16} -1 4" for n in range(16)]
    assert s["seq_busy"] == s["seq_held"] == 0


def test_the_remembered_chord_is_the_last_twelve_held(tools, tmp_path):
    """Thirteen notes held at MIDI IN: a tap writes the last twelve, each
    with its velocity (a `tog` takes 12 pairs at most)."""
    notes = [f"--note {0.05 + 0.005 * k:.3f}:{40 + k}:{60 + k}:0.3" for k in range(13)]
    s = step_run(tools, tmp_path, [*notes, "--button 0.50:SEQ", "--key 0.60:2:100:0.02"],
                 seconds=0.8)
    pairs = " ".join(f"{40 + k} {60 + k}" for k in range(1, 13))
    cmds = [t for _, t in s["seq_ui_cmds"]]
    assert [t for t in cmds if t.split()[0] not in ("non", "nof")] == [f"tog 0 1 {pairs}"]
    assert sum(t.startswith("non ") for t in cmds) == sum(t.startswith("nof ") for t in cmds) == 13


def test_full_velocity_plays_the_keys_at_127(tools, tmp_path):
    """SHIFT + 10 in SEQ mode, then a key in HOME: it sounds at 127, and the
    replay's sidecar says so."""
    log = tmp_path / "c.verbs"
    s = step_run(tools, tmp_path, ["--button 0.05:SEQ", "--button 0.10:SEL:0.05",
                                   "--key 0.12:16:100:0.01", "--button 0.30:HOME",
                                   "--key 0.40:7:60:0.2"], "--log-cmds", str(log))
    assert s["seq_view"]["full_vel"] == 1 and s["popup"] == [] and s["replayable"] == 1
    args = (tmp_path / "c.args").read_text().splitlines()
    assert args[args.index("--note") + 1].split(":")[1:3] == ["60", "127"]


def test_oct_on_a_held_step_is_not_held_for_the_keys(tools, tmp_path):
    """OCT+ pressed on a held step transposes the step and nothing else:
    while it is still down, ALGORITHM does not transpose the keys, and OCT-
    after the step's release moves the octave rather than resetting it."""
    s = step_run(tools, tmp_path, ["--button 0.05:SEQ", "--key 0.10:0:100:0.3",
                                   "--button 0.20:OCT+:0.6", "--turn 0.30:ALGORITHM:3",
                                   "--button 0.60:OCT-"], seconds=1.0)
    assert [t for _, t in s["seq_ui_cmds"]] == ["etrn 0 0 0 -1 1"]
    assert (s["octave"], s["transpose"], s["popup"]) == (-1, 0, ["Octave -1"])


@pytest.mark.parametrize("first,replayable", [("note", 1), ("key", 0)])
def test_notes_in_one_block_replay_only_in_the_apps_order(tools, tmp_path, first, replayable):
    """fm1-render plays a block's note-offs, then its note-ons, in the order
    of its --note arguments. A key's --note joins the sidecar when the key is
    pressed, after every MIDI IN note: a MIDI IN note played after a key in
    the same block cannot be replayed in that order, and the run says so
    (here the replay would differ)."""
    lines = ["--note 0.20:60:100:0.3", "--key 0.20:9:100:0.3"]
    panel = tmp_path / "p.panel"
    panel.write_text("\n".join(lines if first == "note" else lines[::-1]) + "\n")
    cmd = tmp_path / "in.verbs"
    cmd.write_text("#! rate=44118 block=64 tracks=8 end=44118\n@0 bpm 12000\n")
    s, _, _, a, b = two_step(tools, tmp_path, "order", panel, cmd, "--engine", "test-sine", lab=False)
    assert s["replayable"] == replayable
    if replayable:
        assert a == b


@pytest.mark.parametrize("mode,lab,popup,sel_led", [
    ("HOME", True, [], "1"),                              # SHIFT: no popup, its LED on
    ("HOME", False, ["SEL", "works in FX mode"], "0"),    # the public page: as before
    ("FX", True, [], "1"),                                # FX mode: the slot grab, as before
])
def test_sel_is_shift_outside_fx_mode(tools, tmp_path, mode, lab, popup, sel_led):
    script = tmp_path / "in.verbs"
    script.write_text("#! rate=44118 block=64 tracks=8 end=22059\n@0 bpm 12000\n")
    panel = [] if mode == "HOME" else ["--button", "0.05:FX"]
    s = run(tools["sim"], [*(["--lab"] if lab else []), "--engine", "test-sine", "--cmd", str(script),
                           *panel, "--button", "0.10:SEL:5"])
    assert s["popup"] == popup and s["leds"][27 + 3] == sel_led
    if lab:
        assert s["seq_view"]["shift"] == (mode != "FX")


def test_the_ui_state_holds_its_s4_fields_in_its_bound(tools):
    z = json.loads(subprocess.run([str(tools["sim"]), "--sizes"], check=True, capture_output=True,
                                  text=True).stdout)
    assert z["seq_ui_size"] <= 1024
    assert z["seq_ui_size"] >= 16 * 16, "sixteen held steps fit"


# ---- Record and Capture (docs/15 S5) ---------------------------------------------------------

REC_LED = 27 + 13


def rec_run(tools, tmp_path, panel_lines, seconds, script="rec.verbs", *extra):
    """A panel run from tests/fixtures/seq-ui/`script`, the lab switch on,
    Test Sine, ended at `seconds` (whatever is held then stays held)."""
    panel = tmp_path / "p.panel"
    panel.write_text("\n".join(panel_lines) + "\n")
    return run(tools["sim"], ["--lab", "--engine", "test-sine", "--cmd", str(TRACES / script),
                              "--panel", str(panel), "--seconds", str(seconds), *extra])


@pytest.mark.parametrize("seconds,lit,state", [
    (0.50, "1", "counting_in"),     # the count-in: fast, 22,059 % 11,029 < 5,514
    (0.65, "0", "counting_in"),     # 28,676 % 11,029 >= 5,514
    (1.50, "1", "recording"),       # the take, from the bar at 1.1 s: on
    (3.00, "0", None),              # REC again at 2.6 s: off
])
def test_recs_led_follows_the_count_in_and_the_take(tools, tmp_path, seconds, lit, state):
    s = rec_run(tools, tmp_path, ["--button 0.10:REC", "--button 2.60:REC"], seconds)
    assert s["leds"][REC_LED] == lit
    if state:
        assert s["rec"][state] == 1
    assert s["popup"] == []


@pytest.mark.parametrize("seconds,lit", [(0.5, "0"), (1.3, "1"), (1.8, "0")])
def test_recs_led_blinks_slowly_while_capture_holds_notes(tools, tmp_path, seconds, lit):
    """O7: keys played stopped are buffered for Capture; REC blinks at 1 s
    (57,353 % 44,118 < 22,059 at 1.3 s; 79,412 % 44,118 is not, at 1.8 s),
    and is dark with nothing buffered."""
    keys = [] if seconds == 0.5 else ["--key 0.10:7:100:0.1", "--key 0.30:9:100:0.1"]
    s = rec_run(tools, tmp_path, keys, seconds)
    assert s["leds"][REC_LED] == lit
    assert s["rec"]["capture_pending"] == len(keys)


@pytest.mark.parametrize("held,cmds", [(0.40, ["rec 0"]), (0.60, [])])
def test_a_rec_tap_in_seq_mode_is_shorter_than_half_a_second(tools, tmp_path, held, cmds):
    """Stopped in SEQ mode, REC acts on its release (Movy's Rec): let go
    within ceil(0.5 x rate) frames and untouched, it records; later, it was
    step record, which ends with nothing entered."""
    s = rec_run(tools, tmp_path, ["--button 0.05:SEQ", f"--button 0.10:REC:{held}"], 1.0)
    assert [t for _, t in s["seq_ui_cmds"]] == cmds
    assert s["rec"]["srec"] == 0 and s["rec"]["counting_in"] == len(cmds)


def test_step_records_leds_show_the_head_and_the_arrows(tools, tmp_path):
    """REC held in SEQ mode: the head's key blinks fast (0.25 s), A#3 is lit
    (a rest), F#3 only once there is a step to go back to; the screen's
    status says STEP."""
    base = ["--button 0.05:SEQ", "--button 0.10:REC:5"]
    at_start = rec_run(tools, tmp_path, base, 0.50, "steps.verbs")
    assert at_start["rec"]["srec"] == 1 and at_start["rec"]["head"] == 0
    assert at_start["seq_view"]["role_leds"] == 0b100          # A#3 only
    assert at_start["leds"][REC_LED] == "1"
    on, off = (rec_run(tools, tmp_path, base + ["--key 0.20:5:100:0.05"], t, "steps.verbs")
               for t in (0.50, 0.65))
    assert on["rec"]["head"] == off["rec"]["head"] == 1
    assert on["seq_view"]["role_leds"] == off["seq_view"]["role_leds"] == 0b101
    assert on["seq_view"]["key_leds"] & 0b10 and not off["seq_view"]["key_leds"] & 0b10


def test_step_record_takes_full_velocity_and_ends_with_play(tools, tmp_path):
    """SHIFT + 10's full velocity enters step record's pitches at 127;
    PLAY/STOP while REC is held ends step record (a stopped-transport mode),
    and REC's release then records nothing."""
    s = rec_run(tools, tmp_path, ["--button 0.05:SEQ", "--button 0.10:SEL:0.05",
                                  "--key 0.12:16:100:0.02", "--button 0.30:REC:0.5",
                                  "--key 0.40:0:60:0.1", "--button 0.60:PLAY/STOP"], 1.2,
                "steps.verbs")
    assert [t for _, t in s["seq_ui_cmds"]] == ["del 0 0 0 -1", "addp 0 0 0 53 127", "play"]
    assert s["rec"]["srec"] == 0 and s["rec"]["counting_in"] == 0 and s["rec"]["recording"] == 0


def test_capture_while_playing_says_captured(tools, tmp_path):
    s = rec_run(tools, tmp_path, ["--button 0.10:PLAY/STOP", "--key 0.30:9:100:0.1",
                                  "--button 0.60:SEL:0.1", "--button 0.65:REC"], 0.8)
    assert [t for _, t in s["seq_ui_cmds"]][-1] == "cap 0" and s["popup"] == ["Captured"]
    nothing = rec_run(tools, tmp_path, ["--button 0.60:SEL:0.1", "--button 0.65:REC"], 0.8)
    assert nothing["seq_ui_cmds"] == [] and nothing["popup"] == ["Nothing to capture"]


def test_a_stopped_capture_opens_the_picker_until_a_press(tools, tmp_path):
    """The stopped Capture's tempo picker (O7): the core's three candidates,
    the transport running at the one taken, and the overlay up until a
    press; SELECT takes another tempo, heard at once. A key pressed then
    closes it and plays nothing: no note in the replay's sidecar."""
    panel = TRACES / "capture-stopped-picker.panel"
    lines = [l for l in panel.read_text().splitlines() if l and not l.startswith("#")]
    up = rec_run(tools, tmp_path, lines, 3.55, "empty.verbs")
    r = up["rec"]
    assert r["capture_mode"] == 1 and r["capture_n"] == 3 and up["seq_view"]["playing"] == 1
    assert r["bpm_x100"] == 100 * r["capture_cands"][r["capture_sel"]]
    picked = rec_run(tools, tmp_path, lines, 3.65, "empty.verbs")["rec"]
    assert picked["capture_sel"] == r["capture_sel"] - 1
    assert picked["bpm_x100"] == 100 * picked["capture_cands"][picked["capture_sel"]]
    s, _, log, a, b = two_step(tools, tmp_path, "picker", panel, TRACES / "empty.verbs",
                               "--engine", "test-sine")
    assert s["rec"]["capture_mode"] == 0 and log.rstrip().endswith("capdone") and a == b
    assert (tmp_path / "picker.args").read_text().count("--note") == 6, "the closing key sounded"
