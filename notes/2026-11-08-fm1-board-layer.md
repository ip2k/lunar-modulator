# 2026-11-08: the FM-1 board layer (M3) and the M5 test-pattern image

Milestone M3 of docs/18 (on `feature/2026-10-29@fm1-release-plan`) is "the
FM-1 board layer on main". This stream adds that layer (audio is the separate ALNK0
driver from #176, merged here) and
builds the M5 test-pattern RAM image. **No hardware was touched.** No traffic
went to the FM-1 or the dev kit, and the M5 image has not been loaded or run
anywhere.

## What was built

| Piece | Where | Source |
| --- | --- | --- |
| SPI1 ST7789V transport (CS PC7, D/C PC8, SCK PC9, MOSI PC10) | `firmware/display/spi1_transport.*` | Codex, MIT, verbatim (`85348309`) |
| TIMER4 bounded delay | `firmware/timing/` | Codex, MIT, verbatim (`c45c3963`) |
| Register allow-list and native backend | `firmware/board/board_io.*` | own |
| 595 matrix (PA4/PA3/PA1 out, rows PA0, PA5-PA8, PB7), LEDs (PA9, PA10, PH6, PH9), PA2 | `firmware/board/matrix.*` | own, Felucca/fm1-nes facts |
| 41 keys and 7 encoders | `firmware/third_party/fm1-nes/fm1_keys.*` | fm1-nes, Apache-2.0, re-indexed |
| MASTER pot ADC 4 (PB6), battery ADC 3 (PB1) | `firmware/board/adc.*` | own, SDK and fm1-nes facts |
| TRS MIDI in: UART1 RX DMA on PH8, running-status parser | `firmware/board/midi_uart.*`, `midi_parser.*` | own; drain adapted from Codex's MIT `midi_uart_stream.c` (`66196f54`) |
| M5 pattern and RAM entry | `firmware/display/m5_pattern.*`, `firmware/m5/` | own; link script adapted from Codex's MIT `ram-recovery` (`62ef114d`) |
| `boot_info` bridge | `firmware/third_party/fm1-nes/boot_compat.c` | already on main; not linked by the SDK-free M5 image |

`firmware/board/README.md` has the per-file provenance and the fact table with
confidence marks.

**Licence sort.** The following were not used:

- Felucca, SLOOP and dinghy (GPL-3.0-only), including Codex's
  `firmware/native/app_probe.c` and `firmware/third_party/dinghy/`. Felucca was
  read only for facts, which were re-implemented: the port, IOMAP and UART1
  values, the read-modify-write shift edges, the LED lines and the 41-key
  physical map that the relabelling was checked against.
- The Arduino MIDI library on Codex's branch. It is MIT, but the parser here is
  shorter, our own, and needs no C++.

**PR #161 overlap.** `firmware/native/diagnostic_display.*` is a host-side
row-lease layer with no transport. Its submit step would sit on
`spi1_transport`, so nothing is duplicated. Aligning the two is a follow-up
once both are on main.

## Evidence

**Host tests** (desktop clang, through a register model in
`firmware/board/host/board_sim.c`). `tests/test_board_layer.py` has 30 tests:

- every register the layer may touch is on the allow-list;
- 595 column words, init, and read-modify-write on every edge;
- each of the 41 keys alone, chords and scan order, and the table against
  fm1-nes's after relabelling;
- LED lines and PA2;
- all 7 encoders both ways, plus invalid jumps;
- ADC sequence, refusal and timeout, and the pot filter;
- the MIDI parser: running status, realtime inside messages, SysEx skipping,
  system common;
- UART configure refusals, poll, wrap and overrun;
- the M5 stream, pinned by hash: id `8d790e30 2026-11-08`, 230,580 sink
  bytes, SHA-256 `81b6a731…cc379fe`. Setting `LUNAR_M5_PNG` writes the pattern
  as a PNG, and it was looked at: no clipped or overlapping text.

`tests/test_spi1_transport.py` and `tests/test_timer4_delay.py` came with the
harvested code. `tests/test_diagnostic_report_ram.py` covers the new `ram`
report profile. Together with `tests/test_diagnostic_report.py`, these five
files gave 99 passed.

**pi32v2 build.** The build ran on the LAN build host (container
`lunar-jieli-check:bookworm`, JieLi toolchain `jieli-linux-toolchains-20250324.1`,
`clang version 4.0.1`) from commit `20297df8`. Command:
`LUNAR_SESSION=fm1-wave1-board-layer bash tools/jieli/link-diagnostic.sh
<host> <toolchain> <scratch> m5-test-pattern`. Results:

