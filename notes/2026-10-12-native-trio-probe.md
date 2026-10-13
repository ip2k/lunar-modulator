# Native Trio integration probe

This is a build-only milestone toward the owner's native, web-installable
Lunar Modulator goal. It is not an installable image or full application.

## Results [verified]

- The owner observed white, red, green and blue bands after the V8 diagnostic
  boot. This is physical display acceptance of that earlier image; this native
  Trio probe has not been installed or tested on the FM1.
- Hera linked the native Trio probe without JieLi SDK archives and with no
  named undefined symbols. ELF SHA256:
  `845bb1237a42de8400bdbe4d1e580597ac2415ea0276f620947f978f333e4b17`.
- ELF regions fit the imported linker script: text 46,372 bytes, RAM text
  1,128, data 8, BSS 16,132, pool 161,792, and noinit 76. The RAM text
  disassembly contains no call instruction.
- Sixteen parallel Hera containers passed the adapter oracle: 128 note and
  velocity cases, 12,288 blocks of 1–64 frames, note release, unsupported-rate
  rejection, output equivalence, and caller-buffer canaries. All exit statuses
  were zero, with no container OOM. These are host CPU tests, not pi32v2
  arithmetic accuracy or real-time audio acceptance.

Private receipts are under `build/native-engines-16-20261012/guarded-probe/`
and `build/native-engines-16-20261012/adapter-oracle-verification.json`.
The remote campaign is `/home/claude/mvave-fm1/native-engines-16-20261012`
on Hera. Its `host-build.sh` and `host-launch.py` record the exact host jobs.

## Implementation and boundaries

The pinned GPL-3.0-only Dinghy platform is imported with its licences,
provenance and per-file hashes. The application uses the existing Lunar Trio
engine descriptor through a narrow C adapter, with fixed instance storage and
64-frame rendering. Audio mutations happen in the ISR; the main loop queues
key and USB MIDI events. The display reports peak and callback timing.

`tools/native/build_probe.py` verifies source pins and generates a guarded
platform copy. Exactly two checked adaptations skip boot OTA cleanup and
make the flash-write allowlist empty. Upstream files remain unmodified.
There is no firmware packaging or flash admission in this builder.

