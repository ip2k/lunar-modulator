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


### Batch 12 — modulation UI, screen layout and destination-list tests

Read all 1,694 lines of `sim/web/src/fm1_mod_ui.c`, its 348-line header, all 388 lines of `sim/web/src/fm1_mod_view.c`, its 65-line header, and all 247 lines of `tests/test_sim_lists.py`. Reviewed name compression, destination/source list construction, slot serialization and edits, module moves/kind changes, engine re-aiming, rack/matrix/chain interactions, per-voice refusal displays, parameter routes and raster geometry. Cross-checked the short-name code against `fm1_param_t`'s documented non-null abbreviation contract in `engines/include/fm1_engine.h:159-171` and the module initializers, including the input parameters that are valid destinations. The screen harness's exhaustive `unique_dests` sweep is a planned validation of those contracts, but it could not be executed without building the native tool.

No confirmed defect was established in this batch. Static geometry assertions cover the rack strip, rows, matrix, chain, and popup agreement; no rendered visual inspection was performed. `tests/test_sim_lists.py` was read but not run because pytest and the native simulator are unavailable in this worktree. No source changes or device actions occurred.


### Batch 13 — modulation core/planner and focused regression tests

Read all 1,880 lines of `engines/mod/mod_core.c` and all 614 lines of `engines/mod/mod_plan.c`, tracing the fixed-size runtime state, sink record packing, module create/destroy/move/rebind lifecycle, system and per-voice event windows, gate merging and overflow policy, parameter/sink writes, note/voice allocation and release, arena layout/replanning, graph SCC/topological ordering and refusal explanations. Reviewed the complete `tests/test_sim_mod.py` (576 lines), `tests/test_module_list.py` (247 lines), and `tests/test_sim_editor_meta.py` (123 lines) for their stated coverage and gaps. The module-list tests include native build/link checks, which were not run under the no-heavy-build constraint. The other tests require pytest/native simulator artifacts unavailable in this checkout. This is source review only; no build, device action or runtime test was performed.

No additional confirmed defect was established in the core or planner after cross-checking capacity bounds, slot/destination cardinalities, fixed-array indexes, delayed edge selection, voice replan offset restoration and the slot refusal walk. This does not substitute for the pending native core fuzz/voice regression tests, sanitizer runs, or hardware engine integration. A renderer/test invocation was intentionally avoided because it would require generating the native build artifacts; no pass is claimed.


### Batch 14 — modulation primitives and first-wave module kinds

Read the complete helper/bridge/registry and primitive implementation set: `engines/mod/mod_int.h`, `mod_glue.c`, `mod_registry.c`, `fm1_mp.h`, `mp_int.h`, `mp_rng.c`, `mp_clkdiv.c`, `mp_lfo.c`, `mp_env.c`, `mp_slew.c`, `mp_sah.c`, `mp_turing.c`, `mp_tool.c`, and the generated `mp_tables.c`. Read the full first-wave module implementations `kinds_int.h`, `mod_lfo.c`, `mod_env.c`, `mod_chance.c`, `mod_function.c`, `mod_bounce.c`, `mod_register.c`, `mod_coin.c`, `mod_divide.c`, and `mod_burst.c`, following frame/native-rate mapping, trigger and level gate carry, per-voice module registration, script parsing limits, clock queues and module state/data. Read `tests/test_engines_mod_voices.py` (305 lines) in full. Ran the three read-only generated-source consistency checks: `python3 engines/mod/gen_curves.py --check`, `gen_tables.py --check`, and `gen_mi_tables.py --check`; all exited successfully. `tests/test_engines_mod.py` is only partially read so far and no primitive/module tests were executed.

**Optional dead-code candidate, [P4], [verified]:** `engines/mod/kinds/mod_register.c:61,75,95,109` stores the CLOCK input level in `reg_t.clock`, but no code reads the field. Removing that field and its assignments is a safe size/code cleanup candidate; no source change was made.

No additional confirmed runtime defect was established in the reviewed primitives and first-wave kinds. Generated-table consistency is verified, but behavior checks remain source-only; test/build availability and device integration limitations above still apply.

### Batch 15 — remaining modulation kinds and comparator transition semantics

Read the complete remaining kind implementations `mod_slew.c`, `mod_quantize.c`, `mod_compare.c`, `mod_logic.c`, `mod_calc.c`, `mod_mix.c`, and `mod_resonator.c`, plus the complete Mutable-derived integration layer `mod_mi.c/.h`. Also read all 629 lines of `tests/test_engines_mod.py`, all 405 lines of `tests/test_engines_mod_kinds.py`, and the comparator section of `engines/test/mod_kinds_test.c` (the remainder of that 1,332-line C harness is not yet reviewed). The Python tests define golden traces, cross-block render parity, any-fill determinism, module chaining, feedback, and a sample-accurate GATE/RISE/FALL comparator loop. The native compare test checks GATE, NOT, RISE/FALL, ABOVE and BELOW in ramps/window/trend modes, but does not assert MID transition edges for a multi-zone jump.

**[P3] Compare MID drops its pulse when one tick crosses the whole middle zone. [verified by source control flow; runtime reproduction pending]** `engines/mod/kinds/mod_compare.c:143-164` advances one `zone` per tick: an input starting above `+Width + Hyst/2` and ending below `-Width - Hyst/2` first drops ABOVE and moves its local zone to MID (`:144-146`), then raises BELOW and moves directly to BELOW (`:154-156`). The final MID update compares only the final zone with the stored MID gate level (`:158`); because MID was low at both tick boundaries, it emits neither the intervening MID rise nor fall. The module contract at `:12-17` says the zone outputs are threshold bands and interpolates crossings along the straight line between tick samples, so the segment traverses MID and should produce a bounded pulse. This is reachable whenever the compared signal changes across both zone thresholds in one modulation tick; downstream gate consumers then miss that MID event. The Python golden `SCENES["compare"]` at `tests/test_engines_mod_kinds.py:134-136` does not exercise MID edges. The C compare test at `engines/test/mod_kinds_test.c:345-357` asserts MID's steady level during a gradual Window ramp, but it does not assert the edge pair for a single-tick sweep across both boundaries. Confidence high in the static defect; no native build or dynamic reproduction was available. No fix was made.

No other confirmed defect was established in the remaining kind source or the Mutable adapter. The rest of the C kind harness, modulation data/reference tests, runtime tests, and vendor-source tier remain pending. No engine build, firmware build or device action was performed.

### Batch 16 — modulation C regression and Python runtime suites

Read all 1,332 lines of `engines/test/mod_kinds_test.c`, all 397 lines of `engines/test/mod_mi_ref.cc`, all 126 lines of `tests/test_engines_mod_data.py`, and all 684 lines of `tests/test_engines_mod_runtime.py`. Traced the deterministic kind checks, fuzz input construction, memory-fill comparisons, limiter/reference checks, audio/tick parity, sink and source registries, parsed-script refusal paths, lock/revert behavior, gate cable edits, system gate frame mapping, synced LFO and seeded route RNG. The runtime tests are substantial and align with many stated MG1/MG2 contracts, though they do not remove the need for direct adversarial cases such as the Compare MID skipped-band edge pair recorded above.

No additional confirmed defect was established in these test harnesses or test descriptions during source review. Tests were not executed: this audit checkout lacks pytest and the native engine artifacts, and building them was intentionally avoided under the no-heavy-build constraint. `engines/test/mod_kinds_test.c` and the named Python files are now marked read in the coverage ledger; behavior remains unverified by those suites in this run.

### Batch 17 — simulator page and editor model/history/sheets

Read the complete baseline `sim/web/www/app.js` (1,109 lines), `index.html` (235), `editor/model.js` (722), `editor/history.js` (108), and `editor/sheets.js` (153). Traced page startup/power lifecycle, AudioContext and worklet setup, screen-buffer transfer, DX7 file handling, MIDI and panel input release, layout switching, packed edit records, metadata-derived controls, project mirror creation, matrix decoding, sheet focus/menu flow, and history grouping. A direct Node reproduction exercised the public `History.record` API; it did not require the unavailable browser test harness.

**[P2] Repeated “Make B from the picks” actions can merge history while keeping the first redo file and an intermediate undo snapshot. [verified by source and direct Node reproduction]** `sim/web/www/editor/history.js:49-55` merges same-target editor `how: 'set'` edits within 600 ms, then updates only `last.after` and `info.redo`. `sim/web/www/editor/project.js:496-498` uses the constant target `ab:${abId()}` and stores its redo payload under `info.reload` instead; immediately before that it calls `onStruct(entry, live)` (`project.js:495-498`), which replaces the merged entry's snapshot with the current pre-load project (`project.js:797-806`). `redoPicks` later reloads `e.info.reload` (`project.js:521-529`). Therefore, if a user makes two picks-based loads to the same scope within the merge interval after the first finishes, they occupy one history entry: undo restores the state before only the second load, while redo reloads the first selection's file. The entry's displayed `after` describes the second action, but its reload payload still describes the first. Direct Node reproduction with two same-target structural entries at t=0 and t=500 ms returned one shared entry with `after="three from A"` and `reload="first-selection"`. The UI disables the action while each asynchronous load is busy, but permits another click as soon as it completes; the 600 ms interval makes the repeat timing conditional on the load duration and user timing. Confidence high in stale redo data when that reachable timing occurs; severity P2 for incorrect undo/redo. The editor-unit suite does not exercise this repeated-picks case. No product fix was made.

`editor/model.js` and `editor/history.js` were reviewed in baseline form only; their editor-branch versions and callers remain separately pending. `style.css`, the remaining editor modules and project/cable flows remain pending. No browser or firmware build was run.


### Batch 18 — editor port, cable map, project flows and unit regression

Read all 1,348 lines of baseline `sim/web/www/editor/editor.js`, 1,253 lines of `chains.js`, 717 lines of `map.js`, and 850 lines of `project.js`; traced editor-port attach/detach and snapshot state, panel and editor change feed, structural and parameter history, metadata-derived controls, cable CRUD and preview, pointer/keyboard patch gestures, SVG routing/layout, file import/export and library, A/B loads/picks, search operators, and hash-checked undo fallback. The module source itself did not establish another confirmed finding in this pass; the picks-history interaction remains the concrete finding in batch 17. `project.js` is now full-file baseline coverage, so batch 17's “remaining project flows” status is superseded.

Ran `node sim/web/test/editor-unit.mjs sim/web/www` against the checked-in WASM artifact. It passed all checks: 360 metadata parameters; packed records and change-feed parity; value history (115 steps) and structural history (17 steps); refusal invariance; source/destination metadata; and RAM accounting. This verifies the unit harness at this pinned snapshot, not browser interaction or firmware behavior. The Playwright package expected at `/pw` is unavailable (`MODULE_NOT_FOUND`), so the browser suites could not be run in this environment. No source fixes or device actions occurred.

