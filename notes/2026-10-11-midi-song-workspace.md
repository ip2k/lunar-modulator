# MIDI and Song workspace implementation

Owner-authorized endpoint: standard MIDI import, native clip/scene/song editing,
parameter-lock automation, sound/master mixing, `.lunar` and `.movy1` exchange,
and actual-engine stereo master, sound stems and eight-channel WAV export,
tested, reviewed, merged and deployed to GitHub Pages. Four stereo sound stems
form the multichannel file; eight sequencer-track stems are also offered.

Branch: `feature/2026-10-11@midi-sequencer-workspace`, starting at `b335dc2`.
Managed checkout: `~/.codex/worktrees/midi-sequencer-workspace/mvave-fm1-firmware`.
This is a work-in-progress checkpoint, not acceptance or a deployment.

The Song workspace edits the native Movy sequencer model: eight tracks routed
to four sounds, eight scene columns, 64 scene presses, and 96 ticks per quarter
note. MIDI type 0/1 imports preview instrument mappings and unsupported data;
capacity overflow, unsupported meters and unknown set extensions are refused
instead of silently dropping events. Native shadow import/export is compared
before an editor transaction replaces the running project.

Evidence so far [verified]: 23 parser/model tests pass, including native Wasm
round trips. Offline Wasm render tests on Hera pass deterministic finite song
length, unused-stem silence, track isolation, exact eight-channel interleave,
FM6/inserts/arp/modulation and separate master-effect processing, cancellation,
and WAV header/PCM/bounds checks. The complete existing container build passes
108 Wasm/native parity scenarios and the 30-second edit storm with zero late
quanta. These checks do not establish browser UI or owner listening acceptance.

Further evidence [verified]: real Chromium/Wasm integration passes native
note/gate/microtiming/probability edits, lock serialization, routing/repeat
undo/redo, clip-matrix transport, MIDI batch preview/refusal/replacement, text
and binary project reopen, set reopen, stale-document/atomic-hash refusals and
six real Worker WAV downloads. Five stereo files and one eight-channel file
have matching 44,118 Hz, 24-bit headers and one-pass frame counts. Desktop and
390-pixel mobile screenshots have been inspected; internal matrix/piano-roll
scrolling is deliberate. This is browser automation, not physical touch testing.

Native insert/master/mixer automation and its focused test are implemented.
Correct RAM accounting exposed an existing near-budget modulation fixture;
Room replaces Plate in that fixture while keeping its routing coverage and the
strict budget. The preceding rebuilt module has SHA-256
`b98e8e3295dba072a65d2d49bd5e1b3d57afc63ce2b2aa33027202e1d7c8c258`.
It passes 108 parity scenarios (all identical to JavaScript and musl), plus the
30-second edit storm: zero late blocks, p99 0.1402 ms, maximum 0.3050 ms.
Native web/mod/multi/automation regression: 281 passed, with two staging-only
asset/staleness checks excluded and covered separately by the complete rebuild.
Chromium, Firefox and WebKit real-module workflows pass; exact final-module
browser reruns, independent review, required CI, merge and deployed deep-link
proof remain outstanding. Current source checkpoints are not deployment proof.

Device boundary: `.lunar` and `.movy1` remain the same portable native formats.
The owner's FM-1_092 does not run Lunar; direct device project exchange requires
a running Lunar firmware and transport implementation. No device load or flash
operation belongs to this editor checkpoint.

Orientation: Rarefaction's bounded TypeScript query of `startEditor` and Serena's
C symbol lookup succeeded on the primary checkout. Serena had no TypeScript
backend, reference results were incomplete, and the managed feature worktree
was inspected directly rather than retargeting another active shared session.

