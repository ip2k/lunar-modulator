#!/usr/bin/env python3
"""One-use paired read-only backup after owner-attested Cynthion USB_KEY entry.

This is a distinct cold-ROM admission path. It leaves the soft-key adapter and
the audited loader/read request builder unchanged. ROM entry is correlated by
fresh USB topology plus an explicit owner statement; ROM has no serial here.
It never erases, programs flash, resets, boots, or retries a failed attempt.
"""
from __future__ import annotations

import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import types

if __package__:
    from . import fm1_fixed_loader_backup as fixed
else:  # Direct `python tools/fm1_cold_rom_backup.py` invocation.
    import fm1_fixed_loader_backup as fixed

SCHEMA = 1
KIND = "fm1-cold-rom-backup-campaign"
ENTRY_KIND = "fm1-cold-rom-entry"
SOURCE = "cynthion-usb-key"
FIXED_ADAPTER_SHA256 = "79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb"
MAX_ENTRY_AGE_SECONDS = 120
MAX_SESSION_SECONDS = 600
FLASH_IMAGE_CLASSIFICATION = "unclassified"


def _same_keys(value: object, keys: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"Unexpected {label} fields")
    return value


def _timestamp(value: object, label: str) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"Invalid {label} timestamp")
    return float(value)


def validate_entry(data: bytes, usb_binding: dict, dongle_sha256: str,
                   *, now: float | None = None) -> float:
    """Validate cold-source evidence without synthesizing soft-key identity."""
    now = time.time() if now is None else now
    try:
        entry = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Malformed cold-ROM entry evidence") from exc
    _same_keys(entry, {"schema", "kind", "source", "owner_attestation",
                       "dongle_upload", "attempt_started_at",
                       "status_observed_at", "target_port", "rom_enumeration",
                       "rom_usb"}, "cold-ROM entry")
    if (type(entry["schema"]) is not int or entry["schema"] != SCHEMA or
            entry["kind"] != ENTRY_KIND or
            entry["source"] != SOURCE):
        raise ValueError("Cold entry source or dongle image differs")

    upload = _same_keys(entry["dongle_upload"],
        {"firmware_sha256", "build_receipt_sha256",
         "owner_confirmed_exact_image_uploaded"}, "dongle upload")
    if (upload["firmware_sha256"] != dongle_sha256 or
            not isinstance(upload["build_receipt_sha256"], str) or
            len(upload["build_receipt_sha256"]) != 64 or
            any(ch not in "0123456789abcdef" for ch in upload["build_receipt_sha256"])):
        raise ValueError("Uploaded Cynthion image/build receipt binding differs")
    attestation = _same_keys(entry["owner_attestation"],
        {"performed_usb_key_once", "selected_physical_unit",
         "rom_device_is_selected_unit", "identity_basis", "usb_serial",
         "status_observation"}, "owner attestation")
    for field in ("performed_usb_key_once", "selected_physical_unit",
                  "rom_device_is_selected_unit", "owner_confirmed_exact_image_uploaded"):
        value = upload[field] if field == "owner_confirmed_exact_image_uploaded" else attestation[field]
        if type(value) is not bool or not value:
            raise ValueError(f"Owner must affirm {field}")
    if (attestation["identity_basis"] != "owner-attested-physical-selection" or
            attestation["usb_serial"] is not None):
        raise ValueError("ROM identity must remain explicitly owner-attested and serial-less")
    observation = _same_keys(attestation["status_observation"],
        {"method", "value"}, "gateware status observation")
    if (observation["method"] not in ("status-leds", "other-owner-observed") or
            not isinstance(observation["value"], str) or
            not observation["value"].strip() or len(observation["value"]) > 240):
        raise ValueError("Record the owner-observed gateware status without inferring recovery")

    started = _timestamp(entry["attempt_started_at"], "attempt")
    status = _timestamp(entry["status_observed_at"], "gateware status")
    enumeration = _same_keys(entry["rom_enumeration"],
        {"observed_at", "candidates"}, "ROM enumeration")
    observed = _timestamp(enumeration["observed_at"], "ROM enumeration")
    if (not started <= status <= observed or not 0 <= now - observed <= MAX_ENTRY_AGE_SECONDS or
            observed - started > MAX_ENTRY_AGE_SECONDS):
        raise ValueError("Cold-ROM entry is stale or has invalid event ordering")

    port = _same_keys(entry["target_port"], {"path", "was_absent_before_attempt"}, "target port")
    if (not isinstance(port["path"], str) or not port["path"] or
            type(port["was_absent_before_attempt"]) is not bool or
            not port["was_absent_before_attempt"]):
        raise ValueError("A fresh absent-to-ROM target-port transition is required")

    observed_usb = entry["rom_usb"]
    fixed.validate_usb(observed_usb)
    candidates = enumeration["candidates"]
    if (not isinstance(candidates, list) or len(candidates) != 1 or
            candidates[0] != observed_usb or observed_usb != usb_binding or
            observed_usb["path"] != port["path"]):
        raise ValueError("Observed ROM and current USB binding differ")
    return observed


