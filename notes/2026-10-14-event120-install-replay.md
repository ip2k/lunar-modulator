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

Independent review prompted duplicate JSON-key rejection, the transport's
2,700-second elapsed-time ceiling and 32,768-command ceiling. The updated
simulator suite passed 12 cases; the six native host/toolchain helper contract
cases also passed (18 combined). A first attempt to import a CLI module's JSON
helper failed collection because that module assumes a different import path;
the file-only replay now keeps its small duplicate-key check local. [verified]

SDK-optional worker checkpoint `32551eadfe53b9d3673b5320e8be8a2f79f2b409` was
backed up with its matching GitHub SHA and integrated after portability parent
`4263126b9493a8806974a6b9715c3e1f0bac5be4`. The content-embedding conflict was
resolved by retaining the coordinator's shared fixture and one target test,
with the new absent-only SDK skip helper. The worker's configured-SDK focused
set passed 30 cases; its full SDK-absent host run is still running. [verified]
