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
