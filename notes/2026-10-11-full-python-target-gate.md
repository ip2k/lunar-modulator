# Complete Python suite after target-reset integration

Personal, non-commercial. Root authorized sixteen isolated Hera chunks on the
current feature head plus frozen target-reset source/tests. This is a source
regression gate, separate from GitHub CI and physical boot/display/recovery.
No hardware, server selection changes, commits or pushes belong to this lane.
Root owns commits and immediate verified push.

The harness under ignored `build/full-python-target-hera/` adapts the existing
`build/recovery-python-shards-entry-bringup` module-balanced sixteen-shard plan,
runner and precise XML node coverage. It archived all tracked current files
plus the three frozen target-reset paths, excluding pending private ROM-stage
probe changes and other untracked work. Both new adapters (install254 and target
resetb846) are included. The exact base commit, archive members/source hashes,
collection, plan and runtime evidence were sealed before execution.

Hera uses the existing pinned recovery image
`sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`.
Each isolated container uses four CPU/four GiB, network none, no devices and
nonprivileged mode. Read-only fixtures provide the actual original private
loader, fixed loader/profile, SDK ELF/app, raw reference files and historical
backup. Each container makes its own mutable modeled backup copy; actual bench
backup directories are not mounted. Tests preserve existing skips for unavailable
reference repositories/artifacts. All full-factory SG operations are mocked.

Status: target107 final independent offline review accepted (report
`build/fixed-target-reset-review.md`, SHA-256
`bb3db9d4653e338d1027b3b0ecd98c565e339926b99c25e1f3e1dfe0107c8c81`).
The full suite completed on Hera; exact coverage and runtime evidence passed. The target
source/test/note were subsequently committed and verified pushed at 45e21964.
Latest independently checked local and remote feature head is
`6b8ed4b277783fb447a5eb03712b8134b93fcd1d`; branch
`feature/2026-10-11@installable-firmware`. Later notes checkpoints do not change
the archived code bytes. Final results and OOM/removal receipts are recorded below; independent
whole-suite review has now independently accepted the sealed evidence.

## Sealed execution snapshot

[verified] Archive base `3cc74bfd5891b58b31730ee572ec34323957611a` plus
exact frozen target adapter/test/note, 1,651 files total; the tools/tests/
pyproject subset is exactly 539 files. Ignored private ROM-stage wrapper333
and untracked diagnostic trial work were excluded. The snapshot records the
actual dirty-file list so base-commit identity is not substituted for bytes.

- `source.tar.gz`: `d94145cca0ac6b1ac378b4d704bfe068b67fa7dfa2c5a58510d226182745c673`.
- `snapshot.json`: `3daf1de6a0385a08be53b7365dd4868590ace2a9362fe306de76a344c9519647`.
- `run.py`: `f619bd404d50f5de5524343733e0f0626b8d6e7605e2d6cbf0a6be135cd250e2`.
- `make-plan.py`: `dab3bbd20d025eb672b10812b395eb996143764325c3be7be5df77b0a43d29fe`.
- `aggregate.py`: `fd5e9f272fdd5f8308822184a97c402f6c767721b8b7891d428f7f734d786db3`.

Remote root: `/home/claude/mvave-fm1/full-python-target-20261011-3cc74bfd`.
[verified] Remote read-only fixture pins before launch: original loader
`d41da6126760c9d66660bcc0cac8d27d221806c5e369a8036921efe68dca5376`,
SDK ELF `8832aa4677a7da3aa7871da58a092e5c3e69d766b31d5e67744301ce437979e2`,
fixed candidate `fe6d1bd36c8ffe4674e4a05ee748fe87480b5867fac58230b14ff089d411012c`,
profile `3c03e413b9df29d85e4c07d886d9bfb9b3ab2fc66845d5220f82998dd44f4afe`.
Archive and extracted member hashes are checked by the remote runner before
collection. The historical foreground SSH runner used terminal session97994; durable
remote `runner.log` and per-container receipts retain the completed execution.

[verified] Collection succeeded: 6,389 unique nodes across 142 modules.
The sixteen module-balanced shards contain 399 or 400 nodes each.
Collection node order SHA-256 is
`93830dd8f6d885dbe4445ee1d771f2c5e9fe77529fc6b81ac43cfc67b0dd9243`;
canonical sorted collection SHA-256 is
`8c90a5c6a54b6f581ddb0a4d4ffb25cce865069115a4865991fe92e3c0c77acb`.
All sixteen shards completed; the longest contained the sequential private-fixture
full rehearsal and ten ambiguous-worker cases. Its result and precise XML
coverage, runtime and removal checks are recorded in final evidence below.

