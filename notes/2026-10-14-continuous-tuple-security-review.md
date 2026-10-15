# Independent review: continuous build tuple and installer boundary

Reviewed sibling branch `codex/2026-10-14-current-continuous-build-tuple` at
`3273abe1361357b52bd1ee725300196ed5601ccb` against coordinator base
`ce451eab8111ac794c29b2a5dfe9402b2fd1ceb1`. This was a read-only source and
retained-artifact review. No hardware, package file, service, or source was
changed. Hera's shared semantic servers were not retargeted; source review used
the assigned isolated checkout and exact bare-commit file reads.

## Findings

- **The provenance chain is strong for this private link result.** The operator
  wrapper requires a clean pinned source commit, creates a detached source
  snapshot, copies the catalogue to a private snapshot and mounts it read-only,
  pins and inspects the Docker image/container contract, uses no network and
  fixed resource limits, and hashes toolchain/catalogue snapshots before and
  after the run. Capture rehashes app, ELF, artifact/build receipts, request,
  profile, catalogue inputs, generated and linked objects; it binds the full
  source/toolchain/catalogue manifests and retains all acceptance flags false.
  The tuple digest remains an external trust anchor: the sidecar is not signed
  and a consumer must receive its expected SHA from a trusted coordinator.

- **The retained tuple and built files match their recorded digests.** The
  private output at
  `/home/claude/.local/share/codex-private/continuous-tuple-20261014/run-298ff12/build-output/build`
  has tuple SHA-256
  `9c246fb70bfb04cb6a6adbaf845fe71a882ba0228317b286f648b502b2e66ec4`,
  provenance `2d8c80fd69df3dd5015fa1d64866d29f7035b0ba0fe8204ea5bac25ba66b5094`,
  app `0a7a2fecbd730586b8792e7da6c9a6cf35fa26ae4fb77798b93b5f30e9922f02`
  (845,716 bytes), ELF
  `7c79e47b0261f0a8ac7bdbf80ff61a3250dedac04503df0efa9b9ca75c887e9d`,
  request `a089835b668a07d711ee13a2a4bd58aa96f483925aaf2f47767fa2be6e0e9a07`,
  prepared profile `af37827fa09a5925864bfebe01d800f8b37ffcda8ce4f42bf533ea9e774c4f30`,
  verification receipt `2a66c7cff2f1433cf7b1025c4cb84ef73cfea73a3fd471029d8e469ec6fc18f5`,
  artifact receipt `7526411bf043ea7e962f02de21f9186a84cbd02e00b3cedc9981e7f6c8987482`,
  and catalogue manifest `af1462fc04d6a6614c4b2d5b417e43c2670361095ea1484a8b7b03e2e5fd0429`.
  These were independently recomputed with `sha256sum` on Hera.

- **Selection is bound as build evidence, but selection is not installer admission.**
  This tuple records Event Horizon Showcase with startup index 0 and its companion
  SET (4,345 B project plus 1,887 B SET). It is the 13 sound-engine / 54 selected
  module Shapes8 profile, not the separate 55-module or Plate-enabled build.
  The compiled artifact, verification receipt, linked-object inventory, request,
  and profile are hash-bound; the image/selection receipts are cross-checked by
  capture. The FWSC consumer verifies the exact app/ELF and tuple, not physical
  playback or that firmware sequence semantics work on-device.

- **There is no current API-to-install connection for continuous mode.** The
  operator worker deliberately builds `runtime_mode=continuous` and a private
  FWSC can be composed in memory, but `tools/installer_service/api.py` at this
  review base still accepts only `diagnostic` and `song-diagnostic` and requires
  `linked-private-diagnostic`. Therefore this continuous tuple does not pass
  through the current installer service or produce a web-download/installable
  artifact. Keep this a separate integration task; do not widen the API allowlist
  merely because the build/tuple works.

- **GPL distribution remains a release obligation, not a private-build defect.**
  The worker sets `FM1_GPL_MODS=1` and links GPL modules. The build/source snapshot
  and provenance can identify the exact linked inputs, but neither the tuple nor
  in-memory FWSC composition is a source archive or license-notice bundle. Any
  later distribution must provide the corresponding GPL source and notices under
  the repository's GPL-3.0-only policy. The current result remains private and
  `file_written=false`; no distribution occurred.

- **Tuple schema evolution needs an explicit compatibility policy.** The tuple
  now requires `toolchain_tree_sha256`; older diagnostic tuples without it are
  correctly rejected rather than assigned invented provenance. The format still
  labels itself schema 1. Before treating this as a stable interchange format,
  either document schema 1 as exact-key/current-provenance-only or increment the
  schema in both producer and consumer. The integration note already records
  this; no change is needed to accept stale tuples.

- **The capture README is stale in its status text.**
  `notes/2026-10-14-continuous-tuple-capture/README.md` still says no tuple was
  captured and asks for another retry, while the later capture-only follow-up
  and handoff report a successful capture. Update or clearly archive those
  superseded paragraphs before relying on that README as an operator handoff.

## Checks and limits

Reviewed the exact wrapper, worker, capture helper, builder, tuple consumer,
relevant tests, integration/composition notes, and current installer API. The
committed sibling handoff records the 93-pass continuous capture/wrapper/controller
suite and 18-pass package suites; I did not rerun those tests in this independent
review. No new link or package was built. The retained in-memory composition
report states 978,484 bytes, `file_written=false`, all hardware/installability
flags false, and 13,964 bytes of modeled stage slack; that is structural offline
composition only. It does not establish updater acceptance, recovery, physical
write safety, runtime, or musical acceptance.

Next: coordinator may integrate the tuple/capture branch as a private build
provenance milestone after deciding the schema-1 policy and fixing the stale
README. A later, separately reviewed change is required to connect continuous
mode to the installer service and to define GPL source/notice delivery before
any publication. Do not represent this branch as an installer-ready release.
