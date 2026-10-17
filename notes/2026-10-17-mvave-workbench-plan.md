# M-VAVE workbench reuse: proposed Sol/Luna implementation plan

2026-10-17. Companion to the [evaluation](2026-10-17-mvave-workbench-evaluation.md).
**Proposed work only.** This evaluation does not authorize implementation,
upstream messages, new hardware traffic or a change of firmware architecture.

## Milestone and fixed constraints

Deliver an offline pilot proving which M-VAVE sources/tools save work while
preserving Lunar's SDK-free GPL application, reusable MIT core, songs and
editor. Its outputs are a pinned inventory, source-only format prototype,
board/audio comparison, reproducible test fixtures, and a go/no-go decision.
Do not promise that this pilot repairs recovery or yields installable firmware.

Use upstream `b178ac43c25f010c60a878056fb5331fe693fd62` and the kit digest in
the [evidence receipt](2026-10-17-mvave-workbench-evidence.json). Revalidate pins
before implementation. Use the active installable stream as the architecture
reference, not stale local main. The coordinator must choose and transmit an
exact reviewed implementation base after reconciling main-only changes.

Preserve engine IDs, parameter semantics, state formats, sequence timing,
sound parity and public editor behavior. Imported vendor GPL files belong in
their own attributed third-party subtree; no vendor binaries enter Git. Keep
file-level licences and the existing module switch; do not create a second
switch that falsely implies removing GPL engines removes the GPL platform.

## Worker routing and ownership

Use **Aeon first**. The current installable handoff says Hera is unavailable
during owner RAID/M.2/NIC maintenance; do not probe or launch there until that
restriction is explicitly lifted. Afterwards, Hera can take bounded inventory,
fixture and review jobs. Mac retains browser review and exclusive device work.
Supported Windows build validation requires a separately confirmed Windows
worker/VM; installing PowerShell on Linux does not establish vendor-tool parity.

Use Sol for architecture, adapters and integration; Luna for bounded inventories,
fixture enumeration and mechanical documentation. Start with three or four
workers, not twelve. The twelve packages below are a dependency queue, not a
request to run all at once. Obey existing host/container limits and current
resource allocations.

Before remote work, read current LAN docs and the coordination README; claim a
unique task atomically under `claims/lunar--<task>`, record host/session/base/
branch/files, and use isolated Git worktrees. Branch format:
`{type}/YYYY-MM-DD@workbench-<task>` using the actual start date. Do not claim
someone else's work or share writable build trees. Each worker's allowed files
must be explicit; coordinator owns shared build/catalogue/editor integration.

Check semantic-tool absolute roots/readiness without changing another session's
shared project. Use source fallback for incomplete indexes. Save a handoff at
each milestone and before exit: outcome, artifact paths, branch/commit/pushed
SHA, checks and limits, blocker and next dependency. Push through the authorized
coordinator where workers lack GitHub credentials, and verify remote SHAs.

## Phase A: evidence and decision, no production dependency

| ID / worker | Owned work and output | Dependencies | Acceptance / stop condition |
| --- | --- | --- | --- |
| W1 Luna, Aeon (Hera later) | Pin vendor source/kit; inventory file licences, hashes, build inputs and native/public split in `notes/workbench/inventory.*` | Exact pins/base | Reproduce 150-file comparison and 65 manifest checks; distinguish licences from binary provenance; no binaries committed |
| W2 Sol, Aeon | Native integration feasibility in `notes/workbench/native-seams.md`: symbols/sections; APP startup/control/audio; timestamped MIDI RX/TX ownership; USB/BLE roles, contexts and lifetimes; exact compiler/build-host feasibility and resource map plan | W1 | Demonstrate a supported engine-free platform seam or explicitly fail this option. `fm1_midi_post` and untimestamped APP SysEx are insufficient. Preserve the 49,152-byte minimum heap and package bounds; no binary surgery or link-conflict suppression |
| W3 Sol, Aeon | Compare public board/audio/LCD/panel code against current native adapter; report only in `notes/workbench/board-delta.md` | W1 and pinned native candidate | Explain 44,118-Hz hardware vs 44,100-Hz simulator clocks, 128-vs-64-frame contracts, float/Q23 conversion, DMA ownership, flash stalls and deadline/overrun metrics; distinguish source facts from timing proof |
| W4 Luna, Aeon (Hera later) | Format inventory and synthetic fixtures under `tests/fixtures/workbench/` plus a loss matrix | W1 | Cover `.fm1/.fm1t/.fm1s/.syx`, sizes/checksums/versioning, shared samples, tuning reservation, invalid/truncated/boundary files; no owner's recorded data |

**Gate A:** coordinator reviews W1–W4. Keep the source-only selective path if
the vendor SDK cannot separate platform from engine or compatible permissions
are absent. Do not let technical link success waive licensing. A vendor-SDK
fork may proceed only as a separately chosen product profile with a reviewed
component inventory; it cannot silently replace all thirteen Lunar engines.

Timebox the initial feasibility work to a few worker-days [planning estimate,
not a delivery promise]. Stop native rebasing early if it requires unpublished
vendor source, incompatible GPL permissions or invasive binary rewriting.

## Phase B: bounded useful implementations