Baseline editor coverage is complete for `editor.js`, `chains.js`, `map.js`, `project.js`, `model.js`, `history.js`, and `sheets.js`. `editor.css` and all separately required editor-branch source variants remain pending. The wider simulator, test, tool, engine, firmware and vendor audit remains in progress.

### Batch 19 — editor feature-branch styles, file boundary and search batches

Reviewed the feature-branch `editor.css` (836 lines), `files.js` (1,244), `shadow.worker.js` (340), `editor/model.js` (722), and `editor/sheets.js` (153) in complete branch form; `chains.js` (1,253), `map.js` (820), and `project.js` (947) were read completely in the preceding editor batches. Also read the changed-file diffs and the relevant search-batch portion of `editor-v1.mjs`. The files/storage layer now forwards `FLAG_RESTORE_SOUND` for explicit sound restoration, the Worker separates request ids from parameter module ids, the stylesheet includes the Map, sheets, and batch search layouts, and the model removes its unused `defaultValue` export. CSS was source-reviewed only; no browser screenshots/visual audit were possible because the configured Playwright environment is unavailable.

**[P2] Search cable batches can act on a replacement cable under the stale search label. [verified by source control flow; runtime reproduction pending]** `sim/web/www/editor/project.js:671-684,714-741,808-815` captures cable slot indexes and labels when Search opens. `applyBatch()` then reads the current cable at that index and checks only that it is nonempty; it never compares it with the cable captured in the search item or records the generation from Search-open time. If the FM-1 panel changes that matrix slot while the modal remains open, the batch's displayed label and chosen action refer to the former cable but `packCable()` modifies/removes the replacement cable. This is reachable through independent physical panel input while the editor dialog remains open; editor change-feed processing updates the mirror while the Search item list remains a snapshot. The feature's browser tests cover batch enable/undo/redo and parameter batches (`sim/web/test/editor-v1.mjs:964-1009`) but not a slot replacement between open and apply. The current-generation check at `:672,703-704` only protects changes after the click starts and therefore does not cover the stale interval before click. Confidence high in the stale target path; P2 because a bulk action can modify a different cable than the one named and selected. No fix was made.

The branch's `restoreSound` flag forwarding and Worker reply correlation were checked against the corresponding C flag and worker handler diffs. The new audio detector/check and loopback scripts were read completely (16, 46 and 140 lines). Their detector uses a synthetic 440 Hz signal and checks silence, held blocks, phase skips, right-channel loss and absent output; the loopback additionally requires no refused edit/resync, complete replies, continued A/B transport and non-silent musical capture. The tests themselves were not run because their browser/PulseAudio setup is unavailable here. The CI change installs a null sink/monitor for each browser matrix leg and runs loopback in all three browsers; this remains unverified in this environment. The branch also deletes the pinned base's 233-line `notes/2026-10-07-sdk-runtime-evaluation.md` and bench note. This is recorded as branch drift only; neither licensing nor bench notes were edited in the audit worktree.

No additional confirmed defect was established in these source reads beyond the stale Search cable batch target. The source-fork-specific runtime tests, rendered UI checks, and remaining modified branch files are still pending.

### Batch 20 — engine API contracts and editor telemetry variant

Read the complete baseline API headers `fm1_comp.h`, `fm1_dx7.h`, `fm1_dynamics.h`, `fm1_engine_meta.h`, `fm1_fx_host.h`, `fm1_fx_idle.h`, `fm1_gate.h`, `fm1_known.h`, `fm1_math.h`, `fm1_midi_ev.h`, `fm1_mix_limiter.h`, `fm1_mod_host.h`, `fm1_refusal.h`, `fm1_state_caps.h`, and `fm1_tele.h`. Cross-checked declared pointer lifetimes, audio-task/thread ownership, fixed array sizes, numeric assumptions, event-source packing, pass-through and telemetry formulas. Also read the feature-branch complete `fm1_dynamics.h`, `fm1_tele.h`, and `squash.mk`: telemetry schema version correctly rises from 1 to 2 when the reduction row gains the gate field, and the Squash reference object renames the new symbol alongside its engine/gain symbols.

No additional confirmed defect was established from the contracts alone. Full engine implementations, the larger public headers, and their cross-component callers remain pending. No builds or hardware actions were performed.


### Batch 21 — sequencer, resampler and expanded engine contracts

Read the complete `engines/include/fm1_engine.h` (678 lines), `fm1_mod.h` (655), `fm1_resampler.h` (389, including all 769 kernel entries), `fm1_seq.h` (484), `fm1_seq_host.h` (377), `fm1_meta.h` (96), and `fm1_mfx_host.h` (217). Reviewed API version compatibility, task/lifetime contracts, static capacities, sequence transport/import interfaces, resampler rate and ring bounds, host dispatch ordering, MIDI effect queue sizes, metadata canonicalization/versioning, and caller-supplied memory contracts. The fixed-point resampler initialization rejects nonpositive/nonfinite/unsupported ratios before table indexes are used; its required-input lead and duplicated rings cover the advertised kernel radius. Runtime parity, boundary-rate and block-size tests remain pending with their implementation files and are not inferred from this header review.

No confirmed runtime defect was established from these declarations. One documentation inconsistency is visible in `fm1_mod.h`: `FM1_MOD_HOST_PARAMS` is six and the `fm1_mod_bind` documentation at line 399 says HOST takes two, while the shared sink comment at line 109 says four records are consumed by bind. This is a stale contract comment pending implementation cross-check, not a runtime finding. No source code changed; tests and builds were not run.


### Batch 22 — engine registry, metadata tables and modulation sink allocation

Read complete `engines/src/registry.cc` (178 lines), `engines/src/editor_meta.cc` (281), `engines/mod/mod_registry.c` (previously reviewed in batch 14), and the binding/allocation portion of `engines/mod/mod_core.c:130-237` against the public contract. Checked feature guards, GPL rows versus module registry, absent-module rows, group and page lookups, metadata table bounds, and sink record packing/rebinding. `fm1_mod_bind` seeds all six fixed HOST records at runtime (`mod_core.c:145-160`), so the public comment that HOST “takes two” at `fm1_mod.h:399` is stale and conflicts with the six-record constant and initialization. This is a documentation defect only; capacity allocation uses the correct six. Record it as optional P4 cleanup, confidence high. No other confirmed defect from these files. No code changed or build/test run.


### Batch 23 — sequencer storage, commands, Capture and host bridges

Read complete `engines/seq/seq_int.h` (381 lines), `seq_clip.c` (898), `seq_capture.c` (684), `seq_cmd.c` (725), `seq_host.c` (761), `fx_host.c` (117), and `mfx_host.c` (476). Traced fixed-pool movement and clip offsets, note-fire index invalidation, lock/trig edits, all command argument/cast paths, packed Capture ring rebasing and stopped/playing commit, event-room budgeting, reroute ownership, multi-sink and modulation-hook dispatch order, audio-effect beat boundaries, and MIDI effect note lifetime, queues and flush. The ring and queue writes are bounded by their public capacities; the dispatcher preserves note-off ownership over reroutes and separates live/sequenced keys. No confirmed reachable runtime defect was established in these files.

Two comment-level inconsistencies remain low-confidence impact and are not counted as behavioral findings: `fm1_mod.h:399` says HOST takes two records although initialization reserves six (`mod_core.c:145-160`), already recorded in batch 22; and `seq_clip.c:587-598` says Movy per-clip-cap excess is silently dropped while `note_room` increments `stats.refused` at `:584-586`. The latter is a telemetry/source-comment mismatch; the focused cap test checks retained notes but not the counter. No product code changed and no tests/builds were run. `seq_engine.c`, `seq_persist.c`, and sequencer cross-caller tests remain pending.


### Batch 24 — sequencer scheduler, transport and set persistence

Read all 2,239 lines of `engines/seq/seq_engine.c` and 700 lines of `engines/seq/seq_persist.c`, following pool-layout validation, gate/event guarantees, per-tick scheduling, note and automation ordering, song/scene edit carry, count-in/recording, external MIDI-clock transitions, block clock arithmetic, getters, export byte layout, streaming import state and malformed-line handling. The scheduler's fixed-capacity event emissions retain the documented note-off reserve when callers provide `fm1_seq_min_events`; playback and persistence state transitions are now source-reviewed against batches 21-23.

**[P2] Malformed trig-row lane tokens cause an uninitialized read during set import. [verified]** In `engines/seq/seq_persist.c:333-336`, `field_end()` declares `int64_t lane`, calls `num_i()` into it, records the parse result in `fok[1]`, then copies `lane` to `fv[1]` unconditionally. A tagged `movy1` set with a trig list such as `tg 0 0 0:bad:50:1:1:0` reaches this path when the colon ends the second field; `num_i()` rejects `bad` without writing its output, so line 336 reads an indeterminate automatic value. The row is later ignored because `fok[1]` is false, but undefined behavior has already occurred while parsing user-supplied state. Confidence high; severity P2 for a malformed import invoking C undefined behavior. The scenario is established from parser control flow; native malformed-input tests and sanitizer execution were not run in this environment. No fix was applied.

No other confirmed defect was established in these two complete files. Their related native tests, import fuzzing and oracle parity remain unexecuted because pytest/native tools are unavailable here and no heavy build was authorized. No code changed and no device action occurred.

### Batch 25 — engine, simulator and CI build boundaries

Read `engines/Makefile`, `engines/modules/catalogue.mk`, all 40 `engines/mk/*.mk` fragments (including `filter.mk`), `sim/web/mk/sim.mk`, `sim/web/build.sh`, `sim/web/build-on-aeon.sh`, and both workflow files under `.github/workflows/`. Checked source/object selection against the MIT/GPL switch, module list generation, generated GPL headers, dependency includes, native versus wasm object boundaries, wasm imports/exports, test gates, artifact write order, remote staging, Pages deploy permissions/concurrency, and CI coverage matrices. The source/object declarations have no discrepancy established in this static pass; native and wasm build/parity workflows remain unexecuted under the audit constraint against large local builds and unavailable remote tooling.

No new confirmed correctness defect emerged from these build files. Two bounded provenance/safety risks remain for follow-up: CI refers to GitHub Actions by movable major-version tags and fetches `ip2k/FM-1-RE` by mutable branch names; and `build-on-aeon.sh` interpolates `FM1_REMOTE_DIR`/`FM1_SESSION` into remote shell command strings without escaping embedded quotes. The latter requires an unusual caller-supplied environment value and is not an externally reachable code path in ordinary use, so it is recorded as a hardening candidate rather than a confirmed vulnerability. No remediations were made. No containers, remote builds, firmware tools, hardware or devices were invoked.
### Batch 26 — branding generator and editor mockup source

