# 11 — A Schwung-style plugin platform on the FM-1: feasibility

The question: could the FM-1 get something like [Schwung](https://schwung.dev):
swappable sound engines, effects and MIDI tools, ideally compatible with
Schwung's modules, and above all could Mutable Instruments' code run on it?

This builds on docs/05 (what an open firmware can be) and docs/06 (why Movy
and Schwung themselves cannot be ported). Research on 2026-09-29 covered
three things, with working notes in `scratch/` (not committed):

- Schwung's source at commit `70c4171` (host v1.5.0) and the repos of all
  147 catalog modules;
- plugin systems on microcontrollers (Korg logue SDK v1/v2, OWL, Axoloti,
  Daisy, disting NT, Zephyr LLEXT) and the published costs of synth
  engines;
- MCU-class Eurorack firmware from
  [eurorack-awesome](https://github.com/newdigate/eurorack-awesome) (CTAG
  TBD, 4ms, Music Thing, Daisy ports) and the Mutable Instruments source
  itself.

Nothing was built or run, so every CPU figure for the FM-1 below is
**[inferred]** until someone benchmarks on the chip (§8).

## 1. Short answer

| Question | Answer |
| --- | --- |
| Run Schwung itself? | **No.** Its host is `LD_PRELOAD`, `dlopen`, POSIX shared memory and QuickJS on quad-core Linux [verified: Schwung `docs/ARCHITECTURE.md`]. docs/06 stands. |
| Load Schwung module *binaries*? | **No.** They are aarch64 Linux `.so` files. |
| Compile Schwung modules from *source*? | **Yes, for a subset.** Schwung's DSP contract is three plain C structs of function pointers, and it runs at 44.1 kHz like the FM-1. About 22 of the 100 sound generators and audio effects look likely to port; about 42 more would need work (§3). Their JavaScript UIs do not carry over. |
| Mutable Instruments code? | **Yes, and it is the best fit found.** MIT licence, C++98 with no exceptions, RTTI or heap, single-precision float or fixed point, few ARM-specific lines, each with a C fallback. It has already been ported to an ESP32, a chip of the same class (§4). Polyphony is the constraint, not whether it runs. |
| A plugin loader? | **Yes, in stages** (§5). Start with engines compiled into the firmware behind one stable C API. Then add units loaded into RAM at a fixed address over USB-MIDI, the Korg logue v1 / OWL model. Relocatable plugins depend on a toolchain question nobody has answered yet. |
| What gates it? | The same things that gate the whole project: a firmware of our own on the device (docs/07 rule 1), and a first benchmark of pi32v2 DSP speed. The benchmark needs no FM-1 at all: a JieLi AC79 dev board will do (§8). |

## 2. The FM-1's budget

| Resource | Figure | Confidence |
| --- | --- | --- |
| Audio clock | 44,118 Hz, 64-sample blocks, i.e. 1.451 ms per block | [reported] AL-255 `04-synth-engine.md` §2 |
| Cycles per output sample, one core | 5,440 at 240 MHz (the stock clock), 7,250 at 320 MHz (the family maximum) | arithmetic |
| Same figure on CTAG TBD's ESP32 | 5,442 (`CPU_MAX_ALLOWED_CYCLES 174150` per 32-frame block at 240 MHz, 44.1 kHz) | [verified] CTAG `SPManager.cpp` |
| Stock load | **Not measured.** msfa renders its 12 voices on cpu1; the 6 FX slots, the fade and the output run in a task on cpu0 (next row). "240 of 320 MHz" in older docs is clock speed, not load | — |
| Second core | **Stock uses both cores**: JieLi's OS on cpu0, and the msfa voice render on cpu1, outside the OS. The routine at V13 file `0x86AD6` (AL-255's "engine task pump loop") writes 1 to `0x01C1FF08`, busy-polls a state byte at `0x01C16EC0` and, on value 2, calls `dx7note_compute_block` (`0x862FA`), its only call site. That routine is cpu1's: AL-255's `cpu1_boot_start` writes `0x020001B8` to the cpu1 mailbox `0x01C7FFF8`, clears `0x01C1FF08` and waits for it to turn non-zero, and the vector at file `0x98` returns into this routine, which has the shape of the SDK's `cpu1_main` (`cpu1_run_flag = 1` first). The interrupt table is the SDK's `CPU_CORE_NUM 1` table: SOFT5 on cpu0, SOFT4 on cpu1. In that mode the OS runs on cpu0 only and `cpu1_main` runs bare-metal; it needs a single-core `system.a` that JieLi supplies on request. cpu0 runs the UI, MIDI, USB and BLE, and the audio task with the fade, the six FX slots and the output. **AL-255's docs are partly wrong here.** `reversing/01-hardware-map.md` reads `CPU_CORE_NUM 1` as a single core, and `io/01-boot.md` takes cpu1's entry `0x01C023D6` for the cross-core IPC path. With `app.bin` running from `0x02000120` (docs/01 §2), that address is the render loop above | the loop and call [verified: V13 disassembly]; that it runs on cpu1 [reported: AL-255's symbol names; inferred from the `cpu1_run_flag`]; the mailbox write, the wait and the vector [verified: V13 disassembly, file `0x5A0C8` and `0x98`]; the interrupt table [verified: bytes at V13 file `0x4DD48` and V15 and FM-1_092 file `0x4D4A0`, against the SDK's `demo_hello`]; the mode and its library [reported: JieLi AC79 doc 7.40; the SDK's `init.c` verified]; cpu0's audio task [reported: AL-255 `io/03-audio-dac.md` §7.2; its core inferred] |
| Code in RAM | Stock copies msfa's hot kernels from flash to SRAM at boot and runs them there | [reported] AL-255 `04-synth-engine.md` §2 |
| Free SRAM in the stock layout | Stock `.bss` ends at `0x01C211FC` and the boot info struct sits at `0x01C7FD50`: a gap of about 387 KB, part of it used by stock's heap. AL-255's demo used 192 KB of it; FM-1+VA uses the top | [inferred] from AL-255 addresses and `link.ld` |
| Flash for code | App area up to `0xD9000` in FM-1+VA's layout (about 852 KB). The stock app is 581 KB; FM-1+VA's is 692 KB | [verified] docs/01 §2 |
| Flash writes | 4 KB sectors. The write routine re-encrypts only below a boundary, so a partition above it may be readable in place unencrypted | [reported] AL-255 `09-storage.md`; [inferred] |
| Controls for parameters | **Four** free parameter knobs (KNOB1–4), plus SELECT/ALGORITHM for lists, PRESETS, MASTER (volume) and a 240×240 colour TFT. docs/06 said eight knobs map one-to-one onto Movy's pages; in practice it is four knobs per page | [reported] Baud Girl's manual; docs/01 §3 |
| Built-in effect slots | Stock's FX chain is already a small plugin table: 6 slots, each entry `{init, …, process(buf, frames)}`, sharing an 8 KB arena | [reported] AL-255 `04-synth-engine.md` §4 |

What that buys, in round numbers [inferred]:

- **Mutable Instruments modules are built to use 80–95 % of their chip**
  [verified: MI tech notes]:
  - Plaits: one voice on a 72 MHz Cortex-M4F at 48 kHz, with a 32 KB RAM
    region and a 16 KB engine arena.
  - Braids: a 72 MHz Cortex-M3 with no FPU, in fixed point, with 20 KB of
    RAM.
  - Rings, Elements and Clouds: a 168 MHz Cortex-M4F with 128 + 64 KB of
    RAM.
- **Plaits on the FM-1:** if a pi32v2 cycle is worth roughly a Cortex-M4F
  cycle, one core at 240 MHz holds about three worst-case Plaits voices, or
  one Rings instance. The light engines (VA, waveshaping, 2-op FM,
  wavetable) cost far less than the heavy ones (string, modal, particle).
  That per-cycle parity is the big unknown.
- **One weak data point:** Synth_Dexed on a Teensy 3.6 (Cortex-M4F) plays
  12 notes with effects at 180 MHz [verified: MicroDexed `config.h`], and
  the FM-1 plays 12 msfa notes at 240 MHz on one core, with its effects on
  the other. That fits "M4F-class per clock" but does not prove it, because
  the FM-1's headroom is unknown.
- **The second core** is the largest lever if the SDK lets us use it. Stock
  already gives it the voices (above), and CTAG pins audio to its own core
  on the ESP32 for the same reason. docs/14 §5.1 probes it on the dev kit.

## 3. Schwung compatibility

### 3.1 The contract

**DSP contract** [verified: Schwung `src/host/*.h`, `docs/MODULES.md`,
`docs/API.md`]:

- **Sound generators.** `plugin_api_v2_t` has these members:
  - `api_version`
  - `create_instance(module_dir, json_defaults)`, `destroy_instance`
  - `on_midi`, `set_param(key, val)`, `get_param(key, buf, len)`, `get_error`
  - `render_block(inst, int16_t *out_lr, frames)`

  The entry point is `move_plugin_init_v2(const host_api_v1_t*)`.
- **Audio effects.** `audio_fx_api_v2` provides `process_block(inst,
  int16_t *inout, frames)` and the same parameter calls; the entry point
  is `move_audio_fx_init_v2`.
- **MIDI effects.** `midi_fx_api_v1` provides `process_midi(...)` and
  `tick(...)`, with at most 16 output messages.
- **Audio format.** 44.1 kHz, up to 128 frames per block, interleaved int16
  stereo. The host owns the buffers.
- **Parameters.** Parameters are strings passed by key. A module describes
  them in `chain_params` JSON and lays them out as knob pages through
  `get_param("ui_hierarchy")`, with up to 8 knobs per level. Presets use
  `get_param("state")`.
- **What modules may do in practice.** The header forbids heap, file I/O
  and locks in the audio callback, but a 2026-08 audit counted about 150
  violations, and most modules `calloc` their instance and their delay
  lines.
- **The UI side.** QuickJS with ES modules, drawing on Move's 128×64 1-bit
  screen.

### 3.2 What a compatibility shim needs [inferred]

- **Loading.** A static table of the three structs, built at link time,
  instead of `dlopen`/`dlsym`.
- **Audio format.** `frames` ≤ 128 is satisfied by the FM-1's 64-sample
  blocks, and 44,118 Hz is close enough to 44.1 kHz that the pitch error
  is about 0.7 cents.
- **Memory.** A stub `host_api_v1_t` and a bounded arena behind `calloc`
  for `create_instance`.
- **Parameters.** A small JSON reader and writer for `chain_params`,
  `ui_hierarchy` and state blobs, read once at load. A `ui_hierarchy` of 8
  knobs becomes two FM-1 pages of four.
- **Removals.** Take out file I/O (sample, preset and bank folders), worker
  threads and logging.
- **UI.** Drop the JavaScript UI. The FM-1 draws a generic parameter page
  from the declared parameters, as Schwung's own Shadow UI does for modules
  that ship no JavaScript.

### 3.3 Candidates

All verdicts are [inferred] from sources the agent read. Licences are
[verified].

| Likely | Licence | Notes |
| --- | --- | --- |
| `schwung-braids` (4-voice Braids wrapper), `move-anything-plaits` (Plaits, mono), MrHyde (Plaits + modulation matrix) | MIT | MI code; both already run Braids and Plaits at 44.1 kHz with a pitch offset |
| Chiptune (blargg NES / Game Boy sound) | MIT | integer, small |
| HUSH ONE, RaffoSynth, Denis, Aphex, Maze Voice, Hank, Bouba-Kiki, MonkSynth, Sophie, Weird Dreams | MIT (Hank: in `module.json` only) | small original monosynths, drum voices and FOF voices; RaffoSynth has some `double` to convert |
| TAPESCAM, Junologue Chorus, Gate, Ducker, Usefulity, Filter, PushNPull, PSX Verb (128 KB work area), Schwung's built-in Freeverb | MIT | small effects; delay lines of 512 samples to 64K |
| Dexed wrapper, OTTx, CHONK | GPL | technically likely; blocked by licence (§7). msfa itself is already in the FM-1 under Apache-2.0 |

- **Possible with work** (about 42 modules): double→float conversion, fewer
  voices, or shorter buffers. Examples are OB-Xd (2–4 voices), Open303,
  TAL NoiseMaker, the Clouds port Verglas (254 KB of buffers), MVerb,
  TapeDelay and the 606/808/909 circuit models.
- **Not feasible:**
  - Surge, Helm (`double` throughout), the JV-880 / Virus / JE-8086
    emulators, and Rust modules;
  - anything needing a filesystem, megabytes of samples, a network or live
    audio input;
  - the spectral effects;
  - CloudSeed, which needs about 18 MB of delay lines as shipped.

**The trade.** A Schwung shim costs a JSON layer and string-keyed
parameters on a microcontroller. In return we get a set of MIT modules
that compile largely as they are, plus an ecosystem other people already
write for. The recommendation is to make our native API the primary one
and put the Schwung shim on top of it (§5.2), so that neither Move's
constraints nor its string parameters leak into every engine.

## 4. Mutable Instruments on the FM-1

Why it fits [verified: `pichenettes/eurorack` and `stmlib` sources unless
marked]:

- **Licence.** MIT for all the STM32-era DSP and for stmlib. The one
  exception is stmlib's `ui/event_queue.h` (GPL-3), which DSP does not
  need. MI asks that derivatives not use "Mutable Instruments" or the
  module names (see §7).
- **Language.** C++98. There is no `constexpr` or `auto`, `virtual` appears
  only in Plaits' `Engine` base (it needs a `__cxa_pure_virtual` stub), and
  there is no heap: static arrays plus `stmlib::BufferAllocator`. stmlib
  builds with `-fno-exceptions -fno-rtti`, which is exactly the FM-1's
  toolchain profile.
- **Arithmetic.** Float, apart from fixed-point Braids, Tides v1 and
  Streams. Grep found no `double` and almost no libm in the Plaits, Rings,
  Elements and Braids DSP paths; they use tables and polynomials. That suits
  a single-precision FPU.
- **ARM specifics.** `ssat`/`usat`/`vsqrt` assembly and `IN_RAM` /
  `.ccmdata` section attributes. All of them have C fallbacks under
  `-DTEST`, which is how VCV Rack builds the same code.
- **Precedent in the same class.** CTAG TBD runs on an ESP32: 240 MHz,
  dual-core, about 520 KB SRAM, 44.1 kHz. It ships ports of all 24 Plaits
  models, Rings, Clouds, Braids and MI's effects.
  - What CTAG changed: sample rates set to 44,100, `kMaxBlockSize` raised to
    32, Braids tables regenerated, ARM assembly removed, and Rings' reverb
    and Clouds' buffers moved to external PSRAM. The ESP32's internal
    arena is 112 KB.
  - Its wrappers are GPL-3, but its MI files keep their MIT headers.
- **Other ports.** Daisy, RP2040/RP2350, Korg logue and WebAssembly.

| Engine | RAM it asks for | Tables in flash | Verdict [inferred] |
| --- | --- | --- | --- |
| **Plaits, light engines** (VA, VA+VCF, waveshaping, 2-op FM, wavetable, phase distortion, wave terrain) | a few hundred bytes of arena per voice ([reported] Daisy 4-voice design) | about 73 KiB shared by all Plaits engines, plus 11 KiB of speech data | **first target**; the best candidates for 8–12 voices |
| **Braids** | tiny (the whole firmware fits in 20 KB of RAM) | about 55 KiB | **first target**; fixed point, so cheap per voice; CTAG's MIT fork has the 44.1 kHz tables |
| **Plaits 6-op FM** | small | includes 3 DX7 banks | reads DX7 SysEx banks; an MIT comparison point with the FM-1's own msfa |
| **MI effects** (Rings/Elements reverb, chorus, ensemble, diffuser) | 64 KB (16-bit) for the reverb | small | shared across voices; big sound for little CPU |
| **Plaits, heavy engines** (string, modal, particle, speech, chords) | 16 KB arena per voice | as above | a few voices at most |
| **Rings** | about 160 KB (8 strings + 64 KB reverb) | about 23.5 KiB | one instance, as a 4-voice instrument or a resonator effect |
| **Clouds** | about 184 KB (118,784 + 65,408 B) | about 45 KiB | one instance, or cut down as CTAG did. Spectral mode uses stmlib's ShyFFT by default (`stft.h` 34–40 comments out `USE_ARM_FFT`) [verified: notes/2026-10-01-monome-oc-jhjlim-survey.md]; a reduced granular-only version fits in about 88 KB |
| **Elements** | about 60 + 32 + 64 KB | **about 364 KiB** (samples) | no, on flash grounds |

**Porting steps** [inferred; mirrors CTAG and VCV]:

1. Vendor only `<module>/dsp/**`, `resources.cc` and the stmlib DSP files,
   pinned to an upstream commit.
2. Build with `-DTEST`, then map `IN_RAM` and `.ccmdata` to the JieLi RAM
   sections.
3. Move each engine to 44.1 kHz natively. That means changing
   `kSampleRate` and `kCorrectedSampleRate` and regenerating Braids' and
   Rings' tables with MI's own `resources/*.py` on the host.
4. Render the FM-1's 64-sample block as several calls of at most
   `kMaxBlockSize`.
5. Replace `plaits::Voice`, which embeds all 22 engines, with a slim voice
   holding one engine and its own arena. Allocate voices with stmlib's
   `voice_allocator.h` (MIT).
6. Keep tables in flash, and copy the hot ones (sine, the 49.5 KiB wavetable
   bank) into RAM only if cache misses show up.
7. Write our own thin wrappers (CTAG's Plaits wrapper is about 150 lines)
   rather than reusing GPL ones.

## 5. The plugin loader

### 5.1 Lessons from the precedents [verified mechanisms; lessons inferred]

- **Korg logue v1 (prologue, minilogue xd, NTS-1).**
  - Units are linked to a fixed SRAM window and run from RAM. Oscillators
    get 32 KB for everything; effects get 6–12 KB plus external SDRAM.
  - One binary runs on three products because the firmware API sits at a
    frozen address.
  - The 32 KB slots forced ports of MI engines to be split: Plaits'
    wavetable engine became six units, and Elements was cut down. Units
    over budget failed **silently**, which produced years of "no sound"
    reports.
- **Korg logue v2 (NTS-1 mkII, NTS-3).**
  - Units are relocatable ELF objects (`-fPIC -shared`) loaded through
    `unit_init(const unit_runtime_desc_t*)`, with
    `unit_render(in, out, frames)`.
  - The runtime descriptor passes the sample rate, and a unit may refuse to
    load. External memory comes from `sdram_alloc`.
  - The SDK is BSD-3. Of the 259 indexed units, 83 are paid and about 30 %
    are open.
- **OWL / OpenWare.**
  - A patch is a fixed-address image copied into PATCHRAM with a CRC check
    and run in its own task.
  - The API arrives as a `ProgramVector` of function pointers.
  - Firmware measures `cycles_per_block` with the core's cycle counter.
  - Patches are compiled online, which spares users the toolchain.
- **Axoloti.**
  - Patches are linked with `--just-symbols=axoloti.elf`, which ties every
    patch to one firmware build.
  - The firmware mutes when load passes 99 %.
- **disting NT.**
  - Plugins are relocatable objects that **declare their memory needs** per
    pool (SRAM, DRAM, tightly-coupled RAM).
  - The API has gone through 14 numbered versions.
  - The UI shows CPU load live.
- **CTAG TBD.**
  - Processors derive from one base class with `Process`, `Init` and
    `knowYourself`.
  - Parameters are described in JSON files that drive a generic web UI.
  - Each processor gets a 112 KB arena through an overridden
    `operator new`.
  - A fixed cycle budget per block turns an LED orange when exceeded.
- **Daisy.** Not a plugin system: the bootloader swaps the whole program.
  - What is worth taking is DaisySP (MIT): per-sample building blocks
    (oscillators, SVF and ladder filters, physical models, drums ported
    from Plaits, effects) that set the sample rate at runtime. Its ARM code
    is `#ifdef`-guarded, so it should compile for pi32v2 as it stands.
  - DaisySP-LGPL (ReverbSc, MoogLadder and others) is best avoided in
    static firmware.

### 5.2 Design [inferred]

**Tier 0 — a static registry. Do this first, and it may be all that is
ever needed.** Engines, effects and MIDI tools are compiled into the
firmware behind one versioned C API. A sketch:

```c
typedef struct fm1_host {              /* passed in, never linked against */
    uint32_t api_version;
    float    sample_rate;              /* 44118 */
    uint32_t max_frames;               /* 64 */
    void    *(*arena_alloc)(size_t n, uint32_t pool);  /* bounded, per instance */
    uint32_t (*cycles)(void);          /* for the CPU meter */
    /* tempo, MIDI out, voice-steal hints, ... */
} fm1_host_t;

typedef struct fm1_engine {
    uint32_t magic, api_version, kind;   /* sound gen / audio fx / midi fx */
    const char *id, *name;
    const fm1_param_t *params; uint16_t n_params;   /* typed: range, unit, enum names, page, knob */
    size_t   (*requirements)(const fm1_host_t *, uint32_t pool);  /* disting NT style */
    void    *(*create)(const fm1_host_t *);
    void     (*destroy)(void *);
    void     (*note)(void *, uint8_t ch, uint8_t key, uint8_t vel);   /* vel 0 = off */
    void     (*midi)(void *, const uint8_t *msg, uint8_t len);
    void     (*set_param)(void *, uint16_t index, float value);
    void     (*render)(void *, float *out_lr, const float *in_lr, uint32_t frames);
    uint8_t  (*max_voices)(void *);      /* engines own polyphony */
} fm1_engine_t;
```

- **Parameters** are typed and indexed, not string-keyed. The generic UI
  lays them out four to a page on the TFT, as FM-1+VA already does with its
  four assignable knobs. As built (`engines/include/fm1_engine.h`, API v2,
  docs/15 stage S7a; API v3 since 2026-10-05), each also has a stable uid,
  which locks, modulation routes and presets store, and 16-bit flags for
  what a lock or a route may do with it (LATCH, SMOOTH, NOLOCK, MOD, INPUT,
  POLY, and LOG for pitch- and time-like knobs that move in ratios), a unit
  (dB among them since v3) and a short abbreviation [verified:
  engines/README.md, "Parameters"]. Since v3 an effect may also take a key
  input, the tempo, its beats and the transport's events (`fm1_fx_ext_t`;
  engines/README.md, "Engine API v3"). Since v4 (2026-10-06) a pad kit's
  edit focus is flagged FOCUS and its per-pad parameters PER_FOCUS, and an
  optional `get_param` reads any pad's value back, so a saved kit holds
  every pad (engines/README.md, "Engine API v4"). An engine may
  also take per-note offsets on its POLY parameters and the note's pitch
  (`set_param_note`, for per-voice modulation) [verified: engines/README.md,
  "Per-note offsets"]. Since stage S7b a SMOOTH parameter ramps over 2.5 ms
  inside its engine, keyed to the engine's own samples
  (`include/fm1_smooth.h`), and a voice's offset rides on that ramp
  [verified: engines/README.md, "SMOOTH"].
- **A Schwung v2 shim** is one more `fm1_engine_t` that adapts a Schwung
  module's structs, strings and int16 buffers.
- **CPU.** The host measures cycles per block for every instance, shows the
  load, and refuses or mutes an instance that overruns, visibly and never
  silently.
- **Shipping.** Engines are installed through firmware updates over the
  stock OTA path, which is proven (docs/03 §5).

**Tier 1 — RAM units loaded over USB-MIDI.** A unit is a flat image linked
for a fixed RAM window, as in AL-255's demo blob (`link.ld`: code at a
fixed base, data in the free RAM gap).

