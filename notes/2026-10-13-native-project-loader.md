# Native project loading: retained storage and adaptation plan

## Measured limit

`tools/native/measure_project_loader.py` compiles the existing browser project
adapter with the pinned pi32v2 r3/mfprev1 toolchain, external instance arenas and
indexed display enabled. Sixteen Hera containers cover eight root combinations
at Os and Oz. A relocatable garbage-collected link measures this translation
unit's retained sections; unresolved external definitions, runtime stack,
allocator overhead and complete firmware placement are outside this measurement.
No LTO or hardware execution is claimed.

All sixteen corrected runs passed, without OOM [verified]. Both optimization
levels retain the same writable sizes:

| Entry roots | Writable bytes |
| --- | ---: |
| check, load, or check plus load | 629,916 |
| save | 917,851 |
| pack | 852,313 |
| load plus save, load plus pack, or all four | 990,365 |

Import alone retains `g_w` 491,520 bytes, `g_set` 65,538, `g_clip` 32,770,
`g_seq_scratch` 32,768, `g_plan` 6,976 and merged globals 344 [verified].
The import-only local storage already exceeds the device's total SRAM; it cannot
be directly linked into the native firmware. Changing Os to Oz cannot reduce
these fixed buffers. `rate_ok` retains the large workspace because it constructs
engines there during preflight [verified source inspection].

The first measurement attempt failed because the Hera snapshot/include path
lacked `state_clip.h`; its failed logs are retained. The corrected attempt adds
`engines/host` to the source closure and include path. Private reports and receipt
are under `build/native-external-arenas-16-20261012/project-loader-v2/` and
`project-loader-v2-verification.json`. Receipt SHA256: `8e8f5762d4cf20f8aab3b107eae04bf67e32055ef1ffa585769792baa54b4def`.

## Existing implementations and bounded adapter decision

Reuse the existing binary state codec, module registry, parameter mapping,
sequencer importer and application activation APIs. The browser adapter remains
useful as a host reference; its whole-text buffering and scratch-engine creation
cannot establish native admission. Keep JSON export/packing on the build host.
The existing native set loader already reads immutable packed bytes and stages a
sequencer in temporary pool storage before activation [verified source].

A native project adapter needs the following before use:

1. Stream binary records from immutable XIP bytes into a bounded project plan;
   avoid retaining export buffers or materializing set/clip text.
2. Validate every module and parameter against the selected catalogue and check
   the native allocator's capacity, alignment and overhead. The browser's
   387,924-byte aggregate budget is not the native pool's 216,064-byte budget.
3. Stage the sequencer through the checked importer and refuse observed syntax,
   range, capacity or binding loss. Current syntax diagnostics remain partial.
4. Establish an allocation/commit strategy that preserves the live project on
   failure. Browser pass-two assumptions do not prove this for the native pool.
5. Compare accepted project behavior with the host reference and malformed-input
   refusals in sixteen Hera chunks, then verify target link, stack and timing.

Shrinking a buffer alone is insufficient: `rate_ok` currently assumes that an
engine larger than its scratch buffer supports the rate. A native adapter must
not inherit that assumption as acceptance evidence. Clip merging also allocates
host memory. Neither path is admitted for native runtime use yet.

Goal remains the thirteen-engine default plus selectable engines, effects and
songs/sets builder. Expanded-layout approval, real installation/recovery, full
engine timing, MIDI and persistence acceptance remain outstanding.

## Actual-pool allocation preflight

`lunar_instance_pool_can_fit` tries at most 32 allocations in the proposed order
and frees its trial blocks in reverse order on either outcome. Exclusive
main-task ownership is required. Live allocations and their data remain intact;
free-list ordering is not guaranteed byte-identical, and this does not reserve
capacity, initialize engines or establish atomic project activation.

