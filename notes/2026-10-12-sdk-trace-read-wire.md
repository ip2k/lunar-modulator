# Fixed trace-read wire and native replay

Personal, non-commercial; root owns hardware, commits and pushes. This separate
evidence-only source preserves the existing 8fb two-read verifier and all frozen
boot, reader, SG, capture, backup and restore sources. Shared semantic backends
select the primary checkout; no retarget/restart was attempted. Worktree file
inspection and AST parsing are the fallback, not device ABI verification.

Before implementation: an actual SG completion hash, a USBmon response prefix
and an owned capture lifecycle are different evidence. USBmon text displays at
most32 bytes of a64-byte trace; it cannot independently prove the full record.
Source2b787 emits no ordinary successful close event. An ioctl intent/return
alone cannot establish that the response/status was accepted by the reader.

Saved `tools/fm1_sdk_trace_read_wire.py` supplies pure native-log cross-check and
fixed five-read BOT replay. Exact operations are INQUIRY36 followed by trace64,
stage4, trace64, stage4 at the ELF-derived candidate addresses01c02880/01c03418.
Native replay cross-checks ordered ioctl intents with outer request/completion
times, one bound FD identity, source-owned exception/open/binding/close failures
and no later ioctl after failure. Missing native evidence cannot imply success.

Wire replay checks one bound ROM USB address, endpoint1, exact31-byte CBWs,
direction/LUN/CDB sizes, paired URB tokens/status/lengths, matching tag and
zero-residue CSW. It accepts exact kernel TUR, solicited sense, INQUIRY and
rejected PREVENT followed by illegal-field sense. Vendor reads must follow the
exact recorded native prefix; reset, upload, NOR/eFuse, OUT payloads, reordered
or repeated reads, unexplained sense and malformed records fail. A stopped
terminal read transfer retains ambiguity. An empty consumed-pretransport route
requires zero relevant bulk requests. Actually published replies can verify
displayed prefixes, with no claim to process attribution or full64-byte wire data.

After implementation: this module has no opener, marker, mutable authority
registry or returned-proof factory. Every result retains false CPU boot,
reset cause, process origin, full trace bytes and returned-proof claims. The
future returned factory must independently replay actual reader/publication
files and owned lifecycle, freeze sources/evidence/absences and preserve the
registered boot lineage plus original journal. Historical snapshots stay fixed;
fresh live witness remains the later backup opener's separate gate.

The final source is frozen at
`68abb2e35350fd0ca70e985d4a2cd9562a6540af6b023cd565ba1f9bda4ecadc`;
V3 tests are
`9fe01660bccfabae3fb599f62ed3b10dd6692b8ab5dfadde2e2cc5ce9e67cb48`.
AST parsing passed. The source never changed during the three test gates.
V1 had two test-owned failures: a CSW-tag corruption set the byte to its already
valid value, and a return placed inside `pytest.raises` was skipped after the
expected exception. V2 repaired the first; V3 repaired the second. All original
archives, XML and failed receipts remain under `build/sdk-trace-read-wire-hera`.
Those failures are not accepted verifier evidence.

Final V3 passed 91 unique cases in 30 nonempty chunks (one chunk of four and
29 of three), plus one exact smoke case, with zero failures/errors/skips.
Author replay verified all 1,742 regular archive file pins, ordered exact XML
coverage without duplicates, all 32 collection/smoke/shard container inspections,
exit0/no OOM, named removal receipts and a fresh structured empty-label lookup.
The exact image was
`sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`;
each container had 2 CPUs, 2 GiB memory and 4 GiB combined memory/swap allowance,
read-only source, no network, no devices and no privilege. Heavy execution was
only on Hera; no physical command occurred.

The retained remote directory is
`/home/claude/mvave-fm1/sdk-trace-read-wire-20261012`.
Local final artifacts and SHA256:

