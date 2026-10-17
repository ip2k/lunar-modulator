"""Small synthetic checks for the Workbench archive inventory verifier.

The end-to-end verifier intentionally accepts only the pinned vendor archives.
These tests exercise its member and manifest readers directly so malformed
archives can be covered without weakening those production pins.
"""
from __future__ import annotations

import hashlib
import json
import stat
import zipfile

import pytest

from tools.workbench import verify_inventory as inventory


def _zip(tmp_path, entries):
    path = tmp_path / "synthetic.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for item in entries:
            if len(item) == 2:
                name, data = item
                archive.writestr(name, data)
            else:
                info, data = item
                archive.writestr(info, data)
    return path


def _open(path):
    return zipfile.ZipFile(path)


def test_zip_index_normalizes_backslashes_without_extracting(tmp_path):
    path = _zip(tmp_path, [(r"sdk\app\image.bin", b"payload")])
    with _open(path) as archive:
        files = inventory.zip_index(archive)
        assert set(files) == {"sdk/app/image.bin"}
        assert archive.read(files["sdk/app/image.bin"]) == b"payload"


@pytest.mark.parametrize(
    "name",
    ["../escape", "/absolute", "C:\\outside", r"sdk\..\escape", "sdk/./file"],
)
def test_zip_index_rejects_unsafe_paths(tmp_path, name):
    path = _zip(tmp_path, [(name, b"x")])
    with _open(path) as archive, pytest.raises(inventory.VerificationError):
        inventory.zip_index(archive)


@pytest.mark.parametrize(
    "names",
    [
        (r"sdk\file.bin", "sdk/file.bin"),
        ("Assets/Patch.syx", "assets/patch.syx"),
    ],
)
def test_zip_index_rejects_normalized_and_casefold_duplicates(tmp_path, names):
    path = _zip(tmp_path, [(names[0], b"first"), (names[1], b"second")])
    with _open(path) as archive, pytest.raises(inventory.VerificationError):
        inventory.zip_index(archive)


def test_zip_index_rejects_symlink_members(tmp_path):
    link = zipfile.ZipInfo("sdk/link")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    path = _zip(tmp_path, [(link, b"target")])
    with _open(path) as archive, pytest.raises(inventory.VerificationError, match="link/special"):
        inventory.zip_index(archive)


def _manifest_zip(tmp_path, corrupt=False):
    files = {f"payload/{i:02d}.bin": bytes([i, i ^ 0x5A]) for i in range(65)}
    listed = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    stored = dict(files)
    if corrupt:
        stored["payload/64.bin"] = b"altered"
    manifest = json.dumps({"files": listed}, separators=(",", ":")).encode()
    path = tmp_path / "manifest.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("sdk/manifest.json", manifest)
        for name, data in stored.items():
            archive.writestr(name, data)
    return path


def test_check_manifest_accepts_matching_synthetic_hashes(tmp_path):
    path = _manifest_zip(tmp_path)
    with _open(path) as archive:
        files = inventory.zip_index(archive)
        assert inventory.check_manifest(archive, files)["checked"] == 65


def test_check_manifest_rejects_hash_mismatch(tmp_path):
    path = _manifest_zip(tmp_path, corrupt=True)
    with _open(path) as archive:
        files = inventory.zip_index(archive)
        with pytest.raises(inventory.VerificationError, match="manifest mismatch"):
            inventory.check_manifest(archive, files)
