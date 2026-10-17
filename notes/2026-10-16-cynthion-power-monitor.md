# Cynthion r1.4 TARGET-A power monitor prototype

Status: source, simulation, and Aeon routing are complete pending coordinator artifact review. The full register-wrapper discrepancy was resolved as a responder fixture error, as recorded below. No bitstream has been accepted or loaded for a physical measurement.

## Scope and interface

The new `tools/cynthion_usb_key/power_monitor.py` top uses the maintained Cynthion r1.4 `power_monitor` resource and LUNA `I2CRegisterInterface` to read PAC1954 channel 1. It authenticates manufacturer ID `0x54`, requires active range register `0x22` to equal `0x0000`, issues `REFRESH_V` (`0x1f`) as a zero-length Send Byte, waits for conversion, then reads VBUS1 (`0x07`) and VSENSE1 (`0x0b`). Transactions are bounded and NACK/timeout/range/identity failures latch a fault. The SLOW input selects 8 SPS; the sample interval is 125 ms.

JTAG exposes raw measurement words only. Host-side conversion helpers use the PAC195x unipolar defaults: `VBUS_uV = raw * 32,000,000 / 65,536`, `VSENSE_uV = raw * 100,000 / 65,536`, and with the r1.4 R2 20 mOhm shunt `current_uA = raw * 5,000,000 / 65,536`. The code does not claim that this reports the FM-1 CPU rail; it measures the channel-1 VBUS/VSENSE path.

The top uses LUNA's `period_cyc=600`, a 100 kHz I2C bus on the 60 MHz USB domain (the driver divides the full period into four phases). It explicitly enables CONTROL-to-TARGET-A VBUS and disables TARGET-C, AUX, and TARGET-A discharge. It requests no target D+/D- GPIOs, USER button, or USB_KEY core. The target ULPI PHY is initialized using the existing fail-closed, non-driving USB3343 profile and r1.4 DP/DM swap readback. The measurements and power control pins are JTAG read-only. There is no hardware load or physical result.

The new CI gateware step includes `tests/test_cynthion_power_monitor.py`. It covers conversion scaling, identity/range rejection, transaction timeout, sample sequence and age behavior after subsequent success/failure, real LUNA size-zero Send Byte wire behavior, a two-byte MSB-first LUNA initiator read, wrapper big-endian aggregation source, and top power/pad resource constraints. The two-byte bus exercise is against `I2CInitiator`; it is not an end-to-end PAC register-wrapper read simulation.

## Follow-up: full register-wrapper read simulation attempt

Root requested a complete `I2CRegisterInterface` read simulation with a two-byte responder. A temporary line-level responder acknowledged device/register/read-address bytes, issued a repeated START, emitted `0x12` then `0x34` MSB-first, ACKed the first data byte, NACKed the second, and observed STOP. The responder's own sampled data stream was `0x1234`, but the wrapper's `read_data` was `0x2569` at completion. Raising the I2C period from 16 to 64 system cycles did not change the result. This temporary experiment was not retained as a passing test because it does not yet distinguish a responder/synchronizer modeling error from an actual driver read-path issue; expecting either value would encode an unverified conclusion.

The existing 42-test gateware suite still passes. The full wrapper gap remains open. Next diagnostic should instrument the actual nested `I2CInitiator.bus.sda_i` (post-synchronizer) and `data_o` at each completed read, while checking the responder's transmitted 0x20/0x07/0x21 bytes and ACK timing. No RTL was changed, no hardware was accessed, and no Hera job was launched for this follow-up.

## Evidence and sources

