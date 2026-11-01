# SDK-free current-app diagnostic adapter plan

Personal, non-commercial. Base b831724fcf413720aaa036dac742a382cdfaa93c.
Branch feature/2026-11-01@native-app-adapter. Hardware operations forbidden.

Bounded file ownership, saved before copying:
- firmware/native/diagnostic_{app,platform}.{c,h}, diagnostic.ld,
  diagnostic_crt0.S: new fixed single-core current-main app seam, permanent aligned
  external arena, startup and base HAL integration; no old app_probe structures.
- firmware/third_party/dinghy/: selected GPL startup/vector/ISR/base HAL,
  LCD/USB-MIDI implementation and source/license inventory. Exclude platform.c,
  dinghy.c, flash, OTA, recovery, settings and generated font closure.
- firmware/third_party/{musl,compiler-rt}/ and firmware/native/libc_compat/:
  pinned source-only C runtime subsets with original licences and inventories.
- tools/native/build_diagnostic.py: distinct offline builder; existing installer
  service Python helper names belong to installer_release_audit.
- tests/test_native_diagnostic.py and focused host replay fixture.

Endpoint: source-bound native link using FM1_APP_EXTERNAL_ARENAS=1 consistently,
FM1_DX7_VOICES=8/current trunc12, measured flash/RAM/app/arena bounds, no SDK
archives, no linked NOR mutators; hardware_admitted=false. Fixed smaller diagnostic
arrangement is not the final all13 product. No SAVE, OTA/browser transport,
persistence, CPU1 backend, deadline acceptance, device traffic or installer admission.

Validation: host current-app PCM equivalence and arena/fault cases; actual pinned
pi32v2 compile/link if available; map/symbol/source provenance and memory report.
Build objects live only in scratch/native-diagnostic-20261101 or unique Aeon lane
/home/likwid/datasets/lunar/native-adapter-20261101; remove reproducible products
after preserving reports/logs. No vendor/toolchain binaries in Git.

Navigation: Rarefaction root is the primary checkout, fallback clangd flags, no
compile DB; name query failed its 200-file cap. Serena initial instructions/config
read and find_symbol found fm1_app_init_arenas in primary source. Both remain on
shared primary; no project switch. External isolated worktree uses bounded source
inspection, not claims of semantic/ABI verification.