Sixteen Hera chunks passed 48 sanitizer executions across 165,376, 196,608 and
216,064-byte pools, with 8,192 randomized allocation operations per execution
[verified]. Added tests cover failed partial trials, invalid request vectors,
empty requests, preserved live data/accounting and trials during fragmentation.
Shapes' 206,904-byte instance fits only the largest tested pool; adding a
32,768-byte sequencer staging allocation is refused [verified host allocator].
All sixteen v15 native content links and their 77 audit/option checks passed,
without OOM; owned containers were removed. The new API is not called by the
firmware yet and may be garbage collected: links do not prove target execution.

Private receipts: `instance-pool-preflight-v1-verification.json` SHA256 `2ee8ec3cde909bbfcf2a39ee2d5427d3d9449535a618127d14492207b0fb896a`. `content-loader-link-v15-verification.json` SHA256 `7d256412511bcd4faae5273acf230a1586e776a65c16e8a05157419ca1b7c24c`.

## Bounded selected-catalogue unit plan

`firmware/native/project_units.c` streams an immutable binary PROJECT through
the existing CRC-checking codec. It collects eighteen native engine slots
(four sounds, eight inserts, two master effects, four MIDI effects) and eight
rack positions against caller-supplied selected registries. It rejects duplicate
positions, unavailable IDs, unsupported slots and zero/missing engine allocation
sizes. Size callbacks run after the complete container read; a failed call keeps
the output plan unchanged. Empty non-primary sound/effect units retain no engine.
The compact slot numbers are explicitly different from shared-app unit codes.

The pi32v2 compiler confirmed the plan occupies184bytes [verified]. Sixteen Hera
chunks passed32 ASan/UBSan host executions at Os/Oz and compiled the new source
with the pinned target compiler [verified]. Complete18-unit/eight-module plans,
compressed input, CRC damage, truncation, empty optional sound, catalogue/type
mismatch, unsupported second MIDI slot, duplicate units/modules, invalid API
arguments and missing/zero size callbacks were covered. Initial fixture failures
were corrected to include a modulation seed and mandatory Sound1; v1/v2 are
failed campaigns, not acceptance evidence. No OOM; owned containers removed.
Receipt `project-units-v3-verification.json` SHA256 `3e67f287205abcf231314154dfbc1a5e778bee336ad9b44a3c4584bee025661f`.

This is only a unit/allocation plan, not project admission: parameter values,
modulation cables/data and sequence semantics/bindings are not validated. Module,
sequencer and workspace allocations are excluded. No engine is constructed,
capacity reserved, app changed or project activated. It is not linked/called by
the running firmware yet; target compilation does not prove execution, whole
firmware placement, stack or timing. Atomic replacement remains outstanding.

## Selected-owner parameter admission

The unit planner now also checks PARAM records against the previously selected
engine or rack kind [verified source/tests]. Unknown UIDs, empty owners, index
values for continuous parameters, values outside descriptor limits, fractional
enum values, nonfinite float bits and invalid/missing pad indices refuse the
plan before engine size callbacks run. Valid index values add the descriptor's
minimum, as the existing state applier does. Ordinary parameters require the
no-focus marker; per-pad parameters need an owning FOCUS descriptor and an
index within its entry range. No parameter is applied or normalized.

Sixteen Hera chunks passed64 ASan/UBSan executions at Os/Oz, with target source
compiles and the184-byte plan size assertion [verified]. Added cases cover
missing engine/module UIDs, an empty optional sound's parameter, low/high range
errors, enum/index mismatch, fractional enum values, normal/per-pad focus
errors, accepted endpoint values, accepted module parameter and valid last-pad
value. No OOM; owned containers removed. Receipt SHA256 `3e67f287205abcf231314154dfbc1a5e778bee336ad9b44a3c4584bee025661f`.

This supersedes the earlier parameter-validation exclusion for UID/type/range/
pad metadata only. Engine-specific parameter behavior, modulation cables/data,
sequence dependencies, actual pool admission, engine initialization, atomic
activation and whole-firmware/hardware execution remain unproven.

