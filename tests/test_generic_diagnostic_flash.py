import json
from dataclasses import replace
from pathlib import Path

import pytest

from tools.native import generic_diagnostic_flash as module
from tools.native import build_application_probe as builder
from tools.fm1_flash_transaction import create_transaction, digest, encoded


def test_schema6_irq_receipt_is_exact_and_strictly_typed():
    receipt = {
        "enabled": True, "schema": 6,
        "compile_definition": "LUNAR_DIAGNOSTIC_IRQ_PROFILE=1",
        "frame_bytes": 119, "packets_per_frame": 40,
        "transport": "USB-MIDI-SysEx", "hardware_tested": False,
    }
    assert module._exact_irq_profile_receipt(receipt)
    for key, value in (("schema", True), ("frame_bytes", True),
                       ("packets_per_frame", 41), ("hardware_tested", True)):
        changed = dict(receipt, **{key: value})
        assert not module._exact_irq_profile_receipt(changed)
    assert not module._exact_irq_profile_receipt(dict(receipt, extra=False))


def _schema7_receipts():
    engine = json.loads(json.dumps(builder.engine_render_profile_configuration(True)))
    stages = builder.render_stage_profile_configuration(True)
    return engine, stages


def test_schema7_engine_profile_receipt_is_exact_and_strictly_typed():
    engine, stages = _schema7_receipts()
    assert module._exact_engine_render_profile_receipt(engine)
    assert module._exact_render_stage_profile_receipt(stages)
    for key, value in (("schema", True), ("frame_bytes", True),
                       ("packets_per_frame", 19), ("hardware_tested", True),
                       ("counter_semantics", "per-window")):
        assert not module._exact_engine_render_profile_receipt(dict(engine, **{key: value}))
    assert not module._exact_engine_render_profile_receipt(dict(engine, extra=False))
    assert not module._exact_render_stage_profile_receipt(dict(stages, schema=True))
    assert not module._exact_render_stage_profile_receipt(dict(stages, stages=[]))


def test_song_profile_may_omit_autoplay_only_for_exact_irq_profile(monkeypatch):
    irq = {
        "enabled": True, "schema": 6,
        "compile_definition": "LUNAR_DIAGNOSTIC_IRQ_PROFILE=1",
        "frame_bytes": 119, "packets_per_frame": 40,
        "transport": "USB-MIDI-SysEx", "hardware_tested": False,
    }
    base = {
        "diagnostic_trio_pulse": {
            "enabled": False, "compile_definition": None, "note": None,
            "velocity": None, "start_ms": None, "end_ms": None,
            "once": True, "hardware_tested": False,
        },
        "diagnostic_telemetry": {
            "enabled": True, "compile_definition": "LUNAR_DIAGNOSTIC_TELEMETRY=1",
            "interval_ms": 1000, "transport": "USB-MIDI-SysEx",
            "hardware_tested": False,
        },
    }
    monkeypatch.setattr(module, "_validate_event_horizon_set_profile",
                        lambda *_args: {"validated": True})
    record = {"kind": module.SONG_INPUT_KIND}
    disabled_play = builder.validate_diagnostic_song_play(
        False, "song-diagnostic", None, True, False)
    assert disabled_play == {
        "enabled": False, "compile_definition": None, "start_ms": None,
        "once": False, "hardware_tested": False,
    }
    actual_builder_receipt = dict(base, diagnostic_irq_profile=irq,
                                  diagnostic_song_play=disabled_play)
    assert module._validate_diagnostic_mode(record, {}, actual_builder_receipt, b"") == {"validated": True}

    with pytest.raises(ValueError, match="bounded one-shot PLAY"):
        module._validate_diagnostic_mode(record, {}, base, b"")
    with pytest.raises(ValueError, match="bounded one-shot PLAY"):
        module._validate_diagnostic_mode(
            record, {}, dict(base, diagnostic_song_play=disabled_play), b"")
    with pytest.raises(ValueError, match="IRQ profile telemetry receipt differs"):
        module._validate_diagnostic_mode(record, {},
                                        dict(base, diagnostic_irq_profile=dict(irq, frame_bytes=118)), b"")
    valid_producer = {
        "enabled": True, "schema": 5,
        "compile_definition": "LUNAR_DIAGNOSTIC_PRODUCER_GAPS=1",
        "frame_bytes": 59, "packets_per_frame": 20,
        "transport": "USB-MIDI-SysEx", "hardware_tested": False,
    }
    with pytest.raises(ValueError, match="bounded one-shot PLAY"):
        module._validate_diagnostic_mode(record, {},
                                        dict(base, diagnostic_producer_gaps=valid_producer), b"")

    malformed_play = dict(disabled_play, once=True)
    with pytest.raises(ValueError, match="bounded one-shot PLAY"):
        module._validate_diagnostic_mode(record, {},
                                        dict(base, diagnostic_irq_profile=irq,
                                             diagnostic_song_play=malformed_play), b"")


