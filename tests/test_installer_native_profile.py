# SPDX-License-Identifier: MIT
import json
from pathlib import Path

import pytest

from tools.installer_service.native_profile import (
    PROFILE_CONTRACT, PROFILE_ID, evidence_manifest, profile_sha256, validate_receipt,
)


def target_receipt():
    from tools.native.build_demo_image import (BASE_INSTANCE_POOL_BYTES, HALL_O2_STAGE7_TARGET_STORAGE,
                                               SHAPES8_TABLES)
    return {
        "flash_layout": "expanded-d7000", "app_budget_bytes": 860644,
        "shapes_voices": 8, "indexed_tft": True,
        "flash_plaits_wavetables": False,
        "target_app_storage": dict(HALL_O2_STAGE7_TARGET_STORAGE),
        "compressed_wave_tables": [dict(row) for row in SHAPES8_TABLES],
        "instance_pool_bytes": BASE_INSTANCE_POOL_BYTES
            + HALL_O2_STAGE7_TARGET_STORAGE["pool_credit_bytes"]
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
        "catalogue_optimization_overrides": {
            "our/src/fx_hall.o": "-O2", "our/src/mi_sixop.o": "-Os",
        },
        "catalogue_limiter_os": False, "catalogue_hall_o2": True,
        "catalogue_source_freshness_verified": True, "boot_ota_cleanup": False,
        "catalogue_objects": [
            {"path": "/catalogue/shard-02/obj/our/src/mi_sixop.o",
             "sha256": "a" * 64, "optimization": "-Os"},
            {"path": "/catalogue/shard-04/obj/our/src/fx_hall.o",
             "sha256": "b" * 64, "optimization": "-O2"},
        ],
        "module_selection": {"selected": ["macro", "shapes", "sixop", "drums", "hall"]},
        "hot_dsp_ram": {
            "enabled": True, "selected_bodies": PROFILE_CONTRACT["hot_dsp_ram_bodies"],
        },
        "diagnostic_song_play": {"compile_definition": None, "enabled": False,
                                  "hardware_tested": False, "once": False, "start_ms": None},
        "project_save_service": {
            "compile_definition": "LUNAR_PROJECT_SAVE_SERVICE=1", "flash_io_bound": False,
            "hardware_tested": False, "linked": True, "runtime_verified": False,
            "save_service_armed": False, "storage_admitted": False,
        },
        "diagnostic_cpu_rate": None, "diagnostic_producer_gaps": None,
        "diagnostic_irq_profile": None, "installable": False,
        "hardware_tested": False, "hardware_candidate": False,
    }


def test_native_profile_matches_corrected_stage7_contract_and_binds_raw_receipt():
    receipt = target_receipt()
    validate_receipt(receipt)
    raw = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    manifest = json.loads(evidence_manifest(raw))
    assert manifest == {"schema": 1, "profile_id": PROFILE_ID,
                        "profile_sha256": profile_sha256(),
                        "build_receipt_sha256": __import__("hashlib").sha256(raw).hexdigest()}


@pytest.mark.parametrize("mutate", [
    lambda r: r["catalogue_optimization_overrides"].update({"our/src/fx_hall.o": "-Os"}),
    lambda r: r["catalogue_objects"][1].update(optimization="-Os"),
    lambda r: r["target_app_storage"].update(rgb565_bytes=220832),
    lambda r: r.update(instance_pool_bytes=r["instance_pool_bytes"] + 16),
    lambda r: r["catalogue_objects"].pop(),
    lambda r: r["catalogue_objects"].append(dict(r["catalogue_objects"][0])),
    lambda r: r.pop("native_midi_input"),
    lambda r: r["diagnostic_engine_render_profile"].update(schema=8),
    lambda r: r["diagnostic_clock_snapshot"].update(supplemental_schema=3),
    lambda r: r["native_midi_input"].update(unknown=True),
    lambda r: r["hot_dsp_ram"].update(selected_bodies=r["hot_dsp_ram"]["selected_bodies"][:-1]),
    lambda r: r.update(diagnostic_cpu_rate={"enabled": True}),
    lambda r: r["diagnostic_song_play"].update(enabled=True),
    lambda r: r["project_save_service"].update(save_service_armed=True),
    lambda r: r.update(installable=True),
])
def test_native_profile_rejects_mismatched_receipt_fields(mutate):
    receipt = target_receipt()
    mutate(receipt)
    with pytest.raises(ValueError, match="native diagnostic profile"):
        validate_receipt(receipt)


