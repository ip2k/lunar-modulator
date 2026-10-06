# The Advanced editor: the design (2026-10-06)

**Why.** The owner, 2026-10-06: "a train of work to add in a web-based
settings editor that lives alongside the emulator so people can edit complex
sounds and modulation / effect chains in a browser with larger and more
well-laid-out controls instead of doing everything through the simulator,
and in line with the work to inject simulator state and import/export
things, this 'Advanced web-based editor' should fit right in."

**What this is.** Stage X0 of the state note's build plan
(`notes/2026-10-06-state-files.md` §18): the editor's own design and
decisions, before any code. Two designers drew it through two lenses, and
this note judges them dimension by dimension and keeps the best of both:
- **design A**, a visual patch bay: signal flow you can see and touch,
  knobs, cables, drag and drop;
- **design B**, a dense inspector: every parameter of a sound on one screen,
  sliders with typed values, a sortable matrix, search, A/B and memory.

Neither proposal is committed; what survives is here. **Nothing is built.**
The six final mockups are in `assets/web-editor/` (§3).

**Status: decided** (owner, 2026-10-06). ED1–ED18 are adopted as
recommended (§19), with two answers on top:
- **FM6 (DX7) voice editing is a later stage**, not v1 (ED17).
- **Memory figures a user sees are percentages of the FM-1's budget
  only**: on the FM-1's screen, on the page, in the editor and in refusal
  messages. Bytes and kilobytes appear only in developer docs
  (DEVELOPERS.md, `engines/README.md`, notes like this one). This settles
  §20.2; the mockups predate it (§3).

The build order is decided too: ED0 after the state core (E1–E3) lands, ED1
after A1, ED2–ED5 after W1 (§18).

**Read with.**
- `notes/2026-10-06-state-files.md` and `notes/2026-10-06-song-and-scenes.md`
  on `docs/2026-10-06@state-song-design` ("the state note"): the record
  model, JSON as the readable format with a schema per kind, the metadata
  export, the stages E1–E3, P1, A1, W1 and the owner's decisions ST1–ST20.
- `notes/2026-10-06-ui-audit.md` and `sim/web/PALETTE.md` v2 (PRs #67 and
  #75, on main): the semantic colour map and the sound colours, used
  unchanged.
- `tools/manual/diagram_theme.py` (PR #73): the manual's line kinds, used
  unchanged for cables.

**Marks.** `[verified]` was checked for this note on 2026-10-06 against the
UI colour lane's worktree at `b1677cd` (its `sim/web/src`, `www/` and native
harness) or the state branch at `1757499`, by reading the code or running
it; the claims added with the owner's decisions (§19, §20.2, §20.3) were
checked against main at `96fae8a`. `[reported]` names its source ("A" and
"B" are the two designers' scratch notes). `[inferred]` is reasoning, to be
checked when built.

**The one rule holds.** The editor changes the virtual FM-1 on its own page.
It never sends anything to a device; the device link in §16 is design only,
behind the dump-and-restore gate, and the state note's ST18 ("the browser
never sends") stands.

## Contents

1. Short answer
2. The two designs, judged
3. The mockups
4. Where it lives
5. One truth: records, ops and the edit layer
6. Metadata: the editor never names an engine
7. Live sync and follow
8. Undo
9. Files, links and storage
10. The views
11. Controls and the visual language
12. The audio thread and performance
13. Accessibility and keys
14. Tablets and phones
15. Licences and the GPL switch
16. Later: our firmware on a device (design only)
17. Tests
18. Build plan
19. Owner decisions
20. Found on the way

## 1. Short answer

- **An inspector backbone with a patch-bay view.** B's inspector is the
  editing surface: sliders with typed values, grouped by the device's
  pages, keyboard-first, with search, A/B and a memory page. A's signal
  flow is the editor's home and its effect-chain editor (four strips into
  the Mix and the master chain, blocks you drag). Modulation is edited in
  the matrix table; A's patch bay becomes a second view of the same slots,
  the **Map**, with a focus mode that keeps 32 cables readable.
- **It lives on the simulator's page** as lazily loaded modules, with three
  layouts: Panel (today's page), Workbench (the panel docked beside the
  editor) and Editor (the panel folded to its live screen). One wasm
  instance, in the AudioWorklet, is the only state (§4).
- **One vocabulary.** An edit is one of the state note's records (a
  parameter, a unit, a level, a rack position, a matrix slot, a MIDI effect
  on or off) or one of four verbs (swap, move, current, view). C applies it
  through one edit layer that the panel's own handlers share, and C answers
  with a refusal and its reason when it must. JavaScript holds no engine
  rule (§5).
- **The audio thread sees only binary**: packed records in, a change feed
  and a telemetry block out. JSON, value text, pass-1 checks, hashes and
  diffs run in a shadow Worker with a second instance of the module (§5,
  §12).
- **Controls come from the metadata export** (the state note's `metadata`
  kind), shipped as a static `meta.json` and matched to the module by a
  hash; ED0 adds page names, the knob detent, effect groups and refusal
  reasons to it (§6).
- **Both ways, one history.** A knob turned on the panel lights its row in
  the editor; an edit in the editor opens its page on the panel. Undo
  covers editor and panel edits alike; the sequencer keeps its own (§7, §8).
- **Files are the state note's**, with drop targets, per-block export,
  links that open the editor at a parameter, and a library (§9).
- **Build** (decided): ED0 (metadata and C helpers) once the state core
  (E1–E3) has landed; ED1 (the edit layer and the shadow Worker) after A1;
  the editor's views after W1, in four stages, ED2–ED5 (§18).
- **Memory as a percentage** (decided): every memory figure the editor
  shows is a percentage of the FM-1's budget, as the screen's meter is
  (§11, §20.2).

## 2. The two designs, judged