- The image has a header: `{magic, api_version, size, crc32,
  requirements, entry}`.
- The entry receives `fm1_host_t*`, like OWL's `ProgramVector`, so a unit
  is never linked against firmware symbols.
- Loading one into RAM for the session writes no flash. Keeping units in a
  flash partition is a later step.
- Big shared tables, such as MI's resources and stmlib, can live in the
  firmware and be offered through the host struct. That keeps units small.

**Tier 2 — relocatable ELF units** (logue v2, disting NT, Zephyr LLEXT).
These need position-independent output and a pi32v2 relocation handler.
Whether JieLi's Clang 4.0.1 fork can emit PIC is **unknown**; test it on
the Linux toolchain before designing for it.

**Scripting** — Berry (MIT, under 40 KB of code) or Lua. Use it for MIDI
effects, sequencer tools and parameter mapping, never for audio: wasm3 is
about 11× slower than native, and monome crow's 256 KB board was dominated
by the Lua heap [verified figures, §5.1 sources].

**The toolchain problem.** Unit authors would need JieLi's closed compiler,
and whether it may be redistributed is unknown. Tier 0 sidesteps this:
contributions arrive as source and CI builds them. OWL solved the same
problem with an online compiler.

## 6. Where the platform would run

- **The open firmware** (docs/05 L1, the SDK). This is the clean home. It
  needs the recovery path first (docs/07).
