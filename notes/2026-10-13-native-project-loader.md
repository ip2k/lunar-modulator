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
