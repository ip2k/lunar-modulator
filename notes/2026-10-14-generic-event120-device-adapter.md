# Generic Event120 read/boot adapters

This change adds reusable read and completion-first boot adapters for a coordinator-selected FM-1 ROM enumeration. It replaces per-device-53 assumptions with an externally pinned campaign digest and an explicit expected USB device number. The adapters still accept only the reviewed fixed loader/profile/source chain and exact USB/SG identity; they have no default target device.

The read campaign verifies a fresh ROM snapshot, replays the pinned 8,757-operation inventory, and requires two complete 1 MiB dumps to match the externally supplied expected flash SHA-256. It records a one-use marker scoped to the observed USB and SG mapping. The boot campaign verifies the read campaign, manifest, transcript, dump hashes, and marker, then requires a fresh snapshot on the same USB and SG mapping before preparing the fixed completion-first reset adapter. Its campaign separately binds the expected image digest and is also externally pinned by raw campaign SHA-256.

The implementation does not claim that no other process can issue commands between observations. The boot adapter only binds the newly observed USB/SG session to the completed read evidence and preserves the reviewed one-shot reset behavior. It performs no flash write. Ambiguous reset completion stays latched and is not retried. Hardware recovery, boot acceptance, and installation remain unverified and outside this offline task.

## Verification

On Hera, the generic read/boot tests and the unchanged device-53 repeat-read/repeat-boot suites passed together: **40 passed**. The synthetic happy path replays all 8,757 inventory operations, binds two identical 1 MiB dumps and their manifest, and prepares boot against the same connection. Negative cases reject a wrong target digest, wrong manifest digest, USB mismatch, stale or malformed campaign, and replacement SG mapping.

Also passed `py_compile` for both adapters and test modules, and `git diff --check`. Tests use mocked transport/session boundaries only; no USB, MIDI, flash, power, reset, or device operations were run.
