# Offline stock handover layout evidence

2026-10-09. Personal MIT stream `chore/2026-10-09@handover-layout-audit`,
based on main `9cfc46dc`. No device traffic, register initialization,
package generation or driver implementation occurred.

## Check and result

`tools/jieli/handover_layout.py` accepts a linked diagnostic ELF, its flat
binary, and the locally held decoded stock `top/uboot.boot`. It recomputes
the complete SDK-free link audit and strict diagnostic report before deriving
RAM ranges from ELF sections and linker boundary symbols. It does not trust
a supplied map/report JSON. The existing inert/handover profile distinction,
stock package guards and staging rejection of SP/SSP variants are unchanged.

The SPL must match all 14,384 bytes and SHA-256
`730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef`.
Its bank header must declare one body, length 14,368, file offset 16 and
load address `0x01c02000`; CRC16/XMODEM checks independently bind the header
and body [verified against the held stock bytes]. **Loaded SPL body is
`[0x01c02000, 0x01c05820)`.** The 16-byte bank header is not loaded code;
adding the entire file length gives an incorrect end address.

The comparison rejects malformed/overlapping/duplicate linked RAM ranges
and overlap with the observed six-word boot prefix
`[0x01c7fe08, 0x01c7fe20)` or pointed 32-byte header
`[0x01c7fe20, 0x01c7fe40)`. It also checks the whole reserved span, including
alignment gaps. These two protected ranges are stock handover evidence,
**not a complete map of SPL, ROM or secondary-core RAM ownership**. The
strict current link budget already excludes these upper ranges; direct
classifier negative cases exercise the additional protection independently.

Actual linked artifacts retained from [PR #134](https://github.com/ip2k/lunar-modulator/pull/134)
at `7385bee77d70e81d0bf588e7479c016ee5a9e154` were checked, without rebuilding
or selecting replacement binaries. All use entry `0x02000120`. Each listed
RAM section overlaps the loaded SPL body [verified ELF-derived ranges]:

| Variant | Flash bytes | Reserved RAM bytes | Data / BSS / SP / SSP section bytes |
| --- | ---: | ---: | --- |
| Inert | 200 | 4,144 | 4 / 24 / 4,112 / absent |
| Handover capture | 288 | 8,352 | 4 / 116 / 4,112 / 4,112 |
| RAM-only panel protocol | 1,212 | 8,400 | 4 / 160 / 4,112 / 4,112 |

Complete artifact hashes, exact ranges and report output are in the
[layout receipt](data/2026-10-09-handover-layout-audit.json). Vendor binaries
remain ignored and are not committed.

## Meaning and remaining gates

Success means **layout evidence only**. Every section retains
`ownership="unresolved"`, `private_ram_proven=false`, and device execution
is unverified. Loaded-SPL overlap establishes a constraint: any future
execution must remain non-returning and must not call overwritten SPL code
[inferred from the verified overlap]. It does not prove the selected low
RAM is safe, even with private SP/SSP reservations and CLI.

Core identity/secondary-core quiescence, exception vector routing, MMU/TLB
ownership, final watchdog state, and inherited clock/power/XIP/cache/SFC
behavior remain runtime gates. The early watchdog disable transaction
does not settle final state across the unresolved indirect callback.
No guessed vector, cache, watchdog or core-control register writes were added.
The ordinary SPL call path and protected boot dimensions come from the
[stock SPL handover research](https://github.com/ip2k/lunar-modulator/pull/107),
checked with JieLi vendor disassembly, and the credited Apache-2.0 fm1-nes
bridge; no GPL implementation was copied. See also the existing
[handover preparation limits](2026-10-09-handover-preparation.md).

## Validation and recovery

Focused bounded LAN checks: **89 passed**, covering the new audit, diagnostic
report and SDK link audit, including the optional held-stock check. Negative
cases cover foreign/truncated/extended stock, header off-by-16 mapping,
header/body CRC corruption, protected-range boundary overlap, zero/negative/
overflow/type-invalid ranges, duplicated/overlapping sections, mismatched
ELF/flat bytes, wrong profile, recomputed forbidden-access audit and CLI
refusal without success JSON. Synthetic hashes are patched only inside tests;
the production CLI offers no alternate stock pin.

LAN workspace: `/home/claude/mvave-fm1/handover-layout-audit-20261009`, cached
`python:3.12-bookworm`, read-only source/input mounts, `docker-batch.slice`,
four CPUs and 4 GiB RAM/swap ceiling. Logs: `/tmp/lunar-handover-layout-lan.log`.
Mac's project venv also passed the focused new/report checks; no target
compiler or hardware action was needed for this Python-only guard.

Rarefaction remained rooted at the original checkout and could not orient
the newer diagnostic files in this worktree. Serena activated this worktree's
Python tools project, found the report symbol and returned no tool-file
diagnostics. File inspection supplied the missing navigation. Neither LSP
result is pi32v2 ABI or device execution evidence.

Next: review and CI, then use this comparison alongside existing link and
package guards when evaluating a future candidate. Unknown ownership must
be resolved with exact platform evidence and an explicitly authorized
experiment; this receipt grants no device-write or installation approval.
