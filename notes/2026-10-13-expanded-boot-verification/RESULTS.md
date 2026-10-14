# Expanded device36 installation proof and one-use boot

[verified] expanded_install_proof.py independently replays the exact fresh
device36-to-current-all13 installation: reviewed campaign/source/plan hashes,
matching physical backup bytes, protected ranges, complete journal,
directory-last sector order, every command/payload and actual read-page hash,
SG status, chronological events and exact terminal result. It opens saved
files only. It cannot establish the truth of a fabricated transcript or grant
physical boot acceptance; private operator-reviewed evidence is trusted.

[verified] expanded_boot.py requires that replay before opening the original
device36 SG connection. It freezes the campaign, installation evidence,
source files and fresh backup evidence, validates a passive observation no
older than120 seconds and consumes a durable one-use marker before opening.
It reuses the pinned incumbent reset method: literal FC0C argument1 only,
no upload/flash operation or automatic retry. Success reports request
completion, not observed boot or recovery.

[verified] The real guarded transaction executed against the NOR model using
the private physical baseline/current candidate bytes. Its transcript replay
verified213 sectors and25,573 commands (one read heartbeat),58,517 events.
Final target SHA256:
`c543e538754d0ae02ee119fd1e29a9b8cb9eb21a23edf0c12fc981ddaa3bc903`.
This is simulated installation evidence, not a hardware installation.

[verified] All32 refusal/replay tests passed in30 Hera containers. Every log,
container exit/no-OOM result and five changed source hashes was checked.
Receipts: verification.json, source-hashes.json. Existing41 writer/policy/
wire-budget tests also pass locally (1.28 seconds). Semantic tools select the
primary checkout and cannot resolve these worktree-only files; exact worktree
file inspection was used without changing shared selection.

Initial test harness issues were corrected: the generator incorrectly assumed
no heartbeat; the response-corruption fixture changed a query acknowledgement
hash rather than a flash-page hash. Full model generation was not repeated:
the saved successful transaction was independently replayed and reused. All
changed tests were rerun. Original failure outputs remain on Hera.

The separate fresh-baseline41-case recovery v1 launcher terminated with Linux
E2BIG: pytest placed a nearly1MiB bytes fixture in one node ID. Twenty-nine
chunk logs exist, but no aggregate success is claimed. Explicit short fixture
IDs fix collection. The corrected v2 campaign is running in30 chunks on Hera:
launch-fresh-recovery-v2.py, out/fresh36-candidate-recovery-v2/.

No physical transport was opened, flash programmed or reset sent in this
checkpoint. Physical campaign admission, all13 startup/audio/timing, recovery,
stock migration/rollback, release builder/installer and integration remain open.
