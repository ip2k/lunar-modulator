# Developing Lunar Modulator

*The [README](README.md) presents Lunar Modulator as a product: what it does,
how to try it, and what is coming. This file holds everything technical:*
- the specifications and the hardware;
- how the software works;
- the research behind it ([`docs/`](docs/), [`notes/`](notes/));
- where development stands and the roadmap in detail;
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

- **The chip is a JieLi AC791N** (JieLi's "WL82" family) running JieLi's own
  Blackfin-derived **pi32v2** CPU core, executing in place from a 1 MB flash
  image. It is the same platform JieLi sells for Wi-Fi speakers and story
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

## How the software works

### The engine platform

- **The API:** five swappable sound engines and four effects behind one C
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
- **Threading:** audio and screen drawing share that one thread, as UI and
  audio share one core on the stock FM-1.
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
| SoC | JieLi AC791N (WL82), LQFP48, marking `C1xxxxx-11B8` (lot varies; owner's `C188612-11B8`); pi32v2 core, 240 MHz used of 320; 578 KB SRAM; 1 MB flash (probably in-package) |
| Memory map | flash XIP `0x02000000`, RAM `0x01C00000`, SFRs `0x1xxxx…0x5xxxx`, mask ROM `0xFFC0xxxx` |
| USB | normal `4C4A:C755` (USB-MIDI + UAC1, full-speed, product string `FM-1`), OTA loader `4D4A:4155` |
| Display | 240×240 RGB565 TFT on SPI1 (`0x11D00`), ST7789-class commands |
| Controls | 27 keys + ~14 LED buttons in a 41-input matrix; 8 knobs (stock reads 2 encoders + 2 ADC channels; split unresolved) |
| Audio | internal DAC, 44.1 kHz, 64-sample blocks; 12 msfa voices |
| Update | USB-MIDI SysEx, CRC16 only; step 1 refuses only the running version, so rebuilt packages with a new version install; the OTA loader can rewrite `uboot.boot` |

The details, with confidence marks, are in [docs/01](docs/01-hardware.md),
[docs/02](docs/02-stock-firmware.md) and [docs/03](docs/03-update-protocol.md).
Some points behind the roadmap:
- **The second core.** The AC791N has two pi32v2 cores. The stock kernel is
  an SMP scheduler that starts the second core but runs all its work on the
  first [reported: AL-255; [docs/11](docs/11-plugin-platform.md) §2].
  - Whether an SDK build can put audio on the second core is an open
    question ([docs/11](docs/11-plugin-platform.md) §8).
  - It is to be answered on the AC79 dev kit, whose AC7916 has the same two
    cores ([docs/07](docs/07-recovery-and-risk.md) §3,
    [docs/14](docs/14-verification-ladder.md)).
- **MIDI in and out.**
  - **Three inputs:** the stock firmware merges USB-MIDI, the TRS jack (DIN
    MIDI on the chip's UART) and BLE-MIDI through one parser [reported:
    AL-255; [docs/02](docs/02-stock-firmware.md)].
  - **The jack:** documented as input-only, but the stock code merges
    MIDI-thru into the UART's transmit line [reported: AL-255; docs/01 §4,
    docs/02 §6].
  - **Whether TX reaches the jack:** not known. It needs a trace of the
    board or a bench measurement [inferred].
  - **USB:** the FM-1 is a USB-MIDI device, and the stock firmware already
    sends notes over USB [reported: docs/02 §6]. MIDI out over USB is a
    firmware matter.
- **BLE MIDI.** It is a stock feature built on JieLi's closed Bluetooth
  libraries. They make up 719 of the 2,062 functions AL-255 classified in the
  stock app [reported: AL-255; [docs/02](docs/02-stock-firmware.md) §4,
  [docs/05](docs/05-open-source-feasibility.md) §3.4].
  - It can stay in builds that link JieLi's SDK, but not in a fully blob-free
    build.
  - docs/08 Phase 5 leaves keeping it as a decision.
  - The stack's RAM cost, out of the roughly 387 KB the stock layout leaves
    free ([docs/11](docs/11-plugin-platform.md) §2), is not measured
    [inferred].
- **Recovery.** The `USB_KEY` dongle for the chip's mask-ROM download mode is
  in [docs/10](docs/10-usb-key-dongle.md) and [`dongle/`](dongle/). Reports
  from other owners are in docs/10 §1.1.

## The roadmap in detail

| Roadmap line (README) | Depends on | Where it is planned |
| --- | --- | --- |
| Sequencer on the panel and screen | the sequencer core and Capture (both built); the gesture state machine and screen views (docs/13 stage M4) | [docs/13](docs/13-movy-port.md) §4 and §9 |
| Arpeggiator and MIDI effects | the sequencer's clock and note path in the simulator; a MIDI-effect engine kind (`FM1_KIND_MIDI_FX`, [`engines/seq.md`](engines/seq.md), "What M2 and later still need") | [docs/08](docs/08-roadmap.md) Phase 5; [`notes/2026-10-01-monome-oc-jhjlim-survey.md`](notes/2026-10-01-monome-oc-jhjlim-survey.md); more research under way |
| LFOs, envelopes, modulation matrix | engine parameter IDs and smoothing (docs/13 stage M2) | research under way |
| More effects | the effect API ([`engines/README.md`](engines/README.md)) and memory | research under way; memory is the limit ([docs/11](docs/11-plugin-platform.md) §2) |
| DX7 patches and SysEx, presets on the synth | the device firmware's storage (VM/flash) and USB-MIDI | [docs/08](docs/08-roadmap.md) Phase 4 |
| Installing on the FM-1 | dev-kit verification, then a proven dump and restore on the unit | [docs/14](docs/14-verification-ladder.md), [docs/08](docs/08-roadmap.md) Phases 2–6, [docs/07](docs/07-recovery-and-risk.md) |
| MIDI out over USB | the device firmware's USB-MIDI class driver | docs/08 Phase 4 |
| MIDI out on the jack | a board trace or bench measurement of the UART TX line | [docs/01](docs/01-hardware.md) §3–§4 |
| BLE MIDI | an SDK-linked build; its RAM cost | [docs/05](docs/05-open-source-feasibility.md) §3.4, [docs/08](docs/08-roadmap.md) Phase 5, [docs/11](docs/11-plugin-platform.md) §2 |
| The second core | an SDK build on the dev kit | [docs/11](docs/11-plugin-platform.md) §2 and §8, [docs/08](docs/08-roadmap.md) Phase 7 |

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
