# Operator-owned continuous build tuple capture

This tooling captures provenance for one private expanded-D7000 continuous
FM-1 candidate. It snapshots the source, catalogue, and toolchain trees; pins
the container image and inspected configuration; and records hashes for the
request, prepared profile, app, ELF, receipts, and linked inputs. The resulting
tuple is diagnostic build evidence only: storage admission, hardware testing,
installability, and release acceptance remain false.

The tuple contract is now schema 2. Its toolchain_tree_sha256 binds the
complete mounted toolchain tree, while build-provenance.json deliberately
remains schema 1 because its field contract did not change. The trusted
package consumer accepts only exact schema-2 tuples and rejects legacy schema-1
tuples; it still requires an externally supplied digest of the canonical tuple
as the trust anchor. A format upgrade does not retroactively bless or rewrite
older retained tuple bytes.

The retained 2026-10-14 build was captured before this schema change. Its
on-disk build_tuple.json remains schema 1 with raw SHA-256
9c246fb70bfb04cb6a6adbaf845fe71a882ba0228317b286f648b502b2e66ec4.
The tests preserve those bytes, verify that the consumer rejects them, and
construct a canonical schema-2 in-memory fixture for package-path testing.
That fixture digest is
247c8ded29a33a014cec82f7dafc548e718ad9d576107e3f3453388c4c9cd19a;
it is test-only and is not a newly captured operator tuple. A fresh successful
capture under the schema-2 producer has not yet been recorded.

The selected workload in the retained build is Event Horizon plus its
companion SET, Shapes8, D7000, continuous FM-1_500 identity and FM-1_000
recovery identity. That is build provenance, not package release or hardware
acceptance.

Focused validation for the schema update:
- tests/test_native_continuous_tuple_capture.py covers canonical schema-2
  envelope creation and independent provenance schema versioning.
- tests/test_trusted_fwsc_package.py refuses legacy schema 1, accepts only
  externally pinned schema 2, preserves all false admission flags, and tests
  the retained package inputs without modifying their on-disk receipts.
