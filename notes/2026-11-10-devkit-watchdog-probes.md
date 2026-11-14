# 2026-11-10/14 — Dev-kit watchdog probes K1–K3

The follow-up to `notes/2026-11-10-m5-fm1-ram-run.md` asked three questions
of the AC79 dev kit:

- **K1:** is the P33 watchdog armed at RAM-image entry, and with what timeout?
- **K2:** how long does the watchdog take, and does M5's frame beat it?
- **K3:** does the `usb_update_mode` mailbox send a watchdog reset back to the ROM?

The probe images were built on 2026-11-10 (§3) and could not run then. Their
pinned ROM port held the FM-1 transporter (§1). They ran on 2026-11-14 with
a run-local port override (§4).

**Answers** [verified on the dev kit unless marked]:

- **K1: the watchdog is armed at entry: `WDT_CON` `0x1C`, 4 s, reset mode.**
  - **On every reset into the ROM.** This holds for the application's
    acknowledged ROM entry, and also after an image disabled the watchdog
    (`0x0B`) and reset through P33. Either the ROM writes `0x1C` or a P33
    reset restores it as a default; the kit cannot tell which.
  - **The ROM keeps it fed.** The ROM sat idle for 2 to 70 s without a
    reset.
  - **The count restarts at the jump.** Every image got the same time from
    its ready line to the reset.
- **Clocks under the kit's ROM:**
  - **Oscillator: 24.00 MHz.** TIMER4 at OSC/16 counted 1.5000 MHz against
    the host clock, within 0.02 % in four runs.
  - **CPU: 48 MHz** [register decode verified; the live PLL tap inferred].
- **K2: the watchdog fires 4.02–4.12 s after the image's ready line**, about
  4.06 s from the application's own boot stamp [inferred].
  - **Kicking holds it off.** An image that kicks on every 100 ms beat ran
    15.0 s and came back `SOFT`.
  - **M5's pixel computation takes 374 ms**, about 6.5 µs a pixel, and 240
    kicks take 14.2 ms.
  - **M5's frame would beat the watchdog at the kit ROM's clocks**, about
    1.2–1.8 s to display-on [inferred]. On the FM-1 it showed neither the
    pattern nor the LED blinks, so either the FM-1's cold ROM runs at least
    2–3× slower or something other than the watchdog stopped it (§5).
- **K3: yes.** With the marker set, a watchdog reset lands back in the mask
  ROM instead of the application.
  - **Both breadcrumbs survive** that reset, and also a marker-routed P33
    reset.
  - **The marker reads zero at the next image**, so something on the route
    into the ROM clears it.
  - **The reset source tells the two apart:** `P3_RST_SRC` reads `0x04`
    after a watchdog reset and `0x40` after a P33 soft reset.
- **New kit ROM port: `3-1.1`**, not `3-1.2` (§1).

Nothing was sent to the FM-1 (`1-2`) or the transporter (`3-1.2`).

## 1. The kit's ROM port

**2026-11-10: blocked.** `ram_runner.py` accepts only the kit's committed
pin, `3-1.2` (`tools/bench_targets.json`).

- **The port held the transporter.** On 2026-11-10 that port held the FM-1
  Transporter (`2e8a:000a`): at 18:58 PST, at 19:31 PST, and still on
  2026-11-14 at 02:41 PST [verified: sysfs].
- **The kernel log shows how it got there** [verified: `journalctl -k`]:
  - the kit's ROM device last left `3-1.2` at 09:50:53 PST on 2026-11-10;
  - the hub came back at 14:45:50 with the transporter on that port.
- **ROM entry was not attempted then.** The runner would have refused the
  kit, leaving it stuck in the ROM.

**2026-11-14: the owner's layout.** The owner reported the kit board on hub
port 1, its carrier board on port 3, the transporter staying on port 2 and
the Tigard on port 4. In application mode neither kit port enumerates
[verified: sysfs].

**The override.** The committed pin was left alone. The runs used a
run-local `FM1_BENCH_TARGETS` file on bench01:

- `fm1` unchanged;
- `devkit` paths `3-1.1` and `3-1.3`, bus 3 only, with a note saying why;
- `3-1.2` (the transporter) and `3-1.4` (the Tigard) refused [verified:
  `bench_target.check_role_path` against the file];
