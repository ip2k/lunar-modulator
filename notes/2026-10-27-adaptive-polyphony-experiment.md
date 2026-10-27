# Adaptive polyphony: first admission-cap experiment

The owner asked whether Lunar can shed voices when heavy usage would otherwise
exceed its timing budget. This authorizes an explicitly labelled adaptive
polyphony experiment, not a silent change to fixed-polyphony acceptance.
Default tracked engine capacity remains twelve. Native rate, operator math,
control/event order and the 34829 OSC24M-tick deadline remain unchanged.

## First bounded measurement

[verified] Private V141 copies V140 and limits `Instance::Allocate` to its
first eight slots. It retains all twelve slots in the instance layout and the
existing retrigger/oldest-released/oldest-held stealing order. This is fixed
new-note admission, not a dynamic controller or a new fade implementation.
No vendor code is copied. The M-VAVE archive's eight-slot DX7 capacity is a
useful comparison, not proof that stock firmware dynamically sheds voices.

[verified] Normal and ASan/UBSan host runs each complete 22052 blocks and
5645312 PCM bytes with identical output. A host assertion checks at most eight
active DX7 slots before every block. The first two mixed cases remain byte
identical (2822656 bytes). Cases 2 and 3 change intentionally; their hashes
are `e463c1c3` and `97a83c77`, following unchanged `6bcab227` and `46c02687`.
The stress fixture's held-note count is not total active engine polyphony;
eight held notes does not guarantee an eight-slot cap leaves its output intact.

The initial host fixture still asserted the original twelve-slot hash; it
stopped as expected. A second check assumed the first three cases were exact;
the comparison disproved that at the beginning of case 2. Only the private
experiment fixture was corrected. Production exact-PCM gates remain intact.
Host scripts and complete logs remain private under `scratch/devkit-20261023`
and the bounded Aeon task directory, `voice-cap-v141-proof-v3/summary.json`.

## Target run and experiment-specific output guard

[verified] V141 was installed application-only after acknowledged UART entry.
Its unchanged native guard rejected the intentionally changed case-2 hash
with fault 10308; no starvation preceded that rejection. It stopped after
16548 produced / 16546 harvested blocks. The receiver was closed with one
SIGTERM after two exact argv checks; terminal status and PID absence preceded
ordinary PING ACK. Its reset receipt is consumed and must never be retried.

V141b keeps that DSP unchanged and supplies the four precise hashes established
by both host builds to the private native fixture. It retains the existing
underrun, deadline, callback, finite-exit and full-count checks. This is not a
relaxation of the original fixed-polyphony gate: it is a separately labelled
reduced-polyphony run. The corrected target result follows.

## Next dependency

Measure whether the eight-slot cap gives the mixed producer meaningful
headroom without starving output. Then evaluate a render-owned dynamic limit:
retire quiet release tails before audible held voices, account for fade cost,
respond before the output queue empties and restore capacity with hysteresis.
Report active/admitted/shed voices beside deadline misses and underruns.
Fixed-cap success would not establish dynamic-controller or analog acceptance.


## V141b target result

[verified] The application-only dev-board run completes all 22052 produced,
harvested and submitted blocks, four cases of 5513 blocks each. All four
reduced-polyphony hashes match the independent normal/sanitizer host results.
Transport fault0, backend0, off/close0, IRQ late0, gaps0; final drain35,
ready minimum1. IRQ maximum1050 ticks. Parent unused445 words, heap4052
after DAC open. Finite workload returns `LUNAR_DEVKIT complete=1`.

| Mixed case | Producer mean ticks | Mean microseconds | Producer deadline misses | Consumer mean ticks | Consumer deadline misses |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | 24578 | 1024.08 | 1 | 30479 | 0 |
| 1 | 28414 | 1183.92 | 0 | 32116 | 0 |
| 2 | 29775 | 1240.63 | 2 | 32131 | 0 |
| 3 | 29630 | 1234.58 | 2 | 32129 | 0 |

[verified] The deadline remains 34829 ticks (1451.21 us). Heavy-case producer
maximum39467 still exceeds it; the full buffered playback completes without
starvation. This does not pass a zero-producer-miss gate. V140's unchanged
twelve-slot workload starved after 907 heavy-case blocks; that incomplete
population cannot support a precise performance percentage against this
complete 5513-block run. The eight-slot run demonstrates useful headroom,
not sustained fixed-polyphony or listening acceptance.

The sole receiver PID714046 was twice exact-argv verified, sent one SIGTERM,
and reached terminal255/PID absence before ordinary PING ACK. Board is healthy
idle on V141b. No buttons, full backups, restore rehearsals, full-flash readbacks,
KA6 captures, Hera contact or physical FM-1 traffic. V141 and V141b reset
receipts are consumed and must never be retried.