def test_private_evidence_reader_requires_profile_digest_bound_to_receipt(tmp_path):
    from tools.installer_service.docker_adapter import read_private_evidence
    from tools.installer_service.docker_worker import GENERATED_EVIDENCE_PATHS
    from tools.installer_service.provenance import sha256

    result = tmp_path / "result"
    evidence_root = result / "evidence"
    catalogue_root = tmp_path / "catalogue"
    evidence_root.mkdir(parents=True)
    catalogue_root.mkdir()
    request = b'{"version":1}\n'
    prepared, source, artifact = b'{"prepared":true}', b'{"source":true}', b'{"artifact":true}'
    receipt = target_receipt()
    catalogue_rows = []
    for suffix, optimization, content in (
        ("our/src/mi_sixop.o", "-Os", b"sixop"),
        ("our/src/fx_hall.o", "-O2", b"hall"),
    ):
        relative = Path("shard-" + ("02" if "sixop" in suffix else "04")) / "obj" / suffix
        path = catalogue_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        catalogue_rows.append({"path": "/input/catalogue/" + relative.as_posix(),
                               "sha256": sha256(content), "optimization": optimization})
    receipt["module_selection"] = {"selected": ["macro", "shapes", "sixop", "drums", "hall"]}
    receipt["catalogue_objects"] = catalogue_rows
    receipt["linked_objects"] = [{"path": row["path"], "sha256": row["sha256"]}
                                  for row in catalogue_rows]
    build_raw = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    image_raw = json.dumps({
        "request_sha256": sha256(request), "prepared_profile_sha256": sha256(prepared),
        "verification_sha256": sha256(build_raw),
        "artifact_receipt_sha256": sha256(artifact),
    }, sort_keys=True, separators=(",", ":")).encode()
    contents = {
        "request.json": request, "prepared_profile.json": prepared,
        "source_profile.json": source, "artifact_receipt.json": artifact,
        "build_receipt.json": build_raw, "image_receipt.json": image_raw,
        "native_profile.json": evidence_manifest(build_raw),
        "catalogue_manifest.json": json.dumps(
            {"schema": 1, "objects": catalogue_rows}, sort_keys=True,
            separators=(",", ":")).encode(),
        "linked_objects.json": json.dumps(
            {"schema": 1, "objects": receipt["linked_objects"]}, sort_keys=True,
            separators=(",", ":")).encode(),
    }
    contents.update({"catalogue/" + Path(row["path"]).relative_to("/input/catalogue").as_posix():
                     (catalogue_root / Path(row["path"]).relative_to("/input/catalogue")).read_bytes()
                     for row in catalogue_rows})
    contents.update({"linked/catalogue/" + Path(row["path"]).relative_to("/input/catalogue").as_posix():
                     (catalogue_root / Path(row["path"]).relative_to("/input/catalogue")).read_bytes()
                     for row in catalogue_rows})
    contents.update({"generated/" + rel: ("generated:" + rel).encode()
                     for rel in GENERATED_EVIDENCE_PATHS})

    def write_evidence():
        manifest = {}
        for rel, raw in contents.items():
            path = evidence_root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            manifest[rel] = {"bytes": len(raw), "sha256": sha256(raw)}
        (evidence_root / "manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")), encoding="ascii")

    write_evidence()
    assert read_private_evidence(result, request, image_raw, catalogue_root)["native_profile.json"] == contents["native_profile.json"]
    invalid_sidecars = [
        None,
        b"{ malformed",
        evidence_manifest(build_raw).replace(profile_sha256().encode(), b"0" * 64),
        evidence_manifest(build_raw).replace(sha256(build_raw).encode(), b"0" * 64),
        json.dumps({"schema": 1, "profile_id": "other", "profile_sha256": profile_sha256(),
                    "build_receipt_sha256": sha256(build_raw)}, sort_keys=True,
                   separators=(",", ":")).encode(),
    ]
    for sidecar in invalid_sidecars:
        if sidecar is None:
            contents.pop("native_profile.json", None)
        else:
            contents["native_profile.json"] = sidecar
        write_evidence()
        with pytest.raises(ValueError):
            read_private_evidence(result, request, image_raw, catalogue_root)


