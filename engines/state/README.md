# engines/state/ — saved state: the JSON file kinds

The files Lunar Modulator saves, loads, links and ships with the guide:
projects, sounds, effects chains, mod racks, clips and settings, in JSON,
and the export of every parameter's metadata that an editor builds its
controls from. The design, its measurements and the owner's decisions are
in [notes/2026-10-06-state-files.md](../../notes/2026-10-06-state-files.md)
(§7 is the format); the song list's part is in
[notes/2026-10-06-song-and-scenes.md](../../notes/2026-10-06-song-and-scenes.md).

**Status: the format is designed; nothing reads or writes its files yet.**
The C records, the streaming JSON reader and the canonical writer, and the
binary container for the device, are stage E3; the Python reader is P1; the
simulator's Open, Save and launch links are A1 and W1. Stage E2 (2026-10-06)
made the engines saveable and wrote the **metadata export in C**:
`fm1-render --meta` (`fm1_meta.c`, `include/fm1_meta.h`; engines/README.md,
"The parameter metadata export"), with the known ids and aliases it carries
(`fm1_known.c`, written by `tools/gen_known.py` from `engines/known-ids.json`
and `engines/aliases.json`). `examples/metadata.json` is that export cut to
a few engines and kinds, byte for byte.

```bash
make -C engines                                   # the registry the examples are written from
python3 tools/state_examples.py --write           # rewrite examples/ from it
python3 tools/state_examples.py --measure         # the note's §3.4 sizes
python -m pytest tests/test_state_schema.py       # schemas, examples, canonical layout
engines/build/fm1-render --meta                   # the metadata export, canonical JSON
python -m pytest tests/test_engine_metadata.py tests/test_engine_names.py
```

## What is here

| Path | What |
| --- | --- |
| `schema/common.schema.json` | the pieces every kind shares: the head (`lunar`, `kind`, `made`, name and text), sounds, effects, MIDI effects, FM6 voices, the modulation rack and matrix, the view, the `movy1` lines |
| `schema/project.schema.json` | a project: session, four sounds, master slots, FM6 voices, modulation, the set, the view |
| `schema/sound.schema.json` | one sound with its inserts, MIDI effects, voices and the modulation that touches only it |
| `schema/fx.schema.json` | an effects chain |
| `schema/mods.schema.json` | a mod rack and its cables |
| `schema/clip.schema.json` | one clip, as `movy1` lines |
| `schema/settings.schema.json` | device preferences |
| `schema/metadata.schema.json` | the parameter metadata export: engines, effects, MIDI effects and modulation kinds with every parameter's uid, name, range, unit, page and knob, flags and entries; sources, units and ports; FM6's voice fields; keys; known ids; the reader's caps |
| `examples/` | one file of each kind, canonical, and the metadata export for a few engines (the golden file `fm1-render --meta` is held to) |
| `fm1_meta.c` | the metadata export (`include/fm1_meta.h`), in the canonical layout, written as it goes |
| `fm1_known.c` | the ids a build may lack and the old names of renamed parameters and entries (`include/fm1_known.h`), written by `tools/gen_known.py` |

The schemas are JSON Schema draft 2020-12. Their `$id`s are under
`https://ip2k.github.io/lunar-modulator/schema/1/`, where stage W1 will
publish them; until then they live here. They check structure, ranges and
lengths; the build's names come from the metadata export.

## The rules in short

- A file is one JSON object that opens with `"lunar": "1.0"` (the format
  level it needs) and `"kind"`. Sounds, effects and modules give their
  parameters by name, in uid order, with `"#UID"` for a parameter the
  writer cannot name and an ENUM by its entry's name.
- The set rides as the array of its `.movy1` lines, so it stays
  byte-identical to Movy's export.
- Canonical files list members in the schemas' order, one a line, with
  every value of every unit, and floats as the shortest decimal that reads
  back to the same float32. `tests/state_canon.py` is the reference that
  every writer must match byte for byte.
- `.lunar` is the extension of every kind; the kind is the middle word of
  a suggested name (`deep-bass.sound.lunar`). Readers trust the content.
- The guide's files and these examples are MIT, as the repository.
