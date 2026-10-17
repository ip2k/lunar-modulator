# Reuse M-VAVE Workbench Without Replacing Lunar

2026-10-17. Research and proposed implementation plan for **Lunar Modulator,
open firmware for the M-VAVE FM-1**. Personal project. No migration, vendor
build, firmware installation, device connection or upstream contact was performed.

## Recommendation

**Keep Lunar's SDK-free GPL native direction and selectively reuse the new
workbench's source, protocols and engineering ideas. Do not rebuild everything
on its binary SDK now.** [inferred]

The workbench is useful: it exposes manufacturer board code, a connected
editor/library/update workflow, sample tools, and documented interfaces to USB
audio, Bluetooth audio and BLE-MIDI. But the shipped native synthesis, sequencer, startup and
platform services are coupled inside a proprietary library. Its application
licence exception does not extend to unrelated GPL components. Replacing our
base would therefore trade an advanced source-based integration for a different,
restricted integration with unresolved engine replacement and release rights.
It would also replace Lunar's musical model with a much narrower instrument
unless we port that model back in. [verified source boundaries; inferred tradeoff]

Recommended next milestone: a **bounded offline reuse pilot**, with a board/audio
comparison and a source-only format converter. Preserve existing Lunar engines,
sequencer/state, editor, source collector and installer safeguards. Consider a
vendor runtime fork only if M-VAVE provides a separable platform API and the
exact combined component set has compatible permissions. The executable task
breakdown is in the [implementation plan](2026-10-17-mvave-workbench-plan.md).

## Evidence and version identity