- `ram_runner.py` passes no explicit config, so it reads the override
  through `sudo env` [verified: source and a sudo load test].

**The first acknowledged entry enumerated `WL80UBOOT1.00` at `3-1.1`**
(devnum 34, `/dev/sg0`) [verified: sysfs]. The override was then narrowed to
`3-1.1` for every later run.

**Proposal: the committed pin should move to `3-1.1`.** That needs its own
change.

## 2. What the runs show

### 2.1 The clock under the kit's ROM

Every image printed the same clock words [verified: UART, six runs]:

```text
LUNAR_WDTPROBE clock pwr_con=0x00000000 sys_div=0x00000000 clk_con0=0x000001c1 clk_con1=0x00010000 clk_con2=0x00000080 clk_con3=0x00000002 pll_con0=0x0940022b pll_con1=0x3f5030ee pll2_con0=0x00000000 pll2_con1=0x00000000 timer4_con=0x00000000
```

- **TIMER4: 1.5000 MHz** [verified: least-squares fit of the beat totals
  against host arrival times]. The report tool gives 23,997,785, 24,000,378,
  24,004,865 and 24,000,030 Hz as 16 × the rate for runs a, b, c-read and
  d-mailbox, with a worst residual of 2.3–2.6 ms (13 ms in run b, whose last
  line follows the pixel pass).
- **Oscillator: 24.00 MHz.** That is 16 × the TIMER4 rate, because `CON`
  `0x29` selects the oscillator divided by 16 [verified: SDK `timer.c`
  decode, 2026-11-09]. PLL2 is off.
- **CPU: 48 MHz.** `CLK_CON0` `0x1C1` and `CLK_CON2` `0x80` select the PLL's
  192 MHz tap divided by 4, and `SYS_DIV` 0 gives HSB = LSB = 48 MHz
  [decode verified against the SDK; that the 192 MHz tap is live is
  inferred]. These match M6 run c's words [verified:
  `notes/2026-11-09-m6-image.md` §3].
- **SPI1:** LSB / (BAUD + 1) gives M5's BAUD 4 a 9.6 MHz bit clock under
  this ROM [inferred].

### 2.2 The watchdog

At the entry of every image [verified: UART]:

```text
LUNAR_WDTPROBE p33 ok=1 wdt_con=0x0000001c vld_keep=0x00000020 rst_src=0x00000040 pr_pwr=0x00000000 sys_rst_src=0x00000001
LUNAR_WDTPROBE wdt armed=1 code=12 interrupt=0 expt_en=0
```

That is enabled, time code `0xC` = `WDT_4S`, reset mode: bit 5 is clear,
and `VLD_KEEP` bit 6 (`WDT_EXPT_EN`) is clear [verified: SDK `wdt.h`].
`rst_src` read `0x04` instead of `0x40` only after a watchdog reset (§2.4).

**Timing, from the read image (no kicks)** [verified: host-timed UART,
`devkit_wdtprobe_report.py`]:

| Run | ROM idle before load | Ready → last beat (40) | Ready → app's reset line | Reset |
| --- | ---: | ---: | ---: | --- |
| a-read-2 | about 70 s | 4.022 s | 4.163 s | `WDT` |
| c-read | about 42 s | 4.024 s | 4.173 s | `WDT` |
| d-mailbox | 2 s | 4.022 s | — (landed in ROM) | — |
| d-read | about 36 s | beat 40, no beat 41 | — | `WDT` |

- **Firing window: 4.02–4.12 s after the image's ready line** [verified]. No
  beat 41 was printed in any run, and it would have fallen at 4.12 s.
- **About 4.06–4.07 s** [inferred]: the time to the application's reset
  line, less the 100 ms the application stamps on it.
- **The count restarts at the jump.** The ROM sat idle for 2 to 70 s with
  the watchdog armed and did not reset, and every image then got the same
  4 s [verified]. So the ROM feeds the watchdog while it serves USB, and
  the last feed is at or just before `FB08` [inferred: the ready line
  follows the jump by a few ms].
- **The 2026-11-09 inference is confirmed.** M6 run b's "the count seemed to
  restart around the jump" was that inference.

**Kicked (run b):**
- 150 beats over 15.0 s, kicked through `lunar_ramtest_wdt_kick` on every
  100 ms beat, then `reset=app`;
- the application reported `system reset reason: SOFT` [verified].

