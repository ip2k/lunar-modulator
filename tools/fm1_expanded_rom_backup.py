#!/usr/bin/env python3
"""MIT. One-use, exact device38 ROM observation followed by fixed-loader dual read.

This offline-reviewed adapter admits only the known expanded-install digest and
its pinned installation evidence. It contains no write, reset, retry, or
caller-selected target/loader path. Passing this gate does not prove recovery.
"""
import argparse
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time

from tools.fm1_repeat_rom_backup import load_source, read_file

SOURCES = {
    "fm1_fixed_loader_backup.py": "79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb",
    "fm1_returned_rom_backup.py": "afeefe7bd7e9044cb34106081766d6104cda7ab0196d0de903c35a5c1a52b4be",
    "fm1_uboot_read.py": "28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57",
}
TARGET_SHA = "c543e538754d0ae02ee119fd1e29a9b8cb9eb21a23edf0c12fc981ddaa3bc903"
KIND = "fm1-device38-expanded-rom-fixed-loader-dual-read"
INSTALL_PROOF_SHA = "1798734ef5d8a0754cd17e039e7747a306e34177ebaabcdc591ad06f3a25e41c"
INSTALL_PROOF_RELATIVE = Path("notes/2026-10-13-current-expanded-candidate/device36-physical-install.json")
COMMANDS = 8757
INVENTORY_SHA256 = "f99b6e738d19d24442ad4d056985e6f4dc200d0b09059b80428f4ff989838017"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def validate_install_proof(path):
    raw = read_file(Path(path).absolute(), 65536)
    if digest(raw) != INSTALL_PROOF_SHA:
        raise ValueError("Exact prior expanded-install proof required")
    proof = json.loads(raw)
    if (proof.get("verified") is not True or
            proof.get("target_sha256") != TARGET_SHA or
            proof.get("full_flash_readback_verified") is not True or
            proof.get("physical_recovery_verified") is not False or
            proof.get("release_accepted") is not False):
        raise ValueError("Prior installation proof does not bind exact target")
    return digest(raw)


def validate_observation(c, now):
    required = {"schema", "kind", "adapter_sha256", "observed_at", "usb_binding",
                "loader_path", "profile_path", "profile_source_path", "receipt_path"}
    if (set(c) != required or type(c["schema"]) is not int or c["schema"] != 1 or
            c["kind"] != KIND):
        raise ValueError("Exact device38 fresh-ROM envelope required")
    observed = c["observed_at"]
    if (type(observed) not in (float, int) or not math.isfinite(observed) or
            not 0 <= now - observed <= 120):
        raise ValueError("Fresh passive ROM observation required")
    usb = c["usb_binding"]
    if (not isinstance(usb, dict) or set(usb) != {"path", "busnum", "devnum", "vid", "pid"} or
            any(not isinstance(v, str) for v in usb.values()) or
            usb != {"path": "1-1", "busnum": "1", "devnum": usb.get("devnum"),
                    "vid": "4c4a", "pid": "8057"} or
            not usb["devnum"].isdigit() or usb["devnum"].startswith("0")):
        raise ValueError("Fresh ROM observation must match device38 port 1-1")


def prepare(path):
    raw = read_file(Path(path).absolute(), 65536)
    c = json.loads(raw)
    validate_observation(c, time.time())
    root = Path(__file__).absolute().parent
    if digest(read_file(Path(__file__).absolute())) != c["adapter_sha256"]:
        raise ValueError("Adapter source changed")
    proof_path = root.parent / INSTALL_PROOF_RELATIVE
    proof_sha = validate_install_proof(proof_path)
    modules = {name: load_source(root / name, pin, "_device38_" + name[:-3])
               for name, pin in SOURCES.items()}
    bridge = modules["fm1_fixed_loader_backup.py"]
    reader = modules["fm1_uboot_read.py"]
    bridge.validate_usb(c["usb_binding"])
    mapping = bridge.discover_sg(c["usb_binding"])
    loader = bridge.pinned_file(c["loader_path"], bridge.LOADER_SHA)
    profile = json.loads(bridge.pinned_file(c["profile_path"], bridge.PROFILE_SHA))
    bridge.pinned_file(c["profile_source_path"], bridge.PROFILE_SOURCE_SHA)
    if len(loader) != bridge.LOADER_SIZE or ctypes.sizeof(reader.SGHeader) != 88:
        raise ValueError("Exact reviewed RAM loader and Linux SG ABI required")
    operations = modules["fm1_returned_rom_backup.py"].inventory(
        bridge, reader, loader, profile)
    if (len(operations) != COMMANDS or bridge.inventory_digest(operations) != INVENTORY_SHA256):
        raise ValueError("Exact pinned dual-read command inventory required")
    receipt = Path(c["receipt_path"])
    parent = receipt.parent
    if (not receipt.is_absolute() or os.path.lexists(receipt) or
            not stat.S_ISDIR(parent.lstat().st_mode) or stat.S_IMODE(parent.stat().st_mode) != 0o700):
        raise ValueError("New receipt in direct private directory required")
    usb = c["usb_binding"]
    marker = parent / (".device38-rom-" + usb["path"] + "-" + usb["devnum"] + ".consumed")
    if os.path.lexists(marker):
        raise ValueError("This ROM enumeration was already consumed")
    prepared = bridge.PreparedCampaign(c, digest(raw), loader, operations, reader.SGHeader,
                                       c["observed_at"], bridge.inventory_digest(operations))
    return bridge, prepared, mapping, marker, proof_sha


