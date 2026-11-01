# Offline installer request contract — 2026-11-01

## Scope and result

Added a small, offline request validator at `tools/installer_service/request_contract.py` for browser-exported requests and generated image catalogues. It validates syntax, API-shaped strict fields, group membership, project membership and companion SET parent/startup binding. The output always carries `installable: false`; it does not compile, package, return firmware, contact a service or touch a device.

The module accepts the catalogue emitted by `tools/native/export_image_catalogue.py`: `groups` maps the four request group names to module ID arrays, `projects` contains project rows keyed by `id`, and `sets` contains rows with `id` and `parent_project_id`. The current exporter branch reports these names and mappings. The contract carries the same mapping locally to keep this branch independent until integration; replace it with the shared schema when both commits are integrated if that schema becomes a common module.

## Request compatibility

The strict Pydantic v2 request model follows `tools/installer_service/api.py` at the installable-firmware reference checkout, specifically `BuildRequest`, `canonical_request`, `_unique_object`, and the `read_bounded_json` validation path (API lines 19, 62–115, 725–767 at inspection). It preserves version 1, list bounds, strict integer/string handling, extra-field refusal, unique IDs, startup range, default `flash_layout` / `runtime_mode` behavior, D7000 runtime restrictions, and the named song-diagnostic prerequisites. `model_dump(mode="json", exclude_defaults=True)` plus compact sorted JSON and one trailing newline produces the API's canonical request representation; explicit empty `set_ids` is elided.

Request bytes are capped at 65,536 bytes; catalogue input is capped at 4 MiB. Both reject duplicate JSON keys (at any nesting level), non-finite numbers, non-object JSON and malformed UTF-8/JSON. Catalogue IDs must be well-formed and unique, and a SET must name an existing project. Requests reject test-prefixed modules, unknown/wrong-group modules, unknown projects/SETs, and SETs whose parent is not the selected startup project.

Pydantic is pinned to the same 2.14.1 version as the existing reference API in `tools/installer_service/requirements-contract.txt`. The contract does not import or copy the native-builder closure and leaves the reference service unchanged.

## Checks and limits

- `python3 -m unittest -v tests/test_installer_request_contract.py` in a temporary local venv with the pinned Pydantic: 15 passed.
- `git diff --check`: passed.
- Tests cover valid minimal/default request bytes, a valid continuous D7000 request, valid SET binding, CLI output (`installable: false`), and refusal paths for schema extras/types, duplicates, malformed/non-finite/oversized JSON, test/unknown/wrong-group modules, unknown IDs, cross-startup SET, duplicate catalogue IDs, invalid runtime combinations and missing song-diagnostic prerequisites.
- The current source API was read directly from the installable-firmware worktree; no import or execution of its API/backend was attempted. No catalogue build, firmware build, service operation, device I/O, USB, MIDI, flash, deployment or package admission was run.
- Rarefaction remains fixed to `/Users/likwid/Developer/mvave-fm1-firmware`; status showed Python ready, and a bounded position query resolved only the primary checkout's `tools/fm1_identify.py` (2080 indexed files, on-open index). It cannot see this assigned external worktree. Serena was activated for `/Users/likwid/.codex/worktrees/lunar-installer-contract-20261101`; its symbol overview and body query resolved the new `validate_request` source, while diagnostics reported Pydantic unresolved because the project interpreter was not configured to the temporary venv. The installed pinned venv and tests supplied the dependency check. No semantic callers from Rarefaction are claimed because this module is new and outside its root.
- `df -g /System/Volumes/Data` before work reported 1127 GiB available. The temporary `.contract-venv` is removed after testing; no other scratch output is retained.

## Remaining integration work

Integrate with the separate installer customization branch, then point the offline chooser/CLI to the generated catalogue. Keep release/package admission and artifact return as separate future boundaries; this CLI proves request/catalogue consistency only and never proves a build, package, updater, hardware or installability acceptance gate.
