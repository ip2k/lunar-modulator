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

Pending: deterministic audio capture before a correction, focused regression,
browser scheduling evidence, and owner listening after any tested correction.
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
