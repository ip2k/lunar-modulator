#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Private, offline policy for one externally pinned D7000 Trio diagnostic.

This module creates transaction artifacts and an injected-only command policy.
It has no USB/SG opener, loader/reset command, package emitter, or admission path.
The build/source pins are external attestations, not a hardware or provenance
claim made by this module.
"""
from dataclasses import dataclass
import hashlib
import math
import os
import stat
import json
import re
from pathlib import Path
import sys
from weakref import WeakSet

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "jieli"))

import event120_generic_boot as generic_boot
import expanded_candidate
import expanded_flash_profile as expanded
import raw_flash_profile as raw
from fm1_bound_diagnostic import BoundDiagnosticSession, _VALIDATED
from fm1_flash_transaction import (create_transaction, digest, encoded,
                                   load_transaction, checked_plan_order, checked_identity,
                                   mkdir_durable, save_new, sync_directory, check_outside)

KIND = "lunar-private-d7000-trio-diagnostic-plan"
INPUT_KIND = "lunar-private-d7000-trio-diagnostic-input"
SONG_KIND = "lunar-private-d7000-event-horizon-set-diagnostic-plan"
SONG_INPUT_KIND = "lunar-private-d7000-event-horizon-set-diagnostic-input"
FLASH_BYTES, SECTOR, APP_BASE = raw.FLASH_BYTES, 4096, raw.APP_BASE
CURRENT_END, TARGET_END = 0xD9000, 0xD7000
SOUND_IDS = ("macro", "shapes", "macro-heavy", "sixop", "dx7", "sw-sophie",
             "drums", "acid-bass", "comet", "crater", "drawbar", "trio",
             "phase-bend")
EVENT_HORIZON_ID = "replacement-showcase-candidate-event-horizon"
EVENT_HORIZON_SET_ID = "replacement-showcase-event-horizon-companion-set"
_POLICIES = WeakSet()
_RESUMES = WeakSet()
_USED_RESUMES = WeakSet()
RESUME_SESSION_SECONDS = 1800
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")


def _json(path, expected_sha, limit):
    path = Path(path).resolve()
    data = path.read_bytes()
    if len(data) > limit or digest(data) != expected_sha:
        raise ValueError("Pinned evidence bytes differ: " + path.name)
    def unique(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError("Duplicate JSON key")
            out[k] = v
        return out
    return json.loads(data, object_pairs_hook=unique), data


def _file(path, sha, size=None):
    path = Path(path).resolve()
    data = path.read_bytes()
    if (size is not None and len(data) != size) or digest(data) != sha:
        raise ValueError("Pinned file differs: " + path.name)
    return data


def _valid_sha(value, pattern=_HEX64):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _unique_json(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("Duplicate JSON key")
        out[key] = value
    return out


def _validate_event_horizon_set_profile(build, verification, prepared_raw):
    """Bind EH+SET startup identity to the prepared bytes and linked report."""
    try:
        profile = json.loads(prepared_raw, object_pairs_hook=_unique_json)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Prepared song profile is not valid JSON") from error
    if not isinstance(profile, dict):
        raise ValueError("Prepared song profile is malformed")
    profile_assets = profile.get("content")
    module_selection = profile.get("module_selection")
    if (type(profile.get("version")) is not int or profile.get("version") != 1
            or profile.get("installable") is not False
            or profile.get("native_link_verified") is not False
            or profile.get("native_ram_verified") is not False
            or profile.get("hardware_tested") is not False
            or not isinstance(module_selection, dict)
            or not isinstance(module_selection.get("selected"), list)
            or profile.get("module_selection") != verification.get("module_selection")):
        raise ValueError("Prepared profile module/admission receipt differs from the linked build")
    if (not isinstance(profile_assets, list) or len(profile_assets) != 2
            or type(profile.get("packed_content_bytes")) is not int):
        raise ValueError("Song diagnostic requires exactly one project and one SET")
    project, companion = profile_assets
    if (not isinstance(project, dict) or not isinstance(companion, dict)
            or project.get("kind") != "project" or companion.get("kind") != "set"
            or project.get("source") != "projects/" + EVENT_HORIZON_ID + ".lunar"
            or companion.get("source") != "sets/" + EVENT_HORIZON_SET_ID + ".movy1"):
        raise ValueError("Prepared content is not the exact Event Horizon project/SET pair")
    selected_modules = set(module_selection["selected"])
    for index, asset in enumerate(profile_assets):
        if (not _valid_sha(asset.get("source_sha256"))
                or not _valid_sha(asset.get("packed_sha256"))
                or type(asset.get("bytes")) is not int or asset["bytes"] <= 0
                or asset.get("packed") != f"content-{index:02d}.bin"
                or asset.get("sequence_semantics_verified") is not False
                or not isinstance(asset.get("dependencies"), list)
                or any(not isinstance(dep, str) for dep in asset["dependencies"])
                or not set(asset["dependencies"]).issubset(selected_modules)):
            raise ValueError("Prepared song asset hashes, length or admission flags differ")
    if project.get("dependency_scan_complete") is not True or companion.get("dependency_scan_complete") is not False:
        raise ValueError("Prepared project/SET dependency-scan contract differs")

    verification_assets = [
        {"kind": row["kind"], "bytes": row["bytes"], "packed_sha256": row["packed_sha256"]}
        for row in profile_assets
    ]
    packed_bytes = sum(row["bytes"] for row in profile_assets)
    if profile["packed_content_bytes"] != packed_bytes:
        raise ValueError("Prepared profile packed-content total differs")
    embedded = verification.get("embedded_content")
    if (not isinstance(embedded, dict)
            or embedded.get("prepared_sha256") != build["prepared_profile_sha256"]
            or embedded.get("asset_count") != 2
            or embedded.get("packed_content_bytes") != packed_bytes
            or embedded.get("packed_sha256") != [row["packed_sha256"] for row in verification_assets]
            or embedded.get("assets") != verification_assets
            or embedded.get("sequence_semantics_verified") is not False
            or embedded.get("native_playback_verified") is not False):
        raise ValueError("Linked content receipt differs from the exact prepared profile")

    startup = verification.get("startup_project")
    if (not isinstance(startup, dict) or type(startup.get("index")) is not int
            or startup["index"] != 0 or startup.get("runtime_hook_linked") is not False
            or startup.get("staging_reclaimed_before_engine_allocation") is not True
            or startup.get("failure_returns_to_recovery") is not True
            or startup.get("runtime_verified") is not False
            or startup.get("hardware_tested") is not False):
        raise ValueError("Event Horizon startup index or admission receipt differs")

    companion_receipt = verification.get("companion_set_selection")
    selection_path = Path(build["prepared_profile_path"]).resolve().parent.parent / "selection.json"
    if not isinstance(companion_receipt, dict):
        raise ValueError("Companion SET selection receipt is missing")
    selection, selection_raw = _json(
        selection_path, companion_receipt.get("selection_receipt_sha256"), 1024 * 1024)
    if not isinstance(selection, dict):
        raise ValueError("Companion selection receipt is malformed")
    content = selection.get("content")
    selected = selection.get("selected_content")
    if (type(selection.get("version")) is not int or selection.get("version") != 1
            or selection.get("status") != "prepared-build-inputs"
            or selection.get("prepared_profile_sha256") != build["prepared_profile_sha256"]
            or selection.get("project_ids") != [EVENT_HORIZON_ID]
            or selection.get("startup_index") != 0
            or selection.get("startup_project_id") != EVENT_HORIZON_ID
            or selection.get("set_ids") != [EVENT_HORIZON_SET_ID]
            or selected != [{"kind": "project", "id": EVENT_HORIZON_ID},
                            {"kind": "set", "id": EVENT_HORIZON_SET_ID,
                             "parent_project_id": EVENT_HORIZON_ID}]
            or not isinstance(content, list) or len(content) != 2):
        raise ValueError("Hash-pinned selection receipt is not the exact EH+SET startup")
    for index, (prepared, selected_asset) in enumerate(zip(profile_assets, content)):
        expected_id = EVENT_HORIZON_ID if index == 0 else EVENT_HORIZON_SET_ID
        if (not isinstance(selected_asset, dict) or selected_asset.get("id") != expected_id
                or selected_asset.get("kind") != prepared.get("kind")
                or selected_asset.get("source") != prepared.get("source")
                or selected_asset.get("source_sha256") != prepared.get("source_sha256")
                or selected_asset.get("packed") != prepared.get("packed")
                or selected_asset.get("packed_sha256") != prepared.get("packed_sha256")
                or selected_asset.get("bytes") != prepared.get("bytes")):
            raise ValueError("Selection receipt asset identity differs from prepared profile")
    if content[1].get("parent_project_id") != EVENT_HORIZON_ID:
        raise ValueError("Companion SET parent differs from selected startup project")
    if selection.get("packed_content_bytes") != packed_bytes:
        raise ValueError("Selection receipt packed-content total differs")
    if companion_receipt != {
            "enabled": True,
            "selection_receipt_sha256": digest(selection_raw),
            "parent_project_index": 0,
            "set_indices": [1],
            "before_audio_init": True,
            "timeout_keeps_project_sequence": True,
            "runtime_verified": False,
            "sequence_semantics_verified": False,
            "hardware_tested": False}:
        raise ValueError("Companion SET selection report differs from the bound profile")
    project_loader = verification.get("project_loader")
    project_linked = ("modulation_staging_link_verified", "sequence_staging_link_verified",
                      "engine_staging_link_verified", "engine_parameter_link_verified",
                      "audio_adoption_link_verified", "midi_restore_link_verified",
                      "scalar_restore_link_verified", "dx7_restore_link_verified",
                      "modulation_adoption_link_verified", "modulation_restore_link_verified",
                      "startup_composition_link_verified", "view_restore_link_verified")
    set_loader = verification.get("set_loader")
    if (not isinstance(project_loader, dict)
            or any(project_loader.get(key) is not True for key in project_linked)
            or any(project_loader.get(key) is not False for key in
                   ("activated", "stack_margin_verified", "timing_verified",
                    "hardware_tested", "sequence_semantics_verified"))
            or not isinstance(set_loader, dict)
            or set_loader.get("native_link_verified") is not True
            or set_loader.get("activation_api_link_verified") is not True
            or any(set_loader.get(key) is not False for key in
                   ("activated", "stack_margin_verified", "hardware_tested",
                    "sequence_semantics_verified"))):
        raise ValueError("Native project/SET loader link or admission receipts differ")
    # The combined project+SET path is represented by startup_project plus
    # companion_set_selection. `startup_set` describes standalone SET startup,
    # which the builder does not emit for a project startup and must not be
    # accepted as a substitute for the parent-bound companion selection.
    if "startup_set" in verification:
        raise ValueError("Standalone SET startup receipt is incompatible with EH+SET startup")
    for flag in ("installable", "native_link_verified", "native_ram_verified", "hardware_tested"):
        if selection.get(flag) is not False:
            raise ValueError("Selection receipt has an invalid admission flag: " + flag)
    return {"project_id": EVENT_HORIZON_ID, "set_id": EVENT_HORIZON_SET_ID,
            "startup_project_index": 0,
            "startup_set_index": companion_receipt["set_indices"][0],
            "selection_path": selection_path, "selection_raw": selection_raw,
            "selection_receipt_sha256": digest(selection_raw),
            "asset_count": 2, "packed_content_bytes": packed_bytes}


def _transition(stock, current, target):
    """Derive exact sectors for stock-derived D7000 target over live D9000."""
    if any(not isinstance(x, bytes) or len(x) != FLASH_BYTES
           for x in (stock, current, target)):
        raise ValueError("Three complete raw NOR images required")
    if target[:APP_BASE] != current[:APP_BASE]:
        raise ValueError("Boot prefix differs from the freshly read current image")
    if target[CURRENT_END:] != current[CURRENT_END:]:
        raise ValueError("D9000-and-above suffix differs from the current image")
    if target[TARGET_END:CURRENT_END] != stock[TARGET_END:CURRENT_END]:
        raise ValueError("Reclaimed D7000-D9000 bytes are not exact stock bytes")
    if current[:APP_BASE] != stock[:APP_BASE] or current[CURRENT_END:] != stock[CURRENT_END:]:
        raise ValueError("Current D9000 image does not retain stock prefix/suffix")
    sectors = [a for a in range(APP_BASE, CURRENT_END, SECTOR)
               if current[a:a + SECTOR] != target[a:a + SECTOR]]
    if not sectors or sectors[0] != APP_BASE:
        raise ValueError("Changed app-directory sector must be included")
    ranges = [[a, a + SECTOR] for a in sectors]
    order = [a for a in sectors if a != APP_BASE] + [APP_BASE]
    return ranges, sectors, order


def _exact_producer_gap_receipt(value):
    expected = {
        "enabled": True, "schema": 5,
        "compile_definition": "LUNAR_DIAGNOSTIC_PRODUCER_GAPS=1",
        "frame_bytes": 59, "packets_per_frame": 20,
        "transport": "USB-MIDI-SysEx", "hardware_tested": False,
    }
    return (isinstance(value, dict) and set(value) == set(expected)
            and type(value.get("enabled")) is bool
            and type(value.get("schema")) is int
            and type(value.get("frame_bytes")) is int
            and type(value.get("packets_per_frame")) is int
            and type(value.get("hardware_tested")) is bool
            and value == expected)


def _exact_irq_profile_receipt(value):
    expected = {
        "enabled": True, "schema": 6,
        "compile_definition": "LUNAR_DIAGNOSTIC_IRQ_PROFILE=1",
        "frame_bytes": 119, "packets_per_frame": 40,
        "transport": "USB-MIDI-SysEx", "hardware_tested": False,
    }
    return (isinstance(value, dict) and set(value) == set(expected)
            and type(value.get("enabled")) is bool
            and type(value.get("schema")) is int
            and type(value.get("frame_bytes")) is int
            and type(value.get("packets_per_frame")) is int
            and type(value.get("hardware_tested")) is bool
            and value == expected)


def _exact_render_stage_profile_receipt(value):
    expected = {
        "enabled": True, "compile_definition": "LUNAR_RENDER_STAGE_PROFILE=1",
        "schema": 2,
        "stages": ["sequence_dispatch", "sound_0", "sound_1", "sound_2",
                   "sound_3", "master_fx_0", "master_fx_1", "postmix",
                   "display_strip"],
        "hardware_tested": False,
    }
    return (isinstance(value, dict) and set(value) == set(expected)
            and type(value.get("enabled")) is bool
            and type(value.get("schema")) is int
            and type(value.get("hardware_tested")) is bool
            and isinstance(value.get("compile_definition"), str)
            and isinstance(value.get("stages"), list)
            and all(isinstance(stage, str) for stage in value["stages"])
            and value == expected)


def _exact_engine_render_profile_receipt(value):
    expected = {
        "enabled": True, "schema": 7,
        "compile_definition": "LUNAR_DIAGNOSTIC_ENGINE_RENDER_PROFILE=1",
        "frame_bytes": 54, "packets_per_frame": 18,
        "counters": ["uptime_ms", "drums_render_ticks", "drums_render_calls",
                     "drums_render_block_ticks", "drums_render_block_calls",
                     "sixop_render_ticks", "sixop_render_calls",
                     "sixop_render_block_ticks", "sixop_render_block_calls"],
        "counter_semantics": "cumulative-uint32-device-timer-ticks",
        "hardware_tested": False,
    }
    return (isinstance(value, dict) and set(value) == set(expected)
            and type(value.get("enabled")) is bool
            and type(value.get("schema")) is int
            and type(value.get("frame_bytes")) is int
            and type(value.get("packets_per_frame")) is int
            and type(value.get("hardware_tested")) is bool
            and isinstance(value.get("compile_definition"), str)
            and isinstance(value.get("counters"), list)
            and all(isinstance(counter, str) for counter in value["counters"])
            and isinstance(value.get("counter_semantics"), str)
            and value == expected)


def _exact_clock_snapshot_receipt(value):
    expected = {
        "enabled": True, "schema": 3, "supplemental_schema": 4,
        "supplemental_registers": ["pll_osc_selector_raw", "pll_predivider_raw",
                                   "pll_multiplier_raw"],
        "supplemental_register_addresses": ["0x119a0", "0x119a8", "0x119ac"],
        "supplemental_frequency_interpreted": False,
        "compile_definition": "LUNAR_DIAGNOSTIC_CLOCK_SNAPSHOT=1",
        "sample": "post-platform-init", "register_writes": False,
        "frequency_interpreted": False, "hardware_tested": False,
    }
    return (isinstance(value, dict) and set(value) == set(expected)
            and type(value.get("enabled")) is bool
            and type(value.get("schema")) is int
            and type(value.get("supplemental_schema")) is int
            and type(value.get("supplemental_frequency_interpreted")) is bool
            and type(value.get("register_writes")) is bool
            and type(value.get("frequency_interpreted")) is bool
            and type(value.get("hardware_tested")) is bool
            and value == expected)


def _exact_song_play_receipt(value, enabled):
    expected = {
        "enabled": enabled,
        "compile_definition": "LUNAR_DIAGNOSTIC_SONG_PLAY=1" if enabled else None,
        "start_ms": 2000 if enabled else None,
        "once": enabled,
        "hardware_tested": False,
    }
    return (isinstance(value, dict) and set(value) == set(expected)
            and type(value.get("enabled")) is bool
            and type(value.get("once")) is bool
            and type(value.get("hardware_tested")) is bool
            and (value.get("start_ms") is None or type(value.get("start_ms")) is int)
            and value == expected)


def _exact_cpu_rate_receipt(value):
    expected = {
        "enabled": True, "schema": 8,
        "compile_definition": "LUNAR_DIAGNOSTIC_CPU_RATE=1",
        "frame_bytes": 49, "packets_per_frame": 17,
        "kernel": "fixed integer workload in XIP and .ram_text",
        "iterations_per_trial": 4096, "trials_per_kernel": 4,
        "timing": "raw TIMER4 ticks; no CPU frequency interpretation",
        "starts": "post-recovery, pre-platform flash probe",
        "register_writes": False, "hardware_tested": False,
    }
    return (isinstance(value, dict) and set(value) == set(expected)
            and all(type(value[key]) is type(want) and value[key] == want
                    for key, want in expected.items()))


def _validate_diagnostic_mode(record, build, verification, prepared_profile):
    """Select one exact diagnostic contract without broadening the pulse path."""
    profile_kind = record.get("kind")
    pulse = verification.get("diagnostic_trio_pulse")
    if profile_kind == INPUT_KIND:
        if ("diagnostic_producer_gaps" in verification or
                "diagnostic_irq_profile" in verification or
                "diagnostic_engine_render_profile" in verification or
                "diagnostic_cpu_rate" in verification):
            raise ValueError("Song-only timing telemetry is only valid for the EH+SET song profile")
        if pulse != {"enabled": True, "compile_definition": "LUNAR_DIAGNOSTIC_TRIO_PULSE=1",
                     "note": 60, "velocity": 100, "start_ms": 3000, "end_ms": 5000,
                     "once": True, "hardware_tested": False}:
            raise ValueError("Exact non-repeating Trio diagnostic pulse required")
        return None
    if profile_kind != SONG_INPUT_KIND:
        raise ValueError("Unknown private diagnostic profile kind")
    if pulse != {"enabled": False, "compile_definition": None, "note": None,
                 "velocity": None, "start_ms": None, "end_ms": None,
                 "once": True, "hardware_tested": False}:
        raise ValueError("EH+SET song diagnostics must explicitly disable the Trio pulse")
    if verification.get("diagnostic_telemetry") != {
            "enabled": True, "compile_definition": "LUNAR_DIAGNOSTIC_TELEMETRY=1",
            "interval_ms": 1000, "transport": "USB-MIDI-SysEx", "hardware_tested": False}:
        raise ValueError("EH+SET diagnostic telemetry must be enabled")
    if "diagnostic_cpu_rate" in verification:
        if (not _exact_cpu_rate_receipt(verification["diagnostic_cpu_rate"])
                or not _exact_song_play_receipt(verification.get("diagnostic_song_play"), False)
                or any(key in verification for key in (
                    "diagnostic_producer_gaps", "diagnostic_irq_profile",
                    "diagnostic_engine_render_profile", "render_stage_profile"))
                or ("diagnostic_clock_snapshot" in verification and not
                    _exact_clock_snapshot_receipt(verification["diagnostic_clock_snapshot"]))):
            raise ValueError("Exact standalone CPU-rate diagnostic with playback disabled required")
        return _validate_event_horizon_set_profile(build, verification, prepared_profile)
    if ("diagnostic_producer_gaps" in verification
            and not _exact_producer_gap_receipt(verification["diagnostic_producer_gaps"])):
        raise ValueError("EH+SET producer-gap telemetry receipt differs")
    if ("diagnostic_irq_profile" in verification
            and not _exact_irq_profile_receipt(verification["diagnostic_irq_profile"])):
        raise ValueError("EH+SET IRQ profile telemetry receipt differs")
    engine_profile_present = "diagnostic_engine_render_profile" in verification
    if engine_profile_present:
        if not _exact_engine_render_profile_receipt(
                verification["diagnostic_engine_render_profile"]):
            raise ValueError("EH+SET engine render profile receipt differs")
        if "diagnostic_producer_gaps" in verification or "diagnostic_irq_profile" in verification:
            raise ValueError("Engine render profiling cannot share producer-gap or IRQ cadence")
        if not _exact_render_stage_profile_receipt(verification.get("render_stage_profile")):
            raise ValueError("Engine render profiling requires the exact schema-2 render-stage receipt")
        # With both profiles enabled, the bounded four-slot scheduler emits
        # schema-2 stage frames about every four seconds (the default two-slot
        # stage cadence is about every two seconds). Keep cadence visible to
        # policy reviewers; do not treat this opt-in as a one-second stream.
    song_play = verification.get("diagnostic_song_play")
    if _exact_song_play_receipt(song_play, True):
        pass
    elif ("diagnostic_irq_profile" in verification
          and "diagnostic_producer_gaps" not in verification
          and _exact_irq_profile_receipt(verification["diagnostic_irq_profile"])
          and _exact_song_play_receipt(song_play, False)):
        pass
    elif (engine_profile_present
          and _exact_song_play_receipt(song_play, False)):
        # Schema-7 engine profiling is a separate bounded, no-autoplay mode.
        # Its exact schema-2 stage receipt and exclusion of IRQ/producer-gap
        # profiles were checked above; do not broaden this exception to other
        # disabled-song receipts.
        pass
    elif (not engine_profile_present
          and "render_stage_profile" not in verification
          and "diagnostic_irq_profile" not in verification
          and "diagnostic_producer_gaps" not in verification
          and _exact_clock_snapshot_receipt(verification.get("diagnostic_clock_snapshot"))
          and _exact_song_play_receipt(song_play, False)):
        # Standard telemetry with clock snapshots has no autoplay and no
        # render-profiler slots. Keep both profiling receipts absent: this is
        # the matched profiler-off measurement profile.
        pass
    else:
        raise ValueError("EH+SET diagnostic playback must be the bounded one-shot PLAY profile")
    return _validate_event_horizon_set_profile(build, verification, prepared_profile)


def _check_build(record, app, elf, disassembly):
    source = record.get("source")
    build = record.get("build")
    source_keys = {"commit", "tree_sha256"}
    build_keys = {
        "frozen_receipt_path", "frozen_receipt_sha256",
        "verification_path", "verification_sha256", "artifact_path", "artifact_sha256",
        "app_path", "app_sha256", "elf_path", "elf_sha256", "disassembly_path",
        "disassembly_sha256", "prepared_profile_path", "prepared_profile_sha256",
        "source_commit", "source_tree_sha256", "source_snapshot_path",
        "source_snapshot_sha256", "toolchain_tree_sha256", "toolchain_snapshot_path",
        "toolchain_snapshot_sha256", "toolchain_image_id", "catalogue_snapshot_path",
        "catalogue_snapshot_sha256", "catalogue_tree_sha256"}
    if (not isinstance(source, dict) or set(source) != source_keys or
            not _valid_sha(source.get("commit"), _HEX40) or
            not _valid_sha(source.get("tree_sha256"), _HEX40)):
        raise ValueError("Exact source commit and source-tree pins required")
    if not isinstance(build, dict) or set(build) != build_keys:
        raise ValueError("Exact frozen build receipt and output pins required")
    frozen, frozen_raw = _json(build["frozen_receipt_path"],
                               build["frozen_receipt_sha256"], 256 * 1024)
    if (frozen.get("schema") != 1 or frozen.get("build_tuple_emitted") is not False or
            frozen.get("image_json_emitted") is not False or
            frozen.get("installable") is not False or frozen.get("hardware_admitted") is not False):
        raise ValueError("Frozen diagnostic build receipt schema or admission flags differ")
    receipt_fields = {
        "source_commit": frozen.get("source_commit"),
        "source_tree_sha256": frozen.get("source_git_tree"),
        "source_snapshot_sha256": frozen.get("source_snapshot_manifest_sha256"),
        "toolchain_tree_sha256": frozen.get("toolchain_source_tree_manifest_sha256"),
        "toolchain_snapshot_sha256": frozen.get("toolchain_snapshot_tree_manifest_sha256"),
        "toolchain_image_id": frozen.get("docker_image_id"),
        "catalogue_snapshot_sha256": frozen.get("catalogue_snapshot_tree_manifest_sha256"),
        "catalogue_tree_sha256": frozen.get("catalogue_source_tree_manifest_sha256"),
        "prepared_profile_sha256": frozen.get("prepared_profile_sha256"),
        "verification_sha256": frozen.get("verification_sha256"),
        "artifact_sha256": frozen.get("artifact_receipt_sha256"),
        "app_sha256": frozen.get("app_sha256"), "elf_sha256": frozen.get("elf_sha256"),
        "disassembly_sha256": frozen.get("disassembly_sha256")}
    if (any(build.get(k) != v for k, v in receipt_fields.items()) or
            build["source_commit"] != source["commit"] or
            build["source_tree_sha256"] != source["tree_sha256"]):
        raise ValueError("External build pins differ from frozen build-input receipt")
    if (not _valid_sha(build["source_snapshot_sha256"]) or
            not _valid_sha(build["toolchain_tree_sha256"]) or
            not _valid_sha(build["toolchain_snapshot_sha256"]) or
            not _valid_sha(build["catalogue_snapshot_sha256"]) or
            not _valid_sha(build["catalogue_tree_sha256"]) or
            not _valid_sha(build["frozen_receipt_sha256"]) or
            not isinstance(build["toolchain_image_id"], str) or
            re.fullmatch(r"sha256:[0-9a-f]{64}", build["toolchain_image_id"]) is None):
        raise ValueError("Build-time source, toolchain, catalogue and image pins required")
    source_snapshot = _file(build["source_snapshot_path"], build["source_snapshot_sha256"])
    toolchain_snapshot = _file(build["toolchain_snapshot_path"], build["toolchain_snapshot_sha256"])
    catalogue_snapshot = _file(build["catalogue_snapshot_path"], build["catalogue_snapshot_sha256"])
    prepared_profile = Path(build["prepared_profile_path"]).read_bytes()
    if (len(prepared_profile) > 1024 * 1024 or
            digest(prepared_profile) != build["prepared_profile_sha256"]):
        raise ValueError("Prepared profile exceeds bound or differs from its pin")
    expected_outputs = {
        "writable-output/build/verification.json": build["verification_sha256"],
        "writable-output/build/artifact/artifact.json": build["artifact_sha256"],
        "writable-output/build/artifact/app.bin": build["app_sha256"],
        "writable-output/build/lunar-app-probe.elf": build["elf_sha256"],
        "writable-output/build/artifact/disassembly.txt": build["disassembly_sha256"]}
    if frozen.get("outputs") != expected_outputs:
        raise ValueError("Frozen receipt output map differs from exact build artifact pins")
    verification, _ = _json(build["verification_path"], build["verification_sha256"], 256 * 1024)
    artifact, _ = _json(build["artifact_path"], build["artifact_sha256"], 64 * 1024)
    if (app != _file(build["app_path"], build["app_sha256"]) or
            elf != _file(build["elf_path"], build["elf_sha256"]) or
            disassembly != _file(build["disassembly_path"], build["disassembly_sha256"])):
        raise ValueError("Build app/ELF/disassembly differ from exact frozen receipt pins")
    if (artifact.get("app_sha256") != digest(app) or artifact.get("app_bytes") != len(app) or
            artifact.get("elf_sha256") != digest(elf) or artifact.get("disassembly_sha256") != digest(disassembly) or
            artifact.get("ram_layout") != "combined" or artifact.get("flash_layout") != "expanded-d7000" or
            artifact.get("layout_passed") is not True or artifact.get("hardware_admitted") is not False or
            artifact.get("hardware_tested") is not False or artifact.get("installable") is not False):
        raise ValueError("Artifact receipt does not describe the pinned non-installable D7000 link")
    modules = verification.get("module_selection")
    if not isinstance(modules, dict) or not isinstance(modules.get("selected"), list):
        raise ValueError("Exact selected module list required")
    catalogue = modules.get("catalogue")
    if not isinstance(catalogue, list):
        raise ValueError("Module catalogue evidence required")
    selected_sounds = [item.get("id") for item in catalogue
                       if isinstance(item, dict) and item.get("kind") == "sound" and item.get("selected") is True]
    if tuple(selected_sounds) != SOUND_IDS:
        raise ValueError("All thirteen expected sound engines must be selected in catalogue order")
    if len(modules["selected"]) != 54 or len(set(modules["selected"])) != 54:
        raise ValueError("Expected exact all-13/54-module link")
    profile_kind = record.get("kind")
    song_profile = _validate_diagnostic_mode(record, build, verification, prepared_profile)
    identity = verification.get("firmware_identity")
    if identity != {"application_identity": "FM-1_500", "explicit": True,
                    "recovery_identity": "FM-1_000", "package_identity_verified": False,
                    "updater_acceptance_verified": False, "hardware_identity_verified": False}:
        raise ValueError("Explicit diagnostic identity or admission flags differ")
    runtime = verification.get("runtime_configuration")
    if not isinstance(runtime, dict) or runtime.get("runtime_mode") != "song-diagnostic" or runtime.get("return_to_rom_seconds") != 120:
        raise ValueError("Bounded diagnostic runtime required")
    save = verification.get("project_save_service")
    if not isinstance(save, dict) or save.get("linked") is not True or any(
            save.get(k) is not False for k in ("storage_admitted", "flash_io_bound", "save_service_armed", "runtime_verified", "hardware_tested")):
        raise ValueError("SAVE must remain linked but fully disarmed/unadmitted")
    embedded = verification.get("embedded_content")
    if profile_kind == INPUT_KIND:
        if (not isinstance(embedded, dict) or embedded.get("asset_count") != 0
                or embedded.get("packed_content_bytes") != 0 or embedded.get("assets") != []):
            raise ValueError("Content-free diagnostic profile required")
    elif not isinstance(embedded, dict):
        raise ValueError("EH+SET linked content receipt is missing")
    if (verification.get("catalogue_source_freshness_verified") is not True or
            verification.get("flash_layout") != "expanded-d7000" or
            verification.get("flash_write_range") != "empty" or
            verification.get("installable") is not False or verification.get("hardware_tested") is not False or
            verification.get("hardware_candidate") is not False):
        raise ValueError("Build freshness/layout/admission contract differs")
    hot_dsp_ram = expanded_candidate.validate_hot_dsp_ram_receipts(
        elf, verification, artifact)
    return verification, artifact, frozen, frozen_raw, song_profile, hot_dsp_ram

def prepare(output, input_record_path, input_record_sha256, *, now=None):
    """Validate exact private artifacts and seal one offline transaction plan.

    input_record_sha256 is an external pin supplied by the coordinator. The
    record contains source/toolchain digests and exact build/read artifacts.
    This function does not discover hardware or open a transport.
    """
    now = generic_boot.time.time() if now is None else now
    record_path = Path(input_record_path).resolve()
    record, record_raw = _json(record_path, input_record_sha256, 256 * 1024)
    expected_keys = {"schema", "kind", "source", "build", "candidate", "stock", "read", "created_at"}
    if (set(record) != expected_keys or type(record.get("schema")) is not int or record["schema"] != 1 or
            record.get("kind") not in (INPUT_KIND, SONG_INPUT_KIND) or
            not isinstance(record.get("created_at"), (int, float)) or
            not 0 <= now - record["created_at"] <= 120):
        raise ValueError("Fresh exact diagnostic input record required")
    candidate = record["candidate"]
    if not isinstance(candidate, dict) or set(candidate) != {"path", "sha256", "receipt_path", "receipt_sha256"}:
        raise ValueError("Exact candidate target and receipt pins required")
    target = _file(candidate["path"], candidate["sha256"], FLASH_BYTES)
    candidate_receipt, _ = _json(candidate["receipt_path"], candidate["receipt_sha256"], 256 * 1024)
    stock_input = record["stock"]
    stock_keys = {"baseline_a_path", "baseline_a_sha256", "baseline_b_path", "baseline_b_sha256",
                  "manifest_path", "manifest_sha256", "identity_path", "identity_sha256",
                  "reference_path", "reference_components"}
    if not isinstance(stock_input, dict) or set(stock_input) != stock_keys:
        raise ValueError("Exact stock provenance evidence required")
    stock_a = Path(stock_input["baseline_a_path"]).read_bytes()
    stock_b = Path(stock_input["baseline_b_path"]).read_bytes()
    if (len(stock_a) != FLASH_BYTES or len(stock_b) != FLASH_BYTES or stock_a != stock_b or
            digest(stock_a) != stock_input["baseline_a_sha256"] or
            digest(stock_b) != stock_input["baseline_b_sha256"]):
        raise ValueError("Two externally pinned matching complete stock baseline images required")
    stock_manifest, stock_manifest_raw = _json(stock_input["manifest_path"], stock_input["manifest_sha256"], 65536)
    stock_identity, stock_identity_raw = _json(stock_input["identity_path"], stock_input["identity_sha256"], 65536)
    reference = Path(stock_input["reference_path"]).resolve()
    components = stock_input["reference_components"]
    component_names = {"top/uboot.boot", "top/isd_config.ini", "files/app.bin",
                       "files/cfg_tool.bin", "files/cfg", "files/cfg-extracted/eq_cfg_hw.bin"}
    if not reference.is_dir() or not isinstance(components, dict) or set(components) != component_names:
        raise ValueError("Exact pinned stock reference components required")
    for name, sha in components.items():
        if not _valid_sha(sha) or digest((reference / name).read_bytes()) != sha:
            raise ValueError("Stock reference component differs from its external pin: " + name)
    read = record["read"]
    read_keys = {"manifest_path", "manifest_sha256", "commands_sha256", "campaign_sha256",
                 "expected_devnum", "current_flash_sha256"}
    if not isinstance(read, dict) or set(read) != read_keys or not _valid_sha(read["current_flash_sha256"]):
        raise ValueError("Fresh paired full-flash read pins required")
    verified_read = generic_boot.verify_read_bundle(
        read["manifest_path"], read["manifest_sha256"], read["commands_sha256"],
        campaign_sha256=read["campaign_sha256"], expected_devnum=read["expected_devnum"],
        expected_flash_sha256=read["current_flash_sha256"], now=now)
    current = _file(verified_read["receipt"] / "dumpA.bin", read["current_flash_sha256"], FLASH_BYTES)
    current_b = _file(verified_read["receipt"] / "dumpB.bin", read["current_flash_sha256"], FLASH_BYTES)
    if current != current_b:
        raise ValueError("Fresh dual reads do not match")
    build = record["build"]
    app = _file(build["app_path"], build["app_sha256"])
    elf = _file(build["elf_path"], build["elf_sha256"])
    disassembly = _file(build["disassembly_path"], build["disassembly_sha256"])
    verification, artifact, frozen, frozen_raw, song_profile, hot_dsp_ram = _check_build(record, app, elf, disassembly)
    rebuilt, expected_candidate_receipt = expanded_candidate.construct(
        stock_a, stock_b, stock_manifest, stock_identity, reference, app, elf,
        "fixed-loader", disassembly.decode("utf-8"), "combined", "expanded-d7000",
        hot_dsp_ram=hot_dsp_ram,
        hot_dsp_ram_receipt=dict(verification=verification, artifact=artifact))
    if (rebuilt != target or candidate_receipt != expected_candidate_receipt or
            candidate_receipt.get("target_sha256") != digest(target)):
        raise ValueError("Candidate bytes/receipt differ from independent reconstruction")
    writable_ranges, sectors, order = _transition(stock_a, current, target)
    if order[-1] != APP_BASE:
        raise ValueError("Application directory sector must be last")
    live_manifest = verified_read["manifest"]
    identity = {"unit_id": "private-live-rom-bound-diagnostic", "flash_size": FLASH_BYTES,
                "sector_size": SECTOR, "page_size": 256, "jedec": 0x856014,
                "simulated": False, "usb_binding": live_manifest["usb_binding"],
                "backup_manifest_sha256": read["manifest_sha256"]}
    out = Path(output).resolve()
    scope = ("offline-prepared content-free D7000 Trio diagnostic; no physical admission"
             if song_profile is None else
             "offline-prepared Event Horizon project+SET song diagnostic; no physical admission")
    plan = create_transaction(out, current, current_b, target, identity, writable_ranges,
                              scope, commit_sector=APP_BASE)
    saved_plan, journal, saved_before, saved_after = load_transaction(out)
    if (saved_plan != plan or journal.get("state") != "prepared" or saved_before != current or
            saved_after != target or checked_plan_order(plan) != order):
        raise ValueError("Durable directory-last transaction plan differs")
    archive = out / "original-092-archive"
    mkdir_durable(archive)
    archive_files = {"flashA.bin": stock_a, "flashB.bin": stock_b,
                     "manifest.json": stock_manifest_raw, "identity.json": stock_identity_raw}
    for name, data in archive_files.items():
        save_new(archive / name, data)
    for name in sorted(component_names):
        destination = archive / "reference" / name
        parent = destination.parent
        if not parent.exists():
            mkdir_durable(parent)
        save_new(destination, (reference / name).read_bytes())
    archive_receipt = {"schema": 1, "kind": "lunar-original-092-raw-archive",
                       "baseline_sha256": digest(stock_a), "manifest_sha256": digest(stock_manifest_raw),
                       "identity_sha256": digest(stock_identity_raw),
                       "reference_components": {name: digest((reference / name).read_bytes())
                                                 for name in sorted(component_names)},
                       "physical_restore_plan_prepared": False,
                       "physical_recovery_verified": False}
    archive_raw = encoded(archive_receipt)
    save_new(archive / "archive.json", archive_raw)
    sync_directory(archive)
    binding = {"phase": "loader", "loader_sha256": generic_boot.READ_SOURCES["fm1_fixed_loader_backup.py"],
               "usb_binding": live_manifest["usb_binding"], "sg_binding": live_manifest["sg_binding"],
               "read_campaign_sha256": read["campaign_sha256"],
               "read_manifest_sha256": read["manifest_sha256"],
               "read_commands_sha256": read["commands_sha256"],
               "baseline_sha256": digest(current), "identity": identity}
    # The actual fixed loader SHA is validated as an explicit portion of the generic read receipt.
    binding["loader_sha256"] = live_manifest["loader_sha256"]
    result = {"schema": 1, "kind": KIND if song_profile is None else SONG_KIND,
              "status": "offline-diagnostic-transaction-prepared",
              "source": record["source"], "build_record_sha256": digest(record_raw),
              "build_artifact_sha256": digest(_file(build["artifact_path"], build["artifact_sha256"])),
              "verification_sha256": build["verification_sha256"],
              "app_sha256": digest(app), "elf_sha256": digest(elf),
              "candidate_sha256": digest(target), "candidate_receipt_sha256": candidate["receipt_sha256"],
              "stock_baseline_sha256": digest(stock_a), "live_baseline_sha256": digest(current),
              "live_manifest_sha256": read["manifest_sha256"], "live_campaign_sha256": read["campaign_sha256"],
              "usb_binding": live_manifest["usb_binding"], "sg_binding": live_manifest["sg_binding"],
              "project_ids": ([] if song_profile is None else [song_profile["project_id"]]),
              "startup_project_id": (None if song_profile is None else song_profile["project_id"]),
              "set_ids": ([] if song_profile is None else [song_profile["set_id"]]),
              "startup_project_index": (None if song_profile is None else song_profile["startup_project_index"]),
              "startup_set_index": (None if song_profile is None else song_profile["startup_set_index"]),
              "content_selection_receipt_sha256": (
                  None if song_profile is None else song_profile["selection_receipt_sha256"]),
              "content_free": song_profile is None,
              "packed_content_bytes": (0 if song_profile is None else song_profile["packed_content_bytes"]),
              "content_asset_count": (0 if song_profile is None else song_profile["asset_count"]),
              "selected_sounds": list(SOUND_IDS), "selected_module_count": 54,
              "diagnostic_pulse": verification["diagnostic_trio_pulse"],
              "diagnostic_telemetry": verification.get("diagnostic_telemetry"),
              "diagnostic_song_play": verification.get("diagnostic_song_play"),
              "diagnostic_producer_gaps": verification.get("diagnostic_producer_gaps"),
              "diagnostic_irq_profile": verification.get("diagnostic_irq_profile"),
              "current_profile_end": CURRENT_END, "candidate_profile_end": TARGET_END,
              "reclaimed_stock_range": [TARGET_END, CURRENT_END],
              "writable_ranges": writable_ranges, "changed_sector_count": len(sectors),
              "sector_order": order, "commit_sector": APP_BASE,
              "transaction_plan_sha256": digest(encoded(plan)),
              "current_baseline_restore_direction_available": True,
              "original_092_raw_archive_sealed": True,
              "original_092_archive_sha256": digest(archive_raw),
              "original_092_full_raw_restore_plan_prepared": False,
              "hardware_admitted": False, "physical_writer_ready": False,
              "installable": False, "updater_accepted": False,
              "settings_migration_verified": False, "physical_recovery_verified": False,
              "SAVE_linked_but_disarmed": True,
              "next_gate": "coordinator review and fresh physical admission; playback, SAVE, and recovery remain unverified"}
    receipt_path = out / "diagnostic-receipt.json"
    receipt_path.write_bytes(encoded(result))
    evidence = list(verified_read["evidence"])
    pinned_paths = [record_path, Path(candidate["path"]), Path(candidate["receipt_path"]),
                    Path(stock_input["baseline_a_path"]), Path(stock_input["baseline_b_path"]),
                    Path(stock_input["manifest_path"]), Path(stock_input["identity_path"]),
                    *[reference / name for name in sorted(component_names)],
                    archive / "flashA.bin", archive / "flashB.bin", archive / "manifest.json",
                    archive / "identity.json", archive / "archive.json",
                    *[archive / "reference" / name for name in sorted(component_names)]]
    pinned_paths.append(Path(build["frozen_receipt_path"]))
    for key in ("source_snapshot_path", "toolchain_snapshot_path", "catalogue_snapshot_path",
                "verification_path", "artifact_path", "app_path", "elf_path", "disassembly_path",
                "prepared_profile_path"):
        pinned_paths.append(Path(build[key]))
    if song_profile is not None:
        pinned_paths.append(song_profile["selection_path"])
    for path in pinned_paths:
        path = path.resolve()
        if path.is_dir():
            continue
        data = path.read_bytes()
        evidence.append((path, data, max(len(data), 1)))
    policy = Policy(out, encoded(plan), current, target, encoded(result), encoded(binding),
                    tuple(sectors), tuple(evidence), verified_read["completed_at"], _VALIDATED)
    _POLICIES.add(policy)
    policy.check_files()
    return policy


# The seal is an offline attestation pinned by the caller, not a signature or
# device identity. Paths use physical absolute names: symlink components reject.
_SEAL_KIND = "lunar-private-generic-diagnostic-policy-seal"
_META_LIMIT = 512 * 1024
_EVIDENCE_LIMIT = 64 * 1024 * 1024
_EVIDENCE_TOTAL = 256 * 1024 * 1024
_EVIDENCE_COUNT = 512


def _parent_fd(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or path.name in ("", ".", ".."):
        raise ValueError("Physical absolute file path required")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in path.parts[1:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                              dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd, path.name
    except BaseException:
        os.close(fd)
        raise


def _bounded_file(path, limit):
    if type(limit) is not int or not 0 <= limit <= _EVIDENCE_LIMIT:
        raise ValueError("Bounded regular-file read required")
    parent, name = _parent_fd(path)
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
                     dir_fd=parent)
    finally:
        os.close(parent)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise ValueError("Unsafe or oversized regular file: " + str(path))
        pieces, total = [], 0
        while True:
            data = os.read(fd, min(65536, limit + 1 - total))
            if not data:
                break
            pieces.append(data)
            total += len(data)
            if total > limit:
                raise ValueError("Regular file exceeded bound")
        after = os.fstat(fd)
        if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) !=
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or total != before.st_size):
            raise ValueError("Regular file changed while reading")
        return b"".join(pieces)
    finally:
        os.close(fd)


def _canonical_json(data):
    try:
        value = json.loads(data, object_pairs_hook=_unique_json)
        if encoded(value) != data:
            raise ValueError("Canonical JSON required")
        return value
    except (UnicodeError, json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Invalid canonical JSON") from exc


def _load_policy_transaction(directory):
    """Shared bounded validation; the transport-independent core is unchanged."""
    directory = Path(directory)
    plan = _canonical_json(_bounded_file(directory / "plan.json", _META_LIMIT))
    journal = _canonical_json(_bounded_file(directory / "journal.json", _META_LIMIT))
    if (not isinstance(plan, dict) or not isinstance(journal, dict) or
            journal.get("record_sha256") != digest(encoded({k: v for k, v in journal.items()
                                                          if k != "record_sha256"})) or
            plan.get("schema") != 1 or journal.get("schema") != 1 or
            journal.get("plan_sha256") != digest(encoded(plan)) or
            journal.get("state") not in ("prepared", "running", "recovery_required", "complete") or
            journal.get("direction") not in (None, "install", "restore")):
        raise ValueError("Invalid or mismatched transaction journal/plan")
    checked_identity(plan["identity"])
    order = checked_plan_order(plan)
    if "sector_order" in plan and journal.get("sector_order") != order:
        raise ValueError("Journal sector order differs from sealed plan")
    baseline = _bounded_file(directory / "backupA.bin", FLASH_BYTES)
    second = _bounded_file(directory / "backupB.bin", FLASH_BYTES)
    target = _bounded_file(directory / "target.bin", FLASH_BYTES)
    if (len(baseline) != FLASH_BYTES or baseline != second or
            digest(baseline) != plan["baseline_sha256"] or len(target) != FLASH_BYTES or
            digest(target) != plan["target_sha256"]):
        raise ValueError("Transaction backup or target hash mismatch")
    check_outside(target, baseline, plan["writable_ranges"])
    return plan, journal, baseline, target


def _evidence_inventory(evidence):
    if not 0 < len(evidence) <= _EVIDENCE_COUNT:
        raise ValueError("Bounded original evidence inventory required")
    inventory, total = {}, 0
    for path, expected, _limit in evidence:
        path = str(Path(path).absolute())
        size = len(expected)
        if path not in inventory:
            total += size
        if total > _EVIDENCE_TOTAL:
            raise ValueError("Original evidence aggregate exceeds bound")
        if size > _EVIDENCE_LIMIT or _bounded_file(path, size) != expected:
            raise ValueError("Original evidence changed or oversized")
        row = {"path": path, "size": size, "sha256": digest(expected)}
        if path in inventory and inventory[path] != row:
            raise ValueError("Conflicting evidence path")
        inventory[path] = row
    return [inventory[path] for path in sorted(inventory)]


def _validation_sources():
    paths = {"policy": Path(__file__).absolute(), "transaction": ROOT / "fm1_flash_transaction.py",
             "bound_session": ROOT / "fm1_bound_diagnostic.py"}
    return {name: digest(_bounded_file(path, _META_LIMIT)) for name, path in paths.items()}


def reopen_policy(seal_path, expected_sha256):
    """Revalidate a durable offline policy with an independently retained pin.

    Never discover a colocated hash. This preserves the original factory
    validation by checking its exact sealed snapshots, without running builds
    or opening devices. Fresh resume admission is a separate required step.
    """
    if not _valid_sha(expected_sha256):
        raise ValueError("Independent expected seal SHA256 required")
    data = _bounded_file(seal_path, _META_LIMIT)
    if digest(data) != expected_sha256:
        raise ValueError("Policy seal differs from independent pin")
    seal = _canonical_json(data)
    if (not isinstance(seal, dict) or set(seal) != {"schema", "kind", "directory",
            "plan_sha256", "receipt_sha256", "binding", "read_completed_at", "sectors", "evidence", "validation_sources"} or
            type(seal["schema"]) is not int or seal["schema"] != 1 or seal["kind"] != _SEAL_KIND or
            type(seal["read_completed_at"]) not in (int, float) or
            not math.isfinite(seal["read_completed_at"]) or seal["read_completed_at"] < 0 or
            not isinstance(seal["evidence"], list) or
            not 0 < len(seal["evidence"]) <= _EVIDENCE_COUNT):
        raise ValueError("Exact bounded policy seal required")
    if seal["validation_sources"] != _validation_sources():
        raise ValueError("Policy validation sources differ from sealed implementation")
    evidence, total, paths = [], 0, set()
    for row in seal["evidence"]:
        if (not isinstance(row, dict) or set(row) != {"path", "size", "sha256"} or
                not isinstance(row["path"], str) or row["path"] in paths or
                type(row["size"]) is not int or not 0 <= row["size"] <= _EVIDENCE_LIMIT or
                not _valid_sha(row["sha256"])):
            raise ValueError("Invalid bounded evidence inventory")
        total += row["size"]
        if total > _EVIDENCE_TOTAL:
            raise ValueError("Original evidence aggregate exceeds bound")
        paths.add(row["path"])
    for row in seal["evidence"]:
        raw = _bounded_file(row["path"], row["size"])
        if len(raw) != row["size"] or digest(raw) != row["sha256"]:
            raise ValueError("Pinned original evidence changed")
        evidence.append((Path(row["path"]), raw, max(len(raw), 1)))
    directory = Path(seal["directory"])
    plan, _, baseline, target = _load_policy_transaction(directory)
    receipt = _bounded_file(directory / "diagnostic-receipt.json", _META_LIMIT)
    receipt_value = _canonical_json(receipt)
    if (not isinstance(receipt_value, dict) or any(receipt_value.get(key) is not False
            for key in ("hardware_admitted", "physical_writer_ready", "installable")) or
            any(receipt_value.get(key, False) is not False for key in ("updater_accepted", "physical_recovery_verified"))):
        raise ValueError("Offline policy receipt must retain unadmitted hardware claims")
    binding = seal["binding"]
    if (digest(encoded(plan)) != seal["plan_sha256"] or digest(receipt) != seal["receipt_sha256"] or
            not isinstance(binding, dict) or binding.get("identity") != plan["identity"] or
            binding.get("baseline_sha256") != digest(baseline) or
            seal["sectors"] != sorted({a for start, end in plan["writable_ranges"]
                                       for a in range(start, end, SECTOR)}) or
            type(binding.get("loader_sha256")) is not str):
        raise ValueError("Sealed policy transaction/binding differs")
    policy = Policy(directory, encoded(plan), baseline, target, receipt, encoded(binding),
                    tuple(seal["sectors"]), tuple(evidence), seal["read_completed_at"], _VALIDATED)
    _POLICIES.add(policy)
    policy.check_files()
    return policy


@dataclass(frozen=True, eq=False)
class _ResumeAdmission:
    """Process-local, one-bind capability; serialized receipts grant no authority."""
    policy: object
    journal_bytes: bytes
    read_bytes: bytes
    binding_bytes: bytes
    evidence: tuple
    admitted_at: float
    deadline: float

    def check(self, policy, *, journal=True):
        if self not in _RESUMES or self.policy is not policy:
            raise ValueError("Factory-created resume admission required")
        policy.check_files()
        if not 0 <= generic_boot.time.time() - self.admitted_at <= RESUME_SESSION_SECONDS:
            raise ValueError("Resume live-session deadline expired")
        for path, expected, limit in self.evidence:
            data = _bounded_file(path, limit)
            if len(data) > limit or data != expected:
                raise ValueError("Fresh resume evidence changed")
        if journal and _bounded_file(policy.directory / "journal.json", _META_LIMIT) != self.journal_bytes:
            raise ValueError("Interrupted resume journal changed")


@dataclass(frozen=True, eq=False)
class Policy:
    directory: Path
    plan_bytes: bytes
    baseline: bytes
    target: bytes
    receipt_bytes: bytes
    binding_bytes: bytes
    sectors: tuple
    evidence: tuple
    read_completed_at: float
    authorization: object

    @property
    def direction(self):
        return "install"

    def check_files(self, *, require_fresh=False):
        if self not in _POLICIES or self.authorization is not _VALIDATED:
            raise ValueError("Exact factory-created generic diagnostic policy required")
        if (require_fresh and
                not 0 <= generic_boot.time.time() - self.read_completed_at <= generic_boot.MAX_AGE):
            raise ValueError("Fresh paired-ROM read evidence expired; prepare a new transaction")
        for path, expected, limit in self.evidence:
            path = Path(path)
            data = _bounded_file(path, limit)
            if len(data) > limit or data != expected:
                raise ValueError("Pinned build/read evidence changed: " + path.name)
        plan, journal, before, after = _load_policy_transaction(self.directory)
        if encoded(plan) != self.plan_bytes or before != self.baseline or after != self.target:
            raise ValueError("Generic transaction artifacts changed")
        receipt = _bounded_file(self.directory / "diagnostic-receipt.json", _META_LIMIT)
        if receipt != self.receipt_bytes:
            raise ValueError("Diagnostic receipt changed")
        return journal

    def seal(self, path):
        """Write once and return the pin the caller must retain independently."""
        self.check_files()
        value = {"schema": 1, "kind": _SEAL_KIND, "directory": str(self.directory.absolute()),
            "plan_sha256": digest(self.plan_bytes), "receipt_sha256": digest(self.receipt_bytes),
            "binding": json.loads(self.binding_bytes), "read_completed_at": self.read_completed_at,
            "sectors": sorted(self.sectors), "evidence": _evidence_inventory(self.evidence),
            "validation_sources": _validation_sources()}
        data = encoded(value)
        if len(data) > _META_LIMIT:
            raise ValueError("Policy seal exceeds bound")
        parent, name = _parent_fd(path)
        try:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                         0o600, dir_fd=parent)
            try:
                view = memoryview(data)
                while view:
                    written = os.write(fd, view)
                    if written <= 0:
                        raise OSError("Short policy seal write")
                    view = view[written:]
                os.fsync(fd)
            finally:
                os.close(fd)
            os.fsync(parent)
        finally:
            os.close(parent)
        return digest(data)

    def receipt(self):
        return json.loads(self.receipt_bytes)

    def admit_resume(self, fresh_read):
        """Explicit offline admission after an interrupted install, never a retry.

        Recovery repairs any changed authorized sector; it does not attribute
        in-range bytes to an exact logged command prefix. No device is opened.
        """
        journal = self.check_files()
        if (journal.get("state") not in ("running", "recovery_required") or
                journal.get("direction") != "install"):
            raise ValueError("Resume requires a durable interrupted install journal")
        required, verified = self._fresh_binding(fresh_read)
        now = generic_boot.time.time()
        if not 0 <= now - verified["completed_at"] <= generic_boot.MAX_AGE:
            raise ValueError("Fresh resume paired read expired")
        admission = _ResumeAdmission(self, _bounded_file(self.directory / "journal.json", _META_LIMIT),
            encoded({**fresh_read, "manifest_path": str(fresh_read["manifest_path"])}),
            encoded(required), tuple(verified.get("evidence", ())), now,
            generic_boot.time.monotonic() + RESUME_SESSION_SECONDS)
        _RESUMES.add(admission)
        return admission

    def _fresh_binding(self, read):
        if not isinstance(read, dict) or set(read) != {
                "manifest_path", "manifest_sha256", "commands_sha256", "campaign_sha256",
                "expected_devnum", "current_flash_sha256"}:
            raise ValueError("Resume requires exact fresh paired full-image read evidence")
        verified = generic_boot.verify_read_bundle(read["manifest_path"], read["manifest_sha256"],
            read["commands_sha256"], campaign_sha256=read["campaign_sha256"],
            expected_devnum=read["expected_devnum"], expected_flash_sha256=read["current_flash_sha256"])
        manifest = verified["manifest"]
        original = json.loads(self.binding_bytes)
        if (manifest["loader_sha256"] != original["loader_sha256"] or
                any(original["usb_binding"].get(key) != manifest["usb_binding"].get(key)
                    for key in ("path", "busnum", "vid", "pid"))):
            raise ValueError("Resume requires same physical USB port and reviewed loader")
        required = {"phase": "loader", "loader_sha256": manifest["loader_sha256"],
            "usb_binding": manifest["usb_binding"], "sg_binding": manifest["sg_binding"],
            "read_campaign_sha256": read["campaign_sha256"],
            "read_manifest_sha256": read["manifest_sha256"],
            "read_commands_sha256": read["commands_sha256"],
            "baseline_sha256": manifest["current_flash_sha256"],
            "identity": json.loads(self.plan_bytes)["identity"]}
        return required, verified

    def bind(self, transport, *, direction="install", restore_read=None, resume=None):
        if direction not in ("install", "restore"):
            raise ValueError("Direction must be the prepared candidate install or current-baseline restore")
        if resume is not None:
            if direction != "install" or restore_read is not None or not isinstance(resume, _ResumeAdmission):
                raise ValueError("Explicit install resume admission required")
            resume.check(self)
            if resume in _USED_RESUMES:
                raise ValueError("Resume admission already consumed")
            _USED_RESUMES.add(resume)
        self.check_files(require_fresh=(direction == "install" and resume is None))
        required = json.loads(self.binding_bytes)
        if direction == "restore":
            if not isinstance(restore_read, dict) or set(restore_read) != {
                    "manifest_path", "manifest_sha256", "commands_sha256", "campaign_sha256",
                    "expected_devnum", "current_flash_sha256"}:
                raise ValueError("Restore requires a new fresh paired full-image read and same-loader binding")
            verified = generic_boot.verify_read_bundle(
                restore_read["manifest_path"], restore_read["manifest_sha256"],
                restore_read["commands_sha256"], campaign_sha256=restore_read["campaign_sha256"],
                expected_devnum=restore_read["expected_devnum"],
                expected_flash_sha256=restore_read["current_flash_sha256"])
            manifest = verified["manifest"]
            old_usb, new_usb = required["usb_binding"], manifest["usb_binding"]
            stable_usb = ("path", "busnum", "vid", "pid")
            if (not isinstance(old_usb, dict) or not isinstance(new_usb, dict) or
                    any(old_usb.get(key) != new_usb.get(key) for key in stable_usb)):
                raise ValueError("Fresh restore read is not the same physical USB port/device")
            # SG node and USB devnum can change on a real reconnect. The fresh
            # verifier binds the new SG mapping to this stable USB port; the
            # transport below must match that newly verified mapping exactly.
            required = {"phase": "loader", "loader_sha256": manifest["loader_sha256"],
                        "usb_binding": manifest["usb_binding"], "sg_binding": manifest["sg_binding"],
                        "read_campaign_sha256": restore_read["campaign_sha256"],
                        "read_manifest_sha256": restore_read["manifest_sha256"],
                        "read_commands_sha256": restore_read["commands_sha256"],
                        "baseline_sha256": manifest["current_flash_sha256"],
                        "identity": json.loads(self.plan_bytes)["identity"]}
        if resume is not None:
            required = json.loads(resume.binding_bytes)
        expected_current = required.get("baseline_sha256") if direction == "restore" or resume is not None else None
        return DiagnosticSession(self, transport, direction=direction,
                                 required_binding=required,
                                 expected_current_sha256=expected_current, resume=resume)


class _DirectionPolicy:
    def __init__(self, policy, direction):
        self._policy, self.direction = policy, direction

    def __getattr__(self, name):
        return getattr(self._policy, name)


class DiagnosticSession(BoundDiagnosticSession):
    """Injected-only wrapper requiring the exact same-ROM read binding."""
    def __init__(self, policy, transport, *, direction="install", required_binding=None,
                 expected_current_sha256=None, resume=None):
        if policy not in _POLICIES or policy.authorization is not _VALIDATED or direction not in ("install", "restore"):
            raise ValueError("Exact generic diagnostic policy and direction required")
        self._policy, self._transport = _DirectionPolicy(policy, direction), transport
        self._resume = resume
        self._expected_current_sha256 = expected_current_sha256
        self._initial_full_read_checked = False
        self._latched, self._running, self._binding = False, False, None
        try:
            observed = self._capture_binding()
            required = required_binding if required_binding is not None else json.loads(policy.binding_bytes)
            if any(observed.get(k) != v for k, v in required.items()):
                raise ValueError("Fresh generic ROM read and loader binding differs")
            self._binding = encoded(observed)
        except BaseException:
            self._stop()
            raise

    def read(self, address, size):
        data = super().read(address, size)
        if (self._expected_current_sha256 is not None and not self._initial_full_read_checked
                and address == 0 and size == FLASH_BYTES):
            self._initial_full_read_checked = True
            if digest(data) != self._expected_current_sha256:
                self._stop()
                raise ValueError("Fresh restore/resume reread differs from the bound complete current image")
            if self._resume is not None:
                check_outside(data, self._policy.baseline, json.loads(self._policy.plan_bytes)["writable_ranges"])
        return data

    def _check(self):
        super()._check()
        if self._resume is not None:
            try:
                if generic_boot.time.monotonic() > self._resume.deadline:
                    raise ValueError("Resume live-session deadline expired")
            except BaseException:
                self._stop()
                raise

    def run(self, checkpoint=None):
        if self._resume is not None:
            try:
                self._resume.check(self._policy._policy)
            except BaseException:
                self._stop()
                raise
        return super().run(checkpoint)

    def _mutation_intent(self, operation, address):
        if self._resume is not None:
            self._resume.check(self._policy._policy, journal=False)
            if not self._initial_full_read_checked:
                raise ValueError("Resume requires complete current-image reread before mutation")
        return super()._mutation_intent(operation, address)

    def build_request(self, op, *, address=0, payload=b""):
        # Inherited checks seal every mutation to this one transaction.
        return super().build_request(op, address=address, payload=payload)
