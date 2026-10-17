# Handoff: Aeon resampler-stage profile pair

Status: completed bounded offline build and artifact audit. No device or hardware validation.

- Worktree/branch: `/Users/likwid/.codex/worktrees/resampler-stage-profile-aeon`, `chore/2026-10-17@resampler-stage-profile-aeon`.
- Source base used by both pair members: `36988d0c2ef1b793e5f9d343fac1b9f6c4b7891f`.
- Documentation/receipt commit: `2f789393f2b5e57f73fbf3a278bd0e79281aec46`; pushed to GitHub `refs/heads/codex/resampler-stage-profile-aeon-20261017`, remote SHA verified identical.
- Earlier driver commits `f68087db` and `eb643ddd` contain wrapper pin/preflight corrections. Two wrapper-only preflight failures occurred before output directories/containers (wrong stage runner pin, then wrong git tree query); final end-to-end preflight resolved both. The final `run_pair.py` is the validated wrapper.
- Aeon task claim was acquired at `/home/claude/.local/share/codex-coordination/claims/lunar--resampler-stage-profile-aeon-20261017-codex` before target builds. Build output root: `/home/claude/mvave-fm1/resampler-stage-profile-pair-aeon-20261017-codex/`.
- Compact local receipt mirrors: `notes/2026-10-17-resampler-stage-profile-aeon/receipts/{schema7-control,schema9-enabled}/{artifact/artifact.json,sections.txt,ram-call-audit.json}`. Details, ELF/app hashes, section sizes/slack, code placement and caveats are in `results.md`.

Both 16-shard catalogue builds and both link stages exited zero under the recorded resource/container policy; no OOM. Both link verifiers report layout passed, hot DSP RAM selected, hardware not admitted/tested and installable false. Pair comparison is profiling-package only: schema 7 disables IRQ and resampler-stage diagnostics; schema 9 enables both and uses schema-9's IRQ-union frame cadence. Do not claim pure resampler-hook overhead. Schema-9 `.ram_dsp` hooks call profile counter/stage helpers in XIP `.text`; profile cost and effect are unmeasured. Stack watermark records sizes but explicitly no worst-case bound; runtime stack is unmeasured.

Next dependency: owner-controlled FM-1 schema-9 diagnostic/run and listening, with explicit allowance for profiling perturbation. To estimate instrumentation-only cost, first create a valid same-cadence comparison that passes app validation. Do not infer speed or sound quality from these builds.
