# Selected Trio v2 private V15 memory candidate

Personal, non-commercial MIT adapter, based on exact coordinator
`9a3b097f1accc84a4312a30716e73186fa2e7ba1`. Source implementation only;
no real vendor input, build, service, browser, transport or device use.

`tools/installer_service/selected_v15_package_candidate.py` accepts actual
request/receipt/app/ELF bytes, independently acquired operator
`selected_trio_profile.TrustedInputs`, and an explicitly pinned V15 donor plus
seven reference byte inputs. It calls the unchanged v2 receipt validator and
original V15 model `_build` / independent `verify_replacement`, with original
package/nested/version checks. It does not use the old generic diagnostic
report, expanded-D7000 tuples or identity translation. Legacy packagers,
request/receipt validators, models, builder and application are unchanged.

The caller supplies an existing owner-only scratch root. Only a fresh private
child containing the seven bounded references is materialized; it is removed
before successful return or propagation of a failure. Immutable byte inputs
prevent repeated inspector reads from observing a changing reference tree.
No candidate file is written. The operator owns the returned bytes and their
private lifetime. No default `/tmp`, implicit input discovery, CLI or route.

The distinct report says `candidate_returned_in_memory=true`,
`file_written=false` (candidate file), and `transport_used=false`. The nested
original model report retains its own `binary_emitted=false`. Every hardware,
install, package, release, distribution and ROM-return admission flag stays
false. Structural verification grants no admission.

The exact original FM-1_015 identity, SPL/config/OTA, resource/layout/partition
metadata, auxiliary bytes, opaque trailer and unused old app tail remain
unchanged. Only the app prefix, child size and established enclosing CRC fields
may change. Same-identity diagnostic packaging is deliberately non-installable;
no runtime identity/update service or recovery acceptance is inferred. There
is no identity override, cfg bump or erased-tail assumption.

Donor pins are the previously recorded official V15 FWSC (699956 bytes,
`db1642b2b6fa5c2cccb11ffd13878068bb28601678d3644049f99dc40e7edb8a`),
original 581564-byte app, pinned stock SPL and OTA. The original version checker
pins the opaque trailer. The operator record must include the exact size/hash
of all seven references, acquisition provenance and protected-input approval
record. Those record names document external trust; a string is not proof of
approval. The full donor and mandatory component pins cannot be overridden by
that record. References are individually capped at 1 MiB and aggregate 2 MiB;
request/receipt/ELF/app bounds are the unchanged selected-v2 bounds.

Existing source evidence: `notes/2026-09-06-bench.md` §5,
`notes/2026-10-09-offline-app-replacement.md`,
`notes/2026-10-09-version-trailer-contract.md`, and `package_guard.py`.
MIT model/reader provenance credits kagaimiq's jl-misctools and AL-255.
The selected SDK-free app is GPL-3.0-only under its existing validated source
pins. That does not establish redistribution rights for proprietary donor
SPL/config/OTA/resources; binaries and private inputs stay out of Git.

Before any future real-input run, locate the exact existing V15 protected
unpack/decode approval or obtain and record the narrowly scoped approval. The
explicit tracked approval located for 2026-10-22 covers the dev board/SDK,
not an inferred new V15 scope. Independently acquire/freeze the remaining
reference hashes (config/cfg/cfg-tool/EQ) and actual operator build evidence.
The prior 5197 job's binaries/objects were intentionally cleaned after root
verification; reports alone cannot replace them. No real-input test is enabled
implicitly by this module or its tests.

Focused tests use an invented full-sized donor, test-local hash substitutions,
actual v2 synthetic ELF evidence, and the original unmodified structural
readers/guard/model. They cover independent trust mismatch before donor decode,
bounds/reference/record refusals, private scratch and cleanup failures, app
extent limits, repaired-CRC preservation failures and legacy cross-profile
refusal. These are source/format proofs, never target execution or installer
acceptance. Exact commands/results are recorded in the ignored lane scratch;
final results will be added after the focused run.

Rarefaction orient/scope and Serena navigation agreed on the existing primary
checkout's verifier. The isolated external worktree is outside their shared
root; exact-base file inspection and focused tests provide the new-file proof.
No global semantic project switch or restart. Test products live only in
`scratch/selected-v15-private-package/` and are removed after results are saved.
