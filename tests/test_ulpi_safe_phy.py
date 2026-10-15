"""Offline simulations of the fail-closed USB3343 ULPI initializer."""

import unittest

import pytest

pytest.importorskip("amaranth")
pytest.importorskip("cynthion")
pytest.importorskip("luna")

from amaranth import ClockDomain, Elaboratable, Module, ResetSignal, ClockSignal
from cynthion.gateware.platform.cynthion_r1_4 import CynthionPlatformRev1D4
from amaranth.sim import Simulator
from luna.gateware.interface.ulpi import ULPIInterface

from gateware.ulpi_safe_phy import ULPISafePHY
from tools.cynthion_usb_key.top import CynthionUsbKeyPlatform


class _Top(Elaboratable):
    def __init__(self, *, startup_cycles=2, transaction_timeout_cycles=8,
                 deadline_cycles=120, platform_pin_record=False,
                 usb_io_power_management=ULPISafePHY.USB_IO_POWER_MANAGEMENT_DEFAULT):
        self.ulpi = ULPIInterface()
        self.platform_pin_record = platform_pin_record
        self.platform = None
        if platform_pin_record:
            self.platform = CynthionPlatformRev1D4()
            self.ulpi = self.platform.request("target_phy")
        self.dut = ULPISafePHY(
            self.ulpi,
            startup_cycles=startup_cycles,
            transaction_timeout_cycles=transaction_timeout_cycles,
            deadline_cycles=deadline_cycles,
            usb_io_power_management=usb_io_power_management,
        )

    def elaborate(self, platform):
        m = Module()
        m.domains.usb = ClockDomain("usb")
        m.submodules.safe_phy = self.dut
        if self.platform_pin_record:
            # This is the bridge used for Cynthion's nested ULPIResource pins.
            m.d.comb += [
                self.ulpi.clk.o.eq(ClockSignal("usb")),
                self.ulpi.rst.o.eq(ResetSignal("usb")),
            ]
        return m


def _port(record, name, direction):
    signal = getattr(record, name)
    return getattr(signal, direction, signal)


