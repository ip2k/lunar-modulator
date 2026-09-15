# Open firmware for the M-VAVE FM-1

Research toward a fully open-source firmware for the M-VAVE (Cuvave) **FM-1**, a
~€70 battery-powered six-operator, 12-voice FM synthesizer with 27 silicone keys,
a 1.54" colour TFT, USB-C (MIDI + audio), BLE-MIDI and a 3.5 mm MIDI input.

> **Initial bench baseline (2026-09-06): first read-only session completed.**
> Nothing has been flashed and the case has not been opened. The owner's unit
> identifies as `FM-1_015`; V15 has been unpacked and compared with V14
> ([`notes/2026-09-06-bench.md`](notes/2026-09-06-bench.md)). The `USB_KEY`
> recovery dongle is specified, implemented and simulated but not yet tried
> ([`docs/10`](docs/10-usb-key-dongle.md), [`dongle/`](dongle/)). Start with
> [`docs/05-open-source-feasibility.md`](docs/05-open-source-feasibility.md) for
> the verdict and [`docs/09-first-session-checklist.md`](docs/09-first-session-checklist.md)
> for what to do with the device on the bench.

## Firmware decoding and local development

**A reproducible offline path from firmware bytes to bounded DSP execution.**
The `codex/firmware-decoding` branch connects instruction decoding, operator
mathematics, effects-routing evidence, and a local workbench for exact-byte
experiments, package rebuilding, and rollback.

> **Draft / work in progress.** The implemented scope is described below.
> This is not a complete firmware replacement, a hardware-validated DSP engine,
> or a proven installation and recovery path.

### Decoder, operator mathematics, and execution

The bounded **pi32v2 decoder** records 2-, 4-, and 6-byte instruction
boundaries, retains raw bytes for unknown forms, and decodes supported operands,
memory accesses, immediates, predicates, and control flow. V15 paired-instruction
markers and companion rows remain visible rather than being flattened away.
The interpreter evaluates paired instructions against their shared pre-write
state and commits their writes atomically. **That timing is inferred from the
V15 evidence, not independently established CPU behavior.** Unsupported
instructions, ambiguous packets, illegal memory accesses, and exhausted
instruction budgets stop execution.

The **V15 three-operator kernel** is bounded to **183 instructions / 544 bytes**,
with three 16-byte operator-state rows and a fixed 64-sample loop. A separate
integer reference model and bounded instruction interpreter are compared using
**19 reproducible verification vectors** covering output and feedback. This
validates the stated kernel model, not every FM algorithm or a complete voice.

The reconstruction preserves the arithmetic details that change the result:

- **Attenuation:** previous-target state, the zero sentinel, logarithmic level
  conversion, rounded `/64` ramps, and increments before the first lookup.
  Rounding overshoot is retained rather than silently clamped away.
- **Feedback and phase:** signed 32-bit wraparound, the caller-adjusted shift
  `min(outer_shift + 2, 16) + 1` for ordinary nonnegative inputs, feedback from
  the final third-operator output, and caller-owned phase writeback.
- **Lookup behavior:** formula-reproduced exponent and log-sine tables with
  exact fingerprints, including the combined-logarithm sign behavior when an
  attenuation ramp underflows.

Evidence: [instruction decoding](docs/13-firmware-decoding.md),
[lookup mathematics](docs/16-operator-mathematics.md), and
[operator state and execution contract](docs/17-operator-abi.md).

### Envelope and effects reconstruction

| Area | Concrete result | Remaining boundary |
| --- | --- | --- |
| Envelope | 79 instructions / 208 bytes; a reconstructed 34-byte state prefix and stage-transition logic; 204 of 208 bytes match the V009 helper, with four relocation-related changes. | Semantic names, full upstream modulation, and MSFA correspondence remain qualified. |
| Effects routing | A 656-byte V15 dispatcher, six slots, and eighteen init/update/process callback pointers, with indexed object, enabled, slot-ID, and parameter fields. | Filter, Reverb, Delay, Distortion, Chorus, and Phaser bindings remain inferred from ordered UI labels. |
| Distortion | A 268-byte state and a traced nonlinear output stage: ×512 lookup scaling, sign restoration, adjacent tanh-table interpolation, separate gain, and an explicit 1.0 saturation path. | Pre-filters, user-parameter mapping, and floating-point details remain open. |
| Chorus | A 44-byte state, 884-byte delay buffer, ring length 220, and a process callback loading the exact 513-cell sine table. | External chorus/flanger analysis supports a modulated-delay interpretation; phase, interpolation, rate/depth, and mix remain open. |
| Reverb and delay | V15 state allocations, ring boundaries, and processing-stage observations, with external multi-stage comb/delay/feedback and interpolated-delay context. | Full equations, mode bindings, and parameter scaling remain open. |

The pinned AL-255 FM-engine analysis places a six-slot effects pass after voice
mixing and before DAC output. Its image and address presentation differ from
V15; that result is corroborating context, not a verified V15 end-to-end map.

Evidence: [envelope reconstruction](docs/20-envelope-decoding.md),
[effects decoding](docs/18-effects-decoding.md),
[effects lookup mathematics](docs/19-effects-mathematics.md), and the
[cross-repository effects roll-up](docs/22-effects-evidence-rollup.md).