- **A patch on stock V15.** Like FM-1+VA (V15 plus 90 hooks plus 110 KB of
  appended code) and AL-255's demo (trampolines over `usr_app_task` and
  `midi_msg_dispatch`).
  - Stock's 6-slot FX table is already a place to plug audio effects in.
  - It reaches users sooner, but it inherits every closed library and every
    stock quirk, and it is still a write under docs/07 rule 1 on the
    owner's unit.
- **Together with Baud Girl.** FM-1+VA already switches engines per preset
  (`0x5A` VA / `0xA5` FM markers). An engine API inside it would be Baud
  Girl's call, since the source is closed. Raising it is the owner's
  decision.

## 7. Licences [verified licence texts; consequences inferred, not legal advice]

**Update 2026-10-01: owner's policy.** The project is personal and
non-commercial, and GPL code may be brought in when needed (CLAUDE.md). The
limit below on GPL and LGPL was never about commercial use: it applies to a
firmware binary that is *shared* while it links JieLi's closed libraries.
Personal builds may include GPL code; shareable builds keep it behind a build
switch. docs/12 §6 has the full rules.

- **Usable:**
  - MIT: MI's STM32 code and stmlib (minus `event_queue.h`), DaisySP,
    Schwung's ABI headers and host helpers, and the MIT Schwung modules in
    §3.3;
  - BSD-3: the logue SDK, as a reference;
  - Apache-2.0: msfa.
