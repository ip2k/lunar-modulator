"""The actual host/arp path while transport pauses at different tick fractions."""
import subprocess

from tests.seq_helpers import ENGINES, seq_tools  # noqa: F401


def test_live_arp_keeps_tempo_while_pause_preserves_sequencer_phase(seq_tools):
    # seq_tools builds this default target with the CI profile already in use.
    out = subprocess.check_output([str(ENGINES / "build" / "fm1-mfx-pause-test")], text=True)
    assert "24 scenarios passed" in out
