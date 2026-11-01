# Private installer build service

This is the private backend for browser-exported Lunar Modulator customization requests. It validates request/catalogue membership, queues one fixed worker, checks app/ELF/receipt/provenance bindings and returns a bounded status preview. There is no artifact download, device connection or installation route. `installable`, hardware admission and release acceptance remain false.

The production launcher is **disabled on the current integration**. Its native source prerequisites and native ELF audit capabilities are incomplete. Importing the API and testing it with an explicit synthetic adapter does not establish native build availability.

## Local operator entrypoint

Install the pinned application dependencies into a project virtual environment. The eventual operator command is:

```sh
python -m tools.installer_service \
  --source-commit FULL_REVIEWED_40_CHARACTER_SHA \
  --toolchain /private/pinned-pi32v2 \
  --catalogue /private/verified-catalogue \
  --runtime /private/installer-jobs \
  --enable-private-builds
```

This command currently refuses before any worker or listener starts. It requires the running checkout, a clean exact Git commit, committed native runtime files, compatible native audit functions, the reviewed immutable worker image, matching private-directory ownership, a separately provisioned toolchain and verified catalogue. It never provisions a Docker image or downloads those inputs. The launcher accepts no host option and binds only `127.0.0.1:8765`, with one worker, no proxy headers, an exact Host allowlist and no CORS grants. Serve it only on an explicitly reviewed private machine; no public deployment is implemented or authorized by this source slice.

Workers use Docker without network access, dropped capabilities, read-only source/toolchain/catalogue mounts and bounded scratch/log/output/time limits. The fixed Aeon policy is CPU4–7, at most4CPU/6GiB, under `docker-batch.slice`. There is no native execution in the offline tests.

## Protocol and lifecycle

- `POST /api/v1/builds` accepts bounded UTF-8 JSON under the shared strict `request_contract.py`. Duplicate keys, non-finite numbers, unknown fields, wrong catalogue groups and mismatched startup/SET parents are rejected. Client fields never select paths, commands, mounts or images.
- `GET /api/v1/builds/{opaque_id}` returns queue state or independently validated preview hashes and summaries. A successful worker process alone does not establish a valid result. Retention is lazy: terminal records and private job directories expire on subsequent API requests; clean shutdown drains active workers and removes this process's admitted job directories. Failed shutdown or a crash leaves recovery evidence in the operator-owned runtime directory; the launcher does not sweep unknown directories. Inspect and remove those exact stale job directories before reusing that private experiment directory.
- `private_package_candidate.py` is a separate offline composition API. It validates the exact preview/source binding, reruns the request through the independently pinned trusted wrapper, requires byte-identical app/ELF and composes only captured tuple inputs. No web endpoint calls it. It first requires the same native audit/runtime capabilities as the private launcher. Failure logs remain private, owner-only and capped; process capture has a deadline and cleans up its process group. The parent records its unique container name in0600 `trusted-wrapper-owner.json` before launch. Parent and child cancel only that exact name after verifying its owner label; unconfirmed daemon cleanup preserves this recovery handle and refuses success. Docker logging rotates at1MiB/one file, and Docker control/log responses are byte-bounded from capture start. A private FWSC candidate is not installation or distribution admission.

The continuous and Hall diagnostic profile constants were extracted from historical source `cccd21cc`. They prescribe exact expected receipt values; they are not current runtime memory measurements. Every real result must bind the exact source commit/tree/archive, worker/image, toolchain/catalogue, request, app and ELF. Changed runtime measurements require a separately reviewed versioned profile. Existing source/notices archives remain explicitly incomplete and distribution-ineligible, and no vendor/private firmware data is included here.

## Outstanding native dependency

Main's `tools/jieli/audit_link.py` lacks `relative_call_payloads`, `stub_call_boundary_patterns`, the corresponding `audit(call_payloads=..., stub_boundaries=...)` parameters and the `--objdump` option required by the historical native builder and `probe_artifact.py`. Startup detects this without importing or executing the target validator. This lane leaves that security-sensitive port and native firmware/runtime sources to their independent owners; it adds no substitute proof or relaxed guard.

Focused offline checks cover queue/retention, refusal/security rules, receipt/profile/SET and source-archive binding, plus real harmless Python-child log/timeout/descendant cleanup. Private retained-image tests and actual native-runtime inventory coverage skip only when their explicit inputs are absent. Full native link, hardware recovery/boot, storage safety, MIDI/audio/performance and distribution acceptance remain separate gates.
