# 2026-11-10 — Dev-kit watchdog probes K1–K3: built, not run (kit's ROM port taken)

The follow-up to `notes/2026-11-10-m5-fm1-ram-run.md` asked three questions
of the AC79 dev kit:

- **K1:** is the P33 watchdog armed at RAM-image entry, and with what timeout?
- **K2:** how long does the watchdog take, and does M5's frame beat it?
- **K3:** does the `usb_update_mode` mailbox send a watchdog reset back to the ROM?

**Outcome: the probe images, their tests and the capture tooling are built
and checked; none of them has run.** The kit's ROM device cannot reach the
runner, because the FM-1 transporter now sits on the kit's pinned USB port
(§1). Nothing was sent to the kit except one PING. Nothing was sent to the
FM-1 or the transporter. §2 says what is known without the runs, from M6's
kit run and desk work. §4 is the sequence to run once the port is free.

## 1. Blocker: the kit's ROM port `3-1.2` holds the Pico transporter

`ram_runner.py` accepts only the kit's pinned sysfs path `3-1.2`
(`tools/bench_targets.json`) and its allow-list stays unwidened.

- **The port now holds the transporter.** bench01's USB tree at 18:58 PST:
  - `1-2` FM-1 (`4c4a:c755`);
  - `3-1` hub (`0424:2514`);
  - `3-1.2` FM-1 Transporter (`2e8a:000a`);
  - `3-1.4` Tigard (`0403:6010`).
  - No dev-kit device appears [verified: sysfs].
- **The kernel log shows how it got there** [verified: `journalctl -k`]:
  - the kit's ROM device last left `3-1.2` at 09:50:53 PST;
  - the whole hub dropped at 12:56:27;
  - the hub came back at 14:45:50 with the transporter on `3-1.2`, which
    re-enumerated four times up to 16:49:19. That window covers the M5 FM-1
    run at 15:15.
- **The kit's application is up.** It answered `LUNAR PING`, run under
  `flock -n ~/.lunar-devkit.lock` on bench01 at about 18:32 PST, with
  "Diagnostic PING acknowledged; no reset requested." [verified].
- **ROM entry was not attempted.** `--enter-uboot` would put the kit in a
  ROM whose USB device is either off the bus or on an unpinned port. The
  runner would refuse to load the return image, and getting out of the ROM
  could then need a button press, which the unattended-test rule rules out.
- **To unblock, the owner:**
  1. unplugs the transporter from hub port 2;
  2. plugs the dev kit's USB data cable back into hub port 2, so its ROM
     device enumerates at `3-1.2` again;
  3. leaves the Tigard on port 4.

  The FM-1 on `1-2` is not involved.

## 2. What is known without the runs

### 2.1 The clock under the kit's ROM (warm entry)

M6 run c printed these words from inside a ROM-loaded image
[verified: `notes/2026-11-09-m6-image.md` §3]:

```text
LUNAR_M6 clock sys_div=0x00000000 clk_con0=0x000001C1 clk_con1=0x00010000 clk_con2=0x00000080 wdt_con=0x0000001C timer_con=0x00000000 cpu_polls=522
```

The decode against the pinned SDK's clock driver and `WL82.h` was done by a
sub-agent and spot-checked:

- **System clock 48 MHz:** the PLL's 192 MHz tap divided by 4.
  - `CLK_CON0` `0x1C1`: bits 7:6 = 3 select the PLL path, and bit 8 takes
    the main mux rather than the RC.
  - `CLK_CON2`: source 0, dividers /1 and /4.
  - `SYS_DIV` 0, so HSB = LSB = 48 MHz.
  - The register decode is [verified: SDK]. That the 192 MHz tap is live is
    [inferred]; it fits a ROM serving full-speed USB.
- **Oscillator 24 MHz** [inferred]. M6's TIMER4 at OSC/16 counted 2,176
  ticks per 64-frame block. Host-timed, that block took about 1.45 ms, which
  is 1.5 MHz ticks.
- **SPI1 bit clock = LSB / (BAUD + 1)** [verified: SDK]. M5's BAUD 4 gives:
  - 9.6 MHz under the kit's ROM (LSB 48 MHz);
  - 12 MHz on stock V15 (LSB 60 MHz);
  - 10.67 MHz in the kit's application [inferred: its LSB is 53.3 MHz].

### 2.2 The watchdog under the kit's ROM

What is known:

- **Armed for 4 s in reset mode.** `wdt_con 0x1C` means bit 4 = enabled,
  time code `0xC` = `WDT_4S`, bit 5 = 0 [verified: SDK `wdt.h`
  table, M6 UART].
- **A reset in that state reports WDT.** M6 run b, with interrupts masked
  and no kicks, reset into the application with
  `system reset reason: WDT`, 2.97–4.47 s after the image started
  [verified: UART; the bound is inferred].
