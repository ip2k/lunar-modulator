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
