# Licensing and source boundaries

This file records the repository's licensing structure and source provenance; it is not legal advice, a release manifest, or release approval.

## Combined native application

The combined Lunar native firmware application is licensed under the GNU General Public License, version 3 only (`GPL-3.0-only`). The root [`LICENSE`](LICENSE) is the unmodified GPLv3 text already distributed with the Dinghy platform at `firmware/third_party/dinghy/LICENSE`. The native application integrates that platform and GPL-licensed native files/selected engines. The `FM1_GPL_MODS` engine-selection option does not remove Dinghy's platform code and does not change this combined application's licence.

This statement concerns the native application as a combined work. It does not relicense separately licensed components or establish release readiness. For a specific distributed image, determine its actual retained inputs, preserve all applicable notices and provide the corresponding source and build material. The 2026-10-14 diagnostic link receipt is not a release-specific manifest.

## Reusable first-party MIT grant

[`LICENSE-MIT`](LICENSE-MIT) is byte-for-byte the original root MIT license from commit `a0d46a9c9611a2240610df5df5d47117b93c1c34`. That existing grant is preserved; this change does not purport to withdraw or narrow permissions previously granted for project-authored material. For reusable first-party code going forward, the explicitly scoped MIT core is:

- `engines/seq/` and `engines/include/fm1_seq.h`: the C sequencer rewrite, whose source records the Movy `seq-core` files it follows and whose upstream notice identifies Movy as MIT. The implementation is a rewrite; the Movy notice in `engines/third_party/movy/LICENSE` and `UPSTREAM.md` remains required.
- `engines/state/`: Lunar's state serialization, validation and conversion implementation. Its Movy-compatible codec identifies its own MIT licence; the directory is first-party code covered by the prior root grant. This scope does not include unrelated imported code, and existing file-level notices continue to control.
- MIT-marked files in `firmware/native/` remain MIT as indicated by their existing `SPDX-License-Identifier: MIT` headers. The directory as a whole is not MIT: GPL-marked files in it retain their own `GPL-3.0-only` identifiers. `firmware/native/libc_compat/` files likewise retain their existing MIT identifiers.

The above is an explicit reusable-core scope, not a claim that every file in those directories or the repository has the same licence. Where a file or subtree carries its own SPDX identifier, upstream licence or attribution, keep that boundary and notice. For newly added reusable first-party code, mark its intended scope with an SPDX header and keep this file and its tests in sync. Other first-party application code that forms part of the combined native firmware is covered by the GPL-3.0-only application grant, subject to the preserved permissions in `LICENSE-MIT` for pre-transition code.

## Third-party material and notices

Third-party sources retain their own grants and notices. Important native-link components documented in the 2026-10-14 inventory include:

| Component | Location | Recorded licence / notice |
| --- | --- | --- |
| Dinghy platform | `firmware/third_party/dinghy/` | GPL-3.0-only; retain `LICENSE`, `LICENSING.md`, `UPSTREAM.md`, source notices and inherited credits |
| Felucca engines | `engines/third_party/felucca/` | GPL-3.0-only; retain its upstream record and notices |
| fm1-x0x engines | `engines/third_party/fm1-x0x/` | GPL-3.0-only with separately identified MIT-derived components/notices |
| Mutable Instruments / stmlib | `engines/third_party/mutable/` | MIT; preserve source headers and upstream record |
| Schwung modules | `engines/third_party/schwung*/` | Component-specific MIT notices and upstream records |
| Google msfa | `engines/third_party/msfa/` | Apache-2.0 |
| musl subset | `firmware/third_party/musl/` | Per-source notices; mixed grants, see `COPYRIGHT`, `inventory.json`, `UPSTREAM.md` |
| LLVM compiler-rt | `firmware/third_party/compiler-rt/` | Apache-2.0 with LLVM exception |
| printf | `firmware/third_party/printf/` | MIT |
| TLSF | `firmware/third_party/tlsf/` | BSD-3-Clause |
| tinf | `firmware/third_party/tinf/` | zlib |
| FM-1 boot bridge | `firmware/third_party/fm1-nes/` | Apache-2.0 |

This table is not exhaustive. The license and provenance files beside each component, the source headers, and the exact build inputs remain authoritative. The diagnostic native receipt also includes test-only catalogue entries, so it cannot substitute for a release-specific component and retained-section audit.

## Evidence and limits

The native release inventory at [`notes/2026-10-14-native-release-license-inventory.md`](notes/2026-10-14-native-release-license-inventory.md) records the diagnostic receipt and its limits. The owner direction at [`notes/2026-10-12-native-gpl-firmware-direction.md`](notes/2026-10-12-native-gpl-firmware-direction.md) sets the intended SDK-free GPL native path. These repository changes document that direction; they do not establish that an image is complete, distributable, installable or accepted on hardware.
