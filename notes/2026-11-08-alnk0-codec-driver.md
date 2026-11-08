# ALNK0 audio output and the FM-1's DAC: facts, and a clean-room driver

2026-11-08, wave 1 lane "codec" toward Lunar 1.0 on the FM-1 (docs/18, M3).
Source reading, one photo inspection and a pi32v2 compile on the LAN build
host. **No hardware was used: nothing was sent to the FM-1 or the dev kit.**

Marks as in CLAUDE.md: **[verified]** checked here against bytes, photos or
SDK files; **[reported]** a named source, not re-checked; **[inferred]** our
reasoning.

## 1. Result

1. **The FM-1's audio part takes no configuration.** None of the four code
   bases that drive this board's audio writes a codec register over I2C, SPI
   or anything else; each one only clocks ALNK0 out on PC0, PC1, PC2 and PC6
   [verified: source reading of all four, §2]. Stock V15's application image
   has no codec part name and no codec driver string: the only audio-link
   strings are `alnk`, `iis`, `iis0`, `iis1` [verified: `strings` over the
   decrypted V15 image]. So the part behind ALNK0 is a **control-less,
   pin-strapped I2S DAC that locks to MCLK** [inferred, strong]. "Codec init"
   on the FM-1 is therefore the ALNK0 bring-up and nothing more.
2. **The part is still unidentified.** `U9`, the part between the SoC and
   `U5`, has **10 leads (5 a side)**, not the 8 that docs/01 and the
   2026-09-29 note gave it [verified: crop of `photos/2026-09-29/3-top.jpg`;
   pin-1 dot top left]. Its marking is not legible at that resolution, and
   the SoC close-up cuts it off at the edge. A 10-lead control-less stereo
   DAC that needs MCLK fits the evidence; the CS4344 family (TSSOP-10, MCLK
   in, ratio auto-detect) is one such class [inferred, a candidate only].
   `U5` (QFN, 16 leads visible in the same crop, ferrites `FB4`/`FB5`, next
   to the jacks) is most likely the headphone/speaker amplifier [inferred].
   Reading both markings needs the board out and a loupe.
3. **The PC6 conflict is settled.** The SDK's own I2S driver maps
   `IIS_PORTC` to data channels 0-3 on PC3, PC4, PC5, PC6 and the clocks to
   PC0, PC1, PC2 (MCLK, SCLK, LRCK) [verified: SDK `iis.c` IR, §3], and M-VAVE's
   own board header says "PC0 MCLK, PC2 LRCLK, PC1 SCLK, PC3 clock/RX, PC6
   DAC" [reported: M-VAVE `fm1_open`]. So PC6 is channel-3 serial data and
   PC0-PC2 the clocks: fm1-nes was right, and Felucca's "codec control lines"
   comment was a misreading of pins that ALNK0 drives.
4. **No source drives an amplifier enable or mute line** [verified: the four
   sources]. If the board has one, it is strapped or unknown; a pop at
   power-up or a hardware mute is untested (M6).
5. **A clean-room MIT driver** (`firmware/board/alnk0_audio.c`) emits the
   ALNK0 bring-up as an ordered list of register operations through
   caller-supplied callbacks, built from the facts table in §3 with the SDK's
   driver as the source of the order. A host test checks the exact sequence
   and the clock invariants against `tests/fixtures/alnk0/lunar_start.json`.
   It compiles with JieLi's pi32v2 clang (§6). It has not run on any chip.

## 2. Sources read

