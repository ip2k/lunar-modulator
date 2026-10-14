import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from fm1_flash_transaction import create_transaction, digest, encoded, save_journal
from fm1_fixed_target_reset import wire
from native import event120_campaign_proof as proof


USB = {"path": "1-1", "busnum": "1", "devnum": "38", "vid": "4c4a", "pid": "8057"}
SG_BINDING = proof.SG_BINDING
STOP_PROOF = {
    "schema": 1, "kind": "event120-v1-stopped-before-sg",
    "campaign_sha256": "e1ccb934a2814f85fc2ad1b5f802f5c982d8e926d1193d0b449f72c89a74bf4f",
    "commands_sha256": "1af816ae7ce0f8e5b2d607cd279c9470468888ae4a343eb7fb00696bb3963ffb",
    "consumed_marker_sha256": "a32770f18f68559923fae7c538e1e3835af9cf33e38d1382f26c331a9d5c395b",
    "events": ["native_transaction_prepared", "native_transaction_stopped"],
    "sg_commands": 0, "reset_commands": 0, "write_intents": 0,
}
PRIOR = {
    "evidence_root": "/home/claude/.local/share/codex-private/device38-event120-stopped-v1-20261014/extracted",
    "campaign_sha256": STOP_PROOF["campaign_sha256"],
    "commands_sha256": STOP_PROOF["commands_sha256"],
    "consumed_marker_sha256": STOP_PROOF["consumed_marker_sha256"],
    "adapter_sha256": proof.V1_ADAPTER_SHA256,
    "fixed_loader_source_sha256": proof.WRITER_SOURCES["fm1_fixed_loader_backup.py"],
}


class Recorder:
    def __init__(self):
        self.events = []
        self.index = 0
        self.direction = None

    def event(self, name, **fields):
        self.events.append(dict(time=100.0, event=name, **fields))

    def command(self, op, address=0, payload=b"", response=None):
        cdb, payload, size = wire(op, address, payload)
        self.event("sg_submit_intent", index=self.index, direction=self.direction,
            cdb=cdb.hex(), out_len=len(payload), in_len=size,
            payload_sha256=digest(payload) if payload else None, retry=False)
        if response is None and size:
            response = b"\x00" * size
        response_sha = digest(response) if response is not None else None
        self.event("sg_completion", index=self.index, direction=self.direction,
            status=0, masked=0, msg=0, host=0, driver=0, resid=0, info=0,
            sense_len=0, sense_hex="", retry=False, response_sha256=response_sha)
        self.index += 1

    def read(self, image, address, size):
        for page in range(address, address + size, 256):
            self.command(0xFD05, page, response=image[page:page + 256])


def transcript(campaign_sha, source_hashes, adapter_sha, backup_manifest_sha,
               sg_binding, baseline, target, order, prior_proof):
    r = Recorder()
    r.event("native_transaction_prepared", campaign_sha256=campaign_sha,
        source_sha256=source_hashes, adapter_sha256=adapter_sha,
        backup_manifest_sha256=backup_manifest_sha, sg_binding=sg_binding,
        variant="native", direction="install", retry=False,
        prior_v1_stop_proof=prior_proof)
    r.direction = "install"
    r.command(0xFC0A)
    r.read(baseline, 0, len(baseline))
    current = baseline
    written = 0
    for address in order:
        sector = target[address:address + 4096]
        actual = current[address:address + 4096]
        r.read(current, address, 4096)
        if actual != b"\xff" * 4096:
            r.event("durable_intent", operation="erase", address=address)
            r.command(0xFC0A)
            r.command(0xFB01, address)
            r.event("operation_returned", operation="erase", address=address)
        blank = current[:address] + b"\xff" * 4096 + current[address + 4096:]
        r.read(blank, address, 4096)
        for page in range(address, address + 4096, 256):
            payload = target[page:page + 256]
            if payload != b"\xff" * 256:
                r.event("durable_intent", operation="program", address=page)
                r.command(0xFC0A)
                r.command(0xFB04, page, payload)
                r.event("operation_returned", operation="program", address=page)
        current = current[:address] + sector + current[address + 4096:]
        r.read(current, address, 4096)
        r.event("sector_verified", address=address)
        written += 1
    r.read(target, 0, len(target))
    r.event("native_transaction_completed", campaign_sha256=campaign_sha,
        direction="install", variant="native", verified_sha256=digest(target),
        sectors_written=written, full_flash_readback_verified=True,
        boot_observed=False, physical_recovery_verified=False,
        kernel_exclusivity=False, hardware_admitted=False, installable=False,
        prior_v1_stop_proof=prior_proof)
    return b"".join(encoded(e) + b"\n" for e in r.events)


