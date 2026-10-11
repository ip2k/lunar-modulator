# Minimal ROM RAM core-reset stub investigation (2026-10-11)

**Offline artifact only; no device commands.** A smaller reset experiment can omit the download loader and its NOR initialization entirely. The compiled fixed entry contains only interrupt disable, an immediate power-register address, a read-modify-write of reset bit4, a synchronization instruction and a self-loop [verified target artifact]. Whether mask-ROM entry can execute it with inherited privilege/cache/write-protection state, and whether the resulting reset returns stock USB, remain unproven.

The [loader audit](2026-10-11-loader-run-app-reset.md) established that LoaderV2 FC0C requests core soft reset via `JL_POWER->CON` at 0x00010000, OR 0x10. It also established that full loader entry can write NOR status if retained RAM selects quad mode. The alternative below avoids that code and post-image configuration parsing; it does not clear the `usb_update_mode` mailbox or change the reset domain.

## Fixed independent source and machine code

The independent MIT assembly source and fixed linker script are saved in tracked `firmware/core-reset/`; byte-identical build inputs and all compiled evidence remain ignored in `build/core-reset-stub/`. The complete source body is:

```asm
.section .entry,"ax",@progbits
.global _start
.type _start,@function
_start:
    cli
    r0 = 0x10000;
    [r0] |= 0x10;
    csync
1:
    goto 1b;
.size _start, .-_start
```

It is an assembly entry with no compiler prologue or inherited stack dependency. “cli” here is the CPU interrupt-disable instruction; no physical command-line entry point was created.

| Address | Exact bytes | Vendor decode |
| --- | --- | --- |
| 0x01C02000 | 60 00 | cli |
| 0x01C02002 | 60 E0 80 0B | r0 = 0x10000 |
| 0x01C02006 | 00 EF 10 00 | [r0+0] OR 0x10 |
| 0x01C0200A | 20 00 | csync |
| 0x01C0200C | F7 9F | goto self |

[verified] The 14-byte binary is `600060e0800b00ef10002000f79f`, SHA256 `b137c15cc0b82d0d056246f08ad2292f754216b9f70bd83a1caec4e35978cee5`. Source SHA256 is `8b6530913943baeec54a67cb82482c3f0870078761c6fe1eb661812f45360e92`; linker source SHA256 is `b989bd8cd561f43083b8470f409d1d7e49987a1cf0218c173e8a858e64148ed4`. The linked ELF entry is 0x01C02000, with exactly one allocated section `.probe` of size14, no nonempty relocations and no named undefined symbols. The vendor listing matches every binary byte. No stack, helper, call, RAM mailbox, flash or eFuse address is accessed by these five instructions. `r0` is clobbered deliberately; entry never returns.

[verified] Primary SDK source at commit `e30b1ee375d1f2993fc23bf92c8b99006a6e5f9d`, `include_lib/driver/cpu/wl82/asm/WL82.h`, defines `JL_POWER->CON` at 0x10000 and aliases `JL_CLOCK->PWR_CON`. `cpu/wl82/tools/jtag/dbg.config` calls this address soft-reset control and bit4 the reset bit. The exact loader core-reset helper uses the same read-modify-write instruction, independently corroborating this operation. This is not the stock soft-key P33 reset; CPU/core/peripheral reset coverage is not established by the register name.

## Build and offline checks

[verified] Built only on Hera (`claude@192.168.1.48`) using the current pinned toolchain symlink to `jieli-linux-toolchains-20250324.1`, image `lunar-jieli-check:bookworm`, 256MiB/one-CPU container under `docker-batch.slice`. Remote saved source and outputs: `/home/claude/mvave-fm1/core-reset-stub-review-20261011/`. No aeon work or hardware traffic occurred.

Commands inside that offline container:

```sh
/toolchain/pi32v2/bin/clang -target pi32v2 -mcpu=r3 -mfprev1 -c core-reset.S -o core-reset.o
/toolchain/pi32v2/bin/ld -T core-reset.ld core-reset.o -o core-reset.elf
/toolchain/pi32v2/bin/objdump -d -mcpu=r3 -mattr=+fprev1 core-reset.elf
/toolchain/pi32v2/bin/objcopy -j .probe -O binary core-reset.elf core-reset.bin
/toolchain/pi32v2/bin/nm -n core-reset.elf
/toolchain/pi32v2/bin/objdump -h -r -t core-reset.elf
```

Full toolchain/output/source hashes, listing, symbols, ELF structure and packet preparation receipt are saved in ignored `build/core-reset-stub/`. The vendor toolchain has no `readelf`; a local minimal ELF32 reader independently checked entry, allocated sections and relocation absence instead. No toolchain or vendor binary enters Git.

