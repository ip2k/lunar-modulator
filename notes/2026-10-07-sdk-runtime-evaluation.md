# SDK runtime versus a bare-metal Lunar (2026-10-07)

Evaluation only: no implementation, licence change, firmware package or device
traffic. Hardware policy was subsequently revised by the owner; soft-key
entry, full backup and bounded sector restoration now have bench evidence
([bench note](2026-10-07-fm1-softkey-bench.md)). Full-image restoration and
a Lunar application on hardware remain untested. This policy update does
not change the licensing analysis.

## Conclusion

**Prefer an SDK-free application runtime for the intended distributable GPL
instrument, while keeping reusable Lunar code MIT** [inferred]. Felucca proves
that this architecture is plausible on the FM-1 [reported: its releases and
community reports]; it does not prove Lunar's larger floating-point DSP, memory
budget, USB traffic or timing on that hardware. Keep the SDK as a reference and
compiler/header source where its individual licences permit, rather than importing
its runtime wholesale. Make the SDK-runtime decision separately from the existing
GPL-module switch. Do not copy Felucca's GPL HAL into a promised permissive image.

At the inspected 2026-10-07 baseline, **Lunar did not link a JieLi hardware
application** [verified at that inspection: build scripts and tracked firmware
tree]. Its pi32v2 check compiled individual objects and scanned candidate library
symbol tables; there was no Lunar app ELF/map from which to enumerate actual
linked SDK members. This is historical compile/provider evidence. The GPL-off
rule protects a *planned* SDK-linked distributable firmware. Desktop/browser GPL
builds distribute without those vendor runtime archives. See the dated integration
update below for the subsequent SDK-free diagnostic link.

## Evidence and exact scope

Inspected Lunar at `64209e3` (origin/main), SDK at
`e30b1ee375d1f2993fc23bf92c8b99006a6e5f9d` (V1.2.13 pin), and local Felucca reference
at `b0dcd53a251d5f5392fea9478b48244d322eeb2a` [verified: git rev-parse].

- [`compile-check.sh`](../tools/jieli/compile-check.sh) says compile-only and
  builds no firmware; [`in-container.sh`](../tools/jieli/in-container.sh) compiles
  each object, measures it and runs `nm --defined-only` over candidate archives.
  [`analyze.py`](../tools/jieli/analyze.py) matches undefined names against these
  symbol inventories; it does not perform archive extraction or a firmware link
  [verified]. The first matching provider is retained with `setdefault`, so a
  reported provider is a candidate, not proof that the linker must choose it.
- At that baseline, [`DEVELOPERS.md`](../DEVELOPERS.md), hardware budget
  paragraph, said vendor libraries and device platform code were not linked
  [verified at inspection].
- At that baseline, `firmware/` contained the Apache-2.0 fm1-nes boot-info bridge
  and its host test, without a board startup, scheduler, device USB or audio
  application [verified at inspection].
- The existing LAN compile report was read without rebuilding or modifying it:
  `/home/claude/mvave-fm1/sdk-v1213/out/{record.json,report.md}`. It records tree
  `41f083dfb272e5c054d15f5d8eaff412327bedb5`, 12 uncommitted files, GPL on,
  run `2026-10-06T10:01:55Z`, SDK pin above [verified]. It is historical evidence,
  not a link-map assertion for today's code. Its unresolved internal MIDI/mod
  names are also historical; later object-list fixes are in current source.

### What the inspected DSP objects needed

The historical compile report identifies these candidate providers [verified:
report table; no linked members claimed]:

| Library category | Referenced functions / role | Consequence for SDK-free app |
| --- | --- | --- |
| newlib libc | memory/string primitives, `atoi` | Keep a permissively licensed freestanding implementation with complete provenance; supply required primitives. |
| newlib libm | `exp2[f]`, `expf`, `floor`, `fmod`, `log`, `log10f`, `logf`, `lrintf`, `powf`, `sin[f]`, `sqrtf`, `tanf` | Preserve numerics and target performance; verify licences/source for actual target archive members or rebuild a compatible open libm. |
| compiler-rt | software double operations/conversions/comparisons; 64-bit division/modulo and float/integer conversions | Need compatible pi32v2 helpers; hardware float is not a substitute for software double. Audit actual runtime helper provenance. |
| libc++ | float `std::__1::__sort` used by two objects | Avoid pulling an OS through threading configuration; provide open runtime member/source or replace this narrow call after parity verification. |
| `system.a` candidate | `snprintf` in six objects, `vsnprintf` in two | Formatting does not require the whole OS by design. An open bounded formatter can remove this candidate dependency. |
| `common_lib.a` candidate | `sscanf` in one object | Replace or use an open parser/scanf implementation with matching required behavior. |

