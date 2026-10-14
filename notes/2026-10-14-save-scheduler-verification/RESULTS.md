# Native SAVE scheduling verification — 2026-10-14

[verified] `project_save_service.h` handles application SAVE generations in the
core-0 main loop. It refuses unadmitted/incomplete storage before pausing;
defers without consuming a request while display DMA is incomplete; calls the
actual application collector/transactional store while app state and drawing
are exclusive; redraws before resume on success and storage failure. A handled
request is consumed on failure as well, preventing implicit NOR retries.

[verified] `save_quiesce.h` finishes a completed panel transfer, masks/stops ALNK
under interrupt exclusion, and unprimes USB audio with an empty ring and zero
last sample. It restores codec DMA/IRQ state after clearing both DMA halves and
stale queued audio. It leaves USB unprimed so the existing producer initializes
silence and 48 kHz resampler history on its next render. TIMER5 remains enabled
between the begin/end critical sections. Already queued USB packets may drain.
No application/event-dispatching platform poll may run during synchronous SAVE;
future physical I/O must meet watchdog, interrupt and NOR-XIP safety requirements.

[verified] `app_probe.c` wires the service behind `LUNAR_PROJECT_SAVE_SERVICE`.
Its storage binding remains zero/unadmitted; the compile flag does not authorize
flash writes. Default diagnostic builds do not enable this flag. Stock storage,
flash geometry, migration and two-slot capacity remain unresolved admission gates.

[verified] Thirty concurrent Hera ASan/UBSan application cases pass: thirteen
engines with two configurations each, FIRST ORBIT twice, DX7 user voice, default
chain. Each tests refusal with zero storage I/O, display deferral, two successful
transactions, redraw before the modeled resume hook, failed storage read,
consumed failure/no automatic retry, prior committed generation selection and
fresh-app project reload. These use the actual app, collector, binary writer,
validator and store with host NOR and pause-hook models. All thirty logs, process
and container exits, OOM flags and fourteen exact source hashes were checked.
Receipt: `app-verification.json`; reproduction: `launch.py`.

[verified] Thirty concurrent standalone ASan/UBSan shards pass 30,000 quiescence
cycles. The test driver extracts unmodified `uac_packet` and `uac_render_start`
functions and their declarations from the pinned USB source. The actual helper
is tested against register/display models: reproduce held-sample underrun,
defer pending DMA without pausing, complete display transfer, pause with globals
restored, silence packets at both rates during SAVE, restore codec IRQ/run bits,
clear DMA and queue, and re-prime silence including 48 kHz history. Full source
and extracted-header hashes are recorded in `quiesce-verification.json`.
Reproduction: `tests/native/verify_save_quiesce.py`.

[verified] Offline retained integration link rebuilds the actual app with the
scheduler flag against the same reviewed generated platform, plus current
app-state/sequence/binary objects and retained SAVE service roots. It verifies
281 baseline object hashes and 72 fresh compiler dependency hashes. Both native
quiescence functions are retained in the ELF. Application is 863,380 bytes,
with 5,456 bytes of budget remaining after the configuration record reserve;
global arena headroom is 2,320 bytes. SDK-free/eFuse audit passes with zero pending
checks, independent flatten passes and no undefined symbols remain. ELF SHA256:
`ed067d2233d8b2b7994a3d8a0740a5a9b3ddfa6ec5acf06b990e0b49365cb9ab`.

This link reuses baseline objects and is not a fresh release build. Receipt's
inherited `save_scheduling_integrated=false` denotes the still-unadmitted physical
path; `scheduler_flag_compiled=true` identifies the integration experiment.
Link receipt, source hashes, section sizes and audit are saved here. Private full
logs, objects, exact source archive and generated test header are in
`build/native-save-scheduler-20261014/`. No vendor binaries are committed.

[verified] Serena resolved the exact worktree's audio-stop HAL body. Rarefaction
reported the primary checkout and fallback flags, and its bounded named search
failed to find that HAL symbol. File inspection and the actual target compiler
establish the source/compile evidence; neither semantic backend establishes
pi32v2 ABI, DMA behavior or physical acceptance. Shared project selection stayed
unchanged. No FM1 command was sent.

[inferred] Restoring ALNK DMA enable should restart its configuration; physical
codec/USB pause and resume, pending IRQ halves, duration, audible behavior,
stack/IRQ margins and sustained engine execution are still unverified. Host
source tests do not model real bus timing or flash stalls. Do not enable physical
SAVE until concrete storage allocation, capacity, lossless stock migration,
validator/transport integration and recovery are verified. The installed all13
20-second diagnostic still needs watched boot acceptance; the older Trio's
confirmed screen/keys/encoders/audio does not establish all13 acceptance.

Next: capacity/layout/migration, concrete physical SAVE I/O and stack analysis;
watched all13 boot and physical rollback; complete web installer/custom builder,
GPL notices, fresh release build, review/CI/integration and shipping.
