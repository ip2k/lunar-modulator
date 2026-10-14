# Continuous tuple integration review

Read-only review of branch `codex/2026-10-14-current-continuous-build-tuple` at `ce3c998449210f5ff917f7fd53d6a1baa48f8a6f`, against base `e0cc5b42`. The branch contains the operator wrapper, capture helper and tests, plus the strict FWSC tuple schema update. No source or receipt was changed during this review.

## Findings

- `toolchain_tree_sha256` is now a required tuple key, validated as lowercase 64-hex and checked against the same provenance field. Missing or malformed tuple values and missing or changed provenance values are covered by tests. The external tuple digest still anchors the raw canonical tuple bytes.
- The retained earlier diagnostic tuple (`2005957a…`) predates this provenance field and is rejected at exact-key validation. This is fail-closed behavior and is intentional for an input whose full toolchain-tree provenance is absent; accepting it as if it had that provenance would be unsafe. The previous positive packager test against this diagnostic tuple was replaced with a positive test using the current continuous tuple (`9c246fb7…`). Separate `compose_500_*` candidate tests still pass, but those use their own pinned composition paths and do not establish compatibility of the tuple packager with the old tuple.
- Compatibility is therefore deliberately broken for old tuple documents. The `schema` integer is still `1`; before this tuple format is treated as stable, producer and consumer should either explicitly define schema 1 as exact-key/current-provenance-only or bump the schema in both places. No relaxation or receipt rewrite is recommended.
- Private artifact tests skip through `_inputs()` when the retained source/reference/build files are absent. The synthetic tuple/schema tests remain runnable; `test_private_artifact_loader_skips_cleanly_when_inputs_are_absent` exercises the unavailable-artifact path. On Hera, the retained continuous artifacts were present and all real artifact checks ran rather than skipping.
- Capture/wrapper inspection found no additional integration issue: the source, catalogue snapshot, toolchain manifest, worker source/provenance, request, linked objects, inspection contract, and output receipts are bound in the capture path; no private payload is published by the tests or note.

## Checks

On Hera at the reviewed commit:

- `/home/claude/.cache/lunar-host-set-fixtures-venv/bin/pytest -q -rA tests/test_native_continuous_tuple_capture.py tests/test_native_continuous_build_wrapper.py tests/test_native_demo_image_controller.py`: 93 passed, 0 skipped.
- Same pytest environment, `tests/test_trusted_fwsc_package.py tests/test_package500_continuous_d7000_candidate.py tests/test_package500_d7000_candidate.py`: 18 passed, 0 skipped.
- `python3 -m py_compile tools/jieli/trusted_fwsc_package.py tests/test_trusted_fwsc_package.py` and `git diff --check`: passed.

No package file, device action, build, or admission flag change occurred in this review. The in-memory package result remains diagnostic-only, with `file_written=false` and hardware/installability flags false.

## Minimal integration set

The latest consumer fix is commit `ce3c99844`. It depends on the continuous tuple/capture branch changes from `e75941244` through `e4cd4ec86`, with the intervening fixes recorded on the same branch, and the latest tested tuple fixture/schema changes in `ce3c99844`. Integrate the branch as a unit if retaining the capture producer; do not cherry-pick only the consumer schema change into a producer that emits no `toolchain_tree_sha256`. Hera bare branch was verified at `ce3c998449210f5ff917f7fd53d6a1baa48f8a6f`; GitHub backup remains coordinator-managed.
