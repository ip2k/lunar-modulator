# Continuous FM-1_500 target link

[verified] Exact source base `b7998a28ea1d6805c52fbbf69cc8ab45a9764c20`
compiled on Hera in isolated checkout `/home/claude/worktrees/lunar-continuous500-link`.
Output: `/home/claude/mvave-fm1/continuous500-link-20261014/out3/build`.
Retained launch: `launch3.sh` and `run.sh` in that task directory; log `docker3.log`.

The pinned `lunar-jieli-check:bookworm` image digest is
`0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc`.
The container used 4 CPUs, 8 GiB memory, 16 GiB memory-plus-swap, 256 PIDs,
docker-batch.slice, no network, read-only root, dropped capabilities,
no-new-privileges, task labels and a 1 GiB temporary filesystem. Task bind
mounts used SELinux label=disable, root UID and a root-owned output directory;
source, catalogue, prepared content and toolchain were read-only.
Earlier launches stopped before compilation because output creation or
catalogue reads failed with PermissionError; those are not target failures.

Builder options match the explicit identity diagnostic target except
`--runtime-mode continuous`: FM-1_500, expanded-d7000, stack watermark,
project loader and disarmed SAVE service, startup project 0, Shapes voices 8,
indexed TFT, compressed wavetables, prepared profile
`bfe627dc60ca5552dfd2f749611105989f7fcfb3c8637840225b377c38ac6972`.
The same freshness-checked catalogue retains all thirteen engines and 55 modules.

[verified] The compiler/linker completed successfully with no undefined symbols.
SDK-free linked audit: zero failures and zero pending checks. App size
845,336 bytes, leaving 15,308 bytes in the 860,644-byte D7000 app budget.

- App SHA-256: `5c923197629121ce90a33919b516ced23ef8edbaa1943ea1e9568b596b6557ee`
- ELF SHA-256: `4b8ae5a1f68550bcbedc2442d98f03f5af85daa88fcfbb69af37985b3d9f0120`
- Verification SHA-256: `d1ec99dd5c45862a921b6579949ee6b71cc16eef2391eabaff5f2e57a578083f`
- RAM-call audit SHA-256: `96d5eed3853201e9706a4fd90362c0d990bb598e8939643f6208997b59890936`

The approved Event Horizon Showcase packed project remains 5,100 bytes,
SHA-256 `ecb00a5363695e3275891bcb1fa0ab44d9b23d7108c1b9ddac35230d81f24a32`.
Continuous mode sets the timed ROM return to zero. This output has not been
packaged, installed, booted or heard on hardware. SAVE binding, admission and
arming remain false; hardware, updater acceptance and installability remain
false. The private FM-1_500 composer is bound to a different, song-diagnostic
app and must not silently consume this continuous app.
