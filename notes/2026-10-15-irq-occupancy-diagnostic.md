# IRQ occupancy discriminator [inferred until target measurement]

The owner cold-booted Lunar and still heard severe distortion and observed a
very laggy waveform. The completed producer-gap campaign produced 267.96
64-frame blocks/device-second against roughly689 required [verified: retained
schema1 counters]. It auto-started Event Horizon; it does not isolate idle or
single-note behavior. See `2026-10-15-producer-gap-results.md`.

## Measurement design

`LUNAR_DIAGNOSTIC_IRQ_PROFILE=1` adds cumulative schema6 observations. The
register-free core tracks inclusive ALNK0, timer5, input, USB-poll and nested
UAC-service durations, plus their union (`busy_ticks`). The timer may interrupt
ALNK0; inclusive totals must not be summed. Full saved ICFG is restored after
each short mutation, preserving its global-enable state [verified: source
matches the existing flash HAL critical-section contract]. Timestamp sampling
is inside the mask to prevent a preemption gap from double-counting union time.

Render elapsed and concurrent IRQ union ticks are cumulative uint32 counters.
The counter copy is interrupt-quiesced; USB encoding/publication occurs after
restoration. Packet encoding is22 canonical uint32 fields,119 bytes/40 USB-MIDI
packets, reserved as a complete frame. Existing schemas1-5 retain their format.
This is a private diagnostic protocol, not release readiness or an ABI promise.

## Limits and next acceptance

Hooks measure C handler bodies, excluding interrupt entry/exit assembly and
some compiler prologue/epilogue. Short masked accounting adds overhead and
slightly delays pending interrupts. Input still scans10kHz and USB services2kHz;
no service bypass is justified by present evidence. Raw TIMER4 ticks do not
establish CPU frequency. Cumulative counters wrap modulo2^32; captures and
comparisons must use bounded elapsed windows and unsigned deltas.

Host checks validate arithmetic, disabled behavior and wire representation.
They cannot verify pi32v2 code generation or device scheduling. Next: frozen
Hera build with no autoplay and schema6, exact image/recovery admission, then
controlled note capture. Compare a matched profiling-disabled image before
attributing sustained overhead to the original firmware. SAVE remains disarmed;
no new hardware operation is authorized by a host test result alone.

## Frozen target build and runtime checkpoint

[verified: Hera build and locally rehashed outputs] Firmware source
`3e8664b58e65aac90c3ca6258f89f874075691e3` completed all sixteen catalogue
shards (167 objects) and target link. App size is 853,368 of 860,644 bytes
(7,276 bytes free). ELF SHA256 is
`dcacd894f5b1c8c1828c5c35024142cf8b1d225942747ed02228281f5d5b5cb3`;
app SHA256 is
`66ba7cd0d7640a314fed80c00b6723a3a0c76734b12097869193968550a8bb7e`.
Independent disassembly review confirmed saved-ICFG restoration and timestamp
ordering at the instrumented handlers. Key audit passed 12 checks with no
failures or pending checks. This is static evidence, not timing acceptance.

Private evidence is retained under `scratch/irq-profile-result/`; archive
SHA256 `faeaf854929a24d09a05a9f7230a5f5fb553e815445813e1b1119f2688b9798b`.
The original frozen receipt is preserved; all ten output digests were rechecked.
Independent review is `scratch/irq-profile-build/target-review-3e8664b5.md`.
Build omits autoplay and producer-gap telemetry, retains all thirteen engines,
and keeps SAVE disarmed. No new image has been installed.

[verified: passive bench sysfs] FM1 is bus1/path1-1/dev89, 4c4a:8057,
WL80UBOOT1.00. Fresh paired reads must still match the previous full target
`bc593f95bbfc9731dbbc906fb67c06d9882fbd51403cdda3dbe9ab95740fb566`
before a separately reviewed installation. Prior ROM87 campaign is consumed.
The reviewed diagnostic flash/adapter/boot source pins were refreshed for the
new no-autoplay policy; 18 focused flash/adapter/boot checks pass.

## Private campaign preparation follow-up

[verified: retained six-channel recording, FFmpeg astats] The prior producer-gap
capture's inputs1/2 peak at -1.359959/-0.940678 dBFS, respectively. Neither hits
digital full scale in this recording. This does not exclude analog clipping or
upstream distortion, and does not replace listening acceptance. Retained report:
`scratch/producer-gap-result/physical/audio-astats.txt`. Keep the current gain
settings for the next comparison.

[verified: bench filesystem only] The frozen build and runtime are separately
staged under `/home/claude/fm1-irq-profile-3e8664b5-20261015`. Original producer
receipt remains unchanged; compatibility receipt SHA256 is
`1344f8f757ec02b90e56307889b77dee276c8a2405192c4ee8a3904eb4c7429f`.
Capture runtime covers174 files; its249-file tools-source inventory is a separate
binding. No new candidate has been installed. Independent construction review
found that the staged candidate audit's source scan resolves to an absent
`runtime/firmware/native` directory. An exact frozen-source staging and rehash
step is being prepared to close that gap before construction. The linked ELF
check alone does not make a missing source scan pass meaningful.

## Candidate construction and one-use launch

[verified: staged filesystem and independent runner review] Exact frozen native
source inventory now exists at runtime/firmware/native:60 files,2 directories,
rehashed against source-manifest SHA256 d061242c5da63d9486c49571cd19ed712cf67b687c9f14a62e9fd8b3def2a594.
The previously absent source scan is no longer vacuous. Candidate target SHA256
is a2c7eee6ca72659435452b59bd381fa8556b05a4fdc898329de3ea4fcdbf41d4;
receipt6a228b99f65f975dd240335324bdd599fc37e073dc728d6beb44fa4b6fdac9c7.
Offline comparison against predecessor found209 transition sectors within211
allowed sectors; fresh reads remain mandatory before physical mutation.

Runner tests50 passed, compilation passed; independent final review is retained
at scratch/irq-profile-build/cycle-review.md (5c10396ccb044db98901eb8e8dec5993bda4846ae78d811ebaa3b9247ee55dfe).
Review caught a Git40 source-tree ID being treated as SHA256; contract corrected,
with actual template evidence checked. The separately frozen deployment passed
file-only preflight on bench twice. Pin-file SHA256:
7f727ce4de9b8aaf6524342b5730ab4d8759df67d1fb30acebdebc9016974828.

[verified: launch receipt/output] Root launched rom89-irq-profile-cycle once,
PID122407, under private base /home/claude/fm1-irq-profile-3e8664b5-20261015.
Initial output FRESH_PAIRED_READ_START; installation/boot/capture are not yet
claimed at this checkpoint. Do not relaunch. The flow requires exact predecessor
paired reads,209-sector transition and full image readback, then durable install
result, recording readiness and one boot request. No autoplay or MIDI output;
no musical acceptance inferred. Inspect retained journals for actual outcome.
