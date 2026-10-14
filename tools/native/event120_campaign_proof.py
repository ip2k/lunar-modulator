#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline verification wrapper for a completed device38 Event120 install.

This reads retained evidence only. It never imports or calls the live writer.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
from contextvars import ContextVar

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
# Replay code is imported before verify() can build its evidence map. Verify its
# exact dependency bytes before Python executes any of them; verify() reads them
# again through _read so the caller can freeze those same bytes before admission.
REPLAY_SOURCE_PINS = {
    "native/event120_install_proof.py": "f90f8601a88d9eae6ae7ee9e455ff2b0965837181003373074c28cb0ddc9b102",
    "fm1_fixed_target_reset.py": "b846b574fe1e5b7597001f6f833044a07143540f2c0b3676e93bac807869833a",
    "fm1_fixed_loader_reset.py": "dbbe363104aa339b63430ff0a99f817aba27afa233a266d449f45e048cd09116",
    "native/expanded_sg.py": "f18e73b658c9d0b06b03b528c6fd4dd4da511a95102ea44252836d885e1a3700",
}
# Verify every imported project module before Python executes it. The writer
# source map below is duplicated here deliberately so a modified imported
# helper cannot run before verify() later records its digest for the caller.
_BOOTSTRAP_PINS = {
    **REPLAY_SOURCE_PINS,
    "fm1_flash_transaction.py": "d0527efbe74314b30a2cd76897c022a1c7857db888ef6e8f8610dbb329956908",
    "native/event120_bench_transactions.py": "a0711605440b5414feda742f55e458a5ea9628da6bfebb98ffa48a58dc63a2c9",
    "native/event120_bench_policy.py": "528a3020674f158cec796cf9b77e4275f35c6651434ca7e760ed1edfcf007355",
    "fm1_fixed_loader_backup.py": "79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb",
    "fm1_uboot_read.py": "28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57",
    "fm1_bound_diagnostic.py": "25e57ffda466c898df88370069cf4d7fce02134e141ba95516347c30953d1a36",
    "native/event120_bench_live.py": "fd1ee3515f3eb534ea2ce9aec35fe15b28199fc7aea367e1868045e7478d4ae2",
}
for _relative, _sha in _BOOTSTRAP_PINS.items():
    _raw = (ROOT / "tools" / _relative).read_bytes()
    if hashlib.sha256(_raw).hexdigest() != _sha:
        raise RuntimeError("Reviewed proof dependency source hash differs")
    del _raw
from fm1_flash_transaction import checked_identity, checked_plan_order, digest, encoded
from native.event120_bench_transactions import (
    BASELINE_SHA, COMMANDS_SHA, MANIFEST_SHA, TARGET_SHA, pinned,
)
from native.event120_install_proof import replay

_EVIDENCE = ContextVar('event120_evidence', default=None)
MAX_JSON = 65536
MAX_TRANSCRIPT = 32 * 1048576
FLASH_BYTES = 1048576
APP_BASE = 0x4000
AREA_END = 0xD9000
PLAN_PINS = {
    "native": ("46425c0e3e12f5a61737c4160af595afb1c6955453bff8ee6a14d0c53279d25a", 208, TARGET_SHA),
    "stock": ("ed934f5476fb02891ebe43bae3f885e8b0900573ec78b927739681744c67455a", 213,
              "96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4"),
}
USB = {"path": "1-1", "busnum": "1", "devnum": "38", "vid": "4c4a", "pid": "8057"}
CANDIDATE_DIR = Path("/home/claude/.local/share/codex-private/shapes8-event120-expanded-candidate-20261014")
CANDIDATE_RECEIPT_SHA256 = "1c53f94ba57001f30901a2f33081f26c223f1789781abaa0f5325e83880684db"
IMAGE_RECEIPT_SHA256 = "b7c34d28a02029b23849d75b2a9a2acbcd3464fcf888be8abbfbfb8d66dbd9a4"
TRANSPORT_MANIFEST_SHA256 = "3c891dac59234a92dc58e66a8bfa7d779a4ccf20c82f057c98a463f16a3bec40"
CANDIDATE_APP_SHA256 = "5709ac03377a310eefdff563f4f08fe8a0e932ed9e0ecacef96464a59ec48573"

