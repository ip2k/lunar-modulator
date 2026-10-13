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
