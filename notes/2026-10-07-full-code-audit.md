# Full code audit — 2026-10-07

Status: **in progress; no completion claim yet**. Device firmware implementation remains paused pending this audit and review.

## Scope and pinned source variants

- Baseline worktree commit: `d7111a985d5d6262767d6af49ba26caf0e1b9453`.
- Fetched `origin/main`: `64209e3c08222ada0eb61afcaef89e909ae07955`.
- Fetched editor feature head: `861b725bbe4efadb2d56400853a03b78f695f4cf`.
- The audit branch contains a post-main 16-file hardware-recovery/provenance delta. Review those files as present without executing device tools.
- The editor branch is a separate source variant. Review its diff and complete modified-file context; do not merge it into this branch.
- File-by-file progress is recorded in [the coverage ledger](2026-10-07-full-code-audit-coverage.md): 726 source/build files are tracked there (501 first-party, 225 vendored; 178,989 and 81,114 physical lines respectively). The separately pinned editor delta contains 36 source/build paths. No generated firmware or hardware command is authorized by this audit task.

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

### Batch 3 — JieLi compile, link and package gates

Read the complete ELF link gate, package guard, compile-check and in-container scripts, object manifest, size probes, SDK sparse list, analyzer, and the synthetic ELF/package tests. No SDK checkout, device command, or build was run.

#### Findings

1. **[P2] The reserved IRQ-123 source gate is bypassable through a named constant. [verified]** `tools/jieli/audit_link.py:103-109,466-476` checks each source line with a regex that recognizes only a numeric literal (optionally one cast). For `#define APP_IRQ 123` followed by `request_irq(APP_IRQ, ...)`, neither line matches. The ELF immediate scan checks the IRQ vector address, not the small IRQ number passed to `request_irq`; thus the compile-time guard can report clean while future app code claims SDK-reserved IRQ 123. Existing tracked code has no `request_irq` call. The current tests (`tests/test_audit_link.py:455-459`) cover literals/casts only, not macro expansion. Fix or explicitly constrain this before relying on the gate for a firmware build.

2. **[P2] The compile-check command can return success after engine objects fail to compile. [verified]** `tools/jieli/in-container.sh:105-110` records and prints per-profile failure counts, while `tools/jieli/analyze.py:273-285` records failed objects in the report. The script never turns those failures into a nonzero result; its final exit gate at `in-container.sh:212-215` only considers the boot bridge and `audit_link.py`. Since `analyze.py` also exits normally after writing its report, an object failure can leave `compile-check.sh` green with failure rows in `report.md`. The compile check must not be treated as a pass unless its caller inspects every profile failure.

3. **[P3] Compile records can say clean when staged build inputs are dirty. [verified]** `tools/jieli/compile-check.sh:172-174` stages `engines`, all of `sim/web`, `firmware` and `tools/jieli`, but line 184 counts worktree changes only under `engines`, `sim/web/src` and `tools/jieli`. An uncommitted edit in `firmware/third_party/fm1-nes/boot_compat.c` or `sim/web/mk/sim.mk` is staged and compiled while `record.json` can claim `uncommitted_files: 0`. Expand the recorded dirty scope to the staged build inputs or record a content diff/hash.

The compile-only and link gates are not yet equivalent to an accepted firmware link: `in-container.sh` states that late-initcall layout and the exact `sdk_meky_check` machine code remain pending until a real link. The report also confirms no package build or chip run is part of this script. Those limits are documented and remain device-readiness gates, not new defects.

No source edits were made. Targeted tests remain unavailable because pytest is not installed in this environment; a small direct regex check confirmed the alias bypass (`literal matches: True`, macro alias matches: False).

### Batch 4 — State codecs, app loader and desktop renderer

Read the complete `tools/lunar_state.py` implementation (2,623 lines), C codec core (`fm1_json.c/.h`, `fm1_num.c/.h`, `fm1_state.h`, `fm1_state_mod.h`, `fm1_deflate.c/.h`, `state_bin.c`, `state_json_read.c`, `state_json_write.c`, `state_mod.c`, `state_movy1.c/.h`, `state_names.c`, `state_print.c`, `state_registry.c`, `fm1_known.c`), `sim/web/src/fm1_app_state.c/.h`, `engines/host/render_state.cc/.h`, and `tests/test_app_state.py`. The state codec test suite was reviewed at interoperability, truncation/bit-flip, deflate, schema and launch-link boundaries; app-load tests include round-trip, “load without” for unknown engines, RAM/rate and refusal atomicity, but no unknown MFX with ON coverage. They could not be executed because pytest and generated engine tools are unavailable. A direct Python reproduction used tracked `engines/state/examples/metadata.json` and `first-orbit.lunar`.