Read the complete 926-line `assets/branding/render_branding.py`, all six editor HTML pages, their stylesheet and renderer (`editor.css`, `editor.js`, `shell.js`, `render.mjs`, `shrink.mjs`), and parsed the complete JSON payload in `meta.js`. Checked deterministic seeding, glyph/font inputs, bounds and overlap guards, SVG/raster geometry sharing, PNG filter decoding/palette encoding, editor metadata bounds/defaults/enum counts/log ranges, static HTML injection surfaces, wire/layout measurement, browser process lifecycle and the mockup test gate. All parameter records are internally within their declared bounds, log-scaled parameters have positive minima, and no enum table exceeds its declared count.

**[P3] The mockup renderer returns success when its layout or page checks report failures. [verified]** `assets/web-editor/src/editor.js:324-325` logs layout findings to the browser console; `assets/web-editor/src/render.mjs:87-93` counts and prints those findings but never sets a failing exit code when `total` is nonzero. In addition, `render.mjs:82` clears the console records collected while waiting for the page's ready marker, including `PAGEERROR` and `not ready`, before the final tally. If a page script fails or its rendered labels overlap, a caller that relies on the process status can still accept screenshots as a clean run. This weakens a developer layout check but does not directly affect the shipped simulator. Confidence high from the full control flow; no Chromium binary is available here for end-to-end reproduction. No change was made.

The mockup HTML and frame scripts are static, authored example files; interpolation into `innerHTML` is sourced only from those local `data-*` attributes and metadata, not from runtime project files. Branding geometry and metadata were source-checked, but image rendering was not run because no Chromium/headless shell is installed. The mockup renderer also lacks a `finally` cleanup around its spawned browser and temporary profile; this is a low-priority cleanup candidate if an exception interrupts rendering. No source changes or visual claims from an unrun render are recorded.

### Batch 27 — host modulation/sequence scripts, clip bridge and sequence CLI

Read the complete `engines/host/mod_script.c/.h`, `seq_script.c/.h`, `state_clip.c/.h`, and `seq_tool.c`. Traced script tokenization and numeric coercion into runtime setters, the timed-frame header and stable ordering, typed command formatting round-trips, clip lane remapping into/out of canonical set text, two-pass state-reader streaming imports, import timing, event-cap boundaries, JSON diagnostics, and desktop file writes. The sequencer tool is a test/host harness and the state writer goes through the same core codecs described in batch 4; these reads do not substitute for the unavailable pytest/native run.

**[P2] `NaN` in a modulation script reaches undefined floating-to-integer conversions. [verified]** `engines/host/mod_script.c:48-52` accepts any complete `strtod` spelling, including `nan`; `position()` at `:55-58` checks range using comparisons that are false for NaN, then casts it to `unsigned` before deciding whether it is integral. C makes conversion undefined when the floating value cannot be represented in the integer type. A user-supplied module line such as `mod nan lfo` reaches this while parsing a `.mod` script; analogous unchecked casts exist for `lock=nan` at `:308-312`, a `data` version at `:352-356`, and a `seed nan` line at `:395-403`. Other NaN parameter values are clamped safely by `fm1_param_clamp`/`mod_clampf`, so the issue is specifically the integer conversions. Confidence high from source plus `strtod` behavior; no sanitizer build or malformed-file test ran. No fix was made.

No other confirmed defect was established in the host script and clip bridge paths. `fm1-seq` CLI numeric options mostly rely on `strtol`/`strtoull` and core limit checks, which leave malformed-input diagnostics and strict argument rejection as a cleanup opportunity; no independent runtime-impacting case was promoted from that broad behavior in this pass. The script/clip paths' corresponding tests were read but not run because pytest and the prebuilt native binaries are unavailable. No large build or device action occurred.

### Batch 28 — desktop renderer and audio host lifecycle

Read the complete 2,174-line `engines/host/render.cc`. Traced option parsing through host construction, command and set imports, audio/MIDI/MFX unit creation, timed modulation application, per-block rendering and mixing, fault injection, WAV and JSON output, and both normal/error cleanup paths. Checked rate/frame arithmetic, capacity checks, malformed modulation scheduling, and all live unit ownership. No native renderer build or large local build was run.

**[P3] Non-finite or out-of-range render durations reach an undefined float-to-integer conversion. [verified]** `engines/host/render.cc:941-943` accepts `--seconds` and `--rate` through `atof` with no finite/range check. With a supported non-silence input such as `--input noise`, `--seconds nan` reaches line 1743, where `seconds * rate` is cast to `uint32_t`; C++ floating-to-integer conversion is undefined when the value is NaN or outside the destination's representable range. `--rate nan` reaches the same expression even with the default duration. This is an ordinary local CLI input case that can trigger undefined behavior before allocation/rendering. Confidence high from source and language conversion rules; no native executable was available for runtime reproduction.

**[P3] A timed modulation-script error skips cleanup for MIDI-effect units and its log. [verified]** `ModFail` at `engines/host/render.cc:1549-1565` releases sound/effect/insert units and the sequencer/modulation resources, but omits every `mfx_units[k][j]` and `mfx_log`, even though the comment says all units and both logs are released. A malformed timed line (for example `@64 mod 1 lfo unknown=value`) is stored by the file reader at `:1574-1599`; frame-zero lines are applied before MFX creation, but this line is applied later in the render loop at `:1914`, after MFX unit creation and optional log opening at `:1670-1693`. `fm1_mod_script_apply` rejects the unknown parameter, and `ModFail(2)` returns without releasing the MFX engine instances or closing the log. Process exit reclaims these resources, but leak-checking and any embedding that continues after the returned error observe the cleanup defect. Confidence high from cross-path control flow; no sanitizer run was available.

No additional confirmed issue was established in the remaining renderer paths. One output-integrity issue is recorded as a cleanup candidate: when `--save-mod-data` cannot open its requested file, it prints an error at `:2160` but still exits successfully; a failed `fprintf`/`fclose` is also not checked. No source changes were made.

### Batch 29 — saved-state command-line tooling

Read all 747 lines of `engines/host/state_tool.c`. Traced file caps and input buffering, JSON tree construction and stable context ordering, binary/JSON/set dispatch, record callbacks, engine instantiation and RAM accounting, line diff construction, numeric helper commands, and output handling. The state tool is a desktop utility and was reviewed without a native build.

**[P3] `fm1-state diff` can allocate a quadratic LCS table from two 1 MiB inputs. [verified]** `read_file()` accepts files up to 1 MiB (`engines/host/state_tool.c:73-87`). The diff path counts every newline as a row at `:455-468`, then `diff()` allocates `(nx + 1) * (ny + 1)` `unsigned` entries at `:473-481` and fills the entire matrix at `:482-487`. Two accepted, newline-dense files can therefore request terabytes of zeroed memory; overcommitting hosts may kill the process while the loops touch it. The CLI does not impose a line-count or diff-memory bound, so a valid input size can cause abrupt resource exhaustion. Confidence high from the complete path; no stress run was made. This is a desktop input robustness issue, not a device runtime concern.

No other confirmed defect was established in the file during this pass. The code's `write_out()` and record/meta emitters do not propagate every `fwrite`/`fflush` failure; this is an output-integrity cleanup candidate for a full disk or broken pipe, not separately ranked. No source changes or runtime tests were performed.

### Batch 30 — arpeggiator contracts, adapter, tables and smoothing helper

Read `engines/midi_fx/fm1_arp.h`, `arp_engine.c`, `arp_rhythm.c`, `registry.c`, `engines/include/fm1_smooth.h`, and `engines/mod/mod_mi_tables.c` in full. Checked the public event/capacity and transport contracts, engine parameter ordering/UID/core-value mapping, module guards, bounded Euclidean grouping/flattening, sample-rate ramp arithmetic, and generated-table attribution and shape. The Euclidean work arrays stay within 32 entries for `len` in 1..32; the 2.5 ms smoothing multiplication remains within 32-bit unsigned range after its 1 MHz rate clamp.

No confirmed defect was established in these files. The wrapper and rhythm tests and the generated-table comparison remain unexecuted; the core arpeggiator implementation and its full regression suite are still pending. No source changes, builds or device actions occurred.

### Batch 31 — arpeggiator runtime core

Read all 944 lines of `engines/midi_fx/fm1_arp.c`. Traced the fixed instance state, note ledger and deferred note-off policy, live/sequencer key ownership, sustain/latch/stop behavior, all order construction modes, octave spans and lifts, deterministic step randomization, rhythm and Euclidean indexing, ratchet/gate timing, free and sequencer-locked clocks, event ordering, parameter updates and caller-supplied output capacity. Maximum cycle construction remains within 128 entries for 16 held keys and four octaves; note generation's ratchet list is bounded by the 16-key chord. The core does not allocate or use global mutable state.

No confirmed defect was established from the implementation. `tests/test_engine_arp.py` (951 lines) and the broader MIDI effect tests were not read or executed yet. No build or device action occurred.

### Batch 32 — GPL acid-line MIDI effect

Read the complete 553-line `engines/midi_fx/acid_gen.c`. Followed its GPL build assertion and TB-3PO dependency, parameter-to-generator mapping, deterministic and automatic mutation rebuilds, project-key tracking, transpose/run modes, note stack, ping-pong/random directions, slide/tie and gate timing, small-cap output deferral, and panic/reset/flush handling. The eight-entry owed-off queue exceeds the maximum two notes this effect can have active during a slide transition; note-ons are omitted when output has no room. This source review does not change the existing licensing/runtime report or authorize any license edits.

No confirmed correctness or lifetime defect was established in this file. The GPL switch build test and MIDI-effect behavior tests remain unread/unexecuted. No source or licence changes, builds or device actions occurred.

### Batch 33 — arpeggiator command-line harness

Read all 347 lines of `engines/midi_fx/arp_tool.c`. Traced parser behavior for timed events, clocks and run/halt records; sorting and block boundaries; 16-bit block-relative frames; core calls and deferred note-off draining; JSON logging and the list export. Confirmed the command-line tool is a test harness, not device code.

**[P3] An event at the maximum 32-bit frame makes the default run loop wrap and never finish. [verified]** Script frames are stored as `uint32_t` (`:148-150`), while the automatically derived `end` is `unsigned long`; `UINT32_MAX + 1ul` is representable on the supported 64-bit host (`:268-270`). The render cursor `start` and each `stop` are then narrowed to `uint32_t` (`:283-284`). Given a script containing `@4294967295 on 60 100`, the derived end is 4,294,967,296; once the final `start + block` wraps, the loop resets to a smaller frame and `start < end` remains true indefinitely. Explicit `--end` values above `UINT32_MAX` have the same mismatch. This can be triggered by an accepted script/input value; the tool has no frame-range rejection. Confidence high from integer widths and loop control; no native harness executable was available for a run.

