# K1–K3 watchdog probe images (dev kit)

RAM-only, SDK-free pi32v2 images for the AC79 dev kit, loaded and started by
`tools/ram_runner.py` through the mask ROM, like the M4 RAM test
(`firmware/ramtest/`). They answer the dev-kit questions K1–K3 of
`notes/2026-11-10-m5-fm1-ram-run.md`; the plan and results are in
`notes/2026-11-10-devkit-watchdog-probes.md`.

Every image first reads, without writing anything, the clock words, TIMER4's
control word, the P33 watchdog, `VLD_KEEP`, reset-source and power words, the
`usb_update_mode` marker and two 16-byte crumbs (`0x01C07C00` and
`0x01C7C000`). Then it sets up UART1 TX on PB3 at 1,000,000 baud, prints
them, and does one thing, fixed at build time:

| Image | Mode | Then |
| --- | --- | --- |
| `wdtprobe-read.bin` | 1, read | clears the marker and crumbs, prints a beat every 150,000 TIMER4 ticks (100 ms at a 24 MHz oscillator) with the watchdog word, never kicks; after 150 beats resets to the application |
| `wdtprobe-kick.bin` | 2, kick | as read, but kicks the watchdog on every beat; then times M5's `lunar_m5_pixel` over the whole frame with a kick per row, and 240 kicks alone; resets to the application |
| `wdtprobe-disarm.bin` | 3, disarm | writes `P3_WDT_CON` = `0x0B` (disabled, time code `WDT_2S`), reads it back, writes the crumbs and the marker, resets through P33 into the ROM |
| `wdtprobe-mailbox.bin` | 4, mailbox | writes the crumbs and the marker, arms the watchdog (`0x1C`, 4 s, reset mode) only if it is not armed, beats without kicking until it fires; after 150 beats clears the marker and resets to the application |

No SPI1: on the kit PC7–PC10 are its LCD and touch pins. TIMER4 runs free at
OSC/16 with `PRD` `0x7FFF`, as M6's stopwatch. A timer that stops counting, or
a P33 bus that stays busy, sends the image back to the application.

`wdtprobe.c` takes all register access through ramtest's I/O table and links
`ramtest.c` unchanged, so `tests/test_wdtprobe_image.py` compiles it natively
and checks every access, the P33 frames and which P33 registers are written
(`P3_WDT_CON` and `P3_PR_PWR` only).

Build (JieLi clang in a container on a Docker host; the base id is at most
11 characters and each image gets `<base>-<mode>`):

    LUNAR_BUILD_ID=wdtprobe-1 LUNAR_SESSION=<label> \
        bash tools/jieli/link-diagnostic.sh <docker-host> <toolchain-dir> <scratch-dir> wdtprobe

That writes `build/jieli-wdtprobe/`. Capture with
`tools/devkit_uart_capture.py --timestamps` and summarise with
`tools/devkit_wdtprobe_report.py`. For the dev kit only.