def test_song_profile_accepts_exact_schema7_plus_schema2_and_preserves_default_receipts(monkeypatch):
    monkeypatch.setattr(module, "_validate_event_horizon_set_profile",
                        lambda *_args: {"validated": True})
    base = {
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
            "enabled": True, "compile_definition": "LUNAR_DIAGNOSTIC_SONG_PLAY=1",
            "start_ms": 2000, "once": True, "hardware_tested": False,
        },
    }
    record = {"kind": module.SONG_INPUT_KIND}
    # The schema-7 build alternates four bounded telemetry slots. Its schema-2
    # stage frame therefore arrives about every four seconds, versus two
    # seconds for the default two-slot telemetry build.
    engine, stages = _schema7_receipts()
    opted_in = dict(base, diagnostic_engine_render_profile=engine,
                    render_stage_profile=stages)
    assert module._validate_diagnostic_mode(record, {}, opted_in, b"") == {"validated": True}

    disabled_play = builder.validate_diagnostic_song_play(
        False, "song-diagnostic", None, True, False)
    no_autoplay = dict(opted_in, diagnostic_song_play=disabled_play)
    assert module._validate_diagnostic_mode(record, {}, no_autoplay, b"") == {"validated": True}

    # Older standard diagnostics omit both optional profiling fields and keep
    # their existing one-shot-play receipt contract.
    assert module._validate_diagnostic_mode(record, {}, base, b"") == {"validated": True}

    for bad_engine in (dict(engine, frame_bytes=53), dict(engine, schema=True),
                       dict(engine, hardware_tested=True)):
        with pytest.raises(ValueError, match="engine render profile receipt differs"):
            module._validate_diagnostic_mode(
                record, {}, dict(base, diagnostic_engine_render_profile=bad_engine,
                                 render_stage_profile=stages), b"")
    with pytest.raises(ValueError, match="exact schema-2 render-stage"):
        module._validate_diagnostic_mode(
            record, {}, dict(base, diagnostic_engine_render_profile=engine), b"")
    with pytest.raises(ValueError, match="exact schema-2 render-stage"):
        module._validate_diagnostic_mode(
            record, {}, dict(base, diagnostic_engine_render_profile=engine,
                             render_stage_profile=dict(stages, schema=3)), b"")
    with pytest.raises(ValueError, match="engine render profile receipt differs"):
        module._validate_diagnostic_mode(
            record, {}, dict(no_autoplay, diagnostic_engine_render_profile=dict(engine, schema=True)), b"")
    with pytest.raises(ValueError, match="exact schema-2 render-stage"):
        module._validate_diagnostic_mode(
            record, {}, dict(no_autoplay, render_stage_profile=dict(stages, schema=True)), b"")
    malformed_disabled_play = dict(disabled_play, once=True)
    with pytest.raises(ValueError, match="bounded one-shot PLAY"):
        module._validate_diagnostic_mode(
            record, {}, dict(opted_in, diagnostic_song_play=malformed_disabled_play), b"")

    irq = {
        "enabled": True, "schema": 6,
        "compile_definition": "LUNAR_DIAGNOSTIC_IRQ_PROFILE=1",
        "frame_bytes": 119, "packets_per_frame": 40,
        "transport": "USB-MIDI-SysEx", "hardware_tested": False,
    }
    producer = {
        "enabled": True, "schema": 5,
        "compile_definition": "LUNAR_DIAGNOSTIC_PRODUCER_GAPS=1",
        "frame_bytes": 59, "packets_per_frame": 20,
        "transport": "USB-MIDI-SysEx", "hardware_tested": False,
    }
    for incompatible in (dict(opted_in, diagnostic_irq_profile=irq),
                         dict(opted_in, diagnostic_producer_gaps=producer)):
        with pytest.raises(ValueError, match="cannot share producer-gap or IRQ cadence"):
            module._validate_diagnostic_mode(record, {}, incompatible, b"")
    for incompatible in (dict(no_autoplay, diagnostic_irq_profile=irq),
                         dict(no_autoplay, diagnostic_producer_gaps=producer)):
        with pytest.raises(ValueError, match="cannot share producer-gap or IRQ cadence"):
            module._validate_diagnostic_mode(record, {}, incompatible, b"")


