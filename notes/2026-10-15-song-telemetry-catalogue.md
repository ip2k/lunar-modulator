# Song telemetry catalogue compile

## Result

Built a fresh 16-shard native object catalogue from source commit
`d4e0583880764cb81c37d9eb09413ac30184d484` in an isolated checkout. All 167
catalogue object indices (0–166) appear exactly once across the shard reports;
all 167 object files match their report SHA-256 values. Every shard reports the
same 536-entry source manifest, with canonical SHA-256
`01a7165667aea4e7f44cd29130d00dc0d8f7698aab2357c50687c9e0965dd4d0`.
The canonical object-to-SHA manifest is
`fdc1061ade61c8c59ba73b5bca9c9beabdc42cfbaea9d5453c88b89161150538`.

The exact profile was GPL enabled, all modules, `-Oz`, LTO, shared resampler,
Shapes polyphony 8, and indexed TFT. Reports list no closed SDK archives and
no device SDK headers. The resulting 3,166,844 bytes of objects are offline
compile inputs only; this task did not perform a firmware link, package, device
operation, or admission check.

## Toolchain and bounded execution

Toolchain root:
`/home/claude/mvave-fm1/sdk-v1213/toolchain/jieli-linux-toolchains-20250324.1`
with clang SHA-256
`42b94f9e11140b0fcab8f807b2872ad245b8eeca03a2d792f8706c5a3a35d34c`.
C++ headers:
`/home/claude/mvave-fm1/matched-os-ab-20261014/cxx-pristine`; input
`__config` SHA-256
`1ecea71a69fcc88a4ed7bf290ac60ec92eb351ee0c3cc0a1808ade179540bcaf`.
The private per-shard configured `__config` digest is
`ee3918b43648d0b092a8ef0fa6f1948bd270f64c1919962d5b2759c6a9678375`.
Container image ID was
`sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc`.
Each of 16 containers was created and inspected before start with 2 CPUs,
2 GiB memory, 4 GiB swap limit, 256 PIDs, `docker-batch.slice`, no network,
read-only root filesystem, all capabilities dropped, no-new-privileges, and
only source/toolchain/headers read-only plus a dedicated output-parent mount.
All 16 exited 0 with `OOMKilled=false`; each was removed and a final task-label
query found no remaining containers.

## Artifacts and initial failed attempt

Successful output is outside Git at
`/home/claude/mvave-fm1/song-telemetry-catalogue-d4e058-20261015/run2`.
It includes `shard-00` through `shard-15`, per-shard report/object/log files,
pre/post container inspection JSON, execution summary, and
`catalogue-object-manifest.json`.

The first attempt at the parent output directory failed before compiling: the
shard directories had been pre-created, while `compile_catalogue.py` requires
`--out` to be absent and creates it itself. This is preserved in the parent
attempt directory’s logs/summary and was not counted as compilation evidence.
The successful retry mounted only the parent output directory and passed an
absent shard child path to each compiler invocation.

## Limits and next dependency

This catalogue is tied to the exact d4e05838 source manifest. Before using it
for a build from a later source commit, compare all source-manifest entries;
any difference requires a fresh compile. Next, create a separate isolated
checkout at the coordinator’s exact `6a8a11d6828a47cff2109e352c55d9a2d75ac981`
source, build a fresh `fm1-state` tool in a bounded container, and prepare the
Event Horizon Showcase plus companion SET profile from the approved request.
That profile/build/link is not part of this catalogue task.
