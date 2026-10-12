# SDK diagnostic recovery phase implementation and Hera evidence

2026-10-12, personal/non-commercial. Implementation of the accepted design in
`notes/2026-10-11-sdk-recovery-phase-design.md`. No device operation, production
physical adapter, vendor source/library change, package creation or PR. Root owns
checkpoint/push, independent review acceptance and all hardware. Source branch
`feature/2026-10-11@installable-firmware`; native snapshot base `580b098`.
Root checkpoint `41fc898d2d887c615406869ea969a239702d65f7` contains the frozen
trace source/tests and this note [verified: explicit branch push and matching
remote SHA]. Independent review was subsequently accepted within offline scope.

Insight before code: old stage6 could indicate waiting for the SDK lock or a
nonreturning final reset transfer. The new trace publishes evidence before each
boundary and leaves the existing recovery IO sequence intact.

## Saved implementation

[verified: source] `firmware/sdk-diagnostic/recovery_trace.c/.h` owns an aligned
64-byte ordinary BSS object. `LUNAR_SDK_RECOVERY_TRACE` is enabled only by the SDK
diagnostic builder's explicit `--recovery-trace`. The reusable IO ABI is unchanged;
conditional request hooks require strong definitions. Missing trace object is a
host link failure. The ordinary macro-off path has no trace references. No weak
hook, new lock primitive, SDK callback while locked, P33 access, clock/rail write,
mailbox allocation or manual RAM address was introduced.

[verified: source/model] Phase values are 1 initialized, 2 before lock, 3 lock
acquired, 4 all 16 marker bytes verified, 5 final START intent, 6 request returned
success, 7 request returned failure. Success describes a returned request only;
phase5 describes intent before the write, not reset completion. Initial magic is
`0x4c525431`, schema1 and length64. The 128-bit nonce is stored at byte8,
phase/complement at24/28 and publication sequence at60. Odd publication marks an
update; an even sequence follows payload/phase/complement and a CSYNC. Another
CSYNC follows that committed sequence. Payload clocks/panel/elapsed/heartbeat are
snapshotted before `p33_lock`; locked updates only store owned phase/complement,
mailbox flag and sequence. Startup reason is `0xffffffff`: no safe existing
SDK cached-reason declaration was established, and no new P33 read was added.

[verified: source/native] `app_main` initializes the record before worker creation.
The worker publishes before-lock after old stage6, acquired after lock returns,
and returned phases after unlock. The final hook executes after the final send's
CON read and before its unchanged CON|START write. The fixed three bytes remain
0x20, 0xa0, 0x10; marker, poll budget and one-shot recovery state remain unchanged.

[verified: build] Builder generates a fresh `secrets.token_hex(16)` nonce by
default, embeds the four little-endian words and records the normalized nonce in
the manifest. `--recovery-trace-nonce` enables an explicit reproducible 32-hex
input only with `--recovery-trace`. Invalid length/content and nonce-without-switch
fail before creating output. Reusing one nonce distinguishes an image/campaign,
not individual repeated boots.

## Native artifact freeze

[verified] Local private evidence is `build/sdk-recovery-trace-hera/`; Hera copy is
`/home/claude/mvave-fm1/sdk-recovery-trace-20261012/`. Files in `native-enabled/`:

| Artifact | SHA256 |
| --- | --- |
| app, 120688 bytes | 76382f531491b63a9cb75258ae9299185219b55f201e5110a74eb03ab328bf44 |
| ELF | e9d54172bda7dd085fbd1a46ef35c353210f75ec5f621a3e352a075d7f2a6035 |
| build-manifest.json | b58c49fed04efb4fc29eaf2602605a8e4ec197048bcd418c86a53276198cf86e |
| key-link-audit.json | 2b107e81e4dc35e9dd8eda1324a26743b44728f865ae5abe20d9f0baf1167a1c |
| sdk-image-audit.json | 946961b92a3a1db9b5de52201464b8afd6ebe85f30b100c3e74bfa6e9ae8471b |
| disassembly.asm | 5f1c00b76d6e7c8c85384b303c3ed42646304c6c6e8954488a1b3e5af2cdf5b3 |
| symbols.txt | 5de79da684bf83a608f7d8cf0044d355a0f08a3a02c30d08131db4e4cc9ad7e6 |
| lunar-sdk-diagnostic.map | 38af63aa300532479d13d0c4c214a38aa8a005c3a2b670048512edb9932f867c |

