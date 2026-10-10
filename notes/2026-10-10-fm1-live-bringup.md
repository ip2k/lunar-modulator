# FM-1 live bring-up continuation, 2026-10-10

Personal MIT stream `chore/2026-10-10@fm1-live-bringup`, based on main
`bdba4476570b0a77d13c76a38dfb3bcfd364277b`. The owner authorized parallel
firmware preparation and bounded read-only bring-up with the powered FM-1
still directly on Bench01. The browser candidate and shared MCP projects
remain separate. No soft key, loader upload, flash erase/program, eFuse,
new application execution, or topology change occurred in this checkpoint.

## Fresh physical state

[verified, 07:21–07:25 UTC] Bench01 is reachable as `claude` and enumerates
USB `4c4a:c755` FM-1 at direct root port `3-2`, 12 Mbps, ALSA card 2 /
`hw:2,0,0`; no process owned its raw MIDI node. A separate USB Analyzer
`1d50:615b` is also enumerated. This does not imply the FM-1 has been moved
onto the analyzer. Keep the direct connection for initial checks.

[verified] One updater identity request, exactly
`F0 00 32 45 00 00 00 40 7F F7`, returned a complete 41-byte `FM-1_092`
reply. It is byte-identical to the previously recorded owner-unit frame
`KNOWN_092`, SHA-256
`7679e7be907c6cc32b3c1f27c48cc8ce6daa865852e8021e2207cdeae223217d`.
The decoder's checksum remains **false**, as documented previously; this
is not a new checksummed identity or a general checksum exception. Only
identity was transmitted. The capture is private in the worktree's ignored
`scratch/fm1-bench-20261010/identity.syx` and Bench01
`/tmp/fm1-identity-20261010-0725.syx`. The nonbinary
[receipt](data/2026-10-10-fm1-live-inventory.json) records the exact frame.

Bench01's system Python has no `mido`; no packages or services were changed.
The reviewed `amidi` raw-MIDI request used the same exact ten bytes as the
Python tool, with three seconds of silence termination, then the existing
Python decoder read the saved reply without accessing the device. Focused
identity/probe tool tests: **19 passed**.

## Recovery evidence, freshly rehashed

[verified] On both Bench01 and this Mac, session2 `dumpA.bin`/`dumpB.bin`
and restore1 `beforeA.bin`/`beforeB.bin`/`after.bin` are each 1,048,576 bytes
with SHA-256
`96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`.
Bench01 directories are root-private; unprivileged enumeration initially
returned no files, and explicit `sudo -n` read-only hashing resolved this
without permissions changes. Private storage paths remain
`/home/claude/fm1-backups/2026-10-07-{session2,restore1}/` and the original
Mac checkout's ignored `scratch/fm1-bench-20261007/` directory. No vendor
or flash binary is tracked here.

This preserves the historical bounded sector program/restore proof in
[the bench note](2026-10-07-fm1-softkey-bench.md). It does not establish
full-image restoration or broken-application recovery. No Lunar application
has executed on this unit.

## Semantic tooling for this continuation

Rarefaction `status` reports the original checkout, on-open clangd and no
root compilation database. That checkout does not contain the newer
handover capture file; its attempted orientation failed ENOENT. A corrected
exact-position Python `query_device` orientation resolves the 27-line body,
`main` caller and `hexs` callee, consistent with source. No tests are indexed
in that result. The wrong initial line resolved a noncallable position and
is not useful coverage evidence. Python interpreter advice remains present.

Serena initial instructions/config reports ready servers at the separate
semantic-tools-config worktree (`cpp`, `typescript`, `python`). Its
`find_symbol(query_device)` body agrees with actual source. SHA-256 of the
identity tool is identical in both MCP roots and this branch
(`684342b034b1a97b0e070ff758edf9bff20714523316a968952ccf48f52c0de0`).
No shared activation/restart occurred; these results do not index this new
worktree or prove pi32v2 ABI/device behavior. New firmware code is inspected
with file tools and actual target build evidence when available.

## Offline returning leaf, exact target build

[verified, offline] Independently authored MIT assembly and linker script in
`firmware/ram-leaf/` build with the pinned JieLi Linux toolchain
`jieli-linux-toolchains-20250324.1`, `clang -target pi32v2 -mcpu=r3 -mfprev1`
and vendor `ld`/`objcopy`/`objdump`. The existing Aeon
`lunar-jieli-check:bookworm` container used `docker-batch.slice`, four CPUs,
4 GiB memory and read-only toolchain input. No hardware was accessed.
The first immediate-XOR form exceeded the assembler's immediate range;
loading the constant into `r2` and using register XOR resolved that error.

