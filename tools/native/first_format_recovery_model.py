# SPDX-License-Identifier: MIT
"""Offline-only model for a ROM-held first-format campaign.

This module consumes supplied snapshot/readback bytes. It has no transport,
flash API, device discovery, or command generation. The state machine records
operator-reported observations and always withholds physical/admission claims.
"""
import hashlib
import json
import re

from tail_migration_plan import FLASH_BYTES, SECTOR_BYTES, SLOT_SECTORS

PAGE_BYTES = 0x100
PAYLOAD_BOUND = 43130
CAMPAIGN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{7,63}\Z")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _digest(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"{label}: lowercase SHA-256 required")
    return value


def _slot_sector_order():
    return tuple((slot, offset) for slot, offsets in SLOT_SECTORS.items()
                 for offset in offsets)


def _protected_runs():
    mapped = sorted(offset for offsets in SLOT_SECTORS.values() for offset in offsets)
    runs = []
    cursor = 0
    for sector in mapped:
        if cursor < sector:
            runs.append((cursor, sector - cursor))
        cursor = sector + SECTOR_BYTES
    if cursor < FLASH_BYTES:
        runs.append((cursor, FLASH_BYTES - cursor))
    return runs


def create_campaign(snapshot_a, snapshot_b, snapshot_sha256, target_identity,
                    expected_target_identity, campaign_id, archive_refs,
                    payload_bytes):
    """Create a review plan from two matching 1 MiB snapshots; never IO-ready."""
    expected = _digest(snapshot_sha256, "snapshot")
    if not isinstance(snapshot_a, bytes) or not isinstance(snapshot_b, bytes):
        raise ValueError("Two complete immutable snapshot byte strings required")
    if len(snapshot_a) != FLASH_BYTES or len(snapshot_b) != FLASH_BYTES:
        raise ValueError("Two complete 1 MiB snapshots required")
    if snapshot_a != snapshot_b or sha256(snapshot_a) != expected:
        raise ValueError("Matching snapshots bound to explicit full-image SHA-256 required")
    if (not isinstance(target_identity, str) or not target_identity.strip()
            or target_identity != expected_target_identity):
        raise ValueError("Explicit matching target identity assertion required")
    if not isinstance(campaign_id, str) or not CAMPAIGN_ID.fullmatch(campaign_id):
        raise ValueError("Unique, bounded campaign ID required")
    if (not isinstance(archive_refs, (list, tuple)) or len(archive_refs) != 2
            or any(not isinstance(ref, str) or not ref.strip() for ref in archive_refs)
            or archive_refs[0] == archive_refs[1]):
        raise ValueError("Two distinct durable private archive references required")
    if (not isinstance(payload_bytes, int) or isinstance(payload_bytes, bool)
            or not 0 <= payload_bytes <= PAYLOAD_BOUND):
        raise ValueError("Payload exceeds the measured 43,130-byte supported bound")

    sectors = []
    for slot, offset in _slot_sector_order():
        before = snapshot_a[offset:offset + SECTOR_BYTES]
        trailer = snapshot_a[offset + 0xF00:offset + SECTOR_BYTES]
        sectors.append({"slot": slot, "offset": offset,
                        "before_sha256": sha256(before),
                        "erased_sha256": sha256(b"\xff" * SECTOR_BYTES),
                        "trailer_before_sha256": sha256(trailer),
                        "trailer_before_is_ff": trailer == bytes([0xff]) * PAGE_BYTES})
    protected = [{"offset": offset, "length": length,
                  "sha256": sha256(snapshot_a[offset:offset + length])}
                 for offset, length in _protected_runs()]
    plan = {
        "schema": 1,
        "kind": "fm1-storage48-first-format-recovery-plan",
        "campaign_id": campaign_id,
        "target_identity_assertion": target_identity,
        "snapshot_sha256": expected,
        "archive_refs": list(archive_refs),
        "payload_bytes": payload_bytes,
        "sector_size": SECTOR_BYTES,
        "slot_sector_count": len(sectors),
        "sectors": sectors,
        "protected_complement_extents": protected,
        "required_operator_actions": [
            "obtain ROM mode before each operation or after any interruption",
            "read and compare observed bytes before deciding resume or rollback",
            "retain both exact private baseline archives until migration acceptance"],
        "execution": "review-plan-only",
        "commands": [],
        "physical_usb_key_verified": False,
        "physical_rom_recovery_verified": False,
        "semantic_migration_verified": False,
        "physical_rollback_verified": False,
        "hardware_admitted": False,
        "physical_writer_ready": False,
        "hardware_operations": 0,
    }
    plan["plan_sha256"] = sha256(_canonical(plan))
    return plan