def test_v1_stop_event_rows_match_writer_terminal_schema():
    rows = [
        {"time": 10.0, "event": "native_transaction_prepared",
         "campaign_sha256": PRIOR["campaign_sha256"], "direction": "install",
         "variant": "native", "retry": False},
        {"time": 10.1, "event": "native_transaction_stopped",
         "error": "ValueError", "detail": "preflight refusal", "retry": False},
    ]
    proof._validate_v1_stop_events(rows, PRIOR["campaign_sha256"])
    rows[1]["campaign_sha256"] = PRIOR["campaign_sha256"]
    with pytest.raises(ValueError):
        proof._validate_v1_stop_events(rows, PRIOR["campaign_sha256"])


def test_actual_device38_sg_mapping_is_exact_and_separate_from_usb_identity():
    proof._validate_sg_binding(SG_BINDING)
    altered = dict(SG_BINDING, node_identity=[6, 1725, 5377])
    with pytest.raises(ValueError):
        proof._validate_sg_binding(altered)
    nested = dict(SG_BINDING, usb_binding=USB)
    with pytest.raises(ValueError):
        proof._validate_sg_binding(nested)


def test_replay_source_pin_rejects_modified_dependency(tmp_path):
    tools = tmp_path / "tools"
    for relative in proof.REPLAY_SOURCE_PINS:
        destination = tools / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((proof.ROOT / "tools" / relative).read_bytes())
    changed = tools / "native/event120_install_proof.py"
    changed.write_bytes(changed.read_bytes() + b"\n# changed\n")
    with pytest.raises(ValueError, match="replay dependency"):
        proof._pin_replay_sources(tmp_path)


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    case = tmp_path / "case"
    case.mkdir(mode=0o700)
    receipt = case / "backup"
    receipt.mkdir(mode=0o700)
    plan_dir = case / "plan"
    output = case / "event120-install-v2"
    output.mkdir(mode=0o700)
    baseline = b"\xff" * 1048576
    target_bytes = bytearray(baseline)
    addrs = list(range(0x4000, 0xD9000, 4096))[:208]
    for address in addrs:
        target_bytes[address:address + 4096] = b"\x00" * 4096
    target = bytes(target_bytes)
    manifest = {"kind": "fm1-device38-expanded-rom-fixed-loader-dual-read",
        "usb_binding": USB, "sg_binding": SG_BINDING,
        "flash_operations": 0, "reset_operations": 0}
    manifest_raw = encoded(manifest)
    (receipt / "manifest.json").write_bytes(manifest_raw)
    backup_commands = b"backup evidence\n"
    (receipt / "commands.jsonl").write_bytes(backup_commands)
    (receipt / "dumpA.bin").write_bytes(baseline)
    (receipt / "dumpB.bin").write_bytes(baseline)
    identity = {"unit_id": "owner-fm1-fresh-rom-device38", "flash_size": 1048576,
        "sector_size": 4096, "page_size": 256, "jedec": 0x856014,
        "simulated": False, "usb_binding": USB, "backup_manifest_sha256": "a" * 64}
    plan = create_transaction(plan_dir, baseline, baseline, target, identity,
        [[0x4000, 0xD4000]], "test full Event120", commit_sector=0x4000)
    sector_order = [a for a in addrs if a != 0x4000] + [0x4000]
    plan_sha = digest(encoded(plan))
    journal = {"schema": 1, "plan_sha256": plan_sha, "state": "complete",
        "direction": "install", "intent": None, "sector_order": sector_order,
        "verified_sha256": digest(target)}
    save_journal(plan_dir, journal)

    source_hashes = dict(proof.WRITER_SOURCES)
    adapter_sha = proof.WRITER_ADAPTER_SHA256
    monkeypatch.setattr(proof, "_pin_sources", lambda *args: None)
    monkeypatch.setattr(proof, "_validate_candidate_sources", lambda: None)
    monkeypatch.setattr(proof, "_verify_v1_stop",
        lambda prior: STOP_PROOF if prior == PRIOR else (_ for _ in ()).throw(ValueError("prior mismatch")))
    monkeypatch.setattr(proof, "BASELINE_SHA", digest(baseline))
    monkeypatch.setattr(proof, "TARGET_SHA", digest(target))
    monkeypatch.setattr(proof, "MANIFEST_SHA", digest(manifest_raw))
    monkeypatch.setattr(proof, "COMMANDS_SHA", digest(backup_commands))
    monkeypatch.setattr(proof, "PLAN_PINS", {"native": (digest(encoded(plan)), 208, digest(target)),
        "stock": proof.PLAN_PINS["stock"]})
    campaign = {"schema": 2, "kind": "fm1-device38-event120-transaction-v2",
        "adapter_sha256": adapter_sha, "observed_at": 100.0,
        "receipt": str(receipt), "plan": str(plan_dir), "direction": "install",
        "variant": "native", "output": str(output), "sg_binding": SG_BINDING,
        "prior_v1_stop": PRIOR}
    campaign_raw = encoded(campaign)
    campaign_path = case / "event120-install-v2-campaign.json"
    campaign_path.write_bytes(campaign_raw)
    campaign_sha = digest(campaign_raw)
    (case / ".event120-v2-native-install.consumed").write_bytes(campaign_sha.encode("ascii"))
    result = {"campaign_sha256": campaign_sha, "direction": "install", "variant": "native",
        "verified_sha256": digest(target), "sectors_written": 208,
        "full_flash_readback_verified": True, "boot_observed": False,
        "physical_recovery_verified": False, "kernel_exclusivity": False,
        "hardware_admitted": False, "installable": False,
        "prior_v1_stop_proof": STOP_PROOF}
    (output / "result.json").write_bytes(encoded(result))
    raw_transcript = transcript(campaign_sha, source_hashes, adapter_sha,
        digest(manifest_raw), manifest["sg_binding"], baseline, target,
        sector_order, STOP_PROOF)
    (output / "commands.jsonl").write_bytes(raw_transcript)
    return {"case": case, "campaign": campaign_path, "campaign_sha": campaign_sha,
        "output": output, "target": target, "baseline": baseline,
        "result": result, "sector_order": sector_order, "raw": raw_transcript}


