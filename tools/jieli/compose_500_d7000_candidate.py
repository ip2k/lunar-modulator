#!/usr/bin/env python3
"""Compose one private FM-1_500 D7000 FWSC candidate from pinned local inputs.

This is a structural offline composer, not an installer or admission tool. It
reuses the reviewed 092 nested-container model under an exact, scoped FM-1_500
app hash, then changes only the unchecksummed outer identity marker. All other
container and nested bytes are independently reopened and checked.
"""
import hashlib
import json
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import inspect_fwsc  # noqa: E402
import model_092_app_replacement as legacy  # noqa: E402

SOURCE = Path("/home/claude/.local/share/codex-worktrees/092-package-model/scratch/092-package-model/FM-1_092.fwsc")
REFERENCE = SOURCE.with_name("FM-1_092.fwsc_unpack")
TARGET_BUILD = Path("/home/claude/mvave-fm1/native-identity-target-20261014/canonical-rerun2/out/build")
APP = TARGET_BUILD / "artifact/app.bin"
ELF = TARGET_BUILD / "lunar-app-probe.elf"
ARTIFACT_RECEIPT = TARGET_BUILD / "artifact/artifact.json"
BUILD_RECEIPT = TARGET_BUILD / "verification.json"
OUTPUT = Path("/home/claude/mvave-fm1/private-package500-candidate/lunar-FM-1_500-d7000.fwsc")

SOURCE_SHA256 = "ed8415f32f5e2ff5558a24cee45eafd8d0a5b1982af14d4cb88ba019b876eb80"
APP_SHA256 = "27600a10bae2ec177699ae2a1e3794b739e6085f61d088c47307db7a0eb515e4"
APP_BYTES = 845272
ELF_SHA256 = "335c448e67919e2bc52e7421164033ddd505956016531897aebe73f15772a4d1"
ARTIFACT_RECEIPT_SHA256 = "7b28bc74cd250c2f21ca96c2dd8b86efc03550a28bedc569385ea043f8c02129"
BUILD_RECEIPT_SHA256 = "eca3d6d0f2575af44712a6fc6ce32f4b104dd0b6202b7c58df53a0729c79f3ea"
PACKAGE_IDENTITY = "FM-1_500"
RECOVERY_IDENTITY = "FM-1_000"
EXPECTED_CONTAINER_BYTES = 978484
MAX_CONTAINER_BYTES = EXPECTED_CONTAINER_BYTES
_MODEL_PIN_LOCK = threading.RLock()
LEGACY_APP_SHA256 = "5709ac03377a310eefdff563f4f08fe8a0e932ed9e0ecacef96464a59ec48573"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _require_hash(data, expected, label):
    actual = sha256(data)
    if actual != expected:
        raise ValueError(f"{label} SHA-256 is not the pinned target input")
    return actual


@contextmanager
def _bound_target_app_pin():
    """Reuse strict 092 parsing with one serialized, exact 500 app binding."""
    with _MODEL_PIN_LOCK:
        if (legacy.SOURCE_SHA256 != SOURCE_SHA256 or legacy.IDENTITY != "FM-1_092"
                or legacy.TARGET_APP_SHA256 != LEGACY_APP_SHA256):
            raise ValueError("reviewed strict 092 model pins have changed")
        prior = legacy.TARGET_APP_SHA256
        legacy.TARGET_APP_SHA256 = APP_SHA256
        try:
            yield
        finally:
            legacy.TARGET_APP_SHA256 = prior


