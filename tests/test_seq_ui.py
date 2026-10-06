"""The sequencer on the virtual FM-1's panel (docs/15 stages S3 to S8;
behind a lab switch until 2026-10-05): golden gesture traces with two-step
parity (§6.3), the typed commands' text round trip, the demo pattern, step
entry (taps, holds, the Step pages, SHIFT, bar paging and the LEDs),
record and Capture (REC, step record, SHIFT + REC, live input from the
keys and MIDI IN, and REC's LED), tracks (focus, mute, the Set, Clip
and Track pages, the metronome's click and the browser's routes), and
parameter locks (the lock pages, the 7-bit knob grid and the lanes' bases,
live takes, CLEAR, and the traces transcribed from Movy's own tests).

A gesture trace is a .panel file (one --key, --button, --turn or --note per
line) and its golden .verbs, what `fm1-sim-render --log-cmds` writes
for it: the script lines as applied and every command the panel sent, at
the block it led. Two-step parity: fm1-render replaying that file, with the
sidecar of arguments the harness writes next to it (.args: the engine, the
notes the keys and MIDI IN played, the knob turns on the sound), renders
the same bytes as the panel run. Every trace here plays Test Sine; S3's
start from tests/fixtures/seq-ui/input.verbs, S4's (step-*) from
steps.verbs, a bar at 240 BPM, S5's (rec-*, capture-*) from rec.verbs, two
notes at 240 BPM for 4 s, S6's (track-*, mute-*, set-*, metro-*, clip-*,
pages-*) from tracks.verbs, four tracks routed to the sound, S8's (lock-*)
from steps.verbs with Macro, which has eight lockable parameters and a
NOLOCK one, or the input TRACE_INPUT names. A note
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
BLACK = [1, 3, 5, 8, 10, 13, 15, 17, 20, 22, 25]                     # role_leds bit n -> key index
MUTE_KEY, PREV_KEY, NEXT_KEY = 13, 20, 22                            # F#4, C#5, D#5 (S6)
ROLE_MUTE, ROLE_PREV, ROLE_NEXT = (1 << BLACK.index(MUTE_KEY), 1 << BLACK.index(PREV_KEY),
                                   1 << BLACK.index(NEXT_KEY))


S6_PREFIXES = ("track-", "mute-", "set-", "metro-", "clip-", "pages-")


def trace_engine(stem):
    return "macro" if stem.startswith("lock-") else "test-sine"


def trace_input(stem):
    default = ("steps.verbs" if stem.startswith(("step-", "lock-")) else
               "rec.verbs" if stem.startswith(("rec-", "capture-")) else
               "tracks.verbs" if stem.startswith(S6_PREFIXES) else "input.verbs")
    return TRACES / TRACE_INPUT.get(stem, default)


def two_step(tools, tmp_path, name, panel, cmd, *args):
    """The panel run and its replay: (panel summary, replay summary, the
    logged script, the panel run's WAV, the replay's WAV)."""
    log, a, b = tmp_path / f"{name}.verbs", tmp_path / f"{name}-panel.wav", tmp_path / f"{name}-replay.wav"
    s = run(tools["sim"], [*args, "--cmd", str(cmd), "--panel", str(panel),
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
    s6 = {"track-focus", "track-focus-from-home", "mute-tap", "mute-map", "set-page",
          "metro-shortcut", "clip-page", "clip-quant-cycle", "track-page-route", "pages-browse"}
    assert stems >= s6
    s8 = {"lock-knob-sync", "lock-eight-lanes", "lock-several-held",
          "lock-several-clear"} | set(MOVY_TRACES)
    assert stems >= s8


@pytest.mark.parametrize("panel", PANELS, ids=lambda p: p.stem)
def test_a_trace_logs_its_golden_verbs_and_replays_byte_for_byte(tools, tmp_path, panel):
    s, r, log, a, b = two_step(tools, tmp_path, panel.stem, panel, trace_input(panel.stem),
                               "--engine", trace_engine(panel.stem))
    assert log == panel.with_suffix(".verbs").read_text(), "not the golden trace"
    assert s["replayable"] == 1
    assert a == b, "two-step parity: the replay differs"
    assert s["seq_dropped"] == r["seq_dropped"] == 0 and s["seq_busy"] == s["seq_held"] == 0
    assert s["seq_notes_to_engine"] == r["seq_notes_to_engine"]
    played = [t for _, t in s["seq_ui_cmds"]]
    if panel.stem.startswith(S6_PREFIXES):
        # Browsing never empties Capture (docs/15 §3.6): no `clipsel` or
        # `launch` from any of these, and `watch` only from a focus gesture.
        verbs = [t.split()[0] for t in played]
        assert "clipsel" not in verbs and "launch" not in verbs
        assert ("watch" in verbs) == (panel.stem in {"track-focus", "track-focus-from-home",
                                                      "track-page-route"})
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
    s = run(tools["sim"], ["--engine", "test-sine", "--cmd", str(TRACES / "input.verbs"),
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
                                           "seq-panel-record", "seq-panel-capture-stopped",
                                           "multi-panel", "seq-panel-tracks", "seq-panel-locks"}
    for sc in panels:
        seq = ROOT / "sim" / "web" / "test"
        args = ["--engine", sc["engine"], "--seconds", str(sc["seconds"])]
        for p in sc.get("params", []):
            args += ["--param", p]
        for fx, ps in sc.get("fx", []):
            args += ["--fx", fx]
            for p in ps:
                args += ["--fx-param", p]
        for k, sound, ps in sc.get("sounds", []):           # multi-sound (docs/15 §3.16)
            args += ["--sound", f"{k}:{sound}"] + [a for p in ps for a in ("--sound-param", f"{k}:{p}")]
        for k, fx, ps in sc.get("inserts", []):
            args += ["--insert", f"{k}:{fx}"] + [a for p in ps for a in ("--insert-param", f"{k}:{p}")]
        s, r, log, a, b = two_step(tools, tmp_path, sc["name"], seq / sc["panel"], seq / sc["cmd"],
                                   *args)
        assert s["replayable"] == 1 and a == b and s["peak"] > 0.01
        if sc["name"] != "seq-panel-play-stop":
            continue                    # modulation's (tests/test_sim_mod.py)
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
        if sc["name"] == "seq-panel-tracks":
            assert played == ["play", "watch 1", "route 1 1 1", "mute 3 1", "swing 60", "bpm 12400",
                              "cscl 1 1 2", "cscl 1 2 1", "metro 1", "metro 0", "mute 1 1"]
            assert sidecar.startswith("--slots\n") and s["current"] == 1, "Sound 2 follows track 2"
            assert s["seq_clicks"] == r["seq_clicks"] == 2
        if sc["name"] == "seq-panel-locks":
            assert played == ["alabel 0 0 synth:Timbre", "abase 0 0 64", "aset 0 0 4 94 1",
                              "alabel 0 1 synth:Morph", "abase 0 1 64", "aset 0 1 4 44 1",
                              "alabel 0 2 synth:Harmonics", "abase 0 2 64", "aset 0 2 12 89 1",
                              "play", "abaseq 0 0 54", "stop", "play"]
            assert sidecar.count("--param-at") == 4, "three snaps at the lanes' births, one turn"
            lk = s["locks"]
            assert lk["shown_mask"] == 0b1110 and lk["shown"][1:4] == lk["value"][1:4], \
                "after the stop's D6 revert the engine heard the knobs' values to the bit"
        if sc["name"] == "multi-panel":
            assert sidecar.startswith("--slots\n"), "the replay routes by slot"
            assert sidecar.count("--sound-note\n1:") == 2, "Sound 2's key and MIDI IN note"
            assert sidecar.count("--sound-param-at\n1:") == 1 and sidecar.count("--level-at") == 2
            # The keys and MIDI IN notes are live input to track 1 too (S5).
            verbs = [t.split()[0] for t in played]
            assert verbs[0] == "play" and verbs[-1] == "stop"
            assert verbs.count("non") == verbs.count("nof") == 4 and len(verbs) == 10


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
    assert out["verbs"] == len(names) == 77
    assert out["records"] >= 77 * 30


def test_the_demo_pattern_plays_on_the_browsers_start_only(tools):
    """The demo pattern (owner decision O4) comes with the browser's start
    chain, on every start since the lab switch went: PLAY/STOP then plays
    it. Without the start chain (every test and parity run) the sequencer
    starts empty."""
    demo = run(tools["sim"], ["--start", "--seconds", "2", "--button", "0.1:PLAY/STOP"])
    assert demo["engine"] == "macro" and demo["fx"] == ["plate", ""]
    assert demo["peak"] > 0.05 and demo["seq_view"]["clip_playing"] == 1
    assert demo["leds"][27 + 12] == "1" and demo["popup"] == []
    empty = run(tools["sim"], ["--engine", "macro", "--seconds", "2", "--button", "0.1:PLAY/STOP"])
    assert empty["peak"] == 0 and empty["seq_view"]["clip_playing"] == 0


def test_a_change_of_sound_from_the_panel_is_not_replayable(tools, tmp_path):
    """PRESETS changes the sound, which fm1-render cannot replay (§6.3's
    exclusion): the harness says so instead of logging a wrong replay."""
    panel = tmp_path / "p.panel"
    panel.write_text("--button 0.1:PLAY/STOP\n--turn 0.3:PRESETS:1\n")
    s = run(tools["sim"], ["--engine", "test-sine", "--cmd", str(TRACES / "input.verbs"),
                           "--panel", str(panel), "--log-cmds", str(tmp_path / "c.verbs")])
    assert s["replayable"] == 0


def test_the_ui_state_fits_its_bound(tools):
    z = json.loads(subprocess.run([str(tools["sim"]), "--sizes"], check=True, capture_output=True,
                                  text=True).stdout)
    assert z["seq_ui_size"] <= z["seq_ui_bytes"] == 1024


# ---- Step entry (docs/15 S4) -----------------------------------------------------------------

def step_run(tools, tmp_path, panel_lines, *extra, script=None, seconds=None):
    """A panel run from steps.verbs (or `script`), Test Sine; `seconds`
    ends it early (a key still held at the end stays held)."""
    panel = tmp_path / "p.panel"
    panel.write_text("\n".join(panel_lines) + "\n")
    cmd = TRACES / "steps.verbs"
    if script is not None:
        cmd = tmp_path / "in.verbs"
        cmd.write_text(script)
    args = ["--engine", "test-sine", "--cmd", str(cmd), "--panel", str(panel), *extra]
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
    dark and A#3 (on) lit, since a second, empty bar can be reached; since
    S6 MUTE (F#4) and the next track (D#5) lit too, the previous (C#5) dark
    on track 1. A held step is lit, the steps under its note blink at the
    1 s rate, and both bar keys light (they nudge); MUTE and the track keys
    go dark."""
    s = step_run(tools, tmp_path, ["--button 0.05:SEQ"], seconds=0.3)
    assert lit_keys(s) == {WHITE[0], WHITE[4], WHITE[8], WHITE[12], 5, MUTE_KEY, NEXT_KEY}
    assert s["seq_view"]["role_leds"] == 0b100 | ROLE_MUTE | ROLE_NEXT
    assert s["seq_view"]["key_leds"] == 0x1111
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
    assert s["seq_view"]["bar"] == 0 and s["seq_view"]["role_leds"] == ROLE_MUTE | ROLE_NEXT, \
        "no clip: bar 1 only"
    s = step_run(tools, tmp_path, ["--button 0.05:SEQ"] + [f"--key {0.1 + 0.05 * k:.2f}:5:100:0.02"
                                                         for k in range(4)], seconds=0.5)
    assert s["seq_view"]["bar"] == 1 and s["seq_view"]["role_leds"] == 0b001 | ROLE_MUTE | ROLE_NEXT
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
    s, _, _, a, b = two_step(tools, tmp_path, "order", panel, cmd, "--engine", "test-sine")
    assert s["replayable"] == replayable
    if replayable:
        assert a == b


