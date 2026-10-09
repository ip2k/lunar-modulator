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
  startup/LCD prerequisites; leave hardware writes gated on missing evidence.
