# Cynthion recovery audit: implementation handoff and Sol prompt

Owner request, 2026-10-18: persist the independent findings, notes and next steps,
and prepare a prompt for the next turn in the existing Sol session. This is a
documentation handoff, not a new authorization to operate hardware.

## Read first and preserve

- [Independent audit](2026-10-18-cynthion-independent-audit.md): prioritized
  findings, exact source references, raw evidence checks, alternative explanations,
  and the single proposed measurement.
- [Original review packet](reviews/2026-10-18-cynthion-recovery/README.md), reviewed
  at `67f8c3665be0f3ea524bf9c8115605af5fd9b3a5`. Keep the entire checksum-covered
  packet byte-for-byte unchanged, including historical incorrect interpretations.
  Record corrections in an external addendum with links to the original evidence.
- [Repository handoff](../HANDOFF.md), AGENTS.md and CLAUDE.md, including the
  current host routing restriction and hardware gates. The reviewed branch is
  `feature/2026-10-11@installable-firmware`; preserve unrelated `uv.lock`.

[verified: audit] The packet hashes, source pins and retained build-artifact
hashes matched. The independent offline rerun passed 119 tests with 177 warnings.
Those checks do not establish loaded connector voltages, ROM entry, CPU reset,
or a passing full-speed control. No independent FPGA rebuild or new physical
operation was performed during the audit.

[verified: retained evidence; reported: owner switch state] The last recorded
repeat ended DONE after 16 cycles with no reported PHY fault and both OEs off;
no valid FM1 identity followed, including direct connection. RIGHT is ON and
LEFT is OFF. An internal battery makes USB VBUS toggling insufficient proof of
CPU reset. These are historical observations; do not assume they are live state.

## First milestone: concrete offline fixes

The endpoint is reviewed, tested diagnostic correctness with durable source and
verification receipts. It is not a declaration of physical recovery. Revalidate
the findings against the current branch before editing; another session may
already have addressed a finding.

1. **Persistent ACK-candidate telemetry.** The terminal snapshot currently stores
   `debug_ack_confirm`, a microsecond-tick-qualified predicate, rather than the
   persistent candidate flag. Give the core an explicit persistent diagnostic
   output and make terminal telemetry unambiguously report whether a candidate
   occurred. Inspect all register-layout consumers before choosing a new field
   or versioned semantic change. Preserve interpretation of historical layouts;
   never relabel a candidate as a proven target/ROM ACK.
2. **Production-clock regression.** Exercise the real 60 MHz divider and actual
   terminal capture path, including an earlier candidate whose transient pulse
   has expired by terminal capture, no-candidate completion, and reset behavior.
   Ensure the test fails on the reviewed implementation. Do not merely assert
   a newly copied implementation expression or run all long profiles at 60 MHz.
3. **Historical decode erratum.** Archived attempt 5/6 narratives call `0x18d`
   ACK-confirm=1. The actual decode is receiver-live=1, ACK-confirm=0, ticks=99.
   Keep the archive intact. Add a correction outside it, preserving the distinct
   fact that WAIT_DP/history latched a local candidate; that candidate is not ROM
   proof. Update current documentation/readout interpretation where applicable.
4. **Phase-unit correction.** The history phase field is a microsecond index,
   not USB clock cycles. Correct the current README and any consuming parser or
   labels; inspect consumers before changing code. No waveform change follows.
5. **Evidence wording.** Keep startup register readback distinct from continuous
   PHY-health monitoring, disconnected loopback distinct from loaded voltage,
   and terminal completion distinct from target acceptance. A constant Bank 6
   voltage assumption is not a voltage sensor. TARGET C VBUS disable is not data
   isolation; the host cable must remain absent during GPIO driving.

Relevant source: `tools/cynthion_usb_key/{gateware,top}.py`,
`gateware/ulpi_safe_phy.py`, `tools/cynthion_usb_key/README.md`, register readers,
and their existing tests. The exact line references are in the independent audit.

## Checks and completion evidence

- Start with Rarefaction/Serena readiness and absolute checkout selection as
  required by AGENTS.md. The audit tools selected the separate primary checkout;
  direct pinned-file inspection was used. Do not claim semantic coverage without
  a successful real-source query, or retarget another active session's server.
- Run the focused regressions and the original eight offline test modules:

  ```text
  tests/test_ulpi_safe_phy.py
  tests/test_cynthion_usb_key_gateware.py
  tests/test_cynthion_usb_key_ack_gap_reset.py
  tests/test_cynthion_usb_key_pico_repeat.py
  tests/test_cynthion_usb_key_protocol_review.py
  tests/test_cynthion_power_monitor.py
  tests/test_cynthion_power_readout.py
  tests/test_cynthion_target_usb_probe.py
  ```

- Use the existing project/dependency environment; retain exact command,
  interpreter/dependency versions, counts and warnings. Verify tests remain
  offline before running. No USB/JTAG readout is part of this milestone.
