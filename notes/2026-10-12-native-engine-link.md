# Native engine compilation and dependency inventory

[verified] The actual `RENDER_PRODUCT_OBJ` selection in `engines/Makefile`, with
`FM1_GPL_MODS=1 FM1_MODULES=all`, contains 160 engine product objects after
excluding the host renderer. `tools/native/engine-objects.mk` enumerates that
selection rather than maintaining a second source list. This excludes the
sequencer, application UI and HAL; it is not the full firmware build.

[verified] Sixteen simultaneous Hera containers compiled disjoint object shards.
All exited zero, without OOM. A pi32v2 relocatable link combined all 160 objects
with 28 unmodified pinned LLVM compiler-rt arithmetic units. No SDK archive was
linked. Hash verification and the arithmetic undefined-symbol gate passed.

[verified] The experiment used the JieLi compiler's pi32v2 r3 target with
`-mfprev1`, freestanding function/data sections, C++11, no exceptions or RTTI,
and the engines' existing wraparound flags. Standard C/C++ headers temporarily
came from the SDK source checkout. `_LIBCPP_CONFIG_SITE` bypassed its bundled
pthread prefix configuration and `_LIBCPP_HAS_NO_THREADS` selected the upstream
no-thread profile. `_GNU_SOURCE` and `_XOPEN_SOURCE=700` expose math constants
used by the existing engines. The first two attempts failed respectively on
incompatible pthread configuration and unavailable M_PI; both are retained.
These flags do not demonstrate numerical accuracy or realtime suitability.

[verified] The final link has no unresolved compiler arithmetic helpers. It still
requires C++ string/vector/sort/new/delete support, C/math functions and file I/O.
This link retains every function; a firmware link with garbage collection must
establish which dependencies are reachable before excluding host paths. No
stubs were supplied to claim success. Independent standard headers and runtime
sources remain necessary before calling the complete build SDK-free.

[verified] Private receipts: local `build/native-engines-16-20261012/`, and Hera
`/home/claude/mvave-fm1/native-engines-16-20261012/`. Final receipts are
`verification.json` and `out/dependencies.json`; earlier receipts are
`first-verification.json` and `second-verification.json`. All task containers
were inspected and removed. Container image SHA:
`0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc`.

[verified: source] Dinghy pinned at `d44df7db09b98ccad2f1233b8f83f5f09c04829e`
supplies a GPL-3.0-only FM1 platform derived from Felucca/SLOOP, with an
`app_audio` and `app_main` application boundary. Its integer-only rule includes
the absence of compiler arithmetic helpers. Supplying those helpers resolves
linkage, but does not establish that software floating-point meets its 256-frame
audio budget. Next: link a real engine through that boundary, measure cost on
hardware, retain stock SPL/OTA/cfg gates, and validate controls, MIDI and recovery.

No FM1 command or flash write was issued during this compilation campaign.

## Full catalogue size experiment and release priority

[verified: owner instruction] Maximize engine count before release. The earlier
balanced catalogue proposal is not the release completion criterion.

[verified] All 166 catalogue/application object selections compiled in sixteen
concurrent Hera containers with -Oz. Each process and inspected container exit
was zero, without OOM. tools/native/compile_catalogue.py now records its selected
optimization; -Os remains the default. The -Oz evidence is in Hera
`/home/claude/mvave-fm1/native-catalogue-16-20261012/out-oz/`.

[verified] An exploratory entry retaining shared-app init, draw and render,
with external arenas and every catalogue object, failed the preserved Dinghy
XIP region (581,564 bytes): -Os overflowed by 269,172 bytes; -Oz by 186,684.
The measured reduction is 82,488 bytes. Neither attempt linked SDK or standard
archives, HAL or the complete C/C++ runtime. Undefined-symbol relocation errors
remain, and neither output is a firmware candidate. Private scripts/receipts:
`build/native-external-arenas-16-20261012/`, mirrored on Hera; link-audit and
link-audit-oz subdirectories retain failures. This is a lower-bound integration
experiment, not a measured size for a complete working application.

[verified] A pinned MIT standalone formatter was imported unmodified with
licence and per-file hashes in firmware/third_party/printf. Sixteen parallel
ASan/UBSan format/truncation/guard comparisons and sixteen pytest wrapper cases
passed on Hera. Actual pi32v2 compilation passed; its arithmetic helpers and
optimizer-emitted memcpy still need runtime resolution. UPSTREAM.md records the
candidate evaluation and scope. No device operation was performed for these
tests. Next: inspect reachable resource costs and finish the source-based native
runtime, then establish a real complete link and a catalogue that fits without
changing stock partition safeguards.

## Shared resampler coefficients

[verified] FM1_SHARED_RESAMPLER=1 selects one copy of the unchanged kernel
and lowpass arrays, with C linkage for C/C++ consumers. The default remains
header-only. Use separate BUILD directories for each profile, as for other
compiler-flag changes. Sixteen parallel Hera measurement comparisons passed:
tables, exact pass-through, refused ratios, input window, chunking/extreme input
at five rates and two sweeps. The first run caught early expansion of COMMON
before the fragment changed EXTRA; both flag paths are now consistent.

[verified] All 167 native catalogue/application objects in the shared -Oz
profile compiled in sixteen Hera chunks, no OOM. A relocatable garbage-collected
link retained init/draw/render and measured text+rodata of 761,108 bytes versus
774,380 for header-only -Oz (13,272 bytes saved, including code differences).
nm shows one 3,076-byte kernel and one 248-byte lowpass array instead of five
of each. This relocatable link deliberately leaves runtime symbols unresolved;
it does not use the device linker layout and is not executable firmware.

