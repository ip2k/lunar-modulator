#!/usr/bin/env python3
"""Deterministic, process-reopened recovery fault campaign. MIT.

Only synthetic bytes and a modeled device are used. No physical transport is
opened or called, no private firmware is needed, and receipts are model evidence only.
Synthetic app digests are a boot-health oracle, not execution of FM-1 firmware.
Run on the authorized compute host, for example --case-range 0:125 --output
receipts.json. Ranges are half-open; --list reports the stable indexed catalog.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from fm1_flash_transaction import create_transaction, run_transaction
from fm1_simulated_device import SimulatedDevice

FLASH_SIZE = 1024 * 1024
SECTOR_SIZE = 4096
PAGE_SIZE = 256
APP_RANGE = (0x4000, 0x6000)
SEED = 20261011
LOADER = (b"LUNAR MODEL ONLY RECOVERY FIXTURE\0" * 800)[:24064]
LOADER_SHA256 = hashlib.sha256(LOADER).hexdigest()


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def fixtures(seed: int = SEED) -> tuple[bytes, bytes]:
    """Public reproducible fixture, unrelated to any vendor image or loader."""
    block = hashlib.shake_256(f"lunar-synthetic-stock:{seed}".encode()).digest(4096)
    stock = block * (FLASH_SIZE // len(block))
    app = hashlib.shake_256(f"lunar-synthetic-diagnostic:{seed}".encode()).digest(
        APP_RANGE[1] - APP_RANGE[0])
    target = stock[:APP_RANGE[0]] + app + stock[APP_RANGE[1]:]
    return stock, target


def case_catalog() -> list[dict]:
    cases = [{"name": "baseline", "kind": "baseline", "direction": "install"}]
    for direction in ("install", "restore"):
        for page in range(32):
            for prefix in (0, 1, 127, 255, 256):
                cases.append(dict(name=f"{direction}-torn-page-{page:02d}-{prefix}",
                                  kind="fault", direction=direction,
                                  operation="program", fault="torn",
                                  occurrence=page + 1, after_bytes=prefix))
        for operation, count in (("erase", 2), ("program", 32)):
            for occurrence in range(1, count + 1):
                for fault in ("disconnect_before", "ack_loss"):
                    cases.append(dict(name=f"{direction}-{operation}-{occurrence}-{fault}",
                                      kind="fault", direction=direction,
                                      operation=operation, occurrence=occurrence,
                                      fault=fault))
        for occurrence in (1, 2):
            for prefix in (0, 1, 2047, 4095, 4096):
                cases.append(dict(name=f"{direction}-torn-erase-{occurrence}-{prefix}",
                                  kind="fault", direction=direction,
                                  operation="erase", fault="torn",
                                  occurrence=occurrence, after_bytes=prefix))
        for kind in ("verify_corruption", "crash_intent", "crash_after_write"):
            cases.append(dict(name=f"{direction}-{kind}", kind=kind,
                              direction=direction))
    for kind in ("usb_key_recovery", "stale_handle", "completed_journal_readback",
                 "corrupt_backup_a", "corrupt_backup_b", "corrupt_target",
                 "corrupt_journal", "corrupt_plan", "wrong_unit", "out_of_range",
                 "unexpected_preflight_change", "corrupt_journal_state",
                 "corrupt_journal_direction", "corrupt_journal_intent"):
        cases.append(dict(name=kind, kind=kind, direction="install"))
    return [dict(index=i, **case) for i, case in enumerate(cases)]


def _open(directory: Path) -> SimulatedDevice:
    return SimulatedDevice(path=directory / "device")


def _session(device: SimulatedDevice):
    if device.mode == "app" and device.connected:
        device.soft_key()
    return device.recovery_session(LOADER)


def _assert_image(device: SimulatedDevice, expected: bytes) -> None:
    session = _session(device)
    actual = session.read(0, FLASH_SIZE)
    assert actual == expected, "full-image readback differs (including preserved ranges)"
    device.reset()
    assert device.mode == "app", "synthetic registered image did not boot"


def _worker(directory: Path, case: dict) -> int:
    """Faulting process: all recovery happens after this process has exited."""
    import os
    device = _open(directory)
    session = _session(device)
    kind = case["kind"]
    if kind == "fault":
        options = dict(operation=case["operation"], kind=case["fault"],
                       occurrence=case["occurrence"])
        if "after_bytes" in case:
            options["after_bytes"] = case["after_bytes"]
        device.inject_failure(**options)
    injected = False

    def checkpoint(event, **fields):
        nonlocal injected
        if kind == "crash_intent" and event == "durable_intent":
            os._exit(86)
        if (kind == "crash_after_write" and event == "operation_returned"
                and fields.get("operation") == "program"):
            os._exit(86)
        if kind == "verify_corruption" and event == "operation_returned" and not injected:
            device.inject_failure(operation="read", kind="corrupt_read")
            injected = True

    try:
        run_transaction(directory / "transaction", session,
                        direction=case["direction"], checkpoint=checkpoint)
        result = {"status": "completed"}
    except Exception as exc:
        result = {"status": "rejected", "error_type": type(exc).__name__}
    (directory / "worker-result.json").write_bytes(canonical(result) + b"\n")
    return 0


def _attempt(directory: Path, case: dict) -> dict:
    (directory / "worker-case.json").write_bytes(canonical(case))
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--worker", str(directory)],
        capture_output=True, text=True, timeout=120)
    if case["kind"] in ("crash_intent", "crash_after_write"):
        assert result.returncode == 86, f"crash checkpoint not reached: {result.stderr[-1000:]}"
        return {"status": "process_exit", "exit_code": 86}
    assert result.returncode == 0, f"worker failed: {result.stderr[-2000:]}"
    evidence = json.loads((directory / "worker-result.json").read_text())
    expected = "completed" if case["kind"] == "baseline" else "rejected"
    assert evidence["status"] == expected, f"fault was not detected: {case['name']}"
    return evidence


def _reject(callable_) -> str:
    try:
        callable_()
    except (ValueError, OSError, RuntimeError) as exc:
        return type(exc).__name__
    raise AssertionError("unsafe operation was not rejected")


def _corrupt_file(path: Path) -> None:
    value = bytearray(path.read_bytes())
    value[len(value) // 2] ^= 1
    path.write_bytes(value)


class _NoWrites:
    """Rejection cases must not even request a mutation, including a no-op."""
    def __init__(self, session):
        self.session = session

    def __getattr__(self, name):
        if name in ("erase", "program"):
            raise AssertionError("rejected case attempted a flash mutation")
        return getattr(self.session, name)


def _fault_snapshot(case: dict, stock: bytes, target: bytes) -> bytes:
    initial, desired = (stock, target) if case["direction"] == "install" else (target, stock)
    expected = bytearray(initial)
    if case["operation"] == "program":
        page = case["occurrence"] - 1
        address = APP_RANGE[0] + page * PAGE_SIZE
        sector = address // SECTOR_SIZE * SECTOR_SIZE
        expected[APP_RANGE[0]:sector] = desired[APP_RANGE[0]:sector]
        expected[sector:sector + SECTOR_SIZE] = b"\xff" * SECTOR_SIZE
        expected[sector:address] = desired[sector:address]
        count = (case.get("after_bytes", 0) if case["fault"] == "torn"
                 else PAGE_SIZE if case["fault"] == "ack_loss" else 0)
        expected[address:address + count] = desired[address:address + count]
    else:
        address = APP_RANGE[0] + (case["occurrence"] - 1) * SECTOR_SIZE
        expected[APP_RANGE[0]:address] = desired[APP_RANGE[0]:address]
        count = (case.get("after_bytes", 0) if case["fault"] == "torn"
                 else SECTOR_SIZE if case["fault"] == "ack_loss" else 0)
        expected[address:address + count] = b"\xff" * count
    return bytes(expected)


def run_case(root: Path, case: dict, seed: int = SEED) -> dict:
    directory = root / f"case-{case['index']:04d}"
    directory.mkdir(parents=True, exist_ok=False)
    stock, target = fixtures(seed)
    device = SimulatedDevice(stock, path=directory / "device",
                             writable_ranges=(APP_RANGE,),
                             protected_ranges=((0, APP_RANGE[0]), (APP_RANGE[1], FLASH_SIZE)),
                             app_range=APP_RANGE,
                             simulator_loader_sha256=LOADER_SHA256)
    device.register_bootable_image(stock)
    device.register_bootable_image(target)
    device.reset()
    assert device.mode == "app"
    session = _session(device)
    identity = session.identity()
    transaction = directory / "transaction"
    create_transaction(transaction, baseline_a=stock, baseline_b=stock,
                       target=target, identity=identity, writable_ranges=(APP_RANGE,),
                       scope="synthetic-model-app-only")
    device.reset()
    kind = case["kind"]
    evidence = {}
    if case["direction"] == "restore" or kind in ("completed_journal_readback", "usb_key_recovery"):
        run_transaction(transaction, _session(device))
        _assert_image(device, target)
    if kind in ("baseline", "fault", "verify_corruption", "crash_intent", "crash_after_write"):
        evidence = _attempt(directory, case)
        device = _open(directory)
        if kind == "fault":
            assert device.flash == _fault_snapshot(case, stock, target), "fault persistence differs"
            evidence["interrupted_flash_sha256"] = digest(device.flash)
        if device.mode == "app_unavailable":
            evidence["soft_key_rejection"] = _reject(device.soft_key)
            device.usb_key()
            assert device.mode == "rom"
            evidence["recovery_route"] = "simulated_usb_key"
        run_transaction(transaction, _session(device), direction=case["direction"])
        _assert_image(device, target if case["direction"] == "install" else stock)
    elif kind == "stale_handle":
        stale = _session(device)
        device.reset()
        evidence["rejection"] = _reject(lambda: stale.read(0, PAGE_SIZE))
        run_transaction(transaction, _session(device))
        _assert_image(device, target)
    elif kind in ("completed_journal_readback", "usb_key_recovery"):
        session = _session(device)
        session.erase(APP_RANGE[0])
        device.reset()
        assert device.mode == "app_unavailable"
        evidence["soft_key_rejection"] = _reject(device.soft_key)
        device.usb_key()
        assert device.mode == "rom"
        device = _open(directory)
        run_transaction(transaction, _session(device),
                        direction="restore" if kind == "usb_key_recovery" else "install")
        _assert_image(device, stock if kind == "usb_key_recovery" else target)
        evidence["recovery_route"] = "simulated_usb_key"
    else:
        filenames = {"corrupt_backup_a": "backupA.bin", "corrupt_backup_b": "backupB.bin",
                     "corrupt_target": "target.bin", "corrupt_journal": "journal.json",
                     "corrupt_plan": "plan.json"}
        if kind in filenames:
            _corrupt_file(transaction / filenames[kind])
            evidence["rejection"] = _reject(lambda: run_transaction(transaction, _NoWrites(_session(device))))
        elif kind.startswith("corrupt_journal_"):
            field = kind.removeprefix("corrupt_journal_")
            path = transaction / "journal.json"
            journal = json.loads(path.read_text())
            journal[field] = {"state": "recovery_required", "direction": "restore",
                              "intent": {"operation": "program", "address": APP_RANGE[0]}}[field]
            # Preserve the checksum to model unnoticed valid-JSON corruption.
            path.write_bytes(canonical(journal))
            evidence["rejection"] = _reject(lambda: run_transaction(
                transaction, _NoWrites(_session(device))))
        elif kind == "wrong_unit":
            other = SimulatedDevice(stock, path=directory / "other-device", unit_id="wrong-sim-unit",
                                    writable_ranges=(APP_RANGE,), app_range=APP_RANGE,
                                    simulator_loader_sha256=LOADER_SHA256)
            other.register_bootable_image(stock)
            evidence["rejection"] = _reject(lambda: run_transaction(transaction, _NoWrites(_session(other))))
            assert _session(other).read(0, FLASH_SIZE) == stock
        elif kind == "out_of_range":
            bad_target = bytes([stock[0] ^ 1]) + target[1:]
            evidence["rejection"] = _reject(lambda: create_transaction(
                directory / "unsafe", baseline_a=stock, baseline_b=stock,
                target=bad_target, identity=identity, writable_ranges=(APP_RANGE,),
                scope="synthetic-model-app-only"))
        elif kind == "unexpected_preflight_change":
            session = _session(device)
            session.erase(APP_RANGE[0])
            changed = device.flash
            for _ in range(2):
                evidence["rejection"] = _reject(lambda: run_transaction(
                    transaction, _NoWrites(_session(device))))
                assert device.flash == changed
            assert json.loads((transaction / "journal.json").read_text())["state"] == "prepared"
            # Restore only through a separately prepared, matching baseline plan.
            create_transaction(directory / "cleanup", baseline_a=changed, baseline_b=changed,
                               target=stock, identity=identity, writable_ranges=(APP_RANGE,),
                               scope="synthetic-preflight-case-cleanup")
            run_transaction(directory / "cleanup", _session(device))
        else:
            raise AssertionError(f"unknown case {kind}")
        assert _session(device).read(0, FLASH_SIZE) == stock, "rejected case mutated device"
        device.reset()
        assert device.mode == "app"
    if kind not in ("corrupt_backup_a", "corrupt_backup_b", "corrupt_target", "corrupt_journal",
                    "corrupt_plan", "wrong_unit", "out_of_range", "unexpected_preflight_change",
                    "corrupt_journal_state", "corrupt_journal_direction", "corrupt_journal_intent"):
        device = _open(directory)
        run_transaction(transaction, _session(device), direction="restore")
        _assert_image(device, stock)
    return dict(index=case["index"], name=case["name"], outcome="passed", seed=seed,
                stock_sha256=digest(stock), diagnostic_sha256=digest(target),
                final_flash_sha256=digest(stock), full_image_preserved=True,
                process_reopened=kind in ("baseline", "fault", "verify_corruption", "crash_intent", "crash_after_write"),
                model_only=True, hardware_validated=False, evidence=evidence)


def run_campaign(root: Path, indices: list[int], seed: int = SEED) -> dict:
    catalog = case_catalog()
    baseline = run_case(root, catalog[0], seed)
    receipts = [baseline] if 0 in indices else []
    receipts.extend(run_case(root, catalog[i], seed) for i in indices if i != 0)
    return dict(schema=1, seed=seed, model_only=True, hardware_validated=False,
                fixture_loader_sha256=LOADER_SHA256,
                baseline_receipt_sha256=digest(canonical(baseline)),
                catalog_sha256=digest(canonical(catalog)), catalog_count=len(catalog),
                selected_count=len(receipts), receipts=receipts)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    select = parser.add_mutually_exclusive_group()
    select.add_argument("--case", type=int)
    select.add_argument("--case-range", metavar="START:STOP")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        return _worker(args.worker, json.loads((args.worker / "worker-case.json").read_text()))
    catalog = case_catalog()
    if args.list:
        print(json.dumps(catalog, sort_keys=True))
        return 0
    if args.case is not None:
        indices = [args.case]
    elif args.case_range:
        try:
            start, stop = map(int, args.case_range.split(":"))
        except ValueError:
            parser.error("--case-range requires START:STOP")
        if not 0 <= start < stop <= len(catalog):
            parser.error("selection is empty or outside the case catalog")
        indices = list(range(start, stop))
    else:
        indices = list(range(len(catalog)))
    if not indices or any(i < 0 or i >= len(catalog) for i in indices):
        parser.error("selection is empty or outside the case catalog")
    if args.state_dir:
        result = run_campaign(args.state_dir, indices, args.seed)
    else:
        with tempfile.TemporaryDirectory(prefix="lunar-model-recovery-") as tmp:
            result = run_campaign(Path(tmp), indices, args.seed)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonical(result) + b"\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