def test_song_profile_accepts_exact_profiler_off_clock_diagnostic_without_autoplay(monkeypatch):
    monkeypatch.setattr(module, "_validate_event_horizon_set_profile",
                        lambda *_args: {"validated": True})
    base = {
        "diagnostic_trio_pulse": {
            "enabled": False, "compile_definition": None, "note": None,
            "velocity": None, "start_ms": None, "end_ms": None,
            "once": True, "hardware_tested": False,
        },
        "diagnostic_telemetry": {
            "enabled": True, "compile_definition": "LUNAR_DIAGNOSTIC_TELEMETRY=1",
            "interval_ms": 1000, "transport": "USB-MIDI-SysEx", "hardware_tested": False,
        },
        "diagnostic_song_play": builder.validate_diagnostic_song_play(
            False, "song-diagnostic", None, True, False),
        "diagnostic_clock_snapshot": json.loads(json.dumps(
            builder.validate_clock_snapshot(True, "song-diagnostic", True))),
    }
    record = {"kind": module.SONG_INPUT_KIND}
    assert module._validate_diagnostic_mode(record, {}, base, b"") == {"validated": True}

    for changed in (
        dict(base, diagnostic_clock_snapshot=dict(base["diagnostic_clock_snapshot"], schema=True)),
        dict(base, diagnostic_clock_snapshot=dict(base["diagnostic_clock_snapshot"],
                                                  supplemental_schema=3)),
        dict(base, diagnostic_clock_snapshot=dict(base["diagnostic_clock_snapshot"],
                                                  register_writes=True)),
        dict(base, diagnostic_clock_snapshot=dict(base["diagnostic_clock_snapshot"],
                                                  supplemental_register_addresses=["0x119a0"])),
        dict(base, render_stage_profile=builder.render_stage_profile_configuration(True)),
        dict(base, diagnostic_song_play=dict(base["diagnostic_song_play"], once=True)),
    ):
        with pytest.raises(ValueError, match="bounded one-shot PLAY"):
            module._validate_diagnostic_mode(record, {}, changed, b"")

    irq = {
        "enabled": True, "schema": 6,
        "compile_definition": "LUNAR_DIAGNOSTIC_IRQ_PROFILE=1",
        "frame_bytes": 119, "packets_per_frame": 40,
        "transport": "USB-MIDI-SysEx", "hardware_tested": False,
    }
    producer = {
        "enabled": True, "schema": 5,
        "compile_definition": "LUNAR_DIAGNOSTIC_PRODUCER_GAPS=1",
        "frame_bytes": 59, "packets_per_frame": 20,
        "transport": "USB-MIDI-SysEx", "hardware_tested": False,
    }
    for incompatible in (
        dict(base, diagnostic_irq_profile=dict(irq, frame_bytes=118)),
        dict(base, diagnostic_producer_gaps=producer),
    ):
        with pytest.raises(ValueError):
            module._validate_diagnostic_mode(record, {}, incompatible, b"")


def test_cpu_rate_admission_is_exact_and_standalone(monkeypatch):
    monkeypatch.setattr(module, "_validate_event_horizon_set_profile",
                        lambda *_args: {"validated": True})
    cpu = builder.diagnostic_cpu_rate_configuration(True)
    base = {
        "diagnostic_trio_pulse": {
            "enabled": False, "compile_definition": None, "note": None,
            "velocity": None, "start_ms": None, "end_ms": None,
            "once": True, "hardware_tested": False,
        },
        "diagnostic_telemetry": {
            "enabled": True, "compile_definition": "LUNAR_DIAGNOSTIC_TELEMETRY=1",
            "interval_ms": 1000, "transport": "USB-MIDI-SysEx", "hardware_tested": False,
        },
        "diagnostic_song_play": builder.validate_diagnostic_song_play(
            False, "song-diagnostic", None, True, False),
        "diagnostic_cpu_rate": cpu,
    }
    record = {"kind": module.SONG_INPUT_KIND}
    assert module._exact_cpu_rate_receipt(cpu)
    assert module._validate_diagnostic_mode(record, {}, base, b"") == {"validated": True}
    # Every field is required and type-checked, including bool versus integer.
    for key, value in cpu.items():
        bad = dict(cpu)
        del bad[key]
        assert not module._exact_cpu_rate_receipt(bad)
        replacement = int(value) if type(value) is bool else (True if type(value) is int else None)
        bad = dict(cpu, **{key: replacement})
        assert not module._exact_cpu_rate_receipt(bad)
        with pytest.raises(ValueError, match="standalone CPU-rate"):
            module._validate_diagnostic_mode(record, {}, dict(base, diagnostic_cpu_rate=bad), b"")
    for key in ("diagnostic_producer_gaps", "diagnostic_irq_profile",
                "diagnostic_engine_render_profile", "render_stage_profile"):
        with pytest.raises(ValueError, match="standalone CPU-rate"):
            module._validate_diagnostic_mode(record, {}, dict(base, **{key: {}}), b"")
    with pytest.raises(ValueError, match="standalone CPU-rate"):
        module._validate_diagnostic_mode(record, {}, dict(base, diagnostic_song_play=
            builder.validate_diagnostic_song_play(True, "song-diagnostic", 0, True, False)), b"")
    with pytest.raises(ValueError, match="Song-only"):
        module._validate_diagnostic_mode({"kind": module.INPUT_KIND}, {}, base, b"")
    with pytest.raises(ValueError, match="standalone CPU-rate"):
        module._validate_diagnostic_mode(record, {}, dict(base, diagnostic_clock_snapshot={}), b"")
    clock = json.loads(json.dumps(builder.validate_clock_snapshot(True, "song-diagnostic", True)))
    assert module._validate_diagnostic_mode(record, {}, dict(base, diagnostic_clock_snapshot=clock), b"") == {"validated": True}


