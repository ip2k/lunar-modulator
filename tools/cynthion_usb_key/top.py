"""Offline-buildable top level for an explicitly armed Cynthion r1.4 prototype."""

from types import SimpleNamespace

from amaranth import Cat, ClockSignal, Const, DomainRenamer, Elaboratable, Module, ResetSignal, Signal
from amaranth.build import Attrs, Pins, Resource
from cynthion.gateware.platform.cynthion_r1_4 import CynthionPlatformRev1D4
from luna.gateware.interface.jtag import JTAGRegisterInterface

from gateware.ulpi_safe_phy import ULPISafePHY
from tools.cynthion_usb_key.gateware import CynthionUsbKey


_SHARED_TARGET_RESOURCES = {
    "target_usb_diff",
    "target_usb_dp",
    "target_usb_dm",
    "target_usb_dp_chirp",
    "target_usb_dm_chirp",
}


class CynthionUsbKeyPlatform(CynthionPlatformRev1D4):
    """r1.4 pin map with N4/P3 explicitly requested as tri-state GPIOs.

    The base platform exposes these pins as input-only. Replacing the resource
    declarations keeps the same N4/P3 bank and LVCMOS33 attributes; all pseudo
    VCCIO/GND resources and other r1.4 settings remain intact.
    """

    resources = [r for r in CynthionPlatformRev1D4.resources
                 if r.name not in _SHARED_TARGET_RESOURCES] + [
        Resource("target_usb_dp", 0, Pins("N4", dir="io"),
                 Attrs(IO_TYPE="LVCMOS33", PULLMODE="NONE")),
        Resource("target_usb_dm", 0, Pins("P3", dir="io"),
                 Attrs(IO_TYPE="LVCMOS33", PULLMODE="NONE")),
    ]


