# Trace install, single reset and original read lineage

[verified: source inspection] The boot successor pins independently reviewed
installer6be77170, trace policy54bd9a29 and reset-wire validator9c81a30a. The
legacy b846b574 reset module contributes only its strict transcript cursor and
reviewed reset transport methods; its old image-admission factory is unused.
The new executable boot factory still requires the current complete install
journal, original consumed install marker, all30 directory-last sectors and
every actual logged baseline/target read page. It consumes a distinct reset
marker before opening SG, sends at most one FC0C and never retries.

[verified: source inspection; runtime gate pending] `prepare_read_lineage`
is an offline original-file replay. It freezes the original boot campaign and
commands, five hash-bound capture/snapshot files, original complete install
evidence, source dependencies and consumed reset marker. Capture lifecycle
requires one owned timeout/cat process group bracketing the child attempt;
the ROM snapshot requires the same USB port, changed USB address and complete
changed SG/sysfs identities. The independent wire parser checks actual reset
transmission and complete BOT pairing; detach is not promoted to completed
SG, application boot, retained RAM, pixels or recovery.

[verified: source inspection; runtime gate pending] A separately preserved
private 0600 original install journal permits historical read lineage after a
later valid stock restoration changes the current transaction journal. The
sealed plan, original self-hash, order, complete/install/no-intent state and
exact target digest must still agree. It does not authorize another executable
reset, freshen timestamps, reopen SG or replace a consumed marker.

[verified: collected; execution pending] The frozen `final-v2` archive
0673aea7 contains1738 regular tracked/test paths. Boot sourcece8fa0c5,
lineage tests0ed9e5a1 and helper3d193fd8 are frozen during the Hera gate.
105 unique tests were collected for30 nonempty chunks, with a separate genuine
composition smoke. The composition uses production install/reset/lineage
factories without source-pin substitution or fabricated authority; historical
clock, SG/NOR, USBmon capture and passive mapping are explicitly modeled. The
focused unit fixtures separately fabricate upstream authority to isolate
downstream negative cases. Private firmware inputs/native/reference paths are
read-only; containers have no device access or network. Evidence is ignored
under `build/sdk-trace-boot-hera/`; hardware acceptance remains outstanding.

[verified: tool selection, 2026-10-12] Rarefaction and Serena still selected the
primary checkout during the root session, not this dedicated worktree. Shared
selection was left unchanged; file/AST inspection supplies this check. Neither
semantic backend verifies the native pi32v2 ABI or physical USB behavior.

Next: accept actual test receipts and independent source/evidence review, then
bind the independently reviewed RAM reader to this exact boot source. Only the
root agent may perform the concrete fresh-backup/install/boot/read hardware
campaign. The current normal FM-1 identity marker has already been consumed.
