# Independent recovery route when header poisoning is not assumed atomic

Date: 2026-10-14

## Decision

Do not make recovery depend on a presumed atomic NOR program, CRC-word poisoning, or a VBUS toggle. The supported candidate for an application that no longer runs is an externally generated USB_KEY signal at the FM-1’s physical power-on, followed by observed mask-ROM USB enumeration and the already-reviewed RAM-only loader/read path. This is a candidate route, not yet a verified property of the owner’s unit: this project’s RP2040 dongle is host-tested/simulated only. A separately reported Pico device worked on other FM-1 units, but that does not establish this unit’s boot-ROM timing or any interrupted-write guarantee.

The owner’s FM-1_092 has a different proven route: while the application is running, the reviewed SysEx soft key enters mask ROM, and the reviewed loader took matching full-flash backups and completed a bounded scratch-sector program/readback/restore. That route cannot recover a dead application because it depends on the app accepting SysEx. The later complete stock diagnostic install/restore records are separate successful campaigns, not a test that an interrupted or corrupted candidate image can be rescued using USB_KEY.

No operation in this review touched a device, USB, MIDI, power, or flash. No software-only rollback or ROM guarantee is claimed.

## Route evidence and boundary

| Route | Evidence status for owner’s FM-1_092 | What it can establish | Boundary |
|---|---|---|---|
| Stock updater from a running compatible app | [reported] community rollbacks; repository runbook documents the requirement | Can install a package while the installed application/update path responds | Cannot rescue a non-booting app or a dead USB/update service; a resumable transfer is not bad-image recovery. |
| Exact SysEx soft key to mask ROM | [verified] owner’s 2026-10-07 bench record, later independently used in subsequent reviewed sessions | App-running entry to `4C4A:8057`; reviewed RAM loader; full reads; bounded sector restore | Requires the app and MIDI path to work. Not an independent route from a bad app. The fixed scratch-sector proof was not a whole-image rewrite. |
| External USB_KEY at physical power-on | Project RP2040 implementation is specified, implemented and simulated; not run against owner unit. Simpler Pico dongle success is [reported] on other FM-1s. | If independently observed on this unit, could provide app-independent entry to ROM before the damaged application starts. | Until tested on this exact unit, do not count it as the installation rollback route. It gives no claim about torn flash writes, NOR atomicity, ROM fallback selection, or SPL recovery. |
| ROM + RAM loader | [verified] reached through soft key on owner unit; loader is pinned/audited in notes and used for private full reads | Read/restore capabilities only within separately reviewed command adapters and evidence | ROM enumeration alone is not a recovery; arbitrary writes or a full SPL/image restore are not implied. Respect adapter address allowlists and exact fresh backups. |
| Cynthion / Packetry | [verified] passive normal-mode capture and one identity query in `notes/2026-10-12-cynthion-fresh-identity.md`; later capture preparation hit an exclusive-interface error in `notes/2026-10-12-preparation-stop-trace-capture/physical-preparation.md` | Passive observation of USB packets/enumeration when the FM-1 and USB path are already operating | The official Cynthion analyzer topology places target A/C on a USB traffic path; it does not, by itself, sequence the FM-1’s physical switch or demonstrate CPU power removal. A switched VBUS or USB disconnect is not proof of a battery-powered SoC reset. No custom key-driving gateware or FM-1 electrical control has been validated here. |
| External flash programmer / vendor PC updater | No validated FM-1 procedure | Could be investigated only after exact storage/interface identity and electrical access are established | Not an admitted fallback. Flash is believed in-package; no assumption of a separable chip or safe writer. Vendor updater tools are writers and are out of scope for this research. |

Owner-hardware facts are grounded in `notes/2026-10-07-fm1-softkey-bench.md`, `docs/10-usb-key-dongle.md`, `docs/17-recovery.md`, and `docs/07-recovery-and-risk.md`. The current docs explicitly say the app soft key does not prove broken-app recovery, the RP2040 dongle has not been tried on the owner’s FM-1, and Cynthion capture does not establish a CPU power cycle. The unit is battery-powered and is turned on/off by its physical switch; the retained bench notes observed it disappear from USB after switch-off. Do not equate cable detach, VBUS switching, UBOOT reset, or host port reset with that switch.

### Cynthion capability precision

Primary Cynthion documentation describes CONTROL as the host control connector and TARGET C/A as the target USB connection; the analyzer captures packets traversing TARGET C and TARGET A. The device overview also describes TARGET C as the Packetry capture / Facedancer emulation port. This supports USB observation and programmable USB experiments, not a claim that the stock analyzer can generate this board’s USB_KEY waveform or control the FM-1 battery/power switch. Cynthion documentation also describes USB power pass-through; pass-through changes the USB power path, not the FM-1’s independent physical switch/battery. The owner’s own documentation is explicit that VBUS switching alone is insufficient evidence of CPU reset. Any future custom Cynthion key transmitter would need a separately reviewed gateware/electrical design and observed device acceptance; it is not a current fallback.

