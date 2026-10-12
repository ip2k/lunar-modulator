# Scenes matrix clip launch and pencil edit handoff

Owner request: click a populated clip body to launch it; use a small lower-right pencil to open its piano roll. Preserve the scene-heading launch controls and existing launch/edit MIDI target identities.

Implementation on `fix/2026-10-12@clip-launch-body`, based on `86facf5639c0d144537cd28501db7aadeac6e88c`:

- The existing first `.sq-button[data-scene-launch]` is now the large clip body and contains the summary and note preview. The existing second `.sq-button.sq-scene-edit` retains its label, class, pressed state and `data-progress-track/scenes` MIDI context, and contains an accessible 28 px pencil control.
- The progress overlay is now a noninteractive cell child, updated using the cell's existing `data-live-track` and `data-live-scene` values. Empty clip bodies retain stop-track behavior.
- Added UI coverage for body launch without opening/changing the editor, keyboard activation of the pencil opening the correct native clip with its note visible, and non-overlapping launch/pencil hit regions at 1440, 844 and 667 px widths. Updated playback test selector and the user manual plus simulator guide.

Checks: `git diff --check`, `node --check` for the changed JS and UI tests, and both Hera Chromium suites passed:

- `PASS sequencer mock-host desktop/mobile checks, real Verse note visibility and offset-loop navigation`
- `PASS independent playback visuals and native automation editing mock-host checks`

The rendered 1440 px Scenes matrix was visually inspected. The old peer order and MIDI identity are retained. The sibling CI task owns `sim/web/test/sequencer-native.mjs` and its glyph assertion update; this branch does not change that file. Browser checks do not establish device or physical acceptance. Serena/Rarefaction were not used for implementation because their selected roots/index did not cover this isolated worktree; file inspection and test evidence were used instead.

The isolated commit SHA and matching remote SHA are reported in the parent task handoff after push verification.

## Compact playback-overlay follow-up

The first review found that a taller dedicated footer row grew each cell too much and obscured the full-cell progress overlay. Follow-up keeps each cell at 56 px minimum, puts the pencil in a narrow right column aligned to the lower edge, and lets the summary and note preview occupy the left body column. The body and pencil are transparent above an isolated, positioned cell so the full-height translucent progress sibling remains visible across its left-to-right playback width. When the optional `playClip` callback is absent, the legacy edit target retains its summary and preview.

Hera Chromium rerun passed both suites. The playback test now checks the 50% and 12.5% overlays against full cell height and expected widths; the matrix test checks 54–64 px cell heights and disjoint body/pencil/content regions at 1440, 844 and 667 px. Visual review: `/tmp/clip-launch-body-scenes-progress-final.png` shows the active scene cells and their full-height translucent progress; `/tmp/clip-launch-body-matrix-revised-final.png` shows compact layout and pencil placement. The follow-up commit and verified remote SHA are reported in the parent task handoff.
