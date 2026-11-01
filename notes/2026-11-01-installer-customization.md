# Offline installer customization extraction — 2026-11-01

Personal, non-commercial Lunar Modulator project. No device I/O or publication.

## Scope and provenance

Base main `a1b7823b`; branch `feature/2026-11-01@installer-customization`.
Extracted the bounded static page/import closure from
`feature/2026-10-11@installable-firmware` at
`cccd21cc5dc82859ed8a5d84f0a7a40646d07353`, which already contains
continuous-installer-service `93a287c8`. No branch merge, native backend,
firmware implementation, vendor bytes or OTA transport was imported.
The nine JavaScript modules reference only one another. Styles reuse existing
`style.css`. Seven separate init/replacement example sources were added;
main's four existing examples are unchanged. Existing asset provenance pins
are retained, and source digests are recomputed by the exporter [verified].

The exporter uses the actual `engines/modules/catalogue.mk` through Make's
`print-modules`, and has no packed-profile/backend import. Its small group map
is local. It exports all 55 production module IDs, eleven project choices,
one companion SET, content hashes, raw source dependencies and truthful false
install/link/RAM/hardware flags [verified]. Source dependency validation does
not establish packed dependencies or native playback. The owner-approved
Event Horizon musical choice remains distinct from native/release acceptance.

## Safety and behavior

The shipped service marker is disabled. The page exports a JSON request and
says that builds and installation are unavailable. Optional private-service
client binding remains available for future integration; receipt identities,
selection, content, runtime profile and stale-result rejection remain checked.
Its diagnostic profile constants preserve the source branch's contract; this
slice does not implement or independently certify that absent backend.
Local package diagnostics cannot admit a package or enable installation,
even when its nested structure and CRCs pass [verified]. No OTA adapter is
in this page's dependency closure.

## Checks

- `python3 tools/native/export_image_catalogue.py`: succeeds against current
  main catalogue and every source requirement [verified].
- `.venv/bin/python -m pytest -q tests/test_native_image_catalogue.py
  tests/test_native_module_selection.py`: 67 passed [verified]. Used existing
  main project venv by absolute path, bounded Make metadata only, no compiler.
- `node --test sim/web/test/installer*.test.mjs
  sim/web/test/native*.test.mjs`: 77 passed, one optional private stock-derived
  FWSC fixture skipped, zero failed [verified]. Includes real exporter/UI
  integration, selection validation, exact custom subsets, in-flight stale
  result invalidation and package fail-closed checks.
- Test-only nested synthetic fixture was decoupled from the older branch's
  native model: explicit synthetic reserved geometry, no vendor data. Outer
  FWSC tests still compare the existing Python inspector; nested tests cover
  malformed geometry, repaired CRCs and incorrect SFC origin. Do not claim
  independent Python nested-model equivalence for this slice.
- Rarefaction root and Serena config select absolute main checkout, not this
  external worktree. Both inspected representative `createWav`; Rarefaction
  found its real worker and test callers; Serena overview found its symbol.
  Shared root was not switched during concurrent work. Main-tree tools cannot
  certify newly added external-worktree symbols; file/import inspection and
  runtime tests cover this slice. No global semantic configuration changed.

## Integration and remaining gates

Coordinator owns Pages workflow: run
`python3 tools/native/export_image_catalogue.py > sim/web/www/demo-image-catalogue.json`
before the existing static site copy. Never commit generated catalogue output.
Coordinator owns actual Chrome wide/narrow visual review, independent source
review, CI, PR and merge. No public deployment marker should be enabled.
Release-ready native firmware, hardware listening/boot acceptance and protected
package admission remain separate incomplete milestones.

## Lifecycle and recovery

Worktree: `/Users/likwid/.codex/worktrees/lunar-installer-customization-20261101`.
Small test logs remain under ignored `scratch/installer-customization-20261101`;
pytest temp outputs and exporter temporary/build directories are removed after
checks. Exporter TemporaryDirectory cleans its Make-generated headers on exit.
No daemon, container, download or heavyweight build was created. Mac free space
was 1128 GiB at start (500 GiB floor retained). Remove this owned worktree with
`git worktree remove` after integration once coordinator has preserved this
handoff and verified backups. Parent receives exact pushed SHA in exit report.