def test_input_pulse_profile_rejects_schema7_engine_profile():
    verification = {
        "diagnostic_trio_pulse": {
            "enabled": True, "compile_definition": "LUNAR_DIAGNOSTIC_TRIO_PULSE=1",
            "note": 60, "velocity": 100, "start_ms": 3000, "end_ms": 5000,
            "once": True, "hardware_tested": False,
        },
        "diagnostic_engine_render_profile": _schema7_receipts()[0],
    }
    with pytest.raises(ValueError, match="Song-only timing telemetry"):
        module._validate_diagnostic_mode(
            {"kind": module.INPUT_KIND}, {}, verification, b"")


class MemoryROM:
    def __init__(self, flash, binding, *, fail_after_program=False, fail_after_erase=False):
        self.flash = bytearray(flash)
        self._binding = binding
        self.closed = False
        self.fail_after_program = fail_after_program
        self.fail_after_erase = fail_after_erase
        self.mutations = []

    def binding(self):
        return self._binding

    def close(self):
        self.closed = True

    def exchange(self, cdb, payload, in_size):
        op = int.from_bytes(cdb[:2], "big")
        address = int.from_bytes(cdb[2:6], "big")
        if op == 0xFC0A:
            result = bytearray(in_size)
            result[:2] = op.to_bytes(2, "big")
            result[2] = 3
            result[4:8] = (0x856014).to_bytes(4, "little")
            return bytes(result)
        if op == 0xFD05:
            return bytes(self.flash[address:address + in_size])
        if op == 0xFB01:
            self.mutations.append(("erase", address))
            self.flash[address:address + 4096] = b"\xff" * 4096
            if self.fail_after_erase:
                self.fail_after_erase = False
                raise OSError("simulated ambiguous erase completion")
        elif op == 0xFB04:
            self.mutations.append(("program", address))
            self.flash[address:address + len(payload)] = payload
            if self.fail_after_program:
                self.fail_after_program = False
                raise OSError("simulated ambiguous program completion")
        else:
            raise AssertionError(f"unexpected opcode {op:#x}")
        return op.to_bytes(2, "big").ljust(in_size, b"\0") if in_size else b""