[verified] Reachability discards the earlier C++ string/vector/file-I/O paths
in this experiment, but allocation, math, parsing, standard formatting, memory
functions, compiler arithmetic and libc++ float sort remain unresolved. No
placeholder implementations were linked. Hera evidence: catalogue out-shared
is the retained failed attempt; out-shared-v2 is the passing corrected build;
external-arenas out/reachable-shared and shared-resampler-verification.json
hold sizes and comparisons. Primary-root Rarefaction/Serena located the inline
resampler; Rarefaction used fallback clangd flags and incomplete on-open callers,
so actual worktree source and builds are the authoritative checks.

## Source-based math and string runtime (2026-10-13 checkpoint)

[verified] Imported 62 unmodified portable musl units and their required private
headers from official commit b1efda5b91735e33635376ca11c9b497a1c66e39, with
COPYRIGHT, individual notices, per-file SHA-256 inventory and candidate decision
in firmware/third_party/musl/UPSTREAM.md. Picolibc's official source was examined;
its architecture/configuration machinery made a bounded generic musl subset the
smaller integration for this experiment. No Linux services or target assembly
were imported. First-party libc_compat headers supply visibility, compiler-checked
little endian, internal string declarations/aliases and math-header name
separation. Newlib-style __fpclassifyd is supplied by the unchanged musl routine
via a compile define. Standard declarations still come from toolchain headers;
no standard library archive or JieLi SDK archive is linked.

[verified] tools/native/build_libc.py checks all source pins and compiles a
selected shard with pi32v2 r3/mfprev1 -Oz flags. Its 62 objects compiled across
sixteen Hera containers, all process/inspected exits zero and no OOM. A private
relocatable subset link leaves only fourteen compiler arithmetic helpers, not
other libc/libm functions, unresolved. This is not a complete firmware link.

[verified] tests/test_native_libc.py compiled the pinned sources, renamed object
symbols with objcopy and independently compared them against host libc/libm.
All sixteen concurrent Hera pytest chunks passed with ASan/UBSan enabled,
covering 16,384 numerical rows plus floating-point edges, and copy/move/set
alignment, overlap and write canaries. Limits and numerical tolerances are
recorded in UPSTREAM.md. These checks do not establish target floating-point ABI,
execution time, exception flags, or all string-function behavioural cases.

[verified] Private receipts: build/native-musl-evaluation-20261012 and matching
Hera directory. tracked-verification.json and native-libc-pytest-verification.json
record the checked-in build/test results; host-verification.json records the
initial sixteen numeric/memory shards. Earlier compile and host-header failures
were retained. Missing endian/features declarations, internal helper prototypes,
Newlib gamma symbol differences and the extracted build's missing visibility
flag were resolved without replacing any implementation with a stub. No FM1
command was issued. The physical device's earlier identity/admission remains
stale; a fresh admission is required before any further operation.

Next: integrate these objects with the catalogue, formatter, remaining compiler
helpers, parser/allocator/sort support and actual HAL; measure complete flash/RAM
and audio budget before choosing the maximum feasible engine catalogue. Latest
previous exact-head CI (d6dffc5, run 38359023800) was still in progress at this
checkpoint; these local/Hera passes are not CI or release acceptance.


### 2026-10-13: remaining arithmetic conversions and runtime closure

[verified] The compiler runtime now contains 31 pinned LLVM C units. Sixteen
parallel target builds linked the arithmetic probe with no unresolved symbols;
sixteen host UBSan shards compared signed/unsigned 64-bit-to-double software
conversions against hardware casts (16,384 full-width rows per shard, rounding
ties and exponent boundaries). These are source and target-link checks, not
physical execution. Receipt: private `build/native-musl-evaluation-20261012/`.

[verified] Combining the earlier init/draw/render catalogue reachability object
with the selected musl runtime, formatter and compiler runtime gives 389,154
bytes text and 407,727 bytes rodata (796,881 total). The preserved XIP region is
581,564 bytes; HAL and other interaction roots are not included in this count.
The relocatable link still references float sort, __fpclassifyf, atoi and
putchar_. The earlier formatter object may retain unused routines because its
compile did not split all functions; rebuild before treating putchar_ as a
reachable UI requirement. This is not a firmware candidate or a complete app
link. No device command or flash write occurred in this stage.

[verified] Source runtime checkpoint 138cb6733a5dba7a44a0da61664ac1dbc9964070
was pushed and matched its remote branch SHA. Parent d6dffc52 exact-head CI
38359023800 remains in progress; no merge or release acceptance is claimed.
Both semantic tools selected the primary checkout, where the worktree-only
arithmetic probe file was absent; queries failed with file-not-found. Direct
worktree inspection and actual target compilation were used instead, without
changing another session's shared semantic-tool root.

### 2026-10-13: interactive runtime and final LTO measurement

[verified] The musl subset now has 66 unchanged upstream C units: added float
classification and ASCII digit/space predicates plus atoi. Source pins remain
checked. All 16 target shards and 16 independent ASan/UBSan host shards passed
on Hera; initial locale-header failures are retained in private receipts.
The compatibility header prevents toolchain locale-table macros from replacing
the selected predicates. Its opaque locale argument only supports the unused
ASCII _l aliases; it does not implement a locale service. Tests now reject
opposite signed zero rather than allowing tolerance comparison to mask it.

[verified] Disabling libc++ extern template declarations makes float sort
instantiate from the existing standard headers without a closed library or
custom sorting implementation. All 167 catalogue objects compiled in 16
non-LTO shards and 16 LTO shards. The non-LTO interactive closure retains
key/button/encoder/master and note/pitch/all-notes-off roots: text 417,606 plus
rodata 407,830 = 825,436 bytes. Its remaining putchar_ undefined table entry
has no surviving relocation in the inspected earlier interactive closure.
This is a reachability measurement, not a complete firmware application.

[verified] A partial LTO link followed by another GC link grew to 941,421 bytes
and introduced unused parser/heap references. Linking the original bitcode
directly, together with the 66-unit runtime, formatter and 31-unit compiler
runtime, against the actual preserved app.ld avoids those unresolved symbols
but fails: XIP overflow 227,740 bytes. No enlarged partition, unresolved-symbol
ignore option or fake implementation was used. The measurement still excludes
the full HAL and release entry. The toolchain lto-wrapper cannot find its
same-directory ld; directly invoking pi32v2 ld with LLVMgold.so performs LTO.