- `audit_link.py --runtime sdk-free`: **PASS (0 fail, 0 pending, linked)**.
  It found no eFuse SFR, no key-check mailbox, no IRQ 123, no key blob and no
  SDK library.
- `diagnostic_report.py` profile `ram`:
  - entry and `_start` at `0x01c02000`;
  - `.image` 4,176 bytes, `.bss` 216, two 4,096-byte stacks with 16-byte
    guards;
  - 12,624 of 16,384 bytes reserved, no unresolved symbols, `device_execution:
    unverified`.
- Symbols: `lunar_m5_status` at `0x01c03050` (68 bytes), `lunar_m5_main` at
  `0x01c020d4`. No `memcpy`, `memset` or division, multiplication or shift
  helpers.
- Build id in the binary: `20297df8 2026-11-08`.
- SHA-256: `m5.bin` `cbe5f13cb1097de3f132d8565ab032ae3d82f2f97a1930ae039456704825c992`,
  `m5.elf` `010071ffb42d516332fb1d34083b2904b4d650b71f80ad33ec57af6329f5a425`.
- Compile-only objects need only board symbols. `adc` needs
  `lunar_board_change` and `lunar_board_io_valid`; `midi_uart` needs those and
  the parser; `midi_parser` needs nothing.

The build products were deleted after these figures were recorded. Rebuild
with the same command to reproduce them; the hashes depend on the build id,
which is the commit and the date.

## Limits and open questions

1. **Nothing has run.** M5 needs M4 (a bounded RAM runner on the kit) and a
   docs/07 §4 approval for the FM-1. RAM load-and-jump through the ROM is
   untested on WL82 (docs/18 §4).
2. **RAM ownership.** `0x01c02000` is the window `firmware/diagnostic` and
   `firmware/handover` already reserve. It overlaps the stock SPL body's load
   range `0x01c02000..0x01c05820`. What the ROM's RAM upload path itself uses
   is unknown. The window is a link budget, not a proven contract.
3. **TIMER4.** M5 reads TIMER4's control word into its status block, stops the
   timer, and binds at 40 MHz. Stock V15 selects 24 or 40 MHz [verified:
   `firmware/timing/README.md`], and Felucca reports 24 MHz under ROM/UBOOT
   [reported]. A 40 MHz bind makes every delay at least as long as asked (1.67
   times as long at 24 MHz).
   - At 360 MHz, 65,536 polls may run out before a 40,000-tick period. M5 then
     latches `timer_fallback` and spins 20,000 loops per millisecond,
     uncalibrated.
   - Panel waits use the same fallback, so a timer fault cannot abort the
     panel stream.
4. **Watchdog.** M5 does not feed or disable it. If the ROM or SPL leaves it
   armed (stock sets the 4 s period, `notes/2026-10-09-lcd-runtime-prerequisites.md`
   [inferred]), the unit resets after about 4 s. That is safe, but the blink
   code would be cut short.
5. **PA2.** It is driven low before the panel, as fm1-nes and stock do
   [reported]. Whether it is the backlight, a reset or an enable is not
   established.
6. **Key tables** come from fm1-nes's stock `FM-1_010` analysis. They agree
   41/41 with Felucca's independent map, but have not been re-derived from V15.
   The clockwise sign of the encoders is unknown.
7. **UART1 HRXCNT.** Treating HRXCNT as the count since the last latch is
   Felucca's use [reported]. The pinned SDK never reads HRXCNT.
8. **Audio is a separate driver.** ALNK0 audio is `firmware/board/alnk0_audio*.c`
   (clean-room, MIT, #176, `notes/2026-11-08-alnk0-codec-driver.md`). Its finding
   is that the FM-1's DAC needs no register setup, so the earlier blocker (the
   only known codec init sequences are GPL, docs/18 §4) does not apply. It has
   its own ops-based register set, not `struct lunar_board_io`, and has not run
   on a chip. Open: the DAC part, wire format, amplifier enable, real rate.
9. **M2 is not exercised.** The `ram` report checks the image against its own
   16 KiB window, not the size and SRAM gate docs/18 calls M2.
10. **Toolchain.** The LAN build host has the 20250324.1 toolchain, not the
    20250805.1 pin named elsewhere.
11. Host tests compile with the desktop compiler, so pi32v2 code generation is
    checked only by the link, the audit and a read of the disassembly.
