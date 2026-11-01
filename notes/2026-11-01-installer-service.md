# Private installer service extraction — 2026-11-01

Personal, non-commercial Lunar Modulator project. Active bounded implementation plan; no device I/O or publication.

Base `492d5079def4cf28e51460bdb97a7f9c225a2841`, branch `feature/2026-11-01@installer-service`, worktree `/Users/likwid/.codex/worktrees/lunar-installer-service-20261101`. Reuse source `cccd21cc5dc82859ed8a5d84f0a7a40646d07353`; no whole-branch merge. Parent owns integration, review, CI and all final release/device gates.

## Planned owned files and dependencies

- Service: `tools/installer_service/{__init__,api,catalogue,continuous_profile,native_profile,provenance,docker_adapter,docker_worker,private_package_candidate}.py`, existing pinned requirements files; add bounded process-capture helper and loopback-only launcher/tests as necessary.
- Parent owns `request_contract.py`: import its BuildRequest, canonical_request and bounded JSON decoding; never duplicate or edit its schema. Parent is separately correcting finite-number parsing.
- Native Python metadata/build closure: `audit_ram_call_allowlist`, `build_application_probe`, `build_demo_image`, `build_probe`, `compact_font`, `companion_selection`, `compile_catalogue`, `diagnostic_profile_contract`, `diagnostic_telemetry`, `embed_image_content`, `evaluate_wavetables`, `firmware_identity`, `flash_layout`, `prepare_demo_selection`, `prepare_image_profile`, `prepare_wavetables`, `recompress_project`, `runtime_mode`, `stack_watermark`, `stage_demo_profile`, `verify_image_profile`. Existing exporter/module_selection remain unchanged.
- Trusted offline pipeline: `tools/native/{capture_trusted_build_tuple,run_trusted_continuous_build,trusted_continuous_worker,create_gpl_source_bundle,source_compiler_headers,source_libcxx_inputs}.py`, `tools/jieli/{trusted_fwsc_package,model_092_app_replacement}.py`. Existing main lunar_state, inspectors/audit_link/package_guard stay unchanged. AST closure is43 Python files including existing dependencies; it excludes runtime-dispatched scripts/build sources and is advisory [verified]. Add only further Python dependencies proven necessary by imports/tests.
- Tests: existing service, continuous/native profiles, worker/adapter build-path, private-package, trusted-package and source-archive validation suites, plus real noisy-child/timeout/descendant-drain capture regressions. No retained firmware fixture is copied.

## Implementation sequence and acceptance

1. Import the exact bounded Python closure, preserve current main modules, integrate shared request schema. Run import/collection and focused pure-Python refusal/security/receipt/profile/SET/source tests.
2. Repair wrapper subprocess capture using bounded concurrent draining, deadline/process-group cleanup and private bounded failure diagnostics. Real Python-child tests establish memory retention/deadline behavior; never execute native wrapper for a real firmware build.
3. Provide an operator-configured loopback-only entrypoint around real fixed Docker adapter and trusted catalogue. No fake production success, no public binding, no automatic image provisioning. Test factory/configuration with injected test-only adapters; production path retains real validators.
4. Document runtime/source-archive prerequisites and unresolved native/hardware/licensing/distribution gates. Commit and push focused checkpoints, verify exact origin SHA, hand to parent for independent review; no PR/merge by this worker.

## Hazards and boundaries

Historical builder constants describe the old native runtime and must never be described as measurements of current integration. Current integration lacks `firmware/native` runtime/linker sources; no native build is authorized in this lane. Do not invent substitutes or copy firmware/engine/app code beyond Python ownership. Missing runtime/toolchain/catalogue must fail closed; real target build remains dependent on a separate runtime lane. Existing trusted wrapper Docker policy uses8GiB, exceeding this task's6GiB execution ceiling; no such job will be launched. Service configuration will be constrained to at most4CPU/6GiB. UI build marker and all actual installation/release/hardware acceptance remain false. No vendor firmware, loader, private capture or credential is imported. FWSC functions are reviewed/tested with synthetic refusal data only unless an explicitly supplied test fixture is authorized.

Rarefaction Python status ready at absolute main checkout; Serena remains at the same absolute main checkout. External worktree orient is rejected as outside root and Serena cannot find new external symbols. Shared roots are not switched; file/import checks and bounded runtime tests provide this lane's coverage. Existing Serena initial instructions were already read this session [verified].

## Lifecycle

Tests/logs under ignored `scratch/installer-service-20261101/`; pytest temporary data removed by runner finally blocks. No daemon/container/download or target compiler will be launched for validation. Keep only small logs and source notes; remove owned worktree after parent integration and verified backup. Built-in free space1125GiB before extraction, above500GiB floor. No new agent spawned.
