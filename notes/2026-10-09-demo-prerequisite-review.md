# Demo prerequisite review — 2026-10-09

Read-only review against panel-protocol-link 7385bee77d70e81d0bf588e7479c016ee5a9e154
(main cafd77e0 base) and PR121 brief 32d4747f. No composition or hardware action.
Parent owns the consolidated repository handoff; copy this checklist into its next
meaningful checkpoint rather than resetting engine CI with a docs-only push.

## Contracts already present [verified: source/test inspection]

- Project format 1 carries four sounds, inserts/MIDI FX, two master slots,
  modulation, DX7 bank, sequencer set and panel session. Four master slots/sends
  are a planned future format, not required to implement this brief.
- Eight tracks/eight scene columns, named scenes and `sg` song chains already
  exist. Song chains allow 64 scene presses; adjacent repeats fold. Blank scenes
  park; `se 2` stops at the end. Manual scene takeover detaches the active song.
- Default sequencer budgets: 1536 notes, 1536 locks, 256 trigs in total;
  simulator bridge event capacity 272 per block. JSON inflated project cap
  262144 bytes, set 65536 bytes, string 16384 bytes.
- Native fm1-render --load plays a loaded project's set automatically; explicit
  --seconds controls output duration and must include the intended tail.
- Browser library uses explicit files.js example entries and byte-identical
  authority copies in engines/state/examples and sim/web/www/examples. Existing
  autosave/pending-link restore takes precedence; do not replace it with a demo.
- Full project codec save/load/save tests exist. Native renderer intentionally
  omits panel session in saved projects (test_state_render.py), so it is not a
  lossless factory authoring/export route for that session.

## Evidence limits and validation traps [verified: source/test inspection]

- test_seq_song.py:635–689 tests a 116 BPM, 116-bar, four-minute chain with
  test-sine; native renderer event log matches sequencer tool, zero dropped and
  hung notes. This proves chain mechanics, not four complete arranged projects.
- test_state_whole.py:119 tests a guide-like 1444-note project codec cycle;
  :257–283 proves six-second whole-project JSON/binary audio equality. Neither
  is a full-song complete-chain audio or admission receipt for future assets.
- fm1_sim_render.c:215–261 state_load returns success after reading a file even
  if the application refuses its contents; load.ok/code/left_out/skipped must
  be asserted. Exit zero alone is insufficient.
- fm1_sim_render.c:5260/:5424 makes implicit transport start depend on --seq,
  not --load. Start loaded demo playback explicitly (panel PLAY or command),
  and assert actual note/transport activity. Its sequencer summary is conditional
  on use_seq, so arrange a command script if needing those counters.
- parity.mjs:377 checks application Wasm load succeeds, but new complete demo
  scenarios and full-duration validation still need to be added after assets.
- scenarios.json:769–772 already supplies `project-load-play`: First orbit
  loaded with state/play.verbs through the application/native/Wasm parity legs,
  for four seconds. Extend that existing complete-chain contract for each new
  asset and its entire duration; no new generic playback architecture is needed.
- Audio-loopback runner supports up to 300 seconds but its music path currently
  selects First orbit; existing captures cannot be cited as demo-song captures.

## Remaining gates before/demo completion

1. Integrate the completed engine/source streams by normal history merges into
   one combined candidate, then perform one actual final engine/Wasm/metadata/
   golden regeneration against that integrated source. Validate exact source
   hashes and exact-head CI; do not select prebuilt branch artifacts or claim
   candidate evidence is a `main` merge.
2. Generate four original deterministic projects from the PR121 brief, with
   original names/credits, seeds, at least four distinct named scenes, 3–4 minute
   chains, four sounds/eight tracks. Use the distributable MIT/BSD profile or
   explicitly label a separate GPL profile. Avoid incompatible simultaneous
   parameter locks on shared sound units. Keep all asset budgets within limits.
3. Check actual integrated registry admission without --without: no unknown IDs,
   refused objects, omitted content, skipped records, memory overflow or event
   loss. Include JSON/binary canonical roundtrip and panel-session preservation.
4. Add authority and served files plus explicit library entries, schema/license
   and copy equality checks. Verify load/play/stop/save/reload and scene takeover
   in browser without overwriting an existing user's autosave.
