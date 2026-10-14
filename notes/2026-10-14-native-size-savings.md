# Native all13 size-savings audit — 2026-10-14

Scope: identify linked native flash contributors and feature-preserving savings
for the retained all13 application, with special attention to the 56 KiB gap
between two 100 KiB project slots and the current 144 KiB candidate storage
ledger. No production source, build option, storage geometry or capacity was
changed. No hardware operation was performed.

## Baseline and method

[verified] The retained SAVE-scheduler application reports 863,380 application
bytes, 5,456 bytes below its current expanded application budget, and 2,320
bytes of global arena headroom. Its section sizes are `.text` 0xD27BC,
`.ram_text` 0x468, `.data` 0x70, `.bss` 0x4BE0, `.pool` 0x66AA0 and `.noinit`
0x18. The exact local retained ELF/map/symbol artifacts are under
`build/native-save-scheduler-20261014/save-scheduler-link-v1/`; their source
link receipt is `notes/2026-10-14-save-scheduler-verification/link-receipt.json`.
Hera's corresponding retained ELF is
`/home/claude/mvave-fm1/native-external-arenas-16-20261012/out/save-scheduler-link-v1/save-retained.elf`.
The earlier requested path without `/out/` does not exist.

[verified] `tests/native/size_savings_audit.py` ranks nonzero `.text` ELF
symbols by linked size. Run it from the repo root with no arguments for the
retained SAVE link, or pass another `objdump -t` symbol report. The output is a
ranked attribution aid; a symbol's size is not itself a removable saving.
Largest linked data symbols include Plaits integrated waves (50,688 B),
ride/crash/hat samples (110,549 B combined), compressed Braids waves (24,159 B),
the 9W9 pot table (9,728 B), MSFA sine and exp tables (8,192 B each), and the
MSFA 44,118 Hz frequency table (4,100 B). Large live code includes `apply_op`
(14,230 B), app render/encoder (11,040/11,030 B), and `draw` (10,580 B).
The linker uses `-Oz -flto`, function/data sections and garbage collection;
these are retained symbols in an LTO link, not uncollected object baggage.

## Candidates examined

| Candidate | Evidence | Finding |
| --- | --- | --- |
| Losslessly compress Plaits and Braids wave tables | Sixteen pinned Hera raw-DEFLATE profiles and bounded C-decoder round trips are documented in `notes/2026-10-12-native-engine-link.md` § “Lossless wavetable storage evaluation”. Best reported profile saves 27,024 B including indexes, or 25,583 B after the isolated 1,441 B decoder. | Already smaller than the 56 KiB target. Actual full-app LTO cost, adapter, run-time and storage-format costs were not linked. The direct-pointer users need full-table expansion (83,712 B RAM) or a block-cache/API redesign; current pool headroom is only 2,320 B. Not a drop-in native savings. The all13 link already keeps Plaits tables in flash and stores Braids tables compressed. |
| Compress the 8-bit mu-law 909 cymbal samples | Recorded measurement in `notes/2026-10-12-native-engine-link.md` § “Comet sample storage measurement” used the three existing arrays in `engines/third_party/fm1-x0x/gen/x0x_drum_samples.h` (header SHA in that note), sixteen Hera raw-DEFLATE profiles and decoder round trips. Best profile saves 8,976 B after the isolated 1,441 B decoder; the source says the full experiment receipts are private on Hera. Small 512-byte blocks plus indexes save little and can expand. | This is prior offline experiment evidence, not a fresh local reproduction or a deployable random-access design. It cannot close 56 KiB; expansion needs about 110 KiB RAM, and block decoding/caching has no native implementation or bounded timing proof. |
| Remove duplicate 9W9 exponent curves | Reproduce with `python3 tests/native/size_savings_pot_table.py`. It parses the 19 initializer rows in `engines/third_party/fm1-x0x/gen/x0x_drum_tables.h`, converts decimal literals to IEEE-754 binary32 and compares row bytes. Output: `rows=19`, each `width=128`, `bytes=9728`, `distinct_byte_rows=19`, `exact_dedup_saving=0`. | Exact row deduplication is unavailable. Computing values on control changes could replace the 9,728 B table, but changes implementation behavior and needs target `powf` parity/error, code-size and control-update validation; no savings are claimed. |
| Change MSFA tables or effect/engine DSP | The retained MSFA ROM contributes 20,484 B across sine, exp2 and fixed-rate frequency data. The required 13 engines/effects and their reference-tested outputs depend on these DSP resources. | No lossless duplication or safe replacement was established. Approximate or regenerated tables need audio parity testing and are outside this evidence. |
| Turn off runtime/link retention or compiler features | Receipt shows `-Oz -flto`, section GC, NDEBUG, indexed TFT and existing compressed wavetable mode. Native project collection, validation, save scheduling and sequencer state are retained by explicit link roots. | No provably dead retained feature found from the current map/symbol listing. Dropping SAVE or project handling would violate the active installation goal; disabling LTO/GC is counterproductive. |

The installed project-capacity plan therefore remains blocked on a storage/layout
solution rather than a demonstrated 56 KiB code/data deletion. The retained
application leaves only 5,456 B in its current app budget after reservations.
The current candidate ledger is 144 KiB: VM 64 KiB + USR 72 KiB + 12 KiB gap,
less the 8 KiB settings reservation, plus one 4 KiB app-tail sector available
at this retained link size. Thus two worst-case 100 KiB slots remain 56 KiB
short before migration, ownership, alignment and implementation costs; the
noncontiguous regions still require a scatter-capable transaction design. The
164 KiB figure in earlier layout discussion is historical and relied on a
larger app tail; it is not the current gap calculation. See
`notes/2026-10-13-native-expanded-layout-proposal.md` and
`notes/2026-10-13-native-footprint/RESULTS.md` for prior bounds and safeguards.

## Recommendation and limits

[inferred] Do not pursue changes to sound tables, DSP algorithms, or live engine
coverage as the near-term answer to this gap. The strongest already-measured
lossless compression result misses the target by about 30 KiB before the real
full-link/runtime/RAM costs, and the obvious sample target adds only a small
offline whole-stream number with an unsuitable access model. Next evaluate a
transaction/storage design that preserves two-generation recovery while using
available noncontiguous flash, or revise the physical capacity/layout plan with
an explicit owner-approved maximum project size. Compression of actual project
payloads may improve typical capacity, but cannot promise two worst-case
100 KiB records without an established worst-case bound and raw fallback.

This is an audit, not a release measurement: the retained link reuses verified
baseline objects, is not installable, has no physical storage binding, and has
no watched all13 hardware acceptance. The compression reports are offline
profiles; they do not verify incremental full-app size, playback timing, stack,
or a firmware implementation.