[verified] Private receipts: native-musl-evaluation-20261012/out on Hera
(c-runtime-verification.json, closure-c-runtime/result.json),
native-external-arenas-16-20261012/out (c-runtime-pytest-verification.json,
final-lto-layout/link.log and link.map), and native-catalogue-16-20261012
(out-inline-sort and out-lto). Copies of key receipts are saved under local
ignored build directories. No device operation was performed. Owner direction
remains maximize engine count before release; no reduced release was selected.
Next: measure largest surviving assets/code, reduce footprint, integrate the
full HAL/application, then verify real-device installation and recovery.

### Complete-HAL footprint and lossless asset experiments (2026-10-13)

[verified] Rebuilt the committed browser module on Hera after the external-arena
application changes. Browser/native parity: 108 checks passed, with 108 identical
JS and musl results; glibc had 105 identical results and at most one LSB in the
remaining scenarios. Artifacts are committed at 2fd972950483338f15d3365c721c6a3b4a225c41.
The preceding CI failure was the stale committed Wasm build record, not a claimed
physical-device failure. Exact-head CI was still running when this note was written.

[verified] Sixteen independent lossless block-storage experiments round-tripped
194,261 bytes of Plaits/Braids waves and Comet sample data. Block sizes 64, 128,
256 and 512 were tested with raw or modulo-delta preprocessing and zlib levels
1/9; each block falls back to raw storage if compression expands it. Accounting
includes four-byte block offsets, but excludes an unimplemented decoder. Best:
512-byte delta blocks, level 9, 174,947 stored bytes, saving 19,314 bytes. This
does not close the flash deficit and does not establish real-time suitability.
No source asset was changed.

[verified] Sixteen engine-removal links retained input/note roots and the full
shared UI/runtime. Largest individual removal savings: Comet 139,064 bytes,
Shapes 81,024, Macro Heavy 42,052, DX7 40,384. These are configuration-dependent
link deltas, not independently additive module sizes. Removing Comet, Shapes
and Macro Heavy allowed the engine-only link to pass; no release was selected.

[verified] A second sixteen-way campaign included the pinned Dinghy HAL, actual
crt0/vector/ISR assembly, USB/recovery, audio buffers, LCD driver and crash UI.
Private generated copies disable OTA cleanup and NOR-write ranges, namespace
the HAL's three memory primitives to avoid duplicate musl definitions, and
namespace its two overlapping button enumerators. The first failed compile
receipt is retained. The stock app.ld and boot-pointer/core entry guard remain.
Full catalogue: link fails with XIP overflow 253,336 bytes (25,596 more than the
engine-only baseline). The eleven-engine sizing configuration links: .text
571,596, .ram_text 1,128, .data 44 bytes, giving 8,796 bytes flash headroom;
.bss 14,992 bytes; .pool 251,536 bytes, leaving 92,528 bytes in the fixed pool.
No engine arena is allocated in this measurement.

These callbacks are sizing scaffolding, not a hardware candidate: rendering
and drawing are not serialized, RGB565 display byte order is not adapted,
physical input mapping is absent, and engine arenas are unbound. The shared
application explicitly requires serialized calls. Real integration must resolve
these issues and preserve audio deadlines before any device admission. Successful
container exits are separate from link results: fifteen HAL variants have
link_exit=1 due to overflow, and one has link_exit=0.

[verified] Private scripts and logs: local ignored
build/native-external-arenas-16-20261012/{asset-storage*,module-cost*,hal-cost*,hal-template.py},
with matching Hera source/out directories. The successful module-cost-15 and
hal-cost-15 maps/results/ELFs were copied locally. No device operation occurred.
Owner direction remains maximum engine coverage. Engine-pack preference was
asked while further sixteen-way coverage measurements continued; no answer or
release-profile choice is assumed.

[verified] Sixteen further full-HAL engine-pack layouts all linked, retaining
the shared sequencer/modulation/effects/UI roots. Their union covers all fourteen
sound engines; e.g. eleven engines without Comet/Shapes/Macro Heavy, eleven
without Comet/Shapes/DX7, and separate Shapes/Comet-containing layouts. Headroom
ranges 1,904..79,672 bytes. Engine arenas remain unbound, so these are coverage
measurements, not playable candidates. pack-cost-layouts.json records every
omission and section size privately. The exhaustive 91-pair omission campaign completed in sixteen chunks: all
ninety-one twelve-engine layouts overflowed. The closest omits Comet and Shapes
and exceeds XIP by 33,244 bytes. Eleven is the maximum for this measured
implementation and preserved region, not a global optimum after further changes.

[verified] Added firmware/native/audio_queue.h as the main-loop-to-audio-ISR
bridge for a serialized application adapter. Eight 64-frame stereo Q15 blocks
use 4,096 bytes plus counters. Full queues refuse a push; underruns write a
complete silent block without consuming a future block and increment a counter.
NaNs become silence, and infinities/overflow saturate before integer conversion.
The queue is explicitly core-0 main-loop/core-0 ISR only, using aligned 32-bit
counter accesses and compiler publication barriers; it is not a portable thread
or multicore primitive. Zero initialization must precede interrupts.

[verified] Sixteen Hera ASan/UBSan shards passed 32,768 push/pop operations each:
FIFO reference comparison, full/empty bursts, counters crossing UINT32_MAX,
output/queue guards, silent underruns and Q15 edge cases. This is sequential
interrupt-order modeling, not actual preemption or hardware timing proof. The
queue is not yet wired into a firmware entry point. Sixteen pi32v2 queue-wrapper compilation shards also passed with no undefined
symbols. Full adapter integration and hardware timing remain necessary.

