# 15 — The sequencer in the virtual FM-1: plan

This plan puts the sequencer core, `fm1_seq` ([docs/13](13-movy-port.md),
[engines/seq.md](../engines/seq.md)), into the virtual FM-1
([sim/web](../sim/web/README.md)), so that it can be played from the panel in
a browser and checked sample for sample against `fm1-render`. It is docs/13's
stage M4 for the simulator. It also moves docs/13's M2 (engine API v2) ahead
of the lock UI.

**How it was made (2026-10-01).** Three lanes mapped the simulator, the
sequencer and the controls. Two candidate plans followed: a vertical slice and
an architecture-first plan. A judge combined them. A completeness critic then
re-checked the result against the code at main `0b74b3d` and corrected it.
This document is the judged plan with every one of the critic's corrections
applied. Where the critic's own fix was wrong (the computer-keyboard map, §3.15)
or incomplete (the ENUM flag table, O13), the check is given.

**Marks.**
- [verified]: measured in the planning runs (the method is named) or re-checked
  for this document at `0b74b3d`.
- [reported]: Movy's UI facts, read through a summarising fetch at `9190e79`, and
  the manual's panel drawing.
- [inferred]: estimates and proposals.

**State of main.** PR #21 (Capture, 256 packed 12-byte events, on by default) is
merged as `0b74b3d`, with all 7 CI checks green [verified: `gh pr checks 21`].
There is no precondition left. PR #24 (the user manual, and the simulator
published on GitHub Pages) has merged since, as `0511a31`. It touches no file
that S1 changes except CHANGELOG.md [verified: `git diff --stat 0b74b3d
0511a31`]. PRs #22 (HANDOFF) and #23 (README as the product page,
DEVELOPERS.md) are open.

**The one rule.** Nothing in this plan runs on, writes to, or sends anything
to an FM-1 (CLAUDE.md). Web MIDI stays input only unless the owner opts in
(O18).

## 1. Short answer

| Question | Answer |
| --- | --- |
| What gets built? | A SEQ mode on the virtual FM-1's panel. The white keys become steps and the black keys become sequencer roles. On top of that: Step pages on the four knobs, record and Capture, 4–8 tracks, parameter locks, Session with scenes and song, and sets saved in the browser. |
| In what order? | **S1:** one shared, heap-free C99 host bridge, extracted from `fm1-render` with no change in behaviour. **S2:** the app hosts the sequencer with no UI and proves parity. **S3–S10:** the UI, one PR per stage. S7 (engine API v2) is split into a silent stage, S7a, which lands before the lock UI (S8), and an audio-changing one, S7b, best merged before S8 too. |
| When is it playable? | In S3, PLAY/STOP plays a demo pattern and SEQ shows the grid. In S4, patterns can be made on the panel. |
| How is it checked? | **Parity:** the module equals `fm1-render` built to JavaScript and against musl exactly, and against glibc within 1 LSB. **Oracle:** every oracle script played through the app equals `fm1-render`. **Gestures:** panel traces replay through `fm1-render` byte for byte. **Layout:** every new screen passes the layout check. **Staleness:** CI's gate covers the new inputs (§6). |
| What does it cost in RAM? | At 8 tracks, at most 36,428 B of the 36,864 B half budget since S6 (272 events and the click), leaving 436 B. At 4 tracks, at most 22,604 B (§2.6). |
| What does the owner decide? | 24 decisions (§8). S1 needs none. S2 needs one constant. |
| What is left out? | Compat mode in the app, undo (until M4/D14, or O16), MIDI out (O18), and anything on an FM-1. Several sound units, first left out (O10), are in since 2026-10-02 (§3.16). |

## 2. Architecture

### 2.1 Where the code lives

| Layer | Files | Rules |
| --- | --- | --- |
| Core | `engines/seq/*.c`, `engines/include/fm1_seq.h` | Unchanged except for two additions. S4 adds a read-only page getter and `rec_track` in `fm1_seq_info_t`. S5 adds nothing: O9 kept Movy's Capture growth, so the proposed D-row in `commit_playing` was not made. |
| Host bridge, new in S1 | `engines/include/fm1_seq_host.h`, `engines/seq/seq_host.c` | C99 with `-Wpedantic`, no heap, no stdio. It goes in `SEQ_SRC`, so `test_the_core_never_allocates` covers it; that test's object count goes from 5 to 6 [verified: tests/test_seq_core.py 895–896]. It is linked into `fm1-seq`, `fm1-seq-check`, `fm1-render` and `fm1-render.js`, and from S2 into `fm1-sim-render` and `fm1.wasm`. |
| Script host code | `engines/host/seq_script.[ch]` | It allocates and uses stdio, so only the native tools link it. `fm1.wasm` never does, because stdio and malloc would add WASI imports, and parity fails on any import. S3 adds `fm1_seq_cmd_format`. |
| Reference host | `engines/host/render.cc` | It keeps its CLI and its 65,536-entry event buffer [verified: render.cc 419]. S1 adds `seq_dropped`, `seq_max_block_events`, `seq_splits` and `--events N`. |
| App | `sim/web/src/fm1_app.[ch]` | Hosts the sequencer from S2 (§2.5). |
| Gesture machine, new in S3 | `sim/web/src/fm1_seq_ui.[ch]` | Pure. Its inputs are key, button and encoder edges stamped with `a->frames`, plus a const view of the sequencer. Its outputs are `fm1_seq_cmd_t` records and UI state. |
| Views, new in S3 | `sim/web/src/fm1_seq_view.[ch]` | Draw the SEQ screens into `fm1_tft`. Each grid is one logged graphic box, painted inside. |
| Web layer | `sim/web/src/fm1_web.c`, `WASM_EXPORTS` in `sim/web/mk/sim.mk` | The two export lists stay equal [verified: test_sim_web.py 231]. |
| Native harness | `sim/web/test/fm1_sim_render.c` | Mirrors `fm1-render`'s sequencer flags. |
| Page | `sim/web/www/worklet.js`, `app.js`, `index.html` | Not hashed by the staleness gate. |

### 2.2 The shared host bridge

`render.cc` holds the only per-block sequencer host today. Its dispatch loop is
at lines 493–522. `LaneParam` and `LockValue` sit at 103–120, in C++, using
POSIX `strcasecmp` [verified: render.cc]. S1 moves that code into C99, so that
`fm1-render` and the app run the same code path. Proposed interface
[inferred]:

```c
typedef struct {
  void *ctx;
  const fm1_engine_t *engine;
  void (*render)(void *ctx, float *lr, uint32_t n);
  void (*note_on)(void *ctx, uint8_t note, uint8_t vel);
  void (*note_off)(void *ctx, uint8_t note);
  void (*set_param)(void *ctx, uint16_t index, float value);
} fm1_seq_sink_t;

typedef struct {
  fm1_seq_t *seq;
  fm1_seq_ev_t *ev;
  uint32_t cap, n, max_n;
  uint64_t notes_to_engine, locks_to_engine, splits;
} fm1_seq_host_t;
```

