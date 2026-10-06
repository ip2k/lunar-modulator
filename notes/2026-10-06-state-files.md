# Saved state, files and launch links: the recommended design (2026-10-06)

**Why.** The owner, 2026-10-06: "Make the block diagrams sooner, and work on
the song-list editing, patch / project / sequence / effect rack / sound
stuff and opening the simulator at a given state / injecting state into it
for the firmware now." The files will ship with the illustrated beginner
guide (web and PDF), whose missions offer downloads and "Launch in the
simulator" links, and with a 4-minute song that plays hands-free from the
song list. The song list and scenes are in the companion note,
[2026-10-06-song-and-scenes.md](2026-10-06-song-and-scenes.md).

**What this is.** A design, and the decisions it needs (§19). **Nothing is
built.** The owner works "ask per stage". Two proposals were written first
and judged here, dimension by dimension (§3):
- **design A**, firmware-first: one chunked binary container read by a
  1 KiB push parser;
- **design B**, interchange-first: one text format in the mod script's
  style, deflated on the device.

This note keeps the best of both. Neither proposal is committed; what
survives is here.

**The one rule holds throughout.** Nothing here is sent to or written on
the owner's FM-1. The SysEx protocol (§15) is for our own firmware. Its
host tool refuses any unit that is not ours, and it is not built in this
plan. Flash storage (§14) is compiled out until the dump-and-restore gate
passes on the unit in question.

**Marks.** `[verified]` was checked for this note on `origin/main` at
`250bf53` (after PR #69, the arpeggiator), by reading the code or by
running a desktop build of it. `[reported]` names its source; "design A"
and "design B" are the two proposals, measured on `ebb9577`. `[inferred]`
is reasoning, to be checked when built.

## Contents

1. Short answer
2. What exists today
3. A against B, and the verdict
4. State inventory
5. Gaps that block a faithful save
6. The record model
7. The text encoding, `lunar1`
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
  - **`lunar1` text** is for people: downloads, links, browser storage, the
    guide's files in git. It is in the mod script's style, and it holds the
    sequencer's `movy1` set and the `--mod` script verbatim (§7).
  - **The binary container** is for the device: flash and SysEx. It has a
    32-byte header, a directory, a CRC32 per chunk, and critical and
    ancillary chunk tags. Its parser needs about 1 KiB of RAM (§8).
  - Conversion goes through the records, so it is lossless both ways.
    Golden files pin both encodings (§17).
- **Kinds:** Project, Sound, Effects, Mod rack, Clip and Settings in
  `lunar1`. The Set stays `.movy1` and the DX7 bank stays `.syx` (§11).
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
  - `#lunar=` for small inline states;
  - hints: `into`, `view`, `hl`, `play` and `entry`;
  - an `?embed=1` postMessage API, same origin only;
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
- **Build** (§18):
  - four stages need only `engines/` and `tools/`, so they can start now,
    beside the UI colour and fonts stage;
  - three need `sim/web/src` or the page, and follow that stage;
  - the device's two come last: D1 needs only the harness, D2 the dev
    kit, and the gate before anything on an FM-1.
- **Block diagrams sooner** (§13.2):
  - the song note's state diagrams are ready for the diagram lane now;
  - a signal-flow diagram generator reads `lunar1` files in Python, so it
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

`fm1_seq_export_movy1` returns the full length and writes only what fits
[verified: `fm1_seq.h`], so a set too large for the buffer is detected, not
cut short. A set with every pool full exports to 53,208 B [reported:
docs/15 §2.7] or 63,035 B with design A's fill [reported: design A]. Both
fit 65,536 B. A full project's text, about 78 KB [reported: design B,
generated], does not.

## 3. A against B, and the verdict

### 3.1 A measurement that settles the size question

The two proposals measured different "typical" songs: A's had 1,196 notes,
B's had 18 clips of random pitches. For this note, a set shaped like the
guide's song was generated and run through the core:
- 6 tracks, 7 scenes, 40 clips;
- 1,444 notes and 160 locks;
- drums repeating per bar, a bass riff, chords, a two-bar melody;
- the song list of the companion note (§7 there).

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

