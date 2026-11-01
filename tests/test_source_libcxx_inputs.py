import hashlib
import json
import os
import stat
from pathlib import Path

import pytest

from tools.native import source_libcxx_inputs as inputs


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")


def _fixture(tmp_path, monkeypatch):
    source = tmp_path / "pristine"
    source.mkdir(parents=True)
    names = ["__config"] + [f"detail/header-{index:03}.h" for index in range(188)]
    source_bytes = {}
    for name in names:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        data = (b"#define _LIBCPP_HAS_THREAD_API_PTHREAD\n"
                if name == "__config" else ("// " + name + "\n").encode())
        path.write_bytes(data)
        path.chmod(0o644)
        source_bytes[name] = data
    rows = []
    for path in sorted(source.rglob("*")):
        rel = path.relative_to(source).as_posix()
        if path.is_dir():
            rows.append(f"{rel}\0{stat.S_IMODE(path.stat().st_mode)}\0\n".encode())
        else:
            rows.append(f"{rel}\0{stat.S_IMODE(path.stat().st_mode)}\0{_sha(path.read_bytes())}\n".encode())
    # The production pin covers files only; directory modes are not part of it.
    tree_digest = _sha(b"".join(sorted(
        f"{path}\0{stat.S_IMODE((source / path).stat().st_mode)}\0{_sha(data)}\n".encode()
        for path, data in source_bytes.items())))
    monkeypatch.setattr(inputs, "LIBCXX_TREE_SHA256", tree_digest)
    monkeypatch.setattr(inputs, "HEADER_COUNT", len(source_bytes))

    catalogue = tmp_path / "catalogue"
    catalogue.mkdir()
    for shard in range(16):
        cxx = catalogue / f"shard-{shard:02d}" / "cxx"
        cxx.mkdir(parents=True)
        for name, data in source_bytes.items():
            target = cxx / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if name == "__config":
                data = data.replace(inputs._PTHREAD, inputs._NO_THREADS)
            target.write_bytes(data)
            target.chmod(0o600 if name == "__config" else 0o644)
    manifest = tmp_path / "catalogue-tree-manifest.json"
    objects = [{"path": ".", "kind": "directory", "mode": stat.S_IMODE(catalogue.stat().st_mode)}]
    for path in catalogue.rglob("*"):
        rel = path.relative_to(catalogue).as_posix()
        if path.is_dir():
            objects.append({"path": rel, "kind": "directory", "mode": stat.S_IMODE(path.stat().st_mode)})
        else:
            data = path.read_bytes()
            objects.append({"path": rel, "kind": "file", "bytes": len(data),
                            "sha256": _sha(data), "mode": stat.S_IMODE(path.stat().st_mode)})
    objects.sort(key=lambda row: row["path"])
    raw = _canonical({"schema": 1, "objects": objects})
    manifest.write_bytes(raw)
    license_path = tmp_path / "LICENSE.TXT"
    license_bytes = b"fixture official notice"
    license_path.write_bytes(license_bytes)
    monkeypatch.setattr(inputs, "LIBCXX_LICENSE_SHA256", _sha(license_bytes))
    return source, source_bytes, catalogue, manifest, _sha(raw), license_path, license_bytes


def _collect(fixture, *, pristine_headers=None, expected=None, license_path=None):
    source, _, catalogue, manifest, digest, notice, _ = fixture
    return inputs.collect_libcxx_inputs(
        catalogue_root=catalogue,
        catalogue_manifest=manifest,
        expected_catalogue_tree_sha256=expected or digest,
        official_license=license_path or notice,
        pristine_headers=pristine_headers,
    )


def test_rejects_missing_pristine_tree(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path, monkeypatch)
    with pytest.raises(TypeError, match="pristine_headers"):
        inputs.collect_libcxx_inputs(
            catalogue_root=fixture[2], catalogue_manifest=fixture[3],
            expected_catalogue_tree_sha256=fixture[4], official_license=fixture[5])