- **Avoid in firmware that links JieLi's closed `.a` libraries:**
  - GPL-3 code (CTAG wrappers, VCV wrappers, the Dexed / OB-Xd / OTTx
    modules and others) and LGPL code (DaisySP-LGPL, FluidLite). GPL needs
    the corresponding source of the whole work, and JieLi's Bluetooth,
    audio and cpu blobs are not System Libraries in any obvious sense. Get
    advice before shipping any.
  - Anything with no licence file: several Schwung modules, the Daisy MI
    ports, eurorack-prologue.
  - Non-commercial terms (Noise Plethora).
  - RNBO exports under Cycling '74's licence, unless the conditions are
    met.
- **Names.** Do not call engines "Plaits", "Braids" or "Mutable
  Instruments". Credit the code, name the engines ourselves, and keep the
  MIT notices.
- **CHOMPI** (CHOMPI Club / Chase Bliss, 2026). Its own sources are MIT, so
  its echo, DJ filter and Warble are usable with the CHOMPI Club notice. But
  its vendored DaisySP predates Electrosmith's LGPL split: it still holds the
  19 modules now published as DaisySP-LGPL (`reverbsc`, `moogladder`, …)
  under an MIT label. Never take DaisySP code from that repository; use
  upstream MIT DaisySP. The CHOMPI name and marks are not licensed [verified:
  notes/2026-10-01-chompi-evaluation.md].

