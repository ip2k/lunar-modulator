# SDK-free current-app diagnostic

Personal, non-commercial. [verified: source and offline target build, 2026-11-01]
This distinct profile links current-main `fm1_app_init_arenas` with a selected
GPL Dinghy base HAL and source-only portable runtime. It is a fixed single-FM6
arrangement, not the all13 product. `hardware_admitted=false`,
`release_candidate=false`; no device command or output test was performed.

## Source and licence boundary

[verified: source] Base is `b831724fcf413720aaa036dac742a382cdfaa93c`.
The tested source commit is `eb131d68b9d03572389e0ba9ac4012ffdca49bca` on
`feature/2026-11-01@native-app-adapter`. The new adapter uses current engines,
app headers, module selection and generated metadata; it does not use an old
app-private structure or cached engine objects. Existing engines and simulator
sources are unchanged. The file plan was saved before importing sources in
[the lane plan](2026-11-01-native-diagnostic-plan.md).

| Dependency | Pinned provenance | Licence and selected scope |
| --- | --- | --- |
| Dinghy base HAL | d44df7db09b98ccad2f1233b8f83f5f09c04829e, through historical Lunar cccd21cc5dc82859ed8a5d84f0a7a40646d07353 | GPL-3.0-only; base input/audio/time/IRQ/LCD/vectors only |
| musl | b1efda5b91735e33635376ca11c9b497a1c66e39 | COPYRIGHT and per-source notices; 30 C units contributing allocated target sections |
| compiler-rt | LLVM 21.1.0, 3623fe661ae35c6c80ac221f14d85be76aa870f1 | Apache-2.0 WITH LLVM-exception; 23 contributing C units |
| printf | 22318ed6bd87b0d597b4a4868d5b00daf66540fd | MIT; unmodified bounded formatting source/header |
| Current FM6/app/runtime | current source manifest, 738 files | Existing MIT/Apache/per-file notices retained; selected modules dx7,arp,lfo,env,chance |

[verified: source] Each imported library has its licence, UPSTREAM.md and
SHA-256 inventory. New app glue is MIT; derived startup/linker/platform glue is
GPL-3.0-only. The combined diagnostic is GPL-3.0-only regardless of switchable
GPL engine selection. SDK-free GPL distribution is possible with the combined
licences and complete corresponding source; no JieLi SDK archive is linked.
The compiler and standard headers are build inputs, not copied into Git.

[verified: source and target map] Only `fm1_irq.h` has a local imported-HAL
change: nested faults halt rather than reset. Original notices remain. Flash,
OTA, recovery, USB, settings, reboot/UBOOT helpers and the historical platform
app are absent from this source selection. The linked image contains no NOR
mutators, SDK/key-check code, heap allocator or external printf output sink.
`putchar_via_gadget` is printf's internal bounded buffer helper, not a stubbed
output callback. No audit implementation was changed.

## App and memory contract

[verified: source] Every target translation unit receives
`FM1_APP_EXTERNAL_ARENAS=1`; the app and its permanent aligned 65536-byte sound
arena have distinct nonoverlapping linker addresses. Only unit 0 has storage.
Initialization checks the current engine's reported size before selection,
then explicitly sets the FM6 runtime voice cap to 8. The current `trunc12`
sine selection is used. The 12-slot engine storage remains the current API's
layout; the profile does not claim an 8-slot source layout.

[verified: target ELF] The stock-sized XIP linker ceiling is retained.
No retained bootguard, expanded flash layout or CPU1 backend is included.
The compact [receipt](2026-11-01-sdk-free-native-diagnostic-receipt.json)
records hashes and exact measured sections:

| Item | Bytes / address range |
| --- | --- |
| Flash load bytes | 210364 (.text 210360 + .data 4) |
| BSS | 300240 |
| Retained crash record | 64 at 0x01c7c000 |
| Current target app | 232832 at [0x01c18020,0x01c50da0) |
| Permanent sound arena | 65536 at [0x01c08020,0x01c18020) |
| Arena descriptors | 112 at [0x01c50da8,0x01c50e18) |
| Globals end to first stack guard | 142112 |
| Reserved user/supervisor stacks | 24320 / 7936 |

[verified: source and vendor disassembly] At 44118 Hz the target FM6
instance-size branch returns 16244 bytes, below the arena capacity. Host
layout differs: app 234992 and engine 16248 bytes. Neither host sizes nor
reserved stack sizes prove target maximum call depth.

[verified: source] The adapter exposes note keys and four parameter knobs
(current panel indices 3..6). It has no button, selector, algorithm, save,
text editor, sequence or engine-selection entry point. Non-HOME knob calls
fault before app dispatch. MATRIX is inaccessible through legal controls.
Target disassembly confirms the baseline MATRIX knob allocates 6472 local
bytes and its algorithm path 6204, before register saves; nested calls make
those unsafe to expose on the reserved supervisor stack. The current general
encoder frame also allocates 756 bytes, render 348. This is a focused stack
review, not a complete callgraph bound; browser stack safety proves nothing
about the target. A separately reviewed indexed-enumeration fix may remove
the MATRIX hazard, but this diagnostic keeps MATRIX disabled.

