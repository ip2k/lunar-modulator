# FM-1 board layer: ALNK0 audio

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
