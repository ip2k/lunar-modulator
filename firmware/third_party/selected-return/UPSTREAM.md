# Selected return offline policy — 2026-11-01

This GPL-3.0-only derivative has two mutually exclusive offline selections:
portable host fake and an explicitly selected, unqualified pi32v2 binding
candidate. The latter has an immutable all-zero qualification record and refuses
functional startup. Neither is hardware admission. The default FM6 and existing
selected-Trio profiles do not select these objects. No inherited write guard,
default startup, reset whitelist or release/install admission is changed.

## Source and licence

[verified: Git source] The narrow P33 command/watchdog/mailbox sequence derives
from Dinghy's historical `hal/fm1_sys.h`, read at Lunar
`fad3a965f9aa9949069a3d864047eaca5ddf0be8`, SHA-256
`5d56781274406b0a1bf816c66d86c0b0b23b49757cc6f5644df566127827a9a7`.
Credit Leo Kuroshita (@kurogedelic), Hügelton Instruments, zvenson, Felucca
and SLOOP/isod89. The imported base HAL records upstream
<https://github.com/zvenson/dinghy> at
`d44df7db09b98ccad2f1233b8f83f5f09c04829e`, carried through Lunar
`cccd21cc5dc82859ed8a5d84f0a7a40646d07353`.
See this package's `LICENSE`, `../dinghy/LICENSING.md` and `../dinghy/UPSTREAM.md`.
This separate derivative inventory does not reimport the historical header.
GPL source permission does not authorize distribution with closed SDK objects.
No new third-party binary, extraction, download or proprietary output is used.

[verified: source] Historical CON/DAT are `0x13e08`/`0x13e0c`; normal P33 uses
CS bit0, BUSY bit1, kick bit4, RTC domain bit8 clear. Allowed private commands
are only watchdog write/AND/OR/read and power-reset OR. Registers are WDT
`0x80`, mode `0x17` bit6, reset `0xa0` bit4; a reset transaction is exactly
`20 a0 10`. No arbitrary register/op/address API is exported. TIMER4 is
`0x10800` with CNT/PRD at +4/+8. `fm1_time.h` and `fm1_timer.h` supply the
source/divider contract. Actual physical bit and reset behavior is unverified.

The original read-only design and independent review were supplied privately
and checked before implementation. Their exact digests and current input hashes
are in `inventory.json`. All 16 source/doc inputs named by that
review were byte-identical at the portable milestone's base
`c7f7abdf1c87ad43a54f4c0c13850e390ee5f013`.

## Deliberate changes from the historical sequence

The adapter never continues after a failed byte. It halts terminal without later
DAT reads, bytes, commands, retry or an invented busy-CS cancellation sequence.
Already BUSY or selected CS is refused. Only a successful command deasserts CS.
Its named poll limit bounds returning reads, not a stalled MMIO bus or time.
Successful arm/feed restores the exact saved ICFG; terminal masks bit8, never
restores it and cannot return. P33 ownership is one CPU0 main owner only.

The policy verifies `(TIMER4_CON & 0xff)==9` and `PRD==UINT32_MAX` before any
mailbox write and after watchdog setup; progress checks configuration again.
It samples one raw origin after setup, before any future app phase. The nominal
threshold is 480000000 ticks. Each ordered APP/LCD/IO completion, then each MAIN
completion, needs healthy==1 and advancing ticks within a caller-qualified
maximum interval shorter than a separately qualified watchdog lease. It never
feeds on deadline, stopped/regressed/unqualified clock, oversized interval,
wrong phase, init refusal, P33 failure or fault. The origin is not reset release;
poll/request latency and reset-to-ROM latency are separate future measurements.
Unsigned subtraction covers a wrap, not a missed full cycle. The source-reported
24 MHz and historical selector-to-seconds comments are not measured facts here.

The exact marker is `usb_update_mode\0`, 16 volatile byte stores, an explicit
compiler fence plus a required binding publication callback, then exact readback.
The borrowed typed mailbox object is exactly 16 bytes. Constant extent is
`[0x01c7fd80,0x01c7fd90)`, above the current retained ceiling `0x01c7fd50`
and below vectors `0x01c7fe00`. These assertions do not reserve a future target
section. Its last eight bytes overlap the first eight bytes of the historical
UPDATA record at `0x01c7fd88`; there is no broad mailbox clear or UPDATA write.
Prearming would intentionally change warm-reset destination for the lifetime of
this temporary diagnostic; persistent installed behavior is outside this proof.

Mailbox readback precedes reset-mode watchdog setup and stable-field readbacks.
Self-clearing strobe bit6 is not required to read back set. No app startup is
allowed until setup returns success. Normal deadline/init refusal attempts one
reset transaction; any failure retains the first error and does not retry.
Fault/nested fault makes sticky terminal state and never enters P33, including
when a normal feed owns it. A fault cannot undo a byte already completed: tests
also cover a feed accepted just before the fault and require no later access.
Bootstrap before a known armed reset backstop remains an unsupported window.

