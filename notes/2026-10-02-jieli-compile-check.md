# JieLi pi32v2 compile check: stage B, compile-only (2026-10-02)

**Scope.** Everything a Lunar firmware would link from this tree was compiled
with JieLi's Linux toolchain for `-target pi32v2 -mcpu=r3`. That is our
engines and effects, the vendored Mutable Instruments and Schwung code, the
sequencer core (`engines/seq/`) and the simulator's app layer
(`sim/web/src/`): 63 objects. Each was built in four profiles, then sizes,
symbols, relocations, code bytes and prologues were read from the objects.
- Nothing was linked into a firmware.
- Nothing ran on a JieLi chip.
- Nothing touched an FM-1 or a dev board.
- The toolchain was fetched by a container on the LAN build host and stays
  there. It is not on the Mac and not in the repository.

The tool is [`tools/jieli/compile-check.sh`](../tools/jieli/compile-check.sh)
(`FM1_JIELI_HOST=user@host tools/jieli/compile-check.sh`). The run recorded
here built tree `c27ef63` with no uncommitted changes. It ran at
2026-10-02T08:09Z in image `lunar-jieli-check:bookworm` (Debian bookworm,
with GCC multilib for the i386 comparison). The full report lands in
`engines/build-jieli/report.md` (git-ignored).

Credits:
- the toolchain and the AC79 SDK are JieLi's (Zhuhai Jieli Technology);
- the SDK was taken from the `amitv87/fw-AC79_AIoT_SDK` GitHub mirror;
- libc++ is LLVM's;
- the vendored DSP code is Emilie Gillet's (Mutable Instruments, MIT);
- Sophie is Matt Estela's and PSX Verb is Charles Vestal's (Schwung modules,
  MIT).

## Verdict

**Everything compiles for pi32v2: 63 of 63 objects in every profile, with no
errors [verified].** One header had to be supplied first. The AC79 SDK's copy
of libc++ has no `math.h`, so `<cmath>` does not compile, and 42 of the 63
objects fail without it (§2).

Other findings [verified unless marked]:
- **C++11 builds.** No C++11 feature, dialect flag or builtin was refused.
- **No C++ runtime is needed.** There is no `operator new` or `delete`, no
  `__cxa_*` and no static-init guard. The only libc++ symbol used is
  `std::__sort` on floats.
- **Every external symbol resolves** in the libraries the SDK's own
  `demo_hello` links:
  - newlib's libc and libm;
  - compiler-rt;
  - the SDK's libc++;
  - the SDK's `common_lib.a`, for `snprintf` and `vsnprintf`.
- **Size.** About 386 KB of code and tables at `-O2`, and 343 KB at the SDK's
  `-Oz`, before `--gc-sections`.
- **Static RAM.** Little: 960 B of data and 184 B of bss, once the
  simulator's two buffers are left out.

Facts about the target [verified]:
- **No fused multiply-add.** The pi32v2 code is byte-identical with
  `-ffp-contract=fast` and `=off`, in all 622 code sections.
- **The FPU is single precision only.** Float add, multiply, divide, floor
  and conversions are single FPU instructions. `double` is compiler-rt
  software. `sqrtf` is a newlib library call, not an instruction.
- **The instance sizes are i386's.** Every engine's instance size and every
  sequencer record has the same size on pi32v2 as on i386.

## 1. Toolchain and SDK

