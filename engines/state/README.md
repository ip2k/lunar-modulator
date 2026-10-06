# engines/state/ — saved state: records, JSON and the binary container

The files Lunar Modulator saves, loads, links and ships with the guide:
projects, sounds, effects chains, mod racks, clips and settings, in JSON
for people and programs, and in a chunked binary container for the device;
and the export of every parameter's metadata that an editor builds its
controls from. The design, its measurements and the owner's decisions are
in [notes/2026-10-06-state-files.md](../../notes/2026-10-06-state-files.md)
(§6 the records, §7 JSON, §8 the binary, §20 what stage E3 settled); the
song list's part is in
[notes/2026-10-06-song-and-scenes.md](../../notes/2026-10-06-song-and-scenes.md).

**Status (stage E3 and P1, 2026-10-06):** the record model, the streaming
JSON reader, the canonical JSON writer, the binary container and its
deflate are built in C, and independently in Python (`tools/lunar_state.py`);
the desktop tools load and save every kind (`fm1-state`, `fm1-render
--load/--save`, `fm1-seq --load/--save`). Nothing in the virtual FM-1 calls
them yet: its Open, Save and launch links are stages A1 and W1.

```bash
make -C engines                                          # fm1-state, fm1-state-fuzz; fm1-render and fm1-seq take files
engines/build/fm1-state canon FILE                       # any state file as canonical JSON (puts context order right)
engines/build/fm1-state pack FILE -o F.lunarb            # JSON to binary (deflated chunks); unpack back
engines/build/fm1-state records FILE [--pieces 7]        # the records a reader gives, a line each
engines/build/fm1-state check FILE                       # pass 1: names, rate, instances' RAM at 44,118 Hz
engines/build/fm1-render --load deep-bass.sound.lunar --note 0:36:100:1 --out a.wav
engines/build/fm1-render --load s2:deep-bass.sound.lunar --save project:p.lunar ...
engines/build/fm1-seq --seq set.movy1 --load t3.5:bass-a.clip.lunar --export out.movy1
python3 tools/lunar_state.py check FILE                  # schema, the build's names, canonical
python3 tools/state_examples.py --write                  # rewrite examples/ from the registry
python3 tools/state_goldens.py                           # a level's missing golden files
python -m pytest tests/test_state_schema.py tests/test_state_codec.py tests/test_state_render.py
```

## What is here

| Path | What |
| --- | --- |
| `fm1_state.h` | the record model (§6): record types, the report and its refusal codes, the names a JSON file resolves against, the reader and writer interfaces, the caps |
| `fm1_json.[ch]` | the streaming JSON tokenizer: fed pieces of any size, 168 B of state, no malloc or recursion |
| `fm1_num.[ch]` | exact numbers: decimal to float32 (ties to even) and the shortest decimal back in ECMAScript's form; percent to Q1.14 and back; no `strtod` or `printf` |
| `state_json_read.c` | the tokenizer's events to records, under the context-first rules; 1,416 B of state in all |
| `state_json_write.c` | the canonical writer: holds a document (desktop and simulator only) and writes `tests/state_canon.py`'s layout |
| `state_bin.c`, `state_movy1.c` | the binary container (§8 and §20): written whole, read by pulling through a 64-byte window; movy1 lines as typed items with a raw fallback |
| `fm1_deflate.[ch]` | raw deflate: a pull inflater with the container's 4 KiB window (4,928 B), and a deterministic greedy compressor |
| `state_names.c`, `state_registry.c` | names to uids and back over a build's registries; the pad kits' focus and per-pad parameters until engine API v4 says so |
| `state_print.c` | records as text (`fm1-state records`; P1 prints the same) |
| `fm1_state_mod.h`, `state_mod.c` | the modulation records' one applier to the runtime, and its collector |
| `fuzz/state_fuzz.c` | the fuzz target, with its invariants |
| `schema/` | the JSON Schemas of every kind and of the metadata export (draft 2020-12, `$id`s under `https://ip2k.github.io/lunar-modulator/schema/1/`, published by W1) |
| `examples/` | one file of each kind, canonical, and the metadata export for a few engines |
| `../host/state_tool.c` | `fm1-state` |
| `../host/render_state.[ch]`, `../host/state_clip.[ch]` | fm1-render's `--load` and `--save`; a clip into a set and out |
| `../../tools/lunar_state.py` | P1: the independent Python reader and writer of both encodings |
| `../../tests/fixtures/state/1.0/` | the golden files of level 1.0: JSON, binary twins (`.lunarb`) and records |

