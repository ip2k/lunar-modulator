# Exact fixed-loader NOR erase/program native review

2026-10-11. Offline read-only audit in the installable-firmware worktree on
`feature/2026-10-11@installable-firmware`, observed checkpoint
`6e024411651335617204bbb9267043896e3a9158`. Parent owns commits, immediate
push, source integration and any hardware decision. No source adapter changed,
loader ran, SG descriptor opened or hardware traffic occurred in this audit.
The installation goal remains active.

## Conclusion and boundary

For the exact fixed candidate, literal FB01 dispatch selects internal ioctl200,
which selects erase kind2 and emits SPI opcode20 plus the requested address.
FB04 with exactly256 bytes at a256-byte-aligned address selects the internal
NOR write method and emits one opcode02 page-program transfer. For the observed
JEDEC856014 and unchanged mode2/default state, these traced command paths do
not select whole-chip erase, NOR security-register programming, SoC eFuse,
status/configuration programming or another partition address. [verified:
actual vendor native listing and decoded bytes; conditional state premise]

This is narrow native evidence for a future guarded adapter. The loader has no
application partition policy and does not enforce the host's aligned allowed
ranges. FB04 does not visibly validate its CDB CRC, does not check the receive
callback return and ignores the write result. Native completion is not proof
of completed or correct NOR programming. A future adapter must require actual
bounded readback and full protected-region comparison. [verified: traced path]

## Exact inputs and tooling

| Input | SHA256 |
| --- | --- |
| Original encrypted loader,24064B | `d41da6126760c9d66660bcc0cac8d27d221806c5e369a8036921efe68dca5376` |
| Original decoded | `db8676b9cca4e2c0dfee062715cdb41528a2a8ccc827520ba8c194e4a2e0356e` |
| Fixed encrypted candidate | `fe6d1bd36c8ffe4674e4a05ee748fe87480b5867fac58230b14ff089d411012c` |
| Fixed decoded candidate | `a228c6fa2dd733802723099dab8216edbfbdfcef1dc155ffcd8ac2b96fd480af` |
| Fixed profile | `3c03e413b9df29d85e4c07d886d9bfb9b3ab2fc66845d5220f82998dd44f4afe` |
| Profile source | `9664e1329d8259362da78c047ce2d6003dfe8df2850f02703f98e8b6bf277cd8` |
| Actual fixed vendor listing | `f8aeedf382158f17627ce119b01e451ab5611b6cafed485dca385a226334776e` |
| Vendor objdump | `cffc304e1a9be5dac22984a6ad48e81ef82b17166fd8864c251cf635c9663b73` |

[verified: private file hashes; objdump provenance from independent listing review]

Original encrypted source is in the primary checkout at
`reference/jl-uboot-tool/data/loaderblobs/usb/wl82loader.bin`; original decoded
and listing are `/tmp/lunar-loader-run-app/`. Fixed encrypted/decoded/profile
are `/tmp/lunar-loader-config-final-20261011/`. Actual fixed listing is
`/tmp/lunar-loader-config-20261011/loader.patched.vendor-disasm.txt`.
`build/loader-config-native-review.md` independently generated that listing on
Hera with the pinned 20250324.1 vendor toolchain and matched all24064 listed
bytes to the candidate. This audit uses its actual instruction text, including
bundled/continued instructions, rather than Ghidra decoding.

Machine evidence `build/fixed-loader-nor-write-evidence.json` SHA256
`f107118a3614ba76d5c0981601fcf7eabc2c8b56a4ad56c4f5ed5ddf32843a51`
records every input path/hash,12 unchanged original/candidate spans and resolved
operations/dispatch tables. It contains hashes and addresses, no vendor payload.
The entire internal NOR driver `[0x01c04e1a,0x01c05438)` is unchanged, SHA256
`b9de147bac2023a4fd1eee33ae35546ddb36dd9d737cfec98af9d83a7a0923c0`.
[verified: independent bounded byte comparisons]

## Resolved driver and erase path

The sole12-byte registration table `[0x01c07c28,0x01c07c34)` selects ops table
0x01c07964. Registration 0x01c02556 binds this table to handle+8; initializer
0x01c028f4 stores the handle at context0x01c09700+8. Its actual methods are
initializer0x01c04e3c,read0x01c04e1a,ioctl0x01c0505a,write0x01c05430. Thus the
NOR methods relevant here are available in the native listing; they are not
unresolved SDK-library calls. [verified: tables/native registration]

FB01 table entry at0x01c041c0 selects0x01c04458. The handler decodes CDB2..5
as a big-endian32-bit address, then calls0x01c025b8 with(handle,200,address).
That trampoline dispatches ops+8 to ioctl0x01c0505a. Its 200..203 table at
0x01c050ba resolves to0x01c050c2,0x01c05364,0x01c05368,0x01c05394;
only200 is admitted. Target0x01c050c2 sets kind2;0x01c05396 passes the original
address to0x01c04ffa. [verified: actual parsed table and instructions]

Erase0x01c04ffa waits through status helper0x01c03a88, emits WREN06 via
0x01c03a74, lowers CS, selects byte2 from packed constant0x8120d8c6 (opcode20),
sends the address through0x01c04b7a and raises CS. That address helper emits
three address bytes when context+52 iszero. Initializer0x01c03d40 sets itzero
for capacity<=16MiB, including the observed1MiB. This path issues one addressed
erase, with no iteration over other sectors. [verified: native path]

Other driver entry points support other erase modes and dangerous magic ioctl
values; these are outside the literal200 path. The packed type0 byte isC6,
while a separate helper comparison checksC7. No claim about type0 semantics
or safety of the whole driver is made. [verified: actual native constant]

