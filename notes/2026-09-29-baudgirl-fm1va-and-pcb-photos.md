# 2026-09-29 — Baud Girl's FM-1+VA firmware, and photos of the owner's board

This project sent the FM-1 nothing except the read-only identity query (§4).
The owner had already installed FM-1+VA on the unit before this session, by
their own decision. Sources:

- Baud Girl's pages for **FM-1+VA** — [install](https://baudgirl.com/work/FM-1+VA/install),
  [presets](https://baudgirl.com/work/FM-1+VA/presets),
  [manual](https://baudgirl.com/work/FM-1+VA/manual) — and the Web MIDI
  installer's JavaScript modules those pages load, read as text and not run.
  Local copies are in `scratch/baudgirl-2026-09-29/`, which git ignores.
- The release package `FM-1_092.fwsc` (810,548 bytes, SHA-256
  `ed8415f3…876eb80`), downloaded from the install page with the owner's
  agreement. It sits in `scratch/baudgirl-2026-09-29/fw/` and is not
  committed, per the vendor-binary rule. It was compared with M-VAVE's V15
  package (§3).
- Three photos of the owner's opened unit, in
  [`photos/2026-09-29/`](../photos/2026-09-29/): `1-soc-closeup.jpg`,
  `2-bottom.jpg` and `3-top.jpg`, plus the `crop-*.jpg` evidence crops cited
  below. They carry no location metadata.

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
| How it is built | A **binary patch of V15**: V15's `app.bin` with about 90 small edits and 110 KB of new code and data appended, the version string renamed in place, the VM partition moved to make room, and every CRC recomputed. The flash head, the OTA loader and `cfg` are untouched. The code refers to stock functions, tables and RAM addresses (stock `voice_unpack` at file `0x1DBBA`, the sequencer block at `0x01C14CD0`, `g_settings` at `0x01C0E840`) | [verified] package diff, §3; build recipe [reported] `fwsc.js` |
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
| `U2`, `U3` are **SOIC-16** (8 leads a side, counted, not SOIC-20). `U3` reads `74HC595D` on its first line; `U2`'s marking is too faint to read | [verified] photo 3, `crop-u2-u3-soic16.jpg` |
| The **"unpopulated 3-pin header" left of `U2` is the battery connector's leads.** With the bottom photo flipped and aligned on the mounting hole, the three pins of the bottom-side `电池` connector (`正` +, `负` −, `NTC`) land on those three pads. The pads carry soldered, clipped leads, not open holes. So the desk review's candidate UART (2026-09-08 §1) is not one | [verified] by overlay, `crop-mirror-top.jpg` vs `crop-mirror-bottom-flipped.jpg`; confirm by eye with the board out |
| Likewise the four plated holes labelled **`J14`** (right of the SOP-10) and the pair just above them carry the leads of the bottom-side electrolytics `C112`/`C113` (16 V 100 µF) and `C111` (10 V 100 µF) | [verified] same overlay; why the column is labelled `J14` is unknown |
| So the V07 board has **no debug or UART header**. Access to the SoC's pins means soldering to the LQFP48 leads (docs/07 §2.4) | [inferred] |
| `PC1` = `OCIC P2362 2623`, a 5-lead SO6-style package (2 + 3 leads), i.e. a TLP2362-class 10 Mbps logic-output photocoupler. Baud Girl's manual says the TRS socket is **MIDI input only**, so this is the MIDI IN optocoupler | package [verified] photo 1; function [inferred, strong] |
| SOP-10 marked **`SLS316D` / `6253KD`** right of the display FPC `J12`, next to `J14`; designator not legible; function unknown (a quick datasheet search found nothing) | [verified] marking, `crop-sls316d.jpg` |
| `U5` is a QFN-20-class part near the jacks, with ferrites `FB4`/`FB5` (docs/01 had it as SOIC-8); `U9` is an 8-lead SOP; `U6` a SOT-89/SOT-223-class part, probably a regulator | package [verified] photo 3; roles [inferred] |
| Speaker connector **`J13`** (SMD 2-pin, `+S`/`−S`, `喇叭`) on the owner's board; the 2026-09-08 notes read `J11` on aroum's | [verified] photo 2, `crop-j13-speaker.jpg` |
| Bottom, by the USB-C: `R32` = `R100` (0.1 Ω) next to `U12`; `U12`'s marking is not legible in this photo | [verified] photo 2 |
| Antenna: red wire from pad `P1` (`天线`) routed toward the knob block. The silkscreen box around the SoC area has oblong corner slots, probably an unpopulated shield-can frame | wire [verified] photo 1; shield [inferred] |
| 24.000 MHz crystal can next to the SoC; `L2` marked `100` (10 µH) | [verified] photo 1 |
| Knobs: a 2×2 block top left (`RW1` with an index mark, i.e. a potentiometer, plus three encoders including `E6`) and a row of four encoders `E2`–`E5` top right. Baud Girl's manual names eight controls: MASTER (volume), SELECT, ALGORITHM, PRESETS and KNOB1–KNOB4. Most likely `E2`–`E5` = KNOB1–KNOB4 and `RW1` = MASTER, with SELECT/ALGORITHM/PRESETS in the block | layout [verified] photo 3; mapping [inferred] |
| 27 keys on interdigitated contact pads, one LED and one diode beside each. Baud Girl's manual calls them "touch keys", but the pads look like contacts for silicone keys, not capacitive electrodes | [verified] photo 3; reading [inferred] |

## 3. `FM-1_092.fwsc` against M-VAVE's V15 package [verified]

Both packages were unpacked with `jl-misctools/firmware/fwunpack_newfw.py`
and their UFW entry lists read directly. Scripts and outputs are in
`scratch/baudgirl-2026-09-29/fw/` (`appdiff.py`, `patchscan.py`,
`patch_regions.txt`).

| Part | V15 (`FM-1_015`) | `FM-1_092` | |
| --- | --- | --- | --- |
| Whole file | 699,956 B | 810,548 B | +110,592 (`0x1B000`): only `flash.bin` grew |
| UFW entries besides `flash.bin` (types 50, 52, 100 = `ota.bin` 19,969 B, 251, 161, 255) | | | **byte-identical** |
| Flash head, file `[0x414, 0x4414)` | SHA-256 `d9f43191…d9bd67` | same | identical, and equal to the constant Baud Girl's installer checks |
| `uboot.boot`, `isd_config.ini`, `cfg_tool.bin`, `cfg` / `eq_cfg_hw.bin` | | | byte-identical; the `cfg` CRC is unchanged, so this release uses no "cfg bump" |
| `app.bin` | 581,564 B | 691,744 B | +110,180 B appended after V15's last byte |
| `app.bin` over V15's length | | | 1,820 bytes differ (0.31 %) in 90 regions (gap-merged at 16 B): 60 of 1–4 bytes, 21 of 5–16, 7 of 17–256, and 2 larger (836 B at file `0x21DAC`, 270 B at `0x25FFE`). The first difference is at `0x17C6` |
| Pointers into the appended code | | | 15 of the 90 regions hold 41 absolute addresses in the new tail's range `0x208E0DC–0x20A8F40`. Most of the rest are 1–4-byte edits, consistent with retargeted call/branch displacements (not decoded here: there is no pi32v2 disassembler in this checkout) |
| Version string | `FM-1_015` at `app.bin` `0x4EA64` | `FM-1_092` at the same offset | renamed in place; the identity block's checksum was left at V15's value (§4) |
| msfa algorithm table | file `0x8BE8C` | file `0x8BE8C` | intact in both (`tools/check_msfa_table.py`: 30/32 rows equal to msfa, the Dexed-family fix) |
| Directory: `VM` | `0x93000`, 0x56000 (344 KB) | **`0xD9000`, 0x10000 (64 KB)** | moved up and shrunk; still ends at `0xE9000` |
| Directory: `PRCT` | `[0, 0x93000)` | `[0, 0xD9000)` | covers the larger app area |
| `BTIF`, `USR`, `key_mac` | `0xE9000`, `0xEA000` (72 KB), `0xFF000` | same | unchanged |

What follows:

- **FM-1+VA is V15 plus hooks, not a new application.** Nearly every stock
  byte is still in place and still runs; the new engine, screens and
  sequencer live in the appended 110 KB. It carries all of stock's closed
  JieLi libraries, as expected [inferred from the diff].
- **A re-declared partition table passes the stock update path.** VM and
  PRCT differ from V15's, and the package installed on the owner's unit (§4).
  So the step-1 gate does not compare the directory against the installed
  one, at least not for reserved entries.
- **Why settings reset on first boot** [inferred]: VM, JieLi's key/value store
  for settings (and, per AL-255, the BT address and wheel calibration), now
  starts at a different address. The first boot finds no VM there and starts
  fresh; this is the GLOBE reset Baud Girl warns about. Presets survive
  because `USR` did not move. Going back to V15 moves VM down again, over
  flash that FM-1+VA's code occupied, so expect settings to reset again.
- **For this project**: the headroom Baud Girl bought by shrinking VM (the
  app area can reach `0xD9000`, about 852 KB) is available to an open
  firmware on the same terms. It also means a flash dump of the owner's unit
  now captures FM-1+VA, not stock.

## 4. The owner's unit now runs FM-1+VA

`tools/fm1_identify.py` (read-only, the only allowed query) on 2026-09-29:

```
F0 00 32 45 58 01 00 00 23 4D 5A 44 79 05 26 0E 19 00×21 20 06 F7
→ FM-1_092
```

- The owner installed FM-1+VA with Baud Girl's browser installer before this
  session; the exact date was not recorded. The unit identified as
  `FM-1_015` (stock V15) on 2026-09-06 and as **`FM-1_092`** now [verified].
- The reply's checksum byte (`0x19` in the ID block) is V15's; the version
  digits changed but the checksum did not, so `fm1_identify.py` prints
  `checksum_ok: False`. Parse the plain field, as the tool does, and do not
  gate on the checksum.
- Rules of engagement: this was the owner's decision about the owner's unit.
  docs/07 §4 still governs everything this project builds or sends; the way
  back to stock is M-VAVE's V15 `.fwsc` through the same installer
  [reported], which has not been exercised here.

## 5. Follow-ups

- Bench, with the board out: confirm by eye that the battery connector's pins
  come through at the 3 pads and the electrolytics' at `J14`; read `U12`,
  `U2`, `U5` and the SOP-10 under a loupe with raking light.
- Decoding the 90 hook sites would show exactly where FM-1+VA enters the
  stock code. That needs JieLi's pi32v2 `objdump` (CLAUDE.md trap 4) and is
  only worth it if we want to learn from their integration points.
- Upstream: the same-version finding and the updater resume would help
  AL-255's `fm1_ota.py` users. They are Baud Girl's findings, so whether and
  how to point AL-255 at them is the owner's call (oss-contributions rules).
- Contact: Baud Girl publishes an email address. Asking about the FINDINGS
  document and the emulator is the owner's call.