| Function | What it does |
| --- | --- |
| `fm1_seq_host_init(h, seq, ev, cap)` | Binds an instance to an event buffer. |
| `fm1_seq_realtime_status(ops, len)` | Length-aware `rt` parsing, moved from seq_script.c. The script loader's `rt` check calls it. |
| `fm1_seq_apply_line(seq, ops, len, out, cap)` | Applies either `rt F8\|FA\|FB\|FC`, through `fm1_seq_realtime_in` at frame 0, or `fm1_seq_apply_text`. seq_script.c's `fm1_script_apply` becomes a wrapper over it. |
| `fm1_seq_host_line`, `_cmd`, `_note_in(h, track, pitch, vel)`, `_realtime(h, status)` | Each appends its frame-0 events at `ev[n..]`. |
| `fm1_seq_host_room(h)`, `fm1_seq_cmd_max_events(lim)` | Room left, and the most events one command can emit: gates + 8 × tracks + 1, which is 129 at 8 tracks and 64 gates (§2.3). |
| `fm1_seq_host_advance(h, frames)` | Appends `fm1_seq_advance`'s events, returns `n` (for logs) and updates `max_n`. |
| `fm1_seq_host_dispatch(h, frames, block, sink)` | render.cc's loop, verbatim. It acts only on NOTE_ON, NOTE_OFF and LOCK, and only for engine-routed tracks (`fm1_seq_get_track` per event). It resolves a lock's parameter before any split and skips unmapped locks. It clamps the frame to `n`, keeps emission order (offs, locks, ons), renders the tail and counts splits. A NULL sink only resets `n`. |
| `fm1_seq_lane_param(e, label)` | `LaneParam`: the text after the last `:`, compared case-insensitively in ASCII. |
| `fm1_seq_lock_value(p, v)` | `LockValue`, as the same float expression, parenthesised identically: FLOAT is linear over 0..127, ENUM is min + ⌊v·n/128⌋. |
| Added in S7a | Label-to-uid resolution, and refusal of NOLOCK parameters, counted. |
| Added in S8 | `fm1_seq_value7(p, x)`, the inverse of `lock_value`; as built also `fm1_seq_value7_step` (a knob detent on the 7-bit grid) and `fm1_seq_lane_label_for` (a lane's label, a space written `_`, which `fm1_seq_lane_param` reads back). |

### 2.3 Host policy

These rules sit outside the core, in each host. S1 writes them into a "Host
contract" section of engines/seq.md.

**The event-room rule.** Commands from the UI add frame-0 events to the same
buffer that `fm1_seq_advance` fills afterwards. The core keeps every sounding
gate's note-off only if each call gets at least `fm1_seq_min_events` = gates + 8
= 72 events [verified: fm1_seq.h 157–166]. A single command can emit far more:
one `stop` at 8 tracks, with 8-note chords and 64 locked lanes, emitted 129
events (64 note-offs, 64 D6 base reverts and STOP), and `play` emitted 129
[verified 2026-10-01, planning run]. The rule is that a host applies a command
only while its room is at least `cmd_max + min_events`.
- **In the app (S2),** a command that does not fit waits in a pending record
  and is applied at the next block start, before any new input. The critic's
  minimum is one slot; S2 may make it a short fixed queue, with a test that
  fills it.
- **In render.cc,** the 65,536 entries never reach the limit. S1's
  `--events N` lets it run with the app's 256.

**The default-route rule.** The core starts every track on USB-MIDI channel
t mod 16 + 1. render.cc routes track 0 to the engine only when all three of
these hold: no `--route` was given, the set has no `rt` lines, and an engine is
loaded [verified: render.cc 402–417].
- Import resets every route to MIDI t mod 16 + 1 [verified: seq_persist.c
  376–377], and export writes only routes that differ from that [verified:
  seq_persist.c 100–101].
- `fm1_app_init` leaves the core's default routes alone.
- One app function applies render.cc's rule after create, reset and import.
  The browser calls it from its start chain, and the harness mirrors
  `fm1-render`.
- Parity scenarios route only with `route` verbs, never with `--route`, so the
  module needs no route export.

**Reset, import and engine changes.** Recreating the instance or importing a
set emits no events, so the old gates would hang on the engine.
- Before a reset or an import, the app sends a note-off for every count in
  `seq_note_count` and clears `lock_shown`. After an import it applies the
  default-route rule.
- `fm1_app_all_notes_off`, which runs on an engine change, also clears
  `seq_note_count`. Later sequencer note-offs clamp at 0.

### 2.4 The per-block contract

Both hosts run the same order. Parity always runs at 64-frame blocks.

1. **Controls.** Bend and parameters first, then note-offs before note-ons. In
   the browser, panel and MIDI input has already been applied between quanta:
   keys have called the engine, and UI commands wait in the bridge as frame-0
   events.
2. **Commands due** (frame ≤ pos) go through the bridge. The app's pending
   command goes first, if it now fits. `--seq` alone implies a `play`.
3. **Live input.** `note_in` and realtime input, at frame 0.
4. **Advance.** `fm1_seq_advance(n)` appends its events into the room left.
5. **Event log.** In the harnesses only.
6. **Dispatch.** Unit 0's render is split at each engine-routed NOTE_ON,
   NOTE_OFF and LOCK frame, in emission order (offs, locks, ons). CLICK, CLOCK,
   START, STOP and MIDI-routed tracks are only logged.
7. **The rest of the block.** Effects 1–2 run in place, then (from S6) the
   metronome's click from the block's events (`fm1_seq_click_mix`), then the limiter. The
   app then takes the scope and peak, applies MASTER, advances `frames` and
   updates the LEDs.

**Invariants:**
- the default RNG seed;
- the same block size;
- `seq_dropped == 0`;
- the sequencer created at `lrintf(rate)` on both hosts.

The sink calls the engine exactly as render.cc does. `fm1_app_note_on` clamps
velocity to 1..127 [verified: fm1_app.c 305], so the app's sequencer path
does not use it; sequencer velocities are in range already.

### 2.5 The app's sequencer state

**Fields in `fm1_app_t` before `tft`.** `fm1_app_init` zeroes these
[verified: it memsets up to `tft`, fm1_app.c 172]:
- the `fm1_seq_host_t` and the `seq` pointer;
- `uint8_t seq_note_count[128]`;
- `float lock_shown[32]`, the display mirror of locked values, which is never
  written into `value[]`;
- the pending command record;
- `on_cmd(void *, uint64_t frame, const fm1_seq_cmd_t *)`, a native-harness
  hook (NULL in the module);
- the UI state.

**Fields after `tft`.** These are not zeroed and need not be:
- `unsigned char seq_mem[FM1_APP_SEQ_BYTES = 32768]`, 16-byte aligned;
- `fm1_seq_ev_t seq_ev[FM1_APP_SEQ_EVENTS = 256]`.

`fm1_app_init` calls `fm1_seq_limits_default(&lim, FM1_APP_SEQ_TRACKS)` (8,
pending O3) and `fm1_seq_create(seq_mem, &lim, lrintf(rate))`, the same
rounding as render.cc. `fm1_app_seq_cmd()` is the single seam where every UI
command enters. In the browser it applies at once, on the worklet thread,
subject to the event-room rule. On the FM-1, a compact single-producer ring
goes here later (docs/13 §6).

**UI state** (`fm1_seq_ui_t`; a sizeof test asserts at most 1,024 B):
- the view: TRACK, STEP1, STEP2, the lock pages, SET, CLIP, TRACKPG, SESSION,
  LOOP or PICKER;
- the focused track and the bar page;
- up to 16 held steps, each `{step, press_frame, gestured}`;
- SHIFT and the role keys held;
- the remembered chord, up to 12 pitches with a velocity each, plus the current
  velocity and full-velocity mode;
- the frame of the last knob turn, for `abaseq` after 600 ms idle;
- page memory per view;
- the toast or confirm state and its expiry;
- transport and Capture info, cached once per block.

The UI keeps **no copy of lanes or bases**. Each frame it derives them from
`fm1_seq_get_track` (`base[8]`, `lanes_assigned`) and `fm1_seq_lane_label`,
so they cannot drift after an import or an `aclr`.

**The page getter (S4).** `fm1_seq_get_page(s, t, slot, first, n, out[])`
makes one pass over a clip's notes, locks and trig rows. For each step it
gives the note count, the locked-lane mask with values, and the trig flags
(probability, A:B condition, invert). A per-step getter would scan linearly
instead: `sq_clip_lock_at` searches up to 1,024 locks per lane, and
`sq_clip_governing_trig` calls `find_trig` twice. That is about 650,000
comparisons per redraw for a 64-step grid with 8 lanes, on the audio thread
[inferred from seq_clip.c 338–349].

The hold threshold is ⌈0.3 · rate⌉ frames on `a->frames`: 13,236 at
44,118 Hz. Native and wasm builds therefore agree.

### 2.6 Memory

**Against the half budget.** The owner's budget for the sequencer is about
half of docs/13 §5's 72 KiB, 36,864 B (docs/13 §10).

| Item | 4 tracks | 8 tracks | Note |
| --- | --- | --- | --- |
| Sequencer instance, Capture 256 × 12 B included | 18,056 | 31,880 | [verified: `fm1-seq --sizes`; test_seq_render.py 52 asserts 18,056] |
| Event buffer, 272 × 12 B (256 until S6) | 3,264 | 3,264 | The minimum is 72 events (864 B). The measured worst is 193 events (2,316 B) in seq_bench's burst, and at most 7 per 64-frame block over the 34 oracle scripts [verified 2026-10-01]. Beside the 64 gates' note-offs the core keeps room for, that burst needs 257, one more than 256; S6 raised the buffer to 272, which holds it [verified 2026-10-02: `fm1-render --events`, tests/test_seq_render.py] |
| Pending command record | 240 | 240 | One `fm1_seq_cmd_t` [verified 2026-10-01: sizeof]. It stands in for the FM-1's command ring, whose compact record is still to be designed |
| UI state | ≤ 1,024 | ≤ 1,024 | asserted; 552 B at S6 |
| Metronome click voice (S6, O11) | 20 | 20 | `fm1_seq_click_t`, asserted |
| **Total** | **≤ 22,604 (61.3 %)** | **≤ 36,428 (98.8 %)** | |
| Spare | 14,260 | 436 | docs/13 §5's 12,288 B undo ring fits only at 4 tracks |
| Stack during a stopped Capture's tempo search | about 1.55 KB | about 1.55 KB | transient [verified: engines/seq.md 286] |

Without Capture the instance is 14,984 B at 4 tracks and 28,808 B at 8
[verified: docs/13 §10]. The instance holds no pointers, so its size is the
same in 32-bit and 64-bit builds.

**Simulator only, not FM-1 RAM:**
- **Fixed arena:** 32,768 B. A test asserts that `fm1_seq_size(8 tracks)` ≤
  `FM1_APP_SEQ_BYTES`. A second test asserts that `fm1_seq_size(8)` + events +
  pending record + `sizeof(fm1_seq_ui_t)` ≤ 36,864.
- **Text buffer:** 65,536 B of BSS in fm1_web.c (§2.7).
- **`fm1_app_t`:** 1,168,288 B natively today [verified: sim/web/README.md
  144]. It grows by about 37 KB [inferred]. Multi-sound (§3.16) makes it
  4,880,816 B (4,881,424 B with S6): four 512 KiB sound arenas and ten 256 KiB effect arenas
  [verified 2026-10-02: `fm1-sim-render --sizes`, clang, 64-bit]; 4,880,384 B
  at 32 bits [verified 2026-10-02: the same, gcc 12 `-m32`].
- **`fm1.wasm`:** 391,277 B today. It grows by about 60–80 KB of code
  [inferred from the 5 seq objects' arm64 text, about 78 KB].
- All of it fits the module's fixed 8 MiB of memory.

**Compat stays out.** The compat pools, about 300 KB at 8 tracks [reported],
never enter the app. Compat stays on `fm1-seq` and `fm1-render`.

**The on-screen figure.** It becomes engines plus sequencer plus events,
against 387,924 B. For example, Shapes with PSX Verb is about 340 KB plus
about 35 KB, roughly 375 KB, still under [inferred].

### 2.7 The browser side

**Exports.** EXPORTED_FUNCTIONS cannot export data, and
`test_wasm_exports_match_the_web_layer` matches functions only. Text therefore
goes through functions.

| Stage | Exports |
| --- | --- |
| S2 | `fm1w_text_buf()` returns a pointer to one 65,536 B buffer, and `fm1w_text_cap()` its size. Also `fm1w_seq_text(len)`, `fm1w_seq_reset(tracks)` and `fm1w_seq_dropped()` |
| S3 | `fm1w_seq_info()` |
| S10 | `fm1w_seq_realtime(status)`, `fm1w_seq_export()` and `fm1w_seq_import(len)` |

**Text buffer size.** Planning first sized the buffer from a full 8-track note
pool's export of 33,936 B. Full pools export to more:
- every pool full (1,536 notes, 1,536 locks, 256 trig rows) with 64-step
  clips: 47,640 B;
- with 256-step clips and conditions on steps of 100 and up: 53,208 B
  [verified 2026-10-01: `fm1-seq` built from `0b74b3d`].

`fm1_seq_export_movy1` already returns the whole length and writes only if it
fits [verified: fm1_seq.h 195–197], so an export that does not fit is
detected, not cut short. JavaScript checks a set's length against
`fm1w_text_cap()` before copying it in.

**Worklet.** `sendState()` runs today only after an applied message and at
init [verified: worklet.js 55, 83]. If nothing else changed, a song end, an
external-clock stop or a Capture tempo change would not reach the status line.
From S3, `process()` compares a small snapshot of the sequencer info once per
quantum and posts it only when it changed. `master_tick` is read as a BigInt,
or left out. Nothing is posted per event.

## 3. Control mapping on the FM-1 panel

This is a proposal. [O#] marks an owner decision in §8; (S#) is the stage that
lands the item. The buttons carry the manual's printed names: OCT−, OCT+, FX,
SEL, ENV, LFO, EDIT, GLO, HOME, SAVE, ARP, SEQ, PLAY/STOP and REC [reported:
the manual's panel drawing, as sim/web/README.md has them]. docs/13 §4 still
calls them roles to assign; S1 corrects that sentence. docs/13 §4's abstract
roles go onto black keys inside SEQ mode [O1], so no printed button changes
meaning outside SEQ.

**Numbering.** The 16 white keys are numbered 1–16 from the left, as the
manual numbers steps. Verbs count from 0, so a step index is bar page × 16 +
(white key − 1).

### 3.1 Modes

- HOME, FX and GLO are unchanged. SEQ is new (S3).
- SEQ, from any mode, enters the SEQ Track view (GRID). HOME, FX and GLO leave
  SEQ mode. The transport keeps running in every mode.
- A SEQ tap inside SEQ switches between Track and Session (S9). SEQ held peeks
  at Session until release (S9).
- SEQ held plus white key 1–8 focuses track 1–8 from any mode (S6). It sends
  `watch t`, which empties Capture [verified: seq_cmd.c 225–229], and a
  toast says so.

### 3.2 The keys outside SEQ mode (KEYS)

- They play the engine as today.
- From S5 they also call `fm1_seq_note_in` for the focused track at frame 0,
  with velocity 0 on release, so REC and Capture see them. **Only outside SEQ
  mode:** in the SEQ grid views the white keys are steps and the black keys are
  roles, so they never feed `note_in` there.
- MIDI IN notes feed `note_in` in every mode (S5).
- Sequencer notes do not light the key LEDs in HOME [O6].

### 3.3 The white keys in the SEQ Track view (S4)

- **Tap:** toggles the step on release with `tog t s p1 v1 [p2 v2 …]`, which
  takes pitch and velocity pairs, at most 12 [verified: seq_cmd.c 263–276].
  The pairs come from the remembered chord (played on the keys in KEYS mode or
  at MIDI IN, each pitch with its own velocity), else the last pitch, else a
  default [O5].
- **Hold:** 13,236 frames (300 ms) or more opens the Step page. It changes only
  the display, and the toggle is cancelled.
- **Hold A, press B:** `slen`. Pressing B again trims to B's start.
- **Several steps held:** edits apply to all of them.
- **Any gesture made during a hold** cancels the toggle.
- **A pitch on a held step** (O22, answered 2026-10-02, changed by the
  owner from the proposal): pitches are only ever added. With a step held,
  SHIFT turns the white keys into pitches in the current octave, and each
  press adds one to every held step (`addp`); a note at MIDI IN does the
  same with any pitch. There is no per-pitch removal: SHIFT pressed and
  released with nothing else touched, while a step is held, clears that
  step's notes (`del t s s -1`). The final gesture table is in §3.5.

### 3.4 The black keys in the SEQ Track view [O1]

The screen labels each role; the panel's printed legends do not apply in SEQ
mode. A black key's LED is lit only when its role is available. ◀ and ▶ are
drawn as `<` and `>`, because the font has ASCII only [verified: fm1_tft.c 87].

| Key | Printed under it [reported] | Role | Stage |
| --- | --- | --- | --- |
| F#3 | OP1 | ◀ bar page. With a step held: `enudge` − (SHIFT: one tick) | S4 |
| G#3 | OP2 | LOOP. Held, the white keys are bars 1–16; LOOP + SELECT resizes (`loop`, `dbl`) | S9 |
| A#3 | OP3 | ▶ bar page. With a step held: `enudge` + (SHIFT: one tick) | S4 |
| C#4 | OP4 | COPY: `cpy` / `pst`, and `cpyclr` on release; `clipcopy` / `clippaste` in Session | S9 |
| D#4 | OP5 | CLEAR. + step: `del` + `aclrstep` (S9). + one knob detent: `aclr` (S8). Tap: delete the clip, with a confirm until undo exists [O15] | S8, S9 |
| F#4 | OP6 | MUTE. A tap mutes the focused track; held, white keys 1–8 are a mute map; no solo (O12, answered: mute only) | S6 |
| G#4 | PIT | UNDO, inert until undo exists (M4/D14) [O16] | — |
| A#4 | GLO | spare | — |
| C#5 | MONO | previous track | S6 |
| D#5 | POLY | next track | S6 |
| F#5 | (none) | spare | — |

### 3.5 SHIFT

SHIFT is SEL outside FX mode [O2]. FX mode keeps SEL's slot grab (S4). With no
step held, SHIFT + white key N gives Movy's shortcut N [verified: Movy's
`src/seq/step-shortcuts.ts` and MANUAL.md at `9190e79`, read in S4], with a
legend on the hint line while SHIFT is held:

| White key | Function | Stage |
| --- | --- | --- |
| 2 | Track page | S6 |
| 3 | Clip page | S6 |
| 5, 7, 9 | Set page | S6 |
| 6 | metronome, `metro` | S6; sound only under O11 |
| 10 | full velocity | S4 |
| 15 | double the loop, `dbl` | S9 |
| 16 | quantise cycle, `cq` 0 / default / 100 | S6 |

**The gestures as built in S4** (O1, O2, O5, O19, O21 and O22; SEQ mode
with the lab switch on; `t` is the focused track, `s` a step). Every edit
on held steps is one command per held step, in press order, as Movy's
`step-edit.ts` sends them, and cancels those steps' toggles.

| Input | No step held | Steps held |
| --- | --- | --- |
| White key | A tap toggles the step on release: `tog t s` with the last chord played, each pitch with its velocity, else note 60 at velocity 100 (O5); 127 with full velocity. A press of 13,236 frames or more (⌈0.3 · rate⌉) is a hold: the Step page, no toggle. A tap in the hidden rest of a short clip's last bar enters nothing, as Movy | One step held, with a note, and B pressed after it: `slen` to the end of B, B again to its start, and so on; B before it: nothing. Otherwise B is held too: steps pressed together each toggle on release unless edited, however long the first was held alone |
| SHIFT + white key N | Movy's shortcut N: 10 is full velocity (S4); the rest come with S6 and S9 and do nothing yet | `addp t s s p v` on every held step: p is the key's pitch in the current octave (53 + key + 12 × octave + transpose), v the key's velocity |
| SHIFT tap (pressed and released with nothing else touched) | nothing | `del t s s -1` on every held step with notes: the step's notes are cleared (O22) |
| Knob detent with SHIFT held | the sound, as without SHIFT | kept for `aclrs` on the lock pages (S8); nothing on the Step pages |
| SHIFT + PLAY/STOP | while playing, a restart (`play`; D12 adds the Stop and Start); stopped, `play`. In every mode but FX, where SEL grabs a slot | the same |
| F#3 / A#3 (◀ ▶) | the bar on the keys, back and on: the loop's bars and one empty bar after them, as Movy's `maxBarOffset`, except that Movy counts a loop shorter than a bar as a whole bar from its start, so a short loop starting mid-bar gets a second empty bar there [verified: `state.ts` at `9190e79`] | `enudge t s s -1 ∓2` (Movy's coarse step, 2 ticks), ∓1 with SHIFT |
| Other black keys | inert until their stage (§3.4) | inert |
| OCT− / OCT+ | the octave, as stock; both: reset | `etrn t s s -1 ∓1`, ∓12 with SHIFT |
| SELECT | the sound's pages | Step page 1/2 or 2/2, remembered from hold to hold (O21) |
| KNOB1–4 | the sound's page, its name and value on the hint line | Step page 1: VEL (`evel`, 4 per detent, relative), LEN (`slen` with Movy's 21 lengths, from 1/32 to 16 bars), PROB (`eprob`, 100 % down to 10 %), COND (`econd`, the 36 A:B pairs); page 2: INV (`einv`, on with a turn up, off down) and the nudge and note as read-outs. The values move from the first held step's |
| MIDI IN note | sounds, and joins the chord a tap writes: every note held when one goes down, the last 12 | sounds, and `addp` on every held step |
| Keys outside SEQ mode | play the sound and join the chord, as MIDI IN | — |
| HOME, FX, GLO | leave SEQ mode | leave SEQ mode; the held steps go, with no toggle |

The computer keyboard [O19]: Digit1–Digit8 and C, V, B, N, M, comma, period
and slash press white keys 1–16 in SEQ mode, and Shift holds SEL there.

### 3.6 Transport

**PLAY/STOP** works in any mode: `play` / `stop` (S3). SHIFT + PLAY while
playing restarts (S4); D12 makes that a Stop and a Start.

**REC tap** sends `rec <focused>` (S5).
- Stopped: a one-bar count-in.
- Playing on an empty clip: the take starts at the next bar.
- Playing over notes: an overdub that starts at once.

**REC held while stopped** is step record [O8].

**SHIFT + REC** is Capture, `cap <focused>` [O7].
- **capture_mode 1, the tempo picker:** a held popup lists the candidates.
  SELECT or KNOB1 sends `capsel i`, heard at once. Any other press sends
  `capdone`.
- **capture_mode 2:** a two-line toast, `Captured` / `at 120 BPM`.
- **Browsing never empties Capture.** No browsing gesture sends `watch`,
  `clipsel` or `launch`, because each of them empties the Capture ring
  [verified: seq_cmd.c 154–175, 225–229].

### 3.7 OCT− and OCT+

- No step held: octave, as stock.
- Steps held: `etrn` −1 / +1, or ±12 with SHIFT (S4).
- Both together: reset, as stock.

### 3.8 Encoders

- **SELECT** moves between pages and remembers the last page per view [O21]:
  - Step 1/2, then Step 2/2;
  - then the sound's pages, as lock pages (S8);
  - then Set, Clip and Track.

  In the Capture picker it chooses the candidate.
- **PRESETS** chooses the current sound's engine; SHIFT + PRESETS chooses
  the current sound (§3.16). With the lab switch each engine-routed track
  plays the sound its route names; without it, every one shares unit 0
  [O10, answered 2026-10-02].
- **ALGORITHM** turns the model, the engine's first ENUM parameter. It **never
  creates a lock**. Whether a parameter can be locked at all is its flag
  (NOLOCK, from S7a), not which encoder turns it. For Six-Op, ALGORITHM turns
  Patch, which O13 proposes to keep lockable as LATCH [verified: mi_sixop.cc
  136; fm1_app.c `model_param`].

### 3.9 KNOB1–4

**No step held:** the knobs turn the sound page, as in HOME. From S8:
- **On a parameter with a lane** on the focused track, a detent moves the
  parameter's 7-bit value v7 by ±1.
- It sets `value[] = fm1_seq_lock_value(p, v7)`, the bridge's exact
  expression, and sends `abase t lane v7`, then `abaseq` after 600 ms idle (R8:
  no snap-back to a stale base).
- The grid is v/127 for FLOAT and the ⌊v·n/128⌋ bins for ENUM. Today a detent
  is 1/100 of the range [verified: sim/web/README.md, Limits]. Without the
  snap, the engine would play a different value from the one the screen shows,
  after every `abase` and after D6's revert at stop.

**One step held** (S4):
- **Step page 1:**
  - VEL, ±4 per detent;
  - LEN, Movy's 21 values from 1/32 to 16 [reported; S4 re-reads the units in
    `step-page-vm.ts`];
  - PROB, 100 % down to 10 %;
  - COND, 36 A:B pairs.
- **Step page 2:** INV, plus read-outs of nudge and transpose.
- **Lock pages** (S8), on the first turn of a parameter without a lane:
  1. `alabel t lane synth:<Name>`;
  2. `abaseq t lane value7(current)`, so the base equals what the knob shows;
  3. `aset t lane step v 1`, which is quiet.

  NOLOCK parameters are hidden. A ninth lane gives the toast `8 lanes used`.

**Two or more steps held:** the Step pages edit every held step. The sound
pages edit the sound, with no lock.

**Recording while playing:** a turn sends `aset … 0`, which is heard (S8).

**Hold step + SHIFT + one detent:** `aclrs` (S8).

**Display:** locked values in engine units, over dim bases [O14].

### 3.10 Pages (S6)

| Page | KNOB1 | KNOB2 | KNOB3 | KNOB4 |
| --- | --- | --- | --- | --- |
| Set | TEMPO (`bpm`; 1 BPM per detent, 0.1 with SHIFT) | SWING (50–80) | DQ | METRO |
| Clip | SPEED (`cscl`, 1/8X–4X) | LENGTH (`clen`, 1–256 steps) | TRANSPOSE (`ctr`, ±36) | QUANT (`cq`) |
| Track | ROUTE (engine or MIDI) | CH/SLOT (`route`) | MUTE | — |

- Track page 2 lists the 8 lane labels with their bases, read-only.
- Clock in and out go on Set page 2, or on GLO [O18].

### 3.11 Session (S9)

- **White keys 1–8:** the focused track's slots. `launch` on the bar; an empty
  slot sends `stoptrk`.
- **White keys 9–16:** focus tracks 1–8.
- **LOOP + white key:** scenes [O20], which also build the song (`songadd`,
  `song`).
- **COPY / CLEAR on slots:** `clipcopy`, `clippaste`, `clipdelat`.
- **MUTE held:** the mute map.

### 3.12 Other buttons

- SAVE in SEQ mode exports the `movy1` set to browser storage or a download
  only (S10) [O17]. Nothing is ever sent to a device.
- ARP, ENV, LFO and EDIT keep their stub meaning. The arpeggiator, modulation
  and effects report
  ([notes/2026-10-01-arp-modulation-effects-options.md](../notes/2026-10-01-arp-modulation-effects-options.md))
  plans them after this work.

### 3.13 LEDs

LEDs are on or off, plus the simulator's two blink periods (1 s and 0.25 s,
from `a->frames`) [verified: fm1_app.c 553]. The LED array is 27 keys then
14 buttons: SEQ is 38, PLAY 39 and REC 40 [verified: fm1_app.h 81–84, 134].

| LED | Meaning | Stage |
| --- | --- | --- |
| White keys, grid | on: a note inside the loop. Off: empty, or outside the loop. Inverted: the playhead. Fast blink: the record head. Slow blink: under the held step's length | S3, S4, S5 |
| White keys, Loop view | on: in the loop. Fast: the playing bar. Slow: the viewed bar | S9 |
| White keys, Session | on: a clip. Fast: queued. Inverted: playing | S9 |
| White keys, mute map | on: sounding | S6 |
| PLAY | on while playing | S3 |
| REC | on while recording. Fast during the count-in or a waiting take. Slow while `capture_pending` > 0 and nothing is recording [O7] | S5 |
| SEQ | on in the Track view, slow in Session | S3, S9 |
| SEL | on while SHIFT is held | S4 |
| OCT | as stock | — |

### 3.14 Gestures that stay out

Movy's touch gestures become one knob detent with CLEAR or SHIFT held. Its pad
layouts, its LFO assign and its MIX page are dropped here, as in docs/13 §4.

### 3.15 The computer keyboard [O19]

- **Space** presses PLAY/STOP when no button has focus. On a focused button,
  Space and Enter keep pressing that button [verified: app.js 546].
