# Private Docker diagnostic worker validation

Date: 2026-10-14 UTC  
Scope: private local service prototype only. No deployment, public listener, hardware, USB, MIDI, flash, power, or reboot operation was performed.

## Result

The FastAPI TestClient submitted the retained Event Horizon replacement-project request through the fixed Docker worker and received HTTP 200 with status succeeded. The service verified the actual build receipt and returned:

- status=linked-private-diagnostic
- app: 862,320 bytes; SHA-256 b1b9cc3d7989c180a8744e7cbc01afac3f667442d685c87ca79dce847a4e9aac
- installable=false, hardware_tested=false

The request file remained the exact retained input: SHA-256 0a3b172639a849aa95d0e97519fc67c2dafc674c17bdde053c48f04be84afe7a. The API's opaque build ID was EkXJ3rMSKQz6-JSt-7XClDdOjb-jIIOo. The successful adapter run deleted its temporary job directory after obtaining the verified result; no app binary was retained in this checkout.

## Fixed worker inputs and limits

The successful run used source commit b21bfe2f09289a49fb0f70769677d39ed1ded068, immutable image lunar-recovery-pytest@sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d, and the retained JieLi pi32v2 toolchain under /home/claude/mvave-fm1/sdk-v1213/toolchain/jieli-linux-toolchains-20250324.1.

The build requires a prepared 16-shard object catalogue. The trusted catalogue-z cache at /home/claude/mvave-fm1/all13-fullsong-link-comparison-v1/catalogue-z was checked against the worker checkout: its source manifest matched exactly, and the shard report showed all modules, -Oz, LTO, shared resampler, indexed TFT, 12 Shapes voices, and one GPL module. Its canonical object-list SHA-256 was 63049e9382b0902c90a92d89fca149cd0c4ba8a9dbfeffb8679e36d3e3e50afe. The builder's own checked_catalogue then revalidated source manifest, flags, object lists, and every compiled-object digest before linking.

The service mounts source archive, worker entrypoint, toolchain, catalogue, and request read-only; only a private result directory is writable. The entrypoint is exported with git show <pinned-commit>:tools/installer_service/docker_worker.py into the mode-0700 job input, hashed, made read-only, and mounted from that copy so it cannot drift from the archived source. The container runs with docker-batch.slice, network=none, 4 CPUs, 8 GiB memory/swap, 512 pids, read-only root, all capabilities dropped, no-new-privileges, and a 3 GiB bounded executable tmpfs. The worker has a 1,500-second timeout; request, archive, log, receipt, and app sizes are capped. Captured worker output is retained only as a capped private job-local file (0600); the API does not return logs.

## Failures resolved

Two initial attempts exposed assumptions in the prototype, and both were corrected before the successful run:

1. The pinned container image did not contain /workspace/tools/installer_service/docker_worker.py. The adapter mounts the separately exported pinned-commit worker file read-only at /input/docker_worker.py.
2. The builder requires the 16 prebuilt catalogue shards and rejects absent/stale objects. The service now requires the configured catalogue directory and mounts it read-only at /input/catalogue; the worker passes this fixed path to the existing builder. No request field can select the path.

The diagnostic log stays inside the mode-0700 private runtime job directory, is capped at 1 MiB, and is never exposed by the API. Failed temporary job inputs were removed after diagnosing them.

## Validation

- /tmp/lunar-installer-service-venv/bin/python -m pytest -q tests/test_installer_service.py: 36 passed, 1 skipped.
- python3 -m py_compile tools/installer_service/docker_adapter.py tools/installer_service/docker_worker.py tests/test_installer_service.py: passed.
- git diff --check: passed.
- One full bounded Docker diagnostic build through FastAPI TestClient: succeeded and passed API receipt verification.
- Starlette emitted its existing deprecation warning recommending httpx2; this did not fail the tests.

This is evidence for the local private diagnostic API/worker path only. It does not establish production service readiness, public API security, CI acceptance, installability, physical-device behavior, or listening/perceptual acceptance.


## Lifecycle and source-pinning follow-up

A follow-up review found two race conditions in the adapter. The worker entrypoint was mounted from the live checkout even though the source archive used a pinned commit; the adapter now exports that exact committed file and SHA-256 beside the archive. A regression test changes the live checkout after config validation and verifies the mounted input still equals the committed bytes.

The output drain detects log overflow even if the Docker CLI exits with status zero. If an inherited pipe remains open after the CLI exits, the adapter allows at most five seconds for EOF, then fails the job, closes its descriptor, and removes the server-generated container name. Teardown kills and waits for a live Docker client, then runs docker rm --force on the opaque name (with one retry for launch races); no cidfile is needed. Cleanup failure fails the job rather than returning a successful result.

The adapter rejects new work once shutdown begins. FastAPI lifespan shutdown invokes a bounded adapter drain: it kills active clients, removes their named containers, and joins tracked worker threads against a deadline. If they remain alive, shutdown raises TimeoutError after a final bounded cleanup attempt. Regression tests cover inherited-pipe timeout, active-job shutdown, and FastAPI lifespan wiring. Daemon threads remain a last-resort process-exit behavior; abrupt termination such as SIGKILL cannot run Python cleanup, so this is still a private prototype rather than a long-lived public service.

Follow-up validation: the service test suite passes with source-pinning, pipe-drain, and shutdown lifecycle cases; no second heavy Docker build was run because worker command and compiler inputs are unchanged.