## Qualification and later acceptance

All explicit qualification flags default to refusal. Host tests deliberately
provide assumptions; no flag establishes physical permission. The portable fake
has no real mailbox/MMIO/ICFG/csync/halt binding; the separately guarded candidate
below binds register operations but does not qualify their physical behavior. Actual watchdog stable-field semantics,
reset mode and measured lease, inherited write-guard permission for the exact
mailbox, TIMER4 frequency/ownership and reset-source mailbox retention/ROM
consumption remain unqualified. No target profile can be admitted from this test.
`atomic_signal_fence` is only a compiler barrier, not target `csync`; the candidate uses explicit `csync` callbacks as well.

Later work needs a separately reviewed narrow binding, selected linker mailbox
reservation, target source/codegen/call reachability/fit/security audit, exact
origin before app/IRQ work, fault integration, measured P33 masked latency and
phase bounds versus audio deadlines, and coordinator-owned physical observations
of watchdog/reset/mailbox/ROM enumeration and recovery. Preserve original default
audit exclusions, fixed-eight cap, arenas and guards. No blanket write-limit
removal, CPU1, retries, fault-time P33, USB/MIDI/storage/update or reset service
is admitted by this module. RAM/stack/text target closure is not measured here.

Host verification: `tests/test_selected_return.py` compiles the actual policy
with its register-only fixture, normal and ASan/UBSan; it also checks three
compile refusals. The fixture covers 90 terminal cases per run: threshold/wrap,
progress/config refusals, exact mailbox/sentinels, each of 24 arm/9 feed/3 reset
byte timeouts and exact poll cap, inherited busy/CS, four arm readbacks, timer
mutation during setup, sticky terminal/one reset, enabled/disabled ICFG restore,
and first/nested faults before and after a completed feed. It does not simulate
a watchdog reset or claim silicon acceptance. Generated products live in a named
pytest basetemp under scratch and are removed after recording the small logs.


## Unqualified target binding candidate

The target-binding work branches from root-integrated
`e5acacea04b42f75feed8332d1a091ff5ce73f21`. The portable source has an
independently reviewed host-only contract. The added pi32v2 binding, selected
platform and linker script are a separate candidate, not an extension of that
physical acceptance. `selected_return_platform.c` derives narrowly from the
current GPL `firmware/native/diagnostic_platform.c`; its HAL/ISR/app behavior
stays in the existing interfaces. `selected_return_candidate.ld` derives from
current GPL `diagnostic.ld`. Their provenance/source pins are inventoried.

The binding requires explicit offline-proof and pi32v2-binding defines. Actual
pi32v2 and host injection cannot be combined; portable fake cannot be combined
with either target binding. The host mode and field layout remain unchanged.
Target fault-shared fields and the port pointer have volatile, aligned scalar
accesses. An exception never resumes the interrupted main owner, so there is no
retry or resume race to repair with locks/CAS. This is a target/compiler contract,
not ISO C11 thread synchronization, C signal safety, CPU1 or cache proof. A fault
before a valid policy/exception handler exists remains in the bootstrap gap.

ICFG capture and restoration use volatile assembly with memory clobbers.
The policy's four compiler fences (IRQ mask, P33 begin/end and mailbox
publication) use an empty volatile assembly memory clobber on actual pi32v2.
The vendor compiler lowered C11 `atomic_signal_fence` to an unresolved
`__sync_synchronize` in the failed source-pinned `ca45926a` target attempt;
adding a runtime helper or no-op stub would not establish the intended ordering.
Host fake and injected-target paths retain the original C11 signal fence.
The target fence is compiler ordering only: it neither substitutes for nor adds
to the explicit `csync` operations in the unchanged ICFG/MMIO/publication
callbacks. Object/IR inspection and the eventual full target link remain separate
acceptance gates; this correction does not qualify hardware.

Register callbacks use exact volatile 32-bit accesses and `csync` after each
load/store; P33 DAT is 32 bits with the low protocol byte returned. No pointer
or opcode is provided by a caller. Mailbox stores remain exactly the policy's
16 volatile bytes followed by `csync` and readback. The separate linker script
reserves one 16-byte NOLOAD section at `0x01c7fd80`, outside C data/BSS zeroing,
retained state and both stacks. It neither removes inherited write limits nor
proves permission to write that range.

The checked-in target qualification is immutable and all zero. There is no CLI,
weak symbol or retained-memory override. The candidate therefore halts before
TIMER4, mailbox, P33, IRQ setup, app, LCD or audio operations. It masks normal
IRQs and waits; this is an explicit unsupported recovery case, not a working
ROM return. Qualified host injection exists only in tests. A later physical
qualification/source change needs separate review, including how an exclusively
owned TIMER4 is configured before the policy's first read. This candidate does
not reset or reconfigure a borrowed counter.

