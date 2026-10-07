# What PR #1 (Echomatter) teaches us (2026-10-06)

[PR #1](https://github.com/ip2k/lunar-modulator/pull/1), "WIP: Decode FM-1
firmware and add reversible local workbench", is Echomatter's draft of
2026-09-14 (47 files, head `ed63278`, branch `codex/firmware-decoding` of
their fork). Its author closed it on 2026-10-05, saying this repository is
the one they will support and offering to coordinate. It was never merged,
and until today nothing here used it. This note records what it knows that
this repository did not, what was checked here, and what changes in our
docs as a result. Credit for every finding below is Echomatter's; the checks
are ours.

The PR's own documents are its docs 13 (decoding) and 16 to 22 (operator
mathematics, the operator's contract, effects decoding and mathematics,
envelope, offline experiments, effects roll-up), on its branch.

## 1. Checked here

All offline, against the stock V15 image (`FM-1_015`) unpacked under
`scratch/` (git-ignored, never committed): `app.bin`, 581,564 bytes, SHA-256
`306e47065f35d7a7a05ada7f5dd092f6e770952054f33f0a86b75fd10ffe3203`, which
is the image the PR names.

- **The two FM tables equal the PR's formulas, every entry** [verified,
  2026-10-06, twice]: 1,024 little-endian u16 each,
  - exponent at file `0x89F8E`: `round((2^(i/1024) − 1) × 4096)`;
  - log-sine at file `0x8A78E`: `round(−log2(sin((i + ½)π/2048)) × 1024)`.
- **The envelope level table at `0x4E8AA` and the six effects callback
  triples at `0x457A4`** are where the PR puts them, and the byte hashes of
  its operator kernel and effects dispatcher match [verified by this
  session's study agent].
- **The decoder agrees with the vendor's disassembly** [verified by the
  study agent]. The PR's pure-Python decoder (`tools/fm1_decode.py`), run
  over AL-255's vendor `objdump` listing, gives the same instruction width
  for all 199,931 entries. 171,131 of them (85.6 %) are forms it decodes,
  and all 4,121 six-byte `80 ff` call targets agree. The rest are mostly
  floating-point forms, which the vendor `objdump` also prints as unknown.

## 2. What it knows that we did not

