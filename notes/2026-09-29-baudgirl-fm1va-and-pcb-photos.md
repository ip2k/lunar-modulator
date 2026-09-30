# 2026-09-29 — Baud Girl's FM-1+VA firmware, and photos of the owner's board

No bytes were sent to the FM-1. Sources:

- Baud Girl's pages for **FM-1+VA** — [install](https://baudgirl.com/work/FM-1+VA/install),
  [presets](https://baudgirl.com/work/FM-1+VA/presets),
  [manual](https://baudgirl.com/work/FM-1+VA/manual) — and the Web MIDI
  installer's JavaScript modules those pages load, read as text and not run.
  Local copies are in `scratch/baudgirl-2026-09-29/`, which git ignores. No
  firmware file was downloaded.
- Three photos of the owner's opened unit: a close-up of the SoC, the bottom
  side and the whole top side. They are kept in `scratch/photos/2026-09-29/`,
  with crops in `scratch/crops/2026-09-29/`. Both folders are git-ignored and
  unpublished.

Marks: [verified] means checked here, in the photos or the page source.
[reported] means Baud Girl's own statement, on a page or in a code comment,
not re-checked. [inferred] is our reading.

## 1. FM-1+VA

Baud Girl is Madeline's workshop label. Baud Girl publishes a third-party
firmware for the FM-1 that is installed from Chrome or Edge over the FM-1's
ordinary USB-MIDI connection. The site shows `Copyright Baud Girl, 2026` and
links to no source repository, so treat the code as all rights reserved. Link
to it and summarize it, and copy none of it.

| | | |
| --- | --- | --- |
| Releases | `FM-1_083` … `FM-1_086` on 2026-09-26, `FM-1_089` on 09-27, **`FM-1_092`** on 09-29 (current). The project's numbering starts at `FM-1_020`, and the installer treats anything up to `FM-1_019` as M-VAVE's. There is also a "beta" tier that has only run on an emulator | [reported] install page, `link.js` |
| Installs from | M-VAVE V15 (`FM-1_015`) or one of Baud Girl's own versions. V13/V14 are refused before anything is sent, and the page says to update with M-VAVE's updater first | [reported] install page, `install.js` |
| Rollback | M-VAVE's own `.fwsc`, installed through the same page | [reported] install page, manual |
| What it replaces | screens, sound engine, MIDI handling. Presets and patterns are kept, and the GLOBE settings may reset once | [reported] |
| New engine | "Virtual Analog": Sine/Saw/Tri/Square with up to 6 detuned copies (Super), sub, noise, PWM, drift; LP12/LP24/BP/HP filter with its own envelope; 12 voices with Sine/Saw, 8 with Tri/Square; the same filter available on FM presets (9–12 voices while on) | [reported] manual, release notes |
| Other features | 64-step sequencer (stock: 16), real-time recording, MIDI CC control of the panel and engine, colour themes (GLOBE > Theme) | [reported] |
| Preset pack | 16 VA presets into slots 113–128 as `fm1-va-presets.syx` (3,696 bytes); needs `FM-1_079`+; written one preset every 3 s and read back to verify | [reported] presets page, `bank.js`; file size from the HTTP header [verified] |
| How it is built | A **modified V15 package**. The flash head is stock, `app.bin` is replaced and may grow, the version string is renamed in place at the same length, reserved partitions can be re-declared, there is an optional "cfg bump", and every CRC is recomputed. The code refers to stock functions, tables and RAM addresses (stock `voice_unpack` at file `0x1DBBA`, the sequencer block at `0x01C14CD0`, `g_settings` at `0x01C0E840`), so the firmware extends V15's application. It is not a rewrite on the SDK | build: [reported] `fwsc.js`; "extends stock": [inferred] |
| Tooling it stands on | AL-255's FM-1-RE (vendored; the installer is a port of its `tools/fm1_ota.py` with three fixes, Baud Girl's FINDINGS 24.39/24.52/24.53) and kagaimiq's jl-misctools ciphers and CRC. Baud Girl also has an **FM-1 emulator** (`tools/emu/…`), a numbered FINDINGS document, and a private firmware repository | [reported] code comments |
| Telemetry | The install and presets pages forward their progress events, failure traces and script errors to `baudgirl.com/api/event`, keyed by a per-page-load id and the site's visitor cookie | [verified] `fm1-report.js` |

### 1.1 What it tells us about the stock update path

1. **The step-1 check refuses a no-op, not foreign code** [reported].
   Baud Girl measured this on hardware on 2026-09-25. `FM-1_079` sent to a
   synth already running `FM-1_079` stopped after **9 step-1 requests** with no
   verification. A `FM-1_079` that differed only by a CRC-neutral table patch
   was refused the same way. `FM-1_078` → `FM-1_079` and back both installed.
   Baud Girl does not know whether the device compares the version string or
   the file list. This fits AL-255's 2026-07-21 probes, which saw 9 requests
   when refused and 49 once a `cfg` CRC changed, and Echomatter's
   version-bumped `FM-1_016`. Content is not authenticated. The answer to our
   open question "what does the verifier compare" is now "at least the
   version, perhaps the file list".
2. **The OTA loader can rewrite the flash head** [reported: Baud Girl's FINDINGS
   5.4]. That region holds `uboot.boot` and `isd_config.ini`. The installer
   refuses any package whose bytes `[0x414, 0x4414)` do not have the SHA-256
   of V15's, which is the first 16 KB of `flash.bin`. A package that changes
   the head therefore rewrites the second-stage bootloader over USB-MIDI, the
   one write this project's rule 2 (docs/07 §4) is there to prevent.
3. **An install that stops after step 1 can be resumed** [reported]. A synth
   left in its updater stays there across power cycles and answers the
   identity query as `ota-FM-1`. The installer then goes straight to step 2.
   The help text also says that when the installer lost contact at the very
   end, the install had in fact worked in more than half of the reported
   cases.
4. **Some field failures are still unexplained** [reported]. Some FM-1s
   confirm step 1 and never restart into the updater, so nothing is
   installed; the cause is unknown to Baud Girl. Port names: on Windows the
   synth is `FM-1 Midi` and its updater `USB-Midi`. In Chrome on macOS both
   are `USB Composite Device`. Re-enumeration takes about 6 s after each step.
   Bluetooth MIDI ports must be skipped because the update only runs over USB.
5. **Scale** [reported]. Versions `FM-1_020` to `FM-1_092` were installed on
   Baud Girl's synth over roughly a week, public installs on Windows and macOS
   followed from 2026-09-26, and rollback to V15 goes through the same path.
   The stock update path has now installed dozens of non-stock applications.
6. **Presets over SysEx, in Baud Girl's firmware only** [reported:
   `fm1sound.js`]. A stored sound is a 128-byte DX7 packed voice (VMEM) plus a
   59-byte settings record: effects, an engine marker (`0x5A` VA / `0xA5` FM),
   the VA filter, and ADSR. It is written as the 155-byte unpacked edit buffer
   plus that record. Writes are paced 3 s apart because each one rebuilds the
   effects and writes flash, and closer spacing was heard as crackling.

