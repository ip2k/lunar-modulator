# Saved state, files and launch links: the design (2026-10-06)

**Why.** The owner, 2026-10-06: "Make the block diagrams sooner, and work on
the song-list editing, patch / project / sequence / effect rack / sound
stuff and opening the simulator at a given state / injecting state into it
for the firmware now." The files will ship with the illustrated beginner
guide (web and PDF), whose missions offer downloads and "Launch in the
simulator" links, and with a 4-minute song that plays hands-free from the
song list. The song list and scenes are in the companion note,
[2026-10-06-song-and-scenes.md](2026-10-06-song-and-scenes.md).

**What this is.** The design, with the owner's decisions (§19, 2026-10-06):
**every recommendation is adopted except ST2, and the readable format is
JSON**, not the mod script's line style. A browser editor of sounds,
modulation and effect chains follows (§18), so the JSON is shaped for it,
and the parameter metadata it builds its controls from is exported from C
(§7.7).

**Built so far:** the JSON Schemas of every file kind and of the metadata
export, with example files that validate (`engines/state/schema/`,
`engines/state/examples/`, held by `tests/test_state_schema.py`). Nothing
reads or writes these files yet; the stages are in §18, and the owner works
"ask per stage".

Two proposals were written first and judged here, dimension by dimension
(§3):
- **design A**, firmware-first: one chunked binary container read by a
  1 KiB push parser;
- **design B**, interchange-first: one text format in the mod script's
  style, deflated on the device.

This note keeps the best of both, with JSON in the place of B's text.
Neither proposal is committed; what survives is here.

**The one rule holds throughout.** Nothing here is sent to or written on
the owner's FM-1. The SysEx protocol (§15) is for our own firmware. Its
host tool refuses any unit that is not ours, and it is not built in this
plan. Flash storage (§14) is compiled out until the dump-and-restore gate
passes on the unit in question.

