# Puya 85 60 14 identity and NOR-busy recovery evidence

Date: 2026-10-14. Offline manufacturer-source review on exact base
`3807f3de8d0e1d1ef9b659678a1b15607835bc5c`, branch
`codex/2026-10-14-nor-busy-recovery-research`. No firmware source or admission
policy was changed.

## Decision

[verified] JEDEC RDID `85 60 14` identifies an 8-Mbit Puya SPI NOR density/type,
not a unique orderable suffix. Puya datasheets explicitly assign the same tuple
to P25Q80H, P25Q80SH, P25Q80U, P25Q80L, P25Q80SL and P25Q80SLE. This list is
only the variants confirmed in manufacturer documents reviewed here, not a
claim that it exhausts Puya history. Their operating-voltage ranges differ:
H/SH are 2.3–3.6 V, U is 1.65–3.6 V, and L/SL/SLE are 1.65–2.0 V. The FM-1's
ROM-reported ID alone therefore cannot establish the fitted suffix, reset
feature set, or applicable timing table. Do not select a less-conservative
watchdog or reset policy from this ID.

[verified] Reset is not a safe escape from an in-progress operation in the
reviewed documents. H and U document the 66h/99h software-reset sequence and
warn that reset during program/erase disables the operation and data under
processing could be damaged or lost. SH documents RESET#; driving it low during
program/erase terminates the operation and data could be lost. H's parameter
table reports its hardware RESET# pin as unsupported. Thus even the flash's
own reset mechanisms are not a recovery primitive during WIP. This does not
prove what the FM-1's MCU watchdog toggles: no evidence reviewed shows that the
watchdog toggles an external NOR reset pin or removes NOR power.

[verified] Puya's power-transition protection language is narrower than a
rollback guarantee. SH says the state machine initializes to standby on power
up and lists POR/command validation/WREN protections against accidental write
cycles. That text does not promise old-or-new contents after loss of power
mid-program/erase, nor does it state that a bootloader can safely fetch XIP
while an interrupted operation remains busy. Power-up initialization cannot
be used as evidence that bytes being processed were preserved.

## Watchdog assessment for current firmware

The existing task notes and pinned SDK evidence show an 8-second reset-mode
watchdog, normally fed from the main loop through XIP code. The destructive NOR
path disables XIP and polls status from RAM. Its safe return condition is a
completed status transaction positively reporting WIP clear; when transport
or WIP remains unknown it cannot return to XIP. The normal-loop feed is not
available in that interval.

No safe bounded watchdog policy is established by these datasheets. Not feeding
allows the MCU watchdog to reset while NOR readiness may be unknown. Feeding
only while busy can keep the CPU trapped indefinitely if status stays busy or
unreadable, and the existing feed path is not a verified RAM-resident closure.
A nominal/max erase timing row is not a recovery guarantee: the exact part is
unknown, the datasheets' timing notes describe characterization, and neither
document guarantees interrupted-state recovery. The recommendation not to add
a busy-loop feed, disable or force-reset the watchdog, or return to XIP on a
finite timeout was a conservative interpretation of those unknowns, not an
owner or project prohibition. The owner has authorized robust recovery
development; the follow-up below evaluates a concrete fail-stop candidate.

## Minimum next evidence and implementation gate

The exact suffix is needed before making part-specific timing, voltage, or
reset-recovery claims. It is not a prerequisite to designing software that
never returns to XIP while readiness is unknown. A safe software path can be
developed and target-audited from current source; behavior after power loss or
a later user power cycle remains a separate acceptance question.

If no manufacturer guarantee exists, any electrical characterization must be a
separately designed, owner-authorized sacrificial-part experiment; this task did
not authorize or perform it. Do not test by interrupting the owner's flash.

## Primary sources and cross-checks