def test_pristine_tree_pin_and_exact_bytes_enable_identity_metadata(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path, monkeypatch)
    entries, metadata = _collect(fixture, pristine_headers=fixture[0])
    assert metadata["pristine_tree_identity_verified"] is True
    assert metadata["header_tree_sha256"] == inputs.LIBCXX_TREE_SHA256
    assert entries["external/libcxx-llvmorg-12.0.0/LICENSE.TXT"] == fixture[6]


def test_tuple_manifest_digest_and_recomputed_tree_are_both_required(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="tuple-bound digest"):
        _collect(fixture, expected="0" * 64)
    (fixture[2] / "shard-00/cxx/__config").write_bytes(b"changed")
    with pytest.raises(ValueError, match="tuple-bound tree manifest"):
        _collect(fixture)


def test_rejects_missing_shard_and_multiple_adaptation_lines(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path, monkeypatch)
    for path in (fixture[2] / "shard-15/cxx").rglob("*"):
        if path.is_file():
            path.unlink()
    # Rewrite the manifest for the deliberately mutated catalogue.
    _refresh_manifest(fixture[2], fixture[3])
    with pytest.raises(ValueError, match=r"missing captured libc\+\+ input tree"):
        _collect(fixture, expected=_sha(fixture[3].read_bytes()))

    fixture = _fixture(tmp_path / "second", monkeypatch)
    for shard in range(16):
        config = fixture[2] / f"shard-{shard:02d}/cxx/__config"
        config.write_bytes(inputs._NO_THREADS + inputs._NO_THREADS)
    _refresh_manifest(fixture[2], fixture[3])
    with pytest.raises(ValueError, match="exactly the known no-thread adaptation"):
        _collect(fixture, expected=_sha(fixture[3].read_bytes()))


def _refresh_manifest(catalogue, manifest):
    objects = [{"path": ".", "kind": "directory", "mode": stat.S_IMODE(catalogue.stat().st_mode)}]
    for path in catalogue.rglob("*"):
        rel = path.relative_to(catalogue).as_posix()
        if path.is_dir():
            objects.append({"path": rel, "kind": "directory", "mode": stat.S_IMODE(path.stat().st_mode)})
        else:
            data = path.read_bytes()
            objects.append({"path": rel, "kind": "file", "bytes": len(data), "sha256": _sha(data),
                            "mode": stat.S_IMODE(path.stat().st_mode)})
    objects.sort(key=lambda row: row["path"])
    manifest.write_bytes(_canonical({"schema": 1, "objects": objects}))


def test_rejects_wrong_notice_symlink_and_nonregular_pristine_input(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path, monkeypatch)
    bad_notice = tmp_path / "wrong-license"
    bad_notice.write_bytes(b"not the pinned notice")
    with pytest.raises(ValueError, match="pinned LLVM"):
        _collect(fixture, pristine_headers=fixture[0], license_path=bad_notice)

    symlink = tmp_path / "header-link"
    symlink.symlink_to(fixture[0] / "__config")
    with pytest.raises(ValueError, match="symlink file"):
        inputs._read_header_tree(symlink.parent)
    fifo = tmp_path / "header-fifo"
    os.mkfifo(fifo)
    with pytest.raises(ValueError, match="invalid or oversized regular file"):
        inputs._read_regular(fifo, 1024)


def test_rejects_pristine_mode_or_content_mutation(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path, monkeypatch)
    (fixture[0] / "detail/header-000.h").chmod(0o600)
    with pytest.raises(ValueError, match="fixed upstream path/mode/hash pin"):
        _collect(fixture, pristine_headers=fixture[0])


def test_rejects_oversized_manifest_and_header_files(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(inputs, "MAX_MANIFEST_BYTES", 8)
    with pytest.raises(ValueError, match="oversized regular file"):
        _collect(fixture, expected=_sha(fixture[3].read_bytes()))

    fixture = _fixture(tmp_path / "second", monkeypatch)
    monkeypatch.setattr(inputs, "MAX_MANIFEST_BYTES", 16 * 1024 * 1024)
    monkeypatch.setattr(inputs, "MAX_HEADER_FILE_BYTES", 4)
    with pytest.raises(ValueError, match=r"byte limit|oversized regular file|invalid libc\+\+ file row"):
        _collect(fixture)
