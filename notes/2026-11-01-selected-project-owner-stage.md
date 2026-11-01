# Offline selected-app PROJECT staging

[verified source] This opt-in source slice combines the actual selected Trio
app with the reviewed PROJECT staging API. It does not start the interactive
platform, implement a live pause, bind storage, enable SAVE or change a default
target/profile. Base: `4857d4273f8ab686031870c322cf3b09f9f62679` (reviewed
interactive checkpoint A). The codec, cold selected loader, owner scheduler and
builders are unchanged.

`LUNAR_SELECTED_PROJECT_STAGE_PROOF` additionally requires the explicit offline
and selected interactive proof flags. The caller uses a never-started, exclusively
owned app, or a future caller-proven shutdown excluding all owner/IRQ/render/
input/display access for the complete synchronous call. Checkpoint A has no stop
API; merely omitting owner/IRQ calls does not satisfy its live-owner contract. The boolean operation guard rejects same-thread reentry; it is not a lock
or proof of a target pause. No mutable app pointer is exported.

The private aligned startup reader allocation becomes 65,536 bytes only under
this opt-in. The cold reader returns before staging reconstructs the complete
arena. Default storage remains 16,384 bytes. The full allocation lives through
preflight, begin, replay, mandatory identity and semantic readback, commit or
abort. Candidate storage and callback/report objects remain disjoint and
caller-owned. No callback may retain borrowed bytes or workspace pointers.

The app wrapper bridges the existing five callbacks and observes sticky faults
before and after each hook. A fault after a successful begin closes its candidate;
a fault during write/read returns failure to the core, which aborts once. A
fault already observed before commit closes the uncommitted handle without
publication. Fault during commit preserves a definitive REFUSED result;
otherwise the wrapper returns INDETERMINATE because publication may already have
occurred. It never retries or aborts after a commit hook. The operation guard
stays held through cleanup. Early wrapper refusal leaves the report untouched;
admitted calls keep the core's ordinary byte/report behavior.

The focused host fixture uses the existing transaction fixture's model by
including it under a renamed original main. This intentionally shares its
seekable slots, generation/CRC checks and partial-effect mechanism, without
copying a second transaction protocol into production. Its large buffers are
host test storage, not target RAM or a proposed flash geometry. The actual
private selected app is initialized and driven through checkpoint A's app
adapters by one offline caller, before any live platform exists. A separately
initialized host app is the byte/report/PCM oracle. Full PROJECT output is
checked by the shared general reader; the fixed 30-record cold loader remains
narrow and refuses it without mutation.

[verified host] Exact source `6f16d68331f43662b8a788aef3ddca257f791d65`
passed the focused test in normal Clang and Clang ASan/UBSan builds with leak
detection enabled. Each run checks modes 2/3 bytes and complete reports against
the separately initialized actual host app, shared-reader records, unchanged
full app/engine snapshots and identical next-block nonzero PCM. All 182 storage
operations were faulted at zero/half/full effect (546 cases); 531 callback calls
checked reentry refusal. Eight additional app-fault scenarios cover begin,
write, read, commit, abort, pre-entry poison and commit returning REFUSED or
INDETERMINATE. No automatic retry occurs. Normal object symbols prove the
default reader remains 16,384 bytes with no stage API, versus the opt-in shared
65,536-byte arena. ASan adds global redzones, so allocation-size assertions run
only in the normal build; all runtime cases run under both.

The first test attempt exposed an uninitialized independent-reader report in
the fixture; that test setup was corrected. The next run passed all runtime
cases but counted ASan redzones as allocation bytes; the size assertion was
corrected as above. Neither required changing production code. The included
old transaction fixture has an unused renamed main with its existing implicit
main return, producing a compile warning; that function is never invoked.
No production diagnostic source warning was introduced.
No target compile, aggregate RAM/stack proof, physical output or storage
admission is claimed. The earlier component's 98,036-byte conditional bound is
not transferred to this new app/Trio/caller composition without fresh accounting.

Code-intelligence check: Rarefaction remains fixed at the primary checkout and
rejects the sibling worktree project path. Serena's absolute query returned no
conditional symbol under its current flags. No shared root was changed; exact
Git/source reads in the isolated checkout are the fallback. All AGENTS/CLAUDE
instructions match the previously read frozen plan inputs.

Private logs/commands/products: owned
`/datasets/lunar-modulator/selected-project-owner-stage-20261101/` on Aeon and
`scratch/selected-project-owner-stage-20261101/` in the author worktree. Retain
small receipts/logs; remove copied source, build products and test corpora after
review. Host jobs use CPUs 0–3, at most four CPUs and 6 GiB memory/swap,
`docker-batch.slice`, network disabled and read-only source. The Hera claim is
`lunar--selected-project-owner-stage-20261101`.