Primary references:

- [Cynthion device overview](https://cynthion.readthedocs.io/en/latest/hardware/device_overview.html)
- [Cynthion USB analysis tutorial](https://cynthion.readthedocs.io/en/latest/tutorials/usb_analysis.html)
- [Cynthion safety information, including pass-through voltage/current limits](https://cynthion.readthedocs.io/en/latest/support/safety_information.html)
- [Great Scott Gadgets Cynthion hardware design update](https://greatscottgadgets.com/2023/04-14-cynthion-hardware-design-update/)

These references explain Cynthion’s documented USB/power topology; they do not establish behavior of this particular FM-1 installation or imply it is safe to attach/use for key generation.

## Minimal acceptance sequence before relying on USB_KEY

This is a proposal for a separately scheduled owner-supervised physical acceptance campaign. It is not authorization for this research task to operate the device. Existing project hardware authorization still governs the exact procedure, and any erase/program step requires its own concrete image/range plan plus fresh matching backups.

1. **Identify and prepare without touching the FM-1.** Use the owner’s known unit identity and the current project’s open-drain RP2040 design from `docs/10`; review the exact wiring, polarity strategy, current limiting/pull-ups, and host tool version. Do not use the reported push-pull FM1-transporter wiring. Run the existing PIO/model tests and retain the source/build hashes. Do not infer physical ROM timing from simulator results.
2. **Demonstrate entry, first with no flash command.** With the FM-1 physically switched off, connect the reviewed dongle so the key is present before the owner switches the unit on. Observe and retain the USB enumeration and timing/capture evidence. If ROM does not enumerate, stop and return to normal power state; do not improvise GPIO, vendor updater, or flash commands. This one test establishes only key-to-ROM entry for this unit.
3. **Exercise the read-only rescue path.** In a distinct owner-approved session, use the exact pinned/audited RAM loader. Record fresh identity, ROM enumeration, command receipts and loader hash. Take two complete 1 MiB reads, compare them, preserve their hashes privately, and verify the project’s backup manifest. Do not load the candidate firmware or issue writes during this gate.
4. **Prove recovery from a non-booting image on a sacrificial target first.** A normal entry test does not prove recovery after app corruption or power loss mid-write. Before relying on it as the single FM-1 rollback route, rehearse a controlled interrupted-write/failure case on an AC791N-compatible sacrificial board/target with matching boot-ROM behavior, or obtain owner approval for a concrete, recoverable FM-1 fault-injection plan after a separately verified full stock-return route. The evidence must include: damaged/unavailable app, physical USB_KEY entry at switch-on, ROM enumeration, audited loader access, restoration within an allowlist, full readback comparison, and normal app/stock recovery after a manual power cycle. Do not manufacture this test by corrupting protected SPL/config/OTA data.
5. **Only then consider a separately reviewed candidate-image campaign.** Pin exact image and raw-layout hashes; preserve stock SPL, OTA, cfg and protected ranges; take fresh matching full dumps; journal each allowed range; verify each write and complete final image; retain the USB_KEY and ROM read path for rollback. A successful package transfer is not interrupted-write acceptance. Stop on any identity, readback, or protected-byte mismatch.

If step 3 succeeds but step 4 is unavailable, the correct statement is “ROM entry/read path tested; interrupted-install recovery remains unproven,” not “bricking is recoverable.” A browser installer must not imply that USB KEY is present, that it can reset the FM-1, or that a failed candidate can always be restored.

## Why this route is independent of header poisoning

Earlier CRC-poison modeling considered clearing a single raw stored-CRC bit before payload mutation. Its proof is an idealized byte/bit transform and parser predicate; it does not establish physical NOR interrupted-program granularity, torn-write outcomes, or a chip guarantee. This note does not rely on any of those assumptions. USB_KEY instead requires a physical key observed before boot, then ROM entry observed after enumeration. Even after that is validated, the link from an interrupted physical flash transaction to a recoverable boot state remains a distinct acceptance gate; the mask ROM’s behavior for every partially written layout is not inferred here.

## Artifact scope and follow-up

Research inputs are the exact branch source documents listed above plus the current Cynthion primary documentation. No private binary dumps, loader bytes, credentials, or hardware packets were copied into this note. A separate offline tool’s inability to claim the Cynthion interface is recorded in the existing preparation note; this review does not force-release it or turn a passive identity capture into a recovery test.

Next dependency: owner-supervised physical validation of the reviewed open-drain USB_KEY design on the identified FM-1, starting at the enumeration-only gate. If that route is unavailable, the current project has no demonstrated app-independent software recovery route for an application that cannot boot; investigate a vendor-supported route or a sacrificial compatible target before any candidate installation relies on it.
