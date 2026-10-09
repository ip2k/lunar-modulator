# Factual documentation corrections — 2026-10-09

This pass ports three still-useful factual corrections from conflicted PR #58
onto current `origin/main` (`e76392b`), without carrying its obsolete status
claims or recovery wording.

| Correction | Evidence checked | Result |
| --- | --- | --- |
| Stock firmware row no longer says V15 is running on the owner's FM-1 | `notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md` §4 records the read-only ID as `FM-1_092` after the FM-1+VA installation; current `AGENTS.md` independently says V15 ran until that installation | `docs/02-stock-firmware.md` now records the transition and links the dated evidence |
| Movy commit and release tag are distinguished | `docs/13-movy-port.md`'s correction table identifies `675054f` as v0.31.0 and `5627d51` as the inspected commit; `module.json` metadata at the latter says v0.31.0 | `docs/06-movy-and-schwung.md` describes the inspected commit without treating it as the tag |
| Recovery hardware state is described as built/simulated, not complete or used | `notes/2026-10-05-softkey-efuse.md` says the project USB_KEY dongle has been simulated but not used on hardware; `docs/10-usb-key-dongle.md` documents its firmware/design | `manual/chapters/11-updating-and-recovery.md` now says the design firmware builds and passes simulation, but the project has not assembled the design or used either dongle on an FM-1 |

The same review corrected an audit-note unit error. `sim/web/test/editor.mjs`
copies `ctx.playbackStats.underrunDuration` into a field named `underrun_ms`,
but playbackStats reports duration in seconds. Thus values `0.01` and `0.02`
mean 10 ms and 20 ms, respectively; traced underrun events were 10–20 ms.
`notes/2026-10-08-audit-remediation.md` now states this explicitly rather than
calling the event 0.01 ms. No test or browser run was needed for these
documentation-only edits; `git diff --check` passed.