- **Shift** is SEL in SEQ mode.
- **Steps in SEQ mode:** Digit1–Digit8 for steps 1–8, and KeyC, KeyV, KeyB,
  KeyN, KeyM, Comma, Period and Slash for steps 9–16.
  - All of these are unused today [verified: app.js KEYMAP 49–50, `OCT_KEYS` 508,
    the arrow, Minus and Equal encoder keys, Escape].
  - The critic proposed KeyZ and KeyX for two of them, but those are OCT− and
    OCT+ [verified: app.js 508] and stay so.
  - The judge's "Q–I" row would have collided with KEYMAP's KeyW, KeyE, KeyR,
    KeyY and KeyU, which play black keys 1, 3, 5, 8 and 10.
- **The existing KEYMAP is unchanged.** In SEQ mode its black-key letters reach
  the role keys, as the panel does.

### 3.16 Multi-sound [O10, answered 2026-10-02]

The owner replaced O10's proposed default: up to **four sound units**
(engine instances) play at once, each sequencer track routed to one of
them; **each sound unit has two insert effect slots**; the two effect
slots the panel had stay as the **master bus**, after the sounds are mixed,
and each sound has its own level into that mix. A **RAM meter** against the
FM-1's budget refuses any engine or effect that would not fit, so what
plays in the simulator fits the device. It is all behind the lab switch
(O24); with the switch off the panel has one sound and two effects, as
before.

**Why two inserts per sound, not one.** Every instance's RAM is metered,
and an empty slot costs the FM-1 only its record [inferred: the firmware's
one arena sized to the chain, §2.6], so the budget limits what is loaded,
not how many slots there are; and two inserts let a sound carry a colour
effect and a space effect of its own while the master bus is shared. The
simulator's cost is its fixed arenas: eight more 256 KiB effect arenas, 2
MiB of the module's 8 MiB. CPU per slot is not measured (stage B).

