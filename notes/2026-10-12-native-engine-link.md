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
