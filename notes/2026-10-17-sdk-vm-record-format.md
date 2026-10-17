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
