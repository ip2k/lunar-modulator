# Exact offline strict Pico image pin — 2026-11-01

[verified] This source update supplies the reviewed-image manifest for the corrected strict Pico artifact built from **ff1fed64c180a4e604f21bf6d34146f295f7f859**. It populates the existing host digest trust anchor; the only executable host change is that constant. CLI/schema, private test seam, whole-phase deadlines, durable no-overwrite campaign records, namespace guards and unknown-outcome/spent behavior are unchanged. No discovery, retry, post-call command, installer route or transport implementation was added.

## Source and artifact basis

[verified] Before setting the pin, read the complete independent `rom-return-transport-review/target-ff1fed64/REPORT.md` and `rom-return-build-next/actual-build-ff1fed64/HANDOFF.md` in private performance scratch. The build's Git tree equals source-approved27c3736b. The independent emitted-code review passed all22 STLB release sites across13 source exits, restoring PRIMASK from a private saved value after unlock. That review is specific to the retained ARM artifact; it is not target execution or physical qualification.

[verified] Read-only rehashes of the held actual output agree with the independent record: UF2 **144384bytes**, SHA256 `fecc4f116e212bed5906e7519a93ffe4907e1c93229307c43736b97f85dcbfaf`; ELF SHA256 `3599d7e81c3f46d84bd2bf037e064e89442ab07407e13fb342869f28c046844c`. No target binary was copied or committed. Retained recipe, patch and build-manifest hashes were separately compared with exact ff1fed64 Git bytes.

[verified] New `firmware/rom-witness-return/reviewed-pico-image.json` uses the existing strict schema. Its exact raw SHA256 is **84f294a2140e4425f764e5597c9618d9c571f4952b3d2baed3c78938d30dc5a7**, pinned in `rom_return_once.py`. It binds:

- The original host/contract source basea7a1c310, frozen contract6f5b203a, native return-payload source manifeste03ef5e0 and exact512-byte plaintext payload898b7737.
- The separately built strict source commitff1fed64, recipe8da6d6ac, Pico build manifestd102b5fa, exact three-patch inventory (corrected0003 is808264d0), upstreama7fb5e8a, boardpico2_w and fixed source/USB identity.
- The exact final UF2 size/hash above, rather than a source-ID or self-hash claim.

These identities have different roles. `source_base` stays at the original contract source; `strict_source_commit` names the actual Pico build input, not this later host-pin commit. The Pico build manifest deliberately keeps its own `uf2_sha256:null` and `hardware_admitted:false`; this separate reviewed-image record binds the later final output. No self-referential digest or fabricated flashed attestation is introduced. Manifest bytes must match exactly; no CLI/environment pin or approval-flag bypass exists.

## Checks and limits

[verified] Focused macOS run: **177passed,1expected retained-native-artifact skip in4.61s**, covering `test_rom_return_once.py`, `test_rom_witness_return.py` and fake-only `test_rom_return_build_recipe.py`. New checks exercise the actual committed manifest/default host pin with fake serial only, compare current recipe/patch inventory, refuse12 identity/byte mutations before campaign creation, retain all admission/qualification flagsfalse, record exact UF2 identity and refuse a second call without another write. Explicit UNSET private-seam refusal before file reads remains tested; the CLI refuses an invented manifest before campaign allocation. Existing writable-ancestor/race/descriptor/persistence/deadline/crash/concurrency cases remain active.

A first test-selection command named a nonexistent recipe-test file and collected no tests; its error log is retained. The corrected actual filename was inspected before the successful run. All temporary pytest/input/campaign directories were under owned project scratch and removed in the same flow. Small source-bound receipts, derivation hashes and test logs remain privately under `audit-20261101/rom-return-reviewed-image-pin`; no dependencies, downloads, target build or device action occurred in this lane.

[verified] Rarefaction primary Python profile is ready but rejects this external worktree's orient/scope at the workspace boundary. Serena absolute `_preflight` symbol lookup matched direct source; the shared primary project was not activated or restarted. Exact Git/source and retained artifact records are the basis here.

This pin removes the offline missing-image prerequisite only after independent source review/integration. It does **not** attest the flashed Pico image, identify the target ROM, prove cold power-off, qualify RTS/RETS ABI, fetch/cache coherence or watchdog lease, prove endpoint abort/quiescence or electrical silence, authorize a serial connection, or claim installation/recovery acceptance. All host result hardware/ABI/cache/watchdog/install flags remainfalse. Root separately owns required CI, exact artifact deployment/provenance and any explicitly authorized physical experiment. Existing source/artifact review justifies the offline identity anchor; physical qualification remains a separate gate, not an assumed prerequisite result.