@pytest.mark.parametrize("mode", ["HOME", "FX"])
def test_sel_is_shift_outside_fx_mode(tools, tmp_path, mode):
    """SEL held outside FX mode is SHIFT, its LED on and no popup; in FX
    mode it is the slot grab, as before."""
    script = tmp_path / "in.verbs"
    script.write_text("#! rate=44118 block=64 tracks=8 end=22059\n@0 bpm 12000\n")
    panel = [] if mode == "HOME" else ["--button", "0.05:FX"]
    s = run(tools["sim"], ["--engine", "test-sine", "--cmd", str(script), *panel, "--button", "0.10:SEL:5"])
    assert s["popup"] == [] and s["leds"][27 + 3] == "1"
    assert s["seq_view"]["shift"] == (mode != "FX")


def test_the_ui_state_holds_its_s4_fields_in_its_bound(tools):
    z = json.loads(subprocess.run([str(tools["sim"]), "--sizes"], check=True, capture_output=True,
                                  text=True).stdout)
    assert z["seq_ui_size"] <= 1024
    assert z["seq_ui_size"] >= 16 * 16, "sixteen held steps fit"


# ---- Record and Capture (docs/15 S5) ---------------------------------------------------------

REC_LED = 27 + 13


def rec_run(tools, tmp_path, panel_lines, seconds, script="rec.verbs", *extra):
    """A panel run from tests/fixtures/seq-ui/`script`, Test Sine, ended at
    `seconds` (whatever is held then stays held)."""
    panel = tmp_path / "p.panel"
    panel.write_text("\n".join(panel_lines) + "\n")
    return run(tools["sim"], ["--engine", "test-sine", "--cmd", str(TRACES / script),
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


def test_live_input_is_released_once_whatever_the_mode_or_a_panic(tools, tmp_path):
    """A key played in HOME is live input; entering SEQ mode while it is
    held does not keep its release from the sequencer. A change of sound
    (PRESETS) lets every note given go at once, and the key's own release
    afterwards gives nothing more, so no note is left on or let go twice."""
    seq = rec_run(tools, tmp_path, ["--key 0.10:7:100:0.5", "--button 0.30:SEQ"], 1.0)
    assert [t for _, t in seq["seq_ui_cmds"]] == ["non 0 60 100", "nof 0 60"]
    assert seq["seq_ui_cmds"][1][0] >= int(0.6 * 44118) - 64
    panic = rec_run(tools, tmp_path, ["--key 0.10:7:100:0.5", "--turn 0.30:PRESETS:1"], 1.0)
    cmds = panic["seq_ui_cmds"]
    assert [t for _, t in cmds] == ["non 0 60 100", "nof 0 60"]
    assert cmds[1][0] < int(0.35 * 44118), "released at the change of sound, not at the key's"


def test_step_record_takes_a_midi_pitch_already_down_once(tools, tmp_path):
    """A second note-on of a pitch already down in step record enters
    nothing, and its first release closes the chord (one pad, as Movy's
    map of held pads), so the head moves on and the chord is not held open
    by a release that never comes."""
    s = rec_run(tools, tmp_path, ["--button 0.05:SEQ", "--button 0.10:REC:5",
                                  "--note 0.30:62:100:0.3", "--note 0.40:62:90:0.05"], 0.5,
                "steps.verbs")
    assert [t for _, t in s["seq_ui_cmds"]] == ["del 0 0 0 -1", "addp 0 0 0 62 100"]
    assert s["rec"]["srec"] == 1 and s["rec"]["head"] == 1


@pytest.mark.parametrize("engine,pitches", [
    ("test-sine", (53, 55, 57)),        # F3, G3, A3 at octave 0
    ("drums", (36, 37, 38)),            # a pad kit: the kick, the rim, the snare
    ("sw-sophie", (36, 37, 38)),
])
def test_step_record_enters_the_note_the_key_plays(tools, tmp_path, engine, pitches):
    """Step record enters the note a white key sounds: its pitch, or with a
    pad kit as the sound (fm1_engine.h, pad_count) the pad it plays, not
    53 + key, which the kit would leave silent on playback. OCT+ moves the
    pitches, not the pads."""
    panel = tmp_path / "p.panel"
    lines = ["--button 0.03:OCT+", "--button 0.05:SEQ", "--button 0.10:REC:0.8"]
    lines += [f"--key {0.2 + 0.1 * i:.2f}:{WHITE[i]}:100:0.05" for i in range(3)]
    panel.write_text("\n".join(lines) + "\n")
    s = run(tools["sim"], ["--engine", engine, "--cmd", str(TRACES / "steps.verbs"),
                           "--panel", str(panel), "--seconds", "1.2"])
    up = 12 if engine == "test-sine" else 0
    want = sum(([f"del 0 {i} {i} -1", f"addp 0 {i} {i} {p + up} 100"]
                for i, p in enumerate(pitches)), [])
    assert [t for _, t in s["seq_ui_cmds"]] == want


@pytest.mark.parametrize("engine,pitches", [("test-sine", (69, 77)), ("drums", (38, 43))])
def test_shift_adds_the_note_the_key_plays_to_held_steps(tools, tmp_path, engine, pitches):
    """O22's SHIFT pitches (tests/fixtures/seq-ui/step-add-pitch.panel) with
    a pad kit as the sound: white keys 3 and 8 add the snare (38) and the
    floor tom (43), the pads they play, where a pitched sound gets A4 and F5."""
    s = run(tools["sim"], ["--engine", engine, "--cmd", str(TRACES / "input.verbs"),
                           "--panel", str(TRACES / "step-add-pitch.panel")])
    assert [t for _, t in s["seq_ui_cmds"]] == [f"addp 0 4 4 {pitches[0]} 90",
                                                 f"addp 0 4 4 {pitches[1]} 100", "play"]


def test_step_record_wraps_at_the_end_of_a_loop_on_a_later_bar(tools, tmp_path):
    """A loop on bar 2 (steps 17-32 of a 3-bar clip): the head starts on its
    first step and wraps at its end, the bar on the keys following it, and
    SHIFT + white key 1 moves it to the loop's first step (docs/15 S5: Movy
    compares the head with the loop's length, the same for a loop on bar
    1). Leaving SEQ mode ends step record, and REC's release then records
    nothing."""
    script = tmp_path / "loop.verbs"
    script.write_text("#! rate=44118 block=64 tracks=8 end=176472\n"
                      "@0 bpm 24000;clen 0 48;tog 0 20 60 100;loop 0 16 16\n")
    base = ["--button 0.05:SEQ", "--button 0.10:REC:3"]
    rests = [f"--key {0.2 + k * 0.1:.2f}:5:100:0.03" for k in range(20)]
    start = rec_run(tools, tmp_path, base, 0.15, script)
    assert start["rec"]["head"] == 16 and start["seq_view"]["bar"] == 1
    wrapped = rec_run(tools, tmp_path, base + rests, 2.25, script)
    assert wrapped["rec"]["head"] == 20 and wrapped["seq_view"]["bar"] == 1
    jump = rec_run(tools, tmp_path, base + rests + ["--button 2.30:SEL:0.2", "--key 2.35:0:100:0.05",
                                                     "--button 2.70:HOME"], 3.5, script)
    assert jump["rec"]["srec"] == 0 and jump["seq_view"]["playing"] == 0
    assert [t for _, t in jump["seq_ui_cmds"]] == [], "rests and a jump to an empty step send nothing"
    moved = rec_run(tools, tmp_path, base + rests + ["--button 2.30:SEL:0.2",
                                                      "--key 2.35:0:100:0.05"], 2.45, script)
    assert moved["rec"]["head"] == 16


def test_the_fitted_tempo_stays_through_select_and_knob1(tools, tmp_path):
    """Over the fitted tempo (capture_mode 2) SELECT and KNOB1 do nothing,
    as Movy's jog does there; another press closes it (`capdone`)."""
    panel = TRACES / "capture-stopped-fitted.panel"
    lines = [l for l in panel.read_text().splitlines() if l and not l.startswith("#")]
    lines = [l for l in lines if "FX" not in l] + ["--turn 2.20:SELECT:1", "--turn 2.30:KNOB1:-1"]
    up = rec_run(tools, tmp_path, lines, 2.40)
    assert up["rec"]["capture_mode"] == 2
    assert [t for _, t in up["seq_ui_cmds"]][-1] == "cap 0"
    closed = rec_run(tools, tmp_path, lines + ["--turn 2.45:KNOB2:1"], 2.60)
    assert closed["rec"]["capture_mode"] == 0
    assert [t for _, t in closed["seq_ui_cmds"]][-2:] == ["cap 0", "capdone"]


# ---- Tracks, mute and the pages (docs/15 S6) --------------------------------------------------

def tracks_run(tools, tmp_path, panel_lines, *extra, seconds=None):
    """A panel run from tracks.verbs: four tracks at 240 BPM, Test Sine."""
    panel = tmp_path / "p.panel"
    panel.write_text("\n".join(panel_lines) + "\n")
    args = ["--engine", "test-sine", "--cmd", str(TRACES / "tracks.verbs"), "--panel",
            str(panel), *extra]
    if seconds is not None:
        args += ["--seconds", str(seconds)]
    return run(tools["sim"], args)


def cmds_of(s):
    return [t for _, t in s["seq_ui_cmds"]]


def test_the_traces_do_what_their_names_say(tools, tmp_path):
    """The S6 traces' commands, beyond the golden text: the focus gestures'
    `watch`, the mute map's tracks, the pages' values, and nothing at all
    from browsing."""
    def played(stem):
        return cmds_of(run(tools["sim"], ["--engine", "test-sine", "--cmd",
                                          str(TRACES / "tracks.verbs"), "--panel",
                                          str(TRACES / f"{stem}.panel")]))
    assert played("track-focus") == ["watch 1", "watch 2", "watch 1", "play"]
    assert played("mute-map") == ["play", "mute 1 1", "mute 2 1", "mute 1 0"]
    assert played("set-page") == ["bpm 24300", "bpm 24320", "swing 60", "dq 70", "metro 1", "play"]
    assert played("clip-page") == ["cscl 0 1 2", "play", "cscl 0 2 1", "clen 0 8", "ctr 0 7",
                                   "cq 0 50"]
    assert played("clip-quant-cycle") == ["dq 70", "cq 0 70", "cq 0 100", "cq 0 0", "play"]
    assert played("track-page-route") == ["play", "watch 1", "route 1 0 2", "route 1 0 5",
                                          "route 1 1 0", "mute 1 1", "mute 1 0"]
    assert played("pages-browse") == ["play"]


def test_a_focus_from_home_goes_back_there_and_capture_follows(tools, tmp_path):
    """SEQ held with a white key focuses its track from HOME and goes back
    there on SEQ's release; the keys' live input and Capture then follow the
    track (the core's `watch`)."""
    s = run(tools["sim"], ["--engine", "test-sine", "--cmd", str(TRACES / "tracks.verbs"),
                           "--panel", str(TRACES / "track-focus-from-home.panel")])
    assert s["mode"] == 0 and s["seq_view"]["track"] == 2
    assert cmds_of(s) == ["play", "watch 2", "non 2 65 100", "nof 2 65", "cap 2"]
    held = tracks_run(tools, tmp_path, ["--button 0.05:SEQ:0.5"], seconds=0.3)
    assert held["mode"] == 3 and held["seq_view"]["key_leds"] == 1, "SEQ held: the focused key"
    # A SEQ press with no focus stays in SEQ mode.
    plain = tracks_run(tools, tmp_path, ["--button 0.05:SEQ:0.1"], seconds=0.3)
    assert plain["mode"] == 3


@pytest.mark.parametrize("button,mode", [("FX", 1), ("GLO", 2)])
def test_a_focus_from_fx_or_glo_goes_back_there(tools, tmp_path, button, mode):
    s = tracks_run(tools, tmp_path, [f"--button 0.05:{button}", "--button 0.10:SEQ:0.1",
                                     "--key 0.12:4:100:0.02"], seconds=0.4)
    assert s["mode"] == mode and s["seq_view"]["track"] == 2 and cmds_of(s) == ["watch 2"]


def test_seq_let_go_outside_seq_mode_leaves_the_white_keys_steps(tools, tmp_path):
    """SEQ held, HOME pressed, SEQ let go in HOME: nothing is held over, so
    back in SEQ mode a white key is a step again, not a track."""
    s = tracks_run(tools, tmp_path, ["--button 0.05:SEQ:0.2", "--button 0.10:HOME",
                                     "--button 0.40:SEQ", "--key 0.45:2:100:0.02"], seconds=0.6)
    assert s["mode"] == 3 and s["seq_view"]["track"] == 0 and cmds_of(s) == ["tog 0 1 60 100"]


def test_focus_says_when_capture_was_emptied(tools, tmp_path):
    played = ["--note 0.05:60:100:0.1", "--button 0.30:SEQ:0.2", "--key 0.35:4:100:0.02"]
    s = tracks_run(tools, tmp_path, played, seconds=0.45)
    assert s["popup"] == ["Track 3", "Capture emptied"]
    again = tracks_run(tools, tmp_path, ["--button 0.30:SEQ:0.2", "--key 0.35:4:100:0.02"],
                       seconds=0.45)
    assert again["popup"] == ["Track 3"]
    same = tracks_run(tools, tmp_path, ["--note 0.05:60:100:0.1", "--button 0.30:SEQ:0.2",
                                        "--key 0.35:0:100:0.02"], seconds=0.45)
    assert same["popup"] == [] and "watch" not in " ".join(cmds_of(same)), \
        "the focused track again: nothing sent, Capture kept"
    assert same["rec"]["capture_pending"] == 1


def test_the_track_keys_stop_at_the_ends(tools, tmp_path):
    s = tracks_run(tools, tmp_path, ["--button 0.05:SEQ"] +
                   [f"--key {0.1 + 0.05 * k:.2f}:22:100:0.02" for k in range(10)], seconds=0.8)
    assert s["seq_view"]["track"] == 7 and cmds_of(s) == [f"watch {t}" for t in range(1, 8)]
    assert s["seq_view"]["role_leds"] & ROLE_PREV and not s["seq_view"]["role_leds"] & ROLE_NEXT


@pytest.mark.parametrize("seconds,muted", [(0.55, set()), (0.75, {1})])
def test_the_mute_map_lights_the_tracks_that_sound(tools, tmp_path, seconds, muted):
    """MUTE held: white keys 1-8 lit while their track sounds, and MUTE;
    track 2, muted from the map, goes dark."""
    s = tracks_run(tools, tmp_path, ["--button 0.05:SEQ", "--key 0.50:13:100:0.5",
                                     "--key 0.60:2:100:0.05"], seconds=seconds)
    assert lit_keys(s) == {WHITE[t] for t in range(8) if t not in muted} | {MUTE_KEY}
    assert s["tracks"]["muted"] == sum(1 << t for t in muted)
    assert s["seq_view"]["hint"] == 0


def test_mute_and_track_keys_wait_while_steps_are_held(tools, tmp_path):
    s = tracks_run(tools, tmp_path, ["--button 0.05:SEQ", "--key 0.10:0:100:0.5",
                                     "--key 0.20:13:100:0.05", "--key 0.30:22:100:0.05"],
                   seconds=0.8)
    assert [t for t in cmds_of(s) if t.split()[0] in ("mute", "watch")] == []
    assert s["seq_view"]["track"] == 0


def test_shift_with_a_page_open_keeps_it_and_a_step_key_closes_it(tools, tmp_path):
    base = ["--button 0.05:SEQ", "--button 0.10:SEL:0.05", "--key 0.12:7:100:0.01"]
    page = tracks_run(tools, tmp_path, base, seconds=0.3)
    assert page["seq_view"]["view"] == 2 and page["popup"] == []
    metro = tracks_run(tools, tmp_path, base + ["--button 0.30:SEL:0.05", "--key 0.32:9:100:0.01"],
                       seconds=0.5)
    assert metro["seq_view"]["view"] == 2 and metro["popup"] == ["Metronome", "on"]
    step = tracks_run(tools, tmp_path, base + ["--key 0.30:2:100:0.02"], seconds=0.5)
    assert step["seq_view"]["view"] == 0 and cmds_of(step) == ["tog 0 1 60 100"]


def test_the_tempo_knob_clamps_and_takes_a_tenth_with_shift(tools, tmp_path):
    base = ["--button 0.05:SEQ", "--button 0.10:SEL:0.05", "--key 0.12:7:100:0.01"]
    up = tracks_run(tools, tmp_path, base + [f"--turn {0.2 + 0.01 * k:.2f}:KNOB1:64" for k in range(2)],
                    seconds=0.5)
    assert cmds_of(up)[-1] == "bpm 30000" and up["rec"]["bpm_x100"] == 30000
    fine = tracks_run(tools, tmp_path, base + ["--button 0.20:SEL:0.1", "--turn 0.22:KNOB1:-3"],
                      seconds=0.5)
    assert cmds_of(fine) == ["bpm 23970"]


@pytest.mark.parametrize("delta,speed", [(-64, [1, 8]), (-1, [3, 4]), (1, [3, 2]), (64, [4, 1])])
def test_the_speed_knob_walks_movys_eight_speeds(tools, tmp_path, delta, speed):
    s = tracks_run(tools, tmp_path, ["--button 0.05:SEQ", "--button 0.10:SEL:0.05",
                                     "--key 0.12:4:100:0.01", f"--turn 0.20:KNOB1:{delta}"],
                   seconds=0.4)
    assert s["tracks"]["speed"] == speed and cmds_of(s) == [f"cscl 0 {speed[0]} {speed[1]}"]


def test_the_length_knob_makes_a_clip_only_turned_up(tools, tmp_path):
    """Track 5 has no clip: KNOB2 down sends nothing, up makes one of a step
    a detent, and the clip is at most 256 steps."""
    focus = ["--button 0.02:SEQ", "--button 0.05:SEQ:0.1", "--key 0.07:7:100:0.01",
             "--button 0.20:SEL:0.05", "--key 0.22:4:100:0.01"]
    down = tracks_run(tools, tmp_path, focus + ["--turn 0.30:KNOB2:-3"], seconds=0.5)
    assert cmds_of(down) == ["watch 4"] and down["seq_view"]["length"] == 0
    up = tracks_run(tools, tmp_path, focus + ["--turn 0.30:KNOB2:3", "--turn 0.32:KNOB2:64",
                                              "--turn 0.34:KNOB2:64", "--turn 0.36:KNOB2:64",
                                              "--turn 0.38:KNOB2:64", "--turn 0.40:KNOB2:64"],
                    seconds=0.6)
    assert cmds_of(up)[:2] == ["watch 4", "clen 4 3"] and cmds_of(up)[-1] == "clen 4 256"


def test_a_route_on_the_track_page_makes_its_sound_current(tools, tmp_path):
    """Focusing a track or routing it to a sound makes that sound current
    (S6), so the keys play what the track plays; SHIFT + PRESETS can still
    choose another one after."""
    s = tracks_run(tools, tmp_path, ["--button 0.05:SEQ", "--button 0.10:SEL:0.05",
                                     "--key 0.12:2:100:0.01", "--turn 0.20:KNOB2:1"],
                   "--sound", "1:shapes", seconds=0.4)
    assert cmds_of(s) == ["route 0 1 1"] and s["current"] == 1
    assert s["tracks"]["route"] == [1, 1]
    back = tracks_run(tools, tmp_path, ["--button 0.05:SEQ", "--button 0.10:SEL:0.05",
                                        "--key 0.12:2:100:0.01", "--turn 0.20:KNOB2:1",
                                        "--button 0.30:SEQ:0.2", "--key 0.32:2:100:0.01"],
                      "--sound", "1:shapes", seconds=0.6)
    assert back["current"] == 0, "track 2, on Sound 1: Sound 1 current again"


def test_the_browsers_start_routes_every_track_to_sound_1(tools):
    """O10 as changed (2026-10-02): on the browser's start chain every
    track plays Sound 1 until the user routes it; track 1 by the
    default-route rule, the others by fm1_app_seq_start_routes. The Track
    page reads it. Without the start chain (tests, parity) track 8 stays on
    its own MIDI channel."""
    panel = ["--button", "0.05:SEQ", "--button", "0.08:SEQ:0.1", "--key", "0.09:12:100:0.01"]
    s = run(tools["sim"], ["--start", "--seconds", "0.4", *panel])
    assert s["seq_view"]["track"] == 7 and s["tracks"]["route"] == [1, 0]
    plain = run(tools["sim"], ["--engine", "macro", "--seconds", "0.4", *panel])
    assert plain["seq_view"]["track"] == 7 and plain["tracks"]["route"] == [0, 8]


def test_the_click_sounds_only_while_the_metronome_is_on(tools, tmp_path):
    """O11: the bridge's click, the same in the app and fm1-render, block
    for block; none with `metro 0`, not even the count-in's."""
    script = tmp_path / "click.verbs"
    script.write_text("#! rate=44118 block=64 tracks=8 end=132354\n"
                      "@0 metro 1;play\n@44118 metro 0\n@66000 metro 1\n")
    a, b = tmp_path / "a.wav", tmp_path / "b.wav"
    s = run(tools["sim"], ["--engine", "test-sine", "--cmd", str(script), "--out", str(a)])
    r = run(tools["render"], ["--engine", "test-sine", "--cmd", str(script), "--frames", "64",
                              "--out", str(b)])
    assert s["seq_clicks"] == r["seq_clicks"] == 5 and a.read_bytes() == b.read_bytes()
    assert s["peak"] > 0.3
    count_in = tmp_path / "count.verbs"
    count_in.write_text("#! rate=44118 block=64 tracks=8 end=88236\n@0 rec 0\n")
    quiet = run(tools["sim"], ["--engine", "test-sine", "--cmd", str(count_in)])
    assert quiet["seq_clicks"] == 0 and quiet["peak"] == 0


# ---- Parameter locks (docs/15 S8) ------------------------------------------------------------

MOVY = ROOT / "reference" / "movy"
MOVY_SOURCES = [MOVY / "browser-test" / "logic" / "automation.mjs", MOVY / "src" / "seq" / "automation.ts",
                MOVY / "src" / "seq" / "edit-ops.ts"]


def _aset_after(cmds, pattern):
    hit = [i for i, c in enumerate(cmds) if re.fullmatch(pattern, c)]
    return cmds[hit[0] + 1:] if hit else None


# The traces transcribed from Movy's own tests (tests/fixtures/seq-ui/lock-movy-*, with Movy's MIT
# notice), each with the assertions of Movy's they reproduce: the assertion as Movy's source at
# 9190e79 writes it, and what it asks of the commands the FM-1's panel sent for the same gesture.
# Movy's parameter is `cutoff` at 1 of 0..2; the FM-1's is Macro's Timbre at 0.5 of 0..1, the same
# 7-bit 64.
MOVY_TRACES = {
    "lock-movy-held-step": [
        ("q.includes('alabel 0 0 synth:cutoff')", lambda c: "alabel 0 0 synth:Timbre" in c),
        ("q.includes('abase 0 0 64')", lambda c: "abase 0 0 64" in c),
        (r"/^aset 0 0 4 \d+ 1$/.test(o)", lambda c: any(re.fullmatch(r"aset 0 0 4 \d+ 1", x) for x in c)),
        ("eq('release after step-auto is NOT a tap', editStepUp(0), false)",
         lambda c: not any(x.startswith("tog ") for x in c)),
    ],
    "lock-movy-live-take": [
        (r"/^aset 0 0 7 \d+$/.test(o)", lambda c: any(re.fullmatch(r"aset 0 0 7 \d+", x) for x in c)),
        ("afterRelease.some((o) => o.startsWith('abase 0 0')), false",
         lambda c: not any(x.startswith("abase") for x in _aset_after(c, r"aset 0 0 7 \d+") or ["abase"])),
    ],
    "lock-movy-nolock": [
        ("peekSeqCmdQueue().some((o) => o.startsWith('aset')), false",
         lambda c: c == ["play"]),
    ],
    "lock-movy-tap-clear": [
        ("peekSeqCmdQueue().some((o) => o.startsWith('aclrs 0 0 4'))", lambda c: "aclrs 0 0 4" in c),
    ],
    "lock-movy-clear-knob": [
        ("peekSeqCmdQueue().some((o) => o.startsWith('clipdel')), false",
         lambda c: "aclr 0 0" in c and not any(x.startswith("clipdel") for x in c)),
    ],
    "lock-movy-clear-step": [
        ("() => seqCmd('aclrstep ' + track + ' ' + step)", lambda c: "aclrstep 0 4" in c),
        ("for (const s of steps) clearStepAllAutomation(watchedTrack(), s);",
         lambda c: not any(x.startswith("del ") for x in c)),
    ],
}


def lock_run(tools, tmp_path, panel_lines, *extra, script=None, seconds=None, engine="macro"):
    """A panel run from steps.verbs (or `script`), Macro."""
    panel = tmp_path / "p.panel"
    panel.write_text("\n".join(panel_lines) + "\n")
    cmd = TRACES / "steps.verbs"
    if script is not None:
        cmd = tmp_path / "in.verbs"
        cmd.write_text(script)
    args = ["--engine", engine, "--cmd", str(cmd), "--panel", str(panel), *extra]
    if seconds is not None:
        args += ["--seconds", str(seconds)]
    return run(tools["sim"], args)


def cmds(s):
    return [t for _, t in s["seq_ui_cmds"]]


def test_every_parameter_is_on_the_lock_grid(tools):
    """docs/15 S8's round trip, on every parameter of every registered
    engine and effect: fm1_seq_value7 inverts every lock value of a FLOAT,
    and gives every list entry's lowest 7-bit value; a knob detent moves one
    7-bit value or one entry (O14); the lane label the UI writes names the
    parameter (a space as '_')."""
    res = subprocess.run([str(tools["sim"]), "--lock-check"], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["failures"] == 0 and out["engines"] >= 14 and out["params"] >= 78
    assert out["checks"] >= out["params"] * 128


@pytest.mark.parametrize("stem", sorted(MOVY_TRACES))
def test_movys_automation_traces_are_reproduced(tools, tmp_path, stem):
    """The Movy-derived traces (docs/15 S8): the panel sends what Movy's
    tests assert for the same gesture. With Movy at 9190e79 under
    reference/movy (git-ignored), each assertion is also found, word for
    word, in its source, so the transcription cannot drift from it."""
    s = run(tools["sim"], ["--engine", "macro", "--cmd", str(TRACES / "steps.verbs"),
                           "--panel", str(TRACES / f"{stem}.panel")])
    for quoted, holds in MOVY_TRACES[stem]:
        assert holds(cmds(s)), (stem, quoted, cmds(s))
    notice = (TRACES / f"{stem}.panel").read_text()
    assert "MIT, Copyright (c) 2026 megadake" in notice and "9190e79" in notice
    if not all(p.is_file() for p in MOVY_SOURCES):
        pytest.skip("Movy is not under reference/movy")
    head = subprocess.run(["git", "-C", str(MOVY), "rev-parse", "HEAD"], capture_output=True, text=True)
    if head.returncode == 0:
        assert head.stdout.startswith("9190e79")
    source = "".join(p.read_text(encoding="utf-8") for p in MOVY_SOURCES)
    for quoted, _ in MOVY_TRACES[stem]:
        assert quoted in source, f"Movy's source no longer says {quoted!r}"


def test_a_nolock_parameter_says_so_on_a_lock_page(tools, tmp_path):
    lines = [l for l in (TRACES / "lock-movy-nolock.panel").read_text().splitlines()
             if l and not l.startswith("#")]
    s = lock_run(tools, tmp_path, lines, seconds=0.5)
    assert s["popup"] == ["Model", "cannot be locked"] and cmds(s) == []
    assert s["seq_view"]["step_page"] == 2 and s["locks"]["lock_pages"] == 4   # Macro's 4 pages


def test_the_knob_and_the_base_agree_to_the_bit_after_a_stop(tools, tmp_path):
    """docs/15 S8's knob sync: after a turn of a laned parameter with no step
    held (the 7-bit grid, the base following at once) and after the stop's
    D6 revert, what the engine last heard through the lock path is the
    knob's value, bit for bit (%.9g text, which round-trips a float)."""
    s = run(tools["sim"], ["--engine", "macro", "--cmd", str(TRACES / "steps.verbs"),
                           "--panel", str(TRACES / "lock-knob-sync.panel")])
    assert cmds(s) == ["alabel 0 0 synth:Timbre", "abase 0 0 64", "aset 0 0 4 84 1", "play",
                       "abaseq 0 0 61", "stop"]
    lk = s["locks"]
    assert lk["bases"][0] == 61 and lk["shown_mask"] & (1 << 2)
    assert lk["shown"][2] == lk["value"][2] == "0.48031497"      # float(61 / 127), as lock_value
    assert s["seq_locks_to_engine"] >= 4, "the base at play, the lock, its revert"


def test_eight_lanes_and_a_ninth(tools, tmp_path):
    lines = [l for l in (TRACES / "lock-eight-lanes.panel").read_text().splitlines()
             if l and not l.startswith("#")]
    s = lock_run(tools, tmp_path, lines, seconds=0.6)
    assert s["popup"] == ["8 lanes used"]
    assert s["locks"]["lanes"] == ["synth:Harmonics", "synth:Timbre", "synth:Morph", "synth:Decay",
                                   "synth:Colour", "synth:Volume", "synth:Env_Pitch",
                                   "synth:Env_Timbre"]
    assert s["locks"]["assigned"] == 0xFF and s["hold_locks"] == [65, 65, 65, 63, 63, 88, 69, 59]
    assert sum(c.startswith("alabel") for c in cmds(s)) == 8


def test_a_lock_goes_to_the_sound_its_track_plays(tools, tmp_path):
    """Multi-sound (docs/15 §3.16): track 1 routed to Sound 2 (Shapes) while
    Sound 1 (Macro) is current. The lock pages are Shapes' (Color, which
    Macro has not), the lane resolves on Shapes, the knob that snaps is
    Shapes', and fm1-render replays it byte for byte."""
    script = ("#! rate=44118 block=64 tracks=8 end=88236\n"
              "@0 bpm 24000;tog 0 0 48 110;tog 0 4 55 90;route 0 1 1\n")
    panel = tmp_path / "other.panel"
    panel.write_text("--button 0.05:SEQ\n--key 0.10:7:100:0.4\n--turn 0.20:SELECT:1\n"
                     "--turn 0.25:SELECT:1\n--turn 0.30:KNOB3:6\n--button 0.60:PLAY/STOP\n")
    cmd = tmp_path / "other.verbs"
    cmd.write_text(script)
    s, r, log, a, b = two_step(tools, tmp_path, "other", panel, cmd, "--engine", "macro",
                               "--sound", "1:shapes")
    assert cmds(s) == ["alabel 0 0 synth:Color", "abase 0 0 64", "aset 0 0 4 70 1", "play"]
    assert s["current"] == 0 and s["values0"] == run(tools["sim"], ["--engine", "macro",
                                                                    "--seconds", "0.01"])["values0"]
    assert s["values3"][2] == pytest.approx(64 / 127, abs=1e-6), "Sound 2's Color on the grid"
    assert s["replayable"] == 1 and a == b and s["seq_locks_to_engine"] == r["seq_locks_to_engine"] > 0


def test_a_laned_knob_turns_on_the_7_bit_grid_and_every_base_follows(tools, tmp_path):
    """No step held: Timbre has a lane on tracks 1 and 2
    (both on Sound 1) and on track 3 (on Sound 2). KNOB3 in HOME moves one
    7-bit step a detent, and the two lanes on Sound 1 take the value as
    their base; track 3's does not move. A knob with no lane keeps its
    1/100 detent."""
    script = ("#! rate=44118 block=64 tracks=8 end=22059\n"
              "@0 route 1 1 0;route 2 1 1;alabel 0 0 synth:Timbre;abaseq 0 0 64;"
              "alabel 1 3 synth:Timbre;abaseq 1 3 10;alabel 2 0 synth:Timbre;abaseq 2 0 20\n")
    s = lock_run(tools, tmp_path, ["--turn 0.10:KNOB3:2", "--turn 0.15:KNOB2:1"], "--sound",
                 "1:macro", script=script, seconds=0.3)
    assert cmds(s) == ["abaseq 0 0 66", "abaseq 1 3 66"]
    assert s["values0"][2] == pytest.approx(66 / 127, abs=1e-6)
    assert s["values0"][1] == pytest.approx(0.51, abs=1e-6), "Harmonics has no lane"


def test_algorithm_on_a_laned_list_moves_its_base(tools, tmp_path):
    """ALGORITHM turns the model and never makes a lock (docs/15 §3.8), but
    a lane on it (Six-Op's Patch, LATCH) takes the new patch as its base:
    the lowest 7-bit value of its bin."""
    script = "#! rate=44118 block=64 tracks=8 end=22059\n@0 alabel 0 0 synth:Patch;abaseq 0 0 43\n"
    s = lock_run(tools, tmp_path, ["--turn 0.10:ALGORITHM:3"], script=script, seconds=0.3,
                 engine="sixop")
    assert s["values0"][0] == 35 and cmds(s) == ["abaseq 0 0 47"]      # ceil(35 * 128 / 96) = 47


def test_a_live_take_starts_again_from_the_knob_after_a_pause(tools, tmp_path):
    """A live take's detents add up (Movy's accumulator) until 600 ms pass
    without one, Movy's knob release; the next turn starts from the knob's
    value again. The knob itself never moves: the take is the lane's."""
    lines = ["--button 0.05:PLAY/STOP", "--button 0.10:REC", "--turn 0.20:KNOB3:3",
             "--turn 0.30:KNOB3:3", "--turn 1.00:KNOB3:1"]
    s = lock_run(tools, tmp_path, lines, seconds=1.2)
    takes = [c for c in cmds(s) if c.startswith("aset")]
    assert [int(c.split()[-1]) for c in takes] == [67, 70, 65]
    assert all(len(c.split()) == 5 for c in takes), "heard: no quiet flag"
    assert s["values0"][2] == pytest.approx(64 / 127, abs=1e-6), "snapped once, at the lane's birth"


def test_clear_and_a_knob_clear_the_lane_however_many_steps_are_held(tools, tmp_path):
    """CLEAR + a knob is CLEAR's gesture whatever is held (Movy's router: only
    its step page owns the knobs before Clear does). With two steps held on a
    lock page a knob edits the sound, but with CLEAR held too it clears the
    parameter's lane (`aclr`) and leaves the knob where it was."""
    lines = [l for l in (TRACES / "lock-several-clear.panel").read_text().splitlines()
             if l and not l.startswith("#") and "PLAY/STOP" not in l]
    s = lock_run(tools, tmp_path, lines, seconds=0.8)
    assert cmds(s) == ["alabel 0 0 synth:Timbre", "abase 0 0 64", "aset 0 0 4 66 1",
                       "abaseq 0 0 65", "aclr 0 0"]
    assert s["popup"] == ["Timbre", "lane cleared"] and s["locks"]["assigned"] == 0
    assert s["values0"][2] == pytest.approx(65 / 127, abs=1e-6), "CLEAR's detent turned nothing"
    assert s["seq_view"]["held"] == 2 and s["seq_view"]["step_page"] == 2


def test_the_clear_key_lights_with_a_lane_and_a_tap_does_nothing_yet(tools, tmp_path):
    clear = 1 << BLACK.index(10)
    none = lock_run(tools, tmp_path, ["--button 0.05:SEQ", "--key 0.10:10:100:0.05"], seconds=0.3)
    assert not none["seq_view"]["role_leds"] & clear and cmds(none) == []
    script = ("#! rate=44118 block=64 tracks=8 end=22059\n"
              "@0 tog 0 0 60 100;alabel 0 0 synth:Timbre;aset 0 0 0 30 1\n")
    lit = lock_run(tools, tmp_path, ["--button 0.05:SEQ", "--key 0.10:10:100:0.3",
                                     "--key 0.20:0:100:0.05"], script=script, seconds=0.5)
    assert lit["seq_view"]["role_leds"] & clear
    assert cmds(lit) == [] and lit["seq_view"]["held"] == 0, "CLEAR + a step waits for S9"


def test_the_ui_state_holds_its_s8_fields_in_its_bound(tools):
    z = json.loads(subprocess.run([str(tools["sim"]), "--sizes"], check=True, capture_output=True,
                                  text=True).stdout)
    assert z["seq_ui_size"] <= 1024
