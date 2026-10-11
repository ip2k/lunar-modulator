# Stock SPL final handoff: selected path and remaining ownership gates

2026-10-11. Independent, bounded offline follow-up to
[the earlier handover trace](2026-10-09-stock-spl-handover.md). No hardware
traffic, native activation, flash operation or new vendor build occurred.
`[verified]` below means artifact/source inspection, not target execution.
This note does not authorize a hardware experiment or establish a complete
SDK-free startup contract.

## Exact inputs and mapping

[verified] Stock V15 and FM-1_092 unpacked `uboot.boot` both contain 14,384
bytes and have SHA-256
`730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef`.
The existing vendor decode was compared again with the exact stock file:
14,384 byte columns covered, zero mismatches. Decoding data as instructions
does not make it executable; the conclusions below follow named control-flow
paths. No vendor binary or full decode is included here.

[verified] The 16-byte bank header specifies a 14,368-byte body loaded at
`0x01c02000`, with file entry offset `0x10`. All instruction offsets below
are **complete SPL file offsets**; the RAM mapping is
`0x01c02000 + file_offset - 16`. The body occupies
`[0x01c02000, 0x01c05820)`.

[verified] The saved 1-MiB FM-1_092 backup used here has SHA-256
`96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`.
Its four top-level records independently pass their header CRCs after the
JieLi header cipher with key `0xffff`. The `app_dir_head` record points to
flash offset `0x4000`. Its first application record passes its header CRC
after the SFC cipher with chip key `0x980f` and relative block offset zero.
The same records were checked in both packages' existing decrypted images.
The cipher/CRC primitives were those of kagaimiq's `jl-misctools`; no
firmware implementation was copied.

| Profile | Application record | Entry | Area size | Flags |
| --- | --- | --- | --- | --- |
| Stock V15 package | `[verified]` `app_area_head` at `0x4000` | `0x02000120` | 582,235 | `0x83` |
| FM-1_092 package | `[verified]` same | `0x02000120` | 692,415 | `0x83` |
| Saved FM-1_092 raw flash | `[verified]` same | `0x02000120` | 692,415 | `0x83` |

## Selected ordinary XIP path

[verified] Helper `0x1320` searches the top records for `app_dir_head`
(or its alternate), reads and CRC-checks the application-area header, and
stores its entry at metadata address `0x01c075e8`. It stores the top record's
flash address plus the selected flash base in metadata word +4. Successful
selection reaches `0x2d7e`, which clears `r13`. The inspected profiles supply
the valid ordinary entry `0x02000120`; this establishes their metadata,
not a live observation of all runtime inputs.

[verified] At `0x3202` the SPL tests entry bit `0x04000000`. It is clear in
all three checked headers, so these entries take the ordinary XIP branch
to `0x3248`, bypassing the RAM-application decompression path. At `0x3294`
the SPL loads that entry into `r1`; `0x3298` sets `r0 = 0x01c7fe08`;
`0x329c` executes `call r1`. The byte windows are respectively
`d0 ec c0 10`, `00 e1 88 a0`, and `c1 00`. The return continuation is
`0x01c0528e`, where SPL code remains. This is a call with one established
boot argument, not a reset-vector ABI.

## What the earlier indirect callback actually selects

[verified] `0x2f74` (`c2 00`, `call r2`) calls an optional flash payload
after its decompression and CRC checks. Its entry is not a fixed SPL
function. The relevant chain is:

1. `[verified]` `0x2df6..0x2e00` copies an 80-byte inherited RAM record from
   `0x01c7fd88` to `0x01c06550`. At `0x2e5e..0x2e72`, a nonzero CRC over
   bytes 2–79 must equal its stored CRC, and its word at +2 must be nonzero.
2. `[verified]` With an invalid RAM record, successful application selection
   (`r13 == 0`) takes `0x2e08 -> 0x2f78`. It **skips** the trailing-flash
   record search. The latter search runs when application selection has
   not cleared `r13`; it checks an `0x5441` signature and a record CRC.
3. `[verified]` A valid RAM record instead supplies a flash-record pointer
   at +72 through helper `0x1448`. Helper `0x147e` streams its contents.
   Two 32-byte reads at `0x2e98` and `0x2ea2` leave the second header at
   `sp + 200`. Its bytes 2–31 are CRC-checked at `0x2eb2`.
4. `[verified]` Inner header +8 supplies both decompression destination
   (`0x2ed2`) and eventual entry. Blocks have a compressed-size bound of
   4096, a nonzero output length, and checked decompressor output counts;
   the total output length and output CRC must match the header.
