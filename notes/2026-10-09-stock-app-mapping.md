# Stock application placement and XIP evidence

2026-10-09. Offline investigation for Lunar Modulator, personal MIT project.
No device traffic, writes or emitted modified firmware container. This extends
[container inspection](2026-10-09-offline-container.md), not bootability proof.

## Inputs and reproducibility

- Guarded stock V15 unpacked `top/uboot.boot`: 14384 bytes, SHA-256
  `730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef`.
- Stock V15 `files/app.bin`: 581564 bytes, first 128 bytes decoded separately.
- Existing private owner backups: original checkout's ignored
  `scratch/fm1-bench-20261007/backup-session{1,2}/dump{A,B}.bin`, each 1 MiB.
- Previously acquired ignored `scratch/baudgirl-2026-09-29/fw/FM-1_092.fwsc`.
- JieLi `WL82.h` SFC register definitions and kagaimiq's MIT
  [jl-misctools unpacker](https://github.com/kagaimiq/jl-misctools/blob/master/firmware/fwunpack_newfw.py).

The existing SPL vendor decode at
`/tmp/lunar-stock-spl-handover/stock-v15-uboot.vendor-disasm.txt` was checked
against the guarded SPL: all 14384 byte columns agree [verified]. New app-prefix
decode used the existing LAN image `lunar-jieli-check:bookworm` and Linux
toolchain `jieli-linux-toolchains-20250324.1` (`clang 4.0.1`), capped at 1 GiB
inside `docker-batch.slice`. Own temporary evidence directory:
`/home/claude/mvave-fm1/codex-board-diagnostic-20261009/stock-entry-evidence`.
Wrap bytes in `.section .fw,"ax",@progbits` with `.incbin`, then run:

```sh
/toolchain/common/bin/clang -target pi32v2 -mcpu=r3 -mfprev1 -c prefix.S -o prefix.o
/toolchain/pi32v2/bin/objdump -D -mcpu=r3 -mattr=+fprev1 prefix.o
```

All 128 byte columns agree with the input, SHA-256
`5b7afe0c3b9477cb5711850f9993468065932328c79e901132841aa555968db4`
[verified]. The long instruction starting at offset `0x7E` is truncated;
no interpretation extends beyond offset `0x7C`. Local raw bytes/disassembly
and comparison reports stay ignored under
`build/jieli-diagnostic/stock-entry-evidence/`. No vendor bytes are committed.

## File offsets, bank load and disassembler caveat

The decoded SPL bank header declares count 1, body offset 16, body size
14368 and load address `0x01C02000` [verified]. Thus the loaded body is
`[0x01C02000, 0x01C05820)`, and an offset in the **complete SPL file** maps
to RAM as `0x01C02000 + file_offset - 16`. The separate 16-byte file header
must not extend the loaded-body range to `0x01C05830`.

At raw file offset `0x136A`, vendor objdump prints assignment decimal
`29382335`, which is `0x01C056BF`, while its angle-bracket annotation prints
`0x01C056BE`. The immediate bytes are `c6 ff bf 56 c0 01` [verified]. Use
the assignment/immediate value, not that annotation. The actual address maps
to file offset `0x36CF`, exactly the NUL-terminated string `app_dir_head`.
Raw instruction offsets below remain complete-file offsets, not RAM addresses.

## Static handover mapping

Each JLFS record has address at byte +4, size +8 and name +16. Stock top
`app_dir_head` has address `0x4000`; its first `app_area_head` record has
address `0x02000120`; first child `app.bin` has relative address `0x120`
[verified metadata]. Named SPL dataflow:

| SPL file offset | Verified instruction/dataflow |
| --- | --- |
| `0x17F0..0x17FA` | Save incoming ROM argument; read its word at +4; store at state `0x01C06460 + 44`. This is the base used by the later arithmetic. |
| `0x136A..0x1374` | Pass `app_dir_head` string and output at `sp+68` to top lookup `0x12A2`. Output contains cursor then the 32-byte header. |
| `0x13E4..0x13EA` | Read first app-area record to `sp+36` through helper `0x1306`; helper uses cursor plus top-header address and advances cursor 32 bytes. |
| `0x13F8..0x13FE` | `r2=[r7+44]`, `r3=[sp+76]`, `r0=r2+r3`; then `r2=[sp+40]`. These are ROM base + top directory address, and first app-area header entry respectively. |
| `0x1408..0x1410` | Store physical-directory sum at `0x01C075E8+4` and entry at `0x01C075E8+0`. |
| `0x2D72..0x2D7E` | Successful lookup returns zero; failure clears the stored physical base. |
| `0x2DBA`, `0x31AA..0x31AE` | Set SFC register base `0x40200`; write stored physical-directory sum to +12 (`BASE_ADR` in `WL82.h`). |
| `0x31BA..0x31C0` | Save virtual base `0x02000000`, physical-directory sum and chip key in boot state. |
| `0x3294..0x329C` | Load stored entry into r1; set r0 to boot state `0x01C7FE08`; `call r1`. |

The normal XIP path therefore corresponds to physical
`ROM_image_base + 0x4000 + 0x120` and virtual entry `0x02000120`
[inferred translation from verified register/dataflow and metadata]. The
header entry lacks the bit-26 RAM-loading flag checked at `0x3202`.
Actual SFC translation/register state on the device has not been observed.

The nested stock inspector now enforces
`app_area_head.address == 0x02000000 + app.bin.relative_address` and reports
image offset `0x4120`. A repaired-CRC relocation from +0x120 to +0x130 with
unchanged file bytes is rejected [verified synthetic regression]. This
guards stock classification; it does not implement changed placement rules.

## Recorded owner flash image base

All four saved 1 MiB dumps have a CRC-valid flash header at physical zero,
and matching top placements (SPL `0xA0`, config `0x38D0`, app directory
`0x4000`, key_mac `0xFF000`) [verified offline]. Of the unpacker's candidate
header offsets inside 1 MiB (`0`, `0x1000`, `0x10000`, `0x80000`), only zero
is CRC-valid. The first `0xAE000` bytes of **each dump are byte-identical**
to the entire raw flash payload carved from the FM-1_092 package at logical
offset `0x400`, SHA-256
`e054fdc557a6c2690367c0090d16c21c4d5c07d0eec3f4e796812bbbfe96fc27`
[verified]. This establishes base-zero placement in the recorded flash,
without examining or publishing key_mac/device-specific data.

The installed app header also has entry `0x02000120`, child offset `0x120`,
child size 691744 and app-area size 692415; its decoded SPL matches the stock
pin [verified offline]. It does **not** resolve FM-1_092's relocated outer
auxiliary cipher origin. Strict inspection still refuses that container.
It also does not directly observe the ROM argument or running SFC register.

## Stock entry prefix and next gate

V15 app offset zero branches to offset four. It establishes SP
`0x01C16FD0` at +4 and SSP `0x01C17FD0` at +0xA; a call at +0x10 targets
offset `0xC6` outside this prefix, whose function is not established here
[verified decode]. It zeros from `0x01C0A05C` using byte count `0x195C0`
and copies `0xA05C` bytes from XIP `0x02084060` to RAM `0x01C00000`
[verified loop operands; inferred bulk effects]. This intentionally overlaps
the old SPL body; it is not evidence of private RAM ownership for Lunar.

The existing 200-byte inert Lunar diagnostic can link at `0x02000120`, but
there is no modified-container builder, externally observable result,
owned SSP/exception policy or proven complete startup. Its low RAM overlaps
the SPL and it must not return to or call overwritten SPL code. An unresolved
SPL callback prevents an unconditional final watchdog-state guarantee;
clock/cache/TLB/secondary-core handover remains open. See the parallel stock
handover note for those boundaries.

Next offline experiment: model a fixed-allocation app replacement in a
synthetic image, preserving cfg/resource positions and stock SPL/OTA/config;
recompute child and directory CRCs, SFC encoding, flash/list/header CRCs,
and independently revalidate each modified layer. Explain remaining envelope
metadata, trailer and version policy before emitting an experimental
container. Device experimentation additionally requires an observable
diagnostic, a reviewed candidate and exact write range, fresh backups and the
owner's staged recovery policy. Full-image and broken-app recovery remain
unproven specific risks; the existing bounded 4 KiB restore-and-boot evidence
must not be described as proof of those broader recovery cases.

## Change log

- 2026-10-09: Verified saved-image base zero, static SPL entry/address
  correspondence, bank-body range and fresh vendor stock app-prefix decode;
  added stock-entry placement regression. No device execution or installer.
