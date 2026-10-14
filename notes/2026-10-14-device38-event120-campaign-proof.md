# Device38 Event120 completed-transaction proof

This offline-only wrapper validates a completed Event120 native install campaign before a separate coordinator boot-admission step. It performs no USB, SG, flash, reboot, MIDI, or power operations. Its successful test fixture is a deterministic simulator transcript over 208 changed sectors; it is not hardware evidence.

## Proof contract

`tools/native/event120_campaign_proof.py::verify(directory, campaign_sha256, source_root=..., now=...)` reads the V2 campaign, exact private V1 stopped-before-SG evidence, fixed source pins, two matching 1 MiB backup reads, the immutable transaction plan and target, completed journal, one-use campaign marker, result JSON, and SG transcript. It returns:

- `proof`: strict offline result including `hardware_admitted=false`, `installable=false`, no boot or physical recovery claim, target SHA, 208 sector count, transcript SHA and the exact prior V1 stop proof.
- `evidence_sha256`: absolute evidence paths mapped to SHA-256 of the exact raw bytes read, for a caller to freeze/recheck before any later admission step.

The V2 prepared and terminal transcript rows and `result.json` must carry the same strict `prior_v1_stop_proof`. The replay checks command order and payload/readback hashes, rejects trailing rows, and verifies the directory sector was last. The campaign is pinned to device38's USB identity and SG binding. V1 prior evidence must be the preserved two-row prepared/stopped attempt with no SG, reset, or write intent; its marker is not consumed again.

## Verification

Hera bounded pytest container: `tests/test_event120_campaign_proof.py`+ßuÁ‚ùÁT 6 passed. The positive case creates a 1 MiB synthetic baseline and target with exactly 208 changed sectors, records the complete deterministic SG transcript, and executes the real pure replay. Negative cases reject altered V1 binding, altered readback response hash, changed source manifest, and non-complete journal; symlink evidence is refused. `py_compile` passed for wrapper, replay, and test.

This proves the verifier/replay behavior for synthetic evidence only. The actual V2 writer result must still be passed through this verifier by the coordinator; wrapper success does not itself authorize boot, establish ROM recovery, or establish device acceptance.

## Follow-up: retained stop schema and source freeze

The V1 stopped row in the retained transcript contains only time, event, error,
detail, and retry; identity fields are on the prepared row. The verifier now
checks these two row schemas separately. I ran the V1 stop verifier against the
actual retained Hera transcript outside the pytest container; its pinned bytes
passed. The portable unit test exercises the writer row shape without depending
on a private absolute path.

Before importing the pure replay and writer helpers, module initialization now
checks their exact reviewed source hashes. Verification rereads the replay
dependencies through the evidence collector, so evidence_sha256 includes the
source bytes consumed by replay as well as artifact inputs. The boot caller must
also pin the wrapper's own SHA externally (self-hashing would be circular).

## Follow-up: actual SG binding contract

The completed coordinator run exposed a schema mismatch: the writer records USB
identity in the backup manifest's usb_binding and records the SG/sysfs mapping
separately. The mapping itself has class/device/node/usb paths and corresponding
identity tuples; it does not contain a nested usb_binding. The verifier now
pins the exact observed device38 mapping and independently requires the manifest
USB identity, manifest SG map, and campaign SG map to match. Tests exercise that
real mapping and reject altered node identity or an unexpected nested field.
The completed V2 bundle remains coordinator-owned and is checked there; this
worker did not read the in-progress private Pi output.
