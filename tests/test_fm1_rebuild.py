"""Rebuild/rollback contracts using independently assembled synthetic packages."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import fm1_package as package
import fm1_rebuild as rebuild

spec = importlib.util.spec_from_file_location("rebuild_fixtures", Path(__file__).with_name("test_fm1_package.py"))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def change(offset=0, expected=b"synthetic", replacement=b"SYNTHETIC", label="Capitalization probe"):
    return {"offset": offset, "expected_hex": expected.hex(), "replacement_hex": replacement.hex(), "label": label}


def build(raw, patches, kind="package"):
    function = rebuild.rebuild_package if kind == "package" else rebuild.rebuild_application
    return function(raw, patches, expected_source_sha256=digest(raw))


def test_public_inspect_and_extract_has_same_checked_report():
    raw = fixture.synthetic_package()
    report, app = package.inspect_and_extract(raw)
    assert report == package.inspect_package(raw)
    assert app == fixture.app_image()


def test_no_op_repack_is_byte_identical_through_all_integrity_layers():
    raw = fixture.synthetic_package()
    result, manifest = build(raw, [])
    assert result == raw
    assert manifest["verification"]["no_op"] is True
    assert manifest["source_sha256"] == manifest["result_sha256"] == digest(raw)
    assert len(manifest["updated_integrity"]) == 7
    assert all(item["before"] == item["after"] for item in manifest["updated_integrity"])
    restored, reverse = rebuild.rollback_package(result, manifest)
    assert restored == raw and reverse["verification"]["original_source_restored"] is True


def test_patch_repack_and_rollback_are_byte_exact():
    raw = fixture.synthetic_package()
    result, manifest = build(raw, [change()])
    before_report, before_app = package.inspect_and_extract(raw)
    after_report, after_app = package.inspect_and_extract(result)
    assert result != raw and len(result) == len(raw)
    assert after_app == b"SYNTHETIC" + before_app[9:]
    assert after_report["identity"] == before_report["identity"]
    assert manifest["source_sha256"] == digest(raw)
    assert manifest["result_sha256"] == digest(result)
    assert manifest["verification"]["changed_application_bytes"] == 9
    assert manifest["verification"]["non_application_payloads_preserved"] is True
    assert manifest["verification"]["unrelated_bytes_preserved"] is True
    assert manifest["verification"]["bootability_verified"] is False
    restored, reverse = rebuild.rollback_package(result, json.loads(json.dumps(manifest)))
    assert restored == raw
    assert reverse["source_sha256"] == digest(result) and reverse["result_sha256"] == digest(raw)
    assert reverse["operation"] == "rollback"
    redone, _ = rebuild.rollback_package(restored, reverse)
    assert redone == result


def test_only_exact_patch_and_dependent_crc_bytes_can_change():
    raw = fixture.synthetic_package()
    result, manifest = build(raw, [change()])
    source, _ = package.inspect_and_extract(raw)
    logical_before = fixture.logical_image(raw)
    logical_after = fixture.logical_image(result)
    flash = next(entry for entry in source["entries"] if entry["name"] == "flash.bin")
    app_start = flash["offset"] + source["application"]["extraction"]["flash_data_offset"]
    allowed = set(range(app_start, app_start + 9))
    for field in manifest["updated_integrity"]:
        allowed.update(range(field["logical_field_offset"], field["logical_field_offset"] + 2))
    changed = {index for index, (left, right) in enumerate(zip(logical_before, logical_after)) if left != right}
    assert changed <= allowed
    assert changed & set(range(app_start, app_start + 9)) == set(range(app_start, app_start + 9))
    assert all(raw[i * 48 + 47] == result[i * 48 + 47] for i in range(20))
    before_entries = package.inspect_package(raw)["entries"]
    after_entries = package.inspect_package(result)["entries"]
    assert [entry for entry in before_entries if entry["name"] != "flash.bin"] == [
        entry for entry in after_entries if entry["name"] != "flash.bin"]


def test_nonstandard_padding_is_preserved_and_no_op_still_exact():
    raw = bytearray(fixture.synthetic_package())
    logical = fixture.logical_image(raw)
    # Header padding and encrypted-entry allocation padding are not reconstructed.
    logical[800:810] = bytes(range(10))
    script = package.inspect_package(bytes(raw))["entries"][2]
    padding_start = script["offset"] + script["size"]
    logical[padding_start:padding_start + 3] = b"PAD"
    raw = fixture.reinterleave(logical)
    assert build(raw, [])[0] == raw
    result, manifest = build(raw, [change()])
    restored, _ = rebuild.rollback_package(result, manifest)
    assert restored == raw
    assert fixture.logical_image(result)[800:810] == bytes(range(10))
    assert fixture.logical_image(result)[padding_start:padding_start + 3] == b"PAD"


def test_standalone_application_patch_rollback_and_no_op():
    raw = fixture.app_image()
    assert build(raw, [], kind="app")[0] == raw
    result, manifest = build(raw, [change()], kind="app")
    assert manifest["input_kind"] == "application" and manifest["updated_integrity"] == []
    assert manifest["source"]["package_identity"] is None
    assert result == b"SYNTHETIC" + raw[9:]
    assert rebuild.rollback_application(result, manifest)[0] == raw


@pytest.mark.parametrize("value", [None, "", "0" * 63, "g" * 64, "0" * 64])
def test_requires_exact_valid_source_hash(value):
    with pytest.raises(rebuild.RebuildError, match="SHA256|expected_source"):
        rebuild.rebuild_package(fixture.synthetic_package(), [], expected_source_sha256=value)


def test_uppercase_source_hash_is_accepted_and_normalized():
    raw = fixture.synthetic_package()
    _, manifest = rebuild.rebuild_package(raw, [], expected_source_sha256=digest(raw).upper())
    assert manifest["source_sha256"] == digest(raw)


@pytest.mark.parametrize("patches,reason", [
    ([change(expected=b"mismatch!")], "expected bytes"),
    ([change(replacement=b"short")], "same byte length"),
    ([change(expected=b"", replacement=b"")], "nonempty"),
    ([change(offset=-1)], "nonnegative integer"),
    ([change(offset=True)], "nonnegative integer"),
    ([change(offset=0.0)], "nonnegative integer"),
    ([change(offset=2**63)], "outside"),
    ([{"offset": 0, "expected_hex": "zz", "replacement_hex": "00"}], "hexadecimal"),
    ([{"offset": 0, "expected_hex": "73", "replacement_hex": "53", "typo": 1}], "unknown fields"),
    ([{"offset": 0}], "hexadecimal"),
    ([change(label="line\nbreak")], "single-line"),
    ([change(label="x" * 161)], "160"),
    (None, "list"),
    ([None], "not an object"),
])
def test_rejects_malformed_or_wrong_patches(patches, reason):
    raw = fixture.app_image()
    with pytest.raises(rebuild.RebuildError, match=reason):
        build(raw, patches, kind="app")


def test_overlapping_ranges_are_rejected_even_when_before_bytes_match():
    raw = fixture.app_image()
    patches = [change(), change(offset=1, expected=b"ynthetic", replacement=b"YNTHETIC")]
    with pytest.raises(rebuild.RebuildError, match="overlap"):
        build(raw, patches, kind="app")


def test_unsorted_disjoint_patches_are_normalized_and_reversible():
    raw = fixture.app_image()
    patches = [change(offset=5, expected=b"etic", replacement=b"ETIC"),
               change(offset=0, expected=b"synth", replacement=b"SYNTH")]
    result, manifest = build(raw, patches, kind="app")
    assert [patch["offset"] for patch in manifest["patches"]] == [0, 5]
    assert result == b"SYNTHETIC" + raw[9:]
    assert rebuild.rollback_application(result, manifest)[0] == raw


def test_patch_limits_are_enforced_before_allocating_large_output(monkeypatch):
    raw = fixture.app_image()
    monkeypatch.setattr(rebuild, "MAX_PATCHES", 1)
    with pytest.raises(rebuild.RebuildError, match="at most 1"):
        build(raw, [change(), change()], kind="app")
    monkeypatch.setattr(rebuild, "MAX_PATCH_BYTES", 5)
    with pytest.raises(rebuild.RebuildError, match="bounded|total limit"):
        build(raw, [change()], kind="app")


@pytest.mark.parametrize("before,after", [(b"015", b"014"), (b"FM-1", b"XX-1")])
def test_identity_edits_are_rejected_without_version_guessing(before, after):
    raw = fixture.app_image()
    patch = change(offset=raw.index(before), expected=before, replacement=after)
    with pytest.raises(rebuild.RebuildError, match="version identity"):
        build(raw, [patch], kind="app")


def test_creating_new_identity_occurrence_is_rejected():
    raw = b"neutral-abcdefgh"
    with pytest.raises(rebuild.RebuildError, match="version identity"):
        build(raw, [change(offset=8, expected=b"abcdefgh", replacement=b"FM-1_015")], kind="app")


def test_rollback_rejects_another_image_or_another_manifest_kind():
    raw = fixture.synthetic_package()
    result, manifest = build(raw, [change()])
    with pytest.raises(rebuild.RebuildError, match="source SHA256"):
        rebuild.rollback_package(raw, manifest)
    with pytest.raises(rebuild.RebuildError, match="unsupported manifest"):
        rebuild.rollback_application(result, manifest)


def test_rollback_rejects_changed_manifest_bytes():
    result, manifest = build(fixture.synthetic_package(), [change()])
    damaged = copy.deepcopy(manifest)
    damaged["patches"][0]["replacement_hex"] = "00" * 9
    with pytest.raises(rebuild.RebuildError, match="manifest SHA256"):
        rebuild.rollback_package(result, damaged)


def test_even_resealed_manifest_must_restore_exact_original_source():
    result, manifest = build(fixture.app_image(), [change()], kind="app")
    manifest["patches"][0]["expected_hex"] = b"different".hex()
    rebuild._seal(manifest)
    with pytest.raises(rebuild.RebuildError, match="exact original source"):
        rebuild.rollback_application(result, manifest)


@pytest.mark.parametrize("manifest", [None, {}, {"schema_version": 1}, {"loop": float("nan")}])
def test_malformed_manifest_fails_without_output(manifest):
    with pytest.raises(ValueError):
        rebuild.rollback_application(fixture.app_image(), manifest)


def test_cli_preview_creates_no_files(tmp_path, capsys):
    source = tmp_path / "input.fwsc"
    request = tmp_path / "patches.json"
    raw = fixture.synthetic_package()
    source.write_bytes(raw)
    request.write_text(json.dumps({"expected_source_sha256": digest(raw), "patches": [change()]}))
    assert rebuild.main(["rebuild", "package", str(source), str(request)]) == 0
    manifest = json.loads(capsys.readouterr().out)
    assert manifest["source_sha256"] == digest(raw)
    assert set(tmp_path.iterdir()) == {source, request}
    assert source.read_bytes() == raw


def test_cli_outputs_must_be_paired_and_cannot_overwrite_input(tmp_path):
    source = tmp_path / "input.fwsc"
    request = tmp_path / "patches.json"
    raw = fixture.synthetic_package()
    source.write_bytes(raw)
    request.write_text(json.dumps({"expected_source_sha256": digest(raw), "patches": []}))
    with pytest.raises(SystemExit):
        rebuild.main(["rebuild", "package", str(source), str(request), "--output", str(source)])
    with pytest.raises(SystemExit):
        rebuild.main(["rebuild", "package", str(source), str(request), "--output", str(source),
                      "--manifest-out", str(tmp_path / "new.json")])
    assert source.read_bytes() == raw


def test_cli_same_outputs_rejected_and_rollback_preview_works(tmp_path, monkeypatch, capsys):
    raw = fixture.app_image()
    result, manifest = build(raw, [change()], kind="app")
    source, request = tmp_path / "modified.bin", tmp_path / "manifest.json"
    source.write_bytes(result)
    request.write_text(json.dumps(manifest))
    assert rebuild.main(["rollback", "app", str(source), str(request)]) == 0
    assert json.loads(capsys.readouterr().out)["result_sha256"] == digest(raw)
    monkeypatch.setattr(package, "_output_path", lambda path: path)
    output = tmp_path / "same-output"
    with pytest.raises(SystemExit):
        rebuild.main(["rollback", "app", str(source), str(request), "--output", str(output),
                      "--manifest-out", str(output)])
    assert not output.exists()


def test_corrupt_package_with_matching_source_hash_is_still_rejected():
    raw = bytearray(fixture.synthetic_package())
    raw[1100] ^= 1
    with pytest.raises(package.PackageError, match="CRC"):
        build(bytes(raw), [])


def test_cli_writes_reversible_pair_and_preserves_existing_evidence(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(package, "__file__", str(tmp_path / "tools" / "fm1_package.py"))
    raw = fixture.synthetic_package()
    source, request = tmp_path / "input.fwsc", tmp_path / "request.json"
    source.write_bytes(raw)
    request.write_text(json.dumps({"expected_source_sha256": digest(raw), "patches": [change()]}),
                       encoding="utf-8-sig")  # Windows PowerShell's UTF8 files may carry a BOM.
    output, manifest_path = tmp_path / "scratch" / "result.fwsc", tmp_path / "scratch" / "manifest.json"
    command = ["rebuild", "package", str(source), str(request), "--output", str(output),
               "--manifest-out", str(manifest_path)]
    assert rebuild.main(command) == 0
    capsys.readouterr()
    manifest = json.loads(manifest_path.read_text())
    assert digest(output.read_bytes()) == manifest["result_sha256"]
    assert rebuild.rollback_package(output.read_bytes(), manifest)[0] == raw
    original_output = output.read_bytes()
    original_manifest = manifest_path.read_bytes()
    with pytest.raises(SystemExit):
        rebuild.main(command)
    assert source.read_bytes() == raw
    assert output.read_bytes() == original_output
    assert manifest_path.read_bytes() == original_manifest


def test_duplicate_json_keys_are_rejected(tmp_path):
    request = tmp_path / "request.json"
    request.write_text('{"patches": [], "patches": []}')
    with pytest.raises(rebuild.RebuildError, match="repeats key"):
        rebuild._read_json(request)
