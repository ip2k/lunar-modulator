# Independent SDK raw diagnostic review

[verified] Reviewed frozen dirty additions over commit `54037db3fbe9c411b9cbf60dd75ee78d7586e979` on `feature/2026-10-11@installable-firmware` in the installable-firmware worktree. This review changes only ignored review artifacts. No transport, hardware traffic, source edit, commit, push or test suite execution occurred. Root owns Hera verification and integration.

## Finding requiring a small correction

[verified] **P3 — ELF architecture metadata is not checked in the SDK native audit.** `tools/jieli/audit_sdk_diagnostic.py:audit` parses `e_type` and entry but never requires `Elf.e_machine == EM_PI32V2`. The new `raw_sdk_diagnostic.validate_target` trusts this audit for the SDK executable contract. A bounded probe on the frozen actual ELF changed only the ELF header LE16 at offset 18 from `0x00f1` to ARM `40`; both `native.audit(elf, app)` and `audit_link.audit(..., runtime='sdk')` still returned passed. App and all native instructions stayed unchanged. This is a malformed-artifact acceptance gap, not evidence of unsafe executable behavior. Add the same explicit architecture check used by `diagnostic_report.report`, and a mutation regression case. Parent was notified before this report.

[verified] No other actionable defect was found in the reviewed source. Acceptance of this lane is conditional on resolving or explicitly recording the metadata finding and root's focused checks passing.

## Preserved guards and raw geometry

[verified] Original `raw.profile_dump` delegates with the original `d41da612…` loader pin. It cannot accept the new `fe6d1bd3…` manifest. Original `raw.validate_target` still calls `runtime='sdk-free'` then `diagnostic_report.report`, which requires zero pending checks, absence of SDK initcall/key machinery and the SDK-free section/stack contract. Refactors extract the same construction and byte geometry; canonical existing profile/status/hash semantics are preserved. Original emitter still requires its original status and rejects SDK receipts. Existing bound diagnostic preparation still calls this original validator and original loader binding; these files do not silently grant an SDK physical write path.

[verified] The SDK branch independently recomputes key/eFuse audit from the actual ELF and app, rejects any failed key check, then recomputes native image reconstruction, entry/startup/bridge/stack/exception/key scheduling/P33 instruction contracts and exact init/file-cfg registries. A supplied native report must canonical-equal the recomputed report; it cannot authorize bytes. Reconstruction makes app exactly equal contiguous ELF `.text/.data/.dynamic_data/.ram0_data/.cache_ram_data` load bytes. SDK-free ELF is rejected. Link scan's remaining native scheduling pending item remains visible; native gate supplies the independently reviewed byte contract, rather than removing vendor code or relabeling the pending key report.

[verified] Shared raw validation reparses complete 1 MiB baseline and target, requires original SPL/config/cfg_tool/config components and CRCs, and independently verifies unchanged raw ranges `[0,0x4000)` and `[0xacf40,0x100000)`. Decoded differences are confined to `[0x4000,0x4004)`, `[0x4020,0x4024)`, `[0x4028,0x402c)` and the exact supplied app starting `0x4120`. Original app tail, gaps, directory descriptors and reservations cannot change, even after repaired CRCs. SFC transform retains recorded base-zero origin and original bytes outside app payload. Changed-sector list is derived from raw byte comparisons, not receipt claims. Any 4 KiB changed sector crossing a protected allocation is rejected, even if application bytes fit the nominal capacity. The reviewed 120432-byte SDK application ends at `0x21790`, comfortably below protected `0xacf40`.

## Fixed-loader backup classification

[verified] Explicit fixed-loader path requires exact new loader, original-loader provenance, fixed profile hash, profile-source hash, pinned reader dependency, request inventory hash, 8757 command completions, exact two completed matching full dumps, recorded prefix hash, identity/entry-log/USB binding consistency and strict lowercase digest syntax. The original reader/source pin currently equals `28317ee5…`; loader-profile source equals `9664e132…`. Non-dict dump entries cannot evade the checks because exactly two dump entries plus shared unique `dumpA.bin`/`dumpB.bin` matching hashes/sizes are required. Profile includes actual new loader hash and receipt includes explicit baseline-profile. Original path is not relabeled as the new loader.

