# Offline native PROJECT replay and conditional component budget

The bounded offline source milestone is complete: current PROJECT collection,
canonical replay, two-pass binary staging, mandatory identity and semantic
readback, and a fake transaction are implemented. Production storage, SAVE/UI,
concurrent runtime and hardware admission remain disabled. This is a component
result, not a full application RAM fit or an installable image.

## Source and behavior

[verified] The implementation begins at frozen corrected PROJECT oracle
`e267d7cd58efef29afb2c0c38562f4878e8106f5`. Phase1 codec
`3a1c9a31a79fd4582ed0e7e154e1d4426def7396` and phase2
`2cb13c5838583517ad0f169ca8240ec3722e1276` received independent source/host
review. The target validation composition is
`6896b9ab8b8eaae10b5db706adf15a549ef7a6b3`: phase2 plus reviewed same-pin musl
and compiler-rt restorations, originally `2654742b` and `effa797c`. Documentation
clarifications after that composition do not alter executable source.

The existing record collector, canonical JSON emitter, 256-byte push parser,
binary record encoder and semantic reader are reused. Native PROJECT modes2/3
retain current SIM metadata/version0.1.0, normalization/default padding, BROW,
full caps, reports, first failure and near-field behavior. Host modes0/1/2/3 and
all existing APIs remain. MIT streaming helper provenance is historical
`cccd21cc5dc82859ed8a5d84f0a7a40646d07353`; no GPL store implementation was copied.

`collect_project` is shared by old host collection and native preparation.
The host all-kind dispatch retains CLIP handling separately, so native PROJECT
closure cannot retain its heap-backed CLIP extractor. Full active MIDI-effect
descriptors and their parameter arrays are included in known live alias guards.
Opaque getter/self/string/backend backing still requires caller-owned disjoint
storage. A single synchronous busy lease is not a concurrency lock.

`fm1_app_state_project_stage(app, binary, ops, ctx, workspace, report)` performs
complete preflight before `begin`, freezes its canonical source/manifest,
replays into an uncommitted seekable sink, verifies manifest/bytes and runs the
same semantic binary parser with CRC, then rechecks source before `commit`.
All source/getter/sequence/registry/backend state must remain exclusively owned
and stable throughout. Failure before commit aborts the candidate; an uncertain
physical commit returns INDETERMINATE and requires rescan, never automatic retry.
Readback is structural format validation, not full app-load/rate/constructor
admission. Source fingerprints are neither authentication nor synchronization.

## Host proof

[verified] Fresh exact old/current translation-unit comparisons pass in normal
and ASan/UBSan builds:244 PROJECT saves across all four modes plus80 host-only
kind saves. Actual staged modes2/3 match old bytes and full reports. Corpus
includes32 FM6 slots, randomized per-focus drum values, non-sorted/duplicate
parameter descriptors, rich modulation/data/BROW, empty sounds, missing set,
UTF-8/nonfinite failures, near reports and real64,920/66,456-byte set boundaries.
The latter oversized set refuses before output. Reader relocation passes1,633
old/workspace comparisons per build; codec passes387 cases plus ownership and
reentry boundaries. No caps were reduced to make the component fit.

[verified] The fake transaction runs183 operations/549 partial-effect fault
cases per build: source mutation, reentry, aliases, corruption, positive short
reads, old/new semantic rescans, wrap/equal/half-range ambiguity and uncertain
publication. Its two102,400-byte slots are test-only external storage geometry,
not target RAM or a flash partition proposal. Independent review additionally
snapshots full app/editor and checks held-voice64-frame PCM across122 stage
success/refusal calls per build, starting with nonzero output. A causal MFX
alias test reaches begin on old3dd but refuses before begin on corrected2cb.

## Target closure and ownership boundary

[verified, compile/link only] Actual pinned pi32v2/r3 toolchain, `-Oz`,
`-mfprev1`, freestanding/no-builtin, function/data sections, C99/C++11,
no exceptions/RTTI; external app arenas and external state workspace enabled.
Selected modules:dx7,drums,arp,lfo,env,register,chance; GPL modules enabled,
DX7 trunc12. The link uses maintained SDK-free runtime sources and no SDK
library. Existing SDK headers/toolchain are build inputs only.

The probe receives all caller-owned objects; it creates no app, engine,
sequencer, editor, storage backing or arena:

```c
int native_state_probe(fm1_app_t *app,
    const fm1_app_state_stage_t *ops, void *ctx, void *memory,
    fm1_state_report_t *report) {
  fm1_app_state_workspace_t workspace = { memory, 65536 };
  return fm1_app_state_project_stage(app, 2, ops, ctx, &workspace, report);
}
```

