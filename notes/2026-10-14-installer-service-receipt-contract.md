# Installer service receipt contract — 2026-10-14

## Result

The local FastAPI prototype now admits a successful worker result only when its receipt matches the exact selected module groups, ordered project list and startup project, bounded app size, embedded content summary, and the currently linked-but-disarmed SAVE/codec metadata. The API still exposes only a private diagnostic result summary. It does not build, store or serve firmware artifacts, create cluster jobs, deploy, or access hardware.

`WorkerTemplate` now requires a lowercase, 64-hex SHA-256 image digest (`sha256:<hex>`). The in-memory admission store and fake adapter now prune expired terminal records after a bounded retention period. Defaults are at most 64 records retained for one hour, no more than 128 records/24 hours when explicitly configured, and at most four queued/running jobs. Active work is not expired; when the record cap is full, submissions return 429 until a terminal record expires. This bounds the prototype's per-process record memory, but it is not durable or coordinated across processes.

## Receipt checks

`_verify_result` rejects malformed/non-unique JSON, oversized output, non-diagnostic status, mismatched canonical request hash or ordered project IDs, wrong startup index/ID, app hash/byte mismatch, zero or over-budget app, and any install/hardware/runtime claim. It verifies that `module_selection.selected` exactly equals the admitted ordered module groups; the embedded assets equal the receipt's ordered project-content list; asset count, packed byte sum, ordered packed hashes and prepared-profile hash agree; and native playback/sequence semantic verification remain false. It requires the SAVE service to be linked with the expected compile definition and all storage/flash/runtime/hardware flags false. It also requires the compact state-bin writer mode, expected compile definition, exactly-one replacement marker, and well-formed source/fresh/cached object hashes.

This checks receipt consistency. The actual build controller remains responsible for producing a trusted receipt from its link audit; the prototype has no worker signature or independent ELF/artifact verifier.

## Retained build API exercise

The saved top-level `image.json` from `/home/claude/mvave-fm1/save-codec-controller-validation-20261014/run/` predates the current receipt fields, so the integration test does not pass that stale JSON through as a success. It regenerates the current-format receipt in memory using `checked_link_receipt` with retained `selection.json`, the prepared profile, `verification.json`, `artifact.json`, `app.bin`, and `link/lunar-app-probe.elf`. It then submits the retained request through FastAPI TestClient, binds the fake job submission to the canonical request SHA, returns the retained app bytes plus regenerated receipt, and verifies a 200 success summary. The same regenerated receipt is mutated to test wrong module selection, absent codec metadata, wrong startup project, and an app budget one byte below the actual app; each returns 502.

The retained source data is specific to Hera and is supplied to the environment-gated test with `LUNAR_RETAINED_BUILD`; test code defaults to skipping this integration case elsewhere. No retained input files are modified.

## Verification

On Hera, with the task venv at `/tmp/lunar-installer-service-venv`:

```text
python -m pytest -q tests/test_installer_service.py
33 passed, 1 skipped, 1 Starlette/HTTPX TestClient deprecation warning

LUNAR_RETAINED_BUILD=/home/claude/mvave-fm1/save-codec-controller-validation-20261014/run \
  python -m pytest -q tests/test_installer_service.py -k actual_retained_controller_receipt
1 passed, 1 Starlette/HTTPX TestClient deprecation warning
```

The integration case is also part of the full suite when `LUNAR_RETAINED_BUILD` is set. `git diff --check` passed. No compiler build, deployment, public listener, cluster job, USB/MIDI, flash, power, or reboot operation occurred.

## Scope and next step

Changed files are limited to `tools/installer_service/api.py`, `tests/test_installer_service.py`, and this note. This remains a local prototype with a fake adapter. A real adapter requires separate owner-approved worker image, queue, persistence, authentication, resource isolation, result retention/storage and deployment decisions; a successful diagnostic receipt is not installation or hardware acceptance.