- `source-v3.tar.gz`: `5e18e3baaf3a31ccb7909b4a86d03e79777222b8aac88ab140887d61f933519b`
- `snapshot-v3.json`: `32dddc14e9e418f86c5191c33c328f23c0a12d04d5dddad7403070a7320ba3ac`
- `run-v3.py`: `d880c6dc4c3f58b8e6ca0ed92ad94b70e6dc05282e22c9bba7007bbdda8417f4`
- `plan-v3.json`: `f1de562bdbcec488ac3b7900441d24b5d3a7d87b09b53722d97dc01d65f3840e`
- `aggregate-v3.json`: `27fa861f75e30b2ee60ef5877749969a4819b49c1f727f74df0d1b308c2c736e`
- `cleanup-v3.json`: `2216d68ddf16831121d8a106420f652f489002386ef70d2167aa3068ff521a18`
- `author-check-v3.json`: `88f91e869a855630205d15431b84d703343f711269cbd53dc94d19b631ce6e50`

Independent V3 source/runtime acceptance is retained in
`build/sdk-trace-read-wire-hera/independent-review.md`, SHA256
`68b7a041b4820c97dcc42dd45e5e5fc8e4882080d2e2842a7da69ffd97038355`;
its independent replay is `2369b8e38d364ee0c8a5d1741cfa01486b9849466231b43869469e8c670f05ea`.
This gate models fixed
transcripts; it grants no opener, returned proof, CPU/reset cause or full trace
wire proof. Actual native receipt and capture integration must still use exact
accepted boot/read/native sources, registry lineage, source/receipt freezes and
negative evidence. Original snapshot timestamps cannot be refreshed.

Branch `feature/2026-10-11@installable-firmware`; current checkpoint HEAD is
`4c9120efcfb57bf6391ca0b9e8b83a8d4c7f7842` (parent owns remote verification).
Root must checkpoint these three new files and verify its push. Next dependency:
independent wire/native replay acceptance, then genuine original-path private
lineage before the always-closed returned-state factory can admit actual files.
SPL behavior after corrupted/partial apps and physical USB_KEY remain open.


The V5 narrow regression successor passed 96 unique cases in 30 nonempty
chunks (six of four, twenty-four of three), plus one smoke case. All 1,742
archive pins and ordered XML records match; all 32 inspections have exit0,
no OOM, the same pinned image, 2 CPUs / 2 GiB / 4 GiB combined memory/swap,
source/jobs read-only, no network/devices/privilege. Named removals and a fresh
structured empty-label lookup are retained. V4's five new cases failed before
constructor execution because the test imported the module without its `tools`
namespace. V5 changes only that test import; V4 failure receipts remain intact.

Five V5 cases invoke the actual frozen `2b7872d7...` native constructor and
real temporary journal, with fabricated private test permit and mocked device
syscalls. Initial mapping/open/lock failures persist open-intent/open-failed;
regular-FD/identity failures persist open-intent/binding-failed. The latter
binding failure closes the journal before the constructor's later log attempt,
so no durable open-failed event follows it. The independent reviewer retracted
the earlier combined-event finding. Matcher source `68abb2e...` stayed unchanged.
These tests prove emitted stopped grammar with zero ioctl, not real factory,
loader provenance, device exclusivity or hardware recovery.

V5 tests SHA256:
`10a01b392aa2984ce7d57c20ebc91d98c8de32a8bfb7ab00123a17d4f235189f`.
V5 retained artifacts under `build/sdk-trace-read-wire-hera`:

- `source-v5.tar.gz`: `9e187835a483eca01424449752fd60ec013281086875d2a0a577100cb859b732`
- `snapshot-v5.json`: `d271795bf24f6e2f49a3afc6c9ca3c2b1f4baa0076720d5fcf8776a8017e4d22`
- `run-v5.py`: `46eef1fe060a6ebfb4b58e98caf868e28804576c0e8427faf394ffa6bacc08b8`
- `plan-v5.json`: `0bd69794a8e70657a7bc852fb80ecde06127e0b01823abe859dc4b2249e0f819`
- `aggregate-v5.json`: `0ee02b1362b37609ad9ebffd04e2dee982270a4a39da16344cab523b03463585`
- `cleanup-v5.json`: `374837b74eec09f285588d39d7be564bbd09dd298927ff930634dd7c0991728d`
- `author-check-v5.json`: `3cdb1902662a1cafd91e19797654bd77363bf68552d405ec066cfa0d01b79394`

V5 independent narrow addendum is pending. The three new matcher files remain
for root's checkpoint/push; current verified parent checkpoint is `4c9120ef...`.
The next distinct admission source must remain closed until canonical boot,
reader/native and owned capture/wire lineage are independently accepted.