- Cynthion r1.4 platform source: installed `cynthion/gateware/platform/cynthion_r1_4.py`; its `power_monitor` resource maps SCL D7, SDA C7, PWRDND D5 (`PinsN`), SLOW C6, and GPIO D6.
- Maintained factory self-test: [greatscottgadgets/cynthion-test `selftest.py`](https://github.com/greatscottgadgets/cynthion-test/blob/main/selftest.py), which uses LUNA `I2CRegisterInterface`, PAC address `0x10`, `pwrdn.o=0`, `slow.o=1`, and manufacturer ID `0x54`.
- PAC195x register definitions and conversion ranges: [Microchip PAC195x family datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/PAC195X-Family-Data-Sheet-20006539B.pdf), registers `0x07`, `0x0b`, `0x1f`, `0x22`, `0xfe`; VBUS 32 V and VSENSE 100 mV unipolar ranges; 50 ms startup and 1 ms `REFRESH_V` conversion settling.
- Cynthion r1.4 R2 component marking/source: schematic/PCB commit `13aa71c2fb0be3837cd2ec580ee5d2c25fc1c678`, resistor `ERJ-3BWFR020V` (20 mOhm nominal, 1%).
- USB3343 non-driving/readback sequence is the existing `gateware/ulpi_safe_phy.py`; r1.4 platform source declares ULPI extra register `{0x39: 0x06}` for the board DP/DM swap.

## Checks and limits

Run from this worktree with the local test environment:

```sh
PYTHONPATH=/Users/likwid/.local/share/uv/tools/cynthion/lib/python3.12/site-packages \
  /tmp/lunar-installer-service-test-venv/bin/python -B -m pytest -q -p no:cacheprovider -o addopts='' \
  tests/test_ulpi_safe_phy.py tests/test_cynthion_usb_key*.py \
  tests/test_cynthion_power_monitor.py
```

Result on assigned base `86154bc7843d7b1965d346af78620917fd2836f1`: the exact command above passed 42 tests with 69 warnings (Amaranth/LUNA deprecation and existing unused elaboratable warnings). `Fragment.get(CynthionPowerMonitorTop(), CynthionPlatformRev1D4())` elaborated successfully and reported ULPI extras `{0x39: 0x06}`. `git diff --check` passed and Ruby Psych parsed `.github/workflows/ci.yml` successfully. These are source/simulation/elaboration checks only; they do not prove routed pin OEs, timing, current sense calibration, or physical measurement.

The owner redirected builds to Aeon during Hera RAID/NIC maintenance. The routed build has completed there; exact artifact review remains a prerequisite to any volatile load. Root owns all hardware operations. The register-wrapper discrepancy is resolved by the simulation follow-up below; routing alone does not establish physical measurement correctness.

### Nested LUNA I2C read-path simulation follow-up

The ignored, self-contained reproducer is preserved at
`scratch/cynthion-i2c-wrapper-diagnostic/repro.py` with its latest output in
`run.log`. The initial fixture returned `0x2569` because the responder retained
its `saw_rise` flag across the repeated START. That allowed the START setup
edge to advance its bit counter before the first read-address bit. Clearing
that pending edge on START fixed the fixture without changing LUNA or project
RTL.

The corrected simulation is now tracked in
`tests/test_cynthion_power_monitor.py` as a public-API
`I2CRegisterInterface` integration test. It verifies the transmitted bytes
`0x20` (address write), `0x07` (register), and `0x21` (address read), all three
address ACKs, the master's ACK after byte one, final master NACK, STOP, and
returned two-byte value `0x1234`. It checks
that its open-drain responder presents 16 MSB-first data bits, `0x12` then
`0x34`, and that the wrapper combines them as `0x1234`. A separate ignored
scratch trace captures LUNA's internal read-state sample edges and shift
register, confirming the wrapper result and synchronized SDA match for this
fixture. This resolves the earlier `0x2569` discrepancy as a testbench phase
error, not evidence of a LUNA RTL defect. This is a complete simulated
register-wrapper transaction, but the responder is an offline deterministic
model, not a PAC1954 electrical/bus measurement or FPGA-top integration test.

Validation command:

```sh
PYTHONPATH=/Users/likwid/.local/share/uv/tools/cynthion/lib/python3.12/site-packages \
  python3 scratch/cynthion-i2c-wrapper-diagnostic/repro.py
```

It exits zero with the assertions described above. No hardware, Hera, Aeon,
synthesis, or project RTL was touched. Serena was ready but selected a sibling
worktree; Rarefaction was ready on the primary checkout. Neither index was
retargeted during this task to avoid disturbing another active session.