## Fresh modulation rack capacity

The unit planner now checks selected module descriptor magic/API, bounded
parameter/port/data counts, required callbacks and parameter metadata pointers.
After the complete binary read it calls instance_size, bounds each request
before arithmetic, rounds each to16 bytes and gives zero-byte modules the
runtime's16-byte minimum. The fresh base rack must fit FM1_MOD_ARENA (8192B).
No constructors or process callbacks run; a failed call preserves output.
The plan remains184B on pi32v2 [verified target compile assertion].

Sixteen Hera chunks passed96 ASan/UBSan executions at Os/Oz and target source
compilation [verified]. Added checks cover8192/8193-byte requests, eight1024-
byte modules, alignment overflow with eight1025-byte modules, zero-byte
modules, missing callbacks, invalid magic/API, excessive metadata counts,
SIZE_MAX and8191-byte alignment. Six passing nodes per shard were checked in
the saved logs; no OOM, owned containers removed. Receipt
`project-units-v5-verification.json` SHA256
`3e67f287205abcf231314154dfbc1a5e778bee336ad9b44a3c4584bee025661f`.
The compact receipts intentionally record shard exit status, not node lists;
this hash matches earlier campaigns with identical status vectors. Campaign
launcher and logs identify the actual selected nodes.

This proves only fresh base-rack capacity under stable descriptors. Per-voice
module copies, modulation cable/data semantics, the enclosing26848B modulation
runtime, actual engine pool admission and transactional replacement remain
separate gates. The planner is still not linked/called by the native app. No
hardware operation occurred. All-thirteen default and selectable image builder
remain the target; expanded-layout approval remains pending.

## Disposable modulation staging

Added lunar_project_mod_stage: a main-task-only adapter using the selected unit
plan, shared state modulation applier and production route/per-voice planner.
It requires a disposable aligned fm1_mod_size() workspace, verifies selected
module pointer identity against the compiled runtime registry before constructors,
binds selected engine metadata, applies module parameters/data and cables, and
refuses skipped records or enabled routes refused by the planner. Failed staging
destroys the candidate; it does not touch a live runtime. Caller owns immutable
input and stable descriptors and must keep workspace disjoint from live state.

Sixteen Hera chunks passed32 ASan/UBSan executions at Os/Oz with all16 production
modulation kinds and256 rack arrangements [verified]. Tests compare fresh base
capacity planning against actual constructors; cover single, repeated-eight and
mixed-eight racks, valid routes, unavailable source/destination, disabled invalid
routes retained under shared runtime policy, incompatible data and undersized
workspace. Source compiled with the pinned pi32v2 compiler at both optimizations.
No OOM; owned containers removed; every saved shard log checked. The first v3
run failed because a launcher rename changed sdk-v1213 to sdk-v3213; corrected
launcher rerun passed. Status-only receipt project-racks-v3-verification.json
SHA256 3e67f287205abcf231314154dfbc1a5e778bee336ad9b44a3c4584bee025661f.

This stages modulation only. Sound engine constructors/audio are not exercised
by these tests; they use a small sound descriptor fixture. Engine parameters,
sequence bindings, allocator reservation, transactional project activation,
whole-firmware stack/timing and device execution remain separate gates. Shared
per-voice planning may reduce modulation voice capacity and does not establish
advertised sound polyphony. The adapter is not called by the app. No hardware
operation or installable release; expanded-layout approval remains pending.

## Opt-in native project staging link

The timed application builder accepts --link-project-loader, compiles both
native project adapters and roots lunar_project_mod_stage against the checked
catalogue's shared codecs/applier. Its receipt records modulation staging linked,
with activation, stack margin, timing, sequence semantics and hardware all false.
The timed probe does not call this entry point or allocate a staging workspace.

