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