[verified] Both semantic MCPs located fm1_app_render on the primary checkout.
Rarefaction reports fallback flags without a root compilation database and a
truncated named scan; its empty caller list is not evidence of no callers.
The tools remain on the primary checkout, not this installable worktree, to
avoid disturbing another session's shared project selection. Source inspection
and actual Hera pi32v2 builds are authoritative for the changed worktree.

[verified] Added firmware/native/app.ld, a GPL-3.0-only adaptation of the
pinned Dinghy/Felucca map. Globals and .pool now share contiguous RAM
0x01C08000..0x01C74000 (442,368 bytes); XIP, RAM code, reserved debug space,
stack guards/stacks, noinit and boot mailbox addresses are unchanged. Pool
starts on a 16-byte boundary, with explicit stack/global/RAM-code/mailbox
assertions. Startup already clears .bss and .pool by their linker symbols.

[verified] The same sixteen full-HAL pi32v2 link variants completed without
container failures/OOM. Flash outcomes and sizes are unchanged. The eleven-engine
measurement links with .bss end/.pool start 0x01C0BAC0 and .pool end 0x01C49150,
leaving 175,792 bytes before guard0: 83,264 more than the previous map. No engine
arenas or queue storage are included in that capacity figure. This measurement
still uses the earlier unsafe sizing harness and must never be flashed.

[verified] Sixteen separate boundary cases passed on Hera using both GNU host
ELF tools and the actual pi32v2 tools: eight global sizes (8..64 KiB), each with
an exactly full pool and a pool exceeding the stack guard by 16 bytes. Exact
fills linked with expected symbols; every overflow failed with the guard
assertion. Initial harness attempts lacked pytest, then pointed at the wrong
venv; using the existing external-arena campaign venv fixed execution. These
checks establish allocation bounds, not physical memory or startup acceptance.
Private receipts: ram-cost.log, ram-cost-15.map, ram-boundary-combined.log and
Hera out/ram-{cost,boundary,boundary-target}-verification.json under the existing
external-arena campaign.

[verified] GitHub Actions run 38363622962 passed on exact browser checkpoint
2fd972950483338f15d3365c721c6a3b4a225c41. No merge, full native application,
OTA installation or web release is implied. Both semantic MCPs cannot locate
the new external-arena API in their primary-checkout indexes; the worktree
source and actual target compile are used instead.

[verified] Added the timed shared-application entry firmware/native/app_probe.c
and reproducible tools/native/build_application_probe.py. The adapter renders
only in core-0 main context, dequeues Q15 blocks in the audio ISR, bounds render
refills and MIDI polling, maps panel controls explicitly, and copies byte-swapped
16-row display strips into a dedicated DMA canvas. HAL gain remains unity while
the shared application owns the master control. Four 24-KiB sound arenas and ten
8-KiB effect arenas are provisional: larger effects cannot load. MIDI sustain,
channel filtering, MIDI output, persistence and release scheduling remain work.
No perceptual or hardware acceptance is claimed for this adapter.

[verified] The checked eleven-engine profile excludes Comet, Shapes and
MacroHeavy. It compiles current app/registry/adapter and rebuilds pinned musl,
compiler-rt and printf sources; every cached catalogue object's hash is checked
against all sixteen shard receipts. Source freshness of those cached objects is
explicitly not established, so the receipt refuses hardware-candidate status.
The owner selected maximum engine coverage before release; this profile is only
an integration probe, not a reduced release decision.

[verified] The strict artifact verifier caught an implicit ELF-header PT_LOAD
in reserved stack space after combining the RAM regions. Explicit PHDRS in the
native linker map eliminate that segment. The new explicit combined-RAM verifier
profile retains the entry/core/pointer bytes, stack guards, section types and
permissions, startup symbols, overlapping-range rejection and contiguous flash
loads; legacy validation remains the default. The ELF linked and passed the
SDK-free audit with zero failed/pending checks and no calls in .ram_text.

[verified] Final checked-app-probe-04: app 574,116 bytes, flash headroom 7,448;
.pool ends 0x01C70870, leaving 14,224 bytes before guard0. ELF SHA256
bb22e86a08ab01408965d49071e9e3c3c0bede3212ac6bfa7d549c892a029cf2;
flattened app SHA256
ce769b5c461ed7ae1b21b83e9ee7ee25ea82958edb25a65f1873f5ada8d45b7f.
Initial builder attempts exposed missing printf include/alias configuration,
then the obsolete pool verifier contract, then the implicit header segment;
all failed artifacts remain private and were not used on hardware.

[verified] Sixteen concurrent Hera contract chunks passed, each with its own
actual-pi32v2 exact-fill/overflow case and synthetic ELF fault, plus shared
entry/combined-layout checks. No container failed or was OOM-killed. Private
receipts: checked-app-probe-04.log, checked-app-artifact.json and app-contract.log
under build/native-external-arenas-16-20261012; Hera out/checked-app-probe-04 and
out/app-contract-verification.json. No device command was sent for these checks.

[verified] Catalogue receipts now bind every shard to a sorted SHA256 manifest
of source/build inputs and reject inputs changing during compilation. The
application builder requires the manifests to match its current checkout,
in addition to the object/configuration hashes and complete sixteen-shard
coverage. Hidden metadata and build outputs are excluded. The fresh campaign
compiled all 167 objects in sixteen Hera containers; all 535 source entries
match the actual worktree. Sixteen separate receipt fault cases passed in
sixteen containers (no failures or OOM), covering stale/absent manifests,
changed objects/configuration, missing/duplicate/reordered indices, wrong
shards/options and SDK inputs.