### 1.2 What it does not change

- **There is still no recovery for an application that does not run.** Step 1
  runs inside the application. A package that fails to boot, or that loses USB
  or the update handshake, leaves only mask-ROM USB (`USB_KEY`, docs/07 §2.1),
  and that is still unproven on an FM-1. The updater-resume path covers an
  interrupted *transfer*. It does not cover a *bad image*.
- **Rule 1 of docs/07 §4 stands** unless the owner decides otherwise. The new
  evidence lowers the transfer risk; it does not provide the dump-and-restore
  the rule asks for.
- **Openness.** FM-1+VA is a closed modification of the stock image and
  carries JieLi's closed libraries. The goal here, an open application on the
  Apache-2.0 SDK, is a different thing. Baud Girl's FINDINGS and emulator
  would help this project a great deal if Baud Girl ever shares them.

## 2. The owner's board, 2026-09-29

Photo 1 is the SoC close-up, photo 2 the bottom side with the battery, and
photo 3 the whole top side. The unit is the same `DX7 MB V07` layout as
aroum's, from a later batch.

| Observation | Confidence |
| --- | --- |
| SoC marking **`C188612-11B8`**, against `C156211-11B8` on aroum's unit. The first group changes per lot and `11B8` is the same on both | [verified] photo 1 |
| Silkscreen `DX7 MB V07 260708` (aroum's: `260620`); bottom stamp `MC 26 0727` (aroum's: `MA 26 06 24`); battery `DTP704060` 3.7 V 2000 mAh 7.4 Wh dated **2026-07-31** (aroum's: 2026-06-24). The owner's unit was assembled after 2026-07-31 | [verified] photos 2, 3 |
| `U2`, `U3` are **SOIC-16** (8 leads a side, counted, not SOIC-20). `U3` reads `74HC595D` on its first line; `U2`'s marking is too faint to read | [verified] photo 3, `u2-u3-soic16.png` |
| The **"unpopulated 3-pin header" left of `U2` is the battery connector's leads.** With the bottom photo flipped and aligned on the mounting hole, the three pins of the bottom-side `电池` connector (`正` +, `负` −, `NTC`) land on those three pads. The pads carry soldered, clipped leads, not open holes. So the desk review's candidate UART (2026-09-08 §1) is not one | [verified] by overlay, `mirror-top.png` vs `mirror-bottom-flipped.png`; confirm by eye with the board out |
| Likewise the four plated holes labelled **`J14`** (right of the SOP-10) and the pair just above them carry the leads of the bottom-side electrolytics `C112`/`C113` (16 V 100 µF) and `C111` (10 V 100 µF) | [verified] same overlay; why the column is labelled `J14` is unknown |
| So the V07 board has **no debug or UART header**. Access to the SoC's pins means soldering to the LQFP48 leads (docs/07 §2.4) | [inferred] |
| `PC1` = `OCIC P2362 2623`, a 5-lead SO6-style package (2 + 3 leads), i.e. a TLP2362-class 10 Mbps logic-output photocoupler. Baud Girl's manual says the TRS socket is **MIDI input only**, so this is the MIDI IN optocoupler | package [verified] photo 1; function [inferred, strong] |
| SOP-10 marked **`SLS316D` / `6253KD`** right of the display FPC `J12`, next to `J14`; designator not legible; function unknown (a quick datasheet search found nothing) | [verified] marking, `sls316d.png` |
| `U5` is a QFN-20-class part near the jacks, with ferrites `FB4`/`FB5` (docs/01 had it as SOIC-8); `U9` is an 8-lead SOP; `U6` a SOT-89/SOT-223-class part, probably a regulator | package [verified] photo 3; roles [inferred] |
| Speaker connector **`J13`** (SMD 2-pin, `+S`/`−S`, `喇叭`) on the owner's board; the 2026-09-08 notes read `J11` on aroum's | [verified] photo 2, `j13-speaker.png` |
| Bottom, by the USB-C: `R32` = `R100` (0.1 Ω) next to `U12`; `U12`'s marking is not legible in this photo | [verified] photo 2 |
| Antenna: red wire from pad `P1` (`天线`) routed toward the knob block. The silkscreen box around the SoC area has oblong corner slots, probably an unpopulated shield-can frame | wire [verified] photo 1; shield [inferred] |
| 24.000 MHz crystal can next to the SoC; `L2` marked `100` (10 µH) | [verified] photo 1 |
| Knobs: a 2×2 block top left (`RW1` with an index mark, i.e. a potentiometer, plus three encoders including `E6`) and a row of four encoders `E2`–`E5` top right. Baud Girl's manual names eight controls: MASTER (volume), SELECT, ALGORITHM, PRESETS and KNOB1–KNOB4. Most likely `E2`–`E5` = KNOB1–KNOB4 and `RW1` = MASTER, with SELECT/ALGORITHM/PRESETS in the block | layout [verified] photo 3; mapping [inferred] |
| 27 keys on interdigitated contact pads, one LED and one diode beside each. Baud Girl's manual calls them "touch keys", but the pads look like contacts for silicone keys, not capacitive electrodes | [verified] photo 3; reading [inferred] |

## 3. Follow-ups

- **Static analysis of `FM-1_092.fwsc`** (810,548 bytes, public download on
  the install page), if the owner agrees to fetch it into `scratch/`. Unpack
  it with our tools, compare its head with V15's, diff `app.bin` against V15
  to see how much changed and where, and check whether the msfa table is
  still in place. This is offline only: nothing goes to the device.
- Bench, with the board out: confirm by eye that the battery connector's pins
  come through at the 3 pads and the electrolytics' at `J14`; read `U12`,
  `U2`, `U5` and the SOP-10 under a loupe with raking light.
- Upstream: the same-version finding and the updater resume would help
  AL-255's `fm1_ota.py` users. They are Baud Girl's findings, so whether and
  how to point AL-255 at them is the owner's call (oss-contributions rules).
- Contact: Baud Girl publishes an email address. Asking about the FINDINGS
  document and the emulator is the owner's call.
