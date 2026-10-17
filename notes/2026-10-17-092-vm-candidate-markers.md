# Exact FM-1_092 VM candidate markers

## Address correction — read before historical observations

[verified: coordinator exact-byte and pointer-table checks] The linked model is
0x02000120 plus raw offset. Earlier XIP labels below used a wrong zero-origin
bias and are superseded; their raw offsets and literal-byte observations remain
locators. Add 0x120 to the former listing labels when referring to decoded code
locations, but do not add it to embedded absolute literals or RAM addresses.
See notes/2026-10-17-092-disassembly-review.md for independent string, pointer
table and corrected startup-copy checks. Candidate init raw0x33F56 is actual
0x02034076 and has a pointer at raw0x8300C; candidate read raw0x34294 and write
raw0x34384 have adjacent pointers. Earlier absent-pointer/reachability and RAM
alias arguments based on wrong labels are withdrawn pending the corrected trace.
No bank ownership, physical recovery or write admission follows from this fix.

## Historical zero-origin observations

[verified: offline payload scan] Coordinator scanned the exact public 691,744-byte
092 app with SHA-256
`9c5a44706b7686746b389e3e8fe6ff051fc50028f9b708ac59f493300f793a7b`
for the complete little-endian four-byte values identified in the pinned SDK
VM member. The scan used Python bytes.find, advancing one byte after each hit.
Offsets below identify literal bytes, not necessarily instruction boundaries.

| Value | All raw app offsets |
| --- | --- |
| `0x55AAAA55` | `0x28E80`, `0x29078`, `0x296F2`, `0x340A0`, `0x340DC` |
| `0xDDEEBB77` | `0x28F56` |
| `0xDDEEAA55` | `0x2901E`, `0x3408E` |

[verified: origin-correct vendor listing] The candidate cluster has a prologue
at raw `0x28F10` / XIP `0x02028F10`. It tests an area-like value at a 12-byte
stride; adds four to a loaded address; loads the DDEEBB77 literal and calls
`0x02003AA8` with a four-byte length. Later it loops through indices 0–255,
loads DDEEAA55 and calls the same target with four bytes, toggles a flag,
then loads 55AAAA55 and calls that target again. A separate branch calls the
prologue at `0x02028E7A`. These observations are a multi-feature candidate for
the SDK defragmentation routine; neither function nor callee names are proven.
The listing SHA-256 is
`f62050c81be2ff7e1f5645873bc47ca07c52c7a95b9e7752b5792a5a181767d8`.

[verified: candidate-library extraction; reported worker inventory] Aeon
extracted the public V1.1.9 and V1.2.13 cfg_tool.a vm.c.o members using the
pinned JieLi clang. Input archive hashes and complete commands are in ignored
`scratch/sdk-vm-ir-20261017/analysis-original.md`, SHA-256
`34f547f62ffa51a2483869a087fbbb3f73fa3268da1458c30ae0b4be70e8de23`.
Coordinator copied and independently hashed that report and the V1.1.9 IR
(`a0f2bd1e8cc7edb02e5526c5cb23ae553de4351d3b3fdf6a789c0c89dfdd1a0f`).
The IR's _vm_defrag body uses these markers with calls named sfc_write.

The first extraction let clang override the target triple to x86_64. Although
it emitted textual IR without machine-code generation, its ABI/layout must
not be relied upon. A follow-up explicitly uses the existing firmware target
flags (-target pi32v2 -mcpu=r3 -mfprev1) and preserves the original output for
comparison. Full vendor IR/disassembly and binaries remain uncommitted.

[inferred: candidate correspondence only] The multiple shared motifs make a
VM-family match worth pursuing. They do not prove which SDK revision was
linked, exact VM/USR bank boundaries, allocator ownership, persistence record
semantics, boot reachability or erase permission. Next compare target-correct
IR body structure and actual 092 callsites, then trace bank arguments and
record decoding. Do not enable SAVE or format sectors from this evidence.
No hardware or Hera access occurred.

## Common callee follow-up