[verified: source] Timer5 scans input and ALNK0 handles the app/render work.
App calls have one owner. This is a first single-core functional baseline;
no deadline/underrun, input timing, interrupt nesting or audio-quality
acceptance is claimed. Faults are sticky and silence output; exceptions stop
audio and halt. There is no fail-open/recovery lease, watchdog ownership
proof or installer admission in this profile.

## Reproduce and verify

[verified: execution] Use the existing pinned Linux toolchain archive
SHA-256 `f686586bcfb45e0f0bb27fd2b39c7a7f313cb4f0e88a66a14da621ffa8225958`.
The isolated build ran on Aeon with the existing
`lunar-jieli-check:bookworm` image
`sha256:bcffae0f43893343df2c5ec1a0e53458682cc421f1e33ec7802a98482afd3495`,
CPU 4-7, 4 CPUs, 6 GiB memory/swap, `docker-batch.slice`, `--rm` and task labels.
No infrastructure change was made. The builder refuses existing output,
verifies inventories, copies libc++ headers to private build storage and
removes only the generated pthread selection for this single-thread profile.
It compiles all 127 objects fresh, bounds parallelism at 4, links without SDK
archives, checks symbols, emits vendor disassembly, exports only checked
contiguous XIP text/data and invokes unchanged `audit_link` on ELF and binary.

```sh
python3 tools/native/build_diagnostic.py \
  --toolchain /opt/jieli \
  --toolchain-archive /toolchain-archive/jieli-linux-toolchains-20250805.1.tar.xz \
  --cxx-headers /cxx --out /lane/target-fresh --jobs 4
```

[verified: execution] Focused host commands from the checkout:

```sh
make -s -C engines -f Makefile -f ../sim/web/mk/sim.mk \
  -f ../firmware/native/diagnostic.mk \
  BUILD="$PWD/scratch/native-diagnostic-20261101/host" SIM="$PWD/sim/web" \
  FM1_MODULES=dx7,arp,lfo,env,chance FM1_DX7_SINE=trunc12 \
  EXTRA=-DFM1_APP_EXTERNAL_ARENAS=1 \
  "$PWD/scratch/native-diagnostic-20261101/host/native-diagnostic-check"
scratch/native-diagnostic-20261101/host/native-diagnostic-check
scratch/native-diagnostic-20261101/host/native-diagnostic-check cold-fault
scratch/native-diagnostic-20261101/host/native-diagnostic-check null-output
scratch/native-diagnostic-20261101/host/native-diagnostic-check mode-fault
python -m pytest tests/test_native_diagnostic.py \
  -o cache_dir=scratch/native-diagnostic-20261101/pytest-cache \
  --basetemp=scratch/native-diagnostic-20261101/pytest-tmp
```

[verified: execution] PCM conversion matches the current app sample-for-sample
across 256 blocks, including 10-note cap stress, key edges and parameter change.
Cold fault, NULL output, invalid mode, oversized block and sticky silence
checks pass. The existing external-arena regression also passes with selected
`test-sine,test-gain,arp,lfo,env,chance` modules and the same external-arena
flag: PCM hash `e4092d01`. It checks invalid rates/pointers/alignment, pairwise
arena overlap, app/descriptor overlap, overflow rejection, guard bytes and
storage-less selection. Two focused builder inventory/manifest tests pass.
System Python lacked pytest; the existing project venv was used without
installing or changing dependencies.

[verified: execution] Final ELF SHA-256
`9cd8ffc1e430e735a7952b9bcdecc98cfd89d1be08133aef1c4324e7cc25940b`;
application SHA-256
`30d7fdfe5cce6c1c17079ad4356523757c8be3a768e1c8f4d811e450509e5d3f`.
The 738-file input manifest matches the local committed checkout. Existing
SDK-free audit_link passes all 12 checks, zero failures/pending. Its general
limits remain: the scanner is not a complete MMIO or callgraph proof.
The missing relative-call/stub-boundary helper CLI expected by the historical
installer is a separate security delta; this profile does not weaken that gate.

## Integration and lifecycle handoff

[verified: source] The installer extraction currently expects old
`tools/native/Makefile`, `firmware/native/app.ld`, `runtime_mode.h` and
historical profile constants. This lane deliberately adds a distinct
`build_diagnostic.py`/`diagnostic.ld` profile. The coordinator must select and
review this profile explicitly rather than treating the old contract as met.
All13 engines, real UI/USB/MIDI, persistence, SAVE/OTA/browser install, CPU1,
bootguard/fail-open, target stack bound, deadline and physical acceptance
remain later dependencies. No hardware or release approval is implied.

[verified: navigation] Rarefaction root remained the primary checkout;
clangd fallback lacked a compile database, and the name query hit its 200-file
cap. Serena initial instructions/current config and primary-source
`fm1_app_init_arenas` symbol lookup succeeded. The shared project was not
switched. External-worktree investigation used bounded source reads; neither
index verified pi32v2 ABI. No graph was built.

Evidence stays in the lane's ignored
`scratch/native-diagnostic-20261101/logs/`: full source/object receipt,
compiler command log, target listing/map, audit and host results. Reproducible
host/target objects, private header copies and staged sources are removed
after recording results. The unmerged source worktree remains for review;
remove it after integration under the repository lifecycle rule.
