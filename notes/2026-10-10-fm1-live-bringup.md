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
The existing reader does not implement FD07. FC0C writes SFRs and runs
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
