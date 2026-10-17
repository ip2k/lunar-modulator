# Cynthion PAC1954 bipolar current diagnostic

This branch corrects the Cynthion r1.4 TARGET-A monitor's current polarity.
The board sense resistor is between CONTROL's supply path and TARGET-A. With
PAC1954 `VSENSE1 = SENSE+ - SENSE-`, CONTROL-to-TARGET-A current is negative.
The previous unipolar profile clamped negative readings and could not diagnose
the observed path.

The monitor now writes `NEG_PWR_FSR` register `0x1d` with the PAC word
`0x4000`, sends the `REFRESH_V` command (`0x1f`), waits 1 ms, and reads back
`NEG_PWR_FSR_ACT` (`0x22`) before accepting each sample. Any transfer error,
timeout, or non-`0x4000` active word faults the monitor. The range selection is
channel-1 VSENSE ±100 mV; the other configuration fields retain reset defaults.
The current decoder interprets VSENSE as signed 16-bit two's complement and
uses 32768 counts per polarity. A new PAC2 magic/layout prevents the old
unsigned PAC1 reader from accepting the changed register meaning.

The PAC195x data sheet documents `NEG_PWR_FSR` channel-1 VSENSE bits 15:14
(`00` = +100 mV/0, `01` = ±100 mV), the `REFRESH_V` send-byte command, the
active `NEG_PWR_FSR_ACT` register, and the bipolar two's-complement scale:
[PAC195X Family Data Sheet DS20006539B](https://ww1.microchip.com/downloads/en/DeviceDoc/PAC195X-Family-Data-Sheet-20006539B.pdf),
§5.4 and register tables. The existing LUNA `I2CRegisterInterface` is used;
wire-level simulation confirms that a 16-bit `write_data=0x4000` sends bytes
`0x40, 0x00` and reads the active-range bytes back as `0x40, 0x00`.

The status is a diagnostic of the Cynthion TARGET-A USB supply path only. It is
not an FM-1 CPU-rail measurement, boot/recovery evidence, flash authorization,
or physical acceptance. This branch has not been synthesized or loaded onto
gateware; no hardware command was run. Both TARGET ports were reported empty
while this source and simulation work proceeded. The monitor still drives only
the existing CONTROL-to-TARGET-A supply setting; USB data GPIOs remain absent,
TARGET-C/AUX/discharge controls remain off, and JTAG telemetry registers remain
read-only.

## Verification

Base: `a070dd93b70f5fb20708569a1352d118aa3de019`.

- `tests/test_cynthion_power_readout.py`: 27 passed.
- `tests/test_cynthion_power_monitor.py`: 16 passed with the installed Cynthion
  Python 3.12 Amaranth/LUNA environment and the repository's existing pytest
  package path. Coverage includes signed endpoints, configuration ACK/NACK and
  timeout, active-range mismatch, refresh/readback/sample ordering, and actual
  LUNA wire ordering for the configuration word, send-byte refresh, and
  big-endian active-range read.
- `git diff --check`: passed.

The local test run establishes simulation/source behavior only. FPGA synthesis,
timing closure, volatile load, unloaded physical readback, and any connected
load measurement remain separate gates owned by the coordinator.