# These are the reviewed writer source hashes. Keep the live adapter hash in
# sync with the final writer commit; its exact hash is also embedded in campaign.
WRITER_ADAPTER_SHA256 = "fd1ee3515f3eb534ea2ce9aec35fe15b28199fc7aea367e1868045e7478d4ae2"
V1_ADAPTER_SHA256 = "fc913ba0498c0f45c39120fd4c8bfc1ea95ff1c55c7a918fa73cb4cca5f369d3"
WRITER_SOURCES = {
    "native/event120_bench_transactions.py": "a0711605440b5414feda742f55e458a5ea9628da6bfebb98ffa48a58dc63a2c9",
    "native/event120_bench_policy.py": "528a3020674f158cec796cf9b77e4275f35c6651434ca7e760ed1edfcf007355",
    "fm1_fixed_loader_backup.py": "79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb",
    "fm1_uboot_read.py": "28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57",
    "native/expanded_sg.py": "f18e73b658c9d0b06b03b528c6fd4dd4da511a95102ea44252836d885e1a3700",
    "fm1_bound_diagnostic.py": "25e57ffda466c898df88370069cf4d7fce02134e141ba95516347c30953d1a36",
    "fm1_flash_transaction.py": "d0527efbe74314b30a2cd76897c022a1c7857db888ef6e8f8610dbb329956908",
}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _safe_path(path):
    path = Path(path).absolute()
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise ValueError("Symlink evidence path refused")
    return path


def _read(path, limit):
    path = _safe_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("Regular evidence file required")
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Evidence file exceeds bound")
    evidence = _EVIDENCE.get()
    if evidence is not None:
        evidence[str(path)] = digest(raw)
    return raw


