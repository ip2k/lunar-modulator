# CPU1 offline candidate — 2026-11-01

Personal, non-commercial Lunar work. Base e267d7cd58efef29afb2c0c38562f4878e8106f5;
branch feature/2026-11-01@cpu1-offline-candidate, isolated worktree
/Users/likwid/.codex/worktrees/lunar-cpu1-candidate-20261101.

Authorized endpoint: separately selectable OFFLINE stock-SPL candidate, actual
native adapter/common-core host checks and actual pi32 object/link inventory.
[verified] Current behavior source bc6bfcf733c376217fa43c340040d644b5ca5fbd;
this supersedes the historical1c5/f703 source review with explicit clock ordering.
Hardware admission/execution is absent: ENABLE=1 still errors, hardware_admitted
always zero, no installer/catalogue/package exposure. Default diagnostic startup,
linker and original native/JieLi link auditors remain byte-unchanged from base.
No power/rail/cache reconfiguration, late restart or hold in wake-abort. No device,
ROM, USB/MIDI, flash, reset or power action occurred.

New MPL platform files implement injectable boot-once state, CPU0-only vectors,
guarded pre-RUN cleanup/readback, per-core monotonic shared-origin clock, exact IRQ
save/restore, bounded polling, core-local permanent raw fault records and stack
canaries. Separate linker/entry/profile owns permanent per-core user/supervisor/
emergency stacks. The five-TU deterministic witness drives the actual native
adapter/common core for 24 tags; no SDK, OS, app, DSP, audio or transport closure.
MPL license, attribution/UPSTREAM and pinned upstream NOTICE are retained under
firmware/third_party/felucca-cpu1-candidate. Public grant evidence is private.

Separately reviewable common-core/adapter dependencies: 1b671524 (poisoned polling
escape), c1d2ea29 (READY-before-RUN hook recheck), 1c5a1f41 (post-clock poison before
callback/publication). Last correction has standalone coordinator-safe equivalent
f74633075cf2b595c76d235caa740ef915718a33 from9537ae55, without candidate imports.
All three have independent exact-delta source review; final candidate target
manifest review is recorded separately rather than inferred from those approvals.

[verified] Historical core-correction source1c5: three focused host suites 27 passed33.10s,
1,222 executions: 542 candidate modes x normal/ASan+UBSan, 24 SDK/host core modes
x4, 21 native lifecycle modes x2. Nine new candidate clock-poison modes independently
failed against exact parent core in18 normal/sanitizer runs; standalone existing
protocol fixture adds26 causal failures and12 greenpytest/122 executions8.23s.
No mirrored worker model; actual core/adapter/candidate source executes. Host raw
fault tests set claimed[1]; the native_ms condition reads both words. Host atomic
words/mock MMIO do not prove target compiler/SRAM/fault-entry/cache contracts.

[verified] Actual pi32 clang4.0.1 r3 compiled all5TUs warning-clean and linked,
sourcebc6bfcf7. ELF SHA2562deb969452c6857af5ab9e31dfd578bcbd2ae565b4671f3f4229afcd5db13795.
.text7372B, BSS5568B, explicit stacks/canaries23040B; RAM28608B, ending01c0efc0.
Default disabled object compiles and ENABLE=1 rejects. Original link auditors are
unchanged and were not repurposed as candidate admission. Actual entry/RTI/ICFG/
fault and corrected poison reload instructions inspected. Compiler rejects
-fstack-usage; explicit stack-decrement/call-site TSVs are inventory, not whole-path
stack bounds or high-water proof. No executable target code was run.

Source-bound actual five-TU/compiler-M header/toolchain/object/ELF manifest:
scratch/cpu1-candidate-20261101/evidence-ordered/source-artifact-receipt.json.
Private ELF/map/listings, stack TSVs and review, disabled/ENABLE evidence are beside
it. Full commands/logs and public MPL grant/NOTICE records with hashes are retained
under this owned scratch lane. Actual clang/ld/objdump and used header bytes are
hashed; no protected archive extraction or new archive-to-tree admission occurred.
Readonly mounts plus before/after exact SHA do not constitute cryptographic TOCTOU
attestation against an untrusted host. Toolchain image ID and quotas are in receipt.

Private accepted plan, independent reviews and author handoff are under sibling
worktree devkit-performance-20261022/scratch/devkit-20261023/audit-20261101/.
See native-cpu1-backend-plan.md, cpu1-astra-review/, and
native-cpu1-offline-candidate-implementation.md. No shared Serena re-root: current
selection belongs to WASM lane, generic config does not prove absolute root.
Rarefaction fixed-root refuses this external worktree; exact Git/source inspection
was used, no clangd/device ABI claim. No agents spawned.

Remaining gates: independent final manifest/disassembly review, coordinator review/
CI/integration. Any future execution needs a separately authorized watched witness
for exact stock-SPL entry/inherited RTI/cache/rails, actual local exception/stack
setup, nonce/READY/RUN plus restoration chronology, raw/first/nested faults,
bounded terminal hold, adversarial bidirectional SRAM coherency/PCM, raw-clock
origin/wrap/35-minute lifetime and actual DSP deadlines. No rail/cache adjustment
or restart is assumed safe. See CPU1_CANDIDATE.md for the exact envelope.

Lifecycle: local scratch lane retains small logs/private ELF/listings only after
reproducible tests/builds are removed. Aeon owned place
/home/likwid/datasets/lunar/cpu1-candidate-20261101 used CPU8–11/max4CPU/6GiB,
labelled --rm containers; target compilation was subsecond, no daemon changes.
Owned claim handoffs/cleanup are recorded in the private final author report.
Mac free space was1115GiB, above500GiB floor. Unmerged pushed source worktrees
remain for coordinator integration; no owner or sibling data is removed.

Superseding timestamp portability correction:5a8e16c4 is the separately approved
a1eda test-only lifecycle dependency, already present on coordinator root. Then
bc6bfcf7 sequences two clock samples into p_start/p_end full expressions in the
actual profile and owned candidate fixture. No other paired clock arguments found
in bounded candidate search. Exact final candidate12pytest pass17.78s; combined
precheck27pass33.15s. Actual five-TU profile recompiled and linked; fresh receipt
binds bc6 source. profile-order-check.json traces actual first/second pi32 clock
returns into publish r1/r2. Historical compiler happened to choose this order;
portable C sequencing no longer depends on that choice. New .text instructions
match1c5; full ELF differs due build-path symbol metadata. See separate ordered-
timestamps note. No artificial host MMIO startup model or regex source test used.
Final offline review/port handoff is in private author report; hardware stays false.
