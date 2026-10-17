# Schema9 Aeon target artifact review

[verified: coordinator independent read-only review] Both builds at Aeon
/home/claude/mvave-fm1/resampler-stage-profile-pair-aeon-20261017-codex
completed. Coordinator recomputed every one of the ten output hashes per side
against its frozen receipt on Aeon. All twenty hashes matched, including app,
ELF, map, disassembly, verification, artifact and RAM-call audit outputs.

| Target result | Schema7 control | Schema9 enabled |
| --- | ---: | ---: |
| App bytes | 856096 | 857912 |
| Slack to860644 app bound | 4548 | 2732 |
| RAM DSP bytes | 15700 | 16660 |
| RAM DSP end | 0x01c04298 | 0x01c04658 |
| RAM-code slack to0x01c06000 | 7528 | 6568 |
| Instance pool bytes | 165376 | 165376 |

Control receipt SHA256:
11f7bc853beb9592b8bc322b14d830796498548434967db443c2bb904e291143.
Enabled receipt SHA256:
70a4f2c90d938e25544380bc41467bef80d2bbca9a6f568168596ecf491286b7.
Control app SHA256:
c1dd1270af183f507011314767c610bec4c90ba80a4e3d6b6738fa87e5774e0a.
Enabled app SHA256:
9bae424c1e83cf2d50a70c42af4ebf4cb4530de56c7fe4515b202bc3e9709193.
Control ELF SHA256:
aa5a4faaa4af35b0c110119c2b658b3ca875de55417eacd812b282a492cb856f.
Enabled ELF SHA256:
48c028b5f9afcf7bb468be67c7445e48fe2dd2eea6cf4a22111db6351ce9611c.

Both artifact receipts report layout_passed=true, installable=false and
hardware_tested=false. Verification says selected hot DSP bodies are in RAM,
but all_callees_in_ram=false and flash_write_execution_verified=false. These
flags must not be upgraded from fit or codegen checks.

The pair uses exact firmware source36988d0c. Coordinator compared engines/,
firmware/, builder/catalogue and telemetry source paths against integrated
head dc29d5ea: no differences. The full Git trees differ in unrelated integration
and notes, so do not claim an identical whole-repository source SHA.

Baseline excludes IRQ and resampler-stage profiling; enabled includes both,
with a different report cadence. Same source/workload/compiler/image enables a
profiling-package comparison, not isolated resampler-hook overhead attribution.
Worker reports all32shards and both links exit0 under resource policy with no
OOM; coordinator has not independently rechecked all container inspections yet.
Worker detailed call/stack placement audit and final receipt handoff pending.
Physical execution, profiling overhead, stack high-water, realtime audio and
musical acceptance are not established. No device operation was performed.
