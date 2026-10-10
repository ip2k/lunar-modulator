# Sequential engine integration handoff

All build evidence below is offline. Parent owns main merges. No hardware
traffic or change to the owner's localhost8778 listening server is authorized
by this work. Browser and offline scheduler acceptance gates remain unchanged.

The three branches below incorporate main
`67d5e12dee561abca5d0a2256fec85d75522a806`. Their final generated Wasm and
records come from actual combined builds on bounded LAN containers; both
source hashes were checked against each committed record. Initial CI on these
heads was queued when this handoff was written; this is not CI pass evidence.

| Stream | Tested source checkpoint | Focused pytest | Wasm parity | Screens / layout faults |
| --- | --- | --- | --- | --- |
| Warble, PR123 | `abac01cafe90c99b446fd0ff890d0d102932dd7f` | 42 pass | 105 pass | 4632 / 0 |
| A/B restore, PR128 | `1c09c5a229dd8c4ec4dd9e725f9c7bdb27f889c5` | 13 pass | 104 pass | 4621 / 0 |
| Compare MID, PR113 | `b43960680760092bf1eb13ad2371b2039326abd9` | 32 pass | 104 pass | 4621 / 0 |

[verified: build reports] All three builds also pass metadata, 18 DX7 checks,
native edit checks and zero edit audio delta. Each measured 30-second offline
storm has zero late quanta/resyncs. Warble's seven native effect checks pass.
Compare's native kind checker has 1,245,985 checks and zero failures, including
bidirectional hysteresis timestamps 12/28 and 20/28; its intended golden
trace is retained. Detailed receipts and evidence boundaries are in the
individual Warble, A/B and Compare notes and `notes/data/` JSON files.

The first branch with all required exact-head checks green may be proposed
to parent for merge. After that engine merge, integrate the then-current main
into the next branch using a merge, review source conflicts separately,
rebuild combined generated artifacts on LAN, run focused validation, commit
and push with remote SHA verification, then wait for that new head's CI.
Continue sequentially with the third branch. Do not select an older generated
binary as the final conflict resolution or repeat independent baseline builds
while the first merge remains pending. A preceding trace-only merge should
be checked for actual source-hash impact before deciding it needs a rebuild.

Demos depend on these integrations and the final generated registry. They
must not start from a mixture of individually tested branch artifacts. Final
combined build evidence, rather than earlier branch passes, must describe
the actual integrated source.

The original owner native Safari listening failure remains unresolved:
"Sound 2 A had a few small crackles when i switched to it" at localhost8778,
root `35c37940`, First orbit at 116 playing. There is no measured owner capture
or passing Safari listening retest. A/B's deterministic native regression
proves the narrowly corrected same-engine restore behavior; it does not
establish universal click-free switching or overturn that listening receipt.

Rarefaction's root remains the original checkout and lacks a compilation
database; it was useful for orientation but is not exact-branch verification.
Serena was activated on each worktree and returned relevant exact source
bodies. File inspection and tests establish the behavior claims.

Recovery: each stream's worktree is under the corresponding
`~/.codex/worktrees/{warble-effect,ab-sound-switch-crackle,compare-midi-pulses}`
directory. Final LAN sources are under
`/home/claude/mvave-fm1/{warble-current-main-20261009,ab-main-integrated-20261009,compare-main-integrated-20261009}/src`.
Containers use `docker-batch.slice`, four CPUs and 8 GiB memory. Local raw
logs are `/tmp/lunar-{warble-current-main,ab-main,compare-main}-{build,pytest}.log`;
compact evidence is committed, so those temporary logs are supplementary.
