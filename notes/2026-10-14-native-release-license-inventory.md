# Native release licence inventory — 2026-10-14

This is a factual repository inventory, not a legal opinion or release approval.
The owner has directed an SDK-free native firmware path, a combined GPLv3
application, and a root licence change; those changes are not yet reflected in
the checked-out repository. The [direction note](2026-10-12-native-gpl-firmware-direction.md)
separates the reusable MIT core from the combined GPL application and requires
component notices and complete corresponding source.

## Evidence boundary

The retained [save-scheduler link receipt](2026-10-14-save-scheduler-verification/link-receipt.json)
records 282 input objects, a successful link (`link_exit: 0`), ELF SHA-256
`ed067d2233d8b2b7994a3d8a0740a5a9b3ddfa6ec5acf06b990e0b49365cb9ab`, and
explicitly says `hardware_tested`, `installable`, `save_scheduling_integrated`
and `physical_storage_admitted` are false. Of the inputs, 160 are under
`/catalogue/shard-*/obj/`, 117 are under the mixed-project link output, and
five are save-scheduler integration objects. This is evidence of a diagnostic
link, not an admitted release image. The receipt records object inputs, not a
per-section post-GC attribution report.

The catalogue object inputs include the ordinary Lunar code plus GPL paths
`gpl/felucca/felucca_bridge.o`, `gpl/fm1-x0x/dsp/{bass303,drum808,drum909}.o`
and `gpl/fm1-x0x/seq/tb3po.o`. The output inputs include musl-subset objects,
compiler arithmetic objects, `printf.o`, `tlsf_runtime.o` and `tinflate.o`.
The names correspond to the existing notices below. `engines/modules/catalogue.mk`
defines test-only `test-sine`, `test-gain` and `test-ext` alongside production
modules; because this receipt does not identify a release profile or prove
post-link retention, it must not be used alone as the final shipped component
manifest.

## Components evidenced by the receipt

| Receipt component | Repository notice/provenance | Recorded licence |
| --- | --- | --- |
| Lunar application, sequencer/state, wrappers and catalogue objects under `our/`, `c/`, `sim/`, `state/`, `mod/`, `midi_fx/` | Root [`LICENSE`](../LICENSE); third-party detail in `engines/` notices | MIT for repository-authored code, subject to separately listed imported sources |
| Mutable Plaits/Braids and stmlib DSP | [`engines/third_party/mutable/UPSTREAM.md`](../engines/third_party/mutable/UPSTREAM.md); `stmlib/LICENSE` | MIT; vendored file headers retained; stmlib GPL UI event queue is documented as excluded |
| Google msfa | [`engines/third_party/msfa/UPSTREAM.md`](../engines/third_party/msfa/UPSTREAM.md), `engines/third_party/msfa/LICENSE` | Apache-2.0 |
| Schwung Sophie and PSX Verb modules plus ABI headers | `engines/third_party/schwung{,-modules/*}/UPSTREAM.md` and component `LICENSE` files | MIT; local PSX Verb correction is documented in its upstream record |
| Felucca bridge and engines | [`engines/third_party/felucca/UPSTREAM.md`](../engines/third_party/felucca/UPSTREAM.md), `LICENSE`, `LICENSING.md` | GPL-3.0-only |
| fm1-x0x bass, drum and sequencer objects | [`engines/third_party/fm1-x0x/UPSTREAM.md`](../engines/third_party/fm1-x0x/UPSTREAM.md), `LICENSE`, `LICENSE-Open303`, `LICENSING.md` | GPL-3.0-only files; Open303-derived bass portions have a separate MIT notice; 909 recordings are documented as GPL-3.0 |
| musl math/string/ctype subset | [`firmware/third_party/musl/UPSTREAM.md`](../firmware/third_party/musl/UPSTREAM.md), `COPYRIGHT`, `inventory.json` | Per-source notices include Sun, FreeBSD, Arm and MIT grants; no single uniform licence is asserted |
| LLVM compiler-rt arithmetic | [`firmware/third_party/compiler-rt/UPSTREAM.md`](../firmware/third_party/compiler-rt/UPSTREAM.md), `LICENSE.TXT`, `inventory.json` | Apache-2.0 WITH LLVM-exception |
| formatted output | [`firmware/third_party/printf/UPSTREAM.md`](../firmware/third_party/printf/UPSTREAM.md), `LICENSE`, `inventory.json` | MIT |
| TLSF allocator | [`firmware/third_party/tlsf/UPSTREAM.md`](../firmware/third_party/tlsf/UPSTREAM.md), `LICENSE`, `inventory.json` | BSD-3-Clause |
| tinf decoder | [`firmware/third_party/tinf/UPSTREAM.md`](../firmware/third_party/tinf/UPSTREAM.md), `LICENSE`, `inventory.json` | zlib |

