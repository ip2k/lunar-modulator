"""The edit layer (sim/web/src/fm1_edit.h, stage ED1 of
notes/2026-10-06-web-editor.md): records and verbs through the panel's own
calls, the change ring with its sources, telemetry, the view and knob map,
and the parameter text parser.

The native harness checks it (fm1-sim-render --edit-check); test/edit.mjs
plays a script of every verb to the browser's module and to the harness and
compares them, when node is here; build.sh runs the same on aeon with a
30-second edit storm whose measured cost it records in fm1.wasm.json.
"""
import json
import re
import shutil
import subprocess

import pytest

from tests.engine_helpers import GPL_MODS, ROOT
from tests.test_sim_web import tools  # noqa: F401  (the harness fixture)

SIM = ROOT / "sim" / "web"
WWW = SIM / "www"

# Every refusal code an edit can meet with today's modules. The file-level
# ones (NOT_LUNAR, TOO_NEW, TOO_BIG, STOPPED) belong to loads; NO_MOD needs a
# float without MOD, which no module has (the planner's own fuzz reaches it
# with a test engine); ARENA needs an effect or kind larger than its arena,
# which none is, even at 96 kHz; VOICE_ROOM cannot happen with today's kinds
# (notes/2026-10-06-web-editor.md §21).
REACHABLE = {"UNKNOWN", "RATE", "RAM", "NO_ROOM", "BAD", "NO_SOURCE", "NO_DEST", "NOLOCK",
             "ENUM_NO_MOD", "VOICE_TO_MONO", "VOICE_TO_EFFECT", "UNIT_RESERVED", "VOICE_FULL"}


@pytest.fixture(scope="module")
def check(tools):  # noqa: F811
    r = subprocess.run([str(tools["sim"]), "--edit-check"], capture_output=True, text=True, timeout=300)
    out = json.loads(r.stdout)
    assert r.returncode == 0 and out["failed"] == 0, (out["why"], r.stderr[-2000:])
    return out


def test_every_parameter_reads_back_what_the_screen_shows(check):
    # fm1_param_parse(fm1_look_value(v)) for every knob step of every
    # engine, effect, MIDI effect, modulation kind and host parameter.
    # 467 parameters and 34,376 steps with the GPL switch on; the MIT/BSD
    # build has fewer modules (373 parameters).
    assert check["params"] >= (400 if GPL_MODS else 300) and check["steps"] >= (30000 if GPL_MODS else 20000)
    assert check["text_bad"] == 0, check["text_first_bad"]


def test_every_refusal_an_edit_can_meet_comes_from_c(check):
    assert set(check["codes"]) == REACHABLE


def test_the_panel_and_the_editor_make_the_same_changes(check):
    # Seven panel gestures (knobs over two pages, PRESETS, the Mix page,
    # SEL + SELECT, SHIFT + PRESETS, the arpeggiator, the rack), their ring
    # entries replayed as editor ops: the same entries and the same state.
    assert check["hands"] == 7 + 40
    assert check["tele_fills"] in (29, 30, 31)


def test_a_sweep_of_random_gestures_gives_the_same_state_either_way(check):
    # The note's section 17, "parity of hands": forty runs of the families above with
    # random deltas, in random order, each replayed as editor ops (the seed is the run's
    # number).
    assert check["sweeps"] == 40 and check["failed"] == 0


def test_a_lock_playing_moves_no_base(check):
    # Section 7, "heard, not set": the start chain's demo pattern plays for 900 blocks;
    # every parameter of every unit reads what it did, and the ring holds no parameter write.
    assert check["lock_blocks"] == 900 and check["failed"] == 0



def test_the_verbs_script_parses_in_c():
    lines = [l for l in (SIM / "test" / "edit" / "verbs.edit").read_text().splitlines()
             if l.startswith("@") and " edit " in l]
    assert len(lines) >= 30
    kinds = {l.split(" edit ")[1].split()[0] for l in lines}
    assert kinds >= {"param", "unit", "on", "level", "module", "cable", "swap", "move", "current", "view"}


def test_the_module_plays_the_script_as_the_harness_does(tools, tmp_path):  # noqa: F811
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    mod = (WWW / "fm1.wasm").read_bytes()
    if b"fm1w_edit_text" not in mod:
        pytest.skip("www/fm1.wasm predates the edit layer: rebuild it (build-on-aeon.sh)")
    r = subprocess.run([node, str(SIM / "test" / "edit.mjs"), "--wasm", str(WWW / "fm1.wasm"),
                        "--sim", str(tools["sim"]), "--script", str(SIM / "test" / "edit" / "verbs.edit"),
                        "--work", str(tmp_path)], capture_output=True, text=True, timeout=300)
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert r.returncode == 0 and out["parity"] == "ok", out["fails"]


def test_the_storm_was_measured_and_the_audio_thread_kept_up():
    rec = json.loads((WWW / "fm1.wasm.json").read_text())
    edit = rec.get("edit")
    assert edit, "fm1.wasm.json has no edit-layer record: rebuild the module (build-on-aeon.sh)"
    assert edit["parity"] == "ok" and edit["check"]["failed"] == 0
    storm = edit["storm"]
    assert storm["seconds"] == 30 and storm["quanta"] == 10341 and storm["applied"] == 8 * storm["quanta"]
    print(f"storm: {storm['late']} late quanta of {storm['quanta']}, p99 {storm['p99_ms']:.3f} ms, "
          f"max {storm['max_ms']:.3f} ms, edit layer {storm['edit_us_per_quantum']:.1f} us a quantum")
    # §12's target: the layer's own work under 2 % of a quantum (58 us).
    assert storm["edit_us_per_quantum"] < 58
    assert storm["late"] == 0


def test_the_editor_port_and_the_shadow_name_no_module():
    # No engine rule in JavaScript (ED2): the shadow Worker's and the
    # worklet's editor code carry no engine, effect, kind or source id.
    listed = json.loads(subprocess.run([str(ROOT / "engines" / "build" / "fm1-render"), "--list"],
                                       capture_output=True, text=True).stdout or "[]") \
        if (ROOT / "engines" / "build" / "fm1-render").exists() else []
    ids = {e["id"] for e in listed} | {"lfo", "env", "chance", "arp", "macro", "comp", "echo"}
    shadow = (WWW / "shadow.worker.js").read_text()
    worklet = (WWW / "worklet.js").read_text()
    editor_part = worklet[worklet.index("onEditor(m)"):worklet.index("async onMessage(m)")]
    for name, code in (("shadow.worker.js", shadow), ("the worklet's editor code", editor_part)):
        quoted = set(re.findall(r"'([a-z0-9_-]+)'", code)) | set(re.findall(r'"([a-z0-9_-]+)"', code))
        assert not (quoted & ids), (name, quoted & ids)
