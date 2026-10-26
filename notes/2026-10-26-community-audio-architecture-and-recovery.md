# Community audio architecture and physical FM-1 recovery — 2026-10-26

Personal, non-commercial research. No third-party code imported; no physical
FM-1 traffic, loader execution, flash writes or power operations performed.
This supplements the earlier [runtime comparison](2026-10-23-fm1-audio-runtime-comparison.md).

## Exact sources inspected

[verified] Fresh fetches/clones, with original reference checkouts untouched:

| Project | Commit | Principal files inspected |
| --- | --- | --- |
| [SLOOP](https://github.com/isod89/sloop-fm1) | d89364253b79a5c6002c0d90c5f16b3c3c16ea9d | firmware/src/{core.h,audio.c,voice.c,fx.c,engines.c,eng_analog.c,eng_fm6.c}, tools/build.py, DUALCORE.md |
| [Felucca](https://github.com/hugelton/Felucca) | 440e62ce8a33d9bb285ab6bbca9a0fd50e459648 | firmware/src/{core.h,audio.c,voice.c}, README.md |
| [Melodee](https://github.com/keremimo/melodee) | 29ab096a6dce1ce4ed7524ad5a67c26d9e118fe9 | firmware/src/{core.h,voice.c,fm6_core.c}, tools/build.py, BUILDING.md |
| [Clipper](https://github.com/isod89/clipper-fm1) | e69067211c4690f34e494b5b896e4585163dcc2b | README.md, firmware/src/{core.h,audio.c} |
| [FM-1-transporter](https://github.com/kurogedelic/FM-1-transporter) | a7fb5e8ac692c528f8ed29e325911a3f4b8111d6 | README.md, AGENTS.md, CMakeLists.txt, tools/fm1t.py, src/{main.c,recovery.c,jieli_uboot.c,transporter_proto.c}, pio/usb_key.pio, docs/DEVLOG.md |

Private source extracts/clones and raw measurements remain ignored under
scratch/devkit-20261023/community-20261026 and build-renderer-queue-region-v31.
Source inspection proves implementation choices; upstream hardware reports
remain reported, not measurements on our devices.

## Differences that matter

[verified] SLOOP shares eight sounding synth voices across three synth parts,
with a separate drum track; its FM6 polyphony caps at six. Felucca also shares
an eight-voice synth budget. Both request gradual voice shedding after two
successive audio halves above 85% of their time budget. Melodee has sixteen
voice slots per part but a shared weighted admission budget, charging complex
engines multiple units. Catalogue size and voice slots are not simultaneous
render capacity. These are sensible product overload policies, not evidence
that audio has to glitch. They are also different from preserving every voice
in Lunar's fixed correctness/timing workload.

[verified] SLOOP uses 256-frame DMA halves and 32-sample processing slices;
Felucca/Melodee use 128-frame halves. Lunar's diagnostic deadline is 64 frames,
34,829 timer ticks, approximately 1.4512 ms. Larger halves amortize interrupt
and handoff overhead and tolerate longer scheduling stalls, at a latency cost.
They do not make steady per-sample work disappear: four successive 64-frame
computations taking about 2 ms each would still exceed a 256-frame window.
Changing Lunar's buffer is not an acceptance result under its existing gate.

[verified] SLOOP runs complete independent render units on CPU1: synthesis,
per-track inserts, level/pan, and contributions to dry and shared-send buses.
Each core owns separate accumulators, merged before shared bus effects. Lunar's
current worker runs only Macro engine callbacks; track FX, mixing, master FX,
UI/scope and diagnostic output/hash work remain on CPU0 after the join. This is
an architectural difference, not merely a choice of which engine uses CPU1.

[verified] SLOOP's analog engine is specialized fixed-point C, using table and
integer operations and skipping unused oscillators/noise/drive. Lunar's mixed
Macro voice uses actual Plaits VA+Filter with its native-rate renderer and
resampling. Shared ancestry does not imply the same algorithm or workload.
Melodee's FM6 has floating-point buses/gains, so 'floating point cannot work on
this chip' is not supported. SLOOP/Melodee build flags include -Os, not a magic
-O3 advantage. Melodee also has an explicit full audio-residency profile and
per-engine fast paths; Lunar already has verified resident hot code/tables.
Resident entry functions alone do not establish whole-graph residency.

[reported] SLOOP's dual-core documentation reports roughly 31% to 23% CPU for
its example pattern; its release notes also describe a possible short glitch
when retiring a failed/late worker. Clipper describes limited actual-unit
validation. These qualifications do not negate successful instruments; they
prevent claiming flawless behavior for every engine combination or treating
an upstream CPU percentage as a matched benchmark of Lunar.

## New V31 target evidence and next causal work

[verified] The protected V31 install/recovery/run cycle completed, with a fresh
79.0572 ms UART recovery handshake and actual ROM enumeration. All four
arithmetic checks and mixed PCM/control fingerprints passed; 22,052 queue jobs
completed without errors. Heap remained 77,780 bytes; unused stack was
2,500/8,192 parent and 7,452/8,192 worker. Sole owned receiver was closed after
twice checking its exact argv, terminal before ordinary PING ACK. Board healthy
idle. WINDOW77679 and RUN17180, and all older reset receipts, are consumed.

| Density case | Mean microseconds | Late / 5,513 blocks |
| --- | ---: | ---: |
| 0 | 1950.167 | 5513 |
| 1 | 2013.000 | 5513 |
| 2 | 2043.250 | 5513 |
| 3 | 2198.667 | 5513 |

[verified] Five additive CPU0 regions show recording about 257–258 us,
caller execution/publication 648–1,136 us, wait 235 down to 3 us, and
post-dispatch work about 790–797 us. CPU1 engine time, 878–946 us, overlaps
CPU0 and must not be added. Removing every wait tick from the lightest case
still leaves 1,715.5 us, above the 1,451.2 us deadline. The post-dispatch region
includes real DSP as well as mixing/UI/output/hash; its full cost cannot be
called framework overhead without a further split.

[inferred] Additional engine partition experiments alone cannot close the
measured gap. Next: split post-dispatch DSP/mix from UI/scope/conversion/hash;
measure callback recording separately; then evaluate complete per-track work
ownership and fewer handoffs while preserving exact output/event ordering.
Add a clearly identified reference-like voice-budget workload for comparison,
without replacing the original stress acceptance or silently shedding voices.
The earlier V30 partition regression supports measuring before repartitioning.
The earlier comparison already identified several community policies; our
implementation has not yet reproduced their complete audio work boundary.

Instrumented timing is diagnostic, not dropout-free acceptance. Actual mixed
deadline compliance, underrun fault validation, DAC/KA6 and 30-minute analog
soaks remain unfinished. CI and Pages are separate from those hardware gates;
PR155 remains draft and unmerged.

## Physical FM-1 recovery assessment

[reported: owner, 2026-10-26] The actual FM-1 still does not boot. Older status
claiming a healthy FM-1_092 is historical, not current. Owner hardware inventory:
Raspberry Pi Pico 2 W, Tigard, and Great Scott Gadgets LUNA/Cynthion. The last
operation preceding this failure has not yet been established in this session.
Dev-board recovery results do not establish physical FM-1 recovery.

[verified: transporter source] The independent entry path sends USB_KEY with
D+ clock, D- data, detects acknowledgement, maintains calibration/keep-alive
pulses, then hands off quickly to its PIO USB host. This does not require a
working application soft-key handler. The stock-V15 soft-key path is a separate
convenience path; info/dump/write call ensure_uboot automatically. Supplying a
loader causes upload to bridge RAM, and info/flash reads can cause execution
of that loader on the FM-1. Even a write dry run is not passive USB observation.
No such commands were executed here.

[reported: upstream DEVLOG] XIAO RP2040 tests reached UBOOT, read a matching
1 MiB dump, rewrote sector 0x92000 and booted V15 afterward. These are useful
recovery evidence on another unit, not acceptance on ours.

[verified] The writer gates chip key/flash ID, reviewed package, current flash
against a reference, sector ranges, per-sector readback and final full read.
It refuses writes below 0x4000 or at/above 0x93000. Thus it deliberately cannot
repair a damaged header/SPL through that writer. Matching those constants to
our unit and establishing what was damaged are prerequisites, not assumptions.
The ROM-entry mechanism and the app-region writer are different capabilities.

[verified] Upstream recommends XIAO RP2040 and reports Raspberry Pi Debug Probe
tested. Pico 2 is listed as buildable but untested; Pico 2 W is not explicitly
validated. Its RP2350 stepping/GPIO leakage workaround and exact board build
need checking. Tigard is not a drop-in PIO USB host. Cynthion is useful for USB
capture, but no transporter Cynthion backend was found in this repository.

[verified] Current transporter PIO still drives high/low push-pull during key
transmission and probe_high actively drives high; its documented direct wiring
has no series resistors. This conflicts with our docs/10 E1 open-drain key-entry
and E2 series-resistor rules. Do not silently adopt that electrical behavior.
Normal USB host signaling is a separate phase from proprietary key/ACK entry.
Before a live attempt, prepare a concrete reviewed adapter/wiring plan and
resolve that specific exception or preserve our existing entry safeguards.
No exemption was requested or inferred merely from authorization to research.

Next recovery dependency: identify the last write/known-good backup, confirm
actual bridge and wiring, and select a bounded entry/observation plan. Preserve
full current dumps and original backups before proposing a restore. Never send
an arbitrary loader from a new SDK or eFuse/programming command. Existing
protected-target approvals must be checked against the exact loader/method.
