# Instruction-only entry prerequisite

Independently authored MIT code for Lunar Modulator, open firmware for the
M-VAVE FM-1. This distinct **offline** build profile stops on both outcomes.
It is not an installation candidate, diagnostic board output, or installed
exception handler. `hardware_ready=false`.

At the ordinary stock XIP entry `0x02000120`, the code preserves incoming r0,
executes CLI, reads `cnum` into r1, and checks core ID exactly 0. Other IDs
branch to the rejected stop. It then compares r0 with literal `0x01c7fe08`
without dereferencing it. A mismatch takes the same rejected stop; a match
falls into the separate accepted stop. Both stops execute CLI and branch
back to their own CLI. Neither path calls, returns, changes SP/SSP, accesses
RAM/MMIO, writes memory, changes core1, installs a vector, or activates a
peripheral [verified: Hera vendor listing and exact linked-byte audit].

The check is based on instruction/source facts, not copied SDK startup code:
pinned JieLi AC79 SDK V1.2.13 (`e30b1ee`), `cpu.h:78-84`, defines
`current_cpu_id` with the `cnum` read. Stock app raw offset `0x1b16` has
`64 e0 00 06` (`r0 = cnum`); this own scratch-register read assembles to
`64 e0 00 16` (`r1 = cnum`) [verified: inspected source and vendor listings].
Expected r0 comes from the separately reviewed ordinary stock SPL contract,
`notes/2026-10-11-stock-spl-final-contract.md`. The accepted value does not
prove safe access to that address.

Build only on the currently authorized Hera host:

```sh
bash tools/jieli/link-diagnostic.sh claude@192.168.1.48 \
  /home/claude/mvave-fm1/sdk-v1213/toolchain/current \
  /home/claude/mvave-fm1/entry-guard-review-20261011 entry-guard
```

The output is `build/jieli-entry-guard/`: a 26-byte flat entry export,
linked ELF, vendor listing, generic SDK-free audit, and strict `report.json`.
`tools/jieli/entry_guard_audit.py` requires exactly nine pinned instruction
rows, matching ELF/flat bytes, fixed branch targets, entry/stop/end symbols,
one RX entry section/load mapping that excludes ELF headers, and no other
code or RAM allocation. The supplied generic link receipt must carry matching
ELF/app hashes and agree with an independently recomputed linked audit.
Supported ELF header metadata and section-table geometry/types are pinned to
the actual vendor artifact, including its alignment values. Any compiler or
program change fails until its bytes and vendor listing are reviewed and the
explicit contract is updated. ELF LOAD headers are not a deployment format.
Existing package/raw-model profile allowlists exclude `entry-guard`.

Unresolved activation gates are ordinary-entry privilege and CLI/cnum
semantics, secondary-core ownership/quiescence, SSP/protection and bootstrap
RAM ownership, exception dispatch and nested faults, and externally witnessed
recovery/result. No RAM fault handler, exception draft, watchdog recovery,
core1 hold bit or IRQ-vector policy is supplied. A bootstrap fault may enter
inherited dispatch; XIP failure survival is unproven. The terminal loops are
intentional endpoints and carry no external success or recovery signal.