- If synthesized gateware changes, prepare fresh source pins and obtain the
  required offline build/routing review using the existing approved build path.
  Use a new artifact directory; never overwrite the audited image or pretend its
  old routing receipts cover the changed design. Follow current Aeon-only heavy
  work routing; do not start Hera work or change infrastructure.
- Check the packet manifest remains valid, documentation links resolve and
  `git diff --check` passes. Review exactly the changed source and tests.
- Commit focused work, push explicit branch refspecs and verify remote SHAs.
  Integrate only through the repository's applicable review/CI gates; do not
  merge the unfinished installable-firmware stream merely to publish diagnostics.
  Record branch, pushed SHA, checks, limits and next dependency in HANDOFF.md.

## Changes that are not yet justified

[inferred] The 1 kΩ drive path may fail loaded-low margin, and repeat timing may
miss or contaminate a ROM entry/calibration window. These are hypotheses, not
established causes. Do not change pin order, D+/D− swap register, clock polarity,
series resistance, drive strength, key gaps, PWM phase or duration on this audit
alone. The reference Pico's real idle/transition waveform remains unmeasured.

A post-release observation window could improve diagnostics, but is a separate
enhancement. It is not needed to correct the two concrete telemetry/documentation
defects and must not be presented as a recovery fix.

## Next physical dependency: prepare one measurement, do not execute it

The audit recommends one analog D+/D−/VBUS capture at the FM1 end of the cable
during the existing bounded, unchanged repeat profile. It measures loaded key
levels, gaps, PWM and release; it does not require opening the unit. Read the
audit for the exact setup, acquisition requirements, expected outcomes and stop
conditions. TARGET C remains physically unplugged while GPIO drive is active.

The owner was already asked for the scope model and breakout/test-cable access.
Check the Sol session for an answer before asking again. Confirm sufficient
memory/streaming (about 56 million samples per data channel at 1 MS/s), probe
grounding, transparent USB-C routing, and a reviewed safe abort/release action.
Prepare the scope-specific procedure for separate authorization. If equipment
cannot capture the required regions, resolve the acquisition plan first rather
than substituting an uninstrumented recovery retry.

No gateware load, USB/MIDI/JTAG transaction, device power cycle, probing, flash
operation, or infrastructure change is authorized by this handoff. Do not execute
hardware steps until separately approved. A silent target with clean external
waveforms still leaves CPU supply/reset versus rejected key unresolved; a verified
internal execution/reset witness would then be the next separately planned step.

## Paste-ready prompt for the next Sol turn

```text
Continue the Cynthion/FM1 recovery work from the independent audit. Read
AGENTS.md, CLAUDE.md, the latest HANDOFF.md, and:
  notes/2026-10-18-cynthion-independent-audit.md
  notes/2026-10-18-cynthion-recovery-fix-handoff.md
  notes/reviews/2026-10-18-cynthion-recovery/README.md

The audit reviewed commit 67f8c3665be0f3ea524bf9c8115605af5fd9b3a5 on
feature/2026-10-11@installable-firmware. Verify current branch/HEAD, dirty state
and remote before edits; preserve uv.lock and any other unrelated work. Reuse
the current stream or an isolated dependent fix branch as coordination requires.

Implement the concrete OFFLINE fixes now: persistent terminal ACK-candidate
telemetry with explicit layout compatibility; a regression through the actual
terminal snapshot at the production 60 MHz divider; correct phase units and
current readout/documentation; record the 0x18d historical-decode correction in
an external erratum. Preserve the original checksum-covered review packet and
raw evidence byte-for-byte. Revalidate each finding first and avoid duplicating
fixes another worker has already made.

Run the focused tests and the eight offline modules listed in the handoff.
If gateware changes, produce new pins and required offline build/routing evidence
through the existing approved path without overwriting old artifacts. Use both
semantic MCPs with verified absolute roots where available; report limitations.
Follow current Aeon-only heavy-work routing; do not start Hera work. Review,
commit and push the fixes, verify remote SHAs, and follow applicable CI/review
gates. Do not merge the unfinished firmware stream merely for these fixes.

Do not speculate by changing waveform, GPIO resistance/drive, polarity or PHY
swap settings. Digital tests and DONE are not physical recovery. After the
offline milestone, prepare the ONE loaded FM1-connector D+/D-/VBUS scope capture
from the audit, using the owner's actual scope/breakout details if already
provided. Keep internal CPU/reset uncertainty explicit and define safe abort,
observations and decisions. Do not load gateware, send USB/MIDI/JTAG commands,
power-cycle, probe, flash, or change infrastructure without separate approval.

Persist an actionable handoff with changed files, branch, verified pushed SHA,
test/build/review results, limits, blockers and the exact next owner action.
Continue the authorized offline milestone through its checks; do not stop at a
plan or an intermediate passing test. Recovery itself remains unproven.
```
