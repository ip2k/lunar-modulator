# Generic D7000 diagnostic flash policy

Date: 2026-10-14

## Outcome

[verified] Added an offline-only policy for the content-free FM-1_500 Trio pulse candidate. It derives a transaction from the exact stock 092 raw pair, exact current D9000 image, and the D7000 candidate. The path has no transport opener or command-line flash operation. Hardware, installation, package, and writer admission remain false.

[verified] The candidate transition preserves the boot prefix [0, 0x4000) and current suffix [0xD9000, 1 MiB), restores [0xD7000, 0xD9000) to the pinned stock image, and puts the app-directory sector last. Restore is direction-bound to the original transaction baseline.

## Frozen build evidence

[verified] _check_build() passed against the actual frozen run-5 receipt and artifacts at /home/claude/.local/share/codex-private/trio-pulse-frozen-build-20261014/run-5/. The externally pinned receipt is frozen-build-input-receipt.json, SHA-256 136dad341994bee22919e115a04951ad983935729023bbc6b648c7b9b29c3ce2. Source commit/tree: 66196f54f3295cfdec14a2924c767235bbd5cc2c / 483e0fa782650c2158eae979f1830960c5f86a96. App SHA-256 3de52e9bddd24c19fbabaa3cc7cec97ea78ef0a2397debfc009befb1f8b9b6bc (807320 bytes); ELF SHA-256 a07fbd8e966873c154bfc4f62fc1d9b608004e7d1c56640f59a762959d324e6e.

[verified] Frozen source, toolchain, catalogue, and prepared-profile manifests are checked against the receipt and the coordinator-supplied input pins. Receipt outputs are checked against exact app, ELF, verification, artifact-receipt, and disassembly bytes. No image.json or build_tuple.json was created or inferred.

[verified] Full prepare() has not passed: the coordinator has not supplied a fresh paired-read bundle for the current device. Historical device-53 evidence is not used as current admission.

## Restore binding

[verified] A restore bind after the original read's 120-second freshness window requires a new verified paired-read on the same stable physical USB port. The fresh transport may have a different enumeration number and SG node/inode. Its complete fresh mapping and read hashes are bound to the new transport.

[verified] Before any erase or program, the transaction rereads the full flash and requires its SHA-256 to equal the fresh restore manifest's current-flash SHA-256. The original transaction baseline remains the restore target; the fresh partial/current image cannot silently become the baseline.

[reported] The original stock 092 raw pair is retained in private scratch, but it is not a fresh physical recovery plan or proof of restore behavior.

## Checks and limits

[verified] Focused command: pytest -q -p no:cacheprovider tests/test_generic_diagnostic_flash.py in the pinned Python 3.12 container with network disabled and bounded CPU, memory, swap, and process limits. Result: 6 passed.

[verified] Synthetic tests cover interrupted ambiguous completion, direction-bound install/restore, stale original-read expiry with fresh restore read, wrong physical port refusal, changed devnum/SG acceptance on the same port, and refusal before mutation when the transaction's first reread differs from the paired-read digest.

[reported] The restore verifier is stubbed in the focused synthetic binding tests. The real frozen build receipt and output pins were checked independently. No physical transport, flash operation, installation, boot, package acceptance, or hardware admission was performed.

## Next dependency

[reported] Supply a fresh paired-read bundle and externally pinned input record for the generic adapter to exercise full prepare() without reusing the historical device-53 receipt. An independent review should then exercise the RehearsalSG shim against the exact policy API before any separate physical plan is considered.

## Offline full-prepare replay (historical bytes; simulated verifier)

[verified] Full prepare() wiring succeeded using the actual frozen run-5 build artifacts, exact stock baseline/reference files, independently reconstructed candidate, and retained full-image bytes SHA-256 145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657. Input record: /home/claude/.local/share/codex-private/trio-pulse-d7000-corrected-66196-20261014/candidate/offline-replay/input-record.json, SHA-256 b72ad381d8362b95d5906ee01b47c7cdb6ca53c5f830b7a97ae24be0ba48db12. Prepared receipt SHA-256 5e6e4ab5a998a86792f8f2bffdc479e300afe426073be55f67e513377b65900a; transaction plan SHA-256 3b9cc7335cc191133ec90d6ad5bcadf15483ad39d0f30efbaa5694cd2336a192; 210 changed sectors.

[reported] To preserve the production generic read verifier unchanged, this replay injected a simulated verify_read_bundle result over the retained real 145c bytes and a synthetic USB/SG mapping. It did not validate the historical device-53 transcript with the generic verifier and is not a live/fresh read or admission. The prepared transaction artifacts are offline analysis outputs only.
