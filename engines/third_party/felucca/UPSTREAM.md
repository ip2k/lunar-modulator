# Vendored: Felucca's WHEEL, TRIO and PHASE engines (GPL-3.0-only)

**GPL code.** Everything in this folder is built only while the GPL switch
is on (`FM1_GPL_MODS`, `engines/Makefile`; CLAUDE.md, "The GPL switch";
docs/12 §6). While it is on, no firmware image that links JieLi's libraries
may be shared, and the simulator's module is offered under the GPL. The
build with the switch off compiles none of it (`tests/test_gpl_switch.py`).

| | |
| --- | --- |
| Upstream | https://github.com/hugelton/Felucca at `b0dcd53a251d5f5392fea9478b48244d322eeb2a` (2026-10-06, after Felucca 1.0.2): `firmware/src/{core.h, dsp.c, eng_wheel.c, eng_trio.c, eng_phase.c, voice.c}`, `tools/gen_tables.py`, `LICENSE`, `LICENSING.md` |
| What it is | Felucca is open firmware for the M-VAVE FM-1 by **Leo Kuroshita (@kurogedelic), Hügelton Instruments**, bare metal, integer DSP. These are three of its fourteen engines, all of its own design: **WHEEL**, a tonewheel-style additive organ (nine drawbar partials, 16 registrations, percussion, key click, drive, a two-rotor rotary); **TRIO**, three oscillators with ring modulation and hard sync into a gritty 12 dB multimode filter, in the style of the sound chips of early 8-bit home computers; **PHASE**, phase distortion, a C port of the oscillator of **CrispyZebra** (<https://github.com/hugelton/CrispyZebra>, the same author's, GPL-3.0). `core.h` holds the types they share, `dsp.c` the fixed-point blocks they use, `voice.c` the voice code that drives them on the device, and `LICENSING.md` is Felucca's own account of its licences |
| Licence | `GPL-3.0-only` (every source file's SPDX line; `LICENSE` is the GPL version 3 as the FSF publishes it) |
| Copied by | `vendor.py` (`--check` compares every file, and runs `tools/gen_tables.py` again to compare `gen/felucca_tables.h`) |
| Local changes | **None.** Every file is upstream's, byte for byte |
| Generated | `gen/felucca_tables.h`: the output of upstream's own `tools/gen_tables.py` at that commit, as Felucca's build makes it (its `tools/build.py` and `tests/run_tests.sh` write it to `build/gen/`), committed so that no build here needs Python. Its tables are for 44,100 Hz and a 32-sample control block |
| Used by | `engines/src/felucca_bridge.c`, which includes `core.h`, the tables, `dsp.c` and the three engines as Felucca's `felucca.c` does, and `engines/src/felucca_shim.cc` above it: the sound engines **Drawbar** (`drawbar`, WHEEL), **Trio** (`trio`, TRIO) and **Phase Bend** (`phase-bend`, PHASE), built through `engines/mk/felucca.mk` only while the switch is on. `voice.c` is used only by the test oracle `fm1-felucca-oracle` (`engines/test/felucca_oracle.c`), a desktop tool |
| Not taken | Felucca's other engines (ANALOG, DIGITAL, LOFI, SAMPLE, VOICE, GRAIN, PHYS, DRUM, NOISE, SLICE; FM6 is ours from msfa, with Felucca's `fm6_core.c` as its oracle in `../felucca-fm6/`), its parts, mixer, effects, sequencer, UI, platform and tools, and its sample material. `notes/2026-10-06-fm1-x0x.md` §3 ranks them |

## How the files are compiled (no change to them)

`engines/src/felucca_bridge.c` makes two definitions around `core.h`, so
that it compiles off the FM-1 and each of our instances holds its own part;
neither changes what an engine computes:

- `core.h`'s last line puts Felucca's boot-loop record in a `.noinit`
  section, which only the FM-1's linker script has (Mach-O cannot name it).
  `section` is defined to `unused` for that line, and the record renamed.
- `core.h` defines Felucca's four parts, `trk[4]`. After it, `trk` is
  defined as the part the current call works on, the instance's own, so an
  engine that finds its part as `t - trk` (WHEEL) finds part 0.

WHEEL keeps its per-part and per-voice state in static arrays of its own
(`eng_wheel.c`, `drw_t` and `drw_v`). Each instance holds a copy of part
0's, which the bridge copies into those arrays at the start of every call
that runs WHEEL code and back at its end: 832 bytes each way, once a
control block and once a note-on. The audio task is the only caller
(`fm1_engine.h`, "Threads"), so two instances never meet in them.

The bridge is compiled as C (`-std=gnu11`: `core.h` has a `_Static_assert`,
the engines use designated initialisers and GNU attributes) with
`-fwrapv`, since Felucca's fixed-point code multiplies and shifts signed
values as its ARM build does.

## The shim's voice code against Felucca's

Above the engines, `felucca_bridge.c` and `felucca_shim.cc` do in our own
code what `voice.c` does for a part: voice allocation (POLY, Felucca's
ROTATE order and its steal), the envelope on Felucca's tables, the
modulation an engine reads (`vmod_t`) and the retrigger of a sounding voice.
`fm1-felucca-oracle` runs the real `voice.c`, with the three engines, beside
our engines through the API, and `tests/test_engine_felucca.py` holds them
to the same samples, bit for bit, on every factory sound of the three
engines, through steals and retriggers, at host blocks of 1, 7, 32 and 64
and at 44,100 and 44,118 Hz [verified 2026-10-06]. What `voice.c` reaches
outside these files (the modulation matrix, the DRUM engine, the LFO's
generator) is stubbed there, inert as on a part with no route, no drum and
no LFO depth.

## Sanitizers

Nothing here is reported under ASan and UBSan (Apple clang, `-O1`, the
bridge with `-fwrapv` as it is built, so signed wrap and left shifts of
negative values are defined, as in Felucca's ARM build): the oracle, the
engines' own tests and the glide, SMOOTH and per-note tests, and the
simulator's tests with the three parity scenarios [verified 2026-10-06].
No entry in `engines/sanitizers/` is needed.

## Sizes

On pi32v2 as on i386 [verified: the JieLi compile check with the switch on,
2026-10-06]: `track_t` 1,752 bytes (8 voices of 84), WHEEL's part 96 and
voice 92 bytes; an instance of Drawbar 4,976 bytes, of Trio or Phase Bend
4,144. The bridge object, with the three engines and Felucca's tables, is
15,269 bytes of code and read-only data at -O2 (13,539 at -Oz), and holds
3,344 bytes of static RAM: WHEEL's arrays, sized for Felucca's four parts.

## Files

| File | sha256 |
| --- | --- |
| `LICENSE` | `3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986` |
| `LICENSING.md` | `7fe37c44120f506c4e5ecc3af92cf3e75aa26eb2c81c178290db36267e7b841a` |
| `src/core.h` | `1822b8b41853127cd6f21dde363c3627f4dbd234f603618c0feb2dcdd4c02a3c` |
| `src/dsp.c` | `f3bb643947d1d80e46aeb23985f0f61cefc02c222952a06d79f79153acdf01e7` |
| `src/eng_wheel.c` | `f82d6e0fe99dec64c477e83db7d70ca774fcbf2764768748eb33295232348b0b` |
| `src/eng_trio.c` | `7bf65c3662f72dfb893dd8897ef26025ffe551a664c70256e374d826f1fd163a` |
| `src/eng_phase.c` | `172dc2beab85c618068d58eaf06ac4c757b3fa07ed8f918d2523e992bccfe204` |
| `src/voice.c` | `d58be394655cf0fc61df201d10a4283262625367a825bc07ba10349863baebd7` |
| `tools/gen_tables.py` | `a1896486ffa6605c5ccb1dfbccac2e5c79e96e3a65cc938a5df52a99c15e3ad8` |
| `gen/felucca_tables.h` (generated) | `a975289289c52b9f9fd2ff985a147b199f8a3afa9fb416e95f99cb83131993cb` |

Re-vendoring:

```bash
git clone https://github.com/hugelton/Felucca reference/Felucca
python3 engines/third_party/felucca/vendor.py reference/Felucca --check
```

The engine files and `gen_tables.py` are the same at Felucca 1.0
(`727f272`), the commit `../felucca-fm6/` is pinned at; `core.h` gained the
retirement of SAMPLE's PERC set after it, which these engines do not read.

## Credits and names

Leo Kuroshita (@kurogedelic), Hügelton Instruments: Felucca, WHEEL, TRIO,
PHASE and CrispyZebra. "Drawbar", "Trio" and "Phase Bend" are this
project's names for them (proposed to the owner,
`notes/2026-10-06-fm1-x0x.md` §6.1; "Trio" is Felucca's own, borrowed with
thanks as "FM6" was). Felucca's own names appear in credits.
