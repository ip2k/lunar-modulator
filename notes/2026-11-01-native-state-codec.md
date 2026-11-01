# Bounded native state codec work — 2026-11-01

Offline codec phase, not persistence or native admission. Personal MIT work.
Base e267d7cd58efef29afb2c0c38562f4878e8106f5 includes the independently reviewed
PROJECT oversized-SEQS refusal. Later phases must add current PROJECT canonical
replay and an offline fake transaction. Production SAVE/UI/storage stays unbound.

The ordinary and compact writers share one record encoder. Explicit backing
pointers replace private inline host buffers; the public opaque API and its
queried allocation contract remain. Current callers in render_state, seq_tool,
state_tool and fuzz query size; fm1_app_state checks both writers against its
480 KiB scratch phase. No hardcoded old writer size was found. Host backing
retains all old capacities and compression. Compact backing streams SEQS/CLIP
and counts invalid non-line tails up to the original logical 65536-byte cap;
tag limits still fail at close, on the same record. The format is unchanged:
minimal directory 36+20*N, producer/version unchanged, zero alignment padding.

Pass1 has no sink. Its completed separate manifest holds expected metadata,
chunk lengths/CRCs and a normalized record trace. Pass2 uses an uncommitted
seekable callback, compares the manifest, emits directory then header last.
Short writes poison that replay; the caller must abort, with no codec retry.
Readback matching compares the entire frozen header/directory, payload CRCs,
zero gaps and exact extent. Semantic validation and commit are separate gates.
The manifest is immutable and must outlive both phases/readback. Source ownership
must cover the entire transaction; CRCs are not locks or authentication.

[verified, host only] 387 cases compare full reports, first failing
record and byte output with the ordinary writer AND with state_bin.c compiled
from exact base e267d7cd. Includes raw/typed/fragmented lines, logical/tag/file
caps, module data, FM6 voices, BROW, golden binary files, short sink writes and
readback corruption. Initial host sizes: compact43856, manifest1072, host289616.
Normal and ASan/UBSan runs pass against the exact old TU. JSON-driven refusal
reports also match line/column/path/offset/near and counters, including delayed
chunk-cap errors. Host DEFLATED bytes/reports match the old TU on directed cases.

[verified, target object only] Existing pinned pi32v2 clang (r3/fprev1, -Oz)
compiled state_bin.c: compact43784, manifest1072, host289548 bytes, read from
vendor objdump return immediates. The compiler rejects -fstack-usage; exact
disassembly is retained privately for subsequent call-chain accounting. Two
unchanged read_browser signed-comparison warnings were retained with
-Wno-error=sign-compare. No other warnings. No
native budget/ABI/stack/link/real-storage/atomic-live-load claim is made.

MIT historical cccd21cc5dc82859ed8a5d84f0a7a40646d07353 informed the small
encoded-line strategy; current code keeps current BROW and exact old cap timing.
No GPL store source was copied. New code does not adopt the historical1316-byte
reserved directory or its smaller early SEQS rejection.

Code intelligence: both servers remain on primary absolute checkout. Rarefaction
rejects sibling worktree project paths; its primary fallback has no compilation
database. Serena absolute lookup returns a symbol but inconsistent body bounds.
Exact new-worktree source/caller reads are authority; shared roots unchanged.

Reproduce: FM1_CODEC_BASELINE_SOURCE=<exact-old-state_bin.c> python -m pytest
-q -s tests/test_state_two_pass.py --basetemp=scratch/native-state-20261101/pytest.
Omit the optional baseline path for current host comparison. Tests remove their
own compiler products. Retain logs/receipts; clean own scratch objects before
handoff. Independent phase review by audit_effects is still required.