**Marks.** `[verified]` was checked for this note on `origin/main` at
`250bf53` (after PR #69, the arpeggiator), by reading the code or by
running a desktop build of it; the JSON measurements (§3.4) and the
examples ran on the registry at `9f96194`, after PR #72 (Glide). `[reported]` names its source; "design A" and "design B"
are the two proposals, measured on `ebb9577`. `[inferred]` is reasoning,
to be checked when built.

## Contents

1. Short answer
2. What exists today
3. A against B, the verdict, and JSON
4. State inventory
5. Gaps that block a faithful save
6. The record model
7. The JSON encoding
8. The binary encoding, for the device
9. Names, uids and versions
10. Loading
11. File kinds
12. The simulator: open and inject
13. The guide, the manual and block diagrams
14. The device: user data in flash (gated)
15. The device: SysEx transfer (design only, gated)
16. Hostile input
17. Tests
18. Build plan
19. Owner decisions

## 1. Short answer

- **One record model, two canonical encodings.** Every saved thing is a
  stream of typed records (§6), defined once in C.
  - **JSON** is for people and programs: downloads, links, browser
    storage, the guide's files in git, and the coming web editor (§7).
    Sounds, effects, the rack and the matrix are structured objects with
    parameters by name; the sequencer's set rides as the array of its
    `movy1` lines, so it stays byte-identical to Movy's export.
  - **The binary container** is for the device: flash and SysEx. It has a
    32-byte header, a directory, a CRC32 per chunk, and critical and
    ancillary chunk tags. Its parser needs about 1 KiB of RAM (§8).
  - Conversion goes through the records, so it is lossless both ways.
    Golden files pin both encodings (§17).
  - **Canonical JSON** has a fixed member order, one member a line, and
    floats as the shortest decimal that reads back to the same float32, so
    files diff cleanly and every writer (C, Python, the browser) produces
    the same bytes (§7.2).
  - **JSON Schemas** (draft 2020-12) describe every kind, and the build's
    parameter metadata is exported as JSON, so no editor hard-codes a name,
    a range or a uid (§7.7).
- **Kinds:** Project, Sound, Effects, Mod rack, Clip and Settings in JSON,
  as `.lunar` files. The Set stays `.movy1` and the DX7 bank stays `.syx`
  (§11).
- **A small C reader** of our own streams JSON in pieces with under 256 B
  of state and no malloc, so it fits the firmware too (§7.6).
- **Loads are two-pass and atomic** (§10):
  - pass 1 checks everything and changes nothing: engines, RAM at
    44,118 Hz, rack room, pools and FM6 slots;
  - pass 2 applies;
  - a refusal says why and changes nothing;
  - a partial load happens only when the user picks "load without …",
    and the report names what was left out;
  - over budget is always refused (owner, 2026-10-05).
- **The simulator opens and injects state** (§12) through:
  - `?load=` for same-origin guide files;
  - `#lunar=` for small inline states (deflated JSON);
  - hints: `into`, `view`, `hl`, `play` and `entry`;
  - an `?embed=1` postMessage API, same origin only, whose `query` returns
    the state's JSON, the same text a save writes;
  - Open, Save and drop;
  - IndexedDB, with a whole-project autosave and Undo load.
- **Blockers found in the code** (§5):
  - Drums' and Sophie's per-pad values cannot be read back;
  - list entry names are not pinned;
  - `movy1` drops the default quantize;
  - the mod dump cannot write a lock uid;
  - Register's locked loop has no data;
  - FM6's bank cannot be exported;
  - the RAM meter counts at the browser's rate.
- **Movy deviations** (owner, 2026-10-06): all four adopted, each with
  compat mode keeping Movy's behaviour: a hand launch detaches the song
  and keeps its list (SG1), a count-in does not use up bar 1 (SG2), a
  stopped Capture or REC with a song is fixed (SG12), and the sequencer's
  RNG is reseeded on load (ST11).
- **Build** (§18):
  - now, `engines/` and `tools/` only, beside the UI colour and fonts
    stage: E1 song core, E2 saveable engines (with the metadata export),
    E3 records and codecs, P1 the Python reader;
  - after that stage: A1 app state, W1 the page, S9+ the Session view and
    the Song page;
  - then a new train, the **advanced web-based editor** beside the
    simulator, with its own design stage (X0);
  - the device's two come last: D1 needs only the harness, D2 the dev
    kit, and the gate before anything on an FM-1.
- **Block diagrams sooner** (§13.2):
  - the song note's state diagrams are ready for the diagram lane now;
  - a signal-flow diagram generator reads the JSON files in Python, so it
    waits for neither the C loader nor the app stages.

## 2. What exists today

| Thing | Where | Today [verified] |
| --- | --- | --- |
| `movy1` set text | `engines/seq/seq_persist.c` | Byte-identical to Movy. Writes `bpm swing link sg tk pm ps au rt cl cp lk tg`; `rt` is our only addition, outside compat mode. No `metro`, no `dq`. Unknown lines are ignored on import |
| `--mod` script | `engines/host/mod_script.c`, dump in `sim/web/src/fm1_mod_ui.c` | `seed`, `mod`, `slot … amt= ofs= via= pol= curve= [voice] [off]`. A slot with a lock uid (MG6) is not written: `fm1_mod_ui_slot_line` returns 0 for it. Per-voice slots are written as `voice` since MG9 (PR #68). Amounts as `%.12g` |
| Verb scripts | `engines/host/seq_script.c` | Timed Movy verbs, including `metro`, `dq` and `tdrum`. Tests only |
| `.syx` | `fm1_dx7_read_sysex` | Load only, into FM6's 32 user slots, from the picker or a drop. No export |
| The page | `sim/web/www/app.js` | No storage, no download, no URL parameters. The drop handler loads `.syx` only |
| The wasm | `sim/web/src/fm1_web.c` | One text buffer, `g_text[65536]`, used by verbs, mod lines and `.syx`. No set import or export (`fm1_app_seq_import` exists in C, S10 planned the export) |
| RAM meter | `fm1_app_ram` | Instance sizes at the **host's** rate, against `FM1_APP_RAM_BUDGET` 387,924 B |
| Parameter metadata | `fm1-render --list`, `--list-mod` | JSON of every engine's, effect's, MIDI effect's and mod kind's parameters (uids, ranges, flags, units, pages, entries), and the mod sources, units and ports: most of the metadata export (§7.7) |
| Schemas and examples | `engines/state/`, `tests/test_state_schema.py` | The JSON Schemas of every kind and of the metadata export, and example files (this branch). Nothing reads them yet |

`fm1_seq_export_movy1` returns the full length and writes only what fits
[verified: `fm1_seq.h`], so a set too large for the buffer is detected, not
cut short. A set with every pool full exports to 53,208 B [reported:
docs/15 §2.7] or 63,035 B with design A's fill [reported: design A]. Both
fit 65,536 B. A full project's JSON, about 170 KB [inferred: §16], does
not; A1 grows the buffer to 256 KiB.

## 3. A against B, the verdict, and JSON

### 3.1 A measurement that settles the size question

The two proposals measured different "typical" songs: A's had 1,196 notes,
B's had 18 clips of random pitches. For this note, a set shaped like the
guide's song was generated and run through the core:
- 6 tracks, 7 scenes, 40 clips;
- 1,444 notes and 160 locks;
- drums repeating per bar, a bass riff, chords, a two-bar melody;
- the song list of the companion note (§9 there).

`fm1-seq --seq` imported it, and its export was the same set [verified]. The
only difference was a track whose selected slot was empty: it fell back to
its lowest clip, which is Movy's rule.

| Encoding | Bytes | deflate-raw, 4 KiB window | 1 KiB window |
| --- | --- | --- | --- |
| `movy1` text | 26,958 | 2,542 | 5,849 |
| Binary records (A's layout: 8 B a note, 3 B a lock) | 13,535 | 2,087 | — |

[verified: Python, zlib level 9, 2026-10-06]

Real music repeats, so it compresses about tenfold. **Compression matters
far more than text against binary**: compressed, the two differ by 20 %.
A 1 KiB window loses most of the gain; 4 KiB keeps it.

### 3.2 Dimension by dimension

| Dimension | A: binary container | B: text, deflated on the device | Better |
| --- | --- | --- | --- |
| Firmware RAM to load | About 1 KiB of reader state, no heap, no pointers into the input [inferred: A's layout] | A 4 KiB inflate window, 1–2 KiB of tables and a streaming tokenizer: a `cl` line reaches about 12 KB [inferred: B] | A |
| Firmware code | One binary codec | A tokenizer, a strict number parser, a shortest-float printer, name and alias tables, inflate, and deflate to save compactly | A |
| Flash per project | 13.5 KB raw, 2.1 KB deflated | 27 KB raw (stored blocks when RAM is short), 2.5 KB deflated | Even once compressed (§3.1) |
| Robustness | CRC32 per chunk, lengths and counts checked before use, criticality in the tag | One CRC32 per slot, a strict grammar, line and token caps | A: its bounds are simpler to prove; B is adequate |
| Forward compatibility | Chunk versions, critical and ancillary tags, unknown keys skipped | `needs lunar=1.N`, unknown lines skipped and counted, an alias table | Both. Uids survive a rename; names survive a mistake in a uid |
| Guide and git | Needs a second, text form, compiled through the app | The file is the text; a turned knob is a one-line diff | B |
| Links | A project is about 20 KB of base64 uncompressed; A capped its inline links at 16 KiB | 3–5 KB of base64 for a typical project | B |
| Cost to build | A binary codec plus a text form for git: two codecs either way | One codec plus compression | B now; A's codec when the device needs it |
| Tests | `movy1` ⇄ binary byte equality; truncation and bit-flip sweeps | `save(load(f)) == f`; extracted blocks run in Movy and fm1-render | Both, combined (§17) |

### 3.3 The verdict, and the owner's change

- **The interchange is JSON** (owner, 2026-10-06, ST2). The judgement of
  §3.2 stands, with JSON in the place of B's line format (`lunar1` in this
  note's first draft): everything a person or a program touches is JSON,
  built first: guide files, links, downloads, git and the web editor. The
  device has no storage before the gate anyway.
- **A's container is the device's encoding.** On the device it is lighter
  in RAM and code, and the device never formats a float as text. Its codec
  is built in an engines-only stage, before any device stage.
- **One record model joins them.** Each encoding is a reader and a writer
  of the same records, so conversion is lossless by construction and
  tested both ways. Only the desktop tools and the simulator carry the
  JSON writer; the firmware links the binary codec, and may link the JSON
  reader (§7.6), never a writer.
- **Both may compress.** A link deflates the JSON. A binary chunk may be
  stored deflated with a window of at most 4 KiB, which the device can
  inflate in about 6 KiB of transient RAM [inferred].
- **Changed from each:**
  - A's name tables inside the binary are dropped; the JSON carries the
    names;
  - A's two-letter link key is renamed `#lunar=`, because the naming rule
    forbids that abbreviation;
  - B's JavaScript reader for mission checks is not needed: the file is
    JSON, and the embed API's `query` returns it (§12.4);
  - B's partial-load refusal gets A's "load the rest" as an explicit
    choice (§10.3);
  - B's line grammar (`#!` first line, `NAME=VALUE` tokens, `_` for
    spaces, `%XX` escapes, comments) is gone. The `--mod` script stays
    what it is: `fm1-render`'s input and the simulator's replay log.

### 3.4 JSON, measured

The guide-like project: §3.1's set at the app's 8 tracks (26,976 B of
`movy1`), four sounds (a 16-pad Drums kit; Shapes with Filter and Drive
inserts; Macro with the arpeggiator on; FM6 with Echo and one user voice),
Hall and Limit on the master slots, the default rack's five modules and
four cables. It was written in the canonical layout of §7.2 from today's
registry, with every value of every unit.

| Encoding | Bytes | deflate-raw, 32 KiB window | 4 KiB window | `#lunar=` link |
| --- | --- | --- | --- | --- |
| JSON, canonical layout (files, git) | 38,385 | 4,694 | 4,772 | — |
| JSON, compact (links) | 32,637 | 4,404 | 4,465 | 5,872 characters |
| of which the set's lines | 27,199 | — | — | — |
| everything but the set | 5,440 | 1,715 | — | — |
| Binary, a prototype of §8's layout | 16,308 | 3,172 | 3,192 | (4,230) |

[verified: `tools/state_examples.py --measure`, Python's zlib at level 9,
2026-10-06, on the registry at `9f96194`, after PR #72 (Glide); the binary
is a prototype of §8's layout, not E3's codec, so its size is a guide]

- **JSON costs bytes before compression, little after.** Deflated, the
  project is 1.4 times the binary as a link (4,404 B against 3,172 B) and
  1.5 times as a file, about 1.2–1.5 KB more.
- **The set is 83 % of the compact project**, and in JSON it is Movy's own
  text plus 223 B of quotes and commas, so it compresses as §3.1's `movy1`
  does.
- **A 4 KiB window** costs about 2 % against 32 KiB; 1 KiB nearly doubles
  the size (8,680 B).
- **Lines:** 605 in the canonical layout, one value each outside the set.
- **Links:** a sound with an insert and an LFO is 688 characters
  (`lunar1`'s was about 370 [reported: design B]), a 16-pad kit 538, the
  guide-like project 5,872: all far under the 32 KiB cap (§12.4).
- **Files:** the examples are 0.2–12 KB (§11).

## 4. State inventory

Everything a user can create or change, and where it goes. RAM figures are
instance sizes at 44,118 Hz [reported: designs A and B, measured on
`ebb9577`] unless marked.

| State | Lives in [verified] | Record (§6) | Saved |
| --- | --- | --- | --- |
| Engine per sound unit (4; Sound 1 never empty) | `fm1_app_unit_t` | unit | project, sound |
| Its parameters (≤ 32, `FM1_APP_MAX_PARAMS`) | `value[32]` | param | project, sound |
| Per-pad values of pad kits: Drums 8 × 16, Sophie 17 × 16 | inside the engine only | param with a focus | **cannot be read today** (§5.1) |
| Inserts, 2 per sound; master slots, 2 (4 ordered, plus 2 shared sends, planned) | units 6–13 and 1–2 | unit, param | project, sound (inserts), effects |
| Level per sound, 0–100 % | `level[4]` | level | project, sound |
| Arpeggiator per sound: on, about 25 parameters [reported: design B] | `arp_value[4][32]`, `fm1_mfx_t` | unit (`sndK.mfx1`), param | project, sound |
| Latched arp keys | the arp instance | — | not saved: live |
| FM6 user bank: 32 VCED voices, names, loaded flags | `fm1_app_dx7_t` | dx7 voice | project (all loaded), sound (those it uses), `.syx` bank |
| Mod runtime seed | `mod_seed` | mod seed | project, mod rack |
| Rack: 8 positions, kind and parameter bases | `fm1_mod_t`, 26,192 B with its arena since MG9 [reported: owner's answer, 2026-10-06] | mod position, mod param | project, mod rack, a sound's subset |
| Matrix: 32 slots (source, via, unit, flags, destination uid, amount, offset, lock uid) | `fm1_mod_t` | mod slot | as the rack |
| Pattern data (Curves, Draw, Scenes, Motion recordings) | `get_data` / `set_data`; no kind has any yet | mod data | as the rack; Motion's recordings with it (owner) |
| Cables switched off by a kind change, kept to restore | `fm1_mod_ui_t` | — | not saved: UI memory |
| Set: tempo, swing, link, song list, 8 tracks, 64 clips, notes, locks, trig rows | `fm1_seq_t` | set items | project, `.movy1` |
| Default quantize | `default_quant` | set item (`dq`, new) | project, `.movy1` |
| Song end mode, scene names | new (song note) | set items (`se`, `sn`) | project, `.movy1` |
| Metronome, count-in click option, full-velocity toggle | `metronome`, UI | setting | device settings (§19 ST10) |
| Drum flag per track (no clip transpose on a drum track, Movy's rule) | `sq_track_t.drum`, set by the `tdrum` verb; nothing in `sim/web/src` sends it yet [verified] | — | derived from the routed engine being a pad kit, not saved (ST10) |
| Sequencer RNG | `rng`, seeded with a constant at init | — | reseeded on every load; compat mode lets it run on, as Movy (§19 ST11) |
| Clipboards, Capture ring, transport, record arm, playing position | core | — | not saved, as in Movy |
| Current sound, octave, transpose | `sound`, `octave`, `transpose` | session | project |
| Project key (one per project; fixed C major today) | planned | session | project |
| MASTER | a potentiometer on PB6 | — | not saved: the pot decides |
| View: mode, page, FX slot, track, bar, RACK and MATRIX selection | `fm1_app_t`, `fm1_seq_ui_t`, `fm1_mod_ui_t` | view | project and guide files, as a hint |
| MIDI in channel, clock follow, MIDI out opt-in (browser) | page, later the device | setting | settings only, never from a file or link |

A typical guide-song chain needed 298,596 B, 77 % of the budget, before
MG9 grew the mod runtime by about 3 KB [reported: design A, at `ebb9577`].
Its saved part is about 16 KB of binary or 38 KB of JSON, 3–5 KB deflated
(§3.4). **The RAM is in the instances, not the settings**: the loader's
first job is the RAM check, not parsing.

## 5. Gaps that block a faithful save

1. **Per-pad values are write-only** [verified: `fm1_engine.h` has
   `set_param` and no getter; `drums.cc`: "each of the 16 pads keeps its
   own Tune, Decay, Level, Tone, Snap, Sweep, Drive and Model"; Sophie
   likewise].
   - The app's `value[]` holds what it last sent, which is the focused
     pad's.
   - So a saved kit would lose every other pad, and after Pad moves, a
     knob shows a stale value [inferred].
   - Fix (ST7): two flag bits and an optional getter, in API v4.
     - `FM1_PARAM_FOCUS` (0x0100) goes on Pad.
     - `FM1_PARAM_PER_FOCUS` (0x0200) goes on each per-pad parameter.
       Bits 0x0100–0x8000 are free [verified].
     - `float (*get_param)(const void *self, uint16_t index, uint8_t
       focus)` reads a pad's value without moving the focus.
   - A load replays through plain `set_param`: Pad = k, that pad's
     values, and so on, then Pad = the saved focus.
   - Moving Pad leaves sounding voices intact [reported: engines/README.md].
2. **List entries are pinned by index only** [verified:
   `tests/fixtures/param-uids.json` pins names, types, uids and flags,
   not entry names].
   - An entry inserted mid-list moves every saved index and every 7-bit
     lock on it.
   - Fix: an `enum-names` fixture. Entries are append-only, and renames
     are aliases.
3. **`movy1` drops the default quantize** [verified: no `dq` line].
   - Fix: `dq PCT` as an FM-1 line, written outside compat mode and only
     when it is not the default, as `rt` is.
   - Movy ignores unknown lines [verified: `seq_persist.c` header].
4. **The mod dump cannot write a lock uid** (MG6), and it leaves out
   module parameters at their defaults.
   - Fix, in the mod script (the replay log) and in the JSON alike
     (§7.3):
     - a `lock=UID` slot option (a cable's `lock`);
     - `data P VERSION HEX` lines for pattern data (a module's `data`);
     - a full dump that writes every parameter;
     - amounts at the shortest percent that maps back to the same Q1.14
       (`amt=40`, not `amt=40.0024414062`; `"amount": 40`).
5. **Register's locked loop has no data** [verified: `mod_register.c`
   registers no `get_data`/`set_data`].
   - Its seed is saved, so a load replays from the seed. It does not come
     back as the loop the user locked or edited with WRITE.
   - Fix: give Register 32 bits and a length as pattern data (ST12).
6. **FM6's bank cannot leave the module** [verified: a reader and no
   writer].
   - Fix: a VCED → VMEM packer, for `.syx` bank downloads.
7. **The RAM meter counts at the browser's rate** [verified: "each
   engine's instance_size at the host's rate", `fm1_app.h`].
   - Some instances grow with the rate: Comb is 17,840 B at 44,118 Hz and
     19,392 B at 48 kHz [reported: design B, wasm in Node].
   - So a file could load in one browser and be refused in another.
   - Fix: `fm1_app_ram_at(a, 44118)` for loads and for the meter (ST6).
8. **Defaults can drift.** If a file leaves out values at their defaults,
   changing a default later changes old songs. Rule: the canonical
   writers write every value.

## 6. The record model

One C header, `engines/state/fm1_state.h` [inferred: location]. A writer is
a visitor over records, and a reader produces them. The app's collector and
applier (stage A1) are the only code that touches `fm1_app_t`.

| Record | Fields | JSON (§7.3) | Binary chunk (§8) |
| --- | --- | --- | --- |
| info | name (≤ 16 ASCII, the screen's), title and about (UTF-8), author, licence, writer | the top-level `made`, `name`, `title`, `about`, `author`, `licence` | `info` (ancillary) |
| unit | unit code, engine id (≤ 15 of `[a-z0-9-]`), on/off for MIDI effects | a sound's, insert's, master slot's, chain entry's or MIDI effect's `engine` (and `on`) | `UNIT` head |
| param | unit code, uid, focus (none, or pad 1–32), value: f32 base in its unit, or a list index | a member of `params`, or of a `pads` entry | `UNIT` record, 8 B |
| level | sound, percent | a sound's `level` | `UNIT` key-value |
| dx7 | user slot 1–32, loaded, 155 VCED bytes | an item of `dx7` | `DX7V`, 160 B |
| session | current sound, octave, transpose, key root and scale | `session` | `PROJ` key-value |
| mod | seed; position (kind, parameter bases by uid, pattern data); slot (12 B) | `mod`: `seed`, `rack`, `cables` | `MODR` |
| set | the `movy1` items: header, song, track, lane, route, clip, note, lock, trig, `dq`, `se`, `sn` | `set`: the `movy1` lines | `SEQS` |
| clip | one clip's items and the lanes its locks use | `clip`: its `movy1` lines | `CLIP` |
| view | mode and keys | `view` | `view` (ancillary) |
| setting | key, value | a member of `settings` | `SETG` |

Rules:
- **Canonical order of records**: info, session, units and params (by
  role, sound, slot, then uid; pads in pad order, the focus last), levels,
  FM6 voices, mod, set, view. The JSON member order (§7.2) follows the
  schemas; the load order (§10) is fixed whatever either order is.
- **Every value is written.** Floats are written as their exact bits in
  binary and as the shortest decimal that reads back to them in JSON
  (§7.2).
- **No personal data.** No timestamps or user names. `made` gives the
  writer, a version and a commit; `author` is never filled in
  automatically.
- **The set's items** come from a refactor of `fm1_seq_import_movy1` into
  `begin / item / end` calls [inferred: design A §5.3]. The `movy1` text,
  the JSON lines and the binary `SEQS` are three views of one item stream,
  so the clamps, the "lowest real clip" fallback and
  `sq_reseed_empty_clips` stay in one place.
- **The mod records** have one applier. The JSON reader produces them, and
  the mod script parser is refactored to produce the same records instead
  of applying lines, so `fm1-render --mod`, the simulator's replay log and
  a loaded file reach `fm1_mod_set_slot` and friends through one function.

### 6.1 The interfaces between the stages

What each stage of §18 delivers to the next [inferred: names; E3 settles
them, these are the shapes the lanes agree on].

```c
/* engines/state/fm1_state.h */
typedef struct fm1_rec fm1_rec_t;   /* a tagged union: type, unit code, uid, focus,
                                       value bits or index, and small payloads */
typedef int (*fm1_rec_sink_t)(void *ctx, const fm1_rec_t *r);   /* 0 stops */
typedef int (*fm1_src_read_t)(void *ctx, uint32_t off, uint8_t *buf, uint32_t n);
typedef void (*fm1_put_t)(void *ctx, const char *bytes, size_t n);

/* Readers produce records; writers are fed them in canonical order. */
int fm1_state_json_read(const fm1_state_names_t *nm, fm1_src_read_t rd, void *rctx,
                        fm1_rec_sink_t sink, void *sctx, fm1_state_report_t *rep);
int fm1_state_bin_read(fm1_src_read_t rd, void *rctx, fm1_rec_sink_t sink, void *sctx,
                       fm1_state_report_t *rep);
fm1_state_writer_t *fm1_state_json_writer(void *mem, const fm1_state_names_t *nm,
                                          fm1_put_t put, void *ctx);
fm1_state_writer_t *fm1_state_bin_writer(void *mem, fm1_put_t put, void *ctx);
int fm1_state_write(fm1_state_writer_t *w, const fm1_rec_t *r);   /* a sink too */
```

- **Names.** `fm1_state_names_t` maps names to uids and back, built from
  the registries: engines and MIDI effects, mod kinds, ports, system
  sources, ENUM entries, aliases and entry aliases (E2's `enum-names.json`
  and `aliases`). The binary side never needs it. The metadata export
  (§7.7) is written from the same tables, so a name a file may use is a
  name the editor offers.
- **E1 → E3.** E1 adds the song verbs and the `se`, `sn` and `dq` lines in
  `seq_persist.c`, in the formats of the song note §5.6 and of §5.3 here,
  and the RNG reseed on import (ST11). E3 refactors import and export into
  the item stream, without changing a byte of either (every Movy fixture
  and oracle set stays identical).
- **E2 → E3.** Per-pad values readable through `get_param(self, index,
  focus)` and the FOCUS and PER_FOCUS flags (API v4); `enum-names.json`,
  aliases and `engines/known-ids.json`; Register's `get_data` and
  `set_data`; the VCED → VMEM packer; the mod script's `lock=` and `data`
  lines, so the replay log can say everything a file can; and
  `fm1-render --meta`, which writes `metadata.schema.json`'s layout.
- **E3 → A1.** `fm1_app_state_check`, `_load` and `_save` (§12.1) call
  E3's readers and writers with the app's collector (a record visitor over
  `fm1_app_t`) and applier (a record sink with pass 1 and pass 2).
  `fm1-state` (§12.6) uses the readers and writers without the app:
  `canon` is a JSON reader feeding a JSON writer, `pack` a JSON reader
  feeding a binary writer.
- **P1 beside E3.** `tools/lunar.py` reads and writes JSON with Python's
  `json` (duplicate keys refused) in `tests/state_canon.py`'s layout,
  reads and writes the binary container on its own, and checks files
  against the schemas and the metadata. Its records, printed as JSON,
  equal `fm1-state records` for every fixture (§17).

## 7. The JSON encoding

### 7.1 Why JSON, and what it costs

The owner, 2026-10-06: adopt the design, except that the readable format
is JSON. The web editor that follows (§18) edits sounds, modulation and
effect chains in the browser, and builds its controls from metadata (§7.7).
- **What it gives:**
  - every language reads it: `JSON.parse` in the page, `json` in Python,
    `jq` in a shell; the web editor and the guide's mission checks need no
    parser of ours (§12.4);
  - structure instead of a line grammar: a cable is an object with named
    fields, a sound an object with its inserts inside;
  - JSON Schema (§7.7) checks a file in an editor and in CI, and can drive
    a form.
- **What it costs** (§3.4): about a quarter more bytes than `lunar1` raw
  (38 KB against about 30 KB [reported: design B] for a project), 1.4 to
  1.5 times the binary once deflated, and a sound link of about 690
  characters instead of 370.
- **What it keeps from `lunar1`:** names with `#UID` as the fallback,
  every value written, the set verbatim as Movy's lines, a fixed load
  order, and a one-line diff for a turned knob.
- **What it drops:** comments (JSON has none; a mission's prose goes in
  `about` or in the guide beside the file), `_` for spaces and `%XX`
  escapes (JSON strings hold any character), and the mod rack file being
  an `fm1-render --mod` script (A1's harness loads any kind with
  `--load`).

### 7.2 Lexical rules and the canonical layout

**Reading.**
- RFC 8259 JSON: one object, UTF-8 (validated: no overlong forms, no
  surrogate halves, no U+0000), no byte-order mark.
- **Duplicate keys refuse the file** (BAD). In `params`, two keys that
  name one parameter (`Cutoff` and `cutoff`, a name and its alias) are
  duplicates too.
- **Member order is free, except context first:** `lunar` and `kind` open
  the document (after an optional `$schema`); `engine` comes before
  `params` and `pads`; a module's `kind` before its `params` and `data`.
  So a streaming reader always knows whose names it reads, and never holds
  a subtree. A file that breaks this is refused with its path;
  `fm1-state canon`, which holds the whole file, puts it right.
- **Numbers** have JSON's grammar: no `+`, no leading zeros, no `NaN` or
  `Infinity` (JSON has none). The parser is ours, not libc's `strtod`, so
  native, wasm and the device agree bit for bit:
  - a FLOAT parameter or a level: the exact decimal, rounded to the
    nearest float32, ties to even;
  - an integer field (an ENUM index, a position, a slot, a uid, the seed,
    a VCED byte): an exact integer; a fraction or an exponent there is BAD;
  - an amount or an offset: the exact Q1.14 rule of §7.3.
- Members a reader does not know are skipped and counted (§9).

**Writing, canonical.** `tests/state_canon.py` states this layout as code.
The examples equal its output byte for byte, and E3's C writer, P1's
Python writer and the web editor must too.
- Two spaces of indent, `": "` after a key, one member or item a line, LF,
  a final newline.
- On one line: an array of numbers, and the values of `made`, `key`,
  `data`, `from`, `via`, `to` and `view`.
- Members in the order the schemas list them (§7.7); parameters in uid
  order (stable for ever, whatever a table's order); rack positions,
  matrix slots and FM6 voices ascending.
- **A float32 as the shortest decimal** (at most 9 significant digits)
  that reads back to the same bits, formatted as ECMAScript's
  `Number::toString` formats that decimal: `0.41`, `420`, `0.0000015`,
  `5e-7`; `-0` is `0`. A JavaScript writer is therefore
  `String(Number(Math.fround(v).toPrecision(p)))` with the smallest `p`
  that round-trips; Python's is in `tests/state_canon.py`.
- Strings as raw UTF-8; only `"`, `\` and U+0000–U+001F are escaped.
- Every value of every unit, so a changed default cannot move an old file
  (§5.8). `null` for an empty insert, master slot or sound unit.
- No `$schema` (allowed on read, ignored).

**Free text:** `name` is 1–16 printable ASCII, for the screen. `title` (≤ 80
characters) and `about` (≤ 240) are UTF-8; lengths count code points, in
the C reader too. Control characters and bidi overrides are stripped on
read, and the schema refuses them in canonical files.

**Links need not be canonical.** A `#lunar=` link deflates the compact form
(no white space), and any valid file loads.

### 7.3 The document

| Member | Kinds | Holds |
| --- | --- | --- |
| `lunar` | all | the format level the file needs, `"1.0"` (§9) |
| `kind` | all | `project`, `sound`, `fx`, `mods`, `clip` or `settings` (and `metadata`, the export of §7.7, which no loader takes) |
| `made` | all, optional | `{by, version, commit}`, information only; `by` is `simulator`, `firmware`, `desktop`, `editor` or `hand` |
| `name`, `title`, `about`, `author`, `licence` | all, optional | the info record; `licence` is an SPDX id (`MIT` for the guide's files, ST19) |
| `session` | project | `current` 1–4, `octave` −3..3, `transpose` −12..12, `key` `{root, scale}` |
| `sounds` | project | sound units 1–4; Sound 1 is never `null` |
| `sound` | sound | one sound |
| `master` | project | master slots `fx1` and `fx2` |
| `chain` | fx | one to four effects, in order |
| `dx7` | project, sound | FM6 user voices |
| `mod` | project, sound, fx, mods | `seed`, `rack`, `cables` |
| `set` | project | the set's `movy1` lines |
| `clip` | clip | one clip's `movy1` lines |
| `settings` | settings | device preferences |
| `view` | all but settings | where the panel opens |

**A sound** is `{engine, params, pads, level, inserts, midi_fx}`:
- `engine`: its id (`shapes`; FM6 stays `dx7`);
- `params`: every parameter by name, in uid order: an ENUM by its entry's
  name (`"Shape": "Saw Sub"`), a FLOAT in its own unit (`"Cutoff": 420`,
  in Hz);
- `pads`, pad kits only: one object a pad, in pad order, with the PER_FOCUS
  values; `params` holds the rest, the focus (`"Pad": "1 Kick"`) among
  them, applied last (§5.1);
- `level`: percent into the mix;
- `inserts`: two, each `{engine, params}` or `null`;
- `midi_fx`: the chain in front of the sound, mfx1 first, each
  `{engine, on, params}` or `null`; values are kept while it is off.

**Names and their fallbacks** (ST4):
- a parameter the writer's build cannot name is written `"#UID"`
  (`"#12": 0.5`), and read the same way;
- an ENUM entry with no stable name, or one the writer cannot name, is
  written as its index (0-based);
- a reader takes a name exactly, then without ASCII case, then by
  abbreviation, then by alias (§9); a name that resolves nowhere is
  skipped and reported, never guessed.

**FM6 voices** are `{slot, name, ops, globals}`:
- `slot` 1–32 (Patch's `User N`);
- `name`, up to 10 characters, written without trailing spaces;
- `ops`: six arrays of 21 values, OP6 first, in VCED order;
- `globals`: the 19 values before the name.

These are VCED's 155 bytes in order, so a voice leaves as it came. The
metadata export names every field (`R1` … `DET`, `PR1` … `TRNSP`), so an
editor can draw them.

**The modulation runtime**, `mod`:
- `seed`: in project and mod rack files. Sound and effects files leave it
  out, and a merge keeps the project's.
- `rack`: modules by position, ascending: `{pos, kind, params, data}`.
  `data` is a kind's pattern data, `{version, hex}` (Register's locked
  loop after E2).
- `cables`: matrix slots, ascending: `{slot, on, from, via, to, amount,
  offset, polarity, curve, voice, lock}`.
  - `from` and `via`: `{"source": "VEL"}`, a system source by the
    registry's name, or `{"module": 3, "port": "Env"}`, a module output by
    position and port name (or 1-based index). `via` is `null` for none.
  - `to`: `{"unit": "snd2.fx1", "param": "Cutoff"}`, `{"module": 1,
    "param": "Rate"}` or `{"module": 2, "gate": "Gate"}`.
  - `amount` and `offset`: percent. The reader computes q = round(percent
    × 16384 / 100), ties away from zero, in exact arithmetic on the
    decimal. The writer gives the shortest decimal, with at most three
    places, that maps back (`35`, not `34.99755859375`). Every Q1.14 value
    has one, and the mod script's float rule maps it back too [verified:
    Python, all 32,769 values, `tests/test_state_schema.py`].
  - `polarity` is `auto`, `uni`, `bi` or `inv`; `curve` is `lin`,
    `square`, `cube`, `root`, `cbrt`, `exp`, `log` or `s`; `voice` runs the
    cable per voice (MG9); `lock` is the base uid of the slot's own AMT and
    OFS for locks (MG6), 0 for none.

**Units** carry the mod script's names [verified:
`fm1_mod_script_unit_name`], with Sound 1 written `snd1`:
- in project and mod rack files: `snd1`–`snd4`, `snd1.fx1` … `snd4.fx2`,
  `fx1`, `fx2` and `host`;
- in a sound file: `snd` is the target sound and `snd.fx1`, `snd.fx2` its
  inserts; `host` reaches only `Pitch`, the target sound's pitch; the
  per-sound sources `S1NOTE` … `S1RTRG` mean the target sound's;
- in an effects file: `fx1`–`fx4` are the chain's own positions;
- later: `fx3`, `fx4`, `send1` and `send2` with the master chain stage,
  and `sndK.mfxJ` when cables reach MIDI effects.

**The set** is the array of its `.movy1` lines (owner, 2026-10-06). Joined
with LF and ended with one, they are the `.movy1` file the core exports,
byte for byte, trailing spaces included; the first is `movy1`. The FM-1
lines `rt`, `dq`, `se` and `sn` are there outside compat mode, as in a
`.movy1` file. So `set` to `.movy1` is a join, and a set that uses no FM-1
feature stays byte-identical to Movy's export [verified: the example
project's set is the core's export, `tests/test_state_schema.py`].

**A clip** is its `movy1` lines at track 0 and slot 0: the `au` lines of
the lanes its locks use, then its `cl`, `cp`, `lk` and `tg` lines.

**The view** is one line, `{"mode": "seq", "track": 3, "bar": 2}`: modes
`home`, `fx`, `glo`, `seq`, `session`, `song`, `rack`, `matrix` and
`chain`; keys `sound`, `page`, `unit`, `track`, `bar`, `panel`, `pos`,
`slot` and `entry`, 1-based.

**Settings** are `metronome`, `count_in_click`, `full_velocity` and
`midi_in_channel` (0 for every channel); A1 settles the list. Never MIDI
out (§12.2).

### 7.4 Examples

A sound, `engines/state/examples/deep-bass.sound.lunar`: 1,471 B, 878 B
compact, a 688-character link [verified]:

```json
{
  "lunar": "1.0",
  "kind": "sound",
  "made": {"by": "hand"},
  "name": "DEEP BASS",
  "title": "Deep space bass",
  "about": "Mission 2.3: open the filter with KNOB2 until the bass growls.",
  "licence": "MIT",
  "sound": {
    "engine": "shapes",
    "params": {
      "Shape": "Saw Sub",
      "Timbre": 0.41,
      "Color": 0.5,
      "Attack": 0,
      "Release": 0.2,
      "Volume": 0.7,
      "Glide": 1,
      "Voice Mode": "Poly"
    },
    "level": 80,
    "inserts": [
      {
        "engine": "filter",
        "params": {
          "Type": "Ladder",
          "Cutoff": 420,
          "Resonance": 0.3,
          "Drive": 0,
          "Mode": 0,
          "Morph": 0,
          "Mix": 1,
          "Level": 1
        }
      },
      null
    ],
    "midi_fx": []
  },
  "mod": {
    "rack": [
      {
        "pos": 1,
        "kind": "lfo",
        "params": {
          "Rate": 0.25,
          "Shape": "Triangle",
          "Depth": 1,
          "Mode": "Free",
          "Phase": 0,
          "Sync": "Off",
          "Width": 0.5
        }
      }
    ],
    "cables": [
      {
        "slot": 1,
        "on": true,
        "from": {"module": 1, "port": "Out"},
        "via": null,
        "to": {"unit": "snd.fx1", "param": "Cutoff"},
        "amount": 35,
        "offset": 0,
        "polarity": "auto",
        "curve": "lin",
        "voice": false,
        "lock": 0
      }
    ]
  },
  "view": {"mode": "home", "sound": 1, "page": 1}
}
```

A pad kit writes the kit-wide values with the focus, then each pad in
full (from `first-orbit.lunar`, abridged):

```json
{
  "engine": "drums",
  "params": {
    "Pad": "1 Kick",
    "Kit": "Punch",
    "Accent": 0.6,
    "Volume": 0.7
  },
  "pads": [
    {
      "Tune": 0,
      "Decay": 0.34,
      "Level": 0.9,
      "Tone": 0.52,
      "Snap": 0.5,
      "Sweep": 0.5,
      "Drive": 0,
      "Model": "Kit"
    },
    …
  ],
  …
}
```

A cable switched off, scaled by velocity, into the host's amp:

```json
{
  "slot": 4,
  "on": false,
  "from": {"module": 2, "port": "Out"},
  "via": {"source": "VEL"},
  "to": {"unit": "host", "param": "Amp"},
  "amount": -12.5,
  "offset": 0,
  "polarity": "uni",
  "curve": "square",
  "voice": false,
  "lock": 0
}
```

The other examples are a project (`first-orbit.lunar`), an effects chain,
a mod rack, a clip, settings and the metadata export.

### 7.5 Diffs in git

- One member a line, so a turned knob, a moved cable end or a new module
  is a diff of a line or a few.
- A `movy1` clip is still one line (Movy's format; up to about 12 KB).
  `.gitattributes` gives `*.lunar` and `*.movy1` a `textconv` through
  `tools/lunar.py explode`, which prints one note a line for review.
- CI checks that every guide and golden file is canonical (`canon(f) ==
  f`), so a hand edit that breaks the layout is caught before review.

### 7.6 The C reader (E3)

- **Our own streaming pull parser**, `engines/state/fm1_json.[ch]` (MIT):
  - `fm1_json_feed(p, bytes, n)` takes pieces of any size (a SysEx page, a
    flash read, the whole buffer) and yields events: an object or array
    begins or ends, a key, a string (a long one in pieces), a number (as
    its text), `true`, `false`, `null`;
  - its state is the nesting stack (depth ≤ 8), a 64 B buffer for keys
    and short strings, a 32 B number buffer, the UTF-8 decoder's state and
    byte, line and column counters: under 256 B whatever the file's size,
    with no malloc and no recursion [inferred];
  - a long string (a `movy1` line, up to 16 KiB) goes out in pieces to the
    `movy1` item parser, which tokenizes as it goes, so no 16 KiB buffer
    exists;
  - its number parser is exact: decimal to float32 by a fast path (up to 7
    digits and a power of ten that float32 holds exactly, one correctly
    rounded operation) and a big-integer path otherwise, plus exact
    integers. It is tested against an exact reference in Python's
    `fractions`.
- **On top, the record builder** turns events into records (§6) under the
  context-first rule. Pass 1 and pass 2 (§10) both stream the source
  through it.
- **jsmn** (MIT), which the owner allowed, was weighed and is not linked:
  it is small, but it needs the whole text in one buffer and a token array
  (16 B a token in its default layout [inferred]; 1,098 tokens for the
  guide-like project [verified: counted]), so that project would need
  about 55 KB of RAM where ours needs 256 B. It may serve as a second
  opinion in the fuzz harness.
- **The device** reads binary (ST1). The reader is small enough to link
  there too, so D1 may let our firmware take JSON over SysEx and convert
  it on the device; the host tool converts to binary by default. The
  device never writes JSON (no float printer in the firmware).
- **Hostile input:** §16's caps, enforced while streaming; libFuzzer with
  ASan and UBSan; the JSONTestSuite corpus (nst/JSONTestSuite, MIT): every
  `y_` file parses, every `n_` file is refused, every `i_` file has a
  documented outcome (§17).

### 7.7 The schemas and the parameter metadata

**JSON Schemas** (draft 2020-12) are in `engines/state/schema/`:
`project`, `sound`, `fx`, `mods`, `clip`, `settings`, `metadata`, and
`common` for the shared pieces.
- Their `$id`s are under `https://ip2k.github.io/lunar-modulator/schema/1/`.
  W1 publishes them there; until then they live only in the repository.
- They check structure, ranges and lengths, not the build's names, which
  come from the metadata. P1's `tools/lunar.py schema` can generate a
  build schema from the metadata export (each engine's names, entries and
  ranges) for the web editor and CI.
- **A schema describes its format level.** A minor level adds members to
  it. A file of a newer level fails an older schema, while an older reader
  still loads it, skipping and counting what it does not know (§9).
- The canonical member order is the order of each schema's `properties`.

**The parameter metadata export** (`metadata.schema.json`, kind
`metadata`, at the same `lunar` level) is what an editor builds its
controls from:
- every engine, audio effect, MIDI effect and modulation kind, with each
  parameter's uid, name, abbreviation, type, range, default, unit, page and
  knob, flags (LOG, and API v4's FOCUS and PER_FOCUS among them), ENUM
  entries, aliases and entry aliases;
- the system sources, the cable units, each kind's ports, the host's
  parameters, the polarities and the curves;
- FM6's VCED fields, the project keys, the known-but-absent ids with
  their reasons (`engines/known-ids.json`), and the file caps (§16);
- the build: the engine and mod API versions, the rate files are checked
  at, the RAM budget, and whether `FM1_GPL_MODS` is on.

C writes it, so an editor never hard-codes a name or a range:
`fm1-render --meta` on the desktop (E2), and a wasm call in the simulator
(A1). It is versioned by its `lunar` level; a minor level adds members and
never moves one.

Today's `fm1-render --list` and `--list-mod` print most of it [verified].
`tests/test_state_schema.py` turns them into the export's layout and
validates the result, so an engine whose names or ranges the format cannot
carry fails CI now, the GPL lane's included. The full export is 172,499 B
canonical, 14,086 B deflated [verified].
`engines/state/examples/metadata.json` is the export for Shapes, Drums,
Filter, the arpeggiator, the LFO and the envelope.

## 8. The binary encoding, for the device

Little-endian, read byte by byte (never by cast), so alignment and byte
order do not matter. CRC-32 is zlib's (`0xEDB88320`, reflected), so
Python's `zlib.crc32` checks a file.

### 8.1 Header, 32 bytes

| Offset | Size | Field | Rule |
| --- | --- | --- | --- |
| 0 | 8 | magic `89 4C 75 6E 61 72 0D 0A` (`\x89Lunar\r\n`) | Exact. The high byte and the CR LF catch 7-bit and line-end damage, as PNG's magic does |
| 8 | 1 | major = 1 | Another value: refuse |
| 9 | 1 | minor, the `needs` level | Higher than the reader's: refuse (§9) |
| 10 | 1 | kind: 1 project, 2 sound, 3 fx, 4 mods, 5 clip, 6 settings, 7 set, 8 DX7 bank | Others: refuse |
| 11 | 1 | flags (0) | Unknown bits are ignored |
| 12 | 2 | header bytes (32) | 32–256; skip the extra |
| 14 | 2 | chunk count | 1–32 |
| 16 | 2 | directory entry bytes (20) | 20–64 |
| 18 | 2 | reserved, 0 | — |
| 20 | 4 | total bytes | ≤ 96 KiB, or the device's staging size |
| 24 | 4 | writer: 1 simulator, 2 firmware, 3 desktop; then version major, minor, patch | Information only |
| 28 | 4 | CRC-32 of bytes 0–27 | Must match before any length is used |

### 8.2 Directory and chunks

The directory is `count × 20 B`, then a CRC-32 of the directory: per
entry, `tag[4]`, `u16 version`, `u16 flags`, `u32 offset`, `u32 length`,
`u32 CRC-32 of the stored bytes`.
- Chunks follow in directory order, each 4-aligned with zero padding.
  Offsets ascend, nothing overlaps, and the last chunk ends at `total`.
  So the file is one forward stream: a SysEx receiver or a flash reader
  never seeks back.
- **Criticality is in the tag**, as in PNG. An upper-case first letter
  (`UNIT`) is critical: a reader that does not know it refuses the file. A
  lower-case one (`view`) is ancillary: skipped and reported.
- **Flag bit 0, DEFLATED.** The stored bytes are a `u32` unpacked length,
  then raw deflate with a window of at most 4 KiB.
  - Writers in the simulator and the desktop tools compress a chunk when
    that saves at least a quarter.
  - The device writes chunks uncompressed until a compressor is shown to
    fit (ST1).
- **Versioning.** A new field goes at a chunk's end, and the chunk version
  goes up; an older reader ignores the tail. A change an old reader would
  misread needs a new tag. The major changes only with the container.

### 8.3 Chunks

| Tag | Holds | Layout (summary) |
| --- | --- | --- |
| `info` | name, title, about, author, licence, writer | key-value records |
| `PROJ` | session: current sound, octave, transpose, key | key-value records |
| `UNIT` | one unit | role (sound, insert, master, send, MIDI effect), sound, slot, flags (bit 0: on), id, then `u16 count` × `{u16 uid, u8 focus (0xFF none), u8 type (0 f32, 1 list index), u32 value}`, then key-value (1 level) |
| `DX7V` | one FM6 user voice | `u8 slot, u8 flags, u8 vced[155]`, padded to 160 B |
| `MODR` | the mod runtime | seed; per position `guid, n × {uid, f32}, data version, data`; 32 slots of 12 B, including the lock uid |
| `SEQS` | the set | a field-for-field image of the `movy1` items, so `movy1` → `SEQS` → `movy1` is byte-identical |
| `CLIP` | one clip | `SEQS`'s clip layout, plus the lanes its locks use (labels and bases) |
| `view` | the view hint | key-value records |
| `SETG` | device settings | key-value records |

Key-value records are `u16 count` × `{u16 key, u8 type, u8 len,
value[len]}`, with types u32, i32, f32, ASCII string and bytes. An unknown
key is skipped. A known key with the wrong type or length is skipped and
reported.

### 8.4 Reading in fixed small RAM

- `fm1_state_bin_feed(r, bytes, n)` takes pieces of any size: a SysEx page,
  a flash read, or the whole buffer.
- Its state: the header, the directory (≤ 640 B), a 64 B field buffer and
  counters, which is under 1 KiB [inferred: design A §6].
- A DEFLATED chunk adds the inflate window and tables while it is read:
  about 6 KiB, transient [inferred].
- The source is a `read(ctx, offset, buf, n)` callback, so RAM and a flash
  region look the same, and pass 2 re-reads instead of buffering.

## 9. Names, uids and versions

| Thing | Identity (never changes) | Written in JSON | Pinned in |
| --- | --- | --- | --- |
| Engine, effect | its `id` (`dx7` stays `dx7` while shown as FM6) | the id | the registry; a retired id stays reserved |
| Parameter | its uid [verified: "never changed or reused"] | its name (`#UID` as the fallback) | `param-uids.json`, plus an `aliases` map |
| List entry | its index (append-only) | its name as the registry has it (FM6's user voices are `User N`, not the voice names the screen shows); an index if a list has no stable names | a new `enum-names.json` |
| Mod kind | `id` and 4-character `guid` | the id | `mod-uids.json` |
| Port, system source | index or id | name (`"port": "Wrap"`, `"source": "RTRG"`; a port's 1-based index as the fallback) | `mod-uids.json` |
| Unit | its code (`fm1_mod.h`) | `snd2`, `snd1.fx2`, `fx1` | `fm1_mod.h` |
| Guide file | its path | — | permanent once published: printed QR codes point at it |

- A rename adds an alias and never removes one. A test loads a pinned file
  of every name ever shipped.
- A name that resolves nowhere is skipped and reported ("Unison skipped: not
  in this build"), never guessed.
- **Known but absent** ids get a reason table (`engines/known-ids.json`),
  so a refusal can be specific:
  - a planned engine: "not built yet";
  - a GPL module: "in the GPL build only", because `FM1_GPL_MODS` may be
    off in some build;
  - a retired one: "retired in 0.5".
- **Format levels.** JSON's `"lunar": "1.N"` and the binary header's
  major 1 and minor N move together. The writer writes the highest level
  of any member or chunk whose loss would change the sound or the song.
  Readers skip and count other unknown members or ancillary chunks. A
  level 2.0 would come with a migration in the C loader, and schemas
  under `/schema/2/`.
- **The metadata export** (§7.7) lists every name, alias, entry and
  known-but-absent id a build has, so an editor offers only names a
  load resolves.
- **Engine changes are not format changes.** A new parameter takes a new
  uid, and an old file keeps its default for it. A changed default cannot
  move an old file, because files write every value.

## 10. Loading

### 10.1 Two passes

- **Pass 1, the check, changes nothing.** It streams the file through
  the reader (§7.6), from RAM or flash, and works out:
  - each unit's engine, and whether it accepts the host's rate (`create`
    refuses Plaits-based engines above 47,872 Hz [verified:
    `FM1_APP_SELECT_RATE`]);
  - RAM at 44,118 Hz against 387,924 B;
  - rack positions, matrix slots and FM6 slots needed;
  - notes and locks against the pools.

  The plan is a few hundred bytes [inferred]. The simulator can run pass 1
  in a second instance of the module on the main thread, so a refused
  file never reaches the audio thread [reported: design B §7.1].
- **Pass 2 applies, in the fixed order**, on the control task:
  1. release notes and drop held commands;
  2. destroy and create units, each arena zeroed;
  3. set parameters, pads, levels and FM6 voices;
  4. load the rack and matrix;
  5. import the set, then apply the default-route rule;
  6. reseed the sequencer's RNG (ST11; in compat mode it runs on, as
     Movy's does);
  7. apply the view.

  After pass 1 nothing in pass 2 can fail [inferred: every refusal is
  decided in pass 1].
- **A project** mutes audio and starts from `fm1_app_init`.
- **A partial kind** touches only its target. A sound loaded into Sound 2
  releases Sound 2's notes and leaves the transport running: that is the
  guide's "inject a sound while the song plays".

### 10.2 Replace and merge

| Kind | On load |
| --- | --- |
| Project | Replaces everything, from init |
| Sound into Sound K | The sound and its inserts and MIDI effects are created afresh (deterministic). `snd` becomes `sndK`. Its modules go to free rack positions, or reuse an identical module (same kind and values). Its cables go to free slots, renumbered. Cables already aimed at Sound K follow the engine-swap rule: re-aimed by parameter name, else switched off (owner, 2026-10-05). Its FM6 voices: an identical voice in the bank is reused, else the first slot not loaded; Patch is re-pointed |
| Effects | Into the master chain or a sound's inserts, with the same remapping |
| Mod rack | Replaces the rack and the matrix |
| Clip into track T, slot S | A slot that is not empty asks first, as CLEAR does. Lanes match by label on the target track: the same label, else a free lane |
| Set (`.movy1`) | Replaces the set (S10's import) |
| DX7 bank (`.syx`) | Into FM6's user bank, as today |

### 10.3 Refusals, and "load without"

| Code | When | The page says (in love, C_REFUSE) |
| --- | --- | --- |
| NOT_LUNAR | Neither the binary magic nor a JSON object that opens with `lunar` | "This is not a Lunar Modulator file." |
| TOO_NEW | `lunar` above the reader's level | "Made with a newer Lunar Modulator (format 1.3); this simulator reads 1.2." |
| UNKNOWN | An engine or kind not in this build | The known-ids reason: "This project uses Rings, which is not built yet. Nothing was changed." |
| RATE | An engine refuses this browser's rate | "Macro cannot run at this browser's 96 kHz." |
| RAM | Over 387,924 B at 44,118 Hz | "Needs 412 KB; the FM-1 has 388 KB." **Always refused** (owner) |
| NO_ROOM | A merge needs rack, matrix or FM6 room that is not free | "The rack is full (8 of 8)." |
| TOO_BIG, BAD | Caps of §16, JSON that is not well formed, a member out of context order, or a value that cannot be read | The line and column, the JSON path (`/sounds/1/params/Cutoff`) and the first 40 characters there |

- **UNKNOWN and NO_ROOM are refused by default**, with one explicit
  choice: **"Load without Rings"**, or "Load without its modulation". The
  report then names what was left out:
  - an unknown engine leaves its unit empty (Sound 1 takes the default
    engine);
  - its cables are re-aimed or switched off;
  - a sound whose modules do not fit loads without its cables.
- On the device the same choice is a confirm popup.
- A refusal leaves the app's state hash unchanged; a test checks this.

### 10.4 The RAM rule

- Loads and the meter count every instance at **44,118 Hz**, the FM-1's
  rate, whatever the browser runs at.
- With that rule, a file is accepted or refused the same everywhere (ST6).
- CPU is not metered yet: four Macro Heavy sounds could pass the RAM rule
  and still not run on the FM-1 [inferred]. That is left to docs/14's
  verification ladder.

## 11. File kinds

| Kind (screen and guide) | File | Holds | Typical [verified: §3.4 and the examples] |
| --- | --- | --- | --- |
| **Project** | `first-orbit.lunar` | everything in §4 but settings and MASTER | 38 KB for the guide-like song, 4.7 KB deflated; the example, with a small set, 12 KB |
| **Sound** | `deep-bass.sound.lunar` | one sound, its inserts and MIDI effects, its level, its FM6 voices, the modules and cables that touch only it | 1.5 KB; a 16-pad kit 3.4 KB, 0.4 KB deflated |
| **Effects** | `space-verbs.fx.lunar` | an ordered chain of effects, with its cables and modules | about 1.3 KB |
| **Mod rack** | `wobble.mods.lunar` | a rack, its cables and its seed | about 1.7 KB; up to about 35 KB with every position's pattern data [inferred] |
| **Clip** | `bass-a.clip.lunar` | one clip's `movy1` lines, at track 0 slot 0, and the lanes its locks use | 0.5–12 KB (the example, a bar of bass with locks, 458 B) |
| **Set** | `first-orbit.movy1` | Movy's set, with FM-1 lines | 2–60 KB |
| **DX7 bank** | `brass.syx` | VCED voices or a VMEM bank | 4–5 KB |
| **Settings** | browser storage, device settings | device preferences | about 200 B |
| (Metadata) | `lunar-metadata.json` | the build's parameter metadata (§7.7), for editors; never loaded as state | 172 KB, 14 KB deflated |

- "Patch" is not used for a file, because FM6 and Six-Op FM already call a
  DX7 voice a Patch (ST3). The owner's "patch" is the Sound file; his
  "sequence" is the Set or a Clip; his "effect rack" is Effects.
- **`.lunar` for every JSON kind** (ST3), with the kind as a middle word in
  suggested names (`deep-bass.sound.lunar`). The content is JSON, and a
  download's type is `application/json`. Readers trust the content, never
  the name.
- **Binary files are the device's.** The simulator saves JSON; the host
  tool converts what it reads from a device to JSON unless asked not to.
  Every reader sniffs the first bytes:
  - `\x89Lunar` for binary;
  - `{`, after white space, for JSON, which must then open with `lunar`
    and `kind` (§7.2);
  - `movy1` for a set;
  - `F0 43`, or a raw 4,096-byte bank, for DX7 (as today [verified:
    `fm1_dx7.h`]).

## 12. The simulator: open and inject

### 12.1 C and wasm

- `fm1_app_state_check(a, src, opts, rep)`, `fm1_app_state_load(a, src,
  opts, rep)` and `fm1_app_state_save(a, kind, opts, put, ctx)`.
  - `src` is a read callback, so JSON, binary, RAM and flash look the
    same.
  - `opts` gives the target sound, track or slot, and "load without".
- The report is a small struct: code, line and column, the JSON path,
  counts of units, modules, cables, tracks, clips and song entries, RAM
  and budget, skipped members, values defaulted or repaired, dropped
  notes, and the name a refusal points at.
- **wasm**:
  - `fm1w_state_load(kind, target, flags, len)`, `fm1w_state_report()`,
    `fm1w_state_save(kind, arg)` returning the full length,
    `fm1w_meta()` (the metadata export, §7.7) and `fm1w_view(len)`;
  - the text buffer grows to 256 KiB, the largest cap (§16). The module
    has a fixed 8 MiB [reported: docs/16 §4.5];
  - parity tests feed the C reader in random-sized pieces (1, 7 and 256
    bytes), so the simulator also exercises the device's streaming path.
- **Worklet** messages: `state-load`, `state-save`, `view`; replies
  `loaded`, `saved`.

### 12.2 Open, drop and Save

- **Open…** and drop take several files at once: a project and a `.syx`,
  say. Each goes through the sniffing (§11) and the caps (§16).
- A partial kind asks for its target: "Load sound *Deep bass* into Sound
  1 / 2 / 3 / 4".
- **Save…** offers:
  - the project;
  - the current sound;
  - the master effects;
  - the mod rack;
  - the set, as `.movy1`;
  - the DX7 bank, as `.syx` VMEM.

  The JSON kinds download as `application/json`, the set as `text/plain`
  and the bank as `application/octet-stream`.
- **SAVE on the panel** stores the project in the browser and shows the
  L1 banner. The download stays a page button.
- **Nothing is sent to any device.** MIDI out stays the user's opt-in and
  refuses ports named FM-1 or M-VAVE (owner, S10). No file or message can
  turn it on.

### 12.3 Browser storage

- IndexedDB, database `lunar-modulator`, with three stores:
  - `files`: kind, name, text, size, origin (user, guide or autosave),
    mission and modified;
  - `autosave`: one record;
  - `recent`: the last five states replaced by a load.
- **Autosave** keeps the whole project, not only the set (ST16). It writes
  5 s after the last change, at most every 5 s, and on `visibilitychange`
  and `pagehide`. The start restores it, unless a link loads something.
- localStorage holds only small preferences under `lunar.sim.`: MASTER,
  the MIDI opt-in, the last file. The manual and the guide share the
  origin and its storage.
- Every access sits in try/catch. With storage blocked, the page works,
  with memory only.
- This replaces O17's localStorage sets; `.movy1` stays as a download and
  upload, for Movy.

### 12.4 Launch links and the embed API

**`?load=PATH`:**
- PATH is relative to the simulator page and must start with an
  allowlisted prefix: `guide/`, `manual/`, `examples/`.
- It is resolved with `new URL(PATH, document.baseURI)` and accepted only
  when the origin is the page's. The path must match
  `^[a-z0-9][a-z0-9/_.-]*\.(lunar|movy1|syx)$` after normalization, with
  no `..`, `//`, `\`, encoded dots or other schemes.
- It is fetched with `credentials: 'omit'` and `redirect: 'error'`, through
  a counting stream with the kind's cap.
- GitHub Pages serves the simulator at the root and the manual at
  `/manual/` [verified: `pages.yml`], so a guide at `/guide/` is the same
  origin.

**`#lunar=DATA`:**
- DATA is the base64url of the deflate-raw of the JSON, compact (§7.2). A
  fragment never reaches a server or a Referer.
- It is inflated through `DecompressionStream('deflate-raw')` into a
  counting stream that stops at the kind's cap, so a decompression bomb
  stops there.
- It is capped at 32 KiB of base64. A sound is about 690 characters, a
  16-pad kit about 540, and the guide-like project 5,872 [verified:
  §3.4].

**Hints**, applied after the load and the user's POWER press (browsers
allow audio only after a gesture):

| Hint | Does |
| --- | --- |
| `into=s2` | Target for a partial kind |
| `view=seq.track=2` | As a `view` line, which it overrides |
| `hl=KNOB2,FX` | Rings those controls on the page's panel drawing; no firmware involved |
| `play=1` | Starts the transport |
| `entry=3` | Starts the song at entry 3: the song note's `sgjump 2`, then play. These are the same verbs a person sends, so a link can never reach a state the panel could not |

**Arrival.** A card shows the file's title and about, and what it will
replace, with [Power on and load]. When the current state is the untouched
start chain, the card is only the POWER prompt. The replaced state goes to
Recent as "Before *mission*" (ST14).

**QR codes and PDFs** carry the mission page's URL or a `?load=` link of
about 70 characters, never inline state.

**`?embed=1`** for the guide's and the manual's pages. The page embeds
`<iframe src="../?embed=1&load=guide/missions/3-2/start.lunar"
allow="autoplay">`, with no `midi`.

| From the page | Does | Reply |
| --- | --- | --- |
| `load {kind, text, into?}` | A file load (§10), with the banner | `{re, ok, report}` |
| `save {kind}` | The canonical JSON of the current state | `{re, ok, text}` |
| `query {kind}` | The same JSON, parsed for the page | `{re, ok, json}` |
| `view {view}`, `highlight {controls[]}` | As the hints | `{re, ok}` |
| `transport {play, entry?}` | Only after the user powered on | `{re, ok}` |

From the simulator, unasked, it sends:
- `ready {formats, version}`;
- `power {on}`;
- `changed {gen}`, debounced to at most 4 a second.

**Mission checks** answer `changed` with `query` and test the JSON ("is
the Cutoff on `snd1.fx1` below 600 Hz?" is
`json.sounds[0].inserts[0].params.Cutoff < 600`). The guide needs no
parser of its own, and the check reads exactly what a save holds.

**Checks on every message:**
- The API exists only with `embed=1`.
- A message is accepted only when `event.source === window.parent` and
  `event.origin === location.origin`, plus `http://localhost:*` in a dev
  build. Replies go to that source and origin, never `'*'`.
- One operation runs at a time, and text has the file caps.
- Nothing can enable MIDI out, choose a port, fetch a URL, change a
  setting or delete storage.

A foreign site can still frame the page, because GitHub Pages cannot send
`frame-ancestors`. Without the API, it gets only the plain simulator.

### 12.5 What the screen and the page show

- **On the device screen:**
  - a load shows the L1 banner (the UI audit's toast style) for a second:
    `LOADED`, the name, `RAM 69%`;
  - a refusal shows `NOT LOADED` and the short reason, on base in
    C_REFUSE, never on overlay (the audit).
- **On the page:** a banner over the status line, for example "Loaded
  *First orbit*: 4 sounds, 6 effects, 8 cables, 8 tracks with 40 clips, a
  10-entry song. RAM 77 %. [Undo load]". Skips and drops go under it in
  subtle text.
- **Undo load** restores the state before the load from Recent. It is not
  the edit undo, which waits for the firmware's per-clip ring (owner).

### 12.6 The native harness and tools

- `fm1-sim-render --load F [--into s2] --save KIND:F --view …` gives:
  - golden tests;
  - the guide's audio renders, from the same files;
  - screenshots at a given state.
- `fm1-state` (desktop, C, the same objects): `pack` (JSON → binary),
  `unpack`, `canon`, `check` (RAM at 44,118 Hz), `diff`, `records`,
  `meta` and `from-movy1`.
- `tools/lunar.py` (Python, an independent reader of both encodings):
  `check`, `canon`, `explode`, `url`, `qr`, `schema`, `diagram`. It never changes app state;
  only the C loader does.

## 13. The guide, the manual and block diagrams

### 13.1 A mission's folder

```
guide/missions/3-2/
  start.lunar     the state the mission starts from
  goal.lunar      what it should sound like ("Launch the end result")
  goal.ogg        rendered by fm1-sim-render from goal.lunar
  diagram.svg     generated from goal.lunar (§13.2)
```

Paths are permanent once published. CI checks every guide file:
- it validates against its schema and is canonical (§7.2);
- it loads without refusal at 44,118 and 48,000 Hz, with ≥ 5 % RAM
  margin;
- `pack` then `unpack` gives it back;
- its `goal.ogg` matches a render.

So a mission cannot ship broken.

### 13.2 Block diagrams sooner

- A diagram lane is in flight (`docs/2026-10-06@manual-diagrams`, with a
  diagram theme and metrics module in `tools/manual/`). It owns the look.
  This design only feeds it.
- **Now:** the song note's transport and song state diagrams (§8 there,
  Mermaid and DOT) are ready for that lane.
- **Without waiting for C:** `tools/lunar.py diagram FILE` reads a project
  or sound file and draws the signal flow on that lane's theme:
  - sounds → inserts → level → mix → master slots → limiter;
  - cables as a second layer, sources on the left.

  It needs only the Python reader (stage P1, §18). So the manual's block
  diagrams can start as small JSON example files now
  (`engines/state/examples/` are the first), and the C loader checks the
  same files when it lands.
- Because the figures come from the files the missions ship, they cannot
  drift from them. The manual's figure test already holds the simulator's
  geometry the same way [reported: docs/15 S10,
  `test_figures_match_the_simulator`].

## 14. The device: user data in flash (gated)

Nothing here is enabled before the dump-and-restore gate passes on the
unit in question. The build switch `FM1_USER_FLASH` is off.

- **Where** [reported: docs/01 §2, from AL-255]:
  - flash is 1 MiB in 4 KB sectors;
  - the USR region is 72 KB at `0xEA000`;
  - the VM region is `0x56000` in V15, shrunk to 64 KB in FM-1+VA;
  - `key_mac` at `0xFF000` is never touched.

  The package guard keeps the stock partition layout byte-identical, so
  the store lives in those regions as they are. An app at FM-1+VA's size
  leaves 136 KB; one inside V15's boundary leaves up to about 400 KB
  [reported: design A §9]. The split is decided on the dev kit (ST17).
- **How:** a circular journal of our own, about 2–3 KB of code [inferred].
  - Each record has a 32 B header: magic, state word, slot, kind,
    generation, length, payload CRC and header CRC. A binary file
    follows, in 256 B pages.
  - **Commit:**
    1. program the header (WRITING) and the payload;
    2. read it back and check its CRC;
    3. program COMMITTED;
    4. mark the slot's older record OBSOLETE.

    The state words only clear bits, so each step is one NOR program.
  - **Boot:** for each slot, the newest committed record with good CRCs.
    A torn record is ignored, so the previous copy survives a power cut at
    any step.
  - **Garbage collection** copies live records from the tail, then
    erases. That levels wear by construction.
- **Wear:** with 136 KB and 20 KB saves, each sector is erased about once
  in 7 saves. At 100,000 cycles that is about 700,000 saves [inferred;
  check the Puya part's datasheet]. Autosave runs on SAVE, and when idle
  ≥ 30 s after a change, at most every 5 minutes.
- **Audio:** the CPU cannot fetch code from flash while it programs or
  erases [inferred: XIP from one flash; measure on the dev kit]. So a save
  mutes and shows "Saving…": about 80 ms for 20 KB into erased space, more
  with an erase. It runs while the transport is stopped.
- **Tests before any flash exists:** a NOR model that cuts power at every
  program and erase step, and in the middle of one, leaving bits half-set.
  Every reboot must show the old or the new copy of every slot, never
  neither.

## 15. The device: SysEx transfer (design only, gated)

For our own firmware, later. **Nothing in this plan builds a tool that can
reach a unit.** The first stage (D1, §18) runs only against the virtual
FM-1 in the harness.

- **Frame:** `F0 7D 4C 75 <ver 01> <cmd> <seq> <body…> F7`.
  - `0x7D` is MIDI's non-commercial ID, which suits this personal project.
  - `4C 75` is "Lu".
  - The body is packed 8 → 7, MSB-first, unlike stock's LSB-first stream,
    so no frame of ours parses as theirs. It ends with a CRC-16/CCITT of
    the unpacked body.
  - At most 256 data bytes a message: one flash page, about 300 B on the
    wire.
- **Commands:** `HELLO`, `LIST`, `GET {slot | LIVE kind}`, `PUT_BEGIN
  {target, kind, total}`, `DATA {offset, ≤ 256 B}`, `PUT_END` (the device
  runs pass 1 and answers with its report), `APPLY {source, target}`,
  `DELETE {slot}` (after the gate only), `ABORT`.
- **Replies:** `INFO` (firmware, format levels, max file, staging size,
  free store, which is 0 while disabled), `DIRENT`, `DATA`, `ACK {next
  offset}`, `NAK {CRC | NO_SPACE | TOO_BIG | BUSY | DISABLED | BAD_STATE}`,
  `REPORT`.
- **Flow:** a window of 4 messages with cumulative ACKs.
  - Offsets make retries idempotent and transfers resumable.
  - Staging is dropped after 2 s idle.
  - Before the gate, a `PUT` to a slot answers `DISABLED`, and only RAM
    staging exists.
- **Safety, in the host tool's code:**
  - It sends only two kinds of frame: the read-only identity query `F0 00
    32 45 00 00 00 40 7F F7`, then `F0 7D 4C 75` frames.
  - It goes on only when the identity reply is in our own range,
    `FM-1_5xx` (owner, 2026-10-05), **and** `HELLO` is answered with our
    `INFO`. It stops at any other `FM-1_0xx`, including the owner's
    `FM-1_092`, and at anything unknown.
  - It never sends `5A AA A5` frames, syscmd 33–36 or 48, or the soft key
    (CLAUDE.md traps 7 and 9).
  - The device has no address-level read or write and no code transfer:
    files only.
- **Not the browser.** Our preview firmware keeps the product string
  `FM-1`, and the page refuses ports named FM-1 (owner, S10). So the page
  cannot be the transfer tool, and stays that way.
- **Not over DIN in v1.** The jack is input only (UART RX), so a transfer
  there could not be acknowledged.
- **Files on the wire** are binary by default. D1 decides whether our
  firmware also takes JSON, which its reader would allow (§7.6).
- **Throughput:** USB-MIDI full speed moves a few to tens of KB/s
  [inferred]. A compressed project (3–4 KB) takes about a second.

## 16. Hostile input

| Check | Limit |
| --- | --- |
| Bytes after inflating | sound and fx 32 KiB, clip 32 KiB, mods 64 KiB, set 64 KiB, project 256 KiB, settings 4 KiB, `.syx` 64 KiB (`FM1_APP_DX7_FILE_MAX` [verified]). A full project is about 170 KB [inferred: a full set, 63 KB, plus four 16-pad sounds, every insert and MIDI effect, 32 cables, 8 KB of pattern data and 32 FM6 voices] |
| JSON structure | depth ≤ 8 (the deepest file is 6); strings ≤ 16 KiB (a `movy1` line); keys ≤ 64 B; numbers ≤ 32 characters; ≤ 64 members an object; ≤ 8,192 items an array |
| JSON text | UTF-8 checked (overlong forms, surrogate halves and U+0000 refused); no byte-order mark; duplicate keys refused; `lunar` and `kind` first, context first (§7.2) |
| Binary | total ≤ 96 KiB; header 32–256 B; entries 20–64 B; ≤ 32 chunks; `UNIT` 6 KiB, `SEQS` 48 KiB, `CLIP` 16 KiB, `MODR` 12 KiB, `DX7V` 160 B, key-value chunks 2 KiB; a DEFLATED chunk's declared length ≤ its cap, and the inflater stops there |
| Counts, checked before any multiply | records ≤ 512 per unit, tracks ≤ 16, song ≤ 255, notes per clip ≤ 512, locks and trigs per clip ≤ 1,024, positions 8, slots 32, pads 32, pattern data ≤ 8,192 B in all, voices ≤ 32 |
| Values | `fm1_param_clamp`; out of range clamped and counted as repaired; lists clamped; Q1.14 clamped to ±16,384; a fraction or an exponent where an integer belongs refuses the file; `movy1`'s own clamps |
| Indices | role, sound, slot, lane, step and pitch bounded; one unit per (role, sound, slot), and a duplicate position or slot refuses the file |
| Text on screen | `textContent`, never HTML; control characters and bidi overrides stripped from title and about |
| Links | §12.4: allowlisted same-origin paths, counted streams, one load at a time |

- **No file is code.** Nothing in a file can run, fetch, change a device
  setting or reach MIDI out.
- **Privacy:** no user name, path or account in any file. Nothing is
  uploaded. A fragment is never sent.
- **The metadata export carries the caps** (§7.7), so the web editor
  refuses what a load would.

## 17. Tests

- **Already, for the design** (`tests/test_state_schema.py`, on this
  branch):
  - every schema is a valid draft 2020-12 schema with its `$id`;
  - every example validates, is canonical (`tests/state_canon.py`'s
    layout, byte for byte) and lists its members in the schemas' order;
  - every name in an example resolves in today's build, every value of
    every unit is written, in uid order, and in range;
  - the example set and clip are the core's own export, byte for byte;
  - today's registry, in the metadata export's layout, fits
    `metadata.schema.json`, and the metadata example is that export;
  - number formatting, and every Q1.14 amount's shortest decimal.
- **Round trips:**
  - JSON → records → JSON is identical for every fixture and guide file;
  - JSON → binary → JSON and binary → JSON → binary are identical;
  - random states → save → load → save gives the same bytes in both
    encodings.
- **Golden files** under `tests/fixtures/state/`:
  - each released level's JSON files and their binary twins;
  - loaded in CI forever, so an accidental format change fails;
  - each JSON golden validates against its schema and is canonical.
- **Equivalence:**
  - every Movy fixture gives `movy1` → `SEQS` → `movy1` and `movy1` → JSON
    `set` → `movy1` byte-identical;
  - every mod golden gives a mod script → records → JSON `mod` → records →
    mod script identical;
  - an extracted set imports in Movy's oracle, and an extracted `mod` runs
    in `fm1-render --load`.
- **Two implementations:** the Python reader's records, printed as JSON,
  equal the C side's (`fm1-state records`) for every fixture, and both
  writers give the same canonical bytes.
- **Numbers:** every value a knob step can reach on every parameter reads
  back to the same float32 through the C writer and reader, the Python
  ones and JavaScript's `Number`; the decimal-to-float32 parser matches an
  exact `fractions` reference on random and boundary decimals (halfway
  cases, subnormals, 9-digit and 40-digit inputs).
- **Save coverage:** a random state that touches every parameter of every
  registered engine and kind, every pad and every FM6 slot must round-trip.
  A stage that adds state without adding its records fails this test
  (ST20).
- **Refusals:** each code of §10.3, with the state hash unchanged.
- **Merges:**
  - a sound into each sound unit with a full rack (NO_ROOM, then "load
    without");
  - with identical modules (reuse);
  - with an FM6 voice already in the bank.
- **Hostile input:**
  - libFuzzer targets for the JSON reader, the binary reader, `movy1`
    import, the mod script, the DX7 reader and each kind's `set_data`,
    with ASan and UBSan (`engines/sanitizers/`), run on aeon;
  - the JSONTestSuite corpus for the JSON reader (§7.6);
  - a fuzz build that skips CRCs, so mutations reach the deep parser;
  - truncation at every byte and every bit flipped: refused, and nothing
    changed;
  - the JSON reader fed in random-sized pieces (1, 7 and 256 bytes) gives
    the same records as the whole buffer.
- **Browser** (Playwright on aeon, in Chromium, Firefox and WebKit):
  - `?load`;
  - `#lunar` at its cap;
  - a refused path and a refused origin;
  - the embed API from a same-origin parent and from a foreign one, which
    is ignored;
  - autosave with storage blocked;
  - no MIDI permission requested.
- **Device stages:** the SysEx handler against the harness loopback; the
  journal against the NOR model (§14).

## 18. Build plan

In flight on 2026-10-06 and landing on `main`: the UI colour and fonts
stage (`sim/web/src`), the arpeggiator's follow-ups (the MIDI-effect stage
and a project-key page), the GPL switch `FM1_GPL_MODS` with the X0X 808,
909 and 303, TB-3PO and Felucca engines in `third_party/`, and the
manual's diagrams. The arpeggiator landed at `250bf53` (PR #69). The
owner's app lanes run in sequence because they share `fm1_app.c`.

**Now: `engines/` and `tools/` only, beside the UI stage** (owner,
2026-10-06: E1, E2, E3 and P1 now).

| Stage | Contents | Touches |
| --- | --- | --- |
| **E1** Song core | The song verbs, the `movy1` lines `se`, `sn` and `dq`, D15, D16 and D17 with compat keeping Movy's behaviour, a set import that reseeds the RNG (ST11; compat runs on), and their tests (song note §5.5, §10) | `engines/seq`, `engines/include/fm1_seq.h`, `engines/host/seq_script.c`, tests |
| **E2** Saveable engines and the metadata | Engine API v4, additive: `FM1_PARAM_FOCUS` (0x0100), `FM1_PARAM_PER_FOCUS` (0x0200) and the optional `get_param(self, index, focus)`, in Drums and Sophie and in every pad kit the GPL lane adds (the 808 and 909 are kits); `enum-names.json`, the alias maps and `engines/known-ids.json` (the GPL engines' ids with the reason "GPL build only"); Register's pattern data; the VCED → VMEM packer; the mod script's `lock=` and `data` lines; **`fm1-render --meta`**, writing `metadata.schema.json`'s layout from the registries, with its golden | `engines/include`, `engines/src`, `engines/mod`, `engines/midi_fx`, `engines/host`, `engines/third_party/*` (the hooks only), `tests/fixtures` |
| **E3** Records and codecs | `engines/state/`: the records, the streaming JSON reader (§7.6) and the canonical JSON writer, the binary reader and writer with DEFLATED chunks, the name tables, the `movy1` begin/item/end refactor, `fm1-state` (`canon`, `pack`, `unpack`, `check`, `diff`, `records`, `meta`, `from-movy1`), fuzz targets, the JSONTestSuite run, golden files | `engines/`, tests |
| **P1** Python reader and diagrams | `tools/lunar.py`: both encodings, `check` (schema, metadata, caps, canonical), `canon`, `explode`, `url`, `qr`, `schema` (a build schema from the metadata), `diagram` on the diagram lane's theme; `.gitattributes` | `tools/`; `diagram` after the diagram lane lands |

- The GPL lane's engines need API v4 only where they are pad kits, and
  their parameters must fit the metadata schema: `tests/test_state_schema.py`
  checks every registered engine, so a name, an abbreviation or a list the
  format cannot carry fails there.
- E1 and E2 change code linked into `fm1.wasm`, so each rebuilds the
  module in its own PR and keeps native and wasm parity (docs/15 §6.5). E3
  adds `engines/state/`, which nothing in the module calls until A1, and
  P1 is Python only.
- The app does not call anything new until A1.

**After the UI colour and fonts stage lands: `sim/web/src` and the page,
one at a time.**

| Stage | Contents |
| --- | --- |
| **A1** App state | Collector and applier on `fm1_app_t`: two passes, merges, refusals and "load without", RAM at 44,118 Hz for loads and the meter. Harness `--load`, `--save`, `--view`. wasm exports with the 256 KiB buffer, `fm1w_meta()` for the metadata. The settings list. The mod dump moves onto the records. The save-coverage test |
| **W1** The page | Open, Save and drop; IndexedDB, autosave, Recent and Undo load; `?load`, `#lunar` and the hints; the arrival card and banners; the embed API and `query`; the schemas published under `/schema/1/`. It absorbs S10's set storage; S10 keeps MIDI realtime in and the shortcuts |
| **S9+** Session, scenes and the Song page | The song note §5 and §6 |

- Order (ST20, adopted): A1, W1 and S9+ come first, ahead of the master
  chain and side-chain stages, because the owner asked for this work now.
- The master chain then adds its records (`fx3`, `fx4`, `send1`,
  `send2`), its JSON members and schema changes, at a new format level, in
  its own PR, under the save-coverage rule.

**A new train after W1: the advanced web-based editor** (owner,
2026-10-06). A page beside the simulator that edits complex sounds,
modulation and effect chains in the browser.

| Stage | Contents |
| --- | --- |
| **X0** Design | A design note with its own decisions, before any code: the page's layout beside the simulator; editing a sound, its inserts and MIDI effects, the rack and the matrix (cables as a patch view and as a table), and effect chains; controls generated from the metadata export (pages and knobs, LOG laws, ENUM lists, units, focus and per-pad values); how it talks to the simulator (the embed API's `load`, `query` and `changed`, or the module in the editor's own page); undo; validation (the build schema and the C loader's pass 1 through wasm, so the editor refuses what a load would); and what it writes (canonical JSON through the C writer in wasm, so its files diff as everyone's do) |
| **X1 …** | As X0 decides |

**After the dev kit, and the gate for anything on an FM-1.**

| Stage | Contents |
| --- | --- |
| **D1** SysEx | The protocol in the harness only (virtual FM-1 loopback), and the host tool with its identity gate. It can run any time after E3, because it never touches hardware. It decides whether our firmware also takes JSON (§7.6) |
| **D2** Flash store | The journal against the NOR model with power cuts; then on the dev kit; on an FM-1 only after the gate |

## 19. Owner decisions

Decided by the owner on 2026-10-06: **every recommendation adopted, except
ST2**, where the readable format is JSON. The table gives each decision as
it now stands.

| # | Question | Decision (owner, 2026-10-06) |
| --- | --- | --- |
| ST1 | Encodings | **Adopted.** One record model. A canonical JSON encoding for people, links, guide files and the coming web editor (built first), and the chunked binary container for the device (E3, before any device stage). Lossless both ways, with golden files for both. Binary chunks may be deflated with a window of at most 4 KiB, and the device writes them uncompressed until a compressor fits |
| ST2 | The readable format | **JSON, not the mod script's style** (the owner's change). Structured JSON for the app state, sounds (engine and parameters by name, `#UID` as the fallback), effects, inserts and the master chain, the rack (modules) and the matrix (cables); the set rides as the array of its `movy1` lines and round-trips verbatim, byte-identical to Movy's export. Canonical output: a fixed member order, fixed number formatting, no float that does not read back to its bits (§7.2). A small streaming C reader with bounded RAM and no malloc in the device path, with hostile-input caps and fuzzing (§7.6, §16). JSON Schemas for every kind and for the parameter metadata, which C exports, versioned (§7.7) |
| ST3 | Names | **Adopted.** Project, Sound, Effects, Mod rack, Set, Clip, DX7 bank; no "patch" for a file. `.lunar` for every JSON kind, with the kind as a middle word in suggested names; `.movy1` and `.syx` stay. Readers trust the content |
| ST4 | Values | **Adopted.** Every value written. JSON by name, with append-only list entries and an alias table, and `#UID` as the fallback; binary by uid and index, with no name tables |
| ST5 | Load semantics | **Adopted.** A project replaces everything from init; the other kinds merge into a target and remap. Unknown engines and full racks are refused by default, with an explicit "load without …" that names what is left out. Over budget is always refused |
| ST6 | RAM rule | **Adopted.** Every instance counted at 44,118 Hz, for loads and for the meter |
| ST7 | Per-pad values | **Adopted.** `FOCUS` and `PER_FOCUS` flags plus an optional `get_param(self, index, focus)` (API v4, additive), in every pad kit, the GPL lane's included. Not an app-side shadow copy |
| ST8 | FM6 voices | **Adopted.** They travel with the sounds that use them, as `dx7` items. On a sound load: reuse an identical voice, else the first free slot, else ask which slot to overwrite. Banks download as `.syx` VMEM |
| ST9 | Sound files carry their modulation | **Adopted.** The cables that touch only that sound, and the modules they need. If they do not fit, refuse with "Load without its modulation" |
| ST10 | Metronome, count-in click, full velocity, default quantize, drum flag | **Adopted.** The first three are device settings. `dq` is an FM-1 `movy1` line. The drum flag is derived from the routed engine being a pad kit, and not saved (A1 also makes the app send it) |
| ST11 | Sequencer RNG | **Adopted, with compat keeping Movy's.** Reseeded to its init constant on every set or project load, so a song plays the same each time; no seed in files. In compat mode the RNG runs on, as Movy's does |
| ST12 | Register's locked loop | **Adopted.** Saved as pattern data now (E2), before MG5's pattern work |
| ST13 | Links | **Adopted.** `?load=` for allowlisted same-origin paths (guide, QR codes, PDFs); `#lunar=` deflated JSON up to 32 KiB; hints `into`, `view`, `hl`, `play`, `entry` |
| ST14 | A link over the user's work | **Adopted.** An arrival card; the old state kept as "Before *mission*" in Recent (5), with Undo load |
| ST15 | Embed API | **Adopted.** `?embed=1` and postMessage, same origin only. Mission checks read the state's JSON, the same text a save writes. No reader of ours in the guide's pages |
| ST16 | Browser storage | **Adopted.** IndexedDB for files, a whole-project autosave and Recent; localStorage for preferences only. This replaces O17's localStorage sets; `.movy1` stays as a download |
| ST17 | Device store | **Adopted.** Our own power-cut-safe journal, not littlefs. Its size is decided when the dev kit shows the app's size. Compiled out until the gate |
| ST18 | SysEx transfer | **Adopted.** Designed only. The host tool talks only to units that identify as `FM-1_5xx` and answer our `HELLO`. Never over DIN in v1. The browser never sends |
| ST19 | Licence of guide files | **Adopted.** MIT, as the repository. Not CC0 |
| ST20 | Order and rule | **Adopted.** E1–E3 and P1 now; A1, W1 and S9+ as soon as the UI colour stage lands, before the master chain and side-chain stages; then the web editor's train, from its design stage X0. Every later stage that adds state adds its records, JSON members, schema changes and golden files in the same PR (the save-coverage test) |

**For X0, later:** the web editor's own decisions, in its design note.
