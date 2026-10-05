# 06 — schwung-movy: why it cannot be ported, and what to take from it

## 1. What Schwung and Movy are

**Schwung** (charlesvestal, MIT) is an unofficial framework for the **Ableton
Move**. It injects a shim into Move's own process, intercepts audio and
hardware MIDI, runs a "Shadow UI" in an embedded **QuickJS** engine alongside
the stock UI, and loads community modules (synths, effects, tools) as
aarch64 Linux shared objects (`dlopen`, `create()`), installed over SSH by a
desktop installer.

**Movy** (DimaDake, MIT; read at commit `5627d51`, §5a) is a Schwung *tool
module*: an Elektron-style knob UI plus a 16-track step sequencer modelled on
Move's own. It is two artifacts:

| Part | Language | Size | Runs where |
| --- | --- | --- | --- |
| `ui.js` bundle | TypeScript → JS | ~26k lines in `src/` | Schwung's QuickJS context on the Move, using C bindings like `shadow_set_param`, `move_midi_inject_to_move`, `host_read_file` |
| `dsp.so` engine | Rust (`seq-core` ~9k lines: `engine.rs`, `clip.rs`, `command.rs`, `capture.rs`, `persist.rs`; `movy-dsp` ~7k lines: chain hosting, render pool, MIDI out) | ~16k lines | aarch64-unknown-linux-gnu, cross-compiled, LTO, multi-threaded render pool |

Features (from its README/MANUAL): parameter pages for any module's hierarchy
laid out on 8 knobs with arc knobs, enum overlays, auto-detected ADSR/LFO/
filter graphics; 16 tracks in four groups; clips, session view, scenes and song
mode; live and step recording, capture with tempo detection, non-destructive
quantize, per-step velocity/length/probability/condition, automation, undo/redo,
per-track LFOs, drum layouts, transport lock with Move.

## 2. The gap

| | Ableton Move (Movy's host) | M-VAVE FM-1 |
| --- | --- | --- |
| CPU | quad-core ARM Cortex-A72, 1.5 GHz | two pi32v2 cores (custom Blackfin-like ISA) at 240 MHz, 320 MHz max; stock renders its voices on the second (docs/11 §2) |
| Memory | 2 GB RAM, 64 GB storage | 578 KB SRAM, 1 MB flash |
| OS | Linux with a full userland, SSH | FreeRTOS-derived kernel inside the vendor SDK, XIP from flash |
| Languages | anything with an aarch64 Linux target: Rust, C, JS in QuickJS | C/C++ via JieLi's closed Clang fork; **no Rust, no mainline LLVM/GCC, no JS runtime worth the RAM** |
| Host framework | Schwung shim provides audio interception, module hosting, param API, display writer | none; a custom firmware *is* the whole system |
| Display | monochrome OLED framebuffer written by the shim | 240×240 colour TFT over SPI |
| Controls | 32 velocity/pressure pads, 8 endless encoders + jog, step buttons, transport | 27 silicone keys, **8 knobs** (seven encoders and one pot, MASTER; docs/01 §3), ~14 LED buttons |
| Audio | Move's instruments plus Schwung module chains | one msfa FM engine plus effects |
| Install | copy files over SSH | re-flash the chip |

A "straight port" would mean running a JS bundle and a Rust shared library on a
microcontroller with no operating system, no Rust target and 578 KB of RAM.
There is no path for that. Even QuickJS alone would consume a large share of
the SRAM before loading a 26k-line UI.

## 3. What transfers: the design

Movy is unusually well documented (`DESIGN.md`, `MANUAL.md`, `CONVENTIONS.md`,
`CHANGELOG.md`, `plans/`), and much of it is a specification an FM-1 firmware
could implement in C:

1. **The parameter-page model.** Movy lays a module's parameter tree out
   as pages of eight knobs with typed cells (arc knob, enum list, fader,
   switch, envelope graphic, filter curve). The FM-1 has eight knobs, but only
   four of them (KNOB1–4) are free for parameters; MASTER is volume and
   SELECT/ALGORITHM/PRESETS navigate (corrected 2026-09-29), so a Movy page
   becomes two FM-1 pages of four. Its colour screen has far more pixels than
   Move's OLED. A DX7 voice has 6×21
   operator parameters plus 19 globals; Movy's page/cell scheme is a ready-made
   answer to "how do you edit 145 parameters on eight knobs".
2. **Sequencer semantics as a spec.** Clips with length/scale/transpose; steps
   with velocity, length, probability, condition, invert; non-destructive
   quantize strength per clip; live vs step recording with count-in; capture
   with tempo detection; scenes/song; undo as one gesture = one undo. The FM-1's
   stock 16-step sequencer is far simpler; Movy's model is a good target for
   an open firmware, scaled to one synth engine and 16 or 32 steps.
3. **A reference implementation to test against.** `seq-core` is pure Rust
   logic with no hardware dependency. A C sequencer for the FM-1 could be
   validated on a desktop against `seq-core` with golden tests (same inputs,
   same event stream), keeping Movy as the oracle without porting it.
4. **Conventions.** The FFI safety rules (`panic = unwind`, every entry point
   catching panics), the persist format, and the CPU-optimization settings UI
   are all patterns worth copying in spirit.

## 4. Patch compatibility already exists

Schwung hosts a Dexed-based "DX7" sound generator, and Movy's bank selector
handles Dexed `.syx` banks. The FM-1 runs the same msfa engine and imports the
same 32-voice DX7 SysEx banks. The two devices can share sounds today; an open
FM-1 firmware should keep that.

## 5. Update 2026-09-29: a Schwung-style platform

Schwung's *modules* are a different question from Schwung itself. Their DSP
contract is three plain C structs at 44.1 kHz, and about 22 MIT and GPL
modules look portable from source through a shim. Mutable Instruments' MIT
code is the stronger candidate for engines. See docs/11.

## 5a. Update 2026-10-01: Movy has parameter locks

This document inspected Movy at `5627d51`, a `main` commit of 2026-09-05
whose `module.json` says 0.31.0; the v0.31.0 tag is `675054f`, 38 commits
earlier [verified 2026-10-05: GitHub API]. (This line used to call
`5627d51` v0.31.0; docs/13 refuted that.) Movy has since gained
Elektron-style per-step parameter locks: hold a step that has notes and turn
a module knob, and the value is stored for that step only and plays when the
step plays [verified at `9190e79`, `main` on 2026-10-01, 299 commits past
the v0.34.0 tag `7539028`: MANUAL.md, `clip.rs`]. It also
has per-step velocity, length, probability and A:B conditions. It is still
Rust and TypeScript on aarch64 Linux, so the conclusion below stands; its MIT
licence makes it a usable spec and desktop test oracle for an FM-1 sequencer.
See docs/12, and docs/13 for the plan to replicate its sequencer, which is
pinned to `9190e79`.

## 6. Recommendation

Do not attempt a port. Treat Movy as the design reference for the FM-1's UI and
sequencer, write the FM-1 firmware in C/C++ against the vendor SDK (docs/05),
and consider a small "movy-compat" test harness on the desktop that plays the
same MIDI/step input into `seq-core` and into the C sequencer and diffs the
output. Credit Movy and Schwung prominently.
