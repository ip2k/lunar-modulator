# Proposed storage48 scatter-map host checks — 2026-10-14

[verified] `tests/native/storage48_scatter.c` runs the candidate geometry from
`2026-10-14-storage48-migration-plan.md` through the existing extent adapter and
the real project journal in an in-memory NOR model. Four physical extents form
two logical 49,152-byte slots. Slot A spans three extents; slot B occupies the
fourth. No production address table, physical IO binding or admission changed.

[verified] Crossing checks compare bytes on both sides of all three extent
boundaries, including the logical slot boundary. The backend enforces the
256-byte NOR page limit. Replacement sweeps interrupt every erase/program
mutation for each destination slot, applying a partial mutation before returning
an error. Old and new payloads differ. Scanning afterward must select the older
committed generation and recover its byte-exact old payload, even when slot A
is the interrupted discontiguous destination. All bytes outside the candidate
extents retain their initial sentinel, including OTA staging, BTIF and the
protected tail.

[verified] On the Mac, `build/installer-test-py313/bin/python -m pytest -q
tests/test_native_extent_io.py` passes both the existing and new harness with
AddressSanitizer and UndefinedBehaviorSanitizer enabled. This is host-model
evidence only. Real NOR behavior, sector ownership, stock SPL trailer collisions,
watchdog safety, migration and physical rollback remain separate unresolved
gates. The map is not admitted for any hardware write.
