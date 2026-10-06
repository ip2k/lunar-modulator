# Schwung v2 shim (stage A)

A compatibility layer that builds [Schwung](https://github.com/charlesvestal/schwung)
modules from source into the engine platform (docs/11 §3, §5.2): each module
becomes one more `fm1_engine_t` in the static registry. Two MIT modules are
built through it:

| Engine | Module | Kind | Author |
| --- | --- | --- | --- |
| `sw-sophie` | [Sophie](https://github.com/mestela/schwung-sophie) 0.5.1, 16-pad metallic FM percussion, 12 voices | sound generator | Matt Estela |
| `sw-psxverb` | [PSX Verb](https://github.com/charlesvestal/schwung-psxverb) 0.5.3, PlayStation SPU reverb, 6 presets | audio effect | Charles Vestal |

```bash
make -C engines
engines/build/fm1-render --engine sw-sophie --note 0:36:110:0.5 --note 0.25:42:90:0.2 \
    --fx sw-psxverb --fx-param Model=4 --seconds 2 --out kit.wav
engines/build/fm1-schwung-selftest                     # arena, re-blocking, MIDI, parameter, init and parser checks
engines/build/fm1-schwung-selftest --contract sw-sophie  # our table next to the module's chain_params
python -m pytest tests/test_engines_schwung.py           # 56 tests
# data races between create and render, under ThreadSanitizer only:
make -C engines clean && make -C engines EXTRA="-fsanitize=thread -g" OPT=-O1 build/fm1-schwung-race
engines/build/fm1-schwung-race && make -C engines clean
```

Nothing here has run on an FM-1 or on pi32v2. Figures are from a desktop
build unless marked.

## Files

| Path | What |
| --- | --- |
| `src/schwung_shim.h`, `src/schwung_shim.cc` | The shim: stub host API, once-only module init, arena allocator, sound and effect adapters, parameter strings, number parser, MIDI |
| `src/schwung_abi.h` | Includes Schwung's ABI headers so that they build as C++ with g++ and on 32-bit targets (below) |
| `src/schwung_module_prefix.h` | Force-included into every module source: `malloc`/`calloc`/`realloc`/`free` go to the arena, `atof`/`strtod`/`strtof` to the shim's parser |
| `src/sw_sophie.cc`, `src/sw_psxverb.cc` | One adapter per module: the fm1 parameter table, the Schwung keys, the arena size, the effect headroom, the `ModuleState`, the `fm1_engine_t` |
| `test/schwung_selftest.cc` | `fm1-schwung-selftest`: probe modules and checks a render cannot make |
| `test/schwung_race.cc` | `fm1-schwung-race`: renders on a thread while creating on another; for ThreadSanitizer builds, not part of `all` |
| `mk/schwung.mk` | Build fragment: module sources as C with the prefix and a renamed entry point, the selftest |
| `third_party/schwung/` | `plugin_api_v1.h`, `audio_fx_api_v2.h` and `LICENSE` from Schwung `70c4171`, unmodified |
| `third_party/schwung-modules/<id>/` | Each module's DSP source, its own header copies, `module.json`, `LICENSE`, unmodified, with `UPSTREAM.md` |

## How the ABI maps

| Schwung | Here |
| --- | --- |
| `move_plugin_init_v2(host)` / `move_audio_fx_init_v2(host)` | Renamed at compile time to `fm1_sw_<id>_init` (so any number of modules can link into one image) and called **once**, by the module's first fm1 `create`, as Schwung calls it once per `dlopen`. The table it returns is kept in the adapter's `ModuleState` and reused by every later `create` (see "Threads") |
| `host_api_v1_t` | One static struct for the whole firmware, because modules keep the pointer in a global and use it after `create` (PSX Verb logs from `destroy`). Filled in once, by the first `create` of any module, and never written again. `sample_rate` is the host's rate rounded (44,118), `frames_per_block` the module block. `log` does nothing; `midi_send_*` return 0 ("not queued"); `get_clock_status` answers unavailable, `get_bpm` 120, `get_beat_position` −1 (no transport); `mapped_memory` is NULL; the modulation, MIDI-inject and slot callbacks are NULL, which the ABI defines as unsupported; the `reserved` tail is zero. A later `create` for a host with another rate returns NULL (`LastError()` says why); one with another `max_frames` gets the first host's block |
| `create_instance(module_dir, json_defaults)` | Called with `""` and `NULL` (no files, no defaults) while the instance's arena is open |
| `destroy_instance` | Called from fm1 `destroy`; the module's `free()` calls do nothing |
| `on_midi` | `note_on` → `90 kk vv`, velocity 0 → `80 kk 00`; `note_off` → `80 kk 00`; `pitch_bend` → `E0` at the bend range the adapter declares (none for Sophie, which ignores bend). Channel 1, source `MOVE_MIDI_SOURCE_INTERNAL` |
| `set_param(key, value)` | fm1 index → the adapter's key; the value is clamped to the table's range, then written as a float with six decimals (as Schwung's host does) or as an integer index plus an offset. No `printf`, no `double`. The module reads it back with `atof`/`strtof`, which the prefix maps to the shim's own parser (below) |
| `render_block(out, frames)` | Always called with the same block: the first host's `max_frames`, made even and at most 128 (64 on the FM-1). The shim renders ahead and serves any frame count from that block; int16 → float by 1/32768 |
| `process_block(inout, frames)` | Same fixed block, through a FIFO one block long: float → int16 saturating (NaN → 0), processed, int16 → float, with the adapter's headroom around it (below). **Latency is one block**, 64 frames = 1.45 ms on the FM-1, dry signal included |
| `get_param`, `get_error` | Not used by the fm1 path but once: at create, a focused module's starting values per entry (`focus_key`; "Reading values back" below). `fm1::schwung::GetParam` exists for tools and the selftest; the engine's own `get_param` is the shim's table (`GetParamValue`) |

The module block is fixed because modules may assume it: the ABI says
`frames` is always `MOVE_FRAMES_PER_BLOCK`, and PSX Verb processes frames in
pairs and silently skips an odd last frame [verified: `psxverb.c`]. A sound
generator renders ahead at no cost while the host calls with full blocks; if
it calls with partial ones, a note can start up to one module block late. An
in-place effect cannot produce output for input it has not seen, hence the
FIFO. A host that always calls with full blocks (as a 64-frame FM-1 audio
task would [inferred]) could say so in a flag and let the shim skip the FIFO
and its latency (see "API requests").

## Threads: init once, host set once

Schwung calls a module's init once per `dlopen`, and modules rely on it: PSX
Verb's init memsets and refills the one static `audio_fx_api_v2_t` that every
instance's `process_block` goes through, and both modules keep the host
pointer in a global [verified: `psxverb.c`, `sophie.c`]. The first version of
the shim called init, and memset and refilled the shared `host_api_v1_t`, at
every fm1 `create`. A second PSX Verb created on one task while the first
rendered on another opened a window in which the audio task could call a NULL
`process_block` [verified: ThreadSanitizer on `fm1-schwung-race`, which
renders one `sw-sophie` and one `sw-psxverb` on a thread while the main thread
creates and destroys others; found in the stage review, reproduced here with
the pre-fix shim on macOS arm64: a race between `fm1_sw_psxverb_init`'s table
refill and `ProcessFx`'s call through it]. Now:

- each module's init runs once, at its first `create`, while no instance of it
  exists; the table it returns is kept in the adapter's `ModuleState` and
  reused by every later `create`;
- the `host_api_v1_t` is filled in once, at the first `create` of any module,
  before any init has been handed it; a later host with another rate is
  refused instead of written over (the FM-1 has one host);
- so a `create` writes only its own instance memory and arena. The same
  harness reports no race [verified: TSan, exit 0], and the selftest checks,
  without threads, that every init ran once and that later and refused
  creates leave the struct as it was.

The contract assumed is that `create` and `destroy` come from one control
task, never two at once, while `render`, the note calls and `set_param` may
run on the audio task; `fm1_engine.h` does not say so yet (API requests).
One gap remains: the arena is a global pointer that is open while a
`create_instance` runs, so a module that allocated from `render` on another
task at that moment would take memory from the new instance's arena instead
of getting NULL. Neither module allocates outside `create_instance`
[verified: `psxverb.c`, `sophie.c`].

## Levels: headroom for effects

The host's bus is float and may go above full scale (twelve voices in phase
can; the bus limiter is there for it, `README.md`). A Schwung effect takes
int16, so the shim saturates at the conversion, and PSX Verb mixes its dry
signal inside the module: anything above full scale was hard-clipped there,
Mix at 0 included, before the limiter could handle it [verified: a 12-note
velocity-127 chord on `shapes` peaks at 1.092 raw; through `sw-psxverb` with
Mix=0 it came out at 0.99997].

Each adapter now sets `fx_headroom`: the bus is divided by it on the way into
int16 and multiplied by it on the way out. PSX Verb uses 2 (6 dB), so peaks up
to +6 dBFS reach the limiter (the same chord now peaks at 1.0917 through it)
and the module's own output clamp, which also used to hard-clip dry plus
reverb at full scale, sits at 2.0 on the bus. The module is linear apart from
its saturating work-area writes, so the only change in sound is that the work
area saturates 6 dB later. The cost is one bit: the module's 16-bit step is
now 2/32768 of the bus, and its dry path (which already had a 32767/32768
gain and truncated) stays within two such steps of the input [verified:
tests]. A level-dependent effect (a saturator, a compressor) should keep
headroom 1 so that it sees the levels it was designed for; it then clips
above full scale, and only a pre-FX limiter in the host would avoid that (API
requests).

## Memory: the bounded arena

An instance is the shim's header (1,104 bytes on a 64-bit host, most of it two
128-frame int16 stereo buffers) followed by the module's arena. The arena is a
bump allocator: 16-byte aligned blocks, each with a 16-byte size header (for
`realloc`), `calloc` zeroes, `realloc` copies and leaves the old block, `free`
does nothing. It is open only while `create_instance` runs.

- **Too small fails loudly.** If any allocation in `create_instance` fails,
  `create` returns NULL even if the module carried on without the memory
  (NuSaw, for one, runs without its delay line when that `calloc` fails).
  `fm1::schwung::LastError()` says why.
- **No allocation after create.** Outside `create_instance` every allocation
  returns NULL and is counted (`LateAllocations()`); nothing reaches a heap.
- **Sized by measurement.** Each adapter's `kArenaBytes` is what the module
  asks for plus under 1 KB. The selftest fails if the module outgrows it, and
  `tests/test_engines_schwung.py` fails if the constant drifts more than 2 KB
  above the need.
- `nm` on every module object must show no `malloc`, `calloc`, `realloc`,
  `free`, `atof`, `strtod`, `strtof`, file, thread or `mmap` symbols, and only
  the renamed entry point as a global (a test). Symbols whose names are not C
  identifiers are compiler helpers and are ignored: i386 GCC emits
  `__x86.get_pc_thunk.*` as global `T` symbols in every PIE object
  [verified: `nm -g` of a GCC 15 `-m32 -fPIE` object], which failed this test
  in CI's 32-bit configuration before the filter [reported: stage review].

| Engine | Instance (64-bit host) | Arena | Module's allocations | 32-bit |
| --- | --- | --- | --- | --- |
| `sw-sophie` | 79,344 B since API v4's table (78,080 B before it; 77,904 B when first measured) | 76,800 B | one `calloc` of 76,752 B (12 voices with 1,536-sample ring delays, 16 pad patches) | the same: `sophie_t` holds only `int`, `float`, `uint32_t` and `char` [verified: `sophie.c`]; 76,768 B used on i386 [reported: the stage review's i386 run of `fm1-schwung-selftest`]; armv7 and pi32v2 [inferred] |
| `sw-psxverb` | 134,432 B since API v4 (134,400 B before it; 134,224 B when first measured) | 133,120 B | 1,280 B instance + a fixed 128 KB int16 work area | 132,368 B used on i386, 16 B less, within the arena [reported: the same run]; armv7 and pi32v2 [inferred] |

No compile-time assertion checks these sizes (the structs are private to the
vendored sources). What does check them, on whatever target it is built for,
is the selftest's `arena_bounds`, which fails if a module outgrows its arena;
run on a `-m32` build it measures the 32-bit figures.

Static memory: one `host_api_v1_t` (184 bytes on a 64-bit host, 100 on
32-bit), one `ModuleState` per module (24 bytes, 16 on 32-bit) and four small
globals (whether the host struct is set, the open arena, a late-allocation
counter, the last error).

## Parameters

Each adapter holds a hand-written `fm1_param_t` table and the matching Schwung
keys. `fm1-schwung-selftest --contract <id>` prints the table next to the
module's live `get_param("chain_params")`, `ui_hierarchy` and `ui_pages`, and
the tests check name, type, range, default, enum options and knob order
against them (and, for PSX Verb, against `module.json`). Names are the
module's own, less Sophie's per-pad "Pad 1 " prefix; the only one shortened is
Sophie's "Ring Feedback" (13 characters) to "Ring Fdbk". Checking names
matters because two parameters of the same range can swap without any render
noticing: PSX Verb's Level and Input both silence the wet signal at 0. Pages
are four knobs in the module's own knob order.

- **PSX Verb:** Model (enum of the six presets), Decay, Mix, Level on page 0;
  Input on page 1.
- **Sophie** keeps 16 pad patches and edits the focused pad. The table starts
  with Pad (the module's `focused_pad`, 1–16, as an enum of its pad names),
  then the knobs of its `ui_pages` levels (Tune, Decay, Model, Color, Metal,
  Feedback, Sweep; Crush, Drive, Level, Cutoff; Resonance, Filter Type; the four
  Ring controls), which reach the focused pad through Sophie's bare-key alias.
  The defaults shown are pad 1's (the Kick). **Only the first two pages (eight
  parameters) are exposed**, because `tests/test_engines.py` accepts pages 0
  and 1 only; the other ten are defined, checked against the module and
  settable through the shim, and exposing them is one constant (`kExposed`).

## What does not map

- **JavaScript UIs** (`ui.js`, `ui_chain.js`, canvases, cards, custom cells).
  Dropped; the FM-1 would draw a generic page from the table, as Schwung's own
  Shadow UI does for modules without JavaScript.
- **Reading values back** (engine API v4, 2026-10-06). The shim answers the
  engine's `get_param` for a module whose table has a FOCUS parameter
  (Sophie's Pad) from a table of its own: what it set on each parameter and
  on each focus entry, starting from the module's own pad patches, which it
  reads once at create through the adapter's `focus_key` (`p01_tune` …).
  So a host reads every pad's values without moving the focus, exactly as
  set rather than through the module's `%.3f` text, and a saved kit
  restores bit for bit (`fm1-param-get-test`, engines/README.md, "Engine
  API v4"). A module without a focus has no table and no `get_param`: its
  host keeps its values. The module's own presets and state
  (`get_param("state")` / `set_param("state", …)`) are still not mapped.
- **Errors.** `get_error` and a failed `create` have no channel in the fm1 API
  beyond returning NULL.
- **Anything outside DSP:** file I/O (`module_dir` is empty), worker threads,
  Schwung's shared memory, networking, audio input through `mapped_memory`,
  MIDI output, clock and transport, modulation buses, per-voice split
  rendering (`move_plugin_render_split`), capacitive-touch MIDI (source 5).
  Modules that need these are out of scope, not stubbed into working.
- **The C library's number parsers.** Both modules parse `set_param` values
  with `atof` or `strtof` [verified: `sophie.c`, `psxverb.c`], and newlib's
  `strtod` gets its big-number blocks from `Balloc`, which takes its freelist
  from the heap on first use [reported: stage review; not checked here, nor
  whether JieLi's libc is newlib]. The prefix maps `atof`, `strtod` and
  `strtof` in module sources to `fm1_sw_strtof`: decimal only (sign, digits,
  fraction, exponent; no hex, `inf` or `nan`), nine significant digits,
  single precision, no heap. Against the C library over 500,035 strings
  (every `%.6f` value from −100 to 100 in steps of 0.001, random `%.6f`,
  `%.9g` and integer strings, and edge cases) it matches exactly on 97 %, is
  never more than one ulp away, and always stops at the same character
  [verified: selftest, against macOS libc and against glibc with GCC 15].
  A module that needs double precision from `strtod` would need its own
  adapter. `atoi` and `strcmp` stay with the C library (neither needs the
  heap [inferred]). With that, the modules' `set_param` paths call nothing
  that allocates [verified: `sophie_set`, `v2_set_param` and what they call;
  `nm` shows no `atof`/`strtod`/`strtof` import, a test]. `snprintf` remains
  in the modules' `get_param` (Sophie formats `chain_params` with `%g`, which
  newlib can also allocate for [inferred]); the fm1 path never calls
  `get_param`.

## Which modules, and why

All candidates' licences were read from their `LICENSE` files at the commits
in the local clones used for docs/11.

| Candidate | Licence | Verdict |
| --- | --- | --- |
| **Sophie** (mestela) | MIT | **Chosen.** One 28 KB C file, one allocation, float DSP, no I/O; listed "likely" in docs/11 §3.3 |
| **PSX Verb** (charlesvestal) | MIT | **Chosen.** One C file, 130 KB arena, the effect docs/11 §8 names for stage A |
| HUSH ONE (charlesvestal) | MIT | Skipped: the module reads preset folders and imports `.vstpreset` files (`fopen`, `opendir`, `stat`) |
| MonkSynth (charlesvestal, DSP by Jonathan Taylor) | MIT | Skipped: about 2.6 MB per instance (ten unison voices of tables and a 768 KB delay, fixed by `#define`s in its headers) |
| Bouba-Kiki (charlesvestal) | MIT code, **CC BY-SA 3.0 data** | Skipped: its NOTICE puts the contour tables compiled into the DSP (`contour_tables.h`) under CC BY-SA |
| Denis, Aphex (filliformes) | MIT | Skipped: both `mmap` Schwung's shared memory from `create_instance` |
| TAPESCAM, Junologue Chorus (charlesvestal) | MIT | Suitable, not needed yet |

PSX Verb's presets are the SPU register values published in psx-spx; the
README names Mednafen (GPL) as a reference, and no Mednafen code was found in
the file [inferred from reading it]. Recorded in its `UPSTREAM.md`.

## Findings

- **The ABI header does not build for 32-bit targets or as g++ C++.**
  `plugin_api_v1.h` ends with `_Static_assert(offsetof(host_api_v1_t, reserved)
  == 120, …)`, which pins the aarch64 layout shipped Move binaries depend on.
  With 4-byte pointers `reserved` is at +68, and g++ has no `_Static_assert` in
  C++ [verified: an i386 clang build fails the assertion; g++ 15 rejects the
  header as C++ with a parse error]. `schwung_abi.h` maps it to
  `static_assert` and applies it only where pointers are 8 bytes. Nothing
  checks the 32-bit layout at compile time: there are no prebuilt binaries
  here, the shim and the modules are compiled from source for the same target,
  and the modules' header copies share the fields the shim fills (header
  drift, below).
  Upstream candidate: a `sizeof(void *) == 8` guard in the header.
- **Init is once per `dlopen` in Schwung, and modules depend on it.** PSX
  Verb's init rewrites the static table its instances call through; calling
  init per instance is a data race with any instance already rendering
  (Threads, above).
- **An int16 effect clips what a float bus lets through.** Fixed per adapter
  with headroom (Levels, above); level-dependent effects need a host-side
  answer instead.
- **Header drift is real.** Modules ship their own trimmed copies of the
  headers: Sophie's `host_api_v1_t` has `get_project_bpm` where the canonical
  one has `reserved[0]`; PSX Verb's `audio_fx_api_v2_t` stops before `on_midi`
  [verified]. The shim reads only the common prefix and keeps the tail zero.
- **Rate.** Sophie reads `sample_rate` from the host, so it is in tune at
  44,118 Hz: its kick body measures within 0.01 cent of C2 and C3 [verified:
  measured; the tests hold it to 1 cent]. PSX Verb scales every delay by 48000/44100 for a 48 kHz device that
  Schwung is not, so its reverb is about 9 % longer than the PlayStation's
  wherever it runs [inferred from the source]. A module that hard-codes
  44,100 Hz would be 0.7 cents flat here.
- **CPU, desktop only** (Apple M1 Max, share of the 1.451 ms block):

  | | µs per 64-frame block | Share |
  | --- | --- | --- |
  | Sophie, 12 long voices | 91 | 6.3 % |
  | Sophie, the 16-pad kit hit at once | 54 | 3.7 % |
  | PSX Verb | 2.8 | 0.2 % |

  Sophie costs three to six times Macro's 12 voices because every voice
  evaluates two `expf`, one or two `exp2f`, one or two `powf` and five to
  eight `sinf` per sample, several of them per-patch constants (the decay
  multiplier, the filter coefficient, the drive curve) that could be
  computed once per hit [verified: `sophie.c`]. On pi32v2 that probably means fewer voices, or an
  upstream change hoisting those constants (a candidate contribution).
- **Memory.** PSX Verb allocates its 128 KB work area whatever the preset; the
  presets need 16 KB (Room, Studio S), 32 KB (Studio M, L), 64 KB (Hall) and
  128 KB (Space Echo) [verified: work sizes in `psxverb.c`]. Sizing it to the
  largest preset offered would save up to 112 KB; that needs an upstream
  change. Sophie's 75 KB is 12 × 6.1 KB ring-delay voices.
- **Sophie on a keyboard.** Only notes 36–51 sound, note-offs are ignored
  (each hit rings for its Decay), and at full velocity the whole kit reaches
  Sophie's own output clamp (30000/32768) [verified: tests].

## Porting checklist for the next module

1. **Licence:** a `LICENSE` file that is MIT, BSD, Apache-2.0 or public domain.
   Read `NOTICE` and the README too: data or bundled code under another licence
   (Bouba-Kiki's CC BY-SA contours) rules a module out.
2. **Grep the DSP** for `fopen`, `opendir`, `stat`, `mmap`, `shm_`, `pthread`,
   `std::thread`, `dlopen`, sockets and `mapped_memory`. Any hit on a path the
   module needs means it is not a candidate yet.
3. **Arithmetic:** `double` in per-sample code, heavy libm per sample, tables
   generated at create time.
4. **Allocations:** list every `malloc`/`calloc`/`new` in `create_instance` and
   add them up; anything allocated later (lazy buffers, preset loading) will
   get NULL. C++ modules need more than the prefix header (`new`, `std::free`);
   no C++ module has been ported yet.
5. **Assumptions:** hard-coded 44,100/48,000 Hz, 128-frame buffers,
   frame pairs, and the module's own copy of the ABI headers (drift). Number
   parsing: `atof`/`strtod`/`strtof` become the shim's single-precision
   decimal parser; anything that needs hex, `inf`, `nan` or double precision
   from them needs its own adapter. Level: does the effect's sound depend on
   its input level (headroom, below)?
6. **Vendor** the DSP files, the module's header copies, `module.json` and
   `LICENSE` byte-identical into `third_party/schwung-modules/<id>/`, with an
   `UPSTREAM.md` that pins the commit and lists each file's SHA-256 (the tests
   enforce the manifest).
7. **Build:** add the object to `SW_OBJ` in `mk/schwung.mk` and a
   pattern-specific `SW_DEFS` renaming its entry point to `fm1_sw_<id>_init`.
8. **Adapter** `src/sw_<id>.cc`: the parameter table (the module's own
   names, shortened only past 12 characters, four to a page, the module's knob
   order, defaults from `chain_params`), the keys and value formats,
   `kArenaBytes` from the selftest's `arena_used`, `bend_range` if the module
   handles `0xE0`, `fx_headroom` for an effect (2 for a linear one that mixes
   its dry signal, 1 for a level-dependent one), a zero-initialised
   `ModuleState` of its own (one per init function), `max_voices`, credits
   naming the author and licence. Engine id `sw-<id>`.
9. **Register** it (one extern, one array line in `src/registry.cc`), add it to
   the selftest's arena, exhaustion, chunking, init-once and `--contract`
   lists, and add tests: clean render, parameters change the output, contract
   against `chain_params` (names included, with any shortened name in
   `SHORTENED`), determinism.
10. **Run** the sanitizer build and `nm` the object: only `fm1_sw_<id>_init`
    global (compiler helpers aside), no heap, file or C-library float-parser
    symbols. Add the engine to `test/schwung_race.cc` and run it under
    ThreadSanitizer: a module whose functions touch shared statics from
    `create_instance` shows up there.

## API requests (not made here)

- `fm1_engine_t::create` may return NULL (the shim does when an arena is too
  small, or for a host whose rate differs from the first host's);
  `fm1_engine.h` should say so, and `host/render.cc` should check it instead
  of calling `set_param` on NULL. A way to say why (an error string) would
  carry Schwung's `get_error` too.
- A threading contract in `fm1_engine.h`: which calls may run on which task
  and which may overlap. The shim assumes `create`/`destroy` from one control
  task, never two at once, alongside `render`, note and parameter calls on
  the audio task (Threads, above).
- A pre-FX limiter (or a documented headroom convention) on the host bus, so
  an int16 effect that must see full-scale levels does not hard-clip overs.
- A read-back call (`get_param(self, index)`) so a UI can show the values of
  a multi-target engine (Sophie's pads) and of anything that changes its own
  parameters.
- An opaque state get/set for presets, which would map to Schwung's `state`.
- An `fm1_host_t` flag promising full `max_frames` blocks, so fixed-block
  effects need no FIFO and no added latency.
- `tests/test_engines.py::test_registry_lists_engines` limits every engine to
  pages 0 and 1; relaxing it to "at most four per page" would let Sophie
  expose all 18 parameters.
- CI's 32-bit job runs only `tests/test_engines.py`; adding
  `tests/test_engines_schwung.py` would run these tests against the `-m32`
  binaries. With the `nm` filter above, the one test that failed there in
  the stage review (tests=122, failures=1, on i386 GCC 13) should pass
  [inferred: its synthetic i386 `nm` case passes here; not rerun on i386].
