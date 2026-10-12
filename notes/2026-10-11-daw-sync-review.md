# PR146 independent implementation review [verified]

Read-only review against origin/main `621490b9553b17f23add077f8dd79c01b5c15db8` at feature HEAD `a095501d9174f3849cbe7cb2b7cbb24c400812db`, branch `feature/2026-10-11@midi-sequencer-workspace`. The parent owns concurrent source fixes, checkpoints, push and merge; no source edits/commits/pushes/rebuild/device writes by this review. Shared layout-only CSS changes were excluded. Exact reviewed content hashes: `code-review-hashes.json`; this matters because editor/sequencer JS has concurrent uncommitted density work. Parent's previously verified pushed checkpoint is `1141e12b5ea585d6be2dcbd71484d281e7d5e3b2`; review HEAD backup status belongs to parent.

## Findings

1. **P1 — sequencer undo can delete subsequent native/panel edits.** `sim/web/www/editor/sequencer-host.js:75` restores an entire historical project through `loadChecked`. A JSON-parsed history snapshot has no `versions` WeakMap entry, so the version guard at line33 does not compare it against the state on which that history entry was created. The load at line52 instead fences against the *current* snapshot hash. This detects changes during the transaction but deliberately accepts unrelated changes made before undo starts. Reproduction creates one browser note, then another native/panel note, and invokes undo: accepted current hash4321; loaded project contains neither note. Saved `review-history-repro.mjs` and `.log`, run with Node26.10.0. Require current canonical state to match the history entry's expected after-state (before-state for redo), or apply a guarded sequence delta into the current project. Preserve the final audio-thread hash check. Do not silently overwrite subsequent edits.

2. **P2 — panel sequencer edits leave the DAW model stale.** Native edits increment `seq_gen` (`sim/web/src/fm1_app.c:3653`, live recording at3723), but `sim/web/www/worklet.js:419` posts no content revision, and `sim/web/www/editor/editor.js:157` only calls the transport-only `sequencer.update` (`sequencer.js:691`). Add/clear/edit a note or lock through native panel gestures while viewing the piano roll: its notes/lanes are not re-fetched until another action triggers refresh. Existing edit handlers fetch fresh native data and guard note identity, which limits wrong-target mutations, but does not satisfy interchangeable visible editing. Expose a content invalidation/revision signal and refresh the model on native content changes; avoid treating the always-changing playback tick as content revision. This also supplies useful history conflict detection for finding1.

3. **P2 — hostile MIDI can create an unbounded practical preview/batch workload.** `sim/web/www/editor/midi-import.js:68` makes one part per track/channel/program/bank tuple with no part count bound beyond the much larger event/note limits. `sequencer.js:603` bounds each individual file only, without batch count/aggregate bytes. Line604 creates every mapping row, then line615 builds every DOM row and line616 scans the full part list for each row. A valid150,026-byte MIDI with10,000 distinct parts is accepted (saved `review-midi-parts-repro.mjs` and `.log`); it causes roughly50million lookup comparisons plus tens of thousands of interactive DOM nodes on the main thread, and multiple such files have no aggregate ceiling. Enforce reasonable explicit part/file/aggregate-byte limits before allocating preview rows, use an indexed lookup, and paginate or otherwise bound rendered rows. Fail explicitly rather than silently omitting parts. The repro proves parser acceptance; full browser UI stress was intentionally not executed.

## Reviewed behavior and existing evidence

- Standard MIDI bounded binary parsing, chunk/event VLQ/running-status/error handling, sustain/repeated-note lifetime, tempo/time-signature rejection or explicit warnings, mapping, section deduplication and native note/lock/trig/gate/song capacity refusal. Unknown sequencer tags cannot silently pass the native round-trip preservation check.
- Canonical movy1 parsing/writing, all modeled tags, timing/speed semantics against native `scene_bars`, byte ceilings and native shadow round-trip enforcement. Clip scene bars intentionally match the native raw clip-length behavior.
- Native incremental level commands, target isolation for synth/insert/master/mix, lock/modulation/base restoration and sample-frame queues, no-mod guards, stem contribution masks, bounded telemetry masks/arrays/taps and disabled subscription behavior. No additional confirmed blocking C defect found in this bounded review.
- WAV worker lifetime/cancellation, ACK backpressure, project/duration/RIFF/file limits, deterministic frame stop, exact lengths, real stem route masks and 8-channel PCM encoding. Existing export tests establish meaningful execution rather than fixture-only formats. File-byte limits are not a guarantee of total JS heap usage: each finalized ArrayBuffer temporarily copies through `slice`.
- UI edit transaction/native hash fencing, fresh-note identity checks, incremental fader drag history and sequence history restoration. Changing density CSS was excluded.

No rebuild or duplicate full suites. Earlier exact-module receipt remains `README.md` / `receipt.json`: module SHA256 `f163c1b5799bb6109718993600df4c3f7884ffca055a2e4df558cc8007e65219`;27 MIDI tests, actual-Wasm export and meter checks, clean four-demo imports and RAM budgets. This review executed two focused source-level repros only. Review source hashes are sufficient to identify which results need refreshing after parent fixes.

## Limits and next dependency

Rarefaction/Serena status/config were checked. Both select the shared primary checkout, not this worktree; retargeting could disrupt other active agents. Used bounded file/symbol/reference inspection instead, no semantic project activation or server restart. cpp index is a fallback without the actual pi32v2 compile target. No device, physical SRAM/ABI, listening, browser stress, or hardware runtime acceptance claim.