class _FakeUSB3343:
    """Minimal ULPI responder that exercises LUNA's real register window."""

    def __init__(self, top, *, response=True, initial=None, read_override=None):
        self.top = top
        self.ulpi = top.ulpi
        self.dir = _port(self.ulpi, "dir", "i")
        self.nxt = _port(self.ulpi, "nxt", "i")
        self.data_in = _port(self.ulpi, "data", "i")
        self.data_out = _port(self.ulpi, "data", "o")
        self.data_oe = _port(self.ulpi, "data", "oe")
        self.stop = _port(self.ulpi, "stp", "o")
        self.dut = top.dut
        self.response = response
        self.registers = {
            0x00: 0x24,
            0x01: 0x04,
            0x02: 0x09,
            0x03: 0x00,
            0x04: 0x41,
            0x0A: 0x06,
            0x32: 0x00,
            0x39: 0x04,
        }
        if initial:
            self.registers.update(initial)
        self.read_override = read_override
        self.read_counts = {}
        self.reads = []
        self.writes = []
        self.commands = []
        self.stp_pulses = 0
        self.bus_output = []
        self.premature_drive = False
        self.link_enabled_on_fault = None
        self.fault_cycle = None

    async def run(self, ctx, *, max_cycles=200):
        ctx.set(self.dir, 0)
        ctx.set(self.nxt, 0)
        ctx.set(self.data_in, 0)
        ctx.set(self.dut.start, 1)
        mode = "idle"
        address = 0
        command_kind = None
        wait_count = 0
        payload = 0

        for cycle in range(max_cycles):
            await ctx.tick("usb")
            ctx.set(self.dut.start, 0)
            if ctx.get(self.data_oe):
                self.bus_output.append((cycle, ctx.get(self.data_out)))
            if not ctx.get(self.dut.ready) and ctx.get(self.dut.drive_allowed):
                self.premature_drive = True
            if ctx.get(self.dut.ready) or ctx.get(self.dut.fault):
                if ctx.get(self.dut.fault):
                    self.link_enabled_on_fault = ctx.get(self.data_oe)
                    self.fault_cycle = cycle
                return
            if not self.response:
                continue

            if mode == "idle":
                if (ctx.get(self.dir) == 0
                        and ctx.get(self.data_oe)
                        and (ctx.get(self.data_out) & 0xC0) in (0x80, 0xC0)):
                    command = ctx.get(self.data_out)
                    address = command & 0x3F
                    command_kind = "read" if (command & 0xC0) == 0xC0 else "write"
                    self.commands.append((command_kind, address))
                    ctx.set(self.nxt, 1)
                    mode = "accept_read_command" if command_kind == "read" else "accept_write_command"

            elif mode == "accept_read_command":
                value = self.registers.get(address, 0)
                self.reads.append(address)
                if self.read_override is not None:
                    count = self.read_counts.get(address, 0)
                    replacement = self.read_override(address, count, value)
                    if replacement is not None:
                        value = replacement
                self.read_counts[address] = self.read_counts.get(address, 0) + 1
                ctx.set(self.nxt, 0)
                ctx.set(self.data_in, value)
                ctx.set(self.dir, 1)
                wait_count = 0
                mode = "read_turnaround"

            elif mode == "read_turnaround":
                wait_count += 1
                if wait_count >= 3:
                    ctx.set(self.dir, 0)
                    ctx.set(self.data_in, 0)
                    mode = "idle"

            elif mode == "accept_write_command":
                ctx.set(self.nxt, 0)
                mode = "write_payload"

            elif mode == "write_payload":
                payload = ctx.get(self.data_out)
                self.writes.append((address, payload))
                ctx.set(self.nxt, 1)
                mode = "accept_write_payload"

            elif mode == "accept_write_payload":
                self.registers[address] = payload
                if ctx.get(self.stop):
                    self.stp_pulses += 1
                ctx.set(self.nxt, 0)
                mode = "idle"

            elif mode == "write_stop":
                if ctx.get(self.stop):
                    mode = "idle"

            if ctx.get(self.dut.ready) or ctx.get(self.dut.fault):
                return

        raise AssertionError("initializer neither completed nor faulted within simulation bound")


