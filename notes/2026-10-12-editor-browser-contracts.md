# Editor browser contracts and native popover Escape

[verified] The editor shell test originally opened the module Files menu while
`first-orbit.lunar` had automatically selected Song / MIDI. The Song Files menu
has a separate integration gate. The module shell test now selects Flow through
the sidebar before checking its module menus.

[verified] The Song shortcut harness used a retired `play` callback. The current
Play/Pause button calls `playPause`. Its focused Space assertion now checks that
callback increments exactly once, preserving detection of duplicate Song/native
keyboard activation.

[verified] Engine information uses the browser's native auto popover. Its queued
`toggle` event updates `aria-expanded` and positions the popover. Browser tests
now wait for those updates before asserting the state. This revealed a real
Escape defect: the editor's global handler cancelled Escape and switched to PLAY
before native popover dismissal. A Chromium reproduction recorded an open
popover, `aria-expanded=true`, keys in PLAY, and `defaultPrevented=true` after
Escape. The handler now leaves Escape to the browser while an editor auto
popover is open. Tests check dismissal retains EDIT, the next Escape switches
to PLAY, and menu dismissal retains EDIT and returns focus.

## Verification and remaining layout failures

[verified] `node --test sim/web/test/song-shortcuts.test.mjs`: 6/6 passed.
`git diff --check` passed. Hera ran three isolated 3-CPU/3-GiB containers with
`lunar-playwright-audio:1.63.0`, the existing Playwright cache, and a PulseAudio
null sink. All three `song-shortcuts-ui.mjs` runs passed. All editor Files,
popover, menu, and keyboard-mode checks passed with no console/page errors.

[verified] The complete editor test remains red because its layout gates expose
separate issues. Chromium passed 109/116 checks; Firefox and WebKit 106/116.
All browsers report the RAM control overflowing at 375 px and the title's
intentional ellipsis being reported as clipping by its ancestor `.ed-title`.
Firefox and WebKit also report RAM overflow in Workbench at 1440 px; Firefox
reports the CPU percentage overlapping the RAM label. These assertions have
not been weakened. The parent stream owns the remaining layout/probe work.

[verified] Tests used parent runtime source at
`bdc7ca81aca5aa3fc32b2f9eb060b86721922d51`, its pending MIDI clipping change,
and this branch's editor.js and two test changes. Parent editor.css SHA256:
`dd66889026b0f4413eef4bdcae51e7fb7d967e6a25d11efe668cc6654319d822`.
The branch begins at `8ff54529c6fbc2b341e389b22108ffba7d707aef`; it contains no
parent layout/MIDI changes and is ready for a focused cherry-pick.

[verified] Durable receipts are under this worktree's ignored
`scratch/browser-contracts/`: `results-base8ff/`,
`results-current4f8-before-escape/popover-proof/`, and
`results-with-escape-fix/` contain reports and screenshots. The same receipts
remain on Hera in `/home/claude/mvave-fm1/editor-browser-contracts-20261012`.
`handoff.md` records the runner and recovery details. These browser checks do
not establish owner listening or physical MIDI/FM-1 acceptance.
