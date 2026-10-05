# Vendored msfa (Google's music-synthesizer-for-android)

| | |
| --- | --- |
| Upstream | https://github.com/google/music-synthesizer-for-android at `f67d41d313b7dc85f6fb99e79e515cc9d208cfff` (2017-09-12, the repository's last commit), files from `app/src/main/jni/` |
| Author | Raph Levien, for Google; copyright Google Inc. (2012-2013) |
| Licence | Apache-2.0. Every vendored `.h`/`.cc` carries Google's Apache-2.0 header [verified: grep, 2026-10-05]; `LICENSE` is upstream's `COPYING`, the licence text. Upstream has no NOTICE file |
| Copied by | `vendor.py`, which reads the files below from the pinned commit with `git show` (`--check` compares) |
| Local changes | **None.** Files are byte-identical to upstream (the hashes below; `tests/test_engines_dx7.py` checks them). Our code is in `engines/src/` |
| Used by | the FM6 engine, `engines/src/msfa_dx7.cc` (engine id `dx7`); `engines/msfa.md` |

The files and their sha256:

| File | sha256 |
| --- | --- |
| `LICENSE` | `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30` |
| `aligned_buf.h` | `97c267c756088e18fe0a8a5c7d59df3ab5cf967337c7f7d0f90155ba7ea4e366` |
| `controllers.h` | `68bf695b3b3176bf618a919f840093909a89325c57057c73bf8eee5fc8ae61b9` |
| `dx7note.h` | `addd7dd53ec902a66442f0bcd0e5b69c2381037cd85a1dc659c1045dd677f8f7` |
| `env.h` | `8eb661f6c5e4798b0a50f7a81d6493fb8419e1cf9966fbe7911c541b5a277603` |
| `exp2.h` | `23aa480e221e5d1f928a5ccab654a9c01a80eb0b610fd66d9364af09d18cdda8` |
| `fm_core.h` | `8b44690d4965cffe82f71dd12125b7d3b63fb59556c4cac0472cc984cd29a1ea` |
| `fm_op_kernel.h` | `62bfcbbccf445504dd195a6beb05179b9e03235e8e4b19e661b761ddc0e80603` |
| `freqlut.h` | `d319ee2d35e8e8e2c860b6fc2a2d1382bf5782d1d147264914325ca41f89f00b` |
| `lfo.h` | `f88ba2fbd63626483c7a028537a0434aec3b7a159fee154efc0451f8b784dba2` |
| `patch.h` | `2ddf975db873de9071adcec6bf8539a38f98e35e5f2b220045cff658e489b020` |
| `pitchenv.h` | `5701a2dcaf13e1ba7141cfc605ba6163ddffd73a91a0362d31b18a4f99fcd72d` |
| `sin.h` | `77486d3ac19d53514a8d26cd2164374ceceab9b15f8d98f876d4db7647321cc2` |
| `synth.h` | `96f1881020f67e12e3d8ac5d79fc546cab9407605d5274d58ba3b4576b8aaf73` |
| `dx7note.cc` | `bcd52b05c6d316f413088b6ff31486c491abd9ad4a114d0f3309bb555b8fdf24` |
| `env.cc` | `83bf4debc5ea480466892ccf572adcc27b55ee2ac3c21979485e6fa73e5b9ccc` |
| `exp2.cc` | `fe7dc02d600fcaf198ca32b10edfb28ff695d107b401c3fa92a7ac73d2e9096f` |
| `fm_core.cc` | `5039002970c22183944aa9719b3342231ceee441244b8a7dfdf039d2fafaa07d` |
| `fm_op_kernel.cc` | `e91aa1e067bf67c799871344eb1f3cdd92c2c0e4797b2efc2403ac7bb7113af5` |
| `freqlut.cc` | `f46ddab0d296f1a82d2ef6826f7e431cad97967418a37fdb486052a4187dcaf8` |
| `lfo.cc` | `47a34fc38eab4cfc46376732a6ddfd24631b8ef27a67ec4177300a264e5ff867` |
| `patch.cc` | `b4a70d7812052dc52621c2d80f480dcc17b6ff0044cc6e215caae88df41d07b7` |
| `pitchenv.cc` | `da4d85e5957f103e9aae7418fc803ecc61933b42c1d4add67f4ea1dcc8b597e3` |
| `sin.cc` | `06ac6f168f6e63f73e6195bbd4a1a65713f01594aeccef469f9c36e9e22e1d11` |