Sixteen Hera native links passed with the SDK-free key audit, no undefined
symbols, retained staging entry point and byte-for-byte selected content checks
[verified]. Profiles use five sounds (Trio, drums, Shapes12, Macro, DX7), five
effects with optional Plate, Arp and three modulation kinds, with0/1/2/4 assets
from text/binary input. These are fit/link exercises, not the all13 release.
No OOM; owned containers removed. Receipt project-loader-link-v1-verification.json
SHA256 7d256412511bcd4faae5273acf230a1586e776a65c16e8a05157419ca1b7c24c.
No device operation, runtime activation or installable release.

## Disposable project sequence staging

lunar_project_seq_stage validates the binary unit plan before feeding project
SET lines to the existing streaming importer in an initialized disposable
sequencer. It rejects observed importer loss, internal routes to omitted sounds,
unresolved/zero-UID/non-lockable assigned lane parameters and invalid MIDI
channels. No SET lines leaves scratch intact. Failed staging leaves has_set
unchanged; caller must discard scratch. Caller supplies matching rate/limits
and keeps input, descriptors, outputs and live state disjoint from scratch.

Sixteen Hera chunks passed32 ASan/UBSan executions and pi32v2 source compiles
at Os/Oz [verified]. Accepted exports match the existing importer. Cases cover
missing sounds, labels, NOLOCK/zero UID, absent parameter metadata, malformed/
unsupported observed-loss lines, invalid routes, case/last-colon matching, no
SET lines and missing output pointer. Separate live storage remains unchanged.
Receipt project-sequences-v1-verification.json SHA256
3e67f287205abcf231314154dfbc1a5e778bee336ad9b44a3c4584bee025661f.

Opt-in --link-project-loader now retains both modulation and sequence staging.
Sixteen Hera links passed SDK-free audits, undefined-symbol checks, retained
entry points and selected content byte checks [verified]. Same selected profiles
as link-v1, not all13. Receipt project-loader-link-v2-verification.json SHA256
7d256412511bcd4faae5273acf230a1586e776a65c16e8a05157419ca1b7c24c.
All campaign logs inspected; no OOM; owned containers removed. Status-only
receipts repeat earlier hashes; campaign launchers/logs identify executed nodes.

Neither adapter is called by the native app yet. Full grammar/sequence playback,
external MIDI delivery, engine constructor/allocation admission, parameter/base
application, activation, stack/timing and device acceptance remain open. Shapes
needs about207KB of the216KB pool: runtime replacement cannot assume coexistence
with staging or another instance. No hardware operation or installable release.
Expanded-layout approval remains pending; all13 default plus selectable builder
remain the active goal.

## Owned engine candidates

lunar_project_engines_stage validates the unit plan and engine constructor
descriptors, reserves every selected instance in the actual TLSF pool before
calling constructors, then constructs defaults. It retains original allocation
pointers separately from returned handles. Failure destroys successful engines
in reverse order and frees all candidate blocks; existing allocations stay live.
Success gives caller owned candidates requiring release or explicit transfer.
Overwriting a nonempty candidate is refused; empty cleanup is idempotent.

Sixteen Hera chunks passed32 ASan/UBSan executions/256 candidate scenarios and
Os/Oz target compiles [verified]. Controlled sound fixtures return interior
handles and refuse chosen construction positions. Cases vary1..4 sounds/four
allocation sizes, constructor refusal,206904B capacity pressure, fragmented pool,
invalid descriptor/host API and occupied candidate. Live4096B bytes and pool
accounting remain intact after cleanup. No production engine audio or timing
proof. Receipt project-engines-v1-verification.json SHA256
3e67f287205abcf231314154dfbc1a5e778bee336ad9b44a3c4584bee025661f.