The library is C99 with no heap, no stdio and no libm (a test reads its
objects' imports), and is built with `-ffp-contract=off`, so native,
WebAssembly and device builds read every number to the same bits.

## The rules in short

- **One record model, two encodings.** A reader produces records, a writer
  is fed them; conversion goes through the records, so it is lossless both
  ways, and tests hold JSON → binary → JSON and binary → JSON → binary to
  the byte.
- **Canonical JSON** lists members in the schemas' order, one a line,
  parameters by name in uid order, every value of every unit (a missing one
  gets its default, counted), floats as the shortest decimal that reads
  back to the same float32. The C writer, P1 and `tests/state_canon.py`
  give the same bytes, and canonical text reads back and writes back to
  itself.
- **Context first.** A streaming reader resolves a name only once it knows
  whose it is, so `lunar` then `kind` open a file, a unit's `engine` comes
  before its `params` and `pads`, a module's `pos` and `kind` before its
  `params` and `data`, pattern data's `version` before its `hex`, `mod`
  after the units its cables name, and `rack` before `cables`. A file that
  breaks one is refused with its path; `fm1-state canon` reorders a whole
  file first and so puts it right.
- **Names and their fallbacks.** A parameter is read by its name, without
  ASCII case, by abbreviation, then by alias (E2), or as `#UID`, which is
  kept even when this build's engine lacks that uid, so a newer build's
  parameter passes through. A cable's destination on a unit the file does
  not hold (a mod rack's) is kept by name for the applier.
- **Hostile input** meets the caps of the note's §16 while it streams;
  out-of-range values are clamped and counted, unknown members skipped and
  counted, and a refusal says why, where (the JSON path, line and column)
  and quotes the text there.
- **The set** rides as the array of its `movy1` lines, byte-identical to
  the core's export; in binary, the lines the core writes are typed items
  (8 B a note, 3 B a lock) and any other line rides raw.
- `.lunar` is the extension of every JSON kind, the kind the middle word of
  a suggested name (`deep-bass.sound.lunar`); readers trust the content.
  The guide's files and these examples are MIT, as the repository.

## Fuzzing

`fm1-state-fuzz` runs every reader on mutations of seed files and holds
three invariants: pieces of any size never change the JSON reader's records
or verdict; whatever is accepted writes canonical JSON that reads back and
writes back to itself; JSON → binary → JSON is lossless. Binaries are
mutated with their CRCs fixed up, so mutations reach the chunk parsers.

```bash
# the seeded loop, under the sanitizers (Apple clang has no libFuzzer)
make -C engines BUILD=build-asan OPT="-O1 -g" \
  EXTRA="-fsanitize=address,undefined -fno-sanitize-recover=undefined" build-asan/fm1-state-fuzz
engines/build-asan/fm1-state-fuzz -s 7 -n 1000000 tests/fixtures/state/1.0/*.lunar tests/fixtures/state/1.0/*.lunarb

# libFuzzer, with clang on Linux (a Docker host's clang image will do)
make -C engines BUILD=build-fuzz CC=clang CXX=clang++ OPT="-O1 -g" \
  EXTRA="-fsanitize=address,undefined -fno-sanitize-recover=undefined -fsanitize=fuzzer-no-link" \
  build-fuzz/fm1-state-libfuzzer
engines/build-fuzz/fm1-state-libfuzzer -max_len=65536 -jobs=12 -workers=12 CORPUS_DIR
```

A broken invariant writes the input to `fuzz-failure.bin` and aborts. The
pytest suite runs 20,000 iterations of the loop. JSONTestSuite
(nst/JSONTestSuite, MIT) runs in `tests/test_state_codec.py` when it is
cloned to `reference/` (or named by `FM1_JSONTESTSUITE`): every `n_` file is
refused, every `y_` file parses but the three the 32-character number cap
and the U+0000 rule refuse, and the `i_` outcomes are listed there.

## Seams

- **E2** (saveable engines): engine API v4's `FOCUS` and `PER_FOCUS`
  flags and `get_param` (until then `state_names.c` names today's two
  kits, and `fm1-render --save` writes a pad it never set with the
  parameter's default); aliases and enum names (`fm1_state_names_t.aliases`);
  known-ids reasons; pattern data reaching a kind (`state_mod.c` counts it
  as skipped); `fm1-render --meta`, which P1 then reads in place of
  `fm1-state names`.
- **E1** (song core): `dq`, `se` and `sn` ride as raw items in the binary
  set; the begin/item/end refactor of `fm1_seq_import_movy1`, which E1
  edits too, follows it, so a set's records are its lines until then.
- **A1** (app state): the app's collector and applier; `state_mod.c` is
  the modulation runtime's half of it, `host/render_state.cc` the
  desktop's stand-in for the rest.
