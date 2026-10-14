# SPDX-License-Identifier: MIT
"""Fail-closed checks for the host-owned pinned continuous build wrapper."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/native"))
from run_trusted_continuous_build import (  # noqa: E402
    PINNED_IMAGE_ID,
    WORKER_REL,
    _expected_mounts,
    PINNED_IMAGE_ENV,
    container_command,
    inspected_contract,
    require_successful_exit,
)


def _fixture(tmp_path):
    mounts = [
        f"type=bind,src={tmp_path}/source,dst=/workspace,readonly",
        f"type=bind,src={tmp_path}/request.json,dst=/input/request.json,readonly",
        f"type=bind,src={tmp_path}/toolchain,dst=/opt/pi32v2,readonly",
        f"type=bind,src={tmp_path}/catalogue,dst=/catalogue,readonly",
        f"type=bind,src={tmp_path}/output,dst=/output",
    ]
    expected = _expected_mounts(mounts)
    inspect = {
        "Image": PINNED_IMAGE_ID,
        "Config": {"Image": PINNED_IMAGE_ID,
                   "Cmd": ["python3", "/workspace/" + WORKER_REL],
                   "User": "1001:1001", "Env": PINNED_IMAGE_ENV + ["LUNAR_SOURCE_COMMIT=" + "a" * 40],
                   "Labels": {"lan.project": "lunar-modulator", "lan.session": "continuous-tuple-capture"}},
        "HostConfig": {"NetworkMode": "none", "CgroupParent": "docker-batch.slice",
                       "ReadonlyRootfs": True, "CpuQuota": 400000, "CpuPeriod": 100000,
                       "Memory": 8589934592, "MemorySwap": 8589934592, "PidsLimit": 512,
                       "CapDrop": ["ALL"], "SecurityOpt": ["no-new-privileges"],
                       "Tmpfs": {"/tmp": "rw,nosuid,nodev,exec,size=3221225472"}},
        "State": {"Status": "exited", "Running": False, "ExitCode": 0},
        "Mounts": [{"Source": row["source"], "Destination": row["destination"],
                    "RW": not row["read_only"]} for row in expected],
    }
    return inspect, expected, mounts


def test_inspected_container_matches_fixed_image_mounts_and_limits(tmp_path):
    inspect, expected, _ = _fixture(tmp_path)
    contract = inspected_contract(inspect, expected, "a" * 40)
    require_successful_exit(contract)
    assert contract["image"] == PINNED_IMAGE_ID
    assert contract["environment_keys"] == ["LUNAR_SOURCE_COMMIT", "PATH"]
    assert len(contract["mounts"]) == 5


@pytest.mark.parametrize("mutation", ["image", "command", "network", "resource", "mount"])
def test_inspection_refuses_changed_container_policy(tmp_path, mutation):
    inspect, expected, _ = _fixture(tmp_path)
    if mutation == "image":
        inspect["Image"] = "sha256:" + "0" * 64
    elif mutation == "command":
        inspect["Config"]["Cmd"][-1] = "/tmp/user-command.py"
    elif mutation == "network":
        inspect["HostConfig"]["NetworkMode"] = "bridge"
    elif mutation == "resource":
        inspect["HostConfig"]["MemorySwap"] += 1
    else:
        inspect["Mounts"][0]["RW"] = True
    with pytest.raises(ValueError, match="pinned build policy"):
        inspected_contract(inspect, expected, "a" * 40)


def test_nonzero_or_unfinished_container_exit_is_refused():
    for state in (
        {"status": "exited", "running": False, "exit_code": 1},
        {"status": "running", "running": True, "exit_code": 0},
    ):
        with pytest.raises(ValueError, match="did not exit successfully"):
            require_successful_exit({"state": state})


def test_command_uses_only_operator_owned_worker_and_fixed_image(tmp_path):
    root = tmp_path / "src"
    request = tmp_path / "request.json"
    toolchain = tmp_path / "toolchain"
    catalogue = tmp_path / "catalogue"
    output = tmp_path / "out"
    cmd, _ = container_command("docker", "opaque", root, request, toolchain,
                               catalogue, output, "a" * 40)
    assert cmd[-3:] == [PINNED_IMAGE_ID, "python3", "/workspace/" + WORKER_REL]
    assert "--network=none" in cmd
    assert "--read-only" in cmd
    assert not any("user-command" in token for token in cmd)


def test_invocation_source_snapshot_and_request_are_separate_readonly_mounts(tmp_path):
    cmd, mounts = container_command(
        "docker", "opaque", tmp_path / "snapshot", tmp_path / "request.json",
        tmp_path / "toolchain", tmp_path / "catalogue", tmp_path / "output", "a" * 40)
    expected = _expected_mounts(mounts)
    assert {item["destination"]: item["read_only"] for item in expected} == {
        "/workspace": True,
        "/input/request.json": True,
        "/opt/pi32v2": True,
        "/catalogue": True,
        "/output": False,
    }
    assert (tmp_path / "snapshot").resolve() != (tmp_path / "output").resolve()
    assert (tmp_path / "request.json").resolve().parent != (tmp_path / "output").resolve()
