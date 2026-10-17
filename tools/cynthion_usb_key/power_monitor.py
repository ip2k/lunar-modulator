"""Read-only Cynthion r1.4 TARGET-A VBUS/current monitor image.

This is a diagnostic-only top. It never requests the target USB D+/D- GPIOs,
never instantiates the USB_KEY core, and exposes only read-only JTAG registers.
"""

from types import SimpleNamespace

from amaranth import (
    Cat,
    ClockSignal,
    DomainRenamer,
    Elaboratable,
    Module,
    ResetSignal,
    Signal,
)
from cynthion.gateware.platform.cynthion_r1_4 import CynthionPlatformRev1D4
from luna.gateware.interface.i2c import I2CRegisterInterface
from luna.gateware.interface.jtag import JTAGRegisterInterface

from gateware.ulpi_safe_phy import ULPISafePHY


def vbus_uv_from_raw(raw):
    """PAC195x unipolar 32 V VBUS reading to rounded microvolts."""
    return (raw * 32_000_000 + 32_768) // 65_536


def current_ua_from_raw(raw, shunt_uohm=20_000):
    """PAC195x unipolar 100 mV VSENSE reading to rounded microamps."""
    if shunt_uohm <= 0:
        raise ValueError("shunt resistance must be positive")
    # 100 mV is 100,000 uV; uV/uOhm is amperes. Convert A to uA.
    return (raw * 100_000 * 1_000_000 + (shunt_uohm * 65_536) // 2) // (shunt_uohm * 65_536)


class PAC1954Channel1(Elaboratable):
    """Bounded PAC1954 identity/range/refresh/read state machine.

    I2CRegisterInterface is LUNA's maintained device driver. The controller
    treats a transaction that returns idle without `done` as an error (NACK),
    and times out any transaction that never completes.
    """

    I2C_ADDRESS = 0x10
    REG_VBUS1 = 0x07
    REG_VSENSE1 = 0x0B
    REG_NEG_PWR_FSR_ACT = 0x22
    REG_REFRESH_V = 0x1F
    REG_MANUFACTURER_ID = 0xFE
    EXPECTED_MANUFACTURER_ID = 0x54
    EXPECTED_ACTIVE_RANGE = 0x0000

    # r1.4 schematic R2, Panasonic ERJ-3BWFR020V: 20 mOhm nominal.
    SHUNT_UOHM = 20_000
    READ_TIMEOUT_CYCLES = 120_000  # 2 ms at 60 MHz, > one 100 kHz I2C transfer.
    POWERUP_SETTLE_CYCLES = 7_800_000  # 130 ms: 50 ms power-up + one 8 SPS cycle.
    REFRESH_SETTLE_CYCLES = 60_000  # PAC195x requires 1 ms after REFRESH_V.
    SAMPLE_INTERVAL_CYCLES = 7_500_000  # 125 ms, matching SLOW=8 SPS.

    def __init__(self, i2c, *, read_timeout_cycles=READ_TIMEOUT_CYCLES,
                 powerup_settle_cycles=POWERUP_SETTLE_CYCLES,
                 refresh_settle_cycles=REFRESH_SETTLE_CYCLES,
                 sample_interval_cycles=SAMPLE_INTERVAL_CYCLES):
        if min(read_timeout_cycles, powerup_settle_cycles,
               refresh_settle_cycles, sample_interval_cycles) < 1:
            raise ValueError("all PAC timing bounds must be positive")
        self.i2c = i2c
        self.read_timeout_cycles = read_timeout_cycles
        self.powerup_settle_cycles = powerup_settle_cycles
        self.refresh_settle_cycles = refresh_settle_cycles
        self.sample_interval_cycles = sample_interval_cycles
        self.ready = Signal()
        self.fault = Signal()
        self.error_code = Signal(4)
        self.manufacturer_id = Signal(8)
        self.active_range = Signal(16)
        self.vbus_raw = Signal(16)
        self.vsense_raw = Signal(16)
        self.sample_sequence = Signal(32)
        self.sample_age_cycles = Signal(32)
        self.refresh_count = Signal(32)

    def elaborate(self, platform):
        m = Module()
        i2c = self.i2c
        i2c_timeout = Signal(range(self.read_timeout_cycles + 1))
        wait_busy_seen = Signal()
        transfer_done = Signal()
        transfer_failed = Signal()
        settle_count = Signal(range(max(self.powerup_settle_cycles,
                                        self.refresh_settle_cycles) + 1))
        interval_count = Signal(range(self.sample_interval_cycles + 1))
        register_value = Signal(16)

        # Transaction requests are one-cycle strobes. Size zero is the
        # datasheet's Send Byte form used by REFRESH_V (no register payload).
        m.d.sync += [i2c.read_request.eq(0), i2c.write_request.eq(0)]
        m.d.comb += [
            transfer_done.eq(i2c.done),
            transfer_failed.eq(wait_busy_seen & ~i2c.busy & ~i2c.done),
        ]
        with m.If(self.sample_sequence != 0):
            with m.If(self.sample_age_cycles != 0xFFFFFFFF):
                m.d.sync += self.sample_age_cycles.eq(self.sample_age_cycles + 1)

        with m.FSM() as fsm:
            with m.State("POWERUP"):
                # Cynthion's monitor PWRDND is released at FPGA startup. Wait
                # 130 ms before reading: PAC195x specifies 50 ms after PWRDN
                # release and SLOW=high selects 8 samples/second.
                with m.If(settle_count == self.powerup_settle_cycles - 1):
                    m.d.sync += [
                        settle_count.eq(0),
                        i2c.address.eq(self.REG_MANUFACTURER_ID),
                        i2c.size.eq(1),
                        i2c_timeout.eq(0),
                        wait_busy_seen.eq(0),
                    ]
                    m.next = "ISSUE_ID"
                with m.Else():
                    m.d.sync += settle_count.eq(settle_count + 1)

            with m.State("ISSUE_ID"):
                m.d.sync += i2c.read_request.eq(1)
                m.next = "WAIT_ID"
            with m.State("WAIT_ID"):
                with m.If(transfer_done):
                    m.d.sync += self.manufacturer_id.eq(i2c.read_data[:8])
                    with m.If(i2c.read_data[:8] == self.EXPECTED_MANUFACTURER_ID):
                        m.d.sync += [i2c.address.eq(self.REG_NEG_PWR_FSR_ACT), i2c.size.eq(2), i2c_timeout.eq(0), wait_busy_seen.eq(0)]
                        m.next = "ISSUE_RANGE"
                    with m.Else():
                        m.d.sync += [self.fault.eq(1), self.error_code.eq(1)]
                        m.next = "FAILED"
                with m.Elif(transfer_failed):
                    m.d.sync += [self.fault.eq(1), self.error_code.eq(2)]
                    m.next = "FAILED"
                with m.Elif(i2c.busy):
                    m.d.sync += wait_busy_seen.eq(1)
                    with m.If(i2c_timeout == self.read_timeout_cycles - 1):
                        m.d.sync += [self.fault.eq(1), self.error_code.eq(3)]
                        m.next = "FAILED"
                    with m.Else():
                        m.d.sync += i2c_timeout.eq(i2c_timeout + 1)
                with m.Elif(i2c_timeout == self.read_timeout_cycles - 1):
                    m.d.sync += [self.fault.eq(1), self.error_code.eq(3)]
                    m.next = "FAILED"
                with m.Else():
                    m.d.sync += i2c_timeout.eq(i2c_timeout + 1)

            with m.State("ISSUE_RANGE"):
                m.d.sync += i2c.read_request.eq(1)
                m.next = "WAIT_RANGE"
            with m.State("WAIT_RANGE"):
                with m.If(transfer_done):
                    m.d.sync += self.active_range.eq(i2c.read_data[:16])
                    with m.If(i2c.read_data[:16] == self.EXPECTED_ACTIVE_RANGE):
                        m.d.sync += [i2c.address.eq(self.REG_REFRESH_V), i2c.size.eq(0), i2c_timeout.eq(0), wait_busy_seen.eq(0)]
                        m.next = "ISSUE_REFRESH"
                    with m.Else():
                        m.d.sync += [self.fault.eq(1), self.error_code.eq(4)]
                        m.next = "FAILED"
                with m.Elif(transfer_failed):
                    m.d.sync += [self.fault.eq(1), self.error_code.eq(5)]
                    m.next = "FAILED"
                with m.Elif(i2c.busy):
                    m.d.sync += wait_busy_seen.eq(1)
                    with m.If(i2c_timeout == self.read_timeout_cycles - 1):
                        m.d.sync += [self.fault.eq(1), self.error_code.eq(6)]
                        m.next = "FAILED"
                    with m.Else():
                        m.d.sync += i2c_timeout.eq(i2c_timeout + 1)
                with m.Elif(i2c_timeout == self.read_timeout_cycles - 1):
                    m.d.sync += [self.fault.eq(1), self.error_code.eq(6)]
                    m.next = "FAILED"
                with m.Else():
                    m.d.sync += i2c_timeout.eq(i2c_timeout + 1)

            with m.State("ISSUE_REFRESH"):
                m.d.sync += i2c.write_request.eq(1)
                m.next = "WAIT_REFRESH"
            with m.State("WAIT_REFRESH"):
                with m.If(transfer_done):
                    m.d.sync += [settle_count.eq(0), self.refresh_count.eq(self.refresh_count + 1)]
                    m.next = "REFRESH_SETTLE"
                with m.Elif(transfer_failed):
                    m.d.sync += [self.fault.eq(1), self.error_code.eq(7)]
                    m.next = "FAILED"
                with m.Elif(i2c.busy):
                    m.d.sync += wait_busy_seen.eq(1)
                    with m.If(i2c_timeout == self.read_timeout_cycles - 1):
                        m.d.sync += [self.fault.eq(1), self.error_code.eq(8)]
                        m.next = "FAILED"
                    with m.Else():
                        m.d.sync += i2c_timeout.eq(i2c_timeout + 1)
                with m.Elif(i2c_timeout == self.read_timeout_cycles - 1):
                    m.d.sync += [self.fault.eq(1), self.error_code.eq(8)]
                    m.next = "FAILED"
                with m.Else():
                    m.d.sync += i2c_timeout.eq(i2c_timeout + 1)

            with m.State("REFRESH_SETTLE"):
                with m.If(settle_count == self.refresh_settle_cycles - 1):
                    m.d.sync += [i2c.address.eq(self.REG_VBUS1), i2c.size.eq(2), i2c_timeout.eq(0), wait_busy_seen.eq(0)]
                    m.next = "ISSUE_VBUS"
                with m.Else():
                    m.d.sync += settle_count.eq(settle_count + 1)

            with m.State("ISSUE_VBUS"):
                m.d.sync += i2c.read_request.eq(1)
                m.next = "WAIT_VBUS"
            with m.State("WAIT_VBUS"):
                with m.If(transfer_done):
                    m.d.sync += [register_value.eq(i2c.read_data[:16]), i2c.address.eq(self.REG_VSENSE1), i2c.size.eq(2), i2c_timeout.eq(0), wait_busy_seen.eq(0)]
                    m.next = "ISSUE_VSENSE"
                with m.Elif(transfer_failed):
                    m.d.sync += [self.fault.eq(1), self.error_code.eq(9)]
                    m.next = "FAILED"
                with m.Elif(i2c.busy):
                    m.d.sync += wait_busy_seen.eq(1)
                    with m.If(i2c_timeout == self.read_timeout_cycles - 1):
                        m.d.sync += [self.fault.eq(1), self.error_code.eq(10)]
                        m.next = "FAILED"
                    with m.Else():
                        m.d.sync += i2c_timeout.eq(i2c_timeout + 1)
                with m.Elif(i2c_timeout == self.read_timeout_cycles - 1):
                    m.d.sync += [self.fault.eq(1), self.error_code.eq(10)]
                    m.next = "FAILED"
                with m.Else():
                    m.d.sync += i2c_timeout.eq(i2c_timeout + 1)

            with m.State("ISSUE_VSENSE"):
                m.d.sync += i2c.read_request.eq(1)
                m.next = "WAIT_VSENSE"
            with m.State("WAIT_VSENSE"):
                with m.If(transfer_done):
                    m.d.sync += [
                        self.vbus_raw.eq(register_value),
                        self.vsense_raw.eq(i2c.read_data[:16]),
                        self.sample_sequence.eq(self.sample_sequence + 1),
                        self.sample_age_cycles.eq(0),
                        interval_count.eq(0),
                    ]
                    m.d.sync += self.ready.eq(1)
                    m.next = "SAMPLE_INTERVAL"
                with m.Elif(transfer_failed):
                    m.d.sync += [self.fault.eq(1), self.error_code.eq(11)]
                    m.next = "FAILED"
                with m.Elif(i2c.busy):
                    m.d.sync += wait_busy_seen.eq(1)
                    with m.If(i2c_timeout == self.read_timeout_cycles - 1):
                        m.d.sync += [self.fault.eq(1), self.error_code.eq(12)]
                        m.next = "FAILED"
                    with m.Else():
                        m.d.sync += i2c_timeout.eq(i2c_timeout + 1)
                with m.Elif(i2c_timeout == self.read_timeout_cycles - 1):
                    m.d.sync += [self.fault.eq(1), self.error_code.eq(12)]
                    m.next = "FAILED"
                with m.Else():
                    m.d.sync += i2c_timeout.eq(i2c_timeout + 1)

            with m.State("SAMPLE_INTERVAL"):
                with m.If(interval_count == self.sample_interval_cycles - 1):
                    m.d.sync += [i2c.address.eq(self.REG_REFRESH_V), i2c.size.eq(0), i2c_timeout.eq(0), wait_busy_seen.eq(0)]
                    m.next = "ISSUE_REFRESH"
                with m.Else():
                    m.d.sync += interval_count.eq(interval_count + 1)

            with m.State("FAILED"):
                m.d.sync += self.ready.eq(0)
                m.next = "FAILED"

        return m


class CynthionPowerMonitorTop(Elaboratable):
    """Read-only current/voltage monitor with the reviewed power profile."""

    def elaborate(self, platform):
        m = Module()
        m.submodules.car = platform.clock_domain_generator()

        # Default all pass-through/discharge switches off except CONTROL to
        # TARGET A VBUS. TARGET GPIO resources are intentionally never requested.
        control_vbus = platform.request("control_vbus_en")
        target_c_vbus = platform.request("target_c_vbus_en")
        aux_vbus = platform.request("aux_vbus_en")
        target_discharge = platform.request("target_a_discharge")
        m.d.comb += [
            control_vbus.o.eq(1),
            target_c_vbus.o.eq(0),
            aux_vbus.o.eq(0),
            target_discharge.o.eq(0),
        ]

        # Keep the target USB3343 in its existing fail-closed, non-driving
        # configuration and preserve its board-specific r1.4 DP/DM swap.
        target_phy = platform.request("target_phy")
        m.d.comb += [
            target_phy.clk.o.eq(ClockSignal("usb")),
            target_phy.rst.o.eq(ResetSignal("usb")),
        ]
        ulpi = SimpleNamespace(
            data=SimpleNamespace(i=Signal(8), o=Signal(8), oe=Signal()),
            dir=Signal(), nxt=Signal(), stp=Signal())
        m.d.comb += [
            ulpi.data.i.eq(target_phy.data.i),
            target_phy.data.o.eq(ulpi.data.o),
            target_phy.data.oe.eq(ulpi.data.oe),
            ulpi.dir.eq(target_phy.dir.i),
            ulpi.nxt.eq(target_phy.nxt.i),
            target_phy.stp.o.eq(ulpi.stp),
        ]
        safe_phy = ULPISafePHY(
            ulpi,
            usb_io_power_management=ULPISafePHY.USB_IO_POWER_MANAGEMENT_CYNTHION_R14,
        )
        m.submodules.safe_phy = safe_phy
        phy_start = Signal()
        phy_delay = Signal(range(60_001))
        with m.If(~ResetSignal("usb")):
            with m.If(phy_delay == 60_000):
                m.d.usb += phy_start.eq(1)
            with m.Else():
                m.d.usb += phy_delay.eq(phy_delay + 1)
        m.d.comb += safe_phy.start.eq(phy_start)

        monitor_pads = platform.request("power_monitor")
        i2c = I2CRegisterInterface(
            pads=monitor_pads,
            period_cyc=600,  # 100 kHz at the r1.4 60 MHz USB clock.
            address=PAC1954Channel1.I2C_ADDRESS,
            data_bytes=2,
        )
        m.submodules.i2c = DomainRenamer({"sync": "usb"})(i2c)
        pac = PAC1954Channel1(i2c)
        m.submodules.pac = DomainRenamer({"sync": "usb"})(pac)
        # PAC1954 PWRDND is active low; the platform PinsN inversion means
        # this logical zero is a physical high (monitor enabled). SLOW high
        # selects the datasheet-supported 8 samples/s. Leave GPIO high-Z.
        m.d.comb += [
            monitor_pads.pwrdn.o.eq(0),
            monitor_pads.slow.o.eq(1),
            monitor_pads.slow.oe.eq(1),
            monitor_pads.gpio.oe.eq(0),
        ]

        debug = DomainRenamer({"sync": "usb"})(
            JTAGRegisterInterface(default_read_value=0xBAD0C0DE))
        m.submodules.debug_registers = debug
        debug.add_read_only_register(1, read=0x50414331)  # "PAC1"
        debug.add_read_only_register(2, read=1)  # layout version
        debug.add_read_only_register(3, read=Cat(
            safe_phy.ready, safe_phy.fault, pac.ready, pac.fault,
            pac.error_code, pac.sample_sequence != 0))
        debug.add_read_only_register(4, read=Cat(pac.manufacturer_id, pac.active_range))
        debug.add_read_only_register(5, read=pac.vbus_raw)
        debug.add_read_only_register(6, read=pac.vsense_raw)
        debug.add_read_only_register(7, read=pac.sample_sequence)
        debug.add_read_only_register(8, read=pac.sample_age_cycles)
        debug.add_read_only_register(9, read=pac.refresh_count)
        debug.add_read_only_register(10, read=Cat(
            control_vbus.o, target_c_vbus.o, aux_vbus.o, target_discharge.o))
        return m


def main():
    import argparse
    import hashlib
    import json
    import os
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, required=True)
    args = parser.parse_args()
    source_sha = os.environ.get("SOURCE_COMMIT")
    if not source_sha:
        parser.error("SOURCE_COMMIT must identify the exact source commit")
    args.build_dir.mkdir(parents=True, exist_ok=True)
    platform = CynthionPlatformRev1D4()
    expected_ulpi = {0x39: 0x06}
    if platform.ulpi_extra_registers != expected_ulpi:
        raise SystemExit(f"unexpected r1.4 ULPI profile: {platform.ulpi_extra_registers!r}")
    platform.build(
        CynthionPowerMonitorTop(),
        name="cynthion_power_monitor",
        do_program=False,
        build_dir=str(args.build_dir),
    )
    bitstream = args.build_dir / "cynthion_power_monitor.bit"
    if not bitstream.is_file():
        raise SystemExit(f"build did not produce {bitstream}")
    receipt = {
        "purpose": "read-only Cynthion r1.4 TARGET-A VBUS/current diagnosis",
        "hardware_programmed": False,
        "source_commit": source_sha,
        "platform": "Cynthion r1.4",
        "i2c_driver": "LUNA I2CRegisterInterface, PAC1954 address 0x10",
        "channel": 1,
        "target_gpio": "not requested; outputs absent/high impedance",
        "phy_profile": {"identity": "USB3343 0424:0009", "function_control": "0x49 non-driving", "r1_4_io_power_management": "0x06 (DP/DM swap)", "must_readback_before_ready": True},
        "pac1954": {"manufacturer_id": "0x54", "range_register": "0x22", "required_active_range": "0x0000 unipolar defaults", "refresh_command": "REFRESH_V 0x1f Send Byte", "vbus_register": "0x07", "vsense_register": "0x0b", "vbus_scale": "raw * 32,000,000 uV / 65536", "vsense_scale": "raw * 100,000 uV / 65536", "shunt": "20,000 uOhm nominal, Cynthion r1.4 R2 ERJ-3BWFR020V", "current_scale": "raw * 5,000,000 / 65536 uA; unsigned unipolar", "jtag_measurements": "raw VBUS1 and VSENSE1; host applies scales"},
        "vbus_controls_active_high": {"CONTROL": 1, "TARGET_C": 0, "AUX": 0, "TARGET_A_discharge": 0},
        "bitstream": str(bitstream.resolve()),
        "bitstream_sha256": hashlib.sha256(bitstream.read_bytes()).hexdigest(),
        "timing_reports": sorted(p.name for p in args.build_dir.iterdir() if p.suffix in {".tim", ".rpt"}),
    }
    receipt_path = args.build_dir / "cynthion_power_monitor_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
