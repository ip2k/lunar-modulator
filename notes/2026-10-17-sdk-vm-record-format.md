# Candidate SDK VM record format and recovery limits

[verified: offline IR inspection] Compared the target-correct pinned SDK VM
members described in `2026-10-17-092-vm-candidate-markers.md`. V1.1.9 IR SHA-256:
`1a4b69b08ece41d21f259aadf9311adc6c0f77546765453f593b138d3dc1e8c1`;
V1.2.13 IR SHA-256:
`925f950b62527d3b3476085fb8729bd75652ddd5bd6fdfd5b0b332edcd804167`.
The full vendor IR remains ignored. These are SDK facts, not an identification
of the owner's FM-1_092 storage reader, bank boundaries or live flash contents.

Both write paths pack four header bytes followed by the payload:

| Byte | Encoded value |
| --- | --- |
| 0 | Low eight bits of CRC16 over the complete logical payload |
| 1 | Handle bits 0–7 |
| 2, low nibble | Handle bits 8–11 |
| 2, high nibble | Length bits 0–3 |
| 3 | Length bits 4–11 |

The length limit is 4095. Although the encoding has twelve handle bits, both
`vm_check_hdl` implementations accept only handles below 256. Record traversal
and append advancement use exactly four plus the decoded length; these paths
do not add alignment padding. Anchors in the retained IR: V1.1.9 lines
1875–1892, 2182–2200, 2305–2340; V1.2.13 lines 2143–2162, 2449–2467,
1241–1249 and 2556–2607.

[verified: reader and writer control flow] Reads compute the CRC over the
smaller of requested and stored lengths, but compare its low byte with the
header's full-payload CRC byte. A partial read therefore generally fails the
comparison; an eight-bit collision can pass. It is not an independently
validated prefix. See V1.1.9 lines 2518–2531 and V1.2.13 lines 2787–2799.
The CRC16 implementation and parameters have not been established here.

Both writers call the header write before the optional payload write, then
update the RAM index and end pointer. Both ignore the `sfc_write` return values.
This establishes call order, not successful persistence, a commit-last record,
or crash safety. Updates append records; old bytes remain until area erase or
defragmentation. A zero-length write can append a header, but these bounded
functions do not establish a supported delete/tombstone API.

V1.1.9 checks area occupancy through mapped flash; V1.2.13 also supports an
external-read path. Area state and defragmentation must be understood in
addition to the common record encoding. No production decoder, SAVE admission,
format or device operation follows from this comparison.

Next prove the exact 092 reader's byte loads and record advancement, then its
selected range and bank semantics against retained independent flash evidence.
Recovery, fresh paired reads and rollback gates remain required. Worker detail:
`scratch/sdk-vm-record-format-20261017/HANDOFF.md`; coordinator independently
inspected handle bounds, unused write results and the bounded read CRC path.

## Exact 092 reader corroboration (corrected linked origin)

[verified: coordinator-reviewed decoded instructions] The corrected-origin
092 listing pinned in `2026-10-17-092-disassembly-review.md` corroborates the
four-byte header packing and `4 + stored_length` record walk at
`0x020342A6`–`0x0203431A`. The scan extracts the ID as
`((byte2 << 8) & 0xF00) | byte1`. The candidate read callback at
`0x020343B4` calls the helper at `0x020343A8`, which rejects API IDs >=256.
It reads payload at header+4 with `min(stored_length, requested_length)` and
compares the checksum result against header byte0 at `0x02034468`–`0x0203446C`.
The wrapper returns an unsigned low halfword; the caller's `0xFFFF00FF` mask
therefore reduces this comparison to eight bits. This matches the bounded SDK
reader behavior, including its partial-read limitation. It does not identify
all call paths, runtime mode, bank contents, ownership or reuse authority.

Ignored detailed report:
`scratch/sdk-vm-record-format-20261017/reader-match-corrected-origin.md`, SHA-256
`3db314f8481b3eccf40d706dc9f01cd65a15f83bcbb5771723051b9a5d6e9d68`.
Earlier zero-origin addresses in the old reader report are superseded.

## CRC archive follow-up

[verified: worker pinned-object IR inspection; coordinator report review]
Both pinned SDK `cpu.a` archives contain `crc16.c.o`. Their hardware wrappers
write a zero seed at `0x13504`, feed bytes at `0x13500`, synchronize, and read
the result. The V1.2.13 software fallback uses an XMODEM-style `0x1021`
non-reflected recurrence with zero initial/default state and no visible final
xor. This software path does not specify the hardware polynomial or settings.
The exact 092 wrapper at `0x0200270A` has matching seed/feed/sync operations.
Its final parallel packet assigns `r0=r4` while loading `r5=[r0+4]`; validating
old-register packet semantics is still required before treating that load as a
read of the CRC result register. No hardware CRC algorithm or live-record
validity is established here.

Ignored report `scratch/vm-crc-source-20261017/HANDOFF.md`, SHA-256
`87a32b064cf0c553647170676a354645f1570443bea31da4806a5a069e2a809e`.
Next: corroborate packet semantics, then use authoritative peripheral or known
input/output evidence for the exact hardware CRC. No decoder or SAVE authority
is added by an SDK fallback match.

### Parallel-packet compiler corroboration

[verified: pinned compiler output; coordinator report review] An independent
volatile-load-then-call C probe compiled on Aeon with the pinned pi32v2 r3
clang emits `r0 = r1 # r4 = h[r0+4]`. Its C semantics require the load to use
the original pointer while the call receives a different pointer. This
corroborates the compiler's expectation that the 092 wrapper's parallel packet
reads old `r0+4`, consistent with the CRC result register. It is compiler
expectation evidence, not an independent silicon or ISA-manual verification.
The probe uses a halfword load; the 092 packet uses a word load. No CRC
polynomial, live record validity or storage reuse authority follows.

Probe source/IR/assembly/disassembly and exact commands are retained in
`scratch/vm-crc-source-20261017/packet-semantics/`; the report above now has an
appended section. The earlier report hash pins its earlier revision only.
Aeon coordination handoff `lunar--vm-crc-packet-semantics-20261017.md` has
SHA-256 `4deb2e27eaff03727b2f698be57e940c8e71bf5bd33c7053a52d997d0b8610ec`.
