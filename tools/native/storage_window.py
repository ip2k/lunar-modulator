# SPDX-License-Identifier: MIT
"""Offline geometry proof for an initially erased native settings journal.

This is not proof of region ownership, semantic migration, or installation
permission. Re-run against a fresh matching backup pair before hardware use.
"""
from storage_backup import digest, expected_digest, inspect_reservations, prepare

SECTOR = 0x1000
WINDOW_BYTES = 2 * SECTOR
GAP_START = 0xFC000
GAP_END = 0xFF000


def plan(a, b, candidate, profile, baseline_sha256, candidate_sha256, start):
    """Bind preservation and erased-window checks to complete pinned images."""
    prepare(a, b, profile, baseline_sha256)
    expected_digest(candidate_sha256)
    if not isinstance(candidate, bytes) or digest(candidate) != candidate_sha256:
        raise ValueError('Complete candidate bound to retained digest required')
    banks = inspect_reservations(candidate, profile)
    if type(start) is not int or start % SECTOR or not GAP_START <= start <= GAP_END-WINDOW_BYTES:
        raise ValueError('Two aligned sectors wholly inside the globals gap required')
    if a[:0x4000] != candidate[:0x4000]:
        raise ValueError('Stock SPL and top-level configuration changed')
    for name, (off, n) in banks.items():
        if a[off:off+n] != candidate[off:off+n]:
            raise ValueError('Protected storage or globals gap changed: '+name)
    if a[GAP_END:] != candidate[GAP_END:]:
        raise ValueError('Device key sector changed')
    if a[start:start+WINDOW_BYTES] != b'\xff'*WINDOW_BYTES:
        raise ValueError('Journal window contains existing data')
    return dict(schema=1, kind='fm1-native-settings-window-geometry',
                baseline_sha256=baseline_sha256, candidate_sha256=candidate_sha256,
                profile=profile, start=start, bytes=WINDOW_BYTES, sector_bytes=SECTOR,
                window_sha256=digest(a[start:start+WINDOW_BYTES]),
                geometry_verified=True, initially_erased=True,
                protected_storage_preserved=True, ownership_verified=False,
                backup_provenance_verified=False, semantic_migration_verified=False,
                physical_rollback_verified=False, hardware_admitted=False,
                hardware_operations=0)


def verify(receipt, a, b, candidate, profile, baseline_sha256, candidate_sha256, start):
    """External pins and requested geometry prevent a receipt blessing itself."""
    checked = plan(a, b, candidate, profile, baseline_sha256, candidate_sha256, start)
    if receipt != checked:
        raise ValueError('Window receipt differs from independently reconstructed proof')
    return checked
