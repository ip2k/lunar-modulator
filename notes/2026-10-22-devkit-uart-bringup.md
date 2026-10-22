# Dev-kit UART bring-up — 2026-10-22

## Objective and acceptance

Identify the received development board, capture its factory boot log, establish
the actual clock/memory configuration, then prepare a board-specific DSP timing
experiment. USB enumeration alone does not establish firmware performance or
authorize replacing the factory application. No target firmware writes so far.

## Observations

- [verified] Owner photo shows `JL_AC79_DevKitBoard V1.2`, dated `20230609`.
  Carrier exposes a `TX / PB3` row, 3.3V and GND. Core model/revision is not
  established by this photo. Do not substitute the older V1.0 documentation's
  chip identity for identification of this unit.
- [verified] Owner disconnected KA6 MIDI OUT from the carrier MIC IN. MIC IN
  is not a MIDI input. Board audio output is not connected to the KA6 yet.
- [verified] bench01 enumerates JieLi CDC `3654:5155`, serial
  `9127AF1910855C53`, at `/dev/ttyACM0`. An eight-second receive-only CDC
  capture before the Tigard connection received zero bytes. No protocol data
  was transmitted. This does not establish a failed boot.
- [verified] Tigard enumerates as `0403:6010`, product `Tigard V1.1`, serial
  `TG1108fc`. UART is
  `/dev/serial/by-id/usb-SecuringHardware.com_Tigard_V1.1_TG1108fc-if00-port0`
  (`/dev/ttyUSB0`); the second interface is not the UART.
- [verified] Both adapters are behind the same USB hub. JieLi re-enumerated
  from device 78 to 79 between observations; the cause is unestablished.
  Earlier kernel history contains hub overcurrent and descriptor errors.

## Receive-only UART setup given to owner

Disconnect USB power while wiring. Tigard voltage switch **VTGT**; UART pin 1
VTGT to carrier **3.3V**, pin 2 GND to **GND**, pin 4 RX to **TX / PB3**.
Leave TX, RTS, CTS and other interfaces disconnected. Reconnect USB, wait for
capture to be armed, then request one normal Reset press. No Update-button
sequence or firmware upload is part of this step.

[Tigard upstream documentation](https://github.com/tigard-tools/tigard#uart)
establishes UART pinout, first-interface selection, and target-powered VTGT
operation. [JieLi download guide](https://doc.zh-jieli.com/AC79/zh-cn/release_v1.0.3/getting_started/project_download/download.html)
and the pinned local SDK DevKitBoard configuration identify PB3 debug TX at
1,000,000 baud. [inferred] This factory image may use that configuration;
the boot capture must verify it. Start at 1,000,000 baud, 8N1, no flow control.

## Performance context and next dependency

The separate installable-firmware branch records a best physical diagnostic
run of 498.453089 64-frame blocks/s against 689.34375 required (27.69% short).
This is an FM-1 measurement, not a dev-kit result. A paired schema-7/schema-9
target build already exists on Aeon under
`/home/claude/mvave-fm1/resampler-stage-profile-pair-aeon-20261017-codex/`,
source `36988d0c2ef1b793e5f9d343fac1b9f6c4b7891f`. It has not run on this board.
Do not flash an FM-1 image onto a dev kit with different peripherals/memory.

Await owner wiring confirmation; arm receive-only capture before requesting
Reset. Preserve boot log in ignored research storage, summarize non-sensitive
hardware facts here. SWD/JTAG suitability is not established for pi32v2.

## Tool coverage

Rarefaction status and Serena initial instructions/current project were checked
on the primary absolute checkout. Their bounded `fm1_resampler_pop` navigation
agreed with the primary header. Rarefaction C has no root compilation database;
fallback analysis is not pi32v2 ABI or firmware code-generation verification.
The new worktree is separate; do not claim primary indices cover its edits.
No existing graph was found; no graph was built. No new agents were started.

Branch: `feature/2026-10-22@devkit-performance`, based on `659c3aa9`.
Raw USB evidence: ignored `scratch/devkit-20261022/` in this worktree.

## First captured reset

[verified] Owner moved the initial TDI connection to the separate UART RX
header, confirmed VTGT/GND/PB3 wiring, and pressed Reset once after capture
was armed. Capture opened exclusively at 1,000,000 baud, 8N1, no flow control,
DTR/RTS deasserted, with no serial writes. Raw capture is private on bench01:
`/home/claude/fm1-devkit-captures/uart-20261022T165500Z.bin`.

[verified] Readable factory boot output reports:

- `WL82(AC791N) CHIP_ID: 0x6f01`, setup build July 26, 2024.
- CPU 320 MHz; SDRAM 192 MHz; HSB 160 MHz; LSB 53,333,333 Hz;
  SFC 80 MHz. These are firmware-reported settings, not measured frequencies.
- SDRAM 8,388,608 bytes; heap 6,987,712 bytes; internal RAM accounting
  523,596 bytes with 421,452 remaining at startup.
- SDK banner `AC79NN SDK on branch [master]`, with July 2024 component builds;
  do not identify this as our pinned V1.2.13 without matching its provenance.
- SDFILE logical disk capacity 8192 KB; physical flash capacity/JEDEC ID
  is not independently established by that message.
- Display `dc->width : 320, dc->lines : 480`.
- DAC analog initialization succeeds. Demo later reports
  `1open_audio_dec_err!!!`; application UI and network activity continue.
- Reset reason `LOW POWER` is the literal firmware label; no conclusion
  about a brownout or wiring fault follows without further evidence.

UART bring-up is demonstrated. Lunar DSP performance is still unmeasured on
this dev kit. Next: preserve factory/recovery provenance and prepare a minimal
board-specific timing image without assuming FM-1 peripheral compatibility.