### 3.3 The verdict

- **B's text is the interchange, and it is built first.** Everything a
  person touches now is text: guide files, links, downloads, git. The
  device has no storage before the gate anyway.
- **A's container is the device's encoding.** On the device it is lighter
  in RAM and code, and the device never formats or parses a float as text.
  Its codec is built in an engines-only stage, before any device stage.
- **One record model joins them.** Each encoding is a reader and a writer
  of the same records, so conversion is lossless by construction and
  tested both ways. Only the desktop tools and the simulator carry the
  text codec and its name tables; the firmware links the binary codec
  alone.
- **Both may compress.** A link deflates the text. A binary chunk may be
  stored deflated with a window of at most 4 KiB, which the device can
  inflate in about 6 KiB of transient RAM [inferred].
- **Changed from each:**
  - A's name tables inside the binary are dropped; text carries the names;
  - A's two-letter link key is renamed `#lunar=`, because the naming rule
    forbids that abbreviation;
  - B's JavaScript reader for mission checks is replaced by a JSON of the
    records, written by the C side (§12.4);
  - B's partial-load refusal gets A's "load the rest" as an explicit
    choice (§10.3).

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
| Sequencer RNG | `rng`, seeded with a constant at init | — | reseeded on every load (§19 ST11) |
| Clipboards, Capture ring, transport, record arm, playing position | core | — | not saved, as in Movy |
| Current sound, octave, transpose | `sound`, `octave`, `transpose` | session | project |
| Project key (one per project; fixed C major today) | planned | session | project |
| MASTER | a potentiometer on PB6 | — | not saved: the pot decides |
| View: mode, page, FX slot, track, bar, RACK and MATRIX selection | `fm1_app_t`, `fm1_seq_ui_t`, `fm1_mod_ui_t` | view | project and guide files, as a hint |
| MIDI in channel, clock follow, MIDI out opt-in (browser) | page, later the device | setting | settings only, never from a file or link |

A typical guide-song chain needed 298,596 B, 77 % of the budget, before
MG9 grew the mod runtime by about 3 KB [reported: design A, at `ebb9577`]. Its saved part is about 16 KB of binary, or 30 KB of text, or 3
KB deflated (§3.1). **The RAM is in the instances, not the settings**: the
loader's first job is the RAM check, not parsing.

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
   - Fix:
     - a `lock=UID` slot option;
     - `data P VERSION HEX` lines for pattern data;
     - a full dump that writes every parameter;
     - amounts at the shortest percent that maps back to the same Q1.14
       (`amt=40`, not `amt=40.0024414062`).
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