No other confirmed issue was established in this tool. Numeric tokens are generally parsed with unchecked `strtoul`/`atoi` and equal-frame run/halt records are qsorted without a stable tie-break; these remain input-validation/determinism cleanup candidates. No code changes or tests/builds occurred.

### Batch 34 — arpeggiator regression suite

Read the full 951-line `tests/test_engine_arp.py`. Reviewed the table/generator cross-checks, all order and octave variants, Python Yarns parity model, rate/gate/swing/ratchet timing, random-seed repeatability, block-size invariance, no-heap symbol check, latch/pedal/JOIN/SYNC behavior, origin and STOP cases, sequencer grid locking, TRG ordering, seeded event-capacity fuzzing and note-ledger stealing. The suite is broad for normal frame ranges and makes valuable block/capacity invariants explicit.

The suite was not executed because pytest and the generated `engines/build/fm1-arp` tool are absent in this worktree and a local native build was not authorized. The maximum `uint32_t` script frame / `--end` width boundary that triggers the batch-33 wrap is not covered by this suite. No new confirmed implementation defect was established by reading the tests; no source changes occurred.

### Batch 35 — MIDI-effect host and acid generator test suites

Read `tests/test_engine_acid_gen.py` (331 lines) and `tests/test_engine_midi_fx.py` (652 lines) in full. The acid-generator suite checks the vendored TB-3PO line against the vendored/upstream implementations, timing and slides against an independent expected-event model, key/project context, bypass and block invariance, GPL listing and no-allocation imports. The host MIDI-effect suite exercises bypass/no-op, multi-sound/chains, event ownership across effect changes, note-off balance, output capacity, sequencer clocks and grids, TRG events, modulation voice ends, invalid flags and allocation/stdio/libm symbol checks. These tests cover much of the main claimed runtime contract.

Both suites were source-reviewed but not executed; pytest and renderer build artifacts are unavailable in this worktree and native compilation remains out of scope. No new confirmed defect was established by reading them. No code or licensing report was changed.

### Batch 36 — Acid Bass wrapper around the GPL X0X unit

Read `engines/src/acid_bass.cc` (434 lines) and `acid_bass.h` completely. Traced the GPL build assertion, in-place X0X instance lifecycle, accepted sample rates, 16-sample staging buffer across host block splits, SMOOTH parameter ramps, per-note offsets, switch latching, pitch/bend multipliers, gain, key stack insertion/removal, slide and slide-back handling, and idle transitions. Verified the API flag macros mark the listed continuous parameters for smoothing and modulation, including the logarithmic fields.

No confirmed defect was established in this wrapper from source review. Its waveform/oracle comparison, engine parameter tests, and GCC/Clang/wasm build variants remain pending/unexecuted. No source or licensing report changed; no hardware action occurred.

### Batch 37 — Comet Kit wrapper and per-pad voice mapping

Read `engines/src/comet_kit.cc` (485 lines) and `comet_kit.h` completely. Traced its GPL guard and drum909 instance lifecycle, 16 pad-to-11 voice sharing map, per-kit/per-pad voicing initialization and overrides, per-pad SMOOTH ramps, drive type and kit parameters, pad focus/API v4 getters, hit/choke routing through the vendored unit, 16-sample output staging, and idle/volume behavior.

**[P2] A running Comet voice can pick up the newly selected kit's voicing before its next hit. [verified]** The documented `Kit` control is latched for a pad hit, but `Apply(p)` at `engines/src/comet_kit.cc:315-328` always resolves pot defaults through the mutable global `voicing[kit][p]`. While a pad is sounding, changing one of its smooth controls starts a ramp (`:403-409`); each chunk ticks the ramp and calls `Apply(p)` for the current voice owner (`:343-350`). If the user changes `Kit` during that ramp (`:412-413`), the still-ringing voice is retuned to the new kit's voicing even though that kit should take effect on the next hit. The same call also applies the focused pad's `dist` at `:323`, so changing Drive Type during a concurrent smooth ramp can bypass its hit-latched behavior. Confidence high from control/data flow; no runtime build or audio comparison was run. This is a user-facing voice-state/latch defect, not a boot/runtime boundary finding.

### Batch 38 — Crater Kit wrapper and 808 hit controls

Read `engines/src/crater_kit.cc` (429 lines) and `crater_kit.h` completely. Traced the GPL guard, 16-sound/11-track pad mapping including conga/claves/maracas track switches, all per-pad state and API v4 reads, per-hit Tune/Decay/Tone/Snap/Dist application, continuous Level/Drive/Volume ramps, held pitch bend behavior, choke and velocity mapping, 16-sample block staging, and silence/active gating. Cross-checked the vendored `drum808_trigger()` path: it samples Tune and the struck pots at a trigger, while Level/Drive are used through the running sound. Dist is applied at a hit or immediately only when silent.

No confirmed defect was established in the wrapper. The oracle/audio tests and build variants remain pending/unexecuted; this source inspection does not qualify an FM-1 runtime build. No code or licensing report changed.

### Batch 39 — Plaits-derived Drums engine and its complete regression suite

Read `engines/src/drums.cc` (802 lines), `engines/src/drum_voices.h` (326 lines), and `tests/test_engine_drums.py` (718 lines) completely. Traced all 16 pad and 10 model mappings, both voicing tables, per-pad and kit parameters, LATCH/SMOOTH/POLY behavior, note offsets, choke-before-allocation, retrigger/steal selection, quiet-tail deactivation, separate per-pad Plaits RNG, custom-noise state, per-block render/resampler flow and the 12-sample scratch lifetimes. Checked the bend and instance contracts against `fm1_engine.h`, the pitch clamp in Plaits `NoteToFrequency`, and the `fm1-x0x` trigger-reader path already reviewed for Crater. The regression suite covers the user-visible pad maps, tuning, decays, custom groups, saturated voice pressure, block-size and initial-memory invariance, per-note bounds, and non-finite extreme offsets.

No additional confirmed defect was established in these files. The direct engine contract requires `create` to receive a valid host and `pitch_bend` to receive finite values within +/-48; the desktop and browser hosts enforce that bend range, and the renderer's lookup clamps its note domain before table conversion. Tests were source-reviewed but not executed because this worktree has neither pytest nor the generated renderer and a local engine build was out of scope. No product source, licence, device or infrastructure changes occurred.

### Batch 40 — DX7/FM6 voice parsing, loop integration and generated bank

Read `engines/src/dx7_loop.cc/.h`, `dx7_voice.cc/.h`, `msfa_dx7.cc` (777 lines), `engines/include/fm1_dx7.h`, the complete 604-line `tools/dx7_bank.py`, `engines/test/dx7_oracle.cc` (349), `dx7_felucca.c` (100), and `tests/test_engines_dx7.py` (942). Traced the voice-layout sanitizer and bank inverses, 7-bit SysEx framing and checksum/report contract, raw-bank handling, multi-message slot callbacks, cache invalidation, rate/table lifetime, algorithm-loop save/restore, CLI oracle inputs and metrics, and bank/test-data provenance. The generated `dx7_bank.h` was reviewed by its complete canonical generator and `--check`, rather than treating its repeated packed values as handwritten source. Both `python3 tools/dx7_bank.py --check` and `python3 tools/dx7_bank.py --test-bank --check` pass. Full renderer/oracle tests were source-reviewed but not executed because the generated binaries and pytest are unavailable and a native build was out of scope.

**[P3] A DX7 file with 2,048 valid banks wraps the parsed voice count to zero after mutating all user slots. [verified from widths and call flow]** `engines/src/dx7_voice.cc:174-188,204-205` increments the public `uint16_t voices` field by 32 per accepted VMEM message, so a concatenated file with 2,048 valid banks (8,404,992 bytes) stores 65,536 voices through the callback but returns zero. This contradicts `fm1_dx7.h:61-70`'s promise that zero means nothing was recognized and left slots unchanged. In the instance API, `msfa_dx7.cc:343-351` invalidates the LFO and patch caches only when that return is positive; after this input, a note on a user patch already selected can reuse the previous patch's LFO settings while playing the newly loaded operators. `fm1_app_dx7_load` caps browser imports at 64 KiB (`sim/web/src/fm1_app.h:302`), but the public engine C APIs and desktop renderer's file reader have no such limit; the finding concerns those inputs, not the bounded browser importer. The test suite exercises several messages and banks but not counter wrap or cache coherence after it. No code change was made.

### Batch 41 — Felucca bridge, shim and oracle regression coverage

Read `engines/src/felucca_bridge.c` (263 lines), `felucca_bridge.h` (103), `felucca_shim.cc` (736), `engines/test/felucca_oracle.c` (261), and all 531 lines of `tests/test_engine_felucca.py`. Traced the `track_t` world sizing/alignment and WHEEL's lend/take of its static arrays, voice retrigger/release and envelope transitions, per-block modulation/output ownership, parameter maps and metadata, phase glide, voice allocation and held-key return, per-note/latch handling, output gain lanes, oracle event scheduling and test coverage.

No confirmed product defect was established in the bridge or shim during source review. The bridge's file-scope engine state is deliberately serialized through the documented audio-task-only API contract; its WHEEL arrays are copied into/out of each instance around calls. `own_` has one lane per voice, and its index is bounded by the eight-voice loop. The regression suite defines oracle comparisons across factory presets, rates, host block sizes, output instances, latch transitions, and per-note offsets, but neither it nor the oracle was run here because pytest and generated native binaries are absent and a local native build was outside scope. The test suite and oracle themselves are covered as sources; the tests that would execute them remain pending verification. No code or licence changes occurred.

### Batch 42 — Comb, Comp and Crush effects

Read `engines/src/fx_comb.cc` (296 lines), `fx_comp.cc` (512), `fx_comp_math.h` (29), and `fx_crush.cc` (256) completely. Traced the Comb delay allocation and read/write age bounds, interpolation and saturated feedback, control/sample-clock glides and dry/wet path; the Comp static curve, RMS detector, reduction-state handover and per-sample Auto Gain bound; and Crush countdown, seeded per-instance jitter, quantizer, wet low-pass and all ramp fields. Checked instance initialization and memory-size calculations against the engine's caller-allocated storage and sample-rate contracts.

No confirmed defect was established in these files. The shared math wrapper delegates to the engine math helpers and documents their input range. Associated regression tests have not yet been source-reviewed or executed, and no native builds were performed. No source or licence changes occurred.

### Batch 43 — DJ Filter and Drive effects

