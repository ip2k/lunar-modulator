# macOS native-probe flags and project-store fixture

Date: 2026-10-14
Base: 4b5682216b39da193d7f8ceb207473f0fe07fd7e

## Change

The project-sequence, sequence-export, and project-store probes now use the shared
`tests/native_test_flags.py` policy. It keeps ASan/UBSan enabled, chooses
`-Wl,-dead_strip` on Darwin and `--gc-sections` plus non-PIE only on Linux.
No sanitizer or assertion was removed.

The project-store mutation fixture uses a 20 KiB minimum as a storage-pressure
sanity floor, not as a capacity proof. Completeness is checked semantically:
all 8-by-8 clip descriptors, 1,536 notes, 1,536 locks, and 256 triggers survive
both project JSON import/export and compact SAVE serialization, with per-track
and per-clip counts, legal event-field checks, and exact cl/cp/lk/tg payload
comparisons from source through final SAVE serialization. The note records the
malformed high-pitch/wrong-field-order experiment that initially appeared to
lose events. Correcting the sequence format order
(tick:gate:pitch:velocity:step), using legal CP values, and assigning distinct
steps preserved all events. The deterministic valid 32-voice DX7 bank, varied
pad values, and unique maximum-length labels produce a 34,263-byte body. The
fixture still exercises both 102,400- and 49,152-byte journal slot geometries.

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
container. `git diff --check` passed. The corrected full focused suite was rerun after the field-comparison assertion
was added and passed; it includes the 30-shard project-store matrix, large SAVE
bodies, and both slot geometries.

## Limits and handoff

This establishes Linux/Hera behavior and preserves host sanitizer coverage. It
does not establish an actual macOS run; the exact-head macOS CI job must still
verify Darwin compiler/linker behavior. No target SDK or hardware validation is
claimed.