Parent should fix finding1 before merge, address the panel invalidation and MIDI preview bounds, add focused regressions, and rerun changed JS tests plus exact-head required CI. Parent has separately identified/fixed metadata schema/fixture mismatches; those are not counted here. Source changes may require rebuilding Wasm if a native revision bridge is added. Parent owns final checkpoint/push verification and required listening/hardware gates.

## Resolution and final focused verification [verified]

The parent authorized fixes after the read-only review. All three findings above are resolved in the inspected candidate; no additional confirmed blocking C defect emerged from the bounded review.

- P1: `sequencer-host.js:62` compares canonical current whole-project state with the history entry's expected after-state for undo and before-state for redo (`:104`). Key order and movy1 textual ordering are normalized. A later native note, sound-level change, or other saved project difference now refuses restoration before shadow checking, preserving that later edit. The existing final `expectedHash` audio-thread fence at `:81` still rejects a change during validation. The editor restores its history cursor after refusal. History does not merge unrelated later changes; it explicitly refuses a destructive restoration.
- P2 native synchronization: root added `fm1w_seq_gen`/its export; `worklet.js:405` compares that optional native generation and publishes content changes immediately, separately from position-only throttling. `sequencer-host.js:29` coalesces generation bursts for100ms and calls the settlement callback; `editor.js:140` invalidates the model even while hidden and refreshes only when the workspace is visible. No periodic project snapshot polling was added. Older modules without the optional getter retain previous transport behavior. Parent owns the C getter/export/rebuild; sibling owns the editor callback.
- P2 MIDI bounds: independent review of root's `midi-import.js:4` limits and `sequencer.js:604` preflight confirms at most16files,16MiB perfile,32MiB aggregate before any file read, at most64parts in each parser and across the batch before preview rows, and indexed planner/preview lookups. Oversized data errors explicitly; instruments are not silently dropped.

Focused checks: `node --test sim/web/test/sequencer-host.test.mjs`8/8pass, including concurrent-validation refusal and old-Wasm fallback; `node sim/web/test/midi-import.mjs sim/web/www`30/30pass, including exact boundaries and hostile part/batch inputs. Source/test syntax and `git diff --check` pass. These local Node checks used26.10.0.

New separate `sim/web/test/sequencer-sync.mjs` passed all four actual AudioWorklet/Wasm checks in Chromium, Firefox and WebKit (12check executions): clean UI undo/redo, visible native-command-path note refresh, hidden invalidation with zero projectSnapshot calls then updated notes on reopen, and stale undo/redo refusal with native notes/history cursor intact. The command enters the same native sequencer command handler as panel edits; this is not a physical button-matrix test. Firefox used an isolated PulseAudio null sink. All three recorded zero page errors.

Exact module SHA256 `2a2ad121431f6e7fac5aa186d00eb0b75848187441ffe0d4ec4222451ed65cc3`, matching parent's rebuilt/fetchedg module. Browser stage `/home/claude/mvave-fm1/final-sequencer-sync-20261011`, Docker `mcr.microsoft.com/playwright:v1.63.0-noble`, batch cgroup,2CPU/2GiB RAM/2GiB swaplimit. No shared semantic-session retargeting, device writes, additional native rebuilds, or duplicate full suites by this fix subtask. Saved browser receipts/logs and pre-fix repros: `scratch/final-native-acceptance/`; source manifest `sync-fix-hashes.json`.

Branch remains `feature/2026-10-11@midi-sequencer-workspace`; inspected working HEAD `a095501d9174f3849cbe7cb2b7cbb24c400812db`. Sources below include authorized uncommitted parent/sibling integration, so HEAD alone does not identify this candidate. Parent owns checkpoint/push verification, addition of the focused scripts to CI, exact-head CI and integration/merge. Required owner listening/hardware acceptance remains separate.

### Final candidate content hashes

- `sim/web/www/editor/sequencer-host.js`: `b96abb011c124262f1df9e102aff12a884e9301f9d73234cede21cc7293d59a7`
- `sim/web/www/worklet.js`: `bb106094956798ebf2e70fd99d0f1015adb0f0b580a50d6d9d959472b600880e`
- `sim/web/www/editor/editor.js`: `71f0294c0c2ce121c4a828c2fe32eee91e8a5ac0dac96af0a69f4a383a2f624a`
- `sim/web/src/fm1_web.c`: `6a87e8628a0b4b5ca3821f298295a4fa284c3e5267ddea9292b63eebc94df9dd`
- `sim/web/mk/sim.mk`: `49e5dc4f144d430d4532e85c23970b2bf14871d058afcf6916211c581b1f900a`
- `sim/web/www/editor/midi-import.js`: `d020aa65139bdbd6c5bc83ea76e27adb88de1fb7bb2ed8ad0b6ae5a19b856761`
- `sim/web/www/editor/sequencer.js`: `58ee6c7a039b4c00ceb128669dbe7273dc482c73f78eef1bd17d651b3672e2f7`
- `sim/web/test/sequencer-host.test.mjs`: `5b39eb831bc76be9a1ab321029a455ebb82a6e6dc272b5019e99441c739a0e30`
- `sim/web/test/sequencer-sync.mjs`: `dcb62016a1f36273e9321bde66c0b19b07cd099008c6229d2d0a3935d50f5f54`
- `sim/web/test/midi-import.mjs`: `10f66a8594b857b75d037a2cb5fd719bfea80d314994ae9c19134441bfa796e3`
- `sim/web/www/fm1.wasm`: `2a2ad121431f6e7fac5aa186d00eb0b75848187441ffe0d4ec4222451ed65cc3`
