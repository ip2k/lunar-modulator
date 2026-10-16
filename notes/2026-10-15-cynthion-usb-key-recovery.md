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

## Backup admission timing checkpoint

[verified: source review and integration tests] Integration9e85c1da retains
exact gateware/build pins and start/upload/key/status/enumeration ordering,
but applies the120-second freshness checks to the physical key action and ROM
enumeration rather than elapsed FPGA preparation time. A previously loaded
image may precede a fresh owner action; a stale action or enumeration is still
rejected. Cold adapter SHA-256:
`9a6ea5583c985a1c2d0604f0bb5ddc4692ebafcb046d5ba36b61000c1326cc1c`.
Combined focused integration suite:100 passed,43 upstream warnings. Physical
key action, actual ROM enumeration and paired backup remain pending.

## First owner-controlled FM1 attempt

[verified: owner report] USER was pressed once and FM1 switched on as requested;
no precise physical action timestamp was supplied. [verified: coordinator JTAG
at Unix1792106565.965976] Registers1..11 hex:
`4c554e52,3,47d8,0,0,0,01010101,c6,f,c6,ff0d7a`.
The four-state self-test passed while connected, PHYready1/noPHYfault,
terminalFAULT8 and liveGPIO0 with both output enables released. No self-test
failure was latched. The current layout does not identify which later protocol
phase faulted; do not infer ACK/SOF completion or ROM entry. Literal result:
`scratch/cynthion-usb-key-20261015/control-power-operation/owner-attempt-1-status.json`.

Owner was asked to leave FM1 powered and connect TARGET-C to bench01 only after
this terminal/high-Z result, for fresh USB enumeration. Response/enumeration
pending. No RAM loader, flash read or repair write has been issued. Worker is
adding read-only protocol-failure/progress telemetry without changing waveform.

[verified: subsequent owner report] TARGET-C connected to bench01 with FM1
left powered. Passive `lsusb` still shows only KA6 and root hubs, no FM1 ROM,
loader or app. First attempt therefore has no established recovery entry.
Owner was asked to empty both TARGET ports again before any diagnostic image
configuration. Until confirmed empty, do not configure the FPGA. No FM1 flash
operation has occurred in this recovery-key work.

[verified: owner report / follow-up passive check] Owner subsequently moved the
FM1 slide switch to the right position; it had been in the left position.
Absolute ON direction remains unverified. No FM1 USB device appeared on bench01;
JTAG at Unix1792106780.605315 remained0x47d8/GPIO0. This was an observation,
not a second key attempt: terminal operation gateware cannot rearm without
reconfiguration. Evidence: local `switch-right-status.json`. Need a fresh armed
attempt with confirmed switch sequence; do not infer that the prior attempt
actually coincided with SoC power-up.

[verified: owner] Both TARGET ports are now empty again; CONTROL remains on Mac.
Diagnostic-only telemetry source a61af54e is backed up but initial new tests
failed on fractional-ms fixtures (100passed/2failed); fixture repair and fresh
build verification are pending. Existing operation image remains unchanged.
Independent read-only protocol review is saved locally in
`scratch/cynthion-recovery-independent-review-20261015/HANDOFF.md`, SHA-256
`d19f2227dbe55e90b533118079d50913518a3c654a4594b0ee77a1ea5c5133bf`.
It confirms current evidence does not identify the failure phase; released-gap
levels, driven ACK feasibility and GPIO SOF levels remain separate uncertainties.

## Diagnostic-only retry readiness

[verified: integrated source/tests]069c2b00 integrates6279d6a7 telemetry and
9c6a99e7 fixture repair. Combined suite102passed/45upstreamwarnings. No key,
ACK, SOF or arming transitions changed. Layout4 appends terminal reason/origin,
packetcount, receiver/ACKprogress, WAIT_DP/SOF/low counters and keyphase.

[verified: coordinator build review and volatile upload] Exact bitstreamSHA256
`de036dfc80e2e0f2b0c0e4801e3f09ba8e7c100c9a8f630c5fb564d6867587d7`
from source9c6a99e7. Final routed166.25/219.20MHz pass60/120MHz. CompiledJSON
controls independently checked: CONTROL1/TARGETC0/AUX0/discharge0. With both
TARGET ports confirmed empty, upload completed. At Unix1792106989.899127,
JTAGmagicLUNR/layout4/status0x4410/GPIO0; registers12..18 all0. Image is currently
loaded and disarmed; source tests do not establish FM1 acceptance. Local upload,
status and build artifacts are in
`scratch/cynthion-usb-key-20261015/fault-telemetry-operation/`.

[owner action pending] Explicit LEFT→RIGHT switch experiment requested:
CONTROL remains Mac, TARGETC empty, FM1 switchLEFT then connectTARGETA; wait5s,
USERpress/release once then slideRIGHT within10s, leave and report. The switch
ON direction is still unverified; no new key attempt is claimed before report.

## Attempt2 and immediate disconnected recheck

[verified: owner] Explicit LEFT→RIGHT attempt reported done. Precise physical
action time unknown. [verified: JTAG at Unix1792119288.19189] Layout4/status4418,
GPIO0/failure21/failureGPIO3a/stepcounts0/observed0/validmask0/terminal801,
packets0/ACK0/WAIT0/SOF0. PHYready/noPHYfault, cached linevalid1/SE0. First
expectedK step had no RXCMDupdate; no key packet was sent. GPIO snapshot saw
inputK/outputK/bothOEs1 at failure; terminal releases outputs. Actual cause
unproven, possibly target-side clamp/physical powerstate or transient receiver
state. No fresh recovery/USB acceptance exists.

