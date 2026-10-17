# Exact FM-1_092 VM candidate markers

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