class CynthionUsbKeyTop(Elaboratable):
    """Core integration with explicit, default-off VBUS selection."""

    def __init__(self, *, mode="operation", target_power_from_control=False):
        if mode not in {"operation", "disconnected-selftest"}:
            raise ValueError(f"unsupported mode: {mode}")
        if target_power_from_control and mode != "operation":
            raise ValueError("CONTROL power is available only in operation mode")
        self.mode = mode
        self.target_power_from_control = bool(target_power_from_control)

    def elaborate(self, platform):
        m = Module()
        m.submodules.car = platform.clock_domain_generator()

        # `clk` is an FPGA output on this r1.4 ULPI resource. Hold target PHY
        # reset with the USB domain reset and initialize only after that domain
        # is running. The ULPISafePHY then performs identity/config/readback.
        target_phy = platform.request("target_phy")
        m.d.comb += [
            target_phy.clk.o.eq(ClockSignal("usb")),
            target_phy.rst.o.eq(ResetSignal("usb")),
        ]
        # The platform resource is a raw pin record (`dir.i`, `stp.o`), while
        # the safe block intentionally consumes plain ULPI signals. Bridge the
        # two explicitly so direction and data-bus ownership are reviewable.
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
        # Cynthion r1.4 routes D+/D- crossed into the USB3343. This is the
        # platform's documented 0x39 setting, now applied and read back by the
        # standalone initializer rather than inherited via ULPITransceiver.
        safe_phy = ULPISafePHY(
            ulpi,
            usb_io_power_management=(
                ULPISafePHY.USB_IO_POWER_MANAGEMENT_CYNTHION_R14
            ),
        )
        m.submodules.safe_phy = safe_phy

        start = Signal()
        start_delay = Signal(range(60_001))
        with m.If(~ResetSignal("usb")):
            with m.If(start_delay == 60_000):
                m.d.usb += start.eq(1)
            with m.Else():
                m.d.usb += start_delay.eq(start_delay + 1)
        m.d.comb += safe_phy.start.eq(start)

        # The root-reviewed r1.4 schematic places Bank 6 on +3V3. This is a
        # platform constant, not a voltage sensor or universal-board claim.
        # The self-test image autonomously performs only the four-state GPIO
        # loopback after verified PHY isolation. It cannot enter KEY. The
        # operation image remains disarmed until a debounced USER press.
        selftest_only = self.mode == "disconnected-selftest"
        core = CynthionUsbKey(domain="usb", clock_hz=60_000_000,
                              auto_selftest=selftest_only,
                              selftest_only=selftest_only)
        m.submodules.protocol = core
        button = platform.request("button_user")
        dp = platform.request("target_usb_dp")
        dm = platform.request("target_usb_dm")
        m.d.comb += [
            core.user_button.eq(button.i),
            core.pad_dp_i.eq(dp.i),
            core.pad_dm_i.eq(dm.i),
            core.phy_isolated.eq(safe_phy.drive_allowed),
            core.phy_fault.eq(safe_phy.fault),
            core.bank6_3v3_confirmed.eq(1),
            core.ack_sense_valid.eq(safe_phy.ready & ~safe_phy.fault),
            core.line_state_value.eq(safe_phy.line_state_value),
            core.line_state_valid.eq(safe_phy.line_state_valid),
            core.line_state_update.eq(safe_phy.line_state_update),
            dp.o.eq(core.dp_o), dp.oe.eq(core.dp_oe & safe_phy.drive_allowed),
            dm.o.eq(core.dm_o), dm.oe.eq(core.dm_oe & safe_phy.drive_allowed),
        ]

        # Read-only ECP5 JTAG register endpoint (LUNA's supported debug path).
        # It exposes coarse, non-authoritative status only; no write register
        # can arm keying or change electrical gates.
        # Its scan command path uses the domain named "sync" internally. Move
        # that interface into the USB clock domain so the status snapshot is
        # sampled coherently with protocol/PHY state, without a multi-bit CDC.
        debug = DomainRenamer({"sync": "usb"})(
            JTAGRegisterInterface(default_read_value=0xBAD0C0DE))
        m.submodules.debug_registers = debug
        debug.add_read_only_register(1, read=0x4C554E52)  # "LUNR"
        debug.add_read_only_register(2, read=3)           # register layout v3
        status_snapshot = Signal(32)
        status_bits = Cat(core.state, safe_phy.ready, safe_phy.fault,
                          core.selftest_mask, safe_phy.line_state_valid,
                          safe_phy.line_state_value,
                          Const(self.mode == "disconnected-selftest"),
                          Const(self.target_power_from_control))
        m.d.usb += status_snapshot.eq(status_bits)
        debug.add_read_only_register(3, read=status_snapshot)
        gpio_snapshot = Signal(32)
        failure_snapshot = Signal(32)
        failure_gpio_snapshot = Signal(32)
        m.d.usb += [
            gpio_snapshot.eq(Cat(dp.i, dm.i, core.dp_o, core.dm_o,
                                 dp.oe, dm.oe)),
            failure_snapshot.eq(Cat(core.selftest_failure_reason,
                                    core.selftest_failure_step,
                                    core.selftest_failure_expected,
                                    core.selftest_failure_observed)),
            failure_gpio_snapshot.eq(core.selftest_failure_gpio),
        ]
        debug.add_read_only_register(4, read=gpio_snapshot)
        debug.add_read_only_register(5, read=failure_snapshot)
        debug.add_read_only_register(6, read=failure_gpio_snapshot)
        debug.add_read_only_register(
            7, read=Cat(*core.selftest_step_events))
        debug.add_read_only_register(
            8, read=Cat(*core.selftest_step_observed))
        debug.add_read_only_register(9, read=core.selftest_observed_valid)
        debug.add_read_only_register(10, read=0xC6)  # K, J, SE0, SE1, packed
        debug.add_read_only_register(11, read=Cat(*core.selftest_step_gpio))

        for bit in range(6):
            m.d.comb += platform.request("led", bit).o.eq(core.leds[bit])

        # r1.4 switches are active high. CONTROL->TARGET-A is an explicit,
        # operation-only build choice; TARGET-C passthrough and AUX remain off
        # in every mode, and the discharge path stays off. There is no USB
        # control-plane path. The default keeps every switch disabled.
        m.d.comb += [
            platform.request("target_c_vbus_en").o.eq(0),
            platform.request("control_vbus_en").o.eq(
                int(self.target_power_from_control)),
            platform.request("aux_vbus_en").o.eq(0),
            platform.request("target_a_discharge").o.eq(0),
        ]
        return m