[verified] Adapter/campaign/entry-log digests are caller evidence at this offline gate. The adapter hash is syntactically constrained, not an approved source pin. This was explicitly intended by root, is documented by the entry point, and does not grant physical approval. Actual fixed-loader campaign adapter source, command inventory recomputation, current USB topology, entry freshness, live mapping and successful durable backup publication must be reviewed and bound separately. The separately evolving fixed reader was inspected only for manifest compatibility; this report does not certify its implementation or assume the other lane finished.

## Output and test review

[verified] SDK builder validates the baseline profile before construction, constructs only the same app/CRC/length delta, then calls independent SDK target validation before output. Its status differs from SDK-free receipts. Shared emitter verifies immutable 1 MiB target/hash/status/unemitted/unapproved receipt, creates a new 0700 directory, syncs its parent, exclusively saves 0600 target and fsyncs it, syncs directory, exclusively saves/fsyncs `.receipt.json.pending`, atomically hard-links it to `receipt.json` without replacement, removes pending and fsyncs directory. Existing partial receipt-write and fsync-failure tests remain applicable because implementation is shared. An exception after linking may leave a complete valid receipt; a successful return plus final directory sync is the durability acceptance, and no existing directory can be reused.

[verified] Inspected SDK raw tests cover original-versus-fixed provenance, missing/differing evidence and identity/USB bindings, incomplete dumps, actual ELF SDK construction compared against independent fixture geometry, old gate/emitter rejection, protected/tail/gap/app/native-instruction/audit mutations and fixed provenance retention. Actual tests require `LUNAR_SDK_ELF`; without it those cases skip. Fixtures replace only stock provenance hashes for public synthetic layout, so these tests do not establish physical recorded backup acceptance. Inspected existing raw/builder tests cover CRC/format/reservation/sector boundaries, strict references, rejected candidate profiles and exclusive receipt publication. Root's focused Hera results are still a dependency; no duplicate suite was run here. The only executed probe was the header-metadata mutation above.

## Physical and artifact limits / next dependency

[verified] Native SDK audit is a set of instruction/registration contracts, not an immutable hash of every owned-worker or closed-runtime byte. It does not establish the application has booted or displayed pixels, guarantee bounded P33 lock acquisition with a halted peer, or prove all conceivable NOR paths absent. `build/sdk-diagnostic-independent-review.md` supplies the independent owned worker and reachable ordinary startup/NOR investigation for the exact frozen candidate. Keep exact app/ELF/source hashes and that independent review at the concrete physical adapter gate; a future candidate can satisfy selected contracts while changing unrelated worker behavior and needs fresh source/native review.

[verified] Frozen app SHA `991b569df7d131320e42ef34c1b619de586d2a7ba6236c0ea1c089731eb61fa9`; ELF SHA `8832aa4677a7da3aa7871da58a092e5c3e69d766b31d5e67744301ce437979e2`. Native artifact manifest still records baseline source commit `bdbf2d3`; owned staged source hashes and native bytes were independently checked in the prior report. A later commit-only manifest refresh may change manifest bytes but must not silently change native or staged-source bytes.

[verified] **Next step:** root adds the architecture check/regression, supplies focused Hera results, commits/pushes these source changes and records their final hashes. Then review the final fixed-loader backup adapter and explicit SDK live-bound writer/recovery campaign, obtain and compare fresh owner-unit backups, construct the private target from those exact backups, and retain directory-last sector verification/restore gates before physical boot/display/reset acceptance. `hardware_ready=false`; no binary distribution or hardware authorization is implied by this review.

## Source pins

