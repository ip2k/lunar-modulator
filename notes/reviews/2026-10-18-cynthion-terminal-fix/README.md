# Offline terminal telemetry repair receipts

Source build pin: `13cca5c117e5024a07c2544d42da63f4bf3d22b5`.
This is a separate follow-up, **not a replacement or modification** of the
[immutable historical packet](../2026-10-18-cynthion-recovery/README.md).
Neither new image was loaded. Recovery remains unproven.

- `input-pins.json`: six actual synthesis inputs; all still match current source.
- `pinned-build.py`: exact offline entrypoint, interpreter/dependency assertions,
  source hashes, tool versions and `do_program=False` build module. It expects
  `/workspace` read-only sources, `/output` writable output, `SOURCE_COMMIT`
  matching the pin, and `BUILD_MODE=operation` or `pico-repeat`.
- `verification.json`: imageID, resource/isolation policy, stopped-container
  exit/OOM state, artifact hashes, final routed clocks and test environment.
- `operation/`, `pico-repeat/`: full timing report, compressed synthesis report,
  generated build commands/pin constraints, project-generated experimental `.bit`.
  These are diagnostic artifacts, not accepted recovery or firmware releases.
- `all-tests-final.log`:130passes/348warnings/24.70s across the original eight
  modules and new terminal tests. Warnings include dependency deprecations and
  existing domain-placement warnings exposed by four production-top elaborations.
- `focused-tests-final.log`:11passes/167warnings; three production60MHz simulations,
  legacy/current decoder cases and all four top/profile register-map checks.
- `transient-mutation.log`: substituting the old transient signal in the real
  capture block fails both candidate cases; no-candidate still passes. Mutation
  was temporary and restored before building/full tests.
- `container-build-logs.txt`: stdout from both container invocations. Nonfatal
  read-only cache/font warnings went to SSH stderr and are described below.

Build execution: existing Aeon-only approved dependencies/toolchain. Two isolated
containers, each4CPUs/6GiB RAM and swap limit6GiB/512PIDs, docker-batch.slice,
networknone, read-only root/source/dependencies, no devices, caps dropped,
no-new-privileges, workerUID1003. No infrastructure configuration changed.
Each build checks Python3.12.3 and pinned Amaranth0.5.10/Apollo1.1.1/Cynthion0.2.5/
luna-usb0.2.3/luna-soc0.3.2. Existing OSS CAD toolchain: Yosys0.70+145(a31d95ea0),
nextpnr0.11.1-63-g44a6c739, ecppack1.4-86-ga31ff70.

| Profile | Final60MHz domain | Final120MHz domain | Exit/OOM |
|---|---:|---:|---|
| ordinary operation |66.22MHz PASS|201.29MHz PASS|0/false|
| finite repeat |69.70MHz PASS|187.16MHz PASS|0/false|

Timing files retain both initial placement estimates (53.30/59.78MHz failures)
and final routed PASS values. Acceptance uses the **last** result for each
clock after routing, normal program completion and successful bit packing,
not a grep for any PASS. All clocks constrained by the existing generated path;
no timing-allow-fail flag. Read-only `//.config`, `//.cache`, `//.local` and
fonts.conf warnings are the same nonfatal wrapper behavior as the prior build;
no permissions/cache repair was attempted.

Review performed by coordinator: diff against1499f323, persistent latch/output
and reset semantics, one-shot valid/candidate capture, legacy field preservation,
all register-map consumers, all four actual top elaborations, production divider
phase holds, candidate/timeout/DONE/no-candidate/reset and mutation sensitivity,
unchanged waveform/FSM/PHY/resource/power settings, final timing, fresh pins and
all401historical packet hashes. No separate independent reviewer was dispatched;
Astra's earlier independent audit remains the source of findings, not independent
approval of these fixes. These receipts establish offline diagnostic correctness
and routeability, not loaded voltage, target ACK, CPU reset or ROM acceptance.

Absolute owner paths in text logs are replaced with `<owner>`; original private
scratch logs and complete container inspections are retained locally. Build
receipts expose no device serial, flash UID, vendor firmware or credentials.
`SHA256SUMS` covers every file in this follow-up except itself.
