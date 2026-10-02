# Lunar Modulator

![Lunar Modulator: INTERGALACTIC MODULATION STATION](assets/branding/banner.png)

**INTERGALACTIC MODULATION STATION**

Lunar Modulator is open firmware for the M-VAVE FM-1: research, and later
code, toward a fully open-source firmware for the M-VAVE (Cuvave) **FM-1**, a
~€70 battery-powered six-operator, 12-voice FM synthesizer with 27 silicone keys,
a 1.54" colour TFT, USB-C (MIDI + audio), BLE-MIDI and a 3.5 mm MIDI input.
Until 2026-10-01 the project was called "Open firmware for the M-VAVE FM-1"
(`ip2k/mvave-fm1-open-firmware`). It is an independent project, not
affiliated with or endorsed by M-VAVE, Cuvave or any space agency.

> **Status (2026-09-29): research phase; first read-only bench session done.**
> This project has flashed nothing. V15 has been unpacked and compared with
> V14 ([`notes/2026-09-06-bench.md`](notes/2026-09-06-bench.md)), and the case
> has been opened for [photos](photos/2026-09-29/). A third-party firmware,
> Baud Girl's [FM-1+VA](https://baudgirl.com/work/FM-1+VA), now ships to users
> through the stock update path; the owner installed it, so the unit
> identifies as `FM-1_092` instead of stock `FM-1_015`, and its package has
> been diffed against V15
> ([`notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md`](notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md)). The `USB_KEY`
> recovery dongle is specified, implemented and simulated but not yet tried
> ([`docs/10`](docs/10-usb-key-dongle.md), [`dongle/`](dongle/)). Start with
> [`docs/05-open-source-feasibility.md`](docs/05-open-source-feasibility.md) for
> the verdict and [`docs/09-first-session-checklist.md`](docs/09-first-session-checklist.md)
> for what to do with the device on the bench.

## Features

Nothing here runs on an FM-1 yet: the engines, effects and sequencer core
are built and tested on a desktop, and the virtual FM-1 runs them in a
browser. The screenshots below are that virtual FM-1, showing the
firmware's own 240 × 240 screen, and one figure compares its output with
the native renderer's.

### Sound engines

Five swappable sound engines behind one C API with no heap
([`engines/`](engines/README.md)). **Macro** is Plaits' eight light
models (virtual analogue, phase distortion, terrain, chiptune, VA pair,
waveshaper, 2-op FM, wavetable) with 12 voices; **Shapes** is Braids' 47
shapes; **Macro Heavy** is Plaits' other 13 (string machine, chords,
speech, modal, particle, three drums and more) with 4 voices; **Six-Op FM**
is Plaits' DX7-style engine with its 96 patches, 8 voices; **Sophie** is a
16-pad FM drum kit, an MIT Schwung module compiled unmodified through a
compatibility shim. Each engine pages its parameters four at a time, one
per knob, as the FM-1's four free knobs want.

<table>
<tr>
<td><img src="assets/screenshots/screen-macro.png" width="150" alt="Macro on VA Pair: Model, Harmonics, Timbre and Morph with bars, and an oscilloscope strip"></td>
<td><img src="assets/screenshots/screen-shapes.png" width="150" alt="Shapes on Pluck: Shape, Timbre, Color and Attack"></td>
<td><img src="assets/screenshots/screen-macro-heavy.png" width="150" alt="Macro Heavy on its string machine model"></td>
<td><img src="assets/screenshots/screen-sixop.png" width="150" alt="Six-Op FM on patch E.PIANO 1: Patch, Brightness and Envelope"></td>
<td><img src="assets/screenshots/screen-sophie.png" width="150" alt="Sophie's kick pad: Pad, Tune, Decay and Model"></td>
</tr>
<tr>
<td align="center">Macro</td>
<td align="center">Shapes</td>
<td align="center">Macro Heavy</td>
<td align="center">Six-Op FM</td>
<td align="center">Sophie</td>
</tr>
</table>

### Effects