Owner confirmed TARGETs empty. Root volatily reloaded the known disconnected
f5b95... image; at Unix1792119327.303909 it passed27d7/maskF/observedC6, one
event perstate, GPIO0. That bounds the failure to the connected/idle context,
not a persistent receiver failure. Root reloaded unchanged operationde036...;
at the timestamp in the savedJSON SAFE0/PHYready,
noPHYfault/GPIOOEs0/terminalregs0. Exact evidence local in
`fault-telemetry-operation/owner-attempt-2-status.json`,
`phy-swap-v1/recheck-after-attempt-2-status.json`, and
`fault-telemetry-operation/attempt-3-disarmed-status.json`.

Owner requested RIGHT→LEFT fresh experiment, TARGETCempty. No claim that RIGHT
is OFF or LEFT is ON. Pending ownerreport/status; no deviceflashoperation.

## Attempt3: candidate ACK then WAIT_DP timeout

[verified: owner] USER pressed and FM1 switch movedRIGHT→LEFT. Owner subsequently
connectedTARGETC tobench01 without changingLEFT. Actual ONdirection unverified.
[verified: coordinator JTAG at Unix1792119615.494011] Layout4/status47d8,
selftestmaskF/observedC6/validF/oneeventeach, terminal855(reason2,originWAIT_DP5),
packets4222, ACKprogress18d(receiver_live1,ack_ticks99), WAIT500000us,
SOF0/SOFlow0, keyprogressc, GPIO0/OEsreleased. CandidateACK was detected;
no qualifying J/D+pullup followed within500ms, so no calibration pulses were sent.
Literal local `fault-telemetry-operation/owner-attempt-3-status.json`.
[acceptance limit] This is not proof of ROMack/keyrecognition: a power transition
or other clamp could also produceSE0. ONswitch direction is stillunknown.

[verified: passive USB after ownerTARGETCreconnect] bench01.local `lsusb` still
contains onlyKA6/root hubs, noFM1. No loader, flashread/write or boot/reset
command was sent. Current operation image remains terminalFAULT/highZ. Owner
asked to keepstate; no further powercycle requested while offline review
examines ACKrelease/pullup assumptions and possiblefalseACK duringpowertransition.

## Independent TARGET-C cable test preparation

[verified: owner] FM1 detached from TARGET A; only CONTROL→Mac and
TARGET C→bench01 are connected. Pre-test bench inventory has root hubs and
KA6 only; recovery status remains layout4/47d8, terminal855, GPIO0. Raw
evidence is under `scratch/cynthion-usb-key-20261015/target-c-cable-test/`.

[verified: installed source] Stock analyzer uses CONTROL PHY on r1.4; its
built-in test device uses AUX PHY. Neither establishes TARGET-C cable data
continuity. A bounded temporary adapter uses maintained LUNA USBDevice and
its standard control endpoint on target_phy, inherited 0x39=0x06 wiring fix,
no direct data GPIOs, and all four VBUS/discharge controls zero. It will be
loaded only with FM1 detached; cable acceptance requires actual enumeration
and descriptor retrieval from bench01. No verdict yet.

### Cable test result — physical PASS

[verified: bench01 USB, 2026-10-16 03:10:25 UTC] Root loaded the frozen first
probe artifact (119,595 bytes), SHA-256
`c72a4e4e201809c0680948c43f88c9572e31cb0da037bf7031ee16f1346aecfe`.
Source is worker commit `7a1529f34440dab6366d29df68e2862f5a7042a1`.
Synthesized netlist independently confirms four switch/discharge outputs driven
zero and no direct target GPIO ports. Routed clocks pass: USB 103.28 MHz
against 60 MHz; fabric 209.86 MHz against 120 MHz.

Bench01 enumerated `1209:cc01` at bus003/device043, product
“Cynthion TARGET-C descriptor probe”, negotiated full speed (12 Mbps). Two
`lsusb -v` reads retrieved device/configuration/string descriptors and device
status. This establishes bidirectional USB data over the connected TARGET-C
cable at the speed used by FM1; it does not establish FM1 ROM recovery.
FM1 remained detached, with no device commands or flash access.

[verified: upload and subsequent inventory, 03:11:01 UTC] Restored pinned
official analyzer SHA-256
`5afd1741247da483876bbc7b0d87606ef34503558f31f638162409cb2f0ea5da`
volatily. The probe disappeared from bench01 as expected. CURRENT: official
analyzer, CONTROL→Mac, TARGET C→bench01, TARGET A empty. Raw evidence is in
`target-c-cable-test/{bench-before,bench-after,bench-repeat,bench-after-restore}.txt`,
`upload.log`, `restore-analyzer.log`, and `root-netlist-review.json` below
`scratch/cynthion-usb-key-20261015/`.

## ACK gap-reset operation image loaded, 2026-10-16

[verified: owner] Both TARGET ports empty before programming. Root independently
checked hashes/netlist for exact source4ee635ee and loaded volatile bit
`42e805e0cc91becab26c72b9cc2dd3f34c3772d00f3f0b2b224152e6b3662767`.
Routed clocks PASS164.26/205.13MHz vs60/120MHz. CONTROL1,C0,AUX0,discharge0.
Layout4 status4010/GPIO0/terminal0 confirms SAFE, PHYready, noPHYfault, OEs0.
Saved receipt/upload/disarmed snapshot under scratch ack-gap-reset-operation.
Owner physical instructions repeat RIGHT→LEFT after USER with TARGETC empty;
reply pending. No recovery acceptance or FM1 command claimed.
