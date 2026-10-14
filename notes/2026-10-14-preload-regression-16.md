# Selectable full-song preload regression

[verified] At source commit `746e12ec6d50c4989ec0762d08c8f53ab6a14c82`, all 152 focused Python tests passed in 16 parallel Hera containers. Each shard exited zero without an OOM. Coverage: native catalogue export (including source module dependencies), installer service, diagnostic image controller, preload startup selection, native content embedding, scattered extent I/O with sanitizers, and rescue-record/payload cutpoints.

Evidence: `/home/claude/mvave-fm1/preload-regression-16-v4-20261014/out/verification.json`, per-shard logs, collection log, source-hashes.json and adjacent launch.py. Immutable image `sha256:1e6a3bc97b299a40f572ab38972a114e2f9ab0f4daaf96e2ae970f488ac34313`; Python 3.12 with FastAPI 0.143.0 and pytest 8.4.2. Read-only state tool and pinned JieLi 20250324.1 toolchain were mounted. Containers ran networkless in docker-batch.slice, UID 1001, one CPU, 2 GiB memory/swap cap and 256 PIDs each; each used its own writable temporary source copy.

Earlier attempts are retained: first collection lacked FastAPI; v2 lacked make/C compiler; v3 lacked FM1_NATIVE_TOOLCHAIN. These are environment failures, not passing test runs. The corrected v4 run exercised the unchanged source. Each shard also emitted a FastAPI test-client deprecation warning; this did not fail verification.

[verified] GitHub CI run 38580253461 was dispatched at exact source SHA 746e12ec; its completion is not established by this note. The later host-only expanded stream model was independently checked with four standard-library tests after integration; the 152-test receipt does not cover that later commit.

No device operation, public deployment, physical full-song listening acceptance or approved flash transaction follows from these tests. The UI remains a private request chooser pending the build/installer connection and release admission.
