# W2: native integration feasibility

2026-10-17. **Gate A: reject a wholesale vendor SDK rebase; retain selective source reuse.** [inferred from the pinned evidence below] No supported engine-free platform seam is documented in this kit. This is a feasibility result, not a failed test link or a claim that an unsupported binary rewrite is impossible. No firmware, device, USB, MIDI, flash, power or recovery operation was performed.

## Inputs and method

[verified] This worker used an isolated Aeon worktree at implementation base `0b3f377c1175df729591c221fa39de435ff5a8ce`, native reference `1f12ad5b8d6a865268af94179a3442183a680602`, and public kit SHA-256 `2a3b2ede16ac49c867831315714ef9d8c532c70ce28ce1dcf3fc76f0a9f68f57`. The kit pin is upstream M-VAVE `b178ac43c25f010c60a878056fb5331fe693fd62`; W1 owns independent whole-tree and manifest reconciliation. This worker independently rehashed the ZIP and read selected source/archive members as data, without extracting or executing vendor programs. Paths below refer to that vendor pin unless prefixed Lunar.

[verified] `native-seams.json` records the independently reproduced archive topology and selected symbols. Reproduction uses Python stdlib `zipfile`, `hashlib` and `struct`: read `sdk/lib/libfm1_engine.a`; assert ar magic, walk 60-byte member headers using decimal bytes 48:58 and even padding; resolve `/offset` names with the `//` table; parse ELF32 little-endian section headers (`<10I`) and SHT_SYMTAB entries (`<IIIBBH`) via their linked string table. Binding 1 is global, 2 weak; section zero is undefined. The null ELF symbol is included in 116 undefined entries; 115 have names. No vendor disassembler/compiler was run.

[verified] The archive has only one compiled member, `engine_startup.S.o` (1,379,076 bytes), alongside the ar index/name table. The object contains 4,810 sections, 27,559 symbols and 182 defined global/weak symbols. Allocated initialized sections sum to 410,042 bytes and allocated NOBITS to 80,911 bytes. These are relocatable section totals, **not linked flash size or live RAM consumption**; GC, relocation, alignment and app inputs still matter.

## Supported seam: absent

[verified] `sdk/Build.ps1:343-349` compiles native APP C/assembly except `app/synth`, which supplies ABI headers. `:411-420` includes the frozen engine archive under whole-archive and then section GC. The archive has strong `fm1_engine_render`, pause/resume and MIDI/platform services; APP SysEx is weak. Public headers do not expose an engine factory, alternate render registration, platform-only startup mode or a generic timestamped MIDI receive callback. `main`/`fm1_io_start` exist inside the object as local symbols; app dependencies such as `groove_screen_init`, `groove_project_init` and `fm1_audio_start` are undefined imports. Their presence establishes dependencies, not their runtime order.

[verified] Build guards require the fixed archive, real instrument callbacks and transport/runtime symbols (`Build.ps1:72-124`), plus render/sequencer/engine SRAM callbacks (`:136-165,348-349`). Thus replacing one call at `app/board/audio.c:43` does not document disabling sealed groove initialization, allocations, MIDI consumption or UI/edit callbacks. [inferred] A second Lunar render callback beside that runtime creates unresolved ownership/resource questions. No symbol weakening, duplicate-definition suppression, archive carving or guard removal is proposed.

[inferred decision] Stop vendor rebasing at Gate A. A later vendor experiment would need a separately chosen product profile, compatible dependency permissions, a supported platform-only archive/API, timestamped MIDI ownership and a real exact compiler/map baseline. No vendor contact was sent. Keep Lunar's engine/sequencer/state semantics and SDK-free source runtime authoritative.

## Public contexts, ownership and lifetimes

[verified source contracts] These are declared interfaces, not independently measured implementation behavior. An unspecified lifetime is not assumed safe.