Read `engines/src/fx_djfilter.cc` (625 lines) and `fx_drive.cc` (600) completely. Traced the DJ Filter's 16-frame control grid, sweep/dead-zone entry and side switching, TPT SVF state initialization, 12/24 dB transition lifetime, coefficient ramps, cutoff/rate limits and guarded bypass. In Drive, followed its generated piecewise curves and ADAA integration, dead-zone/bias segmentation, quadrature Auto gain, Type transition queuing, pre/de-emphasis, DC blocker, tone tilt, and per-channel state across calls.

No confirmed defect was established in these wrappers. Drive's generated curve coefficients are reviewed as a table here but still need comparison with the canonical generator/test source. The regression suites remain pending. No source changes or tests/builds occurred.

### Batch 44 — Echo and three-band EQ

Read `engines/src/fx_echo.cc` (332 lines), `fx_eq.cc` (608), and `fx_eq_math.h` (82) completely. Traced Echo's fixed ring dimensions and modulo indexing, negative read-age conversion, slow clock and interpolation, anti-alias/reconstruction filters, feedback routing and bounded 16-bit storage. In EQ, followed the three SVF coefficient/mix equations, 8-frame control grid, neutral passthrough, driven-idle gate, settle-time calculation, wake warm-up and per-channel integrators. Reviewed the math helpers against the positive frequency/Q and bounded tangent domains at supported rates.

No confirmed defect was established in these implementations. Echo and EQ regression suites remain pending source review and execution; no local engine build or test run occurred. No code, device or licence changes occurred.

### Batch 45 — Multimode Filter solver and shared DSP math

Read `engines/src/fx_filter.cc` (855 lines) and `fx_filter_dsp.h` (114) completely. Reviewed the six processors (SVF, transistor ladder, diode ladder, Sallen-Key, SK Mixed and Formant), their secant-based nonlinear solves, per-type coefficient storage, cutoff/mode/morph mapping, type reset/warm/crossfade queue, control-grid timing, level/mix path and flush behavior. Checked the shared bit-based `exp2`/`log2` domains and input guard against the supported sample-rate and clamped-parameter ranges.

No confirmed defect was established in this source pair. The main Filter regression suite and cross-platform sanitizer/parity checks remain pending. No source changes, builds or tests occurred.

### Batch 46 — Fold and Gate effects

Read `engines/src/fx_fold.cc` (391 lines) and `fx_gate.cc` (779) completely. Traced Fold's periodic curve reduction, small-step corner integral, larger-step antiderivative, symmetry offset cancellation, DC blocker and tone-state lifecycle. In Gate, followed Schmitt/hysteresis episodes, accepted-trigger and lockout behavior, attack/hold/decay ramps, threshold-derived gains, two key SVFs, link/listen interpolation, caller-provided key/state hooks, aligned lookahead allocation and circular read/write indices.

**[P3] Gate advertises 5 ms maximum lookahead but caps actual delay at 510 frames. [verified]** The supported sample-rate range is 8–384 kHz (`fx_gate.cc:159-160`), while the requested maximum is computed as 5 ms (`:164`, `:419-423`) and then capped at 510 frames (`:423`). `Lookahead=5` therefore yields at most 2.66 ms at 192 kHz and 1.33 ms at 384 kHz; the advertised 5 ms is reachable only through 102 kHz. This is the behavior of an explicit memory cap, so the defect is the mismatch with the parameter's advertised range, not an unbounded allocation. Confidence high from the rate, conversion and cap expressions; no renderer run was performed. The Limiter uses a similar cap and needs comparison when its source batch is reviewed.

Fold and Gate regression suites remain pending source review and execution. No source changes or device actions occurred.

### Batch 47 — Hall reverb and Isolator

Read `engines/src/fx_hall.cc` (612 lines) and `fx_isolator.cc` (569) completely. In Hall, traced rate-specific line/pre-delay layout, power-of-two storage, line partition maximum reads, pointer movement, modulated fractional delays, all-pass locations, shelf/damping gain calculation, Freeze rounding behavior and state initialization. In Isolator, followed the three-band LR4 tree and phase compensation, per-sample TPT coefficients, unity bypass/crossfade, driven-idle behavior and wake warm-up.

No confirmed defect was established in these implementations. Their specific regression suites remain pending source review and execution. This pass did not compare Gate's 510-frame limit against the Limiter; that comparison remains pending. No source changes or tests/builds occurred.

### Batch 48 — Limiter runtime, rate layout and adversarial regression coverage

Read `engines/src/fx_limit.cc` (911 lines), `engines/include/fm1_dynamics.h`, `engines/mk/limit.mk`, the full 856-line `engines/test/limit_test.cc`, and all 459 lines of `tests/test_engines_limit.py`. Traced the byte-offset layout and rate clamp, rounded lookahead conversion, frame-stamp wrap horizon, bounded monotonic-deque and integer box arithmetic, line replay on lengthening lookahead, crossfade state ownership, the zero-lookahead envelope, mode/ROUND state, per-frame control storage, host parameter sanitization and the read-only gain tap. Reviewed the probe build separately from the ordinary engine and the Python suite's renderer/probe contracts.

No confirmed limiter correctness, memory-bound, or lifetime defect was established. The cap of 510 frames is an explicit, tested behavior: the 0–5 ms parameter range represents less than 5 ms above 102 kHz (2.66 ms at 192 kHz and 1.33 ms at 384 kHz). This limitation is stated in the source, engine documentation and test comments. The test source covers that rate boundary; neither the native `fm1-limit-test` nor its pytest wrapper was executed because generated binaries/pytest are unavailable here and building the engine locally is outside this audit's constraints. No source change, device action or license edit occurred.

### Batch 49 — Clouds Room wrapper and deterministic math

Read the complete `engines/src/fx_room.cc` (416 lines), `fx_room_math.h` (107), full `engines/test/room_test.cc` (363), and `tests/test_engines_room.py` (363). Traced instance placement construction/destruction, host rate rejection, Clouds-rate decay and damping transformations, coefficient targets and glide segmentation, frame/grid/sweep phase progression across chunked calls, diffuser/reverb ordering, guarded dry and wet inputs, damping/output flush, stereo width endpoints and Mix=0 exact passthrough. Checked the libm-free log/exp/pow behavior at zero decay, subnormal values and bounded rate ratios. The desktop suite covers adversarial host values, 40 seconds of control/input changes, exact-zero tail state, block-size parity, rate boundaries and output hashes; the heavy reference-comparison file and vendored Clouds implementation have separate ledger entries.

No confirmed wrapper or math defect was established. The documented 2,048-cell diffuser sweep addresses its known subnormal retention; the separate in-loop damping state may retain a tiny value, but it comprises two values and the wet output is flushed, so I found no meaningful impact to promote. Runtime and sanitizer claims in the pre-existing tests were not re-executed; no local build, source change, device action or license edit occurred.

### Batch 50 — Master Sat and Transient shaper implementations

Read `engines/src/fx_sat.cc` (728 lines), `engines/src/fx_shaper.cc` (237), `engines/test/sat_test.cc` (513), and `tests/test_engines_sat.py` (443). Traced saturation curve coefficients and translated offset polynomial, clamp continuity, TPT band-filter state, inverse-drive residual and DC removal, stereo Glue detector/release, parameter target/glide derivation, Shape crossfade queue, Mix exactness, idle rest and warm wake, finite input limits and per-instance state. For Transient, checked fast then slow detector ordering, one-pole sample-rate coefficients, floor behavior at silence, finite dB gain bounds, smooth parameter ticks, and direct-signal mixing. Reviewed the test harness's tone frequency validation, bounded buffers, harmonic folding and large-bin iteration as well as the functional pytest expectations.

No confirmed source defect was established in these implementations or the Master Sat suites. The separate generic idle regression and the combined Squash/Transient-specific regression remain to be audited; those are required before closing the idle and Transient coverage. Test execution is pending unavailable pytest/generated binaries and the no-local-build constraint. No code change, device action or licence edit occurred.

### Batch 51 — Squash and Transient regression path

Read `engines/src/fx_squash.cc` (703 lines), `engines/test/squash_test.cc` (913), and `tests/test_engines_squash.py` (330) completely. Traced Snap's lower/gap state and gate shape, dual-channel link, gated quarter-sine, Mu speed/threshold/makeup and clipping cap, Split's alternating gain sets and zero-blend behavior, Type seed/crossfade, and the read-only gain tap. The tests exercise per-type parity, vendor-oracle fixtures, hostile inputs, parameter changes, makeup clipping, gates, Type transitions, and Transient regressions. Test sources were reviewed but not executed.

No confirmed functional defect was established. **[P4, optional dead-state removal]** `ShaperInstance.gain_db` is written and read only within its own frame-local update in `engines/src/fx_shaper.cc:120,179,203,212`; repository-wide reference search found no consumer. It appears to have no observable effect and is a safe removal candidate after a focused size/behavior check. This was not changed. No code, device or licence changes occurred.

### Batch 52 — Tilt equaliser and regression path

Read `engines/src/fx_tilt.cc` (377 lines), `engines/test/tilt_test.cc` (444), and `tests/test_engines_tilt.py` (401) completely. Traced the one- and two-section TPT transfer equations and prewarp, bounded polynomial tan domain, Shelf/Slope coefficient mapping, two-stage control glide, first-render priming, per-channel state/update ordering, exact neutral bypass, input guard, flush and all host-rate bounds. Reviewed the independent double-precision response oracle and its registration, random block-size, mid-stream control, modulation, silence, hostile input, and rate tests.

No confirmed defect was established in the source or reviewed test contracts. The native probe and pytest suite were not executed; generated binaries/pytest are unavailable and a local engine build is outside this audit's constraints. No source, device or licence changes occurred.

### Batch 53 — Shared note glide rules and exact-path tests

Read `engines/src/glide.h` (371 lines) and `tests/test_engine_glide.py` (835) completely. Traced Time and Rate stepping, fresh/played pitch availability, note-on source selection under Poly/Mono/Legato, Always versus held-key sources, note-off return, the 16-key held stack and eviction, and per-event configuration. The test oracle computes single-precision offsets and compares engine renders byte-for-byte across all six supported engine configurations (GPL phase-bend conditional), then covers mode transitions, mid-glide time changes, bends, poly chords, voice steals, held-key stacks, invalid keys, and measured FM-1-rate behavior.

No confirmed helper or test-contract defect was established. The six engine integrations that embed this helper remain separate coverage items. This source-level review did not execute renderer/pytest tests or builds. No code, device or licence changes occurred.

### Batch 54 — Macro integration of note glide and Plaits

Read `engines/src/mi_macro.cc` (569 lines) completely. Traced voice allocation and same-key retrigger, Mono/Legato retuning and release ordering, model rebuild/lifecycle, held-key and glide state, fixed-rate block advancement through the pull resampler, per-note smoothed controls, per-model arena sizing, and LPG Gate/Ping/Off envelope and termination paths. This was a focused integration review; its broad Plaits/vendored DSP internals have their own vendor coverage tier.

