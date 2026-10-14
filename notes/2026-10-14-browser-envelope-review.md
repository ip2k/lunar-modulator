# Browser FWSC envelope review (2026-10-14)

## Scope and result

Reviewed the browser-only outer-envelope inspector and permanently closed package-admission adapter at `sim/web/www/native-fwsc-inspection.js` and `sim/web/www/native-package-admission.js`, introduced by `29c736907369fec20c3cf1ad22901590051d899e` with the private-fixture test follow-up `21614dc69`. Compared the parser to `tools/jieli/inspect_fwsc.py`, the existing offline reference implementation. I found no release-admission bypass or concrete outer-format mismatch in this bounded review.

The JavaScript implementation validates the established envelope layers: the 20x48 FWSC marker/identity slots and 20-byte stripping transform; decoded UFW header size, chip and CRC; indexed entry table CRC and bounds; unique names, supported types and non-overlapping allocations; plain and SFC auxiliary payload CRCs using the logical absolute offset; required `flash.bin`/`ota.bin`; and the terminal `JLUFW` trailer. It adds a 2 MiB inspection bound before making its logical-image copy. The synthetic fixture calls both JS and Python readers and compares identity, logical size, and entry names/types/offsets/size/allocation. This is useful parity evidence, but it does not independently establish remaining nested JLFS/SFC semantics or package correctness.

The browser API deliberately returns only envelope metadata and CRC status, not decoded payload or a logical flash image. `inspectNativePackage` categorizes inputs but keeps `admissible: false`; `verifyNativePackage` unconditionally rejects. Bare app, ELF, raw 1 MiB image, unknown input, malformed FWSC and the structurally valid synthetic envelope all remain blocked. The optional private FWSC test also asserts blocked status, but was skipped in my Mac test run because `LUNAR_PRIVATE_FWSC_FIXTURE` was unset.

## Verification

At Mac integration checkout `7b71d0c625c585ea9f6de3f67fb3e1afb6e3dc4e`, the focused Node tests completed with **7 passed, 1 skipped** (optional private-package fixture unavailable). The reviewed JS file bytes match the assigned Hera review checkout: inspector SHA-256 `ee1affc9c9bb025ba5fc8aaff4f19e188ff11877e97ea7f3416ea817c93ffd83`; admission SHA-256 `e64bd9d9188096ff046866d904ef84d2c0774090f2228d69a2a13aab9cff9634`. Hera did not have Node installed, so the test run used the corresponding Mac checkout. Shared Serena/Rarefaction roots were not retargeted during concurrent work; this review used bounded direct source/test inspection rather than semantic navigation.

## Limits and next step

This validates only the current inspection boundary. It does not establish nested flash/JLFS mapping, protected-stock correspondence, same-version updater behavior, firmware runtime, or admission to any transport. Keep the verifier fail-closed. The next useful increment is to cross-check a trusted package artifact against the full Python package guard and retained stock components in an isolated test, while keeping browser install capability absent until those independent package and physical recovery gates pass.