The final block is exactly 512 bytes at `0x01c02000`; its first 28 bytes
are instructions, all remaining bytes including the 32-byte mailbox at
`0x01c021e0` are zero. Plain SHA-256:
`22a6f82ad920e320e525ad634efd013f19f2c16a785f30590519dc2e0c340bd5`.
The leaf stores incoming `r0`, incoming `r0 XOR 0x1357`, then completion
bytes `LUNR`, sets `r0=0` and executes `rts`. It has no stack access,
calls, explicit IRQ changes, SDK, flash reference or MMIO. The vendor
disassembly agrees with each of those instructions. The ignored private
binary is `scratch/fm1-bench-20261010/leaf.bin`; build output on Aeon is
under `/home/claude/mvave-fm1/codex-live-bringup-20261010/out/`.

[verified, offline] Applying the existing `jl_crc_cipher` to this single
512-byte block and back recovers the original exactly. The ciphered block
SHA-256 is `003b2ca6a5444e0a6a0ede99ed207c4ac0cfc0c327f0d1be7d05d65228b9764b`,
CRC16-XMODEM `0x5d64`. This is a local codec check, **not** a demonstrated
ROM write/read round trip. System Python lacked `crcmod`; rerunning with
the existing project venv succeeded without package changes. Exact
nonbinary evidence is in [the offline receipt](data/2026-10-10-ram-leaf-offline.json).

[unverified] The actual WL82 ROM argument register, inherited register/
return context, executable RAM reservation, watchdog servicing during a
returning call, and in-place read-cipher behavior remain unresolved.
Neither the existing nonreturning loader execution nor host clangd proves
them. No new custom payload, FD07, or jump was sent. Existing recovery
allowlists remain unchanged; their focused tests passed **12/12**.

## Recovery-loader command correction and rejected alternatives

[verified] The pinned private loader has ciphered SHA-256
`d41da6126760c9d66660bcc0cac8d27d221806c5e369a8036921efe68dca5376`.
Deciphering independently per 512-byte block gives 24,064 bytes, SHA-256
`db8676b9cca4e2c0dfee062715cdb41528a2a8ccc827520ba8c194e4a2e0356e`,
matching the earlier Aeon `softkey-efuse/softkey/bin/wl82loader_plain.bin`.
Fresh vendor disassembly byte columns cover all 24,064 loader bytes and
all 14,384 stock-SPL bytes without gaps or mismatches. That is a byte
coverage check; tables/data still decode as instructions or unknown words
and must be interpreted separately. Private disassemblies are in ignored
`scratch/fm1-bench-20261010/stock-spl/`.

[verified] Loader file offset `0x21b6` (RAM `0x01c041b6`) routes FB
subcommands above 6 to offset `0x2422`, which accepts only `0x42` and
otherwise goes to rejection offset `0x2b60`. The earlier `out/ldr.dis`
agrees. **The RAM loader rejects FB08**; the old 2026-10-05 note's FB08
loader claim is corrected. ROM FB08 is a separate dispatcher and remains
known here only from reported protocol and the successful pinned-loader
entry.

[verified] FB42 assembles the CDB address at offsets `0x2428..0x2450`,
requests ioctl 203 and calls the device wrapper at offset `0x5b8`.
The ops table at `0x5964` selects ioctl at `0x305a` (RAM `0x01c0505a`).
Its 200–203 halfword jump table has raw entries
`0004,0155,0157,016d`; case 203 reaches `0x3394`, passes selector 3 and
the address to helper `0x2ffa`. The packed opcode table bytes are
`c7 d8 20 81`, so selector 3 selects `0x81`. Helper `0x1a74` sends
`0x06` write-enable, followed by chip select, `0x81`, address and release.
This is a flash erase command path, **not a function call to the CDB
address**. Puya's [P25Q80H datasheet v1.7, §10.19](https://www.puyasemi.com/download_path/%E6%95%B0%E6%8D%AE%E6%89%8B%E5%86%8C/Flash/P25Q80H_Datasheet_V1.7.pdf)
identifies `0x81` as page erase. [inferred] That part-family interpretation
fits the reported Puya JEDEC identity, but the exact installed flash
variant has not been independently identified. The SPI command sequence
is verified regardless. Do not borrow an ioctl name from a different SDK
header to override this pinned binary's behavior.

