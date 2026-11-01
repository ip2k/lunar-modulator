# SDK-free current-app diagnostic adapter plan

Personal, non-commercial. Base b831724fcf413720aaa036dac742a382cdfaa93c.
Branch feature/2026-11-01@native-app-adapter. Hardware operations forbidden.

Bounded file ownership, saved before copying:
- firmware/native/diagnostic_{app,platform}.{c,h}, diagnostic.ld,
  diagnostic_crt0.S: new fixed single-core current-main app seam, permanent aligned
  external arena, startup and base HAL integration; no old app_probe structures.
- firmware/third_party/dinghy/: selected GPL startup/vector/ISR/base HAL,
  LCD implementation (USB excluded) and source/license inventory. Exclude platform.c,
  dinghy.c, flash, OTA, recovery, settings and generated font closure.
- firmware/third_party/{musl,compiler-rt}/ and firmware/native/libc_compat/:
  pinned source-only C runtime subsets with original licences and inventories.
- tools/native/build_diagnostic.py: distinct offline builder; existing installer
  service Python helper names belong to installer_release_audit.
- tests/test_native_diagnostic.py and focused host replay fixture.

Endpoint: source-bound native link using FM1_APP_EXTERNAL_ARENAS=1 consistently,
explicit current FM6 voice cap 8/current trunc12, measured flash/RAM/app/arena bounds, no SDK
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

Checkpoint 2: current pinned pi32v2 engine/app/HAL/runtime sources compile and
link without SDK archives. First post-link run stopped on a scanner prefix that
also matched printf's buffer-only putchar_via_gadget; external putchar_/_putchar
and forbidden namespace checks remain. Builder now reuses audit_link's existing
ELF reader for sizes and unchanged SDK-free audit; no audit helper was changed.
Runtime C units pruned by allocated target map contributions: musl30/compiler-rt23.
Host PCM256-block comparison and external-arena regression pass. Final exact
receipt and stack limitations remain pending. Fixed encoder mapping uses current
panel KNOB1..KNOB4 (3..6); selectors/algorithm/buttons are inaccessible, HOME guard
rejects invalid mode before dispatch, so MATRIX's large local arrays are not a
legal control path. This is not a general app stack bound.

Target r5: link and unchanged audit_link passed (12 checks, zero failures or
pending). Actual target .text210344/.data4/.bss300240/.noinit64 bytes;
app232832, arena65536, descriptors112;142112 bytes below first stack guard.
Vendor objcopy rejected GNU-style default section selection. Export now reuses
audit_link's existing ELF reader with strict allowed-section and contiguous-load
assertions, and audits both ELF and exported application bytes. No audit weakening.