Follow-up build [verified]: no SDK source header directory was mounted. Using
the toolchain's C headers and a bounded C++11 placement-construction declaration
produced the same ELF hash above. The wrapper's unused `<cstring>` include was
removed. Full libc++ was evaluated against its official LLVM 4.0 source; it
would import exception and allocation declarations and transitive headers for
a single caller-owned construction operation. The small native-only header
implements that operation, without an allocator or a C++ library runtime.
Primary comparison: [LLVM libc++ new](https://github.com/llvm/llvm-project/blob/llvmorg-4.0.0/libcxx/include/new).

The subsequent guarded probe adds bounded event consumption and releases all
notes after queue overflow. Rendering rejects uninitialized, null, zero-length
and oversized requests. All 16 host shards passed again, with added unsupported
initialization, block-size boundary and all-notes-off checks. Target ELF SHA256
is `bfc32413e1bd9f0aff1c56c4285628fc7033e02d3f913a58e589c301546b3084`.
It links with no SDK archives or SDK source headers and no named undefined
symbols. These assertions do not establish real-time performance or full
toolchain source/licence reproducibility.

The existing `audit_link.py --runtime sdk-free` passed on this ELF: zero
failures and zero pending checks for its key/eFuse/mailbox/initcall scans.
The builder now requires that audit automatically. It does not substitute for
the stock SPL handover or complete recovery admission review.

Stock flash layout and entry/recovery review, queue overflow hardware timing,
and physical audio checks remain required.
The application is a single-engine diagnostic, without the complete Lunar
interface, sequencer, effects or web installer acceptance.

## Semantic tooling limits [verified]

Rarefaction and Serena selected the primary checkout, not this worktree; their
shared selection was left unchanged. Serena found the common Trio descriptor.
Rarefaction found its declaration but returned zero callers despite the known
registry reference and inferred an incorrect fallback type. The absence of
target compile commands limits this index. Native branch-only code was checked
through source and actual Hera target builds; neither index proves pi32v2 ABI.

## Hardware continuation

The accepted V8 diagnostic is still the last installed image; stock restoration
has not been claimed. The earlier stock restore admission is stale and must
not be replayed. Obtain a fresh reviewed loader admission and two matching
backups before another flash operation. Preserve stock SPL, OTA/cfg and the
recovery route; no blanket erase or eFuse commands are authorized.

## Private flat application gate [verified]

`tools/native/probe_artifact.py` independently validates the linked pi32v2
ELF entry, named stack/guard reservations, allocated section permissions and
bounds, startup copy/zero symbols, ELF physical load addresses, contiguous
flash payload, and absence of unaccounted file-backed load segments. Unexpected
allocated sections, including constructor tables, fail closed. It recomputes
the SDK-free key/eFuse audit against both ELF and exported application bytes.
The native builder now requires this gate and writes the private artifact.

The current target ELF `bfc32413e1bd9f0aff1c56c4285628fc7033e02d3f913a58e589c301546b3084`
exports 47,580 bytes, SHA256
`c9119985006ea031f457c95c78ba5134779ae8dabfc0484715e476d7a7775e6e`.
Local export and the Hera builder export agree. The artifact remains explicitly
non-installable, hardware-unadmitted and hardware-untested; this is not a
startup execution proof, full flash candidate or public firmware package.

The synthetic verifier tests and existing diagnostic layout suite passed
36 checks locally. Sixteen concurrent Hera containers each ran the valid case
and one distinct malformed-layout case: all exited zero without OOM. Receipts
are private under `build/native-engines-16-20261012/`; remote campaign is
`/home/claude/mvave-fm1/native-engines-16-20261012`. Two initial container
attempts failed before testing because the image lacked the requested Python
command/pytest; the final suite uses standard-library unittest and needs no
additional dependency. All task containers were removed after inspection.

Next: distinct native raw-target geometry/admission profile, startup/recovery
review and fresh matching device backups before any physical write. The stale
V8 stock-restore admission remains prohibited. No USB or flash command was
sent during this artifact work.

## Native NOR construction profile [verified]

`tools/native/raw_probe.py` adds the separate `native-trio-private` offline
profile. It reconstructs the application from ELF, rejects a mismatched flat
image, independently recomputes the SDK-free binary audit and then uses the
existing strict raw geometry validator. Only application payload, its length
and directory/payload CRCs may change; the stock SPL and bytes from cfg-tool
onward remain protected. Both original-loader and fixed-loader backup
provenance retain their existing distinct validators. There is no USB path,
physical writer readiness or hardware admission in this constructor.

The native construction and artifact suites plus previous diagnostic layout
suite passed 41 tests locally using synthetic NOR/reference/ELF bytes. No new
actual-device full-flash candidate has been emitted from this profile yet.

## Guarded entry and bounded native probe [verified]

The generated crt0 now masks interrupts, rejects a nonzero core number and
rejects a boot pointer other than `0x01C7FE08` before its first RAM write or
stack assignment. The artifact verifier requires the exact compiled guard
prefix, reject symbol address and stack-free reject loop; mutation tests
reject every changed guard byte. Captured ICFG is now after CLI. This does
not establish ownership of the secondary core or recover a rejected entry.

The normal native probe returns to UBOOT after 20 seconds using TIMER4,
independently of TIMER5's millisecond ISR. The generated recovery source
returns after 20 seconds as well. Both use the inherited detach/bootguard/ROM
mechanics. Neither timeout is physically verified or protects a failure before
its loop is reached. Imported Dinghy sources remain byte-identical to their pins.

The actual Hera bounded build passes link, memory-layout, compiled guard and
SDK-free ELF/flat audits with zero pending checks. ELF SHA256
`0b34c276473f1d6c97ca8ce92ee268fe8b52a01656672f31b53f71bc4e01a927`;
47,708-byte app SHA256
`ed2b4e16ace51a7b4e43cb961a467a7e162fd45fd8c8b7d40bd36793024556eb`.
This supersedes the unguarded 47,580-byte artifact above. Sixteen guarded
artifact fault shards on Hera exited zero without OOM; source/receipts remain
private in the native-engines campaign.

A real private 1 MiB offline NOR candidate was constructed from the retained
matching original stock backups through the fixed-loader provenance profile.
Candidate SHA256
`112667509886ddce7536c87e44a4674e5e411ef907f2c8b3d169964637ca0c42`.
Local export agrees with the Hera app hash. Protected stock geometry passes.
Artifact path: `build/native-engines-16-20261012/native-target-historical-offline/`.
These historical backups grant no fresh device-write admission. The candidate
is not an OTA/web package, has never run on hardware and must not be published.

Passive bench enumeration still shows bus 1 device 14, `4c4a:8057`. No device
command, loader upload or flash write was issued during this guarded-build work.
Next: distinct current returned-ROM backup admission, two fresh matching dumps,
native install/recovery review, then physical startup and Trio/audio/controls/MIDI
acceptance. Full Lunar application and web installation remain outstanding.

Focused native/layout/diagnostic regression verification: 95 passed, 9 optional
private-artifact checks skipped. No skip is counted as physical acceptance.


## Fresh returned-ROM backup after the accepted display boot [verified]

The owner reported white, red, green and blue bands. The previous repeat reset
transport remains ambiguous; that report is separate physical display evidence.
A distinct `tools/fm1_repeat_rom_backup.py` adapter preserves that transcript,
replays the original completed backup, binds a fresh passive USB/SG snapshot,
and admits the same fixed RAM-loader dual-read inventory. It cannot issue reset,
NOR erase/program or eFuse commands. Its single-use marker is tied to the
original repeat campaign rather than the new JSON formatting or receipt name.
Original source files and their pinned historical receipts remain unchanged.

On bench01, bus 1 device 14 / port 1-1 / `/dev/sg0`, the actual session completed
8,757 operations in 29.007 seconds with 17,516 receipt events. Both fresh 1 MiB
flash reads match the installed V8 diagnostic SHA256
`5dbada6531e0ad68b1902b4f0d97cc6f78d7fa338b1360c194f98c1475ad7a3d`.
No retry, reset, erase or program was issued. The device is now in the fixed
RAM loader; no native app has run and stock has not been restored.

Adapter SHA256 `9651fc1b08e30c8cf47d37b86a3f2a2557c47134ed46252e5f484381a3acf328`.
New campaign SHA256 `3eccfb5f5a5cd97c2c648ad95d219d630d287f4651f9e6aa05e1de6230e4998b`.
Manifest SHA256 `e97ce2151453d7cff14f6b05fca97ca848bbcfc36387bd536ad85cad5bba8460`.
Command receipt SHA256 `b4b324cfbf65773f29fd46ae25a4115240f236647033acb634444cc889c4c51a`.
Private local evidence: `build/repeat-return-backup-16-20261012/`.
Private Pi receipt: `/home/claude/fm1-sdk-trace-entry-20261012-v8/stock-backup-001/returned-target-backup-001/repeat-boot-001/fresh-backup-001/`.
Pi source stage: `/home/claude/fm1-repeat-return-backup-20261012-source/`.

Twenty focused adapter tests pass; 16 fault chunks on Hera exited zero without
OOM, and the adapter/native artifact focused regression suite passed 43 checks.
These tests verify admission/refusal behaviour, not native hardware acceptance.
The read worker retains its pinned `trace_admitted_backup_completed` event name;
the new first event and manifest explicitly identify the repeat-return route.

Next: bind this fresh completed backup to a distinct native install policy,
review the concrete protected-range transaction and stock rescue plan, then
install and observe the bounded native Trio probe. The old V8 stock restore
admission is stale and must never be executed. Full Lunar UI, sequencer/effects,
engine selection and web-installable packaging remain outstanding.

## Concrete native transaction and 16-way recovery campaign [verified]

The latest owner reply again confirms white/red/green/blue bands on the SDK
diagnostic. No native display or audio observation is inferred from it. Passive
bench enumeration remains bus 1 device 14, 4c4a:8057; no device command, reset,
loader upload or flash mutation was issued during this transaction work.

`tools/native/bench_transactions.py` prepares offline plans from the exact pinned
fresh V8 receipt/dumps, original matching stock dumps and audited native NOR
candidate. Each plan covers 30 changed sectors, derived from current V8 bytes;
protected boot/config/reserved bytes match. Application directory sector 0x4000
is last. Native plan SHA256
`fe07ac6b54006c977249595b2f4df2d68bdce93223675c77556b9f6e6412ef98`;
stock plan SHA256
`0eae15a6a7dd7bcb446f0617a6d7b55bf45b85d33fbafc67910c02be7a5c3baf`.
Private physical-labelled offline plans: `build/native-bench-plans-20261012/`.
Neither plan grants hardware admission; no opener exists in this tool.

`tests/native_bench_recovery.py` ran in 16 simultaneous Hera containers with
the actual private image bytes and simulated NOR. All final chunks exited zero
without OOM. Interruptions span mutation indices 1 through 510, alternating
torn erase/program and completed mutation with lost acknowledgement. Every
case refuses a premature stock transaction, reconnects a fresh simulated
session, restores and verifies full V8, then restores the original stock hash.
It also refuses protected-byte corruption after a completed journal. Shard 0
additionally completes native install and V8 rollback. Directory-last ordering
is checked for each mutation sequence. This models transport interruption,
not physical power-loss durability, ROM entry, real boot or real NOR behaviour.

Local focused suite: 64 tests and 7 subtests passed. Private campaign and final
source pins: `build/native-bench-recovery-16-20261012/`. Hera source/receipts:
`/home/claude/mvave-fm1/native-bench-recovery-16-20261012/`. All containers have
exited and were removed. Serena/Rarefaction remain selected on the primary
checkout; queries for this branch-only transaction module fail ENOENT, so
file inspection was used without changing another session's global selection.

Next dependency: distinct reviewed live native policy/opener, bound to the
current fixed-loader session and fresh backup provenance; then bounded native
install/boot with recovery. Never run the stale V8 restore admission. Full
Lunar UI, engines/effects/sequencer integration, audio/controls/MIDI physical
acceptance and stock-compatible web installation are still required.

## Native injected policy and disconnected hardware [verified]

`tools/native/bench_policy.py` binds only the exact recorded native/stock plans
to an injected fixed-loader transport. It pins the planner and transaction
sources, both matching backup dumps, their manifest and command receipt, the
exact target image, directory-last sector order and all provenance fields.
The inherited wire guard requires durable journal intent before a mutation.
This module has no physical device opener and grants no hardware admission.

`tests/native_bench_policy.py` passed all 16 parallel Hera chunks: invalid
loader/provenance bindings, copied policies, changed sessions, absent journal
intent, incorrect pages, protected erases, changed image artifacts and forbidden
eFuse/upload/reset commands. Shard 0 additionally completed a simulated native
install and full V8 rollback. Each receipt explicitly reports simulation and
zero hardware operations. The first run passed 15 chunks; its session-label
fixture used a valid nonempty label. The final run corrects that fixture to an
empty label and retains the separate changed-after-bind refusal case.
Private final evidence: `build/native-policy-16-20261012/hera-verification.json`;
Hera source and outputs: `/home/claude/mvave-fm1/native-policy-16-20261012/`.

Passive USB checks now show only root hubs and no SG device. The kernel records
`Oct 12 21:39:38 bench01 kernel: usb 1-1: USB disconnect, device number 14`.
This supersedes the earlier current-session description: device 14 admission
is stale. No reset, upload or flash mutation was attempted in this policy work.
The owner's power/connection state is awaiting clarification; fresh connection
evidence is required before any further hardware operation. Neither native
hardware acceptance nor full installable Lunar has been achieved.
