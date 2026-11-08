# FM-1 board layer

Drivers for the FM-1's own peripherals, written for the SDK-free pi32v2
runtime and testable on a desktop. Every register access goes through a
`struct lunar_board_io` (`board_io.h`), whose enum is the complete allow-list;
the native backend (`lunar_board_native_io`, built only with `LUNAR_PI32V2`)
maps it to addresses and nothing else. Every poll has a caller-given limit.
No module enables an interrupt, touches P33, the watchdog, eFuse
(`0x13700`-`0x1371F`), the key-check mailbox or IRQ 123.

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

ALNK0 audio and the codec: the only codec init sequences found are in GPL
sources (docs/18 §4, on the release-plan branch
`feature/2026-10-29@fm1-release-plan`), so they stay out of this MIT layer. The `boot_info`
bridge stays in `firmware/third_party/fm1-nes/boot_compat.c` and is linked
only by SDK builds; the SDK-free M5 image has no `boot_info_init` to wrap.
