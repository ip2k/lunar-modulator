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
