# Vendored: fm1-x0x's 303 bass and TB-3PO generator (GPL-3.0-only)

**GPL code.** Everything in this folder is built only while the GPL switch
is on (`FM1_GPL_MODS`, `engines/Makefile`; CLAUDE.md, "The GPL switch";
docs/12 §6). While it is on, no firmware image that links JieLi's libraries
may be shared, and the simulator's module is offered under the GPL. The
build with the switch off compiles none of it (`tests/test_gpl_switch.py`).

| | |
| --- | --- |
| Upstream | https://github.com/charlesvestal/fm1-x0x at `80b7d40cc9463653554eaf1eb9c24d47162785b7` (2026-10-05, "USB audio input with a resampler; USB MIDI clock fixed; 512-frame audio halves"): `firmware/src/dsp/{bass303.c, bass303.h, fastmath.h, x0x_param.h}`, `firmware/src/seq/{tb3po.c, tb3po.h, pattern.h}`, `LICENSE`, `LICENSING.md` |
| Also | https://github.com/charlesvestal/schwung-303 at `ccc2f1fed90c9c222644b58789b404126b5c7e15` (v0.3.3, 2026-08-31): `src/dsp/open303/LICENSE`, Open303's MIT licence, as `LICENSE-Open303` |
| What it is | fm1-x0x is open firmware for the M-VAVE FM-1 by **Charles Vestal**, a fork of Felucca (hugelton, kurogedelic). `dsp/bass303.*` is its bass after the TB-303: a C99, float, libm-free port of **Open303** by **Robin Schmidt** (MIT) with the **Devilfish** ranges after **jc303** by **midilab** (GPL-3.0) and a Soft or **RAT** drive after **dm-Rat** by **Dave Mollen** (GPL-3.0), by way of Charles Vestal's **schwung-303**. `seq/tb3po.*` is **TB-3PO**, a generator of 303 lines, ported from Charles Vestal's **schwung-tb3po**, itself a port of the `TB_3PO` applet of the **Phazerville Hemisphere Suite** (**djphazer** and contributors, GPL-3.0). `LICENSING.md` is X0X's own account of where every file came from |
| Licence | `GPL-3.0-only` (every file's SPDX line; `LICENSE` is the GPL version 3 as the FSF publishes it). The Open303 parts of `bass303.c` are MIT (Robin Schmidt; `LICENSE-Open303`) |
| Copied by | `vendor.py` (`--check` compares, with `local.patch` applied) |
| Local changes | Two files, `local.patch` (below). Nothing else is changed |
| Used by | `engines/src/acid_bass.cc` (the sound engine **Acid Bass**, id `acid-bass`) and `engines/midi_fx/acid_gen.c` (the MIDI effect **Acid Gen**, id `acid-gen`), both built through `engines/mk/fm1-x0x.mk` only while the switch is on |
| Not taken | Everything else of fm1-x0x: its 808 and 909 kits (another stage, `notes/2026-10-06-fm1-x0x.md` §6.3), its send effects and master, its sequencer, UI, platform and tools, and its break generator, which ports mestela's schwung-breakbeat by that author's permission to X0X, not to us (the note's §5 drafts a request) |

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

## Sanitizers

UBSan reports `fastmath.h`'s `fm_exp2_nf`, which adds `n << 23` to a float's
bits with n negative for every exponent below 0: the two's-complement shift
GCC documents for signed `<<` and clang computes. It is suppressed for that
header alone in `engines/sanitizers/ubsan.supp`; nothing else in these
files is reported under ASan and UBSan [verified 2026-10-06: Apple clang,
`fm1-acid-oracle --twin` and `--fields`, Acid Gen in front of Acid Bass, and
every parameter at NaN and the infinities].

## Files

| File | sha256 |
| --- | --- |
| `LICENSE` | `3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986` |
| `LICENSE-Open303` | `3e00b890ddf22b209a8bd3aa5916d5a442baf2c02c7a5766465a9232431ecc37` |
| `LICENSING.md` | `30f38e8f96064b956907c87edf0e2585d95d6c9f319363fc29a244b892fd336f` |
| `dsp/bass303.c` (patched; upstream `ace73e02…`) | `77b98574427935c92e9c7ea173f5594002502ef5fe651de9f70e026a25e2d958` |
| `dsp/bass303.h` (patched; upstream `6ace82af…`) | `eb9b49782e09b969b5ed13ae9a28019e8d471e047cfe38bf851d96e269e4588a` |
| `dsp/fastmath.h` | `71d0fb4c242e6c03e435cebacc1e978f928ce2672d6b47a48b68372e72453349` |
| `dsp/x0x_param.h` | `13f31ccc9ff3df95b05405012ada6e83306d25f336cdd078c093d95c04e4430a` |
| `seq/pattern.h` | `83f0e690f8d4f7b005632d60b284b1b983b9dea5d20c0397fb5c459f95fc890c` |
| `seq/tb3po.c` | `fa8abf283ba76681b44fddf7c1f360bcd5f4314446c915db7e828fbbe184b221` |
| `seq/tb3po.h` | `7dd646a572129fc8df5628f6111f68fef6b54476446f75cc5f583b6f110f0073` |
| `local.patch` | `ff68a418ad3bbb05885702f35eba9af3554d62b19cfd4f2ebf36bad76d4c8ae9` |

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
lengths) [verified: `notes/2026-10-06-fm1-x0x.md` §2.6].

## Credits and names

Charles Vestal (fm1-x0x, schwung-303, schwung-tb3po); Robin Schmidt
(Open303); midilab (jc303, the Devilfish extensions); Dave Mollen (dm-Rat);
djphazer and the Phazerville Hemisphere Suite's contributors (`TB_3PO`).
TB-303 is Roland's mark, used only to say what the bass is after; "Acid
Bass" and "Acid Gen" are this project's names (proposed to the owner,
`notes/2026-10-06-fm1-x0x.md` §6.1), and TB-3PO and X0X appear only in
credits.
