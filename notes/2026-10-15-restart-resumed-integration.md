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
