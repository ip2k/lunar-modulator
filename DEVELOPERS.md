# Developing Lunar Modulator

*The [README](README.md) presents Lunar Modulator as a product: what it does,
how to try it, and what is coming. This file holds everything technical:*
- the specifications and the hardware;
- how the software works;
- the research behind it ([`docs/`](docs/), [`notes/`](notes/));
- where development stands, the roadmap in detail and the path to an
  installable build;
- how to build, test and contribute.

It is for contributors, and for anyone who wants to know how Lunar
Modulator works. The README's [repository map](README.md#repository-map)
indexes every document.

Until 2026-10-01 the project was called "Open firmware for the M-VAVE FM-1"
(`ip2k/mvave-fm1-open-firmware`). GitHub redirects the old URLs [reported:
GitHub's documentation on renaming a repository].

## The one rule

**Nothing gets flashed to, or written on, an FM-1 until a full flash dump and
a byte-identical restore have been demonstrated on that unit.**
- The FM-1 has one flash bank, no debug pads and no recovery button.
- The only traffic allowed before that is the read-only identity query
  `F0 00 32 45 00 00 00 40 7F F7` and passive captures.
- Never send syscmd 33–36 or 48, or any `5A AA A5` online-tool frame: some
  copy memory or touch flash.

The full rules of engagement are in
[docs/07](docs/07-recovery-and-risk.md) §4. They come from AL-255's safety
review.

## Where development stands

> **Status (2026-10-01): the code runs on a desktop and in a browser, not
> yet on a JieLi chip or an FM-1. This project has flashed nothing.**
>
> - **Desktop and browser:** CI builds the engines, effects and sequencer
>   core on Linux and macOS, and on Linux also as a 32-bit build and under
>   ASan + UBSan; more than 1,400 tests pass [verified: CI on `main`,
>   2026-10-01]. The virtual FM-1 is tested in Chromium only
>   ([What it does](README.md#what-it-does), [Try it in your browser](README.md#try-it-in-your-browser)).
> - **On a JieLi chip:** nothing has been built with JieLi's compiler yet, so
>   speed and memory on pi32v2 are not measured. A JieLi AC79 dev kit and
>   JieLi's USB updater dongle are on order, to run the code there first and
>   to rehearse a flash dump and restore on the kit
>   ([`docs/14`](docs/14-verification-ladder.md)).
> - **On the FM-1:** this project writes nothing to an FM-1 until a full
>   flash dump and a byte-identical restore have been shown on the owner's
>   unit ([`docs/07`](docs/07-recovery-and-risk.md) §4). The dump goes
>   through the chip's mask-ROM USB mode, entered over the USB-C port with a
>   `USB_KEY` dongle: JieLi's (on order), or ours, which is specified,
>   implemented and simulated but not yet run on hardware
>   ([`docs/10`](docs/10-usb-key-dongle.md), [`dongle/`](dongle/)). Two other
>   FM-1 owners report reaching that mode with czietz's Pico dongle, and one
>   reports backing up and writing firmware afterwards [reported:
>   [issue #2](https://github.com/ip2k/lunar-modulator/issues/2),
>   [`docs/10`](docs/10-usb-key-dongle.md) §1.1]; nobody here has run it.
> - **The owner's unit** runs Baud Girl's
>   [FM-1+VA](https://baudgirl.com/work/FM-1+VA), a third-party firmware the
>   owner installed themselves; it identified as `FM-1_092` on 2026-09-29
>   [verified]. This project has only ever sent it read-only requests
>   ([`notes/2026-09-06-bench.md`](notes/2026-09-06-bench.md),
>   [`notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md`](notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md)).
>
> For the verdict on how open the firmware can be, read
> [`docs/05`](docs/05-open-source-feasibility.md); for the plan from desktop
> to device, [`docs/14`](docs/14-verification-ladder.md).

## The short version

- **The chip is a JieLi AC791N** (JieLi's "WL82" family) with two of JieLi's
  own Blackfin-derived **pi32v2** CPU cores, executing in place from a 1 MB
  flash image. The stock firmware appears to render its synth voices on the
  second core ([The hardware](#the-hardware)). It is the same platform JieLi sells for Wi-Fi speakers and story
  machines. The board is silkscreened `DX7 MB V07`.
- **The stock synth engine is Google's msfa, the Dexed core.** Verified in this
  repo: the 32-entry FM algorithm table from `fm_core.cc` sits byte-for-byte at
  offset `0x8C46C` of the V13 application image (with the Dexed-family fix for
  algorithms 4 and 6). The factory bank is reportedly the DX7 ROM1A cartridge.
- **Updates are plain USB-MIDI SysEx with CRC16 and no signature.** Two prior
  projects, [aroum/fm1-custom-fw](https://github.com/aroum/fm1-custom-fw) and
  [AL-255/FM-1-RE](https://github.com/AL-255/FM-1-RE), have reverse-engineered
  the protocol byte-for-byte, disassembled two firmware versions and even built
  an experimental pi32v2 firmware blob.
- **Non-stock firmware now runs on FM-1s, installed over USB-MIDI.** On
  2026-09-04 a contributor to AL-255's repository (Echomatter,
  [PR #2](https://github.com/AL-255/FM-1-RE/pull/2)) installed a V15-derived
  package with its version bumped to 016 and rolled it back to stock V15.
  Since 2026-09-26 Baud Girl's
  [FM-1+VA](https://baudgirl.com/work/FM-1+VA) (a modified V15 with a
  virtual-analog engine and a 64-step sequencer; source not published)
  installs from a browser,
  `FM-1_020` through `FM-1_092` so far. The stock step-1 check turns out to
  be a same-version refusal, and content is not authenticated
  ([docs/03](docs/03-update-protocol.md) §5). There is still **no proven
  recovery path** for a device whose application does not run: one flash
  bank, no debug pads, no recovery button, and JieLi's mask-ROM USB boot mode
  has not been demonstrated on this project's unit. Other owners now report
  reaching it with czietz's Pico dongle, and one reports backing up and
  writing firmware that way ([issue #2](https://github.com/ip2k/lunar-modulator/issues/2),
  [docs/10](docs/10-usb-key-dongle.md) §1.1).
  AL-255's standing verdict remains *NO-GO for non-stock flashing* until
  recovery exists; [docs/10](docs/10-usb-key-dongle.md) is the dongle that
  should provide it.
- **"Wholly open source" is bounded by JieLi.** The compiler is a closed
  Clang/LLVM 4.0.1 fork with a proprietary pi32v2 backend, and the vendor SDK
  links closed `.a` libraries (Bluetooth controller and stack, audio server,
  filesystem, even `cpu.a`). The SDK sources, register headers and a
  replacement bootloader are Apache-2.0. The realistic first target is *an open
  application on the vendor SDK*; blob removal and an open toolchain come later.
- **schwung-movy cannot be ported, but its design can.** Movy is
  TypeScript + Rust running inside Ableton Move, a quad-core Cortex-A72 Linux
  computer with 2 GB of RAM. The FM-1 is a 240 MHz custom-ISA microcontroller
  with 578 KB of SRAM and no Rust or LLVM target. Movy's 8-knob parameter
  pages become two pages of four on the FM-1's four free knobs. Its
  Move-style sequencer model is the specification for `fm1_seq`, our C
  reimplementation ([docs/13](docs/13-movy-port.md),
  [`engines/seq.md`](engines/seq.md)).

## Recommended path

1. **Bench characterization, read-only** ([docs/09](docs/09-first-session-checklist.md)).
   The first session was done on 2026-09-06
   ([`notes/2026-09-06-bench.md`](notes/2026-09-06-bench.md)).
2. **Prove recovery before anything else** ([docs/07](docs/07-recovery-and-risk.md)):
   - Get the chip into its mask-ROM USB boot mode through the USB-C port with
     the `USB_KEY` signal.
   - Dump the flash, restore it, and repeat.
   - Rehearse on the AC79 dev kit first, which is on order
     ([docs/14](docs/14-verification-ladder.md)).
   - Everything else on the FM-1 waits on this.
   - The dongles for it are JieLi's updater (on order) and ours
     ([docs/10](docs/10-usb-key-dongle.md) / [`dongle/`](dongle/)). Other
     owners report the route works with a Pico dongle ([docs/10](docs/10-usb-key-dongle.md)
     §1.1).
3. **First custom code through the mask-ROM route**: the vendor SDK's
   `demo_hello` for AC791N, on the dev kit and then adapted to the FM-1 board.
4. **The synth**:
   - The engine platform ([`engines/`](engines/README.md)), built and checked
     against reference renders on the desktop, brought to pi32v2. Its cost and
     memory are measured on the dev kit first (stage B,
     [docs/14](docs/14-verification-ladder.md)).
   - Then a USB-MIDI class device, DX7 SysEx and presets in flash.
5. **UI and sequencer** after Movy ([docs/13](docs/13-movy-port.md)). The
   sequencer core and its Movy oracle are built and tested on the desktop
   ([`engines/seq.md`](engines/seq.md)); the UI and the rest of the port
   follow.
6. **Ship through the stock OTA path** (new version number, stock flash head),
   as Baud Girl's releases already do, so users install without opening the case.
   That needs Lunar's own update service and installer
   ([The path to an installable build](#the-path-to-an-installable-build)).

## How the software works

### The engine platform

- **The API:** five swappable sound engines and seven effects behind one C
  API ([`engines/include/fm1_engine.h`](engines/include/fm1_engine.h)).
- **Memory:** no heap. The host supplies each instance's memory and makes no
  promise about its contents [verified: `fm1_engine.h`].
- **Parameters:** typed, and shown four to a page for the FM-1's four free
  knobs. Every engine survives any parameter value, NaN included [verified:
  `tests/test_engine_host.py`].
- **Sources:**
  - The engines and effects built from Mutable Instruments code wrap Emilie
    Gillet's modules, vendored unmodified (MIT,
    [`engines/third_party/mutable/UPSTREAM.md`](engines/third_party/mutable/UPSTREAM.md)):
    - **Macro:** Plaits' eight light engines.
    - **Macro Heavy:** Plaits' other 13.
    - **Six-Op FM:** Plaits' DX7-style engine.
    - **Shapes:** Braids.
    - **Plate:** Rings' reverb.
    - **Ensemble and Diffuse:** Plaits' ensemble and diffuser.
  - Sophie and PSX Verb are Schwung modules, compiled unmodified through a
    compatibility shim.
  - Crush, a bitcrusher and sample-rate reducer, is our own code, after
    DaisySP's Decimator and Bitcrush (Electro-Smith, MIT)
    ([`engines/README.md`](engines/README.md#crush)).
  - Fold, a wavefolder with antiderivative anti-aliasing, and Echo, a
    stereo ping-pong delay, are our own code too
    ([`engines/README.md`](engines/README.md#fold),
    [Echo](engines/README.md#echo)).
- **Sample rates:** the Mutable engines run at their modules' own rates and
  are resampled to the FM-1's 44,118 Hz: Braids at 96 kHz, Plaits at
  47,872 Hz ([`engines/resampler.md`](engines/resampler.md)).
- **The output:** a host limiter on the bus keeps twelve voices started in
  phase under full scale [verified: `tests/test_engine_host.py`].
- **The desktop renderer:** `fm1-render` plays notes, parameter changes and
  sequences into WAV files. Details are in
  [`engines/README.md`](engines/README.md).

### Renders checked against the reference, sample by sample

Every engine and effect built from Mutable Instruments code is compared
with the upstream classes it wraps: reference renderers drive the original
Plaits, Braids and Rings code as the modules' own firmware does, with
nothing of ours in the path, and more than 400 tests compare the two. At
the upstream rates 21 of Plaits' 24 engines match sample for sample
(Chiptune once its low-pass gate has opened), its three six-op banks
correlate at 0.99 or better (the wrapper's timing differs by design), and
Braids' 47 shapes and the effects lie within about half a 16-bit step
(0.55 LSB at worst) ([`engines/reference-plaits.md`](engines/reference-plaits.md),
[`engines/reference-braids-fx.md`](engines/reference-braids-fx.md)); the
two Schwung modules are compiled unmodified. The browser adds nothing:
twelve note scripts covering every engine and effect
render identically, sample for sample, in the browser's WebAssembly module
and in the native renderer built with GCC and musl; against GCC with glibc
ten of the twelve are identical, and the two that differ are Sophie's,
whose feedback FM amplifies last-bit differences between the two C
libraries' `sinf` and `expf` [verified: `sim/web/www/fm1.wasm.json`,
2026-10-01].

![Six-Op FM's chord rendered natively and in the browser, with a flat difference line: 0 of 105,882 samples differ](assets/screenshots/parity.png)

### The sequencer core

`fm1_seq` is a C99, heap-free port of Movy's sequencer (schwung-movy, MIT)
with the fixes planned in [docs/13](docs/13-movy-port.md) on by default and
an exact-Movy mode for tests: 4–8 tracks, each routed to the engine or to
USB-MIDI on its own channel, in 14,984 bytes at 4 tracks and 28,808 at 8.
The desktop renderer plays Movy sets and timed scripts through it with
sample-accurate notes and parameter locks, and Movy's own unmodified core,
run in a container, drives 24 golden fixtures that ours matches event for
event, undo aside ([`engines/seq.md`](engines/seq.md)). It is not wired
into the virtual FM-1 yet, so there is no screen to show: SEQ, PLAY/STOP
and REC still say "not in the simulator yet".

### The virtual FM-1

- **What runs:** the firmware's app layer (panel logic, the effect chain and
  the screen drawing), compiled to WebAssembly with every engine and run in
  an AudioWorklet.
- **Threading:** audio and screen drawing share that one thread. On the
  stock FM-1 the screen shares cpu0 with the effects and the output, while
  the synth voices render on cpu1 ([The hardware](#the-hardware)). Whether
  Lunar can split its work that way is to be tried on the dev kit.
- **The screen:** the firmware's own RGB565 frame buffer, copied to a
  canvas. All 287 of its screens pass a layout check, with no text cut short
  and nothing closer than 4 px.
- **On a phone:** the panel keeps keys 31–35 px wide and no target under
  24 px, and scrolls sideways in its own box.
- **Self-contained:** the page loads nothing from anywhere else and finds its
  files relative to itself, so `sim/web/www/` publishes as static files at
  any path. Opened over plain `http://` from another machine, Power on says
  it needs a secure context.
- **Browsers:** tested in Chromium only. That means headless Chromium 153 on
  Linux, from a local server and over https under a sub-path, and Chromium
  152 on macOS. Firefox, Safari, real touch screens and MIDI hardware are not
  tested yet.
- **Checks:** sim/web/README.md, "Limits"; `fm1-sim-render --screens`; and the
  2026-10-01 page test [verified].

**Rebuilding the module** is only needed after changing `engines/` or
`sim/web/src/`.
- It builds in containers on any Linux machine with Docker that you can
  reach over ssh.
- It checks the result sample by sample against the native renderer and plays
  the page in headless Chromium.
- Only then does it replace `sim/web/www/fm1.wasm`.

```bash
FM1_SIM_HOST=user@host sim/web/build-on-aeon.sh   # about 20 s once the images are pulled
python -m pytest tests/test_sim_web.py            # the native checks, no WebAssembly needed
```

The panel's measurements, the parity results and the page tests are in
[`sim/web/README.md`](sim/web/README.md).

## The hardware

| | |
| --- | --- |
| SoC | JieLi AC791N (WL82), LQFP48, marking `C1xxxxx-11B8` (lot varies; owner's `C188612-11B8`); two pi32v2 cores, 240 MHz used of 320; 578 KB SRAM; 1 MB flash (probably in-package) |
| Memory map | flash XIP `0x02000000`, RAM `0x01C00000`, SFRs `0x1xxxx…0x5xxxx`, mask ROM `0xFFC0xxxx` |
| USB | normal `4C4A:C755` (USB-MIDI + UAC1, full-speed, product string `FM-1`), OTA loader `4D4A:4155` |
| Display | 240×240 RGB565 TFT on SPI1 (`0x11D00`), ST7789-class commands |
| Controls | 27 keys + ~14 LED buttons in a 41-input matrix; 8 knobs (stock reads 2 encoders + 2 ADC channels; split unresolved) |
| Audio | internal DAC, 44.1 kHz, 64-sample blocks; 12 msfa voices, rendered on the second core [inferred] |
| Update | USB-MIDI SysEx, CRC16 only; step 1 refuses only the running version, so rebuilt packages with a new version install; the OTA loader can rewrite `uboot.boot` |

The details, with confidence marks, are in [docs/01](docs/01-hardware.md),
[docs/02](docs/02-stock-firmware.md) and [docs/03](docs/03-update-protocol.md).
Some points behind the roadmap:
- **The second core.** The AC791N has two pi32v2 cores, and the stock
  firmware appears to use both: JieLi's OS on cpu0, and the msfa voice
  render on cpu1, outside the OS ([docs/11](docs/11-plugin-platform.md) §2
  has the evidence).
  - The routine at V13 file `0x86AD6` sets a run flag, busy-polls a state
    byte at `0x01C16EC0` and, on value 2, calls `dx7note_compute_block`
    (`0x862FA`), its only call site [verified: V13 disassembly]. That this
    routine runs on cpu1 is [reported: AL-255's symbol names; inferred from
    the `cpu1_run_flag`].
  - cpu0 runs the UI, MIDI, USB and BLE, and an audio task with the fade,
    the six FX slots and the output [reported: AL-255; the core inferred].
  - AL-255's docs read cpu1 as started but unused. Their addresses assume
    `app.bin` runs from `0x02000000`; it appears to run from `0x02000120`
    [inferred: docs/11 §2].
  - Whether a build on the public SDK can do the same is open: the SDK has
    no task-to-core API [verified], and the single-core `system.a` that
    stock's arrangement needs comes from JieLi on request only [reported:
    JieLi AC79 doc 7.40]. The second-core probe on the AC79 kit, whose
    AC7916 has the same two cores, answers it
    ([docs/14](docs/14-verification-ladder.md) §5.1;
    [docs/07](docs/07-recovery-and-risk.md) §3).
- **MIDI in and out.**
  - **Three inputs:** the stock firmware merges USB-MIDI, the TRS jack (DIN
    MIDI on the chip's UART) and BLE-MIDI through one parser [reported:
    AL-255; [docs/02](docs/02-stock-firmware.md)].
  - **The jack is an input, and MIDI out there probably needs a hardware
    change.**
    - M-VAVE's manual and Baud Girl's both call it an input [reported].
    - On the owner's board the jacks are J3, beside the USB-C, and J7
      [verified: [`photos/2026-09-29/2-bottom.jpg`](photos/2026-09-29/2-bottom.jpg)]. J3 is the MIDI input: the
      optocoupler PC1 sits at its pads [inferred, strong]. docs/01 §3 says
      J7/J9, citing aroum's photo.
    - A TRS MIDI input has both signal contacts, tip and ring, on the
      optocoupler's LED, which leaves none for a standard MIDI out (MIDI
      Association RP-054 [reported]) [inferred].
    - The stock code writes the UART's transmit line (AL-255's "MIDI-thru"),
      but that proves nothing about the board: WL82 routes TX to a pin
      through a crossbar, and the SDK accepts `tx_pin = -1` [verified: SDK
      `gpio.h`, `uart_dev.h`].
    - The unpowered checks below settle it.
  - **USB.** The stock FM-1 already exposes a MIDI port that can send.
    - V15 and FM-1_092 declare a device-to-host MIDI source: jacks 1, 2, 7
      and 8, bulk EP `0x84` IN and `0x04` OUT, 64 B each [verified:
      identical bytes in both `app.bin` files at `0x4E6AB`–`0x4E717` and
      `0x4EA7F`–`0x4EA9A`]. CoreMIDI lists the FM-1 as input and output
      [verified on hardware: [`notes/2026-09-06-bench.md`](notes/2026-09-06-bench.md) §1].
    - The public AC79 SDK has no USB-MIDI device class, only CDC, HID, MSD,
      UAC, UVC and printer [verified: V1.1.9 and V1.2.0 trees]. Lunar needs
      its own, which is new work on the SDK's `usb_device` code.
  - **Logging.** docs/08 Phase 3 plans UART logs "on the MIDI TRS jack".
    First logs go out over the SDK's USB CDC class instead (`cdc.c` exists
    [verified]), or on the TFT.
- **BLE MIDI.** It is a stock feature built on JieLi's closed Bluetooth
  libraries. They make up 719 of the 2,062 functions AL-255 classified in the
  stock app [reported: AL-255; [docs/02](docs/02-stock-firmware.md) §4,
  [docs/05](docs/05-open-source-feasibility.md) §3.4]. AL-255's two function
  indexes put that code at 55 KB (287 functions individually classified)
  and 115 KB (all 719) [verified: sums over both indexes].
  - It can stay in builds that link JieLi's SDK, but not in a fully blob-free
    build.
  - The SDK has a BLE GATT-server example but no BLE-MIDI [verified: AC79
    SDK V1.2.0]. Stock also takes the vendor syscmds over BLE [reported:
    AL-255], so Lunar's BLE-MIDI must carry no device-control path.
  - docs/08 Phase 5 leaves keeping it as a decision.
  - The stack's RAM cost, out of the roughly 387 KB the stock layout leaves
    free ([docs/11](docs/11-plugin-platform.md) §2), is not measured
    [inferred].
- **Recovery.** The `USB_KEY` dongle for the chip's mask-ROM download mode is
  in [docs/10](docs/10-usb-key-dongle.md) and [`dongle/`](dongle/). Reports
  from other owners are in docs/10 §1.1.

### Bench checks that write nothing

These settle the MIDI-out questions above within the one rule: the FM-1
gets only the identity query and passive captures. The unit runs FM-1+VA
(`FM-1_092`), so what it sends describes that firmware, not stock; record
the identity with every capture. They extend the read-only session of
[docs/09](docs/09-first-session-checklist.md) (§2 for USB, §5 for the open
case) and answer part of [docs/01](docs/01-hardware.md) §6.

1. **The jack, unpowered.** The owner decides whether to open the case.
   Battery unplugged, switch off, board out of the case.
   - With a TRS breakout plug in J3, use diode mode across tip and ring in
     both directions to find the TRS type (users report Type A [reported]).
   - Check tip, ring, sleeve and J3's two switch lugs for continuity to the
     optocoupler PC1, to GND and to all 48 SoC leads. Follow PC1's output
     to the SoC lead that is UART RX, and confirm J7 as the audio jack.
   - If tip and ring both end on PC1's LED, MIDI out on that jack needs a
     hardware change.
2. **The jack, powered and passive.** A logic analyser decoding 31,250 baud
   on J3's tip and ring, and on any candidate TX lead, while the owner plays
   keys, the arpeggiator and the sequencer. Nothing is sent or plugged in.
   Silence is weak evidence, because FM-1+VA's MIDI path differs from
   stock's [reported: Baud Girl].
3. **The jack, at the desk.** Decode V15's UART1 set-up with JieLi's vendor
   `objdump` (CLAUDE.md trap 4): the TX pin, or "unmapped", with the
   instruction addresses.
4. **MIDI out over USB, passive.**
   - Compare the configuration descriptor the host stored at enumeration
     with V15's bytes above. Avoid `lsusb -v`, which sends extra requests.
   - Listen to the FM-1's MIDI source only while the owner plays, and log
     notes, channels, velocity spread (do the keys send velocity?), CCs,
     clock and the arpeggiator's timing. Baud Girl reports notes on channel
     1 only [reported].
5. **Still forbidden before the gate:** sending MIDI into the unit, for
   example to see whether notes from the jack are passed on to USB.

## The roadmap in detail

The effort figures are rough and come from the 2026-10-01 studies:
- "sessions" are agent working sessions;
- "days" are working days;
- owner bench hours are counted separately.

None of them is a date. Marks follow [Conventions](#conventions). The
arpeggiator, modulation and effects rows draw on the options note
[`notes/2026-10-01-arp-modulation-effects-options.md`](notes/2026-10-01-arp-modulation-effects-options.md),
which lands with the plan PR; its stages S0–S7 are named below.

| Roadmap line (README) | Depends on | Where it is planned | Rough effort |
| --- | --- | --- | --- |
| Sound engines and effects | nothing more in the simulator. On the device: stage B cycle counts and voice caps per engine | [`engines/README.md`](engines/README.md); [docs/11](docs/11-plugin-platform.md) §8 stage B; [docs/14](docs/14-verification-ladder.md) §5 step 8 | done in the simulator; the device part is I8 of [the install path](#the-path-to-an-installable-build) |
| Sequencer | the core and Capture (built and tested [verified: CI]); API v2 parameter uids and the LATCH, SMOOTH and NOLOCK flags (docs/13 M2); the gesture state machine and screen views (M4); the UI-to-audio command ring and undo | [docs/13](docs/13-movy-port.md) §4, §6 and §9 (M2 and M4 on the desktop; B, C and D on hardware); [`engines/seq.md`](engines/seq.md), "What M2 and later still need"; options note stage S0 | not estimated in docs/13. On hardware, stage B is a line in docs/14 §5 step 8 (≤ 2 % of any block) |
| Screen and controls refinement | the simulator (ongoing). On the device: the TFT strip driver, key matrix and encoders (I12), and one sized arena for the app layer, whose `fm1_app_t` is 1,168,288 B today against 578 KB of SRAM [verified: sim/web/README.md] (I2) | docs/13 M4; [docs/14](docs/14-verification-ladder.md) §4.3; [`sim/web/README.md`](sim/web/README.md), "Limits" | ongoing; the device drivers are part of I12 (6–10 sessions) |
| Arpeggiator | the MIDI-effect slot (`FM1_KIND_MIDI_FX`, reserved [verified: `fm1_engine.h` line 46]) with its API v2 contract: transport and tempo in `fm1_host_t`, frame-stamped events, at least 32 outputs per call; the shared helpers and the tick clock (see MIDI effects); its own seeded xorshift generator, never the global `stmlib::Random` that Macro's reference tests rely on [verified: `stmlib/utils/random.h`; options note §2.3] | options note §2, stage S3: `fm1_arp`, our own C after Yarns' `ClockArpeggiator` (MIT: directions, 22 rhythm masks, Euclid, latch), MCL's 19 modes and trig-stepped rate (BSD-3), Super Arp's seeded modifiers (MIT); pages PLAY, RHYTHM, CHANCE and FEEL. [docs/12](docs/12-sequencer.md) §5.1 (stock's ARP becomes the first MIDI effect, so ARP and SEQ run together); [CHOMPI note](notes/2026-10-01-chompi-evaluation.md) step 3. Deluge and Ansible (GPL) are design references only | 1–2 days with golden tests once the slot, helpers and clock exist [inferred: options note §2.1; CHOMPI note] |
| MIDI effects | the contract in API v2 (docs/13 M2): one `process()` per slot per block on frame-stamped events, with a context holding the block's tick frames, at least 64 outputs and note-offs never dropped. Shared helpers: held-note stack, note ledger, scheduler, scale service, seeded RNG. The block's tick frames from `fm1_seq` | [docs/12](docs/12-sequencer.md) §5.1; [docs/13](docs/13-movy-port.md) §6; the 2026-10-01 MIDI-effects study (to be written up in `notes/`) | about 14–17 days to the first six effects in the simulator; under 2 KB of RAM per track [inferred] |
| LFOs, envelopes, modulation matrix | API v2 uids, SMOOTH and NOLOCK, plus a new MOD flag (docs/13 M2); tempo and a beat position in `fm1_host_t`; a fixed control grid of 16 or 32 frames, so output stays identical at any host block size (the owner's choice). `fm1_engine.h` has no modulation kind [verified: lines 41–47], and the matrix needs none: it runs in the host | options note §3–§4, option C in two stages. **C1** (stage S1), `fm1_mod`: 2 global LFOs (Elektron-style pages; free, trig, hold, one-shot and half modes; synced to `fm1_seq`'s tick), 2 ADSR envelopes after Peaks' `MultistageEnvelope` (MIT), a CHANCE source, and a 16-slot bus of 6-byte slots `{source, unit, destination uid, amount, flags}` that writes `set_param`. **C2** (stage S6): per-note sources through an API v2 `set_param_mod(index, key, offset)`, Macro first. Locks set the base and modulation adds an offset (rules M1–M7). Plaits' own per-voice envelope can be exposed in Macro before C1 (stage S2). The [monome/O&C survey](notes/2026-10-01-monome-oc-jhjlim-survey.md)'s block-rate host matrix is C1 | C1 under 0.6 KB and about 0.35 % of a block; C2 about 1.7 KB and 1.1 % [inferred: options note §4.2]. About 1 day per modulation core [reported: survey]; stages S1–S7 add 3,000–5,000 lines in all [inferred] |
| More effects | the effect API (exists); tempo and a beat position in `fm1_host_t` for ECHO, REPEAT and the S&H clock (the Schwung shim answers 120 BPM and −1 today [verified: `engines/schwung.md`]); one host-owned int16 arena for the time effects, so only one big time effect is active at a time [inferred]; the project PRNG in place of DaisySP's `rand()` calls; stage B costs of `powf`, `cosf` and float division on pi32v2 | options note §5, stages S4, S5 and S7, all MIT. Modulators first: CHANCE (stepped S&H, smooth random, drift) and TURING/RUNGLER. Then audio: CRUSH (audio-rate S&H, on Plaits' vendored `SampleRateReducer`), S&H FILTER (random cutoffs into the vendored stmlib `Svf`), FOLD, CHORUS (Junologue). ECHO and REPEAT on the shared arena once tempo exists; WARP and SHIFT later. [CHOMPI note](notes/2026-10-01-chompi-evaluation.md) next steps 1–2; [monome/O&C survey](notes/2026-10-01-monome-oc-jhjlim-survey.md) next steps 1 and 4; [docs/11](docs/11-plugin-platform.md) §3.3 | CRUSH, S&H FILTER and FOLD a few dozen lines each on vendored code [inferred: options note]; ping-pong echo ½ day; pitch shifter ½ day; DJ filter and Warble small; reduced Clouds 3–5 days and about 88 KB [reported: the two notes]. The echo arena is 88 KB for 1 s mono [inferred] |
| Installing on a real FM-1 | the dev kit and JieLi's dongle (on order); the kit's own dump and restore; the gate on the owner's unit ([docs/07](docs/07-recovery-and-risk.md) §4 rule 1); Lunar running on the board; Lunar's own update service and installer, which no doc planned before 2026-10-01 [inferred: install-path study] | [The path to an installable build](#the-path-to-an-installable-build) below; [docs/14](docs/14-verification-ladder.md) §4–5; [docs/08](docs/08-roadmap.md) Phases 2, 3 and 6; [docs/10](docs/10-usb-key-dongle.md) §5–6 | about 30–50 sessions and 25–40 h of owner bench time to a private preview; 8–14 of the sessions fit before the kit arrives [inferred] |
| DX7 patches and SysEx, presets on the synth | the device firmware's USB-MIDI class and flash storage (after the gate); an msfa engine: Six-Op FM is Plaits' DX7-style engine, and `engines/` has no msfa [verified] | [docs/08](docs/08-roadmap.md) Phase 4; docs/13 stage D | not estimated |
| MIDI out over USB | device: a USB-MIDI class on the SDK's `usb_device` code, which has none [verified: V1.1.9 and V1.2.0 trees], mirroring stock's jacks and endpoints. Simulator: an outbound event queue in `fm1_app`, a worklet drain and a Web MIDI port picker | [docs/08](docs/08-roadmap.md) Phase 4; I12 | device 3–5 days on the kit; simulator 1–2 days for notes, plus about 1 for sequencer routing and clock [inferred] |
| MIDI out on the jack | an unpowered continuity map of J3 on an opened unit (the owner's decision); a static decode of V15's UART1 TX pin assignment | [docs/01](docs/01-hardware.md) §3–4; [Bench checks that write nothing](#bench-checks-that-write-nothing) | 2–3 h unpowered, 1 h of passive capture, ½–2 days of static decode [inferred] |
| BLE MIDI | an SDK-linked build (L1). A BLE-MIDI GATT service on the SDK's `ble_op_*` API, which has a GATT-server example but no BLE-MIDI [verified: AC79 SDK V1.2.0]. No device-control path over BLE: stock dispatches vendor syscmds from BLE too [reported: AL-255]. A measured cost | [docs/05](docs/05-open-source-feasibility.md) §3.4; [docs/08](docs/08-roadmap.md) Phase 5; [docs/11](docs/11-plugin-platform.md) §2 | 3–5 days for the service on the kit; ½ day to measure its flash and RAM by linking with BLE on and off [inferred]. In stock V13, Bluetooth's code is 55–115 KB by AL-255's two function indexes [verified: sums over both] |
| The second core | the kit; the second-core probe ([docs/14](docs/14-verification-ladder.md) §5 step 5b and §5.1). The public SDK has no task-to-core API [verified]. JieLi supplies the single-core `system.a` only on request [reported: JieLi AC79 doc 7.40] | docs/14 §5.1; [docs/11](docs/11-plugin-platform.md) §2 and §8 (unknown 3); [docs/08](docs/08-roadmap.md) Phase 7 | 4–5 days on the kit; 2–3 days to rehearse an audio/control split on the desktop under ThreadSanitizer [inferred] |

## The path to an installable build

This is the path from today to an installable preview and a release
[inferred: install-path study, 2026-10-01, unless marked].
- Milestones are numbered I0–I15 so they do not clash with docs/13's M0–M4.
- **[bench]** marks the owner's bench work.
- Nothing is written to the owner's FM-1 before I9 passes
  ([docs/07](docs/07-recovery-and-risk.md) §4).

**Two things no plan covered before.**
1. **Lunar needs its own update service.** The way back to stock goes
   through the FM-1's update path, and its first step is answered by the
   installed app, which stages the loader [reported: AL-255].
   - The public AC79 SDK has the hand-off: `update_mode_api_v2` writes
     `UPDATA_PARM` [verified: `update.c` at V1.1.9].
   - It has no USB-MIDI device class [verified: V1.1.9 and V1.2.0 trees],
     and the FM-1's loader is M-VAVE's own: its 19,969-byte `usb_hid_ota`
     `ota.bin` is not the SDK's 271,182-byte one [verified: sizes].
   - So an app built on the SDK can be taken back to V15 by stock-path
     tools only if it answers that step itself (I13), with a fail-open path
     that does not depend on its USB stack.
2. **Lunar needs its own installer.** Baud Girl's installer starts only from
   V15 or Baud Girl's own versions [reported], so it cannot take a unit
   running Lunar back. AL-255's client rejects identity blocks with a bad
   checksum [reported]. Lunar's identity block must be valid, and its
   installer is built from AL-255's `fm1_ota.py` (WTFPL [verified]) (I3,
   I15).

There are two tracks, and they meet at the gate:
- **Desk work** (I0–I4) can start now.
- **Hardware work** starts when the AC79 kit and JieLi's dongle arrive.

**Critical path:** kit delivery → I6 → I9 → I11 → I12 and I13 → I14 → I15.

### Now, before the kit

**I0. Owner decisions.** Needs nothing. About 1 h of the owner's time. To
decide:
- The preview is an app on JieLi's SDK (docs/05's L1), not a hook build on
  V15 like FM-1+VA.
- After the gate, the first rollback test takes the unit back to M-VAVE's
  V15 through the stock path.
- Which dongle opens the FM-1: JieLi's if the kit rehearsal works,
  otherwise ours. czietz's Pico tool drives push-pull and is ruled out for
  this unit (docs/10 §1.1).
- If the kit is late, whether to run the gate first with our RP2040 dongle.
  docs/08 Phase 2 allows it; docs/14 prefers the kit first.
- A version range clear of M-VAVE (up to FM-1_019) and Baud Girl (FM-1_020
  and up) [reported: docs/03 §5], for example FM-1_500 and up; and whether
  to tell Baud Girl and AL-255.
- The preview's scope (below).
- *Done when:* the answers are recorded in CLAUDE.md or docs/08.

**I1. Toolchain and pinned SDK.** Needs the owner's approval for a change
on the build host. 1–2 sessions.
- **Toolchain.** JieLi's Linux toolchain and post-build tools still
  download: the links redirect to `jieli-linux-toolchains-20250805.1` and
  post-build tools `20260923.1` [verified: HTTP redirects, 2026-10-02 UTC;
  nothing downloaded]. Archive both privately with their SHA-256, and never
  commit them.
- **SDK.** The AC79 SDK (Apache-2.0) at tag `AC79NN_SDK_V1.1.9_2023-08-01`.
  Its `uboot.boot` is the same file as the head of M-VAVE's V15 package (git
  blob `b6cb71ea…`). The V1.2.0 branch's is not (`1cc0f013…`) [verified: gh
  api and `git hash-object`].
- **Build.** A container image on the build host; build `demo_hello` for
  wl82.
- *Done when:* two clean builds are byte-identical and the hashes are
  recorded (docs/14 §5 step 2, done early).

**I2. Compile-only stage B and the ladder runner.** The pi32v2 half needs
I1; the desktop half needs nothing. 3–5 sessions.
- **pi32v2 half.**
  - Build `engines/`, the sequencer core and the app layer with JieLi's
    Clang 4.0.1: C99 and C++11, `-fno-exceptions -fno-rtti`, and `-fwrapv`
    on vendored code.
  - Read `objdump` for fused multiply-adds, with and without
    `-ffp-contract=off`.
  - List the libm functions used.
  - Compare a `sizeof`/`alignof` table with `-m32`.
- **Desktop half.**
  - Replace `fm1_app_t`'s 1.17 MB of arenas with one sized arena and strip
    rendering.
  - Write the ladder runner and the R0 manifest.
  - Write the `bsp_*` contract of docs/14 §4.3, with a desktop
    implementation.
- *Done when:* everything links for pi32v2, or each blocker has a
  workaround. The linker map must also put a candidate preview chain inside
  the FM-1's limits [inferred: docs/01 §1–2, docs/11 §2]:
  - no SDRAM;
  - about 514 KB of usable SRAM, less our system's own use;
  - an app area up to `0x8F000` (V15's layout) or `0xD5000` (FM-1+VA's).

**I3. Packaging, imaging and installer tools.** Offline. Needs nothing: the
V15 and FM-1_092 packages are in `scratch/`. 2–4 sessions.
- **A `.fwsc` builder** that starts from the user's own V15 package. It
  writes:
  - our `app.bin`;
  - a directory that leaves USR, BTIF and key_mac untouched;
  - an identity with a valid ID-block checksum;
  - recomputed CRCs.

  It refuses unless the head, `ota.bin`, `cfg` and `isd_config.ini` are
  byte-identical to V15's.
- **A raw 1 MB flash-image builder** for mask-ROM writes (kagaimiq's
  jl-misctools, MIT).
- **Our own installer client**, built from AL-255's `fm1_ota.py`, with
  Echomatter's framing fix, the head check, resume from the loader, and an
  identity check after reboot.
- **A device model** that speaks both update steps (docs/03), for offline
  tests.
- *Done when:*
  - V15 and FM-1_092 rebuild byte-identical from their parts;
  - the client passes offline tests: the 481-byte final block, timeouts,
    resume, and a wrong head refused.

  Nothing is sent to a device.

**I4. The FM-1's pin map, read from V15.** Needs I1's vendor `objdump`. 2–4
sessions.
- What to map:
  - the key matrix ports and the 74HC595 pins;
  - the encoders and ADC channels;
  - the SPI1 TFT pins and GPIO 39–42;
  - the DAC pin map and the amp enable;
  - UART RX for MIDI in, and USB.
- *Done when:* a `board_fm1` pin table ties every entry to a V15 address
  with a mark, and conflicts are listed as bench checks.

### When the kit arrives

**I5. Inventory. [bench]** Needs the kit and the dongle. ½ session, 1–2 h.
- docs/14 §5 step 1.
- Also record the dongle's version, its DIP switch and its "update" button.
  Try what the button does on the kit only.

**I6. Recovery rehearsal on the kit. [bench]** Needs I5. 1–2 sessions,
2–4 h.
- Enter `UBOOT1.00` with JieLi's dongle, on a direct USB 2.0 port of a
  Linux host. jl-uboot-tool's device finder has no macOS path [reported:
  docs/10 §5].
- Run `jl-uboot-tool --chip wl82`, read-only first: JEDEC ID, dump ×2,
  restore, dump ×3, boot.
- Repeat the entry with our RP2040 dongle.
- Two identical dumps do not prove that reads are raw. Also write, re-dump
  and compare before trusting a restore [inferred].
- *Done when:* two identical dumps, a restore and a third identical dump,
  and the kit boots. The FM-1 procedure is written down with exact
  commands.

**I7. Kit bring-up. [bench]** Needs I1 and I6. 2–3 sessions, 2–3 h.
- docs/14 §5 steps 4–6:
  - `demo_hello` through mask ROM, with the rehearsed restore as the safety
    net;
  - the UART console, and a toggled pin on a logic analyser;
  - the FPU probe image;
  - Test Sine through the DAC, captured twice.
- The second-core probe (docs/14 §5 step 5b) follows here. It is off the
  preview's critical path, because the preview runs on one core.

**I8. Stage B numbers.** Needs I2 and I7. 3–5 sessions, 1–2 h of owner time
(the runs are unattended).
- docs/14 §5 steps 7–9:
  - R2 against R0;
  - cycles per block;
  - ten minutes live from the DAC interrupt;
  - heap and stack high-water marks.
- *Done when:* there is a cycle table and FM-1 voice caps, and a preview
  chain is chosen. Its worst block must leave room for UI, USB and scanning
  (suggested: 70 % or less of 348,160 cycles at 240 MHz), and its SRAM total
  must fit.

### On the owner's FM-1

**I9. The gate. [bench]** Needs I6 and I3's compare script. Independent of
I7 and I8. 1 session, 2–3 h.
1. Run the identity query (FM-1_092 expected) and charge the battery.
2. With the unit off, start the dongle keying, then switch on.
3. Confirm `UBOOT1.00` on a Linux host's direct USB 2.0 port, with no hub,
   and read the JEDEC ID.
4. Take dump 1. Power-cycle, re-enter, and take dump 2. Compare them.
5. Compare the dumps with the FM-1_092 package where they map. Explain every
   difference (encryption, VM, USR, BTIF, key_mac) before writing anything.
6. Write dump 1, boot, and read the identity. Take dump 3 and compare.
7. Restore once more, for docs/08's "two cycles".

The dumps stay private: they hold the chip ID, the Bluetooth address and
key_mac.

*Done when:* dumps 1, 2 and 3 have the same SHA-256, and the unit boots
FM-1_092 after each restore. docs/07 rule 1 is then met for this unit;
record that in notes/ and CLAUDE.md.

**I10. Rollback rehearsal through the stock path. [bench]** Needs I9, I3 and
the I0 decision. 1 session, 1–2 h.
- Install V15 over FM-1_092 with our client.
- Dump in three states: while the loader waits after step 1; after step 2;
  and, optionally, back on FM-1_092.
- *Done when:*
  - our client works for both steps on hardware;
  - the identity reads FM-1_015;
  - USR is unchanged;
  - the dump diffs show where step 1 stages `ota.bin` and `UPDATA_PARM`.
    That decides Lunar's fail-open design.

**I11. First code on the FM-1. [bench]** Needs I9, I4, I7 and I3's image
builder. 2–3 sessions, 2–4 h.
- **RAM only first.** `jlrunner.py` loads a small image that drives the
  LEDs or the TFT. A power cycle brings the installed firmware back
  [reported mechanism: kagaimiq; untested on WL82].
- **Then a flash image.** `demo_hello` plus `board_fm1`, with the fail-open
  key combination and a watchdog boot counter. Restore the dump afterwards.
- **Logs** go out over USB, through the SDK's CDC class, or on the TFT. The
  TRS jack is MIDI in only [reported], so docs/08 Phase 3's "UART on the TRS
  jack" does not apply.
- *Done when:* the build id shows, the LEDs blink and the TFT draws;
  fail-open and the counter are tested; and a mask-ROM restore follows.

**I12. Drivers and the app on the SDK. [bench, iterative]** Needs I11, I8
and I4; overlaps I13. 6–10 sessions, and 6–10 h of owner time over 2–3
weeks.
- **Display:** the TFT strip flush on SPI1.
- **Controls:** the 41-input matrix and its LEDs; the encoders and MASTER.
- **Audio:** a DAC DMA ring at the measured rate, in 64-frame blocks.
- **MIDI:** a USB-MIDI device class, which is new work because the SDK has
  none [verified]; MIDI in on UART RX.
- **App:** the app layer in one sized arena, running I8's chain.
- Each driver runs first on the kit, where the kit has the part, and then
  on the FM-1 by mask-ROM write, with the dump as the net.
- *Done when:*
  - keys play and knobs edit on the FM-1;
  - screens are hash-equal to R0;
  - pre-DAC audio is class E against R0;
  - notes from a DAW and from the TRS jack play;
  - an hour passes without an underrun.

**I13. Update service, fail-open and boot counter. [bench for the power
cuts]** Needs I11, I3 and I10. 3–5 sessions, 3–5 h.
- **Why it is needed.** Lunar has to answer the stock update path itself.
  Otherwise nothing can take it back to V15 without a dongle.
- **What exists and what is ours.** The SDK has the hand-off:
  `update_mode_api_v2` writes `UPDATA_PARM` [verified: `update.c` at
  V1.1.9]. The transfer itself is ours:
  - the identity reply, with a valid checksum;
  - the upgrade command;
  - the package pull and its CRCs;
  - staging the package's own stock `ota.bin`;
  - the hand-off and a reset into the stock loader.
- **Fail-open.** A key combination read before USB and audio start goes
  straight to update mode, without our USB-MIDI driver.
- **Boot counter.** After N failed boots, the unit goes to update mode.
- **Power cuts and unplugs** at every stage: on the kit first, then on the
  FM-1 (docs/07 rule 5).
- The step-1 state machine can be written now and tested on the desktop
  against I3's client.
- *Done when:*
  - V15 installs from Lunar with our client;
  - a deliberately boot-looping build reaches update mode by itself;
  - every interrupted transfer resumes or recovers without the dongle.

**I14. The OTA round trip: the earliest safe installable preview. [bench]**
Needs I12 (a minimal feature set), I13, I3 and I10. 1–2 sessions, 1–2 h.
- Build Lunar's `.fwsc` with I3.
- Install it over V15 and over FM-1_092 with our client, then roll back to
  V15.
- Dump before and after each step.
- *Done when:*
  - V15 → Lunar → V15 and FM-1_092 → Lunar → V15 both work through the
    stock path;
  - the head's SHA-256 never changes, and USR is byte-identical;
  - power cuts during step 2 resume.

**I15. A preview for other owners, then a release.** Needs I14. 2–4
sessions, 2–4 h, plus testers.
- **Installers:** a CLI, and a Web MIDI page beside the virtual FM-1.
  - They build the package on the user's machine, from the user's own V15
    `.fwsc` plus our `app.bin`, so no vendor binary is redistributed.
  - They refuse unless the head matches, the identity is known and the
    connection is direct.
  - They explain how to go back.
- **The build:** the shareable one only. That means MIT, BSD and Apache code
  plus the SDK's libraries, no GPL, and Six-Op FM's patch data either
  reviewed or left out (engines/README.md).
- **Rollout:** first to owners who already have a working `UBOOT` dongle and
  their own identical dumps (the two in issue #2), then public.
- *Done when:*
  - at least 3 other units, on Windows and macOS hosts, have installed and
    rolled back with no unrecoverable failure;
  - the README's "Installing on your FM-1" and docs/08 Phase 6 are updated;
  - there is a GitHub release with its CHANGELOG section.

### The earliest safe installable preview

It is the I14 build, offered first only to owners who can already restore
their FM-1 through mask ROM.
- **In it:**
  - a minimal chain, for example Macro ×12, Ensemble and Plate: 89,200 B of
    instance memory on 32-bit [verified: the sum of engines/README.md's
    sizes];
  - the panel and the screen;
  - USB-MIDI and TRS MIDI in;
  - the update service, fail-open and the watchdog boot counter.
- **Not in it:** BLE, USB audio, the sequencer, MIDI effects, and any flash
  write beyond the boot counter.
- **Why it is safe at that point:**
  - docs/07 §4 rules 1, 2, 4 and 5 are met on the owner's unit;
  - both round trips through the stock path are shown, with USR unchanged
    and power cuts resuming;
  - a boot-looping build returns to update mode by itself;
  - the first outside installs go to owners who can recover with a dongle,
    and a public release waits on their results.

**Rough total** [inferred]:
- 30–50 sessions and 25–40 h of owner bench time;
- about 4–7 weeks of work from the kit's arrival to the private preview;
- 1–2 weeks more to the outside preview.

**Still open before the preview:**
- Where does step 1 stage `ota.bin` and `UPDATA_PARM`, and does the staged
  loader survive step 2? (I10)
- Can code on the WL82 enter mask-ROM `UBOOT1.00` itself? That would give
  owners who have a dump a recovery path without a dongle.
- Does jl-uboot-tool read raw or decrypted flash, given AL-255's per-chip
  OTP seed? (I6)
- Does M-UPGRADE accept an install onto a unit that reports FM-1_5xx?
  Probably, since stock downgrades worked [inferred].
- Does the WL82 have RAM that survives a watchdog reset, for the boot
  counter?
- Distribution: does the installer fetch M-VAVE's V15 `.fwsc`, or ask the
  user for it?

## Building and testing

```bash
python3 tools/check_msfa_table.py path/to/app.bin            # msfa table finder (tested on V13/V14)
python3 tools/extract_fwsc_from_updater.py M-UPGRADE-FM1 -o FM-1.fwsc   # carve package from the updater
python3 reference/jl-misctools/firmware/fwunpack_newfw.py FM-1.fwsc     # unpack (needs: pip install crcmod)
python tools/fm1_identify.py                                   # read-only identity query + decode, any OS (verified on hardware)
python -m pytest                                               # tools, PIO emulation, dongle/ROM co-simulation and engine tests
make -C engines && engines/build/fm1-render --list             # engine platform, desktop build (docs/11, engines/README.md)
python3 -m http.server 8000 -d sim/web/www                     # the virtual FM-1 at http://localhost:8000/ (sim/web/README.md)
FM1_SIM_HOST=user@host sim/web/build-on-aeon.sh                # rebuild and check its WebAssembly module in containers on a Docker host
tools/fm1_identify.sh                                          # Linux, ALSA raw MIDI, read-only, untested
python3 reference/FM-1-RE/tools/fm1_ota.py scan                # AL-255's client, read-only scan
```

`reference/` and `scratch/` are git-ignored; clone third-party repositories
and keep vendor packages there.

## Conventions

- **Confidence marks**, used throughout the docs:
  - **[verified]:** checked in this project against binaries, photos or SDK
    files;
  - **[reported]:** taken from a named source and not independently
    re-checked;
  - **[inferred]:** our reading of the evidence.
- **Never commit vendor binaries:** `.fwsc`, `app.bin`, `uboot.boot`, the
  JieLi toolchain, updater apps. Link to their sources instead.
- **No private details:** no LAN addresses or user names in commits. Remote
  hosts come from environment variables such as `FM1_SIM_HOST`.
- **Licences.**
  - The repository is MIT.
  - GPL code, and code under similar terms such as LXR's, may be brought in
    when needed, each in its own `third_party/<name>/` with its licence and
    an `UPSTREAM.md`.
  - A firmware binary that links JieLi's closed libraries must not be shared
    (released, or sent to anyone) if it contains GPL or LXR code. Personal
    builds may, so keep such code behind a build switch and keep the
    MIT/BSD-only build shareable.
  - GPL and LXR code cannot be combined in one shared work, and MIDIbox code
    needs its author's permission.
  - Details are in [docs/12](docs/12-sequencer.md) §6 and
    [docs/11](docs/11-plugin-platform.md) §7.
- **Credit prior work by name.** Quote, summarize and link rather than copy
  ([README](README.md#credits)).
- **Changes go through pull requests.**
  - Each PR says its intent, its release notes and its test results.
  - Each PR adds its release notes to [`CHANGELOG.md`](CHANGELOG.md).
