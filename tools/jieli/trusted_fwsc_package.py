#!/usr/bin/env python3
"""Compose an offline FWSC package from a trusted expanded-D7000 build tuple."""
from __future__ import annotations
import hashlib, json, re, sys
from collections.abc import Mapping
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import inspect_fwsc  # noqa: E402
import model_092_app_replacement as nested_model  # noqa: E402

PROFILE_ID = "fm1-092-d7000"
RUNTIME_POLICY_SHA256 = "fe457ad4056aeb8e6b3ec9df606ac79ab757adc142bd2db9780357fb72f1e905"
TUPLE_KEYS = {
    "app_bytes", "app_sha256", "application_identity", "artifact_receipt_sha256",
    "build_provenance_sha256", "build_receipt_sha256", "catalogue_sha256", "elf_sha256",
    "flash_layout", "hardware_admitted", "hardware_tested", "installable",
    "prepared_profile_sha256", "profile_id", "recovery_identity", "request_sha256",
    "runtime_mode", "schema", "source_tree_sha256", "toolchain_image_sha256",
    "toolchain_tree_sha256", "tuple_id",
}
HASH_FIELDS = {
    "source_tree_sha256", "toolchain_image_sha256", "toolchain_tree_sha256",
    "catalogue_sha256", "request_sha256",
    "prepared_profile_sha256", "app_sha256", "elf_sha256", "artifact_receipt_sha256",
    "build_receipt_sha256", "build_provenance_sha256",
}
_HASH = re.compile(r"^[0-9a-f]{64}$")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _pairs_no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _json_object(raw: bytes, label: str, *, canonical=False):
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs_no_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    if canonical and canonical_json(value) != raw:
        raise ValueError(f"{label} is not canonical JSON")
    return value


def _require_exact_keys(value, expected, label):
    if set(value) != expected:
        missing, extra = sorted(expected - set(value)), sorted(set(value) - expected)
        raise ValueError(f"{label} fields differ (missing={missing}, extra={extra})")


def _require_hash(value, field, label):
    digest = value.get(field)
    if not isinstance(digest, str) or not _HASH.fullmatch(digest):
        raise ValueError(f"{label}.{field} must be a lowercase SHA-256")


def _validate_tuple(raw_tuple, expected_tuple_sha256):
    if not isinstance(expected_tuple_sha256, str) or not _HASH.fullmatch(expected_tuple_sha256):
        raise ValueError("trusted tuple digest must be a lowercase SHA-256")
    if sha256(raw_tuple) != expected_tuple_sha256:
        raise ValueError("trusted build tuple digest differs from its external trust anchor")
    build_tuple = _json_object(raw_tuple, "build tuple", canonical=True)
    _require_exact_keys(build_tuple, TUPLE_KEYS, "build tuple")
    if (type(build_tuple["schema"]) is not int or build_tuple["schema"] != 1
            or build_tuple["profile_id"] != PROFILE_ID):
        raise ValueError("build tuple schema/profile is not the named D7000 profile")
    if build_tuple["flash_layout"] != "expanded-d7000":
        raise ValueError("build tuple does not select expanded-d7000")
    if not isinstance(build_tuple["tuple_id"], str) or not build_tuple["tuple_id"]:
        raise ValueError("build tuple requires a non-empty tuple_id")
    for field in HASH_FIELDS:
        _require_hash(build_tuple, field, "build tuple")
    size = build_tuple["app_bytes"]
    if isinstance(size, bool) or not isinstance(size, int):
        raise ValueError("build tuple app_bytes must be an integer")
    if not 1 <= size <= nested_model.MAX_APP_BYTES:
        raise ValueError("build tuple app_bytes exceed the preserved-tail D7000 bound")
    for field in ("application_identity", "recovery_identity"):
        if not isinstance(build_tuple[field], str) or not re.fullmatch(r"FM-1_[0-9]{3}", build_tuple[field]):
            raise ValueError(f"build tuple {field} is not a supported FM-1 identity")
    if build_tuple["runtime_mode"] not in ("song-diagnostic", "continuous"):
        raise ValueError("build tuple is not a supported offline runtime mode")
    if build_tuple["runtime_mode"] == "continuous" and (
            re.fullmatch(r"FM-1_5[0-9]{2}", build_tuple["application_identity"]) is None
            or build_tuple["recovery_identity"] != "FM-1_000"):
        raise ValueError("continuous tuple requires an explicit Lunar identity and stock recovery identity")
    if any(build_tuple[key] is not False for key in ("hardware_admitted", "hardware_tested", "installable")):
        raise ValueError("build tuple must keep hardware and installability flags false")
    return build_tuple


