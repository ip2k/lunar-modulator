import importlib.util
import os
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools/native/run_frozen_trio_diagnostic_build.py"
spec = importlib.util.spec_from_file_location("frozen_trio_build", SCRIPT)
frozen = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(frozen)


def test_tree_manifest_is_canonical_and_content_bound(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "sub").mkdir()
    (root / "sub" / "input").write_bytes(b"source")
    first = frozen.tree_manifest(root)
    assert first == frozen.tree_manifest(root)
    (root / "sub" / "input").write_bytes(b"changed")
    assert first != frozen.tree_manifest(root)


def test_tree_manifest_binds_modes_and_symlinks(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    child = root / "child"
    child.write_bytes(b"x")
    link = root / "alias"
    link.symlink_to("child")
    before = frozen.tree_manifest(root)
    child.chmod(0o700)
    assert before != frozen.tree_manifest(root)
    assert b'"target":"child"' in frozen.tree_manifest(root)


def test_tree_manifest_refuses_escaping_symlink(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "outside").symlink_to(tmp_path / "missing")
    with pytest.raises((ValueError, FileNotFoundError)):
        frozen.tree_manifest(root)


def test_copy_verified_snapshot_matches_bytes_and_modes(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "x").write_bytes(b"payload")
    dest = tmp_path / "dest"
    manifest = frozen.copy_tree_verified(source, dest)
    assert manifest == frozen.tree_manifest(source)
    assert manifest == frozen.tree_manifest(dest)


def test_command_contract_is_pinned():
    assert frozen.PINNED_COMMIT == "66196f54f3295cfdec14a2924c767235bbd5cc2c"
    assert frozen.PINNED_IMAGE.startswith("sha256:")