| Dimension | A: visual patch bay | B: dense inspector | Verdict |
| --- | --- | --- | --- |
| A beginner learns | Strong: the signal flow is a picture; knobs look like the device; cables show what moves what | Middling: 51 controls on one screen read as a wall without the picture; K-chips and page labels help | A's flow as the home, B's inspector under it; page and knob labels everywhere (both) |
| An expert is fast | Middling: knobs, drags, no search, no typed entry beyond Enter | Strong: typed values in units, ⌘K search over everything a save holds, PLAY/EDIT keys, batch edits, A/B | B |
| How much of the device | Sounds, inserts, arp, master, rack, matrix, files, library, history | The same plus search, A/B and memory; no file views | Both together; v1 scope in ED17 |
| Fit with the simulator and the state files | Strong: drop targets are the loader's `into`; IndexedDB library; real screens | Strong: edits through A1's applier; the mirror is the JSON a save writes | Both: records as the edit vocabulary (§5) |
| Accessibility | Knobs as sliders; the matrix table as the canonical view; a keyboard twin for every drag | Native slider rows, tables, keyboard-first by design | B's controls, A's keyboard twins |
| Phones and tablets | Designed down to 390 px: stacked strips, sliders, a cable list | 1,024 px and up only | A's phone plan, built last (ED14) |
| Cost to build | High: knob SVGs, cable routing, pill placement, drag and drop | Medium: forms from metadata, tables, a palette | B first; the Map last |
| Risk to the audio thread | Low: binary ops, a change ring, no text in the worklet | Higher: refetching a unit's records JSON from the worklet means formatting text on the audio thread | A's rule: binary only (ED3) |

