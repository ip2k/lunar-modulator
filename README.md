# Open firmware for the M-VAVE FM-1

Research toward a fully open-source firmware for the M-VAVE (Cuvave) **FM-1**, a
~€70 battery-powered six-operator, 12-voice FM synthesizer with 27 silicone keys,
a 1.54" colour TFT, USB-C (MIDI + audio), BLE-MIDI and a 3.5 mm MIDI input.

> **Status (2026-09-06): research phase; first read-only bench session done.**
> Nothing has been flashed and the case has not been opened. The owner's unit
> identifies as `FM-1_015`; V15 has been unpacked and compared with V14
> ([`notes/2026-09-06-bench.md`](notes/2026-09-06-bench.md)). The `USB_KEY`
> recovery dongle is specified, implemented and simulated but not yet tried
> ([`docs/10`](docs/10-usb-key-dongle.md), [`dongle/`](dongle/)). Start with
> [`docs/05-open-source-feasibility.md`](docs/05-open-source-feasibility.md) for
> the verdict and [`docs/09-first-session-checklist.md`](docs/09-first-session-checklist.md)
> for what to do with the device on the bench.

## Firmware development

The `codex/firmware-decoding` branch extends the local Python workbench with
firmware analysis, local projects, reversible byte changes and package
rebuilding. Start it with `python tools/fm1_workbench.py --open`; see
[15 — Firmware development](docs/15-decoding-workflow.md).
Full decoding, DSP replacement, device installation and recovery remain active
work. Offline integrity checks do not prove that a modified image will run.

### Decoding milestone

The decoding work has a concrete byte-level foundation and several bounded
sound-engine footholds:

| Area | Current evidence |
| --- | --- |
| Parser | A bounded pi32v2 parser records 2-, 4-, and 6-byte instruction boundaries, preserves raw bytes for unknown forms, decodes established operands and control flow, and rejects unsupported input without inventing semantics. |
| Paired instructions | V15 pair markers and companion rows are retained in the disassembly. The offline interpreter reads both instructions from the pre-write register state, commits their writes atomically, and rejects ambiguous or unsupported packet behavior. |
| Operators | The V15 three-operator kernel is bounded to 183 instructions / 544 bytes with full supported-operand coverage, explicit phase/increment/level state rows, a 64-sample loop, and 19 reproducible verification vectors. This is a verified foothold for one kernel path, not every FM algorithm. |
| Envelope | The V15 envelope helper has 79 instructions / 208 bytes, a reconstructed 34-byte state prefix, stage transition logic, and a 204-of-208-byte match against the V009 helper. Its names and full upstream modulation path remain inferred or open. |
| FX chain | Six effect slots, a V15 dispatcher, eighteen callback pointers, and indexed object/enabled/parameter state fields. |
| Distortion | A V15 callback with a traced final tanh lookup: ×512 position scaling, sign handling, linear interpolation, gain, and an explicit 1.0 saturation path. |
| Chorus | A V15 44-byte state, 884-byte delay buffer, ring length 220, and a process callback that loads the exact 513-cell sine table. The cross-repository analysis identifies the structure as a modulated delay. |
| Reverb and delay | V15 allocation and ring/stage observations; the cross-repository analysis adds multi-stage comb/delay/feedback and interpolated-delay context. |
| Whole audio path | The cross-repository FM-engine analysis places the six-slot effects pass after the voice mix and before DAC output; the version and address-space boundary is recorded in [22 — Effects evidence roll-up](docs/22-effects-evidence-rollup.md). |

The parser, packet timing, operator names, envelope correspondence, effect
names, and several inner equations remain hypotheses or bounded models. The
evidence and remaining boundaries are recorded in
[13 — Static firmware decoding](docs/13-firmware-decoding.md),
[16 — Operator lookup mathematics](docs/16-operator-mathematics.md),
[17 — V15 operator state and attenuation interpolation](docs/17-operator-abi.md),
[20 — Envelope update and stage transitions](docs/20-envelope-decoding.md),
[21 — Reversible operator experiments](docs/21-offline-operator-experiments.md),
[18 — Effects decoding](docs/18-effects-decoding.md),
[19 — Effects lookup mathematics](docs/19-effects-mathematics.md), and
[22 — Effects evidence roll-up](docs/22-effects-evidence-rollup.md).

## Browser workbench

