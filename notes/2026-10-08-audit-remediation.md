# Audit remediation and firmware resumption — 2026-10-08

Owner authorized resuming firmware work and addressing audit findings.
Branch `fix/2026-10-08@firmware-readiness-audit`, branched from origin/main
64209e3 and integrating the recovery/audit record; firmware has not been
installed. Preserve stock boot/package components and bounded recovery.

Work order: validate and fix target/build guards and parser/bounds defects;
reconcile technical status; then prepare a minimal hardware application.
Remaining editor and P3 findings are tracked in the full audit; no blanket
claim that they are all confirmed or resolved. The platform evaluation
recommends a permissive bare-metal runtime for both GPL/permissive profiles;
no licence change is required or authorized by this implementation work.

## Corrected and verified

- Compile failures now return failure while preserving per-profile reports;
  staged-input dirty detection includes the firmware and target tools.
- IRQ source checks reject unproven nonliteral arguments and reserved IRQ 123.
- Sequencer imports initialize malformed lane temporaries; modulation scripts
  reject nonfinite numbers before integer conversion.
- X0X exponent arithmetic uses unsigned bit operations. Its two sanitizer
  exemptions are removed, and the vendor patch reproduces all 22 files.
- Edit-run dump output is bounded, including the edit serializer's truncation
  handling; manual output paths cannot delete an overlapping source tree.
- Remote oracle runners reject unsafe paths and frame options before SSH;
  Airwindows jobs use the batch resource limits.
- Comet retains each hit's kit and distortion choice throughout control ramps.
- Sound imports omit unavailable MIDI-effect ON/PARAM records and reset the
  replaced slot to the bypassed default used by preflight, rather than
  changing or retaining the previous sound's effect.
- Compressed state chunks and launch links require stream completion and
  reject trailing bytes in C/Python, including CRC-consistent containers.
- Binary state chunks reject duplicate keys and duplicate parameter UID/focus
  pairs instead of silently keeping the last value.
- Updater extraction continues past a length-matching non-AC791N decoy;
  the synthetic regression reproduces the original false negative.
- Technical status and recovery instructions now distinguish bounded sector
  recovery from untested full-image recovery and Lunar installation.

[verified] Local guard regressions: 70 passed, four manual dependency skips;
remote-runner safety regressions: 14 passed; host tools: 13 passed. The manual overlap regressions
then ran with the real manual dependencies: four passed. Native sequencer,
modulation, manual and edit suites passed (six dependency skips); X0X suites:
114 passed, seven reference-checkout skips. ASan/UBSan over X0X, sequencer and
modulation suites: 293 passed, seven reference-checkout skips.

[verified] The initial target runs compiled 151 objects per profile but
omitted the shared metadata/state codec objects. The corrected, deduplicated
object list compiled 164 objects in each of four profiles without failures,
with the GPL switch enabled and the full module list. Two regression cases
(GPL on/off) verify codec coverage and uniqueness in a reduced module list. Injecting a deliberate compile error returned status 1, recorded one
failure in each profile and preserved the report; the injected source was
restored. Object-level guards passed, with two linked-image checks pending.
Both the app-state correction and the C codec corrections are covered by
the final four-profile target run. Native
state suites passed with GPL modules on (nine passed, three dependency skips)
and off (eight passed, four dependency/module skips); the unknown-effect
regression reproduced before the correction in JSON and binary.
The codec suite with GPL off passed (105 passed, one external-corpus skip),
including zlib streams with an empty final block and duplicate-field cases.
Regressions reproduced acceptance of trailing chunk data and incomplete or
trailing launch-link streams before the correction.
The updated Wasm passed 104 parity scenarios, 18 SysEx cases, metadata checks
and native/Wasm edit parity with zero late storm quanta. Chromium's 30-second
page storm passed with zero reported playback underruns on the LAN runner.
The preceding CI checkpoint failed its stale-Wasm check and reported one
Chromium playback underrun. `playbackStats.underrunDuration` is measured in
seconds despite the result field's `_ms` suffix: `0.01` means 10 ms, not
0.01 ms; traced events were 10–20 ms. PR #100's final rebuilt commit
`3c7b6a0ad153eff2f80444af9b2830da2c280538` passed GitHub check run
`37890685197` and Pages before merge. PR #103 later merged the separate
IndexedDB save-durability correction as `ebc6690c7595469359336b145cf1d7c0b4fe333a`.
These are compile checks, not a linked or installable hardware application.

## Firmware memory boundary

[verified] Target sizes identify 4,939,408 bytes for the simulator app struct:
4,784,576 bytes of arenas and 154,832 bytes before them, including a
116,368-byte TFT structure. Other browser/state serialization globals include
491,520 bytes of writer scratch, 262,145 bytes of JSON input and 98,304 bytes
of binary input. This is a desktop/browser layout, not a device allocation
plan. The simulator's chain meter estimates live engine resources; it does
not certify this compiled layout against the FM-1's SRAM. Firmware needs
bounded instance allocation, display buffering and streaming persistence,
then a real linked-image map, stack/interrupt budget and runtime measurements.
The expanded target check also exposes a compiler warning for an 8,264-byte
`fm1_state_bin_read` frame. Its disassembly uses three stack decrements;
the report initially counted only the first and understated the frame as
4,148 bytes. The corrected report sums all three and agrees at 8,264 bytes
(three focused regressions pass). This is not a complete call-chain budget;
retain it as a device-readiness constraint until linked analysis and stack
measurements establish the actual requirement. The codec checks passing do not establish
that its current stack use is appropriate for the FM-1.

## Remaining work and recovery

All unresolved findings remain in the full audit report, including editor
persistence/history/cable identity checks and the remaining state-validation findings. No
hardware operation occurred during this remediation. Full-image restore,
broken-app recovery and a Lunar application on the device remain untested.

Serena indexes this worktree; Rarefaction indexes the original checkout, so
its orientation is context only. Neither index proves target ABI behavior.
Continue on `fix/2026-10-08@firmware-readiness-audit`; target/native checks use
isolated bounded LAN containers. Do not treat a passing compile report as
permission to install an image. Preserve stock package components and the
current staged recovery policy in docs/07 §4.