Re-vendoring:

```bash
git clone https://github.com/google/music-synthesizer-for-android reference/msfa
python3 engines/third_party/msfa/vendor.py reference/msfa
python3 engines/third_party/msfa/vendor.py reference/msfa --check
```

## How the build uses the files

- **Each `.cc` is its own translation unit**, compiled through
  `engines/src/msfa_unit.cc`, which includes it inside `namespace fm1_msfa`
  (`engines/mk/msfa.mk`). msfa's classes and globals (`Env`, `Lfo`, `Sin`,
  the table `lut`...) then cannot collide with anything else the firmware
  links. Five of msfa's headers (`exp2.h`, `fm_op_kernel.h`, `freqlut.h`,
  `lfo.h`, `sin.h`) have no include guard, so the files cannot share one
  translation unit.
- **`synth.h` is vendored but not read.** It defines `HAVE_NEON_INTRINSICS`
  on every aarch64 target, Apple's desktops included, which switches the
  operator kernels to float NEON code that rounds differently from the
  integer kernels the FM-1, the browser and x86 run; and on Apple it
  includes `<libkern/OSAtomic.h>`, which cannot sit inside a namespace.
  `engines/src/msfa_prelude.h` defines what it defines instead, with the
  same values (`LG_N` 6, `N` 64, `min`, `max`, `hasNeon()` returning false,
  an empty `SynthMemoryBarrier`), and claims its include guard.
- **Flags:** the vendored-code flags (`-w -fwrapv`), as for Mutable's code:
  msfa's phase accumulators are `int32_t` and wrap by design.
  `engines/sanitizers/ubsan.supp` exempts its known undefined-behaviour
  reports, each with its reason.
- **Not vendored:** `synth_unit.cc` (the Android synth: MIDI parsing, a
  ring buffer, its resonant filter), `ringbuffer`, `resofilter`, `fir`,
  `sawtooth`, `log2`, `module.h`, `wavout`, the NEON assembly and the test
  programs. `Dx7Note` (`dx7note.cc`) is compiled for its note set-up
  functions; the engine builds its voice from msfa's parts itself.

## What upstream does that the engine works around or adds to

engines/msfa.md has the details; in short:

- **Algorithms 4 and 6.** Rows 4 and 6 of `FmCore`'s table mark a feedback
  loop (`FB_IN` on the sixth operator, `FB_OUT` on the fourth or fifth), but
  `FmCore::compute` runs only single-operator feedback ("todo: more than
  one op in a feedback loop"), so msfa plays those two algorithms with no
  feedback at all. This table is the original one: the initial commit
  (`a99ac7a`, 2012-03-04) already has `0x41` there [verified: git log -S].
  The engine closes the loops itself (`engines/src/dx7_loop.cc`).
- **No amplitude modulation.** `Dx7Note::compute` applies the LFO to pitch
  only; the voice data's AMD and AMS are not read. The engine adds it.
- **No transpose.** The synth ignores the voice's transpose; the engine
  applies it.
- **Envelope rates are set for 44.1 kHz.** `Env` counts 64-sample blocks
  and has no rate of its own; the engine clocks it by 44,118 / rate.
- **Sample-rate state is global.** `Freqlut`, `Lfo` and `PitchEnv` keep
  the rate in globals filled by `init`; the engine fills them once, in its
  first create, and refuses a later instance at another rate.