def make_policy(tmp_path):
    baseline = bytearray(b"\xff" * module.FLASH_BYTES)
    baseline[:module.APP_BASE] = b"S" * module.APP_BASE
    baseline[module.CURRENT_END:] = b"Z" * (module.FLASH_BYTES - module.CURRENT_END)
    target = bytearray(baseline)
    target[module.APP_BASE + 4096:module.APP_BASE + 8192] = b"\x5a" * 4096
    target[module.APP_BASE:module.APP_BASE + 4096] = b"\xa5" * 4096
    identity = {"unit_id": "synthetic-test-only", "flash_size": module.FLASH_BYTES,
                "sector_size": 4096, "page_size": 256, "jedec": 0x856014,
                "simulated": False, "usb_port": "synthetic", "usb_topology": "synthetic"}
    ranges = [[module.APP_BASE, module.APP_BASE + 8192]]
    directory = tmp_path / "transaction"
    plan = create_transaction(directory, bytes(baseline), bytes(baseline), bytes(target),
                              identity, ranges, "test-only install and restore",
                              commit_sector=module.APP_BASE)
    receipt = {"schema": 1, "kind": module.KIND, "installable": False,
               "hardware_admitted": False, "physical_writer_ready": False}
    receipt_bytes = encoded(receipt)
    (directory / "diagnostic-receipt.json").write_bytes(receipt_bytes)
    pinned = tmp_path / "pinned-evidence.json"
    pinned.write_bytes(b"immutable synthetic evidence")
    read_manifest = "1" * 64
    campaign = "2" * 64
    commands = "3" * 64
    binding = {"phase": "loader", "loader_sha256": "4" * 64,
               "usb_binding": {"path": "1-1", "busnum": "1", "devnum": "55",
                               "vid": "4c4a", "pid": "8057"},
               "sg_binding": {"node": "/dev/sg-test", "inode": 1},
               "read_campaign_sha256": campaign, "read_manifest_sha256": read_manifest,
               "read_commands_sha256": commands, "baseline_sha256": digest(bytes(baseline)),
               "identity": identity}
    policy = module.Policy(directory, encoded(plan), bytes(baseline), bytes(target),
                           receipt_bytes, encoded(binding),
                           tuple(plan["sector_order"]),
                           ((pinned, pinned.read_bytes(), 1024),),
                           module.generic_boot.time.time(), module._VALIDATED)
    module._POLICIES.add(policy)
    return policy, bytes(baseline), bytes(target), binding


def fresh_restore_read(monkeypatch, binding, flash, *, usb=None, sg=None):
    now = module.generic_boot.time.time()
    read = {"manifest_path": Path("fresh/manifest.json"), "manifest_sha256": "5" * 64,
            "commands_sha256": "6" * 64, "campaign_sha256": "7" * 64,
            "expected_devnum": 55, "current_flash_sha256": digest(flash)}
    manifest = {"usb_binding": usb or binding["usb_binding"],
                "sg_binding": sg or binding["sg_binding"],
                "loader_sha256": binding["loader_sha256"],
                "current_flash_sha256": digest(flash)}
    monkeypatch.setattr(module.generic_boot, "verify_read_bundle",
                        lambda *args, **kwargs: {"manifest": manifest, "completed_at": now})
    transport_binding = dict(binding)
    transport_binding.update(usb_binding=manifest["usb_binding"],
                             sg_binding=manifest["sg_binding"],
                             read_campaign_sha256=read["campaign_sha256"],
                             read_manifest_sha256=read["manifest_sha256"],
                             read_commands_sha256=read["commands_sha256"],
                             baseline_sha256=digest(flash))
    return read, transport_binding


def test_install_recovery_then_direction_bound_current_restore(tmp_path, monkeypatch):
    policy, baseline, target, binding = make_policy(tmp_path)
    first = MemoryROM(baseline, binding, fail_after_program=True)
    with pytest.raises(OSError, match="ambiguous"):
        policy.bind(first).run()
    assert first.closed
    journal = json.loads((policy.directory / "journal.json").read_bytes())
    assert journal["state"] == "recovery_required"
    assert journal["direction"] == "install"

    resumed = MemoryROM(bytes(first.flash), binding)
    install_result = policy.bind(resumed, direction="install").run()
    assert install_result["direction"] == "install"
    assert bytes(resumed.flash) == target

    current_after_install = bytes(resumed.flash)
    restore_read, restore_binding = fresh_restore_read(monkeypatch, binding, current_after_install)
    restored = MemoryROM(current_after_install, restore_binding)
    restore_result = policy.bind(restored, direction="restore", restore_read=restore_read).run()
    assert restore_result["direction"] == "restore"
    assert bytes(restored.flash) == baseline
    assert restore_result["verified_sha256"] == digest(baseline)
    assert json.loads(policy.directory.joinpath("journal.json").read_bytes())["direction"] == "restore"
    assert policy.receipt()["hardware_admitted"] is False


def test_mutation_requests_cannot_escape_direction_or_sector_plan(tmp_path):
    policy, baseline, _, binding = make_policy(tmp_path)
    session = policy.bind(MemoryROM(baseline, binding))
    with pytest.raises(ValueError, match="changed sector"):
        session.build_request(0xFB01, address=module.APP_BASE + 8192)
    with pytest.raises(ValueError, match="exact direction-bound"):
        session.build_request(0xFB04, address=module.APP_BASE + 4096,
                              payload=b"X" * 256)
    with pytest.raises(ValueError, match="Direction"):
        policy.bind(MemoryROM(baseline, binding), direction="rollback")
    session.close()