- **The count seems to restart around the jump.** Runs a and b returned
  1 ms apart (4,709 and 4,710 ms after the jump), and run b's image ran at
  least 2.97 s although the ROM was entered earlier [inferred].
- **It is inherited, at least on this path.** The kit's ROM was entered
  warm: the application wrote the marker and asked P33 for a reset
  (`nvram_set_boot_state(2)`). The application's `setup_arch` runs
  `wdt_init(0xc)` [verified: `notes/2026-11-08-failopen-watchdog.md`], so it
  armed the watchdog first. The application runs it in exception mode
  (`0x3C` plus `WDT_EXPT_EN`) and reports SOFT. Under the ROM bit 5 was clear
  [verified: M6 line]. Who cleared it is unknown.

What is not known:

- whether the ROM arms the watchdog itself;
- whether a P33 reset keeps `P3_WDT_CON`;
- the watchdog's clock source and its accuracy. A fixed low-rate RC is
  [inferred].

The marker's reader is not in the SDK; it is the ROM or the SPL [inferred].
`notes/2026-10-05-softkey-efuse.md` found that the SPL does not read it.

### 2.3 What a warm entry can and cannot tell about the FM-1's cold entry

**Can tell, on the kit:**

- the ROM's clock tree and TIMER4 rate after a marker-plus-P33 entry;
- whether an inherited, armed watchdog keeps running into a ROM-loaded image,
  and how long it takes there;
- with the disarm probe (§3), whether the ROM *re-arms* a watchdog that
  was left disabled across the P33 reset, and whether `P3_WDT_CON` survives
  that reset.

**Cannot tell:**

- **The cold state.** The FM-1's power switch cuts the SoC fully
  [verified: M5 note], so it enters the ROM by `USB_KEY` from power-on, with
  the P33 domain at its reset defaults. The kit's warm path never starts from
  those defaults. A kit power cycle lands in the application, and a cold ROM
  entry on the kit needs its UPDATE button, which is ruled out.
- **The ROM's branch.** The `USB_KEY` entry may run a different ROM branch,
  with a different clock and a different watchdog setup, from the marker
  entry [inferred].
- **The FM-1's own oscillator.** Stock chooses 24 or 40 MHz
  [verified: `firmware/timing/README.md`].

So a kit result of "the ROM arms it" is strong evidence for the FM-1.
"The ROM does not arm it" is weaker evidence: the 3.89 s reset after the
FM-1's jump [verified: M5 note] and FM-1-transporter's "The ROM runs a 4 s
watchdog" [reported: its `docs/PROTOCOL.md`] both point the other way.

### 2.4 M5's frame against a 4 s watchdog (desk estimate)

M5 sends `0x29` only after setup and the full frame. Its parts on the FM-1,
**assuming the FM-1's ROM runs the kit's 48 MHz** (unknown):

| Part | Estimate | Basis |
| --- | --- | --- |
| Panel waits | 100 + 120 ms asked; 367 ms actual if the oscillator is 24 MHz | TIMER4 bound at 40 MHz, so waits run 1.67× long [inferred] |
| SPI shifting | 115,200 B × 8 bit / 9.6 MHz = 96 ms | §2.1 [inferred] |
| Per-byte polling and calls | about 150–400 cycles a byte: 0.36–0.96 s at 48 MHz | `spi1_transport.c` `byte()`: two writes and two polled reads through function pointers, per byte [inferred, not counted from the disassembly] |
| `lunar_m5_pixel` per pixel | unmeasured; the kick probe measures it | — |

That is about 0.8–1.4 s plus the pixel cost at 48 MHz, so **inside 4 s
[inferred]**. At a 12 MHz RC clock it would be four times that: 3–6 s, which
the watchdog would cut off before display-on. Whether M5's frame beats the
watchdog on the FM-1 therefore turns on the FM-1 ROM's CPU clock, which no
kit run gives. M6's FM-1 build has the same exposure.

## 3. What was built (2026-11-10)

`firmware/wdtprobe/` (README there) has four RAM images built from the same
code, with the mode fixed at build time. All of them are SDK-free, run at
`0x01C02000` and stay inside 16 KiB.

Each image does this:

1. **Snapshot at entry, reads only.** The clock words `PWR_CON`, `SYS_DIV`,
   `CLK_CON0`–`3`, `PLL_CON0`/`1` and `PLL2_CON0`/`1`; `JL_SYSTEM->RST_SRC`;
   TIMER4 `CON`. The P33 words `WDT_CON`, `VLD_KEEP`, `RST_SRC` and `PR_PWR`,
   through a P33 read that never writes back (`lunar_ramtest_wdt_kick` sets
   the clear bit, so it is not used for reads). The marker, crumb A at
   `0x01C07C00` and crumb B at `0x01C7C000`.
