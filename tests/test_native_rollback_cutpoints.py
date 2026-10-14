from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "native"))
from rollback_cutpoints import Operation, enumerate_cutpoints


def test_header_commit_selects_stock_entry_but_never_claims_app_ready():
    points = enumerate_cutpoints(
        [Operation("restore-stock-body"), Operation("restore-stock-header",
                                                    app_header_valid_after=True),
         Operation("erase-stage-sector", recovery_record_valid_after=False)],
        initial_app_header_valid=False,
        initial_recovery_record_valid=True,
        initial_loader_payload_valid=True,
    )
    assert points[0].spl_route == "loader_record_scan_reachable"
    committed = next(point for point in points
                     if point.operation == "restore-stock-header" and point.phase == "after")
    assert committed.spl_route == "stock_xip_selected"
    assert committed.stock_app_ready == "unknown"
    after_stage_cut = points[-1]
    assert after_stage_cut.spl_route == "stock_xip_selected"
    assert after_stage_cut.stock_app_ready == "unknown"


def test_partial_sector_operation_is_unknown_not_atomic():
    points = enumerate_cutpoints(
        [Operation("erase-stage-sector", loader_payload_valid_after=False)],
        initial_app_header_valid=True,
        initial_recovery_record_valid=True,
        initial_loader_payload_valid=True,
    )
    during = points[1]
    assert during.phase == "during"
    assert during.recovery_record_valid is True
    assert during.loader_payload_valid is None
    assert during.spl_route == "stock_xip_selected"
    assert during.stock_app_ready == "unknown"


def test_invalid_app_and_missing_record_has_no_proven_entry():
    points = enumerate_cutpoints([], False, False, False)
    assert points[0].spl_route == "no_verified_spl_entry"
    assert points[0].stock_app_ready == "unknown"



def test_valid_record_without_complete_loader_has_no_verified_entry():
    points = enumerate_cutpoints([], False, True, False)
    assert points[0].spl_route == "no_verified_spl_entry"


def test_partial_loader_programming_does_not_count_as_rescue():
    points = enumerate_cutpoints(
        [Operation("program-rescue-loader", loader_payload_valid_after=True)],
        initial_app_header_valid=False,
        initial_recovery_record_valid=True,
        initial_loader_payload_valid=False,
    )
    during = points[1]
    complete = points[2]
    assert during.loader_payload_valid is None
    assert during.spl_route == "unknown"
    assert complete.spl_route == "loader_record_scan_reachable"


def test_keep_record_and_payload_until_invalid_app_header_is_restored():
    points = enumerate_cutpoints(
        [Operation("invalidate-app-header", app_header_valid_after=False),
         Operation("restore-app-body"),
         Operation("commit-app-header", app_header_valid_after=True),
         Operation("remove-rescue-record", recovery_record_valid_after=False),
         Operation("remove-rescue-payload", loader_payload_valid_after=False)],
        initial_app_header_valid=True,
        initial_recovery_record_valid=True,
        initial_loader_payload_valid=True,
    )
    invalid_header = [point for point in points
                      if point.app_header_valid is False]
    assert invalid_header
    assert all(point.recovery_record_valid is True
               and point.loader_payload_valid is True
               and point.spl_route == "loader_record_scan_reachable"
               for point in invalid_header)
    assert points[-1].spl_route == "stock_xip_selected"
    assert points[-1].stock_app_ready == "unknown"


def test_removing_payload_before_record_breaks_rescue_invariant():
    points = enumerate_cutpoints(
        [Operation("invalidate-app-header", app_header_valid_after=False),
         Operation("erase-rescue-payload", loader_payload_valid_after=False)],
        initial_app_header_valid=True,
        initial_recovery_record_valid=True,
        initial_loader_payload_valid=True,
    )
    assert points[-1].recovery_record_valid is True
    assert points[-1].loader_payload_valid is False
    assert points[-1].spl_route == "no_verified_spl_entry"
