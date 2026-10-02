"""The sequencer on the virtual FM-1's panel (docs/15 stages S3 and S4),
behind the lab switch: golden gesture traces with two-step parity (§6.3),
the typed commands' text round trip, the demo pattern, the switch itself,
and step entry: taps, holds, the Step pages, SHIFT, bar paging and the
LEDs.

A gesture trace is a .panel file (one --key, --button, --turn or --note per
line) and its golden .verbs, what `fm1-sim-render --lab --log-cmds` writes
for it: the script lines as applied and every command the panel sent, at
the block it led. Two-step parity: fm1-render replaying that file, with the
sidecar of arguments the harness writes next to it (.args: the engine, the
notes the keys and MIDI IN played, the knob turns on the sound), renders
the same bytes as the panel run. Every trace here plays Test Sine; S3's
start from tests/fixtures/seq-ui/input.verbs, S4's (step-*) from
steps.verbs, a bar at 240 BPM, or the input TRACE_INPUT names. The parity
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
TRACE_INPUT = {"step-hidden-tail": "tail.verbs"}
WHITE = [0, 2, 4, 6, 7, 9, 11, 12, 14, 16, 18, 19, 21, 23, 24, 26]   # white key n -> key index
BUTTONS = ["OCT-", "OCT+", "FX", "SEL", "ENV", "LFO", "EDIT", "GLO", "HOME", "SAVE", "ARP", "SEQ",
           "PLAY/STOP", "REC"]


def trace_input(stem):
    return TRACES / TRACE_INPUT.get(stem, "steps.verbs" if stem.startswith("step-") else "input.verbs")


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
        assert "play" in played and s["peak"] > 0.01
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
    assert {x["name"] for x in panels} >= {"seq-panel-play-stop", "seq-panel-step-entry"}
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
            assert verbs == {"tog", "eprob", "econd", "einv", "enudge", "addp", "del", "play"}
            assert any(t.startswith("tog 0 16 ") for t in played), "the clip's second bar"


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
    assert [t for _, t in s["seq_ui_cmds"]] == [f"tog 0 1 {pairs}"]


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