def test_check_files_returns_actual_journal_and_freshness_only_at_bind(tmp_path, monkeypatch):
    policy, baseline, _, binding = make_policy(tmp_path)
    journal = policy.check_files()
    assert journal["state"] == "prepared"
    stale = replace(policy, read_completed_at=policy.read_completed_at - 1000)
    module._POLICIES.discard(policy)
    module._POLICIES.add(stale)
    with pytest.raises(ValueError, match="expired"):
        stale.bind(MemoryROM(baseline, binding))
    # Freshness is checked at bind; it does not expire an already-admitted long run.
    fresh = replace(stale, read_completed_at=module.generic_boot.time.time())
    module._POLICIES.discard(stale)
    module._POLICIES.add(fresh)
    session = fresh.bind(MemoryROM(baseline, binding))
    expired_after_bind = replace(fresh, read_completed_at=fresh.read_completed_at - 1000)
    module._POLICIES.add(expired_after_bind)
    assert expired_after_bind.check_files()["state"] == "prepared"
    session.close()

    # A long install may outlive the original 120s read. Recovery uses a new
    # paired-read for the same device and keeps the transaction's old baseline.
    fresh_read, fresh_binding = fresh_restore_read(monkeypatch, binding, baseline)
    restored = fresh.bind(MemoryROM(baseline, fresh_binding), direction="restore",
                          restore_read=fresh_read)
    assert restored._policy.direction == "restore"
    restored.close()


def test_restore_rejects_unbound_or_wrong_device_fresh_read(tmp_path, monkeypatch):
    policy, baseline, _, binding = make_policy(tmp_path)
    fresh_read, fresh_binding = fresh_restore_read(monkeypatch, binding, baseline)
    with pytest.raises(ValueError, match="new fresh paired"):
        policy.bind(MemoryROM(baseline, fresh_binding), direction="restore")
    wrong_usb = dict(binding["usb_binding"], path="different")
    fresh_read2, _ = fresh_restore_read(monkeypatch, binding, baseline)
    monkeypatch.setattr(module.generic_boot, "verify_read_bundle",
        lambda *args, **kwargs: {"manifest": {"usb_binding": wrong_usb,
            "sg_binding": binding["sg_binding"], "loader_sha256": binding["loader_sha256"],
            "current_flash_sha256": digest(baseline)}})
    with pytest.raises(ValueError, match="same physical USB"):
        policy.bind(MemoryROM(baseline, fresh_binding), direction="restore",
                    restore_read=fresh_read2)


def test_restore_accepts_new_devnum_and_sg_node_on_same_physical_port(tmp_path, monkeypatch):
    policy, baseline, _, binding = make_policy(tmp_path)
    new_usb = dict(binding["usb_binding"], devnum="56")
    new_sg = {"node": "/dev/sg-next", "inode": 2}
    fresh_read, fresh_binding = fresh_restore_read(monkeypatch, binding, baseline,
                                                   usb=new_usb, sg=new_sg)
    restored = MemoryROM(baseline, fresh_binding)
    session = policy.bind(restored, direction="restore", restore_read=fresh_read)
    assert session._policy.direction == "restore"
    session.close()


def test_restore_reread_must_match_fresh_manifest_before_any_mutation(tmp_path, monkeypatch):
    policy, baseline, target, binding = make_policy(tmp_path)
    fresh_read, fresh_binding = fresh_restore_read(monkeypatch, binding, target)
    actual = bytearray(target)
    actual[module.APP_BASE + 4096] ^= 1
    transport = MemoryROM(bytes(actual), fresh_binding)
    with pytest.raises(ValueError, match="reread differs"):
        policy.bind(transport, direction="restore", restore_read=fresh_read).run()
    assert bytes(transport.flash) == bytes(actual)
    assert transport.mutations == []
    assert transport.closed


def interrupted_policy(tmp_path):
    policy, baseline, target, binding = make_policy(tmp_path)
    first = MemoryROM(baseline, binding, fail_after_program=True)
    with pytest.raises(OSError, match="ambiguous"):
        policy.bind(first).run()
    assert first.closed
    # Command failure never retries this consumed transport.
    assert len(first.mutations) == 1
    return policy, baseline, target, binding, bytes(first.flash)


