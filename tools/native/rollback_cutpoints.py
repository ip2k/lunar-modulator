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
    loader_payload_valid_after: Optional[bool] = None


@dataclass(frozen=True)
class CutPoint:
    index: int
    operation: str
    phase: str
    app_header_valid: Optional[bool]
    recovery_record_valid: Optional[bool]
    loader_payload_valid: Optional[bool]
    spl_route: str
    stock_app_ready: str = "unknown"


def enumerate_cutpoints(operations: Iterable[Operation],
                        initial_app_header_valid: bool,
                        initial_recovery_record_valid: bool,
                        initial_loader_payload_valid: bool = False) -> Tuple[CutPoint, ...]:
    """Enumerate before/during/after operation states using verified SPL gates.

    "stock_xip_selected" only means the SPL selects the stock XIP entry based on
    the application header gate. It does not assert that application startup,
    storage initialization, MIDI, or recovery UI succeeds.

    A rescue route requires both a valid record and its complete referenced
    loader/header. During a mutation, only predicates touched by that operation
    become unknown; untouched extents retain their prior state.
    """
    app_header = initial_app_header_valid
    record = initial_recovery_record_valid
    payload = initial_loader_payload_valid
    result = [CutPoint(0, "initial", "after", app_header, record, payload,
                       _route(app_header, record, payload))]
    for index, operation in enumerate(operations, 1):
        app_during = None if operation.app_header_valid_after is not None else app_header
        record_during = (None if operation.recovery_record_valid_after is not None
                         else record)
        payload_during = (None if operation.loader_payload_valid_after is not None
                          else payload)
        result.append(CutPoint(index, operation.name, "during", app_during,
                               record_during, payload_during,
                               _route(app_during, record_during, payload_during)))
        if operation.app_header_valid_after is not None:
            app_header = operation.app_header_valid_after
        if operation.recovery_record_valid_after is not None:
            record = operation.recovery_record_valid_after
        if operation.loader_payload_valid_after is not None:
            payload = operation.loader_payload_valid_after
        result.append(CutPoint(index, operation.name, "after", app_header, record,
                               payload, _route(app_header, record, payload)))
    return tuple(result)


def _route(app_header: Optional[bool], record: Optional[bool],
           payload: Optional[bool]) -> str:
    if app_header is True:
        return "stock_xip_selected"
    if app_header is False and record is True and payload is True:
        return "loader_record_scan_reachable"
    if app_header is False and (record is False or payload is False):
        return "no_verified_spl_entry"
    return "unknown"
