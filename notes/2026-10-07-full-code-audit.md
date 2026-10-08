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

Read the complete `sim/web/www/files.js`, `sim/web/www/shadow.worker.js`, `sim/web/www/worklet.js`, `sim/web/www/fm1-wasm.mjs`, `sim/web/src/fm1_web.c`, `sim/web/test/files.mjs`, `sim/web/test/serve.mjs`, `sim/web/test/origins.mjs`, `tests/test_sim_files.py`, and `tests/test_sim_origins.py`. The worklet accepts only the binary magic and caps state input to its fixed text buffer; JSON parse/pack and preflight remain in the shadow Worker. The pure origin test ran directly under Node and passed. The headless Chromium page test requires its configured Playwright container on aeon and was not run; pytest is not installed in this worktree. Editor consumers, native simulator callers and other simulator interactions remain pending.

**[P2] Failed IndexedDB writes can be reported as durable saves while the item disappears from the library. [verified]** `idb()` returns `null` on transaction errors but leaves the opened database marked usable (`sim/web/www/files.js:327-343`). `store.put()` interprets that as a reason to save only in the in-memory map (`:354-361`), but `store.all()` returns the database result without adding those memory-only rows (`:363-365`). If a save transaction fails, for example after storage quota exhaustion, `store.available()` has already succeeded; `savePressed()` therefore gets a successful memory fallback and shows “Saved … in this browser” because `f.memoryOnly` is false (`:655-669`). The saved item is absent from the library, and reload loses it. `tests/test_sim_files.py` checks static path and message boundaries, not transaction-error fallback. Confidence high; severity P2 due to a false persistence confirmation and data loss on reload.

**[P3] Test server's path-prefix check permits traversal into a similarly named sibling directory. [verified]** `sim/web/test/serve.mjs:26-38` decodes the request path, normalizes it, joins it to the served directory, then uses `file.startsWith(www)` for containment. A request for `../lunar-www-private/secret` from `/tmp/lunar-www` normalizes to `/tmp/lunar-www-private/secret`, which still passes that string-prefix check; a direct Node `path` reproduction confirmed the predicate is true. When a local test server is listening, a request can therefore read files from a sibling whose name begins with the served directory name. The helper binds to loopback and is used only by tests/screenshots; this does not affect the production page bundle. Confidence high; severity P3.

No additional confirmed defect was found in the reviewed state-transfer and browser-origin paths. `node sim/web/test/origins.mjs sim/web/www` passed (`{"pass":true,"fails":[]}`). The storage-error scenario and path-traversal request were verified from their control flow and Node path semantics; the browser files test was not run. The remainder of first-party simulator, engine, test, tool and vendored integration coverage is still pending.


### Batch 6 — simulator application core (complete file)

Read all 4,373 lines of `sim/web/src/fm1_app.c`, following app lifecycle, engine replacement and RAM accounting, modulation binding/release, note ownership across key/MIDI/sequencer/MIDI-FX paths, panel button/encoder state transitions, sequencer command buffering/import/reset, audio mix and insert/master FX rendering, screen draw geometry, and JSON catalogue generation. Cross-checked the engine and MIDI-FX constructors/setter contract where slot replacement handles creation. No additional confirmed defect emerged in this file; state-import behavior and browser persistence findings from earlier batches remain reported at their source boundaries. This source path and completion status are now in the coverage ledger. No source changes or runtime builds were made.


### Batch 7 — editor edit layer and telemetry core

Read the complete `sim/web/src/fm1_edit.c` (1,184 lines) and `fm1_edit.h` (243 lines), including packed record/verb codec, record application, ring generation/resync, modulation snapshot, telemetry mask/aggregation, view mapping, typed value parsing, and dump/hash. Confirmed the public wasm wrapper uses the packed edit path and text parser (`sim/web/src/fm1_web.c:446-462`); the shadow worker's typed parameter path uses the separate parameter parser. Input counts are bounded at 64 records, packed sizes derive from the fixed 24-byte record, and view validation is delegated to the app's checked show path. The app sets the editor source around public edits and performs modulation diff scans at the outermost scope. No additional confirmed defect was established in this batch; the possibility of silently ignoring typed-text tokens after `split()` reaches its 14-word cap remains a low-impact test/harness-only robustness observation and is not promoted as a finding without an actual product caller or test contract requiring rejection. No code was changed or executed.


