import hashlib
import json
from pathlib import Path

import pytest

from tools.native import source_compiler_headers as collector
from tools.native.capture_trusted_build_tuple import _toolchain_manifest


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def write_json(path, value):
    raw = canonical(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def fixture(tmp_path, monkeypatch):
    root = tmp_path / "toolchain"
    (root / "pi32v2/include").mkdir(parents=True)
    (root / "common/lib/clang/4.0.1/include").mkdir(parents=True)
    (root / "bin").mkdir()
    header = b"/* pinned target header */\n"
    (root / "pi32v2/include/stdint.h").write_bytes(header)
    (root / "bin/clang").write_bytes(b"compiler")
    (root / "bin/ld").write_bytes(b"linker")
    (root / "bin/plugin.so").write_bytes(b"plugin")
    tool_manifest_raw = _toolchain_manifest(root)
    tool_manifest = json.loads(tool_manifest_raw)
    tool_manifest_sha = digest(tool_manifest_raw)

    base = tmp_path / "output/trace"
    base.mkdir(parents=True)
    script = b"SECTIONS {}\n"
    script_path = tmp_path / "output/build/link/app.ld"
    script_path.parent.mkdir(parents=True)
    script_path.write_bytes(script)
    source_manifest = {"schema": 1, "commit": "a" * 40,
                       "objects": [{"path": "one.c", "sha256": digest(b"source")}]}
    source_raw = write_json(base / "source-manifest.json", source_manifest)
    request_raw = write_json(base / "request.json", {"version": 1})
    write_json(base / "toolchain-manifest.json", tool_manifest)
    obj = b"object"
    source = b"source"
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "one.c").write_bytes(source)
    objpath = "/output/catalogue/one.o"
    sourcepath = "/workspace/one.c"
    (tmp_path / "output/catalogue").mkdir(parents=True)
    (tmp_path / "output/catalogue/one.o").write_bytes(obj)
    compile_raw = write_json(base / "receipts/compile.json", {
        "status": "success", "trace_complete": True, "compile_exit": 0, "dependency_exit": 0,
        "output": objpath, "object_sha256": digest(obj), "source": sourcepath,
        "source_sha256": digest(source), "dependencies": [{
            "spelling": "stdint.h", "resolved": "/opt/pi32v2-real/pi32v2/include/stdint.h",
            "root_class": "toolchain", "size": len(header), "sha256": digest(header)}]})
    linked = [{"path": objpath, "sha256": digest(obj), "size": len(obj), "role": "catalogue"}]
    verification_raw = write_json(base / "verification.json", {"linked_objects": linked})
    link_inputs = [
        {"path": objpath, "sha256": digest(obj), "size": len(obj)},
        {"path": "/opt/pi32v2-real/bin/ld", "sha256": digest(b"linker"), "size": 6},
        {"path": "/opt/pi32v2-real/bin/plugin.so", "sha256": digest(b"plugin"), "size": 6},
        {"path": "/output/build/link/app.ld", "sha256": digest(script), "size": len(script)},
    ]
    elf_sha, map_sha = digest(b"elf"), digest(b"map")
    (tmp_path / "output/app.elf").write_bytes(b"elf")
    (tmp_path / "output/app.map").write_bytes(b"map")
    (tmp_path / "output/app.bin").write_bytes(b"app")
    link_raw = write_json(base / "receipts/link.json", {
        "trace_complete": True, "returncode": 0,
        "outputs": {"elf": {"path": "/output/app.elf", "sha256": elf_sha, "size": 3},
                    "map": {"path": "/output/app.map", "sha256": map_sha, "size": 3}},
        "linker": "/opt/pi32v2-real/bin/ld", "plugin": "/opt/pi32v2-real/bin/plugin.so",
        "argv": ["ld", "-T", "/output/build/link/app.ld"], "inputs": link_inputs})
    tool = {"root": "/opt/pi32v2-real", "tree_sha256": tool_manifest_sha,
            "compiler": {"path": "/opt/pi32v2-real/bin/clang", "sha256": digest(b"compiler")},
            "linker": {"path": "/opt/pi32v2-real/bin/ld", "sha256": digest(b"linker")},
            "plugin": {"path": "/opt/pi32v2-real/bin/plugin.so", "sha256": digest(b"plugin")}}
    trace = {
        "schema": collector.SCHEMA,
        "source": {"commit": "a" * 40, "tree_sha256": digest(source_raw),
                   "manifest": {"path": "source-manifest.json", "sha256": digest(source_raw)}},
        "request": {"path": "request.json", "sha256": digest(request_raw)},
        "toolchain_manifest": {"path": "toolchain-manifest.json", "sha256": tool_manifest_sha},
        "toolchain": tool,
        "catalogue": {"source_tree_sha256": "b" * 64, "selected_count": 1, "shards": ["shard-00"]},
        "retained_verification": {"path": "verification.json", "sha256": digest(verification_raw)},
        "expected_outputs": {"app": {"path": "/output/app.bin", "sha256": digest(b"app")},
                             "elf": {"path": "/output/app.elf", "sha256": elf_sha}},
        "linked_objects": linked,
        "compile_receipts": [{"receipt_path": "receipts/compile.json", "receipt_sha256": digest(compile_raw),
                               "output_path": objpath, "output_sha256": digest(obj), "output_size": len(obj),
                               "source_path": sourcepath, "source_sha256": digest(source),
                               "kind": "compile", "shard": "shard-00"}],
        "storage_ir_receipts": [], "relocatable_link_receipts": [],
        "final_link_receipt": {"receipt_path": "receipts/link.json", "receipt_sha256": digest(link_raw),
                               "trace_complete": True, "returncode": 0, "elf_sha256": elf_sha,
                               "map_sha256": map_sha, "inputs": link_inputs},
    }
    trace_raw = write_json(base / "aggregate.json", trace)
    tuple_record = {"toolchain_tree_sha256": tool_manifest_sha,
                    "app_sha256": digest(b"app"), "elf_sha256": elf_sha,
                    "catalogue_tree_sha256": "b" * 64,
                    "source_tree_sha256": digest(source_raw), "request_sha256": digest(request_raw),
                    "linked_objects": [{"path": objpath, "sha256": digest(obj)}]}
    provenance = {"source_commit": "a" * 40, "toolchain_tree_sha256": tool_manifest_sha,
                  "compiler_sha256": digest(b"compiler"), "linked_objects": linked}
    notice_data = {key: ("notice:" + key).encode() for key in collector.NOTICES}
    monkeypatch.setattr(collector, "NOTICES", {key: (digest(value), f"https://example.invalid/{key}")
                                                for key, value in notice_data.items()})
    notice_paths = {}
    for key, data in notice_data.items():
        path = tmp_path / "notices" / key.replace("/", "_")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        notice_paths[key] = path
    return {"trace_path": base / "aggregate.json", "trace_sha": digest(trace_raw),
            "tuple": tuple_record, "provenance": provenance, "root": root, "source_root": source_root,
            "manifest": tool_manifest, "manifest_sha": tool_manifest_sha, "notices": notice_paths,
            "header": header, "object": objpath}


