# Native GPL firmware direction — owner, 2026-10-12

## Goal and acceptance

The owner clarified that the next 24-hour target is **fully functional Lunar
Modulator firmware, web-installable and running on real FM-1s**, rather than a
diagnostic release. The owner directed removal of JieLi SDK runtime linkage and
reuse of native open firmware approaches, with GPL engines included. This
supersedes the earlier diagnostic-only release endpoint and planned SDK runtime.
Heavy builds belong on Hera; parallelizable verification uses 16 chunks.

Acceptance requires the actual Lunar application: physical display and panel,
keys and encoders, audible audio, MIDI, sequencer and effects, persistence,
browser installation/update, and verified recovery. Host rendering, compile
checks, simulated flashing and diagnostic execution are supporting evidence;
none individually establishes this endpoint. Hub listing is a subsequent
publication step, not evidence of a successful hardware installation.

## Existing work to reuse

[verified] `engines/Makefile` already defaults `FM1_GPL_MODS ?= 1`, rejects other
values than 0/1, generates `fm1_gpl_mods.h`, and collects gated GPL objects.
`engines/mk/felucca.mk`, `fm1-x0x.mk` and `x0x-crater.mk` gate engine sources;
`engines/src/registry.cc` gates entries and license rows. The simulator and
JieLi compile-only check propagate the same switch. CI covers both settings.
Do not add another engine-license switch or mistake this one for an SDK toggle.

[verified] The earlier [runtime evaluation](2026-10-07-sdk-runtime-evaluation.md)
already distinguishes engine selection from runtime linkage and explains that
Felucca's GPL HAL makes the whole application GPL with either switch setting.
The reusable MIT core can remain MIT while the combined firmware is GPLv3,
retaining all component notices and complete corresponding source. A repository
license change must preserve third-party grants and contribution provenance;
changing the root LICENSE does not itself remove incompatible dependencies.

## Platform candidates and limits

[reported] [Dinghy](https://github.com/zvenson/dinghy) provides a small application
surface over the Felucca/SLOOP native platform with display, panel, USB-MIDI,
USB audio, settings, update service and rescue. Its author reports real FM-1
testing. [verified] Read-only local checkout inspected at
`d44df7db09b98ccad2f1233b8f83f5f09c04829e`; its platform is GPL-3.0-only.
Its logo is not covered by the code license and must not enter Lunar's product.

[verified] Dinghy's package builder selects a different SPL hash from Lunar's
stock-only safeguard, and builds its own OTA loader. Reusing its application
runtime does not authorize copying that package policy. Before hardware use,
review its flash bounds, settings/update staging and stock-header compatibility;
retain Lunar's backup, bounded write, stock SPL and recovery protections.

[reported] [Groove OS's own documentation](https://www.groove-os.com/manual/firmware)
describes a V15 modification retaining the stock FM engine, MIDI, Bluetooth and
updater. It is an installation/recovery reference, not evidence of an SDK-free
runtime equivalent to Felucca/SLOOP.

## Current physical boundary and next steps

[verified in retained V8 receipts] The SDK diagnostic was installed, read back,
ran for 20 seconds and returned to mask ROM. Physical display appearance is
unconfirmed. The diagnostic target remains installed; stock restore is prepared
but has not executed. Never replay the consumed diagnostic/backup campaign.
Complete the separately admitted restore and stock boot before native trials.

Then vendor only reviewed, attributed open runtime sources; adapt the existing
Lunar engine/sequence API to its audio and panel contracts; link without JieLi
runtime archives and audit actual symbols, RAM/flash and audio timing on Hera.
Preserve the existing engine GPL switch and use it on for the native firmware.
Build a stock-safe package and exercise browser installation, subsequent update,
rollback and interruption recovery on the real unit before claiming release.

This is a recorded implementation direction. No native runtime has been
integrated and no repository license has changed as part of this note.