[verified] Source-matched checked-app-probe-fresh-02 passed the strict combined
layout and SDK-free audits with zero failed/pending checks and no undefined
symbols. Application bytes are unchanged: 574,116 bytes, SHA256
ce769b5c461ed7ae1b21b83e9ee7ee25ea82958edb25a65f1873f5ada8d45b7f.
ELF SHA256 is
62d0a7500653a561625fae5d42179a7a444512ae0b8b14f5da79daea893e8d02
(ELF metadata differs). Receipt source-freshness is now true; hardware-candidate,
hardware-tested and installable flags remain false. This timed probe contains ten production engines plus the test-sine fixture,
and still has provisional arenas and is not the owner-selected maximum-engine
release. Private evidence: source-bound-v2.log/report.json under the catalogue
campaign, checked-app-probe-fresh-02.log and catalogue-receipts.log under the
external-arena campaign, and the corresponding Hera verification JSON files.


### FM6 pitch constants and maximum-catalogue measurements [verified]

The wrapper computes patch operator pitches from generated constant tables,
leaving vendored msfa untouched. Fixed-frequency arithmetic preserves upstream
signed 32-bit wrap behavior for out-of-range fine bytes. Sixteen independent
Hera oracle chunks compared 245,760 settings against untouched osc_freq,
with zero mismatches. The complete FM6 pytest suite passed 159 tests in sixteen
containers using the freshly built shared-resampler renderer and oracle. The
initial test launcher failed before collection because it selected the base
Python without pytest; selecting the mounted pytest venv corrected the harness.
No failed or OOM-killed containers remained in the rerun. Generated table
freshness and git diff whitespace checks pass.

Fresh native compilation passed all sixteen source-bound shards (167 objects).
Sixteen complete application builds repeated the production-engine omission
profiles. The eleven-production-engine profile excluding test-sine, Comet and
Shapes still overflows the preserved app region by 19,080 bytes, down from
23,224: a 4,144-byte saving. The ten-engine profile additionally excluding
Macro Heavy produces a 558,588-byte app with 22,976 bytes of flash headroom.
Its SDK-free and strict combined-layout audits have zero failed/pending checks;
app SHA256 b60ec45cd927e3d951fffffbc0f5eeda507cd0abf7b53c1abc1b3002838d39ed;
ELF SHA256 5cb5c49f0fef8a80d464c284fb3daac48551ceccdba19b90f26d5a7bb93378f4.
These are sizing results, not a selected release or hardware admission.

Target LLVM size-function inspection completed for all forty catalogue entries
in sixteen containers. Direct constants include Macro 19,872 bytes, Shapes
206,904 and Macro Heavy 71,392. Host structure sizes must not be substituted
for pi32v2 sizes. Conditional sizes still require their target configuration
and layout calculations; this inspection does not establish RAM admission.
The provisional four 24-KiB sound and ten 8-KiB effect arenas cannot admit all
included engines/effects. A general host make-all attempt with shared-resampler
configuration also failed in fm1-shapes-hostile because that standalone target
omits shared tables; targeted renderer/oracle builds and FM6 tests passed.

Private evidence lives under build/native-external-arenas-16-20261012:
pitch-verification.log, pitch-regression-verification.json,
pitch-release-count.log and target-size-functions.json; corresponding Hera
out receipts and catalogue out-pitch-v1 bind builds to their input sources.
No device commands or flash writes were performed for these measurements.
Maximum-engine release work remains active: flash/RAM fit, full native app,
MIDI, persistence, realtime and physical acceptance, OTA/web installation and
release recovery verification remain unfinished.

### Lossless HAL recovery-font packing [verified]

The application builder generates a private adaptation of the pinned small
HAL font and gfx decoder. It validates that every four-bit alpha sample is
0 or 15, that all glyphs remain 12x16, and that offsets/metrics match the
pinned input. Binary pixels pack into one bit without changing the vendored
sources; the large antialiased face retains its original decoder. Crash,
UBOOT and recovery text stay present. Sixteen Hera C-renderer comparison
chunks passed, exercising every byte character with both faces, eight RGB565
colours and three clipping positions. A separate hostile-alpha/changed-decoder
rejection test passed. No test container failed or was OOM-killed.

Sixteen full target builds completed with either an audited fit or the expected
flash overflow, no OOM. The eleven-production profile (omit test-sine, Comet,
Shapes) now overflows by 12,256 bytes: 6,824 fewer than the preceding pitch-only
build. Three ten-engine profiles fit, including the newly fitting profile
that omits Sophie while retaining Macro Heavy and FM6. That app is 578,484
bytes (3,080 flash headroom), app SHA256
0e7416c1fcd04dac01ce1686699365466812d7b9663b69f0a5b1bd63c491add6;
ELF SHA256 4973086696a350f16eaa3d4aed4a430cd276e55c56c893bf897e839a07c78609.
Strict combined-layout and SDK-free audits pass with zero failed/pending
checks. It remains a private sizing/timed probe, not hardware-admitted or
installable. Owner maximum-engine acceptance remains unchanged.
Private evidence: compact-font.log, compact-font-count.log and Hera out
compact-font-verification.json / compact-font-count-verification.json.

### Lossless wavetable storage evaluation, 2026-10-13 [verified]

`tools/native/evaluate_wavetables.py` evaluates sixteen raw-DEFLATE storage
profiles on Hera: block lengths 512, 1,024, 4,096 and whole-table, with/without
modular sample deltas, levels 1/9. Only the retained Plaits integrated waves
(50,688 bytes) and Braids waves (33,024 bytes) count toward savings; excluded
Comet assets do not. Each profile invokes pinned unmodified C tinf to decode
every compressed block, checks exact bytes, verifies output guards and rejects
insufficient output capacity and empty input. All sixteen containers passed,
zero failures or OOM. Pins and source/table hashes are recorded in each receipt.

The isolated pi32v2 `-Oz` decoder object, after section garbage collection,
is 1,441 bytes of text/read-only data and has no undefined dependencies. This
is not the incremental cost in an LTO-linked full app. At level 9 with deltas,
512-byte blocks save 18,762 bytes including four-byte block indices, or 17,321
after that isolated decoder. Whole-table blocks save 27,024 bytes including
indices, or 25,583 after decoder. Adapter/delta reconstruction code and RAM
are not included. No full application fit, realtime timing, hardware admission
or installation is claimed.