Effects chain after any engine: **Plate** (Rings' reverb), **Ensemble** and
**Diffuse** (Plaits), and **PSX Verb**, a second MIT Schwung module. The
virtual FM-1 has two effect slots: FX shows them, SELECT moves between
them and their pages, ALGORITHM picks the effect, SEL then SELECT swaps
the two. A host limiter on the bus keeps twelve voices started in phase
under full scale.

<img src="assets/screenshots/screen-fx.png" width="240" alt="FX mode: slot 1 Plate, slot 2 PSX Verb selected, with its Model, Decay, Mix and Level">

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

### Sequencer core

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

The firmware's app layer (panel logic, the effect chain and the screen
drawing) compiled to WebAssembly and run in an AudioWorklet, behind a
to-scale drawing of the FM-1's front panel: the 27 keys, the 14 buttons
with their LEDs, MASTER and the seven encoders. The screen is the
firmware's own RGB565 frame buffer, copied to a canvas; every one of its
287 screens passes a layout check with no text cut short and nothing
closer than 4 px. Turn KNOB1–4 and the four parameters on the page follow.
Play it with the mouse, a touch screen, the computer keyboard or a MIDI
keyboard.

![Lunar Modulator in the browser: the to-scale FM-1 panel with a chord held on Macro](assets/screenshots/virtual-fm1.png)

<img src="assets/screenshots/panel-params.png" width="560" alt="The screen beside KNOB1-4, turned: Model 2-op FM, Harmonics 0.68, Timbre 0.28, Morph 0.81"> <img src="assets/screenshots/phone.png" width="200" alt="The page on a 390-pixel-wide phone: the panel keeps playable key sizes and scrolls sideways">

On a phone the panel keeps playable sizes (keys 31–35 px wide, no target
under 24 px) and scrolls sideways in its own box; turned to landscape it
fits whole.

## Try it in your browser

The built module is in the repository, so all it takes is Python 3 and a
current browser:

```bash
cd sim/web/www && python3 -m http.server 8000
```

Open <http://localhost:8000/> and press **Power on** (browsers only start
audio after a click). The page needs `http://localhost` or `https://`;
opening `index.html` as a file does not work, and over plain `http://` from
another machine's address Power on says so instead of starting. It loads
nothing from anywhere else and finds its files relative to itself, so
`sim/web/www/` can also be published as static files, at any path.

**Browsers.** It needs WebAssembly, an AudioWorklet and a secure context.
It is tested in Chromium only: headless Chromium 153 on Linux, from a local
server and over https under a sub-path, and Chromium 152 on macOS, from
`python3 -m http.server`. Firefox, Safari, real touch screens and MIDI
hardware are not tested yet. "Connect MIDI input" needs a browser with Web
MIDI; without it the panel and the computer keyboard still play.

**Controls.**

| Control | Mouse or touch | Computer keyboard |
| --- | --- | --- |
| Keys | Click or touch; lower on a key plays louder | `A` `S` `D` `F` `G` `H` `J` `K` `L` `;` `'` play the white keys F3 to B4, `W` `E` `R` `Y` `U` `O` `P` `[` the black ones |
| OCT− / OCT+ | Click | `Z` / `X`. Both together reset octave and transpose; hold one and turn ALGORITHM to transpose ±12 |
| SELECT | Drag up or down, or scroll | `←` `→`: the page, or in FX mode the slot and its pages |
| PRESETS | Drag or scroll | `↑` `↓`: the sound engine |
| ALGORITHM | Drag or scroll | `-` `=`: the engine's model (Model, Shape, Patch or Pad), or in FX mode the effect in the selected slot |
| KNOB1–4 | Drag or scroll | Tab to a knob, then the arrow keys: the four parameters on the screen |
| MASTER | Drag or scroll | Tab to it, then the arrow keys: the volume |
| FX, SEL, GLO, HOME | Click | Tab to a button, then Enter or Space. FX: the effect slots; SEL then SELECT: swap them; GLO: rate, block, RAM, voices, effects, octave and transpose; HOME: back to the sound |
| Everything | | `Esc` releases every note |

