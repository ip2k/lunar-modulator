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


class UsbKeyTerminalSnapshot(Elaboratable):
    """One-shot USB-domain receipt; register 0x0e retains its legacy meaning.

    Layout 9 adds 0x67: bit 0 valid, bit 1 persistent local candidate. Neither
    field establishes a physical target ACK. Domain reset clears every receipt.
    """

    def __init__(self, core):
        self.core = core
        self.valid = Signal()
        self.ack_candidate = Signal(32)
        self.protocol_failure = Signal(32)
        self.packet_count = Signal(32)
        self.ack_progress = Signal(32)
        self.wait_progress = Signal(32)
        self.sof_progress = Signal(32)
        self.sof_low_progress = Signal(32)
        self.key_progress = Signal(32)

    def elaborate(self, platform):
        m = Module()
        core = self.core
        terminal_snapshot_valid = self.valid
        protocol_failure_snapshot = self.protocol_failure
        packet_count_snapshot = self.packet_count
        ack_progress_snapshot = self.ack_progress
        wait_progress_snapshot = self.wait_progress
        sof_progress_snapshot = self.sof_progress
        sof_low_progress_snapshot = self.sof_low_progress
        key_progress_snapshot = self.key_progress
        with m.If(~terminal_snapshot_valid &
                  ((core.state == core.DONE) | (core.state == core.FAULT))):
            m.d.usb += [
                terminal_snapshot_valid.eq(1),
                self.ack_candidate.eq(Cat(Const(1), core.debug_ack_candidate)),
                protocol_failure_snapshot.eq(Cat(
                    Const(1),
                    core.protocol_failure_reason,
                    core.protocol_failure_origin_state,
                    core.state)),
                packet_count_snapshot.eq(core.debug_packets),
                ack_progress_snapshot.eq(Cat(
                    core.debug_receiver_live,
                    core.debug_ack_confirm,
                    core.debug_ack_ticks[:16])),
                wait_progress_snapshot.eq(core.debug_wait_ticks),
                sof_progress_snapshot.eq(core.debug_sof_ticks),
                sof_low_progress_snapshot.eq(core.debug_dp_low_ticks),
                key_progress_snapshot.eq(Cat(
                    core.debug_key_bit, core.debug_key_phase)),
            ]
        return m


class CynthionUsbKeyTop(Elaboratable):
    """Core integration with explicit, default-off VBUS selection."""

    def __init__(self, *, mode="operation", target_power_from_control=False):
        if mode not in {"operation", "disconnected-selftest", "staged-operation", "pico-repeat"}:
            raise ValueError(f"unsupported mode: {mode}")
        if target_power_from_control and mode not in {"operation", "staged-operation", "pico-repeat"}:
            raise ValueError("CONTROL power is available only in operation modes")
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
        pico_repeat = self.mode == "pico-repeat"
        repeat_parameters = (dict(pico_repeat=True, repeat_cycles=16, repeat_words=3000,
                                  repeat_sof_us=2_000_000, sof_period_us=1000,
                                  sof_pulse_us=500) if pico_repeat else {})
        core = CynthionUsbKey(domain="usb", clock_hz=60_000_000,
                              auto_selftest=selftest_only,
                              selftest_only=selftest_only,
                              staged_operation=self.mode in {"staged-operation", "pico-repeat"},
                              **repeat_parameters)
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
            safe_phy.diagnostic_read_request.eq(
                (core.state == core.FAULT)
                & (core.protocol_failure_reason
                   == core.PROTOCOL_FAULT_WAIT_DP_TIMEOUT)),
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
        debug.add_read_only_register(2, read=9)
        status_snapshot = Signal(32)
        status_bits = Cat(core.state, safe_phy.ready, safe_phy.fault,
                          core.selftest_mask, safe_phy.line_state_valid,
                          safe_phy.line_state_value,
                          Const(self.mode == "disconnected-selftest"),
                          Const(self.target_power_from_control),
                          Const(self.mode in {"staged-operation", "pico-repeat"}),
                          Const(pico_repeat))
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

        # Preserve protocol failure provenance after the core has returned its
        # outputs to high impedance. These snapshots are diagnostic-only and
        # are captured once when DONE/FAULT is first observed in the USB
        # domain; they do not feed the protocol state machine.
        terminal = UsbKeyTerminalSnapshot(core)
        m.submodules.terminal = terminal
        debug.add_read_only_register(12, read=terminal.protocol_failure)
        debug.add_read_only_register(13, read=terminal.packet_count)
        debug.add_read_only_register(14, read=terminal.ack_progress)
        debug.add_read_only_register(15, read=terminal.wait_progress)
        debug.add_read_only_register(16, read=terminal.sof_progress)
        debug.add_read_only_register(17, read=terminal.sof_low_progress)
        debug.add_read_only_register(18, read=terminal.key_progress)
        debug.add_read_only_register(0x67, read=terminal.ack_candidate)

        # Layout v5 adds a read-only 32-entry event ring. Each entry is two
        # consecutive 32-bit words at 0x20 + 2*slot: timestamp_us and packed
        # state snapshot. The next-write pointer
        # and saturated count let the reader recover chronological order after
        # wrap without adding an address-selection write path.
        debug.add_read_only_register(19, read=Cat(
            core.history_next_index, core.history_count, core.history_frozen))
        debug.add_read_only_register(20, read=core.history_timestamp_us)
        for index, entry in enumerate(core.history_entries):
            base = 0x20 + index * 2
            debug.add_read_only_register(base, read=entry[:32])
            debug.add_read_only_register(base + 1, read=entry[32:64])

        # A WAIT_DP timeout triggers exactly one bounded, read-only USB3343
        # Debug-register observation. Keep it distinct from PHY initialization
        # fault state; the protocol core remains terminal and pad OEs stay low.
        diagnostic_snapshot_valid = Signal()
        diagnostic_status_snapshot = Signal(32)
        diagnostic_value_snapshot = Signal(32)
        diagnostic_line_snapshot = Signal(32)
        diagnostic_age_snapshot = Signal(32)
        diagnostic_gpio_snapshot = Signal(32)
        with m.If(safe_phy.diagnostic_done & ~diagnostic_snapshot_valid):
            m.d.usb += [
                diagnostic_snapshot_valid.eq(1),
                diagnostic_status_snapshot.eq(Cat(
                    Const(1), safe_phy.diagnostic_attempted,
                    safe_phy.diagnostic_error)),
                diagnostic_value_snapshot.eq(safe_phy.diagnostic_value),
                diagnostic_line_snapshot.eq(Cat(
                    safe_phy.line_state_valid, safe_phy.line_state_value)),
                diagnostic_age_snapshot.eq(safe_phy.line_state_age_cycles),
                diagnostic_gpio_snapshot.eq(Cat(
                    dp.i, dm.i, core.dp_o, core.dm_o, dp.oe, dm.oe)),
            ]
        debug.add_read_only_register(0x60, read=diagnostic_status_snapshot)
        debug.add_read_only_register(0x61, read=diagnostic_value_snapshot)
        debug.add_read_only_register(0x62, read=diagnostic_line_snapshot)
        debug.add_read_only_register(0x63, read=diagnostic_age_snapshot)
        debug.add_read_only_register(0x64, read=diagnostic_gpio_snapshot)

        if pico_repeat:
            # Repeat extension remains read-only and profile-specific.
            debug.add_read_only_register(0x65, read=Cat(
                Const(1, 8), Const(16, 8), Const(3000, 16)))
            debug.add_read_only_register(0x66, read=Cat(
                core.debug_repeat_cycles, core.debug_packets[:16]))

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
