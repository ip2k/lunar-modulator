# AGENTS.md

Guidance for Codex working in this repo.

## What this is

**Lunar Modulator** (tagline **INTERGALACTIC MODULATION STATION**) is open
firmware for the **M-VAVE FM-1** (JieLi AC791N SoC, pi32v2 CPU; the stock
firmware's FM engine is msfa/Dexed).

Status, 2026-10-01: **the code runs on a desktop and in a browser, not yet on
a JieLi chip or an FM-1; nothing flashed by this project.**
- Built and tested on the desktop: an engine platform with Mutable- and
  Schwung-derived engines and effects (`engines/`, checked against reference
  renders), and a C99 port of Movy's sequencer core with its Movy oracle
  (`engines/seq.md`).
- A virtual FM-1 runs the engines and effects in a browser (`sim/web/`).
- The research phase and one read-only bench session are done
  (`notes/2026-09-06-bench.md`).
- An AC79 dev kit and JieLi's USB updater are on order (docs/14).

The owner's unit ran stock `FM-1_015` until
the owner installed Baud Girl's FM-1+VA; it identifies as **`FM-1_092`** since
(2026-09-29). The `USB_KEY` recovery
dongle (docs/10, `dongle/`) is implemented and simulated, not yet tried. Other
owners report that czietz's simpler Pico dongle reaches UBOOT mode on their
FM-1s, and one reports a firmware backup and a write that way (issue #2,
docs/10 §1.1).
Elsewhere, Echomatter ran a version-bumped V15-derived package on their FM-1
via the stock OTA path and rolled it back (AL-255 PR #2, 2026-09-04), and
since 2026-09-26 Baud Girl's FM-1+VA (a modified V15, source not published)
installs from a browser for anyone (docs/04, `notes/2026-09-29-*`).
`HANDOFF.md` is the context summary. `README.md` is the product page, for
users. `DEVELOPERS.md` holds everything technical: specifications, the
hardware, how the software works, the research, where development stands,
and how to build and contribute. `docs/` has the detail.

Keep technical material out of the README and put it in DEVELOPERS.md.

**The name** (owner's choice, 2026-10-01). Until then the project was "Open
firmware for the M-VAVE FM-1", repository `ip2k/mvave-fm1-open-firmware`; it
is now `ip2k/lunar-modulator`. The local folder `~/Developer/mvave-fm1-firmware`
keeps its old name. Rules:

- Full name **Lunar Modulator**; short form **Lunar**. Never "Lunar Module"
  (the Apollo spacecraft), "Lunar Mod" or "LM".
- Tagline **INTERGALACTIC MODULATION STATION**, in capitals.
- Wherever the project is described, keep the descriptor "open firmware for
  the M-VAVE FM-1". The device's name only says what the firmware runs on;
  it implies no tie to M-VAVE or Cuvave.
- The look is a space theme set in Audiowide (SIL OFL 1.1); the art, the
  font and its licence are in `assets/branding/` (see its README). In
  published text name the typeface, never "the NASA font". Never use NASA's
  insignia (the "meatball"), its "worm" logotype, its seal, or any other
  NASA name or mark, and nothing that suggests NASA endorsement. Never use
  M-VAVE's or Cuvave's logos. Mutable Instruments module names (Plaits,
  Braids, Clouds, …) are credited as sources, never used as product names.

This project is unrelated to the BUSY Bar timer repo it was briefly hosted in.

## Project status and licences

**Personal, non-commercial project** (owner, 2026-10-01). The repository is
MIT. GPL code, and code under similar terms such as LXR's, may be brought in
when needed, each in its own `third_party/<name>/` directory with its licence
and an `UPSTREAM.md`. Those licences only bite on distribution: a firmware
binary that links JieLi's closed SDK libraries must not be shared (released,
or sent to anyone) if it contains GPL or LXR code. Personal builds may; keep
such code behind a build switch so an MIT/BSD-only build stays shareable.
GPL and LXR code cannot be combined in one shared work. MIDIbox code needs
its author's permission. Details: docs/12 §6, docs/11 §7.

## The one rule

**Nothing gets flashed to, or written on, the FM-1 until a full flash dump and a
byte-identical restore have been demonstrated on that unit.** There is one
device, one flash bank, no debug pads, and no proven recovery path. The only
traffic allowed before that is the read-only identity query
`F0 00 32 45 00 00 00 40 7F F7` and passive captures. See `docs/07` §4 for the
full rules of engagement; they come from AL-255's safety review and are not
negotiable without new evidence. The owner's own install of FM-1+VA
(2026-09) was the owner's call and does not relax the rule for anything this
project builds or sends.

## Hardware in one table

| | |
| --- | --- |
| SoC | JieLi AC791N (WL82), LQFP48, marking `C1xxxxx-11B8` (lot varies; owner's `C188612-11B8`); pi32v2 core, 240 MHz used of 320; 578 KB SRAM; 1 MB flash (probably in-package) |
| Memory map | flash XIP `0x02000000`, RAM `0x01C00000`, SFRs `0x1xxxx…0x5xxxx`, mask ROM `0xFFC0xxxx` |
| USB | normal `4C4A:C755` (USB-MIDI + UAC1, full-speed, product string `FM-1`), OTA loader `4D4A:4155` |
| Display | 240×240 RGB565 TFT on SPI1 (`0x11D00`), ST7789-class commands |
| Controls | 27 keys + ~14 LED buttons in a 41-input matrix; 8 knobs (stock reads 2 encoders + 2 ADC channels; split unresolved) |
| Audio | internal DAC, 44.1 kHz, 64-sample blocks; 12 msfa voices |
| Update | USB-MIDI SysEx, CRC16 only; step 1 refuses only the running version, so rebuilt packages with a new version install; the OTA loader can rewrite `uboot.boot` |

## Commands

```bash
python3 tools/check_msfa_table.py path/to/app.bin            # msfa table finder (tested on V13/V14)
python3 tools/extract_fwsc_from_updater.py M-UPGRADE-FM1 -o FM-1.fwsc   # carve package from the updater
python3 reference/jl-misctools/firmware/fwunpack_newfw.py FM-1.fwsc     # unpack (needs: pip install crcmod)
python tools/fm1_identify.py                                   # read-only identity query + decode, any OS (verified on hardware)
python -m pytest                                               # tools, PIO emulation, dongle/ROM co-simulation and engine tests
make -C engines && engines/build/fm1-render --list             # engine platform, desktop build (docs/11, engines/README.md)
cd sim/web/www && python3 -m http.server 8000                  # the virtual FM-1 at http://localhost:8000/ (sim/web/README.md)
FM1_SIM_HOST=user@host sim/web/build-on-aeon.sh                # rebuild and check its WebAssembly module in containers on a Docker host
tools/fm1_identify.sh                                          # Linux, ALSA raw MIDI, read-only, untested
python3 reference/FM-1-RE/tools/fm1_ota.py scan                # AL-255's client, read-only scan
```

`reference/` and `scratch/` are git-ignored; clone third-party repos and keep
vendor packages there.

## Conventions

- **Dead-code audit:** not done yet. The mark is 7,463 lines of the repo's
  own source (`dongle/`, `engines/` less `third_party/`, `tests/`, `tools/`)
  at the stage A2 merge, 2026-09-30; audit after about 10,000 more. `sim/`
  is in scope too: it arrived on 2026-10-01 with about 4,200 lines (less its
  built module, record and font data), which count toward the next audit.
- **Confidence marks in every technical claim:** `[verified]` (checked here
  against binaries, photos or SDK files), `[reported]` (named source, not
  re-checked), `[inferred]`. Never upgrade a claim without doing the check.
- **Never commit vendor binaries** (`.fwsc`, `app.bin`, `uboot.boot`, the JieLi
  toolchain, updater apps). `.gitignore` blocks the common ones; link to
  sources instead.
- Credit prior work by name (aroum, AL-255, kagaimiq, probonopd, Google msfa,
  Dexed family, Schwung/Movy). Quote, summarize and link; do not copy whole
  documents or photos (aroum's repo has no license).
- Docs are numbered `docs/NN-topic.md`; bench results go to
  `notes/YYYY-MM-DD-*.md`; answered open questions are removed from `docs/01`
  §6 and the answer written where it belongs.
- Read the device identity (`FM-1_0xx`) from the package or device; never infer
  a version from a filename (the "V13" package identifies as `FM-1_009`).
- Future firmware code: C/C++11 for JieLi's clang (`-fno-exceptions -fno-rtti`),
  built against the Apache-2.0 AC79 SDK; msfa/Synth_Dexed for the engine; keep
  `uboot.boot`, `ota.bin`, `cfg` and the partition layout byte-identical to
  stock in any experimental package until the verifier gate is understood.

## Traps that have already cost people time

1. **`JL-BR22` in the binary is not the SoC.** It is Bluetooth-library lineage;
   the chip is AC791N/WL82 (package ID, SPL match). Register maps borrowed from
   BR2x docs are unsafe until checked against `WL82.h`.
2. **The stock updater is not a recovery tool.** It needs a running app with
   the update service; it installs non-stock images fine (Baud Girl), but it
   cannot save one that does not boot. `0xF0000000/"success"` is a terminal
   acknowledgement, not authorization.
3. **The `USB_KEY` clock is D+.**
   - czietz's Pico dongle clocks on D+ and has reached UBOOT mode on two FM-1s
     (issue #2, docs/10 §1.1).
   - kagaimiq's `usb-key.md` and the diagram in his `how-to-enter-uboot.md`
     agree; only that page's prose says D−.
   - Try D+ first, and keep both roles in the dongle.
4. **ghidra-jieli mis-decodes the `80 ff` long-call prefix**; use the vendor
   `objdump` from the JieLi Linux toolchain as the source of truth.
5. **Raw MIDI on Linux is unusable while PipeWire/JACK/aseq hold the port**;
   the updater and AL-255's client use the ALSA sequencer.
6. **Version numbers are inconsistent** between filenames, marketing (V09/V14/
   V15) and the identity string. Always read the identity.
7. **Do not send syscmd 33–36 or 48** or any `5A AA A5` online-tool frame; some
   copy memory or touch flash.
8. **Movy/Schwung are Linux-only by nature**; do not plan around porting them.
