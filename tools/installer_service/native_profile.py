# SPDX-License-Identifier: MIT
"""Versioned contract for the private Hall-O2 native diagnostic build."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

PROFILE_ID = "fm1-500-d7000-hall-o2-stage7-v1"
PROFILE_SCHEMA = 1

PROFILE_CONTRACT = {
    "schema": PROFILE_SCHEMA,
    "profile_id": PROFILE_ID,
    "firmware_identity": "FM-1_500",
    "flash_layout": "expanded-d7000",
    "runtime_mode": "song-diagnostic",
    "required_caller_selected_modules": ["drums", "hall", "macro", "sixop"],
    "return_to_rom_seconds": 120,
    "shapes_voices": 8,
    "indexed_tft": True,
    "flash_plaits_wavetables": False,
    "catalogue_optimization_overrides": {
        "our/src/fx_hall.o": "-O2",
        "our/src/mi_sixop.o": "-Os",
    },
    "native_midi_input": {"transport": "UART1-RX/PH8", "ring_bytes": 256,
                           "bytes_per_poll": 32, "usb_midi_preserved": True},
    "diagnostic_telemetry": {"transport": "USB-MIDI-SysEx", "interval_ms": 1000},
    "render_stage_profile_stages": [
        "sequence_dispatch", "sound_0", "sound_1", "sound_2", "sound_3",
        "master_fx_0", "master_fx_1", "postmix", "display_strip",
    ],
    "hot_dsp_ram_bodies": [
        "SixOp::Instance::Render", "SixOp::Instance::RenderBlock",
        "plaits::FMVoice::Render", "plaits::fm::Voice<6>::Render(Parameters,float**,size_t)",
        "Hall::Instance::Render", "Limiter::HoldStep", "Limiter::BoxStep",
        "Limiter::TapOut", "Limiter::Render", "fm1_app_render",
        "fm1_resampler_push_ready_", "Drums::Instance::Render",
        "Drums::Instance::RenderBlock", "Drums::Instance::RenderVoice",
    ],
    "diagnostic_schemas": {"render_stage": 2, "engine_render": 7,
                            "clock": 3, "clock_supplemental": 4},
    "diagnostic_song_play_enabled": False,
    "project_save_service_armed": False,
    "excluded_profiles": ["diagnostic_cpu_rate", "diagnostic_producer_gaps",
                          "diagnostic_irq_profile"],
    "installable": False,
    "hardware_admitted": False,
    "hardware_tested": False,
}


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")


def profile_sha256() -> str:
    return hashlib.sha256(canonical(PROFILE_CONTRACT)).hexdigest()


def _expect(actual, expected, field: str) -> None:
    if canonical(actual) != canonical(expected):
        raise ValueError("native diagnostic profile receipt mismatch: " + field)


def validate_receipt(receipt: dict) -> None:
    """Require the exact reviewed target tuple while leaving content caller-owned."""
    if not isinstance(receipt, dict):
        raise ValueError("native diagnostic profile receipt is malformed")
    native_tools = str(Path(__file__).resolve().parents[1] / "native")
    if native_tools not in sys.path:
        sys.path.insert(0, native_tools)
    from build_demo_image import (BASE_INSTANCE_POOL_BYTES, SHAPES8_TABLES,
                                  TARGET_STORAGE)
    expected = {
        "flash_layout": "expanded-d7000", "app_budget_bytes": 860644,
        "shapes_voices": 8, "indexed_tft": True,
        "flash_plaits_wavetables": False,
        "target_app_storage": TARGET_STORAGE,
        "compressed_wave_tables": [dict(row) for row in SHAPES8_TABLES],
        "instance_pool_bytes": BASE_INSTANCE_POOL_BYTES + TARGET_STORAGE["pool_credit_bytes"]
            - sum(row["raw_bytes"] for row in SHAPES8_TABLES),
        "runtime_configuration": {
            "runtime_mode": "song-diagnostic", "return_to_rom_seconds": 120,
            "define": "-DLUNAR_RETURN_TO_ROM_SECONDS=120", "release_accepted": False,
        },
        "firmware_identity": {
            "application_identity": "FM-1_500", "explicit": True,
            "hardware_identity_verified": False, "package_identity_verified": False,
            "recovery_identity": "FM-1_000", "updater_acceptance_verified": False,
        },
        "native_midi_input": {
            "bytes_per_poll": 32, "compile_definition": "LUNAR_UART1_MIDI=1",
            "diagnostic_counters": ["usb_messages_drained", "uart_bytes_processed",
                                    "accepted_note_ons", "rejected_messages"],
            "enabled": True, "hardware_tested": False, "ring_bytes": 256,
            "transport": "UART1-RX/PH8", "usb_midi_preserved": True,
        },
        "diagnostic_telemetry": {
            "compile_definition": "LUNAR_DIAGNOSTIC_TELEMETRY=1", "enabled": True,
            "hardware_tested": False, "interval_ms": 1000,
            "transport": "USB-MIDI-SysEx",
        },
        "render_stage_profile": {
            "compile_definition": "LUNAR_RENDER_STAGE_PROFILE=1", "enabled": True,
            "hardware_tested": False, "schema": 2,
            "stages": ["sequence_dispatch", "sound_0", "sound_1", "sound_2",
                       "sound_3", "master_fx_0", "master_fx_1", "postmix",
                       "display_strip"],
        },
        "diagnostic_engine_render_profile": {
            "compile_definition": "LUNAR_DIAGNOSTIC_ENGINE_RENDER_PROFILE=1",
            "counter_semantics": "cumulative-uint32-device-timer-ticks",
            "counters": ["uptime_ms", "drums_render_ticks", "drums_render_calls",
                         "drums_render_block_ticks", "drums_render_block_calls",
                         "sixop_render_ticks", "sixop_render_calls",
                         "sixop_render_block_ticks", "sixop_render_block_calls"],
            "enabled": True, "frame_bytes": 54, "hardware_tested": False,
            "packets_per_frame": 18, "schema": 7,
        },
        "diagnostic_clock_snapshot": {
            "compile_definition": "LUNAR_DIAGNOSTIC_CLOCK_SNAPSHOT=1",
            "enabled": True, "frequency_interpreted": False,
            "hardware_tested": False, "register_writes": False,
            "sample": "post-platform-init", "schema": 3,
            "supplemental_frequency_interpreted": False,
            "supplemental_register_addresses": ["0x119a0", "0x119a8", "0x119ac"],
            "supplemental_registers": ["pll_osc_selector_raw", "pll_predivider_raw",
                                       "pll_multiplier_raw"],
            "supplemental_schema": 4,
        },
        "catalogue_optimization_overrides": PROFILE_CONTRACT["catalogue_optimization_overrides"],
        "catalogue_limiter_os": False, "catalogue_hall_o2": True,
        "catalogue_source_freshness_verified": True,
        "boot_ota_cleanup": False,
        "diagnostic_song_play": {"compile_definition": None, "enabled": False,
                                  "hardware_tested": False, "once": False, "start_ms": None},
        "project_save_service": {
            "compile_definition": "LUNAR_PROJECT_SAVE_SERVICE=1", "flash_io_bound": False,
            "hardware_tested": False, "linked": True, "runtime_verified": False,
            "save_service_armed": False, "storage_admitted": False,
        },
    }
    for field, value in expected.items():
        _expect(receipt.get(field), value, field)
    for field in ("diagnostic_cpu_rate", "diagnostic_producer_gaps", "diagnostic_irq_profile"):
        _expect(receipt.get(field), None, field)
    _expect(receipt.get("installable"), False, "installable")
    _expect(receipt.get("hardware_tested"), False, "hardware_tested")
    _expect(receipt.get("hardware_candidate"), False, "hardware_candidate")
    overrides = PROFILE_CONTRACT["catalogue_optimization_overrides"]
    selection = receipt.get("module_selection")
    selected = selection.get("selected") if isinstance(selection, dict) else None
    required_modules = set(PROFILE_CONTRACT["required_caller_selected_modules"])
    if not isinstance(selected, list) or not required_modules.issubset(set(selected)):
        raise ValueError("native diagnostic profile caller selection is outside the matched profile")
    rows = receipt.get("catalogue_objects")
    if not isinstance(rows, list):
        raise ValueError("native diagnostic profile catalogue inventory is missing")
    for suffix, optimization in overrides.items():
        matches = [row for row in rows if isinstance(row, dict)
                   and isinstance(row.get("path"), str)
                   and row["path"].endswith("/" + suffix)]
        if len(matches) != 1 or matches[0].get("optimization") != optimization:
            raise ValueError("native diagnostic profile catalogue optimization mismatch: " + suffix)
    ram = receipt.get("hot_dsp_ram")
    if (not isinstance(ram, dict) or ram.get("enabled") is not True
            or ram.get("selected_bodies") != PROFILE_CONTRACT["hot_dsp_ram_bodies"]):
        raise ValueError("native diagnostic profile hot DSP RAM selection mismatch")


def evidence_manifest(build_receipt_raw: bytes) -> bytes:
    """Bind the immutable contract identity to the exact raw build-receipt bytes."""
    if not isinstance(build_receipt_raw, bytes) or not build_receipt_raw:
        raise ValueError("native diagnostic profile build receipt is missing")
    return canonical({"schema": 1, "profile_id": PROFILE_ID,
                     "profile_sha256": profile_sha256(),
                     "build_receipt_sha256": hashlib.sha256(build_receipt_raw).hexdigest()})