def _verify_plan(plan):
    if not isinstance(plan, dict) or plan.get("kind") != "fm1-storage48-first-format-recovery-plan":
        raise ValueError("Recognized campaign plan required")
    expected = _digest(plan.get("plan_sha256"), "plan")
    body = dict(plan)
    del body["plan_sha256"]
    if sha256(_canonical(body)) != expected:
        raise ValueError("Campaign plan digest mismatch")
    if plan.get("slot_sector_count") != 24 or len(plan.get("sectors", [])) != 24:
        raise ValueError("Exact reviewed 24-sector map required")
    if plan.get("execution") != "review-plan-only" or plan.get("commands") != []:
        raise ValueError("Plan must not contain executable commands")
    if any(plan.get(flag) is not False for flag in (
            "physical_usb_key_verified", "physical_rom_recovery_verified",
            "semantic_migration_verified", "physical_rollback_verified",
            "hardware_admitted", "physical_writer_ready")):
        raise ValueError("Physical and migration claims must remain false")
    if plan.get("hardware_operations") != 0:
        raise ValueError("Hardware operation count must remain zero")
    canonical = [{"slot": slot, "offset": offset}
                 for slot, offset in _slot_sector_order()]
    for row, expected_row in zip(plan["sectors"], canonical):
        if (row.get("slot"), row.get("offset")) != (expected_row["slot"], expected_row["offset"]):
            raise ValueError("Sector order differs from the fixed reviewed map")
        _digest(row.get("before_sha256"), "sector baseline")
        _digest(row.get("erased_sha256"), "erased sector")
        _digest(row.get("trailer_before_sha256"), "trailer baseline")
        if not isinstance(row.get("trailer_before_is_ff"), bool):
            raise ValueError("Trailer baseline state must be explicit")
    payload_bytes = plan.get("payload_bytes")
    if (not isinstance(payload_bytes, int) or isinstance(payload_bytes, bool)
            or not 0 <= payload_bytes <= PAYLOAD_BOUND):
        raise ValueError("Campaign payload exceeds supported bound")
    archive_refs = plan.get("archive_refs")
    if (not isinstance(archive_refs, list) or len(archive_refs) != 2
            or any(not isinstance(ref, str) or not ref.strip() for ref in archive_refs)
            or archive_refs[0] == archive_refs[1]):
        raise ValueError("Two baseline archive references required")
    protected_expected = _protected_runs()
    rows = plan.get("protected_complement_extents")
    if not isinstance(rows, list) or len(rows) != len(protected_expected):
        raise ValueError("Protected complement map mismatch")
    for row, (offset, length) in zip(rows, protected_expected):
        if row.get("offset") != offset or row.get("length") != length:
            raise ValueError("Protected complement extent differs from fixed map")
        _digest(row.get("sha256"), "protected extent")
    return expected


def new_journal(plan):
    """Start an append-only hash-chained journal bound to one immutable plan."""
    _verify_plan(plan)
    journal = {"schema": 1, "plan_sha256": plan["plan_sha256"], "events": []}
    return append_event(journal, plan, "campaign_opened", {}, rom_recovery_verified=False)


