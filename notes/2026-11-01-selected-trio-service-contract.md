# Fixed Trio service contract, 2026-11-01

Base 7ab2810420999629d170531a6f2f78fd44a8484f. Owner: installer release audit lane.
Scope: new build_capabilities.py / selected_trio_profile.py, pure focused tests,
and this note. No v1 API/canonicalization, launcher, worker, native or browser
behavior changes are needed for this bounded source-only slice.

Plan: explicit version-2 fixed Trio request with offline/stock-sized-diagnostic semantics;
profile-specific committed-source prerequisites separate from the historical
launcher gate; byte-bounded pure validation of the actual selected-target receipt,
ELF/flat/blob/resource/audit and externally trusted source/toolchain/header/tool
bindings. Trust anchors must come from the future trusted worker/operator, never
from request or receipt fields. All install/release/hardware/distribution flags
remain false and service capability stays disabled. No ROM20 translation.

Actual exact-root target receipt is pending from its existing owner. Synthetic
fixtures test refusals and format coherence only; no real-build acceptance claim.
No target job, listener, Docker, USB/MIDI or hardware is part of this lane.

Rarefaction root remains shared primary; orient/scope reject sibling worktree
project escape. Serena absolute canonical_request lookup matched source bounds.
No shared root/server switch. Exact worktree/Git source is authority.

Tests use the existing service venv with bytecode/cache disabled and an exact
owned scratch basetemp; remove it in the same flow after retaining small logs.
Source worktree remains for independent review; remove only after integration.

Checkpoint: strict v2 fixed-selection/request/capability/source prerequisite and
malformed-ELF tests plus unchanged v1 request suite pass (63 cases). Receipt
validator implementation is WIP pending the real author's build and positive /
causal mutation coverage. This checkpoint does not accept a real native result.
The layout label is stock-sized-diagnostic, with no protected-package claim.

Second checkpoint: 120 focused cases plus 6 subtests pass. Synthetic ELF
coherence fixtures and causal mutations cover actual storage overlap, guard
symbols, flat/blob mismatch after rehashing, retained forbidden symbols, ELF
table overlap/relocations/strides, missing external anchors and changed actual
objects/prepared bytes. The original shared ELF/audit implementation is unchanged.
Actual 7ab target artifacts have arrived; independent positive receipt smoke is
pending external metadata anchor verification. All capability/admission flags
remain false.