def test_explicit_resume_reconnects_and_restores_with_new_mapping(tmp_path, monkeypatch):
    policy, baseline, target, binding, partial = interrupted_policy(tmp_path)
    old = policy.read_completed_at
    monkeypatch.setattr(module.generic_boot.time, "time", lambda: old + 1000)
    usb = dict(binding["usb_binding"], devnum="56")
    read, new_binding = fresh_restore_read(monkeypatch, binding, partial,
        usb=usb, sg={"node": "/dev/sg-resume", "inode": 2})
    with pytest.raises(ValueError, match="expired"):
        policy.bind(MemoryROM(partial, binding))
    admission = policy.admit_resume(read)
    rom = MemoryROM(partial, new_binding)
    session = policy.bind(rom, resume=admission)
    with pytest.raises(ValueError, match="consumed"):
        policy.bind(MemoryROM(partial, new_binding), resume=admission)
    def checkpoint(event, **fields):
        if event == "durable_intent":
            journal = json.loads((policy.directory / "journal.json").read_bytes())
            assert journal["intent"] == {"operation": fields["operation"], "address": fields["address"]}
    result = session.run(checkpoint)
    assert bytes(rom.flash) == target
    assert result["verified_sha256"] == digest(target)
    restore_read, restore_binding = fresh_restore_read(monkeypatch, binding, target,
        usb=dict(usb, devnum="57"), sg={"node": "/dev/sg-restore", "inode": 3})
    restored = MemoryROM(target, restore_binding)
    assert policy.bind(restored, direction="restore", restore_read=restore_read).run()["verified_sha256"] == digest(baseline)
    assert bytes(restored.flash) == baseline and restored.mutations


@pytest.mark.parametrize("state,direction", [("prepared", None), ("complete", "install"), ("recovery_required", "restore")])
def test_resume_requires_interrupted_install(tmp_path, monkeypatch, state, direction):
    from fm1_flash_transaction import save_journal
    policy, baseline, _, binding = make_policy(tmp_path)
    journal = policy.check_files()
    journal.update(state=state, direction=direction)
    save_journal(policy.directory, journal)
    read, _ = fresh_restore_read(monkeypatch, binding, baseline)
    with pytest.raises(ValueError, match="interrupted install"):
        policy.admit_resume(read)


@pytest.mark.parametrize("change", ["port", "loader", "stale"])
def test_resume_fresh_evidence_rejects_wrong_loader_port_or_age(tmp_path, monkeypatch, change):
    policy, _, _, binding, partial = interrupted_policy(tmp_path)
    read, _ = fresh_restore_read(monkeypatch, binding, partial)
    manifest = {"usb_binding": dict(binding["usb_binding"]), "sg_binding": binding["sg_binding"],
        "loader_sha256": binding["loader_sha256"], "current_flash_sha256": digest(partial)}
    now = module.generic_boot.time.time()
    if change == "port": manifest["usb_binding"]["path"] = "different"
    if change == "loader": manifest["loader_sha256"] = "f" * 64
    monkeypatch.setattr(module.generic_boot, "verify_read_bundle", lambda *a, **k:
        {"manifest": manifest, "completed_at": now - (1000 if change == "stale" else 0)})
    with pytest.raises(ValueError, match="same physical|expired"):
        policy.admit_resume(read)


@pytest.mark.parametrize("change", ["journal", "evidence", "target", "receipt"])
def test_resume_rechecks_sealed_artifacts_before_binding(tmp_path, monkeypatch, change):
    from fm1_flash_transaction import save_journal
    policy, _, _, binding, partial = interrupted_policy(tmp_path)
    read, new_binding = fresh_restore_read(monkeypatch, binding, partial)
    admission = policy.admit_resume(read)
    if change == "journal":
        journal = policy.check_files(); journal["error"] = "changed"
        save_journal(policy.directory, journal)
    elif change == "evidence": Path(policy.evidence[0][0]).write_bytes(b"changed")
    elif change == "target": (policy.directory / "target.bin").write_bytes(b"changed")
    else: (policy.directory / "diagnostic-receipt.json").write_bytes(b"changed")
    with pytest.raises(ValueError): policy.bind(MemoryROM(partial, new_binding), resume=admission)


@pytest.mark.parametrize("outside", [False, True])
def test_resume_complete_reread_blocks_mismatch_and_immutable_change(tmp_path, monkeypatch, outside):
    policy, _, _, binding, partial = interrupted_policy(tmp_path)
    actual = bytearray(partial)
    actual[0 if outside else module.APP_BASE + 4096] ^= 1
    read, new_binding = fresh_restore_read(monkeypatch, binding, bytes(actual) if outside else partial)
    admission = policy.admit_resume(read)
    rom = MemoryROM(bytes(actual), new_binding)
    with pytest.raises(ValueError): policy.bind(rom, resume=admission).run()
    assert not rom.mutations and rom.closed


