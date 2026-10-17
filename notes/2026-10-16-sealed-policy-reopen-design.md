# Private durable generic diagnostic policy reopen design

Persist only a canonical bounded JSON seal from a factory-registered Policy.
The seal binds absolute transaction directory, canonical plan/receipt hashes,
original binding and read completion time, sector set, and bounded original
evidence inventory (absolute path, exact byte length, SHA256). The caller must
retain and independently supply the expected seal SHA256; no colocated digest
is accepted or discovered. The seal grants no hardware admission and contains
no serialized resume capability.

Reopen reads regular files using bounded O_NOFOLLOW/O_NONBLOCK descriptors,
walks parent directories without following symlinks, enforces per-file/count/
aggregate limits, rejects duplicate/noncanonical JSON, and validates the actual
transaction backup/target/plan/journal invariants through a private shared
loader. Original evidence snapshots must still match the externally pinned
seal exactly. Policy.check_files uses that same bounded loader and evidence
reader after prepare or reopen. The core transaction implementation is unchanged.
No semantic rebuild/toolchain execution occurs on reopen; the independent seal
attests the original factory validation and current snapshot byte identity.

Original read completion is retained unchanged, so stale initial install still
rejects. Explicit resume additionally needs a new verified paired read and new
process-local admission. A subprocess test will reopen the seal, reject forged
capability data, admit the fresh read, and converge a synthetic MemoryROM.

Limits chosen: seal/plan/receipt/journal <=512KiB, evidence <=512 files,
<=64MiB per file and <=256MiB aggregate. Evidence paths and transaction paths
must be absolute with no symlink components; callers must use physical paths.
No broad runtime security sandbox or protection from a hostile same-user
process replacing directories concurrently is claimed. Device APIs are absent.

## Implemented and verified

[verified: offline synthetic tests] `Policy.seal(path)` writes the canonical
seal once, fsyncs file and parent, and returns its SHA256 for independent
retention. `reopen_policy(path, expected_sha256)` requires that pin explicitly.
It compares original evidence byte hashes and revalidates transaction structure,
backups/target, canonical receipt, identity and original binding. The seal also
pins current policy, transaction-core and bound-session source hashes; changed
validation implementations reject. Receipt fields cannot upgrade hardware or
installation admission. No CLI, service, opener or device action was added.

[verified] A true subprocess starts with an empty process-local policy registry,
reopens the durable seal, refuses stale initial admission and serialized prior
capabilities, obtains a new synthetic paired-read admission with changed devnum
and SG node, then converges MemoryROM to the exact target SHA256. Other tests
cover artifact/evidence/receipt/seal tampering, missing inputs, wrong independent
pin despite a rehashed colocated seal, unsafe symlink components/FIFO/oversized
files, metadata bounds, changed validator fingerprints and hardware-claim
upgrades. Reopened resume tests reject stale reads, wrong loader/port/SG mapping,
full-current reread mismatch and changed immutable bytes before mutation.

Repository .venv focused checks: 70 passed across
`test_generic_diagnostic_reopen.py` (32), `test_generic_diagnostic_flash.py` (32),
and `test_generic_diagnostic_sg_adapter.py` (6). After the final two-pass evidence
aggregate-bound refinement, all 32 reopen checks passed again. `git diff --check`
passed. No whole-suite test, heavy build, SSH or hardware operation occurred.

Semantic configuration checks again selected the shared original checkout,
not this isolated worktree; no retarget/restart was performed. Earlier bounded
Python source queries returned missing files at that shared root. File reads
and executable focused tests supplied verification.

Branch `codex/2026-10-16-sealed-policy-reopen`, exact base
`5efd8847f8ea9ce950ba800a402c15fede3ec4f5`.
Next dependency: independent coordinator review, downstream policy/adapter source
pin refresh, required CI/integration. Schema9 receipt admission is separate work.
Private subprocess recovery is demonstrated; physical device recovery, stable
port identity/authentication, original build provenance trust, release approval
and public installer admission remain outside these tests.

Coordinator review follow-up: resume fresh-evidence reads, journal capture and
journal comparison now use the same bounded nonfollowing reader. The injected
SG adapter also uses it for retained fresh evidence before transport creation.
Three added tests replace fresh evidence after admission/bind with a FIFO,
symlink or oversized regular file: each rejects before mutation and closes the
session. All 73 focused checks passed; the six adapter checks passed again after
the final adapter reader change. Existing fresh-bundle verifier internals retain
their own prior limits and are outside this private reopen implementation.
