#!/usr/bin/env python3
"""Apply reversible, same-size app patches offline, bound to an exact source.

This module has no device transport. Package decoding and cipher provenance
are documented in docs/12-package-inspection.md and THIRD_PARTY_NOTICES.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

try:
    from . import fm1_package as package
except ImportError:
    import fm1_package as package


MAX_PATCHES = 1024
MAX_PATCH_BYTES = 1024 * 1024
MAX_JSON_BYTES = 8 * 1024 * 1024
MANIFEST_KIND = "fm1-rebuild-manifest"


class RebuildError(ValueError):
    """A patch, source, or reversible manifest does not meet the contract."""


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_check(raw: bytes, expected: str) -> None:
    package._bounded(raw)
    if not isinstance(expected, str) or re.fullmatch(r"[0-9a-fA-F]{64}", expected) is None:
        raise RebuildError("expected_source_sha256 must be a complete SHA256 hex digest")
    if _hash(raw) != expected.lower():
        raise RebuildError("source SHA256 differs from the exact source selected for these patches")


def _hex_bytes(value: object, name: str) -> bytes:
    if not isinstance(value, str) or len(value) > MAX_PATCH_BYTES * 3:
        raise RebuildError(f"{name} must be bounded hexadecimal text")
    try:
        return bytes.fromhex(value)
    except ValueError as error:
        raise RebuildError(f"{name} is not valid hexadecimal byte text") from error


def _prepare_patches(app: bytes, patches: list[dict]) -> tuple[bytes, list[dict]]:
    if not isinstance(patches, list) or len(patches) > MAX_PATCHES:
        raise RebuildError(f"patches must be a list with at most {MAX_PATCHES} entries")
    normalized = []
    total = 0
    for index, patch in enumerate(patches):
        if not isinstance(patch, dict) or set(patch) - {"offset", "expected_hex", "replacement_hex", "label"}:
            raise RebuildError(f"patch {index} has unknown fields or is not an object")
        offset = patch.get("offset")
        if type(offset) is not int or offset < 0:
            raise RebuildError(f"patch {index} offset must be a nonnegative integer application file offset")
        before = _hex_bytes(patch.get("expected_hex"), f"patch {index} expected_hex")
        after = _hex_bytes(patch.get("replacement_hex"), f"patch {index} replacement_hex")
        if not before or len(before) != len(after):
            raise RebuildError(f"patch {index} must replace a nonempty range with exactly the same byte length")
        total += len(before)
        if total > MAX_PATCH_BYTES:
            raise RebuildError(f"patches exceed the {MAX_PATCH_BYTES}-byte total limit")
        if offset > len(app) or len(before) > len(app) - offset:
            raise RebuildError(f"patch {index} lies outside the decoded application")
        if app[offset:offset + len(before)] != before:
            raise RebuildError(f"patch {index} expected bytes do not match the source at offset 0x{offset:x}")
        label = patch.get("label", "")
        if not isinstance(label, str) or len(label) > 160 or any(ord(char) < 32 for char in label):
            raise RebuildError(f"patch {index} label must be single-line text of at most 160 characters")
        normalized.append({"offset": offset, "expected_hex": before.hex(),
                           "replacement_hex": after.hex(), "label": label})
    normalized.sort(key=lambda patch: patch["offset"])
    for previous, current in zip(normalized, normalized[1:]):
        if current["offset"] < previous["offset"] + len(previous["expected_hex"]) // 2:
            raise RebuildError("patch ranges overlap; every expected byte must refer to the original source")
    output = bytearray(app)
    for patch in normalized:
        start = patch["offset"]
        replacement = bytes.fromhex(patch["replacement_hex"])
        output[start:start + len(replacement)] = replacement
    identities = lambda data: [(match.start(), match.group()) for match in package.IDENTITY_PATTERN.finditer(data)]
    if identities(app) != identities(bytes(output)):
        raise RebuildError("patches change an embedded FM-1 identity; this builder preserves version identity")
    return bytes(output), normalized


def _logical(raw: bytes) -> bytearray:
    return bytearray(b"".join(raw[i * 48:i * 48 + 47] for i in range(20)) + raw[960:])


def _raw_offset(logical_offset: int) -> int:
    return logical_offset + logical_offset // 47 if logical_offset < 940 else logical_offset + 20


def _restore_markers(logical: bytes, original: bytes) -> bytes:
    output = bytearray(original)
    if len(logical) + 20 != len(original):
        raise RebuildError("rebuild changed the package size")
    for index in range(20):
        output[index * 48:index * 48 + 47] = logical[index * 47:index * 47 + 47]
    output[960:] = logical[940:]
    return bytes(output)


def _assert_unchanged_outside(before: bytes, after: bytes, ranges: list[tuple[int, int]]) -> None:
    if len(before) != len(after):
        raise RebuildError("rebuild changed the image size")
    cursor = 0
    for start, end in sorted(ranges):
        if not 0 <= start <= end <= len(before):
            raise RebuildError("internal preservation range is outside the image")
        if start > cursor and before[cursor:start] != after[cursor:start]:
            raise RebuildError("rebuild changed bytes outside patches and their dependent CRC fields")
        cursor = max(cursor, end)
    if before[cursor:] != after[cursor:]:
        raise RebuildError("rebuild changed bytes outside patches and their dependent CRC fields")


def _snapshot(report: dict) -> dict:
    app = report.get("application", report)
    return {"kind": report["kind"], "size": report["size"], "sha256": report["sha256"],
            "application_size": app["size"], "application_sha256": app["sha256"],
            "package_identity": report.get("identity", {}).get("value"),
            "embedded_identities": app["embedded_identities"]}


def _seal(manifest: dict) -> dict:
    manifest.pop("manifest_sha256", None)
    content = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    manifest["manifest_sha256"] = _hash(content.encode("utf-8"))
    return manifest


def _manifest(source: dict, result: dict, patches: list[dict], updates: list[dict]) -> dict:
    changed = sum(sum(left != right for left, right in zip(bytes.fromhex(patch["expected_hex"]),
                                                          bytes.fromhex(patch["replacement_hex"])))
                  for patch in patches)
    input_kind = "package" if source["kind"] == "fm1-package" else "application"
    return _seal({"schema_version": 1, "kind": MANIFEST_KIND, "input_kind": input_kind,
                  "operation": "rebuild", "source_sha256": source["sha256"],
                  "result_sha256": result["sha256"], "source": _snapshot(source),
                  "output": _snapshot(result), "patches": patches, "updated_integrity": updates,
                  "verification": {"no_op": source["sha256"] == result["sha256"],
                                   "changed_application_bytes": changed, "identity_preserved": True,
                                   "non_application_payloads_preserved": True,
                                   "unrelated_bytes_preserved": True,
                                   "dependent_crc_fields_may_change": input_kind == "package",
                                   "bootability_verified": False},
                  "device_io_performed": False})


def rebuild_application(raw: bytes, patches: list[dict], *, expected_source_sha256: str) -> tuple[bytes, dict]:
    """Patch a standalone app.bin, with no assumed load address or device I/O."""
    _source_check(raw, expected_source_sha256)
    source = package.inspect_application(raw)
    result, normalized = _prepare_patches(raw, patches)
    ranges = [(patch["offset"], patch["offset"] + len(patch["expected_hex"]) // 2) for patch in normalized]
    _assert_unchanged_outside(raw, result, ranges)
    return result, _manifest(source, package.inspect_application(result), normalized, [])


def rebuild_package(raw: bytes, patches: list[dict], *, expected_source_sha256: str) -> tuple[bytes, dict]:
    """Repack a checked FWSC after same-size patches in its decoded app.bin."""
    _source_check(raw, expected_source_sha256)
    source, app = package.inspect_and_extract(raw)
    modified_app, normalized = _prepare_patches(app, patches)
    logical = _logical(raw)
    flash_number, flash_entry = next((index, entry) for index, entry in enumerate(source["entries"])
                                    if entry["name"] == "flash.bin")
    flash_start, flash_size = flash_entry["offset"], flash_entry["size"]
    flash = bytearray(logical[flash_start:flash_start + flash_size])
    extraction = source["application"]["extraction"]
    area_base = extraction["app_area_offset"]
    area = bytearray(package._sfc_decode(bytes(flash[area_base:]), int(extraction["chip_key"], 16)))
    app_offset = extraction["relative_data_offset"]
    app_header = extraction["entry_header_offset"] - area_base
    area_size = struct.unpack_from("<I", area, 8)[0]
    area[app_offset:app_offset + len(app)] = modified_app
    updates = []

    def update_crc(buffer: bytearray, offset: int, value: int, layer: str, logical_offset: int) -> None:
        previous = struct.unpack_from("<H", buffer, offset)[0]
        struct.pack_into("<H", buffer, offset, value)
        updates.append({"layer": layer, "before": f"{previous:04x}", "after": f"{value:04x}",
                        "logical_field_offset": logical_offset})

    logical_area = flash_start + area_base
    update_crc(area, app_header + 2, package.crc16(modified_app), "app.bin data", logical_area + app_header + 2)
    update_crc(area, app_header, package.crc16(area[app_header + 2:app_header + 32]),
               "app.bin directory header", logical_area + app_header)
    update_crc(area, 2, package.crc16(area[32:area_size]), "application area body", logical_area + 2)
    update_crc(area, 0, package.crc16(area[2:32]), "application area header", logical_area)
    flash[area_base:] = package._sfc_decode(bytes(area), int(extraction["chip_key"], 16))
    logical[flash_start:flash_start + flash_size] = flash
    entry_offset = 64 + flash_number * 80
    entry = bytearray(package._unscramble(bytes(logical[entry_offset:entry_offset + 80])))
    update_crc(entry, 4, package.crc16(flash), "UFW flash.bin payload", entry_offset + 4)
    logical[entry_offset:entry_offset + 80] = package._unscramble(bytes(entry))
    header = bytearray(package._unscramble(bytes(logical[:64])))
    table_end = 64 + len(source["entries"]) * 80
    update_crc(header, 2, package.crc16(logical[64:table_end]), "UFW entry table", 2)
    update_crc(header, 0, package.crc16(header[2:64]), "UFW header", 0)
    logical[:64] = package._unscramble(bytes(header))
    result = _restore_markers(bytes(logical), raw)

    allowed = []
    for update in updates:
        for offset in range(update["logical_field_offset"], update["logical_field_offset"] + 2):
            allowed.append((_raw_offset(offset), _raw_offset(offset) + 1))
    for patch in normalized:
        logical_start = logical_area + app_offset + patch["offset"]
        start = _raw_offset(logical_start)
        allowed.append((start, start + len(patch["expected_hex"]) // 2))
    _assert_unchanged_outside(raw, result, allowed)
    result_report, result_app = package.inspect_and_extract(result)
    if result_app != modified_app:
        raise RebuildError("re-inspected application differs from the planned patch result")
    if source["identity"] != result_report["identity"]:
        raise RebuildError("rebuild changed the package identity")
    return result, _manifest(source, result_report, normalized, updates)


def _rollback(raw: bytes, manifest: dict, input_kind: str) -> tuple[bytes, dict]:
    if not isinstance(manifest, dict):
        raise RebuildError("rollback requires a manifest object")
    try:
        serialized = json.dumps(manifest, allow_nan=False)
        if len(serialized.encode("utf-8")) > MAX_JSON_BYTES:
            raise RebuildError("rollback manifest exceeds the input limit")
        checked = json.loads(serialized)
        digest = checked.get("manifest_sha256")
        if _seal(checked)["manifest_sha256"] != digest:
            raise RebuildError("manifest SHA256 mismatch")
        if (checked["schema_version"] != 1 or checked["kind"] != MANIFEST_KIND
                or checked["input_kind"] != input_kind or checked["operation"] not in ("rebuild", "rollback")):
            raise RebuildError("unsupported manifest kind, operation, or schema")
        if (checked["source_sha256"] != checked["source"]["sha256"]
                or checked["result_sha256"] != checked["output"]["sha256"]):
            raise RebuildError("manifest source/result hash fields disagree")
        _source_check(raw, checked["result_sha256"])
        actual_report = (package.inspect_package(raw) if input_kind == "package"
                         else package.inspect_application(raw))
        if _snapshot(actual_report) != checked["output"]:
            raise RebuildError("manifest output metadata does not match the supplied image")
        patches = checked["patches"]
        if not isinstance(patches, list) or len(patches) > MAX_PATCHES:
            raise RebuildError("manifest patches are invalid or exceed the patch limit")
        reverse = [{"offset": patch["offset"], "expected_hex": patch["replacement_hex"],
                    "replacement_hex": patch["expected_hex"], "label": patch["label"]}
                   for patch in patches]
        function = rebuild_package if input_kind == "package" else rebuild_application
        result, reverse_manifest = function(raw, reverse, expected_source_sha256=checked["result_sha256"])
        if (_hash(result) != checked["source_sha256"]
                or reverse_manifest["output"] != checked["source"]):
            raise RebuildError("rollback did not restore the exact original source")
        reverse_manifest["operation"] = "rollback"
        reverse_manifest["reverses_manifest_sha256"] = digest
        reverse_manifest["verification"]["original_source_restored"] = True
        return result, _seal(reverse_manifest)
    except (KeyError, TypeError, OverflowError, RecursionError) as error:
        raise RebuildError("malformed rollback manifest") from error


def rollback_package(raw: bytes, manifest: dict) -> tuple[bytes, dict]:
    """Restore the exact source FWSC identified by a rebuild manifest."""
    return _rollback(raw, manifest, "package")


def rollback_application(raw: bytes, manifest: dict) -> tuple[bytes, dict]:
    """Restore the exact source application identified by a rebuild manifest."""
    return _rollback(raw, manifest, "application")


def _read_json(path: Path) -> object:
    with path.open("rb") as source:
        raw = source.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise RebuildError("JSON file exceeds the input limit")
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise RebuildError(f"JSON object repeats key {key!r}")
            result[key] = value
        return result
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_keys)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("rebuild", "rollback"))
    parser.add_argument("kind", choices=("package", "app"))
    parser.add_argument("input", type=Path)
    parser.add_argument("changes", type=Path, help="patch request JSON or rollback manifest JSON")
    parser.add_argument("--output", type=Path, help="explicit firmware output inside ignored scratch/ or reference/")
    parser.add_argument("--manifest-out", type=Path, help="explicit manifest output inside ignored scratch/ or reference/")
    args = parser.parse_args(argv)
    try:
        # A written firmware artifact always travels with its rollback manifest.
        if bool(args.output) != bool(args.manifest_out):
            raise RebuildError("--output and --manifest-out must be supplied together")
        output_path = package._output_path(args.output) if args.output else None
        manifest_path = package._output_path(args.manifest_out) if args.manifest_out else None
        if output_path and output_path == manifest_path:
            raise RebuildError("firmware and manifest output paths must differ")
        raw = package._read_bounded(args.input)
        changes = _read_json(args.changes)
        if args.operation == "rebuild":
            if not isinstance(changes, dict) or set(changes) != {"expected_source_sha256", "patches"}:
                raise RebuildError("patch request must contain exactly expected_source_sha256 and patches")
            function = rebuild_package if args.kind == "package" else rebuild_application
            result, manifest = function(raw, changes["patches"], expected_source_sha256=changes["expected_source_sha256"])
        else:
            function = rollback_package if args.kind == "package" else rollback_application
            result, manifest = function(raw, changes)
        serialized = json.dumps(manifest, indent=2) + "\n"
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            # Save the recovery description first; never overwrite existing evidence.
            with manifest_path.open("x", encoding="utf-8") as destination:
                destination.write(serialized)
            with output_path.open("xb") as destination:
                destination.write(result)
        print(serialized, end="")
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(2, f"rebuild failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
