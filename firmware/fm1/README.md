# firmware/fm1: the FM-1 application image

The first complete Lunar application for the FM-1 (docs/18 M8–M11). It
builds and passes the offline gates. **No part of it has run on an FM-1 or on
the dev kit**; see `notes/2026-11-08-fm1-app-image.md` for the numbers and the
open items.

| file | what | licence |
| --- | --- | --- |
| `fm1_input.c/.h` | event queue, panel debounce and encoder detents, MASTER, TRS/USB-MIDI decoding, and the router to the app's fence-safe controls; portable C99, host-tested (`tests/test_fm1_input.py`) | MIT |
| `fm1_live.c/.h` | the audio adapter: the pipelined app at 44,118 Hz, cap 8 DX7 voices, arenas, the int16 conversion with a 50 ms fade-in; applies routed actions between blocks | MIT |
| `fm1_sdk_main.c` | the SDK glue: TIMER4, board I/O, boot screen, the producer, the ALNK0 interrupt, the panel/MIDI task, the recovery key combination, and fail-open heartbeats | MIT |

Built by `tools/jieli/prepare-fm1-app.py` (on top of the dev-kit pipeline tree:
cap8, trunc12, `--size-profile`) and `tools/jieli/fm1-app.mk`, which swaps
the kit's test workload for these files and the board layer
(`firmware/board`, `firmware/display`, fm1-nes's key tables). On a LAN node:
`TOOLCHAIN=… tools/jieli/build-fm1-app-on-aeon.sh R NAME SESSION GPL`.

## What it does

- **Boot** [inferred: SDK source and the prepared tree; not run]: the stock
  SPL starts the app; fm1-nes's `boot_info` bridge (`--wrap=boot_info_init`,
  checked in the disassembly) gives the V1.2.13 libraries the words they
  expect. `setup_arch` counts the boot (fail-open). `app_main` honours the
  recovery combination, starts the supervisor, and starts `lunar_fm1_main`.
- **Screen**: backlight on (PA2, active low), the M5 test pattern labelled
  "LUNAR FM-1" over SPI1 [reported pins: Felucca, fm1-nes]. There is no UI
  framebuffer yet (the app's 115,200 B TFT buffer does not fit beside the
  audio), so the screen does not follow the app.
- **Audio**: four sounds as in the dev-kit pipeline (S1 DX7 WARM PAD, S2
  Macro VA, S3 drums, S4 DX7 SAW LEAD), sound 1's filter and drive inserts,
  echo and compressor; eight blocks prefilled; ALNK0 (I2S to the external
  codec, IRQ 11, CPU0), 64-frame halves [reported: Felucca, fm1-nes]. The
  pipeline runs without the kit's lifetime bound (`LUNAR_PIPELINE_UNBOUNDED`);
  its 32-bit block tag lasts about 72 days of continuous audio at 44,118 Hz
  before the pipeline refuses the reserved tag 0xffffffff [inferred: 2^32 ×
  64 / 44,118 s ≈ 6.2 million s]; the main task then resets the unit through
  fail-open (fault `0x47`). A tag wrap is a later fix.
- **Controls** (sim/web's mapping, limited by the pipelined app's fence):
  keys play sound 1 at velocity 100 from F3 (note 53); OCT−/OCT+ shift ±3
  octaves; KNOB1 sets sound 1's filter cutoff in semitone steps (20–18,000
  Hz); KNOB2 its resonance in 0.05 steps; MASTER sets the output level.
  Every other button and encoder is counted as deferred.
- **MIDI in** (TRS, UART1 RX on PH8 [reported: Felucca]): note on/off on
  channels 1, 3 and 4 play sounds 1, 3 and 4; channel 2 (sound 2) is
  deferred; other channels play sound 1. CC 7 is MASTER, CC 123 all notes
  off. Pitch bend is deferred.
- **USB-MIDI**: not in this image. The decoder (`lunar_fm1_usb_midi_packet`)
  is written and tested, but the image has no USB device stack, so the unit
  does not enumerate as `4C4A:C755` and the stock OTA update path is absent.
- **Recovery**: fail-open boot counter (three unhealthy boots lead to mask-ROM
  update mode), a heartbeat supervisor over the main task (5 s) and the
  panel task (2 s), a reset with fault `0x41`–`0x47` on any startup or
  run-loop failure, and a proposed key combination: OCT− and OCT+ held alone at power on. Whether the fail-open
  record survives a warm reset under the FM-1's stock SPL is [inferred];
  docs/17 is the proven route.

## Known gaps (TODO markers in the source)

- `TODO(app)`: the pipelined app refuses `fm1_app_key`, `_button`,
  `_encoder`, `_pitch_bend` and `_all_notes_off` while a block is in flight
  [verified: `PIPELINE_GUARD(!pipeline_busy())` in sim/web/src/fm1_app.c],
  which is nearly always while audio runs. The full panel UI, sound 2's
  notes and pitch bend need that fence widened.
- `TODO(hardware)`: button labels 2–11, encoder direction, edges per detent,
  the 10 ms scan rate for fast turns, LED drive, battery scaling, and every
  pin and peripheral fact still [reported] from other projects.
- `TODO(owner)`: the recovery key combination; whether the debug UART's PB3
  TX should be kept (off by default; `--debug-uart pb3`).
