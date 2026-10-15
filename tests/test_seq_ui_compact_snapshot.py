"""Differentially exercise compact sync snapshot against the full-copy oracle."""
import subprocess

import pytest

from tests.engine_helpers import ROOT
from tests.test_sim_web import GPL_MODS, SIM, ENGINES, tools, run  # noqa: F401


@pytest.fixture(scope="module")
def full_snapshot_sim(tmp_path_factory):
    if not shutil_which("make"):
        pytest.skip("no make")
    build = tmp_path_factory.mktemp("seq-ui-full-snapshot")
    target = build / "build" / "fm1-sim-render"
    subprocess.run(
        ["make", "-C", str(ENGINES), "-f", "Makefile", "-f", str(SIM / "mk" / "sim.mk"),
         f"SIM={SIM}", f"BUILD={build / 'build'}", f"FM1_GPL_MODS={int(GPL_MODS)}",
         "OPT=-O2", "EXTRA=-DFM1_SEQ_UI_SYNC_FULL_SNAPSHOT_ORACLE", "-j4", str(target)],
        check=True, stdout=subprocess.DEVNULL,
    )
    return target


def shutil_which(name):
    from shutil import which
    return which(name)


@pytest.mark.parametrize("stem", [
    "track-focus", "step-hold", "play-stop-from-seq", "capture-playing",
    "capture-stopped-fitted", "session-launch", "session-copy-clear", "song-build",
    "song-edit-playing",
])
def test_compact_sync_matches_full_snapshot_oracle(tools, full_snapshot_sim, tmp_path, stem):
    panel = ROOT / "tests" / "fixtures" / "seq-ui" / f"{stem}.panel"
    verbs = panel.with_suffix(".verbs")
    inputs = (ROOT / "tests" / "fixtures" / "seq-ui" /
              ("song.verbs" if stem.startswith(("session-", "song-")) else
               "rec.verbs" if stem.startswith("capture-") else
               "tracks.verbs" if stem == "track-focus" else
               "steps.verbs" if stem == "step-hold" else "input.verbs"))
    args = ["--engine", "test-sine", "--cmd", str(inputs), "--panel", str(panel), "--log-cmds"]
    compact_log, oracle_log = tmp_path / f"{stem}-compact.verbs", tmp_path / f"{stem}-oracle.verbs"
    compact_wav, oracle_wav = tmp_path / f"{stem}-compact.wav", tmp_path / f"{stem}-oracle.wav"
    compact = run(tools["sim"], [*args, str(compact_log), "--out", str(compact_wav)])
    oracle = run(full_snapshot_sim, [*args, str(oracle_log), "--out", str(oracle_wav)])
    assert compact == oracle
    assert compact_log.read_bytes() == oracle_log.read_bytes() == verbs.read_bytes()
    assert compact_wav.read_bytes() == oracle_wav.read_bytes()