def prepare_campaign(path: str | Path, *, now: float | None = None):
    """Verify every source/evidence pin and build the unchanged fixed inventory."""
    now = time.time() if now is None else now
    path = Path(path).absolute()
    raw = fixed.bounded_file(path)
    try:
        config = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Malformed cold-ROM campaign") from exc
    required = {"schema", "kind", "adapter_sha256", "fixed_adapter_sha256",
        "reader_sha256", "loader_path", "profile_path", "profile_source_path",
        "entry_path", "entry_sha256", "dongle_firmware_path",
        "dongle_build_receipt_path", "dongle_build_receipt_sha256",
        "dongle_firmware_sha256", "usb_binding", "receipt_path"}
    _same_keys(config, required, "cold-ROM campaign")
    if type(config["schema"]) is not int or config["schema"] != SCHEMA or config["kind"] != KIND:
        raise ValueError("Unsupported cold-ROM campaign schema")

    fixed.pinned_file(Path(__file__).absolute(), config["adapter_sha256"])
    fixed.pinned_file(Path(fixed.__file__).absolute(), FIXED_ADAPTER_SHA256)
    if config["fixed_adapter_sha256"] != FIXED_ADAPTER_SHA256:
        raise ValueError("Fixed backup adapter pin differs")
    reader_path = Path(fixed.__file__).absolute().with_name("fm1_uboot_read.py")
    reader_source = fixed.pinned_file(reader_path, fixed.READER_SHA)
    if config["reader_sha256"] != fixed.READER_SHA:
        raise ValueError("Fixed reader pin differs")

    loader = fixed.pinned_file(config["loader_path"], fixed.LOADER_SHA)
    if len(loader) != fixed.LOADER_SIZE:
        raise ValueError("Exact reviewed RAM loader length required")
    profile_bytes = fixed.pinned_file(config["profile_path"], fixed.PROFILE_SHA)
    fixed.pinned_file(config["profile_source_path"], fixed.PROFILE_SOURCE_SHA)
    profile = json.loads(profile_bytes)
    dongle_sha = config["dongle_firmware_sha256"]
    if (not isinstance(dongle_sha, str) or len(dongle_sha) != 64 or
            any(ch not in "0123456789abcdef" for ch in dongle_sha)):
        raise ValueError("Invalid Cynthion firmware hash")
    fixed.pinned_file(config["dongle_firmware_path"], dongle_sha)
    build_sha = config["dongle_build_receipt_sha256"]
    if (not isinstance(build_sha, str) or len(build_sha) != 64 or
            any(ch not in "0123456789abcdef" for ch in build_sha)):
        raise ValueError("Invalid Cynthion build receipt hash")
    fixed.pinned_file(config["dongle_build_receipt_path"], build_sha)
    entry_bytes = fixed.pinned_file(config["entry_path"], config["entry_sha256"])
    fixed.validate_usb(config["usb_binding"])
    entered_at = validate_entry(entry_bytes, config["usb_binding"], dongle_sha, now=now)
    parsed_entry = json.loads(entry_bytes)
    if parsed_entry["dongle_upload"]["build_receipt_sha256"] != build_sha:
        raise ValueError("Owner entry build receipt differs from staged receipt")

    # The entry evidence and campaign live in one private directory. Its durable
    # one-use marker therefore cannot be bypassed by selecting another output.
    root = path.parent
    receipt = Path(config["receipt_path"])
    if not receipt.is_absolute() or receipt.parent != root or receipt.exists():
        raise ValueError("Receipt must be a new direct child of the evidence directory")
    for source_path in (path, Path(config["entry_path"])):
        if source_path.parent != root:
            raise ValueError("Campaign and entry evidence must share the private root")
    root_stat = root.lstat()
    if (not stat.S_ISDIR(root_stat.st_mode) or stat.S_ISLNK(root_stat.st_mode) or
            root_stat.st_mode & 0o777 != 0o700):
        raise ValueError("Evidence directory must be a direct private mode-0700 directory")

    reader = types.ModuleType("_fm1_cold_pinned_reader")
    exec(compile(reader_source, str(reader_path), "exec"), reader.__dict__)
    if C.sizeof(reader.SGHeader) != 88:
        raise ValueError("Only the reviewed 64-bit Linux SG_IO header is supported")

    operations = []

    def add(op, phase, label, address=0, payload=b""):
        cdb, data, size = reader.request(op, phase, address=address, payload=payload)
        operations.append(fixed.Operation(phase, cdb, data, size, label))

    add(0x12, "rom", "inquiry")
    for index, offset in enumerate(range(0, fixed.LOADER_SIZE, 512)):
        payload = loader[offset:offset + 512]
        add(0xFB06, "rom", "upload", fixed.RAM + offset, payload)
        op = operations[-1]
        expected = {"index": index, "address": fixed.RAM + offset,
            "bytes": 512, "cdb_sha256": fixed.digest(op.cdb),
            "payload_sha256": fixed.digest(payload), "read_size": 0}
        if profile["upload_inventory"][index] != expected:
            raise ValueError("Pinned loader upload inventory differs")
    if (len(profile["upload_inventory"]) != 47 or
            profile["patched_encrypted_sha256"] != fixed.LOADER_SHA or
            profile["original_encrypted_sha256"] != fixed.ORIGINAL_SHA):
        raise ValueError("Pinned loader profile identity differs")
    add(0xFB08, "rom", "jump", fixed.RAM)
    add(0xFC14, "loader", "buffer")
    add(0xFC0A, "loader", "online")
    for name in ("dumpA.bin", "dumpB.bin"):
        for address in range(0, fixed.FLASH_SIZE, fixed.PAGE):
            if address % 4096 == 0:
                add(0xFC0A, "loader", "online")
            add(0xFD05, "loader", name, address)
        add(0xFC0A, "loader", name + ".end")

    inventory_sha = fixed.inventory_digest(operations)
    if len(operations) != 8757:
        raise ValueError("Fixed reviewed operation count differs")
    # Construct the existing fixed type so its descriptor/topology checks and
    # exact per-operation exchange path remain byte-for-byte in use.
    prepared = fixed.PreparedCampaign(config, fixed.digest(raw), loader,
        tuple(operations), reader.SGHeader, entered_at, inventory_sha)
    prepared.owner_status_observation = parsed_entry["owner_attestation"]["status_observation"]
    return prepared, receipt, fixed.digest(entry_bytes), dongle_sha