Sixteen native links retain engine staging/release plus modulation/sequence
staging, pass SDK-free/undefined-symbol audits and content byte checks [verified].
Receipt project-loader-link-v3-verification.json SHA256
7d256412511bcd4faae5273acf230a1586e776a65c16e8a05157419ca1b7c24c.
All logs inspected, no OOM, owned containers removed. No app activation, project
parameter/base application, production constructor/CPU timing or device proof.
Candidate pool ownership must remain exclusive; free-list order and allowed
first-create read-only engine caches may change. No hardware operation.

## Owned candidate parameter restoration

`lunar_project_engines_apply` validates the complete immutable project before
applying engine PARAM records to owned candidates. Pad parameters are restored
with their focus indices; saved focus is deferred until all pads are loaded.
Candidate base values retain final focused readback for later app/mod binding.
CRC refusal precedes parameter changes; other failures require discarding the
candidate. This does not apply remaining project records or activate the app.

Sixteen Hera chunks passed32 Os/Oz sanitizer runs/320 controlled scenarios and
pi32v2 compilation [verified]. Focused two-pad fixtures cover distinct values,
final focus, missing readback callback, corrupt reapply, ownership, constructor
failures and capacity pressure. The initial fixture incorrectly grouped all
UNIT records before PARAMs; the production writer refused it. Corrected
canonical ordering passes. Sixteen native links retain parameter apply, pass
SDK-free audits and verify embedded content bytes. A16-chunk regression campaign
passed128 unit-plan/sequence tests. No OOM; all logs checked; containers removed.
Evidence: project-engines-v2, project-loader-link-v4 and
project-parameter-regression-v1 logs/receipts in the ignored evidence directory.
No real-engine parameter/render, activation, timing, stack margin or hardware
acceptance is established. No device operation; no installable release.

## Modulation bases follow saved focus

Modulation staging now resolves final saved focus before restoring sink bases
from engine PARAM records [verified source/tests]. Per-focus records for other
pads remain engine-owned; MIDI-effect parameters have no modulation sink and
are ignored by this base pass. Four sound units, inserts and master slots map
to the production sink codes. This avoids overwriting loaded values with
metadata defaults on the first modulation tick. No live state is accessed.

Sixteen Hera chunks passed32 Os/Oz sanitizer runs/256 rack scenarios and native
compiles, with all16 production module kinds and two-pad base checks [verified].
Another16 native links passed audits/embedded byte checks. NoOOM; all logs
inspected; containers removed. Receipts: project-rack-bases-v1 and
project-loader-link-v5 in the ignored evidence directory. Sound1 bases are
exercised; additional sink mapping, real engine readback, app adoption, runtime
stack/timing and hardware remain unverified. No installable release.

## Prepared shared-app chain adoption

Added external-arena-only `fm1_app_adopt_start_units`: cold empty app accepts
already constructed registry engines in app-unit order without constructors or
allocator calls [verified source/tests]. Before ownership transfer it checks
registry/API/kind/size, disjoint aligned allocations and contained handles,
insert parents, RAM including additional sound mix buffers and modulation sink
capacity. Success preserves app values, binds modulation bases, installs FM6's
user-bank shim and transfers destruction/free responsibility. Failures leave
ownership intact. Caller guarantees before-input startup and valid already-applied
values from the same provider; no live replacement transaction is provided.

Hera `app-adoption-v3`:16 chunks pass embedded/external storage at `-Os` with
address/undefined sanitizers, eight refusal classes, two adopted sounds/master
FX, saved gain/base, finite audible rendering and balanced allocations [verified].
All logs inspected, no OOM; owned containers removed. `app-adoption-target-v1`:
16 chunks compile actual app for pi32v2 at both Os/Oz and verify symbol presence.
No final native link or device execution claimed. Earlier v1 failed missing
clang command; v2 failed a fixture RAM expectation excluding default modulation.
Both failures retained; corrected test includes pre-adoption RAM baseline.
Receipts/logs downloaded to ignored build/native-external-arenas-16-20261012.

