# Stock SPL handover: static evidence and remaining diagnostic gates

2026-10-09. Bounded, read-only investigation before a visible LCD diagnostic.
No device access, flash operation, or Lunar execution occurred. `[verified]`
here means artifact/source inspection, never a runtime observation. No GPL
implementation was copied. This note does not authorize a hardware experiment.

## Inputs and reproduction

- [verified] The local stock V15 package's `top/uboot.boot` is 14,384 bytes,
  SHA-256 `730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef`,
  matching Lunar's `tools/jieli/package_guard.py` pin. The package's
  `jlfw.yaml` records the application entry as `33554720` (`0x02000120`).
- [verified] A fresh JieLi vendor `objdump -D` decode was generated on aeon
  with the installed pi32v2 toolchain, using a temporary assembly object
  containing `.section .fw,"ax",@progbits` and `.incbin` of that exact SPL.
  Every disassembly byte column was compared with the input: 14,384 bytes
  covered, zero mismatches. Offsets below are **SPL file offsets**, including
  its 16-byte header; add `0x01c02000` for RAM addresses. The header's load
  address word is `0x01c02000` and entry-offset word is `0x10`.
- [verified] The run used the existing `lunar-jieli-check:bookworm` container
  (`sha256:bcffae0f43893343df2c5ec1a0e53458682cc421f1e33ec7802a98482afd3495`),
  with the input and toolchain mounted read-only. It assembled only the
  byte wrapper, without linking SDK providers. Raw vendor binaries and the
  full disassembly remain untracked; they are not included in this commit.
