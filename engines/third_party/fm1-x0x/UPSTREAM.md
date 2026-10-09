# Vendored: fm1-x0x's 303 bass, TB-3PO generator, 909 kit and 808 kit (GPL-3.0-only)

**GPL code.** Everything in this folder is built only while the GPL switch
is on (`FM1_GPL_MODS`, `engines/Makefile`; CLAUDE.md, "The GPL switch";
docs/12 §6). While it is on, no firmware image that links JieLi's libraries
may be shared, and the simulator's module is offered under the GPL. The
build with the switch off compiles none of it (`tests/test_gpl_switch.py`).

| | |
| --- | --- |
| Upstream | https://github.com/charlesvestal/fm1-x0x at `80b7d40cc9463653554eaf1eb9c24d47162785b7` (2026-10-05, "USB audio input with a resampler; USB MIDI clock fixed; 512-frame audio halves"): `firmware/src/dsp/{bass303.c, bass303.h, fastmath.h, x0x_param.h, drum909.c, drum909.h, drum909_dsp.h, drum808.c, drum808.h}`, `firmware/src/seq/{tb3po.c, tb3po.h, pattern.h}`, `assets/909/{hh.wav, ride.wav, crash.wav, README.txt}`, `tools/gen_drum_samples.py`, `LICENSE`, `LICENSING.md`; and `gen/{x0x_drum_samples.h, x0x_drum_tables.h}`, written by that script (below) |
| Also | https://github.com/charlesvestal/schwung-303 at `ccc2f1fed90c9c222644b58789b404126b5c7e15` (v0.3.3, 2026-08-31): `src/dsp/open303/LICENSE`, Open303's MIT licence, as `LICENSE-Open303` |
| What it is | fm1-x0x is open firmware for the M-VAVE FM-1 by **Charles Vestal**, a fork of Felucca (hugelton, kurogedelic). `dsp/bass303.*` is its bass after the TB-303: a C99, float, libm-free port of **Open303** by **Robin Schmidt** (MIT) with the **Devilfish** ranges after **jc303** by **midilab** (GPL-3.0) and a Soft or **RAT** drive after **dm-Rat** by **Dave Mollen** (GPL-3.0), by way of Charles Vestal's **schwung-303**. `seq/tb3po.*` is **TB-3PO**, a generator of 303 lines, ported from Charles Vestal's **schwung-tb3po**, itself a port of the `TB_3PO` applet of the **Phazerville Hemisphere Suite** (**djphazer** and contributors, GPL-3.0). `dsp/drum909*` is its kit after the TR-909, ported line for line from **9W9** by **athousanddetails** (GPL-3.0; a 909 for Schwung, https://github.com/athousanddetails/schwung-9W9), which grew out of **ER-99** by **Matthew Cieplak** (GPL-3.0, https://github.com/matthewcieplak/er-99): the kick, snare, toms, rim shot and clap modelled on the 909's circuits, and the hi-hats, crash and ride played from ER-99's recordings (`assets/909/`), which 9W9 ships unchanged. `dsp/drum808.*` is its kit after the TR-808: a C99, float, libm-free port, statement for statement, of **8W8** by **athousanddetails** (GPL-3.0), whose fifteen circuit models are built from the TR-808's service notes and the published analyses of **Werner, Abel and Smith** (DAFx-14, the bass drum; ICMC/SMC 2014, the cymbal), and whose rim shot transcribes **sc808** by **Yoshinosuke Horiuchi**, adapted for Sonic Pi by **Sam Aaron** (MIT). `LICENSING.md` is X0X's own account of where every file came from |
| Licence | `GPL-3.0-only` (every file's SPDX line; `LICENSE` is the GPL version 3 as the FSF publishes it). The Open303 parts of `bass303.c` are MIT (Robin Schmidt; `LICENSE-Open303`); the rim shot in `drum808.c` comes from sc808 (MIT, by way of 8W8, GPL-3.0). The 909's cymbal recordings are GPL-3.0, as ER-99 and 9W9 license them [reported: `assets/909/README.txt`, X0X's `LICENSING.md`]; neither ER-99 nor 9W9 says what they were recorded from (`notes/2026-10-06-fm1-x0x.md` §6.5, R1) |
| Copied by | `vendor.py` (`--check` compares, with `local.patch` applied, and runs the vendored script again for `gen/`) |
| Local changes | Eight files, `local.patch` (below). Nothing else is changed |
| Generated | `gen/x0x_drum_samples.h` (the three recordings as 8-bit µ-law codes, 110,549 B, and their 256-entry int16 decode table; `hh.wav` is 24-bit and rounded to 16 first; local change 7) and `gen/x0x_drum_tables.h` (the tanh table every saturator reads and 9W9's 19 exponential pot curves), written by the vendored, patched `tools/gen_drum_samples.py` and committed so that no build needs Python. Its output was the same, byte for byte, on macOS's Python 3.13 and on Python 3.12 in Alpine (musl) and Debian (glibc) containers [verified 2026-10-06, before local change 7]; the µ-law table is computed in `decimal` arithmetic, without libm, so it should not vary with the platform [inferred]. `tests/test_engine_comet_kit.py` runs the script again and compares; `--int16` writes upstream's int16 arrays (with a guard, local change 7), which the tests measure against |
| Used by | `engines/src/acid_bass.cc` (the sound engine **Acid Bass**, id `acid-bass`), `engines/midi_fx/acid_gen.c` (the MIDI effect **Acid Gen**, id `acid-gen`) and `engines/src/comet_kit.cc` (the sound engine **Comet Kit**, id `comet`), built through `engines/mk/fm1-x0x.mk`, and `engines/src/crater_kit.cc` (the sound engine **Crater Kit**, id `crater`), built through `engines/mk/x0x-crater.mk`, all only while the switch is on |
| Not taken | Everything else of fm1-x0x: its send effects, delay and master (`dsp/fxbus*`, `dsp/master*`: our inserts and master effects do that job), its sequencer, UI, platform and other tools, and its break generator, which ports mestela's schwung-breakbeat by that author's permission to X0X, not to us (the note's §5 drafts a request). `seq/pattern.h`, X0X's own pattern model, which `tb3po.h` includes for its 303 step type, also declares the break part's settings (a struct and the names of its twelve settings, `brkpart_t`); it holds no code of the generator, and nothing here reads that struct [verified 2026-10-06: `grep` of `engines/`, `sim/web/src`] |

## Local changes (`local.patch`)

Each of the eight files opens, under its SPDX line, with a notice that it
was modified for Lunar Modulator on 2026-10-06 and where the changes are
listed (the GPL version 3, section 5(a)); inside, every change is marked
"Lunar Modulator". What they are:

1. **The rate is the instance's.** Upstream fixes 44,100 Hz (`BASS303_SR`).
   `bass303_t` gains a last field, `sr`, which `bass303_init_rate(b, sr)`
   sets, and `bass303.c` reads `b->sr` wherever upstream reads
   `BASS303_SR` (every such place has the instance in scope).
   `bass303_init(b)` is `bass303_init_rate(b, 44100.0f)`. At 44.1 kHz the
   arithmetic is upstream's, operation for operation, so the samples are
   too [verified: `tests/test_engine_acid_bass.py`, against fm1-x0x's own
   file when `reference/fm1-x0x` is cloned]. Our hosts run at 44,118 Hz
   (the FM-1) or whatever a browser gives; X0X's own resampling to its
   device is not ours (study, R4: a 44.1 kHz bass at 44,118 Hz would be 0.7
   cents sharp, and 1.5 semitones at 48 kHz).
2. **Pots between the integers.** `bass303_set_value(b, i, x)` is upstream's
   `bass303_set` with the pot a float, so a continuous control moves
   smoothly rather than in 1/127ths; `bass303_set(b, i, v)` clamps and
   calls it with `(float)v`, computing every value it computed before.

3. **The 909's rate is the instance's.** Upstream fixes 44,100 Hz
   (`D9_SR`, `D9_MS`, `D9_PHASE_PER_HZ` in `drum909_dsp.h`). `drum909_t`
   gains a last field, `rate` (a `d9_rate_t`: the rate, samples a
   millisecond and phase steps a hertz), which `drum909_init_rate(d, sr)`
   sets; `drum909_init(d)` is `drum909_init_rate(d, 44100.0f)`. In
   `drum909.c` every function that reads the rate has the instance's
   `rate` in scope as `rt` (the static ones take it as a last argument),
   and `D9_SR`, `D9_MS`, `d9_biquad_set` and `d9_inc` read it; the header
   gains `d9_biquad_set_sr` and `d9_inc_pph`, which take the rate, and
   keeps upstream's two as those at `D9_SR`. The cymbals stay 44.1 kHz
   recordings: a sampler's step is its pitch times 44,100 / the rate, so
   they keep their pitch and length at any rate. At 44.1 kHz `rt` holds
   upstream's three constants to the bit (2^32 / 44,100 in float is
   upstream's literal), so the arithmetic is upstream's, operation for
   operation [verified: `tests/test_engine_comet_kit.py` builds
   `engines/test/drum909_drive.c` against fm1-x0x's own file and ours,
   four passes of every voice, the same 7 MB of samples, both reading the
   int16 cymbals (local change 7)].
4. **9W9's pots between the integers.** `drum909_set_value(d, voice, i,
   x)` is `drum909_set` with the pot a float: a LIN pot is read at x / 127
   of its range, an EXP pot linearly between its table's two neighbours, a
   switch at the nearest position, so a knob moves smoothly rather than in
   1/127ths; for an integer x it applies what `drum909_set` applies.
5. **The 808's silence threshold is a constant.** Upstream's
   `drum808_quiet` is a global that X0X's overload guard raises; here it is
   `static const` at upstream's value (3.2e-5), so no two instances share
   state one of them moves. Nothing here moves it; an overload guard would
   keep it in the instance [verified: the same samples, below].
6. **The 808's pots between the integers.** `drum808_set_value(d, snd,
   slot, x)` sets sound `snd`'s pot `slot` (8W8's `D8S_*` and `D8P_*`) as
   a float, whatever the track switches say: a new last field of
   `drum808_t`, `potx`, keeps the float pots, which `drum808_trigger`
   reads where upstream reads the integers (`pot[]`, as `x / 127`, and the
   snare's piecewise tone), and `pot_value` takes the pot as a float.
   `drum808_set`'s integer pots go through the same path (`set_pot` is
   `set_potf` at `(float)v`), so they compute every value they computed
   before. Tune's x may lie past the pot's ends, 12 semitones either way
   about pot 64: far on the toms and congas, whose own law spans 2
   semitones either way, and half a pot past the top elsewhere; within that
   every tuned path clamps or stays in range (the rim shot's filters below
   Nyquist, its 0.32 pulse increment under 2^32). Crater Kit uses it so a
   continuous control does not move in 1/127ths, and to tune the toms an
   octave either way.
7. **The 909's cymbals are 8-bit µ-law** (owner's decision, 2026-10-06;
   `tools/gen_drum_samples.py`, `dsp/drum909.h`, `dsp/drum909.c`). The
   script writes each recording as one byte a sample, a sign bit and 7 bits
   of the companded magnitude (µ = 255): code `(s << 7) | q` decodes to
   −/+ round(32768 (256^(q/127) − 1) / 255), capped at 32,767, and each
   sample takes the code whose decoded value is nearest. The header carries
   the 256 decoded values as `x0x_mulaw_dec` (512 B), and the 909 reads a
   cymbal sample as `x0x_mulaw_dec[code]` where upstream reads the int16
   (`D9_SMP` in `drum909.c`; `d9_smp_t.buf` points at codes,
   `d9_smp_code_t`); every operation after it is upstream's. That halves
   the cymbals' flash, 221,098 B to 110,549 B + 512 B. `--int16` writes
   upstream's int16 arrays, and a build with `-DX0X_SMP_INT16` reads them
   as upstream does; each header refuses the other build (`#error`), so the
   two cannot be mixed silently. What it costs the sound is measured in
   `engines/README.md`, "Comet Kit": 37.8–38.0 dB of SNR against the int16
   recordings, and 38.5–44 dB under each hit in the kit's output
   [verified: `tests/test_engine_comet_kit.py`].

The wrapper (`engines/src/comet_kit.cc`, MIT) also sets one float of the
unit's state: the kick's pitch-sweep offset `bd_df`, which decays
geometrically for as long as the kick sounds and turns subnormal after
about 1.2 s (the only float of the state that does [verified:
`fm1-comet-oracle --state`]), is set to 0 once it is under 1e-20 Hz, where
adding it to the kick's base (21 Hz or more) no longer changes a bit. The
output is the unit's, sample for sample (`fm1-comet-oracle --twin`).

**Attribution in upstream's own files.** `assets/909/README.txt` calls 9W9
Charles Vestal's; 9W9's repository, its commit history and X0X's
`LICENSING.md` give it to athousanddetails [verified 2026-10-06:
`reference/schwung-9W9` at `10cbe5c`: of its 105 commits, all but nine
are athousanddetails', eight a release bot's and one Charles Vestal's]. We credit athousanddetails; the
vendored README is left as upstream wrote it.

## Sanitizers

UBSan reports `fastmath.h`'s `fm_exp2_nf`, which adds `n << 23` to a float's
bits with n negative for every exponent below 0: the two's-complement shift
GCC documents for signed `<<` and clang computes. It is suppressed for that
header alone in `engines/sanitizers/ubsan.supp`, and so is the same shift in
`drum808.c`'s own `d8_exp2_cr`; nothing else in these
files is reported under ASan and UBSan [verified 2026-10-06: Apple clang,
`fm1-acid-oracle --twin` and `--fields`, Acid Gen in front of Acid Bass, and
every parameter at NaN and the infinities; for the 909, Apple clang 21,
`fm1-comet-oracle --twin` (blocks of 7 at 44,118 Hz, of 64 at 48 kHz),
`--fields` and `--state`, and all sixteen pads struck with every knob of
every pad at 0, 0.5, 1, NaN and the infinities, from memory filled with
0xA5, at blocks of 7]; for the 808, `fm1-crater-oracle
--twin`, `--fields` and `--pads`, and Crater Kit with every parameter at
both ends, NaN and the infinities, bent 48 semitones both ways].

## Files

| File | sha256 |
| --- | --- |
| `LICENSE` | `3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986` |
| `LICENSE-Open303` | `3e00b890ddf22b209a8bd3aa5916d5a442baf2c02c7a5766465a9232431ecc37` |
| `LICENSING.md` | `30f38e8f96064b956907c87edf0e2585d95d6c9f319363fc29a244b892fd336f` |
| `dsp/bass303.c` (patched; upstream `ace73e02…`) | `a2ed702bacaab05d57705e4096189947f3c7261b366ee5172d8caa307a2bde21` |
| `dsp/bass303.h` (patched; upstream `6ace82af…`) | `b15035bb6558594c3ff80fb46ad2de26cc3f71c25ed1d8247c1556ace035f5b3` |
| `dsp/drum909.c` (patched; upstream `80d619c2…`) | `a4ceedd0c1c6aa53037ae540c98022a15aef721abbea75f3f661b1c20d8b6b8d` |
| `dsp/drum909.h` (patched; upstream `39d79c84…`) | `f41e4da7b0fb7afa4dbfe59d366b96cb5258b941e21b02e5113940053d4c7902` |
| `dsp/drum909_dsp.h` (patched; upstream `b9a2e498…`) | `dd4a16d645dc53c588954a8810cae4b098c74c7540222b0eb5945306ba0fe422` |
| `dsp/drum808.c` (patched; upstream `c39de770…`) | `322275d389b532ee5dacf7da4c39bcc77b6cdb34247f2c9e07813ad453267ff4` |
| `dsp/drum808.h` (patched; upstream `77534283…`) | `e138870d0495aa3039feb6e9e345fc916b26866110dfef084a1b712b1f7965af` |
| `dsp/fastmath.h` | `71d0fb4c242e6c03e435cebacc1e978f928ce2672d6b47a48b68372e72453349` |
| `dsp/x0x_param.h` | `13f31ccc9ff3df95b05405012ada6e83306d25f336cdd078c093d95c04e4430a` |
| `seq/pattern.h` | `83f0e690f8d4f7b005632d60b284b1b983b9dea5d20c0397fb5c459f95fc890c` |
| `seq/tb3po.c` | `fa8abf283ba76681b44fddf7c1f360bcd5f4314446c915db7e828fbbe184b221` |
| `seq/tb3po.h` | `7dd646a572129fc8df5628f6111f68fef6b54476446f75cc5f583b6f110f0073` |
| `tools/gen_drum_samples.py` (patched; upstream `3e18ed28…`) | `78c0cc810c085d7e6d005558e9c10d2d8955c5acaf09f95343adc9bf4975fb45` |
| `assets/909/README.txt` | `cf2cb2a5858587489ddf67802117d456cad42b26fad11cc1ec35ddf8af9ed36c` |
| `assets/909/hh.wav` | `8ae963e80b8604bf23733545117d3b115767aa48ecd3013ad5d91506337d289a` |
| `assets/909/ride.wav` | `f1d1cee24a7c91bb2ca9c6eb97badad3841226897ad0daabfc35801371d78182` |
| `assets/909/crash.wav` | `4a1b8d8828f9e530e9ae7f1a3cdffbcb1466e633a2b0607b3aac914699bc8400` |
| `gen/x0x_drum_samples.h` (generated) | `3e3d1c1661d605cf8a6b85db7601f1a2159c81d72925251d2deaf4e23dee9f9e` |
| `gen/x0x_drum_tables.h` (generated) | `5998fade81059c9c5d74494fa4fdc0c739371df0065bd4d316182ba2f27b6684` |
| `local.patch` | `54c870b6cb69ffaa388faf6546e1a8e477a488f95a3735fd5dcb2e994e6939e1` |

Re-vendoring:

```bash
git clone https://github.com/charlesvestal/fm1-x0x reference/fm1-x0x
git clone https://github.com/charlesvestal/schwung-303 reference/schwung-303
python3 engines/third_party/fm1-x0x/vendor.py reference/fm1-x0x reference/schwung-303 --check
```

Upstream moves fast (62 commits of its own from 2026-10-03 to 2026-10-05):
re-pin by commit, run `--check` against the new commit, and re-run the
tests before taking anything newer.

## What upstream's own tests showed (the study, 2026-10-06)

fm1-x0x's `tests/run_tests.sh`, run against the upstream checkouts beside
it: the 303 matches Open303 (envelopes within 0.3 dB, the alias floor
within 1 dB of the reference at 1x, 2x and 4x), and TB-3PO matches
schwung-tb3po step for step (31,920 of 31,920 steps over 396 seeds and 4
lengths), the 909 matches 9W9's own engine ("PASS: 0 failure(s)"; its
demo pattern within 3.9e-4, −68.8 dB), and the 808 matches 8W8's own engine built from its sources in
double, sound by sound and pot by pot (436 cases, none over 1e-3 of the
reference's RMS, the worst 6.1e-4) [verified: `notes/2026-10-06-fm1-x0x.md`
§2.6]. The last passes with the vendored, patched `drum808.c` too
[verified 2026-10-06: `tests/test_engine_crater_kit.py`, with
`reference/schwung-8W8` at `94aa271`].

## Credits and names

Charles Vestal (fm1-x0x, schwung-303, schwung-tb3po); Robin Schmidt
(Open303); midilab (jc303, the Devilfish extensions); Dave Mollen (dm-Rat);
djphazer and the Phazerville Hemisphere Suite's contributors (`TB_3PO`);
athousanddetails (9W9, 8W8); Matthew Cieplak (ER-99, and its cymbal
recordings); Kurt James Werner, Jonathan S. Abel and Julius O. Smith III
(the TR-808 bass drum and cymbal analyses); Yoshinosuke Horiuchi and Sam
Aaron (sc808). TB-303, TR-909 and TR-808 are Roland's marks, used only to
say what the bass and the kits are after; "Acid Bass", "Acid Gen", "Comet
Kit" and "Crater Kit" are this project's names (proposed to the owner,
`notes/2026-10-06-fm1-x0x.md` §6.1), and TB-3PO, X0X, 9W9, ER-99 and 8W8
appear only in credits.

## Audit correction (2026-10-08)

`dsp/fastmath.h` and `dsp/drum808.c` scale exponent bits using unsigned
32-bit addition and shifting. This defines the intended modulo bit operation
for negative exponents instead of relying on signed-left-shift undefined
behavior. Their previous UBSan shift exemptions are removed. Audio parity
verification is recorded in the audit remediation note.
