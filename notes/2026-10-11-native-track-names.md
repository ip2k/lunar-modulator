# Native track names

Implemented on `feature/2026-10-11@native-track-names`, source commit
`2c64e695fbc45e9e61be438ee91af2bfebabd5e3` (pushed and remote SHA checked).
Root integration, rebuilt Wasm parity and the project's CI gates remain pending.

Track titles are native sequencer state: at most 16 printable ASCII bytes,
including significant spaces; empty restores the numbered display. The C
getter/setter and strict editor model reject invalid lengths and characters
without truncation. Optional `tn <zero-based track> <hex ASCII>` lines follow
`tk` in `.lunar`/Movy text. The existing raw-item binary project codec carries
these lines. Legacy imports clear titles; compatibility mode ignores `tn` and
omits titles on export. Scene metadata is unchanged. [verified: focused C and
JavaScript regressions] Movy's pinned loader at `9190e79`,
`engine/crates/seq-core/src/persist.rs:235`, ignores unknown verbs. [verified:
source inspection]

Arrangement, Scenes, Clip, Automation and Mixer display titles, as do track
selectors. Header fields edit on double click, Enter or F2; Enter/blur saves
and Escape cancels. Explicit Rename buttons support touch. Numeric track
identity remains in ARIA labels. The shared editable-name helper validates
before returning the input to read-only state and waits until a pointer click
has dispatched before blur saves can disable/redraw its destination. Touch
compatibility mouse events are included. [verified: independent mock-host
Playwright desktop and 844×390 landscape regression]

The desktop C layout is 256 bytes per track (+16), 32,072 bytes per eight-track
instance (+128), and 184 bytes per streaming importer (+24). The fixed 32,768
byte instance arena remains unchanged. Instance plus event pool (3,264), pending
command (240), UI allowance (1,024) and click state (20) totals **36,620 of
36,864 bytes**, leaving **244 bytes**. Tests assert this budget and guard the
arena with a canary. Four-track instances measure 18,184 bytes; no-capture
instances measure 15,112 and 29,000 bytes for four and eight tracks.
[verified: host `sizeof`, `fm1-seq --sizes` and memory-contract tests; the JieLi
ABI has not been verified]

Checks passed:

- Focused native C API, invalid-input immutability, chunked text import,
  legacy/compatibility import, binary codec and arena/budget tests; the same
  executable under AddressSanitizer and UndefinedBehaviorSanitizer.
- Twelve JavaScript model/host tests; two existing memory contracts; three
  existing Movy fixture import/export round trips.
- Full mock-host sequencer UI suite, including held mouse click, touch tap,
  Enter/F2/Escape/blur, invalid and host-refused rename rollback, names across
  views, selectors, and restoring numbered defaults. Named Scenes/Mixer
  screenshots inspected with no label collisions.
- Native UI test source syntax check and `git diff --check`.

Durable local evidence is in `scratch/native-track-names/HANDOFF.md`,
`scratch/native-track-names/ui/results.json` and the adjacent screenshots.
The harness used the existing Chromium headless shell, without operating an
owner tab. Rebuilt Wasm/native-browser integration, full DSP/CI, hardware and
listening acceptance were not performed by this subtask.

Rarefaction status/orient and Serena instructions/config/symbol queries were
checked against the primary checkout. Shared semantic services were not
switched or restarted while the parent used them; this worktree was inspected
through files and lightweight local tests. The primary C index lacks a full
compile database, so semantic results do not establish device ABI correctness.

Integration must reconcile `sequencer.js` with the parent's scene helper and
the piano-roll/transport streams, retain the helper's pointer/touch ordering
fix, and run the extended native UI suite after a LAN Wasm rebuild. Additional
transport state must respect the 244-byte remaining ancillary budget. No PR or
merge was created by this subtask.
