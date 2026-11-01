# Combined release corrections validation — 2026-11-01

[verified] Fresh browser build source is `897931cf8025176e387b8fe686613a50215aad83`.
Generated outputs were committed at `a295f588`; no acceptance hashes were hand-edited.
The current strict CI source-record gate passes against both engine and simulator
digests. The module is 1,630,509 bytes, SHA-256
`609d4f4c9344ed210ef8797f02634b3d891d30e5e46e67e2fd9dc0356dd57fca`.
Metadata is unchanged. GPL is enabled, `acid-bass` is present, and DX7 uses trunc12.

[verified] Actual build gates: 108 parity scenarios pass, exact to JavaScript
and musl in all 108, exact to glibc in 105 (the documented libm differences
remain). SysEx 19/19, routing 5/5, all four actual-WASM MIDI runtime groups,
metadata and edit parity pass. The 30-second edit storm processes 10,341 quanta
and 82,728 edits with zero late quanta and zero resynchronizations.

[verified] Browser-state regressions, sequencer UI and compact toolbar pass in
Chromium, Firefox and WebKit. An initial Firefox run lacked CI's PulseAudio
null sink and timed out during startup; that failure log is retained. Firefox
and WebKit pass with the CI audio setup. This is automated browser interaction,
not real-Chrome visual review, hardware audio or owner listening acceptance.

[verified] The first combined build at `951ca6eb` correctly refused four old
multi-sound arrangements after immutable event storage added 6,536 counted
bytes. Four fixture substitutions use Room with unchanged panel/routing
assertions; 29 other scenarios still cover Plate, and an explicit oversized
Plate refusal remains tested. Production RAM limits and guards are unchanged.
See `2026-11-01-seq-panel-parity-budget.md` for measured sizes and compatibility.

[verified] Independent combined source review approved the final source and
the incremental palette, RAM-fixture and JSON-contract corrections. The
reviewer repeated 22 Node checks, two native sequencer checks, 23 palette/gate
checks and 99 codec/schema checks at their respective reviewed heads. These
are distinct focused runs, not a claim of one aggregate test-suite count.

Private logs and exact image/source digests are retained in coordinator
`scratch/release-combined-897931cf/HANDOFF.md` and its sibling logs, mirrored
under the project's bounded Aeon dataset. Reproducible remote source/browser
stages and owned containers were removed. The earlier failed build retains
logs only. Mac free space remains about 1,118 GiB, above the 500 GiB floor.

Remaining gates: required exact-head CI/review and applicable real-Chrome visual
review; corrected aggregate native RAM/stack and general interactive runtime;
physical FM-1 boot, controls, display, audio, persistence/update and owner
listening. No hardware action occurred in this batch and no install/release
admission follows from these source/browser results.