def _json_bytes(raw, label):
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _verify_target(app, elf, artifact_receipt, build_receipt):
    _require_hash(app, APP_SHA256, "FM-1_500 app")
    _require_hash(elf, ELF_SHA256, "FM-1_500 ELF")
    if len(app) != APP_BYTES:
        raise ValueError("FM-1_500 app length differs from pinned target link")
    _require_hash(artifact_receipt, ARTIFACT_RECEIPT_SHA256, "artifact receipt")
    _require_hash(build_receipt, BUILD_RECEIPT_SHA256, "build receipt")
    artifact = _json_bytes(artifact_receipt, "artifact receipt")
    receipt = _json_bytes(build_receipt, "build receipt")
    if (artifact.get("app_sha256"), artifact.get("app_bytes"), artifact.get("elf_sha256")) != (
            APP_SHA256, APP_BYTES, ELF_SHA256):
        raise ValueError("artifact receipt does not bind the pinned app and ELF")
    identity = receipt.get("firmware_identity")
    if not isinstance(identity, dict) or identity != {
            "application_identity": PACKAGE_IDENTITY,
            "explicit": True,
            "recovery_identity": RECOVERY_IDENTITY,
            "package_identity_verified": False,
            "updater_acceptance_verified": False,
            "hardware_identity_verified": False,
    }:
        raise ValueError("build receipt identity contract differs from pinned target")
    if receipt.get("elf_sha256") != ELF_SHA256:
        raise ValueError("build receipt does not bind the pinned ELF")
    if (artifact.get("installable") is not False or artifact.get("hardware_tested") is not False
            or artifact.get("hardware_admitted") is not False
            or receipt.get("installable") is not False
            or receipt.get("hardware_tested") is not False
            or receipt.get("hardware_candidate") is not False):
        raise ValueError("target receipt must leave installation and hardware admission false")
    save = receipt.get("project_save_service")
    if not isinstance(save, dict) or any(save.get(key) is not False for key in (
            "storage_admitted", "flash_io_bound", "save_service_armed", "runtime_verified", "hardware_tested")):
        raise ValueError("target receipt does not keep SAVE service disarmed and unadmitted")
    if app.count((PACKAGE_IDENTITY + "\0").encode("ascii")) != 1:
        raise ValueError("app does not contain exactly one explicit FM-1_500 identity")
    if app.count((RECOVERY_IDENTITY + "\0").encode("ascii")) != 1:
        raise ValueError("app does not contain exactly one recovery identity")
    return artifact, receipt


def _set_physical_identity(raw, identity):
    if not identity.startswith("FM-1_") or len(identity) != 8 or not identity[-3:].isdigit():
        raise ValueError("unsupported fixed-length package identity")
    out = bytearray(raw)
    for i, char in enumerate(identity):
        out[i * 48 + 47] = (ord(char) + i + 1) & 0xFF
    for i in range(len(identity), 20):
        out[i * 48 + 47] = 125
    return bytes(out)


def _physical_identity(raw):
    if len(raw) < 20 * 48:
        raise ValueError("container is shorter than the physical identity prefix")
    markers = [raw[i * 48 + 47] for i in range(20)]
    end = next((i for i, value in enumerate(markers) if value == 125), 20)
    if any(value != 125 for value in markers[end:]):
        raise ValueError("container identity markers are not contiguous")
    try:
        return bytes((value - i - 1) & 0xFF for i, value in enumerate(markers[:end])).decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("container identity marker is not ASCII") from exc


def _with_legacy_identity(raw):
    return _set_physical_identity(raw, legacy.IDENTITY)


