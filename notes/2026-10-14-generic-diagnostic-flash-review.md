# Independent review: generic D7000 diagnostic flash policy

Date: 2026-10-14

## Disposition

[verified] Reviewed sibling commit 3a9ec8fb1a0937ace7221ed8e65856a87cf97852 in /home/claude/worktrees/generic-d7000-diagnostic-flash-policy. I found no source-level blocker in the offline transaction policy. The factory has no hardware transport opener or command-line writer; it creates a plan only from externally pinned private evidence. All install, package, hardware, and physical-recovery admission flags stay false.

[verified] The D9000-to-D7000 transition preserves [0, 0x4000) from the live image, preserves the current suffix [0xD9000, 1 MiB), restores [0xD7000, 0xD9000) from the exact stock baseline, and changes only derived sectors in [0x4000, 0xD9000). The app-directory sector at 0x4000 is ordered last. The transaction revalidates changed ranges, sector programming, and the complete final image through the inherited transaction path.

[verified] A restore after the original read expires requires a new complete paired-read bundle. The policy preserves the physical USB port tuple (path, busnum, VID, PID) while allowing a new enumeration number and SG node/inode, then binds the fresh transport to the newly verified USB/SG mapping and hashes. Before any restore erase/program, the first full-flash reread must match the fresh manifest's complete-image digest; the restore target remains the transaction's original current-image baseline. The focused mismatch test confirms the session closes without erase/program requests.

## Evidence and checks

[verified] The real frozen run-5 build-input receipt is /home/claude/.local/share/codex-private/trio-pulse-frozen-build-20261014/run-5/frozen-build-input-receipt.json, SHA-256 136dad341994bee22919e115a04951ad983935729023bbc6b648c7b9b29c3ce2. The policy's _check_build() passed against that receipt and its pinned outputs: source commit/tree 66196f54f3295cfdec14a2924c767235bbd5cc2c / 483e0fa782650c2158eae979f1830960c5f86a96; app 807,320 bytes, SHA-256 3de52e9bddd24c19fbabaa3cc7cec97ea78ef0a2397debfc009befb1f8b9b6bc; ELF SHA-256 a07fbd8e966873c154bfc4f62fc1d9b608004e7d1c56640f59a762959d324e6e.

[verified] I independently ran pytest -q tests/test_generic_diagnostic_flash.py in the pinned Hera Python environment: 6 passed. I also ran py_compile on the factory and test. Tests cover ambiguous program completion, journal recovery/resume, direction-bound current-baseline restore, stale-read rejection, same-port reconnect with new devnum/SG mapping, refusal on changed physical port, and full-reread mismatch before mutation.

## Limits and remaining gate

[verified] The full prepare() call has not run against a current fresh-read receipt. The frozen run-5 build validates build/source/toolchain/catalogue/profile inputs only; the coordinator has not supplied a fresh paired ROM read for the current device, and historical device-53 evidence is not admissible as that read.

[verified] The archived original FM-1_092 raw A/B pair and six stock reference components are sealed separately. The policy marks the original-092 raw archive available but explicitly leaves a full original-092 restore plan unprepared. The modeled restore direction returns to the transaction's current pre-install baseline; it does not establish restoration to the archived 092 image or prove physical recovery.

[reported] The stable USB path and the exact full-flash digest bind the reconnect used by this policy, but this offline review does not establish a serial-number identity for the physical unit. A fresh coordinator-approved read and source-level review of the RehearsalSG adapter against this policy remain prerequisites before any separate physical campaign.

[verified] Rarefaction and Serena could not be safely retargeted from the active Mac checkout to this Hera nested worktree while concurrent tasks were using their shared sessions. I reviewed the bounded implementation, inherited transaction/session APIs, and tests directly over read-only SSH; this is a coverage limitation, not a claim that the semantic indexes were checked.

## Review record

- Reviewed source: tools/native/generic_diagnostic_flash.py
- Reviewed tests: tests/test_generic_diagnostic_flash.py
- Sibling branch/commit: codex/2026-10-14-generic-diagnostic-flash-policy / 3a9ec8fb1a0937ace7221ed8e65856a87cf97852
- Review checkout base: 66196f54f3295cfdec14a2924c767235bbd5cc2c
- Scope: offline source and test review only; no hardware, USB, SG, flash, power, or reset commands.

