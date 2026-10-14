# Event Horizon offline installation replay

The new `tools/native/event120_install_proof.py` replay checks a complete saved
protocol transcript against immutable before/after NOR images. It checks the
derived changed sectors, protected prefix/suffix, directory-last order,
every mutation intent, exact page payload hash, complete SG status, sector
readback, all 4,096 final readback page hashes and terminal result. It rejects
trailing records and invalid observation/transcript chronology. [verified]

The test fixture records the existing bounded diagnostic writer running against
the NOR/protocol simulator, rather than manufacturing a passing replay trace.
Negative cases remove a completion, alter SG status/readback/intent, append an
event, claim boot acceptance, expire observation, reorder sectors and alter a
protected byte. The focused local check of this module plus the Event Horizon
plan helper passed 12 cases and skipped the private-evidence case. [verified]

This pure replay function does not validate caller provenance, admit hardware,
open a transport or authorize reset. A later exact-campaign verifier must bind
the reviewed writer source, plan, fresh backup and campaign before using it as
boot evidence. It proves no cold-start, audible playback or physical recovery.

The Shapes8 transport profile is integrated at `2cfce53c`; its Hera worker
commit `49ede4e1755ed588bbef09f75802342081cff337` and the transaction-plan worker
`4b3f474e6b69af5f94d42d1c150d30c37ecce8e5` are backed up on their named GitHub
branches with matching remote SHAs. Device38 writer preparation and an
independent review remain active; no Event Horizon physical boot has started.
