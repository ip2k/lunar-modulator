# 13 — Replicating Movy's sequencer on the FM-1: port plan

The owner's request (2026-10-01): the open FM-1 firmware should replicate
[schwung-movy](https://github.com/DimaDake/schwung-movy)'s sequencer as
closely as possible. This builds on docs/06 (why Movy itself cannot run on
the FM-1) and docs/12 (sequencer feasibility), and changes docs/12's
recommendations where Movy and Elektron differ.

Three lanes inventoried Movy (engine, UI, host integration), then a
verification pass re-read the load-bearing code. Everything was read through
the GitHub API and raw files at one commit, **`9190e79`** (main, 2026-10-01
19:34 UTC). All three lanes pinned that same commit. Nothing was cloned,
built or run, and nothing was sent to any MIDI or USB device. Bare file
names below are in `engine/crates/seq-core/src/`; `movy-dsp/` is under
`engine/crates/`, and `src/` is the TypeScript UI.

**What the verification pass re-read:**

| Lane claim | Result |
| --- | --- |
| The grid is 96 PPQN, with 24 ticks per 1/16 step and 16 steps per bar, in 4/4 only. The clock is an integer accumulator from 20.00 to 300.00 BPM | **confirmed**: `lib.rs` 13–20; `clock.rs` 21–22, 45–65 |
| 16 tracks × 8 clips of 1–256 steps. Per clip: at most 512 notes, 1,024 locks and 1,024 trig rows, in `Vec`s with no global cap. 8 lanes per track, whose base values are shared by the track's clips. Values are 7-bit | **confirmed**: `track.rs` 6–7, 49–59; `clip.rs` 9–12, 35–47, 82–87 |
| The latch runs on step entry: the step's lock, else the base if any note is anchored there, else the carried value. A CC goes out only on a change. It is sent on muted tracks and regardless of conditions | **confirmed**: `engine.rs` 2263–2285; the mute check covers only the note loop (2123–2126 against 2248–2253) |
| Order per clip tick: note-offs, note-ons, advance and wrap, then the entered step's CCs. So a lock leads its step's notes by one clip tick, except on the first step after Play or a launch, where it follows them | **confirmed**: `engine.rs` 2100–2253; the carry is reset at 588 and 2013 |
| Stop sends no base values and keeps `playing_slot` | **confirmed**: `engine.rs` 960–981 |
| A:B is `((cycle−1) mod B)+1 == A`, XOR invert, with the cycle counted per track. A roll is taken only when the condition passes and prob < 100. The RNG is one xorshift64*, seeded once. A chord shares one decision | **confirmed**: `clip.rs` 72–78; `engine.rs` 287, 393–398, 590, 2015, 2174–2186, 2244 |
| Events carry no sample offset: a whole 128-frame block's events go out at its start. Locks reach the sound as CC 102+lane | **confirmed**: `engine.rs` 15–32; `movy-dsp/src/lib.rs` 640–713 (CC at 677–695), 780–792 |
| Persistence is the `movy1` text format, without transport, cycle or RNG. Undo keeps 64 snapshots in at most 512 KiB | **confirmed**: `persist.rs` 1–107; `undo.rs` 14–16 |
| Holding one step and turning a knob locks at once; 300 ms only promotes the display. With two or more steps held, the turn edits the patch | **confirmed**: `src/seq/step-edit.ts` 49, 103–126, 219–225; `automation.ts` 251–256. This **refutes** docs/12 §5.6 |
| Held-step locks are quiet; live-record locks audition. Movy has no external MIDI | **confirmed**: `automation.ts` 283–291; `engine.rs` 2319–2327. `src/app/globals.ts` 21 installs only `onMidiMessageInternal`, and `movy-dsp/src/lib.rs` has no `midi_send_external` call |
| Suspected defects (§3.3) | **the code paths are confirmed**; their consequences are [inferred], and no Movy test pins them |
| UI lane: the A:B count is per clip and reset on stop; the RNG is not deterministic | **refuted**. The count is per track (`track.rs` 60–62) and is reset at start and launch. The RNG is deterministic from engine creation |
| docs/06 gives v0.31.0 as `5627d51`; docs/12 gives v0.34.0 as `9190e79` | **refuted**: the tags are `675054f` (v0.31.0) and `7539028` (v0.34.0). `9190e79` is 299 commits past v0.34.0, and `module.json` still says 0.34.0 |

## 1. Short answer

| Question | Answer |
| --- | --- |
| Can the FM-1 replicate it? | **Yes, the sequencer, closely** [inferred]. `seq-core` is about 5,100 lines of dependency-free Rust logic [verified: `lib.rs` 1–2, `Cargo.toml`], and nothing in it needs Linux. A C99 rewrite can reproduce its event stream tick for tick. The Move's surface and Schwung's chains cannot be copied. |
| How closely? | **Engine:** tick-identical in a `compat` mode used for tests. The shipped default adds sample offsets and fixes behaviours that look like bugs (§3.3). **UI:** every core gesture gets an FM-1 equivalent. Touch gestures and the pad grid are substituted (§4). |
| What does it cost? | [inferred] **RAM:** about 72 KiB for Movy's whole 16 × 8 grid, with pooled storage: 18.9 % of the 387,924 B stock gap (§5). **CPU:** under 1 % typical. A fire-tick index makes a scan cost the notes due, not the notes stored, but that is not a bound: every note can fall due on one tick, and Movy's core runs up to 255 clip steps per tick (D8 clamps that to 4). The desktop worst case is in engines/seq.md; stage B measures pi32v2. **Code:** about 4–6k lines of C for the core and 3–5k for the FM-1 UI. |
| What has to change? | Fixed pools instead of `Vec`s; binary undo; direct `set_param` lanes instead of CC 102+lane, which is Movy's own plan D1 [reported: `plans/2026-09-30-drum-modules-schwung-pages.md` line 76]; frame offsets; tracks routed to the engine or to USB-MIDI. **For this goal, docs/12's Elektron revert rule and its MCL lock store are superseded** by Movy's latch and sparse locks. |
| What gates it? | Nothing on the desktop. On the device, the one rule (CLAUDE.md, docs/07). A differential test needs the owner's approval to build Movy's code (§7). |

## 2. Movy in one page

Movy (MIT, "Copyright (c) 2026 megadake") is a Schwung tool for the Ableton
Move: a TypeScript UI in QuickJS, and a Rust plugin (`seq-core` +
`movy-dsp`) in Move's audio callback. The two halves talk through one param
slot carrying `cmd` text-verb batches, plus a status poll at about 24 Hz
[verified: `command.rs` 1–53; reported: comment in `automation.ts` 6–8].
Module 0.34.0, ENGINE_VERSION 0.81.0 [verified: `movy-dsp/src/lib.rs` 129].
Its README calls it an early prototype [reported].

| Group | Features [verified in `seq-core` and `src/seq/` unless marked] |
| --- | --- |
| **Core, port first** | Tap a step to toggle it on release; a hold of 300 ms or more opens the step. Hold one step and turn a knob for a quiet lock; lanes are assigned lazily, 8 per track, and a lock on an empty step latches. Step page: VEL, LEN, PROB (100–10 %), COND (36 A:B pairs up to 8), INV (`step-page-vm.ts` 11–31). Hold A and press B for length. Loop view and window, 1–256 steps. Swing 50–80 %. Per-clip non-destructive quantise. Live record with a one-bar count-in, overdub and first-take growth. Step record. Undo by gesture. MIDI clock out |
| **Nice-to-have** | 8 clips per track, scenes and song mode. Clip page: SCALE speed 1/8–4X (`clip-scale.ts` 6–8), length, transpose ±36, quantise. Double loop. Copy, paste and duplicate. Mute and solo. Drum lanes with pad mute and solo. Metronome. Capture (retroactive record with tempo detection) |
| **Move-specific** | 32-pad layouts and colours; capacitive knob touch; the RGB step-LED language; 128×64 OLED pages; Schwung chains, LFOs and the MIX page; the Move transport link and MovePlay inject; Link tempo; backups; background mode |
| **Not in Movy** | Retrigs, slides, FILL/PRE/NEI/1ST and sound locks. Micro-timing beyond nudges of ±24 ticks. An arpeggiator (Schwung's MIDI FX supply one). External MIDI |

## 3. Semantics to reproduce exactly

### 3.1 Data model and limits [verified: `track.rs`, `clip.rs`; `engine.rs` 54–59, 156–164, 1174–1183]

| Object | Fields and limits |
| --- | --- |
| Set | `bpm_x100` 2000–30000. `swing_pct` 50–80. Song: a list of scene indices. `default_quant` 0–100, stamped into every empty clip after each command |
| Track ×16 | Slots: `active_clip`, `playing_slot`, `queued_slot`, `pending_stop`, `pending_select`. `pos_tick`, absolute within the clip. `muted`, `pad_mutes` (an ordered set) and `pad_solo`. 8 lanes, each with `assigned`, `base` (0–127) and a target. Runtime only: `last_auto_step`, `auto_cur[8]` (−1 means none), `cycle` (from 1) and `scale_acc` |
| Clip ×8 per track | Exists iff `length_steps` > 0. `length_steps` runs from 1 to 256 − `loop_start_steps`. `scale_num`/`scale_den` 1–255, `transpose` −36..36, `quant` 0–100. Notes, locks and trig rows are each kept in insertion order |
| Note | `tick` (absolute start), `gate` ≥ 1, `pitch` (stored without transpose), `vel` 1–127, `step` (a stored anchor), `suppress`, `fired` |
| Lock and trig row | A lock is (lane 0–7, step 0–255, val 0–127), upserted. A trig row is (step, pitch or whole step) → prob 0–100, A and B ≥ 1 (the command clamps them to 1–64), invert. A row that returns to the defaults is `swap_remove`d. Over a cap, new items are dropped silently (`clip.rs` 179, 203, 368, 401, 641) |

### 3.2 Playback rules (the C port and its tests pin these) [verified: `engine.rs` unless named]

| # | Rule | Lines |
| --- | --- | --- |
| R1 | **Clock.** Each block adds `frames·bpm_x100·96` to `accum`. While `accum ≥ sr·6000`, subtract that and fire one master tick. A tempo change keeps `accum`; Play zeroes it and the tick count | `clock.rs` 49–65 |
| R2 | **Each master tick:** a bar-boundary Start after an external-clock revert; F8 if `master_tick % 4 == 0`; then `service_tick`. Start goes out on the first block that plays, Stop on the falling edge | 1963–1991 |
| R3 | **`service_tick`:** (a) a click if `tick % 96 == 0` and the count-in or the metronome is running, accented when `tick % 384 == 0`. (b) On the bar: queued slots launch (`pos` = loop start, pass flags cleared, carry reset, `cycle = 1`; `scale_acc` is kept), then pending stops, selections and a pending take resolve, then `song_bar()`. (c) NoteOff for the gates of unserviced tracks. (d) `master_tick++`. (e) The count-in counts down. (f) Unless counting in, for tracks 0–15: `scale_acc += num`, and while it is ≥ `den`, subtract `den` and run `step_tick` | 1994–2095 |
| R4 | **`step_tick`:** (a) count this track's gates down; at 0, send NoteOff and `swap_remove` the gate, which fixes the order of the offs. (b) Unless muted, scan the notes in insertion order: a note fires when `fire == pos` and it is neither `suppress` nor `fired`, and `fired` is set before the decision. (c) `pos++`. At the loop end a first take grows by a bar; otherwise `pos = loop_start`, the pass flags clear and `cycle++`. (d) Expire recording tails. (e) If `pos/24` changed, run R8 | 2100–2255 |
| R5 | **Fire tick:** `anchor = step·24` and `dev = tick − anchor`. Then `fire = max(0, anchor + dev − (dev·quant ± 50)/100 + swing)`, where the division truncates and ±50 takes `dev`'s sign. If `fire ≥ loop_end`, subtract `length` once | 2151–2166 |
| R6 | **Swing:** none at 50 % or below. With `n = step·den`, a step swings when `n % num == 0` and `n/num` is odd, by `(pct−50)·(num·24/den)/60` ticks: 12 ticks at 80 % and 1X. Parity uses the absolute step | 351–362 |
| R7 | **Trig decision.** The governing row is (step, pitch), else (step, whole step), else the defaults. A note plays if `cond(A, B, inv, cycle)` holds and either prob ≥ 100 or `roll < prob`. `roll` is xorshift64*: `x^=x>>12; x^=x<<25; x^=x>>27`, then `((x·0x2545F4914F6CDD1D)>>33) % 100`, seeded `0x9E3779B97F4A7C15` and never reseeded. The decision is cached per (step, lane key) within one `step_tick`. The emitted pitch is `clamp(pitch + transpose)`, with transpose 0 on drum tracks, and pad mute and solo test that pitch | 287, 393–398, 2174–2219; `clip.rs` 72–78, 159–168 |
| R8 | **Automation**, for each assigned lane 0–7: `v` = the step's lock, else `base` if any note is anchored at the step (played or not), else `auto_cur` (`base` if nothing has been sent). A CC goes out only if `v != auto_cur`. The carry survives the wrap, and Play, a bar launch and Stop reset it. `Clip::effective_at` is the steady-state oracle | 2263–2285; `clip.rs` 212–236 |
| R9 | **Lock edits:** `aset` writes to the active clip, quiet while a step is held. `abase` sends its CC at once if the lane is assigned; `abaseq` is silent. A lane with no lock left in any clip is freed | 434, 2291–2368 |
| R10 | **Transport:** Play always restarts: the song from entry 0 if there is one, else each track's active clip, if it exists. Stop ends recording, commits held notes, resets the song cursor and the carry, and flushes every gate | 579–629, 960–981 |
| R11 | **Launch:** quantised to the master bar. A launch while stopped starts the transport. An empty slot stops its track. A scene is a slot column, lasting as long as its longest clip rounded up to whole bars. The song arms the next scene a bar early, and an empty scene ends it | 657–944 |
| R12 | **Recording:** a 384-tick count-in. A first take queues to the bar; an overdub punches in at once. Pre-roll is at most 12 ticks. `gate = clamp(laps·span + pos − start, 1, limit)`. The anchor is the nearest **swung** step, with ties going to the later one. A note finished on the pass it was played is suppressed until the wrap | 1101–1164, 1620–1803 |
| R13 | **Edits:** a gate is capped at the next same-pitch note and at the clip end. A nudge stays within ±24 ticks of the anchor. No note can go in a sub-bar loop's hidden tail. Step copy carries notes and locks but not trig rows; clip copy carries everything | `clip.rs` 303–676; 407–570 |
| R14 | **`movy1`:** the lines are `bpm swing link sg tk pm ps au cl cp lk tg`, with notes as `tick:gate:pitch:vel:step;…`. Unknown lines are ignored, loading clamps values, and the saved loop window wins | `persist.rs` 1–355 |

### 3.3 Deliberate deviations (a `compat` flag turns each off for tests)

The owner's answer (§10, 1) is to fix everything that can be fixed. D1–D7
come from the plan; D8–D13 from running Movy as an oracle and from the
review of the C core (2026-10-01): each is a Movy behaviour that the code,
the oracle or both show [verified], with no Movy test pinning it.

| # | Movy at `9190e79` | FM-1 default | Why |
| --- | --- | --- | --- |
| D1 | Events at the block start (128 frames) | Each tick at its own frame: offset `k−1`, where `k = ceil((thr − accum)/(bpm_x100·96))` [inferred]. Following an external clock, the frame at which the follow target reaches the tick, as Movy fed one frame at a time would fire it [verified: oracle fixtures 23, 24] | Sample-accurate timing with the same tick counts |
| D2 | After Play or a launch, the first step's locks come after its note-ons | Emit them before the scan when `last_auto_step == −1` | LATCH engines read at note-on. Movy's plan Phase 2 wants a test pinning the same [reported: the plan, lines 214–218] |
| D3 | After a count-in, step 0 plays at master tick 383, while the bar falls at 384 [inferred from 2062–2094] | Start on 384 | Keeps clips aligned with later launches |
| D4 | An overdub note in the last half-step anchors to the loop-end step and grows the clip by a bar [inferred from 377–390; `clip.rs` 342–353, 400–409]. So does a first take's, which is meant to grow, except in a 16-bar clip, which cannot: its note stays on step 256 | Clamp it to the last step, as Capture does (1429–1431); a first take's too once its clip is 16 bars long | The clip silently doubles, or a note sits where only R5's fold-back plays it |
| D5 | With `loop_start` > 0, nudge's `clamp(lo, hi)` can get lo > hi, which panics in Rust, and length caps collapse to 1 tick, because the code uses `length_ticks` [verified: `clip.rs` 544–614, 665–676]. Capture into a clip with notes clamps anchors to `len_steps − 1`, before such a window (1429–1431) [verified] | Use `loop_end_ticks`, and the window's last step | A crash and data loss. In compat the C core reproduces the panic: the edit stops at that note and the rest of its batch is lost, as movy-dsp's `catch_unwind` leaves it [verified: oracle fixture 22] |
| D6 | Stop leaves lanes at their last lock (960–981); so do a track stopping at the bar and a lane released while it holds a lock's value (`aclr`, `aclrs`, `aclrstep`, `clipdel` …) | Send `base` for every lane whose `auto_cur` differs: at Stop, at a track's stop on the bar (after its note-offs) and when a lane is released | Matches docs/12 §5.5 rule 4. **The owner's call**. Otherwise a parameter stays at a value no lock asks for until the knob moves |
| D7 | Unbounded gate and item lists | 64 gates, freeing the oldest; edits refused, with a toast, when a pool is full. An edit that adds several items (a chord, `addp`, `asetr`, Double Loop, step copy and paste, a trig range) is applied whole or not at all | There is no heap |
| D8 | Clip speed 1/255X–255X in the core (`command.rs` `cscl`, `persist.rs` `cp`), though the UI offers 1/8X–4X (`clip-scale.ts` 6–8) [reported for the UI] | Clamp to 1/8X–4X | At 255X one master tick runs 255 step_ticks per track: 2,817 events and 1.35 ms in one block on the desktop [verified: review, 2026-10-01] |
| D9 | A bar launch or stop sends the outgoing clip's look-ahead lock one clip tick before the bar, a value for a step that never plays, then the new clip's (oracle fixture 05) | No look-ahead when a launch or stop already queued for the track falls before its next step | Two values in two ticks |
| D10 | A live-recorded or captured note anchors to the nearest *swung* step but keeps the played tick; playback adds the swing again (R5), so an off-beat replays late by the swing at quantise below 100 (oracle fixture 14: played at 172, replayed at 178) | Store the tick less its anchor's swing | Quantise 0 replays what was played |
| D11 | R5's "subtract the length once" folds a note anchored up to one window length past the loop end back into the window (after `clen` or `loop` shrinks a clip under its notes); a note on an offset window's first step that fires early never plays, though at step 0 it is clamped to tick 0 (oracle fixture 10) | A note anchored outside the window is silent; one inside never fires before the loop start | The LED (its step) and the sound disagree |
| D12 | Play while playing restarts at tick 0 but sends neither Stop nor Start, so a MIDI clock follower is left out of phase (oracle fixture 06) | Stop at the restart, Start on the next block | Followers restart with us |
| D13 | `aclr` unassigns a lane but keeps its base and carried value, which a lane labelled again resumes from (2342–2351) | Reset both, as `free_unused_lanes` does | A new lane starts clean |
| (D14) | `undo_restore` wraps each playhead with `pos %= length_ticks` (2531–2536), below an offset window (oracle fixture 18) | Wrap within the window, when undo is ported (M4) | The D5 bug again |

Kept as Movy has them: the single free-running RNG (tests reset it through
a hook); a launch from stopped restarting every track whose `playing_slot`
survived the stop (579–596, 678–681; §10); Play while playing restarts (D12
only adds the Stop and Start). A look-ahead lock for a launch queued after it
was sent (D9 can only drop what it sees queued).

## 4. Mapping to the FM-1 [inferred unless marked]

**Inputs.** 27 keys, F3–G5: 16 naturals and 11 accidentals (docs/12 §5.6).
About 14 LED buttons (docs/01: K30–K41). Their printed names come from the
M-VAVE manual's panel drawing [reported; sim/web/README.md, The panel]: OCT−,
OCT+, FX, SEL, ENV, LFO, EDIT, GLO, HOME, SAVE, ARP, SEQ, PLAY/STOP and REC.
So PLAY and REC below are printed buttons (PLAY/STOP, REC); SHIFT, CLEAR,
COPY, LOOP, SESSION, MUTE and UNDO have none and stay *roles* to assign.
KNOB1–4 are encoders without touch; SELECT and ALGORITHM navigate, PRESETS
picks presets and MASTER is volume [reported: docs/11 §2]. A 240×240 TFT.
**GRID** mode makes the white keys steps (or bars, or slots); **KEYS** mode
plays pitches, as stock does.

| Movy gesture [verified in `src/seq/`] | FM-1 gesture |
| --- | --- |
| Tap a step to toggle it on release; a hold of 300 ms or more opens it | The same, on a white key |
| Hold one step and turn a knob: an immediate, quiet lock | Hold a white key and turn KNOB1–4 |
| Step page VEL/LEN/PROB/COND/INV on knobs 1–5 | Page 1 VEL/LEN/PROB/COND, page 2 INV, switched with SELECT |
| Hold step A and press B: length | Hold white A and press white B |
| Hold a step and press a pad: that pitch toggles in the step | Pitches are only added (owner decision O22, 2026-10-02; docs/15 §3.5): hold the step and SHIFT, and each white key adds its pitch in the current octave (`addp`); a note at MIDI IN adds any pitch. A tap of SHIFT alone while the step is held clears its notes (`del`) |
| A tap writes the held pads, else the remembered set, else the last pitch | The same order; keys played in KEYS mode, or MIDI IN notes, are the "pads" |
| With steps held: the volume encoder sets velocity, ◀ ▶ nudge ±2 ticks (±1 with Shift), +/− transpose | The VEL knob; two accidentals as ◀ ▶ (which also page bars); two keys or buttons for −/+ |
| Touch-tap a knob during a hold: clears that lock | Hold the step and SHIFT, and turn that knob |
| Step held + Clear: clears its locks. Clear + step: clears notes and locks. Clear + touch a knob: clears the lane. A Clear tap deletes the clip | The same with CLEAR, where "touch" becomes one detent with CLEAR held |
| Copy held: the source, then the destinations | The same with COPY |
| Loop view: bars on the steps; two bars set a range; a double-tap sets 1 bar; Loop + jog resizes | LOOP: white keys are bars 1–16, and LOOP + SELECT resizes |
| Rec tap: live, with a count-in. Rec held while stopped: step record, the head moving on when the last pad comes up [verified: `step-rec.ts`] | The same with REC (owner decision O8, 2026-10-02; docs/15 S5): in step record the white keys are pitches, ▶ (A#3) leaves a rest or ties held keys, ◀ (F#3) steps back, and SHIFT + a white key moves the head |
| Capture: keep what was just played; stopped, a tempo picker on the jog | SHIFT + REC (O7); SELECT or KNOB1 picks the tempo, any other press keeps it |
| Shift + step shortcuts: 3 Clip, 5/7/9 Set, 6 metronome, 15 double, 16 quantise | SHIFT + the white key with the same number, labelled on the TFT |
| Session + step selects one of 16 tracks; clip pads launch; Loop held + steps 1, 3, …, 15 launch scenes 1–8 | SESSION held + a white key selects a track. In SESSION, keys 1–8 launch the focused track's slots, and LOOP + the odd keys launch scenes |
| Mute + step (a map of all 16 tracks); add Shift to solo | MUTE (+SHIFT) + a white key |
| Undo, Shift+Undo. A knob gesture closes on touch release or after 600 ms idle [verified: `src/undo/group.ts` 43] | UNDO, SHIFT+UNDO; a gesture closes after 600 ms idle |
| Touch shows a value; touch opens a list | Values are always on screen. A list opens on the first SELECT detent and commits on a press, or after 1 s idle |

**Dropped:** pad layouts (the FM-1 is a fixed piano); LFO assign and the
MIX and chain pages, which belong on the engine and FX pages; Link and
MovePlay, which USB-MIDI clock replaces; drum lanes, until a drum engine
exists.

**Key LEDs** may be on/off only (74HC595, docs/12 §8), so Movy's eight
colour states become: record head fast blink, playhead inverted, note on,
under the held note's length slow blink, outside the loop off.

**The TFT** carries the colour; stage M4 lays it out and checks it for
overlap. A 20 px header (track, slot, bar, tempo, PLAY/REC/EXT); a 4 × 16
step grid showing 4 bars (filled for notes, a corner dot for a lock, a tick
for a condition or probability, an outline outside the loop); 4 knob cells,
locked values in an accent colour and a dot on each parameter with a lane;
a bottom strip for the loop overview or a toast. SESSION shows Movy's whole
grid at once: 16 × 8 cells of 14 × 22 px.

## 5. Memory and CPU

**Movy at its caps** [inferred sizes]:

| | Note | Lock | Trig row | One clip at caps | 128 clips |
| --- | --- | --- | --- | --- | --- |
| Rust | 16 B | 4 B | 8 B | 20,480 B | 2.5 MiB |
| packed C | 10 B, with a cached fire tick | 4 B | 6 B | 15,360 B | 1.9 MiB |

Even packed, that is five times the SRAM gap. The `movy1` text of a full set
approaches 1 MB, and the undo ring alone is 512 KiB.

**FM-1 limits.** Keep the grid and the per-clip caps, but allocate from
global pools (D7):

| Item | Movy | FM-1 | Bytes |
| --- | --- | --- | --- |
| Tracks | 16 | 16 × ~144 B, including the playing clip's has-notes and has-locks bitmaps | 2,304 |
| Clip headers | 16 × 8 | 128 + 2 clipboard clips, × 20 B (pool offsets and counts, window, scale, transpose, quant) | 2,600 |
| Notes | 512 per clip, no total | a pool of 3,072 × 10 B | 30,720 |
| Locks | 1,024 per clip | a pool of 3,072 × 4 B | 12,288 |
| Trig rows | 1,024 per clip | a pool of 512 × 6 B | 3,072 |
| Fire-tick index | — | 3,072 × u16, sorted per clip | 6,144 |
| Gates, song, state | unbounded | 64 × 4 B; 64 entries; clock, RNG, record and external-clock state | 832 |
| Undo | 64 × ≤ 512 KiB of text | a ring of binary per-clip snapshots | 12,288 |
| Capture | 512 events | 256 × 12 B (on by default, §10) | 3,072 |
| **Total** | | | **73,320 B ≈ 71.6 KiB, 18.9 % of 387,924 B** |

3,072 notes is, for example, 32 clips of 96 notes; a one-track build with
1,024-note pools needs about 23 KiB. That leaves about 314 KB for an engine
and effects (30–200 KB), the display strips (2 × 11.5 KB, docs/01) and the
system. A typical clip snapshot is under 1 KB, so undo holds dozens of
gestures; a worst-case clip (15 KB) does not fit (§10).

**CPU** [inferred], against 348,160 cycles per 64-frame block at 240 MHz:

- **At most one master tick per block.** A tick is 229.8 samples at 120 BPM
  and 91.9 at 300 BPM; a 64-frame block adds at most 184,320,000 against a
  threshold of 264,708,000. A u32 accumulator holds for blocks up to 1,399
  frames.
- **Movy's note scan cannot run as written.** It recomputes every note's
  fire tick (about 60 cycles, three divisions) on every clip tick: with
  3,072 notes at 4X and 300 BPM (1,920 clip ticks/s), about 147 % of the
  core. **Cached fire ticks** (recomputed on edits and on quant, swing,
  scale or window changes) cut a check to about 6 cycles, still 14.7 % on
  average and 21 % of a tick's block. **A per-clip index** sorted by (fire,
  insertion order) makes the cost proportional to the notes due, keeping
  Movy's order and RNG consumption.
- **Typical:** 4 tracks of 128 notes at 120 BPM cost about 0.25 % with
  cached fire ticks, even without the index. Automation is one bit test per
  lane on an empty step.
- **Worst case** [verified on the desktop, 2026-10-01]: the index bounds a
  scan by the notes due, not by a constant. 8 tracks of 12-note chords on
  every step with 8 locked lanes at 300 BPM and 4X (D8) cost 4.1–4.4 µs per
  64-frame block on average and 81–83 µs in the worst block on an M1 Max,
  with at most 193 events in one block; Movy's 255X ran 2,817 events in one
  block. engines/seq.md lists what stage B must time on pi32v2
  (tools/seq_bench.py writes the scripts).

## 6. Architecture of the port

`fm1_seq` is a C99 core in `engines/`. It has no heap: the host passes one
block of memory, sized by `fm1_seq_size()`. Its output is a pure function of
state, commands and frames, and the same code builds for the desktop, the
dev board and the FM-1. `limits.compat` selects Movy's exact behaviour
(§3.3).

```c
typedef struct { uint32_t tick; uint16_t frame; uint8_t kind, track, a, b; } fm1_seq_ev_t;
  /* NOTE_ON(pitch,vel) NOTE_OFF(pitch) LOCK(lane,val) CLICK(accent) START STOP CLOCK;
     tick: the master tick being serviced */
size_t     fm1_seq_size(const fm1_seq_limits_t *lim);
fm1_seq_t *fm1_seq_create(void *mem, const fm1_seq_limits_t *lim, uint32_t sample_rate);
uint32_t   fm1_seq_advance(fm1_seq_t *s, uint32_t frames, fm1_seq_ev_t *out, uint32_t cap);
uint32_t   fm1_seq_apply(fm1_seq_t *s, const fm1_seq_cmd_t *c, fm1_seq_ev_t *out, uint32_t cap);
void       fm1_seq_note_in(fm1_seq_t *s, uint16_t frame, uint8_t track, uint8_t pitch, uint8_t vel);
uint32_t   fm1_seq_realtime_in(fm1_seq_t *s, uint16_t frame, uint8_t status,   /* F8 FA FB FC */
                               fm1_seq_ev_t *out, uint32_t cap);
size_t     fm1_seq_export_movy1(const fm1_seq_t *s, char *buf, size_t cap);
int        fm1_seq_import_movy1(fm1_seq_t *s, const char *txt, size_t len);
```

As built (`engines/include/fm1_seq.h`). The host's side of a block, from
commands into the event buffer through the split renders below, is one
shared bridge, `fm1_seq_host.h` (engines/seq.md, Host contract):
`fm1-render` runs it now, and the virtual FM-1 and the firmware are to run
the same code.

- **Commands.** `fm1_seq_cmd_t` carries Movy's verbs as typed records (tog,
  ltog, aset with its quiet flag, econd, launch, song …). The UI task queues
  them in a single-producer ring, and the audio task applies them at the
  block start, as Movy applies `cmd` between blocks. A text-verb parser is
  built for tests only.
- **Notes.** A track routed to the engine gets note-on and note-off at
  `frame` through split renders (docs/12 §5.4). Other tracks go to USB-MIDI
  channel *t*, the shape of Movy's path for a track without a chain,
  `midi_send_internal(0x90|track)` [verified: `movy-dsp/src/lib.rs` 647–650].
- **Locks.** LOCK maps `lane_target[lane]` to an engine `set_param`, an FX
  slot or a CC (MIDI tracks default to CC 102+lane). CLOCK, START and STOP
  go to USB-MIDI, CLICK to the host's click voice. At one frame the order is
  offs, locks, ons (D2). The host mirrors every value it sets, so `abase`
  needs no getter.
- **Clock in.** Port Movy's follow logic: 24→96 PPQN by ×4, an EMA
  (α 0.25) over intervals of 20–999 BPM, a join at the next bar, and
  staleness after 0.5 s [verified: `engine.rs` 1805–1958]. Then add F2/FB,
  which Movy lacks.

**`fm1_engine.h`, API v2.** `fm1_param_t` gains a stable `uint16_t uid`
(the lock target) and `flags`: LATCH, SMOOTH, NOLOCK (docs/12 §5.3). ENUM
locks use Movy's planned bins, `⌊v·n/128⌋` (plan D14 [reported]).
`FM1_KIND_MIDI_FX` gets `process(self, in, n, out, cap, frames)` on event
arrays, one slot per track, mirroring Schwung's MIDI FX → synth chain.
Nothing else changes: sample offsets come from split renders.

As built in docs/15 stage S7a [verified: engines/README.md, "Parameters";
engines/seq.md, "Host contract"]: the uid and flags, plus MOD and INPUT for
docs/16, a unit and an abbreviation. Lane labels stay `synth:<Name>` text
and resolve to uids in the host bridge when a lane is labelled or a set
imported; a lock on a NOLOCK parameter is refused and counted; no other
render changed. SMOOTH's ramp came with S7b: a change ramps over 2.5 ms
inside the engine, keyed to its native samples (engines/README.md,
"SMOOTH"). `FM1_KIND_MIDI_FX` came on 2026-10-06, in engine API v3: a
`fm1_midi_fx_t` around an `fm1_engine_t` with `process(self, in, n_in, ctx,
out, cap)`, the context holding the block's tick frames, the tempo, the
transport and the project key; a chain of up to four in front of each sound
unit (the owner's four per track), on the host bridge, which both hosts
share; the arpeggiator the first [verified: engines/README.md, "MIDI
effects"; `tests/test_engine_midi_fx.py`]. On 2026-10-06 the context gained
the first tick's place from Start while the sequencer plays (`tick_pos`, so
an effect can step on the beat), notes their origin (the keys or a track),
the transport a STOP that takes back what the sequencer gave, and the
sequencer the project key, kept in the set as an FM-1 `key` line (owner
decisions after PR #69) [verified: engines/seq.md, "The project key";
`tests/test_engine_midi_fx.py`].

**Persistence under the one rule.** Until docs/07's dump and restore, sets
live only in desktop and dev-board builds. Then RAM, with `movy1` text export
and import over SysEx: ASCII needs no 7-bit packing, and a full FM-1 pool is
about 90 KB [inferred], sent in chunks. Flash last: a binary image of about
50 KB (13 sectors of 4 KB) as A/B copies with a CRC (docs/12 §5.7); whether
2 × 13 sectors fit beside FM-1+VA-sized code is open.

## 7. Testing

**Movy material, read-only at `9190e79`:**

- **Rust tests to transcribe.** `seq-core` has 307 `#[test]`s: engine 167,
  command 51, clip 43, persist 20, capture 10, undo 9, clock 5, track 2
  [verified by count]. The most useful: clock exactness (`clock.rs`
  73–144); automation CC sequences and the oracle (`engine.rs` 3616–3700);
  quantise and swing fire ticks (5199–5288); scale (3251–3346); conditions
  and chords (3465–3502); record and count-in (4429–5197); launch, scenes
  and song (5297–5751); `effective_at` (`clip.rs` 1150–1202); `movy1` round
  trips. Skip the Move link and inject tests.
- **Set fixtures** [verified present]:
  `browser-test/fixtures/old-sets/movy-chains/seq-state.json` (a real
  device set with off-grid notes, `cp … 100` and A:B rows),
  `old-sets/schwung-tracks/seq-state.json`, and
  `scripts/fixtures/device-set/seq-state.json` (with an `au` lane line).
  Fetch them by sha into the git-ignored `reference/`. Any committed copy
  keeps the MIT notice.
- **Gesture traces.** `browser-test/logic/automation.mjs` expects commands
  like `aset 0 0 4 N 1`: golden traces for the FM-1 gesture layer.
- **Worked condition vectors**, for example 1:2 → 1, 3, 5 and 4:7 → 4, 11,
  18 [reported]: `docs/superpowers/specs/2026-06-18-automation-latch-design.md`
  and `2026-06-21-step-parameter-page-design.md`.

**Desktop tests in pytest, through `fm1-render`.**

- **New flags:** `--pattern FILE` takes a `movy1` set (docs/12's step lines
  stay a convenience); `--cmd FILE` takes timed verbs
  (`@frame tog 0 4 60 100`); `--compat`; `--log-events FILE.jsonl` records
  master tick, clip tick, frame, kind and arguments.
- **Assertions:** tick-identical events at host blocks of 1, 7, 64 and 128;
  every event at its D1 frame; a lock ahead of its note at the same frame,
  the first step included; no drift over 10,000 steps; no `malloc` in the
  link map; a `sizeof` table within §5.

**A differential test against `seq-core` is worth asking for.**

- **What it takes.** Installing Rust, building `seq-core` (no dependencies
  [verified: `Cargo.toml`]) and a ~150-line driver that replays a verb script
  at a fixed block size and prints the OutEvents with their ticks. That is
  building and running third-party MIT code, so it needs the owner's
  approval. A container on aeon would isolate it.
- **What it buys.** Random scripts would cover the record, song, scale and
  edit interactions that the 307 tests do not pin. Compare at tick
  resolution in `--compat`, with both RNGs at the creation seed. Every
  difference must map to a §3.3 row.

## 8. Licence and credit [verified LICENSE; consequences inferred, not legal advice]

- **Notice.** A C rewrite of `seq-core` is a derived work. Keep "Copyright
  (c) 2026 megadake" and the MIT permission notice in
  `engines/third_party/movy/LICENSE`. Each derived file's header names its
  source path and `9190e79`. This repository is MIT too, and the owner's
  personal, non-commercial policy (2026-10-01) does not change this.
- **Naming.** The UI says "Sequencer", not "Movy", unless megadake agrees.
  No Ableton, Move or Elektron product names; clips, scenes, song and
  capture are generic words.
- **Credit**, in About and the README: "Sequencer design and logic after
  Movy by megadake (MIT), github.com/DimaDake/schwung-movy".
- **Upstream.** D3–D6 go to `notes/upstream-candidates.md` as drafts, with
  two places where the MANUAL disagrees with the code: Clip SCALE is
  playback speed, not a "musical scale" [verified: `clip-scale.ts` 1–8], and
  LINK is the third knob, not "knob 4" [verified: `main-page-constants.ts`
  11–13; MANUAL.md near line 1580]. Under the `oss-contributions` rules
  nothing is filed without the owner's sign-off.

## 9. Staged plan

| Stage | Where | Work | Exit |
| --- | --- | --- | --- |
| M0 — decisions | owner | §10, questions 1–5 | answers recorded here |
| M1 — core | desktop, `engines/` | `fm1_seq`: clock, pools, `step_tick`, automation, conditions, RNG, swing, quantise, scale, gates, record, launch, scenes, song, `movy1` I/O, a verb parser for tests, `compat` | transcribed tests pass in compat; fixtures round-trip byte-identical (apart from the envelope); tick-identical at four block sizes; no heap; within budget |
| M2 — render | desktop | `fm1-render` flags (§7), split renders, LOCK → `set_param` by uid, API v2, MIDI_FX | the §7 assertions; Macro Model refused as NOLOCK; output identical at host blocks of 1, 7 and 64. Done: split renders (docs/15 S1), API v2's uids, flags and NOLOCK refusal (S7a), SMOOTH's ramp (S7b), and MIDI_FX (2026-10-06, engine API v3: the arpeggiator in fm1-render `--mfx` and the virtual FM-1, the same at blocks of 1, 7, 64 and 448) |
| M3 — oracle | desktop, if approved | a `seq-core` driver and random scripts | no unexplained difference in 10,000 scripts |
| M4 — UI | desktop | §4's gesture state machine in pure C; TFT views rendered to PNG | `automation.mjs` traces reproduced; no overlap in the PNGs |
| B — bench | JieLi AC79 dev board | pi32v2 build, worst-case cycles per block, USB-MIDI clock in and out | the sequencer takes ≤ 2 % of any block; jitter figures |
| C — FM-1 | after docs/07's dump and restore | GRID and KEYS modes, LEDs, TFT, RAM sets, SysEx | core gestures playable; export/import round trip |
| D — FM-1 | after C | flash set partition | an A/B save survives a power cut mid-write |

docs/15 plans M4 in the virtual FM-1 as stages S1–S10, with M2's engine API v2 landing before its lock UI.

## 10. Open questions

**The owner's answers (2026-10-01):**

1. **Deviations:** fix everything we can. D1–D7 are the defaults; `compat`
   exists only for tests against Movy.
2. **Tracks:** 4–8 tracks, each with configurable routing (an engine, or
   USB-MIDI on a channel) where possible.
3. **Budget:** with fewer tracks it should be about half of §5's 72 KiB.
   Measure it: the M1 tests assert `fm1_seq_size()` for 4 and 8 tracks.
4. **Oracle:** approved. Build and run Movy's `seq-core` on aeon in
   containers, and test as much as is useful (§7, stage M3). The owner also
   asked for an FM-1 emulator, or a virtual FM-1 with its screen in a
   browser, if one exists or can be made.

5. **Capture and lock width (the owner's decisions, 2026-10-01):** lock
   values are 7-bit, as in Movy, behind `fm1_seq_val_t`, and the engine-side
   SMOOTH ramp prevents zipper noise. A per-parameter 14-bit "fine" option is
   added only if a real parameter proves too coarse. Capture (record-after)
   was first an optional limit, off by default, until the owner picked a ring
   size from the measured costs below. **The owner's choice:** 256 packed
   events of 12 bytes (3,072 B), on by default (`limits.capture = 256`),
   adjustable later. The 8-track instance is 31,880 B, 86 % of the half
   budget, and the 4-track one 18,056 B [verified: `fm1-seq --sizes`,
   tests/test_seq_core.py]. The earlier estimate of about 3 KB was low for
   the 20-byte events first built, and right for the packed ones.

**Capture's cost** [verified: `fm1-seq --sizes`; 20 B per event as first
built, 12 B packed since the owner's choice], against the half budget of
36,864 B:

| Option | Bytes | 4 tracks | 8 tracks |
| --- | --- | --- | --- |
| Off (`limits.capture = 0`) | 0 | 14,984 (41 %) | 28,808 (78 %) |
| Movy's 512 events × 20 B | 10,240 | 25,224 (68 %) | 39,048 (106 %) |
| 256 events × 20 B (about 128 notes, Movy's 8-bar window when sparse) | 5,120 | 20,104 (55 %) | 33,928 (92 %) |
| 512 × 12 B, packed | 6,144 | 21,128 (57 %) | 34,952 (95 %) |
| **256 × 12 B, packed: the default** | 3,072 | 18,056 (49 %) | 31,880 (86 %) |
| 128 × 12 B, packed (about 64 notes) | 1,536 | 16,520 (45 %) | 30,344 (82 %) |

Besides the ring: about 1.55 KB of stack while a stopped capture searches
its tempo (211 tempos in float, run inside the `cap` command), and undo,
still to come (§5 planned a 12 KiB ring), shares what is left. At 4 tracks
Movy's full Capture fits; at 8 tracks only a smaller or packed ring does.
Capture matched Movy in 2,300 oracle scripts, 237 of them stopped captures.
Packed, it still does [verified 2026-10-01: 2,300 new capture scripts, 225
of them stopped captures, through the oracle, from clang under ASan and
UBSan and from GCC 12 at 64 and 32 bits; in review, those again and the
9,500 earlier random scripts, 1,732 of them with Capture, through both the
plain and the checking build, and a test at the edge of each field's range,
each through the oracle too]. engines/seq.md gives each field's width and
its reason: the frame and master tick are offsets from two bases, the
velocity also tells a note-on from a note-off, and the cycle keeps 20 bits
and a flag. Only above 349,525 Hz at the slowest tempos, or under an
external clock averaging above about 426 BPM, would the ring drop its oldest
events early, where Movy keeps them (and, with a one-step loop at compat's
255X, keep a note Movy's stale rule drops).

**Lock resolution** [verified: the core rebuilt with `fm1_seq_val_t` as
`uint16_t` and a 14-bit maximum, no warnings]: 200 B per track (a lock grows
from 3 to 4 B, the lane bases from 8 to 16 B), so 15,784 B at 4 tracks and
30,408 B at 8 (82 %); events stay 12 B. What else widening needs: a `movy1`
extension (Movy parses lock values as `u8` and clamps them to 127), and on
USB-MIDI a CC pair or NRPN instead of CC 102+lane. Alternatives that keep
7-bit storage [inferred]: map each lane's 0–127 onto a chosen range of its
parameter (fine where it matters); smooth continuous parameters (the SMOOTH
flag, §6) to hide 128-step zipper noise; widen only ENUM-free fine-tune
lanes. The FM engine's own parameters are DX7-style, mostly 0–99
[reported: the DX7 voice format msfa reads], so 7 bits cover them; the
float parameters of the Macro and Six-Op engines are where 128 steps can be
heard [inferred].

The questions below are kept for the record; only 6 (hardware) remains open.

**For the owner:**

1. **Deviations.** Should D1–D7 be the defaults, with `compat` for tests?
   D6 (revert on stop) is audible.
2. **Tracks.** Keep Movy's 16, each routed to the engine or to USB-MIDI? The
   12-voice engine has one patch, so tracks that share it would have
   colliding locks. How many tracks may play it?
3. **Budget.** Is 72 KiB acceptable? How deep should undo be?
4. **Oracle.** May we build and run `seq-core` (§7)?
5. **Scope.** Should Capture go in? Its tempo search scores 211 BPM values
   (40–250) in `f64` [verified: `capture.rs` 150–151, 196]. Should lock
   values stay 7-bit?
6. **Hardware.** What do the 14 buttons say? Are KNOB1–4's push switches
   readable? Can the key LEDs dim? Are the keys velocity-sensitive? What is
   the scan rate? Does flash have room for sets?

**For Movy's author** (drafts, sent only with the owner's sign-off):

1. Are D3–D5 bugs?
2. Is it intended that Stop leaves lanes at their last lock?
3. Is a launch from stopped restarting tracks with a stale `playing_slot`
   what the Move does?
4. Is "after Movy" acceptable as the credit?
5. Will `movy1` change when 32 lanes and enum locks land (plan D13–D15)? If
   so, we re-pin then.