Use the [FM-1 Workbench](docs/11-workbench.md) for a local browser interface to
read device identity, inspect firmware packages and application images, and
export a timestamped debug report. Start it with
`python tools/fm1_workbench.py --open` after installing
`requirements-workbench.txt`. Offline inspection needs only Python.
This first bench contribution is read-only; firmware writing remains subject to
the project's recovery gate.

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
- **One non-stock package has run on an FM-1.** On 2026-09-04 a contributor
  to AL-255's repository (Echomatter, [PR #2](https://github.com/AL-255/FM-1-RE/pull/2))
  installed a V15-derived package whose version identity was bumped to 016;
  the stock verifier accepted it, the device ran it (with a broken USB
  descriptor), and AL-255's corrected client rolled it back to stock V15.
  The version gate is therefore host/verifier policy, not a fuse. There is
  still **no proven recovery path** for a device whose application does not
  run: one flash bank, no debug pads, no recovery button, and JieLi's
  mask-ROM USB boot mode has never been demonstrated on this device.
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
6. **Solve the OTA verifier gate** so users can install without opening the case.

## Repository map

| Path | What it is |
| --- | --- |
| [`docs/01-hardware.md`](docs/01-hardware.md) | SoC, memory, board, connectors, what is still unknown |
| [`docs/02-stock-firmware.md`](docs/02-stock-firmware.md) | Package format, boot chain, what the stock app is made of, the msfa finding |
| [`docs/03-update-protocol.md`](docs/03-update-protocol.md) | The SysEx update protocol and the verifier gate that blocks custom packages |
| [`docs/04-prior-art.md`](docs/04-prior-art.md) | Every project, SDK, tool and thread this work stands on |
| [`docs/05-open-source-feasibility.md`](docs/05-open-source-feasibility.md) | What "open firmware" can mean here, the blockers, the verdict |
| [`docs/06-movy-and-schwung.md`](docs/06-movy-and-schwung.md) | Why Movy cannot be ported and what to take from it anyway |
| [`docs/07-recovery-and-risk.md`](docs/07-recovery-and-risk.md) | Recovery paths, risk register, rules of engagement |
| [`docs/08-roadmap.md`](docs/08-roadmap.md) | Phased plan with exit criteria |
| [`docs/09-first-session-checklist.md`](docs/09-first-session-checklist.md) | Exact commands for the first hands-on session |
| [`docs/10-usb-key-dongle.md`](docs/10-usb-key-dongle.md) | The RP2040 `USB_KEY` dongle: protocol, hardware, firmware, bench procedure |
| [`docs/13-firmware-decoding.md`](docs/13-firmware-decoding.md) | Static pi32v2 parser, paired-instruction handling, address map and coverage |
| [`docs/17-operator-abi.md`](docs/17-operator-abi.md) | V15 operator state, packet timing and three-operator kernel contract |
| [`docs/20-envelope-decoding.md`](docs/20-envelope-decoding.md) | V15 envelope state and stage transition reconstruction |
| [`docs/21-offline-operator-experiments.md`](docs/21-offline-operator-experiments.md) | Reversible bounded operator experiments and verification limits |
| [`docs/22-effects-evidence-rollup.md`](docs/22-effects-evidence-rollup.md) | Cross-repository effects evidence and V15 reconciliation |
| [`dongle/`](dongle/) | Dongle firmware (PIO + C), ROM/dongle simulator, tests |
| [`tools/check_msfa_table.py`](tools/check_msfa_table.py) | Finds the msfa algorithm table in an `app.bin` (tested on V13 and V14) |
| [`tools/extract_fwsc_from_updater.py`](tools/extract_fwsc_from_updater.py) | Carves the embedded `.fwsc` out of an M-UPGRADE updater binary (verified on the macOS DMG) |
| [`tools/fm1_identify.py`](tools/fm1_identify.py) | Read-only identity query with decoder, any OS via mido (verified on hardware 2026-09-06) |
| [`tools/fm1_identify.sh`](tools/fm1_identify.sh) | Read-only SysEx identity query via ALSA `amidi` (untested on hardware) |
| [`notes/2026-09-06-bench.md`](notes/2026-09-06-bench.md) | Bench session 1: USB descriptors, identity reply, MIDI probes, V14 vs V15 |
| [`tests/`](tests/), [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | pytest suite (tools, PIO emulation, dongle/ROM co-simulation) and CI: tests on Linux/macOS, RP2040 UF2 build, AL-255's suite on our fork |
| [`notes/2026-09-06-research-log.md`](notes/2026-09-06-research-log.md) | What was checked, what was blocked, where the numbers come from |

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