Puya's P25Q80SH documentation identifies opcode20 as a4KiB selected-sector
erase with a three-byte address. Sector selection uses address bits12 and above.
This corroborates the command meaning; the precise in-package part variant is
not independently identified by this audit. [primary manufacturer source:
[P25Q80SH datasheet §10.27](https://www.puyasemi.com/download_path/%E6%95%B0%E6%8D%AE%E6%89%8B%E5%86%8C/Flash%20%E8%8A%AF%E7%89%87/P25Q80SH_datasheet_V1.3.pdf)]

## Page programming and CRC limit

FB04 dispatch selects0x01c044be. CDB2..5 becomes the big-endian address;
CDB6..7 becomes the big-endian length. Exact256 produces one256-byte receive
into buffer0x01c099d0, through context+40. With encryption flagcontext+32zero,
0x01c04524 skips the cipher branch. Entry clearing zeros that flag; the admitted
backup inventory has noF5 encryption command. The handler calls ops+16 with
(handle,buffer,256,address), then returns1 at0x01c04b5e without the ordinary
FB01 response callback. [verified: bounded plaintext path]

Write wrapper0x01c05430 rearranges arguments and branches to0x01c04e8a.
The special status/configuration-writing branch is restricted to JEDEC0x856017;
observed0x856014 skips it at0x01c04eba. Context+64 beginszero and is only set
on that skipped branch in this trace; default page size is256. An aligned256B
request gives exactly one call to0x01c04e50. The method temporarily sets the
SPI transfer-mode wordcontext+20zero and restores it after the transfer.
[verified: JEDEC branch and page-boundary arithmetic]

Program primitive0x01c04e50 calls the busy helper,WREN06, lowersCS, sends
context+78 as opcode, emits the requested address and DMA payload, then raises
CS. Initializer0x01c03b52..3b58 places02 in byte2 ofcontext+76; subsequent
mode2 operations preserve that byte. Therefore context+78 is02 on the traced
state. DMA helper0x01c04c66 transfers the supplied length, not a whole sector.
[verified: initializer word stores and internal driver path]

Puya documents opcode02 as page programming; an aligned256-byte transfer fills
one page. Misaligned full-page transfers can wrap within a page, which is why
the host must reject them. [primary manufacturer source:
[P25Q80SH datasheet §10.31](https://www.puyasemi.com/download_path/%E6%95%B0%E6%8D%AE%E6%89%8B%E5%86%8C/Flash%20%E8%8A%AF%E7%89%87/P25Q80SH_datasheet_V1.3.pdf)]

The old scratch builder generates CDB9..10 as CRC16 with seed0,little-endian.
FB04's traced handler does not read these fields or call CRC helper0x01c02068.
In contrast, FB06 at0x01c045fa..461a explicitly reads the same fields, computes
CRC and compares before copying. Context+40 is an entry-supplied receive
callback: its implementation is outside this loader image, so transport-level
CRC validation cannot be claimed. Keep a correct host CRC field for protocol
compatibility, but describe it as host-generated rather than device-verified.
[verified: handlers and unchanged old host builder]

## Completion, guards and next dependency

The busy helper's unusual return logic is not a reliable success gate:
0x01c03ab6 starts with return0 and only reports1 for the r5==-1 edge. Program
ignores its return and returns requested length; FB04 ignores that result.
Neither primitive waits after its final CS rise. The subsequent native read
method does call busy helper when continuous-read context+80zero; matching
readback, bounded host timeout and full-image comparison remain necessary.
FC0A liveness is not a flash-completion proof. [verified: native returns/calls]

A future exact adapter must seal FB01 to aligned4096B sectors wholly in the
reviewed writable ranges, FB04 to aligned256B pages of the sealed target or
baseline, exact candidate/profile/source/provenance and live FD/sysfs binding.
It must reject all other commands and any altered geometry/JEDEC, persist the
mutation intent before submission, consume/latch ambiguity without retry,
verify erased/programmed bytes and compare protected regions. The transaction's
sealed directory commit sector0x4000 must be processed last for install and
restore. No stockSPL/OTA/cfg or partial edge-sector erasure is allowed; current
raw envelope protects `[0,0x4000)` and `[0xacf40,0x100000)` and therefore only
whole eligible sectors can be erased. [required future host guards; existing
transaction order implementation is separate source evidence]

Unresolved boundaries remain external initializer0x01e00428, entry-supplied
USB receive/send callbacks, current RAM state/provenance, concurrent kernel
clients and the precise physical NOR variant/protection/power behavior. The
traced internal NOR driver closes the former “unknown flash-driver method”
question; it does not close those other boundaries. The fixed loader's physical
matching backups prove reads, not this candidate's erase/program behavior or
full restoration. The earlier original-loader scratch proof remains a separate
experiment. [verified limits; physical results documented elsewhere]

Next: parent reviews this bounded native evidence, implements/reviews an exact
physical transaction adapter with truthful payload/zero-input FB04 completion
semantics and independent readback, then seals the concrete target/recovery
manifest. This report does not authorize activation or widen the old scratch
allowlist. Reset after any write/restore requires a separately accepted flash
state and session-provenance policy; baseline reset's no-later-commands claim
would no longer hold.

Semantic tools still select the primary checkout and reject this worktree;
no shared selection/restart changed. Actual file/native inspection is the
recorded fallback. No test was needed for this read-only audit; the separately
repaired reset source has185 passing focused Hera tests and independent review.