def test_worker_selects_named_profile_without_changing_d9000_flags():
    from tools.installer_service.docker_worker import build_profile_arguments

    d7000 = {"engines": ["macro", "shapes", "sixop", "drums"], "effects": ["hall"], "midi": [],
             "modulation": [], "flash_layout": "expanded-d7000",
             "runtime_mode": "song-diagnostic"}
    d9000 = {"engines": ["a"], "effects": [], "midi": [], "modulation": []}
    assert build_profile_arguments(d7000)[-2:] == [
        "--diagnostic-profile", "hall-o2-stage7-v1"]
    incomplete = {**d7000, "engines": ["macro", "shapes"]}
    with pytest.raises(ValueError, match="engines: drums, sixop"):
        build_profile_arguments(incomplete)
    assert build_profile_arguments(d9000) == [
        "--flash-layout", "expanded-d9000", "--runtime-mode", "diagnostic",
        "--wavetable-profile", "compressed-required-banks-flash-plaits-v1"]


@pytest.mark.parametrize(("group", "module"), [
    ("engines", "macro"), ("engines", "shapes"), ("engines", "sixop"),
    ("engines", "drums"), ("effects", "hall"),
])
def test_worker_rejects_missing_named_profile_prerequisite(group, module):
    from tools.installer_service.docker_worker import build_profile_arguments

    request = {"engines": ["macro", "shapes", "sixop", "drums"],
               "effects": ["hall"], "midi": [], "modulation": [],
               "flash_layout": "expanded-d7000", "runtime_mode": "song-diagnostic"}
    request[group].remove(module)
    with pytest.raises(ValueError, match="requires caller-selected modules"):
        build_profile_arguments(request)


def test_worker_rejects_named_profile_module_in_wrong_group():
    from tools.installer_service.docker_worker import build_profile_arguments

    request = {"engines": ["macro", "shapes", "drums"],
               "effects": ["hall", "sixop"], "midi": [], "modulation": [],
               "flash_layout": "expanded-d7000", "runtime_mode": "song-diagnostic"}
    with pytest.raises(ValueError, match="engines: sixop"):
        build_profile_arguments(request)


def test_named_profile_forwards_fixed_flags_to_the_lower_builder():
    from tools.native import build_demo_image as builder

    assert builder.diagnostic_profile_flags("hall-o2-stage7-v1") == [
        "--hot-dsp-os", "--hall-o2", "--hot-dsp-ram", "--enable-trs-midi",
        "--diagnostic-telemetry",
        "--render-stage-profile", "--diagnostic-engine-render-profile",
        "--diagnostic-clock-snapshot",
    ]
    with pytest.raises(ValueError, match="Unsupported"):
        builder.diagnostic_profile_flags("hall-o2-stage8")