Nonce `6b5482dbb66b5f45ed73e2f26c4a4657`. Exact source archive `source-v1.tar.gz`
SHA256 `0fe76b77751023382fc550fe71ba6b8212356bc7f47e5164e0799278f922ca07`;
`snapshot-v1.json` pins its full inventory. Manifest records SDK commit
`e30b1ee375d1f2993fc23bf92c8b99006a6e5f9d`, stage manifest SHA256
`3c58c0bb8ab885f0bf620b2a9e871ee97f771b5563c3dfabb3ecf0436410beb2`,
all archive/toolchain hashes, profile, source hashes and audit tools. SDK source
was `/home/claude/mvave-fm1/sdk-v1213/source-sdk`; toolchain was
`/home/claude/mvave-fm1/sdk-v1213/toolchain/jieli-linux-toolchains-20250324.1`.

[verified: vendor nm/listing] Record `lunar_sdk_recovery_trace_record` at
`0x01c02880`, size0x40, exclusive end `0x01c028c0`, alignment16. Existing
`lunar_sdk_stage` is `0x01c03418`, size4. BSS begins `0x01c02870`; the record is
ordinary linked storage. These addresses must be derived again from the sealed
ELF by any new reader; they are not permission to extend an old RAM adapter.
Native LTO internalizes trace functions as local `t` symbols; no weak definition.
Source/link-failure gate establishes required hooks.

Native instruction landmarks [verified: vendor objdump; independent review accepted]:
worker snapshot call `0x02002c14`, lock `0x02002c18`, acquired `0x02002c20`;
all-marker-match hook `0x02002cce`; final send CON read `0x02002a32`, intent hook
`0x02002a38`, original OR `0x02002a3a`, CON write callback `0x02002a44`.
Publication start stores odd sequence then CSYNC at `0x0200295a/5c`; finish stores
phase/complement then CSYNC at `0x020016f8/fa/fc`, commits even at `0x02001700`,
then CSYNC at `0x02001702`. The `r1=~r1 #` packet paired with phase store requires
vendor parallel-packet interpretation; host models cannot independently establish
that architecture's execution semantics. Independent source/native/allocation
review owns final interpretation and nonoverlap with all inherited reserved,
stack/boot handover, SDK variable and loader/ROM windows. Ordinary BSS does not
establish retention after reset/ROM upload.

[verified: reproduction] `native-repeat/` rebuilt with explicit
`--recovery-trace --recovery-trace-nonce 6b5482dbb66b5f45ed73e2f26c4a4657` and the
same container mount paths: app and ELF byte hashes both match the first build.
`native-disabled/` rebuilt without either trace argument: 120432-byte app SHA256
`991b569df7d131320e42ef34c1b619de586d2a7ba6236c0ea1c089731eb61fa9`, exactly matching
the prior diagnostic application. Disabled ELF SHA256
`f6cbeab59c60a275c225b67481d78cf37fdf945ef28916c2571db53a57b177c0`; debug source
paths differ from historical builds. Both enabled/disabled current link/key and
SDK image guards pass with `flashable:false`; this is not package admission.
No stock-partition package guard was run for a new package by this subtask.

[verified: preserved failure] First native attempt selected an incomplete
`/home/claude/mvave-fm1/sdk-stage-e30b1ee-installable` with 2 files rather than the
9775-file pinned SDK stage; stage verification rejected it before building. The
failed `native-run.log/native-inspect.json/native-removal.json` remain separate
from passing `native-run-v2.log/native-inspect-v2.json/native-removal-v2.json`.
No stage verifier or SDK source was weakened.

## Test and runtime receipts

[verified] Hera pinned container image
`sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`.
Native containers used4 CPU/4GiB; initial tests used16 chunks, each2 CPU/2GiB.
Inspections confirm networknone, no privilege/devices, correct image, source RO
(native SDK/toolchain RO too), exit0 and no OOM. All collection/chunk/native
inspections are saved; fresh label lookups confirm no remaining trial containers.