def test_successful_208_sector_evidence_is_fully_replayed(bundle):
    report = proof.verify(bundle["campaign"].parent, bundle["campaign_sha"],
                          source_root=bundle["case"], now=120.0)
    verified = report["proof"]
    assert verified["verified"] is True
    assert verified["hardware_operations"] == 0
    assert verified["hardware_admitted"] is False and verified["installable"] is False
    assert verified["sectors"] == 208
    assert verified["prior_v1_stop_proof"] == STOP_PROOF
    assert len(report["evidence_sha256"]) >= 12
    assert str(bundle["campaign"]) in report["evidence_sha256"]


@pytest.mark.parametrize("mutation", ["prior-v1", "readback", "source", "prepared"])
def test_mutated_or_incomplete_evidence_is_rejected(bundle, monkeypatch, mutation):
    campaign_path = bundle["campaign"]
    if mutation == "prior-v1":
        campaign = json.loads(campaign_path.read_bytes())
        campaign["prior_v1_stop"]["commands_sha256"] = "0" * 64
        raw = encoded(campaign)
        campaign_path.write_bytes(raw)
        bundle["campaign_sha"] = digest(raw)
        (bundle["case"] / ".event120-v2-native-install.consumed").write_bytes(bundle["campaign_sha"].encode())
    elif mutation == "readback":
        rows = bundle["raw"].splitlines()
        submit = next(i for i, row in enumerate(rows)
            if json.loads(row).get("event") == "sg_submit_intent" and
               json.loads(row).get("cdb", "").startswith("fd05"))
        completion = submit + 1
        record = json.loads(rows[completion])
        record["response_sha256"] = "0" * 64
        rows[completion] = encoded(record)
        (bundle["output"] / "commands.jsonl").write_bytes(b"\n".join(rows) + b"\n")
    elif mutation == "source":
        rows = bundle["raw"].splitlines()
        first = json.loads(rows[0])
        first["source_sha256"]["native/event120_bench_transactions.py"] = "0" * 64
        rows[0] = encoded(first)
        (bundle["output"] / "commands.jsonl").write_bytes(b"\n".join(rows) + b"\n")
    elif mutation == "prepared":
        plan_dir = bundle["case"] / "plan"
        journal = json.loads((plan_dir / "journal.json").read_bytes())
        journal["state"] = "prepared"
        save_journal(plan_dir, journal)
    with pytest.raises((ValueError, OSError)):
        proof.verify(campaign_path.parent, bundle["campaign_sha"],
                     source_root=bundle["case"], now=120.0)


def test_symlink_evidence_is_rejected(bundle):
    actual = bundle["case"] / ".event120-v2-native-install.consumed"
    link = bundle["case"] / "marker-link"
    link.symlink_to(actual)
    with pytest.raises(ValueError, match="Symlink"):
        proof._read(link, 128)
