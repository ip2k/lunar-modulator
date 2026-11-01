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
    PINNED_IMAGE_LABELS,
    container_command,
    inspected_contract,
    require_successful_exit,
    _catalogue_snapshot_fields,
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
        "Name": "/lunar-continuous-" + "a" * 24,
        "Id": "b" * 64,
        "Config": {"Image": PINNED_IMAGE_ID,
                   "Cmd": ["python3", "/workspace/" + WORKER_REL],
                   "User": "1003:1003", "Env": ["LUNAR_SOURCE_COMMIT=" + "a" * 40] + PINNED_IMAGE_ENV,
                   "Entrypoint": None, "WorkingDir": "", "Tty": False,
                   "OpenStdin": False, "StdinOnce": False, "AttachStdout": True, "AttachStderr": True,
                   "Labels": {**PINNED_IMAGE_LABELS, "lan.project": "lunar-modulator", "lan.session": "continuous-tuple-capture", "lan.owner": "lunar-continuous-" + "a" * 24}},
        "HostConfig": {"NetworkMode": "none", "CgroupParent": "docker-batch.slice",
                       "ReadonlyRootfs": True, "CpuQuota": 400000, "CpuPeriod": 100000,
                       "NanoCpus": 0, "CpusetCpus": "4-7",
                       "LogConfig": {"Type": "json-file", "Config": {"max-size": "1m", "max-file": "1"}}, "Memory": 6442450944, "MemorySwap": 6442450944, "PidsLimit": 512,
                       "Privileged": False, "Devices": [], "DeviceRequests": None, "CapAdd": None,
                       "PidMode": "", "IpcMode": "private", "UTSMode": "", "UsernsMode": "",
                       "Runtime": "runc", "Binds": None, "AutoRemove": False, "Init": None,
                       "CapDrop": ["ALL"], "SecurityOpt": ["no-new-privileges"],
                       "Tmpfs": {"/tmp": "rw,nosuid,nodev,exec,size=3221225472"}},
        "State": {"Status": "exited", "Running": False, "ExitCode": 0},
        "Mounts": [{"Source": row["source"], "Destination": row["destination"],
                    "RW": not row["read_only"]} for row in expected],
    }
    return inspect, expected, mounts


def test_inspected_container_matches_fixed_image_mounts_and_limits(tmp_path):
    inspect, expected, _ = _fixture(tmp_path)
    contract = inspected_contract(inspect, expected, "a" * 40, "lunar-continuous-" + "a" * 24, "b" * 64)
    require_successful_exit(contract)
    assert contract["image"] == PINNED_IMAGE_ID
    assert contract["environment_keys"] == ["LUNAR_SOURCE_COMMIT", "PATH"]
    assert len(contract["mounts"]) == 5


def test_producer_and_capture_pin_same_aeon_image():
    from capture_trusted_build_tuple import PINNED_TOOLCHAIN_IMAGE
    assert PINNED_IMAGE_ID == "sha256:" + PINNED_TOOLCHAIN_IMAGE


