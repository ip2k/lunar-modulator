# SPDX-License-Identifier: MIT
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/native"))
from first_format_recovery_model import (
    FLASH_BYTES, SECTOR_BYTES, SLOT_SECTORS, append_event, create_campaign,
    journal_state, new_journal, sha256,
)


def fixture():
    raw = bytearray(bytes([255]) * FLASH_BYTES)
    raw[SLOT_SECTORS["A"][0]] = 0x00
    raw[SLOT_SECTORS["A"][1]] = 0x7f
    # Model the archived stock image's eight non-FF mapped trailer pages.
    for slot, offsets in SLOT_SECTORS.items():
        for index, offset in enumerate(offsets):
            if index < 4:
                raw[offset + 0xF00 + index] = (index + 1) * 17
    image = bytes(raw)
    return image, create_campaign(
        image, image, sha256(image), "FM-1_500", "FM-1_500",
        "campaign-20261014-a", ("private://archive-one", "private://archive-two"),
        43130)


def start(journal, plan, index):
    return append_event(
        journal, plan, "erase_started",
        {"sector_index": index,
         "observed_before_sha256": plan["sectors"][index]["before_sha256"]},
        rom_recovery_verified=True)


def readback(journal, plan, index, digest):
    return append_event(
        journal, plan, "erase_readback",
        {"sector_index": index, "observed_sha256": digest,
         "observed_length": SECTOR_BYTES},
        rom_recovery_verified=True)


def test_campaign_binds_fresh_pair_fixed_map_payload_and_false_claims():
    image, plan = fixture()
    assert plan["snapshot_sha256"] == sha256(image)
    assert plan["slot_sector_count"] == 24
    assert plan["payload_bytes"] == 43130
    assert sum(not row["trailer_before_is_ff"] for row in plan["sectors"]) == 8
    assert all(row["trailer_before_sha256"] for row in plan["sectors"])
    assert plan["commands"] == []
    assert plan["execution"] == "review-plan-only"
    assert all(plan[k] is False for k in (
        "physical_usb_key_verified", "physical_rom_recovery_verified",
        "semantic_migration_verified", "physical_rollback_verified",
        "hardware_admitted", "physical_writer_ready"))
    assert plan["hardware_operations"] == 0
    assert sum(x["length"] for x in plan["protected_complement_extents"]) > 0


@pytest.mark.parametrize("change", ["pair", "digest", "identity", "campaign", "archive", "payload"])
def test_campaign_rejects_unbound_or_out_of_bound_inputs(change):
    image, _ = fixture()
    kwargs = dict(
        snapshot_a=image, snapshot_b=image, snapshot_sha256=sha256(image),
        target_identity="FM-1_500", expected_target_identity="FM-1_500",
        campaign_id="campaign-20261014-b",
        archive_refs=("private://one", "private://two"), payload_bytes=43130)
    if change == "pair":
        kwargs["snapshot_b"] = image[:-1] + bytes([0])
    elif change == "digest":
        kwargs["snapshot_sha256"] = "0" * 64
    elif change == "identity":
        kwargs["expected_target_identity"] = "FM-1_092"
    elif change == "campaign":
        kwargs["campaign_id"] = "../bad"
    elif change == "archive":
        kwargs["archive_refs"] = ("same", "same")
    elif change == "payload":
        kwargs["payload_bytes"] = 43131
    with pytest.raises(ValueError):
        create_campaign(**kwargs)


def test_erase_progress_requires_rom_attestation_order_and_full_readback():
    _, plan = fixture()
    journal = new_journal(plan)
    with pytest.raises(ValueError, match="ROM"):
        append_event(journal, plan, "erase_started",
                     {"sector_index": 0,
                      "observed_before_sha256": plan["sectors"][0]["before_sha256"]})
    with pytest.raises(ValueError, match="order"):
        append_event(journal, plan, "erase_started",
                     {"sector_index": 1,
                      "observed_before_sha256": plan["sectors"][1]["before_sha256"]},
                     rom_recovery_verified=True)
    journal = start(journal, plan, 0)
    with pytest.raises(ValueError, match="4 KiB"):
        append_event(journal, plan, "erase_readback",
                     {"sector_index": 0,
                      "observed_sha256": plan["sectors"][0]["erased_sha256"],
                      "observed_length": 1}, rom_recovery_verified=True)
    journal = readback(journal, plan, 0, plan["sectors"][0]["erased_sha256"])
    assert journal_state(journal, plan)["next_index"] == 1
    assert journal_state(journal, plan)["status"] == "ready_for_reviewed_next_checkpoint"