def append_event(journal, plan, event, data, *, rom_recovery_verified=False,
                 _validate_existing=True):
    """Append an observation/checkpoint. No function here performs operations."""
    _verify_plan(plan)
    if not isinstance(journal, dict) or journal.get("plan_sha256") != plan["plan_sha256"]:
        raise ValueError("Journal does not match this plan")
    if not isinstance(data, dict) or not isinstance(event, str):
        raise ValueError("Typed event and data object required")
    events = list(journal.get("events", []))
    if events:
        expected_prev = events[-1]["event_sha256"]
        if _validate_existing and not _valid_journal(journal, plan):
            raise ValueError("Existing journal chain is invalid")
    else:
        expected_prev = "0" * 64
    if not events and event != "campaign_opened":
        raise ValueError("Journal must begin with campaign_opened")
    if events and events[0].get("event") != "campaign_opened":
        raise ValueError("Journal is missing campaign_opened")
    state = _derive_state(events, plan)
    if event == "campaign_opened":
        if events or data:
            raise ValueError("Campaign can be opened exactly once")
    elif event == "erase_started":
        if (state["uncertain"] or state["awaiting_readback"] or
                state["active_index"] is not None or state["rollback"] or state["complete"]):
            raise ValueError("Campaign state does not permit erase progress")
        idx = state["next_index"]
        if idx >= 24 or data.get("sector_index") != idx:
            raise ValueError("Erase sectors must follow the fixed map in order")
        row = plan["sectors"][idx]
        if data.get("observed_before_sha256") != row["before_sha256"]:
            raise ValueError("Before-readback does not match frozen baseline sector")
        _digest(data.get("observed_before_sha256"), "before readback")
        if rom_recovery_verified is not True:
            raise ValueError("Operator must attest ROM recovery before a sector action")
    elif event == "erase_ack_uncertain":
        if not state["awaiting_readback"] or state["uncertain"]:
            raise ValueError("No unambiguous erase is awaiting acknowledgement")
        if data.get("sector_index") != state["active_index"]:
            raise ValueError("Uncertain acknowledgement must name active sector")
    elif event == "erase_readback":
        if not state["awaiting_readback"] and not state["uncertain"]:
            raise ValueError("No sector action is awaiting observation")
        idx = state["active_index"]
        if data.get("sector_index") != idx:
            raise ValueError("Readback must name active sector")
        observed = _digest(data.get("observed_sha256"), "observed sector")
        row = plan["sectors"][idx]
        if data.get("observed_length") != SECTOR_BYTES:
            raise ValueError("Complete 4 KiB sector readback required")
        if rom_recovery_verified is not True:
            raise ValueError("Operator must attest ROM recovery before readback acceptance")
        if observed == row["before_sha256"] and not state["uncertain"]:
            raise ValueError("Erase readback did not show erased bytes")
    elif event == "rollback_started":
        if (state["awaiting_readback"] or state["uncertain"]
                or state["rollback_awaiting"] or state["complete"]):
            raise ValueError("Resolve uncertain operation before rollback")
        idx = state["rollback_index"] if state["rollback"] else state["next_index"] - 1
        if idx < 0 or data.get("sector_index") != idx:
            raise ValueError("Rollback proceeds in reverse over verified erased sectors")
        if data.get("restore_source_sha256") != plan["sectors"][idx]["before_sha256"]:
            raise ValueError("Rollback source must bind exact baseline sector")
        if rom_recovery_verified is not True:
            raise ValueError("Operator must attest ROM recovery before rollback")
    elif event == "rollback_readback":
        if not state["rollback_awaiting"]:
            raise ValueError("No rollback sector is awaiting readback")
        idx = state["rollback_index"]
        if (data.get("sector_index") != idx
                or data.get("observed_sha256") != plan["sectors"][idx]["before_sha256"]
                or data.get("observed_length") != SECTOR_BYTES):
            raise ValueError("Rollback readback must exactly match baseline sector")
        if rom_recovery_verified is not True:
            raise ValueError("Operator must attest ROM recovery before rollback verification")
    elif event == "restore_started":
        if (not state["uncertain"] or state["active_index"] is None
                or state["restore_awaiting"] or state["complete"]):
            raise ValueError("Only an inspected uncertain active sector can be restored")
        idx = state["active_index"]
        if (data.get("sector_index") != idx
                or data.get("observed_current_sha256") != state["observed_sha256"]):
            raise ValueError("Restoration must bind the latest complete active-sector readback")
        if data.get("restore_source_sha256") != plan["sectors"][idx]["before_sha256"]:
            raise ValueError("Restoration source must bind the exact baseline sector")
        if data.get("archive_ref") not in plan["archive_refs"]:
            raise ValueError("Restoration source must name a bound baseline archive")
        if rom_recovery_verified is not True:
            raise ValueError("Operator must attest ROM recovery before sector restoration")
    elif event == "restore_ack_uncertain":
        if not state["restore_awaiting"] or data.get("sector_index") != state["active_index"]:
            raise ValueError("No restoration acknowledgement is awaiting inspection")
    elif event == "restore_readback":
        if (not state["restore_awaiting"] and not state["restore_attempted"]
                or state["active_index"] is None):
            raise ValueError("No active-sector restoration is awaiting readback")
        idx = state["active_index"]
        if (data.get("sector_index") != idx or data.get("observed_length") != SECTOR_BYTES
                or rom_recovery_verified is not True):
            raise ValueError("Restoration requires ROM-attested complete 4 KiB readback")
        _digest(data.get("observed_sha256"), "restored sector")
    else:
        raise ValueError("Unsupported journal event")

    entry = {"seq": len(events), "event": event, "data": data,
             "rom_recovery_verified": bool(rom_recovery_verified),
             "previous_sha256": expected_prev}
    entry["event_sha256"] = sha256(_canonical(entry))
    events.append(entry)
    result = {"schema": 1, "plan_sha256": plan["plan_sha256"], "events": events}
    _derive_state(events, plan)
    return result