[verified] The component link has193,068 text/rodata bytes,8 data and408 BSS;
the BSS includes380 retained state-TU bytes and alignment. These totals exclude
caller-owned arena and app baseline allocations. No unresolved symbols remain.
The unchanged SDK-free link audit passes12 checks/0 pending. No allocator,
`sscanf`, host CLIP extractor, old stack-backed binary reader or old pull JSON
reader is retained. This probe has no startup/IRQ/storage/backend or installation
contract; its private measurement linker script is not a production linker map.

[verified] Target queries: compact codec43,788; manifest1,072; binary reader
9,528; small JSON emitter2,624; provider/JSON-reader/emitter auxiliary6,912 bytes.
All fit their unchanged reserved arms. The whole65,536-byte caller arena is
charged, including unused alignment and phase space; the auxiliary query alone
is not a fit argument. Persistent context/manifest occupies the first8,192;
codec/reader phase gets49,152; final8,192 holds the emitter and spare space.

## Conditional incremental RAM and stack

[verified, bounded analysis] Vendor linked disassembly and ELF symbol extents
were used to sum register pushes and downward SP adjustments, conservatively
keeping caller frames across tail transfers. Relative transfers without symbol
annotations were resolved by instruction length plus vendor displacement and
checked against every annotated transfer. No recursive direct calls, unresolved
reachable indirect targets or dynamic SP adjustments remain in this scoped
analysis. Native modes exclude legacy writer callbacks; source-backed END does
not recursively emit; SOUND may recurse only one level into INSERT/MFX. Internal
provider callbacks terminate at leaf scans. Movy encode comparison and decode
callbacks are distinct. `snprintf` uses its buffer gadget, not an external putchar.

The conservative library maximum is4,504 bytes including the24-byte probe, or
4,480 bytes from the public API entry. The largest path includes two nested
1,280-byte modulation collectors during prior-parameter scanning:
`stage -> prepare -> collect_project -> mod_out -> mod_collect -> mod_emit ->
out -> state_write -> each_param -> project_params -> mod_collect -> memcpy`.
This is an upper-bound call graph, not a measured high-water mark. With a1,024-byte
external getter/backend complete-callee allowance, the largest modeled path is
5,488 including the probe. Arbitrary callbacks are not proven bounded.

The conditional profile reserves:

| Charge | Bytes |
| --- | ---: |
| Complete caller-owned PROJECT arena | 65,536 |
| Whole app-state TU BSS, including discarded host load plan | 11,976 |
| Other linked globals and alignment | 36 |
| Stack reservation | 8,192 |
| Separate safety reserve | 8,192 |
| Maximum extra backend/context/ops/report/cache RAM | 4,096 |
| Total | **98,028** |
| Remaining below98,304 | **276** |

The8,192 stack reservation requires: library<=4,480; each external getter/backend
callback's complete nested callee closure<=1,024; caller chain and locals<=512;
combined same-stack IRQ/exception use including nesting<=1,024. Their conservative
sum7,040 leaves1,152 stack padding in addition to the separate8,192 safety reserve.
No recursion/reentry or hidden heap/lazy allocations are allowed. Backend buffers,
ops/report/context outside the arena/caller stack all count within4,096. Candidate
file bytes must live in external storage, not an uncharged RAM file. These limits
are documented caller requirements, not runtime-enforced facts. A concrete
backend and platform must prove them before admission; flags/module/caller changes
require fresh closure analysis.

Existing app/engine/modulation/sequencer/editor instances are borrowed with zero
additional copies in this API. Their complete allocations remain separately
charged baseline full-product RAM obligations. This component link neither
measures nor establishes that baseline, general13-engine fit, a suitable target
IRQ stack, storage geometry/endurance, live-save latency or hardware acceptance.

## Evidence and next dependency

Private raw evidence, exact commands, source/object provenance, toolchain/header
binding, linked listing/map, audits and callback graph are retained under
`lunar-native-state-fit-20261101/scratch/native-state-fit-20261101/evidence/`.
Raw vendor output is not committed. Toolchain archive SHA256:
`f686586bcfb45e0f0bb27fd2b39c7a7f313cb4f0e88a66a14da621ffa8225958`;
bound tree SHA256:
`851733550499eca33cd737b2343bf48a1c846e0fe7246054d8372d43e7cfa066`.
Component ELF SHA256:
`94e13b5d7556373e138275b7c8cd4a8976875ad3f7bad7375aa96b560d03ad86`.

Next: coordinator reviews this conditional accounting, integrates approved source
and runtime through CI, and supplies the bounded reader to the separate selected
PROJECT applier. A later concrete backend must prove the caller limits and
transaction/storage contracts in a full application map. No production binding
or hardware admission follows automatically. Reproducible objects/configured
header copies are removed after review; small logs/scripts/maps/receipts remain.
