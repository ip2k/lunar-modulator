# SPDX-License-Identifier: MIT
"""Real harmless Python children establish bounded capture and cleanup behavior."""
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from tools.installer_service.process_capture import run_bounded


def run_script(tmp_path, source, **bounds):
    script = tmp_path / "child.py"
    script.write_text(source)
    return run_bounded([sys.executable, str(script)], cwd=tmp_path,
                       max_stream_bytes=4096, drain_seconds=0.2, **bounds)


def assert_stopped(pid):
    # A reparented zombie has exited; it is waiting for the system reaper.
    state = subprocess.run(["ps", "-p", str(pid), "-o", "stat="],
                           capture_output=True, text=True, timeout=2).stdout.strip()
    assert not state or state.startswith("Z"), state


def test_noisy_dual_stream_has_bounded_retention_and_full_observed_counts(tmp_path):
    result = run_script(tmp_path, "import os\n"
        "for i in range(256):\n os.write(1, b'a' * 65536)\n os.write(2, b'b' * 65536)\n",
        timeout_seconds=5)
    assert result.returncode == 0 and result.failure_reason is None
    assert result.logs == {"stdout": b"a" * 4096, "stderr": b"b" * 4096}
    assert result.observed == {"stdout": 16 * 1024**2, "stderr": 16 * 1024**2}


@pytest.mark.skipif(not hasattr(os, "fork"), reason="POSIX process-group capture")
def test_timeout_kills_parent_and_descendant_and_keeps_prefix(tmp_path):
    start = time.monotonic()
    result = run_script(tmp_path, "import os,time\n"
        "pid = os.fork()\n"
        "if pid == 0:\n time.sleep(30)\nelse:\n"
        " print(pid, flush=True)\n os.write(2, b'private diagnostic')\n time.sleep(30)\n",
        timeout_seconds=0.25)
    assert time.monotonic() - start < 3
    assert result.failure_reason == "timeout" and result.returncode != 0
    assert result.logs["stderr"] == b"private diagnostic"
    assert_stopped(int(result.logs["stdout"]))


@pytest.mark.skipif(not hasattr(os, "fork"), reason="POSIX process-group capture")
def test_exited_parent_cannot_leave_descendant_holding_output_open(tmp_path):
    start = time.monotonic()
    result = run_script(tmp_path, "import os,time\n"
        "pid = os.fork()\n"
        "if pid == 0:\n time.sleep(30)\nelse:\n print(pid, flush=True)\n os._exit(0)\n",
        timeout_seconds=5)
    assert time.monotonic() - start < 3
    assert result.returncode == 0 and result.failure_reason == "output_drain_timeout"
    assert_stopped(int(result.logs["stdout"]))


def test_invalid_bounds_do_not_start_process(tmp_path):
    with pytest.raises(ValueError, match="bounds"):
        run_script(tmp_path, "raise AssertionError('must not launch')", timeout_seconds=0)
    assert not (tmp_path / "unexpected").exists()