5. Render each entire song plus release/effect tail through native engine and
   actual simulator/Wasm full chain. Check duration/end transport, event count,
   no refusals/drops/hung notes, actual RAM admission, finite samples/peak and
   deterministic seeded repeats. Use the simulator's own admission/event limits,
   not the desktop renderer's more generous event capacity alone.
6. Listen through each full arrangement and transitions in the served browser.
   Automated Safari/browser UI checks and focused audio captures exist, but
   the owner's native Safari by-ear result remains unresolved:
   "Sound 2 A had a few small crackles when i switched to it" at localhost8778,
   root 35c37940, First orbit 116 BPM. PR128 has automated capture evidence,
   but no passing owner Safari retest. Preserve this distinction from future
   composition/listening receipts and hardware proof.

## PR134 bounded review

No material issue found in RAM-only protocol capture/reset/hash/bounds or linked
layout validation. Actual linked 1212-byte flash/8400-byte RAM reservation is
supported by the saved target report/disassembly/test receipt. SP and SSP have
4096-byte reservations and 16-byte guards. Default inert profile and staging
reject SSP-bearing variants; no MMIO, real wait, installed image or runtime
observation is claimed. The 0x01c02000 RAM reservation overlaps loaded stock SPL
body, so it must not be called proven private RAM. Remaining inherited state,
exceptions, secondary core, clocks/cache/watchdog, physical transport, panel and
full instrument integration gates remain open. Changed files already end LF.

Both semantic MCPs used for firmware bounded review; Rarefaction source fallback
and engine file inspection used for this checklist because Serena's engine root
did not initialize a language server. No ABI proof inferred from clangd.

## Follow-up status (2026-10-10 UTC)

The combined Warble/Repeat/PSX source candidate is built and passed its
108-scenario simulator matrix. Root reports 24 non-test effects and
independently verified the committed Wasm build record and matching source
hashes. This is not yet a `main` merge or an installable firmware claim. On
standalone PR137 head `e1416ac`, Ubuntu and macOS each failed two integration
checks: Repeat Hold had no pinned list entries, and the checked-in metadata
example differed from built metadata. The combined candidate later added the
Repeat pins/enums and passed the expanded 271-check batch plus 22 focused
tests; PR132 configuration is now integrated into the candidate at
`0e50f1ba`. This does not erase standalone PR137's failures or replace
exact-head CI for the combined candidate. Its WebKit run also failed the strict S2 Harmonics
panel-to-editor latency gate at 22 frames/358 ms; preserve that failure until a
justified correction passes on an exact head.

The engine/editor candidate's native unit and undo/redo checks pass, but the
strict WebKit editor failures on PR130 and PR138 remain captured failures until
their fixes pass exact-head checks. The separate PR131 Chromium underrun remains
an unresolved CI/browser-path issue; it has not been diagnosed as a production
runtime defect. Automated checks do not settle the owner's Safari Sound 2
listening report: the by-ear retest remains pending. No full song compositions,
whole-chain renders or owner listening reviews are complete yet.

DADSR envelope editing is available on merged main through PR101, so song
authors can use its Delay/Attack/Decay/Sustain/Release controls. Demo completion
still requires four original assets, canonical authority/library copies,
admission and roundtrip checks, full native and actual Wasm renders, browser
load/play/save/reload and scene-takeover checks, and listening. Those are planned
acceptance steps; none is inferred from the candidate build or isolated editor
tests. Hardware boot/install/runtime and physical listening remain independent
and are not demo-authoring prerequisites.

The full-code audit is not blanket-closed. Treat a confirmed audible DSP or
song/editor/save defect used by an asset as a demo gate until it is fixed and
validated at the integrated source/Wasm level. Remaining developer-tool,
non-selected-module, audit-removal and hardware bring-up findings stay tracked
in the audit ledger and their owning workstreams; they are not automatically
song-authoring blockers. A candidate fix or a passing focused test does not
close an item for `main` or clear its broader acceptance evidence.

The documentation bundle's manual check passed on 2026-10-10. The current
working-tree sources were staged to aeon and built in the existing manual
container with 8 GiB / 8 CPU limits: 17 chapters, 40 engines/effects, and zero
strict-manual errors or warnings. The engine build printed compiler warnings;
the manual output was confined to the temporary remote directory, which was
removed after the check. This is documentation validation on the current-main
source tree, not the separate 24-effect combined candidate.
