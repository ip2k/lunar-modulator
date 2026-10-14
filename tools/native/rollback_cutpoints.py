"""Offline flash-restore prefix model; not a target writer or admission gate."""
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple


@dataclass(frozen=True)
class Operation:
    """One sector-scale mutation.

    None means the transaction has not proved the field either way. A cut during
    a mutation is always modeled as unknown, never as an atomic erase/program.
    """
    name: str
    app_header_valid_after: Optional[bool] = None
    recovery_record_valid_after: Optional[bool] = None


@dataclass(frozen=True)
class CutPoint:
    index: int
    operation: str
    phase: str
    app_header_valid: Optional[bool]
    recovery_record_valid: Optional[bool]
    spl_route: str
    stock_app_ready: str = "unknown"


def enumerate_cutpoints(operations: Iterable[Operation],
                        initial_app_header_valid: bool,
                        initial_recovery_record_valid: bool) -> Tuple[CutPoint, ...]:
    """Enumerate before/during/after operation states using verified SPL gates.

    "stock_xip_selected" only means the SPL selects the stock XIP entry based on
    the application header gate. It does not assert that application startup,
    storage initialization, MIDI, or recovery UI succeeds.
    """
    app_header = initial_app_header_valid
    record = initial_recovery_record_valid
    result = [CutPoint(0, "initial", "after", app_header, record,
                       _route(app_header, record))]
    for index, operation in enumerate(operations, 1):
        result.append(CutPoint(index, operation.name, "during", None, None,
                               "unknown-during-mutation"))
        if operation.app_header_valid_after is not None:
            app_header = operation.app_header_valid_after
        if operation.recovery_record_valid_after is not None:
            record = operation.recovery_record_valid_after
        result.append(CutPoint(index, operation.name, "after", app_header, record,
                               _route(app_header, record)))
    return tuple(result)


def _route(app_header: Optional[bool], record: Optional[bool]) -> str:
    if app_header is True:
        return "stock_xip_selected"
    if app_header is False and record is True:
        return "loader_record_scan_reachable"
    if app_header is False and record is False:
        return "no_verified_spl_entry"
    return "unknown"
