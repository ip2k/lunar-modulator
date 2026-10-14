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
        [Operation("erase-stage-sector", recovery_record_valid_after=False)],
        initial_app_header_valid=True,
        initial_recovery_record_valid=True,
    )
    during = points[1]
    assert during.phase == "during"
    assert during.spl_route == "unknown-during-mutation"
    assert during.stock_app_ready == "unknown"


def test_invalid_app_and_missing_record_has_no_proven_entry():
    points = enumerate_cutpoints([], False, False)
    assert points[0].spl_route == "no_verified_spl_entry"
    assert points[0].stock_app_ready == "unknown"
