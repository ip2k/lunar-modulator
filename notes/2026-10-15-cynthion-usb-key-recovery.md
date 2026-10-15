# Cynthion USB_KEY recovery preparation

Status: corrected disconnected hardware check **passed**. Both TARGET ports
were empty during configuration. The corrected powered operation image is
loaded, disarmed and ready for the owner-controlled TARGET-A-only attempt. No FM1 was attached or keyed, and no FM1 recovery
acceptance exists.

## Corrected disconnected hardware acceptance

[verified: coordinator execution] Volatile upload of source d65bd636 image
SHA-256 `f5b95db86df7a7b7b6821182bef033c3c54a300aa749ad38cbe154ffa5831463`
completed with both TARGET ports empty. Final routed timing passes 60 MHz USB
and 120 MHz fabric requirements (166.39 / 234.69 MHz maxima). Generated JSON
has all VBUS and discharge controls zero. No configuration flash or MCU firmware
was written.

[verified: read-only JTAG at Unix time1792106363.4083872] Registers1..11, hex:
`4c554e52,3,27d7,0,0,0,01010101,c6,f,c6,ff0d7a`.
DONE7, PHYready1, PHYfault0, self-test mask15, valid mask15; observed sequence
[2,1,0,3] equals expected K/J/SE0/SE1, with one RXCMD event per step. Failure
registers are zero and live GPIO outputs/OEs are released. This image was subsequently replaced by the reviewed operation image below. Logs: local
`scratch/cynthion-usb-key-20261015/phy-swap-v1/disconnected-upload.log` and
`disconnected-status.json` in the same directory.

[verified] The explicit USB3343 register0x39=0x06 board profile resolves the
previous physical J/K reversal. [acceptance limit] Disconnected loopback does
not test ROM key recognition, acknowledgement, SOF acceptance or USB enumeration.
The corrected unpowered operation image9506... is not the selected trial image.

## Operation image ready for owner key attempt

[verified: Hera build / coordinator artifact review] Source d65bd636, command
`python -m tools.cynthion_usb_key.build --mode operation --target-power-from-control --build-dir /out/build`.
Bitstream SHA-256
`30a3ca6c46a2f0594957758a4d1ba90196b6918869d13445be040c1f8569ef3c`.
Final routed maxima164.15/230.15 MHz pass60/120 MHz requirements. Coordinator
independently parsed generated JSON: CONTROL VBUS1, TARGET-C0, AUX0, discharge0;
all four controls actively driven. Build/control receipt SHA-256
`5bab44a32b72696b70938c1bbed01fc41df3ee95a0645217d210f1e962ad4428`.

[verified: coordinator volatile upload and read-only JTAG] With both TARGET
ports empty, upload completed. At Unix time1792106469.461785, status0x4410
means SAFE0, PHYready1, no PHYfault, operation mode, CONTROL power selected.
GPIO snapshot0 confirms outputs released. Registers1/2 match LUNR/layout3.
The operation image is currently loaded. Local artifacts:
`scratch/cynthion-usb-key-20261015/control-power-operation/` including
`upload.log`, `disarmed-status.json` and the exact build products.

[owner action pending] Owner was instructed to keep CONTROL on Mac/TARGET-C
empty; switch FM1 off and connect TARGET-A; press/release USER once, immediately
switch FM1 on within10seconds; leave powered on and report completion. Do not
connect TARGET-C/bench host until coordinator observes terminal/high-impedance
state. No physical key attempt or ROM entry is yet claimed. Passive bench01.local
inventory before this attempt contains KA6/root hubs and no FM1.


## First disconnected hardware check

[verified: coordinator execution] The disconnected-only image, SHA-256
`676c84d4d7ed519282d8c9e073a79889b774d2ac88780cdf8d7a44fad8f22152`
(115790 bytes), was loaded using `cynthion run --bitstream`. The CLI reported
configuration complete; no FPGA configuration flash or MCU firmware was written.
The image cannot enter KEY and holds all VBUS/discharge outputs off.

[verified: read-only JTAG] Registers 1/2/3 returned `0x4c554e52`, `1`, `0x2418`:
FAULT state8, PHY ready, no PHY fault, self-test mask0, valid SE0 observation,
self-test mode, CONTROL target power off. Thus register initialization/readback
passed but the first K-state loopback did not. Terminal FAULT releases the GPIO
outputs. This was the initial image; it has since been replaced by the corrected image above. Logs and literal telemetry:
`scratch/cynthion-usb-key-20261015/disconnected-upload.log` and
`scratch/cynthion-usb-key-20261015/disconnected-status.json` (local artifacts).

