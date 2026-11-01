# Selected Trio aggregate layout experiment, source checkpoint

2026-11-01. This private, fixed-profile builder composes the retained
selected interactive owner and offline PROJECT stage with the existing
unqualified return candidate. It measures a possible target **static layout**;
it does not make target startup, scanner/audio/SPI callbacks, storage, live
PROJECT staging, ROM return, installation, or physical operation functional.

Source base: `2714de42564983433e9aa3b86ee03ff03671d550` (target source equal
to `42604fb03dcece54c54b9b0151467ededa79ee0f`). Private planning
record: `scratch/devkit-20261023/audit-20261101/selected-aggregate-layout-plan/PLAN.md`
under the devkit-performance worktree. This checkpoint owns only the new
wrapper, root TU, focused test, this note, and narrow edits to
`tools/native/build_diagnostic.py`.

## Contract

- New wrapper: `tools/native/build_selected_trio_aggregate_layout.py`. No
  arbitrary profile or project input. Existing default FM6, selected offline,
  and selected return plans, output names and functional fields retain their
  values. Their source-manifest hash legitimately changes when the common
  builder source changes; no old receipt is represented as byte-identical.
- Uses the **same** `selected_return_candidate.ld`, stock-sized XIP/RAM,
  mailbox NOLOAD, stack guard assertions, original `audit_link`, strict
  597-byte selected blob preparation, source/object/toolchain/header binding,
  and immutable all-zero qualification. No linker-script copy or exception.
- All aggregate TUs receive exactly-one selected interactive, offline and
  PROJECT-stage proof flags plus pi32v2 CPU0 publication. The reader/PROJECT
  arena is one 65,536-byte `reader_space`; prior selected profiles still
  require 16,384 bytes. The 16-KiB sound arena, actual app/frame, owner
  platform, 16 input slots and two 64-frame stereo PCM slots are each real
  target globals and counted once.
- The vendor linker must advertise `-u` or `--undefined` in `--help` before
  expensive compilation starts. That option roots the externally visible
  typed constant table in `selected_aggregate_layout_roots.c`; its
  relocations retain the actual stage, owner/platform paths and globals under
  ordinary `--gc-sections`. Post-link `sym()` requires every named function
  and global, so a dead-stripped fit is a failure. If the vendor linker does
  not advertise the option, the experiment refuses; this checkpoint does not
  add a linker-script copy or silently remove GC.

## Verification at this checkpoint

Focused host-only source/plan tests:

```sh
/Users/likwid/Developer/mvave-fm1-firmware/.venv/bin/python -m pytest -q \
  tests/test_native_selected_aggregate_layout.py \
  tests/test_native_selected_trio_diagnostic.py \
  -k 'named_plan or link_root or exact_aggregate_flags or fixed_build_plans'
```

Four tests passed. The root TU was compiled only for **host relocation and
macro-refusal checks** with `LUNAR_DIAGNOSTIC_PUBLICATION_INJECTED=1`;
target publication and linker support were not inferred from that test.
`python3` without the project venv lacked pytest. No target build, vendor
disassembly, hardware or service operation was run.

## Next gate and lifecycle

Independent source review must inspect the exact diff and actual flags/root
inventory. Then root may allocate **one** bounded pi32v2 build on Aeon using
the previously approved immutable image, pinned toolchain archive and
original libc++ headers; a fresh source checkout/stage, CPU/memory/swap
limits, labels and unique claim are required. Proposed wrapper invocation:

```sh
python3 /src/tools/native/build_selected_trio_aggregate_layout.py \
  --toolchain /opt/jieli \
  --toolchain-archive /toolchain-archive/jieli-linux-toolchains-20250805.1.tar.xz \
  --cxx-headers /cxx \
  --renderer /lane/host/fm1-render \
  --state-tool /lane/host/fm1-state \
  --out /lane/aggregate --jobs 4
```

The build must record actual `nm`/map/ELF allocated sections, strict linked
blob, original audit, root symbol and each retained function/global, source
and object hashes, app/sound/reader/owner/queue/frame/stack/guard extents,
and the exact vendor linker help decision. The 5197 baseline had 164,512
bytes to the globals guard before adding the extra 49,152-byte reader arena
and owner/queues/alignment; only the actual link can settle fit. Reserved
stack lengths are not whole-chain high-water proof. Wait for root/reviewer
artifact consumption, then remove only the unique owned reproducible build
products/checkout/container and release its claim, retaining small evidence.

Rarefaction's fixed primary root had no `build_diagnostic.py` and returned
ENOENT for exact-position orient/scope; Serena was selected on the primary
checkout and not changed during concurrent work. Exact Git source, targeted
reads and the focused host checks supplied this checkpoint's evidence.
