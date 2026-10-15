# Render-stage profiling diagnostic

## Scope and implementation

[verified] Render profiling is opt-in through `--render-stage-profile`; the
builder accepts it only with explicit diagnostic telemetry and the bounded
`diagnostic` or `song-diagnostic` runtime. The default desktop, browser and
native builds compile profiling calls out through the shared MIT header
`sim/web/src/render_stage_profile.h`.

[verified] Telemetry schema 2 reports a millisecond timestamp and nine
`(ticks, maximum, calls)` triples: sequencer dispatch; sound slots 0–3; master
FX 0–1; postmix; display strip. `sound_k` aggregates the engine render and
all insert-effect calls belonging to slot k. Its `calls` count is timed render
segments plus insert invocations, not 64-frame audio blocks. Sequencer
dispatch is inclusive of callbacks into sound slots, so stage totals overlap
and must not be added. Postmix covers render work after engines/inserts and
master FX; display-strip timing is separate.

[verified] Profile window totals and maxima are unsigned 32-bit values. A
window total is the accumulated ticks since the prior successfully emitted
profile frame; it wraps modulo 2^32 if necessary. These are interval values,
not cumulative counters, so consumers should use each report's window value
directly. Profile samples reset only after the complete frame is enqueued.
When the USB-MIDI ring lacks room, the report is skipped and the sample window
is retained. The reporter snapshots in the main loop, not in the DMA audio
callback.

## Scheduling and packet budget

[verified] Schema 1 contains 27 USB-MIDI packets and schema 2 contains 50;
the ring holds 64. Calling both reporters independently each second allowed
the 27-packet compatibility frame to leave too little capacity for profiling
every time. In profiling builds, `diagnostic_reports()` therefore assigns
alternating one-second slots: schema 2 on odd slots and schema 1 on even
slots. Each report is still attempted only if its whole frame fits. This
spaces each schema's reports about two seconds apart and prevents one schema
from permanently starving the other. Builds without profiling retain the
schema-1 one-second schedule.

[verified] `test_profile_and_compatibility_reports_alternate_on_64_packet_ring`
compiles the production reporter functions against a 64-packet ring, drains
between slots, and checks both complete frames are emitted repeatedly. Other
focused tests cover compile-out behavior, opt-in validation, C encoder
round-trips, recorder acceptance, mixed captures and analyzer output.

## Limits

[verified] The focused host suite passed 113 tests on 2026-10-15:

```text
pytest tests/test_native_diagnostic_telemetry.py \
  tests/test_native_diagnostic_telemetry_build.py \
  tests/test_record_diagnostic_telemetry.py \
  tests/test_analyze_diagnostic_telemetry.py \
  tests/test_native_catalogue_receipts.py
113 passed
```

[inferred] Stage timing should help distinguish expensive engine/effect work
from display and residual work, but the instrumentation itself adds timer
reads and counter updates. This change has not yet been linked with the
pi32v2 toolchain, measured for flash/stack overhead, or captured on hardware.
It does not change renderer behavior intentionally, and it does not establish
that the measured full-song workload meets its realtime deadline.

## Linked candidate checkpoint

[verified] Hera rebuilt 16 shards from source `7036765028d42488e5f353cd0f3e74fd98a70226`;
all containers exited 0 without OOM, and all 167 object paths/hashes verified.
The first private receipt collector failed after compilation with `KeyError: 15`;
a separate verifier captured the retained inspections/logs and checked all outputs
before container removal. Its verification receipt SHA-256 is
`88b6acaa28e9a25d64aa139f31d11f595e1974e83c2408ee04fa4aafb554382d`.

