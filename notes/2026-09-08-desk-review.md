# 2026-09-08 — desk review: aroum's photos, the FM1 web editor's research, M-VAVE's MIDI guide

No hardware was touched. Sources: aroum/fm1-custom-fw (unchanged since
2026-08-21; our issue #2 has no reply), its five teardown photos inspected here
at crop level, benny-sparra/fm1-dx7-patch-importer (the source of
fm1-editor.com, pushed 2026-09-07), and M-VAVE's download centre. Marks:
[verified] = seen in the photo/file here, [reported] = the named source,
[inferred] = our reading.

## 1. Photo inspection (aroum's `photos/`, 961×1280, crops in `scratch/crops/`)

| Finding | Evidence | Mark |
| --- | --- | --- |
| **An unpopulated 3-pin through-hole header** sits left of U2 (the first 74HC595), below the SoC area (photo 3). Tinned pads, 2.54 mm pitch by eye, no silkscreen label; traces leave the middle and right pads toward the SoC. | `scratch/crops/header3_zoom.png` | [verified] present; function unknown. Candidate factory UART (GND/TX/RX) or debug pins. aroum's "no debug pads" is at least incomplete. |
| **Knobs:** the top-right 2×2 block's upper-right knob is labelled `RW1`, has a single 3-pin row and a **white index line** on its shaft; the other knobs carry `E` designators (`E3`, `E6` legible) and show the 3+2 pin pattern of EC11-type encoders with push switches. | `rw1_label.png`, `knobs_top_block.png`, `knobs_right_column.png` | [inferred] 1 potentiometer (RW1, likely volume) + 7 push encoders. Fits the V15 UI strings `K1-K4 Select Patch`, `Turn the Select`. |
| **USB data path:** between J6 (USB-C) and the SoC there is `R21` (0603) plus a **3-pin SOT-23** device right under the connector shell; marking unreadable. | `usb_sot23_zoom.png` | [verified] present; [inferred] ESD/protection or a small switch/detector on D+/D−/VBUS. Matters for the dongle's series-resistance assumption (docs/10 §8). |
| **Bottom side, under the connector area: a SOIC-8 (`U12`?)** with pin-1 mark, `R35`/`R36` beside it and a large resistor marked `R100` (0.1 Ω) nearby. | `bottom_soic8_zoom.png`, `bottom_usb_ic.png` | [verified] present; identity unknown. A 0.1 Ω sense resistor suggests a **battery charger IC**; an SOIC-8 there could also be an **external SPI NOR flash**, which would open the external-programmer recovery path (docs/07 §2.5). Read the marking on the bench. |
| The round bare pads near the SoC (top-left corner, near `PC1`, near `C93`) are **fiducials**, not test points. | `soc_left_pads.png`, photo 1 | [inferred] |
| `PC1` = the white 4-pin `OCIC P2362` package next to the jacks. | `soc_right.png` | [inferred] optocoupler for the TRS **MIDI IN** (a TLP2362-class part; `PC` designator = photocoupler). |
| `J12` display FPC: about 12 contacts at 0.5 mm. | `j12_fpc.png` | [verified] count approximate |
| Board: `DX7 MB V07 260620`; battery `DTP704060` 2000 mAh dated 2026-06-24; speaker `J11`; two 16 V/100 µF electrolytics on the bottom. | photos 2–4 | [verified] (already in docs/01) |

**Superseded 2026-09-29** (`notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md`
§2, from the owner's photos): the 3-pin "header" is the battery connector's
leads, not a UART candidate, and the speaker connector reads `J13` on the
owner's board.

## 2. fm1-editor.com is open source and has hardware fixtures

Repository: https://github.com/benny-sparra/fm1-dx7-patch-importer (no license
file; 12 stars; active). `docs/fm1-research.md`, `docs/fx-003-hardware-verification.md`,
`docs/seq-001-findings.md`, `docs/sequencer-fixtures/V15/*.ndjson`,
`scripts/capture-midi.swift`, `scripts/send-standard-midi-cc.c`. Everything it
sends is standard: DX7 bank `F0 43 0n 09 20 00 …`, single voice
`F0 43 0n 00 01 1B …`, parameter change `F0 43 10 gg pp vv F7`, program change,
CC. What we learn [reported]:

- "The FM1 accepts voices and banks but cannot send its stored banks back" —
  independent confirmation of our no-read-back finding (docs/02 §6).
- After a bank dump the **FM-1 shows a bank-selection screen**; the user turns
  K1–K4 to pick destination A–D and the unit saves automatically. No vendor
  message selects the destination.
- Parameter change requires sub-status exactly `0x10`; address `(gg<<7)+pp`
  into the 155-byte VCED buffer (op 6 at 0–20 … op 1 at 105–125, globals
  126–144, name 145–154).
- **The FM-1 transmits MIDI**: key presses and sequencer playback come out as
  Note On/Off over USB-MIDI (their V15 fixtures: `90 40 5A` / `80 40 64`,
  playback repeats every ~2.5 s at 1/8T, 120 BPM, 16 steps; global gate 80 % →
  131–134 ms, 50 % → 83 ms). Our "no spontaneous traffic" (bench 1) holds only
  for an idle unit.
- V15 sequencer pages: `1/3` Pattern 1 · Clear · Chain 1 · Step 1–16;
  `2/3` Voice · Rate `1/8T` · Tempo `120` · Gate `80%`; `3/3` Swing `50%` ·
  Sync `Off` · Transpose `0`. V13's internal record (AL-255) had 10 notes +
  10 velocities per 32-byte record and 16 slots per bank; V15 plays 16 steps,
  so the record format changed with V15 (matches our string diff).
- Bluetooth carries the same syscmd transport as event `0x72` with a
  1046-byte bound (their reading of AL-255).

## 3. M-VAVE's official MIDI control guide (V14/V15) [reported: vendor document]

`FM-1 MIDI EN.docx` from the download centre
(`https://yms-file-store.oss-cn-hongkong.aliyuncs.com/software/releaseNote/firmware/FM-1%20MIDI%20EN.docx`,
copy in `scratch/vendor/`):

- Note channel `midich` defaults to Omni; **FX channel `effectch` defaults to
  channel 2**; CC 1 on the FX channel is Filter Type, not mod wheel.
- Note channel: Note On/Off, Program Change `0–127 → Voice 001–128`, Pitch
  Bend (14-bit), **Channel Aftertouch** (`Dn`), CC 1 Mod Wheel, CC 64 Sustain.
- FX channel CC 0–23: Filter 0–3 (Switch 0/≥1, Type 0–2 LPF/BPF/HPF, Cutoff
  0–107, Q 0–10), Reverb 4–7 (Switch, Type Room/Hall/Plate, Decay, Mix),
  Delay 8–11 (Switch, Decay, Rate, Mix), Distortion 12–15 (Switch, Gain,
  Tone, Level), Chorus 16–19 (Switch, Freq, Depth, Mix), Phaser 20–23
  (Switch, Freq, Depth, Mix); continuous ranges 0–100.
- **System Real-Time:** `F8` clock (follows external BPM), `FA` start (from
  step 0), `FB` continue (= start, no resume), `FC` stop.
- SysEx: `F0 43 10 pp qq vv F7`, param `pp×128+qq`, **0–155**, value `vv`.
- benny-sparra confirmed on a V15 unit that CC 0 = 0/1 switches the filter and
  Cutoff 0 vs 107 is a large audible change.

Download centre (https://www.m-vave.com/download) as of 2026-09-08: V15
(2026-07-30) `.fwsc` is the "latest PC firmware"; V14 (2026-07-06) updaters for
Windows/macOS; MIDI guides EN/CN and release notes per version; **no V16**.

## 4. What changes for us

- Bench to-do (docs/09 §5): read the `U12` marking (charger vs. flash decides
  whether an external programmer route exists); probe the 3-pin header
  passively (scope/logic analyser at power-up; 3.3 V UART at 1 Mbps is the SDK
  default `UTBD=1000000`); confirm RW1 is a pot and the rest encoders; read the
  SOT-23 under J6.
- docs/02 §6 gains the official CC/real-time map, aftertouch, transmit
  behaviour and the V15 sequencer page map; docs/04 gains the editor's repo
  and the vendor guide; docs/01 §3/§6 and HANDOFF §4 updated.
- Our RP2040 dongle spec's "series/ESD parts between the USB-C and the SoC"
  question now has a candidate: the SOT-23 under J6 [inferred].
