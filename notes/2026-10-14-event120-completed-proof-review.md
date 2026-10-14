# Event120 completed-install proof review

Reviewed proof commit c28058350a9837ec9a100f2200f98d172ca0dd35 on Hera. The proof wrapper pins its imported project dependencies before import, records replay-source hashes in the returned evidence map, checks exact V2 campaign/candidate/transport/backup/plan/journal/result/transcript bindings, and delegates the transcript's sector/readback semantics to the pinned pure replay. Admission, installability, boot and physical recovery remain explicitly false.

The V1 stopped-attempt validator now matches the retained event schema: campaign identity is on the prepared row; the terminal stopped row has only `time,event,error,detail,retry`. The prepared identity, exact two-row count, terminal `ValueError`, `retry=false`, monotonic finite times, consumed marker, campaign and transcript bytes are all pinned. I invoked `_verify_v1_stop` directly against the actual retained Hera transcript; it returned the expected pre-SG proof with zero SG commands, reset commands and write intents. This is retained evidence validation only.

Source execution must retain the coordinator's fresh private `pycache_prefix` contract: use a newly created root-only directory with `PYTHONDONTWRITEBYTECODE=1` before importing the pinned modules, so pre-existing bytecode caches cannot substitute code after source-file hash checks. No code change was needed for that operational control. The proof worker's pytest set is portable and does not reach into private absolute paths.

Checks: `PYTHONPATH=tools /home/claude/.cache/lunar-venvs/wave-receipt-validation-20261014/bin/pytest -q tests/test_event120_campaign_proof.py` passed 8 tests; `git show --check c2805835` passed; direct V1 retained-transcript verification passed. The synthetic completion tests exercise the actual replay, but this review did not independently run the wrapper against the live V2 output bundle. That completed-bundle proof remains a coordinator acceptance step. No device command was issued.


## Follow-up: actual SG mapping contract

Reviewed proof correction commit 8e80de8c8f03965688a211983df3cdbc1f44cc11. The actual campaign SG map contains class/device/node/usb path strings and corresponding identity tuples; it does not contain a nested usb_binding field. The corrected verifier pins the exact observed mapping separately, validates the USB identity on the backup manifest, and requires campaign mapping to equal the backup manifest mapping. I independently compared the verifier's pin with the retained fresh backup manifest: equality passed and the expected eight SG-map keys were present.

Checks: focused suite passed 9 tests; `git show --check 8e80de8c` passed. Review of the corrected field bindings found no further mismatch against the retained backup contract. This remains code/backup-field review; I did not run the completed V2 bundle verifier and do not treat synthetic test success as proof of that bundle.


## Follow-up: FC0C reset response and independent USB observation

The owner-reported retained FC0C record has one reset ioctl attempt. Its ioctl return was status=0, masked=0, msg=0, host=7, driver=0, resid=16, info=1, sense_len=0, with a 16-byte all-zero response. Under `CompletionFirstReset.request_reset`, nonzero host/resid/info and a response that does not echo the CDB prefix are incomplete/ambiguous. The adapter therefore stops in `reset-ambiguous-closed`, closes, and does not retry. This does not establish that the command completed.

Immediately afterward, passive enumeration showed native USB dev39, VID/PID 1209:0001, product Felucca. That is independent evidence the device appeared as Felucca mode; it does not repair the incomplete ioctl reply or alone prove causation between the one request and the enumeration. Keep both facts in receipts. Suggested outcome names are `reset_request_ambiguous` and `native_usb_observed`; avoid a combined `reset_completed` status.

The current mock `test_reset_completion_survives_expected_detach` covers clean echoed response, a host-field error, and an ioctl exception; its case named `status` sets `h.host=1`. The production guard also rejects residual, info, sense and response mismatches, but the test does not model this exact observed tuple. A useful offline regression would inject host=7, resid=16, info=1 and zero response, then assert one ioctl, completion record preserved, ambiguity/closed result, and a second call rejected. No code or hardware action was taken in this review.
