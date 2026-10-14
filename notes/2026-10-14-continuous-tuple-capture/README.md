# Operator-owned continuous build tuple capture

This branch adds an offline host wrapper for one privately selected continuous
FM-1 candidate. It creates a clean detached source snapshot, pins the Docker
image by immutable ID, uses fixed command/mount/resource policy, and records
host-inspected image/container configuration plus source/request/output hashes.
The worker and tuple capture keep storage, installability, hardware, and release
admission false. No device I/O is performed.

The current checkpoint is implementation and host-test only. The actual pinned
container build and private tuple composition have not yet run. The selected
input is the already-reviewed Event Horizon + companion SET request; intended
target is Shapes8 on the D7000 profile with continuous FM-1_500 identity and
FM-1_000 recovery identity. A generated tuple will be diagnostic provenance,
not a firmware package or install approval.

Validation at this checkpoint:

- `python3 -m py_compile` on the builder, wrapper, worker, and tuple capture.
- Pinned Hera pytest environment: 71 focused tests passed across continuous
  tuple capture, wrapper policy, and native image controller.
- `git diff --check` passed.

Next: independent review of the pushed source checkpoint, then one fresh
bounded Hera container run using the fixed wrapper. Record actual invocation,
source/toolchain/catalogue/request/app/ELF/receipt hashes and capacity only
after that run succeeds. Keep output in a private mode-0700 location outside
the repository. Do not infer hardware acceptance, NOR ownership, recovery, or
installability from this build.
