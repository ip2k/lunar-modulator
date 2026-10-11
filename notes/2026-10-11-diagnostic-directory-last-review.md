# Independent directory-last review

[verified: current source read] No actionable defect found in the new ordering path. The optional commit sector is an exact integer, aligned and present in validated sorted/disjoint ranges before any transaction directory is created. New plans seal both fields in the plan digest and journal; one missing field, an incorrect complete order, or journal disagreement fails during load. Legacy schema-1 plans with neither field still validate ranges/hash and use ascending order. Bound diagnostic load requires APP_BASE=0x4000 explicitly, which also ensures a legacy or null-commit plan cannot authorize its transport.

[verified: control flow] Install and restore re-read the entire actual array first, check immutable regions, and enforce equality with baseline for a prepared transaction. They then re-read every authorized sector in the sealed order, repairing differing sectors from complete desired bytes. A prior journal progress claim cannot skip a changed sector. Each noncommit sector is verified before the commit-sector iteration, and final complete-array equality is required even for a completed/no-op transaction. Durable intent still precedes each erase/program and the bound adapter rechecks direction, exact address/payload, files and binding at mutation.

[verified: tests inspected, not executed here] Added tests exercise all requested bad types/alignment/range, plan+journal sealing, both directions, eight interruption boundaries with deliberate damage to a previously verified sector, and default/legacy compatibility. Parent owns focused Hera execution.

[inferred: operational limit] Directory-last improves operation order; it provides neither atomic installation nor a bootable intermediate image. The final directory can already match desired bytes on resume, in which case it is freshly read and skipped after repair of earlier sectors. This is valid actual-state recovery, not proof the directory was first published only after all data across earlier failed attempts. Restoration preserves the same last-directory order. No hardware I/O, source changes, commit or push occurred in this review.

Follow-up: retain current fresh-readback/identity checks in the physical adapter; require parent focused tests to pass, then final SDK image and exact patched-loader reviews before a concrete bench action.

Source pins:
- `tools/fm1_flash_transaction.py`: `d0527efbe74314b30a2cd76897c022a1c7857db888ef6e8f8610dbb329956908`
- `tools/fm1_bound_diagnostic.py`: `25e57ffda466c898df88370069cf4d7fce02134e141ba95516347c30953d1a36`
- `tests/test_flash_transaction.py`: `528200a0455b90af509c3ae4a8b43a78ad52581eb5107f5d1d2abca6edfe0005`
- `tests/test_bound_diagnostic.py`: `4f9532d7bb450eaee30204c09a18b69c1e6afb9f1a507cab877e2e27f8ce354a`
- `notes/2026-10-11-diagnostic-directory-last.md`: `ece61ac9b118bf51c22b6b81da438912d46ccf2b5846252020f4f6fcb81d93bd`

Branch `feature/2026-10-11@installable-firmware`; review HEAD `bdbf2d397226e9dbc5711d411f916af6d00ab0da`. Parent owns commit/push state.
