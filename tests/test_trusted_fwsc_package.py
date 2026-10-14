"""Strict offline composition checks for a trusted expanded-D7000 build tuple."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "jieli"))
import trusted_fwsc_package as packager  # noqa: E402
import model_092_app_replacement as model  # noqa: E402

TUPLE_SHA = "2005957ad3dfbb5e34030717c6f0045cb3c96265a24641b8c370f1c39d835a23"
BUILD_ROOT = Path("/home/claude/mvave-fm1/combined-nor-target-20261014/out/companion-set")
TASK_ROOT = BUILD_ROOT.parents[1]
CATALOGUE_ROOT = Path("/home/claude/mvave-fm1/nor-watchdog-target-closure-20261014/catalogue-fresh")
SOURCE_CANDIDATES = (
    ROOT / "scratch/092-package-model/FM-1_092.fwsc",
    Path("/home/claude/.local/share/codex-worktrees/092-package-model/scratch/092-package-model/FM-1_092.fwsc"),
)
REFERENCE_CANDIDATES = (
    Path("/home/claude/mvave-fm1/sdk-raw-final-20261011/private/FM-1_092.fwsc_unpack"),
    Path("/home/claude/mvave-fm1/native-ota-candidate-16-20261012/source/inputs/stock"),
    ROOT / "scratch/092-package-model/FM-1_092.fwsc_unpack",
    Path("/home/claude/.local/share/codex-worktrees/092-package-model/scratch/092-package-model/FM-1_092.fwsc_unpack"),
)


def _retained(path_candidates):
    return next((p for p in path_candidates if p.exists()), None)


def _inputs():
    source = _retained(SOURCE_CANDIDATES)
    reference = _retained(REFERENCE_CANDIDATES)
    manifest_path = TASK_ROOT / "companion-set-catalogue-manifest.json"
    required = [
        BUILD_ROOT / "build_tuple.json",
        BUILD_ROOT / "build-provenance.json",
        BUILD_ROOT / "selection/request.json",
        BUILD_ROOT / "selection/prepared/profile.json",
        BUILD_ROOT / "selection/staged/profile.json",
        BUILD_ROOT / "link/artifact/app.bin",
        BUILD_ROOT / "link/lunar-app-probe.elf",
        BUILD_ROOT / "link/artifact/artifact.json",
        BUILD_ROOT / "link/verification.json",
        BUILD_ROOT / "image.json",
        manifest_path,
    ]
    if source is None or reference is None or any(not path.is_file() for path in required):
        pytest.skip("retained D7000 package artifacts are unavailable on this host")

    tuple_raw = (BUILD_ROOT / "build_tuple.json").read_bytes()
    provenance_raw = (BUILD_ROOT / "build-provenance.json").read_bytes()
    provenance = json.loads(provenance_raw)
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw)
    catalogue_paths = [
        CATALOGUE_ROOT / row["path"].removeprefix("/catalogue/")
        for row in manifest["objects"]
    ]
    generated_paths = [
        BUILD_ROOT / row["path"]
        for row in provenance["module_and_generated_inputs"]
    ]
    if any(not path.is_file() for path in catalogue_paths + generated_paths):
        pytest.skip("retained D7000 catalogue/generated inputs are incomplete")
    catalogue_files = {
        row["path"]: path.read_bytes()
        for row, path in zip(manifest["objects"], catalogue_paths)
    }
    generated_files = {
        row["path"]: path.read_bytes()
        for row, path in zip(provenance["module_and_generated_inputs"], generated_paths)
    }
    return {
        "source_fwsc": source.read_bytes(),
        "reference_dir": reference,
        "app": (BUILD_ROOT / "link/artifact/app.bin").read_bytes(),
        "elf": (BUILD_ROOT / "link/lunar-app-probe.elf").read_bytes(),
        "artifact_receipt": (BUILD_ROOT / "link/artifact/artifact.json").read_bytes(),
        "build_receipt": (BUILD_ROOT / "link/verification.json").read_bytes(),
        "build_provenance": provenance_raw,
        "request": (BUILD_ROOT / "selection/request.json").read_bytes(),
        "prepared_profile": (BUILD_ROOT / "selection/prepared/profile.json").read_bytes(),
        "source_profile": (BUILD_ROOT / "selection/staged/profile.json").read_bytes(),
        "catalogue_manifest": manifest_raw,
        "image_receipt": (BUILD_ROOT / "image.json").read_bytes(),
        "catalogue_files": catalogue_files,
        "generated_files": generated_files,
        "build_tuple": tuple_raw,
        "expected_tuple_sha256": TUPLE_SHA,
    }


def test_real_d7000_tuple_composes_and_reopens_with_independent_integrity_checks():
    values = _inputs()
    package, report = packager.package_bytes(**values)
    assert report["app_sha256"] == "ba46bf0a4d1bda4d604223c658b141b4a9068e37f65afddd998af04d5296cfc8"
    assert report["app_bytes"] == 845732
    assert report["package_identity"] == "FM-1_990"
    assert report["recovery_identity"] == "FM-1_000"
    assert report["outer_integrity"] == {
        "header_crc_verified": True,
        "entry_list_crc_verified": True,
        "all_payload_crcs_verified": True,
    }
    assert report["nested_boundaries"]["slack_to_stage"] == 13948
    assert report["package_returned_in_memory"] is True
    assert report["file_written"] is False
    assert report["hardware_admitted"] is report["hardware_tested"] is report["installable"] is False
    assert packager.sha256(package) == report["package_sha256"]


def test_tuple_requires_external_digest_and_false_admission_flags():
    synthetic = {
        "schema": 1,
        "tuple_id": "synthetic-test-only",
        "profile_id": packager.PROFILE_ID,
        "flash_layout": "expanded-d7000",
        "app_bytes": 100,
        "application_identity": "FM-1_990",
        "recovery_identity": "FM-1_000",
        "runtime_mode": "song-diagnostic",
        "hardware_admitted": False,
        "hardware_tested": False,
        "installable": False,
    }
    synthetic.update({field: "0" * 64 for field in packager.HASH_FIELDS})
    raw = packager.canonical_json(synthetic)
    digest = packager.sha256(raw)
    with pytest.raises(ValueError, match="external trust anchor"):
        packager._validate_tuple(raw, "f" * 64)
    with pytest.raises(ValueError, match="fields differ"):
        packager._validate_tuple(packager.canonical_json({}), packager.sha256(packager.canonical_json({})))
    assert packager._validate_tuple(raw, digest)["tuple_id"] == "synthetic-test-only"

    synthetic["installable"] = True
    altered = packager.canonical_json(synthetic)
    with pytest.raises(ValueError, match="flags false"):
        packager._validate_tuple(altered, packager.sha256(altered))


def test_catalogue_must_match_receipt_and_exact_bytes():
    values = _inputs()
    tuple_data = packager._validate_tuple(values["build_tuple"], TUPLE_SHA)
    verification = json.loads(values["build_receipt"])
    original = values["catalogue_files"]
    missing = dict(original)
    missing.pop(next(iter(missing)))
    with pytest.raises(ValueError, match="exactly all manifest"):
        packager._validate_catalogue(values["catalogue_manifest"], tuple_data["catalogue_sha256"], verification, missing)
    changed = dict(original)
    first = next(iter(changed))
    changed[first] += b"x"
    with pytest.raises(ValueError, match="bytes differ"):
        packager._validate_catalogue(values["catalogue_manifest"], tuple_data["catalogue_sha256"], verification, changed)
    bad_path = json.loads(values["catalogue_manifest"])
    bad_path["objects"][0]["path"] = "/catalogue/../escape"
    raw_bad = packager.canonical_json(bad_path)
    with pytest.raises(ValueError, match="namespace"):
        packager._validate_catalogue(raw_bad, packager.sha256(raw_bad), verification, original)


def test_provenance_files_and_receipt_mutations_refuse():
    values = _inputs()
    tuple_data = packager._validate_tuple(values["build_tuple"], TUPLE_SHA)
    provenance = json.loads(values["build_provenance"])
    files = values["generated_files"]
    bad_files = dict(files)
    path = next(iter(bad_files))
    bad_files[path] += b"!"
    with pytest.raises(ValueError, match="differ from build provenance"):
        packager._validate_provenance_rows(provenance, "module_and_generated_inputs", bad_files)

    changed_image = json.loads(values["image_receipt"])
    changed_image["installable"] = True
    values["image_receipt"] = json.dumps(changed_image, sort_keys=True).encode()
    with pytest.raises(ValueError, match="image receipt must keep"):
        packager._validate_receipts(
            tuple_data, values["app"], values["elf"], values["artifact_receipt"],
            values["build_receipt"], values["build_provenance"], values["request"],
            values["prepared_profile"], values["source_profile"], values["catalogue_manifest"],
            values["image_receipt"], values["catalogue_files"], values["generated_files"])


def test_source_profile_and_image_receipt_crosslinks_are_exact():
    values = _inputs()
    tuple_data = packager._validate_tuple(values["build_tuple"], TUPLE_SHA)
    altered_source = values["source_profile"] + b" "
    with pytest.raises(ValueError, match="exact source profile bytes"):
        packager._validate_receipts(
            tuple_data, values["app"], values["elf"], values["artifact_receipt"],
            values["build_receipt"], values["build_provenance"], values["request"],
            values["prepared_profile"], altered_source, values["catalogue_manifest"],
            values["image_receipt"], values["catalogue_files"], values["generated_files"])

    for field, value in (("verification_sha256", "0" * 64), ("app_bytes", 1)):
        image = json.loads(values["image_receipt"])
        image[field] = value
        with pytest.raises(ValueError, match="image receipt"):
            packager._validate_receipts(
                tuple_data, values["app"], values["elf"], values["artifact_receipt"],
                values["build_receipt"], values["build_provenance"], values["request"],
                values["prepared_profile"], values["source_profile"], values["catalogue_manifest"],
                json.dumps(image).encode(), values["catalogue_files"], values["generated_files"])

    image = json.loads(values["image_receipt"])
    image["firmware_identity"]["application_identity"] = "FM-1_001"
    with pytest.raises(ValueError, match="image receipt firmware identity"):
        packager._validate_receipts(
            tuple_data, values["app"], values["elf"], values["artifact_receipt"],
            values["build_receipt"], values["build_provenance"], values["request"],
            values["prepared_profile"], values["source_profile"], values["catalogue_manifest"],
            json.dumps(image).encode(), values["catalogue_files"], values["generated_files"])


def test_public_model_still_rejects_non_pinned_default_app():
    source = _retained(SOURCE_CANDIDATES)
    reference = _retained(REFERENCE_CANDIDATES)
    if not source or not reference:
        pytest.skip("retained public FM-1_092 source/reference fixture is unavailable")
    changed = bytearray(b"x" * 128)
    with pytest.raises(ValueError, match="pinned Shapes8/Event-Horizon"):
        model._build(source.read_bytes(), reference, bytes(changed))


def test_private_artifact_loader_skips_cleanly_when_inputs_are_absent(monkeypatch, tmp_path):
    missing = tmp_path / "not-retained"
    monkeypatch.setattr(sys.modules[__name__], "BUILD_ROOT", missing / "build")
    monkeypatch.setattr(sys.modules[__name__], "TASK_ROOT", missing / "task")
    monkeypatch.setattr(sys.modules[__name__], "CATALOGUE_ROOT", missing / "catalogue")
    monkeypatch.setattr(sys.modules[__name__], "SOURCE_CANDIDATES", (missing / "source.fwsc",))
    monkeypatch.setattr(sys.modules[__name__], "REFERENCE_CANDIDATES", (missing / "reference",))
    with pytest.raises(pytest.skip.Exception, match="artifacts are unavailable"):
        _inputs()