def _validate_runtime(verification, mode):
    """Verify the compiled timer policy independently of the tuple's mode label."""
    runtime = verification.get("runtime_configuration")
    if not isinstance(runtime, dict) or runtime.get("runtime_mode") != mode:
        raise ValueError("build receipt runtime mode differs from the trusted tuple")
    if runtime.get("release_accepted") is not False:
        raise ValueError("build receipt must keep release acceptance false")
    seconds = runtime.get("return_to_rom_seconds")
    if mode == "continuous":
        if (set(runtime) != {"runtime_mode", "return_to_rom_seconds", "define", "release_accepted"}
                or seconds is not None or runtime.get("define") != "-DLUNAR_RETURN_TO_ROM_SECONDS=0"
                or "probe_return_to_rom_seconds" not in verification
                or verification["probe_return_to_rom_seconds"] is not None
                or verification.get("runtime_policy_sha256") != RUNTIME_POLICY_SHA256):
            raise ValueError("build receipt is not the exact continuous runtime policy")
    elif mode == "song-diagnostic":
        if isinstance(seconds, bool) or not isinstance(seconds, int) or not 1 <= seconds <= 3600:
            raise ValueError("build receipt has no bounded diagnostic runtime configuration")
    else:
        raise ValueError("unsupported offline runtime mode")
    return runtime, seconds

def _validate_catalogue(raw, expected_sha256, verification, catalogue_files):
    if sha256(raw) != expected_sha256:
        raise ValueError("catalogue manifest digest differs from the trusted build tuple")
    manifest = _json_object(raw, "catalogue manifest", canonical=True)
    _require_exact_keys(manifest, {"schema", "objects"}, "catalogue manifest")
    if (type(manifest["schema"]) is not int or manifest["schema"] != 1
            or not isinstance(manifest["objects"], list)):
        raise ValueError("catalogue manifest schema or objects list is invalid")
    expected, previous = {}, None
    for row in manifest["objects"]:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise ValueError("catalogue manifest rows require exactly path and sha256")
        path = row["path"]
        if (not isinstance(path, str) or not path.startswith("/catalogue/")
                or "\\" in path or ".." in Path(path).parts):
            raise ValueError("catalogue manifest path is outside its trusted namespace")
        _require_hash(row, "sha256", "catalogue manifest row")
        if previous is not None and path <= previous:
            raise ValueError("catalogue manifest paths must be unique and sorted")
        expected[path] = row["sha256"]
        previous = path
    receipt_rows = verification.get("catalogue_objects")
    if not isinstance(receipt_rows, list):
        raise ValueError("build receipt is missing catalogue_objects")
    receipt = {}
    for row in receipt_rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise ValueError("build receipt catalogue rows are malformed")
        if row["path"] in receipt:
            raise ValueError("build receipt repeats a catalogue path")
        receipt[row["path"]] = row["sha256"]
    if receipt != expected:
        raise ValueError("manifest must exactly match all build receipt catalogue objects")
    if not isinstance(catalogue_files, Mapping) or set(catalogue_files) != set(expected):
        raise ValueError("catalogue byte mapping must contain exactly all manifest objects")
    for path, digest in expected.items():
        raw_file = catalogue_files[path]
        if not isinstance(raw_file, bytes) or sha256(raw_file) != digest:
            raise ValueError("catalogue bytes differ from their trusted manifest digest")
    return manifest


def _validate_provenance_rows(provenance, field, files):
    rows = provenance.get(field)
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"build provenance is missing {field}")
    expected = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise ValueError(f"build provenance {field} rows are malformed")
        path = row["path"]
        if (not isinstance(path, str) or not path or path.startswith("/")
                or "\\" in path or ".." in Path(path).parts):
            raise ValueError(f"build provenance {field} path is unsafe")
        _require_hash(row, "sha256", f"build provenance {field} row")
        if path in expected:
            raise ValueError(f"build provenance repeats a {field} path")
        expected[path] = row["sha256"]
    if not isinstance(files, Mapping) or set(files) != set(expected):
        raise ValueError(f"provided {field} bytes must exactly match provenance paths")
    for path, digest in expected.items():
        content = files[path]
        if not isinstance(content, bytes) or sha256(content) != digest:
            raise ValueError(f"{field} bytes differ from build provenance: {path}")

