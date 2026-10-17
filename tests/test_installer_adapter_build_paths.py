# SPDX-License-Identifier: MIT
"""The adapter's canonical mounts share one existing scratch allowance."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.installer_service import docker_adapter as adapter
from tools.installer_service import docker_worker as worker


@pytest.mark.parametrize("budget", [128 * 1024**2, 3 * 1024**3, 4 * 1024**3,
                                    128 * 1024**2 + 4095])
def test_scratch_partition_never_exceeds_configured_total(budget):
    mounts = adapter._scratch_tmpfs(budget, 1003, 1004)
    sizes = {}
    for mount in mounts:
        target, raw_options = mount.split(":", 1)
        options = raw_options.split(",")
        size = int(next(item[5:] for item in options if item.startswith("size=")))
        sizes[target] = size
        assert size > 0 and size % 4096 == 0
        assert {"rw", "nosuid", "nodev", "exec"} <= set(options)
        if target != "/tmp":
            assert {"mode=0700", "uid=1003", "gid=1004"} <= set(options)
    assert set(sizes) == {"/tmp", "/workspace", "/output"}
    assert sum(sizes.values()) <= budget
    assert budget - sum(sizes.values()) < 4096
    if budget == 3 * 1024**3:
        assert sizes == {"/tmp": 1536 * 1024**2, "/workspace": 384 * 1024**2,
                         "/output": 1152 * 1024**2}


def test_actual_adapter_command_canonical_paths_and_private_mount_ownership():
    config = SimpleNamespace(
        docker_binary="docker", worker_uid=1003, worker_gid=1004,
        cpu_limit="4", memory_limit="8g", scratch_bytes=3 * 1024**3,
        toolchain_root=Path("/host/toolchain"), catalogue_root=Path("/host/catalogue"),
        image_reference=adapter._IMAGE_ID)
    command = adapter.DockerJobAdapter(config)._command("a" * 32, Path("/host/runtime"))
    tmpfs = [command[i + 1] for i, item in enumerate(command) if item == "--tmpfs"]
    assert tmpfs == adapter._scratch_tmpfs(config.scratch_bytes, 1003, 1004)
    assert command[command.index("--user") + 1] == "1003:1004"
    mounts = [command[i + 1] for i, item in enumerate(command) if item == "--mount"]
    assert "type=bind,src=/host/catalogue,dst=/catalogue,readonly" in mounts
    assert "type=bind,src=/host/toolchain,dst=/opt/pi32v2,readonly" in mounts
    assert "type=bind,src=/host/runtime/input/source.tar,dst=/input/source.tar,readonly" in mounts
    assert not any("dst=/workspace" in item or "dst=/output" in item for item in mounts)
    for flag in ("--pull=never", "--network=none", "--cgroup-parent=docker-batch.slice",
                 "--cpus=4", "--memory=8g", "--memory-swap=8g", "--pids-limit=512",
                 "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges"):
        assert flag in command
    assert command[-3:] == [adapter._IMAGE_ID, "python3", "/input/docker_worker.py"]
    assert adapter._CATALOGUE_MOUNT == worker.CATALOGUE_MOUNT == "/catalogue/"
    assert adapter._BUILD_LINK_MOUNT == worker.BUILD_LINK_MOUNT == "/output/build/link/"


@pytest.mark.parametrize("legacy", ["/input/catalogue/x.o", "/tmp/lunar-worker/output/build/link/x.o"])
def test_canonical_reader_does_not_reinterpret_legacy_paths(legacy):
    with pytest.raises(ValueError):
        adapter._receipt_key(legacy, adapter._CATALOGUE_MOUNT, "catalogue/")
    with pytest.raises(ValueError):
        adapter._receipt_key(legacy, adapter._BUILD_LINK_MOUNT, "linked/link/")
