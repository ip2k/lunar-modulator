# Exact FM-1_092 disassembly: corrected linked address model

## Correction, 2026-10-17 UTC

[verified: exact public bytes, decoded operands and pointer table] The linked
address model supported by this 092 app is **0x02000120 + raw app offset**.
The earlier conclusion using origin 0x02000000 relied on V15 boot-analysis
inference and is superseded. No hardware action relied on that conclusion.
Package metadata alone was insufficient; the independent checks below resolve
absolute data references and function pointers consistently.

The public app is 691,744 bytes, SHA-256
`9c5a44706b7686746b389e3e8fe6ff051fc50028f9b708ac59f493300f793a7b`.
The complete retained listing using base 0x02000120 is
`scratch/fm1-092-objdump-20261017/FM-1_092-app-linear-code-data-sweep.txt`,
13,641,034 bytes, SHA-256
`d4e79e9c77d87f7ee5e999c3182d7156f6e83a0b223902c61a8139ad5bf81f0b`.
Its original rejection was incorrect: raw byte zero is present at 0x02000120;
placing it there does not omit the first 0x120 bytes.

## Independent address consistency checks

[verified: coordinator byte inspection] One decoded base literal is
0x0204E17C. Subtracting 0x02000120 gives raw 0x4E05C, the token `vm`.
The same literal plus offsets 1587, 1520 and 53 resolves respectively to
`app_area_head` at raw 0x4E68F, `EXT_RESERVED` at 0x4E64C, and `res` at
0x4E091. The former zero-origin interpretation instead reached unrelated
binary data or the middle of other strings.

[verified: little-endian pointer bytes and decoded prologues] A contiguous
seven-pointer table has the following first four values:

| Raw pointer offset | Absolute pointer | Raw target offset |
| --- | --- | --- |
| 0x8300C | 0x02034076 | 0x33F56 |
| 0x83010 | 0x0203439A | 0x3427A |
| 0x83014 | 0x020343B4 | 0x34294 |
| 0x83018 | 0x020344A4 | 0x34384 |

The last three entries are zero. These values target the candidate VM init,
ID-check, read and write routines respectively under the corrected model,
matching the SDK operation-table order. This strengthens their identification;
the callback dispatch is now traced below; actual selected flash banks still require runtime evidence.
The earlier failed searches for pointers to zero-origin labels do not show
unreachability. In particular, 0x02033F60 is not an asserted VM entry and
its target must be interpreted using the corrected origin.

## Independent strict package-header check

[verified: coordinator, 2026-10-17 UTC] The existing strict parser
`tools/jieli/model_092_app_replacement.py` accepted the exact public package
through `_outer_parse(..., legacy_092=True)` and `_flash_parse(...)` against
its pinned unpack reference. Package SHA-256:
`ed8415f32f5e2ff5558a24cee45eafd8d0a5b1982af14d4cb88ba019b876eb80`.
The decoded app hash matches the value above. The `app_area_head` record has
address `0x02000120`, and its `app.bin` child has relative address `0x120`.
The VM child has address `0xD9000`, size `0x10000`, flags `0x12`; BTIF has
address `0xE9000`, size `0x1000`; USR has address `0xEA000`, size `0x12000`.
These are validated package descriptors, not measured runtime bank selection
or permission to erase their contents. This read-only check performs no
firmware compilation, device access or vendor-code execution.

## Callback dispatch and conditional VM extent

[verified: exact pointer bytes and coordinator-reviewed decoded instructions]
The dispatcher at `0x020347EC` walks `[0x02083110, 0x02083164)` in
28-byte steps and invokes each nonzero first field. The second record begins
at `0x0208312C` and contains the four pointers tabulated above. Separate
read/write-shaped dispatchers at `0x020027A0` and `0x020033E8` use field +4
as a predicate before invoking fields +8 and +12. Startup at `0x02004D6E`
invokes the preceding callback range containing `0x0202ADDE`, then the pointer
to `0x020347EC`. This establishes static dispatch order, not observed boot.

[verified: bounded source/disassembly comparison] The `0x0202ADDE` callback
walks 32-byte directory records with its cursor at record+8. It compares the
name at cursor+8 against `vm` through an ASCII case-normalizing helper, then
copies cursor-4 and cursor+0 (record address and size) to VM-info +4 and +12.
Selector 205 submits this record; selector 206 retrieves it for the candidate
initializer. Exact SDK linkage and complete parser behavior remain unproven.

