# macOS CI stale source-pin repair

The captured macOS CI run 38599904562 failed in native packet tests because catalogue provenance pointed at receipt commit 53cd518c417adf34a91b8032de3357d8d9801f0e; that commit records runtime acceptance but does not introduce sim/web/test/demo-songs.json. The catalogue now identifies source-introduction commit 05a8740943e2a158c068ad7a71c862fd5a02f996 for the manifest and keeps the receipt commit separately. Manifest bytes remain verified by SHA-256, so this corrects provenance rather than relaxing the guard. The regression deliberately reads only the source commit's manifest blob and asserts that its commit differs from the receipt; it does not require the receipt commit's parent tree or manifest path to be present in a shallow CI clone.

The packet test then exposed a linked stale-pin chain. tools/fm1_prepare_native_read_packet.py copied the current tools/jieli/audit_link.py, while tools/fm1_sdk_rehearsal.py and its immediate wrapper tools/fm1_bound_sdk_trace.py still expected an older SHA. Updated those two expected hashes and the preparer's exact file pins. The audit implementation itself was not changed. The packet dependency test now checks the rehearsal source pin and the wrapper's rehearsal pin against current bytes.

Current SHA-256 values:

- tools/jieli/audit_link.py: c53c79006090d7d3a7b0ea2383d3fa4c52950eb5cf3921807925708f76453103
- tools/fm1_sdk_rehearsal.py: 9d6f3f60e6a3922ef6a1e42be60ec4c68688937eea05a4cbc32551e6518576d4
- tools/fm1_bound_sdk_trace.py: 139df5d9adcb6c3fe946fb4feb5f9e814b4a928ba230a739a1f3e07774c294d1
- tools/fm1_prepare_native_read_packet.py: b46fb9093138e0884b36f4b5a8abc058294c8989a5f49c5e9f0b11e03df5b007

Validation on Hera used the existing task test venv:

    /home/claude/mvave-fm1/ci-contract-repairs-20261012/.venv/bin/pytest -q tests/test_native_demo_preload_catalogue.py tests/test_native_packet_dependencies.py
    22 passed

Other occurrences of the previous audit SHA remain in independent stop/return-admission tools and an older lifecycle-v1 record. They are intentionally outside this packet's direct dependency chain; do not broadly re-pin them or rewrite historical evidence. This checkpoint did not invoke USB, MIDI, flash, reset, or any hardware path. It does not establish the full macOS CI job result; coordinator should rerun the exact job after integrating this branch.

CI history limit: the Python-tests job used actions/checkout@v4's default depth of one. A reproducible depth-1 clone omitted source commit 05a8740943e2a158c068ad7a71c862fd5a02f996 (`git cat-file -e <commit>^{commit}` failed), so the provenance test's `git show <commit>:sim/web/test/demo-songs.json` failed. A full-history clone contained the source commit and blob and the same test passed. This is missing Git history in CI, not an incorrect source-introduction pin. The Python-tests checkout now sets `fetch-depth: 0`; no other job's checkout behavior changes.

Validation after the workflow fix: the focused depth-1 reproduction failed as expected due to the missing commit; full-history reproduction passed. The focused catalogue and packet dependency tests pass with 22 tests. This does not establish the full GitHub CI result; coordinator should rerun the exact failed job after integration.