def test_lost_ack_requires_rom_readback_and_unchanged_sector_can_resume():
    _, plan = fixture()
    journal = start(new_journal(plan), plan, 0)
    journal = append_event(journal, plan, "erase_ack_uncertain",
                           {"sector_index": 0})
    assert journal_state(journal, plan)["status"] == "stop_and_reenter_rom_to_inspect"
    with pytest.raises(ValueError, match="ROM"):
        append_event(journal, plan, "erase_readback",
                     {"sector_index": 0,
                      "observed_sha256": plan["sectors"][0]["before_sha256"],
                      "observed_length": SECTOR_BYTES})
    journal = readback(journal, plan, 0, plan["sectors"][0]["before_sha256"])
    assert journal_state(journal, plan)["next_index"] == 0
    assert journal_state(journal, plan)["status"] == "ready_for_reviewed_next_checkpoint"
    journal = start(journal, plan, 0)
    journal = readback(journal, plan, 0, plan["sectors"][0]["erased_sha256"])
    assert journal_state(journal, plan)["next_index"] == 1


def test_interruption_after_erasure_is_resolved_only_by_observed_ff():
    _, plan = fixture()
    journal = start(new_journal(plan), plan, 0)
    journal = append_event(journal, plan, "erase_ack_uncertain",
                           {"sector_index": 0})
    journal = readback(journal, plan, 0, plan["sectors"][0]["erased_sha256"])
    state = journal_state(journal, plan)
    assert state["next_index"] == 1
    assert state["status"] == "ready_for_reviewed_next_checkpoint"
    assert state["physical_recovery_verified"] is False
    assert state["hardware_operations"] == 0


def test_rollback_progress_is_reverse_order_and_exact_baseline_readback():
    _, plan = fixture()
    journal = new_journal(plan)
    for index in range(2):
        journal = start(journal, plan, index)
        journal = readback(journal, plan, index, plan["sectors"][index]["erased_sha256"])
    with pytest.raises(ValueError, match="reverse"):
        append_event(journal, plan, "rollback_started",
                     {"sector_index": 0,
                      "restore_source_sha256": plan["sectors"][0]["before_sha256"]},
                     rom_recovery_verified=True)
    for index in (1, 0):
        journal = append_event(
            journal, plan, "rollback_started",
            {"sector_index": index,
             "restore_source_sha256": plan["sectors"][index]["before_sha256"]},
            rom_recovery_verified=True)
        with pytest.raises(ValueError, match="baseline"):
            append_event(journal, plan, "rollback_readback",
                         {"sector_index": index, "observed_sha256": "0" * 64,
                          "observed_length": SECTOR_BYTES}, rom_recovery_verified=True)
        journal = append_event(
            journal, plan, "rollback_readback",
            {"sector_index": index,
             "observed_sha256": plan["sectors"][index]["before_sha256"],
             "observed_length": SECTOR_BYTES}, rom_recovery_verified=True)
    state = journal_state(journal, plan)
    assert state["status"] == "rollback_readback_complete_unverified_full_image"
    assert state["physical_recovery_verified"] is False


def test_checkpoint_tampering_and_other_plan_replay_are_rejected():
    _, plan = fixture()
    journal = start(new_journal(plan), plan, 0)
    changed = copy.deepcopy(journal)
    changed["events"][1]["data"]["sector_index"] = 4
    with pytest.raises(ValueError, match="chain"):
        append_event(changed, plan, "erase_ack_uncertain", {"sector_index": 0})
    other = dict(plan)
    other["campaign_id"] = "campaign-20261014-c"
    from first_format_recovery_model import _canonical
    body = dict(other)
    body.pop("plan_sha256")
    other["plan_sha256"] = sha256(_canonical(body))
    with pytest.raises(ValueError, match="does not match"):
        append_event(journal, other, "erase_ack_uncertain", {"sector_index": 0})