5. `[verified]` `0x2f6c..0x2f74` loads entry +8 and calls it with
   `r0 = 0x01c075e8` and `r1 = metadata[3]`. A returning callback proceeds
   to the common path at `0x2fa4`.

[verified] The saved flash and package headers do not capture the inherited
RAM record, and no callback body was identified or decoded in this review.
[inferred] A normal boot with valid ordinary app metadata and an invalid RAM
record bypasses this callback; its absence cannot be claimed for every warm,
update or recovery entry. CRCs establish integrity, not callback behavior.
The `UARTUPDATE` / `UART_UPDATE_CUSTOM` marker branches at `0x2f78` are also
runtime inputs; neither should be presumed absent merely from an app header.

## Final watchdog and execution state

[verified] Both primary SDK archive-member IR versions, V1.1.9 at
`8eae66452ce4c34d64ad38a2764ba1c0610900e3` and V1.2.13 at
`e30b1ee375d1f2993fc23bf92c8b99006a6e5f9d`, agree: P33 command `0x40`
means AND, watchdog register is `0x80`, bit 4 is enable, bit 5 selects IRQ
mode, and bit 6 is service/clear. These are **verified SDK semantics**, not
inferred bit assignments. `wdt_reset_enable` preserves bit 4, clears bit 5
and services bit 6; it does not independently enable a disabled watchdog.

[verified] Early SPL writes at `0x183c`, `0x1850`, `0x1864` send `0x40`,
`0x80`, `0xef`: an AND which clears only watchdog enable bit 4. The optional
RAM-test helper also plain-writes zero to `0x80` at `0x6ea..0x6f0`. The
final directly traced path `0x30d6..0x329c` contains no watchdog re-enable;
its helper `0x11d8` writes P33 registers `0xb0`/`0xb1` and reads `0xb2`,
not watchdog register `0x80`. [inferred] On the callback-bypassing ordinary
path, the known SPL transactions leave the watchdog disabled. An unobserved
callback or inherited execution context prevents a universal final-register
claim. Period, elapsed count and IRQ/reset mode were not observed. An
SDK-free diagnostic must not rely on an inherited watchdog as recovery.

[verified] The final path clears SPI0 control bit 0 at `0x11c00`, configures
SFC base `0x4020c` from metadata, invokes cache helper `0x4f4`, executes
`cli` at `0x31d2` (`60 00`), waits on `CACHE_CON` (`0x01eee008`) bit 14,
writes `1` to `SFCENC_CON` (`0x40300`), and sets cache bits `0x300`.
There is no subsequent `sti` on this XIP path. The six-word boot prefix and
pointed-to 32-byte header are copied to `0x01c7fe08` and `0x01c7fe20`.
Cache helper `0x4f4` clears its selected cache-related memory ranges and
restores bits `0x300`; this is concrete inherited setup, not reset state.

[verified] SPL startup assigns `rete = 0`, `reti = 0x01c02036`, performs
`rti`, and assigns `ssp = 0x01c05c40`, `sp = 0x01c06040`. Its main changes
the stack before application entry. [inferred] This does not identify the
executing core, establish privilege, make the exception path safe, or prove
the secondary core is parked. SDK declarations of two cores and protection
registers are not observations of the selected boot state. The bounded trace
does not establish CPU0/CPU1 control, MPU/debug protection, MMU/TLB or complete
SRAM ownership. A lack of recognizable literal accesses cannot resolve those
questions; ROM and optional payload effects remain outside this trace.

## Next gates

[inferred] The evidence supports offline integration of an explicitly inert,
non-returning startup profile preserving the XIP setup, boot argument,
separate `sp`/`ssp`, and bounded data/BSS ranges. It does not by itself clear
execution gates. The current diagnostic RAM overlaps the SPL body; a new
exception path must not target discarded SPL storage. Before any activated
native profile, independently establish core/exception/protection ownership,
audit the exact linked instructions and preserved boot metadata, and bind the
candidate to the exact raw-flash/package guard and concrete recovery plan.
Before LCD access, also establish its clock/delay and pin contract. A further
probe, if separately authorized, needs a distinct observable result that can
separate execution from watchdog/fault/ROM fallback; ROM re-enumeration alone
cannot do that.

Validation: complete SPL byte-column comparison; independent three-profile
record CRC and entry checks; bounded reachable-path inspection; two-version
SDK IR and named register declaration checks. No target ABI, RAM ownership,
watchdog-duration, LCD, native execution or recovery acceptance is claimed.