## 8. Unknowns and the first steps

**Unknowns, in the order they decide things:**

1. pi32v2 DSP throughput per clock compared with a Cortex-M4F or an ESP32.
2. The stock msfa load.
3. Whether an SDK build can put audio on the second core. Stock does (§2),
   with a modified single-core `system.a` [verified: its build stamp]. The
   public SDK's `os_task_create` has no core argument, but a task-name
   prefix `#C<n>` exists: SDK demos and fm1-nes name tasks `#C0…` to pin
   them to core 0, and the TCB in `system.a` has a `cpu_id` member
   [verified: SDK `app_main.c` at V1.1.9 and `e30b1ee`, `FreeRTOS.h`,
   `system.a` DWARF]. Whether `#C1` pins a task to cpu1 is untested
   [inferred]. docs/14 §5.1 probes it (C6d–C6f).
4. How much SRAM an open firmware with BLE-MIDI leaves free.
5. Whether JieLi's Clang produces PIC or usable relocations, and whether it
   defines anything like `__arm__` that trips `#ifdef`s.
6. Flash/cache behaviour when running from flash with large tables.

**Staged plan:**

| Stage | Where | Work | Exit |
| --- | --- | --- | --- |
| A — desk | any computer, no hardware | `fm1_engine_t` API and a desktop host (the same source building for a simulator and for JACK/CoreAudio, as AL-255's branch does); port the Plaits light engines and Braids at 44.1 kHz and 64 frames; the Schwung v2 shim with `schwung-braids` and PSX Verb compiled through it; build with `-std=c++11 -fno-exceptions -fno-rtti` for a 32-bit target | renders match upstream MI (VCV or MI's own test harness) within tolerance; memory per voice measured |
| B — bench | the JieLi AC79 dev kit (JL-AC79-DevKit V1.0, on order since 2026-10-01; docs/14, docs/07 §3) with the Linux toolchain | build stage A for pi32v2; read the cycle counter per block for msfa, Plaits light and heavy engines, Braids, Rings and the MI reverb; try `-fPIC` and read the relocations | a cycles-per-block table, and a yes or no on Tier 2 |
| C — FM-1 | only after the dump-and-restore of docs/07 | Tier 0 in the open firmware, or in a hook build if the owner chooses that route | engines selectable per preset, CPU meter on screen |
| D | FM-1 | Tier 1 RAM units over USB-MIDI; then flash-stored units and Berry scripts if wanted | a unit built outside the firmware tree loads, runs, and is refused cleanly when over budget |

