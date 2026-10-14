#!/usr/bin/env python3
"""Compose one private continuous FM-1_500 D7000 FWSC candidate from pinned local inputs.

This is a structural offline composer, not an installer or admission tool. It
reuses the reviewed 092 nested-container model under an exact, scoped FM-1_500
app hash, then changes only the unchecksummed outer identity marker. All other
container and nested bytes are independently reopened and checked.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import inspect_fwsc  # noqa: E402
import model_092_app_replacement as legacy  # noqa: E402

SOURCE = Path("/home/claude/.local/share/codex-worktrees/092-package-model/scratch/092-package-model/FM-1_092.fwsc")
REFERENCE = SOURCE.with_name("FM-1_092.fwsc_unpack")
TARGET_BUILD = Path("/home/claude/mvave-fm1/continuous500-link-20261014/out3/build")
APP = TARGET_BUILD / "artifact/app.bin"
ELF = TARGET_BUILD / "lunar-app-probe.elf"
ARTIFACT_RECEIPT = TARGET_BUILD / "artifact/artifact.json"
BUILD_RECEIPT = TARGET_BUILD / "verification.json"
OUTPUT = Path("/home/claude/mvave-fm1/private-package500-continuous-candidate/lunar-FM-1_500-continuous-d7000.fwsc")

SOURCE_SHA256 = "ed8415f32f5e2ff5558a24cee45eafd8d0a5b1982af14d4cb88ba019b876eb80"
APP_SHA256 = "5c923197629121ce90a33919b516ced23ef8edbaa1943ea1e9568b596b6557ee"
APP_BYTES = 845336
ELF_SHA256 = "4b8ae5a1f68550bcbedc2442d98f03f5af85daa88fcfbb69af37985b3d9f0120"
ARTIFACT_RECEIPT_SHA256 = "501c690e8d2c927ac79e45de617195b734f838bb6652aa6c43e62928419a5604"
BUILD_RECEIPT_SHA256 = "d1ec99dd5c45862a921b6579949ee6b71cc16eef2391eabaff5f2e57a578083f"
RUNTIME_POLICY_SHA256 = "fe457ad4056aeb8e6b3ec9df606ac79ab757adc142bd2db9780357fb72f1e905"
PACKAGE_IDENTITY = "FM-1_500"
RECOVERY_IDENTITY = "FM-1_000"
EXPECTED_CONTAINER_BYTES = 978484
MAX_CONTAINER_BYTES = EXPECTED_CONTAINER_BYTES
LEGACY_APP_SHA256 = "5709ac03377a310eefdff563f4f08fe8a0e932ed9e0ecacef96464a59ec48573"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _require_hash(data, expected, label):
    actual = sha256(data)
    if actual != expected:
        raise ValueError(f"{label} SHA-256 is not the pinned target input")
    return actual


def _require_legacy_model_pins():
    """Keep the shared strict model defaults immutable before scoped verification."""
    if (legacy.SOURCE_SHA256 != SOURCE_SHA256 or legacy.IDENTITY != "FM-1_092"
            or legacy.TARGET_APP_SHA256 != LEGACY_APP_SHA256):
        raise ValueError("reviewed strict 092 model pins have changed")


def _json_bytes(raw, label):
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _verify_continuous_policy(receipt):
    runtime = receipt.get("runtime_configuration")
    if not isinstance(runtime, dict) or runtime != {
            "define": "-DLUNAR_RETURN_TO_ROM_SECONDS=0",
            "release_accepted": False,
            "return_to_rom_seconds": None,
            "runtime_mode": "continuous",
    }:
        raise ValueError("target receipt is not the exact continuous runtime configuration")
    if receipt.get("probe_return_to_rom_seconds") is not None:
        raise ValueError("continuous target must not have a diagnostic return timer")
    if receipt.get("runtime_policy_sha256") != RUNTIME_POLICY_SHA256:
        raise ValueError("continuous target runtime policy digest differs from the pinned link")
    selection = receipt.get("module_selection")
    if not isinstance(selection, dict) or selection.get("header_sha256") != "eef6dabe417ebdb03c5ab510f7b4a3733aed331bf656ae26e7535f87276e861e":
        raise ValueError("target receipt is not bound to the pinned production module selection")
    selected = selection.get("selected")
    expected = [
        "macro", "shapes", "macro-heavy", "sixop", "dx7", "sw-sophie", "drums",
        "acid-bass", "comet", "crater", "drawbar", "trio", "phase-bend", "plate",
        "ensemble", "diffuse", "sw-psxverb", "crush", "fold", "drive", "echo",
        "warble", "filter", "comb", "comp", "limit", "djfilter", "tilt", "sat",
        "isolator", "eq", "room", "hall", "gate", "squash", "shaper", "repeat",
        "arp", "acid-gen", "lfo", "env", "chance", "function", "bounce", "register",
        "coin", "divide", "burst", "slew", "quantize", "compare", "logic", "calc",
        "mix", "resonator",
    ]
    if not isinstance(selected, list) or any(not isinstance(item, str) for item in selected):
        raise ValueError("target receipt production module selection has invalid types")
    if selected != expected:
        raise ValueError("target receipt does not match the exact 55-module production selection")


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
    _verify_continuous_policy(receipt)
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
    _require_legacy_model_pins()
    source_model, output, before, after, _, _, bounds = legacy.verify_modeled(
        source, normalized, reference_dir, app, target_app_sha256=APP_SHA256)
    if output["identity"] != legacy.IDENTITY or after["app"] != app:
        raise ValueError("normalized strict-model verification did not reproduce the candidate app")
    if sha256(after["app"]) != APP_SHA256:
        raise ValueError("nested decoded app hash differs from the pinned FM-1_500 app")
    if len(after["app"]) != APP_BYTES or output["entries"][0]["size"] != legacy.STAGE_START:
        raise ValueError("candidate app or expanded flash extent differs from pinned D7000 profile")
    if not (bounds["used_end"] <= legacy.STAGE_START and bounds["slack_to_stage"] >= 0):
        raise ValueError("relocated nested resources exceed D7000")
    modeled, _, _, _, _ = legacy._build(source, reference_dir, app, target_app_sha256=APP_SHA256)
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
        "runtime_mode": "continuous",
        "runtime_policy_sha256": RUNTIME_POLICY_SHA256,
        "selected_production_module_count": 55,
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
    _require_legacy_model_pins()
    modeled, *_ = legacy._build(source, reference_dir, app, target_app_sha256=APP_SHA256)
    legacy.verify_modeled(source, modeled, reference_dir, app, target_app_sha256=APP_SHA256)
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
        raise SystemExit(f"compose_500_continuous_d7000_candidate: {exc}")


if __name__ == "__main__":
    main()
