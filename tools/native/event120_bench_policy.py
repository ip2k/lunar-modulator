#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Pinned offline policy for device38 Event Horizon candidate/stock transactions."""
from dataclasses import dataclass
import json
from pathlib import Path
from weakref import WeakSet
from fm1_bound_diagnostic import BoundDiagnosticSession, _VALIDATED
from fm1_flash_transaction import load_transaction, encoded, digest, checked_plan_order
from native.event120_bench_transactions import (
    BASELINE_SHA, MANIFEST_SHA, COMMANDS_SHA, TARGET_SHA, STOCK_SHA,
    CANDIDATE_APP_SHA, CANDIDATE_RECEIPT_SHA, INSTALLATION_PROOF_SHA, changed_ranges, pinned)

IMAGE_RECEIPT_SHA = "b7c34d28a02029b23849d75b2a9a2acbcd3464fcf888be8abbfbfb8d66dbd9a4"
TRANSPORT_MANIFEST_SHA = "3c891dac59234a92dc58e66a8bfa7d779a4ccf20c82f057c98a463f16a3bec40"
CANDIDATE_DIR = Path("/home/claude/.local/share/codex-private/shapes8-event120-expanded-candidate-20261014")

APP_BASE = 0x4000
USB = dict(path="1-1", busnum="1", devnum="38", vid="4c4a", pid="8057")
PLANS = {
    "native": ("46425c0e3e12f5a61737c4160af595afb1c6955453bff8ee6a14d0c53279d25a", 208, TARGET_SHA,
               "offline device38 Event Horizon 120 candidate plan"),
    "stock": ("ed934f5476fb02891ebe43bae3f885e8b0900573ec78b927739681744c67455a", 213, STOCK_SHA,
              "offline device38 stock restoration plan"),
}
_POLICIES = WeakSet()


@dataclass(frozen=True, eq=False)
class Policy:
    directory: Path
    direction: str
    variant: str
    plan_bytes: bytes
    baseline: bytes
    target: bytes
    receipt_bytes: bytes
    binding_bytes: bytes
    sectors: tuple
    evidence: tuple
    _authorization: object

    def check_files(self):
        if self not in _POLICIES or self._authorization is not _VALIDATED:
            raise ValueError("Exact factory-created Event120 policy required")
        for path, sha, limit in self.evidence:
            pinned(path, sha, limit)
        plan, _, before, after = load_transaction(self.directory)
        plan_sha, count, target_sha, _ = PLANS[self.variant]
        order = checked_plan_order(plan)
        if (encoded(plan) != self.plan_bytes or before != self.baseline or after != self.target
                or digest(encoded(plan)) != plan_sha or len(order) != count
                or tuple(order) != self.sectors or order[-1] != APP_BASE or digest(after) != target_sha):
            raise ValueError("Frozen Event120 transaction differs")
        return json.loads((self.directory / "journal.json").read_bytes())

    def receipt(self):
        return json.loads(self.receipt_bytes)

    def bind(self, transport):
        self.check_files()
        return Event120Session(self, transport, _VALIDATED)


