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
full dispatch reachability and selected flash banks still require tracing.
The earlier failed searches for pointers to zero-origin labels do not show
unreachability. In particular, 0x02033F60 is not an asserted VM entry and
its target must be interpreted using the corrected origin.

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
