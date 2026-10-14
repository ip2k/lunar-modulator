# Private artifact delivery and custom build tuple review

Date: 2026-10-14

## Scope and status

Read-only audit at source base `1f020b4b497ce8f71add8cca07e0ba86352dc540`. This note proposes the smallest next implementation for a private, authenticated artifact-delivery path and a caller-selected build tuple. No source code, deployment, device, package admission, or acceptance flags were changed. The existing service is a local diagnostic prototype; all installability and hardware-admission claims remain false.

## Findings

The API already accepts caller-selected module IDs in `BuildRequest` (`tools/installer_service/api.py`, `BuildRequest`, lines 52–74). Its verifier checks the selected modules, project IDs, startup project, embedded project hashes, app/ELF hashes, codec metadata, and false admission flags (`_verify_result`, lines 213–310). The accepted module choices are resolved against trusted server-side catalogue data; the request does not accept arbitrary filesystem paths or commands.

There are two limits to that flexibility. First, `prepare_demo_selection.py` and `stage_demo_profile.py` resolve only the fixed server-side demo-project registry. A caller can select catalogue modules and preloaded demo IDs, but cannot upload a custom project or set. Second, `prepare_image_profile.py` can parse packed set records, but the public API verifier currently requires each embedded content row to have `kind == "project"`; set assets are rejected. A custom pack feature therefore needs a deliberate API/schema extension and dependency-completeness validation, not a path field or a relaxation of the existing verifier.

The real Docker worker returns a retained tuple of `app.bin`, `elf.bin`, and `image.json`, and the adapter verifies the app/ELF digests before retaining them (`tools/installer_service/docker_worker.py`, lines 49–62 and 121–127). The API offers `POST /api/v1/builds` and `GET /api/v1/builds/{id}`; the latter returns status and a result summary, not artifact bytes (`tools/installer_service/api.py`, lines 418–440). Build records are in memory. Adapter job directories contain request/source archive/entrypoint/output/log data and are deleted only on explicit adapter cleanup; a process restart loses in-memory job records, so private output retention and orphan cleanup need a durable policy.

There is no authenticated principal or owner-bound artifact authorization in the API. An opaque build ID is not authentication. The current service implementation note and delivery audit already identify missing authentication, origin/CSRF policy, private durable storage, retention, restart cleanup, and abuse controls. The browser’s static fallback exports request JSON; it is not a private artifact delivery channel.

The package composers are not general backends. `tools/jieli/model_092_app_replacement.py` pins one stock FM-1_092 source and one app/layout profile. `tools/jieli/compose_500_continuous_d7000_candidate.py` pins one exact app, ELF, receipt set, runtime policy, and module selection. Reusing either as a generic user package endpoint would falsely imply that arbitrary builds satisfy those stock-input, layout, and receipt gates. The current 500 composer note explicitly keeps package admission, hardware admission, and release admission false.

## Recommended minimal design

Keep the diagnostic build service and the future private artifact/package service as separate trust stages:

1. Preserve the current strict request shape for catalogue module IDs and preload IDs. Add custom project/set content only as an explicit, bounded upload/import feature. Store bytes in a server-owned per-job input directory under a generated ID; never accept caller paths, commands, output locations, toolchain selection, or stock firmware paths. Validate format, size, record count, dependency scan completeness, and all content hashes before dispatch.
2. Make the build result a versioned manifest binding the canonical request, selected module IDs, ordered embedded projects/sets, startup selection, runtime mode, source/toolchain/catalogue identity, and exact hashes/sizes of `app.bin`, `elf.bin`, and `image.json`. Keep the current independent receipt verification and false admission fields. Preserve a deterministic explicit default profile policy separately from custom selections.
3. Add artifact download only after an authenticated owner principal has been selected. Resolve `(principal, build_id, artifact_name)` through a server-side record and an allowlist of the three verified tuple artifacts; do not resolve a user-supplied path. Use the framework’s normal response/file streaming primitive, with private storage permissions, safe content headers, bounded streaming, and authorization on every request. An unguessable ID may supplement, but never replace, authorization. Reject expired, deleted, cross-principal, unknown-name, symlink, and hash-changed artifacts.
4. Keep stock-reference inputs out of the general build worker. A separate trusted packaging stage may combine a reviewed build tuple with the exact privately held stock input required by a specific package profile. That stage needs a profile-specific verifier for source identity, protected component byte preservation, address-dependent encoding/CRC, layout, full output hash, and a durable provenance manifest. It must not return stock private bytes or reference material through build downloads.
5. Before implementing auth, the owner must choose the service’s trust boundary and identity source (for example, an existing authenticated same-origin reverse proxy with a verified principal assertion, or another explicitly chosen account system). Do not invent owner identity or ship a bearer-token secret in the static client. Then define same-origin/CSRF/CORS behavior, retention/deletion, restart recovery, and rate/size limits around that principal.

This keeps caller-selected module packs useful without conflating “build succeeded” with “package is installable.” It also leaves existing stock-preservation safeguards and admission gates intact.

## Required tests for the next implementation

- Request and result manifest reject duplicate JSON keys, unknown modules, bad project/set records, incomplete dependency scans, altered content, invalid startup IDs, and oversized inputs.
- Artifact route permits an authenticated owner to retrieve only the named tuple files for their own build; denies unauthenticated, cross-owner, expired/deleted, unknown filename, path/symlink, changed-hash, and missing-file cases.
- Restart/recovery tests prove that stale in-memory state cannot expose orphan artifacts; retention cleanup removes all job input/output/log copies as specified.
- Packaging tests prove the selected profile’s protected stock components are logically preserved and address-specific transformations/checksums are correct, while unsupported layouts refuse. No package is marked installable by the build API.

## Evidence and limits

Reviewed the service/API/worker/adapter, custom selection and profile-preparation tools, 092 replacement model, continuous FM-1_500 composer, and prior installer design, implementation, delivery, and build-tuple notes. No tests were run because this task was a read-only architecture audit. No current primary external documentation was needed: the concrete constraints are in the checked-in API and adapter, and the recommendation is to use the existing framework’s standard response primitive only after the project selects an authentication mechanism.

Rarefaction status was checked and is ready on the Mac primary checkout; Serena’s current project configuration also points to that Mac checkout. I did not switch either shared semantic tool to the Hera isolated worktree. Findings were verified by direct source inspection in the exact Hera worktree, so semantic navigation coverage is not claimed for that checkout.