def load_policy(directory, *, receipt, direction, variant):
    if direction not in ("install", "restore") or variant not in PLANS:
        raise ValueError("Explicit Event120 direction and candidate/stock variant required")
    directory, receipt = Path(directory).resolve(), Path(receipt).resolve()
    plan_sha, count, target_sha, scope = PLANS[variant]
    mp, cp = receipt / "manifest.json", receipt / "commands.jsonl"
    manifest = json.loads(pinned(mp, MANIFEST_SHA, 65536))
    pinned(cp, COMMANDS_SHA, 8 * 1048576)
    a, b = pinned(receipt / "dumpA.bin", BASELINE_SHA), pinned(receipt / "dumpB.bin", BASELINE_SHA)
    plan, journal, before, after = load_transaction(directory)
    order = checked_plan_order(plan)
    identity = dict(unit_id="owner-fm1-fresh-rom-device38", flash_size=1048576,
        sector_size=4096, page_size=256, jedec=0x856014, simulated=False,
        usb_binding=USB, backup_manifest_sha256=MANIFEST_SHA)
    if (manifest.get("kind") != "fm1-device38-expanded-rom-fixed-loader-dual-read"
            or manifest.get("usb_binding") != USB or manifest.get("current_flash_sha256") != BASELINE_SHA
            or manifest.get("installation_proof_sha256") != INSTALLATION_PROOF_SHA
            or manifest.get("flash_operations") != 0 or manifest.get("reset_operations") != 0
            or a != b or before != a or digest(after) != target_sha or plan.get("identity") != identity
            or plan.get("scope") != scope or plan.get("commit_sector") != APP_BASE
            or order[-1] != APP_BASE or len(order) != count or digest(encoded(plan)) != plan_sha
            or plan.get("writable_ranges") != changed_ranges(before, after) or journal.get("state") != "prepared"):
        raise ValueError("Exact prepared device38 evidence and directory-last plan required")
    evidence = ((mp, MANIFEST_SHA, 65536), (cp, COMMANDS_SHA, 8 * 1048576),
        (receipt / "dumpA.bin", BASELINE_SHA, 1048576), (receipt / "dumpB.bin", BASELINE_SHA, 1048576))
    if variant == "native":
        candidate_path = CANDIDATE_DIR / "candidate-receipt.json"
        image_path = CANDIDATE_DIR / "image-receipt.json"
        transport_path = CANDIDATE_DIR / "transport-manifest.json"
        candidate_raw = pinned(candidate_path, CANDIDATE_RECEIPT_SHA, 65536)
        image_raw = pinned(image_path, IMAGE_RECEIPT_SHA, 65536)
        transport = json.loads(pinned(transport_path, TRANSPORT_MANIFEST_SHA, 65536))
        candidate = json.loads(candidate_raw)
        image = json.loads(image_raw)
        if (candidate.get("app_sha256") != CANDIDATE_APP_SHA or candidate.get("app_bytes") != 845036
                or candidate.get("target_sha256") != TARGET_SHA or candidate.get("hardware_admitted") is not False
                or candidate.get("installable") is not False or candidate.get("physical_writer_ready") is not False
                or image.get("app_sha256") != CANDIDATE_APP_SHA or image.get("app_bytes") != 845036
                or image.get("startup_project_id") != "replacement-showcase-candidate-event-horizon"
                or image.get("startup_index") != 0 or image.get("hardware_admitted") is not False
                or image.get("installable") is not False or image.get("full_song_default_accepted") is not False
                or image.get("runtime_configuration", {}).get("runtime_mode") != "song-diagnostic"
                or image.get("runtime_configuration", {}).get("return_to_rom_seconds") != 120
                or image.get("project_save_service", {}).get("save_service_armed") is not False
                or image.get("project_save_service", {}).get("storage_admitted") is not False
                or image.get("project_save_service", {}).get("flash_io_bound") is not False
                or image.get("project_save_service", {}).get("runtime_verified") is not False
                or image.get("project_save_service", {}).get("hardware_tested") is not False
                or transport.get("app_sha256") != CANDIDATE_APP_SHA or transport.get("app_bytes") != 845036
                or transport.get("target_sha256") != TARGET_SHA or transport.get("startup_index") != 0
                or transport.get("startup_project_id") != "replacement-showcase-candidate-event-horizon"
                or transport.get("hardware_admitted") is not False or transport.get("installable") is not False
                or transport.get("physical_writer_ready") is not False
                or transport.get("candidate_receipt_sha256") != digest(encoded(candidate))
                or transport.get("image_receipt_sha256") != digest(encoded(image))):
            raise ValueError("Pinned Event Horizon image/transport provenance correspondence differs")
        evidence += ((candidate_path, CANDIDATE_RECEIPT_SHA, 65536),
                     (image_path, IMAGE_RECEIPT_SHA, 65536),
                     (transport_path, TRANSPORT_MANIFEST_SHA, 65536))
    binding = dict(usb_binding=USB, backup_manifest_sha256=MANIFEST_SHA,
        backup_commands_sha256=COMMANDS_SHA, backup_campaign_sha256=manifest["campaign_sha256"])
    result = dict(kind="device38-event120-injected-policy", variant=variant, direction=direction,
        hardware_admitted=False, installable=False, physical_recovery_verified=False,
        target_sha256=target_sha, baseline_sha256=BASELINE_SHA, transaction_plan_sha256=plan_sha,
        sectors=count, commit_sector=APP_BASE)
    policy = Policy(directory, direction, variant, encoded(plan), before, after, encoded(result),
        encoded(binding), tuple(order), evidence, _VALIDATED)
    _POLICIES.add(policy)
    policy.check_files()
    return policy


class Event120Session(BoundDiagnosticSession):
    """Existing durable-intent/sector/page guards plus exact backup binding."""
    def __init__(self, policy, transport, authorization):
        if policy not in _POLICIES or authorization is not _VALIDATED:
            raise ValueError("Factory-created Event120 policy required")
        super().__init__(policy, transport, authorization)
        required = json.loads(policy.binding_bytes)
        claim = self._capture_binding()
        if any(encoded(claim.get(k)) != encoded(v) for k, v in required.items()):
            self._stop()
            raise ValueError("Device38 USB/backup/SG binding differs")