All [reported: Echomatter, PR #1] unless marked otherwise.

- **The stock operator is not msfa's arithmetic.** V15 works in the log
  domain: per sample, `exp[(~(logsin[phase >> 12] + att)) & 1023] + 4096`,
  shifted right by `att >> 10`, then left by 13. There is no phase
  interpolation. The attenuation is ramped per sample across each 64-sample
  block, in `(target − start + 32) >> 6` steps, with
  `target = 16384 − (level >> 14)`. The ramp keeps its rounding overshoot
  rather than clamping. msfa (and our FM6) multiplies a linear gain with
  `Sin::lookup` instead (`engines/third_party/msfa/fm_op_kernel.cc`). The
  tables are msfa-family; the arithmetic is the FM-1's own. The PR checks
  its model with 19 vectors run through both an instruction interpreter and
  an independent integer model.
- **Stock runs algorithm 4's feedback loop.** Its three-operator kernel at
  file `0x85064` (183 instructions, 544 bytes, copied to RAM `0x01C01124`)
  feeds the third operator's output back to the first. The total shift is
  `min(outer_shift + 2, 16) + 1`. msfa's `FmCore` leaves that loop out
  (`engines/msfa.md`). Whether algorithm 6's loop runs too is only inferred
  (an inlined two-operator path), and AM is still unknown.
- **The stock envelope is Google's `env.cc`:** the same rates and levels,
  the `<< 6` block factor included. The PR matches its reconstruction to 204
  of 208 bytes of V009's helper; the four that differ are relocations. Its
  state has no hold counter [inferred in the PR], so stock, like FM6, moves
  to the next stage at once when a stage's target equals its start. That
  answers FM6's "envelope holds" question for the stock FM-1.
- **V009 and V15 differ in their FM code.** V009's cascade read the wrong
  level fields for operators 2 and 3; V15 fixes that and adds the ramp. So
  "the stock sound" depends on the version.
- **The stock effects are much larger than an 8 KB arena.** Six slots with
  init, update and process callbacks: Filter, Reverb, Delay, Distortion,
  Chorus and Phaser. The PR binds the names from the order of the UI's
  labels [inferred there].

  | Effect | What V15 allocates or computes |
  | --- | --- |
  | Delay | 44 B of state and a 110,294-byte ring of 55,147 int16 samples (about 1.25 s at 44,118 Hz) |
  | Chorus | 44 B of state, an 884-byte buffer, a 220-sample ring (about 5 ms), a 513-cell sine table |
  | Reverb | Constructors of 164, 332 and 276 B (perhaps three types [inferred]). One path has eight delay stages of 59, 227, 419, 617, 137, 313, 509 and 727 samples, and another ring has 10,261 elements |
  | Distortion | 268 B of state. The last stage is about tanh(8v) from a 513-entry table, hard 1.0 for \|v\| ≥ 1, then a gain |
  | Filter | Coefficients start at `[1, 0, 0, 0, 0]` |
  | Phaser | Coefficients from three tanh-table lookups |

  AL-255 reported an 8 KB buffer at engine + 28 that the effects share
  (docs/11 §2). The delay's ring alone is more than 13 times that, so the 8 KB is not
  all of the effects' memory. When they are allocated, whether all six are
  live at once, and from which heap, are not known. The equations and the
  mapping of the user's parameters are open in the PR too.
- **pi32v2 instruction widths.** If the first halfword's high byte is `0xFF`,
  the instruction is 6 bytes; if its top three bits are `111`, 4 bytes;
  otherwise 2. `80 ff` starts a 6-byte call, and an odd low displacement bit
  makes it `gotoss` (83 of them in AL-255's listing). This is more than
  CLAUDE.md's trap 4 said: that ghidra mis-splits these calls.
  - The PR also gives a rule for expanding compact immediates.
  - Paired instructions read their operands before either writes, and the
    pair commits atomically. That rule is inferred from V15's dataflow and
    pair markers, and the PR says so.
- **The memory map, first.** The PR's docs 13 (2026-09-14) place
  `app.bin`'s base at `0x02000120`, read the C runtime's `0xA05C`-byte copy
  to RAM, and treat AL-255's `0xFFC0xxxx` targets accordingly. That is three
  weeks before our `notes/2026-10-05-softkey-efuse.md`, which found the same
  independently and did not know of it.

## 3. Tools

- **`fm1_decode.py` (646 lines, Python standard library): worth adopting.**
  It is a fast, scriptable V15 reader while the vendor `objdump` stays the
  oracle (trap 4). It does not decode about 14 % of the listing, floating
  point included.
- **`fm1_package.py` and `fm1_rebuild.py`:** package parsing, CRC refresh,
  a sealed rollback manifest, and a byte compare outside the patches. They
  overlap our package tooling. They patch in place, at equal size, and
  refuse a changed identity. Our installs would need a version bump and
  `tools/jieli/package_guard.py` instead.
- **`fm1_pi32.py` (the interpreter) and its 19 vectors:** an offline
  cross-check for a log-domain operator model. It cannot settle the timing
  of paired instructions; the AC79 dev kit (docs/14), which has the same
  core, can.
- **Not adopted:** the local workbench (an HTTP server and rtmidi) and its
  SQLite project store. `sim/web` is our interface.
- **Licence.** The PR's files carry no licence header, and it was closed
  unmerged. Its fork carries our MIT `LICENSE`, and its package parsing
  credits kagaimiq's `jl-misctools` (MIT) in `THIRD_PARTY_NOTICES.md`. Until
  Echomatter states the licence, use the facts, offsets, formulas and hashes
  with credit, and copy no code.

## 4. Against our rules

- **No device writes.** The PR's only device traffic is the read-only
  identity query (`F0 00 32 45 00 00 00 40 7F F7`), once, on Echomatter's own
  V15 unit. It has no writer, no soft key and no flash endpoint
  [verified by the study agent].
- **A caution.** `fm1_rebuild.py` makes CRC-valid patched V15 packages that
  keep the identity `FM-1_015`. The stock path installs downgrades, so such a
  package could install on the owner's `FM-1_092` unit. Nothing made with it
  goes near an FM-1 before the dump-and-restore gate (CLAUDE.md, the one
  rule).

## 5. What changed here (this note's PR)

- docs/02 §5: the engine is msfa-lineage in its tables, algorithm table,
  envelope and patch format, not in its operator arithmetic, and stock V15
  runs algorithm 4's loop.
- `engines/msfa.md`: the stock FM-1's loops and envelope holds, from §2.
- `engines/mi-fx.md` and docs/11 §2: the 8 KB arena is not all of the stock
  effects' memory, and the "eight times stock's arena" comparison is
  withdrawn.
- `notes/2026-10-05-softkey-efuse.md`: credits the PR for the memory map.
- docs/04: the PR in the prior art.

## 6. Next

- **A stock-kernel A/B for algorithm 4 (optional).** FM6 against a
  log-domain model written from the formulas above, not from the PR's code,
  rendered offline. Recordings of the stock FM-1 would be needed to judge
  it.
- **A reply to Echomatter** on PR #1, for the owner to post: ask them to state a licence for the tools, and offer a dev-kit test of the
  paired-instruction rule.