- [Workbench](https://open.m-vave.com/fm1-workbench), fetched 2026-10-17.
- [Upstream tree](https://github.com/m-vave/fm1_open/tree/b178ac43c25f010c60a878056fb5331fe693fd62),
  commit `b178ac43c25f010c60a878056fb5331fe693fd62`.
- [V13 development kit](https://open.m-vave.com/releases/V13/2a3b2ede16ac49c867831315714ef9d8c532c70ce28ce1dcf3fc76f0a9f68f57/FM1-Open-V13-Development-Kit.zip),
  SHA-256 `2a3b2ede16ac49c867831315714ef9d8c532c70ce28ce1dcf3fc76f0a9f68f57`.
  All 150 regular files match that GitHub commit byte-for-byte; all 65 files
  listed in the kit manifest pass their hashes. [verified]
- `app/version.h` declares release `V13` and product `FM-1_8000013`.
  This is **Open V13**, not the old stock package informally called V13.
  The included stock recovery asset is separately labelled V15. [verified source]
- The [machine-readable receipt](2026-10-17-mvave-workbench-evidence.json)
  records exact refs and hashes. No vendor binaries are committed here.

Here, **[verified]** means inspected source, bytes or Git metadata; **[reported]**
means a vendor description or retained build/bench observation not rerun;
**[inferred]** means our engineering assessment. UI capabilities below are
source/manual observations, not a live browser, listening or device acceptance
test. The web reader failed on the site; direct HTTPS retrieval succeeded.

## What the workbench provides

The source presents four connected surfaces: play/edit, project and sound
library, device update, and a searchable/printable bilingual manual. [verified]

| Area | Provided capability | Relevance to Lunar |
| --- | --- | --- |
| Virtual instrument | FM-1 panel/LCD, 27 keys, mouse/keyboard controls, draggable encoders, editable LCD values, MIDI input, local browser saves, import/export | Useful physical-panel UX reference; does not replace Lunar's advanced editor |
| Sound | DX7, 303, 808, PSG, PLUCK, SAMPLER; envelopes, LFO, arpeggiator, shared reverb/delay and track sends | Audition/reference source and optional individually licensed DSP candidates; not parity with Lunar's catalogue |
| Sequence | Eight tracks; independent 16/32/48/64-step loops, step/live recording, count-in, swing, probability, ties, chords, parameter locks, copy/paste and undo/redo | Useful focused controls; retaining Lunar semantics is a migration requirement |
| Projects | 16 factory and 16 user slots; explicit read, save, backup, restore and verified read-back | Adopt the explicit pending/saved state and round-trip verification pattern |
| Patches | Whole-project `.fm1`, track-sound `.fm1t`, DX7 `.syx` single patches and 32-patch banks | Good offline import/export candidates; `.fm1t` excludes sequence steps |
| Samples | Eight shared slots; WAV selection/trimming/preview, mono resampling and SEA5 encoding; whole-bank `.fm1s` backup/restore | A useful sample preparation pipeline, subject to format/licence tests |
| Device audio | Public APIs for USB playback, Bluetooth input, output mixing and USB recording | Valuable interface reference; native transport implementations are binary |
| Bluetooth MIDI | Simultaneous Bluetooth audio/MIDI; BLE peripheral/central roles, scanning, connection/status and pairing management | Potential transport work saved, but no generic inbound short-MIDI callback for Lunar is declared |
| Tuning | Per-track tuning API and persistence; no dedicated tuning editor | Candidate future adapter, not a reason to replace Lunar's core |
| Installation | Browser USB-MIDI update, return to official Open image, stock V15 restore and force-migration UI | Protocol/UX reference; not dead-device recovery |
| Developer tools | APP/board/web source, native SDK archives, hashed manifest/toolchain inputs, Windows build launcher, C# packager, WASI web build, source-download URL requirement | Useful supply-chain practices; Linux portability and target rebuild remain untested |

[verified source/manual inventory] Entry points:
[template/manual](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/sdk/Update.html.in),
[simulator](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/sdk/Simulator.js),
[English strings](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/sdk/I18n.js),
[audio API](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/sdk/include/fm1_audio_io.h),
[MIDI/Bluetooth API](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/sdk/include/fm1.h#L22-L86).

Important limits [verified unless marked otherwise]:

- The manual describes a project-wide pool of 16 chords and 16 single-step
  parameter locks. Do not assume lossless conversion of arbitrary Lunar songs.
- Connecting MIDI does not synchronize a project. Browser edits remain local
  until explicitly written; read-back comparison establishes the saved status.
  Project files omit sample audio; the sample bank needs a separate backup.
- The WAV tool accepts PCM 8/16/24/32-bit or float32, mono/stereo, 8–192 kHz,
  at most 32 MiB/120 seconds; it produces mono 16-bit/32 kHz SEA5 data.
  See [Samples.js](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/sdk/Samples.js).
- There is a useful upstream defect candidate: UI/manual capacity says about
  **20.45 seconds / 456 KiB**, while current writes reserve the final 4 KiB for
  tuning and enforce **452 KiB**. With a 512-byte header and 228-byte/320-frame
  blocks, that is at most **2,027 blocks / 20.27 seconds**, before per-slot
  rounding. This is a source-derived bound, not a device measurement.
  `app/instrument.h:289-296`, `sdk/Samples.js:4,24,33-43,125-131` and
  `sdk/WebUpdate.js:577` provide the concrete evidence. Do not copy the larger
  capacity into a Lunar importer. Any upstream report needs owner sign-off.

## What is actually open, and where replacement becomes expensive

[verified] Public sources cover board audio/panel/LCD, screen UI, project/sample
storage orchestration and transfer handling. A separate `web/engine/` and
`web/synth/` implementation supplies browser sound/sequencing. Native firmware
links `sdk/lib/libfm1_engine.a`; the manifest explicitly identifies native ELF
objects without LLVM bitcode or DWARF. See the
[build script](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/sdk/Build.ps1)
and [web build](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/tools/Build-Web.ps1).

[verified archive inspection] The engine archive has one real member,
`engine_startup.S.o` (1,379,076 bytes). Its symbol table includes strong engine,
sequencer and platform/service definitions, with APP callbacks unresolved.
The supplied build uses `--whole-archive` and requires stock DSP/sequencer
symbols in SRAM. There is no separately packaged platform-only library or
documented drop-in alternative-engine configuration in this kit.

[inferred] It is possible to investigate section garbage collection and symbol
substitution, but one member alone does not prove every section must survive.
Conversely, editing the public audio callback does not prove the closed engine,
state model and dependencies disappear. Binary rewriting is a poor foundation
for a maintained open firmware product. Ask for a supported platform-only
SDK/render callback interface before investing in that route.

[verified] `app/board/audio.c:27-63` exposes the DMA interrupt, render call,
external-audio mix, half-buffer ownership check and overrun/peak counters. This
is immediately valuable for comparison against Lunar's timing failures.
The vendor's native contract uses **128 frames** (`sdk/synth.json`), while the
current Lunar evidence measures **64-frame** production. Rates, sample formats,
clock basis, interrupt deadlines and buffering need explicit adapters; never
compare block counts without converting to frames/time. [inferred consequence]

[verified source] The transport headers expose Bluetooth audio/MIDI together,
BLE central/peripheral roles, scan/connect/disconnect/status and pairing controls.
Their implementations remain in the binary runtime. `fm1_midi_post` feeds the
sealed instrument; the documented inbound APP hook delivers complete SysEx,
capped at 1,024 bytes, without receive timestamps. **There is no declared generic
short-MIDI receive callback for Lunar.** A usable platform seam therefore needs
explicit timestamped MIDI ownership as well as a render callback. ([MIDI and
Bluetooth contracts](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/sdk/include/fm1.h#L22-L86))

[verified source] **Native synth API 7 and browser synth API 4 are different
contracts.** The browser substitutes engine, sequencer and runtime code; it
stubs BLE and supplies inactive USB/Bluetooth audio streams. Hardware audio is
44,118 Hz while simulator time advances at 44,100 Hz. Its initial 4 MiB memory,
up-to-32 MiB growth and 128 KiB stack do not model native SRAM capacity.
A working browser build therefore establishes neither native sound parity nor
radio, flash-stall or interrupt behavior. ([Native API](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/app/synth/engine.h#L7-L14),
[browser API](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/third_party/synth/engine.h#L7),
[simulator](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/web/engine/Simulator.c),
[audio contract](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/app/board/fm1_audio.h#L7-L21),
[web build](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/tools/Build-Web.ps1#L77-L83))

[verified] The supported build is Windows x64/PowerShell with pinned JieLi
clang 4.0.1 r3 executable hashes. Web builds use WASI SDK 27. The kit provides
checks and reports, but no build was run here. Aeon's Linux toolchain is not
automatically equivalent to those Windows executables. A portable web build is
a reasonable bounded experiment; native binary compatibility is a separate
gate. Source URL validation checks a URL's shape, not source completeness.

## Licence implications for the GPL core work

The [APP licence](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/LICENSE.md)
is GPL-3.0-only with an additional permission to combine covered code with the
listed FM1 binary SDK. The
[component terms](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/THIRD_PARTY.md)
permit proprietary engine binaries for FM1 devices, including redistribution;
they do not provide proprietary source. Other component notices still apply.
[verified text; this is an engineering dependency assessment, not legal clearance]

Consequences [inferred from those express boundaries]:

1. A modified M-VAVE APP with covered/permissive additions has a plausible
   licensed vendor-SDK route, subject to a complete component inventory.
2. The exception does **not** grant rights for Dinghy, Felucca, fm1-x0x or other
   unrelated GPL code. Our existing native application cannot simply inherit
   it. Turning `FM1_GPL_MODS` off still leaves the GPL Dinghy platform and does
   not turn all application files into permissive code.
3. Reusing public APP/board code in a source-based GPL Lunar path is a much
   better candidate: retain notices and verify every dependency. Do not mark
   copied GPL code MIT or assume its binary calls have open implementations.
4. Reusable MIT core code remains available under its original grant. A
   hypothetical vendor edition must select files/components individually,
   rather than carry the current combined GPL application into the exception.
5. The vendor's Apache-labelled boot/recovery resources and FreeRTOS MIT notice
   are new provenance evidence to audit against the exact shipped bytes; they
   are not permission to assume every old JieLi component changed licence.

## Current Lunar branches: preserve this work

Refs were checked against GitHub. [verified snapshot]

| Branch/ref | SHA | Finding |
| --- | --- | --- |
| Local `main` in original checkout | `64209e3c08222ada0eb61afcaef89e909ae07955` | Old PR #98 baseline; not the current project state |
| `origin/main` | `bfa042446f36c8647efddc6d76b06753d2a5b612` | Published editor through PR #148; root MIT |
| `feature/2026-10-11@installable-firmware` | `1f12ad5b8d6a865268af94179a3442183a680602` | SDK-free native GPL application with preserved MIT core; active integration stream |
| `codex/2026-10-14-native-license-transition` | `3ac501eb8ae4fbcce2d4991ec64d22d02eae2dd2` | Equivalent patch integrated as `4b52219e` |
| `codex/2026-10-14-sdk-gpl-source-bundle` | `4fc99026b1b52f1e1e7225dd7ac7dd50443b9afa` | Equivalent patch integrated as `a139fcb1` |
| `codex/gpl-source-inputs-20261016` | `e57577a18c819e921a43647932448135690cdcd9` | Four patches already represented by equivalent patches in installable |

The last three are not missing work merely because their original commits are
not ancestors: `git cherry` finds equivalent patches. Installable and remote
main diverge by **161 main-only / 1,173 feature-only commits**, from merge base
`b335dc2c450473dc375163aec7fa679e1b099cc3`. Do not merge the whole stream as a
side effect of this evaluation. Exact installable head had no GitHub check runs
or matching PR in the queried APIs; historical test receipts are separate.
[verified]

At the pinned installable head, the important existing pieces are [verified source]:

- `LICENSING.md`, `LICENSE` and `LICENSE-MIT`: combined GPL native application,
  preserved MIT sequencer/state and individually marked reusable files.
- Dinghy platform at upstream `d44df7db09b98ccad2f1233b8f83f5f09c04829e`, with
  Felucca/SLOOP provenance, existing board and USB integrations.
- Shared application, engine catalogue, sequencer, state codec, native adapters,
  audio queue/pool and MIDI paths. The platform does not need replacing just
  to add an editor/library feature.
- Open runtime replacements: musl subset, compiler-rt, printf, TLSF and tinf.
  Target build rejects undefined symbols and performs SDK-free/key/RAM-call
  audits. It still uses vendor compiler/header inputs.
- Tuple-bound selected-source collection and private selected-module installer
  work. Source-completeness and distribution eligibility remain explicitly false.

The latest retained E7 build records an **854,528-byte** app in an
**860,644-byte** budget: **6,116 bytes spare**, all 55 selected modules / 13
production engines. This is source `e7b65f1a103ac049ff4f898c7980b10433ca2ecb`,
not proof of a rebuild of the branch head. SAVE remains disarmed; source closure
and target trace work remain incomplete. [reported: installable `HANDOFF.md:9275-9355`]

Partial physical progress is real: native Trio display/panel/notes were observed.
All-thirteen Event Horizon audio/cold boot failed owner acceptance; later recovery
remained unresolved following interrupted flashing. [reported: installable
`AGENTS.md:60-94`] No device state was queried here. Do not repeat the old
root checkout's blanket claim that no Lunar application has ever run, or replace
the real unresolved acceptance gates with a successful browser preview.

Pinned branch sources:
[licensing](https://github.com/ip2k/lunar-modulator/blob/1f12ad5b8d6a865268af94179a3442183a680602/LICENSING.md),
[handoff](https://github.com/ip2k/lunar-modulator/blob/1f12ad5b8d6a865268af94179a3442183a680602/HANDOFF.md),
[native direction](https://github.com/ip2k/lunar-modulator/blob/1f12ad5b8d6a865268af94179a3442183a680602/notes/2026-10-12-native-gpl-firmware-direction.md).

## Installation and recovery are separate decisions

[verified] The supplied `uboot.boot` hashes to
`b88747cb72afc554d6ca078594a89f4fdcea5a74d26345b633f8e2524e7e3415`
(14,488 bytes). Lunar's `tools/jieli/package_guard.py` requires
`730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef`
(14,384 bytes). The new kit cannot pass that unchanged stock-SPL condition.
Its partition/package policy also reserves 536,576 user bytes and 32 KiB minimum
VM (`sdk/Package.cs:13`); this is not Lunar's E7 layout.

[verified source; inferred arithmetic] With its 536,576-byte USER reservation,
32,768-byte minimum VM, 4,096-byte BTIF and boot/app boundary, the kit's package
inequality allows a **raw application ceiling of 453,921 bytes before sector
rounding**. The retained Lunar E7 application is 854,528 bytes under a different
layout: it cannot simply be placed in that vendor allocation. This comparison
establishes a layout/size conflict, not the size of a redesigned or selectively
linked image. The native build also requires **at least 49,152 bytes of runtime
heap**, separate from engine state, audio buffers and stacks; the linker declares
523,596 bytes of ram0 plus 28,672 bytes of cache RAM and no SDRAM. Any proposed
vendor integration needs an exact linked map and retained guard comparison,
not browser memory figures or relocatable archive totals. ([Packager](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/sdk/Package.cs#L141-L153),
[heap guard](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/sdk/Build.ps1#L126-L165),
[linker memory](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/sdk/config/linker.ld.in#L13-L28))

[verified source] Library transfers use `7D FM 02` SysEx framing, separate from
the stock `00 59` updater. Force mode relaxes compatibility selection but still
requires a responding device/protocol. The stock-restore flow replaces factory
voice banks; Open projects/samples need separate backups. Retry support for a
responsive update loader cannot recover a non-enumerating unit. See
[WebUpdate.js](https://github.com/m-vave/fm1_open/blob/b178ac43c25f010c60a878056fb5331fe693fd62/sdk/WebUpdate.js).

[inferred] Keep Lunar's backup, package bounds, stock resource checks,
interruption/recovery evidence and explicit hardware admission. This research
authorizes no device traffic and proposes no replacement of those gates.

## Options compared

| Option | Benefit | Cost / blocker | Decision |
| --- | --- | --- | --- |
| Retain Lunar; selectively reuse open tools/driver knowledge | Preserves GPL engine catalogue, songs, editor and source ownership | Adapters, provenance and parity tests; hardware problems still need fixing | **Recommended** |
| Fork M-VAVE APP and keep its six native engines | Integrated vendor instrument and transport APIs | A different product with narrower sequencing; binary dependence and Windows build | Optional separate experiment, not full Lunar migration |
| Put all Lunar on vendor binary base | Potential USB/Bluetooth platform benefit | No supported platform-only seam; GPL exception gap; memory/layout changes; native/web divergence | **Do not start as a wholesale rewrite** |
| Replace their closed engine with their web engine sources | More readable sound/sequence implementation | Still must implement/uncouple native services and validate target performance; duplicates Lunar | Low priority |
| Obtain vendor source or a platform-only library/API | Could reduce board/transport effort | External dependency; exact licence compatibility still required | Ask only after owner approves upstream contact |

[inferred] Success is an offline, measured reduction in work without losing
Lunar behavior or source freedom—not the number of vendor files imported.
The plan defines stop conditions before a speculative migration consumes the
existing implementation effort.

## Research checks and limitations

Three focused Sol/Luna research agents examined branches, architecture and
features. No heavy compute was needed. A read-only Hera coordination README
fetch occurred before the newer maintenance exclusion was found; no further
Hera access or remote worker was launched. Current installable instructions
route compute to **Aeon only** during Hera RAID/M.2/NIC maintenance.

Rarefaction and Serena selected the original absolute checkout, which is stale
main; they were not retargeted over another active session. Rarefaction's exact
`package_guard.py:57:5` query matched source and its `main` caller. Serena found
`fm1_seq_create`, but its reference query missed known host/simulator callers.
Named Rarefaction search also hit its bounded-search limit. Branch-specific
claims therefore use exact Git objects/file reads, not absence inferred from an
index. No pi32v2 ABI, browser rendering, audible quality, rebuild reproducibility,
licence completeness or hardware acceptance was established by these tools.

Open questions for a future vendor discussion: supported platform-only SDK;
engine replacement ABI and memory ownership; source for runtime dependencies;
permissions covering the intended GPL combination; boot-resource provenance;
Linux build support; native/web parity tests; corrected sample-capacity text.
These are evaluation questions, not an issue or message sent upstream.
