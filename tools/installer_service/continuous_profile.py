# SPDX-License-Identifier: MIT
"""Server-owned policy for selected, private continuous D7000 links.

This contract cannot confer tuple trust, package admission, or hardware acceptance.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys

PROFILE_ID = "fm1-500-d7000-continuous-selected-v1"
PROVENANCE_KIND = "private-continuous-build-provenance"
COMPATIBILITY_REASON = "private continuous link only; trusted FWSC composition requires independently captured operator provenance and an external tuple digest"
BUILD_ARGUMENTS = (
    "--flash-layout", "expanded-d7000", "--runtime-mode", "continuous",
    "--wavetable-profile", "compressed-required-banks-ram-plaits-braids-shapes8-v1",
    "--firmware-identity", "FM-1_500",
)
PROFILE_CONTRACT = {
    "schema": 1, "profile_id": PROFILE_ID,
    "build_arguments": list(BUILD_ARGUMENTS),
    "selection_policy": "caller-selected-production-catalogue-groups",
    "wavetable_policy": "exact-selected-namespaces-in-ram",
    "app_budget_bytes": 860644, "shapes_voices": 8,
    "runtime_mode": "continuous", "return_to_rom_seconds": None,
    "firmware_identity": "FM-1_500", "recovery_identity": "FM-1_000",
    "native_midi_input": {"enabled": True, "transport": "UART1-RX/PH8",
                          "ring_bytes": 256, "bytes_per_poll": 32,
                          "usb_midi_preserved": True},
    "diagnostic_instrumentation": "disabled-all", "hot_dsp_ram": False,
    "catalogue_optimization": "z-no-overrides",
    "project_save_service_armed": False, "installable": False,
    "trusted_fwsc_packager_compatible": False,
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def profile_sha256():
    return hashlib.sha256(canonical(PROFILE_CONTRACT)).hexdigest()


def profile_summary():
    return {"flash_layout": "expanded-d7000", "runtime_mode": "continuous",
            "shapes_voices": 8, "profile_id": PROFILE_ID,
            "profile_sha256": profile_sha256()}


def _helpers():
    native = str(Path(__file__).resolve().parents[1] / "native")
    if native not in sys.path:
        sys.path.insert(0, native)
    import build_demo_image
    import firmware_identity
    import runtime_mode
    for module in (build_demo_image, firmware_identity, runtime_mode):
        if Path(module.__file__).resolve() != Path(native) / (module.__name__ + ".py"):
            raise ValueError("continuous helper was not loaded from the pinned source")
    from firmware_identity import identity_configuration
    from runtime_mode import runtime_configuration
    return build_demo_image, identity_configuration, runtime_configuration


def _expect(actual, expected, field):
    # JSON canonical equality distinguishes booleans from integers at every depth.
    if canonical(actual) != canonical(expected):
        raise ValueError("private continuous profile mismatch: " + field)


def validate_request(request, module_kinds, projects, set_parents):
    """Recheck the standalone worker input against its pinned production catalogue."""
    groups = ("engines", "effects", "midi", "modulation")
    required = {"version", *groups, "project_ids", "startup_index", "flash_layout", "runtime_mode"}
    if (not isinstance(request, dict) or set(request) not in (required, required | {"set_ids"})
            or type(request.get("version")) is not int or request["version"] != 1
            or request.get("flash_layout") != "expanded-d7000"
            or request.get("runtime_mode") != "continuous"):
        raise ValueError("private continuous request profile is malformed")
    for group, kind in zip(groups, ("sound", "audio_fx", "midi_fx", "mod")):
        ids = request[group]
        if (not isinstance(ids, list) or len(ids) > 128 or (group == "engines" and not ids)
                or any(type(item) is not str or item.startswith("test-")
                       or module_kinds.get(item) != kind for item in ids)
                or len(set(ids)) != len(ids)):
            raise ValueError("private continuous selection differs from production catalogue groups")
    ids = request["project_ids"]
    index = request["startup_index"]
    sets = request.get("set_ids", [])
    if (not isinstance(ids, list) or not 1 <= len(ids) <= 8
            or any(type(item) is not str or item not in projects for item in ids)
            or len(set(ids)) != len(ids) or type(index) is not int or not 0 <= index < len(ids)
            or not isinstance(sets, list) or len(sets) > 8
            or any(type(item) is not str or set_parents.get(item) != ids[index] for item in sets)
            or len(set(sets)) != len(sets)):
        raise ValueError("private continuous content selection is malformed")


def validate_image_receipt(receipt, selected):
    builder, identity, runtime = _helpers()
    for field, expected in {
        "flash_layout": "expanded-d7000", "app_budget_bytes": 860644,
        "wavetable_profile": builder.SHAPES8_WAVETABLE_PROFILE,
        "shapes_voices": 8, "indexed_tft": True, "flash_plaits_wavetables": False,
        "runtime_configuration": runtime("continuous"),
        "firmware_identity": identity("FM-1_500"),
        "native_midi_input": builder.native_midi_input_configuration(True),
    }.items():
        _expect(receipt.get(field), expected, field)
    if (type(receipt.get("app_bytes")) is not int
            or not 0 < receipt["app_bytes"] <= 860644):
        raise ValueError("private continuous application size is unmeasured or over budget")
    if not isinstance(selected, list) or any(type(item) is not str for item in selected):
        raise ValueError("private continuous module selection is malformed")
    builder.checked_continuous_configuration(receipt)
    checked = builder.checked_wavetable_profile(receipt, selected,
        target_storage=builder.CONTINUOUS_TARGET_STORAGE, selected_shapes8=True)
    expected_rows = [dict(row) for row in builder.SHAPES8_TABLES
                     if row["namespace"] in builder.wavetable_namespaces(selected, flash_plaits=False)]
    _expect(checked["compressed_wave_tables"], expected_rows, "compressed_wave_tables")


def validate_receipt(receipt):
    """Validate lower link evidence; exact request/content binding is separate."""
    if not isinstance(receipt, dict):
        raise ValueError("private continuous build receipt is malformed")
    builder, identity, runtime = _helpers()
    selected = (receipt.get("module_selection") or {}).get("selected")
    if (not isinstance(selected, list) or not selected
            or any(type(item) is not str or item.startswith("test-") for item in selected)
            or len(set(selected)) != len(selected)):
        raise ValueError("private continuous module selection is malformed")
    for field, expected in {
        "flash_layout": "expanded-d7000", "app_budget_bytes": 860644,
        "shapes_voices": 8, "indexed_tft": True, "flash_plaits_wavetables": False,
        "runtime_configuration": runtime("continuous"),
        "probe_return_to_rom_seconds": None,
        "firmware_identity": identity("FM-1_500"),
        "flash_write_range": "empty", "boot_ota_cleanup": False,
        "installable": False, "hardware_tested": False, "hardware_candidate": False,
        "catalogue_source_freshness_verified": True,
        "project_save_service": {
            "compile_definition": "LUNAR_PROJECT_SAVE_SERVICE=1", "flash_io_bound": False,
            "hardware_tested": False, "linked": True, "runtime_verified": False,
            "save_service_armed": False, "storage_admitted": False},
    }.items():
        _expect(receipt.get(field), expected, field)
    builder.checked_continuous_midi_input(receipt)
    checked = builder.checked_wavetable_profile(receipt, selected,
        target_storage=builder.CONTINUOUS_TARGET_STORAGE, selected_shapes8=True)
    _expect(checked["compressed_wave_tables"], [dict(row) for row in builder.SHAPES8_TABLES
        if row["namespace"] in builder.wavetable_namespaces(selected, flash_plaits=False)],
        "compressed_wave_tables")
    builder.checked_continuous_configuration(receipt)


def evidence_manifest(build_receipt_raw):
    if not isinstance(build_receipt_raw, bytes) or not build_receipt_raw:
        raise ValueError("private continuous build receipt is missing")
    return canonical({"schema": 1, "profile_id": PROFILE_ID,
                      "profile_sha256": profile_sha256(),
                      "build_receipt_sha256": hashlib.sha256(build_receipt_raw).hexdigest()})