Still required: compact project-to-app mapping, actual pool-backed startup,
MIDI effects, settings/view/DX7 records, staged sequence/mod rack adoption,
real engine budget/timing and full linked image. Catalogue source manifests
must be rebuilt after these shared-app changes. No installable release or
hardware operation. Expanded flash-layout approval remains pending.

## Pool-backed compact audio mapping

Added external-arena-only `lunar_project_adopt_audio_units`, mapping compact
project sound/insert/master positions into the shared app slots [verified].
It preserves prepared handles and saved parameter bases, rejects incompatible
pool contexts or overlapping candidate metadata, and clears only the fourteen
transferred audio rows after successful adoption. MIDI-effect rows remain
candidate-owned for explicit release. This is a cold-start audio-chain adapter,
not complete project activation or a live replacement transaction.

Hera `app-pool-adoption-v2`: all sixteen shards passed embedded/external storage
with Os address/undefined sanitizers, real TLSF pool allocation, refusal ownership
preservation, every compact audio position, retained MIDI candidates and balanced
pool cleanup [verified]. Initial v1 failed a fixture lookup: arp is in the
MIDI-effect registry, not the audio registry. Corrected fixture uses its actual
MIDI descriptor. Target campaign `app-pool-adoption-target-v1` passed all sixteen
shards: actual shared app and adapter compiled at both Os/Oz (64 objects) with
entry symbols checked. All logs inspected; no OOM; owned containers removed.
Receipts/logs downloaded to ignored build/native-external-arenas-16-20261012.

Fresh indexed Shapes12 catalogue compiled 167 objects in sixteen shards with
zero failures (`out-indexed-shapes12-adoption-v1`) [verified]. Optional project
loader now roots the adapter in its native link; all sixteen link-v6 shards
passed audits, rooted-entry and embedded-byte checks [verified]. MIDI/settings/view/DX7 and staged sequence/modulation startup,
stack/timing margins and real hardware remain unverified. No installable release
or device operation. Expanded layout approval remains pending.


## MIDI startup restoration and saved enable flags

Added cold-start `lunar_project_restore_midi_units`: checks selected MIDI registry
identity, finite/ranged/integral parameters, inline instance capacity and RAM
before mutation; reconstructs four MIDI effects into app inline storage and
restores values/enable flags [verified source/tests]. Pool candidates remain
owned for separate cleanup. Constructor refusal requires discarding the cold
app before playback; this is not live replacement or complete activation.
The checked unit plan retains four ON flags (absent means bypass), refuses
an enabled empty owner and remains failure-atomic. pi32v2 plan is188 bytes.

Hera app-midi-start-v1: all16 Os ASAN/UBSAN shards passed embedded/external,
four MIDI positions, NaN/fractional/empty/frame refusals, saved arp mode,
rendered MIDI note output and balanced pool cleanup [verified]. Target v1:
all16 shards passed actual app/adapter Os/Oz compiles and rooted-entry checks.
Project-units-on-v1: all16 chunks passed96 Os/Oz sanitizer/target tests,
including compressed/uncompressed flags and preserved failure output.

Link-v7 passed12/16, with four audit refusals retained. Vendor objdump proved
the forbidden address pattern crossed a resolved snprintf call and sp+=4,
not an address load [verified]. Extended only the existing byte-exact call
boundary proof to that stack instruction; negative tests retain literal,
missing/mismatched decode, external target and function-boundary refusal.
Link-v8 passed all16: audit/test gates, MIDI root, embedded byte checks;
selected five-sound profiles with optional Plate and0/1/2/4 assets. All campaign
logs inspected, noOOM; owned containers removed, receipts/logs in ignored build
folder. These links do not contain all13 default engines. No installable,
playback, timing, stack-margin or hardware acceptance is claimed.

Next connect the startup transaction to checked ON flags, settings/view/DX7,
sequence/modulation adoption, then persistence/MIDI timing, full catalogue
budgets and installer/recovery. Expanded-layout approval remains pending.
