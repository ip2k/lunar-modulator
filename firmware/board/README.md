# FM-1 board layer

Drivers for the FM-1's own peripherals, written for the SDK-free pi32v2
runtime and testable on a desktop. In the board_io modules (`board_io`,
`matrix`, `adc`, `midi_uart`) every register access goes through a
`struct lunar_board_io` (`board_io.h`), whose enum is the complete allow-list
for those modules; the native backend (`lunar_board_native_io`, built only
with `LUNAR_PI32V2`) maps it to addresses and nothing else. The ALNK0 audio
driver is separate and has its own ops-based register set (`alnk0_audio.h`,
see "ALNK0 audio" below): ALNK0 CON0-CON3, the per-channel ADR registers and
LEN at `0x12E00`-`0x12E20`, CLK_CON2 (`0x10014`), IOMAP CON5 (`0x51030`) and
the PORTC OUT, DIR, PU and PD registers, all reached only through the
caller's `ops`. Every
poll has a caller-given limit. The board_io modules enable no interrupt and
touch no P33, watchdog, eFuse (`0x13700`-`0x1371F`), key-check mailbox or
IRQ 123; the audio driver attaches IRQ 11 through the caller's `ops`.

**Status: built for pi32v2 and host-tested; nothing here has run on an FM-1
or the dev kit.** See `notes/2026-11-08-fm1-board-layer.md` for the evidence
and the open questions.

## Files and provenance

| File | Licence | Origin |
| --- | --- | --- |
| `board_io.{c,h}` | MIT | Lunar, from WL82.h addresses |
| `matrix.{c,h}` | MIT | Lunar; pin facts below |
| `adc.{c,h}` | MIT | Lunar; sequence facts from the SDK's `adc_api.c` and fm1-nes `fm1_volume.c` (both Apache-2.0, nothing copied) |
| `midi_parser.{c,h}` | MIT | Lunar, from the MIDI 1.0 message lengths |
| `midi_uart.{c,h}` | MIT | Lunar; `lunar_midi_uart_drain` adapted from Codex's MIT `firmware/native/midi_uart_stream.c` (branch `feature/2026-10-11@installable-firmware`, commit `66196f54`); register facts below |
| `host/board_sim.c` | MIT | Lunar test double, host only |
| `../third_party/fm1-nes/fm1_keys.{c,h}` | Apache-2.0 | fm1-nes key and encoder tables and sampler, re-indexed (its `UPSTREAM.md`) |
| `../display/spi1_transport.{c,h}` | MIT | Codex, verbatim from `feature/2026-10-11@installable-firmware` (`85348309`, tip `cccd21cc`) |
| `../timing/timer4.{c,h}`, `README.md` | MIT | Codex, verbatim from the same branch (`c45c3963`) |
| `../display/m5_pattern.{c,h}` | MIT | Lunar; glyphs drawn here |
| `../m5/startup.S`, `app.ld` | MIT | adapted from Codex's `firmware/ram-recovery/` (`62ef114d`) |

Nothing here comes from Felucca, SLOOP or dinghy (GPL-3.0-only). Facts marked
"Felucca" below were read from Felucca's HAL as facts and re-implemented; no
code, structure or comments were copied. Codex's `firmware/native/app_probe.c`
and `firmware/third_party/dinghy/` are GPL and were not used.

M5 assumes reset-state peripherals: the code sets up only what it uses
(PA2, TIMER4, SPI1, the 595 pins). Stock clocks the 74HC595s on SPI2; here they
are bit-banged, and nothing configures SPI2 or the clock tree.

## Fact table