| Source | Licence | Commit / version | What it gave |
| --- | --- | --- | --- |
| JieLi AC79 SDK `iis.c`, shipped as LLVM bitcode `iis.c.o` in `cpu/wl82/liba/cpu.a` | Apache-2.0 (the SDK) | Gitee `release/AC79NN_SDK_V1.2.0` at `e30b1ee` (= V1.2.13), pinned in `tools/jieli/compile-check.sh` | Register order and bit meanings of `iis_open`, `iis_set_sample_rate`, `iis_channel_on/off`, `iis_irq_handler`; the port pin table. Read as IR (`clang -x ir -S -emit-llvm` in the build container); the IR and object stay off the repository |
| AC79 SDK headers `WL82.h`, `iis.h`, `hwi.h`, `gpio.h` | Apache-2.0 | same tree (sparse copy in `reference/ac79-sdk`) | Register addresses, `IRQ_ALNK_IDX` 11, `IO_GROUP_NUM` 16, the `iis_platform_data` fields |
| M-VAVE `fm1_open` `app/board/fm1_audio.h`, `audio.c` | GPL-3.0-only with a linking exception | `4c7496daac04a95ff10d1afdcc8f9ead2dbabc41` (2026-10-21) | Pin roles, 11.2896 MHz/256 fs comment, 44,118 Hz hardware rate, register values, Q23 sample range. Facts only |
| Felucca `firmware/hal/fm1_audio.h`, `src/audio.c` (hugelton) | GPL-3.0-only | `b0dcd53a251d5f5392fea9478b48244d322eeb2a` | Register values, 5 ms settle, Q15 << 7 sample scaling. Facts only |
| SLOOP `firmware/hal/fm1_audio.h` (isod89) | GPL-3.0-only | `f2b44c219b8a4ac00bc06dca756cdae8a259dd1a` | Byte-identical to Felucca's file [verified: `diff`]; not an independent source |
| fm1-nes `firmware/nes/src/fm1_wl82.c` (Keitark) | Apache-2.0 | `870f3054869c77f03fc1c8a3a425dafa3dfa7b22` | The SDK `iis_*` configuration it passes: channel 3, MCLK out, `update_edge` 0, `f32e` 0, `sr_points` 128, 44,100 Hz, 24-bit |
| Stock V15 `FM-1_015` application, decrypted (`scratch/`, not committed) | M-VAVE, proprietary | the CDN package of 2026-09-06 | No codec part name, no codec driver; `alnk`/`iis` strings only |
| Owner's PCB photos `photos/2026-09-29/` | ours | — | `U9` lead count |

The two GPL code bases were read for facts and closed before the driver was
written. The driver's shape (callback ops, mask-wide pin writes, validation,
stop order) is ours; its order follows the Apache-2.0 SDK, and Felucca and
M-VAVE appear below only as agreeing or differing witnesses.

## 3. Facts table

SFR addresses from `WL82.h` [verified]: `map_adr(g, a) = (64·g + a)·4`;
ALNK0 = LSB `0x10000` + group `0x2e` = **`0x12E00`**; CLOCK `0x10000`,
`CLK_CON2` at +0x14 = **`0x10014`**; IOMAP `0x50000` + `map_adr(0x10, 7)` =
`0x5101C`, `CON5` at +0x14 = **`0x51030`**; PORTC `0x50000` + `0x20·4` =
**`0x50080`**, with `OUT` +0, `DIR` +8, `PU` +0x10, `PD` +0x14.

