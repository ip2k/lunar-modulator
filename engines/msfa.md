# FM6: six-operator FM on msfa (engine id `dx7`)

FM6 is a polyphonic six-operator FM engine that plays DX7 voice data. Its
synthesis is **msfa**, the FM core of Google's
[music-synthesizer-for-android](https://github.com/google/music-synthesizer-for-android)
(Raph Levien for Google, Apache-2.0), vendored byte-identical in
`third_party/msfa/` ([UPSTREAM.md](third_party/msfa/UPSTREAM.md)). msfa is
the core the stock FM-1 runs: its 32-row algorithm table sits in every
stock `app.bin` [verified: docs/02 §5], and it equals Google's table row for
row, rows 4 and 6 included [verified: `tools/check_msfa_table.py`'s V13
and V14 finds against `third_party/msfa/fm_core.cc`, below].

**Borrowed, with thanks.** The engine is Google's msfa, and its name is
Felucca's: FM6 is the FM engine of hugelton's Felucca, whose Apache-2.0
`fm6_core.c` (Leo Kuroshita's port of msfa as Dexed carries it) is this
engine's test oracle (below). The owner kept the name on 2026-10-06, "since
we're borrowing it"; the engine id `dx7` is internal.

DX7 is a Yamaha trademark. FM6 reads the voice format; it is not affiliated
with or endorsed by Yamaha.

| | |
| --- | --- |
| Source | `src/msfa_dx7.cc` (the engine), `src/dx7_voice.cc` (voice data, SysEx), `src/dx7_loop.cc` (algorithms 4 and 6), `src/msfa_prelude.h`, `src/msfa.h`, `src/msfa_unit.cc` (how msfa is compiled), `src/msfa_tables.cc` and `src/msfa_rom.cc` (msfa's tables as const data, the second made by `tools/msfa_tables.py`), `src/dx7_bank.h` (the built-in voices, made by `tools/dx7_bank.py`), `include/fm1_dx7.h` (the SysEx import) |
| Build | `mk/msfa.mk` |
| Tests | `tests/test_engines_dx7.py`; the generic engine tests list it like the others |
| Oracle | `fm1-dx7-oracle` (`test/dx7_oracle.cc`, `test/dx7_felucca.c`) with Felucca's `fm6_core.c` (`third_party/felucca-fm6/`, Apache-2.0); and msfa's own table init (`test/msfa_ref.cc`) |
| Voices | 12 |
| Instance | 15,848 bytes at 44,118 Hz, on 64-bit, 32-bit and pi32v2 alike; 19,948 at any other rate (below) |
| Shared RAM | none but a few words: msfa's tables are const data, flash on the FM-1 (below) |

## Playing it

| Page | Knob | Range, default | What it does |
| --- | --- | --- | --- |
| 1 | Patch | 32 built-in voices, then User 1–32; TINE EP | The voice the next notes play (read at note-on: sounding notes keep theirs). User slots hold what was loaded from SysEx, the keyboards' INIT VOICE until then |
| 1 | Brightness | 0–1, 0.5 | The output level of every operator that is not a carrier, −24 to +24 dB (0.5: as programmed). A modulator's level is its modulation index, so this is the voice's brightness; carriers, and so the loudness, are untouched |
| 1 | Env Time | 0–1, 0.5 | Every envelope's speed, 8 times faster at 0 to 8 times slower at 1 (2^(6 × (0.5 − value))), the pitch envelope's too: attacks, decays and releases together |
| 1 | Feedback | −7 to +7, 0 | Added to the voice's feedback (0–7), rounded |
| 2 | Volume | 0–1, 0.7 | The voice's gain |

- **All four macros are continuous** (API v2 SMOOTH and MOD): a change
  while notes sound ramps over two 64-sample blocks at 44,118 Hz (2.9 ms),
  and each voice can take its own offset (POLY, `set_param_note`), as can
  its pitch. Patch is LATCH and MOD, as Six-Op FM's.
- **Brightness is exact:** +12 dB renders the same bytes, while the key is
  held, as the voice with 16 more output-level steps on its modulators
  [verified: tests/test_engines_dx7.py]. Feedback +2 on a voice with
  feedback 3 renders as the voice with feedback 5.
- **Env Time runs the envelopes on a clock**, not by editing rates: each
  64-sample block the voice's envelopes take as many of msfa's envelope
  steps as the clock owes (8 at most at 0, one every 8 blocks at 1). At
  0.5 that is one step a block, msfa's own pace, and a change applies while
  the note sounds. A note's first block always takes a step, so at any
  setting the attack starts, and the pitch envelope stands at its start
  level, from the note's first sample (until 2026-10-05's review, at 1 a
  note started up to 7 blocks, 10 ms, late and at its unbent pitch).
- **Voices:** 12. A key played again retriggers its own voice; a new key
  takes a free voice, else the oldest released one, else the oldest held.
  A released voice ends once, for 50 ms, every carrier's envelope has been
  under msfa's threshold (where `FmCore` skips an operator) with a release
  that ends there too. It is the envelope that is read, not the output: a
  tremolo's trough can mute a voice for longer than that while its release
  still has its course to run [verified: tests/test_engines_dx7.py; until
  2026-10-05's review the output was read, and a deep tremolo cut such
  releases off]. A voice whose release ends above silence (the DX7's L4
  above 0 on a carrier) sounds until it is stolen, as on the keyboard.
- **Pitch bend** is the host's, in semitones; the voice data's own bend
  range is not read (it is a function parameter, not voice data).

## The voices

### Built in

32 voices of our own (`tools/dx7_bank.py`, MIT), written from textbook FM
recipes: Chowning's brass and bells, 1:1 and 2:1 stacks, a 14:1 tine,
drawbar ratios on algorithm 32, a pitch-envelope kick, feedback noise for
the snare and hats. `python3 tools/dx7_bank.py --syx bank.syx` writes them
as a 32-voice dump that loads on other DX7-compatible synthesizers;
`--list` lists them with their algorithm and the idea behind each.

| | Voices |
| --- | --- |
| Keys | TINE EP, BARK EP, CLAV, HARPSI, KOTO |
| Mallets and bells | MARIMBA, VIBES, TUBE BELL, GLASS BELL, CHIMES, STEEL DRUM |
| Organs | ORGAN 1, ORGAN PERC, ROCK ORGAN |
| Brass and winds | BRASS, SOFT BRASS, FLUTE, CLARINET |
| Strings and pads | STRINGS, WARM PAD, GLASS PAD, SWEEP |
| Basses | FM BASS, PLUCK BASS, SAW BASS |
| Leads | SAW LEAD, SQUARE LD, SYNC LEAD |
| Drums | KICK, SNARE, HI-HAT |
| Reference | PURE SINE (one operator: the tests' tuning reference) |

Why not the factory voices: Yamaha's ROM cartridges carry no licence to
redistribute, and the three banks Six-Op FM plays ("as distributed with
Plaits") have no stated origin and share names with factory voices
(plaits-heavy.md, "The patch data"), so they are not reused here. Any of
them can be loaded into the user slots from a file the user has.

The voices were designed by numbers, not by ear: each was rendered and its
level, envelope and harmonic profile checked (single notes peak at −9 to
−17 dBFS; the tests check every voice at three velocities for finite
output, no clipping before the limiter, and that every voice has ended 7 s
after its release). They want a listening pass (open questions).

### From SysEx: the user slots

`include/fm1_dx7.h` is the engine-side import. A host hands
`fm1_dx7_load_sysex` the bytes of a `.syx` file (or reads one without an
instance with `fm1_dx7_read_sysex`, and gives an instance a voice with
`fm1_dx7_set_user_voice`, as the simulator does):

- **A single voice (VCED):** `F0 43 0n 00 01 1B`, 155 data bytes, a
  checksum, `F7` (163 bytes). It goes to the slot asked for, the next one
  to the slot after, wrapping at 32.
- **A bank (VMEM):** `F0 43 0n 09 20 00`, 4,096 data bytes (32 voices of
  128 packed bytes), a checksum, `F7` (4,104 bytes). It fills User 1–32;
  msfa's `UnpackPatch` unpacks each voice.
- **Raw bank data:** a file of exactly 4,096 bytes with no SysEx framing.
- A file may hold several dumps; anything else between them is skipped and
  counted. A wrong checksum is counted and the voice stored all the same,
  as the keyboards' editors do (many published files have one). Every
  value is clamped to its range and names to printable ASCII, so any bytes
  are safe to load; a message cut short or broken by another status byte
  is skipped.
- The result says what was skipped and why, for a host's message: other
  SysEx (another maker's, another format), messages cut short, voice or
  bank dumps of the wrong length (a header with another byte count or
  length), bytes outside any message, and raw bank data.
- Sounding notes keep the voice they started with.

On the desktop, `fm1-render --engine dx7 --sysex FILE.syx` loads files
before the first block (single voices into User 1, 2... in order, across
files) and prints what each held:

```bash
engines/build/fm1-render --engine dx7 --sysex mybank.syx --param Patch=40 \
    --note 0:60:100:1 --seconds 2 --out user9.wav
# stderr: sysex mybank.syx: 32 voices from User 1, 0 bad checksums, 0 skipped: "..." ...
```

In the browser simulator, **Load DX7 patches…** (or a file dropped on the
page) reads a `.syx` file in the browser and hands its bytes to the
firmware (`fm1w_dx7_load`, sim/web/README.md); nothing is uploaded. The
app keeps FM6's user bank, the voices the FM-1 would keep in flash: every
FM6 sound gets them when it is created and when a file loads, FM6's Patch
list shows their names in place of "User N", and the current sound then
plays the first voice loaded (it becomes FM6 if it was not). The page
names what was wrong with a file that loaded nothing, and flags wrong
checksums. Files up to 64 KiB [verified: tests/test_sim_web.py natively,
test/sysex.mjs on the module, the page in headless Chromium,
2026-10-06].

## What is msfa's and what is ours

**msfa's, unmodified:** the envelope generator (`Env`), pitch envelope
(`PitchEnv`), LFO (`Lfo`), the 32 algorithms and single-operator feedback
(`FmCore`, `FmOpKernel`, integer kernels), the sine, exponential and
frequency lookups (`Sin`, `Exp2`, `Freqlut`) and their tables' values, made
ahead of time as msfa's init makes them ("Tables in flash" below), the
note set-up in
`dx7note.cc` (`ScaleLevel`, `ScaleRate`, `ScaleVelocity`, `osc_freq`) and
`UnpackPatch`. msfa's `Dx7Note` class is compiled but not used: the engine
builds each voice from the same parts, in the order `Dx7Note::init` and
`::compute` use them, which leaves room for what follows.

**Ours, on top:**

- **The voice's transpose** (24 = none) is applied to the key; msfa's
  Android synth ignores it.
- **Amplitude modulation.** `Dx7Note::compute` applies the LFO to pitch
  only, so msfa never reads AMD or AMS. FM6 attenuates each operator with
  AMS above 0 in the envelope's log domain, as Yamaha's FM chips apply AM
  [inferred]: by AMD (0–99, scaled as msfa scales PMD, × 165 / 64) times
  how far the LFO is from its top, times the sensitivity's depth. Depths:
  AMS 3, 16 doublings (96 dB, about the YM2151's 95.6 dB at its AMS 3
  [reported: its datasheet]); AMS 1 and 2, Dexed's ratios 0.259 and 0.427
  of that (4,342,338 and 7,171,437 of 2^24, Dexed's `ampmodsenstab`, as
  Felucca's `fm6_core.c` carries it [reported]). So AMD 99 at AMS 1 dips
  24.8 dB and at AMS 2 41.0 dB [verified: tests/test_engines_dx7.py,
  square LFO]. No measurement of a DX7's AM depths was available here.
- **The feedback loops of algorithms 4 and 6.** The DX7 feeds the fourth
  operator back to the sixth in algorithm 4, and the fifth back to the
  sixth in 6. msfa's table marks those loops (`FB_IN` on the sixth,
  `FB_OUT` on the fourth or fifth) but `FmCore::compute` only runs an
  operator fed back to itself ("todo: more than one op in a feedback
  loop"), so msfa, and with it the stock FM-1 if its `FmCore` is msfa's
  [inferred], plays those two algorithms with no feedback at all. FM6 runs
  the loop's operators sample by sample as a chain (`src/dx7_loop.cc`),
  the last one's output fed back to the first exactly as msfa feeds an
  operator to itself (the mean of its last two outputs, shifted by
  8 − feedback + 1), and the rest of the algorithm through `FmCore`. A
  chain of one operator with feedback is msfa's `compute_fb` to the bit,
  and the chains without feedback are `FmCore`'s algorithms 4 and 6 to the
  bit, on 3,000 random blocks [verified: `fm1-dx7-oracle --loop-check`].
  Feedback 0 on those algorithms runs `FmCore` alone, as msfa.
- **The macros, per-note offsets, SMOOTH, voice allocation and release**
  (above).
- **A retriggered or stolen voice keeps its phases and its last gains**, so
  its first block glides from where it was; msfa's `Dx7Note::init` zeroes
  them, a click. A voice that was silent starts at phase 0, as msfa.

**How msfa is built** (third_party/msfa/UPSTREAM.md has the reasons): each
vendored `.cc` is its own translation unit inside `namespace fm1_msfa`
(`src/msfa_unit.cc`), so its classes and globals cannot collide with
anything else in the firmware; its `synth.h` is replaced by
`src/msfa_prelude.h`, because it switches the operators to float NEON
kernels on any aarch64 machine (this desktop included) and would make the
desktop's output differ from the browser's and the FM-1's; and the
vendored-code flags (`-w -fwrapv`) apply, msfa's phases being `int32_t`
that wrap by design.

### Rate

msfa runs at the host's rate, in its own 64-sample blocks: the envelopes
and the LFO step once a block, and the engine renders blocks as the host's
calls need them, so the output is the same at any host block size and note
and parameter events land on the next 64-sample block [verified: the
generic block-size and SMOOTH tests]. `Freqlut`, `Lfo` and `PitchEnv` take
the rate in their `init`. `Env` does not: it counts blocks, with rates set
for 44.1 kHz, so the engine clocks it by 44,118 / rate. That is exactly one
step a block at the FM-1's 44,118 Hz, msfa as it runs there (0.04 % faster
than at 44.1 kHz), and the same envelope times at any other rate: a decay
falls at the same dB per second at 22,050 Hz [verified:
tests/test_engines_dx7.py].

The engine runs from 16,385 Hz to 384,000 Hz and refuses other rates.
The floor is msfa's: `Freqlut::init` fills an `int32_t` table up to
2^45 / rate, the top of an octave, which no longer fits at 16,384 Hz and
below, so the pitches in each octave's last few percent come out wrong (a
1,023 Hz operator plays far off at 16,000 Hz) [verified:
tests/test_engines_dx7.py; until 2026-10-05's review the floor was
8,000 Hz].

msfa keeps its rate units (`Lfo`'s and `PitchEnv`'s) in globals. The
engine sets them in its first create and never again; a later create at
another rate is refused (create returns NULL), as the Schwung shim refuses
one. One rate per process is what the FM-1, the simulator and `fm1-render`
have. Its tables are const data, and at a rate other than 44,118 Hz the
frequency table is the instance's own (below).

**No libm while rendering**, and the tables come out exact:

- msfa's `Sin::init`, `Exp2::init` and `Freqlut::init` take one libm value
  each (`cos` and `sin` of 2π/1024, `exp2` and `pow` of 2^(1/1024)), which
  every compiler here folds at compile time, then integer steps or
  repeated multiplication in doubles. Since 2026-10-06 none of them runs:
  `tools/msfa_tables.py` takes the same steps from correctly rounded values
  (Python's `Decimal`) and writes the tables as const data
  (`src/msfa_rom.cc`), and the oracle compares them with msfa's own init,
  word for word (below). At another rate than 44,118 Hz the instance fills
  its frequency table with `FillFreqLut` (`src/msfa_tables.cc`):
  `Freqlut::init`'s doubles and steps, with a truncation where it called
  `floor`, so no libm at all.
- `osc_freq` takes a `log` (a software double on pi32v2) for each
  operator's fine frequency. The engine calls it for each voice of the bank
  and each user slot when the instance is made or a dump is loaded, and
  keeps the six results (the operator's pitch less the key's), so a note-on
  adds integers. The test checks `osc_freq`'s 100 fine values against
  correctly rounded ones.
- The browser's parity scenarios (sim/web/test/scenarios.json, `dx7-*`)
  render the same bytes in WebAssembly as with glibc and musl.

### Output level

A carrier at full level and velocity is ±2^25 in msfa's units; the engine
scales a voice by its Volume (Q16), sums the voices in integers and scales
the sum so that one such carrier is 0.25 at Volume 1. A single note of the
built-in voices peaks at −9 to −16 dBFS at the default Volume, near the
other engines; chords go to the host's bus limiter.

## Differences from a DX7, from Dexed and from the stock FM-1

Known, not exhaustive:

- **Envelope holds.** When a stage's target equals the level it starts
  from, a DX7 still takes the stage's time; Dexed's msfa adds that
  (`ACCURATE_ENVELOPE`), Google's moves to the next stage at once. FM6 runs
  Google's: a voice with L1 = L2 decays sooner than on a DX7 [reported:
  Dexed, via Felucca's port].
- **LFO speeds** follow msfa's formula; Dexed replaced it with a table of
  rates in hertz [reported: the table in Felucca's generator, which names
  Dexed's `lfo.cc` as its source].
- **Detune** is msfa's 12,606 per step at every key; Dexed scales it by key.
- **Fixed-frequency operators** move with the pitch envelope, the LFO's
  vibrato, the bend and a per-note pitch offset, as msfa's
  `Dx7Note::compute` moves every operator. Felucca's port of Dexed's msfa
  moves a fixed operator with none of them [verified: `fm6_core.c`'s note
  compute; Dexed itself not checked], and which a DX7 does was not
  checked here. It matters on voices such as HI-HAT, whose fixed operators
  bend with the rest.
- **Keyboard level scaling** groups keys as `offset / 3`; Dexed rounds the
  other way, `(offset + 1) / 3` (within 0.4 dB on the oracle's voices).
- **Not there:** the mod wheel, breath, foot and aftertouch routings to
  pitch and amplitude modulation and to EG bias; portamento; mono mode;
  operator on/off; the sustain pedal (the engine API has no controllers
  yet). The function data (bend range and these routings) is not voice
  data and is not read.
- **The stock FM-1** runs msfa with Google's algorithm table, rows 4 and 6
  included (`0x41`: the loop marked, not run by msfa's `FmCore`)
  [verified: the table; docs/02 §5 had called those rows a Dexed-family
  change, which they are not: Felucca's port of Dexed's msfa has `0xC1`
  there; Dexed itself not checked]. Whether stock adds AM or the loops in
  its own code is not known.

## Checks

### The oracle: Felucca's port of the same core

Felucca 1.0 (hugelton) runs its FM6 engine on `fm6_core.c`, an integer C
port of msfa as Dexed carries it, by Leo Kuroshita; that file is Apache-2.0
while the rest of Felucca is GPL-3.0-only. It is vendored as a test oracle
only (`third_party/felucca-fm6/`, the owner's decision of 2026-10-05) and
built into `fm1-dx7-oracle`, never into an engine. `test/dx7_felucca.c`
computes the tables it expects (Felucca generates them with a GPL tool not
used here) from the definitions in its comments and in msfa, and plays a
note as a keyboard would. Two tables are set to Google's msfa, which FM6
runs, rather than to Dexed's: the detune step and the LFO speeds. The
oracle then differs from FM6 in its 1,024-point Q15 sine, 32-sample blocks,
Dexed's envelope holds and level-scaling rounding, and its algorithm table's
rows 4 and 6.

Results [verified: tests/test_engines_dx7.py, 2026-10-05; SNR over the
whole one-second render, envelope over 10 ms windows within 60 dB of the
loudest]:

| What | Agreement |
| --- | --- |
| All 32 algorithms, every operator sounding at mixed ratios and levels, feedback 0 and 5 | SNR 28–40 dB, envelope within 0.3 dB (test: 25 dB and 0.6 dB) |
| Algorithms 4 and 6 with feedback | envelope within 0.3 dB; FM6's loop against Felucca's sixth operator fed back to itself |
| Fixed frequencies and detune at both ends, feedback 7 with transpose, velocity sensitivity 7 with rate and level scaling on both sides of the break point, at C2, C4 and C6 | SNR 13–55 dB, envelope within 0.45 dB (level scaling's rounding at the top of the keyboard) |
| Pitch envelope, LFO pitch modulation, LFO delay (C2, C4, C6) | envelope within 0.7 dB; the waveforms drift apart in phase, the pitch moving every 64 samples here and every 32 there |

**A Felucca quirk found on the way:** its port of Dexed's AM computes the
factor `pt` 2^14 too large, in 32 bits, so it wraps, and an operator with
AMS above 0 plays at the top of its range whatever AMD is [verified: a
render of a voice with AMS 1 or 3 at AMD 0, 1 and 30, 2026-10-05]. No
oracle test uses AMS. A candidate upstream report, for the owner to decide
on.

### The rest (tests/test_engines_dx7.py)

- The vendored msfa files against the hashes in UPSTREAM.md (and against
  git, when `reference/msfa` is there); `fm6_core.c` the same; the bank
  header against `tools/dx7_bank.py`; the engine's carrier table against
  msfa's algorithm table.
- msfa's tables, made by `tools/msfa_tables.py` from correctly rounded
  values, against the file the engine builds and against msfa's own init
  (above, "Tables in flash"); an instance's own frequency table at 44,100
  and 48,000 Hz, and its 4,100 bytes in the instance's size.
- Tuning at four keys within 0.5 cent; transpose; a fixed frequency on any
  key; the six carriers of algorithm 32 at 6 dB steps (8 output-level
  steps each, within 0.15 dB).
- Envelope decay in dB per second against msfa's rate formula, at
  44,118 Hz and 22,050 Hz (2 % and 3 %); Env Time's factor of 8, 1/8 and
  2^1.5 (4 %); the pitch envelope's glide time; the LFO's speed (2 %) and
  delay; AM depth at AMS 1 and 2 (0.1 dB); velocity sensitivity 7, 127
  against 40, 25.2 dB (0.15 dB).
- Brightness, Feedback and Volume as above.
- SysEx: a voice as VCED and inside a bank render the same bytes; the
  built-in bank exported and read back renders as the built-in voices,
  byte for byte; several dumps, a bad checksum and a foreign message in one
  file; raw bank data; broken dumps refused; a bank of 0x7F bytes (every
  value out of range) clamped and finite at the keyboard's ends with a
  +48 bend.
- Every built-in voice at three velocities; twelve voices and a steal;
  retrigger and release; instance size and time per block against Macro's.
- The generic tests (instance memory, any parameter value, host block
  sizes, SMOOTH at any split, per-note offsets) list `dx7` like the other
  engines.

## Cost and memory

**Instance:** 15,848 bytes at 44,118 Hz on this 64-bit desktop, on
pi32v2, i386 and x86-64 alike: it holds no pointers [verified:
`fm1-render`'s `instance_bytes`; JieLi's compile check, 2026-10-06; 15,844
before the flag below]. Twelve voices of msfa
state (six envelopes, a pitch envelope, six operators' parameters, our
clocks and per-note offsets: 664 bytes each), the 32 user voices (4,992
bytes, unpacked), the operators' pitches of all 64 slots (1,536 bytes, so
that a note-on needs no `log`), one unpacked built-in voice, msfa's two
64-sample buses, the output block and a flag saying whether a frequency
table follows. At any other rate one does: 4,100 bytes more, 19,948 in all
[verified: tests/test_engines_dx7.py at 44,100 and 48,000 Hz].

### Tables in flash

msfa fills three tables in RAM at start-up, and `exp2.cc` defines a fourth
that nothing here reads. Until 2026-10-06 they were globals, 28,688 bytes
of the FM-1's RAM outside every instance [verified: JieLi's compile check,
`.bss` of `tp/msfa/*.o`, 2026-10-05], which the simulator's RAM meter did
not count. Since then (the owner's decision, 2026-10-06):

| msfa's table | Bytes | Now |
| --- | ---: | --- |
| `sintab` (1,024 points with their deltas) | 8,192 | const data: `kSinTab` |
| `exp2tab` (likewise) | 8,192 | const data: `kExp2Tab` |
| `lut` (`Freqlut`, 1,025 points) | 4,100 | const data at 44,118 Hz (`kFreqLut44118`); at another rate, in the instance |
| `tanhtab` (defined by `exp2.cc`, filled by nothing here) | 8,192 | gone: `exp2.cc` is not compiled |

So at the FM-1's rate FM6 keeps 28,688 bytes less in RAM, and 20,484 more
bytes of const data sit in flash. What is left in RAM besides the
instances is 24 bytes on pi32v2: msfa's `.bss` is 12 (`fm1_freqlut` and
the rate units of `Lfo` and `PitchEnv`), `msfa_tables.o`'s `.data` 8 (the
two table pointers, constant initialised: no start-up code) and the
engine's own rate 4 [verified: JieLi's compile check, 2026-10-06, all four
profiles; `msfa_rom.o` is 20,484 bytes of read-only data and nothing else,
and no msfa table is among the largest static RAM symbols any more].

How, with msfa's files unmodified (`src/msfa_prelude.h`):

- msfa declares `extern int32_t sintab[2048]` (and `exp2tab`) in its
  headers and reads them in its inline `Sin::lookup` and `Exp2::lookup`;
  `freqlut.cc` defines `int32_t lut[1025]` and reads it in
  `Freqlut::lookup`. The prelude makes each name a macro for a pointer's
  target, `#define sintab (*fm1_sintab)`, before msfa's code is read: the
  headers then declare a pointer to the table, the lookups read through it,
  and the rest of msfa's code is as it was. A const declaration would have
  needed msfa's headers edited; defining const tables against msfa's
  non-const declarations is a type mismatch C++ does not allow across
  files, though linkers accept it.
- `src/msfa_tables.cc` points `fm1_sintab` and `fm1_exp2tab` at the const
  tables, as constant initialisation (no start-up code; the `const_cast`
  only matches msfa's declared type, and nothing writes through them).
- `freqlut.cc` is still compiled, for `Freqlut::lookup`; its `lut` becomes
  the pointer `fm1_freqlut`, which the engine sets before each block to the
  const 44,118 Hz table or to its instance's own. An instance's own table
  lives after it in the host's memory (`InstanceSize` adds it at any rate
  but 44,118 Hz), so the RAM meter counts it, and it is filled at create
  with `FillFreqLut`. It is set per block, not once, because the pointer is
  global and an instance can be destroyed (on the control task) while
  another plays; all instances share one rate, so their tables are equal.
- `sin.cc` and `exp2.cc` are not compiled into the engine: they only
  define and fill the tables (`Sin::compute` and `compute10` are used by
  nothing but `#if 0` code in `fm_op_kernel.cc`). The oracle builds them,
  as upstream does, to compare.

Checks [verified, 2026-10-06]:

- `fm1-dx7-oracle --tables-vs-msfa` links upstream's `sin.cc`, `exp2.cc`
  and `freqlut.cc` as they are (in their own namespace, the macros off) and
  runs their init: the const sine and exp2 tables and the 44,118 Hz
  frequency table equal msfa's, word for word, and `FillFreqLut` equals
  `Freqlut::init` at 381 rates from 16,385 to 384,000 Hz (390,525 words), as
  does the table an instance reads at 44,118, 44,100, 16,385 and 384,000 Hz
  (tests/test_engines_dx7.py).
- The output is unchanged: 268 renders with the build before and after,
  byte for byte the same: the three `dx7-*` parity scenarios at 44,118,
  44,100, 48,000 and 22,050 Hz, and every Patch value (the 32 built-in
  voices, and the built-in bank loaded into the 32 user slots) with Env
  Time, Brightness, Feedback and a bend moved, a chord and a high note, at
  44,118, 16,385, 44,100 and 96,000 Hz.
- No measurable cost: twelve voices of PURE SINE, ORGAN 1, TINE EP, BRASS,
  STRINGS and SAW LEAD took between 7 % less and 0.1 % more time than
  before (best of five 5-second renders, this desktop), which is noise:
  the pointer's load is hoisted out of the operator loop.
- The table could live in RAM again without touching msfa: a firmware that
  finds the sine table too slow in flash (docs/11 §2 reports stock copying
  msfa's hot code to SRAM) can copy it there and repoint `fm1_sintab`.

Code and const data on pi32v2 at `-O2` (`.text` and `.rodata`): about
14 KB for the engine, its 32 built-in voices 5.5 KB of it, 5.6 KB for
msfa, and the tables' 20 KB [verified: JieLi's compile check, 2026-10-06;
msfa was 8 KB with `sin.cc` and `exp2.cc`]. `FillFreqLut` uses software
doubles and no libm; the libm calls left are `log` in `osc_freq` (at
create and when voices load) and `floor` in `Freqlut::init` and
`Dx7Note::init`, which nothing calls [verified: the same check's symbol
list].

**Time per 64-sample block on this desktop** (Apple M1 Max, twelve voices
sounding, best of three 5-second renders; share of the 1.451 ms block)
[verified: `fm1-render`'s `ns_per_block`, 2026-10-05]:

| | ns per block | Share |
| --- | ---: | ---: |
| FM6, PURE SINE (one operator) | 1,377 | 0.09 % |
| FM6, ORGAN 1 (six carriers) | 5,225 | 0.36 % |
| FM6, TINE EP, BRASS, STRINGS, SAW LEAD | 8,248–9,222 | 0.57–0.64 % |
| FM6, algorithm 6 / 4 with feedback (the loop) | 13,346 / 16,617 | 0.92 / 1.15 % |
| FM6, one voice of BRASS | 812 | 0.06 % |
| Macro, 12 voices (two models) | 25,520–26,976 | 1.76–1.86 % |
| Six-Op FM, 8 voices | 14,648 | 1.01 % |

FM6 with twelve voices costs about a third of Macro's twelve here. It is
integer arithmetic with 64-bit products (two per operator sample); pi32v2
does those in several instructions, and stage B measures it. The stock
FM-1 runs twelve msfa voices on its second core [inferred: docs/01]; the
loop algorithms are the dearest case here.

## Open questions

- **A listening pass over the 32 built-in voices** (designed by numbers).
- **Envelope holds** (`ACCURATE_ENVELOPE`): adding them means an envelope
  of our own instead of msfa's `Env`, or a check of whether the stock FM-1
  has them first.
- **AM depths** are a design (above), not a measurement of a DX7.
- **The user bank on the FM-1:** the simulator's bank lasts until power
  off. On the FM-1 it would live in a flash partition, which waits for the
  dump-and-restore gate (CLAUDE.md, the one rule) and a SysEx path over
  USB-MIDI.
- **Controllers:** the mod wheel and aftertouch routings, sustain and
  portamento need the engine API to carry controllers first.
- **Felucca's AM quirk:** a candidate upstream report (above).
