# Private SDK diagnostic bound-policy review

2026-10-11. Independent source review by startup_resolution. **Accepted within the offline/injected scope after frozen source, Hera evidence and actual-file factory preflight review. No remaining actionable source defect was found in that scope.** This artifact reviews the offline/injected policy; it does not approve a physical transport, install, boot, display or restore. No device commands or source edits were performed by this reviewer.

## Findings and resolution

The first revision's module-private token survived `dataclasses.replace`, allowing a copied policy to change derived authorization fields without repeating the factory gates. The author repaired this with an identity-based `WeakSet`, `@dataclass(frozen=True, eq=False)`, and membership checks in `check_files`, `bind` and the session constructor. Four copied-field cases reject before exchange. This closes ordinary copied-policy authorization; Python callers remain trusted and are explicitly not a security sandbox.

The reviewer also identified a raw descriptor leak if `os.fdopen` raised. The author added close-on-wrapper-failure and a focused descriptor test. Neither repair changed the old SDK-free source.

## Reviewed behavior

[verified: source] `load_policy` requires a separate SDK scope, explicit install/restore direction and `fixed-loader` baseline. It reloads two equal full-size backups, target, sealed plan and checksummed journal. The identity must equal the plan, explicitly identify a non-simulated FM-1_092 unit/topology and bind the baseline hash. The fixed manifest must bind both dump hashes, USB/entry evidence, exact loader/profile/source/reader and the 8757-request inventory. Actual loader/profile bytes are mandatory. Historical campaign path names are metadata; relocated actual files are independently checked.

[verified: source] The exact app `991b569d…` and ELF `8832aa46…` are pinned. Actual ELF/image bytes are audited through the SDK key/eFuse and native startup/recovery gates, rather than accepting supplied audit JSON. The raw gate pins the recorded base-zero payload and stock SPL, checks CRCs, preserves config/tool/reservation/tail bytes, limits app capacity to 691744 bytes, and permits only exact app bytes and directory CRC/length changes. The plan's writable ranges must exactly equal the derived changed sectors, with directory sector `0x4000` last in both directions.

[verified: source] All supporting evidence, six reference files and three fixed-backup implementation source files are captured as bytes and rechecked at bind, run entry and before each mutation. Actual transaction artifacts are reloaded and compared throughout. Final-component symlinks, non-regular supporting files and oversized supporting evidence are rejected. This is not an adversarial filesystem boundary: trusted private ancestors, inherited transaction file access and staged Python dependencies remain operator responsibilities. The runtime does not freeze every imported implementation module; their exact reviewed hashes and the execution snapshot must be pinned externally.

[verified: source] The inherited session seals all injected binding assertions, checks them before and after every exchange, closes/latches ambiguous failures and never retries that handle. Its allowlist contains FC0A/FC14 queries, aligned bounded FD05 reads, and FB01/FB04 only during the matching running transaction with an exact durable operation/address intent. Program data must be the exact direction-bound 256-byte image page, with exact CRC/padding/response shape. It exposes no ROM inquiry/upload/jump, reset, eFuse or arbitrary command path.

[verified: source] The inherited transaction takes a nonblocking directory lock, verifies identity/JEDEC, reads the entire flash and rejects changes outside authorized ranges. A prepared transaction additionally requires baseline equality. It persists each mutation intent before querying/sending, verifies blank erase and complete sector readback, then verifies full-flash equality. Resume uses actual NOR contents rather than journal progress and rebuilds a differing sector; completed journals still require fresh full readback. Failures preserve prepared/recovery-required state and close the bound handle. Directory-last is ordering, not an atomic install or proof of power-loss recovery.

## Acceptance limits and next dependency

The backup log check verifies its prepared/completed envelope, hashes and absence of an ambiguity-stop record. It does **not** replay all 8757 requests or attest successful process exit; receipts correctly retain `backup_log_replay_verified=false` and `historical_entry_only=true`. The eventual physical campaign must independently accept actual backup exit/completion/dumps and tie a fresh live SG session to this provenance.

The external loader initializer at `0x01e00428`, entry-supplied operations and full NOR-status side effects remain inherited native uncertainty. Matching dumps do not close it. SDK healthy-other-core/P33 and board clock/display/recovery assumptions remain physical limits. A future physical adapter needs separate pinned SG/sysfs checks, ioctl status/sense/residual handling, command inventory, durable capture/logging and concrete recovery transitions. This review grants none of those claims.

Semantic navigation reuses the prior evaluated limitation: tools selected the original checkout and rejected the absolute task-worktree path. No shared project selection or MCP restart was changed. Review used bounded file inspection. No local pytest/native build ran. Hera evidence is accepted below.

## Source and handoff state

Shared branch `feature/2026-10-11@installable-firmware`. Observed HEAD and verified remote branch SHA during review: `6e024411651335617204bbb9267043896e3a9158`. Source ownership and checkpoint/push remain with the parent and author; the reviewed snapshot is based on this pushed commit. This reviewer changed only this ignored report. Final source/dependency hashes and evidence acceptance are recorded below.

