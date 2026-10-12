# Diagnostic recovery cause and reported clocks

Read-only investigation at pushed checkpoint
`ad28c4db862d6fd921c9c89a94a5455d334a5880`. No firmware edit, device
operation, reset retry or fault injection was performed. Root owns hardware.

The retained stage6/result0 is compatible with a successful nonreturning P33
reset [inferred from verified native order]. It is not a demonstrated lock
stall. The least change worth considering is trial-bound RAM evidence before
and during the existing request, retaining its exact protocol and clocks.
There is no established clock or reset defect to fix yet.

## Exact source and native evidence

[verified] Current owned source hashes:

| File | SHA256 |
| --- | --- |
| `firmware/sdk-diagnostic/app_main.c` | `391b22e66101da5aa64682d68729e09f72bd7e9af3f784034227c60302d8a0ab` |
| `firmware/recovery/request.c` | `a19a3b42ad2b00c6f4008eb74188842acd10f7cf1922120c41e27eb9d10741dc` |
| `firmware/recovery/request.h` | `f9352fe0f6fa7bf005db935acda3756184e4ce533a0652f35dd32a45e8fdcc6c` |
| `tools/jieli/audit_sdk_diagnostic.py` | `e8ce7a43e43ef127ecaf87db55578b7cad7bb1a926f2be3ce92b8688ae7dff8b` |

[verified] Installed private candidate evidence remains
`build/sdk-diagnostic-final/`: app SHA
`991b569df7d131320e42ef34c1b619de586d2a7ba6236c0ea1c089731eb61fa9`,
ELF `8832aa4677a7da3aa7871da58a092e5c3e69d766b31d5e67744301ce437979e2`,
original listing
`79c87e8c1bdecaa8fec8b352c5116a2fa82b40b666e87e5777ef562184b23143`,
manifest `c54bdbfe99a0f8bfb8c69a655f1005af361c8baa44f3fae5c0e42f62198a2396`.
SDK commit is `e30b1ee375d1f2993fc23bf92c8b99006a6e5f9d`.

[verified] Hera's pinned vendor objdump
`/home/claude/mvave-fm1/sdk-v1213/toolchain/current/pi32v2/bin/objdump`
(SHA `cffc304e1a9be5dac22984a6ad48e81ef82b17166fd8864c251cf635c9663b73`)
regenerated `-d -mcpu=r3` from the exact ELF in
`/home/claude/mvave-fm1/sdk-diagnostic-final-20261011/`.
Saved local listing `build/diagnostic-recovery-cause/vendor-disassembly.asm`
hashes `1c6a247edf14f6a3b3e3535c6fb5229b5212493aefc810bab3235ef073d41c30`.
Its body equals the original listing byte-for-byte after three filename/header
lines; body SHA is
`2f061b6608f72ae0f41168620ae1d4a59339a0932688ef4e8daba1f863a85284`.
Metadata/checks are saved in `build/diagnostic-recovery-cause/evidence.json`.
No private binary or vendor listing belongs in Git or a release.

## Recovery timing and the nonreturning path

[verified against source and vendor listing] The worker starts its timer at
`0x0200297e`, before GPIO/panel setup and rendering. Its deadline is total
elapsed 20 seconds, rather than an additional 20 seconds after rendering.
Heartbeat increases both after each 256 successful panel bytes and during
soak ticks; 1976 does not establish current liveness or a tick count.

[verified] Native request order is:

1. Stage6 store `0x02002b2e`, then shared SDK `p33_lock` call `0x02002b34`.
2. Refuse an existing P33/RTC selection; each owned BUSY poll is limited to
   4096. Write exactly `usb_update_mode\0` to `0x01c7fd80..0x01c7fd8f`,
   synchronize, and verify all 16 bytes at `0x02002bb6..0x02002bc8`.
3. Select P33; send only opcode0x20, address0xa0 and reset mask0x10 at
   `0x02002bdc`, `0x02002be6`, `0x02002bf0`. The shared `send` body writes
   the START strobe through the native callback at `0x0200296e`, then
   synchronizes and polls idle.
4. Only if the request returns: assign recovery_result at `0x02002b6e`,
   unlock at `0x02002b70`, store stage7/8 at `0x02002b7e`.

[inferred] Reset may occur during the final data transfer, before its idle
poll, select cleanup, assignment or unlock returns. Stage6/recovery_result0
therefore fits that path as well as a lock/transfer stop. Even stage7 would
only show a returning transmitted request, not prove recovery enumeration.

[verified] SDK lock `0x01c00e86` uses nested per-core IRQ disable and an
unbounded TESTSET loop on initialized byte `0x01c025ec`; the exact ELF's
initial lock byte is zero. IRQ nesting state is at `0x01c02814`.
Another core stopping while holding P33 can block acquisition. No observed
record distinguishes that possibility. The current request is bounded only
after ownership; it does not promise fault-independent recovery.

[verified: retained parent receipts] Host target-reset intent is
`1791775833.548683`; the first same-port ROM snapshot is
`1791775855.3214695`, an interval of 21.7727865 seconds. The latter is an
observer snapshot, not the precise USB re-enumeration or CPU-start instant.
The delayed RAM read at `1791778274.585474` returned stage6/result0,
sys360MHz/lsb60MHz, elapsed20000, heartbeat1976 and recovery_result0.
This is consistent with the deadline [inferred], not proof of reset cause,
mailbox consumption, physical pixels, retained-RAM semantics or current CPU
state. Exact actual evidence and hashes are in
`notes/2026-10-11-diagnostic-first-ram-read.md` and the boot-trial note.

