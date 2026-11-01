# SPDX-License-Identifier: MIT
"""Causal offline witnesses for owned temporary-data lifetimes."""
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/native"))
import run_trusted_continuous_build as wrapper
from tools.workbench import verify_inventory as inventory


@pytest.fixture
def setup_build(tmp_path, monkeypatch):
    source, toolchain, catalogue = (tmp_path / name for name in ("source", "toolchain", "catalogue"))
    for path in (source, toolchain, catalogue):
        path.mkdir()
    (catalogue / "input").write_bytes(b"catalogue")
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    request = tmp_path / "request.json"
    request.write_text('{}')
    monkeypatch.setattr(wrapper, "_require_runner_identity", lambda: None)
    monkeypatch.setattr(wrapper, "_run", lambda docker, args: (
        wrapper.PINNED_IMAGE_ID.encode() if args[-1] == wrapper.PINNED_IMAGE_ID and args[3] == '{{.Id}}'
        else json.dumps(wrapper.PINNED_IMAGE_ENV).encode()))
    # All cases stop before a container is created. Any cleanup Docker call is a bug.
    monkeypatch.setattr(wrapper, "cancel_owned_container", lambda *a, **k: pytest.fail("no container was created"))
    return source, toolchain, catalogue, private, request


@pytest.mark.parametrize("phase", ["request-fsync", "catalogue-manifest", "catalogue-copy", "clone", "checkout", "toolchain-manifest", "command"])
def test_setup_failure_removes_owned_copies(setup_build, monkeypatch, phase):
    source, toolchain, catalogue, private, request = setup_build
    def fail():
        raise RuntimeError("injected " + phase)
    def manifest(path):
        if (phase == "catalogue-manifest" and path == catalogue or
                phase == "toolchain-manifest" and path == toolchain):
            fail()
        return b'{}'
    monkeypatch.setattr(wrapper, "_toolchain_manifest", manifest)
    copytree = shutil.copytree
    def copy(src, dst, **kw):
        result = copytree(src, dst, **kw)
        if phase == "catalogue-copy":
            fail()
        return result
    monkeypatch.setattr(wrapper.shutil, "copytree", copy)
    def run(command, **kw):
        if command[1] == "clone":
            destination = Path(command[-1])
            destination.mkdir(exist_ok=True)
            (destination / "partial").write_bytes(b"source")
            if phase == "clone":
                fail()
        elif "checkout" in command and phase == "checkout":
            fail()
        return SimpleNamespace(stdout=("a" * 40 if kw.get("text") else b""))
    monkeypatch.setattr(wrapper.subprocess, "run", run)
    monkeypatch.setattr(wrapper, "container_command", lambda *a: fail())
    if phase == "request-fsync":
        monkeypatch.setattr(wrapper.os, "fsync", lambda fd: fail())
    with pytest.raises(RuntimeError, match="injected " + phase):
        wrapper.run_build(request_path=request, toolchain_path=toolchain,
                          catalogue_path=catalogue, output_path=private / "result", source_root=source)
    assert sorted(p.name for p in private.iterdir()) == ["result"]


@pytest.mark.parametrize("collision", ["catalogue", "source", "request"])
def test_snapshot_collision_preserves_foreign_directory(setup_build, monkeypatch, collision):
    source, toolchain, catalogue, private, request = setup_build
    monkeypatch.setattr(wrapper.secrets, "token_hex", lambda n: "a" * (2 * n))
    foreign = private / (".result-" + (collision + "-" if collision != "request" else "") + "a" * 16
                         + (".request.json" if collision == "request" else ""))
    if collision == "request":
        foreign.write_bytes(b"foreign")
    else:
        foreign.mkdir()
        (foreign / "keep").write_bytes(b"foreign")
    monkeypatch.setattr(wrapper, "_toolchain_manifest", lambda p: b'{}')
    monkeypatch.setattr(wrapper.subprocess, "run", lambda cmd, **kw: SimpleNamespace(stdout="a" * 40 if kw.get("text") else b""))
    with pytest.raises(FileExistsError):
        wrapper.run_build(request_path=request, toolchain_path=toolchain,
                          catalogue_path=catalogue, output_path=private / "result", source_root=source)
    assert (foreign if collision == "request" else foreign / "keep").read_bytes() == b"foreign"
    assert sorted(p.name for p in private.iterdir()) == [foreign.name, "result"]


@pytest.mark.parametrize("failure", [False, True])
def test_inventory_uses_project_scratch_and_cleans_on_exit(tmp_path, monkeypatch, failure):
    import zipfile
    kit = tmp_path / "synthetic.zip"
    with zipfile.ZipFile(kit, "w") as archive:
        archive.writestr("input", b"synthetic")
    scratch = tmp_path / "project-scratch"
    monkeypatch.setattr(inventory, "SCRATCH_ROOT", scratch, raising=False)
    monkeypatch.setattr(inventory, "KIT_SHA256", inventory.digest(kit))
    monkeypatch.setattr(inventory, "EXPECTED_FILES", 1)
    monkeypatch.setattr(inventory, "check_manifest", lambda *a: {})
    destinations = []
    def extract(source, destination):
        destinations.append(destination)
        assert destination.is_relative_to(scratch)
        destination.mkdir()
        (destination / "owned").write_bytes(b"input")
        if failure:
            raise inventory.VerificationError("injected extraction failure")
        return {}
    monkeypatch.setattr(inventory, "extract_pinned_tar", extract)
    monkeypatch.setattr(inventory, "compare", lambda *a: {})
    source = tmp_path / "source.tar"
    source.write_bytes(b"synthetic")
    if failure:
        with pytest.raises(inventory.VerificationError, match="injected extraction"):
            inventory.verify(kit, source)
    else:
        inventory.verify(kit, source)
    assert destinations and not destinations[0].parent.exists()
    assert list(scratch.iterdir()) == []
