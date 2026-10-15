import copy
import json

import pytest

from tools.native import generic_diagnostic_flash as policy
from tools.fm1_flash_transaction import digest


PROJECT = policy.EVENT_HORIZON_ID
SET = policy.EVENT_HORIZON_SET_ID


def song_fixture(tmp_path):
    prepared_dir = tmp_path / "prepared"
    prepared_dir.mkdir()
    selection_path = tmp_path / "selection.json"
    project = {
        "source": f"projects/{PROJECT}.lunar", "source_sha256": "1" * 64,
        "packed": "content-00.bin", "packed_sha256": "2" * 64,
        "bytes": 17, "kind": "project", "dependencies": ["trio"],
        "sequence_semantics_verified": False, "dependency_scan_complete": True,
    }
    companion = {
        "source": f"sets/{SET}.movy1", "source_sha256": "3" * 64,
        "packed": "content-01.bin", "packed_sha256": "4" * 64,
        "bytes": 23, "kind": "set", "dependencies": ["trio"],
        "sequence_semantics_verified": False, "dependency_scan_complete": False,
    }
    profile = {
        "version": 1, "module_selection": {"selected": ["trio"]},
        "content": [project, companion], "packed_content_bytes": 40,
        "installable": False, "native_link_verified": False,
        "native_ram_verified": False, "hardware_tested": False,
    }
    profile_raw = json.dumps(profile, sort_keys=True).encode()
    profile_path = prepared_dir / "profile.json"
    profile_path.write_bytes(profile_raw)
    selection = {
        "version": 1, "status": "prepared-build-inputs",
        "prepared_profile_sha256": digest(profile_raw),
        "project_ids": [PROJECT], "startup_index": 0,
        "startup_project_id": PROJECT, "set_ids": [SET],
        "selected_content": [
            {"kind": "project", "id": PROJECT},
            {"kind": "set", "id": SET, "parent_project_id": PROJECT},
        ],
        "content": [
            {"id": PROJECT, **project},
            {"id": SET, "parent_project_id": PROJECT, **companion},
        ],
        "packed_content_bytes": 40,
        "installable": False, "native_link_verified": False,
        "native_ram_verified": False, "hardware_tested": False,
    }
    selection_raw = json.dumps(selection, sort_keys=True).encode()
    selection_path.write_bytes(selection_raw)
    build = {"prepared_profile_path": str(profile_path),
             "prepared_profile_sha256": digest(profile_raw)}
    project_link_fields = (
        "modulation_staging_link_verified", "sequence_staging_link_verified",
        "engine_staging_link_verified", "engine_parameter_link_verified",
        "audio_adoption_link_verified", "midi_restore_link_verified",
        "scalar_restore_link_verified", "dx7_restore_link_verified",
        "modulation_adoption_link_verified", "modulation_restore_link_verified",
        "startup_composition_link_verified", "view_restore_link_verified",
    )
    verification = {
        "module_selection": profile["module_selection"],
        "diagnostic_trio_pulse": {
            "enabled": False, "compile_definition": None, "note": None,
            "velocity": None, "start_ms": None, "end_ms": None,
            "once": True, "hardware_tested": False,
        },
        "diagnostic_telemetry": {
            "enabled": True, "compile_definition": "LUNAR_DIAGNOSTIC_TELEMETRY=1",
            "interval_ms": 1000, "transport": "USB-MIDI-SysEx", "hardware_tested": False,
        },
        "diagnostic_song_play": {
            "enabled": True,
            "compile_definition": "LUNAR_DIAGNOSTIC_SONG_PLAY=1",
            "start_ms": 2000, "once": True, "hardware_tested": False,
        },
        "embedded_content": {
            "prepared_sha256": digest(profile_raw), "asset_count": 2,
            "packed_content_bytes": 40,
            "packed_sha256": [project["packed_sha256"], companion["packed_sha256"]],
            "assets": [
                {"kind": "project", "bytes": 17, "packed_sha256": project["packed_sha256"]},
                {"kind": "set", "bytes": 23, "packed_sha256": companion["packed_sha256"]},
            ],
            "sequence_semantics_verified": False, "native_playback_verified": False,
        },
        "startup_project": {
            "index": 0, "runtime_hook_linked": False,
            "staging_reclaimed_before_engine_allocation": True,
            "failure_returns_to_recovery": True, "runtime_verified": False,
            "hardware_tested": False,
        },
        "companion_set_selection": {
            "enabled": True, "selection_receipt_sha256": digest(selection_raw),
            "parent_project_index": 0, "set_indices": [1],
            "before_audio_init": True, "timeout_keeps_project_sequence": True,
            "runtime_verified": False, "sequence_semantics_verified": False,
            "hardware_tested": False,
        },
        "project_loader": {**{key: True for key in project_link_fields},
                            "activated": False, "stack_margin_verified": False,
                            "timing_verified": False, "hardware_tested": False,
                            "sequence_semantics_verified": False},
        "set_loader": {"native_link_verified": True,
                       "activation_api_link_verified": True, "activated": False,
                       "stack_margin_verified": False, "hardware_tested": False,
                       "sequence_semantics_verified": False},
    }
    return build, verification, profile_raw, selection, selection_path


