# Cynthion USB_KEY recovery preparation

Status: source review and offline gateware development; **not ready for an FM1
connection or power cycle**. No custom bitstream has been uploaded, no key has
been driven, and no FM1 recovery acceptance exists.

## Current physical state

[verified: owner] Both Cynthion TARGET ports are empty; CONTROL remains on the
Mac. Preserve this state until disconnected checks pass. The FM1 lost power
after the interrupted stage7 installation. Its current flash contents are
unknown and retained-RAM-loader admission is invalid. The original backups and
interrupted journal remain recovery anchors, not current readback evidence.

[verified: read-only host inspection] Installed Cynthion software is 0.2.5,
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
the FPGA's own output. It has not been demonstrated on this board.

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
unchanged fixed-loader adapter pass 72 offline tests. The cold path preserves
the exact reviewed RAM-loader/read inventory and labels acquired flash
unclassified. Its observation schema still needs alignment with the final
gateware status interface before a physical campaign is prepared.

[verified: Hera preparation] The task-local FPGA toolchain is ready in
`/home/claude/lunar-cynthion-toolchain-20261015`, mounted as `/work` in bounded
containers. OSS CAD Suite linux-x64 2026-10-14 archive SHA-256 is
`a6ccc6b96b2d985336a1061c78b2fd2bdd73e0f68690da17db88e00457881a11`,
verified against the official release asset digest before extraction.
Versions: Yosys 0.70+16 (`3bb533450`), nextpnr-ecp5
0.11.1-63 (`44a6c739`), ecppack 1.4-86 (`a31ff70`), Python 3.12,
Cynthion 0.2.5, Amaranth 0.5.10, LUNA USB 0.2.3, Apollo 1.1.1.
Installed r1.4 platform import succeeds. No synthesis/timing result is yet
accepted at this checkpoint. Toolchain and build products remain outside Git.

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