With fake evidence, the selected platform's prospective path is prepare, IRQ
setup, APP completion, LCD completion, IO/audio completion, IRQ enable, then MAIN
completion checks. It reuses the existing fixed Trio initializer and render IRQ.
The LCD completion check requires the existing fresh-zero
`fm1_lcd_timeouts` counter to remain zero: the HAL records a bounded SPI timeout
and returns, so return from `lcd_sync` alone is not healthy completion. A recorded
timeout terminates before another feed or input/audio startup. Exception terminal
publication precedes a bounded best-effort audio stop in halt; no app, allocation,
logging, P33 or waiting helper runs in the fault path.
Nested HAL faults already halt without reentering this adapter. This path is
compiled source only until actual target review, and remains unreachable past
the immutable qualification refusal in this candidate.

The target evidence record adds independently qualified timer frequency and P33
latency flags, plus feed, post-arm tail, masked-feed and audio allowance bounds.
Validation uses subtraction to avoid overflow and requires the strict sum
`max_phase + feed_bound + post_arm_tail < shortest_reset_lease`, as well as
`masked_feed_bound <= feed_bound` and `masked_feed_bound < audio_irq_allowance`.
No duration or selector-to-seconds map is supplied. Poll count is not a latency
measurement. These bounds must include all readbacks, function calls, barriers,
interrupt masking/restoration and the complete final feed transaction. App/LCD/
IO phase work is not run with the P33 mask held. The ISR never feeds the watchdog.

The separate fixed wrapper selects this package/platform/linker only through a
private `return_candidate` build plan. The original two plans, forbidden symbols,
budgets, toolchain pins, source audits and worker capture helper stay unchanged.
The candidate receipt states physical qualification false, functional startup
refused, ROM return false and no distribution/hardware admission. An actual link
can prove retained candidate code and layout; it cannot prove startup execution.

The focused host proof also executes this actual platform startup body through
typed HAL shims and the actual injected target binding/policy. Separate processes
cover qualification refusal, APP failure, a recorded LCD timeout, and MAIN status
failure after IO/audio startup; terminal publication precedes audio stop. The shims
do not model SPI completion, clock frequency, watchdog reset or physical silence.
Normal and ASan/UBSan checks use the same owner body as the candidate. A private
counterfactual build restoring only the old unconditional LCD health predicate
reaches an extra feed and forbidden IO startup in both configurations; the corrected
source stops after the APP feed. All target qualification remains zero.

## Minimal subsequent physical qualification experiment

These are inputs/outputs for a later coordinator-authorized experiment, not
permission to operate hardware from this source milestone.

| Gate | Required input | Required retained output |
| --- | --- | --- |
| Entry and mailbox | Exact selected ELF/image, verified connected unit/boot route, unchanged stock protected regions and recovery route; source proof for inherited exact-range guard state | Guard/register observations bound to entry, exact 16-byte write/readback permission and untouched neighbouring retained/vector/stack bytes; refuse rather than disable guards if unknown |
| Timer ownership | Proven exclusive TIMER4 owner and exact source/divider/PRD configuration; independent time reference | Measured tick frequency, monotonic/wrap behavior, setup order and stopped/changed-clock refusal evidence |
| Watchdog | Exact selector/reset-mode/stable-field source contract, prearmed marker, reviewed no-feed harness and independent timing reference | Minimum/maximum reset lease, stable readback/strobe behavior, reset source and mailbox retention across both watchdog and P33 reset, fresh ROM enumeration/identity and recovery evidence |
| Timing | Exact vendor codegen/call closure, IRQ/audio deadline and worst P33 BUSY behavior; fixed bounded app/LCD/IO phases | Maximum complete feed and masked span, post-arm tail, each phase's worst duration, strict lease/IRQ inequality margins, timeout and bus-stall limits; no assumed safe retry or CS abort |
| Faults | Installed exception path, no-return saved frame, reviewed fault injection points and fresh recovery plan | No further P33/feed on first/nested fault during every feed phase, effective audio stop/silence and bounded reset; qualify bootstrap and memory-corruption exclusions explicitly |

Before any such experiment, target compilation/disassembly must establish exact
volatile widths/ordering, saved ICFG and terminal visibility, NOLOAD mailbox,
reachable calls and source/artifact bindings, no unresolved helpers, original
security audit and RAM/text/stack fit. Physical observations and source/codegen
review are separate gates. No hard 20-second enumeration label is supported.

The separately named audio-only owner candidate reuses the permanent selected
app and aggregate queues. Its new GPL platform binds accepted scanner events
and PCM copy/zero IRQs; rendering stays in main. It omits all LCD/SPI work.
FRONTEND_READY names phase2 truthfully for this explicit display-disabled
profile; LCD_READY remains its legacy numeric alias. No phase order, deadline,
P33 policy or immutable zero target qualification changes. The legacy candidate
and its initializer remain separate. See the dated selected-audio-owner note.
