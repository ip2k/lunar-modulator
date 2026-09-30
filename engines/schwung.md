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
engines/build/fm1-schwung-selftest                     # arena, re-blocking, MIDI and parameter checks
engines/build/fm1-schwung-selftest --contract sw-sophie  # our table next to the module's chain_params
python -m pytest tests/test_engines_schwung.py           # 51 tests
```

Nothing here has run on an FM-1 or on pi32v2. Figures are from a desktop
build unless marked.

## Files

| Path | What |
| --- | --- |
| `src/schwung_shim.h`, `src/schwung_shim.cc` | The shim: stub host API, arena allocator, sound and effect adapters, parameter strings, MIDI |
| `src/schwung_abi.h` | Includes Schwung's ABI headers so that they build as C++ with g++ and on 32-bit targets (below) |
| `src/schwung_module_prefix.h` | Force-included into every module source: `malloc`/`calloc`/`realloc`/`free` go to the arena |
| `src/sw_sophie.cc`, `src/sw_psxverb.cc` | One adapter per module: the fm1 parameter table, the Schwung keys, the arena size, the `fm1_engine_t` |
| `test/schwung_selftest.cc` | `fm1-schwung-selftest`: probe modules and checks a render cannot make |
| `mk/schwung.mk` | Build fragment: module sources as C with the prefix and a renamed entry point, the selftest |
| `third_party/schwung/` | `plugin_api_v1.h`, `audio_fx_api_v2.h` and `LICENSE` from Schwung `70c4171`, unmodified |
| `third_party/schwung-modules/<id>/` | Each module's DSP source, its own header copies, `module.json`, `LICENSE`, unmodified, with `UPSTREAM.md` |

## How the ABI maps

| Schwung | Here |
| --- | --- |
| `move_plugin_init_v2(host)` / `move_audio_fx_init_v2(host)` | Renamed at compile time to `fm1_sw_<id>_init` (so any number of modules can link into one image) and called at every fm1 `create` |
| `host_api_v1_t` | One static struct for the whole firmware, because modules keep the pointer in a global and use it after `create` (PSX Verb logs from `destroy`). `sample_rate` is the host's rate rounded (44,118), `frames_per_block` the module block. `log` does nothing; `midi_send_*` return 0 ("not queued"); `get_clock_status` answers unavailable, `get_bpm` 120, `get_beat_position` −1 (no transport); `mapped_memory` is NULL; the modulation, MIDI-inject and slot callbacks are NULL, which the ABI defines as unsupported; the `reserved` tail is zero |
| `create_instance(module_dir, json_defaults)` | Called with `""` and `NULL` (no files, no defaults) while the instance's arena is open |
| `destroy_instance` | Called from fm1 `destroy`; the module's `free()` calls do nothing |
| `on_midi` | `note_on` → `90 kk vv`, velocity 0 → `80 kk 00`; `note_off` → `80 kk 00`; `pitch_bend` → `E0` at the bend range the adapter declares (none for Sophie, which ignores bend). Channel 1, source `MOVE_MIDI_SOURCE_INTERNAL` |
| `set_param(key, value)` | fm1 index → the adapter's key; the value is clamped to the table's range, then written as a float with six decimals (as Schwung's host does) or as an integer index plus an offset. No `printf`, no `double` |
| `render_block(out, frames)` | Always called with the same block: the host's `max_frames`, made even and at most 128 (64 on the FM-1). The shim renders ahead and serves any frame count from that block; int16 → float by 1/32768 |
| `process_block(inout, frames)` | Same fixed block, through a FIFO one block long: float → int16 saturating (NaN → 0), processed, int16 → float. **Latency is one block**, 64 frames = 1.45 ms on the FM-1 |
| `get_param`, `get_error` | Not used by the fm1 path. `fm1::schwung::GetParam` exists for tools and the selftest |

The module block is fixed because modules may assume it: the ABI says
`frames` is always `MOVE_FRAMES_PER_BLOCK`, and PSX Verb processes frames in
pairs and silently skips an odd last frame [verified: `psxverb.c`]. A sound
generator renders ahead at no cost while the host calls with full blocks; if
it calls with partial ones, a note can start up to one module block late. An
in-place effect cannot produce output for input it has not seen, hence the
FIFO. A host that always calls with full blocks (as a 64-frame FM-1 audio
task would [inferred]) could say so in a flag and let the shim skip the FIFO
and its latency (see "API requests").

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
  `free`, file, thread or `mmap` symbols, and only the renamed entry point as
  a global (a test).

| Engine | Instance (64-bit host) | Arena | Module's allocations | 32-bit |
| --- | --- | --- | --- | --- |
| `sw-sophie` | 77,904 B | 76,800 B | one `calloc` of 76,752 B (12 voices with 1,536-sample ring delays, 16 pad patches) | same struct size on i386 and armv7 [verified: compile-time assertion] |
| `sw-psxverb` | 134,224 B | 133,120 B | 1,280 B instance + a fixed 128 KB int16 work area | smaller by a few pointer widths; fits [verified: compile-time assertion] |

Static memory: one `host_api_v1_t` (184 bytes on a 64-bit host, 100 on
32-bit) and three small globals (the open arena, a late-allocation counter,
the last error).

## Parameters

Each adapter holds a hand-written `fm1_param_t` table and the matching Schwung
keys. `fm1-schwung-selftest --contract <id>` prints the table next to the
module's live `get_param("chain_params")`, `ui_hierarchy` and `ui_pages`, and
the tests check type, range, default, enum options and knob order against
them (and, for PSX Verb, against `module.json`). Pages are four knobs in the
module's own knob order.

- **PSX Verb:** Model (enum of the six presets), Decay, Mix, Level on page 0;
  Input on page 1.
- **Sophie** keeps 16 pad patches and edits the focused pad. The table starts
  with Pad (the module's `focused_pad`, 1–16, as an enum of its pad names),
  then the knobs of its `ui_pages` levels (Tune, Decay, Model, Color, Metal,
  Feedback, Sweep; Crush, Drive, Level, Cutoff; Resonance, Filter; the four
  Ring controls), which reach the focused pad through Sophie's bare-key alias.
  The defaults shown are pad 1's (the Kick). **Only the first two pages (eight
  parameters) are exposed**, because `tests/test_engines.py` accepts pages 0
  and 1 only; the other ten are defined, checked against the module and
  settable through the shim, and exposing them is one constant (`kExposed`).

## What does not map

- **JavaScript UIs** (`ui.js`, `ui_chain.js`, canvases, cards, custom cells).
  Dropped; the FM-1 would draw a generic page from the table, as Schwung's own
  Shadow UI does for modules without JavaScript.
- **Reading values back.** The fm1 API has no `get_param`, so after Sophie's
  Pad changes, the knobs cannot show the new pad's values. Presets and state
  (`get_param("state")` / `set_param("state", …)`) are not mapped either.
- **Errors.** `get_error` and a failed `create` have no channel in the fm1 API
  beyond returning NULL.
- **Anything outside DSP:** file I/O (`module_dir` is empty), worker threads,
  Schwung's shared memory, networking, audio input through `mapped_memory`,
  MIDI output, clock and transport, modulation buses, per-voice split
  rendering (`move_plugin_render_split`), capacitive-touch MIDI (source 5).
  Modules that need these are out of scope, not stubbed into working.
- **The C library.** Modules still call `snprintf`, `strtof`, `atof` in
  `set_param`/`get_param`. In some C libraries (newlib's `strtod`, for one)
  these can allocate internally [inferred]; check JieLi's libc before calling
  `set_param` from the audio task on the FM-1.

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
  header as C++ with a parse error]. `schwung_abi.h` maps it to `static_assert` and applies it only
  where pointers are 8 bytes; the 32-bit layout is checked separately.
  Upstream candidate: a `sizeof(void *) == 8` guard in the header.
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
   frame pairs, and the module's own copy of the ABI headers (drift).
6. **Vendor** the DSP files, the module's header copies, `module.json` and
   `LICENSE` byte-identical into `third_party/schwung-modules/<id>/`, with an
   `UPSTREAM.md` that pins the commit and lists each file's SHA-256 (the tests
   enforce the manifest).
7. **Build:** add the object to `SW_OBJ` in `mk/schwung.mk` and a
   pattern-specific `SW_DEFS` renaming its entry point to `fm1_sw_<id>_init`.
8. **Adapter** `src/sw_<id>.cc`: the parameter table (names of 12 characters
   or fewer, four to a page, the module's knob order, defaults from
   `chain_params`), the keys and value formats, `kArenaBytes` from the
   selftest's `arena_used`, `bend_range` if the module handles `0xE0`,
   `max_voices`, credits naming the author and licence. Engine id `sw-<id>`.
9. **Register** it (one extern, one array line in `src/registry.cc`), add it to
   the selftest's arena, exhaustion, chunking and `--contract` lists, and add
   tests: clean render, parameters change the output, contract against
   `chain_params`, determinism.
10. **Run** the sanitizer build and `nm` the object: only `fm1_sw_<id>_init`
    global, no heap or file symbols.

## API requests (not made here)

- `fm1_engine_t::create` may return NULL (the shim does when an arena is too
  small); `fm1_engine.h` should say so, and `host/render.cc` should check it
  instead of calling `set_param` on NULL. A way to say why (an error string)
  would carry Schwung's `get_error` too.
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
  binaries.
