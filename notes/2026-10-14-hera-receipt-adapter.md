# Hera receipt adapter — 2026-10-14

[verified] The private application probe link receipt now contains an ordered
`embedded_content.assets` array with each packed payload's `kind`, actual byte
length, and SHA-256 digest. The producer uses a small pure helper and retains
all prior receipt fields, including the positional digest array. The helper
rejects descriptor/payload count, kind, byte length, or digest mismatches.

Prepared-profile identity remains fail closed: the existing prepared-profile
loader checks the controller-provided manifest digest and each packed file's
manifest digest and length before linking. This adapter does not change build
or storage limits and does not claim installability, sequence semantics,
native playback, RAM fit, hardware acceptance, or release readiness.

## Checks and limits

- [verified] Python bytecode compilation passed for the producer and focused test module.
- [verified] Direct helper assertions passed for ordered project/set identities, explicit empty content, and refusal of count, length, digest, and kind mismatches.
- Focused `pytest` could not run: system Python has no pytest; creating an isolated venv succeeded, but installing pytest failed because network/DNS access is unavailable. The tests also require existing state-tool and native-toolchain environment variables for their compiler fixtures, which are not present here.
- No semantic MCP capability was available; source behavior was inspected directly.
- No firmware link, heavy build, device, bench, USB, MIDI, flash, power, reboot, or Cynthion operation was performed.

## Next dependency

Coordinator should fetch and review this branch, then push the exact reviewed commit
from the authorized GitHub host and verify the backup SHA. Run focused pytest in
the project environment with the state-tool and native-toolchain variables set.
The receipt only supplies identity for downstream exact-selection comparison;
link/RAM evidence, builder UI/backend integration, storage and physical admission,
watched boot, rollback, licensing, CI, and release gates remain separate.

## Coordinator verification

[verified] Coordinator reviewed the three-file diff, committed it through SSH
when the worker sandbox protected Git metadata, fetched its exact commit
e9814dfedfe5f703ce5eb074e8639f0f41893972 and verified the GitHub worker-branch
backup SHA. Integrated by cherry-pick into the installable-firmware branch.
All six new focused receipt tests passed in the existing Mac project venv:
`python -m pytest -q tests/test_native_content_embedding.py -k link_receipt`.
This tests receipt construction and mismatch refusal without a firmware build.
The existing toolchain-dependent embedding suite was not rerun for this adapter.