[verified] Frozen target source/tests/note were committed and remote SHA
verified as `45e21964d37fde86330eab65fa4c2866b1951ca6` while this suite ran.
The suite archive remains its exact 3cc74 base plus those same source bytes.
Root reported the subsequent actual backup completed about 557 seconds after
entry, within the unchanged inherited 600-second historical validation cap;
no source cap or physical adapter guard was altered by this lane.

## Separately authorized later fixture selector

[verified] Root changed only `tests/test_sdk_rehearsal.py` after this archive
was sealed, adding seven selector boundary cases and optional-public versus
strict-private behavior. Its latest SHA-256 is
`9bda83603dcffaf92a00f27409c2b200fd5b8cf4669a02c22d61075609e7ef50`.
The archive remains unchanged, including its old rehearsal-test bytes.
Final current-source comparison accepted only that explicitly listed drift
(538 equal current code files and all 539 exact archived source files).
The separate 287-case strict/private and public/default gate is documented in
`notes/2026-10-11-private-fixture-selector-gate.md`; it does not replace the
whole-suite gate or claim the older 6,389 archive contains the new cases.

## Final acceptance evidence

[verified] All 6,389 collected nodes occur exactly once in the sixteen XML
reports: 6,352 passed, 35 skipped and two expected failures, zero failures,
errors or unexpected passes. The two expected failures are the documented
unported Movy undo ring. The 35 skips retain unavailable reference clones,
optional stock artifacts, Node and Python markdown dependency boundaries;
actual private SDK/install/reset factory fixtures did run. The exact skip
nodes and reasons are retained in the independent evidence check.

[verified] The longest shard took 3,172.149 seconds (52 minutes 52 seconds);
all shard elapsed times sum to 5,100.961 seconds. Collection took 4.490
seconds. All seventeen collect/test containers exited zero, were not OOM
killed, had four CPUs/four GiB, network none, no device mounts, nonprivileged
mode and the pinned image. Each has a saved inspect/removal receipt; a fresh
lookup for the exact `lan.session=full-python-target-20261011` label was
empty. These are container observations, not device or host exclusivity proof.

The first aggregation attempt failed after all tests completed because runner
receipts encode the shard index as a string while the aggregator expected an
integer. The original aggregator and failed runner log are preserved. The
ignored evidence-only repair compares the exact expected string, then verifies
all unchanged receipts and XML; no source archive or test was rerun or changed.
The repaired aggregator SHA-256 is
`b44bce46fe5dc484cb52710a2b5aecb72d223c0dd8ca3e29f2fa9aedf3b0954a`.

Final ignored evidence is `build/full-python-target-hera/`:

- `aggregate.json`: `bbf40f7317091e74d8a63cdee571fe2d39ac396371ee476108255ccee156eceb`.
- `independent-evidence-check.json`: `d29bb41bfeb12d226a627314494140c61a74e31d7ff45c5498badcec8c2f9657`.
- `removal-lookup.jsonl`: empty fresh exact-label container lookup.
- `evidence/`: all seventeen run/inspect/removal receipts and sixteen exact XML/log sets.

[verified] All 1,651 archive member pins and all 539 archived tools/tests/config
pins match. Current 538 code files still match; the only changed tracked code
file is the explicitly authorized fixture selector 9bda, independently accepted
in `build/sdk-ci-private-fixture-review.md` at
`ccfbba14400af1b8b12a8443b75efe7311639291455ce56ce39a6edbc60da1f1`.
Local and remote branch SHA were freshly compared and equal at
`6b8ed4b277783fb447a5eb03712b8134b93fcd1d` before this note update.

[verified] Independent final whole-suite review accepted the exact archive,
coverage and seventeen runtime/removal receipts in
`build/full-python-target-independent-review.md`, SHA-256
`accf41c441742d899a195a57fd5fe006c746eb5e6b490e53f043abebfb96fe62`.
Root owns checkpoint/push
of this note and later CI. Pending returned-ROM provenance/backup/restore and
ROM probe sources were excluded from this older archive; they require their
own frozen focused gates. This acceptance does not establish diagnostic boot,
display behavior, physical recovery, or firmware installability by itself.