| Item | Value | Mark |
| --- | --- | --- |
| Toolchain link | `pkgman.jieliapp.com/s/linux-toolchain` redirects to `jieli-linux-toolchains-20250805.1.tar.xz` (26,009,040 B, SHA-256 `f686586bcfb45e0f0bb27fd2b39c7a7f313cb4f0e88a66a14da621ffa8225958`) | [verified: download, 2026-10-02] |
| Inside it | One top directory named `jieli-linux-toolchains-20250324.1`; the archive's name and its contents' name differ | [verified] |
| Compiler | Clang/LLVM 4.0.1. Targets pi32, pi32v2 and q32s; `-mcpu=r1`…`r5` accepted (`r6` refused); the SDK uses `r3` for wl82 | [verified] |
| Binutils | GNU `nm`, `ld`, `ar` and `strip` 2.26.51. `objdump` and `objsizedump` are LLVM's. `objdump` decodes FPU instructions only with `-mcpu=r3`; without it they print as "unknown instruction" | [verified] |
| C library | newlib 2.2.0 headers (`newlib.h`), `long double` = `double`; libc, libm and compiler-rt built per CPU level (`lib/r1`…`r5`, plus `-large` variants); **no C++ headers** | [verified] |
| libm | newlib's fdlibm: `__ieee754_*` and `__kernel_*` (60 symbols), `matherr`, and `_impure_ptr` in libc. So not musl, which the ladder's R0 and R1 rungs use | [verified: symbol names] |
| Post-build tools | `…/s/linux-postbuild` redirects to `jieli-linux-post-build-tools-20260923.1.tar.xz` (38,662,628 B). Not fetched: compile-only needs none | [verified: HTTP headers] |
| SDK | `AC79NN_SDK_V1.1.9_2023-08-01` = commit `8eae6645…` (annotated tag `3649fa74…`). Blobless clone; only `include_lib/c++`, demo_hello's wl82 `Makefile` and the seven closed libraries it links checked out, the libraries for their symbol tables only | [verified] |
| SDK libc++ | `_LIBCPP_VERSION 7000`, a 2018 trunk snapshot (it predates 7.0.0's `_LIBCPP_INLINE_VISIBILITY` change), with `libcxx.a` and `libcxxabi.a` | [verified] |
| SDK closed libraries | `cpu.a`, `system.a`, `common_lib.a` and the rest are LLVM bitcode. `nm` lists them only through the gold plugin (`--plugin common/bin/LLVMgold.so`) | [verified] |

The flags are the SDK's `apps/demo/demo_hello/board/wl82/Makefile`, with three
exceptions:
- **`-flto` is dropped.** Bitcode objects have no machine code to measure.
- **`-g` and `-w` are dropped.**
- **The link-time code-generation options move to compile time.** The SDK
  generates code at link time (LTO). Its link line passes `mcpu=r3`,
  `-mattr=+fprev1`, `-pi32v2-enable-simd=true`, `-pi32v2-enable-rep-memop`,
  `-pi32v2-always-use-itblock=false` and `-pi32v2-merge-max-offset=4096`.
  They are given here as `-Xclang -target-feature -Xclang +fprev1` and
  `-mllvm …` [verified: Makefile].
- **Left out on purpose:** the link line's `-inline-threshold=5`. It is a
  size setting that would also apply to our DSP code in an LTO build (§8).

The engines' own Makefile flags are kept unchanged: C++11 with
`-fno-exceptions -fno-rtti -DTEST`, `-fwrapv` on vendored code, C99 for the
sequencer and C11 for the Schwung modules. The objects come from
`engines/Makefile` and `sim/web/mk/sim.mk` themselves (`tools/jieli/objects.mk`).

## 2. The one blocker: libc++ without `math.h`

The SDK's `include_lib/c++/include` has `cmath` but not libc++'s `math.h`
wrapper [verified: directory listing]. So `#include <cmath>` reaches newlib's
`math.h`, which defines `signbit`, `isnan` and the rest as macros, and
libc++'s `using ::signbit;` fails:
`error: no member named 'signbit' in the global namespace` [verified].

- **Without the wrapper, 42 of 63 objects fail** [verified]:
  - all six Mutable-based engine wrappers and Test Sine;
  - every Plaits object;
  - stmlib's `units.cc` and `atan.cc`.
- **These still compile:** Braids, the registry, the Schwung shim and
  modules, the sequencer and the app layer.

The wrapper also supplies the C++ float overloads (`sqrt(float)` and so on).
Without them, unqualified calls on floats would silently become double
library calls on pi32v2 [inferred].

**Workaround used:** libc++ 7.0.0's own `math.h` (dual MIT/UIUC), pinned by
SHA-256 `ccb698bb…`. `compile-check.sh` fetches it on the build host into a
directory searched between libc++ and newlib. It is not committed. With it,
all 63 objects compile.

**For I2.** Ship the same file in the firmware build's include path as
third-party code, with its licence and an `UPSTREAM.md` (CLAUDE.md
convention) [inferred]. How JieLi's own C++ code avoids the gap is unknown;
the SDK's C++ may simply not include `<cmath>` [inferred].

## 3. Results by profile

| Profile | Flags beyond the SDK set | Objects | Errors | Warnings |
| --- | --- | ---: | ---: | --- |
| ladder | `-O2 -ffp-contract=off` (docs/14's ladder profile) | 63 | 0 | 20 × `-Wkeyword-macro` |
| fast | `-O2 -ffp-contract=fast` | 63 | 0 | the same |
| sdk | `-Oz` (the SDK's level) | 63 | 0 | the same |
| pic | `-O2 -ffp-contract=off -fPIC` | 63 | 0 | the same |

- **The only warnings come from newlib's headers.** They are newlib's own
  macro tricks (`#define signed +0` in `sys/_intsup.h`, `#define unsigned
  signed` in `sys/_types.h`).
- **They show only in the sequencer's five C files**, which build with
  `-Wpedantic`. They appear because the toolchain's include directory is
  passed with `-I`, as the SDK does; `-isystem` would silence them
  [inferred].
- **No `-Wframe-larger-than=2560` warning fired** in our code. The vendored
  code builds with `-w`, so its frames are measured from the prologues
  instead (§7) [verified].

## 4. Code and data size

By group, in bytes [verified: section sizes of the objects]. "text" is code
plus read-only data, as `size` counts it.

| Group | Objects | Code (O2) | Read-only data | text (O2) | text (Oz) | data | bss |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Plaits (vendored) | 35 | 66,902 | 88,877 | 155,779 | 147,743 | 0 | 0 |
| Braids (vendored) | 4 | 24,204 | 57,853 | 82,057 | 77,685 | 920 | 0 |
| Sequencer core | 5 | 60,800 | 1,199 | 61,999 | 39,330 | 0 | 0 |
| Engines, effects and shim (ours) | 11 | 28,968 | 21,042 | 50,010 | 45,722 | 4 | 144 |
| Schwung modules (vendored) | 2 | 14,262 | 6,172 | 20,434 | 18,676 | 32 | 32 |
| App layer (`sim/web/src`) | 3 | 11,606 | 1,531 | 13,137 | 10,845 | 0 | 1,200,968 |
| stmlib (vendored) | 3 | 0 | 3,082 | 3,082 | 3,082 | 4 | 0 |
| **Total** | 63 | 206,742 | 179,756 | **386,498** | **343,083** | 960 | 1,201,144 |

- **Tables are almost half of it.** The largest are Plaits' `resources.cc`
  (74,774 B), Braids' `resources.cc` (56,424 B) and Plaits' LPC word bank
  (11,051 B) [verified].
- **`-Oz` cuts code by 21 % overall, most of it in the sequencer**
  [verified]:
  - the sequencer loses 37 % (`seq_persist.o` alone goes from 20,152 to
    6,970 B of code);
  - the DSP groups lose 12–18 %;
  - single objects range from −65 % to +38 %. `mi_fx.o` grows, probably
    because `-Oz` keeps out-of-line copies of what `-O2` inlines
    [inferred].

  A split build is the obvious choice: `-Oz` for the text import/export and
  the UI, `-O2` for the audio path [inferred].
- **Nearly all the bss is the simulator's.** `g_app` (the `fm1_app_t` in
  `fm1_web.c`, 1,168,192 B) and `fm1_app_catalog_json`'s 32,768-byte buffer
  are both simulator conveniences [verified: symbols]. Without them, the 63
  objects keep 960 B of data and 184 B of bss. The rest of the RAM is
  instance memory the host provides (§6).
- **Against the flash budget** [inferred]. These are upper bounds for the
  code: unused functions go at link time with `--gc-sections`, and the test
  engines can go too. The SDK's base (OS, USB, system libraries) is not in
  them.
  - V15's app area is `0x4000–0x93000` = 585,728 B (docs/01 §2): 386 KB is
    66 % of it, and 343 KB is 59 %.
  - FM-1+VA's app area is `0x4000–0xD9000` = 872,448 B: 44 % and 39 %.
  - The stock app is 581 KB with its own OS, Bluetooth and msfa (docs/11
    §2).
  - The size of demo_hello's base is I1's job.

## 5. Floating point, `double` and libm

**The FPU** [verified: disassembly with `-mcpu=r3`]:
- `float` add, multiply and divide are single FPU instructions
  (`r0 = r0 * r1 (f)`), as are `floorf` (`ftof (floor)`), float→int
  (`ftoi (trunc)`) and int→float (`itof`).
- Float compares use FPU conditions (`iff (r2 u>= r1)`).
- `fabsf` is an integer mask.
- `sqrtf` is a call to newlib's `sqrtf`, even with `-fno-math-errno`.
- `double` arithmetic and float↔double conversion call compiler-rt
  (`__muldf3`, `__extendsfdf2` and so on).
- 64-bit division calls `__udivdi3`. 32-bit division is an instruction.

**Contraction.** `-ffp-contract=fast` against `=off` across 622 code
sections: 0 differ [verified]. The backend never fuses a multiply and an add,
so the ladder profile's `-ffp-contract=off` costs nothing on pi32v2. It
matters only on the desktop side, where macOS arm64 contracts. `+fprev1` and
`-pi32v2-enable-simd` changed nothing in a probe of these operations
[verified]. Whether the FPU has a fused instruction the backend never uses is
unknown.

**Where software `double` and libm are called.** From the relocations of each
function, ladder profile [verified]. "Path" is our reading of when the call
runs [inferred].

| Symbol(s) | Called from | Path |
| --- | --- | --- |
| `__muldf3`, `__divdf3`, `__adddf3`, `__extendsfdf2`, `__truncdfsf2`, `__fixdfdi`, `__fixunsdfsi`, `__gedf2`, `__ledf2` | `Instance::Init` of Macro, Macro Heavy, Shapes and Six-Op FM: the resampler's `double ratio` (`fm1_resampler.h` line 251) | create only |
| the same, `exp2`, `sin` (double libm) | Test Sine's `Render` | audio, test engine only |
| `__floatundidf`, `__muldf3`, `__divdf3`, `__ltdf2`, `fmod` | `fm1_app_render`: the blink clock, `seconds()` = frames / rate in double (`fm1_app.c` line 76) | once per block, UI |
| `__extendsfdf2` | `snprintf("%f")` callers in the app layer and the Schwung modules' `get_param` | UI and parameters |
| `__fixunssfdi`, `__floatundisf`, `__udivdi3` | `fm1_seq_advance`, `sq_external_realtime`, Capture | once per block |
| `sqrtf` | Plaits' `NoiseEngine::Render`, `Particle::Render`, `SyntheticSnareDrum::Render` | audio, per block or per sample (to measure) |
| `expf`, `powf` | Shapes' `RenderChunk` (envelope coefficients), Plate and Diffuse `Create` and `Set` | per chunk; parameters |
| `exp2f`, `expf`, `powf`, `sinf`, `lrintf` | Sophie's `sophie_render` and `sophie_midi` | audio (Schwung module, unmodified) |
| `logf` | `sq_capture_commit` | Capture, not per block |
| `log10f` | the app's `draw` (meter) | UI |
| `std::__sort<float>` (libc++) | Plaits' `ChordBank::Reset`, `ChiptuneEngine::Render` | init; audio for Chiptune |

**What follows for stage B** [inferred]:
- Time newlib's `sqrtf`, `expf`, `powf` and `sinf` on the board (docs/14 §5
  step 5).
- `double` stays out of the audio path except in Test Sine, which can change.
- For bit-exact ladder results, newlib's fdlibm on pi32v2 against musl on R0
  and R1 is the open item. docs/14 §2.2's plan already covers it: compile
  musl's float functions into the ladder profile.

## 6. Instance sizes at 32 bits

Bytes, read from compile-time constants (`sizeof`, with each engine's
`instance_size()` rule, `tools/jieli/sizes.cc`) on each target [verified].
Voices are each engine's `max_voices`.

| Engine or effect | Voices | pi32v2 | i386 | x86-64 | Per voice (pi32v2) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Macro | 12 | 18,864 | 18,864 | 31,728 | 1,572 |
| Shapes | 12 | 206,212 | 206,212 | 207,080 | 17,184 |
| Macro Heavy | 4 | 70,880 | 70,880 | 71,088 | 17,720 |
| Six-Op FM | 8 | 10,796 | 10,796 | 12,528 | 1,350 |
| Sophie (Schwung) | 12 | 77,888 | 77,888 | 77,904 | — |
| Test Sine | — | 300 | 300 | 304 | — |
| Plate | — | 65,632 | 65,632 | 65,648 | — |
| Ensemble | — | 4,704 | 4,704 | 4,704 | — |
| Diffuse | — | 18,848 | 18,848 | 18,848 | — |
| PSX Verb (Schwung) | — | 134,208 | 134,208 | 134,224 | — |
| Test Gain | — | 4 | 4 | 4 | — |

- **pi32v2 equals i386 for every engine**, so the desktop `-m32` build in CI
  already reports device sizes [verified].
- **Only the shim side of the Schwung modules is measured.** Their arenas are
  fixed constants: 75 KB for Sophie, 130 KB for PSX Verb. What the modules
  actually allocate inside them at 32 bits was not measured; the shim
  selftest checks it on the desktop.
- **The sequencer.** Every record in `seq_int.h` has the same size on pi32v2,
  i386 and x86-64: `struct fm1_seq` 288 B, a track 240, a note 12, a lock 3,
  a trig row 5, a command 240, an event 12 [verified]. `fm1_seq_size()` at
  the FM-1 defaults was run on i386 and x86-64, and both give 18,056 B for 4
  tracks, 31,880 for 8 and 59,528 for 16 [verified]. The same figures hold on
  pi32v2, since the layout is built from those records [inferred].
- **The app layer.** `fm1_app_t` is 1,168,192 B at 32 bits; the 1,168,288 B
  in `sim/web/README.md` is the 64-bit figure. Of that, 1,048,576 B is the
  fixed arenas and 116,176 B the TFT state, mostly the 115,200-byte frame
  [verified]. This is the 1.17 MB that I2's "one sized arena and strip
  rendering" replaces.
- **The worst chain does not fit; a typical one does** [inferred, against
  docs/11 §2's ~388 KB gap in the stock layout]:
  - Shapes, PSX Verb, Plate and the 8-track sequencer: 437,932 B, over the
    gap.
  - Macro, Plate, Ensemble and the 8-track sequencer: 121,080 B.

## 7. ABI and stack

| Fact | pi32v2 | i386 | x86-64 |
| --- | ---: | ---: | ---: |
| `char` signed | yes | yes | yes |
| `sizeof` pointer, `long`, `size_t` | 4 | 4 | 8 |
| `sizeof(long double)` | 8 | 12 | 16 |
| alignment of `double` and `uint64_t` inside a struct | 4 | 4 | 8 |
| `__BIGGEST_ALIGNMENT__` | 4 | — | — |
| `fm1_engine_t`, `fm1_param_t` | 64, 28 | 64, 28 | 120, 40 |

All values [verified]; `size_t` is `unsigned long` on pi32v2. The pi32v2
column also holds for any code that relies on shifts or wrapping behaving as
on i386, to the extent the compiler rather than the CPU decides them
[inferred].

**Largest stack frames** (prologue register push plus `sp` adjustment, ladder,
575 functions) [verified]:

| Bytes | Function |
| ---: | --- |
| 2,224 | `draw` (app layer) |
| 1,424 | `sq_capture_commit` |
| 460 | Ensemble `Render` |
| 360 | Sophie `sophie_get` |
| 328 | `fm1_seq_advance`, `fm1_seq_apply_text` |
| 320 | `fm1_seq_import_movy1` |
| 296 | Plate `Render`, `fm1_seq_export_movy1` |
| 276 | Macro Heavy `RenderBlock`, `fm1_app_encoder` |

None of these reaches the SDK's 2,560-byte warning threshold. The
audio-path frames are all under 500 B [verified]. `objsizedump
-dump-stack-size` prints 0 for every function of an unlinked object, so it was
not used [verified].

## 8. `-fPIC` and the SDK's link-time options

**`-fPIC`.** All 63 objects compile [verified]. Against the ladder build, the
relocations change [verified: relocation types]:
- `MOV_ABS32` (729) disappears;
- `GOT16` (688), `FUNCDESC` (275) and `GOTFUNCDESC16` (10) appear;
- `ABS32` drops from 800 to 525;
- calls stay `EXTEND_CALL_32M2`.

The names suggest FDPIC-style function descriptors [inferred]. This partly
answers docs/11 §8's unknown 5: the compiler produces position-independent
code. Whether JieLi's `ld` links it, and what a loader must do
with the descriptors, is untested [inferred: needs a link test].

**LTO in the SDK** [inferred from the Makefile]:
- **Code generation happens at link time.** So the link line's
  `-inline-threshold=5` would apply to our engines too.
- **That would undo the inlining the DSP code depends on.** Compare `-O2` and
  `-Oz` above. In the firmware build, either compile the engines without
  `-flto` (as here), or give the engine archive its own LTO settings.
- **Measure it in stage B**, as cycles per block with both.

## 9. What this does not answer

- **Cycles.** Every CPU figure stays [inferred] until the dev kit runs
  docs/14 §5 steps 5 and 8.
- **Linking.** Nothing was linked: neither the SDK's linker script nor
  `--gc-sections` was tried. The flash figures above are therefore upper
  bounds, and whether the FDPIC relocations link is open.
- **libm accuracy and FPU edge cases.** newlib's results against musl,
  subnormals, divide by zero and NaN conversions all need the board (docs/14
  §2.2 and §5 step 5).
- **The Schwung modules' own allocations** at 32 bits (§6).

## 10. Next steps

1. I1: build `demo_hello` with the same toolchain and pins, link it twice and
   compare bytes, as docs/14 §5 step 2 asks. That gives the SDK base's flash
   and RAM, which §4's budget needs.
2. Vendor libc++ 7.0.0's `math.h` for the firmware build, as third-party
   code with its licence (§2).
3. Link a test image of the 63 objects against `sdk.ld` with
   `--gc-sections`. That gives real flash use per engine, and checks the
   `-fPIC` objects (§8).
4. Read the hot loops' disassembly (Plaits' oscillators, the resampler,
   Plate) for the FPU instruction count, ahead of the kit [inferred value: a
   first cycle estimate].

## Reproduce

```bash
FM1_JIELI_HOST=user@host tools/jieli/compile-check.sh
less engines/build-jieli/report.md
```

The script stages `engines/`, `sim/web/` and `tools/jieli/` on the host and
fetches whatever is missing there in containers. Every pin is checked:
- the toolchain archive's SHA-256 (`FM1_JIELI_TOOLCHAIN_SHA256` accepts a new
  one);