## Cached clock and startup evidence

[verified] ELF string reads identify `sys` at `0x020153e7`, `lsb` at
`0x02015380`, and `timer` at `0x020153e1`. `clk_get 0x02000778` returns
cached sys from `0x01c067d0+8` and lsb/timer from `+16`. These are SDK
calculations, not electrical measurements.

[verified] SDK main calls watchdog initialization at `0x02000c7a` and
`clk_early_init 0x020008d4` at `0x02000c7e` before the worker. Early clock
code derives cached sys from inherited register values at `0x10014`
(WL82 `CLK_CON2`), analog PLL words `0x119a0/0x119a8/0x119ac`, and the
USB-PHY word `0x16a00`. It derives cached lsb using `SYS_DIV 0x10008`
bits16..17 and bits8..10, each plus one, and stores it at
`0x020009f4`. Do not substitute a generic header macro's similarly named
divider for these exact native bit fields. Early initialization also changes
clock/P33 settings, including `p33_spicon_clock_div(4)` at `0x02000ace`;
it is not wholly read-only.

[verified] The raw PLL/selection/divider values were not captured in the
32-byte actual record. The sys360MHz report cannot identify its inherited
configuration or prove the chip's electrical frequency. Owned worker source
does not call `clk_set` or `system_clock_set`; its acceptance range includes
360MHz. SDK `clock.h` documents a 24..396MHz switching range, which does not
qualify the owner's rails or every FM-1 for that speed. Changing to 240MHz
without reviewing the exact clock/rail transition would be a new experiment.

[verified] Pinned SDK files under Hera
`/home/claude/mvave-fm1/sdk-v1213/source-sdk/`:
`include_lib/driver/cpu/wl82/asm/WL82.h` SHA
`6f5a44f39282f66203d837a1c74c9d8197d2856547356fce8ed0d191318ff645`,
`include_lib/driver/cpu/wl82/clock_hw.h`
`ae1ea1b672b3855f6b0e2378d9ee1583e1b87614ed617db3d41f001681f855ae`,
and `include_lib/driver/cpu/wl82/asm/clock.h`
`60bde8b1d8bce0c282520094f85886417a42674ab2dba15e17fdfc572aaf5d72`.

[verified] Startup `update_result_get 0x02001bbe` reads update information
from the mailbox and clears 80 bytes at mailbox+8. A prospective evidence
record must not use that mailbox, including its currently unused-looking
tail. SDK main subsequently records its startup reset reason at
`sys_rst_rs 0x01c02870` after watchdog/clock setup and P33 reason reads;
that cached reason concerns entry into this application, not the later
return to ROM. The unchanged integrity callback is scheduled at 8000ms and
has the reviewed no-key-registered return branch. Neither timing coincidence
nor the retained record proves a watchdog/integrity reset instead of P33.

## Smallest proposed follow-on, no implementation authority here

[proposal] Keep reset bytes, shared lock ownership, watchdog, rails and clocks
unchanged. Add an audited owned RAM record, for example 64 bytes outside
mailbox/SDK allocations, with magic/version, a fresh 128-bit nonce embedded
per candidate/trial, phase and complement, mailbox-verification flag, and
bounded diagnostic fields. Exact allocation/address comes from the new link;
it is not a proposed arbitrary RAM write. Publish with volatile stores and
CSYNC, and require coherent nonce/version/phase/complement on read. A nonce
is bound to the new image/campaign, not claimed unique across repeated boots
of the same image. Preserve the one-attempt campaign boundary.

[proposal] Distinguish before-lock, acquired, mailbox-verified and
final-byte-about-to-START phases. The final phase must be committed before
the exact reset START write; a post-return flag is insufficient for a
nonreturning reset. This proves execution/intent under the retained-record
premise, not transmission, reset cause or ROM consumption. Preserve the
original 16-byte ROM marker exactly. Include cached startup reason and
reported clocks if available without new P33 transactions. Capturing raw
clock words in the worker shows post-initialization state; capturing truly
inherited state requires a separate audited early-startup hook after RAM
readiness but before watchdog/clock initialization, a larger change.

[proposal] A new build needs exact native instruction/allocation audits,
guarded new read window/decoder, file-only negative tests and independent
review before any new installation. Observe return to ROM and then complete
stock restore/reset/identity separately. If fault-independent lock acquisition
is required, a bounded compatible try-lock is a distinct ABI/core/IRQ audit;
never force-unlock another owner. No alternate reset-domain fallback is
authorized by this note.

Warm reset of an interrupted/corrupt application that SPL rejects, without
USB_KEY, remains unproved. Successful retained-loader NOR restoration does
not answer that CPU/SPL question. Physical USB_KEY remains untried; no new
fault injection is proposed here.

Checks: exact source hashes, ELF reads, pinned vendor disassembly/body
comparison, SDK header/native register reconciliation and retained timing
receipt inspection. No tests were rerun for this note. Prior semantic-tool
evaluation did not supply isolated worktree language coverage; shared
selection was preserved and source/native inspection is the stated fallback.
Root owns checkpoint/push and any follow-on implementation decision.
