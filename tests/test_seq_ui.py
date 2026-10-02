"""The sequencer on the virtual FM-1's panel (docs/15 stage S3), behind the
lab switch: golden gesture traces with two-step parity (§6.3), the typed
commands' text round trip, the demo pattern, and the switch itself.

A gesture trace is a .panel file (one --key, --button or --turn per line)
and its golden .verbs, what `fm1-sim-render --lab --log-cmds` writes for it:
the script lines as applied and every command the panel sent, at the block
it led. Two-step parity: fm1-render replaying that file, with the sidecar
of arguments the harness writes next to it (.args), renders the same bytes
as the panel run. Every trace here starts from tests/fixtures/seq-ui/
input.verbs with Test Sine; the parity scenario under sim/web/test/seq/
plays Macro and Plate (tests/test_sim_web.py, and in WebAssembly on the
build host).
"""
import json
import re
import subprocess

import pytest

from tests.engine_helpers import ROOT
from tests.test_sim_web import run, tools  # noqa: F401  (the native build of both tools)

TRACES = ROOT / "tests" / "fixtures" / "seq-ui"
PANELS = sorted(TRACES.glob("*.panel"))


def two_step(tools, tmp_path, name, panel, cmd, *args, lab=True):
    """The panel run and its replay: (panel summary, replay summary, the
    logged script, the panel run's WAV, the replay's WAV)."""
    log, a, b = tmp_path / f"{name}.verbs", tmp_path / f"{name}-panel.wav", tmp_path / f"{name}-replay.wav"
    s = run(tools["sim"], [*(["--lab"] if lab else []), *args, "--cmd", str(cmd), "--panel", str(panel),
                           "--log-cmds", str(log), "--out", str(a)])
    sidecar = (tmp_path / f"{name}.args").read_text().splitlines()
    r = run(tools["render"], ["--cmd", str(log), "--frames", "64", *sidecar, "--out", str(b)])
    return s, r, log.read_text(), a.read_bytes(), b.read_bytes()


def test_there_are_the_s3_traces():
    assert {p.stem for p in PANELS} >= {"seq-enter-exit", "play-stop-from-home", "play-stop-from-fx",
                                        "play-stop-from-seq", "play-twice"}


@pytest.mark.parametrize("panel", PANELS, ids=lambda p: p.stem)
def test_a_trace_logs_its_golden_verbs_and_replays_byte_for_byte(tools, tmp_path, panel):
    s, r, log, a, b = two_step(tools, tmp_path, panel.stem, panel, TRACES / "input.verbs",
                               "--engine", "test-sine")
    assert log == panel.with_suffix(".verbs").read_text(), "not the golden trace"
    assert s["replayable"] == 1
    assert a == b, "two-step parity: the replay differs"
    assert s["seq_dropped"] == r["seq_dropped"] == 0
    assert s["seq_notes_to_engine"] == r["seq_notes_to_engine"]
    played = [t for _, t in s["seq_ui_cmds"]]
    if panel.stem != "seq-enter-exit":
        assert played[0] == "play" and s["peak"] > 0.01


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
    names = ["OCT-", "OCT+", "FX", "SEL", "ENV", "LFO", "EDIT", "GLO", "HOME", "SAVE", "ARP", "SEQ",
             "PLAY/STOP", "REC"]
    lit = {n for n, c in zip(names, s["leds"][27:]) if c == "1"}
    assert (s["mode"], lit) == (mode, leds)
    assert s["popup"] == []


def test_the_parity_scenarios_panel_replays_byte_for_byte(tools, tmp_path):
    """The WebAssembly parity scenario's own trace, natively: Macro and
    Plate, knob turns on two sound pages replayed as --param-at."""
    scen = json.loads((ROOT / "sim/web/test/scenarios.json").read_text())["scenarios"]
    for sc in (x for x in scen if "panel" in x):
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
        if sc["name"] != "seq-panel-play-stop":
            continue                    # modulation's (tests/test_sim_mod.py)
        sidecar = (tmp_path / f"{sc['name']}.args").read_text()
        assert sidecar.count("--param-at") == 2, "the two knob turns"
        assert [t for _, t in s["seq_ui_cmds"]] == ["play", "stop", "play"]


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