ENV, LFO, EDIT, SAVE, ARP, SEQ, PLAY/STOP and REC show "not in the
simulator yet". The dropdowns under the panel pick the sound and both
effects directly, "Screen ×2" shows the screen enlarged, and a MIDI
keyboard plays notes with pitch bend (±2 semitones), CC 7 (volume) and
CC 123 (all notes off).

**Rebuilding the module.** Only needed after changing `engines/` or
`sim/web/src/`. It builds in containers on any Linux machine with Docker
that you can reach over ssh, checks the result sample by sample against
the native renderer, plays the page in headless Chromium, and only then
replaces `sim/web/www/fm1.wasm`:

```bash
FM1_SIM_HOST=user@host sim/web/build-on-aeon.sh   # about 20 s once the images are pulled
python -m pytest tests/test_sim_web.py            # the native checks, no WebAssembly needed
```

Details, the panel's measurements and the parity results are in
[`sim/web/README.md`](sim/web/README.md).

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
  has never been demonstrated on this device.
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
  with 578 KB of SRAM and no Rust or LLVM target. Movy's 8-knob parameter-page
  UI maps almost one-to-one onto the FM-1's 8 knobs, and its Move-style
  sequencer model is a good specification for a C reimplementation.

## Recommended path

1. **Bench characterization, read-only** ([docs/09](docs/09-first-session-checklist.md)).
2. **Prove recovery before anything else** ([docs/07](docs/07-recovery-and-risk.md)):
   get the chip into its mask-ROM USB boot mode through the USB-C port with the
   `USB_KEY` signal, dump the flash, restore it, repeat. Everything else waits
   on this. The dongle for it is [docs/10](docs/10-usb-key-dongle.md) / [`dongle/`](dongle/).
3. **First custom code through the mask-ROM route**: the vendor SDK's
   `demo_hello` for AC791N, adapted to the FM-1 board.
4. **The synth**: port msfa / Synth_Dexed, USB-MIDI class device, DX7 SysEx,
   presets in flash.
5. **UI and sequencer** inspired by Movy ([docs/06](docs/06-movy-and-schwung.md)).
6. **Ship through the stock OTA path** (new version number, stock flash head),
   as Baud Girl's releases already do, so users install without opening the case.

## Repository map