[verified] The frozen link at Hera
`/home/claude/mvave-fm1/render-profile-link-70367650-20261015` produced an
849,700-byte app (10,944 bytes under the D7000 limit), SHA-256
`ce7d7dd838d54ca9b860b90d20937f2faf0f56cad500fc31f4f7e5a08c18ce28`.
ELF SHA-256 is `ad76441f849a01409dc025621515a2777709ecc0193443c4504ce104f07bbdc4`;
frozen receipt SHA-256 is
`08e7c209a0871c122ad47976fb253924acbc2db8d0d6d2969c5d97aa74c596af`.
The source tree is `83355e03a27e2de3981a20e9c755d2c2bdf78770` and the
private frozen runner SHA-256 is
`be1095cc0357d327830fe36bab57ef870d31949267ccb5eaaab770ecf17ed9fe`.

[verified] Offline construction against retained stock backups produced target
`52d6846a1a57c253caa6b4ab4dc927761928271a603be13383961936f8b2420b`,
with 208 changed sectors relative to installed target `0903762167a1dd9877c190e3b67e6657cfe4c5f7227af65d327456f73f8ba4fe`.
The prospective input template SHA-256 is
`9417371ddb2a1fc23df9d0679d25ed6e90cb591b9c303f6967c91fe6cf18b5b5`.
The coordinator adds an exact enabled schema-2/nine-stage receipt check because
the generic song diagnostic policy alone also permits non-profiled builds.
This checkpoint has not installed or booted the profiling image. SAVE remains
disarmed and performance, physical transport acceptance and release gates remain open.

## ROM67 campaign in progress

[verified] The private passive capture helper passed 14 focused tests and
Python compilation. Its SHA-256 is
`da4a68693072f61be911d273ff4363f592026c81df52975bdb7806d2a4116fde`;
the frozen coordinator SHA-256 is
`bc847700639f2c3eb7a69e57e41048816d833a5d4a1413d5097b311292eaf79f`.
All four private source hashes matched after transfer, and file-only preflight
returned `FILE_ONLY_PREFLIGHT_OK`. The single-use campaign is
`/home/claude/fm1-render-profile-70367650-20261015/rom67-cycle`.
Its paired fresh reads matched the expected installed image, and the
208-sector install transaction was started once. Installation/readback, boot
and capture acceptance remain pending at this checkpoint. Do not rerun the
consumed coordinator or repeat an ambiguous reset; inspect its durable journal.


## Completed physical profiling campaign

[verified] The single-use ROM67 campaign installed all 208 changed sectors and
verified the complete target readback as
`52d6846a1a57c253caa6b4ab4dc927761928271a603be13383961936f8b2420b`.
Install command log SHA-256:
`28c5206b8f63765de2eb033539e5cc478bae5beaf73bd29456b6d3e31d6fa2eb`;
transaction journal SHA-256:
`53ff863a471fcee2abcc3fbf0df645d9b2990289da35a1fb4f90c395ad559c9f`.
One reset request had an ambiguous SG reply; it was not retried. Native USB
1209:0001 appeared as device68 on port1-1, then automatically returned to
4c4a:8057 recovery device69. Boot campaign receipt SHA-256:
`9c5bb0cf450692e3b1cea7ff9f91b6d27659f02e2d81fb83bb5d3d842d509846`.
No owner power cycle or perceptual acceptance was required or claimed.

[verified] The original private helper failed its journal-creation race:
missing boot evidence raised ValueError rather than the FileNotFoundError
expected by its bounded polling loop. Its initial audio recorder was terminated;
`diagnostic-audio` is failed capture evidence, not a startup recording.
A separate passive capture in `late-diagnostic-audio` started about40s after
boot, validated completed-install/native gates, and completed180s analogue
capture plus110s telemetry without sending MIDI. Audio SHA-256:
`5c586713b4c455c96c33cc06a832e66d23a21a829f014868f163bf261c5e8909`;
events SHA-256:
`5c03b3514f37dd8207ee59b5cd4f09e3b2b8ab35c2b00a340c861c2441364477`.
Both are retained under bench01:
`/home/claude/fm1-render-profile-70367650-20261015/late-diagnostic-audio`.
The fixed local helper SHA-256 is
`5a4e7774d8ca9fc0152fabcfaccb532b4dd33365e392c1a6b868caea6b243b1f`;
16 tests include real filesystem creation-after-poll and unsafe evidence types.
This fix is not deployed into the consumed campaign. Use a fresh campaign for
future capture, with its own frozen hashes; never modify consumed evidence.

