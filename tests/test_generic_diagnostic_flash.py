import json
from dataclasses import replace
from pathlib import Path

import pytest

from tools.native import generic_diagnostic_flash as module
from tools.fm1_flash_transaction import create_transaction, digest, encoded


class MemoryROM:
    def __init__(self, flash, binding, *, fail_after_program=False):
        self.flash = bytearray(flash)
        self._binding = binding
        self.closed = False
        self.fail_after_program = fail_after_program
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
