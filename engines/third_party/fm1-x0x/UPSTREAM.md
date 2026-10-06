# Vendored: fm1-x0x's 303 bass, TB-3PO generator and 808 kit (GPL-3.0-only)

**GPL code.** Everything in this folder is built only while the GPL switch
is on (`FM1_GPL_MODS`, `engines/Makefile`; CLAUDE.md, "The GPL switch";
docs/12 §6). While it is on, no firmware image that links JieLi's libraries
may be shared, and the simulator's module is offered under the GPL. The
build with the switch off compiles none of it (`tests/test_gpl_switch.py`).

| | |
| --- | --- |
| Upstream | https://github.com/charlesvestal/fm1-x0x at `80b7d40cc9463653554eaf1eb9c24d47162785b7` (2026-10-05, "USB audio input with a resampler; USB MIDI clock fixed; 512-frame audio halves"): `firmware/src/dsp/{bass303.c, bass303.h, fastmath.h, x0x_param.h, drum808.c, drum808.h}`, `firmware/src/seq/{tb3po.c, tb3po.h, pattern.h}`, `LICENSE`, `LICENSING.md` |
| Also | https://github.com/charlesvestal/schwung-303 at `ccc2f1fed90c9c222644b58789b404126b5c7e15` (v0.3.3, 2026-08-31): `src/dsp/open303/LICENSE`, Open303's MIT licence, as `LICENSE-Open303` |
| What it is | fm1-x0x is open firmware for the M-VAVE FM-1 by **Charles Vestal**, a fork of Felucca (hugelton, kurogedelic). `dsp/bass303.*` is its bass after the TB-303: a C99, float, libm-free port of **Open303** by **Robin Schmidt** (MIT) with the **Devilfish** ranges after **jc303** by **midilab** (GPL-3.0) and a Soft or **RAT** drive after **dm-Rat** by **Dave Mollen** (GPL-3.0), by way of Charles Vestal's **schwung-303**. `seq/tb3po.*` is **TB-3PO**, a generator of 303 lines, ported from Charles Vestal's **schwung-tb3po**, itself a port of the `TB_3PO` applet of the **Phazerville Hemisphere Suite** (**djphazer** and contributors, GPL-3.0). `dsp/drum808.*` is its kit after the TR-808: a C99, float, libm-free port, statement for statement, of **8W8** by **athousanddetails** (GPL-3.0), whose fifteen circuit models are built from the TR-808's service notes and the published analyses of **Werner, Abel and Smith** (DAFx-14, the bass drum; ICMC/SMC 2014, the cymbal), and whose rim shot transcribes **sc808** by **Yoshinosuke Horiuchi**, adapted for Sonic Pi by **Sam Aaron** (MIT). `LICENSING.md` is X0X's own account of where every file came from |
| Licence | `GPL-3.0-only` (every file's SPDX line; `LICENSE` is the GPL version 3 as the FSF publishes it). The Open303 parts of `bass303.c` are MIT (Robin Schmidt; `LICENSE-Open303`); the rim shot in `drum808.c` comes from sc808 (MIT, by way of 8W8, GPL-3.0) |
| Copied by | `vendor.py` (`--check` compares, with `local.patch` applied) |
| Local changes | Four files, `local.patch` (below). Nothing else is changed |
| Used by | `engines/src/acid_bass.cc` (the sound engine **Acid Bass**, id `acid-bass`) and `engines/midi_fx/acid_gen.c` (the MIDI effect **Acid Gen**, id `acid-gen`), both built through `engines/mk/fm1-x0x.mk`, and `engines/src/crater_kit.cc` (the sound engine **Crater Kit**, id `crater`), built through `engines/mk/x0x-crater.mk`, all only while the switch is on |
| Not taken | Everything else of fm1-x0x: its 909 kit (another stage, `notes/2026-10-06-fm1-x0x.md` §6.3), its send effects and master, its sequencer, UI, platform and tools, and its break generator, which ports mestela's schwung-breakbeat by that author's permission to X0X, not to us (the note's §5 drafts a request) |

## Local changes (`local.patch`)

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

3. **The 808's silence threshold is a constant.** Upstream's
   `drum808_quiet` is a global that X0X's overload guard raises; here it is
   `static const` at upstream's value (3.2e-5), so no two instances share
   state one of them moves. Nothing here moves it; an overload guard would
   keep it in the instance [verified: the same samples, below].
4. **The 808's pots between the integers.** `drum808_set_value(d, snd,
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

## Sanitizers

UBSan reports `fastmath.h`'s `fm_exp2_nf`, which adds `n << 23` to a float's
bits with n negative for every exponent below 0: the two's-complement shift
GCC documents for signed `<<` and clang computes. It is suppressed for that
header alone in `engines/sanitizers/ubsan.supp`, and so is the same shift in
`drum808.c`'s own `d8_exp2_cr`; nothing else in these
files is reported under ASan and UBSan [verified 2026-10-06: Apple clang,
`fm1-acid-oracle --twin` and `--fields`, Acid Gen in front of Acid Bass, and
every parameter at NaN and the infinities; for the 808, `fm1-crater-oracle
--twin`, `--fields` and `--pads`, and Crater Kit with every parameter at
both ends, NaN and the infinities, bent 48 semitones both ways].

## Files

| File | sha256 |
| --- | --- |
| `LICENSE` | `3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986` |
| `LICENSE-Open303` | `3e00b890ddf22b209a8bd3aa5916d5a442baf2c02c7a5766465a9232431ecc37` |
| `LICENSING.md` | `30f38e8f96064b956907c87edf0e2585d95d6c9f319363fc29a244b892fd336f` |
| `dsp/bass303.c` (patched; upstream `ace73e02…`) | `77b98574427935c92e9c7ea173f5594002502ef5fe651de9f70e026a25e2d958` |
| `dsp/bass303.h` (patched; upstream `6ace82af…`) | `eb9b49782e09b969b5ed13ae9a28019e8d471e047cfe38bf851d96e269e4588a` |
| `dsp/drum808.c` (patched; upstream `c39de770…`) | `a7bfa65c81c00673241f74d574fe97557e91b3d2b9379de2ba69c976e4785e2f` |
| `dsp/drum808.h` (patched; upstream `77534283…`) | `c6d2385344148811f89ca08a4ebd964009faee63e2466df8fa86444c0e607136` |
| `dsp/fastmath.h` | `71d0fb4c242e6c03e435cebacc1e978f928ce2672d6b47a48b68372e72453349` |
| `dsp/x0x_param.h` | `13f31ccc9ff3df95b05405012ada6e83306d25f336cdd078c093d95c04e4430a` |
| `seq/pattern.h` | `83f0e690f8d4f7b005632d60b284b1b983b9dea5d20c0397fb5c459f95fc890c` |
| `seq/tb3po.c` | `fa8abf283ba76681b44fddf7c1f360bcd5f4314446c915db7e828fbbe184b221` |
| `seq/tb3po.h` | `7dd646a572129fc8df5628f6111f68fef6b54476446f75cc5f583b6f110f0073` |
| `local.patch` | `be1496594fd9de8c366a53dab2b07ef2ff685b98244d8ca5c149c4b47221e9d0` |

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
lengths), and the 808 matches 8W8's own engine built from its sources in
double, sound by sound and pot by pot (436 cases, none over 1e-3 of the
reference's RMS, the worst 6.1e-4) [verified: `notes/2026-10-06-fm1-x0x.md`
§2.6]. The last passes with the vendored, patched `drum808.c` too
[verified 2026-10-06: `tests/test_engine_crater_kit.py`, with
`reference/schwung-8W8` at `94aa271`].

## Credits and names

Charles Vestal (fm1-x0x, schwung-303, schwung-tb3po); Robin Schmidt
(Open303); midilab (jc303, the Devilfish extensions); Dave Mollen (dm-Rat);
djphazer and the Phazerville Hemisphere Suite's contributors (`TB_3PO`);
athousanddetails (8W8); Kurt James Werner, Jonathan S. Abel and Julius O.
Smith III (the TR-808 bass drum and cymbal analyses); Yoshinosuke Horiuchi
and Sam Aaron (sc808). TB-303 and TR-808 are Roland's marks, used only to
say what the bass and the kit are after; "Acid Bass", "Acid Gen" and
"Crater Kit" are this project's names (proposed to the owner,
`notes/2026-10-06-fm1-x0x.md` §6.1), and TB-3PO, X0X and 8W8 appear only in
credits.