- [verified] Register names were cross-checked against JieLi AC79 SDK
  [V1.2.13 source at `e30b1ee`](https://gitee.com/Jieli-Tech/AC79_AIoT_SDK/tree/e30b1ee375d1f2993fc23bf92c8b99006a6e5f9d),
  specifically `WL82.h`, `csfr.h`, `p33.h`, `cpu.h`, and `sdk_ld_sfc.c`.
  This newer SDK's declarations help identify hardware addresses; its
  initialization behavior is not evidence of what the older stock SPL does.
- [reported] AL-255's [FM-1-RE](https://github.com/AL-255/FM-1-RE) supplied
  useful prior SPL analysis. The facts below were checked against the fresh
  vendor decode, rather than relying on Ghidra's long-call decoding.

## Application call contract

| Item | Evidence and limit |
| --- | --- |
| Entry | [verified] At `0x3294`, `r1 = [r12]`; at `0x329c`, **`call r1`**. This is a metadata-selected call, not a jump or reset vector. Stock metadata selects `0x02000120`. The return continuation is `0x01c0529e`. |
| Argument | [verified] `r10 = 0x01c7fd80` at `0x2dd0`; `r0 = r10 + 136` immediately before the call, giving `0x01c7fe08`. Only this boot argument has been established; other incoming registers are not an application API. |
| Boot information | [verified] `0x31ea..0x31fc` copies six words, replaces word 0 with the address of a separately copied 32-byte header at `0x01c7fe20`, then copies that header. The total copied storage is 56 bytes. Do not read a modern SDK's longer structure directly from the six-word prefix. |
| Interrupts | [verified] `cli` appears at `0x31d2`. There is no subsequent `sti` on the ordinary XIP path to `call r1`; that path should be treated as entering with interrupts masked. This does not establish exception routing or secondary-core state. |
| Stack | [verified] SPL startup explicitly sets `ssp = 0x01c05c40` at `0x46` and `sp = 0x01c06040` at `0x4c`. Its main then saves registers and allocates a frame at `0x17ec`, so the startup `sp` value is **not** the application's incoming `sp`. No later explicit SPL `ssp` assignment was found. An application must establish its own stack and exception-stack policy. |
| Return | [verified] Code after the call changes the SFC control register and resumes the SPL path. [inferred] A bare-metal diagnostic that reuses SPL RAM must remain non-returning and must not call overwritten SPL routines. A return-compatible ABI has not been established. |

[verified] The Apache-2.0 [fm1-nes boot bridge at `870f305`](https://github.com/Keitark/fm1-nes/blob/870f3054869c77f03fc1c8a3a425dafa3dfa7b22/firmware/nes/boot/boot_compat.c)
uses the six-word prefix and zeroes the remainder of its modern SDK copy.
Lunar already carries this bridge in `firmware/third_party/fm1-nes/`.
That bridge addresses the structure-size mismatch; it does not initialize
hardware or establish a safe bare-metal RAM layout.

## Inherited hardware state: what is actually established

- **Cache / flash mapping:** [verified] The final path calls the SPL helper
  at `0x4f4`. It clears bits `0x300` in `0x01eee008` (`CACHE_CON`), clears
  several cache-related memory ranges, and restores those bits. After
  `cli`, it waits for `CACHE_CON` bit 14 and sets `0x300` again
  (`0x31d4..0x31e4`). The SDK's cache-wait macro uses the same bit.
  [verified] The path programs SFC base-address register `0x4020c` from
  metadata at `0x31ae` and writes `1` to SFCENC control `0x40300` at
  `0x31dc`. These are configured peripherals, not reset-state defaults.
  [inferred] This supports an XIP handover, but does not prove an arbitrary
  new cache/TLB policy, complete coherency, or a safe RAM alias.
- **Watchdog:** [verified] Early SPL code at `0x1830..0x1874` drives the
  P33 serial interface (`SPI_CON = 0x13e08`, `SPI_DAT = 0x13e0c`) with
  bytes `0x40`, `0x80`, `0xef`, with chip select and busy polling.
  [verified] SDK `p33.h` identifies P33 register `0x80` as `P3_WDT_CON`.
  [inferred] This is consistent with a watchdog-register write, not an
  untouched watchdog. Its exact enabled/reset mode, remaining timeout,
  and state at the application call are **not established** by this trace.
  Community approximate watchdog periods must not become a diagnostic's
  timing guarantee.
- **Clocks:** [verified] The SPL programs clock and SFC settings through
  conditional paths; the final SFC timing calculation calls the SPL clock
  helper at `0x317c`. [inferred] Constant frequencies present in the code
  cannot identify the selected path or SPI/timer clocks. Exact application
  entry clock rates remain unresolved; stock application's later 240 MHz
  setting is not evidence of the SPL handover rate.
- **TLB and secondary core:** [verified] SDK `sdk_ld_sfc.c` reserves the
  first 8 KiB of SRAM only when `CONFIG_MMU_ENABLE` is selected. This is
  an SDK link-layout choice. [inferred] Neither it nor the absence of an
  obvious literal in the SPL establishes inherited MMU/TLB state, or that
  the second core is reset, parked, or unable to touch application RAM.

## RAM ownership and the next gate

[verified] The SPL header load base plus its byte length spans
`[0x01c02000, 0x01c05830)`. The currently linked minimal diagnostic's
4,144-byte RAM reservation, `[0x01c02000, 0x01c03030)`, therefore overlaps
SPL bytes. Avoiding the SDK's optional first-8-KiB TLB reservation does not
make that range private. This is a confirmed static overlap, **not** a
confirmed runtime failure: the present diagnostic is non-returning and
makes no SPL calls, and no target execution was observed.

[inferred] Before extending it to visible LCD output, establish which SPL
code/data and inherited exception resources may be discarded, reserve
application stacks explicitly, and resolve watchdog service/control,
clock rates for display delays/SPI, cache/TLB ownership, and secondary-core
quiescence. Any unanswered item remains an explicit execution gate.

[verified] fm1-nes's permissive
[`pre_os_display.c`](https://github.com/Keitark/fm1-nes/blob/870f3054869c77f03fc1c8a3a425dafa3dfa7b22/firmware/nes/boot/pre_os_display.c)
places its display hook **after** its main has initialized RAM/cache/heap,
clocks, interrupt routing, debug and P33 latches, before OS startup. Its
successful integration pattern therefore cannot be treated as proof that
LCD code is ready to run immediately at the stock SPL call.

Validation: fresh vendor decode and complete input-byte comparison; named
SDK/source cross-checks; documentation whitespace check. No runtime,
watchdog-duration, LCD, hardware recovery, or target-ABI test is claimed.
