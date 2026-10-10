# Warble + Repeat isolated integration candidate

This branch is a preparation candidate, not merged or accepted for demos.
Parent controls merges after all required exact-head checks pass. No hardware
traffic, device timing evidence or native Safari listening pass is claimed.

## Source provenance

[verified: Git merge parents] Starting main is
`c5fd5e9e01d5c8204e287d3986c929626f19422e`. Warble PR123 parent is
`0e43e503be47737446c1ccd03915f1a888ce9803`; Repeat PR137 parent is
`9b2d80c4c6a9df47c794fa4d413a72e12b645225`. Both source histories are retained.
Pending PR123/137 worktrees and CI heads are unchanged.

[verified: source conflict inspection] Both MIT DSP implementations are
retained unchanged. Shared catalogue/default list, editor effect groups and
user documentation include both effects. Registry and scenarios merged with
both entries. The stable existing parameter UIDs are retained. New metadata
must come from the actual combined native/Wasm build.

## WIP source checkpoint and recovery

The source milestone deliberately removes `sim/web/www/fm1.wasm`,
`fm1.wasm.json` and `meta.json` rather than selecting either branch's stale
binary. This checkpoint cannot pass simulator tests or be served as a preview.
The example metadata ID is also pending regeneration from the combined native
export. No failing checkpoint is eligible for merge.

Next: bounded LAN native build; regenerate only the example metadata ID from
its exact known-module export; build musl and Wasm from the combined sources;
run full parity/screens/metadata/edit checks and focused effect, API,
parameter, smoothing and state checks; then checkpoint generated artifacts
with recomputed source hashes and build provenance. Final combined acceptance
also requires the normal browser/CI gates. Existing frozen-clock WebKit and
owner listening receipts remain failures until independently resolved.

Recovery worktree: `~/.codex/worktrees/warble-repeat-candidate/mvave-fm1-firmware`.
LAN sources: `/home/claude/mvave-fm1/warble-repeat-candidate-20261009/src`.
