# LCD runtime prerequisites

This stream starts from PR #122 (`6efeff9`) because its independently authored
non-returning startup provides separate SP/SSP reservations and bounded boot
input capture. It does not change that PR. No device traffic, panel output,
installable container or device execution has occurred.

## Fresh stock startup evidence

[verified] The guarded V15 `files/app.bin` is 581,564 bytes, SHA-256
`306e47065f35d7a7a05ada7f5dd092f6e770952054f33f0a86b75fd10ffe3203`.
The existing vendor pi32v2 toolchain on aeon decoded the complete image in a
bounded container. Comparing every disassembly byte column to the source
covered all 581,564 bytes with zero missing bytes and zero mismatches. Ignored
artifacts are `build/jieli-runtime-evidence/stock-app.{bin,S}` and
`stock-app.vendor-disasm.txt`. No vendor binary is committed.

[verified] All offsets below are raw app-body offsets. Executable addresses
are `0x02000120 + offset`. A relocatable `.incbin` wrapper has zero section
address, so absolute annotations for PC-relative calls, especially ROM calls,
must be rebased; their printed target alone is not a physical ROM address.

| Raw offset | Fresh vendor decode | Boundary |
| --- | --- | --- |
| `0x4`, `0xa` | SP = `0x01c16fd0`, SSP = `0x01c17fd0` | Stock owns both stacks. |
| `0x10` → `0xc6` | First call captures fields from incoming `r0` into `0x01c7fd50`. | Before BSS/data initialization; dereferences its first word as a header pointer. |
| `0x16..0x46` | Zero 103,872 bytes from `0x01c0a05c`; copy 41,052 bytes to `0x01c00000` from `0x02084060`. | These are stock reservations, not permission to reuse them in a new runtime. |
| `0x90..0x96` | Indirect branch to `0x02001c32` (raw `0x1b12`). | Entry into stock platform setup. |
| `0x1b14..0x1b28` | CLI, read `cnum`, increment a per-core RAM counter, CSYNC. | Stock startup is core-aware; inherited core identity has not been measured. |
| `0x1b2a..0x1b50` | Two writes through a wrapper using P33 address `0x80`, values 0 and 12; then OR-style calls with 32, 64, 16. | Operation semantics must be tied to pinned primary definitions before reuse. |
| `0x1b5e..0x1d74` | Reads clock registers and selects paths, programs clock/timer controls, calls another setup routine. | The stock app establishes its own clock contract; an inherited SPL clock cannot be inferred from the normal application's final clock. |

## Reference boundaries

[verified] Inspected reference revisions: JieLi AC79 SDK V1.2.13
`e30b1ee375d1f2993fc23bf92c8b99006a6e5f9d`, fm1-nes by Keitark
`870f3054869c77f03fc1c8a3a425dafa3dfa7b22`, and Felucca by hugelton
`b0dcd53a251d5f5392fea9478b48244d322eeb2a`.

[verified] fm1-nes's pre-OS display hook expressly runs after SDK main has
initialized clocks and interrupt routing; it establishes board power before
display initialization. Its register/sequence reconstruction refers to stock
`FM-1_010`, not this newly decoded V15 image. Its reported clock gate accepts
24–480 MHz SYS and up to 80 MHz LSB; these are reporting bounds, not electrical
limits or a clock programming recipe.

[verified] Felucca's source establishes its timer, watchdog and exception/IRQ
handling before initializing its LCD. [reported] It times a 24 MHz oscillator
under ROM/UBOOT. This is another author's measurement, not a measurement here.
Felucca is GPL-3.0-only: facts inform this note; no implementation is copied.

[verified] The pinned WL82 primary headers place PORTC at `0x50080`, IOMAP
CON1 at `0x51020`, and SPI1 at `0x11d00`. They describe SPI1 port B as PC9
clock/PC10 output/PC8 input. fm1-nes uses PC7 CS and PC8 D/C and drives PA2 low;
its source does not establish whether PA2 is panel reset, backlight or output
enable. The apparent register support does not prove that clocks, rails and
pad state are ready at stock SPL handover.

## Additional fresh runtime evidence

[verified] Stock's interrupt setup at raw `0x16a4` clears CPU `icfg` bit 8,
reads `cnum`, zeros 32 routing words at `0x01eef100` for core 0 or
`0x01eef300` for the other core, then sets CPU `icfg` bit 8. This proves a
core-dependent routing setup; it does not establish an appropriate exception
handler or second-core parking policy for Lunar. The vector table at
`0x01c7fe00` overlaps the incoming boot-input address `0x01c7fe08`, reinforcing
the need to capture boot input before any vector-table initialization.

[verified] Pinned SDK `asm/p33.h` defines `P3_WDT_CON = 0x80`. Fresh pinned
`cpu.a` IR in `/tmp/lunar-stock-spl-handover/fresh/v1213/wdt.c.ll` implements
`wdt_init` as write 0, write period, IRQ enable, then watchdog enable.
Its IRQ enable performs OR 32 and OR 64 at the watchdog register and modifies
P33 address 23 bit 6. [inferred] The V15 sequence above matches that SDK
watchdog initialization with period field 12 (`WDT_4S` in pinned `asm/wdt.h`,
not a period measured here). Matching operations is not
proof of the final watchdog state at the SPL-to-new-app handover: the fresh
app performs this setup after handover. The stock wrapper's rebased ROM
targets are `0xffc0104e` and `0xffc010b4`; their operation names still need a
primary ROM-symbol binding before a new runtime could call them.