**The signal path.** Each sound renders its own block, split at its own
tracks' events, then its inserts in order, then its level (0–100 %, unity
by default and skipped there); the sounds are summed in order; then the
master slots, the bus limiter and MASTER. A track routed to the engine
plays the sound its route index names (`route t 1 k`, Sound k + 1; the
bridge's `fm1_seq_host_dispatch_slots`, engines/seq.md); a lock lane
resolves on that sound's engine; a track routed to an empty sound plays
nothing. `fm1-render --slots` (with `--sound`, `--insert`, `--level`)
renders the same, so parity holds across sound units.

**The RAM meter.** It replaces the RAM figure in the bottom bar (a bar and
the percentage of 387,924 B, red past 100 %) and feeds GLO's RAM line:
every instance at the build's word size (32-bit in the browser's module,
as on pi32v2; the native harness's 64-bit figures are larger, Macro's by
12,880 B [verified: engines/README.md's size table], so near the budget the
native harness refuses sooner than the browser and a gesture trace there
can play differently in the two),
the sequencer's instance, events, pending record and UI bound (36,216 B at
8 tracks), and a 512-byte mix block per sound past the first. A choice that
would pass the budget is refused (`fm1_app_select` returns -4) with a
popup naming it and by how much, whether the panel, the page's menus or
the API asked (PRESETS and ALGORITHM, which step past it, give the first
refused choice's figure); a chain already past the budget may shrink but
not grow.

**The gestures** (with the lab switch; O1 and O2 hold: SEL is SHIFT
outside FX mode, and the black keys carry sequencer roles only in SEQ
mode, so choosing a sound uses neither the keys nor a new button):

| Input | HOME, GLO, SEQ mode | FX mode |
| --- | --- | --- |
| SHIFT + PRESETS | the current sound, Sound 1 to 4, no wrap; a popup `Sound 2 of 4` with its engine, or `Empty:` / `turn PRESETS` | — (SEL is the slot grab, as before; choose the sound outside FX mode) |
| PRESETS | the current sound's engine, stepping past one this host refuses or that would not fit, with a popup naming the first one skipped; on Sounds 2–4 the list starts with Empty, which unloads the sound (Sound 1 always holds one) | the same |
| ALGORITHM | the current sound's model | the selected slot's effect, stepping past one that would not fit; nothing on the Mix page |
| SELECT | the current sound's pages | walks the current sound's In1 and In2, the Mix page, then M1 and M2 (the master bus), page by page; FX mode opens on the master slot that was selected |
| SEL, then SELECT (FX mode) | — | swaps the selected insert with the other, or master slot with master slot; nothing on the Mix page |
| KNOB1–4 | the current sound's page | the selected slot's page; on the Mix page, the levels of Sounds 1–4, a percent a detent |
| Keys, MIDI IN | play the current sound; a release goes to the sound the note started on | the same |
| Steps held in SEQ mode | unchanged (§3.5): the UI takes SELECT and KNOB1–4, PRESETS and SHIFT + PRESETS act as above | — |

**The screens** (§4's rules; the layout sweep checks every state). The
title names the current sound once a second one is in use (`S2 Shapes`;
`S3 (empty)` for an empty one, whose HOME page reads `Empty sound:` /
`turn PRESETS`). FX mode's first line is the chain, `S2 In1 In2 Mix M1
M2`, the selected slot in the accent colour and an empty one dim; the
second line the selected slot and its effect (`> In1 Ensemble`, `*` when
grabbed); then the slot's page, or on the Mix page four rows, `S1` …
`S4`, each with its engine and level (`Macro 100%`) over a level bar. The
bottom bar reads `1/2 S2 In1`, `1/1 Mix` or `1/3 M1`, beside the meter.

**For stage S6.** `fm1_app_unit_route(a, track, sound)` routes a track to
a sound unit with a typed `route t 1 k`, sent as the panel's commands are
(the event-room rule; the harness logs it, so a gesture that routes
replays through `fm1-render`), `fm1_app_unit_of_track` reads it back, and
`fm1_app_unit_set_current` makes a sound current (for example, to follow
the focused track); the rest of `fm1_app_unit_*` (sim/web/src/fm1_app.h)
loads sounds and inserts, sets levels and plays notes on a given sound.
Which sound a new track starts on, and whether focusing a track makes its
sound current, are S6's.

## 4. Screens

**Rules every screen keeps** [verified: fm1_app.c 46–60, fm1_tft.h 27,
fm1_tft.c 87]:

| Rule | Value |
| --- | --- |
| Screen | 240 × 240 |
| Top bar | 24 px |
| Bottom bar | from y 216 |
| Content | from y 28 |
| Text | 2× by default: 12 px per character and 18 px tall, 19 characters a line |
| Row pitch | 36 px |
| Gap between labels and bars | 4 px |
| Logged boxes | at most 96; one more is a fault |
| Text cut short | a fault |
| Font | ASCII 0x20–0x7E only; anything else draws as `?` |
| Popups | up to 3 lines of at most 18 characters (`POPUP_CHARS`), shown for 1 s |

The GLOBAL page is full at 8 lines, so the sequencer's RAM goes into the
existing figure, not a new line.

| Screen | Stage | Layout |
| --- | --- | --- |
| Track view | S3; marks in S4, lock dots in S8 | **Status line** (y 28–46): BPM on the left; PLAY, REC with the count-in, or EXT on the right (S3 draws PLAY or STOP). **Grid**: 4 × 16, one graphic box. Proposed at y 50–115 with cells 12 × 14 px from x 8; S3 drew it at y 50–156 with cells 12 × 22 px from x 6, 2 px between steps, 4 px between beats and 6 px between bars, which leaves room for the strip [verified: fm1_seq_view.c, the layout sweep]. Filled = notes, corner dot = locks, tick = a trig row, outline = outside the loop, inverted = the playhead, bracket = the bar on the keys. **Knob strip:** per O23; in S3, four bars 8 px tall at y 168. **Hint line:** y 190–208. **Bottom bar:** `n/N Seq T1`, with the RAM figure |
| Held-step pages | S4 | HOME's `draw_params` geometry (four rows of label, value and bar). A 16-step strip replaces the scope |
| Lock pages | S8 | The same geometry. Locked values in engine units over dim bases [O14], and a dot on each parameter with a lane |
| Set, Clip, Track | S6 | The same geometry. Track page 2 lists the 8 lanes at a 23 px pitch, showing each label's text after its last `:` and the base |
| Session | S9 | 8 rows at a 22 px pitch; the slot grid is one graphic box. States: empty, clip, queued (blinking), playing, selected. Muted rows are dim |
| Loop view | S9 | a 16-bar strip |
| Capture picker | S5 | a held popup, one candidate per line |
| Toasts | S3 on | the existing popup |

**The knob strip (O23).** Four columns at x 6, 63, 120 and 177 in 2× text fit
only 4 characters each: a 57 px pitch with a 4 px gap. Real names and values
are longer: Brightness and Word Speed have 10 characters, and enum values such
as `1 *Sampler 3` have 12 [verified 2026-10-01: `fm1-render --list`].

| Option | Layout |
| --- | --- |
| (a) | 1× text: 9 characters per column, a short-name table, and values formatted to fit |
| (b), proposed | Four bars only, with no text in the strip. The turned knob's full name and value go on the hint line, in the same row format as HOME |
| (c) | A 2 × 2 layout |

Option (b) keeps every screen in 2× text and needs no short names. HOME's rows
already pass the sweep with every parameter at its minimum and maximum and
every enum value, so any name-value pair HOME shows fits the hint line too
[inferred]. Whichever option is chosen, the sweep adds the longest name and
the longest enum value of every engine.

**Toasts** fit 18 characters a line. Those over 18 characters become two
lines:

| Toast | Lines |
| --- | --- |
| Model cannot be locked (22 characters) | `Model` / `cannot be locked` |
| Captured at 120 BPM (19) | `Captured` / `at 120 BPM` |
| 8 lanes used (12) | one line |
| Capture emptied (15) | one line |

The sweep shows every toast at its longest value.

**Sweep additions by stage.** The floor in test_sim_web.py, `screens >= 280`
at line 107 [verified], is raised in each stage to its new count.

| Stage | New states |
| --- | --- |
| S3 | At least 295 screens: the empty grid; the demo pattern; the playhead at steps 0 and 15; 20.00 and 300.00 BPM; stopped and playing; the longest names (O23) |
| S4 | About 20 more: empty and full grids, each Step page at its extremes, a 4-bar loop |
| S5 | The picker with 1, 2 and 3 candidates; the count-in; recording; the Capture toasts |
| S6 | Every page at its extremes; 8 tracks' lane labels |
| S8 | Lock pages at 0, 1 and 8 lanes; the longest labels; lock dots on every step; the lock toasts |
| S9 | Session at 1, 4 and 8 tracks with every cell state; the Loop view; the confirm popup |

## 5. Stages

**Rules every stage keeps:**
- **Block size.** Parity always runs at 64-frame blocks: scripts carry
  `#! block=64`, or `fm1-render` gets `--frames 64`.
- **Event budget.** Both hosts assert `seq_dropped == 0`.
- **Parity.** The module equals `fm1-render.js` and musl `fm1-render` exactly,
  and glibc within 1 LSB, except in `libm_sensitive` scenarios. Capture's tempo
  search uses `logf` [verified: seq_capture.c 380].
- **Layout.** The screen sweep has 0 faults and at most 96 logged boxes per
  screen.
- **Staleness gate.** Any stage that touches a hashed input (§6.5) is rebuilt
  with `FM1_SIM_HOST=user@host sim/web/build-on-aeon.sh`. `fm1.wasm` and
  `fm1.wasm.json` are committed in the same PR, or CI fails. From S2 that
  includes changes to `engines/seq`.
- **Process.** One GitHub-Flow branch and PR per stage, with a CHANGELOG entry
  and the three-part description.
- **Manual and readme.** Each UI stage updates, in the same PR:
  - manual chapter 07 (`manual/chapters/07-sequencer.md` on main since PR
    #24, which still says the sequencer is not in the browser simulator);
  - the manual's `roles` list in `manual/manual.toml`, which still follows
    docs/13 §4's unassigned roles [verified: main `0511a31`];
  - the stub-button text in the root README or DEVELOPERS.md, wherever PR #23
    leaves it.
- **Nothing runs on, or is sent to, an FM-1.**

**Overview:**

| Stage | What | Depends on | Owner decisions | Size |
| --- | --- | --- | --- | --- |
| S1 | Shared host bridge, no change in behaviour | — | none | S–M |
| S2 | App hosts the sequencer headless; parity; oracle through the app | S1 | O3 (a constant) | M–L |
| S3 | First playable: PLAY/STOP, SEQ mode, a read-only Track view, a demo pattern | S2 | O4, O6, O19, O23, O24 | M |
| S4 | Step entry: steps, Step pages, SHIFT, bar paging | S3 | O1, O2, O5, O19, O21, O22 | L |
| S5 | Record and Capture | S4 | O7, O8, O9 | M |
| S6 | Tracks, mute, the Set, Clip and Track pages | S4 | O3, O10, O11, O12 | M–L |
| S7a | Engine API v2 (uid, flags, NOLOCK), with byte-identical audio | S2 | O13 | M |
| S7b | SMOOTH inside the engines | S7a | O13 (ramp time) | M–L |
| S8 | Parameter locks from KNOB1–4 | S4, S7a (S7b first if possible) | O14 | M |
| S9 | Session, scenes, song, Loop view, COPY and CLEAR | S6 | O15, O20 | M |
| S10 | Sets in the browser, MIDI realtime in, shortcuts, docs | S6, S8 | O17, O18, O19 | M |

S5 and S6 are independent of each other. S7a can be developed in parallel from
S2, but merges are serialised, since each needs its own rebuild of the module.

### S1. Shared sequencer host bridge, extracted from render.cc (no change in behaviour)

**Starts from** main `0b74b3d` or later. PR #21 is merged, with all 7 checks
green, and nothing else is a precondition. Branch:
`feature/<cut date>@seq-host-bridge`. Expect only CHANGELOG.md rebases
against the other open PRs.

**Goal.** One C99, heap-free per-block host contract, shared by `fm1-render`
now and by the app from S2. Audio and event logs are proven unchanged.

**Scope:**
1. **The new bridge,** as in §2.2: `engines/include/fm1_seq_host.h` and
   `engines/seq/seq_host.c`.
   - C99 with `-Wpedantic`, no heap, no stdio; it includes `fm1_engine.h`.
   - Added to `SEQ_SRC`, so it is built into `fm1-seq`, `fm1-seq-check` and
     `RENDER_EXTRA_OBJ`.
   - It includes the room functions and the documented event-room rule. S2
     enforces the rule in the app.
2. **render.cc:**
   - It uses the bridge for every command, including the implicit `play`.
   - It writes the event log from `ev[0..n)` after advance and before
     dispatch.
   - `seq_ns_per_block` still times only command application and advance.
   - It adds three JSON fields: `seq_dropped` (`stats.dropped_events`),
     `seq_max_block_events` and `seq_splits`.
   - It adds `--events N`, with a default of 65,536.
   - Every other field and every CLI behaviour stays the same. render.cc has
     no `seq_dropped` today [verified: render.cc 576–577].
   - The default-route rule stays in render.cc as host policy, and is
     documented.
3. **seq_script.c:** `fm1_script_apply` becomes a wrapper over
   `fm1_seq_apply_line`.
4. **engines/mk/seq.mk:** `SEQ_SRC += seq/seq_host.c`.
5. **Docs:**
   - engines/seq.md gets a "Host contract" section: the 7-step block order
     (§2.4), the event-room rule, the default-route rule, and the fact that
     import resets routes to MIDI t mod 16 + 1.
   - docs/13 §6's API sketch is refreshed: `note_in` takes a track,
     `realtime_in` takes `out` and `cap`, and events carry `tick`.
   - docs/13 §4's sentence on printed button names now gives the manual's
     names.
   - CHANGELOG.md.
6. **No sim/web change,** so no rebuild on aeon. The engines hash in
   `fm1.wasm.json` goes stale, which is a warning only.

**Files:**
- New: engines/include/fm1_seq_host.h, engines/seq/seq_host.c.
- Changed: engines/host/render.cc, engines/host/seq_script.c, seq_script.h,
  engines/mk/seq.mk.
- Tests: tests/test_seq_core.py (objects 5 → 6), tests/test_seq_render.py.
- Docs: engines/seq.md, docs/13 §4 and §6, CHANGELOG.md.

**Tests and exit:**

1. **Baseline before the edit,** on the same machine and compiler. For each run,
   record the sha256 of the WAV, of the `--log-events` file, and of the JSON
   less `ns_per_block`, `realtime_x` and `seq_ns_per_block`.

   | Scripts | Engines |
   | --- | --- |
   | all 34 oracle scripts: 24 in tests/fixtures/movy and 10 in its random/ [verified] | test-sine |
   | the 29 at 44,118 Hz | macro and sixop |
   | the 5 at 48 kHz: 02-clock-rate48k-block7, 23-ext-clock-follow, 24-ext-clock-stale, rand-604-00035 and rand-604-00159 [verified: their headers]. The Plaits-based engines refuse that rate with exit 1, so macro and sixop are not run on them | shapes |
   | test_seq_render's own scripts | as written |

   Each oracle run is made in default mode and with `--compat`, and at
   `--frames 64` and at the script's own block size.

   After the edit there are 0 differences. The PR reports the counts.
2. **pytest at `0b74b3d`.** Every count is unchanged apart from the new tests
   [verified: `pytest --collect-only`]:

   | File | Tests |
   | --- | --- |
   | test_seq_core | 133 |
   | test_seq_render | 13 |
   | test_seq_oracle | 81 (2 xfail on 18-undo) |
   | test_seq_movy | 136 |
   | test_movy_oracle_fixtures | 112 |
   | test_sim_web | 26 |

   `test_the_core_never_allocates` expects 6 objects, and none of them imports
   heap or stdio functions.
3. **New tests in test_seq_render:**
   - **Labels.** With `--engine macro`, `synth:TIMBRE`, `timbre` and
     `a:b:Timbre` give equal `seq_locks_to_engine` > 0 and identical WAVs.
     The same check on test-sine uses Volume, its only parameter.
   - **Unknown label.** `seq_locks_to_engine == 0`, and `seq_splits` equals
     that of the same script without the lane. The WAV is identical too, but
     the WAV alone cannot show a split, since every sound engine renders
     identically when split [verified 2026-10-01: test-sine, macro, sixop,
     shapes, sw-sophie and macro-heavy give identical WAVs at blocks of 1, 7
     and 64 when events fall on shared block boundaries].
   - **Logs.** For all 34 scripts, `fm1-render --log-events` equals `fm1-seq
     --log` at `--frames 64` / `--block 64` and at the script's own block, in
     default and compat mode. Measured identical: 34/34 at 64 frames and
     68/68 at the scripts' own blocks [verified 2026-10-01]. The check is
     integer-only, so it also runs in the `-m32` and ASan jobs.
   - **Drops.** `seq_dropped == 0` everywhere. `seq_max_block_events` ≤ 7 in
     default mode at 64 frames, as measured.
   - **An app-sized buffer.** With `--events 256`, a full 8-track stop (64
     gates, 64 lanes) gives `seq_dropped == 0` and closes every note.
4. **Build and CI.** `make -C engines` builds with no warnings under clang and
   GCC. CI is green in all 7 checks: tests on ubuntu and macOS, 32-bit, ASan +
   UBSan, the dongle firmware and the two AL-255 jobs. The Pages build from PR
   #24 adds a check to PRs that touch `engines/`.

**Depends on:** nothing. No owner decision is needed.

**Size:** S–M, about 300 lines of C and 120 of tests.

### S2. The app hosts the sequencer headless: native and wasm parity, the oracle through the app

**Goal.** Prove that the virtual FM-1 plays any verb script or `movy1` set
sample-identically to `fm1-render`, natively and in WebAssembly, before any UI
exists.

**Scope:**

**`fm1_app_t`.**
- The fields of §2.5. `FM1_APP_SEQ_TRACKS` is 8 [O3].
- The event-room rule, with the pending record.
- The default-route function (§2.3). `fm1_app_init` leaves the core's
  default routes.

**`fm1_app_render`.** `host_advance`, then `host_dispatch` with the app sink
into `a->out`, then the effects, limiter, scope, MASTER and LEDs, as now. With
no sound engine, advance still runs and the events are dropped, as in
render.cc.

**The new C API:**

| Function | What it does |
| --- | --- |
| `fm1_app_seq_line(a, ops, len)` | applies one script line |
| `fm1_app_seq_cmd(a, cmd)` | applies one command, or holds it in the pending record |
| `fm1_app_seq_note_in` | live note input |
| `fm1_app_seq_reset(a, tracks)` | recreates the instance, at most 8 tracks. It sends the note-offs of §2.3 first |
| `fm1_app_seq_route` | sets a track's route |
| `fm1_app_seq(a)` | the instance, const |
| `fm1_app_seq_events(a)` | the last block's events, for logs |

- **`fm1_app_ram`** adds `fm1_seq_size` plus the 3,072 B event buffer.
- **`all_notes_off`** also releases `seq_note_count`.
- **Static checks and tests** assert the two memory sums of §2.6.

**fm1_web.c.** `fm1w_text_buf()`, `fm1w_text_cap()`, `fm1w_seq_text(len)`,
`fm1w_seq_reset(tracks)` and `fm1w_seq_dropped()`.

**sim.mk.**
- `SIM_ENGINE_OBJ += $(SEQ_OBJ)`, which includes `seq_host.o`. Today
  `SIM_ENGINE_OBJ` has no sequencer objects [verified: sim.mk 18].
- The `fm1-sim-render` link adds `$(SEQ_HOST_OBJ)`. `fm1.wasm` never does.
- `WASM_EXPORTS` is updated.

**Staleness inputs.** `sim/web/tools/source_hash.py` adds
`sim/web/test/seq`, `engines/seq` and `engines/include/fm1_seq*.h` to
`SIM_INPUTS` (§6.5). Parity inputs live under `sim/web/`, because
build-on-aeon.sh copies only `engines/` and `sim/web/` [verified:
build-on-aeon.sh 71–77].

**The harness.** `fm1-sim-render` gets `fm1-render`'s semantics for these
flags: `--cmd`, `--seq`, `--tracks`, `--route T:engine|T:midi:CH`,
`--events N` and `--log-events`.
- Rate and tracks come from the script header unless given.
- `--seq` alone implies a `play`.
- Commands apply at the first 64-frame block with pos ≥ frame, after controls
  and notes.
- Blocks are always 64 frames.
- The default-route rule is mirrored.

It also gets `--log-cmds FILE`. In S2 that file lists every script line
applied, verbatim, with its block; S3 adds UI commands to it. Its JSON gains
`seq_bytes`, `seq_events`, `seq_notes_to_engine`, `seq_locks_to_engine`,
`seq_refused`, `seq_dropped`, `seq_max_block_events` and `seq_splits`.

**Parity.**
- `scenarios.json` gains a `"cmd"` field, pointing at
  `sim/web/test/seq/*.verbs` with `#! block=64`.
- `cliArgs` passes `--cmd` to the glibc, js and musl legs.
- `renderApp` copies each due line into the text buffer and calls
  `fm1w_seq_text` at the same block starts, after controls and notes. It fails
  if `fm1w_seq_dropped() > 0`.
- `renderApp` needs its own loader for the script: a stable sort by frame then
  line, the header keys, skipping `#?@` lines, and trimming CR, spaces and
  tabs, as `fm1_script_load` does. That makes a third parser, which could
  drift. So parity.mjs first asserts that its list of applied (block, line)
  pairs equals the one `fm1-sim-render --log-cmds` wrote, and only then
  compares audio.

**Five scenarios.** They route only with `route` verbs.
1. test-sine Volume FLOAT locks, with `abaseq` and a stop (D6 bases).
2. sixop with two engine-routed tracks, swing 62 and `cscl` 2.
3. An ENUM bin on Six-Op Patch, which S7a will keep lockable.
4. Capture committed while playing.
5. A stopped Capture with `capsel`, marked `libm_sensitive`.

**Measurement.** Node's `seq_ns_per_block` for seq_bench's burst, through
`fm1-render.js`, recorded in sim/web/README.md.

**Files:**
- Source: sim/web/src/fm1_app.h, fm1_app.c, fm1_web.c; sim/web/mk/sim.mk;
  sim/web/tools/source_hash.py.
- Harness and parity: sim/web/test/fm1_sim_render.c, parity.mjs,
  scenarios.json, and the new seq/*.verbs; sim/web/build.sh (to record the
  cmd field).
- Tests: tests/test_sim_web.py; tests/test_sim_seq.py (new: the oracle
  through the app).
- Module: sim/web/www/fm1.wasm and fm1.wasm.json, rebuilt on aeon.
- Docs: sim/web/README.md ("What works", the `fm1_app_t` size, the parity
  counts), CHANGELOG.md.

**Tests and exit:**

**tests/test_sim_web.py.** The 26 existing tests pass, plus new ones:
- **The five scenarios:** for each, `fm1-sim-render`'s WAV is byte-identical
  to `fm1-render --frames 64`'s, and the `--log-events` files are identical.
  Peak > 0.01, except in MIDI-routed cases, and `seq_dropped == 0` on both.
- **Exports:** the export list equals `WASM_EXPORTS`.
- **Sizes:** `seq_bytes` is 31,880 at 8 tracks and 18,056 at 4 (via
  `--tracks`). `sizeof(fm1_app_t)` is printed and asserted ≤ 1,210,000, and
  the two memory sums hold.
- **Event room:** a burst of `stop`, `play` and a restart in one gap, at full
  load (8 tracks × 8-note chords, 64 locked lanes), gives `seq_dropped == 0`
  and no sounding notes after a final stop.
- **Routes:**
  - with no route given, track 0 plays the engine in both hosts;
  - `route` verbs give equal `seq_notes_to_engine` in both hosts;
  - an imported set with `rt` lines keeps its routes;
  - an imported set without them gets track 0 on the engine.
- **Hung notes:** a reset or import while notes sound leaves none sounding.

**tests/test_sim_seq.py.** All 34 oracle scripts in default mode with
`--engine test-sine`, plus 6 with macro chosen from the 29 at 44,118 Hz. The
event logs and WAVs are identical between `fm1-sim-render` and `fm1-render
--frames 64`, with 0 dropped. 18-undo is compared app against reference, so
it needs no xfail. Compat stays on `fm1-seq` and `fm1-render`.

**Screens.** `fm1-sim-render --screens DIR` still prints
`{"screens":287,"faults":0}`.

**On aeon,** `FM1_SIM_HOST=user@host sim/web/build-on-aeon.sh` gives:
- parity passed 17/17, and identical to js and to musl 17/17;
- imports `[]`;
- glibc within 1 LSB, except for the 3 `libm_sensitive` scenarios: the two
  Sophie scenarios and the stopped Capture.

**Record and CI.** The sources in `fm1.wasm.json` are current. CI is green
with `CI=true` in all jobs, including the 32-bit and ASan/UBSan builds of
sim/web.

**Depends on:** S1. O3 is only a constant here (8 proposed).

**Size:** M–L.

### S3. First playable: PLAY/STOP, SEQ mode, a read-only Track view, the demo pattern

**Goal.** In the browser, PLAY/STOP plays a pattern, and SEQ shows the grid,
the playhead, the tempo and the transport. The gesture plumbing and the trace
tests are in place for later stages.

**Scope:**

**Panel.**
- `FM1_MODE_SEQ`. SEQ enters it; HOME, FX and GLO leave it.
- PLAY/STOP sends `play` / `stop` in any mode, through `fm1_seq_ui` and then
  `fm1_app_seq_cmd`, as typed `fm1_seq_cmd_t` records.
- Both buttons stop showing the "not in the simulator yet" popup [verified:
  fm1_app.c 409]; REC still shows it.
- The keys still play notes in SEQ mode in this stage.

**New files.**
- `fm1_seq_ui.[ch]`: the state skeleton (view, focused track, bar page) and
  command emission.
- `fm1_seq_view.[ch]`: the Track view of §4, with the status line, the grid
  of the focused track's first 4 bars (notes from `fm1_seq_get_note`, the
  playhead inverted), the knob strip per O23, and the bottom bar.

**LEDs.**
- PLAY (39) is on while playing.
- SEQ (38) is on in SEQ mode.
- In SEQ mode, the white keys show the playhead in the viewed bar.

**The demo pattern** [O4]. A const verb batch, applied only by
`fm1_app_default_chain`, the browser's start. The harness and parity
therefore start empty. It is a 1-bar, 16-step figure on track 0, with no locks
until S8.

**Exports and page.**
- `fm1w_seq_info()` returns a static snapshot: playing, `bpm_x100`,
  recording, `watch_track`, `master_tick`.
- The worklet posts it only when it changes (§2.7).
- In app.js, Space presses PLAY/STOP [O19], and the status line shows BPM and
  the transport.
- index.html gets the help text and the stub list.

**Harness.**
- `fm1_seq_cmd_format` lands in seq_script.c, and `--log-cmds` adds every UI
  command it applies, via the `on_cmd` hook.
- `--panel FILE` takes one existing `--key`, `--button` or `--turn` flag per
  line.
- `--log-cmds` writes the header and sidecar of §6.3.
- `run_screens` adds the Track view states.
- The stub-button loop drops SEQ and PLAY/STOP, and the saved representative
  popup moves from `popup-button-12` (PLAY) to ENV.

**Parity's panel scenario.** Its `.panel` and `.verbs` files live under
`sim/web/test/seq/`, never in tests/fixtures.
- The render legs get `--cmd C.verbs` and the sidecar's arguments.
- The native screen reference gets `--panel`.
- The module leg calls `fm1w_button`.

**Files:**
- New: sim/web/src/fm1_seq_ui.h, fm1_seq_ui.c, fm1_seq_view.h, fm1_seq_view.c.
- Source: sim/web/src/fm1_app.h, fm1_app.c, fm1_web.c; sim/web/mk/sim.mk
  (`SIM_APP_OBJ`, the exports); engines/host/seq_script.c and seq_script.h.
- Harness and parity: sim/web/test/fm1_sim_render.c, parity.mjs,
  scenarios.json, screenshot.mjs, seq/.
- Page and module: sim/web/www/worklet.js, app.js, index.html, fm1.wasm,
  fm1.wasm.json.
- Tests: tests/test_seq_ui.py (new); tests/fixtures/seq-ui/ for pytest-only
  traces.
- Docs: sim/web/README.md, manual chapter 07, CHANGELOG.md.

**Tests and exit:**
- **Gesture traces** (test_seq_ui). Golden panel-to-verbs traces for:
  - SEQ enter and exit;
  - PLAY/STOP from HOME, from FX and from SEQ;
  - PLAY twice.

  Each passes two-step parity (§6.3).
- **Format round trip.** `parse(format(c)) == c` for every verb.
- **test_sim_web.**
  - `led[39]` is 1 while playing and 0 after stop.
  - The mode is SEQ after a SEQ press.
  - The key LEDs follow the playhead in SEQ mode.
  - HOME's key LEDs are unchanged.
- **Screens:** at least 295, 0 faults; the floor is raised.
- **On aeon:**
  - parity 18/18, with the panel scenario; identical to js and musl; imports
    `[]`.
  - screenshot.mjs: PLAY/STOP with the demo pattern gives `chord_rms` > 0.01
    within 1 s and lights LED 39.
  - `lit_keys === 3` and `fx_led` still pass.
- **CI:** green.

**Depends on:** S2. O4 (demo pattern), O6 (key LEDs for sequencer notes), O19
(Space), O23 (knob strip), O24 (public page).

**Size:** M.

### S4. Step entry: the white keys as steps, the Step pages, SHIFT, bar paging

**Goal.** Make a pattern from scratch on the panel and edit it per step: VEL,
LEN, PROB, COND and INV on the four knobs.

**Scope:**

**Input edges.** Release edges and press-frame stamps for keys and buttons.
Today only press edges are handled [verified: fm1_app.c 370]. The hold
threshold is ⌈0.3 · rate⌉ frames.

**The SEQ Track view,** as in §3.3–§3.7:
- a tap toggles with `tog` pairs;
- a hold opens the Step page;
- hold + press sends `slen`;
- several held steps are edited together;
- ◀ ▶ page bars, or send `enudge` with a step held;
- SHIFT is SEL outside FX;
- OCT with steps held sends `etrn`;
- SHIFT + 10 sets full velocity, and SHIFT + PLAY restarts;
- the remembered chord comes from the keys and MIDI IN, with a velocity per
  pitch;
- the pitch gesture is whatever O22 decides.

**The Step pages.**
- Step 1/2 (VEL, LEN, PROB, COND): `evel`, `elen` with Movy's 21 values,
  `eprob`, and `econd` with the 36 A:B pairs.
- Step 2/2: INV (`einv`).
- SELECT pages between them, with page memory [O21].

**Core.** `fm1_seq_get_page` (§2.5) and `rec_track` in `fm1_seq_info_t`. They
are needed for the PROB, COND and INV read-outs and for the grid's trig
ticks.

**Grid and LEDs.** The grid gains the trig tick and the bracket of the bar on
the keys. The LEDs show steps, the playhead, and a slow blink under the held
step's length.

**Page.** In app.js, Shift is SEL in SEQ mode, and the 16-step keymap of §3.15
applies.

**Docs.** docs/13 §4 records O22's answer.

**Movy facts.** Re-read `step-page-vm.ts` (LEN's units) and the MANUAL's
Shift+step list at `9190e79` into the git-ignored `reference/`. Both are only
[reported] so far.

If the stage grows too large, split it: taps, holds and paging first, then
the Step pages.

**Files:**
- Core: engines/include/fm1_seq.h, engines/seq/seq_engine.c, seq_clip.c,
  tests/test_seq_core.py.
- App: sim/web/src/fm1_seq_ui.c, fm1_seq_view.c, fm1_app.c, fm1_app.h.
- Harness: sim/web/test/fm1_sim_render.c, scenarios.json, seq/.
- Tests: tests/test_seq_ui.py, tests/fixtures/seq-ui/, tests/test_sim_web.py.
- Page and module: sim/web/www/app.js, index.html, fm1.wasm, fm1.wasm.json.
- Docs: docs/13 §4, sim/web/README.md, manual chapter 07 and `manual.toml`
  roles, CHANGELOG.md.

**Tests and exit:**
- **Core.** For every fixture's `.out.movy1` set, `fm1_seq_get_page` agrees
  with the `movy1` export: notes, locks and trig rows.
- **Gesture traces.** At least 15 golden traces, each with exact verb
  strings and two-step parity:
  - a tap on white key 4 gives `tog 0 3 p1 v1`;
  - a 13,236-frame hold toggles nothing;
  - A + B gives `slen`;
  - several steps held, with a KNOB2 turn;
  - OCT with a hold;
  - bar paging;
  - SHIFT + 10;
  - each Step page field at its minimum and maximum;
  - the O22 pitch gesture.
- **Screens:** about +20, 0 faults, at most 96 boxes; the floor is raised.
- **On aeon:**
  - parity 19/19, with one scenario covering probability, condition, invert
    and a multi-bar clip;
  - screenshot.mjs taps 4 steps, plays, and sees rms > 0.01 and moving LEDs.
- **CI:** green.

**Depends on:** S3. O1 (roles), O2 (SHIFT on SEL), O5 (default pitch and
velocity), O19 (the step keys), O21 (SELECT for pages), O22 (pitches on a held
step).

**Size:** L.

**As built (2026-10-02, branch `feature/2026-10-02@seq-step-entry`, on S3's
branch).** Everything stays behind the lab switch (O24). The gestures are
§3.5's table. Where the build differs from, or adds to, the plan above
[verified: tests/test_seq_ui.py, tests/test_seq_core.py, `fm1-sim-render
--screens`]:
- **O22, as the owner changed it:** pitches on a held step are only added
  (SHIFT + white key, or a note at MIDI IN, `addp`); a SHIFT tap during a
  hold clears the step (`del`). It cannot collide with the shortcuts
  (SHIFT + N needs no step held), with `addp` or the SHIFT nudge and
  transpose (another input while SHIFT is down makes it no tap), or with
  `aclrs` (a knob detent is such an input).
- **Movy facts read at `9190e79`** into the git-ignored `reference/`
  [verified]: `step-page-vm.ts` (LEN's 21 lengths in ticks, 12 to 6,144;
  PROB 100 to 10; COND's 36 pairs, B up to 8; INV), `step-edit.ts` (VEL
  is a relative `evel` of 4 per detent; LEN an absolute `slen`; nudge 2
  ticks, 1 with Shift; transpose `etrn` with lane −1; one command per held
  step), `router-steps.ts` (the tap on release, the hold-A-press-B length
  and its end/start toggle, steps pressed together each entered, the
  hidden rest of a short clip's bar) and `step-shortcuts.ts` (Shift + 10 is
  full velocity). Movy's `hold` verb is not sent: the C core stores it and
  nothing reads it.
- **Full velocity** sets every step entered, and the keys played outside
  SEQ mode, to 127; MIDI IN's own notes keep their velocity.
- **OCT on held steps** belongs to them: the app does not count that press
  as held, so ALGORITHM turned while it is down still turns the model, and
  the other OCT pressed after the steps' release moves the octave instead
  of resetting it.
- **The Step pages** stay two (Step 1/2 and 2/2): the sound's pages join
  them as lock pages in S8. Step page 2's nudge and note are read-outs.
- **The Track view** draws the grid's four bars round the bar on the keys
  (from S3's fixed first four), a trig tick under steps with a probability,
  condition or invert row, held steps framed, and a bracket at both ends of
  the bar on the keys; the hint line names the bar after ◀ ▶, and SHIFT's
  shortcut while SEL is held.
- **The bar on the keys follows the loop:** it is kept between the loop's
  first bar and the empty bar after it, so a loop moved away takes it
  along (S3's sweep had kept it on bar 1, outside the loop).
- **Gesture traces:** 22 new golden traces in tests/fixtures/seq-ui/
  (`step-*`), each replayed by `fm1-render` byte for byte. A key that plays
  the sound is now logged into the replay's sidecar as a `--note` at
  mid-block times (half of S5's harness item; S5 adds `non`/`nof`), and a
  `--panel` file may hold `--note` lines for MIDI IN. `fm1-render` plays a
  block's note-offs, then its note-ons, in argument order, so a run whose
  notes went to the sound in another order within a block (a MIDI IN note
  after a key's) says `"replayable":0`.
- **Screens:** 99 more, 914 in all, 0 faults; the lab-off screens are
  byte-identical to S3's (293 compared).
- **Core:** `fm1_seq_get_page` and `fm1_seq_info_t.rec_track`. The Track
  view shows REC when the focused track records.
- **The UI state** is 456 B of its 1,024 [verified: `fm1-sim-render
  --sizes`].
- **On aeon** [verified: `www/fm1.wasm.json` and the screenshot report,
  2026-10-02]: parity 25 of 25 (S2 and S3 had added more scenarios than
  §6.1 counted), with the new `seq-panel-step-entry` covering probability,
  condition, invert, a two-bar clip, a nudge, `addp` and the clear;
  identical to js and musl in 25, to glibc in 22; imports none. In
  headless Chromium, A#3 and four step keys enter bar 2 (exactly those
  four keys light), and played, the pattern sounds (RMS 0.024) and the
  lights move. The module is 482,291 B, up from 466,635.

### S5. Record and Capture (record-after, on by default)

**Goal.** Play on the keys and keep it: REC with a count-in and overdub, and
SHIFT + REC for Capture, including the stopped Capture's tempo picker.

**Scope:**

**Live input** (§3.2). Outside SEQ mode, keys call
`fm1_app_seq_note_in(focused track, pitch, vel)` at frame 0, with velocity 0
on release. MIDI IN notes do so in every mode. The keys still sound the engine
directly, because the core does not echo input.

**REC.** `rec t`. The LED blinks fast during the count-in and a waiting first
take, and is on while recording.

**Capture.**
- SHIFT + REC sends `cap t` [O7].
- capture_mode 1 opens the picker: SELECT or KNOB1 sends `capsel i`, and any
  other press sends `capdone`.
- capture_mode 2 shows the two-line toast.
- REC blinks slowly while `capture_pending` > 0.

**Step record** [O8]: REC held while stopped. It can be deferred.

**Core** [O9]. A new D-row: `commit_playing` clamps a last-half-step note to
the loop's last step, as D4 does for live record.
- **The gap:** capturing a note in the last half-step while playing stores it
  at step index 16, one past the loop, and grows a 16-step clip to 32 steps.
  That happens in default and in compat mode, while live record of the same
  note is clamped [verified 2026-10-01 at `147ed14` and again at `0b74b3d`,
  in planning runs].
- Compat keeps Movy's growth, so the oracle's compat tests are unaffected.
- docs/13 §3.3 gets the row.
- Since S2 put `engines/seq` among the hashed inputs, landing this row alone
  also needs a rebuild of the module.

**Harness.** `--log-cmds` writes key input as `non` / `nof` lines. It writes
the engine notes into the sidecar as `fm1-render --note T:KEY:VEL:DUR`
arguments, at mid-block times (§6.3).

**Files:**
- Core and docs: engines/seq/seq_capture.c, docs/13 §3.3, engines/seq.md,
  tests/test_seq_core.py.
- App: sim/web/src/fm1_seq_ui.c, fm1_seq_view.c, fm1_app.c.
- Harness: sim/web/test/fm1_sim_render.c, scenarios.json, seq/.
- Page and module: sim/web/www/app.js (`onMidi` feeds the sequencer),
  fm1.wasm, fm1.wasm.json.
- Tests and docs: tests/test_seq_ui.py, tests/test_sim_web.py, manual chapter
  07, CHANGELOG.md.

**Tests and exit:**
- **Equivalence.** A panel performance on the keys with REC, logged to verbs,
  replays through `fm1-render --cmd C.verbs` plus the sidecar's `--note`
  arguments byte for byte. Covered: the count-in, overdub, and Capture both
  playing and stopped.
- **The D-row.** In default mode the clip stays 16 steps, with the note at
  step index 15. Compat grows it to 32. test_seq_oracle's 81 tests are
  unchanged.
- **On aeon:** parity 20/20. The stopped Capture is `libm_sensitive`, which
  exempts glibc only; the module, js and musl stay exactly equal.
- **Screens:** the picker with 1, 2 and 3 candidates, the count-in,
  recording, and the toasts; 0 faults; the floor is raised.
- **CI:** green.

**Depends on:** S4. O7 (the Capture gesture and the REC LED), O8 (step
record), O9 (the D-row, which can also land alone in `engines/`).

**Size:** M.

**As built (2026-10-02, branch `feature/2026-10-02@seq-record`, on S4's
branch).** Everything stays behind the lab switch (O24); the owner's
answers to O7–O9 are in §8. Where the build differs from, or adds to, the
plan above [verified: tests/test_seq_ui.py, tests/test_seq_core.py,
`fm1-sim-render --screens`]:
- **Live input.** A note played that no step takes is live input to the
  focused track (`fm1_app_seq_note_in`, at frame 0 of the coming block):
  the keys outside SEQ mode, and MIDI IN in every mode. A note that went
  into the pattern as an edit (a held step's `addp`, step record) is not,
  as Movy's router skips its capture path for a pad it consumed. A release
  goes to the track its note went to, and a change of sound or a panic
  releases every note given. With the switch off nothing is given.
- **REC** sends `rec <focused>` in every mode. In SEQ mode with the
  transport stopped it acts on its release, as Movy's Rec does
  (`router.ts`, `step-rec.ts` at `9190e79`): let go untouched within
  ⌈0.5 · rate⌉ frames (Movy's 500 ms tap; 22,059 at 44,118 Hz), it
  records; held, it is step record. Elsewhere, or while playing, it acts
  on the press.
- **Step record (O8)** follows Movy's `step-rec.ts` and `step-rec-head.ts`
  at `9190e79` [verified: read into the git-ignored `reference/`]:
  - each white key enters its pitch, in the current octave, at the record
    head and sounds (on the sound only: it is no live input): `del` on a
    fresh step, then `addp`, and in a clip that was empty a `clen` that
    grows it to what is played, rests included. MIDI IN notes enter the
    same way, which is how sharps go in;
  - keys held together are a chord on one step, and the head moves on when
    the last is let go;
  - A#3 (▶) leaves a rest, or with keys down ties the chord into the next
    step (`slen` per pitch; the head rides to the tied note's end); F#3
    (◀) steps back, or unties;
  - SHIFT + white key moves the head to that step of the bar and clears it
    (Movy's step buttons); past a clip's end only while the clip grows;
  - a clip that had a length wraps at its loop's end;
  - nothing latches: letting go of REC ends it, and so do PLAY/STOP,
    leaving SEQ mode and the transport starting.
  - **The head advances by itself on key release,** as the owner asked.
    Movy at `9190e79` already does so: its head "advances only when the
    LAST pad comes up" (`step-rec.ts`; MANUAL.md, "Step recording")
    [verified]. So it is no deviation and needs no row, and since step
    record is the UI's alone, compat mode is untouched. The plan's
    premise came from a [reported] summary and was wrong.
  - **Three differences from Movy:** the head starts on the loop's first
    step (Movy parks it on step 1 whatever the loop); it wraps at the
    loop's end, where Movy's `advanceHead` compares the head with the
    loop's length, so for a loop that starts on a later bar Movy's head,
    once in the loop, returns to its first step at every advance, and its
    step buttons refuse every step past the length (`step-rec-head.ts`,
    `step-rec.ts` at `9190e79`) [verified; the wrap here:
    `test_step_record_wraps_at_the_end_of_a_loop_on_a_later_bar`]; and a
    step back does not play the step's notes (Movy's preview), which
    `fm1-render` could not replay. The first two agree with Movy for a
    loop on bar 1. Movy's drum rule (pads only add) waits for drum tracks.
  - **MIDI IN in step record** is ours (Movy steps on pads): a pitch
    already down is one pad, so a second note-on of it enters nothing and
    its first release closes the chord.
- **Capture (O7).** SHIFT + REC sends `cap <focused>` outside FX mode, or,
  with nothing buffered, shows `Nothing to capture` and sends nothing, as
  Movy's `captureButton`. The next block says what it did: `Captured`
  while playing, and for a stopped take whose tempo needed no choice;
  otherwise the core's overlay.
- **The overlay** is the core's `capture_mode`, read once per block and
  drawn over every mode where popups go. The picker (mode 1) lists the
  candidates, one a line, the one taken highlighted; SELECT or KNOB1 sends
  `capsel`, heard at once. The fitted tempo (mode 2) reads `Captured` /
  `at 117.50 BPM`; there SELECT and KNOB1 do nothing, as Movy's jog
  (`captureJog` at `9190e79`) [verified]. **Both stay until a press, as Movy's overlay does,**
  rather than mode 2 being a one-second toast as proposed: the core takes
  no Capture input until `capdone`. Any press (a button, a key, another
  encoder) sends `capdone` and does nothing else, as in Movy, where a key
  that both closed it and wrote into the take would need undo; releases go
  through, and MIDI IN notes are no presses.
- **O9, as the owner changed it:** no D-row. Capture committed while
  playing anchors a last-half-step note on the loop end and grows the clip
  by a bar in both modes, as Movy does;
  `test_capture_while_playing_grows_the_clip_as_movy` pins it (16 steps
  become 32, the note on step 16).
- **LEDs.** REC is on while recording or step recording, fast (0.25 s)
  during the count-in or while a take waits for its bar, and slow (1 s)
  while Capture holds notes and nothing records. In step record the head's
  white key blinks fast, A#3 is lit, and F#3 while a step back or an untie
  is possible.
- **Screens.** The status line reads REC in gold through the count-in or a
  waiting take, in red while the focused track records, and STEP in step
  record; the grid frames the head in red; the hint line gives the head's
  step (`Step rec 17`; a tie, `17-19`) or, with SEL held, `Keys move the
  head`.
- **Harness.** `--log-cmds` logs live input as `non` and `nof` ops at the
  block they led (a second hook, `on_note_in`) and lists them with the
  panel's commands, so traces that play keys or MIDI IN replay byte for
  byte, which closes S3's open issue; three S4 traces gained those lines.
- **Gesture traces:** 11 new golden traces in tests/fixtures/seq-ui/
  (`rec-*`, `step-record*`, `capture-*`), each replayed by `fm1-render`
  byte for byte.
- **Screens:** 39 more, 953 in all, 0 faults. Of the PPMs the sweep
  saves, the 36 with the lab switch off are byte-identical to S4's; of
  the 35 lab-on ones S4 also saved, 24 are identical and 11 (the hint
  line's and each sound's page) differ only because the sweep's REC now
  counts in and the next block's read shows track 1's loop, where S4's
  showed the stale mirror of track 8, which has no clip [verified:
  `fm1-sim-render --screens` at S4's head and here, in review].
- **The UI state** is 536 B of its 1,024; `fm1_app_t` is 1,205,920 B
  [verified: `fm1-sim-render --sizes`].
- **On aeon** [verified: `www/fm1.wasm.json` and the screenshot report,
  2026-10-02]: parity 27 of 27, with `seq-panel-record` (a take after a
  count-in, step record with a tie, a rest and a MIDI IN note, and Capture
  while playing) and `seq-panel-capture-stopped` (the picker,
  `libm_sensitive`); identical to js and musl in 27, to glibc in 24, the
  stopped Capture included; imports none. In headless Chromium, REC in SEQ
  mode while playing overdubs at once and REC again stops; two keys
  played in HOME make REC blink, and Shift (SHIFT) + REC captures them and
  REC goes dark; with the switch off REC stays a stub. The module is
  490,916 B, up from 482,291.

### S6. Tracks, mute, and the Set, Clip and Track pages

**Goal.** 4–8 tracks to focus and mute, with tempo, swing, clip speed, length,
transpose and quantise on the four knobs.

**Scope:**

**Tracks.**
- Focus with SEQ + white keys 1–8, or C#5 / D#5. Both send `watch t`, with a
  toast that Capture was emptied.
- **Routes.**
  - `fm1-render` routes only track 0 to the engine by default; every other
    track starts on MIDI channel t mod 16 + 1 (§2.3).
  - Every engine-routed track shares the one sound unit, as in render.cc,
    which ignores `route_index` [verified: render.cc 493–522]. Since
    2026-10-02 (O10, §3.16) the lab switch routes by slot instead: each
    engine-routed track plays the sound unit its route index names, as
    `fm1-render --slots` does, and S6 routes tracks with `fm1_app_unit_*`.
  - What tracks 1–7 do in the browser is O10. The proposal is that the
    browser's start chain routes them to the engine with `route` verbs, so
    they can be heard. That is browser policy only, like the demo pattern.
    Parity scripts state every route explicitly, with `route` verbs.

**Mute.** A tap, the held mute map, and SHIFT + MUTE to solo by muting the
other tracks [O12].

**Pages,** as in §3.10:
- Set: SHIFT + 5, 7 or 9.
- Clip: SHIFT + 3.
- Track: SHIFT + 2.
- SHIFT + 16 cycles quantise.

**Metronome click** [O11], only if approved: a deterministic, libm-free click
voice in the bridge, mixed before the limiter by both `fm1-render` and the
app. Today render.cc ignores CLICK events [verified: render.cc 493–522].

**Files:**
- App: sim/web/src/fm1_seq_ui.c, fm1_seq_view.c, fm1_app.c, fm1_web.c;
  sim/web/mk/sim.mk.
- Page and module: sim/web/www/worklet.js, app.js, fm1.wasm, fm1.wasm.json.
- Harness: sim/web/test/fm1_sim_render.c, scenarios.json, seq/.
- Tests: tests/test_seq_ui.py, tests/test_sim_web.py.
- engines/seq/seq_host.c and render.cc, only if the click is approved.
- Docs: sim/web/README.md, manual chapter 07, CHANGELOG.md.

**Tests and exit:**
- **Traces.** About 10 more gesture traces, with two-step parity. Each
  browsing trace asserts that no `watch`, `clipsel` or `launch` is emitted
  except by the focus gesture itself.
- **Event logs.** The app equals `fm1-render` for 4 engine-routed tracks, with
  mutes and a solo.
- **On aeon:** parity 21/21, covering 4 tracks, swing, and `cscl` at 1/2X and
  2X. A click adds one more scenario if O11 approves it.
- **Screens:** every page at its extremes, and 8 tracks' lane labels; 0
  faults; the floor is raised.
- **Memory:** at 8 tracks, the RAM figure includes the 31,880 B instance plus
  3,072 B of events.
- **CI:** green.

**Depends on:** S4; S5 is independent. O3 (the final track count), O10 (sound
sharing and default routes), O11 (the click), O12 (solo).

**Size:** M–L.

**As built (2026-10-02, branch `feature/2026-10-02@seq-tracks`, on S5's
reviewed head with the multi-sound branch merged).** Everything stays
behind the lab switch (O24); with it off the panel is unchanged. The
owner's answers to O3 and O10–O12 are in §8. Where the build differs
from, or adds to, the plan above [verified: tests/test_seq_ui.py,
tests/test_sim_seq.py, tests/test_seq_render.py, `fm1-sim-render
--screens`]:
- **Tracks (O3: 8).** SEQ held with white key 1–8 focuses that track, in
  every mode: SEQ's press opens SEQ mode as before, and a focus made while
  it is held goes back to the mode SEQ was pressed in when it is let go
  (so SEQ + 3 from HOME is a quick switch for playing into track 3). C#5
  and D#5 (MONO, POLY printed) step to the previous and next track in SEQ
  mode, stopping at the ends; both are inert with steps held or in step
  record. A focus sends `watch t` and a toast, `Track 3`, with a second
  line `Capture emptied` when Capture held notes; the focused track again
  sends nothing, so it keeps them. The Track view resets to the track's
  first bar.
- **Routes (O10 as changed).** The Track page routes the focused track
  to a sound unit, `route t 1 k` (Sound 1–4), or to MIDI out on a channel,
  `route t 0 c` (logged only: the simulator has no MIDI out). The UI sends
  the typed command itself (as `fm1_app_unit_route` would), so the harness
  logs it and `fm1-render --slots` replays it. Focusing a track, or routing
  the focused track to a sound, makes that sound current (§3.16 left it to
  S6): the keys then play, and HOME edits, what the track plays; SHIFT +
  PRESETS still chooses another after. **The browser's default:** on its
  start chain, with the lab switch, track 1 plays Sound 1 by the
  default-route rule and every other track still on its default MIDI route
  is routed to Sound 1 too (`fm1_app_seq_start_routes`), until the user
  routes it. That is browser policy, like the demo pattern: tests and
  parity runs route with verbs.
- **Mute (O12: no solo).** F#4 (OP6): a tap mutes or unmutes the focused
  track on release (`mute t 0|1`, Movy's router-buttons.ts); held, white
  keys 1–8 toggle tracks 1–8 (the mute map, router-steps.ts) and MUTE's
  release then does nothing. SHIFT + MUTE is MUTE. Inert with steps held.
- **SHIFT's shortcuts** (Movy's step-shortcuts.ts): 2 the Track page, 3
  the Clip page, 5, 7 and 9 the Set page, 6 the metronome (`metro`, with a
  toast), 10 full velocity, 16 the focused clip's quantize on to the next
  of 0, the Set page's default and 100 (`cq`, Movy's
  nextQuantCandidate, with a toast). Their legend replaces the grid while
  SHIFT is held with no step held (the S4 hint-line legend is gone).
- **The pages** (§3.10, HOME's rows). Set: TEMPO (`bpm`, 1 BPM a detent,
  0.1 with SHIFT, 20–300), SWING (50–80 %), DEF QUANT (`dq`, Movy's 0–100 %
  list), METRO. Clip: SPEED (`cscl`, Movy's eight speeds 1/8X–4X), LENGTH
  (`clen`, a step a detent up to 256 less the loop start; with no clip,
  only a turn up makes one), TRANSPOSE (`ctr`, ±36), QUANT (`cq`). Track:
  ROUTE, SOUND 1–4 or CHANNEL 1–16, MUTE; page 2 lists the eight lanes
  (each label's text after its last `:`, cut to 13 characters, and its
  7-bit base), read only. Each knob sends one command a turn, from the
  value last read or sent, so detents between blocks add up. SELECT walks
  past the sound's last page to Set, Clip, Track 1/2 and 2/2 and back
  (O21); SEQ returns to the Track view, and so does a step or bar key (a
  SHIFT shortcut keeps the page). Browsing sends nothing.
- **The metronome's click (O11: yes).** A voice in the shared bridge
  (`fm1_seq_click_t`, `fm1_seq_click_mix` in engines/seq/seq_host.c):
  each CLICK event starts a click at its own frame while `metro` is on; a
  triangle tone of rate/2000 frames a half-period (about 1 kHz; rate/3200,
  about 1.7 kHz and louder, on a downbeat) under a quadratic decay of
  rate/50 frames, all in integers, added to both channels after the
  effects and before the limiter. `fm1-render` and the app mix it the same
  way, so two-step parity and the parity legs cover it; it renders the
  same at blocks of 1, 7 and 64. The count-in's clicks sound only while
  `metro` is on, as O11 reads; Movy clicks the count-in regardless
  [inferred from the core, which emits them either way], which the owner
  may want instead (open).
- **Event buffer.** 272 events (3,264 B), up from 256: seq_bench's burst
  needs 257 [verified: `fm1-render --events 256` drops 400 note-ons,
  `--events 272` none]. With the click's 20 B the sequencer's share is
  36,428 B of 36,864 at 8 tracks (§2.6). The public page's RAM figure
  counts the bigger buffer too: 192 B more, which reads 1K more for 4 of
  the 54 one-effect chains [verified: `fm1-sim-render`].
- **Screens.** The status line holds the eight tracks (a cell each: gold
  for the focused one, an outline for a muted one), a muted track's notes
  dim, and the hint line names SEQ's and MUTE's key maps. 69 more screens,
  1,109 in all, 0 faults; every lab-off screen the sweep saves is
  byte-identical to the merge base's [verified: `fm1-sim-render --screens`
  at both, compared]. The UI state is 552 B of its 1,024.
- **Gesture traces:** 10 new golden traces in tests/fixtures/seq-ui/
  (`track-*`, `mute-*`, `set-page`, `metro-shortcut`, `clip-*`,
  `pages-browse`) from tracks.verbs, each replayed by `fm1-render` byte for
  byte; the browsing ones assert no `clipsel` or `launch`, and `watch`
  only from a focus gesture.
- **Event logs.** Four engine-routed tracks with swing, clips at 1/2X and
  2X, mutes on the fly and the click play through the app as through
  `fm1-render`, event log and audio, with Test Sine and Macro
  (tests/test_sim_seq.py).
- **On aeon** [verified: `www/fm1.wasm.json` and the screenshot report,
  2026-10-02]: parity 32 of 32 (the merge of S5 and multi-sound brought
  30), with `seq-panel-tracks` (the panel trace above, across two sound
  units) and `seq-metro-click` (the click on, off, on with swing, and a
  count-in); identical to js and musl in all 32, to glibc in 29 (the two
  Sophie scenarios and Fold's 1 LSB, as before); imports none. In
  headless Chromium, SEQ held with white key 2 makes track 2 the watched
  one and the screen says `Track 2`; the lab-off checks pass unchanged.
  The module is 514,270 B.

**Review (2026-10-02).** The review found one bug and fixed it: a track
rerouted on its Track page while a note sounded left that note on for
good on the old sound, since its note-off followed the new route
[verified: `fm1-render`, a bar-long note rerouted from Sound 1 to MIDI out
kept sounding to the end]. A `route` that moves a track now closes the
track's gates at once (the core, `seq_cmd.c`), and the bridge sends a
note-off from the block's commands where the track's notes went at the
last dispatch (`fm1_seq_host_t.dest` and `cmd_n`), so both
hosts let go of it there [verified: tests/test_sim_multi.py, to another
sound and to MIDI out, with and without the lab switch, the app equal to
`fm1-render`]. The bridge's own state, `fm1_seq_host_t`, is 352 B
natively (328 B before; it holds the lanes' 256 B of uids since S7a) and
is not in §2.6's sum or the on-screen RAM figure; counted, 8 tracks still
fit the 36,864 B, with about 100 B to spare [inferred: about 336 B at
32 bits]. The module, rebuilt, is 514,688 B: parity 32 of 32, identical to
js and musl in all 32 and to glibc in 29 as before, no imports, and the
headless Chromium checks pass [verified: `www/fm1.wasm.json`, 2026-10-02].

### S7a. Engine API v2 (docs/13 M2): uid, flags, NOLOCK, with byte-identical audio

**Goal.** Fix what a lock targets and which parameters can be locked, before
the lock UI exists, without changing any sound.

**Scope:**

**fm1_engine.h.**
- `FM1_ENGINE_API_VERSION` becomes 2.
- `fm1_param_t` gains a trailing `uint16_t uid` and `uint8_t flags`:
  `FM1_PARAM_LATCH`, `FM1_PARAM_SMOOTH` and `FM1_PARAM_NOLOCK`.

**Engine tables.**
- Every kParams table gets its uids and flags in this PR. The tables use
  positional initialisers, and `-Wextra` warns on missing fields, so they
  cannot be left for later.
- Schwung module parameters get uids derived stably.
- The flag table is O13. It covers all eight ENUM parameters in the registry
  [verified: `grep FM1_PARAM_ENUM engines/src`]:

  | Engine | ENUM parameter | Proposed flag |
  | --- | --- | --- |
  | macro | Model | NOLOCK |
  | macro-heavy | Model | NOLOCK, since Macro's Model rebuilds voices |
  | shapes | Shape | NOLOCK |
  | sixop | Patch | LATCH, read at note-on |
  | sw-sophie | Pad | NOLOCK, unless S7a finds that a change leaves sounding voices intact |
  | sw-sophie | Model | NOLOCK, unless S7a finds that a change leaves sounding voices intact |
  | sw-sophie | Filter Type | lockable, no flag |
  | sw-psxverb (FX) | Model | NOLOCK, unless O14 allows effect locks |

  Continuous parameters get SMOOTH, which takes effect only in S7b.

**Bridge.**
- Lane labels resolve to a uid at `alabel` and at import. `movy1` keeps
  `synth:<Name>`, or the form O13 picks.
- NOLOCK parameters are refused, and the refusals counted.

**Hosts.**
- `fm1-render --list` and the module's catalog JSON show each parameter's uid
  and flags.
- `fm1_app_select`'s version check accepts v2 only.

**Files:**
- engines/include/fm1_engine.h.
- engines/src: mi_macro.cc, mi_macro_heavy.cc, mi_shapes.cc, mi_sixop.cc,
  mi_fx.cc, sw_sophie.cc, sw_psxverb.cc, test_sine.cc, test_gain.cc,
  schwung_shim.cc, registry.cc.
- engines/seq/seq_host.c, engines/include/fm1_seq_host.h,
  engines/host/render.cc.
- sim/web/src/fm1_app.c, fm1_web.c; sim/web/www/fm1.wasm, fm1.wasm.json.
- Tests: tests/fixtures/param-uids.json (new), the engine tests,
  tests/test_seq_render.py.
- Docs: docs/11 §5.2, docs/13 §6 and §9 (M2 done in part),
  engines/README.md, CHANGELOG.md.

**Tests and exit:**
- **Uids.** They are unique per engine and equal `tests/fixtures/param-uids.json`,
  so a reordered table cannot silently move locks. The file pins all eight
  ENUM flags.
- **NOLOCK.** A Macro Model lock is refused: `seq_locks_to_engine` is 0 and
  the refusal is counted. The audio equals the same script without the lane.
  `test_an_enum_lock_selects_a_bin`, which uses Macro Model today [verified:
  test_seq_render.py 108–119], moves to Six-Op Patch.
- **Audio unchanged.** Every WAV in S1's baseline matrix is byte-identical,
  except scripts that lock a parameter which is now NOLOCK; those are listed in
  the PR. The parity records are unchanged.
- **CI:** green.

**Depends on:** S2, for the parity path. It merges before S8. O13: approval of
API v2 now, the flag table, and the label format.

**Size:** M.

**As built (2026-10-02, branch `feature/2026-10-02@engine-api-v2`).** O13
and docs/16's request (§2.2, question 7) were approved. Where the build
differs from the plan above [verified: engines/README.md, "Parameters";
engines/seq.md, "Host contract"]:
- **Ten ENUM parameters**, not eight: Macro's and Macro Heavy's LPG came
  with their third page. Both are lockable with no flag.
- **Sophie.** A triggered voice copies its pad's patch, so Model and Filter
  Type leave sounding voices intact: LATCH and MOD, not NOLOCK. Pad stays
  NOLOCK for another reason: it is the module's edit focus, so a lock on it
  would change what the other lanes' locks mean. Sophie's FLOAT parameters
  are LATCH rather than SMOOTH, for the same copy. (Until S8: the owner
  then made Pad lockable, with no flag; S8's as-built notes.)
- **Also added for docs/16:** the MOD and INPUT flags and the `unit` and
  `abbr` fields.
- **The bridge** keeps one resolved uid per lane (256 bytes in
  `fm1_seq_host_t`) and adds `fm1_seq_host_bind`, `fm1_seq_host_import` and
  `fm1_seq_host_lane_uid`. A stored uid is used only while its parameter
  has the name the lane's label gives, so a host that imports or labels on
  the core directly, past the bridge, still locks the right parameter
  [verified: engines/test/seq_host_test.c]. The app on S2's branch imports
  that way (`fm1_seq_import_movy1`); `fm1_seq_host_import` is the better
  call once both have merged. `fm1-render --list` shows each parameter's uid,
  flags, unit and abbreviation, and its summary `seq_locks_refused`.
- **The simulator is unchanged.** `sim/web/src` already accepts v2 only
  (its check compares against `FM1_ENGINE_API_VERSION`). The catalogue JSON
  with uids and flags, and the module's rebuild, are left to the stage that
  adopts v2 in the app; until then `fm1.wasm.json`'s engines hash is stale,
  which is a warning. The parity scenarios' inputs were run natively before
  and after, identical.

### S7b. SMOOTH inside the engines

**Goal.** Locks and knob moves on continuous parameters stop clicking, and
output stays identical at any host block size.

**Scope:**
- **The owner's choice:** SMOOTH is engine-side (docs/13 §10, answer 5). A
  shared `fm1_smooth.h` ramp of about 2–3 ms [O13] runs inside each engine's
  native-rate block loop, keyed to absolute native samples. It is never
  stepped per render call, which would make output differ between host blocks
  of 1, 7 and 64.
- **Native rates.** The Plaits-based engines run `plaits::Voice` every 12
  samples at 47,872 Hz, and Braids runs every 24 samples at 96 kHz, each
  resampled [verified: engines/README.md 164–165, 192–193]. Keying the ramp
  to native samples keeps `test_engines_reference_plaits`' rate comparison
  valid.
- **Docs.** docs/12 §5.3 still describes a host-side ramp in 16-frame
  sub-blocks [verified: docs/12 247–249]. It is rewritten to match.

**Files:**
- engines/include/fm1_smooth.h (new) and each engine's parameter path in
  engines/src.
- sim/web/www/fm1.wasm and fm1.wasm.json.
- Tests: tests/test_seq_render.py and the engine tests.
- Docs: docs/12 §5.3, engines/README.md, CHANGELOG.md.

**Tests and exit:**
- **Zipper test, on test-sine Volume,** where amplitude is the parameter
  itself. Macro reads its parameters once per 12-sample internal block, and
  `fm1-render` outputs only audio, so a per-sample bound cannot be observed
  there. A 0→127 lock under a held note changes the amplitude by at most a
  measured bound per sample.
- **Block sizes.** `test_audio_is_the_same_at_host_blocks_of_1_7_and_64`
  still passes for test-sine, macro and sixop.
- **The reference-Plaits tests** still pass.
- **The S2 oracle-through-the-app test** still passes, and the screens have 0
  faults.
- **On aeon:** every parity scenario passes against the new audio, with the
  module, js and musl exactly equal. The record shows which scenarios
  changed.
- **CI:** green.

**Depends on:** S7a. O13 (the ramp time).

**Size:** M–L.

### S8. Parameter locks from KNOB1–4 (7-bit)

**Goal.** Hold a step and turn a knob to lock a parameter on that step. The
grid shows lock dots and the pages show locked values, and the base values
stay in sync with what the knobs show.

**Scope:**

**Bridge.** `fm1_seq_value7`, the inverse of `lock_value`: rounded linear
for FLOAT, and for ENUM the lowest v whose bin is the value.

**UI** (§3.9):
- the knob snaps to the 7-bit grid on laned parameters;
- lock pages with `alabel`, then `abaseq` of the current value, then a quiet
  `aset`;
- `abase` with no step held, and `abaseq` after 600 ms idle;
- `aset … 0` while recording;
- clearing: `aclrs` (step + SHIFT + one detent), `aclr` (CLEAR + one detent)
  and `aclrstep` (step + CLEAR);
- the CLEAR role key arrives here;
- the toasts `8 lanes used` and `Model` / `cannot be locked`.

**Display.** The lock sink writes only `lock_shown`, never `value[]`. Lock
pages show locked values in engine units over dim bases [O14], and the grid's
lock dots come from `fm1_seq_get_page`.

**Movy traces.** Fetch `automation.ts` and `automation.mjs` at `9190e79` into
`reference/`, which is git-ignored. Transcribe their command traces, such as
the `aset 0 0 4 N 1` family, as golden traces, keeping Movy's MIT notice.

**Files:**
- engines/include/fm1_seq_host.h, engines/seq/seq_host.c.
- sim/web/src/fm1_seq_ui.c, fm1_seq_view.c, fm1_app.c.
- sim/web/test/fm1_sim_render.c, scenarios.json, seq/.
- Tests: tests/test_seq_ui.py, tests/fixtures/seq-ui/ (the Movy-derived traces,
  with their notice), tests/test_sim_web.py.
- sim/web/www/fm1.wasm and fm1.wasm.json.
- Docs: sim/web/README.md, manual chapter 07, CHANGELOG.md.

**Tests and exit:**
- **Round trip.** `value7(lock_value(v)) == v` for every v in 0..127, on every
  FLOAT and ENUM parameter of every registered engine.
- **Knob sync.** After a turn and after a stop's D6 revert, the value the
  engine received equals `value[]`, bit for bit.
- **Traces.**
  - The Movy-derived traces are reproduced exactly when `reference/` is
    present, and skipped otherwise.
  - FM-1 traces cover multi-step edits, the NOLOCK refusal and the 8-lane cap.
  - Every trace passes two-step parity.
- **On aeon:** parity 22/22, adding a panel-driven FLOAT lock scenario with
  base sync and a D6 stop.
- **Screens:** lock pages at 0, 1 and 8 lanes, the longest labels, and lock
  dots on every step; 0 faults; at most 96 boxes.
- **CI:** green.

**Depends on:** S4 and S7a. S7b should merge first if possible, so that the
lock scenarios are recorded once, with SMOOTH. O14 (the knob grid, display
units, and whether effect-slot parameters can be locked).

**Size:** M.

**As built (2026-10-02, branch `feature/2026-10-02@seq-locks`, on S6's
reviewed head; S7b has not merged, so the lock scenario is recorded
without SMOOTH).** Everything stays behind the lab switch (O24); with it
off the panel is unchanged, the knobs keep their 1/100 detent and send
nothing even where a script made a lane [verified: tests/test_seq_ui.py].
The owner's answers (O14, Sophie's Pad, the multi-sound target) are in §8.
Where the build differs from, or adds to, the plan above [verified:
tests/test_seq_ui.py, tests/test_seq_render.py, engines/test/seq_host_test.c,
`fm1-sim-render --screens` and `--lock-check`]:
- **The lock sound.** A lock targets the sound unit the focused track
  routes to (§3.16), whichever sound is current: the lock pages show that
  sound's pages, and the first line names it (`Lock step 5 S2`) when it is
  not the title's. A track on MIDI out or an empty sound has no lock pages.
- **The lock pages.** With one step held, SELECT walks Step 1/2, Step 2/2,
  then the lock sound's pages (`1/3 Lock T1`; page memory as O21). The
  first turn of a parameter without a lane sends `alabel t lane
  synth:<Name>`, `abase t lane v7` and `aset t lane step v 1`. The base is
  `abase`, not the plan's `abaseq`: Movy's assignLane sends `abase`
  [verified: reference/movy `src/seq/automation.ts` at `9190e79`]; the
  app first puts the knob on the 7-bit grid (`fm1_seq_lock_value(p,
  fm1_seq_value7(p, value))`, at most half a step: Timbre's 0.5 becomes
  0.5039, a bipolar 0 becomes 0.0079), so the base it sends is what the
  knob shows and nothing jumps. Later turns move the step's lock (or, with
  none, the lane's base) a 7-bit step a detent, one entry for a list
  (O14). A NOLOCK parameter is not hidden but named with `no lock`, and a
  turn says `Model` / `cannot be locked` and sends nothing, as Movy's
  SP-35 (a held step that cannot lock a parameter says so rather than
  edit the sound under the hand). A ninth lane says `8 lanes used`. With
  several steps held the lock pages show and edit the sound, with no lock.
- **The knob grid and the bases with no step held.** A knob on a
  parameter with a lane (any track's, on that sound) moves one 7-bit step
  a detent, and every such lane takes the knob's value as its base at
  once, quietly (`abaseq`, only where it differs), in HOME and in SEQ mode
  alike, and for ALGORITHM's model. The plan's `abase` per detent and
  `abaseq` after 600 ms idle became this: Movy syncs the base quietly on
  the knob's touch release, which the FM-1's knobs lack, and a base sent
  at once is never stale, so no note step snaps the parameter back (R8).
  After a turn and after a stop's D6 revert the engine has heard exactly
  `value[]` [verified: `lock-knob-sync`, `seq-panel-locks`, %.9g text].
- **Live takes.** Recording while playing, a knob on the lock sound (the
  current one) writes `aset t lane step v` at the playing step: four
  arguments, no quiet flag, as Movy's live take (its test's
  `/^aset 0 0 7 \d+$/`); the core reads a missing flag as 0, heard. A
  missing lane is made first. Detents add up until 600 ms pass without
  one (Movy's knob release), then the next starts from the knob's value
  again; the knob itself never moves, and the hint line shows the take's
  value in gold.
- **Clearing.** Step + SHIFT + one detent on a lock page: `aclrs`, where
  the step has a lock on that lane (`<Name>` / `lock cleared`); SHIFT's
  release then clears no notes. Steps held + CLEAR (D#4): `aclrstep` for
  each held step with a lock (`Locks cleared`); Movy sends it for every
  held step, but every edit verb empties Capture, so the FM-1 spares the
  steps with none. CLEAR held + a detent (on a lock page, or on the
  current sound's page when it is the lock sound): `aclr` of that
  parameter's lane (`<Name>` / `lane cleared`), and the hint line says so
  while CLEAR is held. CLEAR's tap and CLEAR + a step do nothing until S9.
  CLEAR is lit while the track has a lane.
- **Labels.** A lane label is one token of a script or a set, so a
  parameter name with a space is written with `_` (`synth:Env_Pitch`); the
  bridge's name match takes `_` for a space, in any case
  (`fm1_seq_lane_param`, `fm1_seq_lane_label_for`). Before, such a label
  named nothing. Track page 2 shows it with the space.
- **The display.** A locked parameter's value in its own units in gold,
  as a narrow gold bar inside the dim bar of its base; a lane without a
  lock on the step shows its base, dim; a parameter with no lane the
  knob's value, dim. A dot after the bar marks a lane, filled where the
  step has a lock. The grid and the Step pages' strip mark a step with a
  lock with a gold dot in its corner (`fm1_seq_get_page`'s lock mask).
  The sink still writes only `lock_shown`, never `value[]`.
- **Effect slots** are not lockable (O14): FX mode's knobs are unchanged.
- **The round trip** holds on all 78 parameters of the 14 registered
  engines and effects: 20,242 checks, `fm1-sim-render --lock-check`
  [verified]. No list has more than 128 entries (Six-Op's 96 patches are
  the most), so every entry has a 7-bit value.
- **Movy-derived traces.** Six golden traces (`lock-movy-*`, with Movy's
  MIT notice) reproduce the assertions of Movy's
  `browser-test/logic/automation.mjs` (and `automation.ts`, `edit-ops.ts`)
  at `9190e79` for the same gestures: the lane's `alabel 0 0 synth:<param>`
  and `abase 0 0 64`, the quiet `aset 0 0 4 N 1`, the release that toggles
  nothing, the live take's `aset 0 0 7 N` with no `abase` after it, the
  NOLOCK refusal, `aclrs 0 0 4`, `aclr` with no `clipdel`, and `aclrstep`.
  With Movy under `reference/movy` the test also finds each assertion,
  word for word, in its source; without it that part is skipped. Three
  more (`lock-knob-sync`, `lock-eight-lanes`, `lock-several-held`) cover
  the knob sync, the 8-lane cap and several steps held. All nine replay
  through `fm1-render` byte for byte.
- **Sophie's Pad** is lockable (the owner, below), with no flag. A Pad
  lock moves the edit focus at its step, so the locks after it in lane
  order there, and later, edit the pad it names [verified:
  tests/test_seq_render.py]. Of 708 renders by the merge base's and this
  branch's `fm1-render` (the 34 oracle scripts and the repository's other
  verb scripts on all six sound engines, and a lane on every parameter of
  every sound engine), all are byte-identical but eight: the lanes on
  Macro's and Macro Heavy's Env Pitch, Env Timbre and Env Morph, labelled
  with `_`, and the new trace that labels them, which reach their
  parameter now [verified 2026-10-02, a script over both builds]. A Pad
  lane alone renders as before: Pad only moves the focus.
- **Screens.** 54 new, 1,163 in all, 0 faults, at most 96 boxes; every
  screen the sweep saved at the merge base is byte-identical here
  [verified: `fm1-sim-render --screens` at both, compared]. They cover the
  lock pages with no lane, one, and eight, every sound engine's pages
  locked at both ends and laned without a lock, the toasts, SHIFT on a
  lock page, CLEAR held, several steps held, another sound's lock pages,
  a lock on every grid step, a live take's hint and a spaced label on
  Track page 2. The UI state is 600 B of its 1,024 (552 at S6); `fm1_app_t`
  is 4,881,488 B natively.
- **On aeon** [verified: `www/fm1.wasm.json` and the screenshot report,
  2026-10-02]: parity 33 of 33, adding `seq-panel-locks` (locks on two
  steps from the lock pages, the base sync while playing, a stop's D6
  revert, PLAY again); identical to js and musl in all 33, to glibc in 30
  (the two Sophie scenarios and Fold's 1 LSB, as before); imports none.
  The headless Chromium checks pass with the switch on and off, the
  help's new "Locks (lab)" entry shown only with it. The module is
  526,033 B (514,688 with S6).
- **Sanitizers:** the simulator's tests (test_sim_web, test_sim_seq,
  test_seq_ui, test_sim_multi) under ASan and UBSan, and the engine and
  sequencer tests against a sanitized engines build, report nothing
  [verified, clang, macOS].

### S9. Session, scenes and song, the Loop view, COPY and CLEAR

**Goal.** The rest of Movy's surface: clips launched on the bar, scenes, the
song, loop windows, and copying or clearing steps and slots.

**Scope:**

**Session** (§3.11). A SEQ tap inside SEQ switches to it, and holding SEQ
peeks at it.
- White keys 1–8 launch on the bar, or stop the track from an empty slot.
- White keys 9–16 focus a track.
- LOOP + white key launches scenes [O20].

**Loop view** (LOOP held): `loop`, `dbl`, and LOOP + SELECT to resize.

**COPY:** `cpy`, `pst` and `cpyclr`; on slots, `clipcopy` and `clippaste`.

**CLEAR:**
- with a step: `del` + `aclrstep`;
- with a slot: `clipdelat`;
- a tap deletes the clip, with a confirm until undo exists [O15].

**Screens and LEDs** as in §3.13 and §4.

**Files:**
- sim/web/src/fm1_seq_ui.c, fm1_seq_view.c, fm1_app.c.
- sim/web/test/fm1_sim_render.c, scenarios.json, seq/.
- Tests: tests/test_seq_ui.py, tests/fixtures/seq-ui/, tests/test_sim_web.py.
- sim/web/www/fm1.wasm and fm1.wasm.json.
- Docs: sim/web/README.md, manual chapter 07, CHANGELOG.md.

**Tests and exit:**
- **Traces** for launch, scene, song, loop, copy, paste and clear, each with
  two-step parity. Browsing traces assert that nothing empties Capture as a
  side effect.
- **Event logs.** The oracle fixtures 12-launch-session and 13-scenes-song,
  played through the app path, equal `fm1-render`.
- **On aeon:** parity 23/23.
- **Screens:** Session at 1, 4 and 8 tracks with every cell state, the Loop
  view, and the confirm popup; 0 faults; the floor is raised.
- **CI:** green.

**Depends on:** S6. O15 (the CLEAR tap), O20 (the scene keys).

**Size:** M.

### S10. Browser extras: sets in the browser, MIDI realtime in, shortcuts, docs

**Goal.** Finish the web simulator around the C layer, and close the
documentation.

**Scope:**

**Sets** [O17].
- `fm1w_seq_export` writes into the text buffer and returns the full length;
  JavaScript refuses a length above `fm1w_text_cap()`.
- `fm1w_seq_import(len)` reads from the text buffer. It sends the note-offs of
  §2.3 first and applies the default-route rule after. A refused import keeps
  the current set.
- app.js saves to localStorage inside try/catch, offers a `.movy1` download,
  and loads from a file picker or a drop. It restores the last set on start,
  unless storage is empty or blocked.
- SAVE in SEQ mode exports and shows a toast.
- Nothing is written to any device.

**MIDI in.**
- `onMidi` forwards F8, FA, FB and FC as a worklet `rt` message to
  `fm1w_seq_realtime` [O18].
- Jitter of up to one 128-frame quantum is noted for the clock-follow EMA.
- MIDI out is built only if O18 says so. If it is, it is opt-in, off by
  default, and refuses any port named FM-1 or M-VAVE (the one rule).

**Worklet.** Sequencer info is still batched once per quantum, and nothing is
posted per event.

**Page.**
- The status line already shows `Chain RAM` from `fm1w_ram` against a
  hard-coded 387924, `FM1_APP_RAM_BUDGET` [verified: app.js 351–352,
  fm1_app.h 73]. Relabel it as engines plus sequencer RAM, and keep or export
  the budget constant; `fm1w_ram` needs no change.
- Keyboard shortcuts per O19, the help text, and a role legend on the page.
- The legend must not move app.js's geometry constants (`FN_X`, `WHITE_STEPS`,
  the knob positions, `FN_ROWS`, `WHITE_X0`, `WHITE_PITCH`). The manual's
  `test_figures_match_the_simulator` parses them [verified: main
  tests/test_manual.py]. A PR that moves them also updates
  `tools/manual/figures.py`.

**Docs.**
- sim/web/README.md: "What works", and the Limits lines that say the
  sequencer is not wired [verified: README 237–238].
- docs/13 §4 and §9 (M4 done for the simulator).
- HANDOFF.md, the manual, CHANGELOG.md.

**Files:**
- Source: sim/web/src/fm1_web.c, fm1_app.c; sim/web/mk/sim.mk.
- Page and module: sim/web/www/app.js, worklet.js, index.html, style.css,
  fm1.wasm, fm1.wasm.json.
- Harness and parity: sim/web/test/scenarios.json (a `"seq"` set field),
  parity.mjs, fm1_sim_render.c, screenshot.mjs, readme-screenshots.mjs.
- Tests: tests/test_sim_web.py.
- Docs: sim/web/README.md, docs/13, HANDOFF.md, the manual, assets/screenshots/,
  CHANGELOG.md.

**Tests and exit:**
- **Sets, natively.** Import then export through the app path reproduces each
  fixture's `.out.movy1` for its declared tracks, under test_seq_oracle's
  `set_lines` rule.
- **Export size.** A set with every pool full and maximum-width fields exports
  in full into the 65,536 B buffer.
- **On aeon:**
  - parity 24/24, with one scenario starting from a `movy1` set: `fm1-render
    --seq`, and the module imports it;
  - screenshot.mjs checks that:
    - a save round-trips through a reload;
    - the page loads with localStorage blocked;
    - PLAY lights LED 39;
    - a pattern entered on the panel gives rms > 0.01;
    - no MIDI permission is requested on load;
    - every existing check still passes.
- **CI:** green, including the manual's figure test.

**Depends on:** S6, and S8 for lanes. O17 (persistence), O18 (MIDI in and
out), O19 (shortcuts).

**Size:** M.

## 6. Testing

### 6.1 Parity: native against WebAssembly

`parity.mjs` renders each scenario four ways [verified: sim/web/README.md,
"Parity"]:
- **glibc:** native `fm1-render`;
- **js:** `fm1-render.js` under Node;
- **musl:** static `fm1-render` built on Alpine;
- **app:** `fm1.wasm`, driven by `renderApp`.

It compares int16 samples. It also compares the screen against `fm1-sim-render
--screen`, with the RAM figure masked.

| Check | Pass |
| --- | --- |
| app against js | exact |
| app against musl | exact |
| app against glibc | within 1 LSB, unless `libm_sensitive` |
| Screen | 0 pixels different |
| Imports | none called |

**Counts by stage.** Today there are 12 scenarios: 12 identical to js and
musl, and 10 identical to glibc, the other two being the `libm_sensitive`
Sophie scenarios [verified: fm1.wasm.json]. The counts below assume the stages
merge in numeric order and no click scenario; S7a and S7b add no scenario, and
a click adds one if O11 approves it.

| Stage | Scenarios |
| --- | --- |
| S2 | 17 |
| S3 | 18 |
| S4 | 19 |
| S5 | 20 |
| S6 | 21 (built: 32, with the click's scenario, after S5 and multi-sound) |
| S7a | 21, records unchanged |
| S7b | 21, records re-baselined |
| S8 | 22 (built: 33, after S6's 32) |
| S9 | 23 |
| S10 | 24 |

**Sequencer scenarios add three rules:**
- Commands apply at the same 64-frame block starts on every leg, after
  controls and notes.
- `renderApp` fails on `fm1w_seq_dropped() > 0`.
- parity.mjs asserts that its applied (block, line) list equals the one
  `fm1-sim-render` logged, before comparing audio.

### 6.2 The oracle through the app

From S2, tests/test_sim_seq.py plays all 34 oracle scripts through
`fm1-sim-render`, in default mode with test-sine, plus six with macro chosen
from the 29 at 44,118 Hz. Event logs and WAVs must equal `fm1-render --frames
64`. Movy-exact checking stays where it is: `fm1-seq` and `fm1-render` against
the Movy oracle (test_seq_oracle, test_movy_oracle_fixtures), in compat mode.
The app is checked in default mode against `fm1-render`.

### 6.3 Gesture traces and two-step parity

Each gesture trace is a `.panel` file and its golden `.verbs`. "Two-step
parity" means that a run through the panel and a replay of what it logged give
the same audio:

1. `fm1-sim-render --cmd P.verbs --panel X.panel --log-cmds C.verbs --out A.wav`
   (plus the engine arguments).
2. `fm1-render --cmd C.verbs --frames 64 $(cat C.args) --out B.wav`.
3. A and B must be byte-identical.

**What `--log-cmds` writes:**
- **A header,** `#! rate=R block=64 tracks=N end=TOTAL`, so both runs have the
  same length. `end` is already a header key [verified: seq_script.h 7–9].
  Without it, `fm1-sim-render` defaults to 2 s while `fm1-render --cmd` ends
  one block after the last command.
- **Script lines** verbatim, at the block they applied.
- **UI commands** formatted by `fm1_seq_cmd_format`. A round-trip test
  asserts `parse(format(c)) == c` for every verb.
- **A sidecar, C.args,** with the run's `--engine`, `--param` and `--fx`
  arguments.
  - Panel actions that call the engine directly are logged there as
    `--param-at` and `--bend`, with `%.9g` values: knob turns on the sound
    pages, ALGORITHM and OCT.
  - From S5, key notes are logged there as `--note T:KEY:VEL:DUR`.
  - Note times sit mid-block: t = (pos − 32) / rate and t + dur = (pos2 −
    32) / rate. A time exactly on a block boundary can round past it by one
    ulp, because events apply where t ≤ pos / rate.

**Exclusions.** Traces that use PRESETS are left out of two-step parity,
because `fm1-render` cannot replay a sound change.

**Where files live:**
- Traces used by parity.mjs live under `sim/web/test/seq/`, because that is
  what build-on-aeon.sh copies.
- pytest-only traces may live in `tests/fixtures/seq-ui/`.
- parity.mjs gives the render legs `--cmd C.verbs` and the sidecar, and gives
  the native screen reference `--panel`. They no longer share one argument
  list.

### 6.4 Layout of new screens

`fm1-sim-render --screens DIR` runs every screen through
`fm1_tft_check_layout` with a 4 px gap. It must print 0 faults, and every new
screen state of §4 joins the sweep in the stage that draws it. Truncated text,
overlaps, anything off screen and a box log over 96 are faults. The floor
(`screens >= 280`, test_sim_web.py 107) rises with each stage.

### 6.5 The staleness gate

`tools/source_hash.py` hashes two groups [verified: sim/web/tools/source_hash.py
24–26]:
- `engines/`, less builds, dotfiles and `*.md`;
- `SIM_INPUTS`: `sim/web/src`, `sim/web/mk`, `build.sh`, `test/parity.mjs`,
  `test/scenarios.json`, `test/fm1_sim_render.c` and `www/fm1-wasm.mjs`.

`test_committed_wasm_matches_its_build_record` fails in CI only when the sim
hash is stale. A stale engines hash is a warning [verified: test_sim_web.py
256–261].

Two gaps open once the module links the sequencer:
1. **Parity inputs.** Scripts under `sim/web/test/seq/` are not hashed, so
   editing a `.verbs` file would leave a stale parity record.
2. **Sequencer code.** From S2, `fm1.wasm` links `engines/seq`, so an
   engines-only change (for example a new deviation row landed alone) would
   ship a module that behaves differently, with only a warning.

**The fix, in S2:** add `sim/web/test/seq`, `engines/seq` and
`engines/include/fm1_seq*.h` to `SIM_INPUTS`. More generally, any stage that
changes code linked into `fm1.wasm` rebuilds it in the same PR, even where CI
would only warn: S7a and S7b change every engine.

The rebuild is `FM1_SIM_HOST=user@host sim/web/build-on-aeon.sh`. It needs a
Docker host and is never run in CI.

### 6.6 Checks that run only on aeon

screenshot.mjs and readme-screenshots.mjs run in the Playwright container
through build-on-aeon.sh, not in CI. They assert `lit_keys === 3` after a
chord and `fx_led` [verified: screenshot.mjs 355, 376, 428]. That is one
reason O6 proposes that sequencer notes do not light HOME's key LEDs. Each
stage reports these checks in its PR's test results.

### 6.7 CI

CI has 7 checks [verified: `gh pr checks 21`]:
- **tests** on ubuntu and macOS, including test_sim_web with `CI=true`;
- **engines, 32-bit,** which runs test_sim_web with `-m32 -msse2
  -mfpmath=sse`;
- **engines, ASan + UBSan,** which runs test_sim_web too;
- the dongle firmware;
- two AL-255 jobs.

Since PR #24, the Pages workflow also builds the site and the manual, in
strict mode, for PRs that touch `engines/`, `sim/web/`, `manual/` or
`tools/manual/`. It deploys on main.

## 7. Risks

| Risk | Mitigation |
| --- | --- |
| **The staleness gate.** S2–S10 each change hashed inputs, and CI fails until the module is rebuilt on aeon and committed in the same PR. Every one of those stages needs aeon and Docker. S1 needs neither | Rebuild in every such PR; the S2 gate additions (§6.5) |
| **S1 changes audio subtly:** event order, the frame clamp, skipping unmapped locks, or log timing | The sha256 baseline of S1 over 34 scripts, engines by rate, both modes and both block sizes; event-log checks in CI against `fm1-seq`; no sim change in the same PR |
| **Parity drift.** App-only logic on the audio path: a velocity clamp, another event cap, another block size, or another rate rounding | The sink calls the engine as render.cc does; 64-frame blocks; `lrintf(rate)` on both hosts; `seq_dropped == 0` on both. The measured worst is 7 events per block over the oracle scripts and 193 in seq_bench's burst, against a 256-event buffer |
| **Event room.** A burst of UI commands between quanta can leave `fm1_seq_advance` under 72 events of room; note-offs are dropped and notes hang | The event-room rule and the pending record (§2.3); S1's and S2's tests |
| **Default routes.** An app that routes track 0 unconditionally breaks parity whenever `--route` is used, and leaves an imported set silent | One rule, as render.cc's, applied after create, reset and import; parity routes with verbs only |
| **Hung notes** on reset, import or an engine change | The note-offs of §2.3 |
| **Two-step parity pitfalls:** run length, engine-direct controls, note times on block edges, shared argument lists | §6.3's header, sidecar, mid-block times and split arguments |
| **A third script parser** in parity.mjs drifts from seq_script.c | The applied (block, line) list is compared before audio |
| **Compat never runs through the app.** Its pools (about 300 KB at 8 tracks [reported]) do not fit, and compat events sit at each block's start | Movy-exact checks stay on `fm1-seq` and `fm1-render`; the app is checked in default mode |
| **libm.** Capture's stopped tempo search uses `logf`, so near-tied candidates can differ between glibc and musl or wasm | Such scenarios are `libm_sensitive`, which exempts glibc only |
| **SMOOTH and block invariance** (S7b). A ramp stepped per render call breaks identity at host blocks of 1, 7 and 64, and with it split-render parity. SMOOTH also changes existing audio, such as the `--param-at` scenarios | Native-rate ramps keyed to absolute samples; S7b separate from the silent S7a; re-baselined records listed |
| **Knob and lock values disagree.** The knob's 1/100 grid differs from `LockValue`'s v/127, so the engine plays one value and the screen shows another | The 7-bit snap and `abaseq` on lane creation (§3.9) |
| **Memory at 8 tracks:** 648 B spare. Any core growth (an undo ring, new per-track fields) forces 4 tracks, a smaller Capture ring or a smaller event buffer | Tests pin the arena and the budget sum; O3 |
| **Layout.** 96 boxes, the 4 px gap, 2× text and ASCII only. Grids drawn as one box per cell overflow. The knob strip and two toasts did not fit as first drawn | One graphic box per grid; O23; two-line toasts; the longest strings in the sweep |
| **Capture empties by design.** `watch`, `clipsel`, `launch` and every edit verb clear it, so navigation that sends one as a side effect loses a take | The browsing gestures send none; S6 and S9 traces assert it |
| **One shared sound unit.** Engine-routed tracks share 12 voices and one patch, so locks collide, and one track's note-off can end another's note of the same pitch. render.cc behaves the same | O10, answered: up to four sound units with the lab switch (§3.16), in both hosts; tracks on one sound still share it |
| **No undo.** CLEAR taps, CLEAR + step and clip deletes cannot be undone until M4/D14, or O16 | The O15 confirm |
| **Browser checks run only on aeon.** Changing HOME's key LEDs or FX behaviour breaks `lit_keys` and `fx_led` silently in CI | O6; each PR reports the aeon run |
| **Unmeasured performance.** The sequencer's cost in WebAssembly inside the AudioWorklet, and on phones, is unknown. Native worst blocks are at most 87 µs on an M1 Max, against 1,451 µs per block [verified: engines/seq.md 260–265] | S2 records Node's `seq_ns_per_block`; the page getter keeps redraws linear |
| **Movy UI facts are [reported]:** LEN units, the Shift+step list, page memory and the automation traces | Re-read at `9190e79` into `reference/` before pinning tests in S4 and S8 |
| **Merge friction.** Every stage touches CHANGELOG.md, the sim/web README figures (screens, scenarios, the `fm1_app_t` size), `fm1.wasm.json` and the manual. PRs #22 and #23 change HANDOFF.md, README.md and DEVELOPERS.md | Expect rebases; S7a developed in parallel serialises its merge |
| **Everything merged goes public.** Since PR #24, Pages deploys `sim/web/www` from main on every push that touches `engines/` or `sim/web/` [verified: main .github/workflows/pages.yml] | O24; each UI stage updates manual chapter 07 in the same PR |
| **The one rule.** Web MIDI output could reach an FM-1 plugged into the same computer | No MIDI out unless O18 opts in, with a port-name guard; sets stay in browser storage or files |

## 8. Owner decisions

The proposed default is what the plan builds if the owner agrees. "Blocks" is
the first stage that needs the answer. O22–O24 come from the completeness
critic. The judge's precondition, merging PR #21, is done and was dropped.

| # | Decision | Proposed default | Blocks |
| --- | --- | --- | --- |
| O1 | Where the sequencer roles go | Black keys in the SEQ Track view (§3.4), with the printed buttons keeping their meaning; labelled on the 240×240 screen and, from S10, in a legend on the page. The alternative is to repurpose ENV, LFO, EDIT, SAVE and ARP inside SEQ mode | S4 |
| O2 | Which button is SHIFT | SEL outside FX mode; FX mode keeps the slot grab | S4 |
| O3 | Track count. 8 tracks: at most 36,216 of 36,864 B, 648 B spare, and docs/13's 12 KiB undo ring does not fit. 4 tracks: at most 22,392 B, 14,472 B spare | 8, as a constant in S2. The simulator should use the count the firmware will, so this is final by S6 | S2 (constant), S6 (final) |
| O4 | A demo pattern on the browser's start chain, and what it holds | Yes: a 1-bar, 16-step figure on track 0, never applied in tests or parity | S3 |
| O5 | What a step tap writes when nothing has been played, and whether OCT shifts the remembered pitches | The last chord played, each pitch with its velocity, else note 60 at velocity 100. OCT does not shift the remembered pitches | S4 |
| O6 | Whether sequencer notes light the key LEDs outside SEQ mode | No, so HOME's LEDs and the `lit_keys` check keep their meaning | S3 |
| O7 | The Capture gesture, and the REC LED while Capture holds notes | SHIFT + REC (alternatives: a dedicated button, a REC double-tap); REC blinks slowly while `capture_pending` > 0 | S5 |
| O8 | Step record | REC held while stopped, as in Movy, with ▶ moving the record head; it may be deferred without holding up S5. Open: whether the head should advance by itself on key release (a change from Movy), and whether the mode latches | S5 |
| O9 | A new deviation row: Capture committed while playing clamps a last-half-step note, as D4 does, instead of growing the clip by a bar | Adopt it in default mode; compat keeps Movy's behaviour. It can land alone in `engines/`; after S2 that needs a rebuild of the module | S5 |
| O10 | Several tracks on one sound, and the browser's default routes | (a) every engine-routed track shares unit 0, as render.cc does. The alternatives: (b) more sound units, each a 512 KiB arena in the simulator and FM-1 RAM; (c) MIDI-routed tracks only. In the browser, tracks 1–7 are routed to the engine by `route` verbs on the start chain; `fm1-render`'s default stays track 0 only. **Answered 2026-10-02: (b), up to four sound units (§3.16)** | S6 |
| O11 | A metronome click | A deterministic, libm-free click voice in the shared bridge, sounding only while `metro` is on, so both hosts have it. The alternative is no click audio | S6 |
| O12 | Track solo | Muting the other tracks in the UI, rather than a new core verb | S6 |
| O13 | Engine API v2 | Approve v2 now. **Flags:** the table in S7a, covering all eight ENUM parameters, with SMOOTH for continuous parameters. **Label format:** keep `synth:<Name>` in `movy1` and resolve it to a uid when a lane is labelled or imported. **SMOOTH:** a 2–3 ms ramp, engine-side, keyed to absolute native samples, with docs/12 §5.3 rewritten to match | S7a (the ramp time: S7b) |
| O14 | The lock UX | A knob detent on a laned parameter moves one 7-bit step (v/127 for FLOAT, the bins for ENUM), with the value snapped to that grid. Locked values are shown in engine units, not 0–127. Effect-slot parameters are not lockable yet | S8 |
| O15 | Movy's CLEAR tap (delete the clip) before undo exists | Ask for a confirm, rather than disabling it | S9 |
| O16 | Undo in the simulator | Wait for D14's per-clip ring (M4), so that the simulator matches the firmware. The alternative is memcpy snapshots of the pointer-free instance (31,880 B each, simulator only) | not staged |
| O17 | Browser persistence | Both localStorage and a `.movy1` download and upload; SAVE in SEQ mode exports. Nothing ever goes to a device | S10 |
| O18 | Web MIDI | Realtime input (F8, FA, FB, FC) drives the external clock. No MIDI out; if the owner wants it, it is opt-in, off by default, and refuses any port named FM-1 or M-VAVE. Clock in/out settings go on Set page 2, since GLO is full at 8 lines | S10 |
| O19 | Computer-keyboard shortcuts | Space for PLAY/STOP when no button has focus. Shift for SEL in SEQ mode. Digit1–8 and C, V, B, N, M, Comma, Period, Slash for the 16 steps (§3.15) | S3 (Space), S4 (the rest) |
| O20 | Session scenes | White keys 1–8 with LOOP held, rather than Movy's odd keys 1, 3, … 15 | S9 |
| O21 | What SELECT does | Moves between pages, as stock does and the simulator does today, rather than docs/13 §4's list opening on the first SELECT detent | S4 |
| O22 | Pitches on a held step: how a pitch is added or removed, and how that coexists with SHIFT + N shortcuts and `aclrs` | With a step held, SHIFT turns the white keys into pitches in the current octave, each press sending `addp`. SHIFT + N shortcuts apply only with no step held. Step + SHIFT + one knob detent stays `aclrs`. The black keys keep their roles, so SHIFT + ◀ ▶ still nudges by one tick, and sharps come from MIDI IN or a chord played in KEYS mode first. Open: how a pitch is removed. docs/13 §4 is updated to match | S4 |
| O23 | Text in the Track view's knob strip | (b): four bars only, with the turned knob's name and value on the hint line in 2× text. The alternatives are (a) 1× text with short names, or (c) a 2 × 2 layout | S3 |
| O24 | Whether intermediate stages ship on the public page, now that every merge to main deploys | Ship each stage, with manual chapter 07 saying what works, rather than hiding SEQ mode behind a flag until S5 or S6. A flag would add a code path to test | S3 |

**Answered by the owner, 2026-10-02** (multi-sound; recorded when it
landed):
- **O10, replaced:** (b), more sound units: up to 4 at once, each
  sequencer track routed to one of them; each sound unit has its own
  insert effect slots (2 per sound, §3.16 says why), and the existing two
  effect slots stay as the master bus after the sounds are mixed, each
  sound with its own level into the mix. A RAM meter against the FM-1's
  budget (FM1_APP_RAM_BUDGET, 387,924 B, and the app's other fixed costs,
  with per-instance sizes at 32 bits) refuses any engine or effect choice
  that would not fit, with a clear popup, shown where the RAM figure was.
  Multi-sound is behind the lab switch; with it off there is one sound and
  today's behaviour. The panel UI follows §3's conventions and O1/O2:
  §3.16 has its gesture table.

**Answered by the owner, 2026-10-02** (for S3; recorded when S3 landed):
- **O1, O2:** as proposed. In SEQ mode the black keys carry the
  sequencer's roles and SEL is SHIFT; every printed button keeps its
  meaning (S4).
- **O3:** 8 tracks.
- **O4:** yes, the demo pattern: one bar of 16 steps on track 0 (track 1 to
  the user), applied only by the browser's start chain, never in tests or
  parity runs.
- **O6:** no, sequencer notes do not light the key LEDs outside SEQ mode.
- **O19:** Space is PLAY/STOP when no button has focus (S3); the step keys
  come in S4.
- **O23:** option (b), four bars in the knob strip and the turned knob's
  name and value on the hint line in 2x text.
- **O22, changed** (for S4): pitches on a held step are only added: with a
  step held, SHIFT turns the white keys into pitches in the current
  octave, each press adding one (`addp`). There is no per-pitch removal: to
  remove pitches the user clears the whole step with SHIFT, tapped while
  the step is held (`del`). SHIFT + N shortcuts apply only with no step
  held, and step + SHIFT + one knob detent stays `aclrs` (S8). §3.5 has the
  final gesture table; docs/13 §4 records the answer.
- **O1, O2, O5, O19, O21** (for S4): as proposed.
- **O24, changed:** hide the sequencer from the public page until it is
  usable, that is until step entry and recording (S5, S6). S3 adds a
  runtime lab switch instead: the page turns it on for an address with
  `?lab` or `#lab` and passes it to the module (`fm1w_set_lab`). Off, SEQ,
  PLAY/STOP and REC behave as before S3, Space does nothing, no sequencer
  UI is reachable and the demo pattern is not loaded; the parity runs,
  gesture traces and the layout sweep cover the lab-on screens and keep
  the lab-off ones. The switch is documented in sim/web/README.md, not in
  the user manual, and the manual's chapter 07 stays as it is while the
  features are hidden. S3's scope items written for the public page
  therefore hold with the switch on only, or wait for the stage that
  removes it: the two buttons dropping their popup, the stub-button sweep
  dropping SEQ and PLAY/STOP (its saved popup stays `popup-button-12`),
  chapter 07 and `manual.toml`'s roles.

**Answered by the owner, 2026-10-02** (for S8; recorded when S8 was built):
- **O14:** as proposed. A knob detent on a laned parameter moves one 7-bit
  step (v/127 of the range for FLOAT, the bins for ENUM), snapped to that
  grid; locked values are shown in the parameter's own units, not 0-127;
  effect-slot parameters are not lockable yet.
- **Lock flags:** Sophie's Pad is lockable: its NOLOCK flag goes (S7a had
  kept it, as the edit focus); Sophie's Model and Filter Type stay LATCH
  and MOD, and Macro's LPG as built. Nothing else changes
  (tests/fixtures/param-uids.json differs in Pad's flags only).
- **Multi-sound:** a lock targets the sound unit its track routes to.

**Answered by the owner, 2026-10-02** (for S6; recorded when S6 was built):
- **O3:** 8 tracks, final.
- **O10, changed again:** tracks route to the up-to-four sound units of
  multi-sound (`fm1_app_unit_*`), each track's route shown and set on its
  Track page, or MIDI out on a channel as `fm1_seq` allows. The browser's
  default: track 1 on Sound 1, and the others on Sound 1 too until the
  user changes them (`fm1_app_seq_start_routes`, S6 as built).
- **O11:** yes, the metronome's click: a deterministic, libm-free click
  voice in the shared bridge, sounding only while `metro` is on, so both
  hosts have it.
- **O12:** no track solo for now: mute only.
- **The S2 open issue:** the 256-event buffer was one short of seq_bench's
  burst; raised to 272, which fits the 36,864 B budget at 8 tracks.

**Answered by the owner, 2026-10-02** (for S5; recorded when S5 was built):
- **O7:** as proposed. Capture is SHIFT + REC (SHIFT is SEL in SEQ mode),
  and REC blinks slowly while played notes wait for Capture
  (`capture_pending` > 0).
- **O8:** step record is REC held while the sequencer is stopped, as in
  Movy, with the right black-key role (▶, A#3) moving the record head; the
  head advances by itself when the keys are let go, and the mode does not
  latch (REC is held). The owner asked for the advance as a change from
  Movy, documented as a deviation with compat keeping Movy's way; Movy's
  `step-rec.ts` at `9190e79` turned out to advance on the last release
  already [verified], so no deviation was needed (S5's as-built notes).
- **O9, changed:** Capture committed while playing grows the clip by a bar
  exactly as Movy does; the proposed clamp is not made.
- **Also:** notes played on the keys are logged, so gesture traces that
  press keys replay byte for byte (S3's open issue).
