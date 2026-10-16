"""Fail-closed initialization and line-state observation for a USB3343 ULPI PHY.

This block only controls the USB3343 over ULPI. It never drives target D+/D-;
the enclosing gateware owns those pads and must gate their output enables with
``drive_allowed``. The PHY is initialized in ULPI synchronous mode with its
USB drivers and terminations disabled before that permission can rise.

The implementation deliberately reports RXCMD line-state observations, not
USB ACKs. An RXCMD is an observation at a particular instant; this block does
not promise periodic refresh or continuous line-state validity.
"""

from amaranth import Elaboratable, Module, Signal
from luna.gateware.interface.ulpi import ULPIRegisterWindow


class ULPISafePHY(Elaboratable):
    """Initialize a USB3343 into non-driving FS mode and expose RXCMD state.

    Args:
        ulpi: LUNA ``ULPIInterface`` or Cynthion ``ULPIResource`` pin record.
        startup_cycles: conservative delay after ``start`` before ULPI access.
            At 60 MHz the default 60,000 cycles is 1 ms.
        transaction_timeout_cycles: maximum wait for each register-window
            transaction. The global deadline also bounds the complete sequence.
        deadline_cycles: maximum number of ``usb`` clocks from ``start`` to
            verified completion. At 60 MHz the default 180,000 cycles is 3 ms.

    ``ulpi.rst`` and ``ulpi.clk`` remain owned by the enclosing design. Assert
    ``start`` only after PHY reset has been deasserted and the 60 MHz ULPI clock
    is running. ``start`` is a one-shot request; a fault clears drive permission
    until the FPGA/domain reset. All timing parameters are in ``usb`` clocks.
    """

    # USB334x ULPI register addresses (DS00002646A, §7).
    REG_VENDOR_ID_LOW = 0x00
    REG_VENDOR_ID_HIGH = 0x01
    REG_PRODUCT_ID_LOW = 0x02
    REG_PRODUCT_ID_HIGH = 0x03
    REG_FUNCTION_CONTROL = 0x04
    REG_OTG_CONTROL = 0x0A
    REG_USB_IF_CHARGER_DETECTION = 0x32
    REG_USB_IO_POWER_MANAGEMENT = 0x39

    # USB334x identity: VID 0x0424, PID 0x0009.
    IDENTITY = (
        (REG_VENDOR_ID_LOW, 0x24),
        (REG_VENDOR_ID_HIGH, 0x04),
        (REG_PRODUCT_ID_LOW, 0x09),
        (REG_PRODUCT_ID_HIGH, 0x00),
    )

    # XcvrSelect=FS (01), TermSelect=0, OpMode=non-driving (01),
    # RESET=0, SuspendM=1 (active-low suspend deasserted), LPMEnable=0.
    FUNCTION_CONTROL_SAFE = 0x49

    # All defined OTG controls clear: ID pullup, DP/DM pulldowns, VBUS
    # discharge/charge, VBUS driver and external indicator selection.
    OTG_CONTROL_SAFE = 0x00

    # Disable charger-detection circuitry at 0x32. Its DP/DM pullups are
    # separate bits 5:4 in USB IO & Power Management at 0x39.
    USB_IF_CHARGER_DETECTION_SAFE = 0x00

    # Preserve the USB3343 default UART regulator selection (3.0 V), while
    # leaving the board-specific D+/D- swap disabled unless selected by caller.
    USB_IO_POWER_MANAGEMENT_DEFAULT = 0x04
    USB_IO_POWER_MANAGEMENT_CYNTHION_R14 = 0x06

    def __init__(
        self,
        ulpi,
        *,
        startup_cycles=60_000,
        transaction_timeout_cycles=6_000,
        deadline_cycles=180_000,
        usb_io_power_management=USB_IO_POWER_MANAGEMENT_DEFAULT,
    ):
        if startup_cycles < 1:
            raise ValueError("startup_cycles must be positive")
        if transaction_timeout_cycles < 1:
            raise ValueError("transaction_timeout_cycles must be positive")
        if deadline_cycles <= startup_cycles:
            raise ValueError("deadline_cycles must exceed startup_cycles")
        if usb_io_power_management not in (
            self.USB_IO_POWER_MANAGEMENT_DEFAULT,
            self.USB_IO_POWER_MANAGEMENT_CYNTHION_R14,
        ):
            raise ValueError("unsupported USB3343 board power-management profile")

        self.ulpi = ulpi
        self.startup_cycles = startup_cycles
        self.transaction_timeout_cycles = transaction_timeout_cycles
        self.deadline_cycles = deadline_cycles
        self.usb_io_power_management = usb_io_power_management

        # One-shot initialization request and fail-closed status.
        self.start = Signal()
        self.ready = Signal()
        self.fault = Signal()
        self.drive_allowed = Signal()

        # RXCMD result. line_state_update pulses for a newly sampled RXCMD;
        # line_state_valid latches after the first such sample. The line-state
        # encoding is bit 0 = DP, bit 1 = DM (SE0/J/K/SE1 => 0/1/2/3 in FS).
        self.line_state_value = Signal(2)
        self.line_state_valid = Signal()
        self.line_state_update = Signal()
        self.line_state_age_cycles = Signal(32)

        # Optional one-shot terminal diagnostic. It only reads the PHY's
        # Debug register; status is separate from initialization ``fault``.
        self.diagnostic_read_request = Signal()
        self.diagnostic_attempted = Signal()
        self.diagnostic_done = Signal()
        self.diagnostic_error = Signal()
        self.diagnostic_value = Signal(8)

    def elaborate(self, platform):
        m = Module()
        window = ULPIRegisterWindow()
        m.submodules.register_window = window

        # LUNA's ULPIInterface uses scalar ``dir``/``nxt``/``stp`` signals,
        # while platform.request(ULPIResource(...)) returns nested pin
        # subsignals (``dir.i``, ``nxt.i``, ``stp.o``). Normalize both real
        # layouts explicitly rather than relying on flattened Record names.
        direction_in = getattr(self.ulpi.dir, "i", self.ulpi.dir)
        next_in = getattr(self.ulpi.nxt, "i", self.ulpi.nxt)
        stop_out = getattr(self.ulpi.stp, "o", self.ulpi.stp)
        data_in = self.ulpi.data.i
        data_out = self.ulpi.data.o
        data_oe = self.ulpi.data.oe

        # A global deadline may expire in the middle of an ULPI transaction.
        # Inhibit the link bus combinationally at that boundary, and latch the
        # fault below. The register window is not cancellable; it may complete
        # internally, but it cannot emit another byte or STP after inhibition.
        deadline_expired = Signal()
        inhibit_link = Signal()
        deadline_counter = Signal(range(self.deadline_cycles + 1))
        attempted = Signal()

        # LUNA ULPIRegisterWindow drives the ULPI data bus whenever the PHY
        # yields it. This is the ULPI link bus, not the USB target D+/D- pads.
        m.d.comb += [
            window.ulpi_data_in.eq(data_in),
            window.ulpi_dir.eq(direction_in),
            window.ulpi_next.eq(next_in),
            data_out.eq(window.ulpi_data_out),
            data_oe.eq(~direction_in & ~inhibit_link),
            stop_out.eq(window.ulpi_stop & ~inhibit_link),
            self.drive_allowed.eq(self.ready & ~self.fault),
            deadline_expired.eq(
                attempted
                & ~self.ready
                & ~self.fault
                & (deadline_counter == self.deadline_cycles - 1)
            ),
            inhibit_link.eq(self.fault | deadline_expired),
        ]

        # The verified sequence first authenticates the PHY identity, then
        # selects the disabled-driver mode, clears external pull controls,
        # configures the explicitly selected board-specific D+/D- routing,
        # and finally reads every safety-critical register back.
        transactions = []
        for address, expected in self.IDENTITY:
            transactions.append(("read", address, 0, 0xFF, expected))
        transactions.extend([
            ("write", self.REG_FUNCTION_CONTROL, self.FUNCTION_CONTROL_SAFE, 0, 0),
            ("write", self.REG_OTG_CONTROL, self.OTG_CONTROL_SAFE, 0, 0),
            ("write", self.REG_USB_IF_CHARGER_DETECTION,
             self.USB_IF_CHARGER_DETECTION_SAFE, 0, 0),
            ("write", self.REG_USB_IO_POWER_MANAGEMENT,
             self.usb_io_power_management, 0, 0),
            ("read", self.REG_FUNCTION_CONTROL, 0, 0xFF,
             self.FUNCTION_CONTROL_SAFE),
            ("read", self.REG_OTG_CONTROL, 0, 0xFF,
             self.OTG_CONTROL_SAFE),
            ("read", self.REG_USB_IF_CHARGER_DETECTION, 0, 0xFF,
             self.USB_IF_CHARGER_DETECTION_SAFE),
            ("read", self.REG_USB_IO_POWER_MANAGEMENT, 0, 0xFF,
             self.usb_io_power_management),
        ])

        transaction_index = Signal(range(len(transactions) + 1))
        startup_counter = Signal(range(self.startup_cycles + 1))
        transaction_counter = Signal(range(self.transaction_timeout_cycles + 1))
        direction_delayed = Signal()

        # Requests are single-cycle strobes. ULPIRegisterWindow keeps each
        # operation bounded here even if the PHY never acknowledges it.
        m.d.usb += [
            window.read_request.eq(0),
            window.write_request.eq(0),
            self.line_state_update.eq(0),
            self.diagnostic_done.eq(0),
            direction_delayed.eq(direction_in),
        ]

        with m.If(self.line_state_valid & ~self.line_state_update):
            with m.If(self.line_state_age_cycles != 0xFFFFFFFF):
                m.d.usb += self.line_state_age_cycles.eq(
                    self.line_state_age_cycles + 1)
        with m.If(self.line_state_update):
            m.d.usb += self.line_state_age_cycles.eq(0)

        with m.If(attempted & ~self.ready & ~self.fault):
            with m.If(deadline_counter == self.deadline_cycles - 1):
                m.d.usb += self.fault.eq(1)
            with m.Else():
                m.d.usb += deadline_counter.eq(deadline_counter + 1)

        # LUNA's RX event qualification: DIR high on successive clocks, NXT
        # low, and no register transaction in progress. Ignore startup and
        # configuration RXCMDs; expose only observations after safe readback.
        with m.If(
            self.ready
            & ~self.diagnostic_attempted
            & direction_delayed
            & direction_in
            & ~next_in
            & ~window.busy
        ):
            m.d.usb += [
                self.line_state_value.eq(data_in[0:2]),
                self.line_state_valid.eq(1),
                self.line_state_update.eq(1),
            ]

        with m.FSM(domain="usb", init="IDLE") as fsm:
            with m.State("IDLE"):
                with m.If(self.start & ~attempted):
                    m.d.usb += [
                        attempted.eq(1),
                        startup_counter.eq(0),
                        transaction_counter.eq(0),
                        deadline_counter.eq(0),
                    ]
                    m.next = "STARTUP_DELAY"

            with m.State("STARTUP_DELAY"):
                with m.If(startup_counter == self.startup_cycles - 1):
                    m.d.usb += [startup_counter.eq(0), transaction_index.eq(0)]
                    m.next = "ISSUE_0"
                with m.Else():
                    m.d.usb += startup_counter.eq(startup_counter + 1)

            for index, (kind, address, value, mask, expected) in enumerate(transactions):
                with m.State(f"ISSUE_{index}"):
                    with m.If(self.fault | deadline_expired):
                        m.d.usb += self.fault.eq(1)
                        m.next = "FAILED"
                    with m.Else():
                        m.d.usb += [
                            window.address.eq(address),
                            transaction_counter.eq(0),
                        ]
                        if kind == "read":
                            m.d.usb += window.read_request.eq(1)
                        else:
                            m.d.usb += [
                                window.write_data.eq(value),
                                window.write_request.eq(1),
                            ]
                        m.next = f"WAIT_{index}"

                with m.State(f"WAIT_{index}"):
                    with m.If(self.fault | deadline_expired):
                        m.d.usb += self.fault.eq(1)
                        m.next = "FAILED"
                    with m.Elif(window.done):
                        m.d.usb += transaction_counter.eq(0)
                        if kind == "read":
                            with m.If((window.read_data & mask) != expected):
                                m.d.usb += self.fault.eq(1)
                                m.next = "FAILED"
                            with m.Else():
                                if index + 1 < len(transactions):
                                    m.next = f"ISSUE_{index + 1}"
                                else:
                                    m.next = "VERIFIED"
                        elif index + 1 < len(transactions):
                            m.next = f"ISSUE_{index + 1}"
                        else:
                            m.next = "VERIFIED"
                    with m.Elif(transaction_counter == self.transaction_timeout_cycles - 1):
                        m.d.usb += self.fault.eq(1)
                        m.next = "FAILED"
                    with m.Else():
                        m.d.usb += transaction_counter.eq(transaction_counter + 1)

            with m.State("VERIFIED"):
                with m.If(self.fault | deadline_expired):
                    m.d.usb += self.fault.eq(1)
                    m.next = "FAILED"
                with m.Else():
                    m.d.usb += self.ready.eq(1)
                    m.next = "COMPLETE"

            with m.State("COMPLETE"):
                with m.If(self.diagnostic_read_request
                          & ~self.diagnostic_attempted):
                    m.d.usb += [
                        self.diagnostic_attempted.eq(1),
                        transaction_counter.eq(0),
                    ]
                    m.next = "DIAGNOSTIC_ISSUE"

            with m.State("DIAGNOSTIC_ISSUE"):
                with m.If(~window.busy):
                    m.d.usb += [
                        window.address.eq(0x15),
                        window.read_request.eq(1),
                        transaction_counter.eq(0),
                    ]
                    m.next = "DIAGNOSTIC_WAIT"
                with m.Elif(transaction_counter == self.transaction_timeout_cycles - 1):
                    m.d.usb += [self.diagnostic_done.eq(1),
                                self.diagnostic_error.eq(1)]
                    m.next = "COMPLETE"
                with m.Else():
                    m.d.usb += transaction_counter.eq(transaction_counter + 1)

            with m.State("DIAGNOSTIC_WAIT"):
                with m.If(window.done):
                    m.d.usb += [
                        self.diagnostic_value.eq(window.read_data),
                        self.diagnostic_done.eq(1),
                    ]
                    m.next = "COMPLETE"
                with m.Elif(transaction_counter == self.transaction_timeout_cycles - 1):
                    m.d.usb += [self.diagnostic_done.eq(1),
                                self.diagnostic_error.eq(1)]
                    m.next = "COMPLETE"
                with m.Else():
                    m.d.usb += transaction_counter.eq(transaction_counter + 1)

            with m.State("FAILED"):
                m.d.usb += [self.ready.eq(0), self.fault.eq(1)]

        return m
