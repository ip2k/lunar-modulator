# Codex restart checkpoint — 2026-10-15 20:35 UTC

Owner requested a safe checkpoint for application restart because of suspected
CPU/memory leakage. Stop new work at this boundary. No new hardware campaign
was started during checkpointing. The overall release goal remains unfinished.

## Resume location and source

Use `/Users/likwid/.codex/worktrees/installable-firmware/mvave-fm1-firmware`,
branch `feature/2026-10-11@installable-firmware`, source checkpoint before this
note `791a13f9e7fd85d6daf693f083eb31da207c1880` (verified on origin).
Unrelated untracked `uv.lock` is untouched. Do not use the primary Developer
checkout for integration. Read current AGENTS.md, CLAUDE.md and HANDOFF.md.

## Physical state and acceptance

[verified: last passive observation] FM1 was at USB port 1-1, bus 1/device 113,
4c4a:8057, WL80 UBOOT1.00. Revalidate after restart; this is a historical
observation, not permission to reuse a consumed campaign. Installed image SHA256
`28483c411f23d7d5fba09b4770dd29b3c66b1a154138e493e6e079e54dcf400f`.
Last measured throughput was 498.453089 blocks/s versus required 689.343750,
with 190.892 underruns/s. Owner cold-boot listening FAILED (lag/distortion).
SAVE and autoplay remain disabled. ROM111 campaign is consumed: never rerun it.
No flash/reset was issued in this checkpoint segment. Root exclusively owns
device operations; workers remain offline. No physical power cycle is needed
for this application restart checkpoint.

## Hall candidate: build verified, deployment not constructed

[verified: offline evidence] Exact source `66c95bb2d413242d30dfdef0175156cb66bebbba`,
tree `542445ed68f663d2ea79162a82e1bf772927e0c4`; 16-shard Hera build and link
reported successful. Root independently rehashed all ten frozen outputs:
`scratch/hall-gain-target-independent-review/root-hash-review.json`.
App 855700 bytes, SHA256
`80175b90053bb568d485ebd71516f19889064a4c8c97c8f87c4d0f0747ad08d0`.
No target performance or hardware acceptance is established for this candidate.

Local worker handoff:
`scratch/hall-gain-delta-deployment/rom113-preparation/HANDOFF.md`.
Its canonical 19-member `build-inputs/build-evidence.tar` SHA256 is
`c56c02c7bfc7c437d806fd0b04bd176e902119abce95e5440dd32a99157382bc`.
The copied ROM111-v3 runtime's expanded_candidate validator admits only earlier
10-body profiles; this build requires 14. Constructor correctly rejected it.
No candidate/campaign package was produced, staged, or launched. Next: designate
and review a coherent tools/runtime revision admitting the exact 14-body profile,
regenerate its complete archive/manifest/transitive pins, then resume file-only
construction and tests. Never swap a lone helper under the old provenance.
Hera output: `/home/claude/mvave-fm1/hall-gain-delta-target-66c95bb-20261015/output`.
Hera handoff: `/home/claude/.local/share/codex-coordination/handoffs/lunar--hall-gain-delta-target-build-20261015.md`.

## Installer: integrated boundary, pending focused fix

[verified: source/host tests] Explicit D7000/song-diagnostic request handling was
integrated at d7a788b8 and 4f1f8a3f. Details and checks are in
`notes/2026-10-15-installer-d7000-integration.md`. All installability flags remain
false. Worker independently found and fixed the remaining native wavetable-profile
binding gap. Pending review/integration commit:
`f138766f266c3ebf8a8ef7e651857c222c84f259`, branch
`fix/2026-10-15-d7000-wavetable-binding`; root independently verified origin SHA.
Worker reports ten focused tests passing. Worktree/handoff:
`/Users/likwid/.codex/worktrees/d7000-wavetable-binding/scratch/d7000-wavetable-binding/HANDOFF.md`.
That handoff's last paragraph predates its completed push; use the verified SHA
above. Root has not yet reviewed the diff, rerun its checks, or integrated it.

[verified: read-only source audit] Trusted-package path review is saved at
`/Users/likwid/.codex/worktrees/installer-d7000-tuples/mvave-fm1-firmware/scratch/d7000-trusted-package-path-review.md`.
The service retains only app/ELF/image receipt, while the existing trusted FWSC
packager needs full authenticated build evidence and an external tuple trust
anchor. Next implementation: bounded private evidence retention plus a diagnostic
tuple adapter reusing existing validators/packager. Current continuous tuple
issuer is not a diagnostic issuer; do not merely change a mode string or allow
the service to authenticate itself with its own digest. No new task dispatched.

## Storage and remaining full-goal gates

Stock 092 VM/BTIF/USR ownership remains unresolved; no sector allocation is
authorized by capacity arithmetic alone. Offline SDK VM signature analysis was
inconclusive; saved handoff:
`/Users/likwid/.codex/worktrees/092-storage-reverse-20261015/scratch/092-storage-reverse/fm1092-vm-signature-review.md`.
Do not infer actual CPU MHz from cached SDK clock calculations; no speculative
PLL/voltage writes. Native compression fits capacity but not yet ownership.

Remaining release gates include sustained correct audio and all-engine playback,
full default Event Horizon song and controls, persistence with proven ownership,
MIDI transport acceptance, interrupted/corrupt-write recovery, selectable web
image composition/download/browser installation, physical acceptance, review/CI
and integration. The scope remains the complete usable release, not a diagnostic.

Workers were asked to save handoffs and stop for restart. No new workers or
builds should be started before honoring this restart boundary. After restart,
inspect live agents/processes and shared claims before resuming or reassigning.