| # | Fact | SDK `iis.c` (Apache) | M-VAVE | Felucca/SLOOP | fm1-nes | Mark |
| --- | --- | --- | --- | --- | --- | --- |
| F1 | ALNK0 layout: `CON0` u16 +0, `CON1` u16 +4, `CON2` u8 +8, `CON3` u8 +0xC, `ADR0..3` u32 +0x10..+0x1C, `LEN` u16 +0x20 | `JL_ALNK_TypeDef` | same | same | — | [verified] |
| F2 | IRQ index 11 (`IRQ_ALNK_IDX`) | `hwi.h` | 11 | 11 | via SDK | [verified] |
| F3 | Port group C for ALNK0: clear `IOMAP_CON5` bits 6 and 7 (A: bit 6 set; G: bit 7 set) | `iis_open`, `port_sel` switch, index 0 | clears bits 6-7 | clears `0xC0` | `IIS_PORTC` | [verified] |
| F4 | Port C pins: data ch0 PC3, ch1 PC4, ch2 PC5, ch3 **PC6**; MCLK **PC0**; then PC1, PC2 | `iis_data_port[1]` = `0x23 0x24 0x25 0x26 0x20 0x21 0x22` (GPIO numbers, 16 per port, so 0x23 = 35 = PC3) | PC1 SCLK, PC2 LRCLK | drives the same four | ch3 | table [verified]; SCLK/LRCK order [reported: M-VAVE] |
| F5 | Master mode: `CON3 \|= 3`, then `CON0 \|= 0x80` | yes | `CON3 = 3 \| 4<<5`, `CON0 = 0x180` | same bits | `slave_mode` 0 | [verified] |
| F6 | `CON0` bit 8 = MCLK out | `mclk_output` | set | set | `mclk_output` 1 | [verified] |
| F7 | `CON0` bit 6 cleared always; its meaning is unknown | `&= ~0x40` | 0 | `&= ~0x40` | — | [verified]; meaning open |
| F8 | `CON0` bit 10 = `update_edge`, bit 9 = `f32e` (32 SCLK per frame); both 0, so **64 SCLK per frame**, data changes on SCLK's falling edge | yes, per `iis.h` comments | 0 | cleared | 0, 0 | [verified] |
| F9 | Master pins as outputs, value 0, pulls off: MCLK, SCLK, LRCK and each TX data pin | `gpio_direction_output(p, 0)`, pull up/down off | outputs **high**, PC3 input with pull-up | outputs high (PC6 low first) | via SDK | [verified]; the output level before ALNK0 owns the pin differs between sources |
| F10 | `CON1`, per channel *n* a nibble at bit 4*n*: bit 0 enable, bit 2 24-bit data, bit 3 direction (1 = in) | `iis_open` loop; `iis_channel_on` sets bit 4*n* | `1 \| 1<<2 \| 1<<3 \| 1<<12 \| 1<<14` (RX ch0 + TX ch3) | `1<<12`, `1<<14`, `&= ~(1<<15)` | `data_width` = ch3 | [verified] |
| F11 | `ADR`*n* = channel *n*'s ping-pong base; `LEN` = 32-bit words per half per channel | `ADR`*n* from the channel buffer, `LEN = sr_points` | `ADR0` RX, `ADR3` TX | `ADR3` | `sr_points` 128 = 512 B per half | [verified] |
| F12 | `csync` before setting `CON0` bit 11 (module enable) | yes | a fence | — | — | [verified] |
| F13 | 44.1 kHz family on ALNK0: `CLK_CON2 &= ~(1<<8)`; `CON3 &= ~0x1C`; `CON3 = (CON3 & 0x1F) \| (4<<5)`; `CLK_CON2 &= ~(1<<9)`. (ALNK1 uses bits 10, 11) | `iis_set_sample_rate(44100, 0)` | clears bits 8-11, `CON3 = 3 \| 4<<5` | clears bits 8-11, same `CON3` | 44,100 | [verified] |
| F14 | Rate table: `CON3[7:5]` code 1, 2, 3, 4 and `CLK_CON2` bit 8 select the family: clear = 176.4/88.2/44.1 kHz (codes 1, 2, 4); set = 192/96/64/48 kHz (codes 1, 2, 3, 4) | `iis_set_sample_rate` switch | "11.2896 MHz, 256 fs" | — | — | table [verified]; fs = F / (64 · code) with F = 11.2896 or 12.288 MHz fits every row, so at code 4 MCLK = 256 fs and SCLK = F / 4 = 64 fs [inferred] |
| F15 | Channel on: `CON2 \|= 1<<n` (clear a stale pending), buffer zeroed, `CON1 \|= 1<<4n` | `iis_channel_on` | — | `CON2 = 0x0F` | via SDK | [verified] |
| F16 | Pending: `CON2` bit 4+*n*; acknowledge by writing 1 to bit *n* | `iis_irq_handler` | `(CON2>>4)&15`, writes back | `0x80`, `\|= 0x08` | via SDK | [verified] |
| F17 | Free half: `CON0` bit 12+*n* set → the first half is free, clear → the second | `iis_irq_handler` | `!(CON0 & 1<<15)` | `((CON0>>15)&1)^1` | via SDK | [verified] |
| F18 | Hardware rate about 44,118 Hz rather than 44,100 (24 MHz / 544 = 44,117.6) | — | `FM1_AUDIO_HARDWARE_RATE 44118` | times 44,117.6 Hz | — | [reported]; not measured here |
| F19 | Sample word: signed 24-bit value sign-extended in a 32-bit word (Q23, −8,388,608 … 8,388,607), L then R | — | Q23 clamp | Q15 << 7 (a −6 dBFS ceiling) | "24-bit samples in 32-bit DMA words" | [reported, three sources]. docs/01 said "left-justified in 32"; that is not what the code does |
| F20 | 64 stereo frames per half = 128 words; 1,024 B ping-pong | — | 128 frames per half (its own choice) | `half_words` from the app | 64 frames, as stock FM-1_010 | [reported: fm1-nes, stock]; Lunar uses 64 |
| F21 | A settle delay after start: 5 ms | none | none | 5 ms after enable | none | [reported: Felucca]; purpose (DAC clock lock) [inferred] |
| F22 | IRQ priority: SDK apps choose; M-VAVE 4, Felucca 3 | — | 4 | 3 | service-defined | [reported]; Lunar default 3, a parameter |