[verified] The final log contains41 compatibility and41 profiling frames.
First/last compatibility device uptime10057/120006ms gives109.949s, rather
than the shorter host receipt interval distorted by queued startup reports.
Produced blocks rose256→27616 (248.84/s), underruns774→49205 (440.49/s).
Expected64-frame output at44118Hz is689.34blocks/s. Final maximum render
121237ticks (5051.54us at24ticks/us), draw168745ticks (7031.04us).
Observed stack margins user5888/system7720bytes over106samples; no MIDI input.
Performance acceptance fails.

[verified] Excluding only the first startup profile window and dividing summed
window ticks by27384 master-effect calls (one per rendered block) yields:

| Stage | Mean microseconds per rendered block |
| --- | ---: |
| Sequence dispatch, inclusive of sound rendering | 2295.96 |
| Sound0 drums | 612.84 |
| Sound1 sixop | 743.39 |
| Sound2 Trio | 98.78 |
| Sound3 acid | 251.38 |
| Master0 Hall | 516.28 |
| Master1 limiter | 469.12 |
| Postmix | 350.34 |
| Display strip, amortized over rendered blocks | 10.23 |

Sound totals are nested within sequence dispatch: do not add them twice.
Window totals reset after successful enqueue, so do not difference consecutive
profile counters. Early queued windows are long and valid for block-normalized
cost, not fixed two-second windows. Timer conversion assumes the documented
24MHz oscillator; CPU clock inherited from SPL has not been read/calibrated.
No source-backed evidence yet establishes clock or cache as the cause.

[verified] The analyzer now retains existing host receipt rates and adds explicit
`counter_rates_per_device_second`/device interval fields. Buffered delivery,
uptime uint32 wrap and zero intervals have regression coverage. Device rates
require continuous uptime; intervening reboot/reset must use separate logs.
Combined analyzer/private helper regression:40 passed. Hera is comparing targeted
sixop/Hall optimization settings offline and investigating clock register sources.
Overall release remains incomplete; SAVE remains disarmed.

## Offline compiler and inherited-clock investigation

[verified] Hera's isolated sixop/Hall compile comparison reproduced both frozen
`-Oz` LTO object hashes exactly. Switching those two units to `-Os` changes sixop
bitcode size40024→35328bytes and Hall17516→18388bytes. These are intermediate
bitcode sizes, not linked flash size or measured execution speed. Non-LTO Hall
assembly text grows44423→53484bytes (+20.4%); the earlier worker description of
that change as a decrease was incorrect. Raw results are retained at
`Hera:/home/claude/mvave-fm1/hot-dsp-opt-20261015/summary.json`.
An isolated full-link replay is in progress; experimental substitutions do not
satisfy the production builder's uniform-`-Oz` catalogue provenance gate.

[verified] The read-only clock/cache review found no CPU-clock setter in the
native startup. TIMER4's oscillator reference does not establish CPU frequency.
The pinned SDK invokes `clk_early_init()` before its clock getters, so those
getters do not establish the stock SPL's inherited clock. Almost all linked code
is XIP (`.text`0xcf168bytes); `.ram_text` is0x544bytes. Neither section placement
nor cache-idle polling establishes actual cache behavior or a slow CPU.
The review handoff is
`Hera:/home/claude/.local/share/codex-coordination/handoffs/lunar--clock-readonly-20261015.md`,
SHA256 `d6ebe62d88d43aac12b550a1b1c7ad810cb2a3fd6f0aed358d49cc180c0b924d`.
The next offline clock task maps the exact verified SPL helper to pinned register
definitions; no clock, voltage or cache change follows from this review.
