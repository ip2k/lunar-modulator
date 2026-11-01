# ROM witness offline preparation — 2026-11-01

## File plan and bounded contract

Base: `b831724fcf413720aaa036dac742a382cdfaa93c`.
Branch: `feature/2026-11-01@rom-execution-witness`.
Worktree: `/Users/likwid/.codex/worktrees/lunar-rom-witness-20261101`.

Planned owned files:
- `firmware/rom-witness/witness.S`: independently authored MIT stackless primary-core-only PA2 finite optical signature.
- `firmware/rom-witness/witness.ld`: one RAM code section at `0x01c02000`, max 512 bytes, no writable sections.
- `firmware/rom-witness/README.md`: source provenance, exact limits, signature, pending admission gates.
- `tools/jieli/rom_witness.py`: offline build/audit/manifest only; no device imports or commands.
- `tests/test_rom_witness.py`: rejection tests for exact bytes, native listing/geometry, padding and immutable manifest.
- This note: evidence, checks, handoff and cleanup.

No hardware traffic, PR or merge. No changes to existing device/reset/installer/engine/simulator paths. Native compilation uses only the pinned compiler/linker/binutils (no SDK archive or firmware input). Build products stay in ignored `scratch/rom-witness-20261101/`; remote staging is uniquely `/home/likwid/datasets/lunar/rom-witness-20261101`, removed after results are retained. Preserve small logs/listing/manifest; never commit binary/toolchain. Mac initial free space: 1117 GiB [verified].

Candidate admission is false. PA2 physical role and exclusive cold-ROM ownership, clocks/watchdog/capture timing, ROM entry ABI/cache/exception behavior, strict transport completion and fresh identity/optical capture remain later coordinator gates. The signature is pulse order/relative loop width, not claimed milliseconds. A USB effect alone cannot establish execution.