### Reversible, executable experiments

The offline experiment API ties a specific firmware edit to a numerical result
and a reversible manifest. It accepts only the exact V15 source image and
expected original bytes, with equal-size, nonoverlapping changes confined to
the verified kernel or lookup-table ranges.

One documented experiment changes **a single byte** to shift the final
operator output by 12 bits instead of 13. For the specified test vector,
**all 64 samples and both final feedback words are exactly half the stock
interpreter result**, and rollback restores every original byte. This is a
bounded interpreter result, not a general half-volume modification or a
hardware-audio claim. See [the experiment and reproduction
steps](docs/21-offline-operator-experiments.md).

## Browser workbench

From the repository root, start the local interface with **Python 3.10 or later**:

```bash
python tools/fm1_workbench.py --open
```

Offline inspection, decoding, project storage, editing, and rebuilding use the
Python standard library. Install [requirements-workbench.txt](requirements-workbench.txt)
for the optional MIDI identity functionality. The offline workflow needs no
vendor application, vendor USB driver, or external web service.

The workbench provides package and application inspection, hex views, decoded
findings, source-hash-bound analysis, explicit change manifests, integrity-checked
rebuilds, rollback, and timestamped reports. Local `.fm1proj` projects retain
immutable original and child revisions with hashes and parent relationships.
These private SQLite files contain firmware bytes and must not be published.

**Device communication remains read-only.** Editing and rebuilding local files
is supported; the new analysis and experiment paths do not flash hardware.
Successful integrity checks or byte-exact rollback are not evidence of device
compatibility or recovery.

Start with the [workbench guide](docs/11-workbench.md) and
[development workflow](docs/15-decoding-workflow.md). The
[package-inspection contract](docs/12-package-inspection.md) and
[rebuild contract](docs/14-firmware-rebuild.md) define the supported boundaries.

### Implementation map

These are executable components, not only research notes:

| Source | Responsibility |
| --- | --- |
| [`fm1_decode.py`](tools/fm1_decode.py) | Instruction decoding; executable, memory, feature, and DSP evidence |
| [`fm1_pi32.py`](tools/fm1_pi32.py) | Bounded integer interpreter, atomic paired execution, and source-bound operator experiments |
| [`fm1_operator.py`](tools/fm1_operator.py), [`fm1_verify_operator.py`](tools/fm1_verify_operator.py) | Independent integer block model and finite interpreter/reference verification vectors |
| [`fm1_dsp.py`](tools/fm1_dsp.py), [`fm1_effects.py`](tools/fm1_effects.py) | Lookup-table reproduction and fingerprints; V15 effects callback and stage evidence |
| [`fm1_package.py`](tools/fm1_package.py), [`fm1_rebuild.py`](tools/fm1_rebuild.py) | Container inspection and extraction; exact-source patching, metadata reconstruction, and inverse changes |
| [`fm1_project.py`](tools/fm1_project.py), [`fm1_workspace.py`](tools/fm1_workspace.py) | Persistent revisions and provenance; bounded loaded files, hex views, and rebuild operations |
| [`fm1_workbench.py`](tools/fm1_workbench.py), [`web/`](web/) | Loopback HTTP API and browser interface |
| [`tests/`](tests/), [`ci.yml`](.github/workflows/ci.yml) | Regression coverage and continuous-integration configuration |

The focused tests cover decoder semantics, control flow, arithmetic edge cases,
memory permissions, packet hazards and atomicity, provenance invalidation,
rebuild integrity, experiment boundaries, project persistence, and the local
API. Optional private-image checks require `FM1_V15_APPLICATION`; their absence
is reported as a skip, not a successful firmware execution check.

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
| [`docs/11-workbench.md`](docs/11-workbench.md) | Local browser workbench, device identity, inspection, and reporting |
| [`docs/12-package-inspection.md`](docs/12-package-inspection.md) | Container validation, extraction, and integrity coverage |
| [`docs/13-firmware-decoding.md`](docs/13-firmware-decoding.md) | Static pi32v2 parser, paired-instruction handling, address map and coverage |
| [`docs/14-firmware-rebuild.md`](docs/14-firmware-rebuild.md) | Exact-source patches, package rebuilding, and reversible manifests |
| [`docs/15-decoding-workflow.md`](docs/15-decoding-workflow.md) | Setup, local projects, development workflow, and completion criteria |
| [`docs/16-operator-mathematics.md`](docs/16-operator-mathematics.md) | Reproduced exponent/log-sine tables and operator lookup mathematics |
| [`docs/17-operator-abi.md`](docs/17-operator-abi.md) | V15 operator state, packet timing and three-operator kernel contract |
| [`docs/18-effects-decoding.md`](docs/18-effects-decoding.md) | Six-slot effects dispatcher, callback table, state, and buffer evidence |
| [`docs/19-effects-mathematics.md`](docs/19-effects-mathematics.md) | Effects lookup tables and the distortion nonlinear stage |
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
| [`notes/2026-09-14-workbench.md`](notes/2026-09-14-workbench.md) | Workbench and decoding development record |
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
Third-party attribution and licensing details are retained in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## License

MIT for the contents of this repository. Third-party material keeps its own
license as noted where it is referenced.