Private target facts: `scratch/devkit-20261023/v141b-target-facts.json`.
Raw UART SHA256 `323036c55a2e72e22b309521780da2837bb6a98015edc7476104ab6e4e102e5c`.
Private candidate SHA256 `1eb2930aa20c73843675610f5b2b6f794c9bd515b7fcba55c6f09737799da622`.
No tracked engine default or hardware acceptance gate changed. The heartbeat
now explicitly preserves this opt-in adaptive-polyphony exception and remains
active. Dynamic retiring/fades, controller hysteresis and representative
30-minute analog soaks remain future work.


## Dynamic render-owned budget: V142b

[verified] A private opt-in runtime limit prototype starts with twelve slots.
Only the CPU0 producer changes its DX7 instance's limit, for the next block;
CPU1 and the DAC interrupt do not mutate voice allocation. New-note admission
retains same-key retrigger and released/oldest stealing. When lowering the
limit, retirement prefers released voices, then lower previous carrier gain,
then age. A retiring voice renders one final 64-frame gain-to-zero block.
Raising the limit admits future notes rather than resurrecting retired notes.
The fade still costs a full rendering block and has not been listening-tested.

[verified] Normal and ASan/UBSan host tests cover unchanged default twelve,
repeated setting to twelve, and changes twelve/eight/twelve/four/twelve.
Default/no-op twelve is byte identical over all 5645312 PCM bytes; dynamic
normal and sanitizer output agrees, with active-count bounds and released-key
retirement checks. The controller has separate normal/sanitizer checks for
sustained load, queue headroom, isolated jitter, slow recovery, limits four to
twelve, invalid elapsed time and bounded trace overflow refusal. This does
not establish target race/cache/whole-stack or listening acceptance.

The measured policy uses a quarter-weight moving render-time average. Four
consecutive checks above 90 percent of budget with at most three ready output
buffers reduce the limit one step; a missed block with at most one ready
buffer triggers an urgent reduction. Capacity recovers one step after 1024
consecutive low-load blocks below 80 percent of budget with at least three
ready buffers. There is a two-block cooldown and a diagnostic 32-decision cap.
The latter is intentionally finite and is not a production/30-minute policy.

### Memory failure and correction

[verified] V142 linked and booted but could not open the DAC: a 1536-byte
allocation failed with total heap45548 and free4628. No audio was produced;
this was not a controller performance result. V142b moves DX7 NoteOn,
Allocate, SetVoiceLimit, BudgetStats and the end-of-run budget report to
non-inlined flash `.text`; hot sample arithmetic stays unchanged. It also
corrects inherited absolute build include roots to the exact copied source.
Native symbol placement was checked. The linked heap increases768 bytes to
46316; target free5396 before DAC and3828 after. The DAC then opens normally.
SDK link audit has zero failures; its dormant SDK scheduling item remains a
manual review caveat. No full backup, restore rehearsal or readback was run.

### Target and independent decision replay

[verified] V142b completes all 22052 produced/harvested/submitted blocks with
transport fault0, backend0, off0, close0, interrupt late0, gaps0 and drain35.
IRQ maximum977 ticks; ready minimum1. Parent unused445 words and worker
unused1834 words. Ordinary PING acknowledges after the owned receiver is
closed, terminal and absent. The V142 and V142b reset receipts are consumed.

| Mixed case | Producer mean ticks | Mean microseconds | Producer deadline misses | Consumer deadline misses |
| --- | ---: | ---: | ---: | ---: |
| 0 | 24957 | 1039.88 | 1 | 0 |
| 1 | 28853 | 1202.21 | 3 | 0 |
| 2 | 31268 | 1302.83 | 47 | 0 |
| 3 | 30313 | 1263.04 | 100 | 0 |

[verified] The six limit changes are block1 to11, block1029 to12,
block16624 to11, block16628 to10, block16632 to9 and block16636 to8.
Final active8, limit8, retired4, stolen9, trace overflow0. The initial
reduction before the light case is unnecessary startup sensitivity to fix.
The first three cases retain the original twelve-slot PCM hashes
`6bcab227`, `46c02687`, `1e2f305d`; the heavy case changes to `2b958a05`.

The native dynamic fixture cannot know timing-dependent decisions in advance,
so its static twelve-slot hash expectation is replaced only in the private
experiment by mandatory independent recorded-decision replay. Per-buffer
producer/consumer hash equality, transport, counts, invalid/clipped, and
underrun checks remain intact. The original production gate is unchanged.
Normal and ASan/UBSan host replay each complete22052 blocks/5645312 bytes;
all four target case hashes and active/shed/stolen statistics match exactly.
Host PCM SHA256 `00edab1af5cb621be04ab02b292ddcdc0c6102f01e38f1c5ec3825d7845f0b6c`.