@pytest.mark.parametrize("mutation", ["image", "command", "network", "resource", "mount", "privileged", "device", "cap_add", "pid_mode", "ipc_mode", "runtime", "entrypoint", "extra_env", "missing_base_label", "changed_base_label", "extra_label", "wrong_user", "cpuset", "logging"])
def test_inspection_refuses_changed_container_policy(tmp_path, mutation):
    inspect, expected, _ = _fixture(tmp_path)
    if mutation == "logging":
        inspect["HostConfig"]["LogConfig"]["Config"]["max-size"] = "20m"
    elif mutation == "cpuset":
        inspect["HostConfig"]["CpusetCpus"] = "0-3"
    elif mutation == "wrong_user":
        inspect["Config"]["User"] = "1001:1001"
    elif mutation == "image":
        inspect["Image"] = "sha256:" + "0" * 64
    elif mutation == "command":
        inspect["Config"]["Cmd"][-1] = "/tmp/user-command.py"
    elif mutation == "network":
        inspect["HostConfig"]["NetworkMode"] = "bridge"
    elif mutation == "resource":
        inspect["HostConfig"]["MemorySwap"] += 1
    elif mutation == "privileged":
        inspect["HostConfig"]["Privileged"] = True
    elif mutation == "device":
        inspect["HostConfig"]["Devices"] = [{"PathOnHost": "/dev/null"}]
    elif mutation == "cap_add":
        inspect["HostConfig"]["CapAdd"] = ["SYS_ADMIN"]
    elif mutation == "pid_mode":
        inspect["HostConfig"]["PidMode"] = "host"
    elif mutation == "ipc_mode":
        inspect["HostConfig"]["IpcMode"] = "host"
    elif mutation == "runtime":
        inspect["HostConfig"]["Runtime"] = "other"
    elif mutation == "entrypoint":
        inspect["Config"]["Entrypoint"] = ["/bin/sh"]
    elif mutation == "extra_env":
        inspect["Config"]["Env"].append("EXTRA=1")
    elif mutation == "missing_base_label":
        del inspect["Config"]["Labels"]["project"]
    elif mutation == "changed_base_label":
        inspect["Config"]["Labels"]["session"] = "other"
    elif mutation == "extra_label":
        inspect["Config"]["Labels"]["unexpected"] = "1"
    else:
        inspect["Mounts"][0]["RW"] = True
    with pytest.raises(ValueError, match="pinned build policy"):
        inspected_contract(inspect, expected, "a" * 40, "lunar-continuous-" + "a" * 24, "b" * 64)


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
    assert "--log-driver=json-file" in cmd
    assert "--log-opt=max-size=1m" in cmd and "--log-opt=max-file=1" in cmd
    assert "--network=none" in cmd
    assert "--cpuset-cpus=4-7" in cmd
    assert "--memory=6g" in cmd and "--memory-swap=6g" in cmd
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



def test_capture_and_producer_resource_attestation_policies_agree():
    import ast
    import capture_trusted_build_tuple as capture
    from run_trusted_continuous_build import DOCKER_POLICY
    tree = ast.parse(Path(capture.__file__).read_text())
    policies = [ast.literal_eval(node.value) for node in ast.walk(tree)
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict)
                and any(isinstance(target, ast.Name) and target.id == "expected_resources"
                        for target in node.targets)]
    assert policies == [DOCKER_POLICY]
    assert DOCKER_POLICY["memory"] == DOCKER_POLICY["memory_swap"] == 6 * 1024**3
    assert DOCKER_POLICY["cpus"] == 4 and DOCKER_POLICY["cpuset_cpus"] == "4-7"


def test_native_failure_logs_use_byte_bounded_capture_from_first_byte(tmp_path, monkeypatch):
    import run_trusted_continuous_build as wrapper
    from tools.installer_service.process_capture import Capture
    calls = []
    def capture(command, **limits):
        calls.append(command)
        assert limits == {"cwd": tmp_path, "timeout_seconds": 10,
                          "max_stream_bytes": wrapper.MAX_FAILURE_LOG}
        return Capture(0, {"stdout": b"x" * wrapper.MAX_FAILURE_LOG, "stderr": b""},
                       {"stdout": 100 * wrapper.MAX_FAILURE_LOG, "stderr": 0}, None)
    monkeypatch.setattr(wrapper, "run_bounded", capture)
    wrapper._retain_failure_log("synthetic-docker", "b" * 64, tmp_path)
    assert calls == [["synthetic-docker", "logs", "--tail", "200", "b" * 64]]
    assert (tmp_path / "failed-worker.log").stat().st_size == wrapper.MAX_FAILURE_LOG


def test_native_wrapper_rejects_arbitrary_parent_container_name_before_any_work(tmp_path, monkeypatch):
    import run_trusted_continuous_build as wrapper
    monkeypatch.setattr(wrapper, "_require_runner_identity", lambda: pytest.fail("must refuse before work"))
    with pytest.raises(ValueError, match="parent-owned"):
        wrapper.run_build(request_path=tmp_path, toolchain_path=tmp_path,
                          catalogue_path=tmp_path, output_path=tmp_path,
                          container_name="unrelated-container")
