# First independently authored linked diagnostic

2026-10-09. Branch `feature/2026-10-09@board-diagnostic`, based on main
`3c7b6a0` (PR #100). This advances the first gate in
`notes/2026-10-08-device-bringup-plan.md`; no hardware writes were performed.

## Result

An inert SDK-free pi32v2 application now links using the pinned vendor Linux
compiler and linker on aeon [verified]. Its startup/runtime are independently
authored MIT code, with no Felucca/SLOOP implementation copied. No SDK, libc,
libm, compiler runtime, ROM or other provider is required [verified: linked
symbol table has no unresolved symbols]. The default SDK audit is preserved;
an explicit stricter SDK-free policy requires key/initcall machinery absent.

The first successful LAN build produced these exact figures [verified:
`report.json`, `diagnostic.map`, vendor `diagnostic.disasm.txt`]:

| Item | Result |
| --- | ---: |
| Entry | `0x02000120` |
| Flat application / flash load bytes | 200 B |
| Initialized data | 4 B |
| BSS | 24 B |
| Reserved stack | 4,096 B |
| Stack guard | 16 B |
| Total RAM reservation including alignment | 4,144 B |
| Private RAM budget | 16,384 B |
| Link audit failures / pending checks | 0 / 0 |

The vendor disassembly confirms `cli`, stack setup and the call to C; all
loads/stores are initialization data or this private RAM window [verified:
manual review of the three functions]. The C entry uses a 4-byte argument
slot and the memory initializer pushes 12 bytes, for a 16-byte visible call
path stack use [verified: this link's disassembly], not a device stack
measurement. The byte-for-byte flat-image verifier passes. Host tests cover
data copy/BSS clearing with boundary guards and zero-length ranges; audit
regressions cover SDK-free absence and retain the original SDK policy.

## Evidence boundaries and exact next gate

This is linked code, not a board runtime, package, sound engine, or device
execution result. Its RAM-only state currently has no observation transport.
No watchdog, clock, power, cache/MMU, exception, second-core or peripheral
contract has been implemented or verified. The incoming `r0` is only saved;
it is not claimed to be a verified stock-SPL boot-info pointer.
Inherited watchdog/reset behavior is unknown; the spin could reset rather
than persist [inferred]. There is no debugger/transport available here to
observe its RAM state on the unit. This is link evidence only; it is not yet
a useful on-device diagnostic. A visible LCD diagnostic follows justified
clock/power/peripheral initialization, not the current inert loop.

Next establish the stock SPL handover from vendor/stock disassembly and
permissive references: live memory ownership, CPU mode/stack alignment,
cache/TLB setup, interrupts/exceptions, watchdog state and secondary-core
state. Add only the minimal justified initialization and an observable
diagnostic transport. Then stage a candidate with stock SPL/OTA/cfg/layout
byte-identical and run `package_guard.py`; packaging success will not prove
bootability. A device experiment needs the owner's staged recovery policy,
an exact image/address manifest and documented rollback procedure. Existing
matching backups and the bounded 4 KiB restore do not establish full-image
restoration or broken-application recovery [reported: current bring-up plan].

Do not attach the simulator's 4.94 MB application struct to this diagnostic.
After startup is established, select one small engine and account for its
state, buffers, interrupt stack and runtime providers in the target map.

## Recovery and reproducibility

Managed worktree: `/Users/likwid/.codex/worktrees/board-diagnostic/mvave-fm1-firmware`.
LAN source/output: `/home/claude/mvave-fm1/codex-board-diagnostic-20261009/{src,out}`.
Run `bash tools/jieli/link-diagnostic.sh` with the three arguments documented
in `firmware/diagnostic/README.md`. Its container is capped at 4 GiB under
`docker-batch.slice`. Results stay ignored, source and this evidence note
are committed and pushed. Never flash the raw diagnostic as a substitute
for the remaining gates.