Design references: [Ableton Arrangement](https://www.ableton.com/en/manual/arrangement-view/),
[MIDI editing](https://www.ableton.com/en/manual/editing-midi/),
[Bitwig arranger clips](https://www.bitwig.com/userguide/latest/arranger_clips_and_the_browser_panel/),
[Standard MIDI Files](https://midi.org/standard-midi-files).
The UI and importer are original MIT code; these references inform the workflow.

## Mixer and design iteration — 2026-10-11

The owner requested a critique using all adopted interface-design guidance.
An independent critic is inspecting the actual desktop, phone-landscape and
portrait interfaces, all five views, focus behavior and accessibility. Its
initial findings exposed excessive header height and device controls appearing
below the viewport. Those are being addressed before the final review.

Saved implementation, pending final browser verification: four shared sound
strips plus Master, vertical native faders with dB readouts, per-insert and
master-effect input/output meters, post-fader sound meters and final output
meter. Eight track routing/mute controls explicitly show that tracks share a
sound's engine, inserts and level. Native parameter edits drive faders without
reloading the project; the physical MASTER preference is distinct from the
saved sound levels. Device controls open in a native modal dialog with a Close
action, Escape handling and focus returned to their trigger. File actions are
in a disclosure; Scenes and Clip controls have compact spacing. Short landscape
screens initially collapse Routing & FX to prioritize mixer faders.

The append-only telemetry `levels` section starts at float 1454 and mask bit
119, with five peak/RMS rows. Version 3 has 1464 floats and 124 mask bits; all
older offsets are preserved. Stereo-aggregate RMS and peak are measured on
actual audio only for subscribed rows. Native metering and metadata checks
pass; final browser checks, independent critique, CI, merge and Pages proof
remain required. These checks do not establish physical FM-1 or by-ear
acceptance.

Applied design sources (instruction/reference only, no product code copied):

- Local Apple HIG skill and cached September 13 guidance for layout, labels,
  accessible controls and color cues; the cached guidance was not resynced.
- Anthropic `frontend-design`, commit `dbd4588f9e1033efb41dad4bef2f7947c8993d44`.
- Vercel `web-design-guidelines`, commit `063bee94c3f4df8453406c830b0a7df0f2860278`,
  and separately MIT-licensed interface checklist at
  `434b7f91364665f2f733b310ec54809bf8f37937`.
- UI/UX Pro Max, commit `67803eac81607188194aea9842a723b89326d90d`.
- Bencium `design-audit`, commit `5de46a39b4640fa419560cd0b67e4c4b50dac802`.
- [Bitwig Mix View](https://www.bitwig.com/userguide/latest/the_mix_view/):
  vertical strips, device access, fader/peak/RMS presentation and clear Master
  placement, adapted to Lunar's native capabilities.

Skill source paths and license checks are saved in ignored
`scratch/design-skills/HANDOFF.md` in the primary checkout. The independent
critic's evidence is in managed `scratch/daw-design-critic/`; browser test
receipts are in `scratch/mixer-ui-refinement/`. Root owns integration and the
shared feature branch; agent completion is not overall acceptance.

## Final native/browser acceptance checkpoint — 2026-10-11 [verified]

The final module has SHA-256
`f163c1b5799bb6109718993600df4c3f7884ffca055a2e4df558cc8007e65219`,
metadata `fbd3d320`. The rebuild passed all 108 native/Wasm parity scenarios
and a 30-second edit storm: zero late quanta, p99 0.148251 ms, maximum
1.116497 ms. Final parser/model checks pass 27/27. Exact-module WAV and
meter checks pass, including sample equality with subscriptions on/off,
post-fader and MASTER scaling, silent unused sound rows, empty-effect identity,
and 8-channel interleaving. See [the tracked native receipt](2026-10-11-final-native-acceptance/README.md).

All four showcase assets from merged main `621490b9` load without repairs,
drops or omissions. The chain meter excludes edit-layer telemetry state;
an explicit additional 60-byte debit for the new meters leaves the smallest
chain headroom at 26,604 bytes. This checks the native chain bound, not a
complete physical firmware SRAM layout.

Chromium, Firefox and WebKit each pass 31 mock UI checks and 12 native
workflows, with six valid WAV exports and no page errors. Firefox uses the
documented isolated PulseAudio null sink. Browser receipts and captures are
in ignored `scratch/mixer-ui-refinement/routing-fx-final-20261011e/`.

Independent rendered design review found no remaining P0/P1 in the tested
native browser runtime. Scores /10: clarity 8, spacing 7, DAW familiarity 8,
tested interaction/accessibility 8, mobile usability 6, identity 7. Its
remaining P2 concerns are Scene rows, selected-note controls and inspector
density. A bounded frontend refinement and independent re-review are in
progress; previous captures and scores remain historical evidence.

These checks do not establish physical phone touch, VoiceOver, owner
listening or FM-1 acceptance. PR #146 still requires final source review,
exact-head CI, merge and deployed Pages deep-link proof.

## Documentation and evidence checkpoint — 2026-10-11

The preserved independent design review is tracked in
[`2026-10-11-daw-design-review/`](2026-10-11-daw-design-review/README.md),
including the original reports, rendered assets and audit data. Its report and
audit refer to Wasm SHA-256
`f163c1b5799bb6109718993600df4c3f7884ffca055a2e4df558cc8007e65219`. The
later sequencer bridge module SHA-256
`2a2ad121431f6e7fac5aa186d00eb0b75848187441ffe0d4ec4222451ed65cc3` is
separate evidence and was not reviewed by that report.

Current editor behavior is documented in the Advanced editor manual and
simulator README: compact Scenes rows; selected-note Pitch, Step, Gate and
Velocity always visible, with Microtiming and Probability under **Advanced**;
primary parameters first in Song workspace device inspectors; and modal focus
on Close, Escape handling and trigger-focus restoration. MIDI import is bounded
to 16 files, 16 MiB per file, 32 MiB and 64 parts per batch. Native sequencer
content-generation changes refresh the visible Song view after panel edits and
invalidate a hidden view for refresh on return; Undo and Redo refuse a stale
change after an intervening panel edit.

Focused helper checks are 30/30 for MIDI import and 8/8 for the sequencer
host. Fresh native checks for the latest changes are still ongoing. The
separate design review does not establish physical phone touch, owner
listening or FM-1 hardware acceptance.

## Current final candidate acceptance — 2026-10-11 [verified]

This checkpoint supersedes the earlier pending-work descriptions above;
the older receipts remain historical evidence. The current Wasm SHA-256 is
`2a2ad121431f6e7fac5aa186d00eb0b75848187441ffe0d4ec4222451ed65cc3`.
The bounded Hera build passed 108 native/Wasm parity scenarios and the
30-second edit storm with zero late quanta (p99 0.139144 ms, maximum
0.307414 ms). The build record includes the actual Alpine and Emscripten
image digests and matches the current source hashes. Its timestamp was
regenerated after synchronizing noncompiled example/schema inputs; the
successfully tested binary did not change.

Fresh mock and actual-Wasm Song workflows pass in Chromium 153, Firefox 155
and WebKit 26.6. Each native run passed the real clip-launch transport and
playhead assertion and exported all six WAV files with the expected channel
layouts; no page errors occurred. See
[the three-browser receipt](2026-10-11-final-native-acceptance/browser-results.json)
and [its provenance](2026-10-11-final-native-acceptance/provenance.md).
The separate panel/editor synchronization suite passes all four checks in
all three browsers. MIDI helpers pass 30/30 and host helpers pass 8/8.
The [fresh bridge receipt](2026-10-11-final-native-acceptance/bridge.md)
also verifies exact-module offline rendering, metadata equality, measured
peak/RMS taps and bit-identical audio with metering enabled or disabled.

[Independent source review](2026-10-11-daw-sync-review.md) found stale Undo,
missing native panel invalidation and unbounded aggregate import preview.
All three findings were resolved and rechecked. The
[final rendered design review](2026-10-11-daw-design-review/report.md) scores
clarity, spacing, DAW familiarity and tested interaction/accessibility at 8/10,
mobile usability and identity at 7/10. It found no remaining P0/P1 in its
bounded browser execution. Landscape first-screen chrome remains a P2:
the working panel is accessible but needs scrolling on an 844×390 viewport.

At this dated checkpoint, PR #146 still requires exact-head GitHub CI, merge
and deployed Pages verification. Physical phone touch, VoiceOver, owner
listening and FM-1 hardware acceptance are separate, unclaimed gates.

## Follow-on browser evidence — 2026-10-12 UTC

Codex completed a bounded native Safari check on the owner’s Mac, on HEAD
`069333cddd3dde8fbe0b73797f97add8a0a28ae4`, with Wasm SHA-256
`2a2ad121431f6e7fac5aa186d00eb0b75848187441ffe0d4ec4222451ed65cc3`.
The receipt includes Song loading, MIDI output selection, Undo, an actual
fader edit, advancing transport, measured non-silent meters and inspector
focus restoration: [native Safari receipt](2026-10-11-final-native-acceptance/native-safari.json).

GitHub Actions run
[38201714094](https://github.com/ip2k/lunar-modulator/actions/runs/38201714094)
on that same HEAD passed WebKit but failed Chromium and Firefox browser checks.
The saved diagnostic deterministically reproduced refresh timing that can
interrupt a tab click or rebuild a numeric field during typing; see the
[failure reports and screenshots](2026-10-11-final-native-acceptance/ci-failure-38201714094/).
The run remains a failure alongside the earlier passing browser receipts and
the separate Safari check. `midi_model` owns the production race fix and
regression; required exact-head CI needs a fresh pass after that change. No
by-ear, physical-phone or FM-1 acceptance is established by this browser evidence.
