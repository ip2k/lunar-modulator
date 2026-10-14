# Private toolchain snapshot binding

Date: 2026-10-14

## Finding

[verified] The continuous-build wrapper previously computed a manifest for the live SDK tree, mounted that same path read-only into Docker, and checked the live tree again after the build. A read-only container mount prevented writes by the container, but did not bind the bytes consumed to an immutable snapshot if another host process changed and restored SDK files between the two manifest checks.

[verified] The wrapper now copies the complete configured toolchain tree into a uniquely named private sibling directory. It compares the source and copied manifests, rechecks the source after copying, mounts the copy at `/opt/pi32v2` read-only, and checks the copied manifest again after the container exits. The invocation and captured tuple bind the source root, snapshot root, and matching source/snapshot/tree SHA-256 values. Tuple capture rejects absent or inconsistent bindings.

[verified] The wrapper's cleanup boundary now includes request, source, catalogue, and toolchain snapshot preparation. The focused setup-failure test confirms all temporary snapshots are removed if source cloning fails after the toolchain copy. The private build output remains for diagnosis, as before.

## Before and after

Before: hashes were taken around a read-only mount of the shared SDK path, leaving a same-host time-of-check/time-of-use gap.

After: Docker consumes a separately copied, manifest-bound tree. Changing the original SDK after snapshotting does not change the mounted bytes. This gives the build a stable input tree across container execution.

## Validation

[verified] Hera source branch: `codex/2026-10-14-toolchain-snapshot`, based exactly on `3273abe1361357b52bd1ee725300196ed5601ccb`.

[verified] The configured SDK toolchain currently occupies 136 MiB by `du -sh`; the additional copied tree temporarily adds about that much disk usage, besides the source and catalogue snapshots. Copy time and peak disk usage were not measured in a live build.

[verified] Focused command:

```sh
/home/claude/.cache/lunar-host-set-fixtures-venv/bin/pytest -q -rA \
  tests/test_native_continuous_build_wrapper.py \
  tests/test_native_continuous_tuple_capture.py \
  tests/test_trusted_fwsc_package.py
```

Result: 46 passed, 1 skipped. The skip is `test_capture_reaches_inspection_after_contract_and_name_validation`: its retained private tuple predates snapshot-binding metadata. `py_compile` passed for both changed Python modules, and `git diff --check` passed.

The tests cover full-tree binding, changed source after snapshot, copy mismatch cleanup, failure cleanup before Docker starts, and refusal of altered/missing capture bindings.

## Limits and next step

[verified] No fresh continuous target build was run. The retained historical tuple and package test fixture were not regenerated and must not be described as having been snapshot-bound. A new exact-source build is needed to verify the new snapshot fields through the actual compiler, tuple capture, and package-composition path.

[inferred] The private copy and read-only container mount address accidental/concurrent changes to the shared SDK tree during a build. This is not a defense against a hostile process running as the same host user that can modify the private copy itself; post-build hashing detects modifications that remain, but cannot prove protection against a coordinated modify-and-restore attack on the copy.

[verified] Hardware, installation, and release-admission flags remain false. This change only binds the build toolchain inputs.
