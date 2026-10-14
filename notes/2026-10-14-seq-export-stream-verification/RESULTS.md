# Sequencer callback export verification — 2026-10-14

[verified] `fm1_seq_export_movy1_stream` uses the existing formatter with a
synchronous fragment sink, without heap allocation or a complete-set buffer.
The caller keeps the sequence unchanged during export. Zero succeeds; a nonzero
sink return latches failure, blocks later sink calls and leaves reported length
zero. Partial sink output must be discarded by the caller's transaction. Export
still traverses the bounded state after failure; it does not promise immediate
traversal cancellation. Existing buffered length/truncation/NUL semantics remain.

[verified] 32 cases in 30 concurrent Hera containers passed ASan/UBSan with
`-Oz -Wall -Wextra -Werror`. Each container also compiled seq_persist.c using
pinned pi32v2 r3/mfprev1 freestanding flags. Fifteen fixture inputs in each of
compat/noncompat mode exercise every callback in rejected, partially consumed
and fully consumed but failed modes. Dense eight-track cases sample first/last
and every 1024th callback. Total: 19,032 injected failures; dense output is
52,760/52,768 bytes across 28,223 callbacks. All check unchanged sequencer bytes,
no further callbacks after error, invalid arguments and original buffer behavior.
This is not exhaustive coverage of every representable sequence or every byte
cut in dense exports. All 30 logs/exits/OOM states and four source hashes checked.

[verified] An independent pre-refactor formatter from commit
b0908137b005ab9bf06cf94a7ff93ae4493e4f38 produced byte-identical buffered output
for the 30 fixture cases. `baseline-parity.json` pins the old source and outputs;
`baseline_probe.c` and `check-baseline.py` reproduce this comparison after staging
the old source and probe at the named /tmp paths. It compared the unchanged
production files staged in source-v2; final fault campaign uses source-v4.

Semantic navigation: Serena located the actual worktree function. Rarefaction
only selected the primary checkout with fallback flags, misrepresented the
unresolved type as `int` and missed known callers; its result was not used as
worktree, ABI or caller-completeness proof. No shared server was switched.

No physical operations, app SAVE integration, application link, allocation,
latency guarantee, migration or recovery claim follows. Next: stream fragments
into bounded project line records, expose a collector without desktop JSON/set
scratch, and resolve native writer workspace and protected storage allocation.
Full all13 hardware acceptance, physical rollback, installer/builder and licensing
remain open. Private full logs: build/native-seq-export-stream-20261014/.
