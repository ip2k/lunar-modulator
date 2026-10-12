# Owned capture lifecycle successor

[verified: source and bounded models] The revised owned install/boot capture
program `59b8e8c23f494f0ac6c89585786f72a9b408d5692e2a5fbf66c2c0376945c52d`
and entry/backup orchestrator
`11fb56e84472f064d15e6c24eebcb768e78f1f349569658c17aa4a699f7108c1`
preserve partial child stdout with flush/fsync even on TimeoutExpired or
OSError. Cleanup requires the original timeout leader, original cat reader,
exact process group and expected command/FD relationships before signaling.
It requires SIGTERM status -15 and disappearance of both original PID paths
and the group. A changed reader, unexpected member, early leader exit,
escaped original process, wait timeout or uncertain stop prevents a clean
receipt. Existing install and boot receipt key sets are unchanged.

[verified: independent source review] Full source/diff review is retained at
`build/sdk-trace-fresh-entry-bench-v1/next-campaign/capture-lifecycle-successor-v1/`:
report `472d9f0f`, check `03a09a96`. The frozen copies in
`tools/bench_capture/lifecycle-v1/` exactly match the tested files and pins;
they include the unchanged closed sequence `2ffa1f19`. They are source backup
and explicit Linux model inputs, not a newly activated hardware campaign.

[verified: Hera models] All 61 unique cases passed in 30 isolated shards plus
one collection container. Every container exited 0 without OOM and was
removed; the fresh label lookup was empty. Image was `7e32dd6d`, with 2 CPUs,
2 GiB RAM, explicit 4 GiB memory plus swap, no network/devices/privilege and
read-only source inputs. Evidence is retained under
`build/sdk-trace-fresh-entry-bench-v1/next-campaign/automatic-trace-chain-lifecycle-v5/`.
Source archive `b03a79ea`, snapshot `f51726e1`, retained archive `b64a0002`,
167-file index `8552d7f4`, independent checker `3f88145f` and result
`16f18707` identify this gate. Root replayed the checker from exact copied
inputs; its result matched the independent result byte-for-byte.

The tests model proc paths, transport, time and process seams. They exercise
the actual capture-body AST after the real factory prelude; they do not
substitute canonical factory authority or run that prelude. A sequence case
uses a real harmless exit-23 child, consumes the one-shot marker and starts
no later phase. These results do not prove real kernel orphan races, a full
outer physical pipeline, CPU/SPL recovery, installation or display output.
The Linux CI step runs the same source tests; CI acceptance is still separate
from the recorded Hera result.

[verified: passive observation only] At epoch `1791823338.1693792`, bench01
sysfs reported FM-1 `4c4a:c755`, path `1-1`, bus 1, device 7 at 12 Mbps.
No identity query or device command accompanied that observation. The Mac
computer-use connection continued to return a locked-Mac error despite the
owner confirming it was unlocked and permission was enabled. A fresh
computer-use session reset returned the same native-app error and no native
apps. No Packetry window, screenshot or click is claimed. Bench USB evidence
remains available independently.

Next: validate the exact-source partial recovery allowlist, complete the
whole-checkout policy dependency gate, reseal the new physical campaign and
run fresh entry/dual backup, install, one boot, original RAM trace reads and
full stock restoration. The diagnostic image still needs physical display,
boot and recovery acceptance, required CI/review and final integration.