[inferred] Possible causes include GPIO drive/sense behavior or insufficient
observation dwell; none is established. Next revision adds longer dwell and
latched GPIO/RXCMD diagnostics without making KEY reachable in self-test mode.

[verified: offline integration] 91 focused tests pass across actual-LUNA ULPI
simulation, protocol regressions and the two backup admission paths. These
checks do not override the failed physical loopback.

## Earlier diagnostic checks and source correction

[verified: disconnected four-state characterization] V4 image SHA-256
`c5e46d1cbebaf7213c8337945b8c1066941826779a9fd836e12b90d91dd7accb`
was loaded volatily with both target ports empty. Expected raw levels
`[2,1,0,3]` yielded PHY observations `[1,2,0,3]`, one RXCMD event per step,
valid mask15 and pass mask12. The image completed characterization, then
FAULT/high-Z. Telemetry is in the local `disconnected-diagnostics-v4-status.json`.

[verified: source cause found] The standard Cynthion platform inherits
`ulpi_extra_registers = {0x39: 0x06}` from
[`platform/core.py`](https://github.com/greatscottgadgets/cynthion/blob/dd2340e20de66341b73c6276cf1654800b655db2/cynthion/python/src/gateware/platform/core.py#L55).
The USB3343 IO/Power register bit1 swaps D+/D- to compensate PCB routing.
Our standalone initializer bypassed the standard ULPITransceiver and omitted
that platform setting. An explicit r1.4 profile now writes/reads back 0x39=0x06
before granting drive permission. GPIO mapping and RXCMD decoding stay intact.
97 focused integration tests pass, including mismatch rejection; fresh physical
loopback validation was pending at that source checkpoint; it passes above.

[verified: second disconnected check] Diagnostic v3 image SHA-256
`62e4112c6b3da0d7adfaf293bac6c125706166fd86d23c49f303d6b1f2a10668`
passed routed timing (176.46 MHz / 212.59 MHz against 60 / 120 MHz) and was
loaded volatily with target ports empty. The new 1 ms dwell still failed at
step0. JTAG registers1..10: `4c554e52,2,2418,0,61,3a,1,1,1,c6` (hex).
Failure reason1, expected K2, observed J1, exactly one RXCMD event; GPIO
failure snapshot has input K2, output K2 and both output enables asserted.
After failure the live GPIO snapshot is zero and outputs are released.
The unexpected opposite line report motivates full disconnected four-state
characterization and a pin/receiver mapping review; no swap is established.
Literal telemetry is saved in
`scratch/cynthion-usb-key-20261015/disconnected-diagnostics-v3-status.json`.
No FM1 was connected. This diagnostic image has since been replaced.

[verified: owner] Both Cynthion TARGET ports are empty; CONTROL remains on the
Mac. Preserve this state until disconnected checks pass. The FM1 lost power
after the interrupted stage7 installation. Its current flash contents are
unknown and retained-RAM-loader admission is invalid. The original backups and
interrupted journal remain recovery anchors, not current readback evidence.

[verified: initial read-only host inspection] Installed Cynthion software is 0.2.5,
with Apollo 1.1.1. The current analyzer reports bcdDevice `0104`, matching the
r1.4 mapping in the official getting-started documentation. No `--force-offline`
or configuration command was used for this inspection.

## Source findings

[verified: exact r1.4 schematic] R58 and R57 provide 1 kOhm series paths from
FPGA N4/P3 to target D+/D-. Bank 6 VCCIO pins J6/J7 connect to +3V3. These are
schematic facts, not measurements of the connected board. The standard platform
declares the monitor pins as inputs; a custom output-capable resource is needed.

[verified: datasheet] The USB3343's Function Control OpMode `01` disables its
USB drivers and terminations. In normal synchronous ULPI operation, RXCMD
reports line-state changes. PHY reset/startup has different bias behavior, so
FPGA drive must remain high-impedance through startup, register configuration
and readback. Reset-low isolation cannot simultaneously provide active ULPI
sensing. Charger controls and OTG pull controls require explicit review too.

[inferred] A non-driving PHY receiver can observe the target side of the
resistors while the FPGA generates the recovery waveform. This could support a
disconnected four-state loopback test and distinguish a real ROM clamp from
the FPGA's own output. The corrected disconnected test above demonstrates the loopback path on this board; ROM acknowledgement remains untested.

High-impedance GPIO samples alone cannot qualify the ROM acknowledgement:
the ROM's reported 15 kOhm pull-downs also make both released lines low. The
existing Pico model's strong external pull-ups are absent here. Simulation
must include absent/unpowered-device cases and must not report those as ACKs.

## Staged implementation and physical checks

1. Build and simulate the bounded protocol state machine and a separately
   reviewed ULPI configuration/readback module. Default to disarmed, no VBUS
   passthrough, no discharge, and high-impedance key outputs. Require explicit
   arming and a finite deadline; faults and completion release the bus.
2. Review the exact top-level pin, clock, reset, PHY, power-switch and generated
   implementation constraints. Build on Hera in a bounded container. Simulation
   and timing closure do not establish electrical or ROM acceptance.
3. With both TARGET ports still empty, use only volatile FPGA configuration.
   Verify initialization and receiver loopback before enabling an FM1 trial.
   Do not flash FPGA configuration storage or update MCU firmware.
4. Announce readiness with concrete cabling, arming, power and timeout steps.
   The FM1 must not share the key-driven bus with the bench Pi. A new owner
   power cycle and a fresh ROM enumeration are separate required observations.
5. After genuine ROM entry, admit a fresh cold-ROM read path and take two
   durable full-flash reads before proposing any repair write. Never forge
   normal-app softkey lineage or retained-loader continuity.

## Volatile analyzer restoration

[verified: installed CLI source] `cynthion run --bitstream PATH` uses JTAG
`configure`, while `cynthion flash` writes configuration flash. `cynthion run
analyzer` similarly configures the installed analyzer without flashing it.
The CLI requests Apollo access by forcing the FPGA offline for `run`, which
interrupts capture. These commands are a reviewed plan, not an execution log.

The installed r1.4 analyzer asset has SHA-256
`5afd1741247da483876bbc7b0d87606ef34503558f31f638162409cb2f0ea5da`.
Recheck its digest before restoration. Restore with target ports empty and
confirm analyzer identity before reconnecting a normal capture topology.

## Offline implementation checkpoint

[verified: integration tests] ULPI initialization now accepts the installed
r1.4 nested pin resources and exercises LUNA's actual register-window logic.
Seven focused simulations pass, including a stalled transaction at the global
deadline. Deadline/fault inhibits ULPI output-enable and STP. These are simulated
bus checks, not physical receiver or recovery acceptance.

[verified: integration tests] The separate cold-ROM paired-backup adapter and
unchanged fixed-loader adapter pass 75 offline tests. The cold path preserves
the exact reviewed RAM-loader/read inventory and labels acquired flash
unclassified. Its schema separates coordinator upload/JTAG evidence from owner
physical unit selection and key action, without inventing a fixed status ABI.

[verified: Hera preparation] The task-local FPGA toolchain is ready in
`/home/claude/lunar-cynthion-toolchain-20261015`, mounted as `/work` in bounded
containers. OSS CAD Suite linux-x64 2026-10-14 archive SHA-256 is
`a6ccc6b96b2d985336a1061c78b2fd2bdd73e0f68690da17db88e00457881a11`,
verified against the official release asset digest before extraction.
Versions: Yosys 0.70+16 (`3bb533450`), nextpnr-ecp5
0.11.1-63 (`44a6c739`), ecppack 1.4-86 (`a31ff70`), Python 3.12,
Cynthion 0.2.5, Amaranth 0.5.10, LUNA USB 0.2.3, Apollo 1.1.1.
Installed r1.4 platform import succeeds. Later synthesis/timing results and
physical failures are recorded above. Toolchain and build products remain
outside Git. The latest focused integration suite passes 97 tests; corrected physical
loopback acceptance passes as recorded above.

## Primary references

- [Exact r1.4 hardware source](https://github.com/greatscottgadgets/cynthion-hardware/tree/13aa71c2fb0be3837cd2ec580ee5d2c25fc1c678),
  especially `target_port.kicad_sch`, `bank6_7.kicad_sch` and `usb_phy.kicad_sch`.
- [Platform source](https://github.com/greatscottgadgets/cynthion/blob/dd2340e20de66341b73c6276cf1654800b655db2/cynthion/python/src/gateware/platform/cynthion_r1_4.py).
- [Microchip USB334x data sheet DS00002646A](https://ww1.microchip.com/downloads/aemDocuments/documents/UNG/ProductDocuments/DataSheets/USB334x-Data-Sheet-DS00002646A.pdf),
  reset behavior, Table 5-1, synchronous RXCMD and register definitions.
- [Official hardware-version example](https://cynthion.readthedocs.io/en/latest/getting_started.html).
- [Existing protocol and evidence limits](../docs/10-usb-key-dongle.md).

The recovery signal is implemented from the documented protocol and existing
project model; do not copy the unlicensed third-party Pico gist.