No confirmed new defect was established in the Macro integration. The glide oracle suite was source-reviewed in batch 53 but not executed, and the remaining five engine integrations remain pending. No code, device or licence changes occurred.

### Batch 55 — Macro Heavy integration, speech sharing and stereo path

Read `engines/src/mi_macro_heavy.cc` (907 lines) completely. Followed all 13 model registrations and exact arena-byte requirements, shared LPC speech bank ownership/quantization/restart, per-voice speech controllers, string-machine stereo resamplers and state-copy/stop conditions, other-model mono resampler equivalence, voice allocation and glide transitions, smoothing/per-note controls, self-enveloped silence timeout, LPG modes, and null-engine handling when arena checks fail.

No confirmed defect was established in the Macro Heavy wrapper paths reviewed. The shared glide test suite remains source-reviewed only; no build/test ran. Four other integrations remain pending. No source, device or licence changes occurred.

### Batch 56 — Six-Op FM integration

Read `engines/src/mi_sixop.cc` (516 lines) completely. Traced all 96 patch labels and conditional renames, patch unpack/cache and transpose, voice allocation and held-note transitions, gate-low one-sample setup/retrigger renders, per-block note/bend/glide ordering, leader/follower LFO routing across same and different patches, silent voice retirement, shared algorithm table, scratch-buffer ranges, smoothing and resampler feed.

No confirmed defect was established in the Six-Op wrapper. The existing full glide test suite covers it by source review but was not run; Three integrations remain pending. No source, device or licence changes occurred.

### Batch 57 — Shapes/Braids integration and guarded pitch edges

Read `engines/src/mi_shapes.cc` (465 lines) completely. Traced 96 kHz chunk/resampler flow, note allocation/glide and legato no-Strike behavior, per-note envelope/control offsets, enum shape application, pitch clamp before integer conversion, Comb/Wave Line Timbre guards, oscillator input ranges, and attack/release envelope/state retirement. Checked the API's declared finite ±48-semitone pitch-bend contract against the wrapper's pre-clamp pitch conversion.

No confirmed defect was established in the Shapes wrapper. Shapes edge/hostile tests and the glide suite were source-reviewed elsewhere but not executed. Two glide integrations remain pending. No code, device or licence changes occurred.

### Batch 58 — FM6/msfa integration of glide and retuning

Re-read `engines/src/msfa_dx7.cc` (777 lines) with attention to the new glide/voice-mode path in addition to its previously recorded voice setup, rendering and user-slot paths. Traced key clamping at note-on/off, LFO program/keydown lifecycle, mono/legato operator retuning in log-frequency Q24, transpose and ratio-operator delta, per-note pitch plus bend plus glide composition, envelope and pitch-envelope block clocks, parameter smoothing, table ownership by rate, shared first-create rate gate, and quiet-voice release retirement.

No confirmed defect was established in the FM6 integration. The API limits pitch-bend callbacks to finite values within ±48 semitones, and its Q24 conversion also clamps. Glide-path tests remain source-reviewed only. One integration remains pending. No code, device or licence changes occurred.

### Batch 59 — Felucca Phase Bend shim integration

Re-read `engines/src/felucca_shim.cc` (736 lines), covering Drawbar, Trio and Phase Bend entry points. Traced compile-time GPL gate and per-engine parameter slot maps, LATCH snapshots, shared voice allocation and held-key return, Phase Bend glide on/off and bridge retune ordering, per-note pitch and voice-gain side buffers, float-to-Felucca pitch quantization, block buffering, voice-release cleanup, and aligned world allocation sized from the vendor bridge.

No confirmed defect was established in the Phase Bend integration. Its test path is conditional on `FM1_GPL_MODS`; no vendor binaries/builds or hardware operations were run. All six shared-glide wrappers have now had source review, but the glide suite remains unexecuted. No code, device or licence changes occurred.

### Batch 60 — Mutable audio-effects wrappers and Plaits envelope helpers

Read `engines/src/mi_fx.cc` (565 lines) and `engines/src/mi_plaits_env.h` (74) completely. Traced Plate's freeze ramp, initialized delay storage, parameter smoothing and rate-compensated loop/damping; Ensemble's wet extraction, offset line and dry/wet mix; Diffuse's delay allocation, rate-compensated loop, stereo all-passes and tone states; all input guards and chunk bounds. Checked envelope modulation and velocity mapping against the comments and wrapper callers.

**[P3, confirmed] NaN effect parameters clamp to the minimum instead of the documented default. [high confidence]** `engines/src/mi_fx.cc:66-69` treats failed `v >= min` as `min`, which includes NaN. The engine API explicitly specifies NaN → parameter default (`engines/include/fm1_engine.h:173-178`). All three effects route `set_param` through this helper (`mi_fx.cc:204-209,352-356,499-502`), so e.g. a NaN Plate Mix selects 0 rather than its default 0.3, changing observable output. Infinity still clamps to an endpoint. A focused regression should compare NaN with each parameter's declared default; no fix was made during audit.

Read `tests/test_engines_mi_fx.py` (444 lines), `tests/test_engines_plate_freeze.py` (186), `tests/test_engine_smooth.py` (209), and `engines/test/smooth_test.cc` (228) completely. Their coverage is broad for rendering behavior, freeze transitions, host block splits, instance initialization, bad audio input and smooth ramps, but it does not assert the expected value after a NaN parameter write. The smooth harness sends NaN only to the first non-NOLOCK parameter and compares partition outputs against each other, so a stable wrong clamp passes; the dedicated effects suite has no NaN parameter case. No tests or builds were run.

### Batch 62 — Per-note offset storage and API contract tests

Read `engines/src/note_offsets.h` (87 lines) and `tests/test_engine_note_params.py` (572 lines) completely. Traced the compact bit layout, the reserved pitch bit, index and POLY validation before slot calculation, API-level offset normalization, exact zero-bit clearing, and base-plus-offset clamping. The test file exercises every supported engine family, renderer refusal for non-POLY/invalid keys, exact equivalence to base changes and pitch bend, smoothing interactions, model and parameter enumeration, note isolation, release/retrigger/ended/stolen voice lifecycle, NaN/infinity and extreme-range behavior, initialized-memory independence, and host block partition invariance.

No additional defect was established in the helper or test contract. The tests assert that NaN note offsets have no effect, but do not cover NaN parameters in the separate Mutable effects helper; that defect remains in batch 60. This source-level review did not run renderer tests or builds. No source, device or licence changes occurred.

### Batch 63 — msfa integration and Schwung adapters

Read the msfa integration headers and translation-unit wrapper (`engines/src/msfa.h`, `msfa_prelude.h`, `msfa_tables.cc`, `msfa_unit.cc`), its table oracle (`engines/test/msfa_ref.cc/.h`), and the full Schwung ABI/prefix/adapters (`engines/src/schwung_abi.h`, `schwung_module_prefix.h`, `sw_psxverb.cc`, `sw_sophie.cc`). Reviewed `tools/msfa_tables.py` completely and the generated `msfa_rom.cc` by its declarations, array boundaries and deterministic-source equivalence; `python3 tools/msfa_tables.py --check` passed, and the generated file's SHA-256 is recorded in the manifest. Traced namespace isolation, forced portable kernels, table pointer mutability assumptions, rate-specific table sizing, symbol renaming context, ABI layout guards, allocator/parser redirection, adapter key/UID tables, Sophie focus-entry key construction, PSX Verb headroom and both fixed arena budgets.

No confirmed defect was established in these integration paths. The constant ROM values are reproducible from the tracked generator and have an independent msfa-init oracle path; the oracle itself was source-reviewed but not built or run, so this confirms generator/file consistency rather than runtime word-for-word equality. No licence terms were changed. No hardware action, engine build or test suite was run.

### Batch 64 — Schwung shim runtime, allocator and tests

Read `engines/src/schwung_shim.cc` (700 lines), `schwung_shim.h`, `engines/test/schwung_selftest.cc` (674), `engines/test/schwung_race.cc` (77), and `tests/test_engines_schwung.py` (488) completely. Traced first-host configuration and rate refusal, one-time module initialization, the arena's bounded aligned allocation and realloc path, late-allocation rejection, fixed numeric formatting/parser, integer/MIDI conversion, control-rate ramps, sound lookahead and effect FIFO/casting/headroom, focused-value storage/readback, null behavior, test probes, real-module contract checks and the TSan race-probe scenario.

No confirmed defect was established in the current adapter/shim call paths. The selftest has strong source-level coverage of fixed block/rate semantics, allocation overflow/exhaustion, output guards, parser ULP/end-pointer behavior, MIDI encoding, conversion clipping and initialization lifetime. The TSan race probe is separate and was not built or executed; all renderer and pytest checks remain unexecuted in this worktree. The global allocator handoff during `create_instance` must be considered together with the vendored module call paths; that cross-boundary review is still pending, so no concurrency conclusion is claimed here. No code, device or licence changes occurred.

### Batch 65 — PSX Verb vendored DSP integration

Read `engines/third_party/schwung-modules/psxverb/psxverb.c` (898 lines) completely. Traced preset scaling, fixed work-buffer allocation and power-of-two ring bounds, state restore/get paths, decay stability cap, block-pair processing, saturated work-area writes, reflection/comb/all-pass order, halfband decimation/interpolation, input/output scaling and the v2 API table. The file's SHA-256 matches the pinned hash in `UPSTREAM.md`; the implementation is byte-identical to its named upstream revision.

**[P2, confirmed, high confidence] PSX Verb's interpolation phase has a zero branch, so every second wet output sample is forced to zero.** `psxverb.c:108-112` defines all 19 `g_hb_phase1` coefficients as zero; `halfband_interpolate` multiplies only by that array for `out_s1` at `:158-170`. It also labels `g_hb_phase0` as the even taps at `:99-105`, but that array includes the odd center coefficient `0.6328125`, omits the final even tap `-0.000275135`, and is therefore not the declared even polyphase. Every processed pair invokes this interpolation for both channels at `:725-727`. With `Mix>0`, odd-frame wet contribution is absent and even-frame wet contribution uses the malformed phase weights; at `Mix=1` the second sample of every wet pair is exactly zero, producing audible periodic distortion and an incorrect transfer response. Existing tests check nonzero tail/RMS, latency and dry headroom, but do not compare the interpolator against a reference or check alternating wet samples. No engine build or runtime reproduction was possible in this worktree. This is an upstream defect in the pinned MIT source; no vendor code or licence files were changed.

### Batch 66 — Sophie vendored sound generator

