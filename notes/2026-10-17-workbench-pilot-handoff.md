# Workbench reuse pilot — active implementation

Personal Lunar Modulator work, authorized by the owner on 2026-10-17.

## Endpoint

Complete the offline selective-reuse milestone from the workbench plan: pinned
source/licence and recovery-asset inventory, native seam and board comparison,
one useful source-only format adapter with explicit losses and independent
synthetic tests, attribution, review and CI integration. Select later UI/board
changes from evidence; do not fabricate a native fix to fill a work package.
Hardware acceptance remains a separate owner/coordinator gate. No device
traffic or upstream contact belongs to this task.

## Bases and ownership

Implementation branch: `feature/2026-10-17@workbench-reuse-pilot`, based on
reviewed documentation head `0b3f377c1175df729591c221fa39de435ff5a8ce` (PR #150).
This adds host tooling to published main; the native reference remains
`1f12ad5b8d6a865268af94179a3442183a680602`. The native stream is not merged as a
side effect. The coordinator will review adapter compatibility with both state
contracts before integration.

Workers own isolated Aeon worktrees and atomic claims:

- Luna `workbench-inventory`: inventory, provenance and offline verifier.
- Sol `workbench-native`: native seam/board evidence; propose any justified fix.
- Sol `workbench-formats`: format matrix, adapter and synthetic fixture generator.
- Independent tests/review follow the agreed adapter interface.

Aeon received exact base/reference refs through Git and the public kit ZIP
through SCP. No active checkout or credentials were copied. Light source
inspection/stdlib tests need no heavy containers; any heavy tests use the LAN
batch slice and explicit resource limits. Hera remains unused under the native
project's exclusion even though newer infrastructure notes report maintenance
complete. Worker commits are pushed to the Aeon exchange repository, then
backed up by the Mac coordinator to GitHub with exact SHA verification.

## Navigation limits

Rarefaction and Serena currently select the original absolute checkout,
`/Users/likwid/Developer/mvave-fm1-firmware`, not these new worktrees.
Rarefaction's bounded `check_package` query matched source and its caller;
Serena resolved `engines/seq/seq_engine.c:87` after correcting the file path.
Known callers exist in the host tool and simulator. Shared servers were not
retargeted over other sessions. Branch/worker claims use exact Git objects and
direct source checks; no native ABI or complete cross-language index is claimed.

## Selected implementation and checks

Gate A rejects a wholesale vendor-runtime rebase: the kit supplies no documented
engine-free platform seam and no permission for Lunar's unrelated GPL code.
The retained adapter reuses existing MIT Lunar codecs; no vendor implementation
or binary was imported. Main's host-tool changes remain separate from the GPL
native stream.

| Package | Outcome |
| --- | --- |
| W1 | Pinned inventory, recovery asset table and offline verifier implemented. 150 source files match; 65 internal hashes pass; 22 external toolchain entries remain external. |
| W2 | Native seam, ownership, licence and resource evidence recorded; binary rebase rejected. |
| W3 | Actual board comparison recorded: Lunar 64-frame producer / 256-frame DMA half versus vendor 128-frame ISR render. No clock/audio rewrite selected. |
| W4–W6 | Synthetic formats and independent tests; strict DX7 SysEx to/from real Lunar sound files; structural inspection for vendor project/timbre/sample files. No unsupported song/sample conversion. |
| W7 | Independent review selected detection-only LCD pending timeout in a separate native branch. No DMA abort/retry or device recovery is admitted; target validation remains separate. |
| W8 | Reuse existing Open/drop and Load DX7 patches workflows. No additional UI is needed for this slice. The CLI supplies inspection and explicit loss/default reports; sound-bank remapping/capacity limits are documented. No new browser interaction claim. |
| W9 | File-level provenance and reuse decision recorded; existing MIT codecs retained, no third-party source subtree needed. |
| W10 | Optional update/library adapter deferred: this offline milestone does not need device transport. Recovery state matrix and asset comparison are retained; updater buttons would add no current recovery capability. |
| W11 | Independent source review passed; test integration and exact-head CI govern merge. |
| W12 | Owner/coordinator hardware gate remains outside this offline milestone. Recovery, real audio and installability are not established here. |

The focused Aeon suite passed **25 tests**, including actual compiled C
`fm1-state records -` acceptance, independent VCED/VMEM vectors, malformed
input, loss refusal, writer-repair refusal, output protection and unsafe archive
checks. The C tool was built with `make -C engines -j2 build/fm1-state` in
`lunar-modulator-manual:ubuntu-24.04`; pytest ran in `lunar-asan:ubuntu-24.04`.
Both used `docker-batch.slice`, two CPUs and 2 GiB memory/swap ceilings.
No complete engine/target build is implied by this C-parser check.

The source reviewer also checked 80 seeded synthetic voice round-trips and the
full pinned inventory. An initial inventory checkpoint had literal trailing
backslash-n text and failed coordinator compilation/JSON checks; corrected
checkpoint `6605b24d` was rerun successfully on saved committed bytes. Review
also caught writer normalization not being refused; `3dabbd2e` fixes both
read/write repair checks and the independent regression passes.

Worker backups verified on GitHub: inventory `6605b24d`, native evidence
`b4067c77`, formats `3dabbd2e`, independent tests `01d0096c`. Coordination
handoffs are under `/home/claude/.local/share/codex-coordination/handoffs/`
with `lunar--workbench-{inventory,native,formats,tests}.md` names. The coordinator
cherry-picked reviewed changes into this branch; main/native histories were
not collapsed together.

Next: review the final test/documentation delta, pass exact-head PR CI and merge
the host pilot. The detection-only native change follows its own target-build,
review and CI gates against the installable branch. Do not infer native or
physical acceptance from the host pilot's green tests.