[verified] Loader FD07 at offsets `0x23de..0x2420` assembles the memory
address/length, calls the copy helper at `0x351c` and sends the result via
the device USB-send callback. The helper handles overlapping ranges as
`memmove`; no cipher operation occurs in this dispatcher branch. This
does **not** establish ROM FD07 behavior or permit arbitrary memory reads.
The existing backup reader does not implement FD07. The separately prepared
fixed readback extension below has not been used on hardware. FC0C writes SFRs and runs
the application, so it is unsuitable for the leaf. Patching the loader
would invalidate the pinned-image audit; it is not an alternate allowed
execution route.

## Available ROM and SPL evidence

[verified] Bounded searches of the current Mac reference tree and known
Aeon softkey investigation paths found no WL82 mask-ROM code capture.
`reference/jielie/chips/br25/maskrom.md` describes a different chip;
SDK `specific_rom_inc` headers cover crypto support, not these USB
handlers. `fm1-nes/rom50.h` is a game asset, not the SoC ROM. This is not
an exhaustive claim about all private storage. The previous note already
records that the ROM was not dumped and corrects misleading zero-VMA
`0xffc0xxxx` targets which actually belong to application RAM.

[verified, offline] The fresh stock-SPL callback trace narrows the
handover: its offset `0x2f74` calls the load address from the bank record
at stack offset 208, after header/body CRC checks and decompression.
This is a conditional loaded-bank entry, not a generic arbitrary call.
Which selected file supplies that bank record remains unresolved; do not
label it an application/OTA entry without checking the selector. This
does not prove the ROM leaf call context or a complete Lunar startup.

## Next bounded milestone

Continue from the reviewed linked diagnostic, panel-protocol link and
stock handover layout analysis. Current PR134/136 are not green/merged;
their source/artifact evidence is useful but does not authorize execution.
Identify an observable RAM-only proof and the exact startup/private-RAM,
clock/watchdog/vector/secondary-core/MMIO contracts needed before a
stock-preserving application experiment. Prepare and test offline first;
message the parent with the concrete image, ranges, operation sequence and
recovery plan before any proposed risky device action. No arbitrary vendor
command, blanket erase, eFuse operation or automatic soft-key retry is
permitted.

Next research step authorized by the parent is offline verification of a
narrow audited-loader FD07 read extension: prove command fields, length,
output/acknowledgment and a real WL82 mapped-code window from current
binary/SDK evidence, then prepare guarded tests and an exact proposal for
review. No device read, recovery entry or loader execution is authorized
by this preparation note.

## Fixed loader-code RAM readback proposal, not executed

[verified, offline] `tools/fm1_loader_readback.py` subclasses the existing
backup reader without changing its allowlist. It has no CLI or device-opening
entry point. The only added operation is one FD07 read, after the existing
pinned-loader hash/size, UBOOT identity, upload, jump, buffer and flash-identity
checks have all succeeded. ROM-phase FD07, arbitrary RAM, guessed ROM,
MMIO/eFuse, flash and payload-bearing requests are rejected. A failed
transport consumes the single attempt; there is no automatic retry or
re-entry. Existing commands retain their existing guards.

The exact proposed read is **64 bytes at `0x01c043de..0x01c0441d`**, part of
the already uploaded pinned loader's own code. CDB, all unused bytes FF:
`fd0701c043de0040ffffffffffffffff`. There is no output data stage; input is
64 bytes. Expected plain-byte SHA-256:
`55a58166f612936e6ab55f33a373c07718bcc2069826806f9626521c68bf94c3`.
This slice starts at the audited FD07 branch; the copy destination is the
loader buffer at `0x01c09600`, outside the source slice. A mismatch stops
without recording a verified result. Successful logging records only the
address, length and hash, and does not publish vendor bytes.

[verified, offline] The CDB starts at CBW+15. Dispatcher `r14=CBW+8`, so
FD07 reads `r14+9..12` as CDB bytes 2..5 (big-endian source address), and
`r14+13..14` as CDB bytes 6..7 (big-endian 16-bit length). At loader offsets
`0x240c..0x2412`, `r0=0x01c09600`, `r1=source`, `r2=length` are passed to
`memmove` at `0x351c`. Offsets `0x2416..0x241e` pass that buffer and length
directly to the registered USB-send callback. Unlike FD05's chunk loop,
FD07 has **no device-side length bound**. The buffer's next 256-byte boundary
is control state at `0x01c09700`; this proposal fixes length to 64, below
that boundary. It does not enable the full 16-bit length space.

