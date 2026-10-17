# Interrupted install and reconnect recovery audit

**Scope:** bounded source/test review of the mutable generic D7000 diagnostic
policy, its injected SG adapter and the transport-independent NOR transaction
core. Audited source checkout: `2b1e93f570dec814d6682fdeb88e4ff0ab800674`
(`5ee4ffc4` host-reader change is in that history). No device, USB, Hera/Aeon,
or write-admission operation was performed. No tests were run for this note.

## Finding

The transaction core has a recoverable interrupted-write model, but the current
high-level adapter has no reviewed continuation path for an install after a
real transport disconnect and USB re-enumeration. This is a fail-closed
capability gap, not a fail-open write bypass.

`tools/fm1_flash_transaction.py::run_transaction` records a durable intent
before each mutation, stops on ambiguous command failure, and on a later call
reads the complete image, checks bytes outside the authorized ranges, and
rebuilds changed authorized sectors from the sealed target. A `prepared`
transaction additionally requires the complete image to equal the original
paired baseline. Recovery therefore does not trust a journal page cursor.

`tools/native/generic_diagnostic_flash.py::Policy.bind(direction="install")`
requires the original paired-read evidence to remain within its freshness
window and binds the transport against the original exact USB/SG/read mapping.
`tools/native/generic_diagnostic_sg_adapter.py` repeats verification of that
original read bundle for install. The restore direction is different: it
requires a fresh paired full-image read, checks the same stable USB port tuple
(`path`, `busnum`, VID and PID), and binds the newly observed USB devnum and SG
mapping to the transport. The immutable transaction plan and historical unit
identity remain sealed; the observed mapping is supplied separately.

Consequently, the reviewed API can prepare a baseline restore after
re-enumeration, but it cannot continue the interrupted install through that
reconnect path. If the original read expires, the install bind also rejects.
The transaction-core docstring's “reconnect/re-enter ROM” statement is accurate
for its injected session contract, but should not be read as evidence that the
current physical adapter can reacquire and resume an install after reconnect.

The transaction core's recovery admission is also **authorized-range bounded,
not exact-operation-prefix bounded**. When the journal is no longer `prepared`,
`run_transaction` checks that bytes outside `writable_ranges` still match the
sealed baseline, then converges every differing sector in those ranges to the
requested target or baseline. It does not compare the observed in-range bytes
with the exact prefix implied by `journal.intent`, direction and prior durable
sector records. This may be a deliberate repair policy: a test explicitly
corrupts an already verified authorized sector and expects recovery to rebuild
it. If recovery must reject changes that cannot be explained by the actual
interrupted command prefix, that stronger policy is not implemented and needs
an explicit representation and test contract. Current tests demonstrate
convergence of modeled partial writes, not forensic attribution of every
changed byte to a logged operation.

## Test evidence and limits

`tests/test_generic_diagnostic_flash.py::test_install_recovery_then_direction_bound_current_restore`
simulates a partial program and resumes install using the original unchanged
binding; it does not model USB disconnect/re-enumeration or fresh evidence for
install continuation. `test_restore_accepts_new_devnum_and_sg_node_on_same_physical_port`
checks that restore binding accepts changed USB devnum/SG node on the same
stable port, but only constructs and closes the session. The adjacent restore
reread test proves a mismatching full-image reread prevents mutation. These are
synthetic policy tests, not hardware evidence.

There is no current public or production flash endpoint in the installer
service: `tools/installer_service/api.py` exposes build submission and result
retrieval. The diagnostic receipt explicitly sets `hardware_admitted`,
`physical_writer_ready`, `installable`, and `updater_accepted` false in
`tools/native/generic_diagnostic_flash.py`. Historical lifecycle scripts under
`tools/bench_capture/lifecycle-v1/` are outside this mutable path and were not
treated as current installer behavior.

The source hashes at review time were:

| File | SHA-256 |
| --- | --- |
| `tools/fm1_flash_transaction.py` | `d0527efbe74314b30a2cd76897c022a1c7857db888ef6e8f8610dbb329956908` |
| `tools/native/generic_diagnostic_flash.py` | `fb41aabe42d82ce8dcd735713b9075101390751ce0ed023fc8128b0858138e70` |
| `tools/native/generic_diagnostic_sg_adapter.py` | `a05692b530acb874a0b06870e2fc1d93bc7947260549125df95e27fd3c6e66b2` |
| `tests/test_generic_diagnostic_flash.py` | `2c6afce037e9ba6d98fae14d6518f77dab243a70559dfed312eb944730a9d5b7` |
| `tools/installer_service/api.py` | `8d51c39794bf25c5358a703b8cd45fc54ddaa427416409b08289e575d0be749d` |

## Follow-up acceptance tests

If install continuation after reconnect is a release requirement, implement a
separate explicit resume admission that verifies a fresh paired full-image
read, stable-port correlation, and the new USB/SG mapping while preserving the
original sealed plan, target, backups, and transaction identity. Add tests that:

1. Inject an ambiguous erase/program completion, reconnect with a new devnum
   and SG node on the same stable port, and continue install only after a fresh
   paired read and complete current-image check.
2. Reject a different stable port, a changed historical plan/target/backup,
   modified bytes outside authorized ranges, and stale or mismatched read
   receipts. Decide whether recovery must also reject in-range changes that do
   not classify within an explicit approved interrupted-operation prefix; if
   so, test that policy separately from the existing repair/convergence case.
3. Reject install continuation when the original read has expired unless a
   new explicit resume-admission receipt is present; check freshness at
   admission, then enforce a separate bounded live-session deadline.
4. Prove no automatic retry uses the disconnected transport; intent is durable
   before each command; page/sector work is rebuilt from fresh readback; and
   final full-image readback equals the exact target SHA.
5. Exercise the fresh-read baseline restore path with changed devnum/SG mapping
   through actual simulated erase/program/readback, not only session binding.
6. Reopen the sealed transaction in a new process and prove the admitted resume
   capability cannot be reconstructed from a plain dictionary or modified
   receipt.

No install/resume capability should be advertised until these gates are
implemented and independently reviewed. Physical recovery, loader behavior,
stock invariants on hardware, updater acceptance, release packaging and public
deployment remain outside this audit.