def test_resume_deadline_expiring_after_bind_blocks_before_mutation(tmp_path, monkeypatch):
    policy, _, _, binding, partial = interrupted_policy(tmp_path)
    read, new_binding = fresh_restore_read(monkeypatch, binding, partial)
    admission = policy.admit_resume(read)
    rom = MemoryROM(partial, new_binding)
    session = policy.bind(rom, resume=admission)
    monkeypatch.setattr(module.generic_boot.time, "monotonic", lambda: admission.deadline + 1)
    with pytest.raises(ValueError, match="deadline"): session.run()
    assert not rom.mutations and rom.closed


def test_plain_or_copied_resume_capability_is_not_authority(tmp_path, monkeypatch):
    policy, _, _, binding, partial = interrupted_policy(tmp_path)
    read, new_binding = fresh_restore_read(monkeypatch, binding, partial)
    admission = policy.admit_resume(read)
    for forged in (dict(admission.__dict__), replace(admission)):
        with pytest.raises(ValueError, match="resume admission"):
            policy.bind(MemoryROM(partial, new_binding), resume=forged)


def test_resume_rejects_cross_policy_and_deserialized_capabilities(tmp_path, monkeypatch):
    import pickle
    policy, _, _, binding, partial = interrupted_policy(tmp_path / "one")
    other, _, _, _, _ = interrupted_policy(tmp_path / "two")
    read, new_binding = fresh_restore_read(monkeypatch, binding, partial)
    admission = policy.admit_resume(read)
    with pytest.raises(ValueError, match="Factory-created"):
        other.bind(MemoryROM(partial, new_binding), resume=admission)
    # Copy/pickle round-trips do not carry process-local registry authority.
    restored = pickle.loads(pickle.dumps(admission))
    with pytest.raises(ValueError, match="Factory-created"):
        policy.bind(MemoryROM(partial, new_binding), resume=restored)


def test_resume_fresh_evidence_changes_after_bind_block_before_mutation(tmp_path, monkeypatch):
    policy, _, _, binding, partial = interrupted_policy(tmp_path)
    read, new_binding = fresh_restore_read(monkeypatch, binding, partial)
    verified = module.generic_boot.verify_read_bundle()
    evidence = tmp_path / "fresh-read-evidence"
    evidence.write_bytes(b"fresh paired evidence")
    verified["evidence"] = ((evidence, evidence.read_bytes(), 100),)
    monkeypatch.setattr(module.generic_boot, "verify_read_bundle", lambda *a, **k: verified)
    admission = policy.admit_resume(read)
    rom = MemoryROM(partial, new_binding)
    session = policy.bind(rom, resume=admission)
    def checkpoint(event, **fields):
        if event == "durable_intent": evidence.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="resume evidence changed"):
        session.run(checkpoint)
    assert rom.closed and not rom.mutations


def test_resume_accepts_crash_journal_running_with_durable_intent(tmp_path, monkeypatch):
    from fm1_flash_transaction import save_journal
    policy, _, target, binding, partial = interrupted_policy(tmp_path)
    journal = policy.check_files()
    assert journal["intent"]["operation"] == "program"
    journal["state"] = "running"
    save_journal(policy.directory, journal)
    read, new_binding = fresh_restore_read(monkeypatch, binding, partial)
    session = policy.bind(MemoryROM(partial, new_binding), resume=policy.admit_resume(read))
    assert session.run()["verified_sha256"] == digest(target)


def test_resume_ambiguous_erase_stops_and_requires_new_admission(tmp_path, monkeypatch):
    policy, _, target, binding, partial = interrupted_policy(tmp_path)
    read, new_binding = fresh_restore_read(monkeypatch, binding, partial)
    rom = MemoryROM(partial, new_binding, fail_after_erase=True)
    session = policy.bind(rom, resume=policy.admit_resume(read))
    with pytest.raises(OSError, match="ambiguous erase"):
        session.run()
    assert rom.closed and len(rom.mutations) == 1
    assert policy.check_files()["intent"]["operation"] == "erase"
    read2, binding2 = fresh_restore_read(monkeypatch, binding, bytes(rom.flash),
        usb=dict(binding["usb_binding"], devnum="58"), sg={"node": "/dev/sg-after-erase"})
    recovered = MemoryROM(bytes(rom.flash), binding2)
    assert policy.bind(recovered, resume=policy.admit_resume(read2)).run()["verified_sha256"] == digest(target)
    assert bytes(recovered.flash) == target
