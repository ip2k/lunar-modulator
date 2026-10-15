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
    "capture-stopped-fitted", "session-launch", "session-copy-clear",
    "session-scenes", "session-track-clear", "song-build", "song-edit-playing",
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


def test_session_snapshot_matches_full_oracle_across_count_in_and_recording(
        tools, full_snapshot_sim, tmp_path):
    """The cached grid refreshes on transport transitions and command changes."""
    panel = tmp_path / "session-recording.panel"
    panel.write_text(
        "--button 0.05:SEQ\n"
        "--button 0.10:SEQ\n"
        "--button 0.20:REC\n"          # count-in while Session is visible
        "--key 0.85:0:90:0.05\n"       # recorded note after count-in
        "--button 1.60:REC\n"          # stop recording
        "--button 2.00:PLAY/STOP\n"   # playback while Session is visible
        "--button 2.50:PLAY/STOP\n"   # transition back to stopped
    )
    command = ROOT / "tests" / "fixtures" / "seq-ui" / "song.verbs"
    args = ["--engine", "test-sine", "--cmd", str(command), "--panel", str(panel), "--log-cmds"]
    outputs = []
    for name, binary in (("compact", tools["sim"]), ("oracle", full_snapshot_sim)):
        log = tmp_path / f"session-recording-{name}.verbs"
        wav = tmp_path / f"session-recording-{name}.wav"
        result = run(binary, [*args, str(log), "--out", str(wav)])
        outputs.append((result, log.read_bytes(), wav.read_bytes()))
    assert outputs[0] == outputs[1]
    assert outputs[0][0]["seq_view"]["view"] == 5  # Session remains visible
    assert outputs[0][0]["rec"]["recording"] == 0
    assert outputs[0][0]["rec"]["counting_in"] == 0
    assert b" rec " in outputs[0][1]  # the Session REC action reached the sequencer


def test_capture_pending_256_preserves_sync_change_flag(tmp_path):
    """The 16-bit capture count must participate in the sync diff without truncation."""
    harness = tmp_path / "capture_pending_sync.c"
    harness.write_text(r'''#include "fm1_seq.h"
#include "fm1_seq_ui.h"
#include <stdio.h>
#include <stdlib.h>

int main(void) {
    fm1_seq_limits_t limits;
    fm1_seq_ui_t ui;
    fm1_seq_info_t info;
    fm1_seq_t *seq;
    void *memory;
    size_t bytes;
    int changed, unchanged;

    fm1_seq_limits_default(&limits, 8);
    bytes = fm1_seq_size(&limits);
    memory = calloc(1, bytes);
    if (!memory) return 2;
    seq = fm1_seq_create(memory, &limits, 44118);
    if (!seq) return 3;
    fm1_seq_ui_init(&ui, 44118);
    fm1_seq_ui_enter(&ui);
    (void)fm1_seq_ui_sync(&ui, seq, 0, 0);

    for (unsigned i = 0; i < 256; ++i)
        fm1_seq_note_in(seq, 0, 0, (uint8_t)(36 + i % 60), 100);
    fm1_seq_get_info(seq, &info);
    changed = fm1_seq_ui_sync(&ui, seq, 0, 64);
    unchanged = fm1_seq_ui_sync(&ui, seq, 0, 128);
    if (info.capture_pending != 256 || ui.capture_pending != 256 ||
        !(changed & FM1_SEQ_UI_SYNC_SEQ) || (unchanged & FM1_SEQ_UI_SYNC_SEQ)) {
        fprintf(stderr, "pending=%u ui=%u changed=0x%x unchanged=0x%x\n",
                info.capture_pending, ui.capture_pending, changed, unchanged);
        return 4;
    }
    free(memory);
    return 0;
}
''')
    seq_sources = sorted((ROOT / "engines" / "seq").glob("*.c"))
    common = [
        "cc", "-std=c99", "-O2", "-Wall", "-Wextra",
        f"-I{ROOT / 'engines' / 'include'}",
        f"-I{ROOT / 'engines' / 'seq'}",
        f"-I{ROOT / 'engines' / 'host'}",
        f"-I{ROOT / 'sim' / 'web' / 'src'}",
        str(ROOT / "sim" / "web" / "src" / "fm1_seq_ui.c"),
        *(str(path) for path in seq_sources), str(harness), "-lm",
    ]
    for oracle in (False, True):
        exe = tmp_path / ("capture-pending-oracle" if oracle else "capture-pending-compact")
        command = common.copy()
        if oracle:
            command.insert(1, "-DFM1_SEQ_UI_SYNC_FULL_SNAPSHOT_ORACLE")
        command += ["-o", str(exe)]
        subprocess.run(command, check=True, capture_output=True, text=True)
        subprocess.run([str(exe)], check=True, capture_output=True, text=True)