Read `engines/third_party/schwung-modules/sophie/sophie.c` (637 lines) completely. Traced defaults and JSON state handling, one-shot voice allocation/stealing and per-voice patch snapshots, parameter key dispatch, dynamic metadata/state serialization, oscillator feedback and noise, pitch/amp envelopes, crush/drive, ring delay interpolation/feedback, multimode filter state, stereo output and host-global access. The file's SHA-256 matches the pinned `UPSTREAM.md` hash and is byte-identical to that upstream source.

**[P3, confirmed, high confidence] Sophie phase wrapping fails at supported low sample rates for high-frequency settings.** `sophie.c:87-91` wraps by subtracting or adding at most one `2π`, while `:456,462` permits `hz=18,000` and advances by `2π·hz/sample_rate`. The shim permits 8,000 Hz (`engines/src/schwung_shim.cc:111-114` allows 1 Hz–1 MHz), and the renderer accepts `--rate` without restricting the value (`engines/host/render.cc:942`). At 8 kHz and a parameter setting that reaches the 18 kHz cap, a float32 calculation gives increment 14.137 radians; after one subtraction the phase is 7.854 radians, still above `2π`, and subsequent samples grow rather than wrap (`7.854`, `15.708`, `23.562` …). The sine inputs therefore become unbounded and progressively lose phase precision during long playback. The normal FM-1 rate (~44,118 Hz) stays below the one-wrap threshold, so this does not affect the current device rate. `tests/test_engines_schwung.py` tests tuning only at the FM-1 rate and does not sweep alternate rates. No renderer was built or run.

**Optional dead-code candidate [P4, confirmed]:** `sophie_t.error[96]` (`:78`) is only read by `sophie_error` (`:426-430`) and has no write anywhere in the file; the registered `get_error` callback therefore always returns empty. Removing the field and callback is a safe small cleanup candidate if the upstream module is maintained locally; no vendor change was made.

### Batch 67 — Schwung ABI headers and module-local copies

Read the canonical `engines/third_party/schwung/plugin_api_v1.h` (507 lines) and `audio_fx_api_v2.h` (51), plus the PSX Verb module copies (`plugin_api_v1.h`, 225; `audio_fx_api_v1.h`, 40) and Sophie's trimmed `plugin_api_v1.h` (52) completely. Compared each module-local host/API layout with the shim's canonical types, including the legacy v1 prefixes, PSX Verb's v2 effect struct without the optional `on_midi` tail, Sophie's extra host callback declarations over the canonical zeroed reserved region, the fixed +120 reserved-tail assertion, and the separate optional split-render symbol contract. All copied headers' SHA-256 hashes match their module `UPSTREAM.md` tables. The matching source `module.json` files and provenance notes were read for engine/table context; global licence and data-corpus review remains pending.

No additional confirmed ABI defect was established: the shim checks each API version and required callbacks, reads only fields that are within each module's actual v2 struct, and the copied host callbacks used by these modules precede their divergent tails. The headers' broader Ableton Move host callback and optional voice-splitting material is not used by Lunar's shim; it was read for ABI boundary context, not treated as an implementation obligation. No licence files were changed, and no builds or tests were run.

### Batch 68 — Prior cleanup candidates independently checked

Rechecked the leads in `scratch/audit-2026-10-07.md` against this pinned baseline and the separate editor head. Confirmed that `sim/web/www/editor/model.js:416`'s `defaultValue` and `editor/sheets.js:14`'s `parseBlockKey` import have no baseline caller/use; both were removed on the editor branch (`861b725`). For the remaining low-risk candidates, AST loads are absent for `Fraction` in `tools/lunar_state.py:34`, `GPL_MODS` in `tests/test_app_state.py:21` and `tests/test_gpl_switch.py:37`, `Path` in `tests/test_engine_acid_bass.py:28`, `rms` in `tests/test_engine_drums.py:29`, `run_script` in `tests/test_seq_song.py:28`, and `pytest` in `tests/test_tools.py:6`. This is targeted confirmation of those imports only; those full test files remain separately pending in the coverage ledger. No removals were made.

Also rechecked three optional refactor candidates. `editor/chains.js:25` and `editor/model.js:614` implement the same percent-to-Q14 conversion with different float operation order; consolidation would need to preserve `chains.js`'s multiply-before-divide expression. `editor/model.js:500` hard-codes the current rack capacity 8 despite nearby `POSITIONS` metadata. `sim/web/www/worklet.js:204-210` allocates a seven-word array on each RAM poll before checking whether any value changed; any reuse would need to account for transfer ownership of `parts`. These are optional drift/performance candidates, not demonstrated user-visible defects. No source changes or tests were made.

### Batch 69 — Shared test harness and sequencer oracle helpers

Read `tests/__init__.py`, `tests/conftest.py` (48 lines), `tests/engine_helpers.py` (106), and `tests/seq_helpers.py` (209) completely. Traced the session-wide `subprocess.run` replacement and CPU/wall limits, GPL build agreement, renderer invocation and WAV decoding, zero-crossing pitch/RMS helpers, exact integer clock model, script time/command/reset semantics, and event/snapshot slicing. Confirmed the tests use `subprocess.run` and `check_output` paths (no `Popen`, shell command or direct `os.system` call found) that flow through the harness guard.

No harness or helper defect was established. The test guard is a targeted wrapper around subprocess APIs, not an OS-wide child-process sandbox. The helper suite was source-reviewed only; no pytest or builds were run. No source, device or licence changes occurred.

### Batch 70 — State codec canonicalization and fixture generators

Read `tests/state_canon.py` (272 lines), `tests/state_meta.py` (177), and `tests/state_random.py` (255) completely. Traced decimal exponent pre-bounds that prevent hostile huge-exponent allocation, exact decimal-to-float32 rounding, shortest ECMAScript-compatible float text, string/JSON escaping and layout, duplicate-key refusal, Q1.14 ties-away conversion and shortest reverse mapping. Reviewed metadata construction against the C-export test contract, parameter detent arithmetic and editor-only field projection. Traced seeded valid/loose documents across sound engines and pads, inserts, MIDI effects, effects chains, modulation racks/cables, FM6 slots, projects, clips and settings.

No confirmed defect was established in these helpers. The focused exponent and float32 boundary probes behaved consistently with their documented caps; the one metadata example is deliberately a small subset, so it cannot establish registry-wide generator assumptions. `fm1-state` and the renderer are absent from this worktree, so randomized two-implementation and save-coverage tests were not run. No source, device or licence changes occurred.

### Batch 71 — C metadata export

Read `engines/state/fm1_meta.c` (999 lines) completely. Traced JSON writer nesting/separator state, canonical string/float/integer encoding, parameter pages/aliases/retired ids, engine and modulation metadata, source group classification, effects/refusal/mark/telemetry exports, metadata id omission rules, and the CRC callback. Compared the output fields/order and numeric formatting with `fm1_meta.h`, the metadata schema, and Python construction expectations. Checked fixed writer depth against the actual document nesting and all stack buffers against their bounded inputs.

No confirmed output/schema defect was established by source review. **Concurrency hypothesis [P3, medium confidence]:** first concurrent calls to `fm1_meta_id_of()` / `fm1_meta_write()` race while `crc_put()` initializes its function-static `table` and `made` flag (`fm1_meta.c:961-973`); `fm1_meta_id()` also initializes `id`/`done` without synchronization (`:985-994`). The shared writer APIs are public, but current in-repository paths are CLI, one simulator worker, or before audio starts as documented in `fm1_meta.h:79-90`; I found no present concurrent first-call route. Treat this as a thread-safety assumption to verify if callers expand, not a confirmed reachable product defect. No compile or runtime test was possible because generated binaries are absent. No source, device or licence changes occurred.

### Batch 72 — State fuzz harness and end-to-end codec tests

Read `engines/state/fuzz/state_fuzz.c` (400 lines), `engines/test/meta_number_test.c` (54), `engines/test/state_alias_test.c` (80), `tests/test_engine_metadata.py` (158), and `tests/test_state_whole.py` (401) completely. Traced the fuzz target's 300 KiB input cap, buffer growth and cleanup, CRC-repaired binary mutations, whole/fragmented JSON equivalence, canonical/binary fixed points, sequencer import/export fixed points and failure artifact. Reviewed metadata CLI/canonical/schema comparisons and whole-state coverage for each save format, known missing modules, aliases, future parameter ids, pad kits, FM6 voices and saved-audio parity. Cross-checked the state and metadata harness Make fragments, previously reviewed in batch 25.

No confirmed defect was established in these harnesses or test contracts. The alias test utility's fixed 1 MiB input buffer exceeds the format's largest accepted file cap, so the truncated-read path cannot turn a too-large state into a valid accepted input under the reader's byte limits. Test suites and native harnesses were source-reviewed only; generated executables and pytest are absent, so runtime coverage is not claimed. No source, device or licence changes occurred.

### Batch 73 — Codec hostility and schema contract suites

Read `tests/test_state_codec.py` (666 lines) and `tests/test_state_schema.py` (363) completely. Traced native/Python record parity, memory/import constraints, canonical and binary fixed points, deterministic save coverage, exact float32/Q1.14 comparisons, refusal/repair matrices, duplicate-key overflow policy, RAM/rate refusal, binary truncation and bit flips, JSONTestSuite expectations, seeded fuzz and compressed link caps. Reviewed schema validity, canonical member order, example names and values, sequencer-core set/clip exports, metadata registry coverage and all Q1.14 percent spellings.

**Confirmed test gap [P3, high confidence]:** `test_deflate_interoperates_with_zlib` claims to reject a DEFLATE match more than 4 KiB back (`tests/test_state_codec.py:591-607`), but the local `bits()` encoder is never called. The produced zlib stream consists of 5,000 stored literal bytes plus an empty final block; a local zlib decode confirms its output is 5,000 bytes, while the test asks `ls.inflate(..., 5100)` to produce 5,100. The expected refusal can therefore pass on decoded-length mismatch without exercising the distance/window check. This leaves the intended C/Python 4 KiB-distance contract unverified by this test.

No additional confirmed product defect was established by these test sources. The state and schema suites could not be run because `fm1-state`, `fm1-seq`, `fm1-render` and pytest are unavailable in the audit worktree; prior targeted Python-only validation remains recorded above. No source, device or licence changes occurred.

### Batch 74 — Desktop state rendering and parameter/name contracts

Read `tests/test_state_render.py` (226 lines), `tests/test_engine_names.py` (153) and `tests/test_engine_params.py` (355) completely. Traced saved sound state versus CLI-flag rendering, loaded state round trips, binary equivalence, RAM/missing-engine/full-rack refusal and clip-to-set lane placement. Reviewed enum append-only records, alias/retired-uid and known-id checks, generated registry consistency, full parameter UID/flag fixture coverage, focus/per-focus save behavior, native versus Schwung UID ranges, LOG/unit/abbr rules and the API v4 parameter-contract selftest path.

