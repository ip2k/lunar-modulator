# m5-plan-2: the M5 successor (RAM only)

A RAM-only, SDK-free pi32v2 image for a possible second FM-1 RAM run. It
follows `firmware/m5/`, whose run on 2026-11-10 loaded and jumped but showed
nothing; the chip reset to V15 3.89 s after the jump
(`notes/2026-11-10-m5-fm1-ram-run.md`). The kit showed that the mask ROM
leaves its 4 s watchdog armed (`notes/2026-11-10-devkit-watchdog-probes.md`).
The plan, the kit evidence and the owner decisions are in
`notes/2026-11-14-m5-plan-2.md`.

It is loaded at `0x01C02000` and keeps M5's budget: the image, its stacks
and the breadcrumbs all stay in `[0x01C02000, 0x01C06000)`.

## What it does, in order

1. Clears the ROM's watchdog with the P33 sequence
   (`lunar_ramtest_wdt_kick`). From then on it kicks at least every 10 ms
   in every wait, between spin units, on every pixel row and in the blink
   loop. The longest gap is the 200,000-spin clock measurement: 60 ms on the
   kit [verified, dev kit].
2. Writes twelve breadcrumb words at `0x01C05FC0` (`m5p2.h`).
3. Drives PA2 low: the backlight comes on before anything else.
4. Starts TIMER4 (OSC/16) and times a 200,000-spin block.
5. Flashes the backlight in two cadences that give the clocks without a
   UART:
   - A: three off/on flashes, each half 400 ms at the 40 MHz binding
     (667 ms at 24 MHz);
   - B: three off/on flashes (five if TIMER4 is dead), each half exactly 20
     measured blocks (1.18 s at the kit's 48 MHz CPU).
6. Sets up SPI1 and the panel, sends display-on (`0x29`), then the
   240×240 frame. The frame's label is `m5-plan-2 <WDT_CON> <ticks per
   block>` in hex.
7. Blinks the LEDs: 3 per cycle = frame sent with TIMER4 alive, 2 = frame
   sent on spin waits, 1 = the panel failed.

The default FM-1 image does this until power-off.

## Images and build switches

`m5p2.c` is the same object in every image; only `main.c` reads the
switches, which are both off by default.

| Image | Build id | Switches | Ends |
| --- | --- | --- | --- |
| `m5p2.bin` | `m5-plan-2` | none (FM-1 default) | never; kicks and blinks until power-off |
| `m5p2-mailbox.bin` | `m5-plan-2m` | `LUNAR_M5P2_MAILBOX=1` | writes the `usb_update_mode` marker at entry, stops kicking after 18,000 ms of nominal waits (about 40 s at kit clocks); the armed watchdog then resets into UBOOT with the breadcrumbs kept |
| `m5p2-kit.bin` | `m5-plan-2k` | `LUNAR_M5P2_KIT=1` | dev kit only: FM-1 pins and SPI1 stubbed, UART1 trace on PB3 at 1,000,000 baud, P33 reset to the application after 9,000 ms of nominal waits (26.6 s on the kit) |
| `m5p2-kit-mailbox.bin` | `m5-plan-2km` | both | dev kit only: as the mailbox image, with the trace and 20 heartbeat lines after the last kick |

On the kit, PA0–PA10, PB7 and PC7–PC10 belong to its camera, keys and LCD
[inferred: SDK board options], so the kit images never touch them.

`tests/test_m5p2_image.py` compiles `m5p2.c` natively and models the chip:
time in cycles, TIMER4, the P33 frames, SPI1 bytes with D/C and CS. It
checks:
- the register allow-list;
- that PA2 comes first and display-on comes before the frame;
- the longest kick gap at several clocks;
- that the tick count loses no TIMER4 wraps;
- single faults: a dead timer and a stuck SPI;
- that the build switches live only in `main.c`.

## Build

JieLi clang runs in a container on a Docker host. The base id is at most 10
characters; the variants append `m`, `k` or `km`.

    LUNAR_BUILD_ID=m5-plan-2 LUNAR_SESSION=<label> \
        bash tools/jieli/link-diagnostic.sh <docker-host> <toolchain-dir> <scratch-dir> m5-plan-2

That writes `build/jieli-m5p2/`: each image's ELF, binary, map,
disassembly, `audit_link` result (`--runtime sdk-free`) and
`sha256.txt`. Two builds give identical hashes.

Only an image whose hash the owner has approved may run on the FM-1, and
only through a host tool that pins that hash. Nothing in this directory
changes `tools/fm1-transporter/fm1t_m5.py`.
