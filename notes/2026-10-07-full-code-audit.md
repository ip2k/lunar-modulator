# Full code audit — 2026-10-07

Status: **in progress; no completion claim yet**. Device firmware implementation remains paused pending this audit and review.

## Scope and pinned source variants

- Baseline worktree commit: `d7111a985d5d6262767d6af49ba26caf0e1b9453`.
- Fetched `origin/main`: `64209e3c08222ada0eb61afcaef89e909ae07955`.
- Fetched editor feature head: `861b725bbe4efadb2d56400853a03b78f695f4cf`.
- The audit branch contains a post-main 16-file hardware-recovery/provenance delta. Review those files as present without executing device tools.
- The editor branch is a separate source variant. Review its diff and complete modified-file context; do not merge it into this branch.
- File-by-file progress is recorded in [the coverage ledger](2026-10-07-full-code-audit-coverage.md). No generated firmware or hardware command is authorized by this audit task.

## Method

Read all first-party tracked source and build files in batches; review call graphs, resource ownership/lifetime, concurrency, input validation, integer bounds, build/link and runtime boundaries, test coverage, tool safety, vendored integration/provenance/licensing, generated artifacts, obsolete paths, and dead-code/refactor candidates. Review vendored bulk by explicit tier and document every exclusion. Search results and earlier cleanup candidates are leads only, not audit evidence. Findings require file/line, reachable scenario, evidence, severity, and confidence; distinguish confirmed defects from hypotheses and optional refactors.

## Progress and findings

### Batch 1 — soft-key probe and UBOOT dump/restore tools

Read the complete post-main implementations and tests for `tools/fm1_softkey_probe.py`, `tools/fm1_uboot_read.py`, `tools/fm1_uboot_restore_test.py`, and their three tests. No hardware command was executed. The allowlists are phase-bound: MIDI output accepts only the identity and vetted soft key; ROM upload requires the pinned loader hash and exact RAM span; the dump path permits only inquiry, RAM upload/jump, loader status/type queries and bounded 256-byte reads; restore adds only the fixed 4 KiB sector/pattern. The restore tool verifies two matching current dumps, sector blankness before programming, readback, erase-to-FF and a whole-flash post-restore hash. Test bodies match those intended boundaries, including partial-program cleanup. These are code review observations, not a claim that the tests were executed.

Potential guard limitation for further analysis: `tools/fm1_uboot_read.py:164-178` treats the caller-provided JSONL entry log as evidence of the prior FM-1_092 identity/UBOOT transition, then binds the live SCSI device only by sysfs path and current `devnum`. The live loader also checks WL82/UBOOT1.00 and JEDEC, and this tool only reads flash, so this is not currently a confirmed device-write hazard. Determine whether stale/replayed log acceptance materially undermines the intended wrong-unit prevention before classifying it; do not treat caller-editable logs as independent proof.

No defect is confirmed in this batch. Targeted tests were attempted with `python3 -m pytest -q tests/test_softkey_probe.py tests/test_uboot_read.py tests/test_uboot_restore.py`; they could not start because `pytest` is not installed (`python` is also not on PATH, and this worktree has no `.venv`). No source edits were made. No test pass is claimed.

### Batch 2 — USB_KEY dongle, ROM model, boot bridge and identity tools

Read the complete RP2040 firmware/PIO programs and config, all five simulator modules, their end-to-end/model/waveform tests, the FM-1 boot-info bridge plus host contract test, and both read-only identity clients. The simulator derives PIO waveforms from the actual PIO source, then couples them to a behavioral ROM model; the model explicitly says its AC791N behavior is reported from other JieLi families and has not been observed on an AC791N (`dongle/sim/jieli_rom.py:1-5`). The tests establish agreement with that model and PIO emulator, not hardware compatibility. Keep successful on-device dongle entry as an explicit readiness gate.

**Optional cleanup, [P4], [verified]:** `dongle/firmware/main.c:163-165` increments `samples` through the SOF phase but never reads it. It has no runtime effect; remove the variable and increment during a dongle cleanup if the owner wants to keep compiler warnings clean. No broad cleanup was made.

No other confirmed defect in this batch. `firmware/third_party/fm1-nes/boot_compat.c` is the only included upstream source file in this group; its declared Apache-2.0 origin and delta are documented in `firmware/third_party/fm1-nes/UPSTREAM.md`. Host tests are present but could not run because pytest is missing. No hardware action or source edit occurred.

Audit batches and findings will be appended here with the ledger updated in the same checkpoint.