def run(path):
    started = time.monotonic()
    bridge, prepared, mapping, marker, proof_sha = prepare(path)
    receipt = Path(prepared.config["receipt_path"])
    receipt.mkdir(mode=0o700, exist_ok=False)
    bridge.sync_dir(receipt.parent)
    with bridge.private_file(marker) as fp:
        fp.write(prepared.manifest_sha256.encode("ascii")); fp.flush(); os.fsync(fp.fileno())
    bridge.sync_dir(marker.parent)
    transport = None
    with bridge.private_file(receipt / "commands.jsonl", "w") as events:
        def log(event, **fields):
            events.write(json.dumps(dict(time=time.time(), event=event, **fields), allow_nan=False) + "\n")
            events.flush()
            if event != "sg_completion" and (event != "sg_submit_intent" or fields.get("phase") == "rom"):
                os.fsync(events.fileno())
        try:
            log("device38_expanded_rom_backup_prepared",
                campaign_sha256=prepared.manifest_sha256,
                inventory_sha256=prepared.request_inventory_sha256,
                installation_proof_sha256=proof_sha, commands=COMMANDS,
                loader_sha256=bridge.LOADER_SHA, flash_operations=0,
                reset_operations=0, retry=False)
            transport = bridge.FixedSG(prepared, log)
            if transport.mapping != mapping:
                raise ValueError("SG mapping changed after preflight")
            dumps = []
            for name in ("dumpA.bin", "dumpB.bin"):
                with bridge.private_file(receipt / name) as fp:
                    while transport.next < len(prepared.operations):
                        pending = prepared.operations[transport.next]
                        if pending.label not in ("inquiry", "upload", "jump", "buffer", "online", name, name + ".end"):
                            break
                        if time.monotonic() - started > 120:
                            raise ValueError("Read campaign time bound exceeded")
                        operation, data = transport.exchange_next()
                        if operation.label == name:
                            fp.write(data)
                        if operation.label == name + ".end":
                            break
                    fp.flush(); os.fsync(fp.fileno())
                data = read_file(receipt / name)
                if len(data) != 1048576 or digest(data) != TARGET_SHA:
                    raise ValueError("Complete exact expanded-target read required")
                dumps.append({"file": name, "bytes": len(data), "sha256": digest(data)})
            transport.binding()
            if transport.next != COMMANDS:
                raise ValueError("Incomplete fixed read command sequence")
            transport.close()
            log("device38_expanded_rom_backup_completed", flash_operations=0,
                reset_operations=0, retry=False)
            result = {"schema": 1, "kind": KIND,
                "campaign_sha256": prepared.manifest_sha256,
                "adapter_sha256": prepared.config["adapter_sha256"],
                "source_sha256": SOURCES, "installation_proof_sha256": proof_sha,
                "usb_binding": prepared.config["usb_binding"], "sg_binding": mapping,
                "loader_sha256": bridge.LOADER_SHA,
                "request_inventory_sha256": prepared.request_inventory_sha256,
                "commands": COMMANDS, "current_flash_sha256": TARGET_SHA,
                "dumps": dumps, "identical": True, "flash_operations": 0,
                "reset_operations": 0, "physical_recovery_verified": False}
            with bridge.private_file(receipt / "manifest.json", "w") as fp:
                json.dump(result, fp, sort_keys=True); fp.write("\n"); fp.flush(); os.fsync(fp.fileno())
            bridge.sync_dir(receipt)
            return result
        except BaseException as exc:
            log("device38_expanded_rom_backup_stopped", error=type(exc).__name__, retry=False)
            raise
        finally:
            if transport is not None:
                transport.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    if args.preflight:
        _, prepared, _, _, proof_sha = prepare(args.campaign)
        print(json.dumps({"commands": len(prepared.operations),
                          "installation_proof_sha256": proof_sha,
                          "flash_operations": 0, "reset_operations": 0}))
    else:
        print(json.dumps(run(args.campaign)))
