# Completed-trace stock reset admission

[verified: source inspection] Distinct closed adapter
`tools/fm1_completed_stop_trace_stock_reset.py` reuses reviewed one-FC0C(arg1)
mechanics after the actual completed-trace restore verifier. Source diff against
preparation-stop reset changes only the restore dependency, authority names,
campaign kind/state, event name and durable marker namespace. The exact reset,
bridge and SG reader pins are unchanged. Canonical RESTORE_SOURCE_SHA stays None.

It validates completed dual backup/restore provenance and full baseline readback,
freezes dependency/receipt/journal evidence, preserves absent-evidence checks,
requires the same USB/SG binding and 64-bit SG layout, consumes a private durable
marker before opening, and rechecks evidence after durable reset intent. No
flash write, upload or retry is added. Request completion never claims boot.

[verification pending] Sixteen disposable Hera containers are running the real
backup-to-restore-to-reset composition; chunk0 also checks syscall boundaries.
Private runner /home/claude/completed-stop-trace-reset-16-20261012, local execution
handle67871. Preserve terminal results before retrying. The initial snapshot has
two known test-harness defects (old expected event name and cached canonical reset
module in chunk0). Local tests correct both: exact event name and unique module
loading of the private pinned derivative. Production source is unchanged by these
corrections. Run corrected isolated snapshot after inspecting initial terminal
results; never restart a running handle solely because observation timed out.

[verified: live bench] FM1 still enumerated 4c4a:8057 bus1 device10; no reset was
sent in this step. Computer Use could inspect Packetry, restore capture stopped
and saved, Cynthion selected, target power on and untouched. Physical stock boot,
visible diagnostic display and recovery remain unproven.

[tool limitation] Rarefaction rejected the absolute worktree path outside its
shared workspace; Serena marked that path ignored. Neither shared project was
retargeted or restarted. Direct source inspection used for this adapter.

## Actual proof interface correction

[verified] Initial run67871 ended: eleven chunks passed, four hit the512 MiB
container memory limit (OOM), and chunk0 had the two known harness failures.
Terminal inspection and XML evidence are preserved on Hera; containers removed.
The1 GiB v2 run41798 was superseded after actual evidence-only bench admission
found a production interface mismatch: CompletedStopTraceProof exposes check(),
not check_pending(). No USB opened, reset receipt/marker remained absent. Old
private source and failed physical-stock-reset-001 packet are preserved.

The adapter now calls the real completed proof check(), including original
stop, plan, frozen evidence and negative evidence. Boundary fixtures mirror that
interface. Canonical source0ab72449c4c3f9161c57e243ac57edb497ada7d95df52e854586a42d66378539
stays closed. Distinct private check_v3 source93fd979b10c5f0609c8ad826e998f4583cc94f8e58aacef68c1b70dcf650ac98
differs only by exact restore dependency pin; reverse substitution verified.
Fresh physical-stock-reset-003 campaignac5c3629c93e52f85d53e3699f9f549e923434aeef8e6de3ed276a3781058b57
passed actual admission and check with721 frozen entries, zero USB opens/commands.
No physical reset sent. Complete16-case corrected v3 verification still pending.

[verified: GitHub] Earlier source93d5f2b8 CI38324630190 completed successfully.
This does not establish CI acceptance of the new reset source or physical boot.