Established-library comparison [reported, source inspected]:
- [tinf](https://github.com/jibsen/tinf), revision
  57ffa1f1d5e3dde19011b2127bd26d01689b694b, zlib licence: bounded in-memory
  DEFLATE decoder with no allocation, two Huffman trees held on stack.
  Upstream warns of more than 1 KiB stack; native worst-call-chain stack
  consumption still needs measurement. Selected for this sizing evaluation,
  with current bounds checks retained. No decoder is integrated or vendored.
- [heatshrink](https://github.com/atomicobject/heatshrink), revision
  7d419e1fa4830d0b919b9b6a91fe2fb786cf3280, ISC: static streaming LZSS decoder
  is an alternative when bounded streaming/caches are required. Its compression
  and actual target cost have not been measured here.
- [uzlib](https://github.com/pfalcon/uzlib): streaming tinf derivative;
  not selected because whole/block buffers already permit the measured tinf
  API. This decision is provisional until RAM and access policy are resolved.

The original engines retain direct table pointers, including stored Plaits
wave maps and constant chord pointers. Decompressing entire tables preserves
that access pattern but requires 83,712 bytes of RAM. A block cache requires
explicit pointer-lifetime and bounded-render-time changes; compressed bytes
cannot be substituted behind the existing pointers. Resolve shared instance
allocation and this table access policy before native integration. Firmware
goal remains active at maximum engine count. No hardware commands occurred.
Private receipts: build/native-external-arenas-16-20261012/
wavetable-summary.json and wavetable-verification.json, plus Hera
out/wavetable-eval-00..15/{report.json,decoder-sections.txt}.

## Shared instance pool checkpoint

[verified] Imported unmodified BSD-3-Clause TLSF at
`deff9ab509341f264addbd3c8ada533678591905`, with source hashes and licence.
The main-loop adapter supplies stable 16-byte-aligned instances and records
live requested bytes. Sixteen Hera sanitizer containers passed 131,072
allocation/replacement attempts, including retained-byte checks, allocator
consistency, exhaustion, wrong-pool refusal and final coalescing. These are
host checks, not firmware or physical acceptance.

[verified] Isolated pi32v2 compile/link retains 1,424 bytes of code and
requires memcpy from the native runtime. Control metadata consumes 3,188
bytes inside the supplied pool. The shared application does not yet use this
allocator. Next: transactional application storage callbacks, native pool
integration, compressed table access and full application sizing. Maximum
engine count remains the release target. No hardware commands occurred.

## Managed shared application storage

[verified] Added optional main-loop storage callbacks to external-arena
builds. Registering requires every unit empty and unbound; manual binding
is refused while managed. Larger replacements are allocated and created
before releasing the current engine or its notes. Exhaustion and host refusal
preserve the live instance. Clearing an optional sound or effect frees its
arena. A sufficient existing arena keeps the established in-place rollback
behavior; reserve-before-free temporarily requires both instances to fit.

[verified] All 16 Hera application shards passed in ordinary builds and
ASan/UBSan builds. Checks include retained-instance audio after exhaustion,
host-rate refusal, replacement ownership, cleared-slot frees and unchanged
embedded/manual-arena behavior. The test's first run caught a C99 aligned_alloc
compatibility mistake; corrected to POSIX aligned allocation before rerunning.

[verified] Timed native probe now uses a 192,000-byte TLSF pool rather than
180,224 bytes of fixed arenas. Recompiled all 167 catalogue objects across
16 source-bound chunks, then linked 16 profiles. All completed without OOM;
three ten-engine profiles fit, with empty undefined-symbol lists and zero
failed/pending SDK-free audit checks. Eleven-engine profile (excluding
Comet, Shapes and test-sine) overflows preserved flash by 13,392 bytes,
1,136 more than the prior fixed-arena build. Fits are sizing evidence only: no
hardware candidate or installable release was admitted. All thirteen engines
remain the optimization target; these exclusions are measurements, not a
release decision. Receipts: private app-storage{-asan,}-verification.json,
pool-release-count-verification.json and Hera out-pool-v1/verification.json.

Semantic navigation confirmed existing selection callers in the primary
checkout, but both MCPs still select that checkout, not this feature worktree.
Changed source was inspected directly; primary results do not verify these
changes or the pi32v2 ABI. No hardware commands occurred.

### Startup-decoded wave tables, 2026-10-13 [verified]

Added an optional compressed-table path to the private timed application builder,
using pinned unmodified tinf. Mutable defining declarations live in generated
private resource headers; consumers retain upstream const views and addresses.
The decoder completes before application/engine initialization, reconstructs
modular deltas and checks the full table checksum. Tables occupy NOLOAD RAM;
the shared instance pool shrinks by exactly their raw storage size. No render
callback decompresses data. Host checks use actual generated resource symbols
and the firmware decoder: all 16 Hera ASan/UBSan shards passed, including three
complete reconstructions per shard, every truncated packed-input length, output
guards, checksum mismatch, short destination and invalid sample width.

The first assembly-backed definition hit the old target LLVM verifier; compiling
entire resource units outside LTO linked but retained excessive resources. The
mutable-definition adaptation restores LTO. The eleven-engine profile excludes
Shapes, so Braids waves are already discarded: adding their compressed form
back was a mistake in whole-image accounting. Profile-aware preparation now
retains only Plaits for this profile (50,688 bytes of fixed RAM), leaving
141,312 bytes of instance storage. Evaluation totals for both wave assets were
isolated storage results, not proof both survived every final engine profile.

The final 16 target attempts had no OOM. Twelve-engine profiles still overflow
flash; the eleven-engine profile links within the protected region but FAILS
the key/eFuse audit (0x13700 byte-pattern hit in fm1_seq_view_draw). Several
ten-engine profiles fail similarly; only shard 15 passes all existing gates.
This is not an audited eleven-engine artifact or hardware admission. Vendor
disassembly of the preceding shard-13 hit shows 80 ff 00 37 01 00 is a six-byte
relative call to __floatundisf, not an eFuse address operand. The scanner needs
a separately tested instruction-aware distinction, without exempting real
eFuse loads/data. No audit gate was relaxed. Startup stack/time, engine render
parity on device and maximum catalogue acceptance remain outstanding.

Private receipts: native-waves-v4-verification.json and
compressed-release-count-v4-verification.json under the native-external-arenas
build directory and corresponding Hera out directory. Failed/earlier v1-v3
attempts remain recorded separately. No hardware command or flash write occurred.

### Instruction-backed artifact audit, 2026-10-13 [verified]

Vendor disassembly confirms the 0x13700 match is the signed displacement of
a six-byte pi32v2 direct call. The optional audit path now accepts only linked
pi32v2 executables, exact instruction bytes inside a sized function, and a
resolved function target with matching displacement/address arithmetic. This
distinction applies only to eFuse address-pattern hits; real literals, malformed
instructions, unresolved targets, other architectures and flat-only images
remain rejected. The artifact gate independently maps each proof through its
validated load layout, compares all six flattened instruction bytes, retains
full disassembly and records its SHA256. Neither audit stage is skipped.

All 16 Hera unit shards passed, including existing key/eFuse guards, malformed
call evidence, architecture/type rejection and XIP/RAM-text proof mapping.
The 16 fresh target attempts have no OOM. Eleven production engines (excluding
Comet Kit and Shapes, plus excluded test-sine fixture) now pass SDK-free and
strict artifact/layout audits with zero pending checks: app 578,340 bytes,
3,224 bytes below the 581,564-byte protected app limit. Private app SHA256
2aa75694bbcf099459f07d5497542acc1910074fd4679bf6990eb6b2c1d25bba; ELF SHA256
518d618bb567028882af8e766cebcef053831cb32c0c5d4f8ba3ef38c47f4ae6.

This is still a timed private probe, not installable or hardware admitted.
Twelve-engine profiles overflow flash by 69,064 to 207,068 bytes. The ten-engine
profile also excluding Macro Heavy independently fails the unchanged stub
address scan (0x0200012E in seconds); the aggregate target launcher correctly
exits nonzero for this unexpected gate failure. Other two ten-engine profiles
pass. Do not present all 16 target profiles as passing. Owner requires maximizing
engine count before release; eleven is a sizing milestone, not accepted scope.

Private evidence: artifact-call-proofs-v3-verification.json,
compressed-release-count-v7-verification.json, per-profile logs and
compressed-release-count-v7-12/artifact/{artifact.json,disassembly.txt,app.bin}
under Hera native-external-arenas-16-20261012/out and local ignored build mirror.
Semantic MCP remains rooted at the primary checkout, so worktree edits were
inspected directly rather than claiming index validation of these changes.
No device commands occurred. Next: sample/table storage measurement, RAM and
startup/realtime verification, then fresh hardware admission and acceptance.

### Comet sample storage measurement, 2026-10-13 [verified]

Sixteen Hera containers measured lossless raw DEFLATE of Comet's three existing
mu-law sample arrays (110,549 bytes total), varying block size, modular byte
prediction and compression level. All C decoder roundtrip, exact capacity and
output guard checks passed; no container reported OOM. The best measured profile
(one block per array, byte prediction, level 9) saves 8,976 bytes after its
1,441-byte isolated pi32v2 decoder. Per-array packed payloads are 18,142, 41,527
and 40,439 bytes, with eight index bytes each. Source sample-header SHA256:
3e3d1c1661d605cf8a6b85db7601f1a2159c81d72925251d2deaf4e23dee9f9e.

This cannot close the 135,824-byte flash overflow of the twelve-engine profile
that retains Comet and omits Shapes. It was not integrated: added decoder RAM
and startup work require justification beyond this small saving. Evidence is
comet-storage-verification.json and comet-storage-eval-00..15 on Hera under
native-external-arenas-16-20261012/out. This is storage evidence, not engine
render parity or device acceptance. No hardware commands occurred.

### Sound-engine / effect flash floor, 2026-10-13 [verified]

Sixteen private Hera links crossed four sound catalogues (all thirteen; omit
Comet; omit Shapes; omit both) with four audio-effect registries (all 26 including
fixtures; none; Plate/Echo/Filter/Crush/Limit; nineteen after seven omissions).
No OOM occurred. The all-thirteen profile exceeds the protected app limit by
208,116 bytes with all effects and by 126,260 bytes with none. The twelve-engine
profile omitting Comet fits with no audio effects; five representative effects
still overflow. The twelve-engine profile omitting Shapes exceeds by 53,968
bytes even with no audio effects. The existing eleven-engine combinations fit.

These measurements do not authorize feature removal or a partition change.
They show that removing effects alone cannot fit thirteen sound engines. Shapes'
measured 206,904-byte instance also exceeds the compressed profile's 108,288-byte
instance arena; a successful link does not establish allocation or playability.
Evidence: effect-floor-verification.json and effect-floor-00..15 on Hera and
local ignored build mirror. Private launcher extends the builder's exclusion
choices for this experiment; the tracked builder and release scope are unchanged.
No device commands occurred.

### Linked-code storage bound, 2026-10-13 [verified]

A private oversized link was used only to measure the all-thirteen-engine
image. Its linker script enlarged XIP; the unchanged artifact gate rejected
its `.text` bounds. It is not an admitted image and was never sent to hardware.
The sized, non-overlapping linked function spans total 422,828 bytes.
Sixteen storage experiments compressed those bytes in independent blocks,
then verified exact reconstruction with the pinned C decoder. All sixteen
v2 containers exited zero without OOM. The first campaign failed in the
measurement harness (incorrect Elf API field/method names); its failed receipt
is retained separately.

The best v2 variant, 65,536-byte blocks without byte-delta prediction, saves
107,802 bytes after charging the measured 1,441-byte decoder. This is below
the 208,116-byte all-engine/all-effect flash deficit. Function concatenation
is a storage bound, not an executable overlay: relocation, call routing,
execution RAM, real-time behavior and recovery are not demonstrated. No code
compression or overlay was added to the firmware. Evidence: Hera
out/code-storage-v2-verification.json, code-storage-v2-00..15/report.json,
oversize-full-measure.log and private oversize-full-measure artifacts.

### Current target instance extraction, 2026-10-13 [verified]

All sixteen containers converted the current out-pool-v1 engine bitcode to
LLVM IR without OOM. Forty catalogue size entry points were extracted.
Constant returns include Shapes 206,904 bytes, Macro Heavy 71,392, Macro
19,872, Six-Op FM 11,224, Comet 10,240, Crater 5,984, Drums 7,648 and Acid
1,248. These are target compiler size results, not allocation or playback
acceptance. Rate-dependent and wrapper size functions remain expressions;
no numeric result was inferred for them. Evidence: Hera
out/target-instance-pool-v2/{verification.json,size-functions.json} and the
ignored local size-functions mirror.

### Shared resampler host validation, 2026-10-13 [verified]

The full host build with FM1_SHARED_RESAMPLER=1 initially exposed missing
shared-table link dependencies in Shapes' hostile tool and the Plaits reference
tool. Both explicit link lists now include resampler_tables.o when enabled.
The corrected full host build passes, followed by 456 existing test cases in
sixteen Hera containers, all exit zero without OOM. Coverage is Shapes hostile
scripts and edge sweeps, resampler contracts, and Plaits upstream comparisons.
This is host behavior evidence, not target deadline or device audio acceptance.
Evidence: shared-resampler-host-build-v1.json retains the failed first build;
shared-resampler-host-build-v2.json and shared-resampler-host-v2-verification.json
retain the corrected build and sixteen test results under Hera out/.

The semantic-tool readiness refresh still selects the primary checkout rather
than this worktree. Shared project selection was left untouched; Makefile
inspection/editing used files directly. No device operation occurred.

### Native USB-MIDI channel admission, 2026-10-13 [verified host]

The timed shared-app probe now honors settings.midi_in_channel (omni or
1..16), rejects malformed data bytes and unsupported status families before
calling shared note functions, and releases current notes when the input
filter changes so previously accepted releases cannot become stranded behind
the new filter. This deliberately resets currently sounding notes, including
panel/sequencer notes, on a filter change. It retains the 32-message per-poll
budget and existing pitch/panic behavior. Sustain and jack UART remain work;
this change does not claim full MIDI acceptance.

Sixteen Hera containers compiled and exercised the actual incoming_midi body
with stub packet source and shared-app sinks. All passed without OOM: selected
channels and omni, velocity-zero and normal releases, bend endpoints, panic,
invalid statuses/data, filter transition, and a 64-message stream consumed in
two bounded polls. Evidence: out/native-midi-input-v1-verification.json.
The first native link attempt rejected stale catalogue inputs after the host
Makefile repair; this failure is retained in midi-input-target-v1 receipts.
All 167 catalogue objects then regenerated in sixteen containers without OOM.
The eleven-engine measurement profile linked and passed combined layout and
SDK-free ELF/flattened-image checks (zero failures/pending). It measures
578,440 bytes, 100 bytes larger than the prior measurement, leaving 3,124
bytes under the protected limit. App SHA256:
9591667cc948fd336382ae9220c04079ef54aa604c5f8b28908481456cde9858.
Evidence: catalogue out-pool-v2/verification.json and
out/midi-input-target-v2-12/artifact/artifact.json. Hardware admitted/tested
and installable flags remain false; this is not the accepted release scope.
Semantic navigation of note_off agreed with the worktree function body but
selected the primary checkout; the empty Rarefaction caller list missed the
known native caller and was not treated as proof of no callers.

### Native LTO size matrix, 2026-10-13 [verified measurement]

Sixteen private Hera links compared the same current, manifest-checked
all-thirteen-engine/all-effect bitcode and generated runtime objects. The
installed LLVMgold plugin's `-help-hidden` output confirmed the tested options
exist. The sizing-only linker script enlarged XIP; the unchanged artifact
validator rejected the preparation image. No production linker limit changed,
no candidate was admitted to hardware, and no new compiler setting was adopted.

The current baseline is 789,780 bytes, 208,216 above the protected 581,564-byte
app region (100 bytes above the pre-MIDI-filter baseline). None of the fifteen
alternative combinations improved it. Inline thresholds 0, 10, 25, 50 and 75
produced 789,796, 790,612, 799,060, 818,828 and 840,460 bytes. Negative thresholds
with inline-hint threshold zero produced 789,972. Tail-merge thresholds 20 and
100 produced 789,988 and 789,796; inline-zero plus tail-merge-100 produced
789,812. Explicit target tailcall, type and parallel-pack settings reproduced
the baseline hash; schedule type 1 reproduced it and type 3 grew to 790,420.
These measurements do not demonstrate runtime correctness of alternative flags.

All sixteen corrected v2 links exited zero without OOM. V1 retained a harness
failure: options inserted before the plugin declaration were rejected as bad
plugin options; only its baseline linked. V2 corrected ordering and reused the
same prepared inputs. Evidence under Hera native-external-arenas-16-20261012/out:
lto-size-v1-command.json, lto-size-v1-full, lto-size-v1-verification.json,
lto-size-v2-verification.json, lto-size-v2-00..15/{report.json,link.log,measure.map}.
The ignored local aggregate mirror and launchers preserve the same experiment.

Maximum engine count remains the owner's release requirement. Eleven-engine
fit is not an accepted release, and install-time engine packs have not been
accepted. Full catalogue flash/RAM, target deadlines, complete native MIDI,
persistence and real OTA/web/recovery acceptance remain open.
