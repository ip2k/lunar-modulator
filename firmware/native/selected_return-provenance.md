# Selected return offline policy — 2026-11-01

This is a **host fake only** GPL-3.0-only derivative, not a selected target
profile or a hardware return implementation. Both proof and fake-MMIO defines
are required; the pi32v2 target macro is rejected. Nothing selects these objects
from the diagnostic builder, startup or default platform. No target binding,
guard operation, reset whitelist or release/install admission is added.

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
See `../third_party/dinghy/LICENSE`, `LICENSING.md` and `UPSTREAM.md`.
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
are in `selected_return-inventory.json`. All 16 source/doc inputs named by that
review remain byte-identical at this branch's base
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
provide assumptions; no flag establishes physical permission. There is no real
mailbox/MMIO/ICFG/csync/halt binding. Actual watchdog stable-field semantics,
reset mode and measured lease, inherited write-guard permission for the exact
mailbox, TIMER4 frequency/ownership and reset-source mailbox retention/ROM
consumption remain unqualified. No target profile can be admitted from this test.
`atomic_signal_fence` is only a host compiler barrier, not target `csync`.

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
