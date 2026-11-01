# Immutable sequencer event targets in the app

Personal, non-commercial Lunar work. Exact base:
`ba080c86c188d8be25a4f29dbea58c875ca5f59e`; branch
`fix/2026-11-01@seq-app-integration`. Coordinator owns integration and the
combined source WASM build. No device operations or native adapter edits here.

[verified] The app now resolves queued effect/mixer LOCKs from each event's
immutable `label` and `lane_base`. Block-boundary comparison and knob base edits
still resolve the current lane. `seq_auto_release` is unchanged: it restores
configured values through captured engine/unit/index targets before reset/import.

[verified] The new app probe queues audition, release, then optional lane reuse
before one render. It checks core event identity and the ordered old-target
boundary restore/audition/reset writes for inserts, master slots and mixer level.
It checks reused-lane targets/bases and the next clear. With old dispatch retained
and new event ABI scaffolding, the final regression fails `old_writes == 3 &&
new_writes == reuse`; the snapshot dispatch passes. Test rendering uses one frame
after queued edits so an unrelated next-step reset does not obscure these writes.
The manual test LOCK constructor follows the core snapshot contract. The probe's
Makefile now reads its generated dependency file because it includes `fm1_app.c`;
without that, app-only changes could run a stale probe binary.

[verified] Budget: 272 events * 36 B = 9,792 B, up 6,528 B from 12 B/event.
The eight-track instance is 32,080 B inside its unchanged 32,768 B arena; instance,
events, pending command 240 B, UI bound 1,024 B and click 20 B total 43,156 B
within the approved 45,056 B (44 KiB) budget. The desktop app guard grows by the
approved 8 KiB budget delta to 4,968,192 B, rather than matching exact sizeof.
The two conditional `static PipelineSlot pipeline_work_storage[2]` event arrays
add 13,056 B together; this is static storage, not stack. No new large local array
is introduced. Actual target link/RAM fit remains a separate integration gate.

Focused normal/ASan edit/automation, memory and pipeline PCM/fault checks are
running at this source checkpoint; final results and measured sizes follow.

Rarefaction status/orient/scope and Serena initial/config/symbol checks succeeded
on shared main, including `seq_auto_target` and its event caller. Their fixed root
is `/Users/likwid/Developer/mvave-fm1-firmware`, outside this isolated worktree;
no global project activation/restart was performed. Rarefaction on-open clangd
has no compilation database and missed begin/base callers. Pinned source and
explicit call searches in this worktree remain authoritative.

Aeon online CPUs 0–15 verified; exclusive CPU12–15 assigned by coordinator.
Preapproved lan-compute workflow: Docker `--rm`, `docker-batch.slice`, cpuset12–15,
4 CPUs, 6 GiB memory/swap, project=lunar/session=seq-app-integration-20261101.
Evidence/scripts: ignored local `scratch/seq-app-integration-20261101/` and remote
`/home/likwid/datasets/lunar/seq-app-integration-20261101/`. Reproducible stage and
builds will be removed after recording results; small logs retained. Worktree stays
for coordinator review, then normal removal after integration. No WASM regenerated.