**Does the ROM arm it (run c)?**

The disarm image read `0x1C`, wrote `0x0B`, read back `0x0000000b`, set the
breadcrumbs and the marker, and reset through P33 (`PR_PWR` bit 4). The chip
came back in the ROM. The next image, the read image, found `wdt_con`
`0x0000001c` [verified]:

- **The full word was rewritten.** It was not `0x1B`, which would mean only
  the enable bit had been set and the 2 s code kept.
- **Either the ROM writes `0x1C`, or a P33 reset restores `0x1C` as
  `WDT_CON`'s default.** The kit cannot separate these without a power-on
  entry, which needs its button [inferred].
- **For the FM-1 the two are the same.** If it is the reset default, a
  power-on starts from it too; if it is the ROM, the ROM sets it on that
  path as well, unless its `USB_KEY` branch differs.

### 2.3 What the warm kit entries say about the FM-1's cold entry

- **Shown on the kit:** a 4 s reset-mode watchdog is armed on every route
  into the ROM tried: the application's ENTER, a P33 reset with the marker,
  and a watchdog reset with the marker. It is fed while the ROM idles, and
  it restarts at the jump.
- **Not shown:** the FM-1 enters by `USB_KEY` from power-on.
  - **No cold entry on the kit.** That needs the kit's button.
  - **The FM-1's ROM branch, CPU clock and oscillator are unmeasured** (stock
    chooses 24 or 40 MHz [verified: `firmware/timing/README.md`]).
- **The FM-1 is consistent with the kit:**
  - it reset 3.89 s after its jump [verified: M5 note];
  - FM-1-transporter documents a 4 s ROM watchdog [reported: its
    `docs/PROTOCOL.md`];
  - so the FM-1's ROM almost certainly arms the same watchdog [inferred].
  - Its WDT reset then landed in V15, as the kit's does without the marker:
    M5 never writes the marker [verified: `firmware/m5/` has no reference to
    it].

### 2.4 The mailbox (K3)

**Run d.** The watchdog was already armed (`0x1C`), so the mailbox image
did not arm it:

```text
LUNAR_WDTPROBE mailbox=set waiting_for_wdt=1
LUNAR_WDTPROBE beat=40 ticks=6000000 loops=32284 wdt_con=0x0000001c
```

- The image wrote both breadcrumbs, then the marker, then beat without
  kicking.
- After beat 40 no application boot appeared on the UART in 25 s.
- The ROM device answered at `3-1.1` [verified].
- The read image loaded next printed [verified]:

```text
LUNAR_WDTPROBE p33 ok=1 wdt_con=0x0000001c vld_keep=0x00000020 rst_src=0x00000004 pr_pwr=0x00000000 sys_rst_src=0x00000001
LUNAR_WDTPROBE mailbox usb_update_mode=0 0x00000000 0x00000000 0x00000000 0x00000000
LUNAR_WDTPROBE crumb a=0x01c07c00 valid=1 0x5444574c 0x00000004 0x0000001c 0xabbba8b3
LUNAR_WDTPROBE crumb b=0x01c7c000 valid=1 0x5444574c 0x00000004 0x0000001c 0xabbba8b3
```

**The routes** [verified: runs a, c and d]:

| Reset | Marker set | Lands in |
| --- | --- | --- |
| watchdog | no | application, `system reset reason: WDT` |
| watchdog | yes | mask ROM (`4c4a:8057` at `3-1.1`) |
| P33 soft (`PR_PWR` bit 4) | no | application, `SOFT` (ramtest, M4) |
| P33 soft | yes | mask ROM |

**Breadcrumbs.** Both survived both marker routes into the ROM: mode 3
after the disarm, mode 4 after the mailbox [verified].
- **Crumb B is not reliable once the application has run.** Before the
  probes the application had left its own data at `0x01C7C000` (a word
  `0x414E554C`, "LUNA") [verified: runs a, c and d at entry].

**The marker read zero at the next image's entry in every run** [verified],
including straight after images that set it.
- Whatever reads it on the way into the ROM also clears it: the ROM or the
  first-stage loader. The SDK does not contain that code, and the SPL does
  not read the marker [verified: `notes/2026-10-05-softkey-efuse.md`].