2. **Print them** on UART1 (PB3, 1 Mbaud).
3. **Run its mode:**
   - **read:** clear the marker and crumbs, then beat every 150,000 TIMER4
     ticks without kicking.
   - **kick:** the same, kicking on every beat. Then time `lunar_m5_pixel`
     over the frame with a kick per row, and time 240 kicks alone.
   - **disarm:** write `WDT_CON` `0x0B`, set the crumbs and the marker, then
     P33 reset into the ROM.
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
  gave identical ELF and BIN hashes. The hashes depend on the build id.
- **Audit passed** [verified: `*.audit_link.json`]:
  `audit_link.py --runtime sdk-free`, linked, 0 fail, 0 pending, all four.
- **Memory** [verified: `wdtprobe-*.symbols.txt`]:
  - `__image_end` is `0x01C03764`.
  - `__ssp_top` is `0x01C05790`, below both crumbs.
  - The upload, padded to 512-byte blocks, is `[0x01C02000, 0x01C03800)`.
- **No guarded addresses** [verified: disassembly grep]: no eFuse
  `0x13700`–`0x1371F` and no mkey words `0x01C80108`–`0x01C80110`.
- **Remote scratch removed** [verified]. The local
  `build/jieli-wdtprobe/` is git-ignored build output.

Crumb B stays clear of the `UPDATA_PARM` record at `0x01C7FD88`, which the
SPL CRC-checks [verified: `notes/2026-10-05-softkey-efuse.md`].
`0x01C7FD90`, first considered, sits inside it. `0x01C7C000` begins the
range reported to survive resets and UBOOT entry [reported: Felucca, docs/01].

Host side:

- **`tests/test_wdtprobe_image.py` (19 tests)** model the chip in Python,
  with a P33 frame decoder and a virtual TIMER4. They check:
  - every SFR and SRAM word the image touches;
  - no eFuse or mkey access;
  - the snapshot comes before any setup write;
  - read mode never writes `WDT_CON`;
  - kick mode kicks once per beat, once per row and 240 times alone, and its
    pixel mix equals the M5 pattern;
  - disarm mode writes `0x0B` and leaves the marker set;
  - mailbox mode arms only an unarmed watchdog;
  - a stalled timer and a stuck bus fail safe.
- **`tools/devkit_uart_capture.py --timestamps`** writes
  `<log>.times.jsonl`, one line per chunk read: `t`, `offset`, `n`.
  - It reads as soon as a byte waits (timeout 20 ms), and fsyncs at most
    once a second so a slow fsync does not delay the stamps.
  - It never sends; the test's fake port fails on any write.
- **`tools/devkit_wdtprobe_report.py`** summarises a capture. It fits beat
  ticks against host arrival times to get the tick rate and the oscillator
  (16 × the tick rate), and gives the time from the ready line to the
  application's `system reset reason` line.
  - `tests/test_devkit_wdtprobe_report.py` (7 tests) recovers 24 MHz and
    40 MHz to within 0.3 % from synthetic logs with 4 ms of USB jitter.

## 4. Results

| Question | Probe | Result |
| --- | --- | --- |
| K1 watchdog at entry, clocks | read | **not run** (§1); M6's warm-entry reading in §2 |
| K1 does the ROM arm it | disarm, then read | **not run** |
| K2 time to reset, no kicks | read | **not run**; M6 run b bounds it at 2.97–4.47 s, code `WDT_4S` |
| K2 kicked run comes back SOFT | kick | **not run**; M6 run c did (kick every 256 blocks, `SOFT`) |
| K2 M5 pixel time | kick | **not run**; desk estimate in §2.4 |
| K3 mailbox routes a WDT reset to the ROM | mailbox, then read | **not run** |
| K3 crumbs survive and read back | read after disarm or mailbox | **not run** |
| Read-back with `FD07` through `ram_runner.py` | — | **not possible as is**: the runner's `FD07` reads only the block it has just written (`run` and `plan` are its only subcommands; no read-only mode). The read image prints the crumbs instead; the allow-list stays as it is |

The answers the brief asked for, as far as they go:

- **K1:** under the kit's warm ROM entry the watchdog is armed, 4 s, reset
  mode [verified: M6]. On the FM-1's cold entry it is unknown, and the kit
  cannot settle that (§2.3).
- **Clocks under the kit's ROM:** a 24 MHz oscillator [inferred], a 48 MHz
  CPU [decode verified, live tap inferred], and TIMER4 at 1.5 MHz with /16.
- **Watchdog timeout:** 4 s nominal [verified: code]; 2.97–4.47 s observed
  [inferred bound].