| Record | Fields | `lunar1` line (§7) | Binary chunk (§8) |
| --- | --- | --- | --- |
| meta | name (≤ 16 ASCII, the screen's), title and about (UTF-8), licence, writer | `name`, `title`, `about`, `licence`, `made` | `meta` (ancillary) |
| unit | unit code, engine id (≤ 15 of `[a-z0-9-]`), on/off for MIDI effects | `unit U ID [on\|off]` | `UNIT` head |
| param | unit code, uid, focus (none, or pad 1–16), value: f32 base in its unit, or a list index | `param U Name=V …`; `pad U N Name=V …` | `UNIT` record, 8 B |
| level | sound, percent | `level U PCT` | `UNIT` key-value |
| dx7 | user slot 1–32, loaded, 155 VCED bytes | `dx7 N NAME op6=… … alg= fb= …` | `DX7V`, 160 B |
| session | current sound, octave, transpose, key root and scale | `current`, `octave`, `transpose`, `key` | `PROJ` key-value |
| mod | seed; position (guid, parameter bases by uid, pattern data); slot (12 B) | the `--mod` lines, verbatim, in `begin mod` … `end mod` | `MODR` |
| set | the `movy1` items: header, song, track, lane, route, clip, note, lock, trig, `dq`, `se`, `sn` | the `movy1` lines, verbatim, in `begin movy1` … `end movy1` | `SEQS` |
| view | mode and keys | `view MODE k=v …` | `view` (ancillary) |
| setting | key, value | `set KEY VALUE` (settings kind only) | `SETG` |

Rules:
- **Canonical order**: meta, units and params (by role, sound, slot, then
  uid; pads in pad order, the focus last), levels, FM6 voices, session,
  mod, set, view.
- **Every value is written.** Floats are written as their exact bits in
  binary and as the shortest round-trip decimal in text (§7.1).
- **No personal data.** No timestamps or user names. `made` gives a
  version and a commit; `author` is never filled in automatically.
- **The set's items** come from a refactor of `fm1_seq_import_movy1` into
  `begin / item / end` calls [inferred: design A §5.3]. The text reader
  and the binary reader both drive those calls, so the clamps, the
  "lowest real clip" fallback and `sq_reseed_empty_clips` stay in one
  place.
- **The mod records** come from the mod script parser, refactored to emit
  records instead of applying lines. The app's applier then calls
  `fm1_mod_set_slot` and friends, as today's line handler does.

## 7. The text encoding, `lunar1`

### 7.1 Lexical rules

- UTF-8 with LF line ends (CR LF is read too) and a final newline. `#`
  starts a comment, except inside `begin movy1`, which passes through
  verbatim: a lane label may hold `#`.
- A line is a key, then tokens separated by blanks. `NAME=VALUE` follows
  the mod script:
  - names compare without ASCII case;
  - a space is written `_` (the owner's lane-label rule);
  - abbreviations are accepted on read, and full names are written.
- Tokens are printable ASCII. `#`, `;`, `=` and `%` inside a name are
  written `%23`, `%3B`, `%3D` and `%25`.
- **Numbers** outside `movy1`: `-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][-+]?[0-9]+)?`.
  No `+`, `nan`, `inf`, hex or locale commas.
  - The parser is ours, not libc's `strtod`, so native and wasm agree bit
    for bit.
  - The writer prints the shortest decimal (≤ 9 significant digits) that
    this parser maps back to the same float32.
  - A test sweeps every value a knob step can reach on every parameter.
- **Unknown parameters stay lossless.** A parameter whose name the writer's
  build does not know is written `#UID=VALUE`, for example when converting
  a newer device's binary file. The reader accepts the same form.
- Free text: `name` is ≤ 16 printable ASCII, for the screen. `title` (≤ 80
  B) and `about` (≤ 240 B) are UTF-8. Control characters and bidi
  overrides are stripped on read.

### 7.2 Lines

| Line | Meaning |
| --- | --- |
| `#! lunar1 KIND` | First line. KIND is `project`, `sound`, `fx`, `mods`, `clip` or `settings` |
| `needs lunar=1.N` | The format level the file needs. A reader below it refuses (§9) |
| `made fw=X.Y.Z commit=abc1234` | Information only |
| `unit U ID [on\|off]` | Create ID in unit U (`none` empties it). `on`/`off` only for MIDI effects |
| `param U NAME=V …` | Values; the writer puts one panel page (four knobs) on a line |
| `pad U N NAME=V …` | Pad N (1–16) of a pad kit |
| `level U PCT` | A sound's level into the mix |
| `dx7 N NAME op6=… op5=… … op1=… alg= fb= sync= lfo= pms= trn=` | FM6 user slot N: 21 values per operator in VCED order, the globals by name |
| `current U`, `octave N`, `transpose N`, `key ROOT SCALE` | The panel session |
| `begin mod` … `end mod` | The modulation runtime, as an `fm1-render --mod` script |
| `begin movy1` … `end movy1` | The set, as a `.movy1` file |
| `view MODE [k=v …]` | Where the panel opens: `home sound=2 page=2`, `fx slot=m1`, `glo`, `seq track=3 bar=2`, `seq page=set`, `session`, `song`, `rack pos=3`, `matrix slot=5`, `chain` |
| `set KEY VALUE` | Settings kind only |

**Units** are named as the mod script names them [verified:
`fm1_mod_script_unit_name`]:
- sounds: `snd` (Sound 1; `snd1` reads the same), `snd2`–`snd4`;
- inserts: `snd1.fx1` … `snd4.fx2`;
- MIDI effects, per sound as built (owner, 2026-10-06): `sndK.mfx1`,
  where the arp is `mfx1` and up to `mfx4` are planned;
- master slots: `fx1`, `fx2`, and `fx3`, `fx4` when the chain has four;
- shared sends, when they are built: `send1`, `send2`;
- the host: `host`.

In a sound file `snd` means the target sound; in an effects file `fx1…`
are relative.

**The load order is fixed whatever the line order** (§6); the writer
writes it in that order.

**Additions to `movy1`** are FM-1 lines, written only outside compat mode
and only when not the default: `dq PCT`, `se MODE`, `sn SLOT NAME` (the
song note §3.6). Movy ignores them, so a guide set still opens in Movy.

### 7.3 Examples

A sound, 441 bytes, which is 366 characters as a link [reported: design
B, generated]:

```
#! lunar1 sound
needs lunar=1.0
name DEEP BASS
title Deep space bass
about Mission 2.3: open the filter with KNOB2 until the bass growls.
unit snd shapes
param snd Shape=Saw_Sub Timbre=0.41 Color=0.5 Attack=0
param snd Release=0.2 Volume=0.7
unit snd.fx1 filter
param snd.fx1 Type=Ladder Cutoff=420 Resonance=0.3 Drive=0
unit snd.fx2 none
level snd 80
begin mod
mod 1 lfo Rate=0.25 Shape=Triangle Depth=1 Mode=Free Phase=0 Sync=1/4 Width=0.5
slot 1 lfo1 > snd.fx1:Cutoff amt=35
end mod
```

A pad kit writes the kit-wide values, then each pad in full, then the
focus:

```
unit snd1 drums
param snd1 Kit=Punch Accent=0.5 Volume=0.7
pad snd1 1 Tune=-2 Decay=0.62 Level=0.8 Tone=0.5 Snap=0.5 Sweep=0.5 Drive=0 Model=Kit
…
param snd1 Pad=1_Kick
```

(Abridged, and the parameter and entry names are illustrative: the
registry's tables decide them, and a real file writes every value.)

### 7.4 Diffs in git

- One page of knobs per line, so a turned knob is a one-line diff.
- A `movy1` clip is one line (Movy's format; up to about 12 KB).
  `.gitattributes` gives `*.lunar` and `*.movy1` a word diff
  (`wordRegex = [^ ;]+`), and `tools/lunar.py explode` is a `textconv`
  that prints one note per line for review.

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
| `meta` | name, title, about, licence | key-value records |
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

| Thing | Identity (never changes) | Written in text | Pinned in |
| --- | --- | --- | --- |
| Engine, effect | its `id` (`dx7` stays `dx7` while shown as FM6) | the id | the registry; a retired id stays reserved |
| Parameter | its uid [verified: "never changed or reused"] | its name (`#UID` as the fallback) | `param-uids.json`, plus an `aliases` map |
| List entry | its index (append-only) | its name (an index if a list has no stable names, as FM6's user Patch entries) | a new `enum-names.json` |
| Mod kind | `id` and 4-character `guid` | the id | `mod-uids.json` |
| Port, system source | index or id | name (`lfo1.wrap`, `rtrg`) | `mod-uids.json` |
| Unit | its code (`fm1_mod.h`) | `snd2`, `snd1.fx2`, `fx1` | `fm1_mod.h` |
| Guide file | its path | — | permanent once published: printed QR codes point at it |

- A rename adds an alias and never removes one. A test loads a pinned file
  of every name ever shipped.
- A name that resolves nowhere is skipped and reported ("Glide skipped: not
  in this build"), never guessed.
- **Known but absent** ids get a reason table (`engines/known-ids.json`),
  so a refusal can be specific:
  - a planned engine: "not built yet";
  - a GPL module: "in the GPL build only", because `FM1_GPL_MODS` may be
    off in some build;
  - a retired one: "retired in 0.5".
- **Format levels.** `lunar1` and binary major 1 move together. The writer
  writes `needs` as the highest level of any line or chunk whose loss
  would change the sound or the song. Readers skip and count other
  unknown lines or ancillary chunks. A `lunar2` would come with a
  migration in the C loader.
- **Engine changes are not format changes.** A new parameter takes a new
  uid, and an old file keeps its default for it. A changed default cannot
  move an old file, because files write every value.

## 10. Loading

### 10.1 Two passes

- **Pass 1, the check, changes nothing.** It works out:
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
  6. reseed the sequencer's RNG (ST11);
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
| NOT_LUNAR | Not a known header or magic | "This is not a Lunar Modulator file." |
| TOO_NEW | `needs` above the reader | "Made with a newer Lunar Modulator (format 1.3); this simulator reads 1.2." |
| UNKNOWN | An engine or kind not in this build | The known-ids reason: "This project uses Rings, which is not built yet. Nothing was changed." |
| RATE | An engine refuses this browser's rate | "Macro cannot run at this browser's 96 kHz." |
| RAM | Over 387,924 B at 44,118 Hz | "Needs 412 KB; the FM-1 has 388 KB." **Always refused** (owner) |
| NO_ROOM | A merge needs rack, matrix or FM6 room that is not free | "The rack is full (8 of 8)." |
| TOO_BIG, BAD | Caps of §16, or a line that cannot be read where a block must be whole | The line number and its first 40 characters |

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

| Kind (screen and guide) | File | Holds | Typical |
| --- | --- | --- | --- |
| **Project** | `first-orbit.lunar` | everything in §4 but settings and MASTER | about 30 KB text, 3–4 KB deflated (§3.1) |
| **Sound** | `deep-bass.sound.lunar` | one sound, its inserts and MIDI effects, its level, its FM6 voices, the modules and cables that touch only it | 0.4–4 KB |
| **Effects** | `space-verbs.fx.lunar` | an ordered chain of effects, with its cables and modules | under 1 KB |
| **Mod rack** | `wobble.mods.lunar` | a rack and its cables. Also a valid `fm1-render --mod` script, because the header line is a comment there | about 1 KB; up to about 20 KB with pattern data as hex |
| **Clip** | `bass-a.clip.lunar` | one clip's `movy1` lines, at track 0 slot 0, and the lanes its locks use | 0.2–12 KB |
| **Set** | `first-orbit.movy1` | Movy's set, with FM-1 lines | 2–60 KB |
| **DX7 bank** | `brass.syx` | VCED voices or a VMEM bank | 4–5 KB |
| **Settings** | browser storage, device settings | device preferences | about 150 B |

- "Patch" is not used for a file, because FM6 and Six-Op FM already call a
  DX7 voice a Patch (ST3). The owner's "patch" is the Sound file; his
  "sequence" is the Set or a Clip; his "effect rack" is Effects.
- Downloads suggest the kind as a middle word (`deep-bass.sound.lunar`).
  Readers trust the header, never the name.
- **Binary files are the device's.** The simulator saves text; the host
  tool converts what it reads from a device to text unless asked not to.
  Every reader sniffs the first bytes:
  - `\x89Lunar` for binary;
  - `#! lunar1` for text;
  - `movy1` for a set;
  - `F0 43`, or a raw 4,096-byte bank, for DX7 (as today [verified:
    `fm1_dx7.h`]).

## 12. The simulator: open and inject

### 12.1 C and wasm

- `fm1_app_state_check(a, src, opts, rep)`, `fm1_app_state_load(a, src,
  opts, rep)` and `fm1_app_state_save(a, kind, opts, put, ctx)`.
  - `src` is a read callback, so text, binary, RAM and flash look the
    same.
  - `opts` gives the target sound, track or slot, and "load without".
- The report is a small struct: code, line, counts of units, modules,
  cables, tracks, clips and song entries, RAM and budget, skipped lines,
  dropped notes, and the name a refusal points at.
- **wasm**:
  - `fm1w_state_load(kind, target, flags, len)`, `fm1w_state_report()`,
    `fm1w_state_save(kind, arg)` returning the full length,
    `fm1w_state_json()` (§12.4) and `fm1w_view(len)`;
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

  Each is a `text/plain` or `application/octet-stream` download.
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
- DATA is the base64url of the deflate-raw of the text. A fragment never
  reaches a server or a Referer.
- It is inflated through `DecompressionStream('deflate-raw')` into a
  counting stream that stops at the kind's cap, so a decompression bomb
  stops there.
- It is capped at 32 KiB of base64. A sound is about 370 characters
  [reported: design B]; the guide-like project of §3.1, about 4.5 KB
  [inferred: §3.1 plus the sounds].

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
| `save {kind}` | The canonical text of the current state | `{re, ok, text}` |
| `query {kind}` | The records as JSON, written by the C side | `{re, ok, json}` |
| `view {view}`, `highlight {controls[]}` | As the hints | `{re, ok}` |
| `transport {play, entry?}` | Only after the user powered on | `{re, ok}` |

From the simulator, unasked, it sends:
- `ready {formats, version}`;
- `power {on}`;
- `changed {gen}`, debounced to at most 4 a second.

**Mission checks** answer `changed` with `query` and test the JSON ("is
the Cutoff on `snd1.fx1` below 600 Hz?"). The guide needs no parser of its
own, and the check reads exactly what a save would hold.

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
- `fm1-state` (desktop, C, the same objects): `pack` (text → binary),
  `unpack`, `canon`, `check` (RAM at 44,118 Hz), `diff`, `json`, and
  `from-movy1`.
- `tools/lunar.py` (Python, an independent reader of both encodings):
  `check`, `explode`, `url`, `qr`, `diagram`. It never changes app state;
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
- it loads without refusal at 44,118 and 48,000 Hz, with ≥ 5 % RAM
  margin;
- `pack` then `unpack` gives it back;
- its `goal.ogg` matches a render.

So a mission cannot ship broken.

### 13.2 Block diagrams sooner

- A diagram lane is in flight (`docs/2026-10-06@manual-diagrams`, with a
  diagram theme and metrics module in `tools/manual/`). It owns the look.
  This design only feeds it.
- **Now:** the song note's transport and song state diagrams (§6 there,
  Mermaid and DOT) are ready for that lane.
- **Without waiting for C:** `tools/lunar.py diagram FILE` reads a project
  or sound file and draws the signal flow on that lane's theme:
  - sounds → inserts → level → mix → master slots → limiter;
  - cables as a second layer, sources on the left.

  It needs only the Python reader (stage P1, §18). So the manual's block
  diagrams can start as small hand-written `lunar1` example files now, and
  the C loader checks the same files when it lands.
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
- **Throughput:** USB-MIDI full speed moves a few to tens of KB/s
  [inferred]. A compressed project (3–4 KB) takes about a second.

## 16. Hostile input

| Check | Limit |
| --- | --- |
| Text bytes after inflating | sound and fx 16 KiB, clip 16 KiB, mods 64 KiB, set 64 KiB, project 256 KiB, settings 4 KiB, `.syx` 64 KiB (`FM1_APP_DX7_FILE_MAX` [verified]) |
| Text lines | 4 KiB outside `movy1`, 16 KiB inside (a full clip); 24 tokens of ≤ 64 bytes outside `movy1` (the mod script's own limits [verified: `MAX_TOK`, `TOK_LEN`]); ≤ 8,192 lines |
| Binary | total ≤ 96 KiB; header 32–256 B; entries 20–64 B; ≤ 32 chunks; `UNIT` 6 KiB, `SEQS` 48 KiB, `CLIP` 16 KiB, `MODR` 12 KiB, `DX7V` 160 B, key-value chunks 2 KiB; a DEFLATED chunk's declared length ≤ its cap, and the inflater stops there |
| Counts, checked before any multiply | records ≤ 512 per unit, tracks ≤ 16, song ≤ 255, notes per clip ≤ 512, locks and trigs per clip ≤ 1,024, positions 8, slots 32, pattern data ≤ 8,192 in all, voices ≤ 32 |
| Values | `fm1_param_clamp`; non-finite → the default, counted as repaired; lists clamped; Q1.14 clamped to ±16,384; `movy1`'s own clamps |
| Indices | role, sound, slot, lane, step and pitch bounded; one unit per (role, sound, slot), and a duplicate refuses the file |
| Text on screen | `textContent`, never HTML; control characters and bidi overrides stripped from title and about |
| Links | §12.4: allowlisted same-origin paths, counted streams, one load at a time |

- **No file is code.** Nothing in a file can run, fetch, change a device
  setting or reach MIDI out.
- **Privacy:** no user name, path or account in any file. Nothing is
  uploaded. A fragment is never sent.

## 17. Tests

- **Round trips:**
  - text → records → text is identical for every fixture and guide file;
  - text → binary → text and binary → text → binary are identical;
  - random states → save → load → save gives the same bytes in both
    encodings.
- **Golden files** under `tests/fixtures/lunar/`:
  - each released level's text files and their binary twins;
  - loaded in CI forever, so an accidental format change fails.
- **Equivalence:**
  - every Movy fixture gives `movy1` → `SEQS` → `movy1` byte-identical;
  - every mod golden gives a mod block → `MODR` → mod block identical;
  - an extracted `movy1` block imports in Movy's oracle, and an extracted
    mod block runs in `fm1-render --mod`.
- **Two implementations:** the Python reader's JSON equals the C side's
  for every fixture.
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
  - libFuzzer targets for the text reader, the binary reader, `movy1`
    import, the mod script, the DX7 reader and each kind's `set_data`,
    with ASan and UBSan (`engines/sanitizers/`), run on aeon;
  - a fuzz build that skips CRCs, so mutations reach the deep parser;
  - truncation at every byte and every bit flipped: refused, and nothing
    changed.
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

The UI colour and fonts stage (`feature/2026-10-06@ui-colour-type`) is in
flight in `sim/web/src`. The arpeggiator landed at `250bf53` (PR #69). The
owner's app lanes run in sequence because they share `fm1_app.c`.

**Now: `engines/` and `tools/` only, beside the UI stage.**

| Stage | Contents | Touches |
| --- | --- | --- |
| **E1** Song core | The song verbs, the `movy1` lines `se`, `sn` and `dq`, D15–D17 and their tests (song note §3.5 and §8) | `engines/seq`, `engines/include/fm1_seq.h`, `engines/host/seq_script.c`, tests |
| **E2** Saveable engines | `FM1_PARAM_FOCUS`/`PER_FOCUS` and the optional `get_param` in Drums and Sophie (API v4, additive); `enum-names.json` and the alias map; Register's pattern data; the VCED → VMEM packer; the mod script reader's `lock=` and `data` | `engines/include`, `engines/src`, `engines/mod`, `engines/seq`, `engines/host`, `tests/fixtures` |
| **E3** Record model and codecs | `engines/state/`: the records, `lunar1` reader and writer, binary reader and writer with DEFLATED chunks, the `movy1` begin/item/end refactor, `fm1-state`, fuzz targets, golden files | `engines/`, tests |
| **P1** Python reader and diagrams | `tools/lunar.py` (both encodings, `check`, `explode`, `url`, `qr`, `diagram` on the diagram lane's theme), `.gitattributes` | `tools/`; `diagram` after the diagram lane lands |

- Engines changes are linked into `fm1.wasm`, so each of E1–E3 rebuilds
  the module in its own PR (docs/15 §6.5).
- The app does not call anything new until A1.

**After the UI colour and fonts stage lands: `sim/web/src` and the page,
one at a time.**

| Stage | Contents |
| --- | --- |
| **A1** App state | Collector and applier on `fm1_app_t`: two passes, merges, refusals and "load without", RAM at 44,118 Hz for loads and the meter. Harness `--load`, `--save`, `--view`. wasm exports, with the 256 KiB buffer. The mod dump moves onto the record writer. The save-coverage test |
| **W1** The page | Open, Save and drop; IndexedDB, autosave, Recent and Undo load; `?load`, `#lunar` and the hints; the arrival card and banners; the embed API and `query`. It absorbs S10's set storage; S10 keeps MIDI realtime in and the shortcuts |
| **S9+** Session, scenes and the Song page | The song note §3 and §4 |

- Proposed order (ST20): A1, W1 and S9+ come first, ahead of the master
  chain and side-chain stages, because the owner asked for this work now.
- The master chain then adds its records (`fx3`, `fx4`, `send1`,
  `send2`) in its own PR, under the save-coverage rule.

**After the dev kit, and the gate for anything on an FM-1.**

| Stage | Contents |
| --- | --- |
| **D1** SysEx | The protocol in the harness only (virtual FM-1 loopback), and the host tool with its identity gate. It can run any time after E3, because it never touches hardware |
| **D2** Flash store | The journal against the NOR model with power cuts; then on the dev kit; on an FM-1 only after the gate |

## 19. Owner decisions

Each has a recommendation.

| # | Question | Recommendation |
| --- | --- | --- |
| ST1 | Encodings | One record model; `lunar1` text for people (built first); the binary container for the device (built in E3, before any device stage); lossless both ways, with golden files for both. Binary chunks may be deflated with a window of at most 4 KiB, and the device writes them uncompressed until a compressor fits. Not: text only, deflated on the device (B); not: binary only, with a compiled text form (A) |
| ST2 | Text grammar | The mod script's style, with `movy1` and `--mod` blocks verbatim. Not JSON |
| ST3 | Names | Project, Sound, Effects, Mod rack, Set, Clip, DX7 bank; no "patch" for a file. `.lunar` for every `lunar1` kind, with the kind as a middle word in suggested names; `.movy1` and `.syx` stay. Readers trust the header |
| ST4 | Values | Every value written. Text by name, with append-only list entries and an alias table, and `#UID` as the fallback; binary by uid and index, with no name tables |
| ST5 | Load semantics | A project replaces everything from init; the other kinds merge into a target and remap. Unknown engines and full racks are refused by default, with an explicit "load without …" that names what is left out. Over budget is always refused |
| ST6 | RAM rule | Every instance counted at 44,118 Hz, for loads and for the meter |
| ST7 | Per-pad values | `FOCUS` and `PER_FOCUS` flags plus an optional `get_param(self, index, focus)` (API v4, additive). Not an app-side shadow copy |
| ST8 | FM6 voices | Travel with the sounds that use them, as `dx7` lines. On a sound load: reuse an identical voice, else the first free slot, else ask which slot to overwrite. Banks download as `.syx` VMEM |
| ST9 | Sound files carry their modulation | Yes: the cables that touch only that sound, and the modules they need. If they do not fit, refuse with "Load without its modulation" |
| ST10 | Metronome, count-in click, full velocity, default quantize, drum flag | The first three are device settings. `dq` is an FM-1 `movy1` line. The drum flag is derived from the routed engine being a pad kit, and not saved (A1 also makes the app send it) |
| ST11 | Sequencer RNG | Reseeded to its init constant on every set or project load, so a song plays the same each time. No seed in files. A deviation: Movy's runs on |
| ST12 | Register's locked loop | Saved as pattern data now (E2), before MG5's pattern work |
| ST13 | Links | `?load=` for allowlisted same-origin paths (guide, QR codes, PDFs); `#lunar=` deflated text up to 32 KiB; hints `into`, `view`, `hl`, `play`, `entry` |
| ST14 | A link over the user's work | An arrival card; the old state kept as "Before *mission*" in Recent (5), with Undo load |
| ST15 | Embed API | `?embed=1` and postMessage, same origin only. Mission checks read a JSON of the records from the C side. Not a JavaScript text reader |
| ST16 | Browser storage | IndexedDB for files, a whole-project autosave and Recent; localStorage for preferences only. This replaces O17's localStorage sets; `.movy1` stays as a download |
| ST17 | Device store | Our own power-cut-safe journal, not littlefs. Its size is decided when the dev kit shows the app's size. Compiled out until the gate |
| ST18 | SysEx transfer | Designed only. The host tool talks only to units that identify as `FM-1_5xx` and answer our `HELLO`. Never over DIN in v1. The browser never sends |
| ST19 | Licence of guide files | MIT, as the repository. Not CC0 |
| ST20 | Order and rule | E1–E3 and P1 now; A1, W1 and S9+ as soon as the UI colour stage lands, before the master chain and side-chain stages. Every later stage that adds state adds its records, lines and golden files in the same PR (the save-coverage test) |
