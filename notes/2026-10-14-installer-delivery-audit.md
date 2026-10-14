# Installer delivery audit: diagnostic build to installable artifact

Status: read-only audit at source commit `5bf37c01e30610a826ef28856cca7449a87d9090`. No package was built, service deployed, or device operation performed.

**Follow-up correction:** the fixed stock-OTA extent language below must be
read as the current V15/open-loader profile, not a proven proprietary-loader
limit. See `2026-10-14-expanded-ota-feasibility.md` for the successful larger
FM-1_092 counterexample. The current Lunar image remains unadmitted, and the
artifact delivery/authentication gaps identified here are unchanged.

## Finding

The FastAPI/Docker worker currently produces only `app.bin` and `image.json`. `_verify_result()` hashes the app and checks exact request, project/startup, module selection, embedded content, SAVE-service and codec fields, then returns only status, digest, byte count, app budget/free bytes, `installable: false`, and `hardware_tested: false` (`tools/installer_service/api.py:193-282`). The only routes are POST `/api/v1/builds` and GET `/api/v1/builds/{id}`; there is no artifact-download route (`api.py:348-410`). The container writes only app.bin and image.json (`tools/installer_service/docker_worker.py:90-100`).

The browser client expects false installability/hardware fields (`sim/web/www/installer-build-client.js:130-153`); the page says no installable file is available and otherwise downloads only the JSON build request (`sim/web/www/installer-page.js:9-16, 79-113`). The package classifier rejects bare app, raw 1 MiB flash, ELF, FWSC-like candidate and unknown bytes; its verifier always throws (`sim/web/www/native-package-admission.js:27-45`). The OTA adapter requires an independently reviewed verifier that returns a `logicalImage` capability, but none is supplied (`sim/web/www/native-ota-adapter.js:82-118`). A passing diagnostic receipt cannot become an installable browser artifact by changing a flag or adding a link.

## Packaging routes and inputs

| Route | Inputs | Present blocker |
| --- | --- | --- |
| Preserved stock FWSC/OTA | Supported stock package/reference, unpacked stock component tree, exact app, independently checked rebuilt FWSC preserving SPL/config/OTA/cfg | The stock V15 app component is 581,564 bytes. The full-song app in `notes/2026-10-14-current-ota-package-plan.md` is 862,296 bytes, 280,732 over. Existing `tools/native/ota_candidate.py` is a separately pinned 20-second prototype (specific stock/app hashes and identity `FM-1_990`) and marks physical boot, recovery, web install, and release readiness false. The recorded expanded geometry ends at `0xD9000`, beyond stock OTA's `0x93000` write extent. A raw image is not FWSC/OTA. |
| Expanded raw-flash candidate | Exact app, ELF/disassembly, two matching full 1 MiB baseline dumps, backup manifest/identity and the stock reference parsed for nested records | `tools/native/expanded_candidate.py::construct()` independently flattens ELF, audits link and calls `expanded_flash_profile.construct_geometry()`. It emits a private raw-flash candidate, not OTA, and leaves writer-ready, hardware approval, binary emitted, installability, recovery and migration false (`expanded_candidate.py:48-60`; `tools/jieli/expanded_flash_profile.py:50-71`). Browser rejects raw flash. Offline geometry and matching backups do not prove physical sector ownership/recovery. |

`tools/jieli/package_guard.py` requires the pinned stock SPL and byte-identical `top/isd_config.ini`, `ota.bin`, `files/cfg`, with no foreign loader. These opaque bytes may contain owner-specific settings/state. Keep them on the trusted owner machine: do not mount full-flash backups, stock package trees, config, or keys into the general worker, CDN, or public browser endpoint. The current worker mounts source, toolchain, catalogue, request, and output only.

## Minimum bridge

1. Preserve a verified build tuple: exact app, ELF, image receipt, request/profile identity, source/toolchain/catalogue digests. Hash and bind all files to the same build ID. Today the worker exports no ELF and the API response does not return app bytes. An engineering-only app download must remain explicitly non-installable.
2. Construct on a trusted owner-controlled packaging host. For expanded raw geometry, use locally held paired fresh backups and manifests/identity/reference; keep these inputs private. For stock FWSC, use an independently validated packer and preserve every package_guard component. The recorded large app is incompatible with current stock OTA bounds; a request option cannot widen them.
3. Emit a package receipt bound to package/app/ELF/source/build hashes, selection/startup, baseline identity/hashes, layout, changed sectors and preserved-range hashes. Independently parse and verify the emitted package; bind transport format and exact target. Never accept caller-supplied `installable: true`.
4. Add a separate authenticated, owner-scoped download and UI state only after package verification. Use bounded response size, Content-Length, SHA-256, attachment filename and `Cache-Control: no-store`. Browser admission may issue `logicalImage` only after proving container/nested bounds and CRCs, exact target identity and protected-component correspondence. Define and review a transport that accepts expanded geometry before calling it installable; do not assume present OTA supports it.
5. Protect access and retention. `create_app()` has no auth middleware or owner identity (`api.py:285-310)); `credentials: 'same-origin'` is a fetch setting, not authentication. Add owner authentication/authorization, origin/CSRF protection and owner-bound job/artifact IDs before exposing private artifacts. Opaque IDs alone are not authorization. Retention is 60–86,400 seconds (default 3,600) and lazy: terminal records are removed only on later POST/status calls (`api.py:288-305, 355-402`). Admissions are in memory, while adapter job dirs retain request/source tar/log/result and are removed via `delete()`; define restart cleanup and explicit deletion. Browser cancel only stops local waiting; there is no server cancel endpoint (`installer-build-client.js:183-185`).

## Privacy and limits

The API calls itself a private diagnostic prototype and hides docs, but that does not authenticate or deploy it. There is no service entrypoint in `tools/installer_service/`; `create_app()` is only a factory. Keep any bridge private until auth, owner-scoped retrieval, CSRF/origin policy, restart cleanup and a reviewed service boundary exist. Never place a raw candidate or stock-derived image in public static hosting.

Reviewed exact source at the commit above: API/adapter/worker, browser client/page/admission/OTA adapter, expanded candidate/geometry, package guard, and OTA/package-admission notes. No tests run; this was a read-only audit. Serena and Rarefaction remained selected to the Mac primary checkout; Hera source was inspected directly over SSH. No current-CI, package, loader execution or physical acceptance claim is made.

## Next dependency

Choose the intended delivery format: private engineering download of diagnostic app.bin; stock FWSC (currently size/layout blocked for the recorded full-song build); or raw expanded candidate through a separately reviewed transport/recovery workflow. Then implement packaging on a trusted host without widening the general worker's access to private stock data. Keep browser admission fail-closed until container and device gates are evidenced.