**`P3_RST_SRC`:** `0x04` after the watchdog reset, `0x40` after a P33 soft
reset (the application's ENTER and the disarm image's reset) [verified].
`JL_SYSTEM->RST_SRC` read `0x01` every time.

**A reset into the ROM may not show as a USB detach on the host.**
- **After the disarm and mailbox resets** the kernel logged no disconnect,
  only "reset full-speed USB device number 36/37" after the jump's `SG_IO`
  error, and kept the devnum. The ROM then answered INQUIRY [verified:
  `journalctl -k`].
- **After resets into the application** it logged a disconnect.
- **For the FM-1:** a host that waits for a detach to learn that the chip
  went back to the ROM can miss it; it should query again instead
  [inferred].

**`FD07` read-back of SRAM.** `ram_runner.py` cannot do it without a write:
its `FD07` reads only the blocks it has just written, and `run` and `plan`
are its only subcommands. The read image prints the breadcrumbs instead, and
the runner's allow-list is unchanged.

### 2.5 M5's frame against the watchdog

**Measured in run b** [verified]:

```text
LUNAR_WDTPROBE m5_pixels=57600 ticks=582008 kick240_ticks=21353 mix=0x1c461a2b
```

- **Pixels: 374 ms.** The whole frame of `lunar_m5_pixel` calls with a kick
  and a timer poll per row took 388 ms. 240 kicks alone took 14.2 ms
  (59 µs each, the P33 frames), which leaves 374 ms for the pixels:
  6.5 µs a pixel, about 310 cycles at 48 MHz [inferred].
- **Correct result.** The mix equals the host's for build id
  `wdtprobe-1-kick` (`0x1c461a2b`) [verified: native build of
  `m5_pattern.c`].

**M5 to display-on at the kit ROM's clocks** [inferred]:

| Part | Time | Basis |
| --- | ---: | --- |
| Panel waits (100 + 120 ms asked, TIMER4 bound at 40 MHz) | 367 ms | 24 MHz oscillator [verified] |
| Pixel computation | 374 ms | measured |
| SPI shifting, 115,200 B at 9.6 MHz | 96 ms | §2.1 |
| Per-byte transport (`spi1_transport.c` `byte()`) | 0.36–0.96 s | 150–400 cycles a byte, not measured |
| **Total** | **about 1.2–1.8 s** | well inside 4.02 s |

**So at the kit ROM's clocks M5 would have sent display-on and started its
LED loop at least 2 s before the watchdog fired.** On the FM-1 the owner saw
neither [reported: owner, M5 note]. Then one of these holds:

- **The FM-1's cold ROM runs at least 2–3× slower** than the kit's warm ROM,
  for example on an RC clock with the PLL off.
- **Something other than the watchdog stopped M5.** This covers the M5
  note's hypotheses 3 and 4: a fault before the backlight, or wrong
  backlight and LED lines [inferred].

The watchdog alone explains the FM-1's result only in the first case.

## 3. What was built (2026-11-10)

`firmware/wdtprobe/` (README there) has four RAM images built from the same
code, with the mode fixed at build time. All of them are SDK-free, run at
`0x01C02000` and stay inside 16 KiB.

Each image does this:

1. **Snapshot at entry, reads only.** The clock words, `JL_SYSTEM->RST_SRC`
   and TIMER4 `CON`. The P33 words `WDT_CON`, `VLD_KEEP`, `RST_SRC` and
   `PR_PWR`, through a P33 read that never writes back. The marker,
   crumb A at `0x01C07C00` and crumb B at `0x01C7C000`.
2. **Print them** on UART1 (PB3, 1 Mbaud).
3. **Run its mode:**
   - **read:** clear the marker and crumbs, then beat every 150,000 TIMER4
     ticks without kicking.
   - **kick:** the same, kicking on every beat. Then time `lunar_m5_pixel`
     over the frame with a kick per row, and time 240 kicks alone.
   - **disarm:** write `WDT_CON` `0x0B`, set the crumbs and the marker, then
     P33 reset.
   - **mailbox:** set the crumbs and the marker, arm the watchdog with `0x1C`
     only if it is unarmed, then beat until it fires.
4. **Fail safe.** A stalled timer or a busy P33 bus resets to the
   application. `read`, `kick` and `mailbox` clear the marker and reset to
   the application after 150 beats.

The four images, build base id `wdtprobe-1`, toolchain `clang version 4.0.1`:

| Image | Build id | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `wdtprobe-read.bin` | `wdtprobe-1-read` | 5,988 | `576fe0d3eb53e388368b142c8f756665ebe99a4cea191481b9e058015dab5bb2` |
| `wdtprobe-kick.bin` | `wdtprobe-1-kick` | 5,988 | `ce3b63ed6591e15f50b9346fe17c9178adcbebb3efb2fba9a9416fba72731fc5` |
| `wdtprobe-disarm.bin` | `wdtprobe-1-disarm` | 5,992 | `e8a131819b945ee3e35fe3d363282a505b7789439770fcd3e99dd11c4db43580` |
| `wdtprobe-mailbox.bin` | `wdtprobe-1-mailbox` | 5,992 | `39928503b17c7757263b1deac38403a53b567eb70f57df07958e541b0d5a7236` |

- **Reproducible** [verified]: two builds in separate scratch directories
  gave identical ELF and BIN hashes.
- **Audit passed** [verified]: `audit_link.py --runtime sdk-free`, 0 fail,
  0 pending, all four.
- **Memory** [verified]:
  - `__image_end` is `0x01C03764`.
  - `__ssp_top` is `0x01C05790`, below both crumbs.
  - The upload is 12 blocks, `[0x01C02000, 0x01C03800)`.
- **No guarded addresses** [verified: disassembly grep]: no eFuse
  `0x13700`–`0x1371F` and no mkey words `0x01C80108`–`0x01C80110`.

Crumb B stays clear of the `UPDATA_PARM` record at `0x01C7FD88`, which the
SPL CRC-checks [verified: `notes/2026-10-05-softkey-efuse.md`].

Host side:

- **`tests/test_wdtprobe_image.py` (19 tests)** model the chip in Python,
  with a P33 frame decoder and a virtual TIMER4. They check every SFR and
  SRAM word touched, no eFuse or mkey access, and that only `WDT_CON` and
  `PR_PWR` are written over P33.
- **`tools/devkit_uart_capture.py --timestamps`** writes per-chunk host
  arrival times. It only receives.
- **`tools/devkit_wdtprobe_report.py`** fits the beats against those times;
  `tests/test_devkit_wdtprobe_report.py` has 7 tests.

## 4. The runs (2026-11-14, bench01, 10:45–10:52 UTC)

**Procedure.** Each run used one script, under
`flock -n ~/.lunar-devkit.lock`, in a private run folder on bench01.

- **Steps:**
  1. PING;
  2. acknowledged ROM entry (`devkit_boot_control.py --enter-uboot`);
  3. wait for exactly one `4c4a:8057`, at an allowed path, with its
     `/dev/sgN`;
  4. start the receive-only capture with `--timestamps`;
  5. `sudo env FM1_BENCH_TARGETS=<override> ram_runner.py run`;
  6. wait for the capture;
  7. run the report.
- **The script stops on its own:**
  - when PING or entry is not acknowledged;
  - when a ROM device is already present;
  - when there is more than one ROM device;
  - when a ROM device appears at a path outside the override.
- **Runs that start in the ROM** (`rom` in the table) skip steps 1 and 2.
- **Order matters.** The capture starts after the boot-control steps,
  because both open the Tigard exclusively. Section 6 of the first draft of
  this note had them the other way round.

| Run | How | Image | ROM device | Runner | UART result |
| --- | --- | --- | --- | --- | --- |
| a-read | enter | read | `3-1.1`, devnum 34 | **failed before opening the device**: the run folder lacked `tools/fm1_flash_parts.py` (imported by `fm1_uboot_read.py`) | none; the kit stayed in the ROM, idle 70 s, no reset |
| a-read-2 | rom | read | `3-1.1`, 34 | 12 × `FB06`, 12 × `FD07` equal, `FB08` no answer (4,696 ms) | 40 beats, `system reset reason: WDT` |
| b-kick | enter | kick | `3-1.1`, 35 | same (16,392 ms) | 150 kicked beats, `m5_pixels`, `reset=app`, `SOFT` |
| c-disarm | enter | disarm | `3-1.1`, 36 | same (628 ms) | `disarm wdt_con=0x0000000b`, `reset=uboot`; ROM again at `3-1.1`, 36 |
| c-read | rom | read | `3-1.1`, 36 | same | `wdt_con=0x1c`, crumbs valid (mode 3), 40 beats, `WDT` |
| d-mailbox | enter | mailbox | `3-1.1`, 37 | same | `mailbox=set`, 40 beats, then nothing; ROM again at `3-1.1`, 37 |
| d-read | rom | read | `3-1.1`, 37 | same | `rst_src=0x04`, crumbs valid (mode 4), marker 0, 40 beats, `WDT` |

