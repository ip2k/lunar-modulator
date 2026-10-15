# Restart resumed: installer profile binding

[verified: source and host tests] Resumed from checkpoint17b92837 in the named
installable-firmware worktree. Reviewed worker commit
f138766f266c3ebf8a8ef7e651857c222c84f259 and integrated as
6b6ae4b6813afe96cf9863ab5d499840ac5b8a97. Origin independently matched that SHA.
Explicit D7000 and D9000 requests now require their fixed wavetable profiles
before output creation. Legacy requests without profile keys retain their
previous behavior. Reviewed all call sites of validate_build_profile.

[verified] Worker-checkout selection suite:17 passed with the actual fm1-state
codec. Integrated selection and installer-service suites:121 passed,1 skipped,
one Starlette/httpx deprecation warning. Interpreter:
`/tmp/lunar-installer-service-test-venv/bin/python`; FM1_STATE_TOOL was the
coordinator worktree's `engines/build/fm1-state`. No target link or hardware
acceptance is established by these tests.

[verified: passive] bench01 still enumerated port1-1, bus1/device113,
4c4a:8057 WL80UBOOT1.00 after restart. No device command, flash or reset issued.
Historical installed image and failed audio acceptance remain as checkpointed.

[verified: source review] Designated exact Hall source66c95bb2/tree542445ed as
the source for a coherent new deployment-tools export. Its current candidate,
boot and SG pins agree on the complete14-body profile. An offline worker is
regenerating the archive/manifests and downstream pins in the isolated ROM113
scratch preparation; no physical campaign is authorized by that assignment.
Other workers own bounded private installer evidence retention and read-only
current-target audio codegen review. Root retains exclusive device authority.

Semantic tools: Serena activated the exact coordinator absolute worktree and
successfully returned validate_build_profile, matching the source/caller found
by rg. Rarefaction still selects the primary Developer checkout and its bounded
named query found no symbol; do not infer missing callers from that result or
retarget a shared server while other work is active. Native ABI/codegen checks
continue to require the real pi32v2 tools and hardware evidence.

## Recovery regression and independent package review

[verified: host] Expanded candidate, generic diagnostic boot, SG adapter and
flash suites completed:82 passed. This does not establish physical recovery.

[verified: offline bytes] Independently regenerated the exact66c95bb tools
archive and compared it bytewise with the worker export; checked all manifest
file sizes/hashes and the constructed target/receipt hash. Protected stock
regions0..0x4000 and0xD7000..end match the archived baseline. Evidence:
`scratch/hall-gain-target-independent-review/root-construction-review.json`.
The remaining source/campaign bindings are still being regenerated; no package
staging, fresh-read admission, device write or reset occurred.

[verified: review finding] Private installer evidence worker commit ed6adc5f
is NOT integrated. Its new collector admits /catalogue and /output/build/link,
but the actual worker mounts /input/catalogue and builds under
/tmp/lunar-worker/output/build. Synthetic fixtures therefore do not prove the
real service boundary. Root requested corrected actual-path fixtures, original
receipt ordering, actual generated provenance coverage, canonical path checks,
and file/aggregate caps before allocation. Worker owns corrections and checks.

[reported: worker] Fresh current-source stage2/engine7 profiling catalogue
completed16 Hera shards; bounded target link is running. It preserves all13
engines, Event Horizon+SET, no autoplay/SAVE and120-second recovery. No current
stage timing or hardware improvement has been measured from that build.

## Fresh stage profiling build and malformed pin rejection

[verified: offline bytes] Root copied the stage2/engine7 frozen receipt and
all10 required outputs from Hera and independently rehashed each. All16 shard
and link policy/exit/no-OOM checks pass. Source66c95bb/tree542445ed, receipt
95b57466b48a06c4395132c062a34eb52a952bd0463779b4c3813a43a901b400.
App854644/860644B, all13 production engines, EH+SET, autoplayfalse,
save_service_armedfalse,120-second return. sdk_archives=[]; worker corrected
an unsupported closed-SDK claim in its shared handoff. This is instrumentation
build evidence, not physical audio improvement or installability.
Root evidence: scratch/current-stage7-independent-review/root-hash-review.json.

[verified: review finding] The new ROM113 scratch package carried a65-character
current-flash hash, with its fixture repeating the same malformed value. Root
requested strict64-lowercase-hex checks and negative regression. Read-only
bench filesystem hash and preceding ROM111 install result independently agree:
28483c411f23d7d5fba09b4770dd29b3c66b1a154138e493e6e079e54dcf400f.
Prior result:210sectors, simulatedfalse, full verified hash as above. Retained
result at scratch/current-stage7-independent-review/preceding-rom111-install-session-result.json.
This is historical evidence only; no fresh ROM113 admission or USB/reset/write.
