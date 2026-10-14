# Independent review: trusted continuous build tuple

Date: 2026-10-14

Reviewed physical_storage_compression's tuple-capture implementation at commit
e4cd4ec8699823fe2c720eb14b488352b343fdc8 on
codex/2026-10-14-current-continuous-build-tuple. The worktree and Hera bare
ref matched that exact SHA during review.

The important trust-boundary repair is the immutable catalogue snapshot. The
operator wrapper hashes the source catalogue, copies it without following
symlinks or making hardlinks, checks the copied manifest before Docker create,
mounts the snapshot read-only, and verifies it again before tuple capture.
Capture binds both tree identities and checks selected receipt rows against
the staged snapshot. The inspected Docker contract binds the expected image
identity, container ID/name, command and its argument-vector digest, mounts,
resource limits, environment, and nonprivileged execution settings.

The linked-object inventory was reconciled as 281 exact path/content rows:
161 catalogue inputs and 120 generated/link outputs. The separate catalogue
inventory has 167 entries; six are reported but not linked and remain in the
catalogue manifest. This avoids treating a headline count or a toolchain
compiler hash as complete provenance.

The first actual worker preflight refused before Docker creation because the
curated catalogue has 4,418 entries (about 80.9 MB), above the then-configured
4,096-entry cap. Follow-up commit
cb58361a4673adca62c0a5150e067808b8a285a3 raised only the entry cap to 8,192;
the 512 MiB aggregate and 256 MiB per-file bounds remain. Its boundary test
accepts 8,192 total manifest rows and refuses 8,193.

Validation on Hera:
- Focused tuple-capture, wrapper, and image-controller pytest suite: 87 passed.
- Python bytecode compilation for the wrapper and capture module: passed.
- `git diff --check`: passed.
- Reviewed branch tip and Hera bare ref matched cb58361a4673adca62c0a5150e067808b8a285a3.

Review disposition: no blocker found in the reviewed capture contract or the
bounded manifest-cap increase. A fresh private diagnostic build may proceed.
This review does not establish correctness of the resulting firmware package,
installability, storage admission, device behavior, or physical/perceptual
acceptance.

Residual operational caveat: failures during setup before the wrapper enters
its cleanup region can leave temporary files under the private mode-0700
output parent. Use a unique private output directory and remove abandoned
temporary material after confirming no run is active.
