# Empty project starter investigation

Task base: `0ecf508bfc71182f424f46fc36df450af7b42310`.
Branch: `feature/2026-10-16@empty-project-starter`.
Worktree: `/Users/likwid/.codex/worktrees/empty-project-starter`.

The proposed selectable, unselected engine-less starter has a format blocker
[verified]. At this base, `state_json_write.c` refuses a project without an
engine in Sound 1; `state_json_read.c` refuses Sound 1 `null` and requires every
unit object's engine; `state_bin.c` rejects an explicit empty primary sound.
`tools/lunar_state.py`, the project JSON schema, existing codec tests and the
panel's `sound_empty_ok()` policy agree. An app initialized without engines is
not an established serializable project format.

The existing real host `fm1-state` executable at the coordinator checkout was
run against temporary first-party minimal JSON fixtures. `pack` rejected
`sounds: [null, null, null, null]` with `BAD: Sound 1 is never empty`,
`sounds: [{}, null, null, null]` with `BAD: a unit needs its engine`, and
`sounds: []` with `BAD: Sound 1 is never empty`. No asset or codec policy has
been changed to evade these checks.

Two coherent options were reported to the coordinator: explicitly extend the
project format/runtime empty-primary policy with focused cross-codec tests, or
add named init starters with valid primary engines (at least Trio, Macro and
Shapes to cover the four requested disjoint subsets). A single fixed valid
current-format source project cannot support all of Trio-only, Macro-only and
Shapes-only. Event Horizon remains the approved musical default and its
optional SET parent/startup constraints remain intact.

The service's trusted catalogue currently caps the total catalogue at eight
project IDs. Any added starter needs that catalogue cap adjusted separately
from the existing eight-selected-project request limit.

Semantic tools were checked [verified]. Rarefaction Python and Serena cpp
remain on the shared primary checkout, not this worktree. Bounded orient and
find_symbol calls returned ENOENT for source files missing in that primary
checkout. Shared global roots were not changed; actual worktree source and real
host codec results provide the evidence above. No heavy build, Hera access or
device action occurred. Native key/engine-UI and hardware acceptance are outside
this host-format investigation.

## Approved valid init starters

The coordinator approved the second option above: three explicitly named init
patches, without any engine-less codec/runtime change. Investigation checkpoint
`90a2063fbc8c99e0d0b2f7c41e812ea5bfd4162c` was pushed and its remote SHA verified.
The implementation follows that checkpoint on this branch.

Three first-party MIT assets were canonicalized by the existing real host
`fm1-state canon` [verified]. Each has its named default engine in Sound 1,
three null later sounds, null master effects, and no insert/MIDI effect,
modulation, sequence or SET dependencies. Pack/unpack reproduces each source
byte-for-byte; packed unit records contain only the named engine [verified].

| Trusted project ID | Sole engine | Source SHA256 |
| --- | --- | --- |
| `init-starter-trio` | `trio` | `46541967e4fa7321f4efe1105632de3613064a2fbcf7d71490cb647247a97c1b` |
| `init-starter-macro` | `macro` | `ba5ee5ad6ad38ceba921ce59a9ace12551dfccaee86329a069737ecc4973f055` |
| `init-starter-shapes` | `shapes` | `c05fbc9d8105eb9e863aebaaf3ed3b199d8f638c6f3e66a9eb7e769e0626855d` |

Assets are under `engines/state/examples/init-starters/`. The catalogue labels
these as init patches without a song, supplies no song duration, and leaves
them unselected by default. Event Horizon remains the selected default full
song and keeps its optional SET dependency. Total trusted inventory increases
from eight to eleven; both browser serializer and API retain the maximum of
eight selected projects. The source dependency scanner now accepts canonical
null sound/master slots; packed records remain authoritative [verified].

Actual production-catalogue chooser, API admission and `prepare_selection`
tests cover these exact sound selections, without a hidden Trio dependency
[verified]:

| Selected engines | Selected projects in order | Startup index |
| --- | --- | --- |
| `trio` | `init-starter-trio` | 0 |
| `macro` | `init-starter-macro` | 0 |
| `shapes` | `init-starter-shapes` | 0 |
| `macro`, `shapes` | `init-starter-macro`, `init-starter-shapes` | 1 |

All four requests use `version: 1`, empty effects/MIDI/modulation arrays,
`flash_layout: expanded-d7000`, and `runtime_mode: continuous`. The combined
case intentionally demonstrates preserved project order and Shapes startup.
Additional effects/MIDI/modulation remain selectable through the existing
builder policy. No request-selected toolchain/flags/paths were added.

## Checks and integration handoff

Using the existing coordinator host codec (no new target build):

```sh
FM1_STATE_TOOL=/Users/likwid/.codex/worktrees/installable-firmware/mvave-fm1-firmware/engines/build/fm1-state \
/Users/likwid/.codex/worktrees/installable-firmware/mvave-fm1-firmware/.venv/bin/python \
  -m pytest -o addopts='' -q tests/test_native_init_starters.py \
  tests/test_native_image_catalogue.py tests/test_native_demo_selection.py \
  tests/test_native_stage_demo_profile.py tests/test_installer_service.py \
  tests/test_installer_continuous_profile.py
node --test sim/web/test/*.test.mjs
```

Results [verified]: Python **257 passed, 1 skipped**, with one existing
Starlette/httpx deprecation warning; JS **109 passed, 1 skipped** (110 total).
The new starter file alone has six passing tests. `git diff --check` passes.
A real Chrome localhost preview confirmed all three labels/cards have clear
spacing and unselected initial state, Event Horizon selected, and the public
service marker disabled. The temporary server/tab and generated catalogue were
removed after inspection.

These are host codec/preparation/admission checks, not target ABI/flash/RAM or
device acceptance. All four selected subsets require fresh source-bound Aeon
target links/fit receipts by the coordinator. Native project-load/controls,
engine UI, physical keys and playback remain unverified. No hardware, Hera,
heavy container, binary distribution or public-service enablement occurred.
Root owns review/integration and the next Aeon target-fit dependency; there is
no owner-input blocker for this implementation.
