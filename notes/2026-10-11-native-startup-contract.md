# Native diagnostic startup contract

2026-10-11. Lunar Modulator, personal and non-commercial. The agreed endpoint
is an installable diagnostic image that boots, displays the panel probe and
retains recovery. This note records source evidence and the remaining startup
premises; it does not approve an installation.

## Result and scope

[verified: source/artifact review] The executing-core instruction and stock
interrupt registration layout are known. Secondary-core ownership, exception
delivery while masked, privilege and the safe SSP/protection transition remain
unresolved. The existing handover profile assigns SP and SSP before checking
the core and does not install its own exception dispatch. Its linked memory
reservation is therefore not a complete activation contract.

[verified: bench receipt] The separate 14-byte RAM reset stub returned this
unit from UBOOT to a responsive FM-1_092 application. That experiment supplies
a route out of that ROM session; it does not establish the startup state of
an application called by the stock SPL. See the
[reset receipt](2026-10-11-fm1-core-reset-bench.md).

The review covers the selected ordinary XIP path only. Stock SPL calls
`0x02000120` with `r0 = 0x01c7fe08`; a valid inherited RAM callback record can
select an optional callback before this call. Its effects are not identified.
[verified: decoded instructions; inferred: path premises] See the
[final SPL contract](2026-10-11-stock-spl-final-contract.md). The retained RAM
record cannot be established by inspecting the flash image alone.

## Executing core and secondary-core ownership

[verified: primary SDK and stock decode] SDK `cpu.h:78-84` reads `cnum`;
stock app raw `0x1b16` decodes `64 e0 00 06` as `r0 = cnum`. An independently
authored first-entry prerequisite can preserve incoming r0, mask ordinary
interrupts and check the current core before any stack or shared-RAM use.
An accepted core ID does not establish that the other core is stopped.

[verified: SDK declarations] `csfr.h:106-112,208-214,239-262` places C1_CON at
`0x01eee004`, the core1 PCRS view at `0x01eef27c` and its write-only CMD_PAUSE
at `0x01eef298`. The declarations specify no hold acknowledgment or bit-1/
bit-3 meaning. SDK `debug.c:461-472,555-578` issues CMD_PAUSE, clears bit 3,
sets bit 1 and samples PC/trace, without a finite acknowledgment poll.
[inferred] That debug sequence suggests control policy, but its success and
readback semantics cannot be asserted from the implementation alone.

[verified: stock application decode] Raw `0x5990e..0x5994e` publishes its own
CPU1 entry, sets C1_CON bit 3 and clears bit 1 before waiting for an app RAM
flag. This is application startup evidence, not a measurement before the SPL
call. The saved SPL decode contains no textual occurrence of C1_CON/C0_CON,
`0x01eee004`, CMD_PAUSE or `0x01eef298`. [limit] This bounded negative search
does not exclude computed addresses, ROM helpers or the optional callback.

[proposed] Accept secondary-core ownership only with either a documented
hold/reset readback and finite acknowledged completion, or an owned cooperative
park protocol with owned executable storage, reviewed ordering and a matching
generation-tagged acknowledgment. Neither exists in the reviewed evidence.
An unchanged PC, disabled tracing or zero app flag remains unknown, including
after a fixed number of reads. Do not release the old stock CPU1 entry after
replacing the application.

## Exception delivery and stack transition

[verified: primary SDK and stock decode] IRQ1 is the exception index; its
handler slot is `0x01c7fe04`. The shared table starts at `0x01c7fe00` and slots
2 onward overlap the six-word boot input at `0x01c7fe08`. Core0's IRQ1 route
is nibble 1 of `0x01eef100`; the priority-7 encoding is `0xf`. Capture the
boot input before any permitted vector edit, and never clear the whole table.

[verified: decoded implementation] Stock request_irq raw `0x16e0..0x1764`
can override priority/core through a flash policy table, writes the handler
before masking, then enables ICFG bit 8. Stock debug_init uses that API for
IRQ1. This sequence does not demonstrate IRQ1 delivery under continuous CLI.
The handler at `0x020001cc` begins with `trigger`, saves special/general
registers on the stack and calls the analyzer. Its entry dispatcher and the
meaning of trigger are not established here.

[verified: primary SDK] Special-register views expose USP/SSP/SP and EMU
control/stack bounds, but do not specify privilege selection, implicit entry
saves, nesting or the comparator's equality/access-width rules. SDK
`debug.c:1164-1169` disables the bit-3 stack check, assigns SSP bounds from
linker symbols, then enables it. The high symbol is one past the linked stack
section; that does not establish a half-open hardware range or safe ordering
from unknown inherited protections. Do not copy debug_clear, clear all EMU
state or disable other cores' protections to make a stack relocation work.