def _json(path, limit=MAX_JSON):
    return json.loads(_read(path, limit), object_pairs_hook=_unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Invalid JSON number")))


def _pin_sources(root, expected):
    if expected != WRITER_SOURCES:
        raise ValueError("Writer source set differs from reviewed pins")
    for relative, sha in expected.items():
        raw = _read(root / "tools" / relative, 2 * 1048576)
        if digest(raw) != sha:
            raise ValueError("Writer dependency source hash differs")
    adapter = _read(root / "tools/native/event120_bench_live.py", 2 * 1048576)
    if digest(adapter) != WRITER_ADAPTER_SHA256:
        raise ValueError("Writer adapter source hash differs")
    _pin_replay_sources(root)


def _pin_replay_sources(root):
    for relative, sha in REPLAY_SOURCE_PINS.items():
        if digest(_read(root / "tools" / relative, 2 * 1048576)) != sha:
            raise ValueError("Reviewed replay dependency source hash differs")


def _validate_candidate_sources():
    candidate_path = CANDIDATE_DIR / "candidate-receipt.json"
    image_path = CANDIDATE_DIR / "image-receipt.json"
    transport_path = CANDIDATE_DIR / "transport-manifest.json"
    candidate_raw = _read(candidate_path, MAX_JSON)
    image_raw = _read(image_path, MAX_JSON)
    transport_raw = _read(transport_path, MAX_JSON)
    if (digest(candidate_raw) != CANDIDATE_RECEIPT_SHA256 or
            digest(image_raw) != IMAGE_RECEIPT_SHA256 or
            digest(transport_raw) != TRANSPORT_MANIFEST_SHA256):
        raise ValueError("Candidate, image or transport receipt hash differs")
    candidate = json.loads(candidate_raw, object_pairs_hook=_unique)
    image = json.loads(image_raw, object_pairs_hook=_unique)
    transport = json.loads(transport_raw, object_pairs_hook=_unique)
    runtime = image.get("runtime_configuration", {})
    save = image.get("project_save_service", {})
    from fm1_flash_transaction import digest as sha256, encoded as canonical_json
    if (candidate.get("app_sha256") != CANDIDATE_APP_SHA256 or candidate.get("app_bytes") != 845036 or
            candidate.get("target_sha256") != TARGET_SHA or candidate.get("hardware_admitted") is not False or
            candidate.get("installable") is not False or candidate.get("physical_writer_ready") is not False or
            image.get("app_sha256") != CANDIDATE_APP_SHA256 or image.get("app_bytes") != 845036 or
            image.get("startup_project_id") != "replacement-showcase-candidate-event-horizon" or
            image.get("startup_index") != 0 or image.get("hardware_admitted") is not False or
            image.get("installable") is not False or image.get("full_song_default_accepted") is not False or
            runtime.get("runtime_mode") != "song-diagnostic" or runtime.get("return_to_rom_seconds") != 120 or
            save.get("save_service_armed") is not False or save.get("storage_admitted") is not False or
            save.get("flash_io_bound") is not False or save.get("runtime_verified") is not False or
            save.get("hardware_tested") is not False or
            transport.get("app_sha256") != CANDIDATE_APP_SHA256 or transport.get("app_bytes") != 845036 or
            transport.get("target_sha256") != TARGET_SHA or transport.get("startup_index") != 0 or
            transport.get("startup_project_id") != "replacement-showcase-candidate-event-horizon" or
            transport.get("hardware_admitted") is not False or transport.get("installable") is not False or
            transport.get("physical_writer_ready") is not False or
            transport.get("candidate_receipt_sha256") != sha256(canonical_json(candidate)) or
            transport.get("image_receipt_sha256") != sha256(canonical_json(image))):
        raise ValueError("Pinned Event Horizon candidate admission or receipt linkage differs")


def verify(directory, campaign_sha256, *, source_root=ROOT, now=None):
    """Verify a completed v2 install bundle; return proof and frozen input hashes."""
    evidence = {}
    token = _EVIDENCE.set(evidence)
    try:
        return _verify_v2(directory, campaign_sha256, source_root=source_root, now=now, evidence=evidence)
    finally:
        _EVIDENCE.reset(token)


def _verify_v2(directory, campaign_sha256, *, source_root, now, evidence):
    directory = _safe_path(directory)
    campaign_path = _safe_path(directory / "event120-install-v2-campaign.json")
    raw_campaign = _read(campaign_path, MAX_JSON)
    campaign = json.loads(raw_campaign, object_pairs_hook=_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Invalid JSON number")))
    fields = {"schema", "kind", "adapter_sha256", "observed_at", "receipt", "plan",
              "direction", "variant", "output", "sg_binding", "prior_v1_stop"}
    if (not isinstance(campaign, dict) or set(campaign) != fields or
            type(campaign["schema"]) is not int or campaign["schema"] != 2 or
            campaign["kind"] != "fm1-device38-event120-transaction-v2" or
            campaign["direction"] != "install" or campaign["variant"] != "native" or
            campaign["adapter_sha256"] != WRITER_ADAPTER_SHA256 or
            type(campaign["observed_at"]) not in (int, float) or
            not math.isfinite(campaign["observed_at"]) or campaign["sg_binding"] is None):
        raise ValueError("Exact native Event120 campaign required")
    if not isinstance(campaign["prior_v1_stop"], dict):
        raise ValueError("Prior stopped V1 evidence object required")
    if campaign["sg_binding"].get("usb_binding") != USB:
        raise ValueError("Campaign must bind exact device38 ROM identity")
    now = time.time() if now is None else now
    if type(now) not in (int, float) or not math.isfinite(now):
        raise ValueError("Finite verification clock required")

    if digest(raw_campaign) != campaign_sha256:
        raise ValueError("Campaign digest differs")
    source_root = _safe_path(source_root)
    _pin_sources(source_root, WRITER_SOURCES)
    _validate_candidate_sources()
    receipt = _safe_path(campaign["receipt"])
    plan_dir = _safe_path(campaign["plan"])
    output = _safe_path(campaign["output"])
    if (not all(Path(x).is_absolute() for x in (campaign["receipt"], campaign["plan"], campaign["output"])) or
            campaign_path.parent != output.parent or output.is_symlink() or
            campaign["sg_binding"] != _json(receipt / "manifest.json").get("sg_binding")):
        raise ValueError("Campaign paths or backup transport binding differ")

    manifest_raw = _read(receipt / "manifest.json", MAX_JSON)
    commands_raw = _read(receipt / "commands.jsonl", 8 * 1048576)
    if digest(manifest_raw) != MANIFEST_SHA or digest(commands_raw) != COMMANDS_SHA:
        raise ValueError("Pinned fresh backup receipt differs")
    manifest = json.loads(manifest_raw, object_pairs_hook=_unique)
    if (manifest.get("kind") != "fm1-device38-expanded-rom-fixed-loader-dual-read" or
            manifest.get("usb_binding") != USB or manifest.get("flash_operations") != 0 or
            manifest.get("reset_operations") != 0):
        raise ValueError("Fresh dual-read device38 backup required")
    baseline_a = _read(receipt / "dumpA.bin", FLASH_BYTES)
    baseline_b = _read(receipt / "dumpB.bin", FLASH_BYTES)
    if baseline_a != baseline_b or digest(baseline_a) != BASELINE_SHA:
        raise ValueError("Two matching complete current backups required")

    plan_raw = _read(plan_dir / "plan.json", MAX_JSON)
    journal_raw = _read(plan_dir / "journal.json", MAX_JSON)
    baseline_plan = _read(plan_dir / "backupA.bin", FLASH_BYTES)
    baseline_plan_b = _read(plan_dir / "backupB.bin", FLASH_BYTES)
    target = _read(plan_dir / "target.bin", FLASH_BYTES)
    plan = json.loads(plan_raw, object_pairs_hook=_unique)
    journal = json.loads(journal_raw, object_pairs_hook=_unique)
    plan_sha, sector_count, target_sha = PLAN_PINS["native"]
    order = checked_plan_order(plan)
    checked_identity(plan.get("identity"))
    jbody = {key: value for key, value in journal.items() if key != "record_sha256"}
    if (digest(encoded(plan)) != plan_sha or len(order) != sector_count or order[-1] != APP_BASE or
            baseline_plan != baseline_a or baseline_plan_b != baseline_a or
            digest(target) != target_sha or digest(target) != TARGET_SHA or
            plan.get("target_sha256") != target_sha or plan.get("commit_sector") != APP_BASE or
            journal.get("plan_sha256") != plan_sha or journal.get("record_sha256") != digest(encoded(jbody)) or
            journal.get("state") != "complete" or journal.get("direction") != "install" or
            journal.get("intent") is not None or journal.get("verified_sha256") != target_sha or
            journal.get("sector_order") != order):
        raise ValueError("Completed 208-sector directory-last transaction required")

    marker = _safe_path(campaign_path.parent / ".event120-v2-native-install.consumed")
    marker_bytes = _read(marker, 128)
    campaign_sha = digest(raw_campaign)
    if marker_bytes != campaign_sha.encode("ascii"):
        raise ValueError("Exact one-use consumed campaign marker required")

    transcript_raw = _read(output / "commands.jsonl", MAX_TRANSCRIPT)
    result = _json(output / "result.json")
    prior_v1_proof = _verify_v1_stop(campaign["prior_v1_stop"])
    expected_result = {
        "campaign_sha256": campaign_sha, "direction": "install", "variant": "native",
        "verified_sha256": target_sha, "sectors_written": sector_count,
        "full_flash_readback_verified": True, "boot_observed": False,
        "physical_recovery_verified": False, "kernel_exclusivity": False,
        "hardware_admitted": False, "installable": False,
        "prior_v1_stop_proof": prior_v1_proof,
    }
    if result != expected_result:
        raise ValueError("Exact disarmed full-readback result required")
    first = json.loads(transcript_raw.splitlines()[0], object_pairs_hook=_unique)
    if (first.get("event") != "native_transaction_prepared" or
            first.get("campaign_sha256") != campaign_sha or
            first.get("source_sha256") != WRITER_SOURCES or
            first.get("adapter_sha256") != WRITER_ADAPTER_SHA256 or
            first.get("backup_manifest_sha256") != MANIFEST_SHA or
            first.get("sg_binding") != campaign["sg_binding"] or
            first.get("prior_v1_stop_proof") != prior_v1_proof or
            first.get("direction") != "install" or first.get("variant") != "native" or
            first.get("retry") is not False):
        raise ValueError("Transcript must bind exact campaign, writer, backup and SG identity")

    proof = replay(transcript_raw, result, campaign_sha256=campaign_sha,
        sources=WRITER_SOURCES, adapter_sha256=WRITER_ADAPTER_SHA256,
        backup_manifest_sha256=MANIFEST_SHA, sg_binding=campaign["sg_binding"],
        baseline=baseline_a, target=target, sector_order=order,
        observed_at=campaign["observed_at"], prior_v1_stop_proof=prior_v1_proof)
    proof = {
        "schema": 2, "kind": "device38-event120-offline-install-proof-v2",
        "verified": True, "hardware_operations": 0,
        "hardware_admitted": False, "installable": False,
        "campaign_sha256": campaign_sha,
        "writer_adapter_sha256": WRITER_ADAPTER_SHA256,
        "source_sha256": WRITER_SOURCES,
        "backup_manifest_sha256": MANIFEST_SHA,
        "plan_sha256": plan_sha, "sectors": sector_count,
        "target_sha256": target_sha,
        "transcript_sha256": proof["transcript_sha256"],
        "commands": proof["commands"], "events": proof["events"],
        "boot_observed": False, "physical_recovery_verified": False,
        "prior_v1_stop_proof": prior_v1_proof,
    }
    return {"proof": proof, "evidence_sha256": dict(sorted(evidence.items()))}


def _validate_v1_stop_events(events, campaign_sha256):
    prepared, stopped = events
    if (prepared.get("event") != "native_transaction_prepared" or
            prepared.get("campaign_sha256") != campaign_sha256 or
            prepared.get("direction") != "install" or prepared.get("variant") != "native" or
            prepared.get("retry") is not False or
            stopped.get("event") != "native_transaction_stopped" or
            stopped.get("retry") is not False or stopped.get("error") != "ValueError" or
            set(stopped) != {"time", "event", "error", "detail", "retry"} or
            type(prepared.get("time")) not in (int, float) or
            type(stopped.get("time")) not in (int, float) or
            not math.isfinite(prepared["time"]) or not math.isfinite(stopped["time"]) or
            stopped["time"] < prepared["time"]):
        raise ValueError("V1 stopped attempt identity or terminal event differs")


def _verify_v1_stop(prior):
    expected = {
        "evidence_root": "/home/claude/.local/share/codex-private/device38-event120-stopped-v1-20261014/extracted",
        "campaign_sha256": "e1ccb934a2814f85fc2ad1b5f802f5c982d8e926d1193d0b449f72c89a74bf4f",
        "commands_sha256": "1af816ae7ce0f8e5b2d607cd279c9470468888ae4a343eb7fb00696bb3963ffb",
        "consumed_marker_sha256": "a32770f18f68559923fae7c538e1e3835af9cf33e38d1382f26c331a9d5c395b",
        "adapter_sha256": V1_ADAPTER_SHA256,
        "fixed_loader_source_sha256": WRITER_SOURCES["fm1_fixed_loader_backup.py"],
    }
    if not isinstance(prior, dict) or prior != expected:
        raise ValueError("V1 stopped-before-SG evidence pins differ")
    root = _safe_path(prior["evidence_root"])
    campaign = _read(root / "event120-install-campaign.json", MAX_JSON)
    marker = _read(root / ".event120-native-install.consumed", 128)
    commands = _read(root / "event120-install-v1" / "commands.jsonl", 8 * 1048576)
    if digest(campaign) != prior["campaign_sha256"] or marker != prior["campaign_sha256"].encode("ascii") or digest(marker) != prior["consumed_marker_sha256"] or digest(commands) != prior["commands_sha256"]:
        raise ValueError("Pinned v1 stopped-before-SG artifacts differ")
    events = [json.loads(line, object_pairs_hook=_unique) for line in commands.splitlines()]
    if len(events) != 2 or [e.get("event") for e in events] != ["native_transaction_prepared", "native_transaction_stopped"]:
        raise ValueError("V1 evidence must contain exactly a stopped pre-SG attempt")
    _validate_v1_stop_events(events, prior["campaign_sha256"])
    return {
        "schema": 1, "kind": "event120-v1-stopped-before-sg",
        "campaign_sha256": prior["campaign_sha256"],
        "commands_sha256": prior["commands_sha256"],
        "consumed_marker_sha256": prior["consumed_marker_sha256"],
        "events": ["native_transaction_prepared", "native_transaction_stopped"],
        "sg_commands": 0, "reset_commands": 0, "write_intents": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--campaign-sha256", required=True)
    parser.add_argument("--source-root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(verify(args.directory, args.campaign_sha256, source_root=args.source_root), sort_keys=True))


if __name__ == "__main__":
    main()
