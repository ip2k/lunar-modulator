# RAM-only recovery probe proposal

Independent MIT experiment; built offline on Hera, **not uploaded or executed**.
This is a recovery prerequisite experiment, not the installable-image milestone.
The separate `tools/fm1_ram_recovery.py` prepares the exact-image ROM-only
transport, with no CLI entry point. It requires the exact owner reply and a
fresh (120 seconds) same-port normal-to-UBOOT entry record, binds that record
to the opened SG device, permits two exact encrypted blocks and one jump, and
latches every transport failure. The existing backup reader still accepts
only its audited vendor loader; its allowlist has not changed.

[verified: target build] The 700-byte initialized image starts at `0x01c02000`.
SHA-256: `4498aabad49b5acf1c4f90d949463b590e76e56acf80d6e6d01b292ee9d32c42`.
Its linker reserves `0x01c02000..0x01c06000`; actual BSS plus both 4 KiB
stacks end at `0x01c04300`. There are no named undefined helpers.
Artifacts are ignored under `build/jieli-ram-recovery/`; Hera source/output:
`/home/claude/mvave-fm1/ram-recovery-20261011/{src,out}`.
Build using `tools/jieli/build-ram-recovery-in-container.sh` with the same
pinned toolchain and container as the diagnostic links.

Startup disables interrupts, installs its own SP/SSP, preserves incoming r0,
clears bounded BSS and checks current core zero. It calls only the fixed
recovery component, then loops if reset fails. It deliberately never returns
through the unproven ROM caller ABI. The sole external writes are the retained
16-byte marker at `0x01c7fd80` and fixed P33 CON/DAT at `0x13e08/0x13e0c`.
It changes no flash, SPL, OTA, cfg, clock, pads, timer, IRQ routing, write guard
or secondary-core release state. See `../recovery/README.md` for prerequisites.

## Outstanding execution contracts

[inferred, untested] ROM RAM entry, inherited write protection, P33 availability,
mailbox retention and secondary-core inactivity are not established by this
build. Checking current core zero does not prove the other core is stopped.
The diagnostic RAM state is not currently accessible through a reviewed
transport. A transmitted request is not proof that reset occurred.

[verified: offline] The exact-image transport has been prepared and tested,
including per-block encryption, fixed length/address, fresh owner-unit
identity/UBOOT enumeration and one jump attempt. Hera passes the transport and
existing backup guards; all 65,536 opcode values are exercised. An independently
executed upstream decoder reproduces all 700 bytes plus 324 zero-padding bytes.
These checks do not prove that ROM executes this custom image. No flash/loader/eFuse or
arbitrary-memory operations may be added. A jump transport timeout is an
ambiguous outcome: observe USB, never automatically repeat the jump.

Acceptance needs a recorded pre-entry inventory, fresh UBOOT entry, probe
execution and a distinct post-probe USB enumeration as `4c4a:8057`. Existing
UBOOT enumeration alone cannot prove this probe worked. Record failures too.
If reset fails, stop and have the owner power-cycle; flash remains intact.
Then verify return to normal stock operation. Full broken-app flash restoration
remains unproven and is not established by this RAM test.

## Optional Cynthion instrumentation

[verified: upstream documentation] Packetry 0.5.0 adds Cynthion analyzer VBUS
power control: https://github.com/greatscottgadgets/packetry/releases/tag/v0.5.0.
Wiring: CONTROL to capture host, TARGET C to USB host, TARGET A to FM-1.
When capture and target use the same host, those connections must be on
different hubs: https://cynthion.readthedocs.io/en/latest/tutorials/usb_analysis.html.
Capture reset/enumeration transitions and test installed power-control support.
USB VBUS cycling must not be assumed to reset the battery-powered FM-1;
verify behavior before using it as unattended recovery. No Cynthion power or
firmware change has been performed in this session.

[verified: read-only bench] Cynthion r1.4, analyzer protocol 1.1, is attached
to bench01. Its existing `/home/claude/cynthcap-test/cynthcap` can list it. This
capture tool explicitly preserves power-control bits and cannot switch VBUS.
Current Cynthion and FM-1 connections both appear on USB bus 003; check the
new wiring against the different-hub requirement before capture.

[reported: owner, 2026-10-11, later instruction] Cynthion is deferred. The owner
accepts leaving the FM-1 in UBOOT or hung until a manual power cycle hours
later; lack of an immediate power-cycle fallback no longer blocks the exact
reviewed RAM experiment. Use one attempt, stop on ambiguity, and retain the
receipt. Cynthion wiring and USB power control remain a later experiment.

[inferred: independent source/artifact review] A distinct post-jump UBOOT
enumeration is consistent with the intended reset but cannot prove P33 code
execution: a ROM watchdog reset and a retained marker can resemble it. Keep
that causal claim unverified without an independent observable readout.