def collect(data, trace_sha=None):
    return collector.collect_compiler_headers(
        trace_path=data["trace_path"], expected_trace_sha256=trace_sha or data["trace_sha"],
        tuple_record=data["tuple"], provenance=data["provenance"], source_root=data["source_root"], toolchain_root=data["root"],
        toolchain_manifest=data["manifest"], toolchain_manifest_sha256=data["manifest_sha"],
        expected_tuple_sha256="d" * 64, official_sources=data["notices"])


def test_collects_only_consumed_pinned_header_and_retains_anchor(tmp_path, monkeypatch):
    data = fixture(tmp_path, monkeypatch)
    entries, report = collect(data)
    assert entries["compiler-headers/pi32v2/include/stdint.h"] == data["header"]
    assert "compiler-headers/common/lib/clang/4.0.1/include" not in "\n".join(entries)
    assert entries["compiler-trace/aggregate.json"] == data["trace_path"].read_bytes()
    assert report["trace_sha256"] == data["trace_sha"]
    assert report["external_tuple_sha256"] == "d" * 64
    assert report["corresponding_source_complete"] is False
    assert report["distribution_eligible"] is False
    assert report["reproducible_build"] is False


def test_rejects_wrong_independent_trace_anchor(tmp_path, monkeypatch):
    data = fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="external anchor"):
        collect(data, "e" * 64)


def test_rejects_linked_object_without_compile_receipt(tmp_path, monkeypatch):
    data = fixture(tmp_path, monkeypatch)
    trace = json.loads(data["trace_path"].read_text())
    trace["compile_receipts"] = []
    write_json(data["trace_path"], trace)
    data["trace_sha"] = digest(data["trace_path"].read_bytes())
    with pytest.raises(ValueError, match="lack successful compiler receipts"):
        collect(data)
