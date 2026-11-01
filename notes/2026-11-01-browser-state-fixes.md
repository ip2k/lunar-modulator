# Browser state fixes — 2026-11-01

Personal Lunar work; release-goal lane assigned by the Mac coordinator.
Base: `b831724fcf413720aaa036dac742a382cdfaa93c`.
Branch: `fix/2026-11-01@browser-state-fixes`.
Worktree: `/Users/likwid/.codex/worktrees/lunar-browser-state-fixes-20261101`.

## Confirmed failures and changes

All four failures were reproduced in pinned LAN Chromium against the original
source before its corresponding fix [verified]. The final baseline run is
`red-final.log`; earlier harness runs corrected a missing lunar version marker
and restored Song/Mixer navigation after a normal project load. Those earlier
harness errors are not claimed as product failures.

1. A sound with `lunar: "1.0"`, `kind: "sound"`, and
   `sound: { inserts: {} }` receives C's BAD verdict but its arrival preview
   calls `.map` on the raw object. Rendering throws, leaving no Dismiss.
   `project.js` now skips raw-payload preview for BAD and shape-checks the
   inserts list before mapping. A BAD card offers only Dismiss; it sends no
   load and preserves the live project [verified]. Normal self-exported
   sound data still offers the normal Load card [verified].
   Source commit: `9be61e751d376a7060f8cd2496cfbc57bc1f2bba`.
2. Solo retains eight saved mutes after loading a new project, so the next
   Solo press restores another project's mutes. The host now exposes the
   existing browser project identity, `files.pid`. Normal same:false project
   loads create a new identity even when canonical contents are identical;
   sequencer transactions use same:true and preserve that identity [verified
   against files.load and sequencer-host.loadChecked]. The sequencer binds
   Solo restoration to the observed identity and canonical snapshot, permits
   unchanged refreshes and acknowledged edits through its own apply path,
   and invalidates it on replacement or external content changes. The edit
   path also checks before using a saved baseline, rather than depending on
   the UI having refreshed first [verified].
   Source commit: `5729e32caa35d42899d5e37cf7e54e83e1fee139`.
3. setView snapshots an entire project, asynchronously packs it, then loads
   it without a content fence. A native tempo edit made while packing is
   overwritten. It now uses the existing coherent projectSnapshot text/hash
   and supplies expectedHash to state-load. No retry or stale reload occurs
   on rejection. The worklet's existing fence also rejects pending editor
   batches; this lane does not change that protocol [verified source]. The
   focused regression pauses the actual shadow pack message, sends a native
   tempo edit, observes its new hash, releases the old pack, and verifies
   refusal plus preservation of the new native hash [verified runtime].
   Source commit: `67f707d22f3aac02758db931bb63953ff3940f56`.
4. Closing the editor port retains inflight edits, tags, pending snapshots,
   and their callbacks. A later session can stay permanently busy. detach
   now invalidates snapshot continuations, settles waiters, clears pending
   session data, and resets inflight. Each attached message handler checks
   its captured port and node identities, so an already queued old handler
   cannot acknowledge a new session's work [verified]. The test retains the
   actual old callback, reconnects the editor, and invokes that stale ACK
   after marking new work inflight: the new count stays unchanged; fresh
   snapshots still populate the mirror [verified runtime].
   Source commit: `8aec2f604c7629ab45294c8a59faa4dd14b8ce35`.

Each source commit was immediately pushed using an explicit branch refspec
and verified equal with origin via ls-remote [verified]. No action() changes
were made in sequencer.js: PR151/ca6f3c14's separate synchronous-lock patch
must remain intact during parent integration.

## Verification

`sim/web/test/browser-state-regressions.mjs WWW OUT` runs four focused cases
with real browser Worker/AudioWorklet/WASM. Baseline: all four fail for the
confirmed reasons above. Fixed source: four pass, no page errors [verified].
Solo checks unchanged forced refresh, own tempo edit, restoring the original
mute array, new project identity, identical-content reload, an external
mute edit, an ordinary native mute command, and real sequencer Undo. BAD checks native refusal, Dismiss-only actions, byte-identical
live state, dismissal, then a valid arrival card.

[verified] Existing sequencer-ui.mjs passed desktop/mobile, note visibility,
offset-loop navigation and mock-host interactions. Full files.mjs passed
files, unavailable storage, load links, hash links, embed API, localhost
policy, and layout, with no page/console errors. This also retains normal
view/embed operations alongside the new stale-view rejection.

The final expanded focused run is `green-expanded.log`; its JSON report and
the original four-failure report are retained as browser-state-green.json
and browser-state-red.json. Pending-editor-batch rejection is source checked
in the existing worklet fence; the new runtime race covers an applied native
edit and actual asynchronous shadow packing, rather than synthesizing that
pending queue branch.

Runtime module: tracked `sim/web/www/fm1.wasm`, SHA-256
`72e7ada150bb4b7dd385839fa9ae49cf15c5fd673cdfb027c3931b63ca21a13e`.
No C/WASM inputs changed; this lane does not regenerate the module/record.
JS syntax and git diff whitespace checks passed [verified]. Required CI and
parent merged-source checks remain integration gates. No native full-pytest,
ASan, 32-bit or physical/listening acceptance is claimed.

## Tools, resources and lifecycle

Project AGENTS.md/CLAUDE.md were read; existing personal/non-commercial scope
and pre-approved LAN skill remain in force. Local user-facing Chrome access
is disabled in Work settings and was not bypassed. Tests ran only in the
existing authorized LAN CI environment: Playwright v1.63.0 / Chromium
153.0.8010.12, CPU0–3, at most 4 CPUs, 6 GiB RAM/swap, docker-batch.slice,
--network=none, --rm, labels project=mvave-fm1-firmware and
session=browser-state-fixes-20261101. No device/USB/MIDI/flash/reset action.

Rarefaction's session root remains the primary checkout; absolute worktree
orient/scope calls were rejected as outside its root. No shared root switch
was made. Serena located the actual absolute worktree's refresh symbol;
file inspection and real runtime behavior supplied the missing scoped graph
coverage. Neither tool is claimed to resolve Worker/WASM or port-lifecycle
edges. Tool limitations were handled with pinned source inspection.

Remote stage: `/home/likwid/datasets/lunar/browser-state-fixes-20261101`.
Small evidence destination: ignored local `scratch/browser-state-fixes-20261101/`.
Collect JSON/log evidence, remove this lane's remote reproducible stage after
containers exit, and retain the clean worktree for parent review. Mac free
space at start: 1,124 GiB, above the 500 GiB floor.

## Next dependency

Parent reviews/cherry-picks these incremental commits plus the regression
and note commit, preserves PR151's disjoint action() patch, runs integrated
checks, and wires the new focused test into its browser CI invocation.
No PR or merge is opened by this lane. Required owner visual/hardware gates
remain with the coordinator.

[verified] Cleanup complete: all own containers exited; exact remote staging
path removed after collecting small JSON reports. No persistent service,
installed dependency, compiled artifact or shared cache was created. Retained
local evidence is 124 KiB of logs/JSON under the ignored scratch path.
Worktree remains for parent review; parent should remove it once integrated.
Mac free space at finish: 1,119 GiB, above the 500 GiB floor. The source commits
above are fully backed up; this final regression/note commit is also pushed
and its exact remote SHA is reported in the parent handoff.