def _validate_receipts(build_tuple, app, elf, artifact_raw, build_raw, provenance_raw,
                       request_raw, prepared_profile_raw, source_profile_raw,
                       catalogue_raw, image_raw, catalogue_files, generated_files):
    checks = {
        "app": (app, "app_sha256"), "ELF": (elf, "elf_sha256"),
        "artifact receipt": (artifact_raw, "artifact_receipt_sha256"),
        "build receipt": (build_raw, "build_receipt_sha256"),
        "build provenance": (provenance_raw, "build_provenance_sha256"),
        "request": (request_raw, "request_sha256"),
        "prepared profile": (prepared_profile_raw, "prepared_profile_sha256"),
    }
    for label, (raw, field) in checks.items():
        if sha256(raw) != build_tuple[field]:
            raise ValueError(f"{label} hash differs from the trusted build tuple")
    if len(app) != build_tuple["app_bytes"]:
        raise ValueError("candidate app length differs from the trusted build tuple")

    artifact = _json_object(artifact_raw, "artifact receipt")
    verification = _json_object(build_raw, "build receipt")
    provenance = _json_object(provenance_raw, "build provenance", canonical=True)
    request = _json_object(request_raw, "build request")
    prepared_profile = _json_object(prepared_profile_raw, "prepared profile")
    image = _json_object(image_raw, "image receipt")
    if type(provenance.get("schema")) is not int or provenance["schema"] != 1:
        raise ValueError("unsupported build provenance schema")
    for key in ("profile_id", "flash_layout", "app_sha256", "app_bytes", "elf_sha256",
                "application_identity", "recovery_identity", "artifact_receipt_sha256",
                "build_receipt_sha256", "catalogue_sha256", "request_sha256",
                "prepared_profile_sha256", "source_tree_sha256", "toolchain_image_sha256",
                "toolchain_tree_sha256", "runtime_mode"):
        if provenance.get(key) != build_tuple.get(key):
            raise ValueError(f"build provenance {key} differs from the trusted tuple")
    if provenance.get("request_receipt_sha256") != build_tuple["request_sha256"]:
        raise ValueError("provenance request receipt differs from trusted request")
    if provenance.get("prepared_profile_receipt_sha256") != build_tuple["prepared_profile_sha256"]:
        raise ValueError("provenance prepared-profile receipt differs from trusted profile")
    if provenance.get("flash_layout") != "expanded-d7000":
        raise ValueError("provenance does not name expanded-d7000")
    if any(provenance.get(flag) is not False for flag in ("hardware_admitted", "hardware_tested", "installable")):
        raise ValueError("build provenance must keep hardware/installability flags false")

    if (artifact.get("app_sha256"), artifact.get("app_bytes"), artifact.get("elf_sha256")) != (
            build_tuple["app_sha256"], build_tuple["app_bytes"], build_tuple["elf_sha256"]):
        raise ValueError("artifact receipt does not bind the selected app and ELF")
    if artifact.get("flash_layout") != "expanded-d7000" or verification.get("flash_layout") != "expanded-d7000":
        raise ValueError("artifact/build receipt does not use expanded-d7000")
    if any(artifact.get(flag) is not False for flag in ("installable", "hardware_admitted", "hardware_tested")):
        raise ValueError("artifact receipt must keep hardware/installability flags false")
    if any(verification.get(flag) is not False for flag in ("installable", "hardware_candidate", "hardware_tested")):
        raise ValueError("build receipt must keep hardware/installability flags false")
    if verification.get("elf_sha256") != build_tuple["elf_sha256"]:
        raise ValueError("build receipt does not bind the selected ELF")
    identity = verification.get("firmware_identity")
    explicit = build_tuple["runtime_mode"] == "continuous"
    expected_identity = (build_tuple["application_identity"], build_tuple["recovery_identity"], explicit, False, False, False)
    if not isinstance(identity, dict) or (
        identity.get("application_identity"), identity.get("recovery_identity"), identity.get("explicit"),
        identity.get("package_identity_verified"), identity.get("updater_acceptance_verified"),
        identity.get("hardware_identity_verified")
    ) != expected_identity:
        raise ValueError("build receipt firmware identity differs from the trusted tuple")
    if identity.get("explicit") is not explicit:
        raise ValueError("build receipt explicit identity flag must be a boolean")
    save = verification.get("project_save_service")
    if not isinstance(save, dict) or any(save.get(key) is not False for key in (
            "storage_admitted", "flash_io_bound", "save_service_armed", "runtime_verified", "hardware_tested")):
        raise ValueError("build receipt does not keep SAVE flash I/O disarmed")
    runtime, seconds = _validate_runtime(verification, build_tuple["runtime_mode"])
    if image.get("verification_sha256") != build_tuple["build_receipt_sha256"]:
        raise ValueError("image receipt does not bind the exact build receipt")
    if image.get("app_sha256") != build_tuple["app_sha256"] or image.get("app_bytes") != build_tuple["app_bytes"] or image.get("elf_sha256") != build_tuple["elf_sha256"]:
        raise ValueError("image receipt does not bind the selected app size and ELF")
    image_identity = image.get("firmware_identity")
    if not isinstance(image_identity, dict) or (
            image_identity.get("application_identity"), image_identity.get("recovery_identity"),
            image_identity.get("explicit"), image_identity.get("package_identity_verified"),
            image_identity.get("updater_acceptance_verified"), image_identity.get("hardware_identity_verified")) != (
            build_tuple["application_identity"], build_tuple["recovery_identity"], explicit, False, False, False):
        raise ValueError("image receipt firmware identity differs from the trusted tuple")
    if image_identity.get("explicit") is not explicit:
        raise ValueError("image receipt explicit identity flag must be a boolean")
    if image.get("artifact_receipt_sha256") != build_tuple["artifact_receipt_sha256"]:
        raise ValueError("image receipt does not bind the artifact receipt")
    if image.get("request_sha256") != build_tuple["request_sha256"] or image.get("prepared_profile_sha256") != build_tuple["prepared_profile_sha256"]:
        raise ValueError("image receipt does not bind request and prepared profile")
    if any(image.get(flag) is not False for flag in ("installable", "hardware_admitted", "hardware_tested")):
        raise ValueError("image receipt must keep hardware/installability flags false")
    if image.get("runtime_configuration") != runtime:
        raise ValueError("image and build runtime configurations differ")
    for field in ("application_identity", "recovery_identity"):
        identity_bytes = (build_tuple[field] + "\0").encode("ascii")
        if app.count(identity_bytes) != 1:
            raise ValueError(f"app must contain exactly one {build_tuple[field]} identity")
    profile_source_sha = prepared_profile.get("profile_sha256")
    if (not isinstance(profile_source_sha, str) or not _HASH.fullmatch(profile_source_sha)
            or not isinstance(source_profile_raw, bytes) or sha256(source_profile_raw) != profile_source_sha):
        raise ValueError("prepared profile does not bind the exact source profile bytes")
    if type(request.get("version")) is not int or request["version"] != 1:
        raise ValueError("build request schema is unsupported")
    manifest = _validate_catalogue(catalogue_raw, build_tuple["catalogue_sha256"], verification, catalogue_files)
    _validate_provenance_rows(provenance, "module_and_generated_inputs", generated_files)
    return artifact, verification, provenance, manifest, image, seconds

