# 09 — First hands-on session: read-only checklist

For the first session with the FM-1 on USB and the `M-UPGRADE-FM1.app` disk
image in `~/Downloads`. Everything here is **read-only for the device**. Nothing
below writes flash. Record all output under `notes/` with the date.

Works on macOS or Linux; commands are given for both where they differ.

## 0. Set up a workspace

```bash
cd ~/Developer/mvave-fm1-firmware
git clone https://github.com/AL-255/FM-1-RE reference/FM-1-RE
git clone https://github.com/aroum/fm1-custom-fw reference/fm1-custom-fw
git clone https://github.com/kagaimiq/jl-misctools reference/jl-misctools
git clone https://github.com/kagaimiq/jl-uboot-tool reference/jl-uboot-tool
git clone https://github.com/kagaimiq/jielie reference/jielie
python3 -m venv .venv && source .venv/bin/activate
pip install crcmod pyyaml mido python-rtmidi
```

`reference/` is git-ignored. Vendor firmware files are git-ignored too
(`*.fwsc`, `*.bin`); keep them under `reference/` or `scratch/`.

## 1. Extract and unpack the V15 firmware from the updater

```bash
hdiutil attach ~/Downloads/M-UPGRADE-FM1*.dmg          # note the /Volumes/<name>
BIN="/Volumes/<name>/M-UPGRADE-FM1.app/Contents/MacOS/M-UPGRADE-FM1"
file "$BIN"                                             # Mach-O; may be a universal binary
shasum -a 256 "$BIN"
python3 tools/extract_fwsc_from_updater.py "$BIN" -o scratch/FM-1_v15.fwsc
shasum -a 256 scratch/FM-1_v15.fwsc
cd scratch && python3 ../reference/jl-misctools/firmware/fwunpack_newfw.py FM-1_v15.fwsc && cd ..
ls -la scratch/FM-1_v15.fwsc_unpack/top scratch/FM-1_v15.fwsc_unpack/files
```

**2026-09-06 result:** the macOS DMG embeds V14 (`FM-1_014`), byte-identical to
AL-255's package; V15 must be fetched from the CDN link in docs/02 §1. Details
in `notes/2026-09-06-bench.md`.

The extractor finds the package by its `JLUFW` trailer (16 bytes before the end
of the `.fwsc`) and the Qt resource size prefix that precedes the data; it
sanity-checks the `AC791N` marker at offset `0x424`. Expected: a package around
704 KB, `top/uboot.boot` of 14384 bytes with SHA-256
`730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef` if the SPL
is unchanged, `files/app.bin` around 585 KB.

Then compare with V14 (in `reference/FM-1-RE/firmware-images/v14/`):

```bash
python3 tools/check_msfa_table.py scratch/FM-1_v15.fwsc_unpack/files/app.bin
strings -n 5 scratch/FM-1_v15.fwsc_unpack/files/app.bin | grep -E 'FM-1_0|INCLUDE_|@20|Glide|Portamento|Sequenc|Arpegg' | sort -u
shasum -a 256 scratch/FM-1_v15.fwsc_unpack/top/uboot.boot reference/FM-1-RE/firmware-images/v14/raw_fw/FM-1.fwsc_unpack/top/uboot.boot
cmp scratch/FM-1_v15.fwsc_unpack/top/isd_config.ini reference/FM-1-RE/firmware-images/v14/raw_fw/FM-1.fwsc_unpack/top/isd_config.ini && echo "isd_config identical"
```

Write down: identity string (`FM-1_015`?), app size delta, whether
`uboot.boot`/`ota.bin`/`cfg` are still byte-identical (they were between V13
and V14), and new strings.

Optional deeper look (needs the JieLi toolchain, see AL-255
`docs/04-toolchain-and-vendoring.md`): vendor `objdump` listing of V15 and a
diff of the update subsystem against V14 (AL-255 lists the V13→V14 function
offsets; the update block moved by `+0x74C` last time).

## 2. USB enumeration (device on, plugged in directly, no hub)

macOS:
```bash
system_profiler SPUSBDataType | grep -A 12 -i 'FM-1'
ioreg -p IOUSB -l -w0 | grep -i -E 'FM-1|idVendor|idProduct|USB Serial'
```
Linux:
```bash
lsusb -d 4c4a: ; lsusb -v -d 4c4a: | grep -E 'idVendor|idProduct|iProduct|iSerial|bInterfaceClass|bInterfaceSubClass'
amidi -l ; aplay -l | grep -i fm ; arecord -l | grep -i fm
```