[verified: vendor documentation, retrieved 2026-10-11] The official
[AC791 nonmaskable-interrupt example](https://doc.zh-jieli.com/AC79/zh-cn/release_v1.2.0/module_example/system/%E4%B8%8D%E5%8F%AF%E5%B1%8F%E8%94%BD%E4%B8%AD%E6%96%AD.html)
requires CONFIG_IPMASK_ENABLE and priority 7, with the handler, callees and
constants in internal RAM. Pinned SDK app_config.h has that option disabled.
[inferred] Priority 7 alone is not a contract for synchronous IRQ1 delivery
under CLI; IPMASK and ICFG bit 8 must not be conflated. These mutable release
pages are not immutable source blobs tied to the SDK commit.

[verified: vendor documentation] The official
[exception diagnosis page](https://doc.zh-jieli.com/AC79/zh-cn/release_v1.2.0/module_example/system/exception.html)
recommends SRAM exception handling and a watchdog direct-reset path when flash
failure prevents handler entry/reset. It supplies no complete privilege,
delivery or stack-bounds specification. Links to AC63 and results for other
SoCs were excluded from the AC791 contract.

[proposed] An own branch-only, nonreturning sink can establish the absence
of software stack/data access after successful entry/fetch. It cannot prove
safe dispatch, absence of implicit entry writes, nested-fault behavior or
automatic recovery. A RAM marker, CLI instruction or reset action adds its
own privilege, ownership and fault dependencies. A RAM label and CSYNC alone
do not establish executable visibility after copying.

## Concrete continuation

1. Implement and audit a separate instruction-only entry prerequisite,
   preserving r0 and checking cnum before stack/RAM use. Both accepted and
   rejected paths terminate without board output. Keep hardware_ready false
   and keep this profile out of package/raw-target staging.
2. Exercise the actual display, timer and recovery components together on
   Hera, including timeout and marker/P33 failures. A transmitted request
   remains distinct from observed USB recovery.
3. Obtain a primary AC791/pi32v2 entry/ROM specification or narrowly reviewed
   observation that establishes the missing ownership and dispatch premises.
   Stable register snapshots and source names cannot close those gates.
4. Only then review bootstrap/stack/vector changes and a concrete display
   activation candidate, with the independent clock, watchdog, PA2 and
   application-context recovery contracts. Fresh matching backups and the
   existing stock SPL/OTA/cfg/partition guards still precede flash mutation.

No physical action or package is authorized by this note. The entire-device
recovery model remains a protocol/NOR model rather than a pi32v2 emulator.

## Provenance and verification limits

[verified: review receipts] SDK pin is
`e30b1ee375d1f2993fc23bf92c8b99006a6e5f9d`; stock app is 581,564 bytes with
SHA-256 `306e47065f35d7a7a05ada7f5dd092f6e770952054f33f0a86b75fd10ffe3203`;
SPL is 14,384 bytes with SHA-256
`730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef`.
The vendor stock decode covers every app byte, with zero byte mismatches,
but retains unknown records and does not prove every instruction's semantics.

| Saved evidence | SHA-256 |
| --- | --- |
| SDK csfr.h | `62858489d6a3e68e24b8868175827df1c83c716238b7789be81c74758e1963c6` |
| SDK debug.c | `92d7927fb423e933f8f20ab51d6727d3944954cfd56037a044e4e4d3f48f789a` |
| Stock app vendor decode | `59381ae18823d396fe7f033a589d5a9de7617be5fcbe7d3cc4b7831e232c3fd0` |
| Stock SPL vendor decode | `404f1c48d6445712e85082d4e9fdcdde49f5a9deeea2bfb5d72cfe05e38126ca` |
| build/native-activation-contract-review.md | `6ef76d01e64d990c0c1f453ac6c9825456f0bcb2bb935cf989eba4c51f3dc3ba` |
| build/c1-hold-research.md | `2a7fa996968c54d4e54e7d22e46a42d3d25da34a5540f17ea0b232b55b999248` |
| build/exception-contract-research.md | `4f31eb57fac7c6441bb3e17e31dc4101d43ae0aaa0bd97141d39a74f44f0c93a` |

The three ignored reports were independently reviewed and their essential
findings are preserved here. They used source/artifact inspection, hashes and
bounded vendor-document browsing; they did not build, test or operate hardware.
Rarefaction and Serena still select the original checkout during concurrent
work. Their shared selection was left untouched; exact-file inspection was
used. The result does not claim successful semantic indexing of this worktree.
