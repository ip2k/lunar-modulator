# Fixed-loader reset for the installed SDK display target

Personal, non-commercial. This is a separate target-specific factory and a
single FC0C argument 1 request, with no device reads, uploads, flash writes or
retry. Frozen source/tests passed the focused Hera gate and final independent
source/evidence review. No hardware access occurred in this lane.
A reset-request receipt is not boot, display, or retained recovery evidence.

The install-only runner deliberately leaves the diagnostic target in NOR.
The old baseline and post-rehearsal stock-return reset guards remain unchanged.
This factory cannot accept their receipts: it requires the exact install-only
campaign, terminal install completion/result, complete install journal, and
actual final 4096 page hashes matching the target, all in the original fixed
loader session. The operator must explicitly attest no later commands and
approve `exact-sdk-display-diagnostic` as the target trial. Historical backup
success is checked at its completion time; live USB/SG binding remains a
separate ten-second bound immediately around the one reset ioctl.

## Source and policy

- `tools/fm1_fixed_target_reset.py`: separate factory, replay, exact-instance
  WeakSet authority, frozen evidence recheck after durable reset intent and
  before ioctl, parent-scoped exclusive `.target-core-reset.consumed` marker.
- `tests/test_fixed_target_reset.py`: injected syscall faults, copied authority,
  intent-boundary drift, transcript edits, target/baseline policy confusion,
  and actual private-input install + complete reset factory smoke in an SG model.
- Install source literal pin:
  `25412082d20791d5f84e80d3139d0bc80de7dd78b8d165bca5b48cef6cdcfea5`.
  Install source repair was independently accepted; its 37-node Hera gate and
  actual private model smoke passed with no failures/skips/OOM. Install independent review is `build/sdk-install-independent-review.md`,
  SHA-256 `c4c7d15bcab6b32006e848652c34999ae66a692134fee5d1311fd1d82eb8aa9c`.
  Separate install aggregate: `build/sdk-install-test/aggregate-v2.json`, SHA-256
  `b6f453eeac844bfc3fc6a555c110a8fe7259dac753721881f1824608ef232398`.
- Existing rehearsal source pin is preserved:
  `f696484511754b91d4faf449aa2e4cab3ca910daf05a9acd66daa966bae7d6c4`.
- Existing reset SG/native pin is preserved:
  `dbbe363104aa339b63430ff0a99f817aba27afa233a266d449f45e048cd09116`.
- Exact full target is
  `df6c963ecd37b334f393c5bc92c2780b6094181308822a03c8190b016a4e97db`;
  full original baseline remains
  `96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`.

The new campaign has exactly sixteen fields: `schema=1`,
`kind=fm1-fixed-loader-sdk-target-reset`, `adapter_sha256`,
`install_adapter_path`, `install_campaign_path`, `install_campaign_sha256`,
`install_commands_sha256`, `install_result_sha256`, `install_exit_status=0`
(integer), `journal_sha256`,
`active_session_state=same-fixed-loader-installed-target-no-later-commands`,
`usb_binding`, `sg_binding`, `receipt_path`, `target_sha256` (literal above),
`target_boot_authorization=exact-sdk-display-diagnostic`.
No other schema/keys/target or stock-return state is accepted.

The nested install campaign retains its six-field schema. Its underlying
f696 campaign must have the original nine fields and pinned backup log,
matching USB/SG binding, exact source root and both actual-file policies.
The frozen journal must be complete/install, no intent, target verified hash.
All thirty 4 KiB sectors retain the existing order: 0x5000 through 0x21000,
then application directory 0x4000. Replay checks every initial baseline page,
pre-erase sector, erased sector, program CRC framing/payload, verified sector,
and final target page. It permits only the existing at-most-one timer FC0A
before each FD05 page. Any missing/extra event, reply hash mismatch, stop
following completion, altered result or restore direction fails closed.

## Native and runtime limits

The FC0C argument 1 native assurance is inherited unchanged from
`notes/2026-10-11-fixed-loader-baseline-reset.md`. The fixed candidate's traced
zero-context branch reaches JL_POWER bit 4 then spins; external initializer
`0x01e00428` remains unclosed. No new native reset conclusion is made here.
USB detach or an ambiguous reply consumes/closes the attempt with no retry.
Ordinary completion still has `core_reset_observed=false`,
`boot_observed=false`, `display_observed=false`, and
`physical_recovery_verified=false`. Advisory flock is not global USB
exclusivity. The parent-scoped one-use marker is an operator boundary;
copying private receipts or concurrent uncooperative callers is not excluded
by Python or advisory locks. No later-command attestation is independently
observable from files or sysfs.

Both semantic tools were checked for this task. Rarefaction selects the
primary checkout; worktree Python orient returns ENOENT. Serena selects the
primary checkout with C++ coverage; the worktree Python symbol lookup returns
FileNotFoundError. Shared selection was not altered. File inspection and
pinned native vendor listing are the actual evidence here.

