# 08 — Roadmap

Phases with exit criteria. Phase 0 is done; nothing else has started.

## Phase 0 — Research (done, 2026-09-06)

Findings in docs/01–07. Deliverable: this repository.

## Phase 1 — Bench characterization, read-only

Detailed commands in docs/09.

- USB descriptors in normal mode; confirm `4C4A:C755`, MIDI and UAC1 interfaces.
- SysEx identity query and decoded identity (`FM-1_0xx`).
- Extract the V15 `.fwsc` from `M-UPGRADE-FM1.app`, unpack it, diff against V14
  (sizes, hashes, strings, msfa table, new feature strings such as glide).
- Optional: capture a stock update session (M-UPGRADE re-flashing the current
  version) with a MIDI monitor to validate AL-255's protocol client on this
  unit — the stock path is proven, but note it re-writes the app bank.
- Photos: chip marking, U2/U3/U5/U9/U11 markings, J12 pin count, knob types,
  the USB-C to SoC routing.
- **Exit:** notes/ contains descriptors, identity, V15 analysis, photos; the
  knob/encoder question is answered.

## Phase 2 — Recovery

- Build the RP2040 `USB_KEY` dongle from docs/10 (firmware in `dongle/`, UF2
  from CI, logic tested against a ROM model); rehearse on an AC791N dev board
  if one can be bought (JL_AC79_DevKit V1.0 on Taobao), otherwise proceed
  carefully on the FM-1 following docs/10 §6.
- Reach `UBOOT1.00`; record VID:PID, the SCSI inquiry string, the exact key
  polarity and timing that worked, the power-switch sequence.
- Extend `jl-uboot-tool` for wl82 if needed (read-only first): chip ID, flash
  JEDEC ID, full 1 MB dump ×2 (must match), compare to the stock package.
- Restore the dump; boot; dump again; compare. Then, and only then, write a
  deliberately altered byte in a harmless region and restore it.
- Write `docs/10-recovery-procedure.md` with photos and exact commands.
- **Exit:** two byte-identical dump/restore cycles on the FM-1.

## Phase 3 — First custom code

- Install the JieLi Linux toolchain and post-build tools; build the SDK's
  `demo_hello` for AC791N (`make ac791n_demo_demo_hello`).
- Create a `board_fm1.c` from AL-255's hardware map: SPI1 display pins, key
  matrix ports, encoder/ADC pins, DAC, UART on the MIDI TRS jack for logging.
- Flash via mask-ROM USB; confirm UART log; blink the key LEDs; draw on the TFT.
- Add the fail-open boot path (key combo held at power-up → USB update mode)
  and a watchdog failure counter. Test both.
- **Exit:** "hello" firmware runs, logs, and can always be replaced.

## Phase 4 — The synth

- Port Synth_Dexed `EngineMsfa` (or msfa directly) to pi32v2 with the JieLi
  toolchain (C++11, no exceptions/RTTI; AL-255's branch already did the host
  build and shims).
- DAC output through the SDK audio path or a direct DMA ring (AL-255 recovered
  the DAC SFRs); 44.1 kHz, 64-sample blocks; measure voice count vs. CPU.
- USB-MIDI class device (SDK `usb.h`), UART MIDI, DX7 SysEx bulk/single/param
  messages; program change, CC map compatible with stock where sensible.
- Preset storage in flash (32-voice VMEM banks), factory bank from any DX7
  ROM `.syx` the user provides (do not ship M-VAVE's bank).
- **Exit:** plays DX7 banks from a DAW over USB, on par with stock polyphony.

## Phase 5 — UI, sequencer, effects

- Parameter pages on 8 knobs following Movy's model (docs/06); envelope and
  algorithm graphics on the 240×240 TFT; oscilloscope view like stock.
- Arpeggiator; step sequencer with Movy-style step parameters; optional
  desktop harness diffing against Movy's `seq-core`.
- Effects: filter, reverb, delay, chorus, phaser, distortion (open-source DSP;
  e.g. Freeverb/Dattorro, simple SVF) — or the SDK's `lib_reverb_cal.a` at L1.
- BLE-MIDI via the vendor stack (L1) — decide whether to keep it.
- **Exit:** daily-usable instrument; manual in `docs/`.

## Phase 6 — Distribution

- Install over the stock OTA path so stock units can take the open firmware
  over USB-MIDI. Echomatter showed (2026-09-04) that a package with a bumped
  version identity is accepted, and Baud Girl's browser installer (docs/04)
  has done it publicly since 2026-09-26. The remaining work is our own
  client: start from AL-255's `fm1_ota.py` with PR #2's framing fix and
  `build_fwsc.py`, plus a check that the flash head equals stock (the loader
  can rewrite it) and resume from the loader. Alternatively publish the
  dongle design and a "one-time unlock".
- Reversible: the tool must restore stock (users keep their `.fwsc`).
- Release process, versioning, changelog; coordinate with aroum and AL-255.

## Phase 7 — Deeper openness (long term)

- Replace `uboot.boot` with a build of JieLi's Apache-2.0 `fw-Bootloader`.
- Remove `.a` dependencies one by one: UI (`ui.a`) first, then `fs.a`, audio
  server, `system.a`/`cpu.a` — against `WL82.h` and kagaimiq's peripheral docs.
- Toolchain: document the pi32v2 ISA formally from the vendor objdump +
  ghidra-jieli; fix ghidra-jieli's `80 ff` long-call decoding; evaluate an LLVM
  backend as a separate project.
- Second core: offload effects or the UI.

## Research items (any time)

- Verify the algorithm 4/6 `0x41` variant against upstream Dexed's
  `Source/msfa/fm_core.cc`; check whether any GPL-only Dexed/Synth_Dexed code
  (e.g. `PluginFx`, compressor) is present in the stock app.
- Read fm1-editor.com's JavaScript for the exact patch SysEx and any vendor
  extensions beyond DX7.
- Confirm flash size and whether it is in-package (JEDEC ID from UBOOT mode).
- Identify the AC791N variant and pinout; document the FM-1 pin assignment.
- Understand how the syscmd callback table (`ENG+1336`/`ENG+1400`) is populated.
- Ask aroum and AL-255 whether they want to pool efforts; both repos were
  active in August 2026.