The wire format (I2S or left-justified) is not settled by any source: `CON0`
bit 6 is the only unexplained mode bit, and every source clears it. A DAC
of the CS4344 class comes in fixed-format variants, so the format and the
part must be read together (§7).

## 4. The driver

`firmware/board/alnk0_audio.{h,c}`, MIT, C99, no SDK headers. It accesses no
register itself: the caller passes `struct lunar_alnk0_ops` (register read
and write by address and width, a barrier, IRQ attach and a delay). The
target composes those from `alnk0_audio_mmio.c` (volatile accesses and
`csync`, compiled only for pi32v2) and its own IRQ and timer services.

`lunar_alnk0_start` emits, in order:

1. route: `IOMAP_CON5 &= ~0xC0` (F3), first, as in the SDK;
2. reset: `CON0`, `CON1`, `CON3`, `LEN`, `ADR0..3` = 0 (F1; `CON2` untouched, as in the SDK);
3. master: `CON3 |= 3`, `CON0 |= 0x80`, `CON0 |= 0x100`, `CON0 &= ~0x40`;
   bits 9 and 10 stay clear (F5-F8);
4. pins PC0, PC1, PC2, PC6: `OUT`, `DIR`, `PD`, `PU` cleared, mask-wide (F9);
5. channel 3: `CON1 &= ~(1<<15)`, `CON1 |= 1<<14` (F10);
6. `ADR3` = the buffer, `LEN` = 128, barrier, `CON0 |= 0x800` (F11, F12);
7. rate: the four writes of F13;
8. IRQ 11 attached at the configured priority (F2, F22);
9. channel on: `CON2 |= 1<<3`, buffer zeroed, `CON1 |= 1<<12` (F15);
10. the configured settle delay (F21; 5 ms in the Lunar profile).

Decisions, with the alternatives:

- **TX only, channel 3.** M-VAVE also runs RX channel 0 on PC3 "for the
  interrupt clock"; the SDK, fm1-nes and Felucca run TX alone and use
  channel 3's own pending bit, and Felucca and fm1-nes play on FM-1s that
  way [reported]. PC3 is left untouched.
- **Pins low, not high.** Felucca and M-VAVE set the pins high before ALNK0
  takes them; the SDK sets them low. Once the module is enabled it drives
  them, so the difference lasts only until step 6 [inferred]. The SDK's
  choice is taken because it is the one with Apache provenance.
- **`CLK_CON2` bits 8 and 9 only.** Felucca and M-VAVE also clear bits 10 and
  11, which belong to ALNK1; the SDK leaves ALNK1's bits alone, and so does
  this driver.
- **Buffer 32-byte aligned**, as M-VAVE's, so the DMA area shares no cache
  line with other data [inferred: pi32v2 cache-line size not checked]; the
  validator refuses less. `LEN` and the buffer size come from one
  `half_words` value (128 here); odd or zero values are refused.
- **IRQ before channel-on**, as fm1-nes calls `audio_irq_start` between
  `iis_set_sample_rate` and `iis_channel_on`. The module is enabled at step 6
  but no channel runs until step 9, so no pending can arrive unattended
  [inferred from F10/F15].
- **Stop** clears channel 3's enable, acknowledges its pending and clears
  `CON0` bit 11. The SDK's `iis_close` order was not read; this is ours.
- The ISR helpers (`pending`, `ack`, `free_half`) go through the same ops
  for testing. A production ISR may inline volatile accesses instead; their
  semantics are F16 and F17.