| ID / worker | Owned work and output | Dependencies | Acceptance / stop condition |
| --- | --- | --- | --- |
| W5 Sol, Aeon | Source-only importer/exporter in a new isolated `tools/workbench/` adapter; preserve Lunar state API | W4, Gate A licence review | Synthetic round trips; explicit loss report for unsupported engines, chords/locks, lengths, tuning and sample references; never silently truncate or overwrite a project |
| W6 Luna, Aeon (Hera later) | Converter tests/fixtures, no adapter source edits | W5 interface contract | Malformed input, checksum failure, zero/max sizes, capacity rounding and incompatible versions; deterministic output and clear expected failures |
| W7 Sol, Aeon | One narrowly selected board/audio improvement in coordinator-assigned native files | W3, Gate A, current audio work reconciliation | Compare baseline/candidate at identical rate/block/engine set; if adapting audio, test two 64-frame renders per 128-frame block with event offsets and saturated finite float/Q23 conversion; target disassembly/map and SRAM call graph; no ISR-deadline or audible-success claim |
| W8 Sol, Aeon; Mac Chrome review | UI adapter for explicit import/preview and pending/read-back state; coordinator assigns exact UI modules | W5/W6; existing UI library evaluation | Existing Lunar editor/shortcuts/layout remain intact; preview never implies device save; visible conversion losses; mock transport only until hardware admission |

W5 is the preferred first implementation because it provides value without
depending on a working device or closed runtime. Start with one documented
format/subset, and show unsupported fields explicitly. Whole-bank sample
replacement must remain a distinct operation; `.fm1` is not a sample backup.
Do not port the entire manufacturer sequencer or build a second Lunar state
model merely to support import.

For any vendor-runtime experiment selected at Gate A, W2 must first produce an
exact baseline build/map with the approved compiler and host. The kit supports
hashed Windows executables/plugins; a Linux port needs an explicit substitution
record and successful baseline comparison. Its raw application ceiling is
453,921 bytes before sector rounding, versus the retained Lunar E7's 854,528
bytes in another layout. Its 49,152-byte minimum heap must survive alongside
engine pools, stack and DMA buffers. These are go/no-go constraints, not a
request to remove the vendor guard or promise the full engine set will fit.
The [evaluation](2026-10-17-mvave-workbench-evaluation.md) links the package,
heap and linker evidence. Source-only board reuse instead retains Lunar's
current source-built target pipeline and budgets.

W7 is chosen from the comparison, not predetermined. The source may reveal a
useful clock, DMA, interrupt or mixing correction; adopt only a justified change
after matching the actual register and runtime contracts. A vendor 128-frame
callback is not a drop-in fix for Lunar's measured 64-frame producer shortfall.

## Phase C: packaging, review and integration

| ID / worker | Owned work and output | Dependencies | Acceptance / stop condition |
| --- | --- | --- | --- |
| W9 Luna, Aeon (Hera later) | Attribution, source manifest and developer docs for selected imports; new third-party notice subtree only | Final W5/W7 retained files | Every imported file has exact pin/licence/patch record; public source archive describes actual image inputs; no completeness flag promoted by merely supplying a URL |
| W10 Sol, Aeon | Mock-only library/update adapter and package comparison in isolated tools/tests | W1/W8 and separate protocol-scope decision | Separate `7D FM 02` library and `00 59` update protocols; identity, corrupt/reordered/truncated replies, timeout/disconnect, full-bank replacement and read-back failures; stock-SPL/layout guard unchanged |
| W11 Sol, independent review on Aeon or Mac | Review only; coordinator integrates changes in a dedicated branch | W5–W10 selected scope | Review precise head; resolve main/installable overlap; target link/resource audits, GPL-on/off tests where applicable, relevant browser/state/engine regressions and required CI; merge only green reviewed head |
| W12 Sol coordinator, Mac + owner | Separately admitted hardware acceptance and final report | Recovery restored; W11; exact image/source/backup/recovery plan | Cold boot, panel/display, full-song audio/timing, MIDI, persistence and interruption, browser install/update/rollback, listening acceptance and source closure; no worker device access |

W10 is optional for the first offline pilot. Do not add real hardware update
buttons merely because vendor code is available. Preserve the existing Lunar
private installer/selection work instead of building a competing installer.

For W11, choose tests based on retained changes: codec/property tests for a file
adapter; engine/sequence parity for render changes; actual target ELF/map and
retained symbols for native work; Chrome visual/interaction evidence for UI.
Native synth API 7 differs from browser API 4; BLE and external-audio simulator
stubs, 44,100/44,118-Hz timing and browser memory growth must be recorded in the
parity matrix. No claim of native/web equivalence based on compilation alone.
Compare resource usage against the same candidate/profile, not vendor free space versus an
unrelated all-module Lunar image. E7's recorded 6,116-byte margin leaves little
room for unbudgeted additions.

W12 is deliberately not an offline worker task. This report neither changes
the existing recovery authorization nor supplies a device command. A successful
vendor web update elsewhere is not proof of recovery on the owner's unit.

## Decision record to return after the pilot

The coordinator should present: measured effort saved; features preserved/lost;
exact source/licence inventory; unchanged or justified memory/flash/timing
budgets; host/target/browser tests separately; current physical/recovery state
only from a fresh authorized session; and remaining blockers with owners.

Choose one concrete outcome: keep selective improvements, run a separately
scoped vendor-platform experiment, or reject the migration. A full vendor-base
move needs all three: compatible component permissions, a maintained engine/
platform boundary, and measured target behavior at Lunar's actual workload.
Until then, continue the existing SDK-free GPL core work.
