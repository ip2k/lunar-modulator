# macOS native-probe flags and project-store fixture

Date: 2026-10-14
Base: 4b5682216b39da193d7f8ceb207473f0fe07fd7e

## Change

The project-sequence, sequence-export, and project-store probes now use the shared
`tests/native_test_flags.py` policy. It keeps ASan/UBSan enabled, chooses
`-Wl,-dead_strip` on Darwin and `--gc-sections` plus non-PIE only on Linux.
No sanitizer or assertion was removed.

The project-store large-body regression still requires a valid app SAVE body of
at least 32 KiB. Its deterministic input now uses a generated valid 32-voice
DX7 bank, full legal sequence event variation, varied pad values, and unique
maximum-length labels. The serializer generated 34,263 bytes in this run; the
fixture still checks all previous record totals and both 102,400- and 49,152-byte
journal slot geometries.

## Verification

Pinned image: `lunar-preload-tests:20261014`,
`sha256:1e6a3bc97b299a40f572ab38972a114e2f9ab0f4daaf96e2ae970f488ac34313`.
The image does not contain pytest. The run mounted the existing pytest dependency
directory read-only. Hera execution was contained in `docker-batch.slice`, with
4 CPUs, 6 GiB memory and equal swap, `--network none`, and a 3 GiB executable
temporary filesystem.

Full focused command:

```sh
systemd-run --user --slice=docker-batch.slice --wait --pipe docker run --rm \
  --network none --cpus=4 --memory=6g --memory-swap=6g \
  --label codex.task=lunar-macos-flags-fixture \
  --tmpfs /tmp:rw,exec,size=3g \
  -v /home/claude/worktrees/lunar-macos-flags-fixture:/work \
  -v /home/claude/.cache/lunar-venvs/wave-receipt-validation-20261014/lib/python3.12/site-packages:/pytest-deps:ro \
  -w /work -e PYTHONPATH=/pytest-deps:/work lunar-preload-tests:20261014 \
  python3 -m pytest -q tests/test_native_project_store.py \
  tests/test_native_project_sequences.py tests/test_native_seq_export_stream.py
```

Result: exit 0; 249 tests collected; 246 passed and 3 skipped. The three skips
are target-toolchain-only checks because no target SDK is configured in this
container. `git diff --check` passed. The focused 30-shard project-store
matrix, including large SAVE bodies and both slot geometries, passed.

## Limits and handoff

This establishes Linux/Hera behavior and preserves host sanitizer coverage. It
does not establish an actual macOS run; the exact-head macOS CI job must still
verify Darwin compiler/linker behavior. No target SDK or hardware validation is
claimed.