def test_mixed_readback_stops_campaign_for_rom_recovery():
    _, plan = fixture()
    journal = start(new_journal(plan), plan, 0)
    mixed_digest = "a" * 64
    assert mixed_digest not in (plan["sectors"][0]["before_sha256"],
                                plan["sectors"][0]["erased_sha256"])
    journal = readback(journal, plan, 0, mixed_digest)
    state = journal_state(journal, plan)
    assert state["status"] == "stop_and_reenter_rom_to_inspect"
    with pytest.raises(ValueError, match="state"):
        start(journal, plan, 0)


def test_rollback_must_read_back_before_next_rollback_action():
    _, plan = fixture()
    journal = start(new_journal(plan), plan, 0)
    journal = readback(journal, plan, 0, plan["sectors"][0]["erased_sha256"])
    journal = append_event(
        journal, plan, "rollback_started",
        {"sector_index": 0,
         "restore_source_sha256": plan["sectors"][0]["before_sha256"]},
        rom_recovery_verified=True)
    with pytest.raises(ValueError, match="Resolve uncertain"):
        append_event(
            journal, plan, "rollback_started",
            {"sector_index": 0,
             "restore_source_sha256": plan["sectors"][0]["before_sha256"]},
            rom_recovery_verified=True)


def test_rehashed_plan_still_rejects_invalid_payload_and_archive_identity():
    from first_format_recovery_model import _canonical

    _, plan = fixture()
    for field, value in (("payload_bytes", -1),
                         ("archive_refs", ["private://same", "private://same"])):
        changed = copy.deepcopy(plan)
        changed[field] = value
        changed.pop("plan_sha256")
        changed["plan_sha256"] = sha256(_canonical(changed))
        with pytest.raises(ValueError):
            new_journal(changed)


def test_mixed_first_erase_can_be_restored_from_bound_snapshot_in_rom():
    _, plan = fixture()
    journal = new_journal(plan)
    # First sector was erased; the second first-format erase was interrupted
    # with a mixed sector and must be restored exactly before reverse rollback.
    journal = start(journal, plan, 0)
    journal = readback(journal, plan, 0, plan["sectors"][0]["erased_sha256"])
    journal = start(journal, plan, 1)
    mixed = "b" * 64
    journal = readback(journal, plan, 1, mixed)
    assert journal_state(journal, plan)["active_index"] == 1
    assert journal_state(journal, plan)["uncertain"]
    with pytest.raises(ValueError, match="restoration"):
        append_event(
            journal, plan, "restore_readback",
            {"sector_index": 1, "observed_sha256": plan["sectors"][1]["before_sha256"],
             "observed_length": SECTOR_BYTES}, rom_recovery_verified=True)
    with pytest.raises(ValueError, match="ROM"):
        append_event(journal, plan, "restore_started",
                     {"sector_index": 1, "observed_current_sha256": mixed,
                      "restore_source_sha256": plan["sectors"][1]["before_sha256"],
                      "archive_ref": plan["archive_refs"][0]})
    journal = append_event(
        journal, plan, "restore_started",
        {"sector_index": 1, "observed_current_sha256": mixed,
         "restore_source_sha256": plan["sectors"][1]["before_sha256"],
         "archive_ref": plan["archive_refs"][0]}, rom_recovery_verified=True)
    journal = append_event(
        journal, plan, "restore_readback",
        {"sector_index": 1, "observed_sha256": plan["sectors"][1]["before_sha256"],
         "observed_length": SECTOR_BYTES}, rom_recovery_verified=True)
    state = journal_state(journal, plan)
    assert state["status"] == "rollback_in_progress"
    assert state["active_index"] is None
    assert state["rollback_index"] == 0
    journal = append_event(
        journal, plan, "rollback_started",
        {"sector_index": 0,
         "restore_source_sha256": plan["sectors"][0]["before_sha256"]},
        rom_recovery_verified=True)
    journal = append_event(
        journal, plan, "rollback_readback",
        {"sector_index": 0, "observed_sha256": plan["sectors"][0]["before_sha256"],
         "observed_length": SECTOR_BYTES}, rom_recovery_verified=True)
    assert journal_state(journal, plan)["status"] == "rollback_readback_complete_unverified_full_image"


