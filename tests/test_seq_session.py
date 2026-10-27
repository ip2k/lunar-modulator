"""Session snapshots preserve the full getters' state without mutating it."""
import subprocess

from tests.seq_helpers import ENGINES, seq_tools  # noqa: F401


def test_compact_session_snapshot_matches_full_getters(seq_tools):
    out = subprocess.check_output([str(ENGINES / "build" / "fm1-seq-session-test")], text=True)
    assert "17408 session snapshots passed" in out