def _sync_file(fp):
    fp.flush()
    os.fsync(fp.fileno())


def run_campaign(prepared, receipt: Path, entry_sha256: str,
                 dongle_sha256: str, *, monotonic=time.monotonic):
    """Consume one admission and durably acquire equal full-flash reads."""
    started = monotonic()
    receipt.parent.mkdir(mode=0o700, exist_ok=True)
    fixed.sync_dir(receipt.parent)
    receipt.mkdir(mode=0o700, exist_ok=False)
    fixed.sync_dir(receipt.parent)
    marker = receipt.parent / f".cold-rom-{entry_sha256}.consumed"
    # Claim before FixedSG opens anything. Even failed/ambiguous attempts burn
    # this evidence so a new receipt path cannot silently retry the same entry.
    with fixed.private_file(marker) as claim:
        claim.write(prepared.manifest_sha256.encode("ascii"))
        _sync_file(claim)
    fixed.sync_dir(receipt.parent)

    event_file = receipt / "commands.jsonl"
    transport = None
    try:
        with fixed.private_file(event_file, "w") as events:
            def log(event, **fields):
                events.write(json.dumps({"time": time.time(), "event": event,
                                         **fields}, sort_keys=True) + "\n")
                # An intent is durable before each SG call. A durable completion
                # follows it; a missing completion is an ambiguous stop.
                _sync_file(events)
                if event == "sg_submit_intent":
                    fixed.sync_dir(receipt)

            log("cold_campaign_prepared", campaign_sha256=prepared.manifest_sha256,
                entry_sha256=entry_sha256, dongle_firmware_sha256=dongle_sha256,
                dongle_build_receipt_sha256=prepared.config["dongle_build_receipt_sha256"],
                fixed_adapter_sha256=FIXED_ADAPTER_SHA256,
                reader_sha256=fixed.READER_SHA, source=SOURCE,
                usb_binding=prepared.config["usb_binding"],
                request_inventory_sha256=prepared.request_inventory_sha256,
                operations=len(prepared.operations), retry=False,
                physical_recovery_verified=False, kernel_exclusivity=False)
            # Recheck the short entry admission immediately before open. The
            # transport's existing 600-second freshness guard remains an
            # additional check, while this path imposes 120 seconds.
            if not 0 <= time.time() - prepared.entered_at <= MAX_ENTRY_AGE_SECONDS:
                raise ValueError("Cold-ROM entry expired before SG open")
            transport = fixed.FixedSG(prepared, log)
            dump_entries = []
            for name in ("dumpA.bin", "dumpB.bin"):
                image_hash = hashlib.sha256()
                count = 0
                with fixed.private_file(receipt / name) as dump:
                    while transport.next < len(prepared.operations):
                        if monotonic() - started >= MAX_SESSION_SECONDS:
                            raise TimeoutError("Cold backup session limit reached")
                        pending = prepared.operations[transport.next]
                        if pending.label not in ("inquiry", "upload", "jump", "buffer",
                                                 "online", name, name + ".end"):
                            break
                        op, data = transport.exchange_next()
                        if op.label == name:
                            dump.write(data)
                            image_hash.update(data)
                            count += len(data)
                        if op.label == name + ".end":
                            break
                    _sync_file(dump)
                fixed.sync_dir(receipt)
                if count != fixed.FLASH_SIZE:
                    raise ValueError("Full 1 MiB read did not complete")
                dump_entries.append({"file": name, "bytes": count,
                    "sha256": image_hash.hexdigest(), "complete": True})

            transport.binding()
            if (transport.next != len(prepared.operations) or
                    dump_entries[0]["sha256"] != dump_entries[1]["sha256"]):
                raise ValueError("Operation inventory incomplete or paired reads differ")
            for item in dump_entries:
                fixed.pinned_file(receipt / item["file"], item["sha256"])
                if (receipt / item["file"]).stat().st_size != fixed.FLASH_SIZE:
                    raise ValueError("Durable dump length differs")

            manifest = {"schema": SCHEMA, "kind": "fm1-cold-rom-backup",
                "source": SOURCE, "entry_sha256": entry_sha256,
                "dongle_firmware_sha256": dongle_sha256,
                "dongle_build_receipt_sha256": prepared.config["dongle_build_receipt_sha256"],
                "adapter_sha256": fixed.digest(Path(__file__).read_bytes()),
                "fixed_adapter_sha256": FIXED_ADAPTER_SHA256,
                "reader_sha256": fixed.READER_SHA,
                "loader_sha256": fixed.LOADER_SHA,
                "loader_profile_sha256": fixed.PROFILE_SHA,
                "profile_source_sha256": fixed.PROFILE_SOURCE_SHA,
                "campaign_sha256": prepared.manifest_sha256,
                "request_inventory_sha256": prepared.request_inventory_sha256,
                "owner_unit_attested": True,
                "owner_status_observation": prepared.owner_status_observation,
                "unit_identity": None,
                "identity_basis": "owner-attested-physical-selection; ROM serial unavailable",
                "usb_serial": None,
                "usb_binding": prepared.config["usb_binding"],
                "sg_binding": transport.mapping,
                "flash_bytes": fixed.FLASH_SIZE,
                "dumps": dump_entries, "identical": True,
                "flash_image_classification": FLASH_IMAGE_CLASSIFICATION,
                "current_flash_sha256": dump_entries[0]["sha256"],
                "write_admission": False, "flash_readback_only": True,
                "physical_recovery_verified": False,
                "kernel_exclusivity": False,
                "commands": transport.next,
                "session_elapsed_seconds": monotonic() - started}
            log("cold_campaign_completed", identical=True,
                bytes_per_dump=fixed.FLASH_SIZE, retry=False,
                write_admission=False)
            with fixed.private_file(receipt / "manifest.json", "w") as fp:
                json.dump(manifest, fp, indent=2, sort_keys=True)
                fp.write("\n")
                _sync_file(fp)
            fixed.sync_dir(receipt)
            return manifest
    except BaseException as exc:
        if transport is not None:
            transport.failed = True
            transport.close()
        # An incomplete result never has the success filename. Keep the consumed
        # marker and all partial evidence for diagnosis; never retry in-process.
        try:
            (receipt / "manifest.json").unlink(missing_ok=True)
            fixed.sync_dir(receipt)
        except OSError:
            pass
        try:
            with fixed.private_file(receipt / "stopped.jsonl", "w") as stopped:
                stopped.write(json.dumps({"event": "cold_campaign_stopped_ambiguous",
                    "error": type(exc).__name__, "retry": False}) + "\n")
                _sync_file(stopped)
            fixed.sync_dir(receipt)
        except OSError:
            pass
        raise
    finally:
        if transport is not None:
            transport.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", type=Path)
    args = parser.parse_args(argv)
    if sys.platform != "linux":
        raise SystemExit("Cold-ROM SG_IO backup is Linux-only")
    os.umask(0o077)
    prepared, receipt, entry_sha256, dongle_sha256 = prepare_campaign(args.campaign)
    result = run_campaign(prepared, receipt, entry_sha256, dongle_sha256)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).absolute().parent))
    main()
