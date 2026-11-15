# Native playing Capture: prevent unrepresentable windows

Personal, non-commercial; independent follow-up to `dab713da80ce7ae09fff4001c50a5a58252a0dfa`
on corrections base `bb9187f393f5c5b48ae782ef31a137928f91c167`.

[verified] The CI deep-playhead fixture first creates a clip at start 240,
length 256 (window 240..495). That first Capture already drops pitches 62
and 63 at anchors 256 and 260; the later native Capture needs anchor 352
and drops pitch 72. No refusal was counted. Export/reload changes the window
to start 240, length 16. `sequence-model.js` rejects both that oversized
window and note anchors past 255; the panel navigates only bars 0..15.
Wrapping anchor 352 to 96 cannot fix playback alone: D11 silences anchor 96
outside the window; quantization and swing also use the literal anchor.
An injected-anchor probe confirms `fire=65535` for anchor 96 with tick 2304
or 8448, but `fire=8448` for anchor 352. The existing nine-bit note anchor
can physically hold 352, but widening the supported format would also need
persistence, commands, locks/trigs and both editors. No such change is made.

The owner-approved scope preserves growth for representable clips. Native
playing Capture now checks the whole take before any clip creation, used-bit
pairing, note write or transport change. An anchor beyond 255 or a fresh
window past step 255 refuses the take, increments `stats.refused` once, and
keeps the entire captured history, generation and dirty state. No prefix is
committed and no arbitrary clamp is added. Existing growth arithmetic within
capacity is unchanged; compatibility retains the original raw-2304/96 oracle
witness and its partial-take/oversized-window behavior. Stopped Capture is
unchanged. The 46,080-master-tick packing fixture also exposes an old silent
28-of-33-note truncation; native now explicitly retains/refuses that whole
take while compatibility retains its five-note oracle prefix.

[verified] A new strict C regression fails against the prior core on its
first refused-commit assertion. After the fix it checks full arena identity
apart from the single refusal counter, first/later invalid candidates with
and without existing notes, repeated refusals, retained-history recovery,
FIFO gates, valid growth and saved-state roundtrip, plus both compatibility
modes. The original valid offset-loop and growth tests remain.
Linux Clang normal/checking Capture checks pass: 44 tests, 127 deselected,
8.92 s. The focused C regression also passes under ASan/UBSan with leak
detection and halt-on-error enabled.

[verified] Aeon GCC 13.3 `-O2 -fstack-usage` reports `sq_capture_commit` at
160 bytes, dynamic/bounded, both before and after. The preflight adds no
array, heap allocation or state field. It uses two bounded FIFO scans per
fresh note, O(N²) in the existing ring length. For the full default 256-event
ring, all same-pitch note-ons, 2,000 valid and 2,000 refused preflights average
89.8 and 89.4 microseconds; observed maxima 211.7 and 152.1 microseconds.
These host measurements are not pi32v2 stack, code-generation or deadline
acceptance. Custom larger ring sizes retain quadratic cost.

[verified] Independent review found that a held note can remain in the ring
without a new push until `UINT32_MAX`; the initial preflight's endpoint/bar
rounding could wrap and admit it. The follow-up bounds phase, offset and gate
against the exact available bar end before addition. Regressions reproduce
that failure at phases 0 and 383 and compare the full arena on refusal.
The exact maximum fresh window (tick 0 through 6,144) still captures to 256
steps and roundtrips; tick 6,145 refuses without mutation. Compatibility
arithmetic is unchanged. The focused C probe now covers 12 cases.

Observability seam (reported to coordinator before any app/UI edits): app
command return values and browser text API return admission/bytes consumed,
not semantic edit success. Native render telemetry already exposes
`seq_refused`. Panel sync sees the unchanged `capture_gen`, restores pending
history/REC LED and says “Nothing to capture”, never “Captured”; that wording
needs a refusal toast for unchanged generation with remaining history. The
browser's 61-word transport mirror currently carries no refusal counter.

Small logs/probe sources: this worktree's ignored `scratch/sequencer-ci/`.
LAN containers use CPUs 0–3, four CPUs / 6 GiB, `docker-batch.slice`, `--rm`
and unique labels. Keep the isolated worktree for integration; remove the
owned remote reproducible staging and release both claims after handoff.
No firmware/WASM rebuild, device, browser, listening or target timing proof.
