# Offline returning RAM leaf candidate

Independently authored MIT assembly for one possible RAM-only bring-up
milestone. **Never executed on an FM-1. No device execution is authorized
by this artifact.** The existing recovery tool intentionally rejects this
payload, ROM memory reads and custom jumps.

The target-linked block occupies `0x01c02000..0x01c021ff`. The leaf modifies
only `r0..r2` and stores three words in its own 32-byte mailbox at
`0x01c021e0`: completion bytes `LUNR`, incoming `r0`, and incoming `r0`
XOR `0x1357`. The remaining mailbox bytes start as zero. It then sets
`r0` to zero and uses `rts`. There are no stack accesses, calls, explicit
IRQ changes, flash references, MMIO or SDK dependencies.

This does **not** establish that the ROM passes its command argument in
`r0`, preserves this RAM window, invokes the target as a returning
function, or restores/retains RAM after an encrypted read. Those contracts
must be established and a separate exact transport boundary reviewed
before any execution proposal. The previous successful recovery-loader
upload used a different, pinned 24,064-byte image which never returned;
it does not prove this leaf's call contract.

Build offline inside the existing bounded JieLi container with:

```sh
/opt/jieli/common/bin/clang -target pi32v2 -mcpu=r3 -mfprev1 \
  -c /src/firmware/ram-leaf/leaf.S -o /out/leaf.o
/opt/jieli/pi32v2/bin/ld -T /src/firmware/ram-leaf/probe.ld \
  -Map=/out/leaf.map -o /out/leaf.elf /out/leaf.o
/opt/jieli/pi32v2/bin/objcopy -O binary -j .probe \
  /out/leaf.elf /out/leaf.bin
/opt/jieli/common/bin/objdump -d -mcpu=r3 -mattr=+fprev1 \
  /out/leaf.elf > /out/leaf.disasm.txt
```

Keep generated binaries and vendor inputs private in ignored scratch.
Exact build hashes, disassembly and rejected alternatives are recorded in
`notes/2026-10-10-fm1-live-bringup.md`.