[verified] Hashes at independent inspection; any source change requires targeted rereview.

| Source | SHA256 |
| --- | --- |
| `tools/jieli/raw_flash_profile.py` | `43e4d23f665fac1a73dee2b5ae6e05bc5c3d0ab9bee04b886abad34c6289ae8f` |
| `tools/jieli/build_raw_diagnostic.py` | `d1aafdaec887b5a041aefc19176fdcd7a25bdef1d5340996a9c86a3b000d9971` |
| `tools/jieli/raw_sdk_diagnostic.py` | `8c59b67da2c5b66d48dacadf4d90e48bd80272d1868fab21b2a3a80eb1496f07` |
| `tools/jieli/build_raw_sdk_diagnostic.py` | `3f4c9b82abacbfc78f22b23b2e6baeb1fea6ae7f8f75d541c88235f05fa47580` |
| `tests/test_raw_sdk_diagnostic.py` | `94ab1b848316da2c61772421409b97ee0b91729e3dc5cee7b62c9ef407134f7b` |
| `tools/jieli/audit_link.py` | `673daa193891462147e1aab1082e62f339508e801e14de80a4cfabcca9828252` |
| `tools/jieli/audit_sdk_diagnostic.py` | `5b2a8d67c73115f171808320211a266c6d39c9733d6f3900c23f15cb06867a5f` |
| `tools/jieli/diagnostic_report.py` | `d85f2ca1dd70adc015b724b46d3c332c307509ad91fa6faa86adc5fc45e755cf` |
| `tools/fm1_uboot_read.py` | `28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57` |
| `tools/jieli/loader_config_profile.py` | `9664e1329d8259362da78c047ce2d6003dfe8df2850f02703f98e8b6bf277cd8` |
| `tools/fm1_bound_diagnostic.py` | `25e57ffda466c898df88370069cf4d7fce02134e141ba95516347c30953d1a36` |
| `tests/test_raw_flash_profile.py` | `45274e133929ac082162e397f86eaff24b98ef2fdcf263d7080bb4747aad9080` |
| `tests/test_build_raw_diagnostic.py` | `bca12506b5d750c779004b8af17f08fce4427f0f2dff63d2aec8c9e85fef5087` |

[verified] Machine-readable evidence is `build/raw-sdk-diagnostic-review-evidence.json`. Parent owns saving any durable repository note and source backup; ignored review artifacts are not a pushed source checkpoint.

## Correction rereview addendum

[verified] The P3 ELF architecture finding above is **closed** in the corrected source. `audit_sdk_diagnostic.audit` now requires both `ET_EXEC` and `EM_PI32V2` plus the stock entry before reconstruction/instruction checks. Source SHA256 is `e8ce7a43e43ef127ecaf87db55578b7cad7bb1a926f2be3ce92b8688ae7dff8b`. The original five reviewed source hashes remain unchanged.

[verified] Inspected the new actual-ELF parametrized metadata regression in `tests/test_sdk_diagnostic_build.py`, SHA256 `001d1004296bf06d60bf92794008db9c04ac07ee68688fb549f6d068435c2e77`: it first verifies the actual ELF/app succeeds, then mutates only offset 18 to NONE (0), ARM (40) and RISC-V (243), requiring the explicit pi32v2 rejection. It requires the private fixture environment variable rather than pretending synthetic bytes are the actual candidate.

[verified] Independently executed only the same bounded audit probe: unchanged frozen ELF/app passes; each of the three header-only architecture mutations raises `ValueError: Expected pi32v2 executable with stock app entry 0x02000120`. No full suite was repeated. No new finding. This correction does not change firmware/native bytes or the raw target geometry. Root's focused Hera results, exact physical adapter pin/live backups and actual boot/display/restore remain the next acceptance dependencies; hardware readiness remains false. Earlier finding text and old audit-source hash remain historical initial-review evidence, superseded by this addendum for current acceptance.