- the SDK commit;
- `math.h`'s SHA-256.

It builds the image, runs `tools/jieli/in-container.sh` and copies back the
report, the logs and the record (`record.json`: tree, pins, image ID). The
objects stay on the host.

## Appendix: per object

Ladder profile (`-O2 -ffp-contract=off`), bytes, and the `-Oz` text for
comparison [verified]. `fm1_web.o` is the WebAssembly glue, compiled only to
check it.

<details>
<summary>63 objects</summary>

| Object | Code | Read-only data | text | data | bss | sdk text |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `c/seq/seq_capture.o` | 5,086 | 0 | 5,086 | 0 | 0 | 4,558 |
| `c/seq/seq_clip.o` | 7,674 | 6 | 7,680 | 0 | 0 | 5,942 |
| `c/seq/seq_cmd.o` | 12,560 | 1,141 | 13,701 | 0 | 0 | 10,283 |
| `c/seq/seq_engine.o` | 15,328 | 1 | 15,329 | 0 | 0 | 11,453 |
| `c/seq/seq_persist.o` | 20,152 | 51 | 20,203 | 0 | 0 | 7,094 |
| `our/src/mi_fx.o` | 4,712 | 842 | 5,554 | 0 | 0 | 7,352 |
| `our/src/mi_macro.o` | 4,236 | 3,838 | 8,074 | 0 | 0 | 7,272 |
| `our/src/mi_macro_heavy.o` | 6,224 | 4,154 | 10,378 | 0 | 0 | 9,392 |
| `our/src/mi_shapes.o` | 3,880 | 4,213 | 8,093 | 0 | 0 | 6,793 |
| `our/src/mi_sixop.o` | 5,526 | 5,177 | 10,703 | 0 | 0 | 8,885 |
| `our/src/registry.o` | 210 | 48 | 258 | 0 | 0 | 88 |
| `our/src/schwung_shim.o` | 2,786 | 297 | 3,083 | 4 | 112 | 2,671 |
| `our/src/sw_psxverb.o` | 38 | 624 | 662 | 0 | 16 | 662 |
| `our/src/sw_sophie.o` | 38 | 1,569 | 1,607 | 0 | 16 | 1,607 |
| `our/src/test_gain.o` | 70 | 139 | 209 | 0 | 0 | 209 |
| `our/src/test_sine.o` | 1,248 | 141 | 1,389 | 0 | 0 | 791 |
| `sim/src/fm1_app.o` | 9,542 | 676 | 10,218 | 0 | 32,776 | 8,352 |
| `sim/src/fm1_tft.o` | 1,654 | 855 | 2,509 | 0 | 0 | 2,083 |
| `sim/src/fm1_web.o` | 410 | 0 | 410 | 0 | 1,168,192 | 410 |
| `sw/psxverb/psxverb.o` | 4,924 | 1,794 | 6,718 | 0 | 28 | 5,560 |
| `sw/sophie/sophie.o` | 9,338 | 4,378 | 13,716 | 32 | 4 | 13,116 |
| `tp/braids/analog_oscillator.o` | 3,128 | 0 | 3,128 | 72 | 0 | 3,002 |
| `tp/braids/digital_oscillator.o` | 19,138 | 1,287 | 20,425 | 280 | 0 | 16,361 |
| `tp/braids/macro_oscillator.o` | 1,938 | 142 | 2,080 | 384 | 0 | 1,898 |
| `tp/braids/resources.o` | 0 | 56,424 | 56,424 | 184 | 0 | 56,424 |
| `tp/plaits/dsp/chords/chord_bank.o` | 1,026 | 176 | 1,202 | 0 | 0 | 862 |
| `tp/plaits/dsp/engine/additive_engine.o` | 2,164 | 152 | 2,316 | 0 | 0 | 1,494 |
| `tp/plaits/dsp/engine/bass_drum_engine.o` | 3,116 | 24 | 3,140 | 0 | 0 | 3,304 |
| `tp/plaits/dsp/engine/chord_engine.o` | 2,192 | 296 | 2,488 | 0 | 0 | 2,334 |
| `tp/plaits/dsp/engine/fm_engine.o` | 1,140 | 24 | 1,164 | 0 | 0 | 976 |
| `tp/plaits/dsp/engine/grain_engine.o` | 2,794 | 24 | 2,818 | 0 | 0 | 2,308 |
| `tp/plaits/dsp/engine/hi_hat_engine.o` | 3,584 | 24 | 3,608 | 0 | 0 | 3,230 |
| `tp/plaits/dsp/engine/modal_engine.o` | 304 | 24 | 328 | 0 | 0 | 352 |
| `tp/plaits/dsp/engine/noise_engine.o` | 1,582 | 24 | 1,606 | 0 | 0 | 1,662 |
| `tp/plaits/dsp/engine/particle_engine.o` | 2,376 | 24 | 2,400 | 0 | 0 | 2,912 |
| `tp/plaits/dsp/engine/snare_drum_engine.o` | 3,100 | 44 | 3,144 | 0 | 0 | 3,094 |
| `tp/plaits/dsp/engine/string_engine.o` | 684 | 24 | 708 | 0 | 0 | 648 |
| `tp/plaits/dsp/engine/swarm_engine.o` | 1,810 | 24 | 1,834 | 0 | 0 | 1,736 |
| `tp/plaits/dsp/engine/virtual_analog_engine.o` | 3,270 | 44 | 3,314 | 0 | 0 | 2,950 |
| `tp/plaits/dsp/engine/waveshaping_engine.o` | 1,590 | 24 | 1,614 | 0 | 0 | 1,604 |
| `tp/plaits/dsp/engine/wavetable_engine.o` | 2,180 | 24 | 2,204 | 0 | 0 | 1,606 |
| `tp/plaits/dsp/engine2/chiptune_engine.o` | 2,932 | 24 | 2,956 | 0 | 0 | 2,518 |
| `tp/plaits/dsp/engine2/phase_distortion_engine.o` | 2,728 | 24 | 2,752 | 0 | 0 | 2,468 |
| `tp/plaits/dsp/engine2/six_op_engine.o` | 7,536 | 24 | 7,560 | 0 | 0 | 5,670 |
| `tp/plaits/dsp/engine2/string_machine_engine.o` | 3,006 | 288 | 3,294 | 0 | 0 | 2,912 |
| `tp/plaits/dsp/engine2/virtual_analog_vcf_engine.o` | 2,164 | 24 | 2,188 | 0 | 0 | 2,274 |
| `tp/plaits/dsp/engine2/wave_terrain_engine.o` | 2,010 | 24 | 2,034 | 0 | 0 | 1,884 |
| `tp/plaits/dsp/fm/algorithms.o` | 2,578 | 480 | 3,058 | 0 | 0 | 2,066 |
| `tp/plaits/dsp/fm/dx_units.o` | 0 | 244 | 244 | 0 | 0 | 244 |
| `tp/plaits/dsp/physical_modelling/modal_voice.o` | 752 | 0 | 752 | 0 | 0 | 794 |
| `tp/plaits/dsp/physical_modelling/resonator.o` | 1,354 | 0 | 1,354 | 0 | 0 | 1,052 |
| `tp/plaits/dsp/physical_modelling/string.o` | 2,308 | 0 | 2,308 | 0 | 0 | 2,306 |
| `tp/plaits/dsp/physical_modelling/string_voice.o` | 826 | 0 | 826 | 0 | 0 | 848 |
| `tp/plaits/dsp/speech/lpc_speech_synth.o` | 1,266 | 0 | 1,266 | 0 | 0 | 1,106 |
| `tp/plaits/dsp/speech/lpc_speech_synth_controller.o` | 2,554 | 312 | 2,866 | 0 | 0 | 2,070 |
| `tp/plaits/dsp/speech/lpc_speech_synth_phonemes.o` | 0 | 210 | 210 | 0 | 0 | 210 |
| `tp/plaits/dsp/speech/lpc_speech_synth_words.o` | 0 | 11,051 | 11,051 | 0 | 0 | 11,051 |
| `tp/plaits/dsp/speech/naive_speech_synth.o` | 1,180 | 250 | 1,430 | 0 | 0 | 1,494 |
| `tp/plaits/dsp/speech/sam_speech_synth.o` | 796 | 172 | 968 | 0 | 0 | 930 |
| `tp/plaits/resources.o` | 0 | 74,774 | 74,774 | 0 | 0 | 74,774 |
| `tp/stmlib/dsp/atan.o` | 0 | 1,026 | 1,026 | 0 | 0 | 1,026 |
| `tp/stmlib/dsp/units.o` | 0 | 2,056 | 2,056 | 0 | 0 | 2,056 |
| `tp/stmlib/utils/random.o` | 0 | 0 | 0 | 4 | 0 | 0 |

</details>
