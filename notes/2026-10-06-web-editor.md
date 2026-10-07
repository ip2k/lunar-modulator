Marks here were checked on the ED5b branch, cut from main at `22c75af`
(PR #95, ED5a): the module built and its parity and storm measured natively
and in WebAssembly on aeon, and the page tests run in headless Chromium 153,
Firefox 155 and WebKit 26.6 (Playwright 1.63 in its container on aeon). ED5b
is the second half of §18's ED5 row; with it ED5, and the train ED0 to ED5,
is built.

**What was measured, and what was not** (the final tree, `fm1.wasm.json` and
the page tests' reports of 2026-10-07):
- Module: 104 of 104 scenarios identical to the JavaScript harness and to the
  musl build, 101 to glibc (largest difference 1 LSB); the module is
  byte-identical to the one ED5a shipped (`06a4f93e...`); the edit layer's
  parity is ok with 0 LSB of difference in the audio; the 30-second storm in
  the real worklet's port: 10,341 quanta, 82,728 edits applied, **0 late**,
  p99 0.096 ms against a 2.9 ms deadline.
- Page tests, each browser, the same tests: `editor-ui` 93 of 93 checks,
  `editor-reach` 31 of 31, **`editor-map` 35 of 35** (the Map at 1,440, 1,024
  and 768 px with the layout probe, none at 375 px, focus, a cable by pointer
  and by keys with C's verdict, a refused cable, "n more", 32 cables, a 33rd
  refused), and the storm of `editor.mjs`, 30 s, 10,695 quanta in each, 0
  refused edits, 0 resyncs (Chromium 7,242 edits applied, Firefox 7,204,
  WebKit 3,757).
- **Not measured in Firefox and WebKit:** lateness and underruns. The
  harness times the worklet and counts underruns only where Chromium's
  `playback` statistics exist; Firefox and WebKit report `late: null`. Their
  runs show the page drives the module through the same messages and the
  edits all apply; they say nothing about their audio latency. Neither was
  run with a real audio device (Firefox on a PulseAudio null sink, WebKit
  with its own), nor on a phone or a tablet's touch; the Map's drag was
  driven by pointer events from Playwright, never by a finger.
- Looked at (the screenshots, not only the probe): the Map at 1,440, 1,024 and
  768 px, focused, with a refused cable, selected, and with all 32 cables, in
  Chromium; the focus picture in Firefox and the 768 px one in WebKit. No
  label sits on a cable or on another label. Two things seen and left: at 768
  px the rack's *n more* wraps to two lines in the narrow blocks (not clipped),
  and a refused cable's pill, when it is the selected one, may sit over another
  cable in the gutter (the declared exception; no clear place exists there).
- The manual (chapter 15 and `{{page}}`): the strict build (`tools/manual/build.py
  --site ... --pdf --strict`, the Pages workflow's command) ran on aeon on the
  branch before its five pictures were made again for the final tree: 17
  chapters, 0 errors, 0 warnings, a 270-page PDF. Only the picture files
  changed after it, under the same names; that build was not repeated, and the
  local venv has no `markdown`, so CI's build is the check on the final tree.

**What it is** [verified: `sim/web/src/fm1_edit.c`, `fm1_edit.h`]:
- **One edit layer** as §5 has it: `fm1_edit_apply` (records),
  `fm1_edit_verb` (swap, move, current, view), `fm1_edit_packed` (the
  worklet's 24-byte form of both), `fm1_edit_changes`,
  `fm1_edit_telemetry` with `fm1_edit_subscribe`, `fm1_edit_view`. Records
  go through the app's own calls: `fm1_app_set_param`, `fm1_app_select`,
  the level, the arpeggiator's, and for the rack and the matrix the RACK
  and MATRIX pages' own `fm1_mod_ui_set_*`, so they emit the same `--mod`
  lines. A pad's own value (API v4) moves the focus to the pad for the
  write and back.
- **One truth.** The panel's keys, buttons and encoders enter as source
  PANEL (`fm1_app_key`, `_button`, `_encoder` wrap their handlers), so the
  hooks give the panel's changes and the editor's the same entries. The
  check replays seven panel gestures' ring entries as editor ops on a fresh
  app and gets the same entries and the same state hash [verified].
- **The change ring**: 256 entries of 32 bytes (gen, source, tag, the packed
  record); a load is one `LOADED` entry; a reader more than a ring behind
  gets `RESYNC`. Modulation changes are found by comparing the runtime with
  a snapshot after every modulation edit, so the pages, script lines, the
  engine-change rule's re-aimed cables and the editor all show up; a moved
  module shows as the two positions' records and the cables' new ends.
- **Telemetry** fills `fm1_tele.h`'s block for the subscribed rows only.
  The block comes at most every 1/30 s of audio; with 128-frame quanta that
  is one every 12, 28.7 a second at 44,118 Hz [verified: 862 in the 30-second
  storm]. Not filled yet, said in the code: Limiter's and Squash's
  reduction (no read-out; Comp's and the output limiter's are), and
  `voice_dests` (NaN: the runtime keeps each voice's offsets but has no
  read-out). Destinations read as the last block ran the plan, never
  building it early. With every row subscribed the audio is the audio
  without the layer, bit for bit [verified: `--edit-check`].
- **The wasm exports and worklet messages of §5**, binary only: the
  editor's own port (`editor-port`), at most 64 records a quantum, `edited`,
  `changes`/`resync`, `view`, `telemetry` in two pooled buffers,
  `snapshot`, and `stats` with the late quanta. The shadow Worker is the
  existing `www/shadow.worker.js` (W1's), extended with `metaId`, `meta`,
  `format`, `parse`, `hash` and `diff`; no new file.
- **ED0's leftovers.** `fm1_param_parse` (in `fm1_edit.c`, declared beside
  `fm1_look_value`) with its round trip: 467 parameters, 34,376 knob steps,
  every one read back as the screen shows it [verified]; the criterion is
  the displayed value (within half the last printed digit), since 1,039
  neighbouring steps print the same text and one step can print "100.0"
  and read back as 100, which prints "100". The loop each late slot closes
  is a question, as ED0 made the per-slot reasons: `fm1_mod_slot_loop`
  returns the component and its positions, checked on every delayed slot of
  the planner's fuzz (43 in 1,000 racks) [verified].

**Differences from the plan.**
- **A cable's refusal codes are verdicts, not refusals.** A cable that is
  on but that the planner leaves out is written, as the panel's MATRIX
  writes it, and its verdict is the planner's reason (32-41). Every other
  code changes nothing: the check holds the state's hash and the ring
  unchanged for each [verified].
- **Codes an edit cannot meet today**: NOT_LUNAR, TOO_NEW, TOO_BIG and
  STOPPED are a file's; NO_MOD needs a float without MOD, which no module
  has (every float takes a cable unless NOLOCK); ARENA needs an effect or a
  kind larger than its arena, which none is, even at 96 kHz; VOICE_ROOM
  cannot happen with today's kinds (§21). The other thirteen are reached
  through the layer [verified: `--edit-check`].
- **`move` of an effect slot is a swap**, as the slots come in groups of two
  until the master chain's four slots; `move` of a rack module is
  `fm1_mod_ui_move`.
- **The view verb** takes a file's view keys, checked (a key out of range
  refuses), and an `entry` key for FX's slot (In1, In2, Mix, M1, M2), which
  a file's view has no need of.

**Found on the way.**
- **`fm1_mod_move` read past its permutation** for a slot whose source or
  VIA names nothing past the last position's ports (128-254): `remap_src`
  indexed `perm[]` with (src - 64) / 8. The panel cannot make such a slot,
  but an editor's cable record can (the planner refuses it, NO_SOURCE). The
  check's fuzz of hostile records found it under AddressSanitizer; such a
  source now stays as it is, with a test in `fm1-mod-refusal-test`. The
  fuzz (12,774 records and verbs, fields random and at their edges) then
  runs clean under ASan and UBSan, but for an old left shift of a negative
  value in `third_party/fm1-x0x/dsp/fastmath.h`, which is not this stage's.

**Measured** [verified: `test/edit.mjs` on aeon, Node's V8 in the
emscripten/emsdk container]: the module and the native harness give the
same verdicts, ring, view and state hash for `test/edit/verbs.edit`, the
same screen less its RAM figure, and the same audio (0 LSB apart). The
30-second storm (the demo song playing, eight records a quantum, the change
feed drained every sixth quantum, every telemetry row filled when due):
**0 late quanta of 10,341**, median 0.062 ms, 99th percentile 0.096 ms,
slowest 0.25 ms of the 2.90 ms a quantum plays; the edit layer's own work
7.9 µs a quantum, under §12's 58 µs. **In the real AudioWorklet**
(`test/editor.mjs`, headless Chromium 153 on aeon, 44,100 Hz, the demo song
playing): 30 seconds of 7,252 ops, 58,016 records, every one applied with
verdict 0, 1,724 change batches, 905 telemetry blocks handed back and
reused, a binary snapshot; **Chromium's own playback stats counted 0
underruns** [verified]. Chromium's AudioWorklet scope has no clock
(`performance` is absent), so the worklet's own late-quantum counter reads
"not timed" there; headless Chromium plays to a fake output device, so a
desktop browser with a real one, Firefox and WebKit remain to be measured
(ED5). The module grew by 26,249 B, to 1,538,812 B, after main's S9+. The
104 parity scenarios still match fm1-render [verified: 104 of 104, audio
identical to the JavaScript and musl builds, screens identical], and the
layout sweep passes 4,584 screens with no fault.

## 23. Stage ED2, as built (2026-10-06)

Marks here were checked on the ED2 branch, cut from main at `c9b4c40`
(PR #91, ED1), natively, in node against the module, in the browser pane
and in headless Chromium on aeon.

**What it is** [verified: `sim/web/www/editor/`, `sim/web/README.md`, "The
advanced editor"]:
- **Where it lives** as §4 has it: plain ES modules in `www/editor/`
  (`model.js` and `history.js` with no DOM, `editor.js`, `editor.css`),
  imported on the first switch away from Panel; the page's one module in the
  worklet, the editor's own port, the shadow Worker of W1 and ED1 for text,
  JSON and hashes. The layout switch is the page's (`index.html`), moved
  into the editor's app bar while the editor shows.
- **The shell:** the app bar (the switch, the keys chip, the two follow
  toggles, Undo and Redo, RAM by part), the outline (S1-S4, the Flow; a rail
  in the Workbench and below 1,180 px), the screen card in the Editor layout
  (the panel's frame drawn a second time), the detail bar (the parameter's
  path in the context colour, its value, range, default, flags in words and
  its keys), the history list.
- **The Flow** with selection only: four strips into the Mix, M1, M2 and the
  output, each with the level and a meter from the telemetry block; the
  selected block's inspector below. **A sound**: its path, its engine by the
  device's pages with its level, both inserts, its MIDI effect (three pages
  open, the rest as summaries).
- **Controls from metadata only**, §6's table: 360 shown parameters in this
  build, 274 sliders, 56 segment rows, 14 grids, 13 lists and 3 filtered
  lists [verified: `test/editor-unit.mjs`]; values in C's text and typed
  values read by C's parser, both in the shadow Worker; no engine, kind or
  source id in the code (`tests/test_sim_editor_ui.py`).
- **Follow both ways and K1-K4** (§7), **one history for both hands** (§8),
  **PLAY and EDIT** (§13), as `sim/web/README.md` details.

**Differences from the plan.**
- **RAM by part is C's**: `fm1_app_ram_part` (four sounds with their inserts
  and MIDI effect, the master slots, the rest) and `fm1w_ram_part`, posted
  by the worklet's editor port as `ram` when a figure moves; the six parts
  add up to the meter's figure [verified]. Each part reads in percent of the
  budget, rounded up as the screen's meter, "under 1 %" below one; so the
  parts can add up to a percent or two more than the whole.
- **The Workbench is side by side from 1,400 px, not 1,280:** the page keeps
  the panel at 800 px or more, below which its smallest targets fall under
  24 px; between 1,024 and 1,400 px the panel sits above the editor.
- **Undo is by value only**, as ED2's row has it: a step goes back by
  sending its `before` as an edit. A step whose block has another engine
  since (the panel changed it) is refused in words, not applied to the new
  engine's parameter of the same uid. The hash check and snapshot fallback
  of §8 are ED4's; the tests do the hash check instead.
- **A MIDI effect's page cannot be opened on the panel by the view verb**
  (its keys have no ARP page), so selecting one opens its sound's HOME.
- **The page has one theme**, the dark one (`color-scheme: dark`): a light
  system setting changes nothing [verified: the browser pane, both settings].
- **Per-pad rows** (API v4) are ED3's: a kit's per-pad parameters show and
  edit the focused pad, as the knobs do.

**Measured** [verified]: `test/editor-unit.mjs` against the module: every
check passes, 120 random edits over the start chain undone to the first
state hash and redone to the last. The module is rebuilt for
`fm1w_ram_part`; parity 104 of 104, the edit layer's parity and storm (0
late quanta of 10,341). `fm1w_ram_part` grew the module by 233 B, to
1,539,045 B. In headless Chromium 153 on aeon (`test/editor-ui.mjs`), every
check passes: the Panel layout requests none of `editor/`; a turn of KNOB2
reaches the editor's row in 3 frames (32 ms) as a panel entry with
"From the panel: KNOB2"; the K1-K4 chips are the knob map's four; selecting
M1 in the Flow puts the panel on FX M1 within 150 ms; four arrow keys in
EDIT are one history step and send no key to the FM-1, Ctrl+Z puts the
project back (the shadow Worker's diff: nothing but the view, which follow
moved) and Ctrl+Shift+Z forward; in PLAY the keys play and D edits
nothing; all 40 modules' inspectors (720 rows) at 620 and 360 px with no
overflow or overlap; the Workbench and Editor layouts, Flow and sound, at
1,440 and 1,024 px with no sideways scroll and nothing overflowing. The
eight screenshots and the browser pane's renders (light and dark system
settings) were looked at. Not measured here: Firefox and WebKit, a desktop
browser's real audio device, screen readers (ED5).

**Found on the way.** The shadow Worker's `hash` covers a project's view,
unlike C's `fm1_edit_state_hash`, which leaves it out: a follow that moves
the panel changes it. §8's hash check (ED4) should compare without the view
[verified: `diff` of the two projects names `view.mode` and `view.unit`
only].

## 24. Stage ED3, as built (2026-10-06)

Marks here were checked on the ED3 branch, cut from main at `835c15e`
(PR #92, ED2), natively, in node against the module, in the browser pane
and in headless Chromium on aeon.

**What it is** [verified: `sim/web/www/editor/chains.js`, `sim/web/README.md`,
"Stage ED3"]: §18's ED3 row, in one module beside `editor.js`:
- **Move and swap** with the verdict before the drop: a pointer drag past
  6 px or the keyboard twin (Space, arrows, Space; Esc; ⌥ and an arrow for
  the neighbour; *Swap with…* / *Move to…*). The verdict is the shadow
  Worker's new `preview`: the verb applied to a copy of the live state, its
  code and the RAM after in percent, or the refusal in the metadata's words.
- **Pickers** for engines, effects (by the metadata's groups), MIDI effects
  and rack modules: every choice tried alone on the live state (`preview`
  with `each`), its RAM after or C's refusal; a choice C answers BAD is not
  offered.
- **Meters** for inserts, master slots and the Mix from the telemetry
  block, found by the layout's order, with gain reduction where C reads it
  out; *Make current* (the current verb).
- **Per-pad rows** (API v4): a pad strip above the rows marked *pad*; a
  per-pad edit names its pad in the record, the mirror keeps every pad.
- **Modulation** (ED8): the rack's cards with a live trace and cable count,
  the matrix table (filter, empty slots, sort, *Add a cable*; On, From, VIA,
  To, Amount, live value, the planner's verdict in words, marks `v ! –`),
  the slot inspector (every field, *Remove*) and the module inspector
  (pages, outputs live, gate inputs and what reaches them); each block's
  inspector lists the cables into it. The Map is ED5's.
- **Structural undo**: a choice keeps the records that put the block back
  (its unit, every value, a kit's pads) and the matrix as it was; a swap
  undoes by itself, a move by the move back; redo sends the edit again; the
  panel's structural changes enter the same history from the mirror as it
  was.

**Differences from the plan.**
- **The rack and the matrix come from C as records**: `fm1w_mod_records`
  (new export, used by the shadow Worker only) writes a MODULE record per
  position, a CABLE record per slot and each slot's planner verdict. The
  editor reads cables by their codes and names them from the metadata
  (`mod.sources`, `mod.units`, each kind's `outs` and `gates`), so it never
  reverses a file's names or its percent rounding.
- **An effect into an insert of a sound with no engine is refused** (BAD)
  by the edit layer, as a record or a swap: a file writes a sound's inserts
  with its engine, so such an effect vanished from every save and every
  hash. The random structural undo test found it; `fm1_edit_check` swaps
  into that slot only after giving the sound an engine. The panel was not
  changed.
- **Previews read the last snapshot**, not a fresh one: the editor keeps the
  binary it last mirrored (taken again after every structural change), so a
  preview costs the audio thread nothing; values moved since do not change
  a RAM figure.
- **Undo is still by records**, as §8 has it; the hash check and the
  snapshot fallback stay ED4's. The tests check by hash instead.

**Found on the way.**
- A refusal shown in the detail bar was wiped by the redraw that the
  snapshot after it brings (ED2 had the same): it now stays for 8 s or until
  another parameter is selected.
- The history holds 200 entries; a test that counts steps by its length
  stops counting at the limit. The page checks count by entry id.

**Measured** [verified]: `test/editor-unit.mjs` against the rebuilt
module: every check passes; the packed CABLE and MODULE records come back
through the feed and `fm1w_mod_records` as sent; six hostile records and
verbs (an engine swapped with an insert, an unknown kind or effect, slot 40,
an effect into an empty sound's insert, a swap with one) are refused with
the state hash unchanged; 28 random structural edits through `chains.js`
(17 steps after C's refusals) undo to the first state hash and redo to the
last. In headless Chromium 153 on aeon (`test/editor-ui.mjs`), every check
passes: the keyboard twin shows "Swap · RAM 69 %" over S1 In1 and swaps M1
into it as one step, the keys staying with the block; a pointer drag shows
the same verdict and swaps; M1's picker lists 25 choices with the RAM after
each; S1's engine cannot be emptied (not offered; asked anyway, "Cannot be
read" and nothing changes); a cable added, its amount typed (-40 %, Q1.14
-6554) and polarity set, aimed at a parameter that rebuilds the voices
(the planner's NOLOCK in the metadata's words); a rack module moved by keys
to the first empty place (the others close up, as `fm1_mod_ui_move` does),
one chosen and one emptied; each undone to the state before it, the view and
the current sound aside (follow moves them). All 56 modules' inspectors (the
40 engines and effects and the 16 rack kinds) at 620 and 360 px with nothing
overflowing; the Workbench and Editor layouts, Flow, sound and Modulation,
at 1,440 and 1,024 px with no sideways scroll; the screenshots were looked
at. The module grew by 679 B, to 1,539,724 B; parity 104 of 104, the edit
layer's storm 0 late quanta of 10,341, Chromium's 0 underruns, the layout
sweep 4,584 screens with no fault. Not measured: Firefox and WebKit, a real
audio device, screen readers, phones (ED5).

## 25. Stage ED4, as built (2026-10-07)

Marks here were checked on the ED4 branch, cut from main at `cf2ede3`
(PR #90, after ED3's PR #93), natively, in node, in the browser pane and in
headless Chromium on aeon.

**What it is** [verified: `sim/web/www/editor/project.js`, `sim/web/README.md`,
"Stage ED4"]: §18's ED4 row, in one module beside `editor.js` and
`chains.js`, over W1's paths in `files.js`:
- **Drop targets** (§9): a file on a sound (its MIDI effect, an empty
  strip), an insert, a master slot or the rack gets pass 1 as the kind the
  block takes before anything loads, and a card with C's words and the RAM
  after in percent; *Load* is W1's load. A library item gets its verdict
  while it hovers.
- **Export per block** and *Save to my library* (W1's `saveAs` and `files`
  store, with a kind); the *Library* view (saved and Recent).
- **Links**: `view=edit`, `sel=BLOCK[:Parameter]` (`files.parseSel`, a fixed
  shape; the editor finds the block and the name or says why not).
- **Search** (⌘K / Ctrl+K) over blocks, parameters and commands.
- **A/B** of the project or one sound (X switches; a load sets A), and the
  **Memory** page (each part, free, what would fit; percent only).
- **Undo's hash check and snapshot fallback** (§8) for the editor's
  structural entries.
- **ED1-ED3's leftovers**: the hash leaves the view out in one place (C's);
  the view verb opens the ARP pages; `tests/test_sim_edit.py` runs under
  ASan + UBSan in CI; the page tests that ED3's last commit missed ran.

**Differences from the plan.**
- **The hash leaves out where the panel is: the view and the current
  sound.** `fm1_app_state_save`'s binary 3 writes the project with nothing
  deflated, no VIEW record and `session.current` 0;
  `fm1_edit_state_hash` reads it, the module exports it as
  `fm1w_state_hash`, and the shadow Worker's `hash` calls that. ED3's tests
  compared "less the view and the current sound" by hand; follow moves
  both (the view verb makes a sound current), so a hash with either in it
  failed every undo that a follow had crossed. A file still saves both.
- **The ARP pages are HOME's `entry=2`** (with `page`), not a new view key:
  the view record and its file form are unchanged; `entry` 3 or more in
  HOME is refused (BAD), and so is entry 2 for a sound with no MIDI effect.
- **A desktop file's verdict comes on the drop, not before it**: a browser
  does not let a page read a dragged file until it is dropped, so the
  verdict card comes first and nothing loads until *Load*. A library item
  (the page's own bytes) has its verdict while it hovers.
- **Snapshots only when the editor's copy is current** (no change since it
  was taken, nothing on its way; it is taken again 400 ms after changes
  stop): an entry made otherwise keeps no snapshot and its undo is by
  records alone. The panel's structural entries keep none (their "before"
  has already passed when the editor hears of them).
- **A/B keeps its snapshots in memory**, not in an IndexedDB `snapshots`
  store; "Make B from the picks" is not built.
- **Search reads words only**: the `>cutoff`, `lfo1>`, `!`, `~`, `v` and
  unit forms and ⇧Enter's batch edit are left for later.
- **Words that are module ids** (`mix`, `compare`) cannot appear quoted in
  the editor's code (§17's check), so the A/B view is `ab` inside and the
  `sel` word for the Mix is matched by a pattern.

**Found on the way.**
- C's kind refusal reads "A sound, not a effects chain was expected" (the
  article is fixed in the format string): W1's words, left for a C pass.
- A file dropped from the desktop cannot be judged before the drop (above);
  the arrival card is the "before".
- The library's tiles' tags took the light text of a tag with no sound
  colour; on S4's yellow it vanished. They carry their sound's class now.

**Measured** [verified]: `fm1_edit_check` (native, `tests/test_sim_edit.py`):
the ARP view (HOME `entry=2` opens the ARP pages, the knobs turn the
arpeggiator), `entry=3` refused with the state and ring unchanged, and the
hash unmoved by a view verb, the ARP view and the current sound.
`test/origins.mjs`: 8 good `sel` values read, 25 hostile ones (tags, a URL,
`..`, control characters, overlong values, numbers past the blocks) refused.
In headless Chromium 153 on aeon (`test/editor-ui.mjs`), all 76 checks pass,
ED2's and ED3's included (so the page tests ED3's last commit missed have
run): M1's export is `first-orbit-master.fx.lunar` of kind `fx`; selecting
S1's arpeggiator opens the ARP pages on the panel; dropped on S1, a 300 KB
file, two files, a cut-off JSON file, 4 KB of random bytes, a DX7 SysEx and
a mod rack are each refused at the block in words ("This is not a Lunar
Modulator file.", "A sound, not a mod rack was expected.") with the state
hash unchanged and nothing asked, and a sound file shows "RAM 69 %" and
loads on *Load*; from the library, S1's effects hovering S4 show C's
refusal, S1's sound hovering S3 shows "Load · RAM 64 %" and loads there;
Ctrl+K, "memory", Enter opens Memory, "s1 Tune", ↓↑, Tab (kept), Enter
selects S1's Tune row, "zzzz nothing" says "Nothing matches", Esc closes;
Memory shows eight rows, 64 % in use and 36 % free, no bytes; A/B on Sound 1:
Tune 0 kept as A, End to 24, X hears 0 with one difference listed, X hears
24 again; an effect chosen into S1 In2 keeps a snapshot, its undo is
checked by hash (back to the first hash), and with its inverse records
taken away the undo loads the snapshot, back to the same hash; the links
open the editor at S1's Harmonics (address cleared), say an empty block
(`p8`) and an unknown parameter so, refuse four hostile `sel` values in
words with nothing injected, and refuse an off-site `load` with no request
leaving the page's origin. Library, Memory, Compare and the search at
1,440 and 1,024 px: no sideways scroll, nothing overflowing; the
screenshots were looked at. The module grew by 357 B, to 1,540,081 B;
parity 104 of 104, the edit layer's storm 0 late quanta of 10,341, the
layout sweep 4,584 screens with no fault, `screenshot.mjs`, `files.mjs` and
`editor.mjs` pass. Not measured: Firefox and WebKit, a real drag from a
desktop (the tests build the drop events), a real audio device, screen
readers, phones (ED5).

## 26. Stage ED5a, as built (2026-10-07)

Marks here were checked on the ED5a branch, cut from main at `15627bd`
(PR #94, after ED4), natively, in the browser pane and in headless
Chromium on aeon. ED5a is the first half of §18's ED5 row: reach and the
read-outs. The Map and the manual's chapter are ED5b.

**What it is** [verified: `sim/web/README.md`, "Stage ED5a"]:
- **Read-only taps, no new state.** `fm1_limit_gain` and `fm1_squash_gain`
  (`engines/include/fm1_dynamics.h`) read what the effects already keep
  (the Limiter's per-channel `red` and `red0`, chosen by the tests its
  render loop makes; Squash's `gain[2]`), so no instance grew and no golden
  moved. `fm1_mod_voice_dest` reads a voice's offset for a VOICE cable's
  destination and adds what the engine holds. The edit layer fills the
  `reduction` rows for both effects (a cut in dB) and the `voice_dests`
  rows (NaN where a voice has no value or a plan is pending). Where the
  runtime was left out of a build (`FM1_WITH_LIMIT`, `FM1_WITH_SQUASH`),
  the edit layer's references go with it (guarded in
  `tests/test_module_list.py`).
- **Display.** An effect's *Out* meter gets a thin reduction bar and "GR n
  dB" while the cut is over 0.05 dB and the meter point before it has a
  signal. A per-voice cable's *Live* cell reads the range of its voices.
- **Keyboard and screen reader (§13).** The snapshot test (below) found two
  things, both fixed: the per-voice badge ("v") was part of every
  poly slider's accessible name ("Harmonicsv"), and focus rings were the
  browser's where the CSS set none. The badge is an image named "per
  voice"; one 2 px ring covers the editor. Announcements are throttled
  to one a second (the first at once, then the latest).
- **Phones (§14).** Two tabs (Panel, Edit; the Workbench becomes Edit),
  the outline a row of tabs, a 96 px screen, stacked strips and rows, and
  the matrix a list of cables with its cells named. No Map, since there is
  none yet.
- **The layout probe** (`test/layout-probe.js`): overlaps and clipped text
  at four widths, a check §17 asks for and ED2-ED4 did not have.

**Found on the way.**
- **ED3's gain-reduction text never showed.** `onTelemetry` tested `db <
  -0.05` while C sends the cut as a positive number (Comp, the output
  limiter), so no "GR" was ever drawn. Fixed with the new rows.
- **Squash's gain is not 1 at rest.** Snap's gate state starts at 1 and
  closes the gain by about 1.4 dB over a first 30 ms of silence [verified]
  (and, by its formula, toward -12 dB over a long one [inferred]) even with Gate at -80 dB, its "off". Silence in
  gives silence out, so nothing is heard, but a raw read-out would show a
  constant "GR". The display shows the cut only while a signal goes in.
  Whether Snap's closed gate should be a read-out of its own is left open.
- At 375 px the ED4 editor scrolled the page sideways by 42 px (the rows'
  fixed columns); the phone layout is the fix.
- C's kind refusal, "A sound, not a effects chain was expected" (ED4's
  open issue), is still there: a fixed article in a format string.

**Measured** [verified]: native `--edit-check`: Limiter at Drive +24 dB
reads 1.794 dB of cut and Squash at 1 reads 11.757 dB with a note held,
Limiter at rest 0.000 dB; a per-voice cable's row has a value inside the
parameter's range for a sounding voice and NaN for a slot without one; the
audio with every row subscribed is the audio without the layer, bit for
bit. In headless Chromium 153 on aeon: `test/editor-ui.mjs` 93 of 93
(the 76 before, plus every view at 768 and 375 px, with the probe at all
four widths: no sideways scroll, nothing clipped or overlapping; the
screenshots were looked at); `test/editor-reach.mjs` 31 of 31: the
accessibility snapshot of six views names every control, every slider has
`aria-valuenow`, a valuetext starting with its name, and a label; one
polite live region (the search box's count aside), silent for 1.5 s of
idle; a refusal reaches it in C's words ("S1 engine: Cannot be read.");
thirty announcements in half a second are throttled, the last kept; 40
Tab stops, all in the editor, each with a ring of 2 px or more and a
target of 24 px or more; the first Tab into the editor gives it the keys;
at 375 px the switch has two tabs, the outline scrolls inside itself, the
screen is 96 px, the matrix header is gone and each cell is named, no
Map; a Limiter set to its Drive's end by the keyboard shows "GR 5.6 dB"
and a bar at 0.2; the example's per-voice cable shows `0.54-0.66`
while one note sounds. The module grew by 789 B, to 1,540,870 B (the
accessors and the rows); parity 104 of 104, the storm 0 late quanta of
10,341 (99th percentile 0.092 ms, the layer's own work 7.8 us a quantum),
the layout sweep 4,584 screens with no fault, `screenshot.mjs`, `files.mjs`
and `editor.mjs` pass. Not measured: Firefox and WebKit, a real drag, a
real audio device (Chromium's playback stats counted 0 underruns on the
fake one), a screen reader itself (only the snapshot Chromium builds for
one), a real phone (a 375 px viewport and a mobile user agent only), and
the manual's strict build (CI).


## 27. Stage ED5b, as built (2026-10-07)

Marks here were checked on the ED5b branch, cut from main at `22c75af`
(PR #95, ED5a), natively on aeon, in headless Chromium, Firefox and WebKit
on aeon, and (the manual) in the Pages workflow's Ubuntu 24.04 build on
aeon. ED5b is the second half of §18's ED5 row; with it ED5, and the train
ED0 to ED5, is built.

**What it is** [verified: `sim/web/README.md`, "Stage ED5b"]:
- **The Map** (`www/editor/map.js`, 600 lines; Modulation's *Table | Map*
  switch, the table the default). Sources, the rack and destinations in
  three columns; the sources and destinations from the metadata and the
  mirror (no engine, effect, kind or source id in the code: the editor's
  names test passes, which found two quoted words that happen to be ids,
  `gate` and `function`); cables only in the gutters, in a band above the
  rack and in the gaps between rack blocks, so none runs across a block or a
  label; pills (amount, live value) placed in clear places only; jacks of
  24 px with a 14 px jack drawn in them. Cables stay joined when a block's
  *n more* opens, and a cable whose end has no jack (a module taken away, a
  destination that is not in the list) ends on a stub in words.
- **Focus** (`st.mapMode`): a module's or destination's header, a source's
  name, **F**; *Refused*; **Esc** and *All* leave it. Dimmed cables lose
  their pills.
- **Making a cable**: drag, or Enter, arrows, Enter; every destination
  opens while one is in hand; the verdict over an input is the shadow
  Worker's `preview` of one CABLE record in the first empty slot, answered
  by C's edit codes (32 and up: written and left out) and, new, by the rack
  and matrix as they would be (`preview` with `mod`, `fm1w_mod_records`):
  "Cannot be modulated: Model rebuilds the voices", or *Runs*. One drop is
  one history step, 25 %, selected.
- **Browsers**: `test/launch.mjs`; `editor.mjs`, `editor-ui.mjs`,
  `editor-reach.mjs` and `editor-map.mjs` run in Chromium, Firefox and
  WebKit. The page tests are Playwright 1.63's (Chromium 153, Firefox 155,
  WebKit 26.6).
- **The manual**: chapter 15, *The advanced editor* (nine sections, five
  pictures of the page made by `test/editor-shots.mjs`), a `{{page}}`
  directive for them, and chapter 2's old bullet list of the editor reduced
  to a paragraph and a pointer.

**Differences from the plan (§3 mockup 05, §10, §14).**
- **No "Late" chip**: the planner's cable codes from 32 up are all "does not
  run"; the mockup's "a tick late" is the harness's own `delayed` mask and
  nothing in the edit layer's output separates it. The chips are *All*,
  *Focus: ...* and *Refused*.
- **A jack's verdict is asked for the jack under the cable**, not for every
  jack at once as the mockup draws it: the shadow Worker answers one cable
  per call, and trying all ~330 destinations on every drag would be a
  preview storm. A drag colours the jack it is over, and says why in the
  line above the Map.
- **The sources' groups** are the sources' own names in three classes (the
  notes, clock and chance; each sound's notes, `S1...`; the sequencer's
  lanes, `SEQ` and `SQV`), where the mockup wrote "Every note", "One
  sound's notes" and "Sequencer": a name pattern in `map.js`, not a field of
  the metadata. It should be a field (`group`) in `mod.sources`: open item.
- **Modules are named "3 ENV"** (position and abbreviation, as the table's
  sources are), not the mockup's "ENV3".
- **Selection is `aria-current`, not `aria-pressed`**, on the Map's headers:
  the global `[aria-pressed]` rule paints a pressed button as a full bar.
- **Phones keep the cable list** (§14, ED14): the Map needs 620 px of the
  editor's width, so a 768 px tablet window has it and a phone does not.

**Found on the way.**
- **"n more" never opened** in the first draft: the list was shown only
  while a cable was in hand. Found by reading the draft; the page test now
  opens and closes it with the cables still joined.
- **WebKit counted a ResizeObserver loop as an error**: laying out changes the
  map's own padding (the band above the rack grows with the cables that need
  it) inside the observer's callback. The layout is queued a frame later.
- **Firefox in a headless container never runs the worklet**: its AudioContext
  stays *suspended* with no audio device, with or without its null-context
  pref. A PulseAudio null sink fixes it. In the Playwright image, as root:
  `apt-get install pulseaudio pulseaudio-utils`, then `pulseaudio --system -n
  --disallow-exit --exit-idle-time=-1 --load=module-null-sink --load="module-native-protocol-unix
  auth-anonymous=1 socket=/tmp/pa.sock" -D` and `export
  PULSE_SERVER=unix:/tmp/pa.sock` (a plain `pulseaudio -D --system` answers
  "Access denied" to everything, `pactl` included, and the tests then fail
  at once). WebKit and Chromium need nothing. Not a fault of the page.
- The **edit layer's own codes already carry the planner's verdict** for a
  cable aimed at a parameter that rebuilds the voices (34), so the `mod`
  records the preview now also returns were not needed for that case; they
  are asked for when the code is 0. No case was found in which they
  changed an answer; they are kept (one call) because `fm1_mod_slot_refusal`
  is the rack's own word for a slot.
- Chromium, Firefox and WebKit draw the Map to the pixel alike at 1,440 px
  (looked at: the focus picture in each).

**Open.**
- The sources' groups should come from the metadata (above).
- The Map has no drag for moving a cable's end, nor a way to start a cable
  from an input; the table and the slot inspector do both.
- A crowded Map (all 32 slots in use) is a band of lanes above the rack, 160
  px high; Focus is the answer to reading it, as the mockup said.
