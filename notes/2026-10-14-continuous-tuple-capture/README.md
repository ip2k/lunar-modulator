# Operator-owned continuous build tuple capture

This branch adds an offline host wrapper for one privately selected continuous
FM-1 candidate. It creates a clean detached source snapshot, pins the Docker
image by immutable ID, uses fixed command/mount/resource policy, and records
host-inspected image/container configuration plus source/request/output hashes.
The worker and tuple capture keep storage, installability, hardware, and release
admission false. No device I/O is performed.

The current checkpoint is implementation and host-test only. The first wrapper
attempt stopped before worker execution because Docker normalized `--cpus=4`
without an effective quota. The host contract now pins the observed quota/period,
all privilege/device/namespace/runtime/mount/entrypoint fields, exact command
argument vector and its digest, and the full toolchain tree including directory
modes and symlink targets. The mutable catalogue bind was replaced by a fresh
private snapshot: its complete tree manifest must match the source at copy time,
the container mounts only the snapshot read-only, and the snapshot is rechecked
after completion. The initial real-build preflight measured 4,418 total catalogue entries (including directories) and 80.9 MB; the original 4,096-entry cap refused before Docker creation. The fixed cap is 8,192 entries with the 512 MiB aggregate byte limit retained, and a boundary test accepts 8,192 and rejects 8,193. Selected build-receipt catalogue rows must match that snapshot. Linked-object provenance separately rehashes all
receipt rows: 161 linked catalogue rows and 120 generated `/out/build/link/`
rows, while the 167-row catalogue inventory retains six unlinked rows as well.
The first invocation stopped at host preflight before Docker creation because the catalogue exceeded the former row cap. After the cap increase, a fresh container build completed and wrote app/ELF/verification outputs, but cleanup of the read-only catalogue snapshot failed and prevented tuple capture from completing. The follow-up adds bounded cleanup of only the wrapper-owned private snapshots after the container has exited; an offline read-only tree test covers this. A fresh build then completed but tuple capture rejected the producer's exact `prepared-build-inputs` status because capture expected `prepared`. The image and selection receipts otherwise matched on request, prepared profile, selected content, startup project, and SET IDs. The capture validator now requires the producer's exact status and exact integer schema version; focused positive and negative tests cover that contract. Existing successful private build outputs are retained for a capture-only retry; no tuple has been captured yet. Next: independent review of cleanup, then rerun with a fresh output directory and verify the complete tuple. The selected
input is the already-reviewed Event Horizon + companion SET request; intended
target is Shapes8 on the D7000 profile with continuous FM-1_500 identity and
FM-1_000 recovery identity. A generated tuple will be diagnostic provenance,
not a firmware package or install approval.

Validation at this checkpoint:

- `python3 -m py_compile` on the builder, wrapper, worker, and tuple capture.
- Pinned Hera pytest environment: 88 focused tests passed across continuous
  tuple capture, wrapper policy, and native image controller. Policy tests
  reject added privilege/device/capabilities, namespace/runtime changes, extra
  environment/mounts, and altered worker entrypoint; provenance tests exercise
  catalogue and generated linked-object mappings, tampering, and duplicate rows.
- `git diff --check` passed.

Next: independent review of the pushed source checkpoint, then one fresh
bounded Hera container run using the fixed wrapper and a new private output path. Record actual invocation,
source/toolchain/catalogue/request/app/ELF/receipt hashes and capacity only
after that run succeeds. Keep output in a private mode-0700 location outside
the repository. Do not infer hardware acceptance, NOR ownership, recovery, or
installability from this build.


Capture-only retry follow-up (2026-10-14): After the status fix, the retained
successful build was retried without running Docker. The exact invocation bytes
(SHA-256 `7f993540…8011a3b4`) were preserved. The recorded request hash,
source commit/manifest, catalogue snapshot manifest, toolchain manifest, and
all three originally recorded mount paths were checked. Reconstruction produced
the recorded source manifest `ed9c5ae3…0dd7710e`, catalogue manifest
`7a08f4d4…4650e77a`, and request hash `a089835b…e0e9a07`; these are
reconstructed private inputs, not a claim about original filesystem timing.
Capture then refused because actual `verification.json` has no `app_bytes`
field. The same app SHA/length and ELF SHA are present in `image.json` and
`artifact.json`, and match the retained app/ELF bytes. The helper now checks both
receipts against exact bytes, and keeps the build receipt ELF hash check, without
requiring a duplicate app length that the producer does not emit. The focused
capture/wrapper/controller suite passes 90 tests. No tuple was written; request
independent review before another capture-only attempt. The reconstruction
mounts were removed using the wrapper's bounded owner-path cleanup helper.