| Fact | Mark |
| --- | --- |
| Port registers OUT, IN, DIR, DIE, PU, PD, HD0, HD, DIEH at +0..+0x20; PORTA `0x50000`, PORTB `0x50040`, PORTH `0x501C0`; DIR bit 1 = input | [verified: WL82.h] |
| IOMAP CON2 `0x51024`, CON3 `0x51028`; CLK_CON1 `0x10010`; UART1 `0x12100` (16-bit CON0/CON1/BAUD/HRXCNT, OTCNT +0x10, RXSADR +0x1C, RXEADR +0x20, RXCNT +0x24, HRXCNT +0x28); ADC `0x13100` (CON, RES); ANA WLA_CON0 `0x11900`, PLL_CON1 `0x119A4` | [verified: WL82.h] |
| 74HC595 data PA4, clock PA3, latch PA1; 16-bit word MSB first, active-low column, columns 0 and 1 also pull outputs 11 and 12 low | [reported: Felucca, fm1-nes] |
| Each shift edge is a read-modify-write: write-only edges were too short and latched the neighbouring column | [reported: Felucca] |
| Rows PA0, PA5-PA8, PB7, pulled up, low = closed; pack `(a&1)\|((a>>4)&0x1e)\|((b>>2)&0x20)` | [reported: fm1-nes, Felucca] |
| 41 key cells and 7 encoders (SELECT, ALGORITHM, KNOB1-4, PRESETS), physical column = (fm1-nes label + 10) % 11 | [reported: fm1-nes from FM-1_010]; relabelling [verified here: 41/41 against Felucca's physical map] |
| Encoder A bit0/B bit1 active low, +1 mask `0x2814`, -1 mask `0x4182`, two identical samples per decode; clockwise sign unknown | [reported: fm1-nes] |
| LED lines PA9, PA10, PH6, PH9, active high, high drive, lit while their column is selected | [reported: Felucca] |
| MASTER pot ADC channel 4 (PB6), battery channel 3 (PB1); battery thresholds 531/561/591 (not used in code) | [reported: Felucca, fm1-nes] |
| ADC CON: /96 (`0b110`), bit 3, channel bits 8-11, start delay `0xF << 12`, enable bit 4, kick bit 6, done bit 7, 10-bit RES; analog bias via WLA_CON0 and PLL_CON1 bit 16 | [verified: SDK `adc_api.c`] |
| Pot filter: ±6 deadband, 10 consecutive excursions, level = raw >> 3 | [reported: fm1-nes, from stock] |
| UART1 MIDI: CLK_CON1[11:10] = 1 (48 MHz PLL), IOMAP CON3[7] = 0 and [6:4] = 5, IOMAP CON2[13:8] = 49 (PH8), BAUD 383, OTCNT 60000, CON0 `0x3400` stop then `0x40\|0x80\|0x1000\|0x400` then bit 0 | [reported: Felucca] |
| HRXCNT after a CON0 bit 7 latch counts the bytes received since the previous latch | [reported: Felucca's use; the pinned SDK has no user of HRXCNT] |
| PA2 low before panel output (backlight, reset or enable: not established) | [reported: fm1-nes; stock V15 drives it] |
| TFT on SPI1: CS PC7, D/C PC8, SCK PC9, MOSI PC10, CON `0x4021`, BAUD 4 | [verified: stock V15 decode, notes/2026-10-09] |

## Not here

Audio is not part of the board_io modules: it is the separate ALNK0 driver
below (clean-room, MIT, #176). That work found that the FM-1's DAC needs no
register setup, so no codec init sequence is needed and the earlier concern
that the only known sequences were GPL no longer applies. What is still open
is the DAC part number, the wire format, any amplifier enable and the real
rate. The `boot_info`
bridge stays in `firmware/third_party/fm1-nes/boot_compat.c` and is linked
only by SDK builds; the SDK-free M5 image has no `boot_info_init` to wrap.

## ALNK0 audio

`alnk0_audio.c` brings up the FM-1's audio output: ALNK0 (I2S, `0x12E00`)
as master with MCLK out on PC0, the bit and word clocks on PC1 and PC2, and
channel 3 sending 24-bit words on PC6. That is all the FM-1's DAC needs: it
takes no configuration over I2C or SPI, so there is no codec register setup
to do. The part itself is not identified yet. Evidence, the register facts
(F1–F22) with their sources and confidence marks, and the design choices are
in [`notes/2026-11-08-alnk0-codec-driver.md`](../../notes/2026-11-08-alnk0-codec-driver.md).

Licence: MIT. The order of operations follows JieLi's Apache-2.0 AC79 SDK
driver (V1.2.13, read as IR). Felucca, SLOOP and M-VAVE's `fm1_open` (all
GPL) were used for facts only, and none of their code is here. No fm1-nes
code is here either.

| File | What it is |
| --- | --- |
| `alnk0_audio.h` | Addresses, the `ops`/`config` structs, the API |
| `alnk0_audio.c` | `start`, `stop`, the ISR helpers, the Q23 word packer. Accesses registers only through the caller's `ops` |
| `alnk0_audio_mmio.c` | Volatile register accessors and the `csync` barrier, for pi32v2 builds only |

How the target uses it:

```c
static int32_t audio_buf[2 * LUNAR_ALNK0_HALF_WORDS] __attribute__((aligned(32)));
struct lunar_alnk0_ops ops = { 0, lunar_alnk0_mmio_read, lunar_alnk0_mmio_write,
                               lunar_alnk0_mmio_sync, my_attach_irq, my_delay_ms };
struct lunar_alnk0_config cfg;
lunar_alnk0_default_config(&cfg, audio_buf, (uint32_t)(uintptr_t)audio_buf);
int rc = lunar_alnk0_start(&ops, &cfg);   /* 0, or a negative LUNAR_ALNK0_E* */
```

In the IRQ 11 handler, `lunar_alnk0_pending` returns bit 3 when channel 3
has finished a half. `lunar_alnk0_free_half` says which half (0 or 1) to
refill, with 128 words of L/R interleaved samples, each passed through
`lunar_alnk0_word_from_q23`. Then `lunar_alnk0_ack(ops, 1u << 3)`. Words are
signed 24-bit values in 32-bit containers.

Status:

- The host tests in `tests/test_alnk0_audio.py` check the exact register
  sequence against `tests/fixtures/alnk0/lunar_start.json`.
- The code compiles with JieLi's pi32v2 clang 4.0.1 at `-Os -Werror`.
- **It has not run on a chip.** The first run belongs to M3/M6 in docs/18.
  It needs the runtime's IRQ attach and delay, and a capture of the output
  through the KA6.
- Open questions, listed in the note's §7: the DAC part number, whether the
  wire format is I2S or left-justified, any amplifier enable or mute line, and
  a measurement of the real rate (about 44,118 Hz).