[verified: coordinator instruction review; conditional arithmetic inferred]
The initializer at `0x02034076` caps size at 8192 when VM-info byte 0 equals
1, otherwise at 16384, then rejects sizes below 512. At `0x020340C2`–CE,
`r5` becomes zero when `(clamped_size >> 14)` is zero, otherwise one. It is
**not** an unconditional nonzero/max(1, ...) value. For the public descriptor's
65536-byte size, mode 1 therefore follows the 256-byte-start / 512-byte-span
alignment path with an 8192-byte cap; other modes follow the 4096-byte-start /
8192-byte-span path with a 16384-byte clamped input. Both paths halve their
computed extent into the internal structure. Conditional on successful init
and the exact descriptor, the aligned start remains `0xD9000`; the two
computed halves would be 4096 or 8192 bytes. Actual mode, live ownership,
other users of the descriptor range and erase authority remain unresolved.

A producer at `0x020001E6` stores the mode byte into `0x01C7FD50` from a
pointer obtained through its input: `b[([input+0])+13]`. The provenance of
that input and complete writes to this state still require tracing; package
flags alone do not establish the mode. These conclusions do not authorize
reusing the remainder of the declared VM range.

## Corrected startup copy

[verified: coordinator reran the corrected hash-pinned verifier] The decoded
source literal is 0x02084060 and the length is 0xA05C (41,052 bytes). Under
the supported model this copies **raw offsets [0x83F40, 0x8DF9C)** to RAM
[0x01C00000, 0x01C0A05C). Source bytes SHA-256:
`ef8ba8b5cfb1765df2f810ba9ced9c8cb4822fc3998a1d90bb8acf67b910bb69`.
The earlier raw range [0x84060, 0x8E0BC) and its hash are superseded.
BSS clear operands still delimit [0x01C0A05C, 0x01C2361C), subject to repeat
instruction semantics. The separate overlay copy length remains zero.

The call at actual 0x0200019E has next PC 0x020001A4 and displacement
-4191000, targeting RAM **0x01C00E8C**. Its copied source remains raw 0x84DCC,
now correctly labelled 0x02084EEC in the app listing; the prologue bytes agree.
The earlier target 0x01C00D6C was shifted by the wrong origin. Similarly,
RAM-call and closure conclusions based on the former origin must be redone.

Corrected ignored verifier `scratch/fm1-092-objdump-20261017/startup-copy-trace.py`
SHA-256: `a08ff2a96b481d1a616a9fcdbd3e75d316d765211f74ea865994cfd76e0adde6`.
Command `python3 -B scratch/fm1-092-objdump-20261017/startup-copy-trace.py`
passed against the exact app and retained 0x02000120 listing.

## Scope

These are static linking and byte-coordinate checks, not observed SPL execution
or a physical recovery witness. Both listings are complete linear code/data
sweeps; neither is a recovered call graph. The 0x02000000 listing remains an
ignored historical artifact, SHA-256
`f62050c81be2ff7e1f5645873bc47ca07c52c7a95b9e7752b5792a5a181767d8`.
Its labels must be treated only as raw offsets plus a display bias, never as
validated runtime addresses. Old suffix/reference scans using that bias need
rechecking. SDK IR format facts do not depend on this correction.

No vendor binary or full listing is committed. Heavy tooling ran in bounded
Aeon containers; no Hera or hardware write occurred. Storage ownership,
format/SAVE admission, migration, rollback, recovery and performance acceptance
remain open. See the candidate-marker note for the evolving VM trace.

## Stock SPL identity and remaining launch boundary

[verified: worker byte comparison; coordinator reviewed report and digest]
The retained Aeon V1.1.9 ELF's `.fw` section is 14,384 bytes and matches the
public 092 package's `top/uboot.boot` byte for byte, SHA-256
`730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef`.
The ELF hash is
`ef295427531a7bc66562ebbe3809794e23ecf7b071e01c7d4c446ccc2df3b0d3`;
its retained listing hash is
`3278f3645a956cb1f9e9c1726d269fb9a9046efa63397ed0c85cd912e2bc5ac4`.
This resolves artifact provenance, not the app launch ABI. Bounded examination
of four register-indirect calls did not tie any to the app transfer or establish
incoming `r0`. The mode byte and mode-dependent VM extent remain conditional.
A proven launch contract or trace through the SPL/ROM-to-app boundary is still
needed. No runtime, flash or bank-reuse authority follows from the identity.

Aeon report under coordination tasks:
`mvave-fm1-spl-entry-contract-20261017/spl-entry-r0-review.md`, SHA-256
`3400ebd62e7c38c06eb8ef4ee62d01a1039f74e26e8dfcbaf1dab1913d1f540b`.
No hardware actions or new builds occurred.


