# Separate trace-target returned-ROM recovery (closed WIP)

[design, 2026-10-12] This stream admits only the new app `76382f…`, ELF
`e9d541…`, nonce `6b5482dbb66b5f45ed73e2f26c4a4657` and complete target
`5dbada…`. Existing 471/f696/afeefe/c1b0/f583/26f/9f6 sources, markers and
physical receipts remain unchanged. Root owns every device command and commit.
This stream is personal and non-commercial; private vendor bytes stay ignored.

Before implementation: a completed install does not prove that the CPU reaches
ROM after a partial application write. The new recovery route needs actual
new-target boot/wire evidence, fresh same-port ROM enumeration, and the consumed
trace-read receipt before any fixed-loader upload. Historical snapshots cannot
be refreshed to manufacture an admission window. Neither modeled loader entry
nor a full stock restore establishes SPL rejection behavior or USB_KEY recovery.

Three distinct sources are saved:

- `tools/fm1_sdk_trace_recovery_evidence.py`: pure ordered five-read transcript
  and publication kernel, plus a deliberately closed evidence-only admission.
  Boot/read/wire/owned-capture source pins are all `None`. Complete publication
  requires all actual reply hashes, original ROM INQUIRY and exact decoder
  output. Stopped prefixes retain ambiguity and phase-specific raw/pending/result
  rules. Missing/empty logs need a separate owned zero-CBW gate, not implemented.
  Handmade or copied ReturnedProof objects have no registry authority.
- `tools/fm1_sdk_trace_returned_backup.py`: own factory, registry, schema,
  receipt/marker and dual-read verifier; PROOF pin is `None`. Reuses only private
  pinned afeefe inventory/SG framing kernels. A future genuine proof must expose
  immutable original install inputs, raw snapshot SHA, policies, preserved journal,
  terminal time and absent paths. Separate passive connection witness is age120
  at initial admission and age10 at open; original snapshot timestamps stay fixed.
  The exact 8757 inventory uploads only the fixed candidate and reads two complete
  1-MiB dumps, both required to equal target5dbada; no NOR write or reset.
- `tools/fm1_sdk_trace_stock_restore.py`: own restore factory/worker/full replay
  with BACKUP/POLICY pins both `None`. Reuses private f583 image-independent
  Policy/Prepared/SG kernels, not its hard-target factory or receipt verifier.
  The new exact-image policy is loaded separately. First 4096 target pages must
  match before any erase/program, then thirty derived sectors with0x4000 last,
  sector readbacks and all4096 stock pages. Original complete-install journal is
  preserved before mutation; current complete-restore journal is a separate gate.

After implementation: all three factories remain closed before any campaign
read, discovery or SG opener. Pure transcript checks are value checks only and
must never be relabeled owned physical capture. The saved focused test module
models event shapes/publication, copied authority and closed gates; no genuine
new boot/read/backup/restore composition has executed. Source AST parsing passed;
Hera30 runtime is pending. Tests will use image7e32, 2CPU/2GiB, source read-only,
network none, no devices and nonprivileged containers. No local heavy tests.

Next dependencies: root's independently reviewed boot lineage with preserved
complete-install journal support; frozen reader113 and native SG38; exact owned
capture lifecycle and completed/stopped validator, including consumed zero-CBW
pretransport failures. The evidence admission must freeze positive sources and
all phase-dependent absence assertions, and preserve historical admission time.
Then literal-bind distinct backup/restore successors, run genuine private-file
modeled compositions and adversarial post-durable-intent drift gates, and obtain
independent review before preparing a concrete physical packet. Stock reset and
normal092 observation remain a later separate gate. Boot, pixels, warm corrupt
app recovery and USB_KEY remain unproved by these files.

Shared semantic backends still select the primary checkout; no agent-global
retarget/restart is authorized. Direct worktree inspection is the fallback and
cannot claim language-server or device ABI coverage. Parent verified checkpoint
`abc8135a48ea02e4228b83858481f6c0add7a1a0` contains install54/read113/boot43/
wire55 WIP; these new recovery files are not yet committed. Exact source archive,
XML/isolation/cleanup evidence and final source pins will be appended after the
bounded Hera gate. Root checkpoints and immediately verifies the pushed SHA.


The retained V1 gate completed46unique pure phase/closed cases in30Hera chunks plus1smoke. All32containers exited0/noOOM and were removed, sourceRO/networknone/devicenone/nonprivileged,2CPU/2GiB with actual4GiB MemorySwap allowance. Archive d5ec8a84c0575c64f20a0538dca8fb2dfaeb3162379abd5d261f7a749832d48b checked1729 regular pins; aggregate46d9eca6ad706ebe4696c956d4ce02b58fa6f288ca556160082647987c64a853. V1 is always-closed phase-model evidence only: a later review found that recomputing all_good omitted the percompletion lowercaseSHA predicate, so a stopped malformed final digest could be misclassified as five good completions. No opener/result bypass was admitted. V1 receipts remain immutable.

Parent released the five WIP files after pushed3191c1a18b99133945a2ab622f6b13bf534bb94e. The new successor retains each exact percompletion predicate and adds five malformed-digest adversarial cases. A new pure verify_capture_lifecycle checks exact tenfile envelope/source/input hashes, attempt/sourceUSB identity, owned process group/FD assertions, terminal-15, original finite chronology and unchanged child exit. ZeroCBW pretransport classification cannot invent reader times; wire_inventory_verified and returned_proof_granted remain false. Actual files/source/negative evidence/wire inventory plus registered boot lineage remain unimplemented authority gates; validate_returned_state still always raises. Genuine original-path admission is deferred, with no timestamprefresh and no loader upload.


The distinct V2 completed133exactunique cases across30Hera chunks plus1malformedfinaldigest smoke, no failures/errors/skips. Counts:13chunks of5 and17of4. All1740regular archivepins replayed; all32containers exact7e32,2CPU/2GiB,4GiB MemorySwap allowance,sourceRO/networknone/devicenone/nonprivileged,exit0/noOOM and removed. Fresh structured label lookup is empty. Archive7b7a0e793258bd2ed3abe5edeaab862cc110785828da908b964c2b0e9cb1c20b; plan149fa95aaee1c938f224ff0b4e07cd8ee5d00b5283c5f74f17bdf7c6d717143b; aggregate71b5c6b3c029c0025e6c06cab8bf4786e1904a219e3c355f1441fdf88c89f077; cleanup5758afb6aff4dbe7010456b9e5c9eb06886c029371f04f010d7620a057fce010. Files retained at build/sdk-trace-recovery-v2-hera/{source-v2.tar.gz,snapshot-v2.json,plan-v2.json,aggregate-v2.json,author-check-v2.json,cleanup-v2.json,evidence-v2,supervisor-v2.log}, remote /home/claude/mvave-fm1/sdk-trace-recovery-v2-20261012. Authorcheck 15539e97a817c900fb4c3ff356fb382abc8787af639d0ae87824eadd746d6e32. Independent review pending.

This is pure closed phase/lifecycle and mocked process/syscall regression evidence, including5digestrepairs,36exactcapture contradictions and46tracked wrapper cases. No genuine original-path boot/read/capture factory or physical returned-backup/stock-restore has executed. All activation pins remain None, actual admission always raises, and old installer/rehearsal/physical receipts remain frozen. [verified: archive/XML/source/isolation replay; no hardware claim]