def test_named_profile_flags_are_in_the_actual_lower_builder_invocation(tmp_path, monkeypatch):
    from tools.native import build_demo_image as builder

    captured = {}
    monkeypatch.setattr(builder, "prepare_selection", lambda *a, **k: {
        "prepared_profile_sha256": "f" * 64, "startup_index": 0, "set_ids": [],
    })
    monkeypatch.setattr(builder, "load_prepared_profile", lambda *a: object())
    monkeypatch.setattr(builder, "checked_link_receipt", lambda *a, **k: {})
    monkeypatch.setattr(builder, "read_report", lambda *a: {
        "project_save_service": {"linked": True, "save_service_armed": False},
        "state_bin_codec": {},
    })
    monkeypatch.setattr(builder, "bounded_read", lambda *a: b"bounded receipt")

    def run(args, **kwargs):
        captured["args"] = args

    monkeypatch.setattr(builder.subprocess, "run", run)
    output = tmp_path / "out"
    builder.build_selection(
        {"version": 1, "engines": ["macro", "shapes", "sixop", "drums"], "effects": ["hall"],
         "midi": [], "modulation": [], "project_ids": ["project"],
         "startup_index": 0, "flash_layout": "expanded-d7000",
         "runtime_mode": "song-diagnostic"},
        "state-tool", "toolchain", "catalogue", output,
        runtime_mode="song-diagnostic",
        wavetable_profile=builder.SHAPES8_WAVETABLE_PROFILE,
        flash_layout="expanded-d7000", diagnostic_profile="hall-o2-stage7-v1",
    )
    args = captured["args"]
    assert args[args.index("--firmware-identity") + 1] == "FM-1_500"
    assert {"--hot-dsp-os", "--hall-o2", "--hot-dsp-ram", "--enable-trs-midi",
            "--diagnostic-telemetry", "--render-stage-profile",
            "--diagnostic-engine-render-profile", "--diagnostic-clock-snapshot"}.issubset(args)
    assert "--diagnostic-song-play" not in args
    assert "--diagnostic-cpu-rate" not in args



@pytest.mark.parametrize(("engines", "effects", "missing"), [
    (["macro", "shapes"], [], "effects: hall; engines: drums, sixop"),
    (["macro", "shapes", "drums"], ["hall", "sixop"], "engines: sixop"),
    (["shapes", "sixop", "drums"], ["hall"], "engines: macro"),
    (["macro", "sixop", "drums"], ["hall"], "engines: shapes"),
    (["macro", "shapes", "sixop", "drums", "hall"], [], "effects: hall"),
])
def test_named_profile_refuses_missing_or_misgrouped_modules_before_build_output(
        tmp_path, engines, effects, missing):
    from tools.native import build_demo_image as builder

    output = tmp_path / "out"
    with pytest.raises(ValueError, match=missing):
        builder.build_selection(
            {"version": 1, "engines": engines, "effects": effects,
             "midi": [], "modulation": [], "project_ids": ["project"],
             "startup_index": 0, "flash_layout": "expanded-d7000",
             "runtime_mode": "song-diagnostic"},
            "state-tool", "toolchain", "catalogue", output,
            runtime_mode="song-diagnostic",
            wavetable_profile=builder.SHAPES8_WAVETABLE_PROFILE,
            flash_layout="expanded-d7000", diagnostic_profile="hall-o2-stage7-v1",
        )
    assert not output.exists()


def test_lower_catalogue_checker_rejects_uniform_catalogue_for_hall_profile(tmp_path):
    from tools.native.build_application_probe import checked_catalogue
    from tools.native.compile_catalogue import source_manifest
    from tools.native.build_application_probe import ROOT

    root = tmp_path / "catalogue"
    shard = root / "shard-00"
    shard.mkdir(parents=True)
    expected = ["our/src/mi_sixop.o", "our/src/fx_hall.o"]
    (shard / "objects.json").write_text(json.dumps(expected))
    report = {
        "shard": 0, "chunks": 16, "catalogue_objects": len(expected),
        "gpl_mods": 1, "modules": "all", "optimization": "-Oz", "lto": True,
        "shared_resampler": True, "indexed_tft": True, "shapes_voices": 8,
        "closed_sdk_archives": [], "hot_dsp_ram": True,
        "engine_render_profile": True, "device_sdk_headers": [],
        "optimization_overrides": {}, "limiter_os": False, "hall_o2": True,
        "source_manifest": source_manifest(ROOT),
    }
    (shard / "report.json").write_text(json.dumps(report))
    output = tmp_path / "build-output"
    with pytest.raises(SystemExit, match="optimization overrides"):
        checked_catalogue(root, indexed_tft=True, shapes_voices=8,
                          hot_dsp_os=True, hot_dsp_ram=True,
                          engine_render_profile=True, hall_o2=True)
    assert not output.exists()