Expected: `4C4A:C755`, product strings "FM-1 Midi" and "FM-1 Audio", serial =
chip ID in hex (write it down; it is probably what the identity reply carries),
interfaces: audio control + streaming (UAC1) and a MIDI streaming interface.
Also note whether the device enumerates with the power switch **off** while on
USB power — that matters for the `USB_KEY` attempt in docs/07.

## 3. SysEx identity query (read-only)

The query is `F0 00 32 45 00 00 00 40 7F F7`; the reply is 41 bytes starting
`F0 00 32 45 58 01 00 00 23 4D 5A 44 …` (docs/03). Three ways:

- **AL-255's client** (Linux, ALSA sequencer):
  `python3 reference/FM-1-RE/tools/fm1_ota.py scan` — prints the decoded model
  and version. Hardware validation of its parser is one of AL-255's open items,
  so a working `scan` is itself a useful result to report upstream.
- **`tools/fm1_identify.py`** (any OS, mido + python-rtmidi; prints and decodes
  the reply; used on 2026-09-06, reply decoded to `FM-1_015`).
- **`tools/fm1_identify.sh`** (Linux, ALSA raw MIDI via `amidi`). Note: raw
  MIDI is unavailable while PipeWire/JACK hold the port; stop them or use the
  next option.
- **Any SysEx tool** (macOS: SysEx Librarian, MIDI Monitor; or `sendmidi`/
  `receivemidi`): send the ten bytes, capture the reply.

Decode: model = ASCII before `_`; the 20-byte field after it holds the version
with ASCII `0` added per byte; the decimal suffix is the firmware version. Save
the raw reply.

**Do not** send any other SysEx from the vendor families (`00 59` syscmd, the
upgrade command `F0 22 24 35 7F F7`, the "soft key" `F0 22 24 35 7D F7`
that reboots stock V15 into mask ROM, the `F0 35 59` vendor magic) in this
session.

## 4. Optional: capture a stock update (this one writes the app bank)

Only if you accept that the stock updater will re-flash the unit (it is the
stock path and has been proven, including downgrades). Run M-UPGRADE with a MIDI
monitor recording both directions (macOS MIDI Monitor, or `aseqdump` on Linux
under Wine). The trace validates the framing in docs/03 on this specific unit
and shows the current loader's request sequence. Save the trace. Note the
OTA-mode enumeration (`4D4A:4155`, "ota-FM-1").

## 5. Photos and physical notes (case open, power off, battery unplugged)

- Chip marking under magnification; count pins per side (48?).
- `U2` (`U3` reads `74HC595D`; both SOIC-16), `U5` (QFN-20 class), `U9`
  (8-lead SOP), the SOP-10 marked `SLS316D`, `U11` (SOT-23-6), `Q2`/`Q4`:
  read every marking. (`PC1`, the `OCIC P2362`, is a TLP2362-class
  photocoupler for MIDI IN; nothing to do.)
- Knobs: for each of the 8, count solder pins, feel for detents, note the
  reference designator (`E*` vs `RW*`/`R*`). Decide encoder vs. pot.
- `J12` display FPC: pin count, panel model printed on the flex if any.
- USB-C to SoC: series resistors/ESD parts on D+/D−; which SoC pins they reach.
- Any pads that look like test points near the SoC (the round bare pads are
  fiducials). The three pads left of `U2` are the battery connector's leads
  and `J14` carries the electrolytics' leads (owner's photos, 2026-09-29).
  Confirm that by eye from the bottom; they are not a debug header.
- **`U12`**, the bottom-side SOIC-8 near the connectors: read the marking
  (charger vs. SPI flash decides docs/07 §2.5).
- The SOT-23 and `R21` under J6: read markings; they sit on the USB path the
  `USB_KEY` dongle drives (docs/10 §8).
- Battery: confirm it is disconnected during probing.

## 6. Where the results go

- `notes/YYYY-MM-DD-bench.md`: descriptors, identity reply, decode, photos
  list, knob findings, V15 analysis summary.
- Update docs/01 §6 open questions with answers; update docs/02 §1 with V15.
- Open issues for anything surprising; tell aroum/AL-255 about the `scan`
  result and the V15 package.

## 7. Hard stops

- No custom or modified package is sent to the device in this session.
- No flash writes other than, optionally, the stock updater in §4.
- No soldering yet; `USB_KEY` work is docs/07 Phase 2 and needs a dongle.