[verified] Short buffered mixed playback survives with adaptive retirement;
this is not a zero-producer-deadline-miss result. Heavy maximum44699 ticks
still exceeds34829 (1451.21 us). There is no KA6/analog or sustained30-minute
acceptance yet. The runtime API/controller remain private experimental copies;
tracked default twelve-slot behavior is unchanged. Next: ignore startup-only
pressure, react earlier to sustained overload, replace the finite diagnostic
trace for production, then integrate an explicit opt-in render-owned API with
reproducible tests and assess perceptual retirement plus sustained output.

Private reproduction scripts: `voice-limit-v142-transform.py`,
`voice-limit-v142-proof.py`, `prepare-voice-budget-v142.py`,
`refine-voice-budget-v142.py`, `prepare-voice-budget-v142b.py`,
`test-voice-budget-v142.py`, `replay-voice-budget-v142.py` under
`scratch/devkit-20261023`, mirrored on Aeon with source trees and logs.
Target facts `v142b-target-facts.json`, replay `v142b-replay-summary.json`.
UART SHA256 `9e4f820bef9e54537e1712069b30516eb5c2b142fecaf1dcff1c1be337c690ed`.
Candidate SHA256 `53b30ef0adf63bb1f5e4563410a9fd05d65e8b10c29e6fdcf65c087c059b0480`.


## Earlier-pressure policy: V142c

[verified] The second dynamic controller ignores the first sixteen prefill/
warmup blocks. Sustained pressure requires both the actual current block and
the moving average above90 percent of budget for four consecutive checks,
with at most five ready buffers (previously three). This prevents an isolated
slow block from sustaining the pressure counter and leaves more runway for
retirement. Urgent pressure, fade/DSP source, recovery hysteresis and limits
remain unchanged. Normal and sanitizer tests cover sixteen startup blocks
at200000 ticks with ready1 and no reduction, isolated jitter, sustained
expensive rendering with ready5, floor/ceiling, recovery and trace refusal.

[verified] All22052 target blocks complete, transport faults/underruns/gaps0,
IRQ late0/max956 ticks, ready minimum1 and parent unused445 words. The first
three hashes remain original twelve-slot output; heavy hash is `724a262f`.
There is no startup reduction: the only limit changes are at block16581 to11,
16585 to10,16589 to9,16593 to8. Final active8, retired4, stolen9, overflow0.

| Mixed case | Producer mean ticks | Mean microseconds | Producer deadline misses |
| --- | ---: | ---: | ---: |
| 0 | 24945 | 1039.38 | 1 |
| 1 | 28832 | 1201.33 | 2 |
| 2 | 31260 | 1302.50 | 52 |
| 3 | 30265 | 1261.04 | 57 |

[verified] Heavy-case misses decrease100 to57 versus V142b in these single
runs, but maximum45238 ticks still fails34829. Consumer deadline misses0 in
all four cases. These measurements do not prove sustained or analog acceptance,
and counts across cases need individual assessment rather than declaring a
zero-miss gate passed. Reacting sooner helps, while remaining work includes
predictable worst-case cost and production integration/listening validation.

[verified] Independent replay of the four exact target decisions completes
all5645312 PCM bytes in both normal and ASan/UBSan builds. All four target
hashes and active/shed/stolen counts agree; PCM SHA256
`a2cb0131a556d702a8cb24f395beb92a1dbb7e4a217b41fb8b7c0e6f96dc7300`.
The native receiver was closed with one SIGTERM after two exact argv checks,
terminal255/PID absence before ordinary PING ACK. The board is healthy idle;
V142c and all earlier reset receipts are consumed, never to be retried.
No RX/KA6/build/test/device operation remains live. No physical FM-1 traffic.

Private scripts `prepare-voice-budget-v142c.py`,
`test-voice-budget-v142c-startup.py`, `replay-voice-budget-v142c.py` and target
facts/replay summaries are saved locally and on Aeon. Candidate SHA256
`79d52d7be3c825e38e3ce77f751e788a615f2d70b67887ae02778b5254c9a801`;
raw UART SHA256 `6aaee4447e8f255b0c265656c34d0295c960506ed5524f4c5e0f3881c7f893e2`.
The original production engine remains unchanged; adaptive capacity remains
an explicit experiment pending opt-in integration and sustained acceptance.


## V143 render-owned engine API promotion

[verified] The tracked DX7 engine now exposes optional render-owned voice limits
through `fm1_dx7_budget.h`. Default twelve remains unchanged, with no automatic
controller enabled. Limits apply at the next internal 64-frame boundary;
released voices rank before held voices, then lower summed carrier gain, then
older age. Ranking uses a 64-bit sum to avoid overflowing six carrier gains.
Retirement renders one final fade block; increasing the limit does not resurrect
notes. Pending output remains immutable. Active, retired and stolen counts are
observable, with no locking or allocation in this API.

