# First-format recovery campaign model

Date: 2026-10-14. Branch `codex/2026-10-14-first-format-recovery-model`.

[verified] `tools/native/first_format_recovery_model.py` adds a pure offline plan and append-only journal for the proposed 24-sector storage48 map. It accepts two matching full 1 MiB snapshots with an explicit SHA-256 and caller-asserted current identity, two private archive references, payload at most 43,130 bytes, and all 24 reserved 256-byte trailer pages already erased. It binds the fixed map, per-sector baselines, protected complement extents, payload bound, and false physical/admission flags into a canonical digest. It does not produce device commands or perform I/O.

[verified] The journal records ROM-operator-attested before/readback observations, lost acknowledgements, and reverse-order rollback checkpoints. It requires full 4 KiB readback before advancing; exact baseline bytes permit retry after an unacknowledged erase; exact erased bytes advance; a mixed/unknown sector halts with `stop_and_reenter_rom_to_inspect`. Rollback checkpoints likewise require exact baseline readback. Journal hashes are tamper-evident consistency checks, not signatures or proof that reported observations are true.

[verified] Checks ran in `lunar-preload-tests:20261014` (image SHA `1e6a3bc97b299a40f572ab38972a114e2f9ab0f4daaf96e2ae970f488ac34313`), with 2 CPUs, 3 GiB memory/swap, 256 pids, network disabled, and `docker-batch.slice`; pytest dependencies were mounted read-only from the existing wave-receipt-validation venv. Command: `/usr/bin/python3 -m pytest -p no:cacheprovider -q tests/test_native_first_format_recovery_model.py tests/test_native_tail_migration_plan.py`; result: 25 passed.

[inferred] This model helps review a ROM-held campaign but cannot establish paired-snapshot provenance, archive durability, ROM entry, device identity, flash behavior, semantic migration, rollback, or recovery. In particular it assumes the candidate trailer pages were already erased before first formatting; unknown stock sectors with non-FF pages remain outside this plan. Mixed readback deliberately stops for an externally supervised ROM recovery decision. No device commands were run.

Status: implementation checkpoint paused at coordinator request to prioritize the separate device-42 fresh read/repeat-boot adapter. Resume from this branch and worktree; do not treat the offline model as authorization or a physical result.