### Batch 8 — application contract and TFT/layout primitives

Read all of `sim/web/src/fm1_app.h` (895 lines), `fm1_tft.h` (198 lines), and `fm1_tft.c` (254 lines). Cross-checked the app's fixed arenas, unit indexing, event/ring ownership declarations, public API contracts and advertised memory model against the implementation already reviewed. The TFT code clamps pixel writes to the frame buffer, bounds the glyph tables through compile-time metric checks, and records box geometry/truncation for layout checks. Its checker intentionally treats an opaque fill touching a logged box as hiding it; app overlay call sites reviewed so far use full opaque overlays or the banner-specific erase. No confirmed defect from these files. No source changes or builds were made.


### Batch 9 — screen constants and font provenance

Read `fm1_panel.h`, `fm1_look.h`, and the three generated font headers, plus the complete `sim/web/tools/gen_font.py` and the repository-owned `sim/web/tools/font5x9.txt` as parser input. Read Spleen's `UPSTREAM.md` and license, and the font provenance tests. `python3 sim/web/tools/gen_font.py --check` passed; `--sizes` returned MAIN 855, MID 1,330 and SMALL 1,140 bytes. Git blob hashes for both BDFs and their license match the upstream hashes recorded by the repository and checked in `tests/test_sim_fonts.py`. The BDF files are 22,535 and 10,453 lines: their full glyph data is not manually eyeballed; review is tiered to BDF parser validation, the product's printable ASCII subset, generated-header reproduction, hashes and license. The rest of the BDF glyph repertoire is recorded as excluded from manual visual review; no change to licensing claims. No code changed.


### Batch 10 — sequencer panel UI and gesture tests

Read all 2,258 lines of `sim/web/src/fm1_seq_ui.c`, all 636 lines of its public header, and all 1,053 lines of `tests/test_seq_ui.py`. Cross-checked the UI's command emitter, event-room behavior, transport updates, song/session snapshot invalidation, and app button/key/encoder/note call sites against `fm1_app.c` and the declarations in `fm1_app.h`. The header's no-padding span used by `fm1_seq_ui_sync` is guarded by a compile-time `offsetof` assertion (`fm1_seq_ui.c:853-854`); the member comparison covers the intended range through the byte before `song_gen`. Gesture tests cover S3-S8 panel commands, state size, replay parity, key/MIDI note lifetimes, locks, page state, and source traces from Movy. The module also identifies S9 scenario parity coverage; the linked scenario tests remain pending in the ledger.

No additional confirmed defect was established in this batch. The UI deliberately ignores the emitter's result and the app counts commands held or refused when event capacity is unavailable (`fm1_seq_ui.h:265-270`, `sim/web/src/fm1_seq_ui.c:164-181`, `sim/web/src/fm1_app.c:3404-3421`); this is the documented event-room policy, and this source review did not establish a concrete normal-capacity path that loses a user edit. The pure gesture tests were read but not run: their fixture imports require the native simulator/render tools and pytest, neither of which was built or available in this worktree. No source changes or hardware actions occurred.


The audit branch was at pushed commit `19f7842baa69019d047b80cb095eeb0d35bef4c5` before the batch 10 checkpoint; that note was committed as `c4ff6cce7b9c966d1b0b4edb2a50c143bcb8ab11` and remote-verified.


### Batch 11 — sequencer screens and Session/Song UI scenarios

Read all 972 lines of `sim/web/src/fm1_seq_view.c`, its 119-line header, and all 164 lines of `tests/test_seq_song_ui.py`. Followed the Track, Step, Set, Clip, Track, Session and Song render paths, text/value formatting, song band/list truncation, and their static geometry assertions. Cross-checked the Session and Song page inputs against the sequencer UI snapshot fields and their state tests. The screen source has compile-time fits for grid, track strip, scene grid, list, legend and lane layout; the bottom-bar labels are bounded with `snprintf`. The song-time formatter uses the correct 4-beat-bar duration for hundredths-of-BPM values; the test examples cover saved views, hand-built Song playback, cursor edits, join feedback, confirmation, scene keys and Session LEDs.

No additional confirmed defect was established in these files. The panel tests were read but not executed because their shared fixture requires native simulator/render binaries and pytest, neither built or available in this worktree. The `--screens` raster/layout sweep that supplies visual evidence remains pending; static geometry assertions are not recorded as a rendered visual check. No source changes or device actions occurred.
