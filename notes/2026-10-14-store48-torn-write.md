# 48 KiB project-store torn-write content recovery

Date: 2026-10-14
Base: `1f020b4b497ce8f71add8cca07e0ba86352dc540`
Branch: `codex/2026-10-14-store48-torn-write`

## Finding and change

The assigned base already tested 49,152-byte slots, partial erase/program
mutations, full-mutation/transport-error cases, and callback ordinals split
across 30 shards. Its recovery assertion only checked the chosen slot,
generation, and length. The initial two commits also used the same payload, so
a recovery scan could choose the expected journal metadata without proving the
returned generation's actual SAVE bytes.

The harness now creates three distinguishable journal states using valid SAVE
bodies: generation 0 has the original body, generation 1 has the same complete
project with a same-length changed name field, and generation 2 returns to the
original body. It injects each erase/program callback failure into both
0-to-1 and 1-to-2 replacement transitions. For each partial-mutation and
full-mutation/transport-error case, it confirms the old active slot is byte
unchanged and compares the recovered slot payload byte-for-byte against the
payload expected for the selected generation. The final commit-marker
acknowledgement-loss case expects the new generation only when the marker was
fully written. The existing 30-shard partition and 49,152/102,400 geometries
are preserved.

The dense SAVE fixture is about 34 KiB and has a second valid image with a
changed name. Its compressed binary length differs by four bytes, which the
harness now handles explicitly; callback geometry is computed from the
candidate being written. The small fixture passes itself as both old and new
images, retaining its prior behavior.

## Verification

Passed the complete focused file (150 cases: 60 ordinary geometry/fault
cases, 30 legacy regressions, and 60 large-body geometry/fault cases) in the
pinned Hera container:

```sh
docker run --rm --network none --cgroup-parent=docker-batch.slice \
  --cpus=4 --memory=4g --memory-swap=4g \
  --label lan.project=lunar-modulator \
  --label lan.session=store48-torn-final-confirm-20261014 \
  --mount type=bind,src=/home/claude/worktrees/lunar-store48-torn-write,dst=/work \
  -v /home/claude/.cache/lunar-venvs/wave-receipt-validation-20261014/lib/python3.12/site-packages:/pytest-deps:ro \
  --tmpfs /tmp:rw,exec,size=2g -w /work -e PYTHONPATH=/pytest-deps \
  lunar-recovery-pytest@sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d \
  python3 -m pytest -q -p no:cacheprovider tests/test_native_project_store.py
```

The run completed exit 0; quiet pytest output reached 100% for all 150 cases.
`git diff --check` is clean. A direct Hera host run could not link because
its host GCC installation lacks `/usr/lib64/libasan.so.8.0.0`; the first
container attempt mounted source read-only, preventing its simulator build.
The successful run used a writable isolated worktree mount and the pinned
container with network disabled and 4 CPU/4 GiB limits.

## Limits

These are host-side journal/decoder tests using modeled erase/program behavior.
They do not establish NOR device behavior, power-loss behavior on physical
hardware, production storage admission, or device acceptance. No production
code, storage configuration, writer binding, or admission flag changed.