The receipt contains no LXR or MIDIbox source/object path, and neither appears
in the native engine module catalogue or native build fragments. The existing
source record says LXR's no-sale condition conflicts with GPL, and MIDIbox
needs its author's permission; there is no evidence in this receipt that
either enters this linked set.

Dinghy is part of this link even though the receipt has no standalone Dinghy
object path. `tools/native/build_application_probe.py` reads
`firmware/third_party/dinghy/src/platform.c`, applies pinned probe adaptations
(including the no-write range, smaller canvas and other probe-only changes),
and writes it as generated `platform.c` in the build directory. The compiled
`firmware/native/app_probe.c` includes that generated file directly, and calls
`platform_poll()`. The source-hash receipt names `app_probe.c` and 18 Dinghy
HAL/source inputs (including the HAL headers, `usb.c`, `ota.c`, `recovery.c`,
and `uac_fir.h`); it does not separately name the generated amalgamation or
`src/platform.c`. This mapping shows the platform is an integrated part of the
application object, not an absent component; the object receipt still does not
attribute individual post-GC sections. Dinghy's `UPSTREAM.md` identifies its
FM-1 platform sources as GPL-3.0-only, and `LICENSING.md` attributes the HAL,
loader and inherited Felucca/SLOOP platform files to their upstream authors.
Accordingly this diagnostic link inherits Dinghy's GPL-3.0-only platform
provenance in addition to the separately listed engine components. Dinghy's
source notices/license and the inherited upstream credits must be accounted
for in any combined-image source and notice bundle.

## Distribution work still needed

1. Update the root licensing files and user-facing documentation to distinguish
   the MIT-licensed reusable core from the GPL-3.0-only combined native
   application, preserving every upstream notice. `LICENSE` is still MIT.
   Existing [docs/12-sequencer.md §6](../docs/12-sequencer.md) describes the
   older restriction on sharing GPL images linked with JieLi libraries; that
   condition should be reconciled with the SDK-free native route only after an
   actual native link proves those libraries are absent.
2. Produce a release-specific component manifest from the final linker input
   and retained sections, tied to the exact ELF/package hashes and selected
   production module list. The current receipt is not such a release manifest
   and includes test-module catalogue inputs.
3. Package the applicable licence texts and attributions in a consolidated
   release notice and provide the corresponding source/build material for that
   exact image. Existing `LICENSE`, `UPSTREAM.md` and `inventory.json` files
   provide useful provenance, but no consolidated native firmware notice or
   image-specific source bundle is evidenced here. Preserve generated tables,
   sample-origin notices, local patches, source pins, build scripts/configuration
   and the exact toolchain/build inputs needed to reproduce the image.
4. Retain the existing firmware safeguards in any future package path: stock
   SPL and byte-identical `isd_config.ini`, `ota.bin` and `cfg` checks in
   `tools/jieli/package_guard.py`. This inventory does not establish that a
   package was built or passed that guard.

No legal permission conclusion, release readiness finding, hardware acceptance,
or installation claim is made by this note.