- **Commands sent** [verified]: every `commands.jsonl` holds the pinning
  record and only INQUIRY (`12`), `FB06`, `FD07` and `FB08`, 1/12/12/1
  times.
- **No other device was opened.** The FM-1 (`1-2`) and the transporter
  (`3-1.2`) were not opened.
- **The kit is back.** The last image loaded (read) cleared the marker and
  breadcrumbs. The application booted and answered PING at 10:52:33 UTC
  ("Diagnostic PING acknowledged; no reset requested.") [verified].
- **Evidence** (UART logs, timestamps, receipts, `commands.jsonl` and
  `steps.txt`) stays private on bench01 in `~/lunar-wdtprobe-2026-11-14/runs/`.
  The image copies there were removed after the runs.

## 5. Recommendations for `m5-plan-2`

- **Kick wherever time passes,** with `lunar_ramtest_wdt_kick` [verified on
  the kit: run b, 15 s, `SOFT`]:
  - at entry;
  - inside every wait, in pieces of 10 ms or less;
  - on every pixel row: 240 kicks cost 14 ms a frame;
  - on every LED blink cycle.
  - Budget: the watchdog gives about 4.0 s from the jump.
- **`OSC_HZ`:** the kit's oscillator is 24.00 MHz [verified]; the FM-1's is
  unmeasured (24 or 40 MHz). Keep the 40 MHz binding for the panel waits:
  - on a 24 MHz part they run 1.67× long, which is harmless once the waits
    kick;
  - a 24 MHz binding on a 40 MHz part would cut the ST7789's 120 ms
    sleep-out wait to 72 ms.
- **Sign of life:**
  - send display-on (`0x29`) right after `lunar_panel_setup`, before the
    pixel stream, so a partial frame shows;
  - toggle PA2 at about 2 Hz before setup, as a sign that needs no panel.
- **Measure the FM-1's clock on the FM-1.** At the kit ROM's clock M5 should
  already have shown the pattern before its watchdog reset (§2.5).
  `m5-plan-2` should show, before anything slow, how fast it runs:
  - for example, blink a fixed number of times per 1,000,000 TIMER4 ticks;
  - or count CPU loops per TIMER4 period;
  - or have the mailbox carry a breadcrumb of the last step and the tick
    count.
- **Mailbox.** On the kit, setting the marker at entry routes a later
  watchdog reset back to the ROM, with SRAM breadcrumbs intact [verified].
  - **What it would give.** If the FM-1's ROM behaves the same, `m5-plan-2`
    could set the marker and keep its last step in a breadcrumb at
    `0x01C7C000`, and a watchdog reset would bring it back to UBOOT instead
    of V15.
  - **Before relying on it:**
    1. **An owner yes.** M5's approval excluded the watchdog and the mailbox.
    2. **A way to read the breadcrumb on the FM-1**, which has no UART: a
       reader image that shows it on the panel, or a read-only ROM read in
       the transporter. `ram_runner.py` has none.
    3. **A host that does not wait for a USB detach** to notice the return to
       the ROM (§2.4).
    4. **Its way out.** A unit left in UBOOT is left by power-cycling, which
       on the FM-1 cuts the SoC fully [verified: M5 note].
- **The bench pin.** Update `tools/bench_targets.json` to `devkit` `3-1.1`
  in a separate change, and copy `tools/fm1_flash_parts.py` with
  `ram_runner.py` to any bench run folder.

## Files

- **Code:** `firmware/wdtprobe/`, `tools/jieli/link-wdtprobe-in-container.sh`
  (profile `wdtprobe` in `tools/jieli/link-diagnostic.sh`),
  `tools/devkit_wdtprobe_report.py` and `tools/devkit_uart_capture.py`
  (`--timestamps`).
- **Tests:** `tests/test_wdtprobe_image.py` and
  `tests/test_devkit_wdtprobe_report.py`.
- **Build output:** `build/jieli-wdtprobe/`, git-ignored.
