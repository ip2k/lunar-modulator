# Device bring-up after the full audit — 2026-10-08

Lunar has a verified desktop/browser engine platform and target object
compile coverage; it does not yet have a linked board application or an
on-device Lunar result [verified: firmware/ tree and the four-profile compile
reports]. This plan follows the owner request to resume firmware work after
the audit. Corrections and validation are recorded in
[the remediation ledger](2026-10-08-audit-remediation.md).

## Runtime choice

The working recommendation is an independently permissive, SDK-free board
runtime. This supports a permissive release with GPL modules disabled and a
GPL-compatible release with them enabled [inferred; see
[the licensing evaluation](2026-10-07-sdk-runtime-evaluation.md)]. The owner
has been asked whether a faster GPL-only first firmware using Felucca's board
runtime is preferable. The recommendation is not an approved licensing
change. No board implementation has been copied or written.

Use Felucca/SLOOP as credited register/protocol and behavior references, with
confidence labels; copying their implementation creates GPL obligations.
Keep independently written board code separate from third-party code and
record provenance. The existing fm1-nes boot-info bridge is Apache-2.0 and
specifically bridges the stock SPL to newer SDK boot-info initialization;
its presence does not require an SDK-free application to link SDK archives.
Validate the actual entry/handoff contract chosen for the new application.

## First application and its gates

1. **Link the smallest diagnostic application.** Establish the stock SPL's
   entry and handoff contract, startup/data/BSS initialization, interrupt
   vector placement, ROM-call providers and linker sections. Preserve the
   stock package components. Produce an ELF/map/disassembly, with every
   unresolved provider identified. Apply the existing package and eFuse/IRQ
   checks to the real linked image; object-only pending checks are not passes.
2. **Prove the memory layout before adding the full UI.** The simulator app
   measures 4,939,408 bytes on the target, including 4,784,576 bytes of fixed
   arenas and 116,368 bytes for TFT state [verified: target size report]. Do
   not link that object layout unchanged. Separate application state from
   fixed simulator backing storage, use a bounded chain allocation policy,
   and choose strip/tile display buffering and bounded persistence staging.
   Account for static sections, alignment, stacks, nested interrupts, audio
   DMA, queues and worst-case allocation transitions in the map. The stock
   free-memory estimate is an upper bound, not an allocation guarantee.
3. **Bring up board services separately.** Check power/clock settings against
   stock evidence; initialize panel scanning and the LCD with a diagnostic
   screen. Bring up ALNK0/external-codec audio with silence first, then a
   bounded test tone. Confirm sample rate, channel order and half-buffer
   ownership on the actual unit. Document IRQ priorities and maximum nesting;
   keep rendering separate from display/USB work that can miss its deadline.
4. **Integrate one small engine.** Use the shared engine API and event timing
   rather than the browser wrapper. Start with one sound, no effects or
   persistence. Measure actual cycles, stack high-water marks, underruns and
   sample continuity under panel activity. Add sequencer/modulation and MIDI
   only after the basic render path is established.
5. **Make state changes transactional.** Preflight memory and module
   availability before replacing a live chain. Account for the overlap needed
   during transitions; do not assume two full chains fit. Keep shared state
   codec regressions in the device integration checks. Specify power-loss
   handling before any settings/state flash writes.

These are development gates, not completed hardware results or a schedule.
A minimal diagnostic application is the next implementation milestone; a
full engine/editor feature set is a later integration milestone.

## Bench and release boundaries

Use the current staged recovery policy in docs/07, not the historical blanket
ban. Soft-key UBOOT entry, matching backups and a bounded 4 KiB restore were
verified; full-image restoration and broken-application recovery remain
untested. No hardware traffic occurred in this audit-remediation work. Before
an application experiment, document its exact image, addresses, recovery
steps and the limits of the existing recovery evidence. Never replace the
stock SPL/OTA/cfg/layout or invoke eFuse writes as incidental bring-up work.

BLE and the mobile hardware editor remain deferred until an installable
firmware; their saved plan is
[the mobile note](2026-10-07-mobile-advanced-editor.md). USB/BLE support and
licence obligations must be evaluated against the actual linked providers,
not the SDK's top-level licence or simulator module list.
