"""Reject unsafe runner inputs before any SSH or output cleanup."""
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("frames", ["block; touch marker", "$(id)", "other", ""])
def test_movy_rejects_invalid_frames_before_ssh(tmp_path, frames):
    check_runner(tmp_path, "tools/movy-oracle/run-on-aeon.sh",
                 {"MOVY_ORACLE_HOST": "unused", "MOVY_ORACLE_REMOTE": "/tmp/lunar/oracle"},
                 ["--frames", frames] if frames else ["--frames"])


@pytest.mark.parametrize("remote", ["/", "/tmp", "/home/user", "/tmp/lunar/../oracle",
                                    "/tmp/lunar/oracle'; touch marker; #"])
@pytest.mark.parametrize("runner", ["movy", "airwindows"])
def test_oracle_rejects_unsafe_remote_path_before_ssh(tmp_path, remote, runner):
    if runner == "movy":
        script = "tools/movy-oracle/run-on-aeon.sh"
        env = {"MOVY_ORACLE_HOST": "unused", "MOVY_ORACLE_REMOTE": remote}
    else:
        script = "engines/third_party/airwindows/oracle/run-on-aeon.sh"
        env = {"FM1_SIM_HOST": "unused", "FM1_REMOTE_DIR": remote}
    check_runner(tmp_path, script, env, ["--clean"] if runner == "movy" else [])


def check_runner(tmp_path, script, values, args):
    marker = tmp_path / "ssh-called"
    fake = tmp_path / "ssh"
    fake.write_text('#!/bin/sh\ntouch "$SSH_MARKER"\nexit 99\n')
    fake.chmod(0o755)
    env = dict(os.environ, **values, SSH_MARKER=str(marker),
               PATH=str(tmp_path) + os.pathsep + os.environ["PATH"])
    result = subprocess.run(["bash", str(ROOT / script), *args], env=env,
                            capture_output=True, text=True)
    assert result.returncode == 2, result.stderr
    assert not marker.exists()