#### Findings

**[P3] Link DEFLATE checks accept truncation and trailing data. [verified]** Python `tools/lunar_state.py:1642-1659` verifies `eof` for container chunks but not `unused_data`; its link reader at `:2510-2521` verifies neither `eof` nor unused/unconsumed input. C `engines/state/fm1_deflate.c:235-252,288-291` accepts when the expected output length is reached without requiring stream completion or rejecting unused input; `engines/state/state_bin.c:1316-1319` relies on that helper. Direct reproduction with the tracked `first-orbit.lunar` link and `metadata.json` accepted input with the final 1 or 2 compressed bytes removed, plus an appended byte or 100 zero bytes. This allows incomplete or noncanonical compressed metadata/link data to be treated as valid; no memory-safety consequence was demonstrated. Confidence high; severity P3.

**[P3] Binary state chunks accept duplicate fields and parameter UIDs. [verified]** `engines/state/state_bin.c:655-667` (`kv_each`) does not track keys; known-key handlers such as `proj_kv`, `level_kv`, `view_kv` and `setg_kv` therefore accept duplicates. `read_unit` (`:875-892`) validates UID range/type but does not reject a repeated `(uid, focus)` pair. The binary reader emits both records and the importer applies them in order, so the later value wins. JSON rejects duplicate object keys, and its parameter reader refuses repeated resolutions to the same parameter. A deliberately constructed binary state with internally consistent CRCs reaches this path. It produces ambiguous malformed-file acceptance, without a demonstrated unsafe memory effect. The existing bit-flip tests do not cover it. Confidence high; severity P3.

**[P3] Unknown MFX loads can mutate the old effect and misreport RAM. [verified]** For `FM1_APP_LOAD_WITHOUT`, `plan_pass1` (`sim/web/src/fm1_app_state.c:876-886`) records the unknown MFX as given with a null engine. `plan_finish` (`:1102-1110`) then budgets the target sound as default arp/off. During pass 2, `apply_unit` skips an unknown effect (`:1399-1406`), but the following PARAM and ON records still run: `apply_param` resolves parameter UIDs against the effect currently in the slot (`:1375-1380`), and ON unconditionally calls `fm1_app_arp_set_on` (`:1425-1428`). These APIs operate on the current slot effect (`sim/web/src/fm1_app.c:2418-2441,2485-2499`). Thus importing a sound with an unknown MFX into a sound whose existing MFX uses a matching UID can silently change that old effect's parameter or bypass state, while the load report budgets the slot as default arp/off. An enabled old effect may remain enabled while the report says off; the dynamic toggle has its own RAM guard, so no RAM overflow is demonstrated. The normal call sites use stable memory-backed input (`sim/web/src/fm1_web.c:324-337`; `sim/web/test/fm1_sim_render.c:241-255`), so this is not a changing-source race. `tests/test_app_state.py:249-257` tests only an unknown sound engine, leaving this case uncovered. Confidence high; severity P3.

The browser `DecompressionStream` and full browser/worker path, app simulator checks, `fm1_meta.c`, fuzz driver, schemas and corpus remain pending. No source code changed; this batch only records audit evidence.

### Batch 5 — browser state/file persistence boundary (partial)

Read the complete `sim/web/www/files.js`, `sim/web/www/shadow.worker.js`, the static page checks in `tests/test_sim_files.py`, and the worklet state-load/save implementation and C bridge around those APIs. The audio worklet accepts only the binary magic and caps the input to its fixed text buffer; JSON parse/pack and preflight remain in the shadow Worker. The full worklet/event lifecycle, browser interaction test, editor consumers and native simulator callers are still pending.

**[P2] Failed IndexedDB writes can be reported as durable saves while the item disappears from the library. [verified]** `idb()` returns `null` on transaction errors but leaves the opened database marked usable (`sim/web/www/files.js:327-343`). `store.put()` interprets that as a reason to save only in the in-memory map (`:354-361`), but `store.all()` returns the database result without adding those memory-only rows (`:363-365`). If a save transaction fails, for example after storage quota exhaustion, `store.available()` has already succeeded; `savePressed()` therefore gets a successful memory fallback and shows “Saved … in this browser” because `f.memoryOnly` is false (`:655-669`). The saved item is absent from the library, and reload loses it. `tests/test_sim_files.py` checks static path and message boundaries, not transaction-error fallback. Confidence high; severity P2 due to a false persistence confirmation and data loss on reload.