def test_interrupted_restore_can_be_reinspected_and_repeated_exactly():
    _, plan = fixture()
    journal = start(new_journal(plan), plan, 0)
    journal = readback(journal, plan, 0, "c" * 64)
    journal = append_event(
        journal, plan, "restore_started",
        {"sector_index": 0, "observed_current_sha256": "c" * 64,
         "restore_source_sha256": plan["sectors"][0]["before_sha256"],
         "archive_ref": plan["archive_refs"][1]}, rom_recovery_verified=True)
    journal = append_event(journal, plan, "restore_ack_uncertain",
                           {"sector_index": 0}, rom_recovery_verified=True)
    assert journal_state(journal, plan)["status"] == "stop_and_reenter_rom_to_inspect"
    partial = "d" * 64
    journal = append_event(
        journal, plan, "restore_readback",
        {"sector_index": 0, "observed_sha256": partial,
         "observed_length": SECTOR_BYTES}, rom_recovery_verified=True)
    journal = append_event(
        journal, plan, "restore_started",
        {"sector_index": 0, "observed_current_sha256": partial,
         "restore_source_sha256": plan["sectors"][0]["before_sha256"],
         "archive_ref": plan["archive_refs"][0]}, rom_recovery_verified=True)
    journal = append_event(
        journal, plan, "restore_readback",
        {"sector_index": 0, "observed_sha256": plan["sectors"][0]["before_sha256"],
         "observed_length": SECTOR_BYTES}, rom_recovery_verified=True)
    assert journal_state(journal, plan)["status"] == "rollback_readback_complete_unverified_full_image"


def test_recomputed_hashes_do_not_admit_semantically_invalid_journal():
    from first_format_recovery_model import _canonical

    _, plan = fixture()
    journal = new_journal(plan)
    # Forge a well-formed hash chain with an out-of-order erase event. A plain
    # hash check would accept it because the event hashes are recomputed.
    bad = copy.deepcopy(journal)
    entry = {"seq": 1, "event": "erase_started",
             "data": {"sector_index": 7,
                      "observed_before_sha256": plan["sectors"][7]["before_sha256"]},
             "rom_recovery_verified": True,
             "previous_sha256": bad["events"][-1]["event_sha256"]}
    entry["event_sha256"] = sha256(_canonical(entry))
    bad["events"].append(entry)
    with pytest.raises(ValueError, match="chain"):
        append_event(bad, plan, "erase_ack_uncertain", {"sector_index": 7})
    with pytest.raises(ValueError, match="chain"):
        journal_state(bad, plan)

def test_restore_requires_complete_inspection_and_blocks_erase_readback():
    _, plan = fixture()
    journal = start(new_journal(plan), plan, 0)
    journal = append_event(journal, plan, "erase_ack_uncertain",
                           {"sector_index": 0})
    with pytest.raises(ValueError, match="inspected uncertain"):
        append_event(
            journal, plan, "restore_started",
            {"sector_index": 0, "observed_current_sha256": None,
             "restore_source_sha256": plan["sectors"][0]["before_sha256"],
             "archive_ref": plan["archive_refs"][0]}, rom_recovery_verified=True)

    # A genuine mixed erase readback can start restoration.
    journal = append_event(
        journal, plan, "erase_readback",
        {"sector_index": 0, "observed_sha256": "e" * 64,
         "observed_length": SECTOR_BYTES}, rom_recovery_verified=True)
    journal = append_event(
        journal, plan, "restore_started",
        {"sector_index": 0, "observed_current_sha256": "e" * 64,
         "restore_source_sha256": plan["sectors"][0]["before_sha256"],
         "archive_ref": plan["archive_refs"][0]}, rom_recovery_verified=True)
    journal = append_event(journal, plan, "restore_ack_uncertain",
                           {"sector_index": 0}, rom_recovery_verified=True)
    with pytest.raises(ValueError, match="No sector action"):
        append_event(
            journal, plan, "erase_readback",
            {"sector_index": 0, "observed_sha256": "f" * 64,
             "observed_length": SECTOR_BYTES}, rom_recovery_verified=True)
    with pytest.raises(ValueError, match="inspected uncertain"):
        append_event(
            journal, plan, "restore_started",
            {"sector_index": 0, "observed_current_sha256": "e" * 64,
             "restore_source_sha256": plan["sectors"][0]["before_sha256"],
             "archive_ref": plan["archive_refs"][0]}, rom_recovery_verified=True)

    journal = append_event(
        journal, plan, "restore_readback",
        {"sector_index": 0, "observed_sha256": "f" * 64,
         "observed_length": SECTOR_BYTES}, rom_recovery_verified=True)
    with pytest.raises(ValueError, match="No sector action"):
        append_event(
            journal, plan, "erase_readback",
            {"sector_index": 0, "observed_sha256": "f" * 64,
             "observed_length": SECTOR_BYTES}, rom_recovery_verified=True)
    journal = append_event(
        journal, plan, "restore_started",
        {"sector_index": 0, "observed_current_sha256": "f" * 64,
         "restore_source_sha256": plan["sectors"][0]["before_sha256"],
         "archive_ref": plan["archive_refs"][1]}, rom_recovery_verified=True)
    assert journal_state(journal, plan)["status"] == "stop_and_reenter_rom_to_inspect"


