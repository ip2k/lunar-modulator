# Separate stock handover startup preparation

2026-10-09. Personal MIT stream
`feature/2026-10-09@handover-startup-preparation`, explicitly based on
PR #115 `5e309ea`. The version/trailer research is separate PR #119;
this implementation does not depend on it. No device traffic occurred.

## Concrete linked result

Added `firmware/handover/` alongside the unchanged inert source. Own SP and
SSP stack reservations and guarded six-word capture reduce specific startup
gaps without introducing SDK/ROM/MMIO/board code. Source and algorithm are
independently authored; the six-word/23-slot dimensions and SPL pointer are
facts from the stock SPL research and the credited Apache-2.0 fm1-nes bridge,
not copied GPL bare-metal firmware. No SDK consumer is linked.

Fresh target build on aeon's existing bounded Docker/toolchain cache passes
SDK-free link/eFuse audit with zero failures/pending and memory/flat report
[verified]. Artifact facts:

- Entry `0x02000120`, 288 flash bytes, four data bytes, 116 BSS bytes.
- 8352 reserved RAM bytes within 16 KiB link budget at `0x01c02000`.
- SP guard `0x01c02080`, bottom `0x01c02090`, top `0x01c03090`.
- SSP guard `0x01c03090`, bottom `0x01c030a0`, top `0x01c040a0`.
- App SHA-256 `0991eae9c0fc77bf4ed80f73b2d643972d70bb9151b3b0da29a2a68d41a1b19c`.
- ELF SHA-256 `f02c501923991780532ca4b47dda01d306aa92cf58c1aa2c4838c59e6690631f`.

Vendor disassembly's 282 entry/text byte columns match ELF bytes exactly
[verified]. `_start` begins `60 00` CLI at `0x02000120`, sets SP via
`64 e0 80 1e` at `0x02000128`, sets SSP via `64 e0 80 1d` at
`0x02000132`, then calls `lunar_handover_start` at `0x02000136`.
The compiler preserves incoming r0 in r4 at `0x02000140` before memory
initialization, stores it at state+12 afterward, compares it to
`0x01c7fe08` at `0x020001aa` and skips dereference on mismatch. The capture
at `0x02000204` uses a 23-store zeroing loop and a six-word source-load
loop; no libc/ROM/SDK helpers or access to the trailing SPL header survives.
The non-returning runtime calls only linked XIP capture/memory helpers.

CLI encoding and SSP assignment are target compiler/vendor decode evidence;
the stock SPL itself sets SSP near raw offset `0x46` and masks IRQ before
its app call [verified static decode]. This is not proof of interrupt,
exception or core behavior after an actual jump on this device.

The script accepts an explicit `handover` variant and puts results in
`build/jieli-handover/`; the default still builds inert with its original
link order. Report defaults remain the inert contract and reject the new
allocated SSP section. Explicit handover reports require exact SSP section
boundaries, size/alignment, no overlap with SP, NOBITS type and permissions;
default SDK link audit is unchanged. Staging and app-replacement modeling
still use the inert report and do not admit this variant.

## Remaining runtime boundary and next experiment

Own SSP storage is complete as a **link** contract only. RAM overlaps the
loaded SPL body (`0x01c02000..0x01c05820`, header excluded); no safe-private-RAM
claim follows. The upper boot-info input is outside the bounded low RAM
initialization and stacks [verified link], but its validity on a running
device remains unobserved. Word zero may retain a pointer to the separate
SPL header: it is opaque, not relocated or usable after future RAM changes
without a verified consumer contract. No SDK consumer or exception vector
setup is provided. Keep the variant non-returning with no calls into
overwritten SPL RAM, and preserve inherited SFC/cache/XIP configuration.

Unknown/incomplete final watchdog, clock/power, exception, IRQ and secondary
core state remain explicit. The SPL's early watchdog-disable AND does not
prove its final state across the unresolved indirect callback. No output
driver or transport observes this RAM state; a spin may reset and would not
be an externally useful diagnostic. These facts are preserved rather than
calling the linked variant safe or executed.

Next concrete implementation: verify exact pinned WL82 clock/power/GPIO/SPI
register semantics and stock board transitions, then an independent bounded
fixed-screen LCD variant. A later exact candidate/write-range review and
fresh backups follow the owner's staged policy; full-image/broken-app recovery
is untested and must remain an explicit risk, not an invented blanket ban.
Version-specific loader acceptance and opaque trailer preservation must be
reviewed before emitting an installable container. No binary container was
created, transmitted or installed here.

## Reproduce and handoff

Build command and state meanings are in `firmware/handover/README.md`.
Target cache remains `jieli-linux-toolchains-20250324.1`, not the later
acquisition pin. The existing 4 GiB RAM/swap and `docker-batch.slice` limits
were used; no toolchain/host installation occurred. Source-visible C/assembly
and shell layout checks, focused host capture tests, corrupted SSP layout
tests and actual target audit/byte comparison provide this checkpoint's
evidence. See prior notes for Rarefaction/Serena Python-root limitations;
neither verifies this CPU ABI.

The focused host/layout/audit/package suite passed 121 tests with the local
stock fixture and original inert target enabled [verified]. A fresh default
inert target rebuild remains 200 flash bytes, 4144 reserved RAM bytes and
SHA-256 `5566edb6742aebb695a4ed2ab0e9d979ebadb615190bb030c55f59f2258fee08`,
with zero audit failures/pending [verified]. Rarefaction C orientation used
the original checkout's Apache bridge, reporting fallback clangd flags and
no root compilation database; Serena's symbol overview found both bridge
functions. Neither index describes the new managed-worktree target ABI.

Parent owns independent review, CI and integration. No merge occurred in
this worktree. Keep ignored ELF/disassembly/report artifacts for review and
regenerate through the named LAN command if the worktree is restored.

## Change log

- 2026-10-09: Linked separate SP/SSP preparation and bounded boot snapshot;
  retained inert default, explicit layout guard and non-execution boundary.
