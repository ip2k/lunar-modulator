# Fixed RAM core-reset experiment

This independent MIT assembly entry is a proposed, bounded ROM RAM experiment
for the owner's FM-1. Its exact machine code has been built and checked offline
[verified]; device execution, reset coverage and return of normal USB are
unproven. See [the investigation note](../../notes/2026-10-11-rom-core-reset-stub.md)
for evidence and physical-attempt gates.

The five instructions disable interrupts, set `r0` to `JL_POWER.CON` at
0x00010000, OR bit4, synchronize, and spin forever. Primary WL82 SDK register
definitions and its JTAG configuration identify this core soft-reset operation;
the independently audited download-loader reset helper uses the same SFR RMW
[verified]. This differs from the stock soft-key P33 reset. The entry has no
initialization, stack dependency, helper, call, flash/eFuse access, logger,
watchdog feed or mailbox access [verified target bytes]. In particular it leaves
the retained `usb_update_mode` marker untouched.

## Offline native build

Use Hera's vendor toolchain
`/home/claude/mvave-fm1/sdk-v1213/toolchain/current`, resolved to
`jieli-linux-toolchains-20250324.1`. Heavy work belongs on Hera, not the Mac or
aeon. The audited build used `lunar-jieli-check:bookworm`, with this toolchain
read-only at `/toolchain`, a writable output directory, one CPU and 256MiB.
These commands compile and inspect artifacts only; they contain no device
opener or upload operation:

```sh
mkdir -p build/core-reset-stub
/toolchain/pi32v2/bin/clang -target pi32v2 -mcpu=r3 -mfprev1 -c firmware/core-reset/core-reset.S -o build/core-reset-stub/core-reset.o
/toolchain/pi32v2/bin/ld -T firmware/core-reset/core-reset.ld build/core-reset-stub/core-reset.o -o build/core-reset-stub/core-reset.elf
/toolchain/pi32v2/bin/objdump -d -mcpu=r3 -mattr=+fprev1 build/core-reset-stub/core-reset.elf > build/core-reset-stub/core-reset.disasm.txt
/toolchain/pi32v2/bin/objcopy -j .probe -O binary build/core-reset-stub/core-reset.elf build/core-reset-stub/core-reset.bin
/toolchain/pi32v2/bin/nm -n build/core-reset-stub/core-reset.elf
/toolchain/pi32v2/bin/objdump -h -r -t build/core-reset-stub/core-reset.elf
```

The source and linker script are pinned, respectively, to SHA256
`8b6530913943baeec54a67cb82482c3f0870078761c6fe1eb661812f45360e92`
and `b989bd8cd561f43083b8470f409d1d7e49987a1cf0218c173e8a858e64148ed4`.
The tool executable SHA256 pins are:

| Executable | SHA256 |
| --- | --- |
| clang | 42b94f9e11140b0fcab8f807b2872ad245b8eeca03a2d792f8706c5a3a35d34c |
| ld | fd61aff15616bb6f6b58fd2e9ede7af741c7bf05facb3e0cb3d3c9817c268fd9 |
| objdump | cffc304e1a9be5dac22984a6ad48e81ef82b17166fd8864c251cf635c9663b73 |
| objcopy | a941eab0dd62d51da635be7834fc34d4765dbf421d00599f3a5081d42d416502 |

## Exact proposed transport

The artifact must be exactly 14 bytes, `600060e0800b00ef10002000f79f`, SHA256
`b137c15cc0b82d0d056246f08ad2292f754216b9f70bd83a1caec4e35978cee5`.
Its ELF entry is 0x01C02000, with one allocated section, no nonempty relocations
or named undefined symbols [verified]. The vendor listing was checked against
every image byte. The artifact is padded with exactly 498 zero bytes to one
512-byte ROM block. Padding SHA256 is
`1769116dffef03bcfe5b6f30cbe801ba6fdaef1f7de18631307d39c1cfe6e7fb`;
encrypted-block SHA256 is
`cffeb8df17fe3dbe0fa85c162ad2b29b71ef247e8074259aa13dcebf7d88582f`.
The existing independent cipher was checked against kagaimiq's pinned upstream
decoder [verified offline]. Build artifacts and receipts stay ignored under
`build/core-reset-stub/`.

The proposed separately reviewed guard permits one INQUIRY, one fixed FB06
upload of that encrypted block to 0x01C02000, and one FB08 jump to the same
entry with argument1. It must pin the historical owner/entry receipt and fresh
same-port device binding, validate all artifacts before device access, preserve
durable intent and consume/latch on an attempted command, with no retries or
loader commands. The existing 700-byte RAM guard must retain its own pin.
This directory supplies no physical opener or general command-line uploader.

ROM custom entry, instruction-cache state, inherited privilege/protection,
secondary-core state and SFR readback/reset-domain effects remain unknown.
The device may stall until the owner's real power cycle, reset back to ROM
because the marker remains, or boot with USB absent. A missing response or
enumeration change is not an independent stub-execution witness. Any concrete
attempt needs independent artifact, guard and adapter review under the owner's
standing staged RAM exploration scope; stop after the single attempt.

Credit: JieLi AC79 SDK for primary register/reset facts; kagaimiq (Andrey
Grigoryev) for ROM transport/cipher research. No SDK or GPL implementation is
copied into this entry.