`aggregate-v1.json` records65 passing cases, no failures/errors/skips, exactly
once across16 chunks. `plan-v1.json` SHA256
`c47735eff3164a7ee56a0675d85d7f78bad8eb9e0bcca47c41cc107ae26782ad`; aggregate SHA256
`812ce2673ec2c541407f2b1b6f2bac473c2d57ac93f0f95c0a50e911c9097898`.
Modules: new trace models, existing recovery-request tests and SDK diagnostic
build tests using the exact native ELF (no optional skip). Cases prove unchanged
enabled/off register/mailbox traces and one attempt, all16 marker mismatches,
selection/RTC/stuckBUSY failures, each3-byte timeout/held-START boundary, committed
final intent after CON read before START, frozen payload, layout/alignment and
required strong hook link failure. A native host C longjmp model simulates a
nonreturning final START and requires final-intent/even publication without any
post-return code. This is host C, not pi32v2 hardware emulation.

Five newly added nonce-rejection cases passed in `nonce-evidence-v2/`, one
bounded2CPU/2GiB Hera container. Already-passing65 cases were not rerun at root's
request. Test-only source archive `source-v2.tar.gz` SHA256
`69d959d7374099bb37864dc41a2d39cae22e28431069b5627d8f300d3936f230`;
all native firmware/build sources match V1 exactly. `evidence-index.json` seals
all local artifacts/receipts and independently checks XML node completeness,
image/resources/read-only mounts, repeated builds and fresh cleanup. Nonce test
output has5 tests/no failure/error/skip, inspected successful runtime and removal.

Semantic coverage limit [verified]: Rarefaction status and Serena initial/current
configuration were checked. Both shared servers still select primary
`/Users/likwid/Developer/mvave-fm1-firmware`, not this unmerged worktree; neither
was retargeted/restarted. File inspection and vendor objdump were used instead;
no isolated semantic coverage or substitute clangd ABI proof is claimed.

## Remaining acceptance and handoff

Independent source/native/allocation review is accepted with no actionable
defect found. Private report `build/sdk-recovery-trace-hera/independent-review.md`
SHA256 `cf706b9c95ea0635a9d4521b04d3d42730b80b0dfd97070931892ae163c5d690`
and checker result `e4cbdbba2121b99da170550b92e783cadf91ff889901b11dbac02755ed6185ad`
replay the 280 indexed pins, both source archives, all 70 passing cases, native
allocations/listing and 21 passing runtime inspections. Native parallel-packet
operand timing remains inferred; a strict decoder must reject inconsistent
phase/complement/sequence evidence. Review grants no hardware operation.

New exact-image install/package admission must pin these actual files, not reuse
old pass receipts. Next reader dependency is a distinct sealed ELF-derived64-byte
trace plus4-byte stage policy, four bounded FD07 reads (both ranges twice) and a decoder covering stale
nonce, magic/version/length, unknown phase, complement/sequence, flag agreement,
truncation and inconsistent repeated reads. Old adapters/windows stay frozen.
RAM retention must be measured under the reviewed ROM/loader path. Root alone
owns future one-shot trial and separately reviewed stock restore/reset/identity.
Physical display acceptance and warm recovery from rejected partial/corrupt
applications without USB_KEY remain distinct open gates; no fault injection.

Insight after code: enabled host recovery sequences are identical and the
native macro-off image is identical to the previous application, while the
new build has observable pre-lock and pre-START boundaries. A coherent trace
may establish reaching a phase; it does not establish reset causality,
physical frequency, electrical START completion or ROM mailbox consumption.

## Final owned source pins

| Path | SHA256 |
| --- | --- |
| `firmware/sdk-diagnostic/recovery_trace.c` | f538f3d16de0f1132648c7ee565760dcf8e4a42275f48895205a26ca15c8b7fb |
| `firmware/sdk-diagnostic/recovery_trace.h` | fa969a75033663150f2782d57e2f51f8b96f5b78b41e79e561b4d8bd40ca809d |
| `firmware/sdk-diagnostic/app_main.c` | 6a6d9682edc435811cef27573d3ddbc7ee5da3f1acc533b91401aa8b78c6f62c |
| `firmware/recovery/request.c` | f032ea0f93e2f25b3bf98f3cdcad8b2cc23087a8825ca102fa7fb311194e7c21 |
| `tools/jieli/build-sdk-diagnostic.py` | 2885d948adf438000fafdfa72163fd321f70421a6c0550dfcd3dc9551303d425 |
| `tests/test_sdk_recovery_trace.py` | 9291054e378f536343865af3a179d13e202a33c19059e70bd455fab36147dc6e |

Evidence index SHA256 `0cf58f715186a5b96cb882acd17085953ca8abea0adfe31232ae54dcfac552e6`. Root should update the checkpoint receipt when committing this source/note.