def _set_identity(raw, identity):
    if not isinstance(identity, str) or not re.fullmatch(r"FM-1_[0-9]{3}", identity):
        raise ValueError("unsupported fixed-length FWSC identity")
    out = bytearray(raw)
    for i, char in enumerate(identity):
        out[i * 48 + 47] = (ord(char) + i + 1) & 0xFF
    for i in range(len(identity), 20):
        out[i * 48 + 47] = 125
    return bytes(out)


def _normalize_legacy_identity(raw):
    return _set_identity(raw, nested_model.IDENTITY)


def package_bytes(*, source_fwsc: bytes, reference_dir, app: bytes, elf: bytes,
                  artifact_receipt: bytes, build_receipt: bytes, build_provenance: bytes,
                  request: bytes, prepared_profile: bytes, source_profile: bytes,
                  catalogue_manifest: bytes, image_receipt: bytes, catalogue_files: Mapping[str, bytes],
                  generated_files: Mapping[str, bytes], build_tuple: bytes,
                  expected_tuple_sha256: str):
    """Compose/reopen a private offline package in memory; does not write files."""
    trusted = _validate_tuple(build_tuple, expected_tuple_sha256)
    artifact, verification, _, manifest, image, runtime_seconds = _validate_receipts(
        trusted, app, elf, artifact_receipt, build_receipt, build_provenance,
        request, prepared_profile, source_profile, catalogue_manifest, image_receipt,
        catalogue_files, generated_files)
    if sha256(source_fwsc) != nested_model.SOURCE_SHA256:
        raise ValueError("source FWSC is not the pinned public FM-1_092 model input")
    modeled, *_ = nested_model._build(
        source_fwsc, reference_dir, app, target_app_sha256=trusted["app_sha256"])
    nested_model.verify_modeled(
        source_fwsc, modeled, reference_dir, app, target_app_sha256=trusted["app_sha256"])
    package = _set_identity(modeled, trusted["application_identity"])
    generic = inspect_fwsc.inspect(package)
    if (generic.get("identity") != trusted["application_identity"] or not generic.get("header_crc_verified")
            or not generic.get("entry_list_crc_verified")
            or not all(entry.get("crc_verified") for entry in generic.get("entries", []))):
        raise ValueError("independent FWSC parser rejected package header, list, or payload CRC")
    normalized = _normalize_legacy_identity(package)
    source_model, output, before, after, _, relocated, bounds = nested_model.verify_modeled(
        source_fwsc, normalized, reference_dir, app, target_app_sha256=trusted["app_sha256"])
    if source_model["identity"] != nested_model.IDENTITY or output["identity"] != nested_model.IDENTITY:
        raise ValueError("normalized model identity changed during independent verification")
    if after["app"] != app or after["protected_sha256"] != before["protected_sha256"]:
        raise ValueError("nested candidate app or decoded protected bytes failed preservation check")
    if output["entries"][0]["size"] != nested_model.STAGE_START or bounds["used_end"] > nested_model.STAGE_START:
        raise ValueError("nested payload is outside D7000 profile bounds")
    if generic["identity"] != trusted["application_identity"]:
        raise ValueError("outer identity differs from tuple application identity")
    report = {
        "schema": 1, "status": "offline-trusted-build-tuple-fm1-092-d7000-structurally-verified",
        "profile_id": PROFILE_ID, "tuple_id": trusted["tuple_id"],
        "build_tuple_sha256": expected_tuple_sha256,
        "source_fwsc_sha256": sha256(source_fwsc),
        "source_tree_sha256": trusted["source_tree_sha256"],
        "toolchain_image_sha256": trusted["toolchain_image_sha256"],
        "catalogue_sha256": trusted["catalogue_sha256"],
        "request_sha256": trusted["request_sha256"],
        "prepared_profile_sha256": trusted["prepared_profile_sha256"],
        "app_sha256": trusted["app_sha256"], "app_bytes": trusted["app_bytes"],
        "elf_sha256": trusted["elf_sha256"],
        "artifact_receipt_sha256": trusted["artifact_receipt_sha256"],
        "build_receipt_sha256": trusted["build_receipt_sha256"],
        "build_provenance_sha256": trusted["build_provenance_sha256"],
        "package_identity": generic["identity"], "recovery_identity": trusted["recovery_identity"],
        "runtime_mode": trusted["runtime_mode"], "return_to_rom_seconds": runtime_seconds,
        "package_sha256": sha256(package), "package_bytes": len(package),
        "flash_layout": PROFILE_ID, "expanded_flash_bytes": nested_model.STAGE_START,
        "max_app_bytes_preserving_092_tail": nested_model.MAX_APP_BYTES,
        "app_slack_to_max": nested_model.MAX_APP_BYTES - trusted["app_bytes"],
        "nested_boundaries": bounds, "protected_decoded_sha256": after["protected_sha256"],
        "relocated_outer_payloads": relocated, "catalogue_entries_verified": len(manifest["objects"]),
        "outer_integrity": {
            "header_crc_verified": generic["header_crc_verified"],
            "entry_list_crc_verified": generic["entry_list_crc_verified"],
            "all_payload_crcs_verified": all(entry["crc_verified"] for entry in generic["entries"]),
        },
        "package_returned_in_memory": True, "file_written": False,
        "hardware_admitted": False, "hardware_tested": False,
        "installable": False, "updater_acceptance_verified": False, "release_admitted": False,
        "pending": [
            "external trust policy for the tuple digest",
            "stock updater identity/version and expanded-container acceptance",
            "proprietary loader relocation and physical flash behavior",
            "device recovery, settings migration, runtime and musical acceptance",
        ],
    }
    if not all(report["outer_integrity"].values()):
        raise ValueError("final package integrity report is incomplete")
    if artifact.get("app_sha256") != report["app_sha256"] or verification.get("elf_sha256") != report["elf_sha256"]:
        raise ValueError("independent package output no longer matches controller receipts")
    return package, report
