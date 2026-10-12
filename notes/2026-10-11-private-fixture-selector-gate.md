# Private fixture selector regression gate

Personal, non-commercial. Root owns the only source change: the rehearsal
fixture selector distinguishes no environment keys (optional public skip),
required mode, partial configuration, defined-empty values and invalid mode.
The seven boundary cases and all four importing modules are run separately
from the earlier complete 6,389-node snapshot. No physical SG operation, commit,
push, hardware or shared semantic-server selection change belongs to this lane.

[verified] Frozen `tests/test_sdk_rehearsal.py` SHA-256: `9bda83603dcffaf92a00f27409c2b200fd5b8cf4669a02c22d61075609e7ef50`.
All adapter source pins remain unchanged, including rehearsal f696, install254,
target resetb846, post-rehearsal reset743 and baseline resetdbbe.

Hera root `/home/claude/mvave-fm1/private-selector-20261011-9bda`; local ignored
evidence `build/private-selector-hera/`. The archive contains 1,652 current
tracked files (539 tools/tests/pyproject files) at base checkpoint
`33d3a215ab7f28a6904c80e92cb3eb2cd16a1fc2` plus the pending selector bytes. Untracked
diagnostic/ROM-stage probe source and ignored private wrappers are excluded.

Archive SHA-256 `b976b52cc3a93d734cf0aee0202b623dd350f8a7dd0ac9e7bbdbabdde7839ce2`; snapshot SHA-256
`ab04b4fda3b8f8f9d652e79dad88b85b220763500846598777b978331b627892`.

The pinned recovery image is
`sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`.
Each container has four CPU/four GiB/no swap expansion, network none, no device
mounts, nonprivileged mode and `docker-batch.slice`. Five read-only source/job/private
mounts plus writable evidence are checked for strict runs. Each strict container
uses its own disposable modeled backup copy with actual original-loader, SDK
ELF/app, fixed candidate/profile and historical fixtures. SG syscalls are mocked.
The public container has only source/jobs/evidence mounts and no private input
environment keys or fixture mounts.

[verified] Final collection and 16 node-strided chunks cover exactly 287 unique
nodes in four importing modules; all 287 passed with strict private fixtures,
zero skips/failures/errors. The longest strict chunk took 1,175.665 s; summed
strict container time was 5081.805 s. The public lane ran the same exact 287 nodes:
244 passed and 43 skipped only for the documented unavailable-private-fixture
reason, with zero failures/errors; runtime 24.837 s. All seven selector boundary
cases passed in both modes.

[verified] All 1,652 archived file hashes and 539 frozen source/test/config pins
match. XML covers each planned node once, with no duplicates. All 18 containers
(collection, 16 strict chunks, public) exited zero without OOM, with the specified
image, resource limits, no network/devices/privilege and exact read-only mounts.
Per-container removal receipts and a fresh empty session-label lookup confirm
removal. The independent local verifier inspects evidence without executing tests.

Final aggregate SHA-256 `39680bf5b1040d9db6f88d5d88542a15ca48315fc7077e0149f958490184057c`;
independent verifier receipt SHA-256 `a2719671b04c6fa303bc27f002e8d06d08189f044bfb5ad4727f39cdae4ea033`;
fresh removal receipt SHA-256 `a382920c811213c3190c7922c8a190f690029cdf1dd28054a51fa9ed3115ebaf`.
Saved logs/XML/runtime receipts: `build/private-selector-hera/evidence/`;
runner log: `build/private-selector-hera/runner.log`.

Root-owned checkpoint `1a5e0831e1d4a85bc339311db82ac84a216d523c` is local at this
handoff; root reports immediate verified push. This lane made no commits or
hardware operations. [verified] startup_resolution independently accepted the final source/runtime gate;
report `build/sdk-ci-private-fixture-review.md` SHA-256
`ccfbba14400af1b8b12a8443b75efe7311639291455ce56ce39a6edbc60da1f1`,
independent checker SHA-256
`2c43923512ab9e5009e317f53411fa825a455ab02c0bb396afb065eca1620a76`.
Only authorized root documentation drift lies outside the frozen source gate.
GitHub CI and physical
boot/display/recovery remain separate.