[verified, offline] FD07 skips the common 16-byte command-echo response
path at `0x2b32`; it sends data once, then returns dispatcher result 1 via
`0x2b5e..0x2b64`. That return value is not a data-stage acknowledgment.
The external USB callback/CSW implementation is not present in this loader,
so a byte-level CSW trace remains unavailable. The inherited Linux SG_IO
transport instead requires status, host status, driver status, the error
bit of info and residual length all zero. A short/error transfer fails
before hash acceptance. A 64-byte result does not enter the reader's
16-byte echo heuristic. This is a static transport proposal, not proof of
successful FD07 completion on this unit.

[verified, offline] A common command helper at `0xf00` can decrypt CDB bytes
when control flag `0x01c09720` is nonzero. Loader startup zeros this flag;
the observed setter at `0x20ee` belongs to the F5 handshake, which the
existing reader rejects. The reviewed fresh-loader sequence must have no
other host commands or concurrent session traffic. No explicit cipher call
occurs in the FD07 copy/send branch, agreeing with the raw-data `mem_read`
path in the pinned kagaimiq client. This does not prove arbitrary encrypted
sessions, ROM FD07 or the caller-supplied callback's implementation.

[verified, offline] New guard and mocked SG_IO tests exercise the exact CDB,
all other opcodes, rejected phases/addresses/payloads, failed loader
validation, consumed transport failures, short/long/wrong bytes, and SG_IO
status/host/driver/info/residual faults. No device is opened by these tests.
The focused command
`.venv/bin/python -m pytest -q tests/test_uboot_read.py tests/test_uboot_restore.py tests/test_loader_readback.py`
passed **29/29** on 2026-10-10; `git diff --check` passed. The private plain
loader and complete disassembly stay in ignored scratch.

Proposed reviewed device sequence: re-verify the directly connected owner
unit and private backups; use the already exercised single soft-key entry
and exact pinned-loader path, recording fresh enumeration; issue this one
fixed FD07 read only; require successful transport and the exact hash.
On failure, stop with the actual receipt; no automatic retry, new command
or flash write. Recovery boundary remains the stock application's known
power-cycle return, not an untested full-image restore. No Lunar code is
executed. **Device execution is held for parent review of the exact diff.**

## Loader entry contract and mask-ROM mapping blocker

[verified, offline] Loader offset `0x0` saves incoming `r0..r2`; offset `0x4`
sets `r0=0x01c09600`, offset `0xc` sets a 2,000-byte zero-fill length
(`0x7d0`), clearing `[0x01c09600,0x01c09dd0)`. Offset `0x1a` restores the
incoming registers and `0x1e` enters initialization at `0x63a`. Offsets
`0x63e/0x640` preserve incoming `r1/r0` in `r8/r11`. At `0x890..0x89c`,
`[r11+0]` and `[r11+4]` become USB send/receive callback pointers at
`0x01c09724/0x01c09728`; `0x8a0..0x8ac` dereferences `[r11+8]` as the slot
where the dispatcher address `0x01c03e4a` is registered. Thus **incoming
`r0` is a service-table pointer in this demonstrated loader contract**,
not evidence that the numeric FB08 command argument is passed in `r0`.
The leaf records incoming context only. Returning-call and stack contracts
remain unproven.

[verified, bounded search] Current SDK linker files name the application's
flash region starting `0x02000120` as `rom`; that name is not a mask-ROM
map. The conditional `__JUMP_TO_MASKROM` declaration in
`apps/common/update/update.c` did not provide a definition or an absolute
USB service target in the inspected pinned SDK/library IR. Stock application
calls previously classified as `0xffc0xxxx` using zero VMA are relocated
application RAM calls. No verified WL82 mask-ROM code-only range was
established by these inspected sources. Do not read an assumed `0xffc0`
window or import a different chip's map.

[proposal, separate review required] After the fixed code read establishes
transport, a future **8-byte metadata read at `0x01c09724`** could identify
the actual USB send/receive callback addresses copied from the ROM service
table. Those are known loader-RAM pointer slots, not a guessed ROM window.
This proposal is **not enabled** in the tool or its allowlist. Observing
pointer values would still require checking which mapped, readable code
region they belong to before any subsequent sparse code capture. It would
not establish ROM FB08 return semantics by itself.
