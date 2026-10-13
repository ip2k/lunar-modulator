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
omission and section size privately. An exhaustive 91-pair omission campaign
is running in sixteen chunks to test whether any twelve-engine layout fits.

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
queue is not yet wired into a firmware entry point. Separate target compilation
and full adapter integration remain necessary.

[verified] Both semantic MCPs located fm1_app_render on the primary checkout.
Rarefaction reports fallback flags without a root compilation database and a
truncated named scan; its empty caller list is not evidence of no callers.
The tools remain on the primary checkout, not this installable worktree, to
avoid disturbing another session's shared project selection. Source inspection
and actual Hera pi32v2 builds are authoritative for the changed worktree.
