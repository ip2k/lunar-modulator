# Compact native SAVE compression feasibility — 2026-10-14

## Decision

Do not add compressor support to compact native SAVE to make the proposed
48 KiB logical slots fit the bounded native collector. The source-derived
43,130-byte **full binary container** bound fits the 45,024-byte slot payload
with 1,894 bytes of arithmetic margin. The test corpus and bound do not admit
arbitrary imported files: `FM1_STATE_BIN_MAX` remains 98,304 bytes, and
incompressible input cannot be guaranteed to fit a 45,024-byte payload.
Compression is therefore an optional space optimization, not a safe way to
promise support for every currently accepted import.

The relevant slot geometry is the later tail-page design: 45,056 logical
bytes (11 logical erase blocks), less the 32-byte journal header, gives 45,024
payload bytes. This is a logical candidate only; the storage notes explicitly
do not admit the physical extents or enable SAVE. Do not substitute the older
49,152-byte arithmetic in `2026-10-14-storage48-migration-plan.md`.

## Existing implementation and exact workspace arithmetic

`engines/state/fm1_deflate.c` already supplies deterministic raw DEFLATE with a
4 KiB window and no heap. Its existing one-shot `fm1_deflate` API needs exactly
32,768 bytes of aligned scratch (`FM1_DEFLATE_SCRATCH`) and a caller-owned
output buffer. It has no streaming-encode sink. The compact writer is built
with `FM1_STATE_BIN_COMPACT_WRITER`; its compile-time layout deliberately omits
the normal writer's body, compressed-output buffer and compressor scratch,
and its compact path currently records chunks uncompressed. The pull inflater
and the existing chunk format already provide a reader path for DEFLATED
chunks, with a declared output length and chunk CRC.

The measured compact writer workspace is 39,176 bytes on the host, against a
57,600-byte indexed pixel array. The existing framebuffer lease reserves up
to 15 bytes for 16-byte alignment. A straightforward one-shot per-chunk
compressor would need, in addition to the current writer, 32,768 bytes of
compressor scratch and up to 16,384 bytes of compressed-output staging (the
largest non-SEQS chunk cap). That is 88,328 bytes total on the host, 30,728
over the entire pixel array before alignment. Overlaying the mutually exclusive
`chunk` and `line` buffers saves about 16,384 bytes, but still leaves about
71,944 bytes, 14,344 over the pixel array. These host sizes are planning
arithmetic, not target ABI measurements.

The smallest plausible leased-workspace design is more involved than calling
the existing function: overlay `chunk` and `line`, add the 32,768-byte scratch,
and extend the encoder with a deterministic output-sink/counting interface.
The SAVE preflight pass would count/hash compressed output without writing;
the second pass would rerun the same encoding and stream bytes directly to the
inactive-slot writer. That avoids a 16 KiB output staging array. The resulting
host estimate is 39,176 - 16,384 + 32,768 = 55,560 bytes, leaving only 2,040
bytes (2,025 after worst-case lease alignment) in the 57,600-byte pixel array.
This estimate excludes struct padding changes, encoder callback state, target
ABI differences and any other simultaneous workspace use; it is not a fit
result. A target compile/link and full linked SAVE call-path/stack check are
required before considering implementation.

SEQS is emitted line-by-line and has a 49,152-byte generic chunk cap, so it
cannot simply be buffered as one chunk in this lease. The initial bounded
design should leave SEQS raw and consider only closed non-SEQS chunks, each
capped at 16 KiB. For each candidate chunk, the preflight must select compressed
storage only when it is both smaller and within the slot; otherwise use raw
bytes. It must calculate the exact total before `lunar_project_begin` can erase
the inactive slot, and the second pass must preserve the current deterministic
fingerprint/header comparison and commit-last transaction ordering. If raw and
compressed forms both exceed capacity, refuse before erase and preserve the
old generation. Validate declared uncompressed length against the per-chunk
cap and total format cap before decoding.

## Evidence and limits

- `notes/2026-10-14-collector-total-bound.md` derives 43,130 bytes for the
  complete native collector container, including the 1,316-byte stream
  header/directory reservation and maximum chunk alignment. It is a
  conservative source bound, not proof all independent maxima coexist.
- `notes/2026-10-14-collector-max-validation.md` records an actual 35,176-byte
  dense container and a passing two-slot simulator test with 45,024-byte
  payload capacity. That test does not prove every valid app state reaches the
  bound or inject partial flash mutation.
- `notes/2026-10-14-project-workspace-verification/RESULTS.md` records 39,176
  host bytes for compact writer workspace in a 57,600-byte indexed framebuffer
  and the exclusive lease constraints. Its target compile is not a target
  workspace-size or whole-call-chain measurement.
- `notes/2026-10-13-native-state-codec-budget.md` measures the normal writer at
  284,884 bytes on the target ABI and a reader-only relocatable component at
  15,335 bytes of text/rodata. That reader-only component has no `fm1_deflate`
  compressor symbol. Neither figure gives the link-size delta for adding the
  compressor to the current native image.

No target-link delta for the compressor sink/compact SAVE change has been
measured, so no linker-cost number is claimed. The next meaningful experiment
is a fresh, same-source pi32v2 target link of a narrowly scoped prototype that
adds the sink encoder and buffer overlay, with exact before/after app size,
target writer workspace, main-stack call-chain and RAM/link audits. Keep
storage admission, physical bank ownership, SAVE flash binding, import limits,
hardware behavior and installability false until their separate gates pass.

This note was prepared by direct source/receipt inspection in the current
installable worktree at `63476ba98b2c9fbd7734fb306686eb6b84c6466a`. The shared
semantic services remained selected on the primary checkout, so they were not
retargeted; no production files, hardware, USB, MIDI or flash were changed.
