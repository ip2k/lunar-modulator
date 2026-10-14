# Independent review: trusted FM-1_092 D7000 package composer

Date: 2026-10-14. Scope was a read-only review of the private implementation in `/home/claude/worktrees/trusted-native-package`, branch `codex/2026-10-14-trusted-native-package`, at base `8a9b78519e1e43a31c151f4c4dd6c9f15601a114`. The reviewed implementation was still dirty/uncommitted. File SHA-256 values at review time:

- `tools/jieli/trusted_fwsc_package.py`: `88066f48d65e661e0ae1aebe6d6773e3fc6278426b8454bfed592179a00df733`
- `tools/jieli/model_092_app_replacement.py`: `942102195708efe3b95fa21f35f1ad75b2fd4761fc8e7c128cf37b2db5ac0081`
- `tests/test_trusted_fwsc_package.py`: `cb8ad262932dc82e40b4ccc66d278f1804766f3d22739138cc1df77becb36d7b`
- Other composer/tests were also dirty in the sibling worktree; their hashes are recorded in the reviewer session and can be refreshed after sibling commits.

The first test run exposed a real digest-contract bug: the tuple’s `prepared_profile_sha256` is the SHA-256 of the retained prepared-profile JSON, while that JSON’s `profile_sha256` names the source profile bytes. Equating those digests rejected the valid fixture. The implementation corrected this by requiring the source-profile bytes and checking their digest against the prepared profile’s embedded field, while retaining the tuple’s raw prepared-profile hash check. The positive real fixture then passed.

The second review finding was that the image receipt needed stronger cross-links. The corrected implementation checks its `verification_sha256` against the tuple’s build-receipt digest, the app length and app/ELF digests, and the firmware identities. It also compares runtime configuration and admission flags. These checks close the observed receipt-substitution gap.

Independent review of the current implementation found a suitably narrow offline boundary: caller must supply a valid, explicit external digest for the canonical build tuple; tuple schema/profile/layout/runtime and false admission flags are checked; source FWSC digest is pinned; catalogue manifest canonical bytes are tied to both the tuple and build receipt, and every listed object is rehashed from supplied bytes; generated/module resources are checked against provenance rows; request, prepared profile, app, ELF and receipts are bound by raw hashes; identities must appear exactly once in app bytes; SAVE/install/hardware flags remain false. The composed FWSC is reopened by the generic parser, outer/header/list/payload CRCs are checked, nested app and protected decoded stock data are checked by the 092 model, and relocated entries are independently reopened. The model’s target-app override is explicit and keyword-only; its historical default app pin remains intact.

Focused validation, run against the sibling dirty tree after its fixes:

```text
/home/claude/mvave-fm1/ci-contract-repairs-20261012/.venv/bin/pytest -q \
  tests/test_trusted_fwsc_package.py \
  tests/test_package500_d7000_candidate.py \
  tests/test_package500_continuous_d7000_candidate.py
16 passed
```

Fixture facts independently checked: D7000 app is 845732 bytes, SHA-256 `ba46bf0a4d1bda4d604223c658b141b4a9068e37f65afddd998af04d5296cfc8`; the public source FWSC is pinned at `ed8415f32f5e2ff5558a24cee45eafd8d0a5b1982af14d4cb88ba019b876eb80`; the exact full 092 unpack is `/home/claude/mvave-fm1/sdk-raw-final-20261011/private/FM-1_092.fwsc_unpack`. The scratch unpack is incomplete and should not be used as a silent fallback. The test fixture now prioritizes the complete retained reference tree and requires its files via model validation.

Limits: this is source/host-test review of an uncommitted worker tree, not a verified coordinator commit, CI run, emitted/published package, stock updater acceptance, device install, runtime/song, rollback, or physical storage proof. The test’s expected tuple digest is fixture-specific; a production caller must receive the digest through an independent trusted coordinator channel. The returned bytes and report deliberately remain noninstallable and hardware-unadmitted. Tuple hashes prove consistency only relative to the external tuple digest; they do not independently attest that the source tree/toolchain claims are truthful.

No blocking finding remains in this review scope. Coordinator should re-run the focused suite against the sibling’s committed SHA, retain the tuple digest independently, and keep all installability/admission gates closed.
