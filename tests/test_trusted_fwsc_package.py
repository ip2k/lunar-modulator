"""Strict offline composition checks for a trusted expanded-D7000 build tuple."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "jieli"))
import trusted_fwsc_package as packager  # noqa: E402
import model_092_app_replacement as model  # noqa: E402

TUPLE_SHA = "247c8ded29a33a014cec82f7dafc548e718ad9d576107e3f3453388c4c9cd19a"
LEGACY_TUPLE_SHA = "9c246fb70bfb04cb6a6adbaf845fe71a882ba0228317b286f648b502b2e66ec4"
BUILD_ROOT = Path("/home/claude/.local/share/codex-private/continuous-tuple-20261014/run-298ff12/build-output/build")
TASK_ROOT = BUILD_ROOT
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
    manifest_path = TASK_ROOT / "catalogue-manifest.json"
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
        pytest.skip("retained continuous D7000 package artifacts are unavailable on this host")

    legacy_tuple_raw = (BUILD_ROOT / "build_tuple.json").read_bytes()
    legacy_tuple = json.loads(legacy_tuple_raw)
    assert packager.sha256(legacy_tuple_raw) == LEGACY_TUPLE_SHA
    with pytest.raises(ValueError, match="schema/profile"):
        packager._validate_tuple(legacy_tuple_raw, LEGACY_TUPLE_SHA)
    assert legacy_tuple["schema"] == 1  # retained artifact predates schema 2
    # Exercise current schema-2 envelope policy over immutable retained build
    # inputs; never rewrite the private historical tuple on disk.
    legacy_tuple["schema"] = 2
    tuple_raw = packager.canonical_json(legacy_tuple)
    assert packager.sha256(tuple_raw) == TUPLE_SHA
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
        pytest.skip("retained continuous D7000 catalogue/generated inputs are incomplete")
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


def test_real_continuous_d7000_tuple_composes_in_memory_with_independent_integrity_checks():
    values = _inputs()
    package, report = packager.package_bytes(**values)
    assert report["app_sha256"] == "0a7a2fecbd730586b8792e7da6c9a6cf35fa26ae4fb77798b93b5f30e9922f02"
    assert report["app_bytes"] == 845716
    assert report["package_identity"] == "FM-1_500"
    assert report["recovery_identity"] == "FM-1_000"
    assert report["outer_integrity"] == {
        "header_crc_verified": True,
        "entry_list_crc_verified": True,
        "all_payload_crcs_verified": True,
    }
    assert report["nested_boundaries"]["slack_to_stage"] == 13964
    assert report["package_returned_in_memory"] is True
    assert report["file_written"] is False
    assert report["hardware_admitted"] is report["hardware_tested"] is report["installable"] is False
    assert packager.sha256(package) == report["package_sha256"]


def test_tuple_requires_external_digest_and_false_admission_flags():
    synthetic = {
        "schema": 2,
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
    for wrong_schema in (1, True, 1.0, "2", None):
        malformed = packager.canonical_json(dict(synthetic, schema=wrong_schema))
        with pytest.raises(ValueError, match="schema/profile"):
            packager._validate_tuple(malformed, packager.sha256(malformed))

    missing_tree = dict(synthetic)
    del missing_tree["toolchain_tree_sha256"]
    missing_tree_raw = packager.canonical_json(missing_tree)
    with pytest.raises(ValueError, match="fields differ.*toolchain_tree_sha256"):
        packager._validate_tuple(missing_tree_raw, packager.sha256(missing_tree_raw))
    invalid_tree = dict(synthetic, toolchain_tree_sha256="g" * 64)
    invalid_tree_raw = packager.canonical_json(invalid_tree)
    with pytest.raises(ValueError, match="toolchain_tree_sha256.*lowercase SHA-256"):
        packager._validate_tuple(invalid_tree_raw, packager.sha256(invalid_tree_raw))

    continuous = dict(synthetic, runtime_mode="continuous", application_identity="FM-1_500")
    continuous_raw = packager.canonical_json(continuous)
    assert packager._validate_tuple(continuous_raw, packager.sha256(continuous_raw))["runtime_mode"] == "continuous"
    for changes in ({"application_identity": "FM-1_990"}, {"recovery_identity": "FM-1_001"}):
        altered = packager.canonical_json(dict(continuous, **changes))
        with pytest.raises(ValueError, match="explicit Lunar identity"):
            packager._validate_tuple(altered, packager.sha256(altered))

    synthetic["installable"] = True
    altered = packager.canonical_json(synthetic)
    with pytest.raises(ValueError, match="flags false"):
        packager._validate_tuple(altered, packager.sha256(altered))


def test_continuous_runtime_requires_compiled_timer_policy_and_keeps_release_false():
    valid = {
        "runtime_configuration": {
            "runtime_mode": "continuous", "return_to_rom_seconds": None,
            "define": "-DLUNAR_RETURN_TO_ROM_SECONDS=0", "release_accepted": False,
        },
        "probe_return_to_rom_seconds": None,
        "runtime_policy_sha256": packager.RUNTIME_POLICY_SHA256,
    }
    runtime, seconds = packager._validate_runtime(valid, "continuous")
    assert runtime == valid["runtime_configuration"] and seconds is None
    for changes in (
            {"return_to_rom_seconds": 120}, {"return_to_rom_seconds": 0},
            {"define": "-DLUNAR_RETURN_TO_ROM_SECONDS=120"},
            {"release_accepted": True}, {"release_accepted": 0},
            {"runtime_mode": "song-diagnostic"}, {"unrecognized": False}):
        bad = dict(valid, runtime_configuration=dict(runtime, **changes))
        with pytest.raises(ValueError):
            packager._validate_runtime(bad, "continuous")
    for changes in ({"probe_return_to_rom_seconds": 120}, {"runtime_policy_sha256": "0" * 64}):
        with pytest.raises(ValueError, match="exact continuous runtime policy"):
            packager._validate_runtime(dict(valid, **changes), "continuous")
    missing_timer = dict(valid)
    del missing_timer["probe_return_to_rom_seconds"]
    with pytest.raises(ValueError, match="exact continuous runtime policy"):
        packager._validate_runtime(missing_timer, "continuous")
    diagnostic = {"runtime_configuration": {
        "runtime_mode": "song-diagnostic", "return_to_rom_seconds": 120,
        "release_accepted": False,
    }}
    assert packager._validate_runtime(diagnostic, "song-diagnostic")[1] == 120
    with pytest.raises(ValueError):
        packager._validate_runtime(diagnostic, "continuous")


@pytest.mark.parametrize("schema", [True, 1.0, "1", None])
def test_catalogue_rejects_noninteger_schema_with_matching_digest(schema):
    raw = packager.canonical_json({"schema": schema, "objects": []})
    with pytest.raises(ValueError, match="schema or objects"):
        packager._validate_catalogue(raw, packager.sha256(raw), {"catalogue_objects": []}, {})


@pytest.mark.parametrize("field,key,digest_field,error", [
    ("build_provenance", "schema", "build_provenance_sha256", "provenance schema"),
    ("request", "version", "request_sha256", "request schema"),
])
@pytest.mark.parametrize("value", [True, 1.0, "1", None])
def test_package_rejects_noninteger_schema_even_with_rebound_digests(field, key, digest_field, error, value):
    values = _inputs()
    document = json.loads(values[field])
    document[key] = value
    values[field] = packager.canonical_json(document)
    tuple_data = json.loads(values["build_tuple"])
    tuple_data[digest_field] = packager.sha256(values[field])
    # For request mutations, keep all earlier hash crosslinks consistent so the
    # numeric schema check, rather than a stale receipt digest, rejects it.
    if field == "request":
        provenance = json.loads(values["build_provenance"])
        provenance.update(request_sha256=tuple_data[digest_field],
                          request_receipt_sha256=tuple_data[digest_field])
        values["build_provenance"] = packager.canonical_json(provenance)
        tuple_data["build_provenance_sha256"] = packager.sha256(values["build_provenance"])
        image = json.loads(values["image_receipt"])
        image["request_sha256"] = tuple_data[digest_field]
        values["image_receipt"] = packager.canonical_json(image)
    with pytest.raises(ValueError, match=error):
        packager._validate_receipts(
            tuple_data, values["app"], values["elf"], values["artifact_receipt"],
            values["build_receipt"], values["build_provenance"], values["request"],
            values["prepared_profile"], values["source_profile"], values["catalogue_manifest"],
            values["image_receipt"], values["catalogue_files"], values["generated_files"])


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


def test_catalogue_schema2_binds_per_object_optimization_and_exact_bytes():
    payload = b"catalogue object"
    path = "/catalogue/our/src/fx_hall.o"
    overrides = {"our/src/fx_hall.o": "-O2"}
    row = {"path": path, "sha256": packager.sha256(payload), "optimization": "-O2"}
    raw = packager.canonical_json({"schema": 2, "objects": [row]})
    verification = {"catalogue_objects": [row], "catalogue_optimization_overrides": overrides,
                    "catalogue_limiter_os": False, "catalogue_hall_o2": True}
    manifest = packager._validate_catalogue(raw, packager.sha256(raw), verification, {path: payload})
    assert manifest["objects"] == [row]

    bad_manifest_rows = [
        dict(row, optimization="-Os"),
        {"path": path, "sha256": row["sha256"]},
        dict(row, optimization="-O3"),
        dict(row, optimization="-Oz", ignored=True),
    ]
    for bad_row in bad_manifest_rows:
        bad_raw = packager.canonical_json({"schema": 2, "objects": [bad_row]})
        with pytest.raises(ValueError):
            packager._validate_catalogue(bad_raw, packager.sha256(bad_raw), verification,
                                         {path: payload})

    invalid_receipts = [
        {"catalogue_objects": [{key: value for key, value in row.items() if key != "optimization"}],
         "catalogue_optimization_overrides": overrides},
        {"catalogue_objects": [dict(row, optimization="-Os")],
         "catalogue_optimization_overrides": overrides},
        {"catalogue_objects": [row], "catalogue_optimization_overrides": {"other.o": "-O2"}},
        {"catalogue_objects": [row], "catalogue_optimization_overrides": {"our/src/fx_hall.o": "-O3"}},
        dict(verification, catalogue_hall_o2=False),
    ]
    for invalid in invalid_receipts:
        with pytest.raises(ValueError):
            packager._validate_catalogue(raw, packager.sha256(raw), invalid, {path: payload})


def test_catalogue_schema1_remains_compatible_only_without_optimization_metadata():
    payload = b"historical catalogue object"
    path = "/catalogue/old/object.o"
    row = {"path": path, "sha256": packager.sha256(payload)}
    raw = packager.canonical_json({"schema": 1, "objects": [row]})
    assert packager._validate_catalogue(
        raw, packager.sha256(raw), {"catalogue_objects": [row]}, {path: payload})["schema"] == 1

    optimized = dict(row, optimization="-Oz")
    receipt = {"catalogue_objects": [optimized]}
    with pytest.raises(ValueError, match="manifest schema"):
        packager._validate_catalogue(raw, packager.sha256(raw), receipt, {path: payload})
    with pytest.raises(ValueError, match="cannot discard optimization overrides"):
        packager._validate_catalogue(
            raw, packager.sha256(raw), {"catalogue_objects": [row],
                                        "catalogue_optimization_overrides": {"old/object.o": "-Os"}},
            {path: payload})
    with pytest.raises(ValueError, match="cannot discard optimization overrides"):
        packager._validate_catalogue(
            raw, packager.sha256(raw), {"catalogue_objects": [row],
                                        "catalogue_optimization_overrides": {}}, {path: payload})


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

    for altered_tuple in (
            dict(tuple_data, toolchain_tree_sha256="0" * 64),
            {key: value for key, value in tuple_data.items() if key != "toolchain_tree_sha256"}):
        with pytest.raises(ValueError, match="build provenance toolchain_tree_sha256 differs"):
            packager._validate_receipts(
                altered_tuple, values["app"], values["elf"], values["artifact_receipt"],
                values["build_receipt"], values["build_provenance"], values["request"],
                values["prepared_profile"], values["source_profile"], values["catalogue_manifest"],
                values["image_receipt"], values["catalogue_files"], values["generated_files"])

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