## Validation and handoff

[verified] Local syntax compilation passed; all test execution ran on Hera.
The frozen implementation and tests are:

- Adapter `b846b574fe1e5b7597001f6f833044a07143540f2c0b3676e93bac807869833a`.
- Tests `49d96179c64c97cd58d93bf712f284f141f38886c4973384e5f8dfdadfe588e8`.

[verified] Hera `/home/claude/mvave-fm1/fixed-target-reset-20261011` ran
107 unique nodes across sixteen chunks (eleven with seven, five with six),
with zero duplicates, failures, errors or skips. This includes 59 new target
reset cases and 48 incumbent baseline reset cases. A separate one-case smoke
recreated the complete actual private-input install campaign hierarchy in a
disposable container, modeled installation of the actual target, then passed
its result/log/journal through the complete unmocked target-reset factory.
The SG discovery hook would fail if that factory tried hardware discovery;
only the install SG operations were modeled. Smoke passed, and the same case
also passed within the sixteen-chunk coverage. Neither factory acceptance
nor modeled flash contents constitute a physical reset or boot observation.

[verified] All 539 source archive members and current files matched the sealed
snapshot. Local evidence is under `build/fixed-target-reset-hera/`:

| Artifact | SHA-256 |
| --- | --- |
| `source-v1.tar.gz` | `b4be1e14d7af7dc45bbfeae13f88876cfc7d173bb7236eb281156c900a73e9c9` |
| `snapshot-v1.json` | `8b88676b52ece6a35988fa5f03743a538bd1bf387253b00ed9bf8017fcf46426` |
| `run.py` | `d4369eeafff3f6888fa3d251f6aed5726bde944c1ad750fa0caa7df830417ffc` |
| `plan-v1.json` | `0370bb3f6ba1132bb2bf510ba1c5cca0219acf04b21364b038052dc03c08b5ee` |
| `aggregate-v1.json` | `2db6ae9cce8d5103c82526cacdb2809ee14c1db8a0902e73df4e75c37aaa32e1` |
| `verify_evidence.py` | `156cf3cf8db5fb96b9b4d995f47298c3cca6c3e29f777e08ade0fde6b92848ef` |
| `independent-evidence-check.json` | `13cdb95ebac8fac265e0334ec9afa333ee9f171bae70a650438e3bcfc20923d3` |
| `container-removal-check.json` | `05506b041c99e30febd411732c113cf74e91ed7901315b1cbd3f3b23eca72c70` |
| `current-source-check.json` | `588c9c644a969553cdd84705f3d642f6ffc2ef36f3c9034858ff1d2c0dec111a` |
| `runner-v1.log` | `1e55560e3976dec47f95261953d747289912258b0a8c548ff30cf4c3cf3af810` |
| `evidence-v1/smoke/target-reset-factory-accepted.json` | `9eb8d0191ad2aa7436ede20f7f236291860206ee8906d5fffb6da595dacbd473` |

[verified] The image was
`sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`
(`lunar-recovery-pytest:20261011`, Python 3.11.2). All eighteen collection,
smoke, and chunk container inspections show exit zero, no OOM, network none,
no devices, nonprivileged, 2 CPU/2 GiB, and the exact image. The runner removed
all eighteen; a separate remote `docker ps -a` lookup by exact session label
returned empty with exit zero. The private fixture directories were read-only;
mutable backup/campaign copies lived only inside disposable containers.

Root owns final independent source/evidence review, commits and immediate
push, physical actual-file preflight, exact one-request activation, and
separate target boot/display/retained recovery observations. [verified] Final independent offline acceptance is saved in
`build/fixed-target-reset-review.md`, SHA-256
`bb3db9d4653e338d1027b3b0ecd98c565e339926b99c25e1f3e1dfe0107c8c81`.
The reviewer independently checked all 539 archive/current source pins, exact
107 XML nodes, actual smoke, all eighteen resource/no-device inspections, and
fresh empty removal lookup. No source defect remained; actual physical staged
campaign review is still separate.
The sole invocation after root prepares the exact sixteen-field campaign is
`python3 tools/fm1_fixed_target_reset.py --campaign /absolute/private/campaign.json`
on the reviewed Linux bench. An ambiguous reply consumes/closes the attempt;
do not retry from the same original backup parent. Baseline/stock-return
reset receipts cannot authorize this target trial.

Current branch: `feature/2026-10-11@installable-firmware`. The source archive
base was `af72e6710d180cfd970176f21f45f9a8c39945ce`; latest checked
local/remote checkpoint is `3cc74bfd5891b58b31730ee572ec34323957611a`,
which includes the independently accepted install-only source. New source/tests/note were still
uncommitted at final test completion; root owns checkpoint and verified push.
Next dependency: root checkpoint/push, authorized complete Python suite
regression and CI, then future exact physical install-only evidence/preflight.
Target boot, display, and physical recovery remain false.
