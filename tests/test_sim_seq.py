"""The Movy oracle scripts played through the virtual FM-1's app layer
(docs/15 §6.2): every one of the 34 (tests/fixtures/movy and its random/) in
the default mode with Test Sine, and six with Macro from the 29 at
44,118 Hz, through fm1-sim-render and through fm1-render at 64-frame blocks.
The event logs and WAVs are byte-identical and nothing is dropped.

Movy-exact checking stays where it is (fm1-seq and fm1-render in compat
mode against the oracle: test_seq_oracle, test_movy_oracle_fixtures); the
app runs the FM-1's default mode only, and is checked against fm1-render.
18-undo needs no xfail here: both hosts run the same core.
"""
import json
import re
import subprocess

import pytest

from tests.test_sim_web import tools  # noqa: F401  (the native build of both tools)

from tests.engine_helpers import ROOT

FIX = ROOT / "tests" / "fixtures" / "movy"
ORACLE = sorted(FIX.glob("*.verbs")) + sorted((FIX / "random").glob("*.verbs"))
# Six with Macro, from the scripts at 44,118 Hz (the Plaits-based engines
# refuse 48 kHz): notes and gates, lock latches, swing, a session, an
# overdub and a random one.
MACRO = ["03-notes-gates", "04-locks-latch", "08-quantise-swing", "12-launch-session",
         "15-record-overdub", "rand-601-00377"]


def rate_of(script):
    return int(re.search(r"\brate=(\d+)", script.read_text().splitlines()[0]).group(1))


def play(tools, tmp_path, script, engine):
    state = script.with_name(script.stem + ".in.movy1")
    extra = ["--seq", str(state)] if state.exists() else []
    out = {}
    for tool, more in (("render", ["--frames", "64"]), ("sim", [])):
        wav, log = tmp_path / f"{tool}.wav", tmp_path / f"{tool}.jsonl"
        res = subprocess.run([str(tools[tool]), "--cmd", str(script), *extra, "--engine", engine,
                              "--out", str(wav), "--log-events", str(log), *more],
                             check=True, capture_output=True, text=True)
        out[tool] = (json.loads(res.stdout.strip().splitlines()[-1]), wav.read_bytes(),
                     log.read_bytes())
    return out["render"], out["sim"]


def check(ref, app):
    (r, rwav, rlog), (s, swav, slog) = ref, app
    assert slog == rlog, "event logs differ"
    assert swav == rwav, "audio differs"
    assert r["seq_dropped"] == s["seq_dropped"] == 0
    assert s["seq_lines_left"] == s["seq_held"] == 0
    for k in ("frames", "seq_events", "seq_notes_to_engine", "seq_locks_to_engine",
              "seq_refused", "seq_max_block_events", "seq_splits", "seq_bytes"):
        assert s[k] == r[k], k


@pytest.mark.parametrize("script", ORACLE, ids=lambda p: p.stem)
def test_an_oracle_script_plays_through_the_app_as_through_fm1_render(tools, tmp_path, script):
    check(*play(tools, tmp_path, script, "test-sine"))


def test_six_macro_scripts_are_at_the_fm1_rate():
    names = {p.stem: p for p in ORACLE}
    assert all(rate_of(names[n]) == 44118 for n in MACRO)


@pytest.mark.parametrize("name", MACRO)
def test_an_oracle_script_plays_macro_through_the_app(tools, tmp_path, name):
    script = next(p for p in ORACLE if p.stem == name)
    ref, app = play(tools, tmp_path, script, "macro")
    check(ref, app)
    assert app[0]["seq_notes_to_engine"] > 0, "the script sounds"