def test_plan_rejects_forged_erased_digest_and_trailer_flag():
    from first_format_recovery_model import _canonical

    _, original = fixture()
    for mutate in (
            lambda plan: plan["sectors"][0].update(erased_sha256="0" * 64),
            lambda plan: plan["sectors"][0].update(trailer_before_is_ff=True)):
        plan = copy.deepcopy(original)
        mutate(plan)
        body = dict(plan)
        body.pop("plan_sha256")
        plan["plan_sha256"] = sha256(_canonical(body))
        with pytest.raises(ValueError, match="Erased-sector|Trailer"):
            new_journal(plan)

def test_semantic_replay_rejects_rehashed_missing_and_cross_operation_reads():
    from first_format_recovery_model import _canonical

    _, plan = fixture()

    def forge(journal, event, data, *, rom=True):
        entry = {"seq": len(journal["events"]), "event": event, "data": data,
                 "rom_recovery_verified": rom,
                 "previous_sha256": journal["events"][-1]["event_sha256"]}
        entry["event_sha256"] = sha256(_canonical(entry))
        result = copy.deepcopy(journal)
        result["events"].append(entry)
        return result

    journal = start(new_journal(plan), plan, 0)
    journal = append_event(journal, plan, "erase_ack_uncertain",
                           {"sector_index": 0})
    forged_missing_read = forge(
        journal, "restore_started",
        {"sector_index": 0, "observed_current_sha256": None,
         "restore_source_sha256": plan["sectors"][0]["before_sha256"],
         "archive_ref": plan["archive_refs"][0]})
    with pytest.raises(ValueError, match="chain"):
        journal_state(forged_missing_read, plan)

    journal = readback(journal, plan, 0, "e" * 64)
    journal = append_event(
        journal, plan, "restore_started",
        {"sector_index": 0, "observed_current_sha256": "e" * 64,
         "restore_source_sha256": plan["sectors"][0]["before_sha256"],
         "archive_ref": plan["archive_refs"][0]}, rom_recovery_verified=True)
    journal = append_event(
        journal, plan, "restore_ack_uncertain", {"sector_index": 0},
        rom_recovery_verified=True)
    forged_erase_read = forge(
        journal, "erase_readback",
        {"sector_index": 0, "observed_sha256": "f" * 64,
         "observed_length": SECTOR_BYTES})
    with pytest.raises(ValueError, match="chain"):
        journal_state(forged_erase_read, plan)


def test_plan_rejects_wrong_schema_and_non_list_sector_map():
    from first_format_recovery_model import _canonical

    _, original = fixture()
    for mutate in (lambda plan: plan.update(schema=2),
                   lambda plan: plan.update(schema=True),
                   lambda plan: plan.update(sectors=None)):
        plan = copy.deepcopy(original)
        mutate(plan)
        body = dict(plan)
        body.pop("plan_sha256")
        plan["plan_sha256"] = sha256(_canonical(body))
        with pytest.raises(ValueError, match="Recognized|Exact reviewed"):
            new_journal(plan)