[verified offline] The artifact was padded with 498 fixed zero bytes to one512-byte ROM upload block. The existing independent `scramble_block()` produced SHA256 `cffeb8df17fe3dbe0fa85c162ad2b29b71ef247e8074259aa13dcebf7d88582f` for the encrypted block. Independently executing kagaimiq’s pinned `jl_crc_cipher` reproduced the exact14 bytes plus498 zeros. Padding SHA256 is `1769116dffef03bcfe5b6f30cbe801ba6fdaef1f7de18631307d39c1cfe6e7fb`. This is transport-format validation, not device execution proof. Credit: kagaimiq (Andrey Grigoryev), JieLi AC79 SDK.

## Proposed exact envelope and remaining gates

[proposal only] A dedicated exact-image guard could permit INQUIRY, **one** FB06 encrypted512-byte upload to 0x01C02000, then **one** FB08 jump to 0x01C02000 with argument1. Existing pure packet construction gives upload CDB `fb0601c02000020000a794ffffffffff` and jump CDB `fb0801c020000001ffffffffffffffff`. It would issue no LoaderV2 readiness/reset/flash commands. Validation must happen before device access, using the exact plain/padded/encrypted pins, current port/device binding and one exclusive campaign receipt. The current 700-byte RAM guard is intentionally incompatible; do not override its pin or reuse it to silently permit this image.

The prior RAM guard’s requirement for a fresh normal→ROM entry is not currently satisfiable merely from an old probe receipt. A separate guard must explicitly bind the exact historical owner identity/entry receipt to fresh passive evidence of the still-connected ROM session and its SG/USB handle, fail on replacement, and latch after any attempted upload/jump. Root must review that change as a concrete new envelope, with no arbitrary address/image option, retries, loader commands or mailbox edits. Durable jump intent must precede the syscall; capture starts before entry; bounded post-attempt host observations cannot send extra device commands. Receipt should report transport outcome separately from reset/boot observations.

[verified source/artifact; unproven execution] This removes full-loader initialization, flash configuration and logger/timer helpers from the code graph. It does **not** prove ROM accepts/executes custom code, invalidates instruction cache, permits `cli` or the power-SFR access, leaves secondary-core activity harmless, or implements a reset that resets USB/boots flash. A privilege exception, trap, inherited protection failure or stall can leave the device hung until the owner power-cycles. The RMW preserves observed register bits, as the vendor helper does, but semantics of other readback bits or asynchronous updates are not independently established. No independent execution witness is included.

[verified stock trace; unknown ROM behavior] The stock soft key sets 16-byte `usb_update_mode\0` at 0x01C7FD80 before P33 reset. This stub neither reads nor clears it. Its current retained value and ROM consumer/clear policy are unknown; a core reset may lead back to ROM. [reported] FM-1-transporter found stock V15 warmboot can run without USB attach until cold power-on. Distinct USB enumeration, missing response, or another ROM appearance can be consistent with reset but cannot isolate this stub from the ROM watchdog/reset path. The earlier 700B attempt remains causally ambiguous.

[inferred authorization scope] Preparing this concrete reset-only RAM code is within the owner’s staged reviewed RAM-exploration policy and acceptance of a hang until a later owner power cycle. That policy is not blanket authorization for arbitrary addresses/vendor commands or automatic repeat attempts. Root must complete independent source/artifact/guard review and determine the concrete physical attempt under the owner’s standing scope. This note makes no hardware deployment or USB-restoration claim. A physical CLI was deliberately deferred until those checks exist; no caller can currently invoke this artifact through a newly provided device opener.

Concrete next step: independently review these exact14 bytes and build receipt, then author/review the one-block bound transport separately if root chooses this experiment. Keep retained-mailbox/core-reset/USB uncertainties explicit and stop after one ambiguous attempt. The known fallback is the owner’s real power cycle. Neither this artifact nor an enumeration event establishes full-image recovery or installation readiness.

## Independent attempt-scope assessment

[verified artifact; inferred experimental scope] The five-instruction graph is sufficiently bounded to propose a **single** exact attempt under the owner's already authorized RAM exploration and accepted later power-cycle fallback. There is no identified reachable flash/eFuse operation or full-loader initializer in this artifact. The unknown cache/privilege/protection state can prevent execution or cause a trap; the unresolved reset domain and retained marker can prevent normal USB return. Those are material experimental risks, not evidence that a recovery reset is guaranteed. `cli` deliberately prevents this entry from relying on inherited interrupt handlers; whether ROM-entry privilege permits it remains unproven. The power-register RMW is corroborated by the exact loader helper, but other readback bits/asynchronous changes are not exhaustively characterized.

This assessment is conditional on the independently reviewed concrete guard and private adapter: exact artifact pins, one fixed upload/jump, fresh same-port session binding to the owner receipt, exclusive access, durable pre-syscall intent, ambiguity latching, no retries, and capture started before upload with bounded host-only observation afterward. No additional mailbox clear, arbitrary address, flash operation or loader initialization follows from this assessment. If those conditions hold, remaining semantic uncertainty alone does not require another loader-based staging step; such a step would reintroduce the audited loader initialization risk. Root makes the physical decision and owns integration. This reviewer performed no hardware operation.