[verified: bounded decoded instructions] `0x02003AA8` reorders the second and
third argument registers, calls `0x02003A20`, and returns the requested length
only if its callee returned that length; otherwise it returns zero.
`0x02003A20` bounds address-plus-length, splits the initial chunk at a 256-byte
boundary and later chunks at 256 bytes, and makes two long calls whose raw
next-PC-relative calculation targets `0x01C00700`. The verified startup copy
maps that address to raw app offset `0x84760`. These are additional write-family
motifs, not independently established API names or hardware execution.

The raw `0x84760` routine contains a byte loop and passes the value 2 to a
shared callee. Some of its relative call destinations in the linear listing
precede the identified copy's raw start `0x84060`. Blindly translating all of
those calls through the one known RAM alias would yield addresses below
`0x01C00000`. Stop there: complete runtime aliasing, instruction interpretation
and reachability remain unresolved. Do not infer RAM closure, controller
semantics or a callable flash writer from this partial trace.

## Target-correct IR review

[verified: coordinator file hash and complete text comparison] Corrected V1.1.9
IR SHA-256 is `1a4b69b08ece41d21f259aadf9311adc6c0f77546765453f593b138d3dc1e8c1`.
It has exactly the same line count as the initial extraction; the only changed
line is line 4, from target triple x86_64-unknown-linux-gnu to pi32v2. No function
body or type-layout text changed. The worker used the explicit firmware target
flags in one bounded Aeon container. This verifies the IR correction, not
machine code or physical ABI behavior.

[reported: worker comparison; verified: coordinator inspected both motifs]
The exact092 cluster matches the SDK defragmentation algorithm in ordered
markers, 256-entry loop, two-byte descriptor and 12-byte area strides, record
length/capacity guard, copy/update, and reset branch. This is a strong
algorithmic correspondence. It still cannot distinguish the two SDK revisions
or establish bank arguments/ownership. V1.1.9 has three literal i8 fields after
its i32 field in _VM_STRUCT; V1.2.13 has four. The initial report's wording
about two flag bytes is superseded; no field meaning follows from that count.

Detailed reviewed comparison (before a wording-only correction from “two bytes”
to “value 2”) is retained as
`scratch/sdk-vm-ir-20261017/analysis-pi32v2.md`, SHA-256
`b5bad8eb82305ad46edd6f6d6a6465dea0a25a269e40e7543ba61073d0d03b0c`.
The next assigned read-only trace identifies candidate vm_init in the 092
0x02033xxx–0x020342xx region and follows concrete callsites/bank arguments.
There is no storage admission or physical recovery claim.

## Initializer boundary correction and record-walk evidence

[verified: coordinator listing inspection and independent exact-byte scan]
The candidate initialization prologue starts at `0x02033F56`; `0x02033F58`
adjusts its stack. No exact little-endian pointer to either appears in the
public app. The sole nearby pointer, `0x02033F60` at raw `0x4C12`, lands inside
the four-byte instruction at `0x02033F5E`; it does not establish an entry.
Worker bounded scans of nearby raw/XIP addresses, both byte orders and decoded
call targets likewise found no caller. Indirect dispatch and linear-sweep
limits remain open. The candidate obtains a local configuration record through
`0x0200383C` with selector 206; numeric area arguments are still unknown.
Corrected Aeon analysis SHA-256:
`d554327f3e2c87f53c975093f0254b6d17d6e77ddea26b10af974c7eb6ffb93a`.

[verified: coordinator inspected decoded instructions] The later walk at
`0x02034186` loads four header bytes, reconstructs twelve length bits, reads
payload at header plus four, and advances by exactly four plus length. The
candidate read body at `0x02034294` checks a below-256 handle helper and reads
the smaller of requested/stored lengths. These strengthen the SDK record-format
correspondence, but neither prove the live API dispatch nor select a flash bank.
SDK-side details and recovery limitations are recorded separately in
`notes/2026-10-17-sdk-vm-record-format.md`. No production decoder or device write
was enabled.
