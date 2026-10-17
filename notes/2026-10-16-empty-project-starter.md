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