def verify_package(source, package, reference_dir, app, elf, artifact_receipt, build_receipt):
    """Independently validate final outer marker, container CRCs and nested model."""
    if sha256(source) != SOURCE_SHA256:
        raise ValueError("source package is not the pinned public FM-1_092 fixture")
    if len(package) != EXPECTED_CONTAINER_BYTES or len(package) > MAX_CONTAINER_BYTES:
        raise ValueError("FWSC candidate length differs from the pinned relocated-container extent")
    _verify_target(app, elf, artifact_receipt, build_receipt)
    if _physical_identity(package) != PACKAGE_IDENTITY:
        raise ValueError("FWSC outer identity is not FM-1_500")
    generic = inspect_fwsc.inspect(package)
    if generic["identity"] != PACKAGE_IDENTITY:
        raise ValueError("independent FWSC reader did not accept the FM-1_500 marker")
    if not (generic["header_crc_verified"] and generic["entry_list_crc_verified"]
            and all(entry["crc_verified"] for entry in generic["entries"])):
        raise ValueError("FWSC header, entry-list, or payload CRC validation failed")
    normalized = _with_legacy_identity(package)
    with _bound_target_app_pin():
        source_model, output, before, after, _, _, bounds = legacy.verify_modeled(
            source, normalized, reference_dir, app)
        if output["identity"] != legacy.IDENTITY or after["app"] != app:
            raise ValueError("normalized strict-model verification did not reproduce the candidate app")
        if sha256(after["app"]) != APP_SHA256:
            raise ValueError("nested decoded app hash differs from the pinned FM-1_500 app")
        if len(after["app"]) != APP_BYTES or output["entries"][0]["size"] != legacy.STAGE_START:
            raise ValueError("candidate app or expanded flash extent differs from pinned D7000 profile")
        if not (bounds["used_end"] <= legacy.STAGE_START and bounds["slack_to_stage"] >= 0):
            raise ValueError("relocated nested resources exceed D7000")
        modeled, _, _, _, _ = legacy._build(source, reference_dir, app)
        if normalized != modeled:
            raise ValueError("candidate differs from exact reviewed nested/outer model outside identity marker")
    if source_model["identity"] != legacy.IDENTITY:
        raise ValueError("pinned source is no longer the strict 092 input")
    protected = after["protected_sha256"]
    if protected != before["protected_sha256"]:
        raise ValueError("protected SPL/config/CFG/key data changed")
    return {
        "status": "private-fm1-500-d7000-candidate-structurally-verified",
        "package_identity": PACKAGE_IDENTITY,
        "application_identity": PACKAGE_IDENTITY,
        "source_fwsc_sha256": SOURCE_SHA256,
        "target_app_sha256": APP_SHA256,
        "target_elf_sha256": ELF_SHA256,
        "artifact_receipt_sha256": ARTIFACT_RECEIPT_SHA256,
        "build_receipt_sha256": BUILD_RECEIPT_SHA256,
        "package_sha256": sha256(package),
        "package_bytes": len(package),
        "expected_container_bytes": EXPECTED_CONTAINER_BYTES,
        "expanded_flash_bytes": legacy.STAGE_START,
        "app_bytes": APP_BYTES,
        "max_app_bytes_preserving_pinned_092_tail": legacy.MAX_APP_BYTES,
        "app_slack_to_max": legacy.MAX_APP_BYTES - APP_BYTES,
        "nested_boundaries": bounds,
        "outer_integrity": {
            "header_crc_verified": generic["header_crc_verified"],
            "entry_list_crc_verified": generic["entry_list_crc_verified"],
            "all_payload_crcs_verified": all(entry["crc_verified"] for entry in generic["entries"]),
        },
        "protected_decoded_sha256": protected,
        "relocated_outer_payloads_reencoded": True,
        "binary_emitted": True,
        "installable": False,
        "hardware_admitted": False,
        "hardware_tested": False,
        "updater_acceptance_verified": False,
        "release_admitted": False,
        "pending": [
            "stock updater identity/version and expanded-container acceptance",
            "proprietary loader relocation and physical flash behavior",
            "device recovery, settings migration, SAVE/runtime and musical acceptance",
            "owner and hardware approval",
        ],
    }


def compose_bytes(source, reference_dir, app, elf, artifact_receipt, build_receipt):
    """Compose and fully re-verify the one pinned target without writing files."""
    _verify_target(app, elf, artifact_receipt, build_receipt)
    if sha256(source) != SOURCE_SHA256:
        raise ValueError("source package is not the pinned public FM-1_092 fixture")
    with _bound_target_app_pin():
        modeled, *_ = legacy._build(source, reference_dir, app)
        legacy.verify_modeled(source, modeled, reference_dir, app)
    package = _set_physical_identity(modeled, PACKAGE_IDENTITY)
    report = verify_package(source, package, reference_dir, app, elf, artifact_receipt, build_receipt)
    return package, report


def main():
    try:
        source = SOURCE.read_bytes()
        app, elf = APP.read_bytes(), ELF.read_bytes()
        artifact_receipt, build_receipt = ARTIFACT_RECEIPT.read_bytes(), BUILD_RECEIPT.read_bytes()
        package, report = compose_bytes(source, REFERENCE, app, elf, artifact_receipt, build_receipt)
        if OUTPUT.exists():
            raise ValueError(f"refusing to overwrite existing private candidate: {OUTPUT}")
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with OUTPUT.open("xb") as stream:
            stream.write(package)
            stream.flush()
        report = verify_package(source, OUTPUT.read_bytes(), REFERENCE, app, elf,
                                artifact_receipt, build_receipt)
        print(json.dumps({**report, "output": str(OUTPUT)}, indent=2, sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f"compose_500_d7000_candidate: {exc}")


if __name__ == "__main__":
    main()