- **K2:** M5's frame probably beats 4 s at 48 MHz but not at an RC-speed
  clock (§2.4) [inferred]. Not measured.
- **K3:** open.

## 5. Recommendations for `m5-plan-2`

- **Kick wherever time passes:**
  - at entry, before the BSS clear;
  - inside `wait_ms`, once per millisecond step (`lunar_timer_delay` is
    1 ms per period, so kick between calls in 10 ms pieces or less);
  - on every pixel row (240 kicks);
  - on every LED blink cycle.
  - Use `lunar_ramtest_wdt_kick`: it clears only an armed watchdog and
    leaves an unarmed one alone [verified: ramtest tests].
- **OSC_HZ:** 24,000,000 is the kit's figure [inferred]. Keep the 40 MHz
  binding for the panel waits anyway until the FM-1's oscillator is
  measured. Long waits are harmless once the waits kick (147 ms extra), and
  a 24 MHz binding on a 40 MHz part would shorten the ST7789's 120 ms
  sleep-out wait to 72 ms. Report TIMER4 rates on the panel as M6 does.
- **Display-on (`0x29`) right after `lunar_panel_setup`, before the pixel
  stream,** so even a partial frame shows. Toggle PA2 at about 2 Hz before
  setup as a sign that needs no panel.
- **Mailbox:** do not rely on it until K3 has run. If K3 shows the marker
  routes a watchdog reset back to the ROM, then a `m5-plan-2` that sets the
  marker at entry and records its last step in a crumb would come back to
  UBOOT on a watchdog reset. The transporter could then read the crumb.
  - That needs a transporter read command, and a new owner yes: M5's
    approval excluded the watchdog and the mailbox.
  - If the marker does not route a watchdog reset, keep it clear; the FM-1
    then boots V15, as on 2026-11-10.

## 6. Ready-to-run sequence (once `3-1.2` is the kit again)

Hold `flock -n ~/.lunar-devkit.lock` on bench01 throughout. Copy the four
images and `ramtest.bin` (`m4-ramtest-3`, `74104cb2…`) into a run folder and
check their hashes. Keep UART logs, receipts and `commands.jsonl` on bench01
or in session scratch, not in the repository. Then for each run:

1. `python3 tools/devkit_boot_control.py` (PING) must acknowledge.
2. Start `python3 tools/devkit_uart_capture.py --out <run>/uart.log
   --seconds 60 --timestamps`.
3. `python3 tools/devkit_boot_control.py --enter-uboot`. Wait for
   `4c4a:8057` at `3-1.2`, and note its devnum and `/dev/sgN`.
4. `sudo python3 tools/ram_runner.py run --device /dev/sgN --usb-path 3-1.2
   --devnum <n> --image <image> --sha256 <sha> --out <run>/runner`.
5. When the capture ends, summarise it with
   `python3 tools/devkit_wdtprobe_report.py --raw <run>/uart.log`.
6. PING again.

The runs:

- **a, K1 and K2:** `wdtprobe-read.bin`. Expect the snapshot, then a
  `WDT` reset about 4 s after the jump. The report gives the oscillator and
  the ready-to-reset time.
- **b, K2 control:** `wdtprobe-kick.bin`. Expect 150 beats, the
  `m5_pixels` line, then `SOFT`.
- **c, K1 ROM arming:** `wdtprobe-disarm.bin`. Expect `reset=uboot`, and
  `4c4a:8057` at `3-1.2` again without step 3. Then load
  `wdtprobe-read.bin` straight away (steps 2 and 4) and read `wdt_con`:
  - `0x0B`: the reset kept it and the ROM did not arm;
  - `0x00`: the reset cleared it and the ROM did not arm;
  - armed: the ROM armed it itself.

  Its crumb lines show whether SRAM survived a P33 reset.
- **d, K3:** `wdtprobe-mailbox.bin`. Then one of:
  - `4c4a:8057` reappears at `3-1.2` after about 4 s: the mailbox routed the
    watchdog reset. Load `wdtprobe-read.bin` for the crumbs and the marker
    (consumed or not).
  - The application boots with `system reset reason: WDT`: it did not.
- **If any run leaves the chip in the ROM,** load `ramtest.bin` to return to
  the application, then PING.

Afterwards remove the bench-host copies of the images.

## Files

- **Code:** `firmware/wdtprobe/`, `tools/jieli/link-wdtprobe-in-container.sh`
  (profile `wdtprobe` in `tools/jieli/link-diagnostic.sh`),
  `tools/devkit_wdtprobe_report.py` and `tools/devkit_uart_capture.py`
  (`--timestamps`).
- **Tests:** `tests/test_wdtprobe_image.py` and
  `tests/test_devkit_wdtprobe_report.py`.
- **Build output:** `build/jieli-wdtprobe/`, git-ignored.