[verified] Raw `0x23c1c` selects SPI1 port B through IOMAP CON1 bit 4.
Raw `0x23c20..0x23c3e` establishes PC7 and PC8–PC10 output directions; raw
`0x23c42..0x23c50` writes SPI1 CON `0x4021` and BAUD 4. The vendor annotation
for the CON immediate misleadingly prints `0x4020`; the decoded value is
16,417 (`0x4021`). Stock uses 32-bit register writes and polls CON bit 15
without a deadline. This sequence needs a calibrated bounded replacement,
not an assumption that BAUD 4 means a known SPI frequency under inherited
clocks. PA2's exact electrical role remains unresolved here.

[verified] The V15 setup table is 21 records of 18 bytes at raw `0x4f76c`.
Stock waits 100 ms before sleep-out (`0x11`); record 1 begins `45 78` but the
loop handles it as a 120 ms delay, not a transmitted command `0x45`. The
remaining records configure a 240-column window and rows 40–279, RGB565 word
format, orientation and panel parameters. The decoded display-fill routine
sends memory-write `0x2c` at raw `0x22222`, completes its pixel transfers,
then sends display-on `0x29` at raw `0x22270`. This is protocol evidence;
actual pixel colors and timing have not been observed here.

## Independently authored offline component

`firmware/display/panel_probe.{c,h}` emits the recovered setup and a fixed
four-band 240×240 RGB565 word pattern through caller-supplied transport and
delay callbacks. No framebuffer or allocator is needed. It calls no SDK/ROM
service and performs no MMIO, IRQ or flash operation. There is no hardware
backend or startup caller, so this is preparation for an observable diagnostic,
not an observable diagnostic or an installable application.

[verified] Sixteen focused host tests passed, including the optional direct
comparison of emitted setup bytes with the SHA-pinned private V15 table.
The complete trace has 22 command transactions, 54 setup-data bytes and
115,200 pixel bytes, with waits of 100 and 120 ms. Fault cases cover setup,
pixel and display-on commands, data at beginning/middle/end, both delays,
and missing callbacks. A transfer failure stops further traffic and invokes
transaction cleanup. Logical loops are finite; callbacks must themselves
enforce finite deadlines, including cleanup.

[verified] The existing aeon vendor toolchain compiled the component with
`-target pi32v2 -mcpu=r3 -mfprev1 -Oz -ffreestanding -fno-builtin` and strict
warnings. Object SHA-256 is
`ad63cc687b44446cadbfb9747c12768094ef7f4475746dd52daa4c18008f84e2`.
The vendor decode shows the bounded command/pixel loops and indirect callback
calls. The ELF parser reports 266 bytes of code, 312 bytes of read-only data,
no undefined symbols, and relocations only to `command`, `setup` and the band
words. The row division uses a native target instruction, not a helper call.
This is target object evidence, not a linked application audit. A fresh
SDK-free audit of the **unchanged** PR #122 handover ELF passed with zero
failures and zero pending checks; the new panel component is not linked into
that ELF. Ignored artifacts are under `build/jieli-runtime-evidence/`.

The compile command additionally uses `-fno-common -fno-unwind-tables
-ffunction-sections -fdata-sections -mllvm -pi32v2-large-program=true
-Wall -Wextra -Werror`; the vendor dump uses separate `-d -r` options.
The installed LAN toolchain is `20250324.1`, not the requested but absent
`20250805.1`; no installation was performed. The component's ordinary pytest
run does not require private vendor files; the direct table comparison requires
`LUNAR_STOCK_APP=build/jieli-runtime-evidence/stock-app.bin`.

[verified] Stock also has a later core-start routine at raw `0x5990e`. It
places stock's secondary entry `0x020001b8` at `0x01c7fff8`, manipulates
`0x10008` and core-control `0x01eee004` bits 3 and 1, then waits for a RAM
acknowledgement. This proves explicit stock secondary-core setup, not that the
secondary core is active or parked at SPL handover. A new runtime must not
release that stock entry after overwriting stock's image/RAM. The current
component has no core-control operations.

## Next gate

Do not turn a reference's running-app LCD test into a handover-ready runtime.
Trace the fresh V15 clock/watchdog/interrupt initialization, establish the
primary register operation semantics, and recover the panel setup from that
same image. A new runtime needs an explicit current-core and exception policy,
bounded timing and SPI polling, watchdog/reset behavior, and justified pad and
power handling before GPIO/SPI writes are enabled. The existing inert and
handover diagnostics remain link/audit/RAM-debugger evidence only.

Fresh backups and review of the exact candidate/write range are needed for a
future staged device experiment. Full-image and broken-app recovery remain
untested risks; this offline stream does not perform that experiment.

## Changelog

- 2026-10-09: Checkpoint full byte-matched vendor V15 decode and source-specific
  startup/LCD prerequisites; add an independently authored, host-tested and
  target-compiled callback probe while leaving hardware activation gated.