[verified] Aeon focused API/kernel checks pass all 20 cases, including four host
rates, explicit-default PCM equality, released-voice retirement against an
independent eight-voice instance, partially delivered blocks, invalid requests,
retriggering and future admission. Full mixed replay and independent Hera
compiler/sanitizer checks are next. This is an API checkpoint, not a production
adaptive controller or new target timing result. WASM parity must be rebuilt
from the new source before claiming current-source CI acceptance.

The owner explicitly authorized Hera heavy/parallel work up to 64 threads and
128 GB RAM. Hera is reachable. Its existing batch slice has an approximately
82 GiB cap; current jobs use smaller explicit budgets without infrastructure
changes. Mac retains all device operations. No device action accompanied this
API change. Current V142c producer misses and missing analog/soak acceptance
remain unchanged.


[verified] V143 API full mixed replay now passes normal and Clang ASan/UBSan:
22,052 blocks, 5,645,312 PCM bytes, all four native hashes, and final active8 /
retired4 / stolen9 match the recorded four limit decisions. PCM SHA256 remains
`a2cb0131a556d702a8cb24f395beb92a1dbb7e4a217b41fb8b7c0e6f96dc7300`.
The private fixture needed its original tracing hook preserved when replacing
the engine source; initial missing-hook/include build errors were corrected,
not counted as test passes.

[verified] Hera ran independent GCC and Clang normal builds at all four rates,
and GCC ASan/UBSan at all four rates. A clean selective-build test exposed a
missing object prerequisite in the new test target; `6d465f06` fixes that
prerequisite and the clean GCC sanitizer job passes. Hera's existing Clang image
lacks its sanitizer runtime, so no Hera Clang sanitizer pass is claimed; Clang
sanitizer coverage is from Aeon. Peak planned aggregate Hera use was 16 threads /
24 GiB, with explicit per-container limits, not a host configuration change.
Private receipts are under `scratch/devkit-20261023/hera-voice-budget-v143-*` and
Hera's coordination artifacts. No firmware flash or new target speedup occurred.


[verified] Final actual WASM refresh from the API plus selective-build fix passes
all 108 parity scenarios, identical to JavaScript and musl in all 108. The strict
committed module/source-record test passes with `CI=true` and UserWarnings as
errors. No browser playback, target timing or sustained audio acceptance is
claimed from `--no-screenshot`. Hera's offline jobs are terminal; its atomic
handoff is saved and its task claim released. The owner authorization to use
Hera remains in effect for future useful bounded jobs.


## V144 reusable feedback controller

[verified] `firmware/devkit/voice_budget.h` now contains the explicit opt-in,
render-owner policy: the existing 34829-tick experiment uses a quarter-weight
moving mean, four consecutive expensive blocks with limited queued headroom,
an urgent one-block-ready deadline path, and 1024 low-load blocks before raising
capacity. Limits remain 4..12. Startup tags below 16 are ignored. Failed engine
updates latch refusal without advancing the admitted limit. Change counters
saturate rather than wrap. There is no allocation, logging, IRQ access or
finite trace buffer in the controller itself; replay still needs all decisions.

[verified] Two Clang host tests (normal and ASan/UBSan) pass startup, isolated
jitter, sustained load, slow recovery, floor/ceiling, full queues, urgent pressure,
failed callbacks, invalid timing and 1616 transitions over more than a million
feedback observations. This is not evidence of target deadline acceptance.

A private V144 SDK preparation connects that header to the tracked DX7 API while
preserving earlier native-only per-block control commoning and cold-function
placement. The short-run trace keeps the first 32 events and counts overflow
without stopping synthesis; an overflowed trace cannot support exact replay.
That logger is not complete long-run trace integration. Initial SDK build failed
before compilation because the toolchain mount was absent; corrected bounded
build uses the documented read-only toolchain mount. No device operation yet.
Rarefaction cannot resolve this external worktree's new devkit files from its
main-checkout root; Serena resolves the exact worktree timing symbol. Neither
index proves the pi32v2 ABI or target code generation.

### Native controller integration: allocation regression

[verified] V144 booted with UART recovery and arithmetic intact, but DAC open
failed allocating its 1,536-byte ring. Heap capacity fell from 46,316 to 45,900
bytes; no audio workload ran, so this image has no performance result. The
receive-only process was closed and ordinary PING acknowledged.

[verified] Moving only the feedback wrapper to flash in V144b built successfully
but left heap capacity unchanged; it was not installed. Linker comparison found
RenderBlock grew by 398 SRAM bytes with the new 64-bit ranking implementation.
V144c moves block-boundary ranking and the typed control API to flash while
preserving the DSP kernels and policy semantics; native build is in progress.
Target allocation and timing remain unverified. No backups or readbacks repeated.