- Puya [P25Q80H datasheet V1.7](https://www.puyasemi.com/download_path/%E6%95%B0%E6%8D%AE%E6%89%8B%E5%86%8C/Flash/P25Q80H_Datasheet_V1.7.pdf): RDID table, software reset section, parameter table (H hardware RESET# unsupported).
- Puya [P25Q80SH datasheet V1.5](https://www.puyasemi.com/download_path/%E6%95%B0%E6%8D%AE%E6%89%8B%E5%86%8C/Flash/P25Q80SH_Datasheet_V1.5.pdf): RDID table, RESET# behavior, and data-protection/power-up language.
- Puya [P25Q80U datasheet V1.8](https://www.puyasemi.com/download_path/%E6%95%B0%E6%8D%AE%E6%89%8B%E5%86%8C/Flash/P25Q80U_Datasheet_V1.8.pdf): RDID table, 1.65–3.6 V range and reset-during-WIP warning.
- Puya [P25Q80L datasheet V1.7](https://www.puyasemi.com/download_path/%E6%95%B0%E6%8D%AE%E6%89%8B%E5%86%8C/Flash%20%E8%8A%AF%E7%89%87/P25Q80L_Datasheet_V1.7.pdf), [P25Q80SL datasheet V1.5](https://www.puyasemi.com/download_path/%E6%95%B0%E6%8D%AE%E6%89%8B%E5%86%8C/Flash%20%E8%8A%AF%E7%89%87/P25Q80SL_Datasheet_V1.5.pdf), and [P25Q80SLE datasheet V1.0](https://www.puyasemi.com/download_path/%E6%95%B0%E6%8D%AE%E6%89%8B%E5%86%8C/Flash%20%E8%8A%AF%E7%89%87/P25Q80SLE_Datasheet_V1.0.pdf): reviewed RDID tables also print `85 60 14`.
- Puya [P25Q80SH product page](https://www.puyasemi.com/en/h_series653/3173.html), [P25Q80H product page](https://www.puyasemi.com/en/h_series653/3172.html), [P25Q80L product page](https://www.puyasemi.com/en/l_series483/3141.html), and [official downloads catalog](https://www.puyasemi.com/en/download.html) for family voltage ranges and current datasheet revisions.
- Existing project audits: `notes/2026-10-14-nor-part-interrupt-evidence.md`, `notes/2026-10-14-native-nor-wdt-strategy.md`, `notes/2026-10-14-nor-program-semantics.md`; pinned SDK and writer references are recorded there.

No device command, USB/MIDI/flash/power/reset operation, target measurement, or
SAVE enablement occurred. This establishes manufacturer-documented identities
and warnings only; exact fitted part, MCU watchdog-to-NOR electrical coupling,
and physical recovery remain unknown.


## Follow-up: fail-stop design and journal containment

Date: 2026-10-14. Source review on this note's pinned checkout; note-only,
offline. This section corrects the recommendations above where they could be
read as a ban on implementing an owner-authorized recovery strategy.

### What the current source establishes

- `firmware/third_party/dinghy/hal/fm1_sys.h:32-77,85-93`: the P33 transfer
  helpers are ordinary code, not marked `RAMFN`. A wait timeout increments a
  counter but `fm1__p33_xfer()` still returns sampled data, and the WDT feed
  is an unchecked OR write to P33 register `0x80`. `fm1_wdt_stop()` writes
  zero to the same register. This source does not verify that feed/stop took
  effect.
- `firmware/third_party/dinghy/src/platform.c:254-284,305-343`: the app arms
  reset-mode WDT with `0x0D` during startup and feeds from the normal main
  loop. That feed path is unavailable during the IRQ-off, XIP-off flash call.
- `firmware/third_party/dinghy/hal/fm1_flash.h:190-212,249-305`: destructive
  calls wait for a completed status transaction with WIP clear before
  `fl_exit()` restores SFC/XIP. The loop may remain in RAM indefinitely if
  status stays busy or cannot be read. Its `max_us` parameter reports
  lateness; it does not authorize an unsafe return.
- The target-closure note
  `notes/2026-10-14-nor-real-writer-closure.md` inspected a retained
  writer-only pi32v2 closure, but found no WDT implementation inside that
  closure. The separate continuous500 ELF's writer functions were stubs. Thus
  neither artifact proves a complete RAM-resident WDT feed implementation.
- `firmware/native/project_store.h:47-84,101-117` uses two project slots:
  it scans both, chooses the older/invalid slot as the destination, erases
  only that destination, writes and validates its body, writes/readbacks the
  header fields, then writes the commit word last and verifies again.
  `firmware/native/settings_journal.h:54-73,91-112` likewise preserves the
  selected old sector while erasing and writing the other sector, with its
  commit word last. For an already-valid old slot, a damaged in-flight
  *inactive* payload can be rejected by existing hash/CRC/record validation;
  that data-containment argument does not require an old-or-new guarantee for
  the inactive bytes.

### A bounded conservative candidate

The smallest software candidate to prototype is a watchdog lease around each
individual destructive NOR operation, not a new watchdog loop inside the RAM
poller:

1. With XIP available, audio/display readers quiesced, and before issuing WREN
   or any destructive opcode, use a checked P33 operation to stop the reset
   watchdog and read back a control state whose disabled meaning is separately
   verified. If transport or readback is uncertain, refuse before the NOR
   command.
2. Execute the existing RAM writer. Keep its current rule: after possible
   command acceptance, never restore XIP until a completed status transaction
   positively observes WIP clear. A deadline may record failure but must not
   cause return.
3. On a positive-ready exit only, restore SFC/XIP and IRQ state, re-arm the
   reset watchdog immediately, and return the preserved transport/readiness
   result. SAVE is synchronous, so any watchdog service between completed NOR
   operations must be an explicit XIP-safe checkpoint in the I/O adapter;
   `platform_poll()` does not run during the callback.
4. If readiness cannot be positively established, branch to a minimal
   RAM-resident terminal loop before any SFC/XIP or IRQ restoration. With the
   watchdog verified stopped, this is a deliberate hard hang rather than an
   automatic MCU reset while the NOR may still be busy. It has no automatic
   recovery or user-visible status, and power cycling still has unverified
   flash/SPL behavior.

This candidate does not depend on knowing the precise NOR suffix or assuming
that an operation always completes within a datasheet maximum. It does depend
on proving P33 watchdog stop/readback/re-arm semantics on this platform,
including the disabled-state encoding and whether another reset source exists,
and that every
post-command unknown-state path remains in RAM with interrupts and XIP
unrestored. The current P33 wrappers are not adequate for this: they hide
transfer timeout, so a checked variant and target disassembly/map audit are
prerequisites. If stop cannot be positively verified, the writer must refuse
before WREN rather than proceed with the original watchdog deadline.

A RAM-resident feed alternative is possible to investigate, but is larger and
does not improve the terminal-state contract: a verified feed could keep the
CPU alive in the RAM poll forever after permanent WIP/status failure. It needs
the complete P33 feed call/data closure in RAM plus checked transport and
readback; moving only `fm1_wdt_feed()` into `.ram_text` is insufficient.
It should not be treated as a fail-stop by itself.

### Limits and next implementation boundary

Two-slot journaling contains loss of the *inactive candidate data* after a
previous valid commit, provided the two physical extents are independently
verified non-overlapping and the device can later be read. It does not solve
booting or scanning while the chip remains busy, lost access to the prior
active slot, a first save with no valid predecessor, or corruption of the
commit metadata. A positive-ready gate must therefore remain independent of
the journal recovery guarantee.

The next offline implementation can add checked P33 watchdog stop/readback/
re-arm APIs and an analysis-only RAM terminal branch, then use the pinned
pi32v2 toolchain to audit exact call/data/stack residency and control-flow
edges. Host fault tests should prove: failed stop means zero WREN/erase/program;
post-command unknown status cannot reach XIP/IRQ restoration; positive-ready
restores XIP before re-arm/return; and the transaction reports failure even if
readiness eventually clears. No such implementation was made here. Until
those checks and owner review pass, physical SAVE remains disarmed. This
analysis establishes neither watchdog hardware behavior nor post-power-loss
recovery.