| Path | What it is |
| --- | --- |
| [`docs/01-hardware.md`](docs/01-hardware.md) | SoC, memory, board, connectors, what is still unknown |
| [`docs/02-stock-firmware.md`](docs/02-stock-firmware.md) | Package format, boot chain, what the stock app is made of, the msfa finding |
| [`docs/03-update-protocol.md`](docs/03-update-protocol.md) | The SysEx update protocol and its step-1 version gate |
| [`docs/04-prior-art.md`](docs/04-prior-art.md) | Every project, SDK, tool and thread this work stands on |
| [`docs/05-open-source-feasibility.md`](docs/05-open-source-feasibility.md) | What "open firmware" can mean here, the blockers, the verdict |
| [`docs/06-movy-and-schwung.md`](docs/06-movy-and-schwung.md) | Why Movy cannot be ported and what to take from it anyway |
| [`docs/07-recovery-and-risk.md`](docs/07-recovery-and-risk.md) | Recovery paths, risk register, rules of engagement |
| [`docs/08-roadmap.md`](docs/08-roadmap.md) | Phased plan with exit criteria |
| [`docs/09-first-session-checklist.md`](docs/09-first-session-checklist.md) | Exact commands for the first hands-on session |
| [`docs/10-usb-key-dongle.md`](docs/10-usb-key-dongle.md) | The RP2040 `USB_KEY` dongle: protocol, hardware, firmware, bench procedure |
| [`docs/11-plugin-platform.md`](docs/11-plugin-platform.md) | Feasibility of a Schwung-style engine/plugin platform: Schwung module compatibility, Mutable Instruments engines, loader design |
| [`docs/12-sequencer.md`](docs/12-sequencer.md) | Feasibility of an Elektron-style sequencer with per-step parameter locks: semantics, prior art and licences (Movy, MCL, Eloquencer, LMN-3, …), data model, timing, controls, staged plan |
| [`docs/13-movy-port.md`](docs/13-movy-port.md) | Port plan for replicating Movy's sequencer on the FM-1: exact semantics, mapping to the FM-1's controls, memory and CPU, a C99 no-heap core, tests, staged plan |
| [`dongle/`](dongle/) | Dongle firmware (PIO + C), ROM/dongle simulator, tests |
| [`tools/check_msfa_table.py`](tools/check_msfa_table.py) | Finds the msfa algorithm table in an `app.bin` (tested on V13 and V14) |
| [`tools/extract_fwsc_from_updater.py`](tools/extract_fwsc_from_updater.py) | Carves the embedded `.fwsc` out of an M-UPGRADE updater binary (verified on the macOS DMG) |
| [`tools/fm1_identify.py`](tools/fm1_identify.py) | Read-only identity query with decoder, any OS via mido (verified on hardware 2026-09-06) |
| [`tools/fm1_identify.sh`](tools/fm1_identify.sh) | Read-only SysEx identity query via ALSA `amidi` (untested on hardware) |
| [`notes/2026-09-06-bench.md`](notes/2026-09-06-bench.md) | Bench session 1: USB descriptors, identity reply, MIDI probes, V14 vs V15 |
| [`tests/`](tests/), [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | pytest suite (tools, PIO emulation, dongle/ROM co-simulation) and CI: tests on Linux/macOS, RP2040 UF2 build, AL-255's suite on our fork |
| [`notes/2026-09-06-research-log.md`](notes/2026-09-06-research-log.md) | What was checked, what was blocked, where the numbers come from |
| [`notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md`](notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md) | Baud Girl's FM-1+VA, its `FM-1_092` package diffed against V15, and the owner's board photos |
| [`photos/`](photos/) | The owner's photos of their unit, by date, with the crops the notes cite |
| [`engines/`](engines/) | The engine platform, stage A: the C engine API, sound engines and effects from Mutable Instruments code, a Schwung module shim, a desktop renderer and tests |
| [`notes/upstream-candidates.md`](notes/upstream-candidates.md) | Findings worth sending to other projects, none posted yet |

Confidence marks used throughout the docs: **[verified]** checked in this
project against binaries, photos or SDK files; **[reported]** taken from a
named source and not independently re-checked; **[inferred]** our reading of
the evidence.

## Repository history

The research phase was produced in a Claude Code cloud session that could not
create GitHub repositories (the integration returned `403`), so its first
commit briefly lived on an orphan branch of `ip2k/busybar-dual-timer`. On
2026-09-06 that branch was cloned into `~/Developer/mvave-fm1-firmware` as this
repository's `main`, published as `ip2k/mvave-fm1-open-firmware`. The stray
branch can then be deleted:

```bash
git push https://github.com/ip2k/busybar-dual-timer --delete claude/mvave-fm1-open-firmware-ly2w6u
```

On 2026-10-01 the project was renamed Lunar Modulator and the repository
`ip2k/lunar-modulator`; GitHub redirects the old URLs [reported, GitHub's
documentation on renaming a repository]. The local folder keeps its old name.

## Credits

This is a synthesis of other people's work, credited in
[`docs/04-prior-art.md`](docs/04-prior-art.md). In particular: **aroum**
(updater analysis, teardown photos), **AL-255** (firmware disassembly, protocol
captures, safety analysis, experimental firmware; WTFPL), **kagaimiq** (JieLi
documentation and tools), **probonopd** (SMK-37 Pro notes), Google's
music-synthesizer-for-android and the Dexed / Synth_Dexed / MiniDexed lineage,
and **charlesvestal** and **DimaDake** for Schwung and Movy. Vendor firmware
images are not redistributed here; see the sources.

## License

MIT for the contents of this repository. Third-party material keeps its own
license as noted where it is referenced.