Two places where the designs disagreed, and why the verdict:
- **Knobs or sliders.** A knob of 48 px gives about 150 px of drag on a 270°
  arc; a row slider gives 200 to 700 px, reads left to right, takes a typed
  value beside it and is a native `role=slider` (B). A's case for knobs is
  that they look like the device; the K1–K4 chips and "Page 2 · KNOB1–3"
  labels carry that link without the precision cost, and phones need
  sliders anyway (A's own phone plan). One control everywhere is less code.
- **Follow the panel.** A: the panel only marks the block, never moves the
  editor's selection (two views fighting over focus). B: the editor follows
  the panel, on by default. Verdict: B's follow in the Workbench, where the
  panel is the thing being played, and never while a picker is open or a
  value is being typed; A's mark otherwise (ED9).

## 3. The mockups

Six mockups, each rendered at 1440 × 900 and 1024 × 768, full page, in
`assets/web-editor/` (12 PNGs); the HTML sources and the scripts that
render and check them are in `assets/web-editor/src/` (its README says how
to rebuild them). Every PNG was looked at after the last render.

| Mockup | Shows |
| --- | --- |
| `01-workbench` | The Workbench: the virtual FM-1 with the screen the harness draws for S3 In1, the ring on KNOB2 that just turned; S3 In1 Filter's inspector beside it, page 1's rows carrying K1–K4 because the panel's knobs turn them now, Cutoff lit by the panel's turn with its modulation bracket and live tick; "From the panel: KNOB2", the change log with both origins; the Flow under both, S3 In1 selected |
| `02-sound` | The Editor layout on Sound 2: the outline with the FM-1's screen following (HOME · S2 · page 1/4); the path strip; Macro by its four pages (Model as 8 segments, Timbre modulated by one cable, Morph by a per-voice cable with one tick per sounding voice); the cables into the sound in words; In1 Echo (LOG Time); In2 empty with the effect picker showing each effect's cost and PSX Verb refused "46.0 KB over"; the arpeggiator's PLAY, RHYTHM and CHANCE open, FEEL to SEED as summaries; the detail bar with the parameter's flags in words and its keys |
| `03-chain` | Flow and effects: a drag in hand (S1's Gate onto In1: swap), the source slot "moving"; the Mix with levels in the sound colours; M2 Limiter's inspector with the in, reduction and out meters the screen cannot show; the four drop verdicts and the keyboard twin |
| `04-modulation` | The rack as eight cards with live traces (ENV3 per voice, three voices); the matrix table with filters, the screen's marks with words, a refused row with its reason and fix ("Make it global"), a late row with its loop explained; cable 5's inspector (amount, offset, VIA, curves drawn, polarity, scope, the voices' values now) and its module, ENV3 |
| `05-map` | The Map: sources, the rack and destinations, cables in the manual's line kinds, focus on ENV3 (its three cables bright with their amounts, the other seven dimmed and unlabelled), per voice as a band, refused in the refusal colour ending in ✕, cables between modules in the gutters beside the rack |
| `06-project` | Files and history: an effects file dropped on S2's inserts and its arrival card (what it replaces and brings, the RAM after); a refused sound load; per-block export; A/B compare of Sound 3 with picks; the Memory page by part with "what would fit"; the history with editor, panel and file lines; the library |

**What is real.** The example project is designer A's "First orbit"
(`assets/web-editor/src/README.md` gives its harness command): S1 Drums →
Comp → Gate, S2 Macro (Wavetable) → Echo with the arpeggiator on, S3 Macro
(VA+Filter) → Filter (Ladder, 420 Hz) → Drive (Tube), S4 FM6 → Plate, M1
Master Sat, M2 Limiter; six modules and ten cables.
- Run again for this note, the harness gives 300,672 B of 387,924 at
  44,118 Hz, slot 6 refused and slot 9 a tick late [verified: `refused` 32,
  `delayed` 256 in its `--slots` output]. The screen shows 78 %, and so
  does the editor: a user sees memory only as a percentage of the budget
  (owner, 2026-10-06).
- The four FM-1 screens are the harness's own renders of that project
  [reported: designer A, `fm1-sim-render` on the UI colour lane]; the panel
  around the first is a capture of the page with that screen laid in its
  place.
- Every parameter name, range, unit, flag, list, page and LOG law comes
  from `meta.js`, a subset of `fm1-render --list` and `--list-mod` from the
  UI colour lane's build [verified], drawn by the same rules the editor
  would use (§6). Instance sizes at 44,118 Hz are A's harness measurement
  [reported: A §3]; effects under 1 KB are shown as "under 1 KB".
- **Illustrative:** values the harness was not asked for (page 2 and 3 of
  Macro, the Limiter's meters, the A/B values, the history's times), the
  RAM split by part (within about 1 KB), and the arrival card's figures,
  which are computed from A's sizes.
- **Memory in the mockups is in KB; the editor's will be in percent.** The
  mockups were drawn before the owner decided that a user sees memory
  only as a percentage of the FM-1's budget, and are kept as drawn. Where
  they show memory in KB (the outline's and Memory page's totals, each
  block's and picker entry's cost, "free", "46.0 KB over", the arrival
  card's "RAM after", the refused load's need), the built editor shows the
  same figure as a percentage, by the rule in §11; for example the
  outline's "RAM 293.6 / 378.8 KB" beside "78 %" becomes the 78 % alone.
  A file's or a link's size (the library, "Copy a link") is not a memory
  figure and keeps its unit [inferred: the decision is about the RAM
  budget].

**The check.** `src/editor.js` checks every render and `src/render.mjs`
prints the findings: text over text, text over a mark (thumbs, brackets,
ticks, tags, jacks, pills), a mark within 3 px of text on its line, a
cable over text, text outside its panel or block, clipped text, and
sideways scroll. **All 12 renders: 0 findings.** Two exceptions are
deliberate and declared in the source: the block in hand during a drag
covers its target (`03-chain`), and in the Map a dimmed cable may pass
under an amount pill's opaque ground when no clear place exists. Faults
found by eye and fixed on the way: a crowded app bar at tablet width, an
eight-way list too narrow for its names, a sub-heading running under the
next panel (which added the "outside its box" check), pills on jacks.
The PNGs are quantised to 256 colours keeping the 168 most used exactly
(`src/shrink.mjs`), so the role and sound colours are the tokens' own.

## 4. Where it lives

**On the simulator's page, sharing the one wasm instance.**
- `sim/web/www/editor/` holds plain ES modules, no framework and no build
  step, like the page [verified: `www/` is served as is]. They load on
  first use (`import()`), so the plain simulator loads what it loads today.
- **Three layouts**, a switch in the app bar:
  - *Panel*: today's page;
  - *Workbench*: the panel and the editor side by side at 1,280 px and
    wider, stacked below that; the outline is a rail;
  - *Editor*: the panel folds to its live screen in the outline (in the
    head at tablet widths), so a change is always seen on the FM-1's own
    screen. The screen is the same transferred frame drawn twice.
- **A port of its own.** The editor gets its own `MessageChannel` into the
  worklet, so its traffic never queues behind panel input and the panel's
  code is untouched.
- **Links:** `?view=edit`, and `&sel=s3.fx1:Cutoff` opens the editor at a
  parameter; the state note's hints (`load`, `into`, `view`, `hl`, `play`)
  combine with them (§9).

| Turned down | Why |
| --- | --- |
| A separate `/editor/` page around `?embed=1` | Every 30 Hz telemetry frame would cross an iframe; the embed API (ST15) would grow from a few safe calls to every edit, which is the surface ST15 keeps small; keyboard focus split across frames; two copies of the UI state (A) |
| An editor with its own engine, syncing whole states | Two truths; each knob turn a state copy; audio would glitch on each injection; a refusal could differ (both) |
| The editor drawn by C on a second canvas | Text layout, focus and accessibility are the browser's for free (B) |
| Forms generated from the JSON Schema | The schema validates files; it does not know that four knobs make a page or that Cutoff is LOG. The metadata does (B) |
| A pop-out window now | Kept for later (ED18): BroadcastChannel and a transferred port can put the panel and the editor on two screens |

## 5. One truth: records, ops and the edit layer

**The state lives only in C**, in the worklet's module. The editor keeps a
mirror of the records (keyed by unit, uid and focus) for drawing, search
and undo, and nothing else.

**Edits are records.** The state note's record model (§6 there) already
names every value a file can hold; an edit is one of them, so the editor,
the files, the change feed and a future SysEx link share one vocabulary
[inferred: field layout settles in E3].

| Op | Carries | Same as on the panel |
| --- | --- | --- |
| `param` record | unit, uid, focus (a pad), value or list index | KNOB1–4, ALGORITHM |
| `unit` record | unit, engine id or empty | PRESETS, the FX picker |
| `level` record | sound, percent | the Mix page |
| `mfx` record | sound, slot, on | ARP |
| `mod` position record | position, kind, its parameter bases | RACK |
| `mod` slot record | slot, source, VIA, destination, amount, offset, curve, polarity, scope, on | MATRIX |
| verb `swap`, `move` | two insert or master slots, with their cables | SEL, then SELECT |
| verb `current` | the current sound | SHIFT + PRESETS |
| verb `view` | which page the panel shows (follow); never in history | — |

**One edit layer in C**, `sim/web/src/fm1_edit.c` [inferred: names]:

```c
/* An edit, from the panel's handlers or the editor; src is PANEL, EDITOR,
 * LOAD or SEQ (a recorded knob move), tag the editor's op number. */
int  fm1_edit_apply(fm1_app_t *a, const fm1_rec_t *r, uint32_t n,
                    uint8_t src, uint16_t tag, int8_t *codes);
int  fm1_edit_verb(fm1_app_t *a, const fm1_edit_verb_t *v, uint8_t src, uint16_t tag);
/* The change feed: base changes since `gen`, with who made them. */
uint32_t fm1_edit_changes(fm1_app_t *a, uint32_t gen, fm1_change_t *out, uint32_t max);
/* Live values for what the editor shows: meters, module outputs, the
 * effective value of each routed destination, per voice where it runs so. */
uint32_t fm1_edit_telemetry(fm1_app_t *a, const uint32_t *mask, float *out, uint32_t max);
/* The panel's view as a record: mode, sound, page, slot, and the uid each
 * of KNOB1-4 turns now (the K1-K4 chips). */
void fm1_edit_view(const fm1_app_t *a, fm1_view_t *out);
```

- **Where changes are caught.** Every base value already passes through
  `fm1_app_set_param` [verified: `fm1_app.c`, the knob, a lane's grid and
  the DX7 patch all call it], the arpeggiator's through
  `fm1_app_arp_set_param` [verified], and a lock playing does not: it
  writes the engine through the sequencer's sink and leaves the base alone
  [verified: `sink_set_param`]. So the change ring needs a hook in those
  two functions and in the structural ones (select, level, the mod
  setters), with the source set where input enters (key and encoder
  handlers, the editor's op, a load). That is a small change to
  `fm1_app.c`; the new code is `fm1_edit.c`.
- **The same functions for both hands.** The panel's handlers and the
  editor's ops reach the same calls, so they make the same change-ring
  entries and the same `--mod` lines for the harness log, and the parity
  test does not move (A).
- **A live apply, not a load.** A1's applier mutes audio for a project and
  re-creates units for a sound (state note §10.1); a knob must do neither.
  `fm1_edit_apply` is the applier's single-record path with the panel's
  semantics: C's clamps and LOG law; a `nolock` parameter (Macro's Model)
  is sent once, on release; a `latch` one (the arpeggiator's) reaches the
  next note, and the editor says so.
- **Refusals come from C**, with codes the metadata names in words: RAM (at
  44,118 Hz), RATE, rack or matrix full, and the matrix planner's per-slot
  reasons (§6), and a RAM refusal says by how much in percent of the
  budget (§11). The editor's previews (a picker's RAM column, the jacks
  that would refuse a cable in hand) come from the shadow module; the
  live module's answer wins.

**wasm and worklet** [inferred: names]:

| Direction | Message | Carries |
| --- | --- | --- |
| page → worklet | `edit` | packed records (fixed size, at most 24 B each) and verbs, transferred; at most 64 applied per render quantum, the rest the next |
| page → worklet | `subscribe` | the telemetry mask: what is on screen |
| page → worklet | `snapshot` | asks for the binary container of the project or one kind (A1's `fm1w_state_save` in binary) |
| page → worklet | `state-load` | W1's load, as the binary the Worker made after pass 1 (§9) |
| worklet → page | `edited` | `{tag, codes}`: each record's verdict |
| worklet → page | `changes` | at most one batch an animation frame; an overflow sends `resync`, and the editor asks for a snapshot |
| worklet → page | `telemetry` | one block, at most 30 a second, in two pooled buffers transferred and handed back, as the screen frames are [verified: `worklet.js` transfers `px` and `leds`] |

New exports: `fm1w_edit`, `fm1w_edit_verb`, `fm1w_changes`,
`fm1w_telemetry`, `fm1w_view_get` and `fm1w_meta_id`, beside A1's
`fm1w_state_save`, `fm1w_state_load` and `fm1w_meta`.

**The shadow Worker** (`editor/shadow.worker.js`) runs a second instance of
`fm1.wasm` with no audio. The state note already proposes a second instance
for pass 1 (§10.1 there); this note puts it in a Worker, shared by W1 and
the editor, so a 30 KB file never stalls the main thread either. It
answers, by promise:
- `meta()`: the metadata export, when `meta.json` and the module disagree;
- `format(unit, uid, values)` and `parse(unit, uid, text)`: the screen's
  digits (`fm1_look_value`) and C's parser for "1.2k", "−6 dB", "1/8D"
  (ED0's `fm1_param_parse`); the editor shows the Worker's text one frame
  after a drag moves, and the raw number until the Worker is ready;
- `check(json, kind, into)`: pass 1 against a copy of the live state;
- `toBinary(json)`, `toJSON(bin, kind)`: canonical JSON through C's writer;
- `hash(bin)`, `diff(a, b, kind)`, `ram(bin, ops)`: undo checks, A/B rows
  and every picker's RAM column.

## 6. Metadata: the editor never names an engine

**What exists.** The state branch already has the metadata kind's schema
(`engines/state/schema/metadata.schema.json`) and an example: engines,
effects and MIDI effects with each parameter's uid, name, abbreviation,
type, range, default, unit, page, knob and flags; list entries and
aliases; mod kinds with gates (and their normals) and outputs; sources,
units, the host's parameters, polarities and curves; FM6's VCED fields;
known-but-absent ids; the reader's caps; the build (API versions, rate,
budget, `gpl`) [verified]. E2 writes it as `fm1-render --meta`, and A1's
`fm1w_meta()` returns it from the module. The full export is 172,499 B
canonical and 14,086 B deflated [reported: state note §7.7].

**Delivery.** The build writes `meta.json` beside `fm1.wasm`; GitHub Pages
serves it compressed, it is cached, and the editor can draw before POWER is
pressed. The module exports only `fm1w_meta_id()`, a hash of its
registries; on a mismatch the editor asks the shadow Worker for
`fm1w_meta()`. The 172 KB never passes through the audio thread, and the
editor never touches `fm1w_catalog`, whose 49,152-byte buffer could not
hold it [verified: `fm1_app.c`].

**What ED0 adds** (members at a minor level of the metadata kind, so older
readers skip them):

| Member | Why |
| --- | --- |
| `page_names` per engine | The arpeggiator's PLAY, RHYTHM, CHANCE, FEEL, MORE, KEYS, SEED are not in the export [verified: the schema has `page` numbers only] |
| `step` per parameter | The panel's detent (1/100 of the LOG position, one entry of a list), so arrow keys move as a knob does |
| `group` per audio effect | The picker's groups ("Filter and tone", "Dynamics", "Space"); an editor hint, never a rule |
| `refusals` | Each refusal code with its words: the loader's (NOT_LUNAR … NO_ROOM) and the matrix planner's per slot (NO_SOURCE, NO_DEST, NOLOCK, ENUM_NO_MOD, VOICE_TO_MONO, VOICE_TO_EFFECT, UNIT_RESERVED) |
| `telemetry` | The live block's layout, so the editor reads it by name |
| `meta_id` | The hash `fm1w_meta_id()` returns |

**Controls from metadata** (one factory; the mockups draw by these rules):

| Metadata | Control |
| --- | --- |
| `float` | A slider and a typed value field with its unit |
| `float`, `min < 0 < max` | Fills from zero, with a zero mark |
| flag `log` | Moves on the LOG law, `u = log2(v/min) / log2(max/min)`, with 1-2-5 ticks |
| `enum`, up to 4 entries | One row of segments |
| `enum`, 5 to 8 | A grid of segments under the label |
| `enum`, more than 8 | A list field with its place ("5/17") and type-ahead; over 24, a searchable grid (Shapes' 47, FM6's patches) |
| flag `mod` | Can take a cable: the bracket, the live tick, the cable chip; without it, none (Macro's LPG) |
| flag `poly` | A `v` mark: a per-voice cable may land here; one tick per sounding voice |
| flag `nolock` | "rebuilds the voices": sent on release |
| flag `latch` | "every change reaches the next note" |
| flag `input` (a module's) | A jack in the Map, not a slider |
| flags `focus`, `per_focus` (API v4) | A pad strip above the per-pad rows; the focused pad follows the panel's |
| `page`, `knob` | Grouped by the device's pages, labelled "Page 2 · KNOB1–3"; K1–K4 chips in the Workbench |
| `licence` | A GPL chip in pickers (§15) |

**JSON Schemas** are generated from the same metadata (P1's `lunar.py
schema`) for people and third-party tools. The editor itself never
validates a file: the shadow module's pass 1 does, so there is one judge.

## 7. Live sync and follow

- **Panel → editor.** The change feed brings `{gen, src, record}`. The row
  lights for a second (not under reduced motion), "From the panel: KNOB2"
  appears in the inspector, the history gets a line, and a polite
  announcement says it at most once a second.
- **Editor → panel.** The op is applied between render quanta; the screen
  redraws as if the knob had turned, because it is the same call.
- **Echoes.** A change carrying the editor's own tag confirms the mirror
  and does nothing else. While a slider is held, the panel's changes to
  that one parameter wait until it is let go; the last write wins, as with
  two hands on one synth (B).
- **Heard, not set.** A lock playing, a cable moving a parameter, the
  arpeggiator's notes: these come with the telemetry as the white live
  tick, the gold lane dot and the bracket. They never move a base and
  never enter the history.
- **Follow** (ED9). Selecting a block or a parameter in the editor sends
  `view`, and the panel opens that page: on by default, a toggle, view
  only. In the Workbench the editor also follows the panel (its sound, page
  and slot), on by default, but never while a picker is open, a value is
  being typed or a drag is in hand; in the Editor layout the block the
  panel shows is only marked.
- **K1–K4.** In the Workbench, the rows the panel's knobs turn now carry
  K1–K4, from `fm1_edit_view`; the hardware mapping is then plain.

## 8. Undo

- **One page history** for editor and panel edits, each line with its
  origin: the device has no undo for sounds, and two hands on one sound
  should share one history (both).
- **Entries.** A pointer drag is one entry; key repeats on one parameter
  within 600 ms are one; a swap, a cable made, an A/B "make B" and a load
  are one each.
- **Inverse ops first**, from the mirror before the edit: an engine change
  undoes by selecting the old engine, setting its values and putting back
  the cables the engine-swap rule re-aimed or switched off (owner,
  2026-10-05).
- **Checked by hash.** After an undo the Worker hashes the state and
  compares it with the entry's "before"; on a mismatch the entry's binary
  snapshot (about 16 KB, kept for structural entries only [inferred]) is
  loaded instead.
- **Not in it:** notes, steps, clips and locks (the sequencer's own undo),
  the transport, MASTER and the view. A load's undo is W1's Undo load.
- **Limits:** 200 entries or 4 MB of snapshots; redo is cleared by a new
  edit; the history lasts for the session.

## 9. Files, links and storage

All of it is the state note's (§10–§12 there); the editor adds places to
drop and things to take out.
- **Drop targets are `into`.** A sound file on a strip loads into that
  sound; an effects file on a strip's inserts or on the master chain; a
  mod rack on the rack. Anywhere else, the page asks, as Open does. The
  arrival card shows what is replaced and brought and the RAM after, in
  percent of the budget;
  "Load without its modulation" when the rack is full; over budget is
  refused with no choice (owner) — `06-project` shows both.
- **Out, per block:** "Export Sound 3…", "Export S3's effects…", "Export
  mod rack…", "Copy a link" (`#lunar=`, deflated JSON, up to 32 KiB), "Save
  to my library", and in Chromium a strip dragged to the desktop becomes a
  file. Every file is written by C's canonical writer in the shadow
  Worker, so the editor's files diff like everyone's.
- **Links:** `?view=edit&sel=s3.fx1:Cutoff` opens the editor at a
  parameter; with `?load=guide/…` a guide mission can open straight into
  the right block. `sel` is a new hint, applied after the load and the
  POWER press like the others.
- **Loads through the Worker** (a request to W1). W1 runs pass 1 in the
  shadow Worker and posts the checked file to the worklet as binary, so
  the audio thread never parses JSON; the worklet's pass 2 is unchanged.
- **Storage.** W1's IndexedDB stores `files`, `autosave` and `recent`; the
  editor adds `snapshots` for A/B. Layout, the follow toggles and the keys
  mode are preferences in localStorage under `lunar.sim.editor.`. Every
  access in try/catch; with storage blocked the editor works in memory.
- **A/B** (B). A is set when a sound is loaded or with A; B is now. The
  diff comes from the shadow module, record by record. Hearing A loads it
  into the same sound (its notes released, the transport running); "Make
  B from the picks" is one batch and one undo step.

## 10. The views

| View | Holds | Mockup |
| --- | --- | --- |
| Flow and effects | The four strips (arp, engine, In1, In2, level) into the Mix and the master chain, each block with its meter and its cable or refusal count; drag to move or swap, with the RAM verdict before the drop; the selected block's inspector below | 01, 03 |
| Sound | One sound's engine by its pages, both inserts, the arpeggiator (the first three pages open, the rest as summaries), the cables into it in words, the detail bar | 02 |
| Modulation · Table | The rack as cards with live traces; the matrix with filters, sort, marks in words, reasons and fixes; the slot and module inspectors | 04 |
| Modulation · Map | The same slots as cables, with focus | 05 |
| Compare, Memory | A/B of one sound; RAM by part, in percent of the budget, and "what would fit" | 06 |
| Files and history | Drop, arrival, export, the library, the history | 06 |

**Search** (⌘K, B) reads the mirror and the metadata, so it covers what a
save holds and nothing else: words match names; `>cutoff` is "into",
`lfo1>` "out of"; `!` refused, `~` late, `v` per voice; `s2` a sound; `hz`
a unit. Results are grouped (cables, parameters, lanes, commands); ⇧Enter
selects every match for one batch edit.

## 11. Controls and the visual language

The same meanings as the screen and the page (`PALETTE.md` v2), the same
line kinds as the manual, on the page's dark theme. Rules name roles,
never hues.

| Role | In the editor |
| --- | --- |
| select (iris) | The selected row, block, slot or cable; slider fills; the pressed segment; focus rings; the flash of a change from the panel |
| held (gold) | A block in hand while dragging; a lane that locks a value (the dot); the arpeggiator's lit LED |
| live and mod (foam) | Meters and traces; cables and jacks; modulated labels, brackets and cable chips; the link dot |
| refuse (love) | Refused cables, drops and loads; "% over"; over budget |
| context (rose) | Context lines ("On the panel now: FX · S3 In1"), the detail bar's path, "changed since loaded"; never on a line where love can appear |
| sound 1–4 | Strip frames, tags, level fills, RAM segments, always with the S-number |

| Line kind (manual) | In the editor |
| --- | --- |
| audio, solid | The flow's connections, in the sound's colour before the Mix |
| modulation, dashed | Cables |
| gate, dotted | Gate cables; gate jacks are square |
| refused, dashed in love with ✕ | Refused cables, ending before the jack |
| per voice (new) | The dashed cable over a translucent band, `v` on its pill; offered to the manual's diagrams |

Type: Audiowide for the brand and section titles, Exo 2 for the rest, with
tabular figures; both ship with the page (SIL OFL 1.1).

**Memory is a percentage** (owner, 2026-10-06). Every memory figure the
editor shows (totals, costs, what is free, what would fit, refusals) is a
whole percentage of the FM-1's budget, computed from C's figure and
rounded up as the screen's meter rounds, so the screen, the page and the
editor never differ by a percent [verified: `draw_ram_meter` in
`fm1_app.c`]; a cost under 1 % reads "under 1 %", and a refusal says by how
much ("13 % over"). Bytes and kilobytes stay in developer docs (§20.2).

## 12. The audio thread and performance

- **The worklet's extra work** with the editor open: applying at most 64
  records a quantum, draining the change ring (256 entries [inferred]),
  and filling one telemetry block when a buffer is free. Target: under 2 %
  of a 128-frame quantum, about 58 µs at 44,118 Hz [inferred; measured
  with a counter in ED1].
- **Never on the audio thread:** JSON, value text, pass 1, hashing, diffs,
  metadata. A whole-project snapshot is a binary write (about 16 KB
  [inferred]) and happens only on open, on overflow and for undo's
  fallback.
- **Telemetry** (layout in the metadata): peak and RMS per sound, per
  insert and for the master in and out; gain reduction for Comp, Limiter
  and Squash; each module output's last value with its min and max over
  the frame (so a fast LFO draws its envelope, not an alias); per-voice
  outputs; each routed destination's effective value. About 230 floats,
  under 1 KB a frame [inferred: A]. Only what is visible is filled
  (IntersectionObserver); nothing while the tab is hidden; 15 Hz under
  reduced motion.
- **No SharedArrayBuffer**: it needs cross-origin isolation headers, which
  GitHub Pages cannot send [reported: A, B].
- **Coalescing.** A drag sends at most one op per animation frame for each
  parameter; `changes` is at most one batch a frame; the embed API's
  `changed` stays at 4 a second (ST15).
- **The main thread:** slider rows change one style property a frame;
  cables are SVG paths laid out only on resize or a structural change;
  traces draw on canvas in one requestAnimationFrame pass. Budget: 4 ms of
  script a frame, no long task over 50 ms while dragging.
- **Measured, not assumed** (ED1, ED5): zero underruns during a 30-second
  edit storm with the song playing, in Chromium, Firefox and WebKit.

## 13. Accessibility and keys

- **Sliders** are `role=slider` with `aria-valuetext` from C's text and the
  modulation spoken ("Cutoff, 420 hertz, modulated by LFO1, plus 35
  percent"). Arrows move one detent (the metadata's `step`), ⇧ ten, ⌥ a
  tenth; Home and End the ends; Enter types a value; D restores the
  default; C makes a cable into it.
- **Lists** are radio groups or comboboxes with type-ahead.
- **Every drag has a keyboard twin:** Space picks a block up, arrows move
  it, Space drops, Esc cancels; ⌥↑ and ⌥↓ swap with the neighbour; every
  block has "Move to…".
- **The matrix table is the canonical modulation view** for keyboards and
  screen readers; the Map is a picture of it, with its own Enter-to-patch.
- **Announcements:** polite, at most one a second, for changes from the
  panel, refusals and loads; never for live values.
- **Colour is never the only cue:** S-numbers with sound colours, the marks
  `> v ~ ! –` with words, line styles, "% over" spelt out. Contrast from
  PALETTE.md's checked tokens; forced colours map cables to system colours
  and keep their dashes.
- **Targets** at least 24 px (rows 29 px, segments 24 px); focus rings in
  the selection colour, 2 px. **Reduced motion:** no flashes or moving
  dashes; meters still move, because they are information.
- **PLAY and EDIT** (B). The page maps computer keys to the FM-1's keys.
  While the panel has the focus they play it (PLAY); a click in the editor
  or ⌘E gives them to the editor (EDIT); Esc gives them back. The Keys chip
  always says which, so a stray "X" never changes view while you mean to
  play.

## 14. Tablets and phones

- **1,024 px and up** (v1): the outline becomes a rail below 1,180 px,
  three columns become two, the Workbench stacks the panel above the
  editor, and the Editor layout shows the FM-1's screen in the head
  (mockups at 1,024).
- **Phones** (ED5, last; A's design): Panel and Edit are tabs; Edit keeps a
  96 px screen at the top; strips stack; the matrix becomes a cable list
  with "Add a cable" as a three-step sheet (source, destination, amount);
  no Map; a long press opens a block's menu.

## 15. Licences and the GPL switch

- The editor's code is this repository's (MIT) and part of the page, under
  the page's licence notice: while `FM1_GPL_MODS` is on, the public module
  is offered under GPL terms, the licence named and the source linked
  (CLAUDE.md). The editor adds nothing to that notice.
- The metadata carries each module's licence. Pickers show it beside the
  credits, and a GPL engine gets a "GPL" chip; a file naming a GPL engine
  in a build without it gets the known-ids reason ("in the GPL build
  only").
- Files hold data, never code; their licence field follows the state note
  (MIT for guide files, ST19).

## 16. Later: our firmware on a device (design only)

- The editor talks to a **target** with five calls: apply records and
  verbs, subscribe to changes, subscribe to telemetry, snapshot, load.
  Only the simulator target is built.
- A device target would carry the same records in the state note's frame
  (`F0 7D 4C 75 …`, §15 there): a new `EDIT {records}` with its verdicts,
  a device-to-host `CHANGES`, and low-rate telemetry; files keep `GET` and
  `PUT`.
- **Not from the browser.** ST18 stands: the page refuses ports named FM-1
  and is not the transfer tool. The host tool, which talks only to units
  that identify as `FM-1_5xx` and answer our `HELLO`, is the only thing
  that could carry the editor's records; how the page would reach it (the
  host tool serving its own copy of the editor, or a local bridge, which
  is a new attack surface) is an owner decision for after the gate.
- **Not before** the dump-and-restore gate on the unit in question (the
  one rule). Until then the editor requests no MIDI permission at all.

## 17. Tests

- **Metadata:** `meta.json` pinned like the state branch's fixtures; it
  validates against `metadata.schema.json`; the module's `fm1w_meta_id`
  matches it; every engine, effect, MIDI effect and kind renders an
  inspector with no overflow.
- **No hard-coding:** the editor's code contains no engine, kind or source
  id (a grep in CI).
- **Formatting:** `fm1_param_parse(fm1_look_value(v)) == v` for every knob
  step of every parameter.
- **Parity of hands:** for a sweep of random ops, the editor's op and the
  equivalent panel gesture (or `--mod` line) give the same state hash and
  the same change-ring entries.
- **Refusals:** each code reaches the editor with C's words, and the state
  hash is unchanged.
- **Sync:** a panel turn reaches the editor within two frames; an editor
  drag reaches the screen; a lock playing changes no base.
- **Undo:** random edit sequences undone to the start end at the first
  hash; redo returns to the last.
- **Files:** export then import gives the same hash; each drop target; each
  refusal leaves the hash unchanged.
- **Layout:** this note's check (`assets/web-editor/src/editor.js`) on the
  real editor at 1,440, 1,024 and, after ED5, 390 px, plus axe-core;
  keyboard-only cable creation; reduced motion.
- **Audio:** zero underruns with the editor open during a 30-second edit
  storm, and the telemetry stopped while the editor is hidden.
- **Keys:** in PLAY no editor command fires; in EDIT no FM-1 key sounds.

## 18. Build plan

The order follows the state note's (§18 there): E1–E3 and P1 first; A1,
W1 and S9+ after the UI colour and fonts stage (landed in PR #75); then
this train. The editor's lanes touch `sim/web/src` and the page, so they
run one at a time.

**Decided** (owner, 2026-10-06; ED18): **ED0 after the state core (E1–E3)
lands; ED1 after A1; ED2–ED5 after W1**, in that order, before the master
chain's four slots and two sends.

| Stage | Contents | Needs |
| --- | --- | --- |
| **ED0** Metadata and C helpers | The metadata additions of §6 in E2's `fm1-render --meta`, with their golden; `fm1_param_parse` and its round-trip test; per-slot refusal codes and the loop each late slot closes, in the planner's info | `engines/` and `tools/` only: after the state core (E1–E3, with E2's metadata export) has landed |
| **ED1** Edit layer and shadow Worker | `fm1_edit.c` (live apply of records and verbs, the change ring with sources, telemetry with a subscription mask, the view record and knob map); the hooks in `fm1_app.c`; the wasm exports and worklet messages of §5; `editor/shadow.worker.js`; the parity, refusal and underrun tests. No UI | A1 |
| **ED2** Shell, flow and sound | The layouts, outline and screen card, app bar and RAM by part; the Flow (selection only) and the Sound inspector from metadata; the detail bar; follow both ways and K1–K4; history and undo for parameters; PLAY and EDIT | ED1, W1 |
| **ED3** Chains and modulation | Drag to move and swap with its keyboard twin and RAM verdicts; effect pickers; master inspectors with meters; the Mix; per-pad rows (API v4); the rack cards, the matrix table, slot and module inspectors; structural undo | ED2 |
| **ED4** Files and project | Drop targets, per-block export, the library, `view=edit` and `sel`; ⌘K search; A/B and the Memory page; undo's snapshot fallback | ED3 |
| **ED5** The Map and reach | The patch-bay Map with focus; phones; keyboard and screen-reader passes; the layout check in the page tests; a manual chapter | ED4 |
| later | The pop-out window; a song-list view on S9+'s data; an FM6 (DX7) voice editor, a later stage by the owner's decision (ED17); the device target (§16) | — |

- Each stage that adds state to the page adds nothing to the files: the
  editor writes only through ops and W1's file path, so the state note's
  save-coverage test still covers everything (B).
- The editor lands **before the master chain's four slots and two sends**;
  that stage then adds its rows to the editor in the same PR, as it adds
  its records to the files.

## 19. Owner decisions

**All decided** (owner, 2026-10-06): ED1–ED18 are adopted as recommended.
Each row below is the recommendation as adopted; ED17 and ED18 carry the
owner's additions, and the memory unit (§20.2) is settled under the table.

| # | Question | Decided (owner, 2026-10-06) |
| --- | --- | --- |
| ED1 | Where it lives | **Adopted.** On the simulator's page: Panel, Workbench and Editor layouts, modules loaded on first use, one wasm instance. Not an `/editor/` page over the embed API, not a second engine |
| ED2 | The vocabulary | **Adopted.** Edits are the state note's records plus four verbs (swap, move, current, view), applied live by one C edit layer the panel's handlers share. No engine rule in JavaScript |
| ED3 | The audio thread | **Adopted.** Binary only: packed records in, a change feed and telemetry out. JSON, value text, pass 1, hashes and diffs in a shadow Worker with a second module |
| ED4 | Metadata | **Adopted.** The state note's metadata export as a static `meta.json`, matched by `fm1w_meta_id()`; ED0 adds page names, the detent step, effect groups, refusal words and the telemetry layout |
| ED5 | Controls | **Adopted.** A slider and a typed value field at every width (LOG on its law, bipolar from zero); segments up to 8 entries, a list beyond. Knobs stay the panel's |
| ED6 | Grouping | **Adopted.** All of a block's pages at once, labelled with the device's page and knobs; K1–K4 chips in the Workbench |
| ED7 | The home view | **Adopted.** The Flow: four strips into the Mix and the master chain, drag to move or swap with a keyboard twin and a RAM verdict before the drop |
| ED8 | Modulation | **Adopted.** The matrix table is the editing view (and the keyboard, screen-reader and phone view); the patch-bay Map is a second view of the same slots, with focus, built in the last stage |
| ED9 | Follow | **Adopted.** Editor to panel on by default (view only); panel to editor on in the Workbench, never during a picker, a typed value or a drag; both are toggles |
| ED10 | Undo | **Adopted.** One page history for editor and panel edits, a drag as one step, inverse ops checked by a hash with a snapshot fallback; the sequencer keeps its own undo |
| ED11 | Live values | **Adopted.** One telemetry block a frame at most 30 times a second, only what is visible, in transferred buffers; no SharedArrayBuffer |
| ED12 | Keys | **Adopted.** PLAY and EDIT modes, decided by focus, ⌘E and Esc; the mode always on screen |
| ED13 | Files | **Adopted.** W1's files, storage and links unchanged, plus drop targets, per-block export, `view=edit&sel=` and a library view; and ask W1 to run pass 1 in the shadow Worker and load the worklet in binary |
| ED14 | Reach | **Adopted.** Desktop and tablet in v1; phones (tabs, a cable list, no Map) in the last stage |
| ED15 | The device | **Adopted.** Nothing before the gate; ST18 stands, the browser never sends; records stay transport-agnostic so the host tool can carry them later; how the page reaches it is decided after the gate |
| ED16 | Licence display | **Adopted.** Each module's licence from the metadata, a GPL chip in pickers; the editor is MIT page code under the page's notice |
| ED17 | Scope of v1 | **Adopted.** Sounds (engine, inserts, arpeggiator, per-pad values), Mix, master, rack, matrix, A/B, memory, files. Not clips, lanes or the song list. **FM6 (DX7) voice editing is a later stage** (owner), not v1 |
| ED18 | Order | **Adopted, with the owner's order:** ED0 after the state core (E1–E3) lands; ED1 after A1; ED2–ED5 after W1, in order, before the master chain's four slots and sends; the pop-out window later (§18) |

**Memory figures** (owner, 2026-10-06; the open issue of §20.2): a user
sees memory only as a **percentage of the FM-1's budget**, wherever they see
it: the FM-1's screen, the page, the editor and every refusal message.
Bytes and kilobytes appear only in developer docs (DEVELOPERS.md,
`engines/README.md`, notes). The editor's rule is in §11; the places that
still show KB today are listed in §20.2.

## 20. Found on the way

1. **The state example "Deep bass" cannot load into a busy project.** It
   plays Shapes, 207,128 B at 44,118 Hz, 53 % of the budget on its own
   [reported: A's measurement]. Into "First orbit"'s S3 it would need about
   464 KB of 378.8, so it is refused, as `06-project` shows [inferred: A's
   sizes]. Mission 2.3's file should start from a project with room, or
   use Macro; a note for the guide lane.
2. **Two units for a kilobyte. Resolved: percent only** (owner,
   2026-10-06; §19). The state note's RAM refusal example says "the FM-1
   has 388 KB" (1,000 B) while the page's status line says 379 KB (1,024 B)
   for the same 387,924 B [verified: both texts]. Rather than pick one
   kilobyte, a user now sees memory only as a percentage of the FM-1's
   budget; bytes stay in developer docs. Places that show memory in KB to
   users today, for the lanes that own them [verified: main at `96fae8a`]:
   - the FM-1's screen: both RAM refusals ("…K over budget", for an engine
     or effect and for the arpeggiator) and GLO's RAM line ("…K/379K"),
     in `sim/web/src/fm1_app.c`;
   - the page's status line ("Chain RAM … KB of the … KB the stock layout
     leaves free"), `showStatus` in `sim/web/www/app.js`;
   - the manual's memory figures, in chapters 3, 5, 6 (including its
     sentence that the global page shows KB) and 13 (the memory budget and
     the size table);
   - the state note's RAM refusal example, on its branch.
   File sizes (a DX7 file the simulator reads up to 64 KB, a set sent over
   MIDI) are not memory figures [inferred], and whether the specifications
   chapter's hardware sizes (578 KB of SRAM, 1 MB of flash) stay is a
   question for the owner.
3. **RAM figures round up.** 300,672 of 387,924 B is 77.5 %, and the
   screen says 78 % [verified: the harness's figures; `draw_ram_meter`
   in `fm1_app.c` divides with `+ FM1_APP_RAM_BUDGET - 1`]; the page's
   status line rounds kilobytes up too (`Math.ceil(b / 1024)` [verified:
   `app.js`]). The editor shows C's figure as the screen's meter rounds it,
   so no two views differ by a percent (§11).
4. **A refused cable still marks its destination as modulated on the
   screen.** M1 Master Sat's Drive shows the modulation label and bracket
   although its only cable (slot 6, per voice into an effect) is refused
   [reported: A, a render on the UI colour lane; not re-checked here]. The
   mark probably tests "a slot is on" rather than "on and not refused"
   [inferred]; a one-line fix for the modulation view's lane.
5. **Glide and Voice Mode are now in the export.** A found the host's
   per-sound page missing from `fm1-render --list`; on the UI colour lane's
   build they are Macro's uids 13 and 14 on page 4 [verified], so ED0 has
   nothing to add for them but their page name.
6. **The metadata schema has no page names.** The arpeggiator's seven
   pages have names on the screen but only numbers in the export
   [verified: `metadata.schema.json`]; ED0 adds them (§6).
7. **The browser's catalogue is not the editor's source.** Its static
   buffer is 49,152 B [verified: `fm1_app.c`] and carries no uids, flags or
   modulation tables; the editor reads `meta.json` instead and leaves
   `fm1w_catalog` to the panel.
8. **Pass 1 belongs off the main thread.** The state note runs it in a
   second instance on the main thread (§10.1 there); a Worker keeps a
   30 KB file from stalling the page, and the same instance serves the
   editor (ED13).