## Historical marker cross-check and explicit conditional ranges

[verified: bounded instruction/SDK IR comparison; conditional ranges inferred]
The follow-up review confirms `umin` at `0x020340B4` is an unsigned minimum,
consistent with the pinned V1.1.9 `vm_init` IR's unsigned comparisons/selects.
For descriptor base `0xD9000`, already aligned to both supported start
boundaries, mode 1 computes total span `0x2000`, with halves
`[0xD9000,0xDA000)` and `[0xDA000,0xDB000)`. Other modes compute total span
`0x4000`, with halves `[0xD9000,0xDB000)` and `[0xDB000,0xDD000)`.
These remain conditional on the traced initializer receiving the descriptor
and completing; the runtime mode and active bank were not observed.

[verified: read-only historical image inventory] The matching retained
2026-10-07 backup pair has a marker and candidate records at `0xE8000`,
outside both computed extents. This is the descriptor's final sector start,
not its exclusive endpoint `0xE9000`. It cannot be classified as an active
bank, an end marker or safely reusable residual data from location alone.
The historical record/CRC results are in
`2026-10-17-sdk-vm-record-format.md`. No live ownership or erase authority is
established, and the unexplained second location must remain preserved.


[verified: coordinator reran existing strict raw-image parser] The historical
backup's decoded guarded components byte-match the public 092 reference via
`tools/jieli/raw_flash_profile.py::_parse`. The app SHA-256 is
`9c5a44706b7686746b389e3e8fe6ff051fc50028f9b708ac59f493300f793a7b`,
the exact app used for this instruction analysis. Thus the unexplained E8000
records coexist in the historical image with the analyzed app; a mismatched
app binary does not explain them. This still does not establish activation,
mode, another user's ownership, or how those records were written.

The bank review's Aeon handoff is
`/home/claude/.local/share/codex-coordination/handoffs/mvave-fm1-bank-span-recheck-20261017.md`,
SHA-256 `0f6360e1be03c93a76937335edd8e3bf7aaaf49cdb52e960be8084d7b994cc59`;
its claim is released. No build or device action was performed.


## Initializer-called tail copy can mutate flash

[verified: bounded decoded control/data flow; low-level role inferred] The
initializer calls `0x02029776` at `0x0203416A`, after installing its two-range
context. This routine retrieves selector 206 VM-info and checks metadata near
the descriptor end, with a fallback scan. It can require a `0x55AAAA55` marker,
issue operations through `0x02003B1A`, and copy via `0x02028FF8`. It must not be
classified as read-only or treated as proof that the tail is unused.

[verified: coordinator read exact public-app words] The six words beginning at
runtime `0x0204E6F0` (raw `0x4E5D0`) are masks `FFFF0000`, `FFFFF000`,
`FFFFFF00`, followed by selectors 201, 200, 204. Thus operation 2 aligns to
4 KiB and dispatches selector 200; operation 3 aligns to 256 bytes and
dispatches selector 204. The pinned SDK V1.1.9 commit
`8eae66452ce4c34d64ad38a2764ba1c0610900e3`, header
`include_lib/driver/device/ioctl_cmds.h`, names these selectors
`IOCTL_ERASE_SECTOR` and `IOCTL_ERASE_PAGE`; selector 205, not 204, is
`IOCTL_SET_VM_INFO`. Header names are SDK intent, not observed silicon effects.

[verified: coordinator recomputed calls and mapped copied bytes] The six-byte
relative calls at `0x02003B84` and `0x02003BA4` target RAM `0x01C00820`:
`call_PC + 6 + signed_displacement`. With the verified startup copy, that maps
to source `0x02084880` / raw `0x84760`. Do not subtract `0x120` from an already
runtime RAM target: the incorrect `0x01C00700` falls inside a different body.
The selector path call at `0x020039D2` targets RAM `0x01C005E4`, mapping to
source `0x02084644` / raw `0x84524`.

The first RAM body includes selector-minus-200 dispatch, a 4096-byte default
and output value `0x20`, with a 256-byte/`0x81` alternative. The writer body
outputs `0x02`, an address and source bytes through shared helpers. Together
with the command dispatch and buffer direction, this strongly supports a
flash erase/program migration path rather than RAM memcpy. Complete helper
semantics, branch prerequisites, actual selected addresses, runtime activation
and historical E8000 provenance remain unproven. No new hardware operation or
storage admission follows. Preserve the descriptor tail and unknown records.
