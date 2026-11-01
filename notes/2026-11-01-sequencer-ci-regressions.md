# Sequencer CI corrections, first independent slice

Personal, non-commercial work; base
`bb9187f393f5c5b48ae782ef31a137928f91c167`, PR 165 / CI run 41302493347.

[verified] GCC 13.3 at `-O2 -Wall -Wextra -Wpedantic -Werror` reproduces
`song_restart_at`'s maybe-uninitialized diagnostic. The caller has validated
the entry count, but the compiler cannot prove that the second decoder call
sets its outputs. Launch now requires successful decoding, as other song
callers do; no arbitrary scene is substituted on failure. The same strict GCC
flags build the sequencer session and host regressions successfully afterward:
17,408 session snapshots pass, and the host test reports `ok:true` (230 events,
59 sink calls, 31 splits).

[verified] The stopped-arp fixture's 26,880-frame key hold cannot contain six
straight 1/16 intervals at 120 BPM / 44,118 Hz (33,088.5 frames). Increasing the
hold exposed a second cutoff: the stopped set script ended at 31,360 frames,
before its sixth interval. The hold is now 44,800 frames, and the set script
runs to 53,760, through the release. The original exact six interval checks
and alternating six-tick swing checks remain. Added checks require zero hung
notes/dropped MIDI effects and an off for every on. No arpeggiator runtime
change was needed.

[verified] The original focused failures reproduce on bounded Linux Clang:
three failures, two passes in 11.50 s. After these independent fixes, the
session/release-audit regressions, stopped swing, playing grid and tempo-change
checks pass: seven tests in 4.34 s. Normal host checks only; no sanitizer,
WASM/firmware rebuild, device, listening or CI acceptance claimed here.

The native oversized-window Capture regression remains failing and is **not**
changed by this slice. The fixture's first Capture grows an empty clip at
step 240 to length 256, giving the window 240..495. Later absolute tick 8,448
needs anchor 352, which `sq_clip_add_raw` rejects at the 256-step bound. Its
old oracle expectation (tick 2,304, step 96) lies outside that offset window
and D11 silences it in native mode. Compatibility preserves the Movy witness.
Transitive capture/playback/persistence/UI bounds must be assessed before any
representation change; removing the native assertion would conceal note loss.

Execution: Aeon CPUs 0–3, at most four CPUs / 6 GiB, existing Linux images in
`docker-batch.slice`, `--rm`, project/session labels. Source is a tracked-base
archive plus exact edited files in the lane-owned
`/home/claude/.local/share/codex-builds/lunar/sequencer-ci-20261101/src`.
Keep small logs in this worktree's ignored `scratch/sequencer-ci/`; remove the
remote staging/build outputs and release the unique claim after the remaining
Capture investigation is handed off. No shared checkout or MCP root changed.
