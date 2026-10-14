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
                   "User": "1001:1001", "Env": ["LUNAR_SOURCE_COMMIT=" + "a" * 40] + PINNED_IMAGE_ENV,
                   "Entrypoint": None, "WorkingDir": "", "Tty": False,
                   "OpenStdin": False, "StdinOnce": False, "AttachStdout": True, "AttachStderr": True,
                   "Labels": {"lan.project": "lunar-modulator", "lan.session": "continuous-tuple-capture"}},
        "HostConfig": {"NetworkMode": "none", "CgroupParent": "docker-batch.slice",
                       "ReadonlyRootfs": True, "CpuQuota": 400000, "CpuPeriod": 100000,
                       "NanoCpus": 0, "Memory": 8589934592, "MemorySwap": 8589934592, "PidsLimit": 512,
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


@pytest.mark.parametrize("mutation", ["image", "command", "network", "resource", "mount", "privileged", "device", "cap_add", "pid_mode", "ipc_mode", "runtime", "entrypoint", "extra_env"])
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


def _run_inputs(tmp_path):
    import os, subprocess
    root=tmp_path/"source"; root.mkdir()
    subprocess.run(["git","init","-q",str(root)],check=True)
    (root/"tracked.txt").write_text("source\\n")
    worker=root/WORKER_REL
    worker.parent.mkdir(parents=True)
    worker.write_text("# worker fixture\\n")
    wrapper=root/"tools/native/run_trusted_continuous_build.py"
    wrapper.write_text("# wrapper fixture\\n")
    subprocess.run(["git","-C",str(root),"add","tracked.txt",WORKER_REL,
                    "tools/native/run_trusted_continuous_build.py"],check=True)
    subprocess.run(["git","-C",str(root),"-c","user.name=Test","-c","user.email=test@example.invalid","commit","-qm","fixture"],check=True)
    request=tmp_path/"request.json"; request.write_text("{}")
    toolchain=tmp_path/"toolchain"; toolchain.mkdir(); (toolchain/"clang").write_bytes(b"compiler")
    catalogue=tmp_path/"catalogue"; (catalogue/"shard").mkdir(parents=True)
    (catalogue/"shard/a.o").write_bytes(b"linked"); (catalogue/"unused.bin").write_bytes(b"retained")
    parent=tmp_path/"private"; parent.mkdir(mode=0o700); os.chmod(parent,0o700)
    return root,request,toolchain,catalogue,parent/"build-output"


def test_run_build_refuses_source_snapshot_mismatch_before_docker_create(tmp_path,monkeypatch):
    import json, shutil, run_trusted_continuous_build as wrapper
    root,request,toolchain,catalogue,output=_run_inputs(tmp_path)
    calls=[]; real_copytree=shutil.copytree
    def corrupt_copy(*args,**kwargs):
        result=real_copytree(*args,**kwargs)
        destination=Path(args[1])
        if (destination/"unused.bin").exists():
            (destination/"unused.bin").write_bytes(b"changed during copy")
        return result
    def fake_run(docker,args,**kwargs):
        calls.append(args)
        if args[0:2]==["image","inspect"] and "{{.Id}}" in args: return wrapper.PINNED_IMAGE_ID.encode()
        if args[0:2]==["image","inspect"]: return json.dumps(wrapper.PINNED_IMAGE_ENV).encode("ascii")
        raise AssertionError("Docker create/start must not occur")
    monkeypatch.setattr(wrapper,"_run",fake_run)
    monkeypatch.setattr(shutil,"copytree",corrupt_copy)
    with pytest.raises(ValueError,match="snapshot differs from its source tree"):
        wrapper.run_build(request_path=request,toolchain_path=toolchain,catalogue_path=catalogue,output_path=output,source_root=root)
    assert not any(args and args[0]=="create" for args in calls)


def test_run_build_refuses_snapshot_mutated_during_container_before_capture(tmp_path,monkeypatch):
    import json, subprocess, run_trusted_continuous_build as wrapper
    root,request,toolchain,catalogue,output=_run_inputs(tmp_path)
    calls=[]; inspect_count=0; real_subprocess_run=subprocess.run
    def fake_run(docker,args,**kwargs):
        calls.append(args)
        if args[0:2]==["image","inspect"] and "{{.Id}}" in args: return wrapper.PINNED_IMAGE_ID.encode()
        if args[0:2]==["image","inspect"]: return json.dumps(wrapper.PINNED_IMAGE_ENV).encode("ascii")
        if args[0]=="create":
            snapshot=next(output.parent.glob(".build-output-catalogue-*"))
            (snapshot/"unused.bin").write_bytes(b"changed while build ran")
            return b"b"*64
        if args[0]=="start": return b""
        raise AssertionError("unexpected Docker operation")
    def fake_inspect(docker,container_id): return {"fake":True}
    def fake_contract(_inspect,_mounts,_commit,_name,_container):
        nonlocal inspect_count
        inspect_count+=1
        return {"state":{"status":"created" if inspect_count==1 else "exited","running":False,"exit_code":0}}
    def subprocess_run(args,**kwargs):
        if args and args[0]=="docker": return subprocess.CompletedProcess(args,0,b"",b"")
        return real_subprocess_run(args,**kwargs)
    monkeypatch.setattr(wrapper,"_run",fake_run)
    monkeypatch.setattr(wrapper,"_inspect",fake_inspect)
    monkeypatch.setattr(wrapper,"inspected_contract",fake_contract)
    monkeypatch.setattr(subprocess,"run",subprocess_run)
    with pytest.raises(ValueError,match="snapshot changed while the container was running"):
        wrapper.run_build(request_path=request,toolchain_path=toolchain,catalogue_path=catalogue,output_path=output,source_root=root)
    assert any(args and args[0]=="create" for args in calls)
    assert not (output/"build_tuple.json").exists()


def test_snapshot_invocation_binds_paths_digests_and_all_catalogue_rows(tmp_path):
    import shutil
    from capture_trusted_build_tuple import _toolchain_manifest, sha
    source = tmp_path / "source-catalogue"
    (source / "shard").mkdir(parents=True)
    (source / "linked.o").write_bytes(b"linked")
    (source / "unused.o").write_bytes(b"still included")
    snapshot = tmp_path / "private-snapshot"
    shutil.copytree(source, snapshot)
    source_manifest = _toolchain_manifest(source)
    snapshot_manifest = _toolchain_manifest(snapshot)
    fields = _catalogue_snapshot_fields(source, snapshot, source_manifest, snapshot_manifest)
    assert fields["catalogue_source_root"] == str(source.resolve())
    assert fields["catalogue_snapshot_root"] == str(snapshot.resolve())
    assert fields["catalogue_source_tree_sha256"] == sha(source_manifest)
    assert fields["catalogue_snapshot_tree_sha256"] == sha(snapshot_manifest)
    inventory = __import__("json").loads(snapshot_manifest)["objects"]
    assert {row["path"] for row in inventory} == {".", "shard", "linked.o", "unused.o"}
    with pytest.raises(ValueError, match="snapshot differs from its source tree"):
        _catalogue_snapshot_fields(source, snapshot, source_manifest, b"{}")