- `lunar_alnk0_word_from_q23` saturates to the Q23 range (F19).

## 5. The fixture and the test

There is **no datasheet to derive from**: the DAC is unidentified (§1).
`tests/fixtures/alnk0/lunar_start.json` therefore encodes:

- the exact ordered operation list for the Lunar profile, written by hand
  from the facts table (not generated from the driver), against a fake
  register file whose initial values are all-ones where a read-modify-write
  must keep unrelated bits;
- the SDK rate table (F14), from which the test derives fs = F / (64 · code)
  for every row, and so MCLK = 256 fs and SCLK = 64 fs at the 44.1 kHz code;
- the generic needs of a control-less I2S DAC on this link: MCLK output on,
  master, 64 SCLK per frame, 24-bit data on channel 3, 64 frames per half,
  IRQ 11. These are what a CS4344-class part would need [inferred]; when
  `U9` is read, re-derive them from its datasheet and change the fixture,
  not the test.

`tests/test_alnk0_audio.py` builds the driver into a host library with
`cc -std=c99 -Wall -Wextra -Werror`, drives it through ctypes and checks the
operation list, the final register state against the invariants, the
validator's refusals, error propagation from IRQ attach and delay, the ISR
helpers, `stop`, and the Q23 packer.

## 6. Checks run

- `.venv/bin/python -m pytest tests/test_alnk0_audio.py -rsx`: **27 passed**
  (host `cc -std=c99 -Wall -Wextra -Werror -pedantic`).
- pi32v2 compile on the LAN build host, in the existing
  `lunar-jieli-check:bookworm` image with the pinned V1.2.13 toolchain
  (JieLi clang 4.0.1; `clang -target pi32v2 -mcpu=r3 -mfprev1
  -femulated-tls`, the SDK CFLAGS from `tools/jieli/in-container.sh`,
  `-std=c99 -Os -Wall -Wextra -Werror`), containers labelled
  `project=lunar-modulator session=fm1-wave1-codec`: both files compile with
  no warnings. `.text` is **1,072 bytes** for `alnk0_audio.o` (`start` 772,
  `stop` 96, `validate` 66, `ack` 48, `free_half` 26, `pending` 24, the Q23
  packer 22, `default_config` 18) and **40 bytes** for `alnk0_audio_mmio.o`.
  The vendor `objdump -d -mcpu=r3 -mattr=+fprev1` shows byte, half-word and
  word loads and stores (`b[r1+0]`, `h[r1+0]`, `[r1+0]`) for widths 1, 2 and 4,
  and `csync` as the barrier [verified]. Compile only: nothing linked,
  nothing run.
- Source hashes at build time (sha256): `alnk0_audio.c` `7cbd64c1…`,
  `alnk0_audio.h` `73176931…`, `alnk0_audio_mmio.c` `4d9facf1…`; they match
  the committed files.

## 7. Uncertainties and follow-ups

- Read `U9` and `U5` under a loupe with the board out; then fetch the
  datasheet, settle I2S versus left-justified (and `CON0` bit 6), and
  re-derive the fixture.
- The hardware rate (F18) and the DAC's lock behaviour at 44,118 Hz are
  reported, not measured. M6 should capture the output on the KA6 and
  measure the rate.
- Whether an amplifier enable or a mute line exists (§1.4).
- The `pi32v2` cache-line size behind the 32-byte alignment.
- `CON2` bits 0-3 are treated as write-1-to-acknowledge, following the SDK's
  read-modify-write; whether a write of 0 to the upper bits has any effect
  was not checked.
- fm1-nes reuse: its audio code is calls into the SDK's `iis_*` API, so it
  can be used directly only on the SDK-application route (docs/18 decision
  3). It is Apache-2.0 with no NOTICE file; reuse needs its LICENSE, credit
  and a change record, as `firmware/third_party/fm1-nes/UPSTREAM.md` already
  does for the `boot_info` bridge. For the bare-metal route it offers
  configuration facts (F4, F8, F11, F20), not a register driver, and this
  driver does not include any of its code.
- The SDK IR, the extracted `iis.c.o` and the decrypted V15 image stay in
  private storage. The LAN scratch for this lane was deleted after the
  table was written.