def test_song_policy_binds_exact_event_horizon_project_and_parented_set(tmp_path):
    build, verification, prepared, _, _ = song_fixture(tmp_path)
    song = policy._validate_diagnostic_mode(
        {"kind": policy.SONG_INPUT_KIND}, build, verification, prepared)
    assert song["project_id"] == PROJECT
    assert song["set_id"] == SET
    assert (song["startup_project_index"], song["startup_set_index"]) == (0, 1)
    assert song["asset_count"] == 2
    assert song["packed_content_bytes"] == 40


@pytest.mark.parametrize("mutation, message", [
    ("unknown-kind", "Unknown private diagnostic profile"),
    ("pulse-enabled", "explicitly disable the Trio pulse"),
    ("telemetry-disabled", "telemetry must be enabled"),
    ("play-disabled", "bounded one-shot PLAY profile"),
    ("play-definition", "bounded one-shot PLAY profile"),
])
def test_song_policy_requires_separate_telemetry_only_playback_mode(
        tmp_path, mutation, message):
    build, verification, prepared, _, _ = song_fixture(tmp_path)
    if mutation == "pulse-enabled":
        verification["diagnostic_trio_pulse"]["enabled"] = True
    elif mutation == "telemetry-disabled":
        verification["diagnostic_telemetry"]["enabled"] = False
    elif mutation == "play-disabled":
        verification["diagnostic_song_play"]["once"] = False
    elif mutation == "play-definition":
        verification["diagnostic_song_play"]["compile_definition"] = "OTHER=1"
    kind = "not-a-diagnostic" if mutation == "unknown-kind" else policy.SONG_INPUT_KIND
    with pytest.raises(ValueError, match=message):
        policy._validate_diagnostic_mode({"kind": kind}, build, verification, prepared)


def test_legacy_content_free_pulse_policy_is_not_relaxed(tmp_path):
    build, verification, prepared, _, _ = song_fixture(tmp_path)
    with pytest.raises(ValueError, match="non-repeating Trio diagnostic pulse"):
        policy._validate_diagnostic_mode(
            {"kind": policy.INPUT_KIND}, build, verification, prepared)


@pytest.mark.parametrize("mutation, message", [
    ("wrong-project", "exact Event Horizon project/SET pair"),
    ("wrong-set", "exact Event Horizon project/SET pair"),
    ("wrong-parent", r"exact EH\+SET startup"),
    ("wrong-set-id", r"exact EH\+SET startup"),
    ("wrong-startup", r"exact EH\+SET startup"),
    ("profile-total", "Prepared profile packed-content total"),
    ("selection-hash", "Pinned evidence bytes differ"),
    ("loader-unlinked", "Native project/SET loader link"),
    ("startup-set-index", "Companion SET selection report differs"),
    ("standalone-set-startup", "Standalone SET startup receipt"),
])
def test_song_policy_rejects_tampered_project_set_binding(tmp_path, mutation, message):
    build, verification, prepared, selection, selection_path = song_fixture(tmp_path)
    verification = copy.deepcopy(verification)
    if mutation in ("wrong-project", "wrong-set", "profile-total"):
        profile = json.loads(prepared)
        if mutation == "wrong-project":
            profile["content"][0]["source"] = "projects/other.lunar"
        elif mutation == "wrong-set":
            profile["content"][1]["source"] = "sets/other.movy1"
        else:
            profile["packed_content_bytes"] = 41
        prepared = json.dumps(profile).encode()
    elif mutation == "wrong-parent":
        selection["selected_content"][1]["parent_project_id"] = "other"
        selection_path.write_text(json.dumps(selection))
        verification["companion_set_selection"]["selection_receipt_sha256"] = digest(
            selection_path.read_bytes())
    elif mutation == "wrong-set-id":
        selection["set_ids"] = ["other"]
        selection_path.write_text(json.dumps(selection))
        verification["companion_set_selection"]["selection_receipt_sha256"] = digest(
            selection_path.read_bytes())
    elif mutation == "wrong-startup":
        selection["startup_index"] = 1
        selection_path.write_text(json.dumps(selection))
        verification["companion_set_selection"]["selection_receipt_sha256"] = digest(
            selection_path.read_bytes())
    elif mutation == "selection-hash":
        selection_path.write_text(json.dumps(selection) + " ")
    elif mutation == "loader-unlinked":
        verification["set_loader"]["native_link_verified"] = False
    elif mutation == "startup-set-index":
        verification["companion_set_selection"]["set_indices"] = [0]
    elif mutation == "standalone-set-startup":
        verification["startup_set"] = {
            "index": 1, "runtime_hook_linked": True,
            "staging_reclaimed_before_engine_allocation": True,
            "runtime_verified": False, "stack_margin_verified": False,
            "hardware_tested": False,
        }
    with pytest.raises(ValueError, match=message):
        policy._validate_diagnostic_mode(
            {"kind": policy.SONG_INPUT_KIND}, build, verification, prepared)