No additional confirmed product defect was established. The engine metadata and render tests depend on native executables that are absent here, so no runtime or audio parity result is claimed. No source, device or licence changes occurred.

### Batch 75 — Engine API and editor metadata tests

Read `tests/test_engine_api_v3.py` (299 lines), `tests/test_engine_api_v4.py` (82), `tests/test_engine_host.py` (129), and `tests/test_engine_editor_meta.py` (376) completely. Traced transport callbacks and beat frame expectations, v2 compatibility, LOG parameter/lock interpolation and modulation behavior, UI encoder/bar rendering assertions, focused get/copy/replay restoration contracts, bad-sample limiter recovery, initial-memory independence, parameter extrema and bend/live-change paths. Reviewed editor metadata schema/version field ordering, source groups and ranges, module layout ids, runtime curve samples, refusal/page/group/telemetry stability, metadata CRC and GPL-on/off checks.

No additional confirmed product defect was established in these test sources. Their native renderers, simulator and refusal/selftest tools were not run in this worktree. No source, device or licence changes occurred.

### Batch 76 — GPL build gates and Acid Bass coverage

Read `tests/test_ci_pins.py` (35 lines), `tests/test_gpl_switch.py` (262), and `tests/test_engine_acid_bass.py` (355) completely. Traced CI browser/package-version pinning, switch-on/off generated build selection, dependency-file and object-symbol checks, license/source directory mapping, page notice and build-record checks, and scenario GPL labels. Reviewed Acid Bass upstream-vendoring checks, C oracle parity on 16-sample scheduling across rates/block sizes, parameter-to-unit mapping, mono slide/retrigger/release, velocity accent, pitch bend and per-note offsets, latch/smooth paths, extreme inputs, idle quieting and the realtime cost bound.

No additional confirmed defect was established in these test sources. The GPL switch tests invoke native `make -j4`, inspect built artifacts, and run licensing metadata paths; none were run here. The Acid Bass native/audio tests also remain unexecuted. No code or licensing report was changed.

### Batch 77 — Comet Kit integration and audio tests

Read `tests/test_engine_comet_kit.py` (690 lines) completely. Reviewed its GPL-only gate, source-vendoring and generated-sample reproducibility checks, 16-sample oracle parity, 9W9 pot mapping, all-pad rendering, voice lifecycle and hat choke assertions, latch/smooth behavior, block/memory/rate invariance, extreme-value and subnormal checks, cost bound, and the 8-bit mu-law cymbal provenance and SNR calculations.

No additional confirmed defect was established in this test source. The oracle, renderer and generated int16 reference header are unavailable in this worktree, so no audio parity or runtime results are claimed. In particular, source-review of the loudness/SNR expectations is not a substitute for running their fixtures. No source, device or licence changes occurred.

### Batch 78 — Crater Kit integration and audio tests

Read `tests/test_engine_crater_kit.py` (522 lines) completely. Reviewed GPL gating, upstream sample equivalence, upstream host-test integration, the 16-sample oracle, 8W8 pot and semitone mapping, all-pad loudness/tail coverage, channel-sharing and choke behavior, velocity/bend/latch/ramp paths, rate and block restrictions, extrema/cost checks, and writable-global inspection.

**Confirmed test gap [P3, high confidence]:** the test function named `test_tune_is_in_semitones_on_every_pad` checks rendered pitch only for the kick and low tom (`tests/test_engine_crater_kit.py:306-315`), and the `--fields` oracle provides exact Tune-law assertions for only four pads (kick, low tom, cymbal and cowbell; see settings at `engines/test/crater_oracle.cc:275-279` and assertions at `tests/test_engine_crater_kit.py:213-223`). This does not establish audio semitone behavior across the remaining voice families/pads despite the suite's top-level “every pad” claim. A regression in a pad-family Tune conversion or sound's tune response could therefore escape these assertions. Source inspection of `ApplyTune()` (`engines/src/crater_kit.cc:249-260`) did not show a confirmed implementation defect.

No other confirmed defect was established in this test source. Native oracle and audio tests were not run because generated tools are absent. No code, device or licence changes occurred.

### Batch 79 — Shapes edge and master-FX hostile/switch tests

Read `tests/test_engines_shapes_edges.py` (144 lines), `test_engines_shapes_hostile.py` (74), `test_engines_fx_hostile.py` (107), and `test_engines_fx_switches.py` (159) completely. Traced Braids edge-case pitch/timbre clamps across shapes, hostile between-value schedules and memory fills, master-effect block/rate/input/extreme recovery contracts, and fast switch modulation against held-control step bounds and effect ceilings.

No additional confirmed defect or material coverage gap was established from these four test sources. The required `fm1-render`, hostile-effect tools and sanitizer build are unavailable here; the tests were not executed, so their numerical/audio bounds remain source-reviewed rather than reproduced. No code, device or licence changes occurred.

### Batch 80 — Gate, Hall, idle-path and Isolator suites

Read `tests/test_engines_gate.py` (597 lines), `test_engines_hall.py` (358), `test_engines_idle.py` (316), and `test_engines_isolator.py` (285) completely. Traced Gate host guards, stereo/key-filter and detector timing references, look-ahead latency and switch schedules; Hall size/pre-delay/diffusion/decay/freeze and tail contracts; idle/wake warm-up against non-idle reference builds, modulation-driven awake behavior and known lost-short-lock tradeoffs; and Isolator Linkwitz-Riley response, kill masks, exact-unity path and crossover glide landing.

No additional confirmed defect or material coverage gap was established in these test sources. The associated renderer and selftest tools are unavailable, so none of their long audio/reference tests were run. Their metrics and pinned hashes remain claims recorded in source, not re-measured by this audit. No code, device or licence changes occurred.

### Batch 81 — Plaits envelope/heavy and Braids FX reference suites

Read `tests/test_engines_plaits_env.py` (397 lines), `test_engines_plaits_heavy.py` (502), and `test_engines_reference_braids_fx.py` (886) completely. Traced Plaits page-3/low-pass-gate behavior against upstream at native and FM-1 rates, all-slot envelopes and reference negative controls, Six-Op bank/name provenance checks, every model/patch sounding/tuning, voice pressure/release and channel behavior, Shapes' 47-wave reference comparisons and edges/randomness/retrigger/release, and the Plate/Ensemble/Diffuse coefficient, rate-compensation, stereo and dry/wet models.

No additional confirmed defect or material test gap was established in these suites during source review. Their external reference executable (`fm1-ref-braids-fx`), engine renderer and audio binaries are unavailable, so none of the sample-level comparisons were run. Clone-dependent vendor parity tests may skip if the reference checkouts are absent; those skips are explicit. No code, device or licence changes occurred.

### Batch 82 — Plaits reference harness, resampler and Clouds Room tests

Read `tests/test_engines_reference_plaits.py` (1,757 lines), `test_engines_resampler.py` (506), and `test_engines_reference_room.py` (282) completely. Traced slot/patch mappings, exact and statistical comparison criteria, fixture caching/parallel process orchestration, vendored closure digest, 32.32 input-pull and native-block event placement, pitch/timing and negative controls, wrapper-self resampling and voice-freeing scenarios; reviewed resampler kernel generation/reference tables, FIR boundary/finite-input/window and spectral/alias constraints, Shapes resampled comparisons; and Clouds diffuser/reverb coefficient mapping, Room additions, stereo, host-rate compensation and decay tests.

No additional confirmed defect or material coverage gap was established by source review. The renderer, reference executables, and resampler tool are unavailable, so runtime comparisons and reported spectra/timing are not independently reproduced. The large `--sixop-sweep` and benchmark/calibration commands are documented in the test file but were not run; they invoke native builds and high-volume rendering. No code, device or licence changes occurred.

### Batch 83 — Crush, DJ Filter and FX3 hostile tests

Read `tests/test_engines_crush.py` (319 lines), `test_engines_djfilter.py` (462), and `test_engines_fx3_hostile.py` (70) completely. Traced Crush's sample-hold/quantizer/tone/mix tests across block sizes, rates, channel state, parameter extremes and bad audio; reviewed DJ Filter's parameter/analytic-response contracts, changing controls, block-size invariance, zipper/click/tail bounds and host-rate refusal matrix; reviewed hostile input constraints for the FX3 host effects.

No additional confirmed defect or material coverage gap was established in these tests. Their renderer and hostile tools are absent, so the audio and numerical bounds were not reproduced. No code, device or licence changes occurred.

### Batch 84 — Core engine smoke, Comb split and Compressor tests

Read `tests/test_engines.py` (136 lines), `test_engines_comb.py` (141), and `test_engines_comp.py` (568) completely. Traced registration metadata, macro/Shapes pitch and sound checks, voice release, limiter/instance-size and in-place FX contracts; reviewed Comb's UID preservation and byte-pinned type split, block/memory invariance and hostile-value cases; followed Compressor's static gain curve, detector/release laws, handover/glide, Auto Gain onset ceiling and the large clip-safety matrix.

No additional confirmed defect or material coverage gap was established in these test sources. The cited renderer and probes were unavailable, so numerical/audio assertions were not independently executed. No source, device or licence changes occurred.

### Batch 85 — Drive and Echo integration tests

Read `tests/test_engines_drive.py` (636 lines) and `test_engines_echo.py` (374) completely. Traced generated quintic Drive curves against the declared knot design, alias reduction/ADAA, Type and parameter glides, DC compensation, block/memory/rate/input guard behavior and full effect-chain paths. Reviewed Echo delay and fractional timing across its full-clock and slowed-clock regions, ping-pong/feedback/mix/tone/wow laws, maximum feedback/tail truncation, invalid input recovery and selftest coverage.

No additional confirmed defect or material coverage gap was established in these tests. Their renderer and selftest were unavailable, so the measured acoustic/timing assertions were not reproduced. No code, device or licence changes occurred.

### Batch 86 — EQ, Filter and Fold tests

Read `tests/test_engines_eq.py` (370 lines), `test_engines_filter.py` (442), and `test_engines_fold.py` (358) completely. Traced EQ registration and exact zero-gain bypass, independent RBJ cookbook response calculations, hostile inputs, modulation glides and response hash assertions; reviewed Filter's six retained circuits plus the separate Comb tool path, response/self-oscillation/drive sweeps, crossfade, state flush and host limits; reviewed Fold's symmetry/shape/tone laws, ADAA alias comparison and runtime parameter/rate cases.

No additional confirmed defect or material coverage gap was established in these suites. Their renderer and response tools are unavailable, so none of the acoustic claims were reproduced. No code, device or licence changes occurred.
