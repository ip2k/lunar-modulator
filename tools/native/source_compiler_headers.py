#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate a separately anchored target trace and collect only consumed pi32v2 headers.

This is an input inventory, not a compiler/toolchain source archive. Every raw
receipt is hash-pinned by the trace aggregate and independently checked here.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath

HASH = re.compile(r"^[0-9a-f]{64}$")
MAX_JSON = 64 * 1024 * 1024
MAX_FILES = 12000
MAX_BYTES = 512 * 1024 * 1024
MAX_HEADER_BYTES = 96 * 1024 * 1024
SCHEMA = "lunar-e7-independent-trace-anchor-v1"
HEADER_ROOTS = ("pi32v2/include", "common/lib/clang/4.0.1/include")
NOTICES = {
    "newlib/COPYING.NEWLIB": ("67d85383229c8950fa7bebd1adb74f1382f32d38acc36488055c546ce218e091",
        "https://sourceware.org/git/?p=newlib-cygwin.git;a=blob_plain;f=COPYING.NEWLIB;hb=newlib-2_2_0"),
    "newlib/COPYING": ("231f7edcc7352d7734a96eef0b8030f77982678c516876fcb81e25b32d68564c",
        "https://sourceware.org/git/?p=newlib-cygwin.git;a=blob_plain;f=COPYING;hb=newlib-2_2_0"),
    "clang/LICENSE.TXT": ("de4c79665f0f5688b0ace17cba6f8e0343925bb95e0949d66d47bbd4527310d6",
        "https://raw.githubusercontent.com/llvm/llvm-project/llvmorg-4.0.1/clang/LICENSE.TXT"),
    "llvm/LICENSE.TXT": ("abd4d8794808bacb1eb6924d49efafd9ab6eef88faaaeb5d3cfa13ee3670d672",
        "https://raw.githubusercontent.com/llvm/llvm-project/llvmorg-4.0.1/llvm/LICENSE.TXT"),
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key")
        out[key] = value
    return out


def _read(path: Path, limit: int) -> bytes:
    lexical = path if path.is_absolute() else Path.cwd() / path
    here = Path(lexical.anchor)
    for part in lexical.parts[1:-1]:
        here /= part
        if here.is_symlink():
            raise ValueError("symlink path component refused")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise ValueError("input is not a bounded regular file")
        chunks, size = [], 0
        while True:
            chunk = os.read(fd, min(1024 * 1024, limit + 1 - size))
            if not chunk:
                break
            chunks.append(chunk); size += len(chunk)
            if size > limit:
                raise ValueError("input exceeds byte bound")
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise ValueError("input changed while being read")
        return b"".join(chunks)
    finally:
        os.close(fd)


def _json_bytes(raw: bytes) -> dict:
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    if not isinstance(value, dict):
        raise ValueError("JSON input must be an object")
    return value


def _safe_ref(base: Path, ref: str) -> Path:
    p = PurePosixPath(ref)
    if not isinstance(ref, str) or not ref or p.is_absolute() or any(x in ("", ".", "..") for x in p.parts):
        raise ValueError("unsafe relative trace reference")
    path = base
    for part in p.parts:
        path /= part
        if path.is_symlink():
            raise ValueError("symlink in trace reference")
    if not path.is_file():
        raise ValueError("trace reference is not a regular file")
    if not path.resolve(strict=True).is_relative_to(base.resolve(strict=True)):
        raise ValueError("trace reference escapes trace directory")
    return path


def _pathhash(rows, path_key="path", hash_key="sha256"):
    out = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("inventory row must be an object")
        path, digest = row.get(path_key), row.get(hash_key)
        if not isinstance(path, str) or not path or not isinstance(digest, str) or not HASH.fullmatch(digest) or path in out:
            raise ValueError("malformed or duplicate inventory identity")
        out[path] = digest
    return out


def _relative_runtime(resolved: str, root: str, runtime_root: str) -> str | None:
    prefix = runtime_root.rstrip("/") + "/"
    if resolved.startswith(prefix):
        rel = PurePosixPath(resolved[len(prefix):])
        if rel.is_absolute() or any(x in ("", ".", "..") for x in rel.parts):
            raise ValueError("unsafe resolved dependency path")
        return rel.as_posix()
    return None


def _root_class(path: str) -> str | None:
    roots = (("/output/catalogue/", "catalogue-and-cxx"),
             ("/src/", "catalogue-source"), ("/workspace/", "workspace-source"),
             ("/libcxx/", "libcxx-headers"), ("/usr/include/", "container-system"),
             ("/usr/local/include/", "container-local"), ("/opt/pi32v2-real/", "toolchain"),
             ("/output/", "fresh-build-output"))
    return next((kind for prefix, kind in roots if path.startswith(prefix)), None)


def collect_compiler_headers(*, trace_path: Path, expected_trace_sha256: str,
                             tuple_record: dict, provenance: dict,
                             source_root: Path, toolchain_root: Path, toolchain_manifest: dict,
                             toolchain_manifest_sha256: str,
                             expected_tuple_sha256: str,
                             official_sources: dict[str, Path]) -> tuple[dict[str, bytes], dict]:
    """Check trace closure and return deterministic archive entries + inventory.

    official_sources maps the four NOTICES keys to files fetched from the fixed
    source URLs above. It is deliberately explicit so callers can retain the
    official bytes used for this archive.
    """
    if not isinstance(expected_trace_sha256, str) or not HASH.fullmatch(expected_trace_sha256):
        raise ValueError("external trace SHA-256 anchor is malformed")
    trace_raw = _read(Path(trace_path), MAX_JSON)
    if _sha(trace_raw) != expected_trace_sha256:
        raise ValueError("trace differs from independent external anchor")
    trace = _json_bytes(trace_raw)
    if trace.get("schema") != SCHEMA:
        raise ValueError("unsupported compiler trace schema")
    if (trace.get("source", {}).get("commit") != provenance.get("source_commit")
            or trace.get("source", {}).get("tree_sha256") != tuple_record.get("source_tree_sha256")):
        raise ValueError("trace source commit/tree differs from tuple-bound provenance")
    if trace.get("catalogue", {}).get("source_tree_sha256") != tuple_record.get("catalogue_tree_sha256"):
        raise ValueError("trace catalogue source tree differs from tuple")
    if trace.get("request", {}).get("sha256") != tuple_record.get("request_sha256"):
        raise ValueError("trace request digest differs from tuple")
    base = Path(trace_path).resolve(strict=True).parent
    output_root = base.parent
    source_root = Path(source_root).resolve(strict=True)
    if trace.get("toolchain_manifest", {}).get("sha256") != toolchain_manifest_sha256:
        raise ValueError("trace toolchain manifest digest differs from supplied manifest")
    manifest_bytes = _canonical(toolchain_manifest)
    if not HASH.fullmatch(toolchain_manifest_sha256) or _sha(manifest_bytes) != toolchain_manifest_sha256:
        raise ValueError("toolchain manifest bytes do not match pinned digest")
    try:
        from .capture_trusted_build_tuple import _toolchain_manifest
    except ImportError:
        from capture_trusted_build_tuple import _toolchain_manifest
    actual_manifest = _toolchain_manifest(Path(toolchain_root))
    if actual_manifest != manifest_bytes:
        raise ValueError("supplied toolchain manifest differs from current pinned toolchain tree")
    if trace.get("toolchain", {}).get("tree_sha256") != tuple_record.get("toolchain_tree_sha256"):
        raise ValueError("trace toolchain tree differs from tuple")
    if provenance.get("toolchain_tree_sha256", tuple_record.get("toolchain_tree_sha256")) != tuple_record.get("toolchain_tree_sha256"):
        raise ValueError("provenance/tuple toolchain tree mismatch")
    if trace["toolchain"]["tree_sha256"] != _tree_digest(toolchain_manifest):
        raise ValueError("toolchain manifest tree digest does not match trace")
    compiler = trace["toolchain"].get("compiler", {})
    if compiler.get("sha256") != provenance.get("compiler_sha256"):
        raise ValueError("trace compiler does not match tuple-pinned compiler")
    for key in ("compiler", "linker", "plugin"):
        item = trace["toolchain"].get(key, {})
        _check_manifest_file(toolchain_manifest, toolchain_root, item.get("path"), item.get("sha256"))
    expected_app = tuple_record.get("app_sha256")
    expected_elf = tuple_record.get("elf_sha256")
    outputs = trace.get("expected_outputs", {})
    if outputs.get("app", {}).get("sha256") != expected_app or outputs.get("elf", {}).get("sha256") != expected_elf:
        raise ValueError("trace app/ELF outputs do not match tuple")
    objects = trace.get("linked_objects")
    if not isinstance(objects, list) or not objects:
        raise ValueError("trace lacks linked object inventory")
    expected_objects = _pathhash(objects)
    for row in objects:
        if type(row.get("size")) is not int or row["size"] < 0 or row.get("role") not in ("catalogue", "highlevel"):
            raise ValueError("linked object size/role is malformed")
        _runtime_file(row["path"], "/output", output_root)
    # The schema-2 tuple anchors the provenance sidecar digest; its exact
    # linked-object inventory and compiler hash live in that authenticated
    # sidecar, not in duplicated tuple fields.
    tuple_objects = provenance.get("linked_objects")
    if not isinstance(tuple_objects, list) or _pathhash(tuple_objects) != expected_objects:
        raise ValueError("trace linked objects differ from tuple-bound linked inventory")
    retained = trace.get("retained_verification", {})
    verification_raw = _read(_safe_ref(base, retained.get("path")), MAX_JSON)
    if _sha(verification_raw) != retained.get("sha256"):
        raise ValueError("retained verification bytes do not match trace")
    verification = _json_bytes(verification_raw)
    if _pathhash(verification.get("linked_objects", [])) != expected_objects:
        raise ValueError("retained verification linked objects differ from trace")

    entries: dict[str, bytes] = {"compiler-trace/aggregate.json": trace_raw,
                                 "compiler-trace/retained-verification.json": verification_raw}
    source_manifest = trace.get("source", {}).get("manifest", {})
    request_ref = trace.get("request", {})
    source_manifest_value = None
    for label, row in (("source-manifest", source_manifest), ("request", request_ref)):
        raw = _read(_safe_ref(base, row.get("path")), MAX_JSON)
        if _sha(raw) != row.get("sha256"):
            raise ValueError(f"trace {label} bytes do not match aggregate")
        entries[f"compiler-trace/{label}.json"] = raw
        value = _json_bytes(raw)
        if label == "source-manifest": source_manifest_value = value
        if label == "source-manifest" and (value.get("commit") != provenance.get("source_commit") or _sha(raw) != tuple_record.get("source_tree_sha256")):
            raise ValueError("trace source manifest does not match tuple/provenance")
        if label == "request" and _sha(raw) != tuple_record.get("request_sha256"):
            raise ValueError("trace request bytes do not match tuple")
    source_hashes = {row.get("path"):row.get("sha256") for row in source_manifest_value.get("objects", [])
                     if isinstance(row, dict) and isinstance(row.get("path"), str)}
    manifest_ref = trace.get("toolchain_manifest", {})
    raw_tool_manifest = _read(_safe_ref(base, manifest_ref.get("path")), MAX_JSON)
    if _sha(raw_tool_manifest) != manifest_ref.get("sha256") or raw_tool_manifest != manifest_bytes:
        raise ValueError("trace-pinned raw toolchain manifest differs from supplied manifest")
    entries["compiler-trace/toolchain-manifest.json"] = manifest_bytes
    raw_receipt_rows = []
    dependencies: dict[tuple[str, str], dict] = {}
    compiled = {}
    object_rows = {row["path"]:row for row in objects}
    for row in trace.get("compile_receipts", []):
        raw = _read(_safe_ref(base, row.get("receipt_path")), MAX_JSON)
        if _sha(raw) != row.get("receipt_sha256"):
            raise ValueError("compiler receipt SHA mismatch")
        receipt = _json_bytes(raw)
        if (receipt.get("trace_complete") is not True or receipt.get("compile_exit") != 0
                or receipt.get("dependency_exit") != 0 or receipt.get("status") != "success"):
            raise ValueError("compiler receipt is incomplete or unsuccessful")
        opath, ohash = receipt.get("output"), receipt.get("object_sha256")
        if (opath != row.get("output_path") or ohash != row.get("output_sha256")
                or receipt.get("source") != row.get("source_path")
                or receipt.get("source_sha256") != row.get("source_sha256")):
            raise ValueError("aggregate compiler row differs from raw receipt")
        output_data = _runtime_file(opath, "/output", output_root)
        output_size = row.get("output_size", object_rows.get(opath, {}).get("size"))
        if _sha(output_data) != ohash or (output_size is not None and len(output_data) != output_size):
            raise ValueError("compiler output bytes differ from its anchored receipt")
        source_data = _runtime_file(receipt.get("source"), "/src", source_root,
                                    alternate_runtime_root="/workspace")
        if _sha(source_data) != receipt.get("source_sha256"):
            raise ValueError("compiler source bytes differ from pinned committed source")
        if opath not in expected_objects and not _is_ld_intermediate(opath, trace):
            raise ValueError("compiler output is neither linked nor a declared ld-r input")
        if opath in compiled:
            raise ValueError("duplicate compiler output receipt")
        expected_size = output_size if output_size is not None else len(output_data)
        if type(expected_size) is not int or expected_size < 0:
            raise ValueError("compiler output size is not pinned")
        compiled[opath] = (ohash, expected_size)
        receipt_name = "compiler-trace/receipts/" + row["receipt_path"]
        entries[receipt_name] = raw
        raw_receipt_rows.append({"path": receipt_name, "sha256": _sha(raw), "bytes": len(raw), "kind": "compile"})
        deps = receipt.get("dependencies")
        if not isinstance(deps, list):
            raise ValueError("compiler receipt dependencies must be an array")
        for dep in deps:
            if not isinstance(dep, dict):
                raise ValueError("malformed compiler dependency")
            resolved, root_class = dep.get("resolved"), dep.get("root_class")
            digest, size = dep.get("sha256"), dep.get("size")
            if (not isinstance(resolved, str) or not resolved.startswith("/") or not isinstance(root_class, str)
                    or not isinstance(digest, str) or not HASH.fullmatch(digest)
                    or type(size) is not int or size < 0):
                raise ValueError("invalid dependency identity")
            key = (resolved, digest)
            previous = dependencies.get(key)
            value = {"resolved": resolved, "root_class": root_class, "sha256": digest, "bytes": size}
            if previous is not None and previous != value:
                raise ValueError("conflicting dependency identities across receipts")
            dependencies[key] = value
    if set(expected_objects) - set(compiled):
        raise ValueError("one or more linked objects lack successful compiler receipts")
    for path, digest in expected_objects.items():
        if compiled[path][0] != digest or compiled[path][1] != object_rows[path].get("size"):
            raise ValueError("linked object hash differs from compiler receipt")
    routed_outputs = set(expected_objects)
    for row in trace.get("relocatable_link_receipts", []):
        routed_outputs.update(i.get("path") for i in row.get("inputs", []))
    if set(compiled) - routed_outputs:
        raise ValueError("compiler receipt output is not consumed by final or relocatable link")

    ir_dependencies = _check_ir_and_relocatable(trace, base, output_root, source_root, entries,
                                                  raw_receipt_rows, compiled, expected_objects)
    for dep in ir_dependencies:
        key = (dep["resolved"], dep["sha256"])
        prior = dependencies.get(key)
        value = {"resolved":dep["resolved"],"root_class":dep["root_class"],
                 "sha256":dep["sha256"],"bytes":dep["size"]}
        if prior is not None and prior != value:
            raise ValueError("conflicting IR dependency identity")
        dependencies[key] = value
    final = trace.get("final_link_receipt", {})
    linkraw = _read(_safe_ref(base, final.get("receipt_path")), MAX_JSON)
    if _sha(linkraw) != final.get("receipt_sha256"):
        raise ValueError("final link receipt SHA mismatch")
    link = _json_bytes(linkraw)
    raw_elf = link.get("outputs", {}).get("elf", {})
    raw_map = link.get("outputs", {}).get("map", {})
    for raw_output, expected_hash in ((raw_elf, expected_elf),
                                      (raw_map, final.get("map_sha256")),
                                      (outputs.get("app", {}), expected_app)):
        data = _runtime_file(raw_output.get("path"), "/output", output_root)
        if (raw_output.get("sha256", expected_hash) != expected_hash or _sha(data) != expected_hash
                or ("size" in raw_output and len(data) != raw_output.get("size"))):
            raise ValueError("final linked app/ELF/map output bytes differ from anchored receipts")
    if (link.get("trace_complete") is not True or link.get("returncode") != 0
            or raw_elf.get("sha256") != expected_elf
            or link.get("linker") != trace["toolchain"].get("linker", {}).get("path")
            or link.get("plugin") != trace["toolchain"].get("plugin", {}).get("path")
            or final.get("trace_complete") is not True or final.get("returncode") != 0
            or final.get("elf_sha256") != expected_elf
            or final.get("map_sha256") != raw_map.get("sha256")):
        raise ValueError("final link receipt incomplete, unsuccessful or wrong ELF")
    inputs = link.get("inputs")
    if not isinstance(inputs, list):
        raise ValueError("final link inputs missing")
    input_map = {}
    for item in inputs:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or item["path"] in input_map:
            raise ValueError("duplicate or malformed final link input")
        input_map[item["path"]] = (item.get("sha256"), item.get("size"))
    expected_link_inputs = {p: (h, object_rows[p]["size"]) for p, h in expected_objects.items()}
    for key in ("linker", "plugin"):
        item = trace["toolchain"].get(key, {})
        expected_link_inputs[item.get("path")] = (item.get("sha256"), _toolchain_size(toolchain_manifest, item.get("path"), toolchain_root))
    extras = {p:v for p,v in input_map.items() if p not in expected_link_inputs}
    if len(extras) != 1:
        raise ValueError("final link must have exactly one additional pinned linker script input")
    script_path, script_identity = next(iter(extras.items()))
    argv = link.get("argv", [])
    script_arg = None
    for index, arg in enumerate(argv):
        if arg == "-T" and index + 1 < len(argv):
            script_arg = argv[index + 1]
        elif isinstance(arg, str) and arg.startswith("-T") and len(arg) > 2:
            script_arg = arg[2:]
    if script_arg != script_path:
        raise ValueError("final link script input differs from actual linker argv")
    if script_path.startswith(("/src/", "/workspace/")):
        script_data = _runtime_file(script_path, "/src", source_root, alternate_runtime_root="/workspace")
        rel = script_path.split("/", 3)[-1]
        if source_manifest_value is None or source_hashes.get(rel) != script_identity[0] or _sha(script_data) != script_identity[0]:
            raise ValueError("linker script differs from pinned committed source manifest")
    else:
        script_data = _runtime_file(script_path, "/output", output_root)
    if _sha(script_data) != script_identity[0] or len(script_data) != script_identity[1]:
        raise ValueError("linker script bytes differ from LD receipt")
    entries["compiler-trace/link-inputs/app.ld"] = script_data
    expected_link_inputs[script_path] = script_identity
    aggregate_inputs = final.get("inputs")
    if (not isinstance(aggregate_inputs, list)
            or {x.get("path"):(x.get("sha256"),x.get("size")) for x in aggregate_inputs} != input_map
            or input_map != expected_link_inputs):
        raise ValueError("final link input set does not exactly match linked objects + pinned linker inputs")
    linkname = "compiler-trace/receipts/" + final["receipt_path"]
    entries[linkname] = linkraw
    raw_receipt_rows.append({"path": linkname, "sha256": _sha(linkraw), "bytes": len(linkraw), "kind": "final-link"})

    toolroot = Path(toolchain_root).resolve(strict=True)
    header_files = {}
    unexported_deps = []
    source_deps = []
    for dep in dependencies.values():
        expected_class = _root_class(dep["resolved"])
        if expected_class is None or dep["root_class"] != expected_class:
            raise ValueError("dependency path has an unmapped or conflicting root class")
        rel = _relative_runtime(dep["resolved"], str(toolroot), "/opt/pi32v2-real")
        if rel is None:
            source_prefix = {"catalogue-source":"/src/", "workspace-source":"/workspace/"}.get(dep["root_class"])
            if source_prefix is not None:
                source_rel = dep["resolved"][len(source_prefix):]
                source_data = _runtime_file(dep["resolved"], "/src", source_root, alternate_runtime_root="/workspace")
                if (source_manifest_value is None or source_hashes.get(source_rel) != dep["sha256"]
                        or _sha(source_data) != dep["sha256"]):
                    raise ValueError("source dependency differs from pinned source manifest")
                source_deps.append(dep)
            elif dep["root_class"] in ("catalogue-and-cxx", "fresh-build-output"):
                output_data = _runtime_file(dep["resolved"], "/output", output_root)
                if len(output_data) != dep["bytes"] or _sha(output_data) != dep["sha256"]:
                    raise ValueError("generated output dependency differs from receipt")
                unexported_deps.append(dep)
            else:
                unexported_deps.append(dep)
            continue
        if dep["root_class"] != "toolchain":
            raise ValueError("dependency path is inside pinned toolchain but root class disagrees")
        manifest_row = next((row for row in toolchain_manifest.get("objects", [])
                             if row.get("path") == rel and row.get("kind") in ("file", "symlink-file")), None)
        if (manifest_row is None or manifest_row.get("sha256") != dep["sha256"]
                or manifest_row.get("bytes") != dep["bytes"]):
            raise ValueError("toolchain dependency differs from pinned whole-tree manifest")
        if any(rel == root or rel.startswith(root + "/") for root in HEADER_ROOTS):
            if manifest_row.get("kind") != "file":
                raise ValueError("consumed compiler header must be a regular nonsymlink file")
            source = _safe_under(toolroot, rel)
            data = _read(source, MAX_BYTES)
            if len(data) != dep["bytes"] or _sha(data) != dep["sha256"]:
                raise ValueError("consumed vendor header bytes differ from dependency receipt")
            archive = "compiler-headers/" + rel
            prior = header_files.get(archive)
            if prior is not None and prior != data:
                raise ValueError("conflicting bytes for consumed header path")
            header_files[archive] = data
        else:
            unexported_deps.append({**dep,"scope":"toolchain-file-outside-two-header-roots"})
    if len(header_files) > MAX_FILES or sum(map(len, header_files.values())) > MAX_HEADER_BYTES:
        raise ValueError("consumed compiler headers exceed fixed archive bounds")
    entries.update(header_files)

    notice_rows = []
    if set(official_sources) != set(NOTICES):
        raise ValueError("all four fixed upstream notices are required")
    for name, (digest, url) in NOTICES.items():
        data = _read(Path(official_sources[name]), 1024 * 1024)
        if _sha(data) != digest:
            raise ValueError("upstream notice bytes do not match fixed official pin")
        path = "compiler-notices/" + name
        entries[path] = data
        notice_rows.append({"path": path, "sha256": digest, "bytes": len(data), "source_url": url})
    entry_rows = [{"path": path, "sha256": _sha(data), "bytes": len(data)} for path, data in sorted(entries.items())]
    metadata = {"schema": 1, "trace_sha256": expected_trace_sha256,
                "external_tuple_sha256": expected_tuple_sha256,
                "toolchain_manifest_sha256": toolchain_manifest_sha256,
                "toolchain_tree_sha256": tuple_record["toolchain_tree_sha256"],
                "compiler_sha256": compiler["sha256"], "app_sha256": expected_app, "elf_sha256": expected_elf,
                "raw_receipts": sorted(raw_receipt_rows, key=lambda r:r["path"]),
                "consumed_headers": [{"path": p, "sha256": _sha(b), "bytes": len(b)} for p,b in sorted(header_files.items())],
                "official_notices": notice_rows,
                "dependencies_not_exported_by_compiler_header_collector": sorted(unexported_deps, key=lambda d:(d["resolved"],d["sha256"])),
                "validated_project_source_dependencies": sorted(source_deps, key=lambda d:(d["resolved"],d["sha256"])),
                "entries": entry_rows, "corresponding_source_complete": False,
                "distribution_eligible": False, "reproducible_build": False}
    entries["compiler-trace/INPUTS.json"] = (json.dumps(metadata, sort_keys=True, indent=2)+"\n").encode()
    return entries, metadata


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _tree_digest(manifest):
    return _sha(_canonical(manifest))


def _safe_under(root: Path, rel: str) -> Path:
    p = PurePosixPath(rel)
    if p.is_absolute() or any(x in ("", ".", "..") for x in p.parts):
        raise ValueError("unsafe toolchain path")
    path = root
    for part in p.parts:
        path /= part
        if path.is_symlink():
            raise ValueError("symlink in compiler header path")
    if not path.is_file() or not path.resolve(strict=True).is_relative_to(root):
        raise ValueError("compiler header path is not a regular in-root file")
    return path


def _runtime_file(runtime_path, runtime_root: str, local_root: Path,
                  alternate_runtime_root: str | None = None) -> bytes:
    if not isinstance(runtime_path, str):
        raise ValueError("runtime artifact path is malformed")
    selected = runtime_root
    prefix = selected.rstrip("/") + "/"
    if not runtime_path.startswith(prefix):
        if alternate_runtime_root is None or not runtime_path.startswith(alternate_runtime_root.rstrip("/") + "/"):
            raise ValueError("runtime artifact path is outside its pinned root")
        selected = alternate_runtime_root
        prefix = selected.rstrip("/") + "/"
    rel = runtime_path[len(prefix):]
    path = _safe_under(Path(local_root).resolve(strict=True), rel)
    return _read(path, MAX_BYTES)


def _toolchain_size(manifest, runtime_path, toolroot):
    rel = _relative_runtime(runtime_path, str(Path(toolroot).resolve(strict=True)), "/opt/pi32v2-real")
    for row in manifest.get("objects", []):
        if row.get("path") == rel and row.get("kind") == "file":
            return row.get("bytes")
    raise ValueError("linker/plugin missing from pinned toolchain manifest")


def _check_manifest_file(manifest, toolroot, runtime_path, digest):
    if not isinstance(digest, str) or not HASH.fullmatch(digest):
        raise ValueError("toolchain executable hash is malformed")
    rel = _relative_runtime(runtime_path, str(Path(toolroot).resolve(strict=True)), "/opt/pi32v2-real")
    for row in manifest.get("objects", []):
        if row.get("path") == rel and row.get("kind") in ("file", "symlink-file") and row.get("sha256") == digest:
            return
    raise ValueError("pinned compiler/linker/plugin missing from toolchain manifest")


def _is_ld_intermediate(path, trace):
    allowed = {item.get("path") for row in trace.get("relocatable_link_receipts", []) if isinstance(row, dict)
               for item in row.get("inputs", []) if isinstance(item, dict)}
    return path in allowed


def _check_ir_and_relocatable(trace, base, output_root, source_root, entries, raw_rows, compiled, expected_objects):
    dependencies = []
    for row in trace.get("storage_ir_receipts", []):
        raw = _read(_safe_ref(base, row.get("receipt_path")), MAX_JSON)
        if _sha(raw) != row.get("receipt_sha256"):
            raise ValueError("storage IR receipt SHA mismatch")
        rec = _json_bytes(raw)
        if (rec.get("trace_complete") is not True or rec.get("status") != "success"
                or rec.get("compile_exit") != 0 or rec.get("dependency_exit") != 0
                or rec.get("ir_sha256") != row.get("output_sha256") or rec.get("output") != row.get("output_path")
                or rec.get("indexed") != row.get("define_fm1_tft_indexed")):
            raise ValueError("storage IR receipt incomplete or mismatched")
        ir_data = _runtime_file(rec.get("output"), "/output", output_root)
        if _sha(ir_data) != rec.get("ir_sha256") or len(ir_data) != row.get("output_size"):
            raise ValueError("storage IR output bytes differ from receipt")
        source_data = _runtime_file(rec.get("source"), "/src", source_root, alternate_runtime_root="/workspace")
        if _sha(source_data) != rec.get("source_sha256"):
            raise ValueError("storage IR source bytes differ from committed source")
        deps = rec.get("dependencies", [])
        if not isinstance(deps, list):
            raise ValueError("storage IR dependencies must be an array")
        dependencies.extend(deps)
        name = "compiler-trace/receipts/" + row["receipt_path"]
        entries[name] = raw; raw_rows.append({"path":name,"sha256":_sha(raw),"bytes":len(raw),"kind":"storage-ir"})
    for row in trace.get("relocatable_link_receipts", []):
        raw = _read(_safe_ref(base, row.get("receipt_path")), MAX_JSON)
        if _sha(raw) != row.get("receipt_sha256"):
            raise ValueError("relocatable link receipt SHA mismatch")
        rec = _json_bytes(raw)
        raw_output = rec.get("output", {})
        if (rec.get("trace_complete") is not True or rec.get("returncode") != 0
                or raw_output.get("sha256") != row.get("output_sha256")
                or raw_output.get("path") != row.get("output_path")):
            raise ValueError("relocatable link receipt incomplete or mismatched")
        output_data = _runtime_file(raw_output.get("path"), "/output", output_root)
        if _sha(output_data) != raw_output.get("sha256") or len(output_data) != raw_output.get("size"):
            raise ValueError("relocatable link output bytes differ from receipt")
        inputs = rec.get("inputs")
        if not isinstance(inputs, list) or {i.get("path"):(i.get("sha256"),i.get("size")) for i in inputs} != {i.get("path"):(i.get("sha256"),i.get("size")) for i in row.get("inputs", [])}:
            raise ValueError("relocatable link inputs differ from aggregate")
        input_identities = {item.get("path"):(item.get("sha256"),item.get("size")) for item in inputs}
        if any(path not in compiled or compiled[path] != identity for path,identity in input_identities.items()):
            raise ValueError("relocatable link input lacks a matching successful compile receipt")
        if (raw_output.get("path") not in expected_objects
                or expected_objects[raw_output.get("path")] != raw_output.get("sha256")):
            raise ValueError("relocatable link output is not an exact final linked object")
        name = "compiler-trace/receipts/" + row["receipt_path"]
        entries[name] = raw; raw_rows.append({"path":name,"sha256":_sha(raw),"bytes":len(raw),"kind":"relocatable-link"})
    return dependencies
