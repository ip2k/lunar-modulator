# Cynthion r1.4 TARGET-A power monitor prototype

Status: source and simulation are ready for review; routed build is pending Hera network access. This is an offline diagnostic prototype. No bitstream was built or loaded and no hardware was accessed by this worker.

## Scope and interface

The new `tools/cynthion_usb_key/power_monitor.py` top uses the maintained Cynthion r1.4 `power_monitor` resource and LUNA `I2CRegisterInterface` to read PAC1954 channel 1. It authenticates manufacturer ID `0x54`, requires active range register `0x22` to equal `0x0000`, issues `REFRESH_V` (`0x1f`) as a zero-length Send Byte, waits for conversion, then reads VBUS1 (`0x07`) and VSENSE1 (`0x0b`). Transactions are bounded and NACK/timeout/range/identity failures latch a fault. The SLOW input selects 8 SPS; the sample interval is 125 ms.

JTAG exposes raw measurement words only. Host-side conversion helpers use the PAC195x unipolar defaults: `VBUS_uV = raw * 32,000,000 / 65,536`, `VSENSE_uV = raw * 100,000 / 65,536`, and with the r1.4 R2 20 mOhm shunt `current_uA = raw * 5,000,000 / 65,536`. The code does not claim that this reports the FM-1 CPU rail; it measures the channel-1 VBUS/VSENSE path.

The top uses LUNA's `period_cyc=600`, a 100 kHz I2C bus on the 60 MHz USB domain (the driver divides the full period into four phases). It explicitly enables CONTROL-to-TARGET-A VBUS and disables TARGET-C, AUX, and TARGET-A discharge. It requests no target D+/D- GPIOs, USER button, or USB_KEY core. The target ULPI PHY is initialized using the existing fail-closed, non-driving USB3343 profile and r1.4 DP/DM swap readback. The measurements and power control pins are JTAG read-only. There is no hardware load or physical result.

The new CI gateware step includes `tests/test_cynthion_power_monitor.py`. It covers conversion scaling, identity/range rejection, transaction timeout, sample sequence and age behavior after subsequent success/failure, real LUNA size-zero Send Byte wire behavior, a two-byte MSB-first LUNA initiator read, wrapper big-endian aggregation source, and top power/pad resource constraints. The two-byte bus exercise is against `I2CInitiator`; it is not an end-to-end PAC register-wrapper read simulation.

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

The requested Hera routed build is blocked by current network reachability: root independently saw Hera SSH timeout and a bounded ping from bench01 also fail. Do not build on the Mac, use another host, or load hardware as a substitute. Once Hera is reachable, acquire the assigned unique coordination claim, build with the documented OSS CAD toolchain in the bounded `docker-batch.slice` container, inspect routed timing and netlist proving target GPIO OEs absent and VBUS controls CONTROL=1/TARGET-C=0/AUX=0/discharge=0, then save the bitstream hash/receipt and release the claim. Root owns all hardware operations and must review the artifact before any load.
