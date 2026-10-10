# Sound A/B switching crackle investigation

[reported: owner listening, 2026-10-09] Native Safari served the root checkout
`35c379401ea43da8871dcefdbfe002ca3cec078e` at `http://localhost:8778`.
First orbit was playing at 116 BPM. The owner reported verbatim:

> Sound 2 A had a few small crackles when i switched to it

Project and Sound 2 snapshots existed. Sounds 1, 3 and 4 independently showed
No A, as expected for their scopes. No measured capture existed at the time of
this report. This is a failed listening result; earlier Linux browser loopback
checks do not supersede it. The earlier receipts remain unchanged.

Investigation branch: `fix/2026-10-09@ab-sound-switch-crackle`, based on merged
PR99/main `0a033d4eeca12103dbdbddbd9124fc078196c936`. No hardware traffic.

[verified: source inspection] Sound A/B uses RESTORE_SOUND. Its unit records
call fm1_app_select, which releases the sound's notes and recreates its engine,
even when the engine identifier has not changed. This is a candidate signal
interruption; its role in the owner's exact Safari result is not yet measured.

Pending: the owner's exact Safari scheduling evidence and listening after the correction.
Snapshot/difference wording is secondary to this investigation.

[verified: deterministic LAN Wasm capture, before any source correction] An
unchanged Sound 1 test-sine snapshot was restored during a held A4, at frame
3200 of a 44,118 Hz render. With no restore, the next sample was -0.0630320
(previous -0.0705817; normal step 0.00754969). Restoring that identical sound
made the next sample zero (step 0.0705817) and all following 3200 frames zero.
The control remained audible (peak 0.137795). This offline render has no browser
scheduler or capture clock, proving a sound-load signal interruption independent
of an underrun. It does not prove the cause of the owner's exact Safari event.
Probe source and numeric receipt are recorded in `notes/data/2026-10-09-ab-restore-probe.mjs`
and `notes/data/2026-10-09-ab-restore-before.json`.

[verified: focused correction] RESTORE_SOUND now retains an existing sound or
insert engine when its identifier matches and every ordinary parameter is
present. Parameters are restored through the usual setters. This preserves
held voices and insert history, rather than destroying them on a same-engine
swap. An exactly unchanged, complete MIDI-effect record also retains its notes
and clock. Sparse imports, focused pad kits, changed engines and changed MIDI
configuration retain their existing reset behavior. Project swaps still rebuild
units. No latency or zero-underrun gate changed, and no global fade/mute was added.

[verified: regression against both versions] The new native audio checks fail
11 assertions against the original main loader, then pass with the correction.
They compare five consecutive blocks bit for bit against no-load controls for
held sine, sine through Filter/Drive, and sine with an enabled arpeggiator. They
also check live parameter restoration, ordinary-import note reset, and default
values after a sparse sound restore. Before/after native JSON receipts are in
`notes/data/2026-10-09-ab-native-{before,after}.json`.

[verified: LAN Wasm capture after correction] The original held-tone probe now
reports the same boundary samples, step 0.00754969, and following peak 0.137795
for restore and control. Numeric receipt: `notes/data/2026-10-09-ab-restore-after.json`.
The native/Wasm build passes 4584 screens with zero layout faults, all 104 parity
scenarios, metadata/DX7 checks, edit parity with zero sample difference, and the
30-second offline edit storm with zero late quanta. Containers used the existing
Docker batch slice, four CPUs, and bounded memory; no host configuration changed.
The original build wrapper's temporary CPU-cap adaptation failed at shell
quoting before its core build. The core build was then run directly with nproc
bounded to four, and its record regenerated with verified image digests.

[limitations] These synthetic checks prove the identified load interruption and
its correction. They do not measure the owner's native Safari scheduling or
establish that every audible crackle came from this path. Other parameter changes
may be discontinuous according to an engine's setters; changed topology and
focused kits still reset. A real Safari listening retest is outstanding, and
there is no FM-1 hardware claim.

[reported: parent UI follow-up] Independently, the owner/parent created Sound 1 A
Volume 0.70 and B 0.15 while First orbit played at 116 BPM, leaving Hearing B /
Switch to A. These are scope-specific snapshots. Differences currently appear
only after the first swap; the current A can show a no-difference hint before
that swap. This usability issue is separate from the audio correction.

[verified: strengthened regression] The audio comparison now covers 128 blocks
(~186 ms), and requires audible energy in each control and restore, including
the arpeggiator. This crosses its next step rather than allowing a silent short
window to pass. The extended check fails 310 assertions with the old loader,
then passes with the correction. Extended before/after JSON receipts accompany
the original five-block receipts, which remain unchanged.

[verified: browser integration] Chromium 153.0.8010.12 (Playwright headless,
LAN) passes all 99 editor-v1 checks, including A/B picks and reload, with the
corrected module. Its original JSON receipt is saved as
`notes/data/2026-10-09-ab-editor-v1.json`. This is an editor integration test,
not an external audio capture or an owner listening pass. The module/source
record and zero-late offline storm checks pass two focused pytest checks.

Checkpoint: production correction pushed and SHA verified as
`305b8f67ed59c5d5a9fe55da1b4b2e1c56164c2b`; the following checkpoint adds the
extended audible-window regression and browser receipt. No PR or merge is
performed by this investigation. Owner Safari retest and separately scoped
focused-kit/project-transition behavior remain follow-up work.