def _valid_journal(journal, plan):
    if (not isinstance(journal, dict) or journal.get("schema") != 1
            or journal.get("plan_sha256") != plan["plan_sha256"]
            or not isinstance(journal.get("events"), list)):
        return False
    prev = "0" * 64
    for seq, entry in enumerate(journal["events"]):
        if not isinstance(entry, dict):
            return False
        body = dict(entry)
        digest = body.pop("event_sha256", None)
        if (entry.get("seq") != seq or entry.get("previous_sha256") != prev
                or not isinstance(digest, str)
                or digest != sha256(_canonical(body))):
            return False
        prev = digest
    # A recomputed hash chain is not enough: replay every transition through
    # the same transition validator from an empty journal.
    replay = {"schema": 1, "plan_sha256": plan["plan_sha256"], "events": []}
    try:
        for entry in journal["events"]:
            replay = append_event(
                replay, plan, entry["event"], entry["data"],
                rom_recovery_verified=entry["rom_recovery_verified"],
                _validate_existing=False)
            if replay["events"][-1] != entry:
                return False
    except (KeyError, TypeError, ValueError, IndexError):
        return False
    return True


def _derive_state(events, plan):
    state = {"next_index": 0, "active_index": None, "awaiting_readback": False,
             "uncertain": False, "rollback": False, "rollback_awaiting": False,
             "rollback_index": None, "restore_awaiting": False,
             "restore_attempted": False, "observed_sha256": None, "complete": False}
    for entry in events:
        event, data = entry["event"], entry["data"]
        if event == "campaign_opened":
            continue
        if event == "erase_started":
            state.update(active_index=data["sector_index"], awaiting_readback=True,
                         uncertain=False)
        elif event == "erase_ack_uncertain":
            state["uncertain"] = True
        elif event == "erase_readback":
            row = plan["sectors"][state["active_index"]]
            observed = data["observed_sha256"]
            if observed == row["erased_sha256"]:
                state["next_index"] += 1
                state.update(active_index=None, awaiting_readback=False, uncertain=False,
                             observed_sha256=None)
            elif observed == row["before_sha256"]:
                # Lost acknowledgement with unchanged bytes; retry the same sector.
                state.update(active_index=None, awaiting_readback=False, uncertain=False,
                             observed_sha256=None)
            else:
                # Keep the active sector pinned for ROM-held exact restoration.
                state.update(awaiting_readback=False, uncertain=True,
                             observed_sha256=observed)
        elif event == "restore_started":
            state.update(restore_awaiting=True, restore_attempted=True, uncertain=False)
        elif event == "restore_ack_uncertain":
            state.update(restore_awaiting=False, restore_attempted=True, uncertain=True)
        elif event == "restore_readback":
            observed = data["observed_sha256"]
            state.update(restore_awaiting=False, restore_attempted=False,
                         observed_sha256=observed)
            if observed == plan["sectors"][state["active_index"]]["before_sha256"]:
                state.update(active_index=None, uncertain=False, observed_sha256=None,
                             rollback=True, rollback_index=state["next_index"] - 1)
                if state["rollback_index"] < 0:
                    state["complete"] = True
            else:
                state["uncertain"] = True
        elif event == "rollback_started":
            state.update(rollback=True, rollback_awaiting=True,
                         rollback_index=data["sector_index"])
        elif event == "rollback_readback":
            state["rollback_awaiting"] = False
            state["rollback_index"] -= 1
            if state["rollback_index"] < 0:
                state["complete"] = True
    return state


def journal_state(journal, plan):
    _verify_plan(plan)
    if not _valid_journal(journal, plan):
        raise ValueError("Journal chain is invalid")
    state = _derive_state(journal["events"], plan)
    if state["uncertain"] or state["awaiting_readback"] or state["restore_awaiting"]:
        state["status"] = "stop_and_reenter_rom_to_inspect"
    elif state["complete"]:
        state["status"] = "rollback_readback_complete_unverified_full_image"
    elif state["rollback"]:
        state["status"] = "rollback_in_progress"
    elif state["next_index"] == 24:
        state["status"] = "all_slots_readback_erased_under_operator_report"
    else:
        state["status"] = "ready_for_reviewed_next_checkpoint"
    state.update({"physical_recovery_verified": False, "hardware_admitted": False,
                  "hardware_operations": 0})
    return state