Parent next step: checkpoint/push the exact reviewed source and tests, then commission the distinct physical SG transport review before any flash mutation.

## Frozen source pins under review

All SHA-256 values below were independently checked against current local bytes. The first two are the author's final v3/v4 source snapshot; Hera evidence is accepted below. Other implementation files have no local diff from the shared checkpoint.

| File | SHA-256 |
| --- | --- |
| tools/fm1_bound_sdk_diagnostic.py | 4718825ab07c05364d3141f9281554b22d3eb2c902af759f4bc68a83ca648847 |
| tests/test_bound_sdk_diagnostic.py | bf56da2f12bb03e159487e4859b52ff0a228de1ee5f962c5016bb100143ad099 |
| tools/fm1_bound_diagnostic.py | 25e57ffda466c898df88370069cf4d7fce02134e141ba95516347c30953d1a36 |
| tools/fm1_flash_transaction.py | d0527efbe74314b30a2cd76897c022a1c7857db888ef6e8f8610dbb329956908 |
| tools/fm1_uboot_read.py | 28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57 |
| tools/jieli/raw_flash_profile.py | 43e4d23f665fac1a73dee2b5ae6e05bc5c3d0ab9bee04b886abad34c6289ae8f |
| tools/jieli/raw_sdk_diagnostic.py | 8c59b67da2c5b66d48dacadf4d90e48bd80272d1868fab21b2a3a80eb1496f07 |
| tools/jieli/audit_sdk_diagnostic.py | e8ce7a43e43ef127ecaf87db55578b7cad7bb1a926f2be3ce92b8688ae7dff8b |
| tools/jieli/audit_link.py | 673daa193891462147e1aab1082e62f339508e801e14de80a4cfabcca9828252 |

The base session, transaction, loader request builder, raw layout/parser and SDK gate were reviewed directly for this task. The exact native/key audit and app/ELF checks retain the earlier independent native review, with current auditor byte pins above. Final acceptance also needs a no-device factory preflight against the root's freshly captured real campaign/dumps/reference/target, because the focused suite uses synthetic NOR/provenance alongside the actual private SDK ELF and fixed-loader/profile bytes. It must check the actual command log fits the 16 MiB evidence bound. That preflight is a dependency for future physical use, not a substitute for live transport/recovery review.

## Final evidence acceptance

[verified: archived bytes and evidence inspection] Source archive `bc923064d7887497fb0a5bc7bb8b560ff7816a74aeb48be9ebe086a6011f7b7c` matches the snapshot, including all 528 recorded file hashes. Independently matched each shard's JUnit node names to the 16-chunk plan: exactly 61 unique tests, zero failure/error/skip; one additional smoke case passed. All inspected containers exited zero, were not OOM-killed, used image `sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`, network none, no host devices, no privileged mode and read-only source mounts. Aggregate records all containers removed. This is offline evidence only.

| Evidence | SHA-256 |
| --- | --- |
| build/sdk-bound-evidence/aggregate-v4.json | d92e818cac50c1d3132e823368a2e9b853d4d33f407875298d158d2385268b83 |
| build/sdk-bound-evidence/snapshot-v4.json | 23ffcf18d51b518a49560607a8758f85af2e71abd2c9ae70236064ff3339a89e |
| build/sdk-bound-evidence/plan-v4.json | ee5fc281ef45a77b256a6735ee0373f84b6c3cda98f86e6cce08effb0904b734 |
| build/sdk-bound-evidence/evidence-v4/smoke.xml | 32d8fe594a9531e20d3267b88fa2ff636753d6e79c20d294ff5b4203c43e8bf2 |
| build/sdk-bound-evidence/preflight-v1/summary.json | b0126b1c796116dfafb0eabd6a81a1bac98c1f610687140001091bd8563415aa |
| install-factory-receipt.json | 0a0fe04afff093f8d9cec1d7666751919234681a3e3fecd104fecdec75ee6d68 |
| restore-factory-receipt.json | a0f3739996202a5b731673f0aad634c16c6b467cd210a1c26713e2c2e3237a0e |

[verified: accepted isolated factory evidence] Both directions passed against actual fresh baseline `96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`, target `df6c963ecd37b334f393c5bc92c2780b6094181308822a03c8190b016a4e97db`, original bench identity, actual fixed-loader/profile, SDK app/ELF and receipt files. The command log is 3,742,884 bytes (under 16 MiB), SHA `e626e30e6ea58d3ee6c01aa199af1b678c75615439429ec54dcd8f905525628e`. Separate plan identity adds expected geometry only; original identity is unchanged. No transport was created; no hardware access occurred; journal remains prepared. The remaining dependency is the separate live transport, bounded install and recovery acceptance.
