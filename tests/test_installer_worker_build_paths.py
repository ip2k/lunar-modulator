# SPDX-License-Identifier: MIT
"""Canonical filesystem inputs, without rewriting any resulting ELF bytes."""
import hashlib
import importlib.util
from pathlib import Path
import stat

import pytest

from tools.installer_service import docker_worker as worker


def _trusted_worker():
    path = Path(__file__).resolve().parents[1] / "tools/native/trusted_continuous_worker.py"
    spec = importlib.util.spec_from_file_location("trusted_path_test_worker", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_service_uses_trusted_canonical_target_paths():
    trusted = _trusted_worker()
    assert worker.SOURCE == trusted.SOURCE == Path("/workspace")
    assert worker.CATALOGUE == trusted.CATALOGUE == Path("/catalogue")
    assert worker.OUTPUT == trusted.OUTPUT == Path("/output")
    assert worker.TOOLCHAIN == trusted.TOOLCHAIN == Path("/opt/pi32v2")
    # The shallow bootstrap derives /input from its deployed __file__.
    assert worker.REQUEST == worker.INPUT / "request.json"
    assert trusted.REQUEST == Path("/input/request.json")
    assert worker.CATALOGUE_MOUNT == str(trusted.CATALOGUE) + "/"
    assert worker.BUILD_LINK_MOUNT == str(trusted.OUTPUT / "build/link") + "/"


def test_actual_trusted_invocation_and_service_recipe_agree(tmp_path, monkeypatch):
    trusted = _trusted_worker()
    for name, path in {"SOURCE": tmp_path / "workspace", "OUTPUT": tmp_path / "output",
                       "CATALOGUE": tmp_path / "catalogue", "TOOLCHAIN": tmp_path / "tc",
                       "REQUEST": tmp_path / "request.json", "SCRATCH": tmp_path / "scratch"}.items():
        monkeypatch.setattr(trusted, name, path)
        monkeypatch.setattr(worker, name, path)
    for directory in (trusted.SOURCE, trusted.OUTPUT, trusted.TOOLCHAIN,
                      trusted.CATALOGUE / "shard-00"):
        directory.mkdir(parents=True)
    (trusted.CATALOGUE / "shard-00/objects.json").write_text("{}")
    trusted.REQUEST.write_bytes(b"{}")
    monkeypatch.setenv("LUNAR_SOURCE_COMMIT", "a" * 40)
    commands = []

    def run(command, **kwargs):
        commands.append((command, kwargs))
        if command[0] == "make":
            state_tool = Path(command[-1])
            state_tool.parent.mkdir()
            state_tool.write_bytes(b"host-codec-fixture")

    monkeypatch.setattr(trusted.subprocess, "run", run)
    assert trusted.main() == 0
    state_command, image_command = worker.build_commands(
        worker.SOURCE, worker.OUTPUT, worker.build_profile_arguments(
            {"runtime_mode": "continuous", "flash_layout": "expanded-d7000"}))
    assert state_command == commands[0][0]
    assert commands[0][1] == {"check": True, "timeout": 180}
    assert image_command[:2] == commands[1][0][:2]

    def options(command):
        assert len(command[2:]) % 2 == 0
        return dict(zip(command[2::2], command[3::2]))

    assert options(image_command) == options(commands[1][0])
    assert commands[1][1] == {"check": True, "timeout": 1200}


@pytest.mark.parametrize("bad_root", ["nonempty", "symlink", "mode", "owner", "group", "alias"])
def test_canonical_build_root_refuses_untrusted_directory(tmp_path, monkeypatch, bad_root):
    root = tmp_path / "root"
    root.mkdir(mode=0o700)
    if bad_root == "nonempty":
        (root / "unexpected").touch()
    elif bad_root == "symlink":
        alias = tmp_path / "alias"
        alias.symlink_to(root, target_is_directory=True)
        root = alias
    elif bad_root == "mode":
        root.chmod(0o755)
    elif bad_root == "owner":
        monkeypatch.setattr(worker.os, "getuid", lambda: root.stat().st_uid + 1)
    elif bad_root == "group":
        monkeypatch.setattr(worker.os, "getgid", lambda: root.stat().st_gid + 1)
    else:
        root = root / ".." / "root"
    with pytest.raises(ValueError, match="canonical build mount"):
        worker.require_private_empty_root(root)


def test_empty_private_root_and_readonly_source_preserve_bytes(tmp_path):
    root = tmp_path / "source"
    root.mkdir(mode=0o700)
    worker.require_private_empty_root(root)
    nested = root / "tools"
    nested.mkdir()
    source = nested / "source.py"
    source.write_bytes(b"print('pinned source')\n")
    source.chmod(0o644)
    executable = nested / "worker.py"
    executable.write_bytes(b"#!/usr/bin/python3\n")
    executable.chmod(0o755)
    expected = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (source, executable)}
    try:
        worker.freeze_source_tree(root)
        assert stat.S_IMODE(root.stat().st_mode) == 0o555
        assert stat.S_IMODE(nested.stat().st_mode) == 0o555
        assert stat.S_IMODE(source.stat().st_mode) == 0o444
        assert stat.S_IMODE(executable.stat().st_mode) == 0o555
        assert {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (source, executable)} == expected
    finally:
        root.chmod(0o700)
        nested.chmod(0o700)


def test_freeze_rejects_source_symlinks(tmp_path):
    (tmp_path / "alias").symlink_to(tmp_path / "missing")
    with pytest.raises(ValueError, match="unsafe entry"):
        worker.freeze_source_tree(tmp_path)
