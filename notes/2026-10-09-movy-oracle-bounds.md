# Movy oracle implicit run-length bounds, 2026-10-09

## Confirmed defect

[verified] The project's own Rust harness computed its default run length as
`(ceil(last_frame / block) + 1) * block` without checking either operation.
Its release profile disables overflow checks to match Movy's engine, so an
unrepresentable default length wrapped and silently excluded the last command.
This confirms the P3 finding in the full-code-audit note's Movy oracle section.

[verified] A release build from main `ebc6690c7595469359336b145cf1d7c0b4fe333a`
replayed this input on aeon, with each supported block size below:

```text
#! block=1
@18446744073709551615 play
```

| Block size | Before: exit | Before: blocks/events | After: exit |
| --- | ---: | --- | ---: |
| 1 | 0 | 0 / 0 | 2 |
| 2 | 0 | 1 / 0 | 2 |
| 128 | 0 | 1 / 0 | 2 |
| 8192 | 0 | 1 / 0 | 2 |

## Narrow correction

[verified] `run_length()` checks addition and multiplication before creating
the replay engines. An unrepresentable default length returns a diagnostic
containing the frame and block size, with no successful summary or event log.
It returns an explicit `end=` directly: the documented ability to exclude
later commands remains intact, and no unused implicit arithmetic is evaluated.

[verified] No vendor source or release-profile setting changed. Movy's
`seq-core` remains pinned at `9190e79a2f461e71d2bf0a9fa77042011945021e` and
was mounted read-only for these builds. This guard protects harness scheduling;
it does not change Movy's algorithm or its overflow semantics.

## Validation and limits

[verified] In a network-disabled `rust:1.98.1-bookworm` container on aeon,
capped at two CPUs and 2 GiB in `docker-batch.slice`:

- `cargo test --locked --offline`: 4 passed.
- `cargo test --release --locked --offline`: 4 passed.
- Release CLI: all four maximum-frame repros exited 2 with the expected
  diagnostic and no event output.
- All 24 curated `.verbs` scripts regenerated successfully; their 24 event
  logs and 24 serialized sets matched the committed fixtures byte for byte.
- The source diff passed whitespace checks.

[verified] Regressions exercise ordinary command-block rounding, the largest
representable implicit length and its first overflowing successor for each
tested block size, `u64::MAX`, early replay refusal, and an explicit zero end
with a maximum-frame command. Huge accepted lengths are checked arithmetically
without replaying them. Representable but impractically long runs are not
capped by this correction; choosing a resource policy is a separate decision.

[verified] Raw build logs, before/after CLI reports and regenerated fixtures
remain in the ignored `scratch/movy-oracle-bounds/` directory and isolated LAN
staging `/home/claude/mvave-fm1/movy-oracle-bounds-20261009`. Rarefaction
oriented the original Rust harness; Serena navigated the isolated Rust driver
after its initially selected C++ project configuration excluded that file.
No hardware was used.

## Main integration check, 2026-10-09

[verified] The branch merged `origin/main` at
`67d5e12dee561abca5d0a2256fec85d75522a806` in merge commit
`b91f6b88f2c1a5249965337711d0d83bd8688e67`. The merge introduces no changes to
`tools/movy-oracle/` or `tests/fixtures/movy/` relative to the feature branch.
On the merged source, both `cargo test --locked --offline` and
`cargo test --release --locked --offline` passed (4 tests each) in the pinned
Rust 1.98.1 container on aeon, with 2 CPUs, 2 GiB memory, 128 process limit,
and networking disabled during the build/test. The ignored Movy dependency was
checked out read-only at the pinned commit above. No fixture regeneration was
needed because the merged main contributes no changes to this oracle or its
fixtures; the 24-script comparison result above remains tied to the original
feature source baseline.