Stage A needed no hardware and cost nothing; its exit test is met (below).
Stage B is the one purchase that turns every [inferred] CPU figure in this
document into a measurement; the dev kit for it is on order (docs/14).

**Progress (2026-09-30).** Stage A was well under way in
[`engines/`](../engines/) [verified: desktop builds and tests, CI], and met
its exit test later that day (below):

- the C API, a static registry, and a desktop host that renders WAVs at
  44,118 Hz in 64-frame blocks through a bus limiter, with an effect chain;
- sound engines from Mutable code: **Macro** (Plaits' eight light engines,
  12 voices), **Shapes** (Braids, 12), **Macro Heavy** (Plaits' other 13
  engines, 4) and **Six-Op FM** (Plaits' DX7-style engine, 8);
- effects from Mutable code: **Plate** (Rings' reverb), **Ensemble** and
  **Diffuse** (Plaits);
- the Schwung v2 shim, with two MIT modules compiled through it unmodified:
  Sophie (a sound engine) and PSX Verb (an effect). The plan named
  `schwung-braids`; Sophie was chosen instead because Braids is already here
  natively (engines/schwung.md, "Which modules, and why");
- about 360 engine tests, run on Linux and macOS, on a 32-bit build, and
  under ASan and UBSan in CI. With the effects and features added since
  (engines/README.md) there are 2,430 at `549dda9` (2026-10-05;
  `tests/test_engine*.py`), run the same ways [verified: `pytest
  --collect-only`, `.github/workflows/ci.yml`].

Findings so far:

- Tuning holds within ±5 cents after rate compensation, with the upstream
  sources unmodified. Effects need their loop gains rescaled from 48 kHz.
- Memory, not CPU, sets the first voice caps: Shapes needs 206 KB for 12
  voices, PSX Verb 134 KB, Macro Heavy about 17 KB per voice. The stock
  layout's gap is about 388 KB (§2).
- Schwung modules port if the host initialises each module once, gives
  int16 effects headroom, and replaces libc's number parsing, which can
  allocate under newlib. The engine API now states the threading contract
  this needs.
- Plaits has an arena overrun (`WavetableEngine`) and an out-of-bounds read
  (LPC speech) that are harmless on the module but traps for polyphonic
  ports; Braids and stmlib need `-fwrapv` (`notes/upstream-candidates.md`).

**Exit test (2026-09-30): met at the upstream rates** [verified:
tests/test_engines_reference_*.py]. Reference renderers built from the
vendored code drive `plaits::Voice` and `braids::MacroOscillator` as the
modules' firmware does, instead of VCV Rack as first planned, which keeps
the comparison inside this repository. At Plaits' and Braids' own rates,
Macro and Macro Heavy match upstream sample for sample (21 of 24 slots,
within 16-bit rounding), Six-Op FM closely (correlation ≥ 0.98), Shapes and
the three effects within 0.5 LSB. The comparison found one real bug, in
Shapes' block handling, now fixed. At first only pitch was corrected at the
FM-1's 44,118 Hz. Since 2026-10-01 (the owner's decision) the engines run at
their modules' own rates (Braids 96 kHz, Plaits 47,872.34 Hz) and resample
to the host, so they match upstream at 44,118 Hz too (`engines/README.md`,
"The exit test").

Details are in `engines/README.md` and the per-stream notes it links. Left
before stage B: Shapes' memory (207 KB for 12 voices), and whether the
resampler's stronger second stage fits pi32v2's budget.