class ULPISafePHYTests(unittest.TestCase):
    def test_r14_profile_matches_installed_platform_trace_swap(self):
        self.assertEqual(
            CynthionUsbKeyPlatform.ulpi_extra_registers[
                ULPISafePHY.REG_USB_IO_POWER_MANAGEMENT
            ],
            ULPISafePHY.USB_IO_POWER_MANAGEMENT_CYNTHION_R14,
        )

    def _simulate(self, top, process):
        sim = Simulator(top)
        sim.add_clock(1 / 60_000_000, domain="usb")
        sim.add_testbench(process)
        sim.run()

    def test_success_requires_identity_and_exact_safety_readback(self):
        top = _Top()
        fake = _FakeUSB3343(top)
        observed = {}

        async def bench(ctx):
            await fake.run(ctx)
            observed["ready"] = ctx.get(top.dut.ready)
            observed["fault"] = ctx.get(top.dut.fault)
            observed["drive"] = ctx.get(top.dut.drive_allowed)
            observed["writes"] = list(fake.writes)
            observed["reads"] = list(fake.reads)
            observed["premature_drive"] = fake.premature_drive

            # One RXCMD sample is surfaced with ULPI bit ordering preserved.
            ctx.set(top.ulpi.data.i, 0b10)
            ctx.set(top.ulpi.dir, 1)
            ctx.set(top.ulpi.nxt, 0)
            await ctx.tick("usb")
            await ctx.tick("usb")
            observed["line_value"] = ctx.get(top.dut.line_state_value)
            observed["line_valid"] = ctx.get(top.dut.line_state_valid)
            observed["line_update"] = ctx.get(top.dut.line_state_update)
            observed["drive_after_rxcmd"] = ctx.get(top.dut.drive_allowed)
            ctx.set(top.ulpi.dir, 0)
            await ctx.tick("usb")
            observed["line_update_ended"] = ctx.get(top.dut.line_state_update)

        self._simulate(top, bench)
        self.assertEqual(observed["ready"], 1)
        self.assertEqual(observed["fault"], 0)
        self.assertEqual(observed["drive"], 1)
        self.assertEqual(observed["writes"], [
            (0x04, 0x49), (0x0A, 0x00), (0x32, 0x00), (0x39, 0x04),
        ])
        self.assertEqual(observed["reads"], [
            0x00, 0x01, 0x02, 0x03, 0x04, 0x0A, 0x32, 0x39,
        ])
        self.assertFalse(observed["premature_drive"])
        self.assertEqual(observed["line_value"], 2)  # D- high, D+ low (K)
        self.assertEqual(observed["line_valid"], 1)
        self.assertEqual(observed["line_update"], 1)
        self.assertEqual(observed["line_update_ended"], 0)
        self.assertEqual(observed["drive_after_rxcmd"], 1)
        self.assertEqual(fake.commands, [
            ("read", 0x00), ("read", 0x01), ("read", 0x02), ("read", 0x03),
            ("write", 0x04), ("write", 0x0A), ("write", 0x32), ("write", 0x39),
            ("read", 0x04), ("read", 0x0A), ("read", 0x32), ("read", 0x39),
        ])
        self.assertEqual(fake.stp_pulses, 4)

    def test_cynthion_r14_target_phy_resource_bridges_real_transactions(self):
        top = _Top(
            platform_pin_record=True,
            usb_io_power_management=ULPISafePHY.USB_IO_POWER_MANAGEMENT_CYNTHION_R14,
        )
        fake = _FakeUSB3343(top)
        observed = {}

        async def bench(ctx):
            await fake.run(ctx)
            observed.update(
                ready=ctx.get(top.dut.ready),
                fault=ctx.get(top.dut.fault),
                drive=ctx.get(top.dut.drive_allowed),
                clk=ctx.get(top.ulpi.clk.o),
                stp=ctx.get(top.ulpi.stp.o),
                writes=list(fake.writes),
                reads=list(fake.reads),
                commands=list(fake.commands),
                stp_pulses=fake.stp_pulses,
            )

        self._simulate(top, bench)
        self.assertEqual(observed["ready"], 1)
        self.assertEqual(observed["fault"], 0)
        self.assertEqual(observed["drive"], 1)
        self.assertEqual(observed["clk"], 1)
        self.assertEqual(observed["stp"], 0)
        self.assertEqual(observed["writes"], [
            (0x04, 0x49), (0x0A, 0x00), (0x32, 0x00), (0x39, 0x06),
        ])
        self.assertEqual(observed["reads"], [
            0x00, 0x01, 0x02, 0x03, 0x04, 0x0A, 0x32, 0x39,
        ])
        self.assertEqual(observed["commands"], [
            ("read", 0x00), ("read", 0x01), ("read", 0x02), ("read", 0x03),
            ("write", 0x04), ("write", 0x0A), ("write", 0x32), ("write", 0x39),
            ("read", 0x04), ("read", 0x0A), ("read", 0x32), ("read", 0x39),
        ])
        self.assertEqual(observed["stp_pulses"], 4)

    def test_wrong_phy_identity_never_allows_drive(self):
        top = _Top()
        fake = _FakeUSB3343(top, initial={0x00: 0x00})
        observed = {}

        async def bench(ctx):
            await fake.run(ctx)
            observed.update(
                ready=ctx.get(top.dut.ready),
                fault=ctx.get(top.dut.fault),
                drive=ctx.get(top.dut.drive_allowed),
                writes=list(fake.writes),
            )

        self._simulate(top, bench)
        self.assertEqual(observed["ready"], 0)
        self.assertEqual(observed["fault"], 1)
        self.assertEqual(observed["drive"], 0)
        self.assertEqual(observed["writes"], [])

    def test_function_control_readback_mismatch_latches_fault(self):
        top = _Top()

        def read_override(address, count, value):
            if address == 0x04 and count >= 0:
                return value ^ 0x08
            return None

        fake = _FakeUSB3343(top, read_override=read_override)
        observed = {}

        async def bench(ctx):
            await fake.run(ctx)
            observed.update(
                ready=ctx.get(top.dut.ready),
                fault=ctx.get(top.dut.fault),
                drive=ctx.get(top.dut.drive_allowed),
            )

        self._simulate(top, bench)
        self.assertEqual(observed, {"ready": 0, "fault": 1, "drive": 0})

    def test_cynthion_line_swap_readback_mismatch_never_allows_drive(self):
        top = _Top(
            usb_io_power_management=ULPISafePHY.USB_IO_POWER_MANAGEMENT_CYNTHION_R14,
        )

        def read_override(address, count, value):
            if address == 0x39 and count >= 0:
                return value ^ 0x02
            return None

        fake = _FakeUSB3343(top, read_override=read_override)
        observed = {}

        async def bench(ctx):
            await fake.run(ctx)
            observed.update(
                ready=ctx.get(top.dut.ready),
                fault=ctx.get(top.dut.fault),
                drive=ctx.get(top.dut.drive_allowed),
                writes=list(fake.writes),
                reads=list(fake.reads),
            )

        self._simulate(top, bench)
        self.assertEqual(observed["ready"], 0)
        self.assertEqual(observed["fault"], 1)
        self.assertEqual(observed["drive"], 0)
        self.assertIn((0x39, 0x06), observed["writes"])
        self.assertIn(0x39, observed["reads"])

    def test_unacknowledged_ulpi_request_times_out_fail_closed(self):
        top = _Top(transaction_timeout_cycles=5, deadline_cycles=80)
        fake = _FakeUSB3343(top, response=False)
        observed = {}

        async def bench(ctx):
            await fake.run(ctx, max_cycles=80)
            observed.update(
                ready=ctx.get(top.dut.ready),
                fault=ctx.get(top.dut.fault),
                drive=ctx.get(top.dut.drive_allowed),
            )

        self._simulate(top, bench)
        self.assertEqual(observed, {"ready": 0, "fault": 1, "drive": 0})

    def test_global_deadline_bounds_startup(self):
        top = _Top(startup_cycles=10, deadline_cycles=12)
        fake = _FakeUSB3343(top, response=False)
        observed = {}

        async def bench(ctx):
            await fake.run(ctx, max_cycles=20)
            observed.update(
                ready=ctx.get(top.dut.ready),
                fault=ctx.get(top.dut.fault),
                drive=ctx.get(top.dut.drive_allowed),
            )

        self._simulate(top, bench)
        self.assertEqual(observed, {"ready": 0, "fault": 1, "drive": 0})

    def test_global_deadline_stops_inflight_luna_request_without_more_bus_bytes(self):
        top = _Top(startup_cycles=2, transaction_timeout_cycles=50, deadline_cycles=12)
        fake = _FakeUSB3343(top, response=False)
        observed = {}

        async def bench(ctx):
            await fake.run(ctx, max_cycles=20)
            observed.update(
                ready=ctx.get(top.dut.ready),
                fault=ctx.get(top.dut.fault),
                drive=ctx.get(top.dut.drive_allowed),
                enabled_on_fault=fake.link_enabled_on_fault,
                fault_cycle=fake.fault_cycle,
                bytes=list(fake.bus_output),
            )

        self._simulate(top, bench)
        self.assertEqual(observed["ready"], 0)
        self.assertEqual(observed["fault"], 1)
        self.assertEqual(observed["drive"], 0)
        self.assertEqual(observed["enabled_on_fault"], 0)
        self.assertTrue(any(byte == 0xC0 for _, byte in observed["bytes"]))
        self.assertTrue(all(cycle < observed["fault_cycle"] for cycle, _ in observed["bytes"]))

if __name__ == "__main__":
    unittest.main()