The seven vendor archives on demo_hello's candidate link line are `cpu.a`,
`event.a`, `system.a`, `cfg_tool.a`, `fs.a`, `common_lib.a`, `update.a`; libc,
libm, compiler-rt, libc++, ABI and emulated TLS archives are also listed
[verified: SDK `apps/demo/demo_hello/board/wl82/Makefile`, Lunar scan loop].
**Neither that list nor a symbol-table match proves all seven would contribute to
Lunar.** An eventual SDK build would need an actual map, retained-symbol report,
archive-member provenance and disassembly after LTO/GC [inferred].

### What the SDK would buy at board bring-up

These are planned capabilities, not current linked contributions [inferred from
SDK source APIs, existing developer plan and fm1-nes's SDK build]: startup and
boot-info handling; clocks, interrupt registration, watchdog and power APIs;
FreeRTOS task/timer/event services; device/flash/filesystem support; USB controller
and CDC/UAC scaffolding; update support. Each must be selected and measured rather
than treating all SDK demos as necessary. The stock external I2S codec path,
physical key matrix and TFT still need FM-1-specific integration.

USB-MIDI is not supplied as a ready class in the public SDK [verified: developer
plan and SDK USB source tree]; Lunar would write it either way. BLE is the strongest
optional reason to retain vendor runtime code: the existing plan depends on the
closed Bluetooth stack, and there is no demonstrated open replacement here
[reported: stock reversing; inferred: development implication]. Felucca never
enables radio. Giving up BLE initially is an explicit product tradeoff.

## What Felucca actually does

At the inspected commit, `tools/build.py:build_app()` links **only** `crt0.o`,
`fm1_vec.o`, `fm1_isr.o`, `felucca.o` using its own `app.ld`; no `.a` archive is on
that link command [verified]. `felucca.c` includes its C implementation files,
including its small `libc.c`, USB, UART, audio, sequencer, panel, storage and main
loop. Its startup and interrupt vectors are owned code. Its HAL covers GPIO,
timers, ADC, UART, SPI LCD, USB, ALNK audio, flash/XIP and fault guards [verified].

Its timer/interrupt implementation nests the scanner and USB audio service above
audio rendering; this is engineering to preserve deadlines, not merely removal
of an OS switch [verified: `firmware/src/main.c`]. Its build audits ROM-address
references and RAM-text calls [verified: `tools/build.py`]. Lunar must establish
its own concurrency contract and performance bounds.

**SDK-free application does not mean SDK-free installation package.** Felucca
builds its own OTA loader but packages SDK `uboot.boot`, `cfg_tool.bin` and
`eq_cfg_hw.bin`; its BUILDING/LICENSING documents identify these as Apache-2.0
[verified: documents and package builder; licence attribution reported by upstream].
This is not evidence that every SDK archive has the same grant or that Lunar
should replace its stock boot components. Lunar's packaging rule remains stock
V1.1.9 SPL hash and byte-identical OTA/cfg/partition configuration; Felucca's
V1.2.1 SPL/package choices are not adopted by this evaluation.

## Licence boundaries and two release variants

SDK source checkout has a top-level Apache-2.0 licence, but blanket attribution
must not override individual headers or provenance [verified: local files;
inferred: legal treatment]. FreeRTOS.h explicitly says GPLv2 modified by the
FreeRTOS exception, and describes allowing proprietary components outside the
kernel; it is **not MIT** [verified: SDK header]. The local header links full
terms rather than supplying their complete text. Exact exception version,
modified-kernel source availability and archive grants require a dedicated audit;
do not assume SPDX's generic exception matches automatically. That exception
cannot be presumed to waive unrelated GPLv3 engines' conditions [inferred].
The SDK's `uac_audio.h`/`uac_audio_v2.h` are GPL-2.0, and remain excluded by project
policy [verified]. Compiler/tool invocation, application runtime archives,
immutable mask ROM, separate SPL and package data are distinct dependencies.

A repository-wide dual licence is unnecessary for **MIT reusable core plus a
GPLv3 combined firmware** [inferred from MIT/GPL terms]. With an open compatible
runtime, GPL modules on can yield a GPLv3 whole application; GPL modules off can
yield a permissive aggregate carrying MIT/BSD/Apache and other applicable notices.
Calling every byte of the latter "MIT" would be inaccurate. SDK-runtime on remains
a separate unresolved distribution-rights question, even with GPL modules off.

Changing our own files to `MIT OR GPL-3.0` would add an explicit choice only where
we control the necessary rights; it cannot turn upstream GPL code or vendor
archives into MIT. Removing third-party GPL restrictions needs permission from
all affected holders or genuinely independent replacements [inferred]. A real
relicensing project therefore includes a file/contribution ownership inventory,
permissions, SPDX/header and notice changes, asset/code separation and contribution
policy. Keep upstream GPL modules in their own directories with original licences.
Do not combine GPL and LXR modules in a shared work under current project policy.

Primary legal sources reviewed by the parent evaluation on this date:
[MIT](https://opensource.org/license/mit),
[GPLv3 sections 1, 5, 6, 7](https://www.gnu.org/licenses/gpl.en.html),
[GNU library compatibility FAQ](https://www.gnu.org/licenses/gpl-faq.en.html#GPLIncompatibleLibs),
[GNU compatibility guidance](https://www.gnu.org/licenses/license-compatibility.en.html).
Legal conclusions here are inferred; exact third-party grants still need evidence.
An absent archive-specific licence is not proof that redistribution is forbidden:
the SDK root Apache grant might cover that object work. Distinguish that grant's
scope from availability of corresponding source. Binary redistribution may be
permitted while a GPLv3 combination still cannot satisfy its source obligations.
Any claimed GPL System Library exclusion needs a specific dependency/target
analysis; this evaluation does not establish one. Current project's conservative
GPL-off rule for SDK-linked shared images therefore remains unchanged.

| Application platform | GPL module switch | Whole application / distribution position |
| --- | --- | --- |
| SDK runtime | off | Not an MIT-only binary; SDK grant scope and modified FreeRTOS/source duties need audit. |
| SDK runtime | on | Current project policy forbids shared firmware; corresponding-source/compatibility route not established. |
| Felucca GPL HAL/runtime | either | GPL application even when engine GPL switch is off; satisfy GPL release obligations. |
| Independently permissive SDK-free HAL/runtime | on | GPLv3 combined application, subject to every component's compatible terms. |
| Independently permissive SDK-free HAL/runtime | off | Permissive aggregate, with retained MIT/BSD/Apache and other applicable notices. |

None of the last two profiles requires a whole-repository licence change
[inferred]. Separate package components and their grants must still be audited.

## Work implied, without implementing it

These are planning ranges in engineering effort for one developer, not a delivery
promise [inferred]. They overlap and hardware surprises may extend them. The
2–5-day item is evaluation/documentation work; most hardware weeks are missing
integration required under either architecture. No measured narrow incremental
estimate for dropping the SDK is available:

1. Dependency/provenance matrix, runtime archive/member audit, release profiles,
   notice/source packaging plan: roughly 2–5 days. Own-core dual-licence paperwork
   would add rights-dependent work; contributor permission has no bounded duration.
2. SDK-free minimal board runtime, startup/linker/IRQ/clocks and diagnostics,
   permissive libc/libm/compiler helpers, target compile/ABI/parity checks:
   roughly 1–3 weeks. Reusing GPL Felucca HAL could shorten a GPL-only path but
   requires a separate permissive HAL for the permissive variant.
3. FM-1 audio/codec, scanner/ADC/TFT, USB-MIDI/CDC and optional UAC, real concurrency
   and sustained latency/resource testing: roughly 3–8 weeks after safe hardware
   access. These are missing hardware integration work for either architecture,
   so this range is not all incremental cost of dropping the SDK.
4. Persistence and power-loss behavior, package generation/audits, reproducible
   GPL/permissive builds, matching complete sources/notices, bench/install/recovery
   validation: roughly 1–3 weeks, plus unresolved recovery and package-rights gates.

Two implementation routes have different release consequences [inferred]:

- Reuse Felucca's GPL-3.0-only startup, HAL, USB and runtime under their actual
  file licences: likely the shorter path to a fuller GPL instrument. Every
  resulting application remains GPL even with `FM1_GPL_MODS=0`. Treat whole
  platform reuse as a deliberate GPL product choice, not a permissive shortcut.
- Build a common independently permissive board/runtime layer, using register
  facts and ideas with credit and suitable Apache/MIT pieces after provenance
  review: more work, but genuinely supports both GPL and permissive module
  profiles. fm1-nes is an SDK app, so its root Apache licence alone does not
  make its linked runtime or every USB dependency usable in this route.

Recommended next decision, **if both firmware variants matter**, is the second
route: an SDK-free **open runtime architecture**, keep
BLE deferred, and reuse one permissive board layer across both module profiles
[inferred]. First prove a small audio/USB/input vertical slice with the staged
bench recovery and package safeguards. The owner no longer requires waiting
for the dev kit or a prior full-image restore; see the bench note above. The current
floating DSP and storage model must be benchmarked; Felucca's integer instrument
is supporting evidence rather than a Lunar performance guarantee.

## Original handoff / backup — 2026-10-07

Documentation-only branch `chore/2026-10-07@sdk-runtime-evaluation`, cut from
`origin/main` at `64209e3`; all changes are this report. No PR or merge requested
for this background evaluation. The report commit is pushed to the existing
`origin` using an explicit branch refspec; compare `git rev-parse HEAD` with
`git ls-remote origin refs/heads/chore/2026-10-07@sdk-runtime-evaluation` to identify
and verify the backed-up report commit. Resume with the parent licensing evaluation;
implementation, ownership permissions, hardware tests and any licence change remain
out of scope. No device or infrastructure state was changed.

## Parent integration — 2026-10-07

This report is also recorded in the hardware recovery branch and linked from
CLAUDE.md, AGENTS.md and DEVELOPERS.md, so future Claude/Codex sessions can
find the reasoning. The original evaluation branch remains backed up. This
is an architecture recommendation; no repository licence was changed and
no SDK-free hardware platform was implemented. Full-code audit is required
before beginning device firmware work (owner, 2026-10-07).


## Integration update — 2026-10-09

PR #131 reconciles this original evaluation branch with main at
`cafd77e0216bfc08ec2db49f75227ce9d5650c5d`. The only conflict was this report,
which main already carried with the revised staged hardware policy. That policy
correction and the original dependency analysis, licence uncertainties, confidence
marks and effort estimates are preserved. The original handoff and parent
integration sections above describe their dated state, not the current PR status.
No runtime code, licence or distribution policy changes are part of this update.

The current tree includes an independently authored MIT, SDK-free inert diagnostic
and a separate handover preparation variant [verified: tracked
[`diagnostic/README.md`](../firmware/diagnostic/README.md) and
[`handover/README.md`](../firmware/handover/README.md)]. The diagnostic's vendor
pi32v2 link and audit are recorded in the
[linked diagnostic note](2026-10-09-linked-diagnostic.md) [reported here: its
recorded LAN results; not rerun for this documentation reconciliation]. This
supersedes the baseline's absence of any linked Lunar artifact; it does not
establish a linked full DSP application, functional board runtime, device
execution, actual DSP archive-member requirements or redistribution rights.

The whole-source audit was completed on 2026-10-08 against baseline
`d7111a985d5d6262767d6af49ba26caf0e1b9453`, as recorded in the current
AGENTS.md and CLAUDE.md [verified: tracked audit record]. Findings and remediation
limits remain in the [audit report](2026-10-07-full-code-audit.md) and
[remediation ledger](2026-10-08-audit-remediation.md). Completing that source audit
is separate from proving the board/runtime and release boundaries above.