| Surface | Context and data contract | Lifetime / integration boundary |
| --- | --- | --- |
| `fm1_engine_render` | I2S DMA ISR only; no recursion/concurrency; exactly 128 stereo Q23 frames; invalid pointer/count returns -1 without output (`fm1_engine_control.h:5-10`) | Caller supplies 256 words. This is the sealed instrument renderer, not a platform callback registration. |
| Engine pause/resume/stop | Nestable brief edit transaction in control task (`:11-18`) | Does not document destroying/unregistering the engine or surrendering MIDI ownership. |
| USB PCM read/write, Bluetooth PCM read | ISR only, once per block, nonblocking copy; no wait/allocation/retained caller buffer (`fm1_audio_io.h:6-21`) | USB signed Q23, BT signed int16; consume only a full read. USB reset returns -2; capture may queue partial frames. Gain array must not alias PCM. Success is queue acceptance, not host delivery. |
| `fm1_midi_send` | Control task; complete raw MIDI; -2 busy/full means retry (`fm1.h:22-25`) | No receive timestamp or delivery receipt. Header does not expressly state caller-buffer retention duration. A replacement transport seam must document copying/ownership. |
| `fm1_midi_post` | Control task only; complete short messages into instrument; no SysEx/running status; overflow requests reset (`:26-30`) | Feeds sealed instrument; not receive-to-Lunar. No timestamp parameter. |
| `fm1_app_sysex` | Optional control hook; complete F0/F7; 1,024-byte limit; independent USB/BLE/UART assembly; updater handled first (`:80-86`) | Borrowed until return; copy/queue before return. No timestamp scheduling; storage writes prohibited from routing callback. No generic short-message RX hook. |
| Bluetooth/BLE control | Control task only, never ISR/tick; asynchronous statuses; one BLE connection; peripheral or central; classic audio independent (`:31-79`) | Role change disconnects. Scan list indexes valid until new scan/role; scan 15 s, up to eight devices. Must wait for ready/discovery and handle busy/lost state. No implicit connection or MIDI RX ownership for Lunar. |
| Panel/time/IRQ | Control snapshots; scan is short ISR; TIMER4/5 owned by board start (`fm1_device.h:5-20`, `app/board/device.c`) | Restore exact interrupt token, no waiting/drawing/RTOS/flash while masked. Millisecond timestamps wrap (`fm1.h:106-108`). |
| LCD | Control task; native RGB565; synchronous blit completes before return (`fm1.h:111-125`) | Submit borrows and byte-swaps RAM pixels in place until pending=0; busy leaves buffer unchanged; negative timeout stops DMA. Maximum 240×16 pixels. |
| Flash | Partition-relative, control task with interrupts enabled; never audio/timer/MIDI/SysEx callback (`fm1.h:127-153`) | Input stable, no mapped-partition alias; no auto erase/allocation; partial interrupted writes possible. Writes/erase silence audio. Existing projects/samples occupy the same reservation. |
| Flash map | Read-only mapped samples (`fm1_device.h:25-29`) | Caller owns sample/cache lifetimes and pauses engine for format changes; writes invalidate caches. Not an immutable lifetime across storage edits. |

[inferred] A usable platform seam must define init and shutdown order; task and ISR ownership; timestamp capture time/clock/wrap; complete short MIDI and SysEx RX; TX backpressure; event ordering at render offsets; buffer copying/retention; render rate/size; flash quiescence; and which services remain alive without the groove engine. Current public headers do not jointly provide that seam.

## Compiler and resource gate

[verified] Supported native tooling is Windows x64/PowerShell with exact external `clang.exe`, PI32v2 linker, `LLVMgold.dll`, nm and objcopy hashes (`README.md`, `Build.ps1:294-312`). Flags include `-target pi32v2 -mcpu=r3 -mfprev1`, LTO and vendor plugin options (`:356-380,411-420`). Entry units selectively disable LTO to avoid weak defaults winning. PowerShell Core on Aeon does not make Linux tools equivalent. This worker ran no build or Windows binaries.

[verified] Retain these constraints unchanged:

- Minimum runtime heap **49,152 bytes**, ACL TX/RX pools at least 1,024/4,096 bytes (`Build.ps1:126-135`).
- Linker ram0 **523,596 bytes**, cache RAM **28,672 bytes**, no SDRAM; retain boot-info/update reservations (`linker.ld.in:13-28`). Whole audio call chain and initialized lookup tables must satisfy SRAM placement, not just the render entry (`fm1.h:15-19`, linker `:226-245`).
- Package USER reservation **536,576 bytes**, BTIF 4,096, minimum VM 32,768, boot boundary 16,384; inequality raw app ceiling **453,921 bytes** with sector-rounded image checked again (`Package.cs:12-13,138-153`). This is a different layout from Lunar. Do not relax its guard or substitute its SPL/OTA/config for Lunar's retained stock checks.
- Public board Q23 buffers total 5,120 bytes; mixer USB/BT buffers another 1,536 (`app/board/audio.c:9-11`, `app/audio_output.c:7-8`). These exclude opaque heap, stacks, transport pools, engine state and Lunar additions.

[inferred plan if a future experiment is separately chosen] First confirm supported matching build host/tool hashes and exact inputs. Obtain a clean native baseline ELF/map and retain script reports; enumerate linked members, allocated SRAM/flash, stack/workspace, heap and live transport pools. Only then compare a single chosen Lunar profile at identical compiler, rate, modules and layout, with target disassembly and SRAM call graph. Preserve package/key/link guards. The retained E7 size in the evaluation is historical evidence, not a current-head rebuild or the size of a selectively redesigned app.

## Validation and limits

[verified] Read project instructions and pilot plan; exact Git source reads and Python archive parsing on Aeon; ZIP hash matched; Markdown/JSON checks and `git diff --check` are recorded in the worker handoff. Rarefaction/Serena status/config select the older Mac absolute checkout, not this Aeon worktree/reference. They were not retargeted over another active session; no semantic absence claim relies on their index. No build, runtime, audible, hardware timing, licence completeness or installability acceptance is claimed. Main remains MIT while the native reference is GPL: this report imports no source code, and any future vendor/native code reuse needs its proper notices and provenance.
