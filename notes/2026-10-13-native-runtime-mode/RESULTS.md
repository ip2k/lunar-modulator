# Explicit continuous native runtime preparation

[verified] `build_application_probe.py --runtime-mode continuous` disables only
its automatic twenty-second ROM return. Default `diagnostic` remains timed.
Both modes retain the reviewed generated HAL: watchdog, USB recovery request,
boot-failure guard, no NOR writes and no OTA cleanup. Neither mode is an
admitted release or physical installation. Receipt records mode, compile define,
return timeout and runtime header hash; continuous timeout is null.

[verified] All35 policy tests passed across30 Hera containers. Each terminal
exit/noOOM/log summary was checked individually (tests.json, log-check.json).
Actual C header compiled for default/diagnostic/continuous and exercised both
sides of timeout, unsigned counter wrap and full uint32 elapsed; unsupported
compiler durations and unknown runtime names were refused.

[verified] Both all13 production-engine FIRST ORBIT target builds passed the
SDK-free/eFuse, strict entry/flattened artifact, stack painter and linked content
gates. Shapes keeps12 voices, instance pool216064 bytes, packed project2784 bytes.
Diagnostic app845916 bytes is byte-identical to the physically installed probe;
continuous app845884 bytes. Exact application/ELF hashes, runtime receipts and
container states are in target-checks.json and target-containers.json.
This byte comparison covers application payload, not ELF metadata or a new
full-flash constructor. No continuous image has been written or booted.

[verified] Target source hashes all match this worktree. Test-source hashes
match except build_application_probe.py: a new runtime-policy dictionary was
renamed before target linking to avoid colliding with its existing runtime
output-directory variable. Both actual builder executions validate the corrected
source. Policy/header/test sources did not change after the35-test campaign.

MCP coverage: Serena found app_main at this absolute worktree. Rarefaction's
configured primary checkout rejected the external worktree; source inspection
was used without changing another session's root. clangd source navigation
cannot verify pi32v2 ABI or hardware timing.

Physical all13 diagnostic boot remains pending owner observation. Sustained
hardware operation, flash-backed storage/settings migration, physical rollback,
web OTA/custom builder, GPL distribution and review/CI integration remain open.
Private target builds: Hera native-external-arenas-16-20261012/out/runtime-*
-all13-v1; original writer campaign remains consumed, never replay it.
