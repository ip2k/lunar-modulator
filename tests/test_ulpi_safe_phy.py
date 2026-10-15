"""Offline simulations of the fail-closed USB3343 ULPI initializer."""

import unittest

from amaranth import ClockDomain, Elaboratable, Module
from amaranth.sim import Simulator
from luna.gateware.interface.ulpi import ULPIInterface

from gateware.ulpi_safe_phy import ULPISafePHY


class _Top(Elaboratable):
    def __init__(self, *, startup_cycles=2, transaction_timeout_cycles=8,
                 deadline_cycles=120):
        self.ulpi = ULPIInterface()
        self.dut = ULPISafePHY(
            self.ulpi,
            startup_cycles=startup_cycles,
            transaction_timeout_cycles=transaction_timeout_cycles,
            deadline_cycles=deadline_cycles,
        )

    def elaborate(self, platform):
        m = Module()
        m.domains.usb = ClockDomain("usb")
        m.submodules.safe_phy = self.dut
        return m


class _FakeUSB3343:
    """Minimal ULPI responder that exercises LUNA's real register window."""

    def __init__(self, top, *, response=True, initial=None, read_override=None):
        self.top = top
        self.ulpi = top.ulpi
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
        }
        if initial:
            self.registers.update(initial)
        self.read_override = read_override
        self.read_counts = {}
        self.reads = []
        self.writes = []
        self.premature_drive = False

    async def run(self, ctx, *, max_cycles=200):
        ctx.set(self.ulpi.dir, 0)
        ctx.set(self.ulpi.nxt, 0)
        ctx.set(self.ulpi.data.i, 0)
        ctx.set(self.dut.start, 1)
        mode = "idle"
        address = 0
        command_kind = None
        wait_count = 0

        for _ in range(max_cycles):
            await ctx.tick("usb")
            ctx.set(self.dut.start, 0)
            if not ctx.get(self.dut.ready) and ctx.get(self.dut.drive_allowed):
                self.premature_drive = True
            if ctx.get(self.dut.ready) or ctx.get(self.dut.fault):
                return
            if not self.response:
                continue

            if mode == "idle":
                if (ctx.get(self.ulpi.dir) == 0
                        and ctx.get(self.ulpi.data.oe)
                        and (ctx.get(self.ulpi.data.o) & 0xC0) in (0x80, 0xC0)):
                    command = ctx.get(self.ulpi.data.o)
                    address = command & 0x3F
                    command_kind = "read" if (command & 0xC0) == 0xC0 else "write"
                    ctx.set(self.ulpi.nxt, 1)
                    mode = "accept_command"

            elif mode == "accept_command":
                if command_kind == "read":
                    value = self.registers.get(address, 0)
                    self.reads.append(address)
                    if self.read_override is not None:
                        count = self.read_counts.get(address, 0)
                        replacement = self.read_override(address, count, value)
                        if replacement is not None:
                            value = replacement
                    self.read_counts[address] = self.read_counts.get(address, 0) + 1
                    ctx.set(self.ulpi.nxt, 0)
                    ctx.set(self.ulpi.data.i, value)
                    ctx.set(self.ulpi.dir, 1)
                    wait_count = 0
                    mode = "read_data"
                else:
                    value = ctx.get(self.ulpi.data.o)
                    self.writes.append((address, value))
                    self.registers[address] = value
                    ctx.set(self.ulpi.nxt, 1)
                    wait_count = 0
                    mode = "write_data"

            elif mode == "read_data":
                wait_count += 1
                if wait_count >= 3:
                    ctx.set(self.ulpi.dir, 0)
                    ctx.set(self.ulpi.data.i, 0)
                    mode = "idle"

            elif mode == "write_data":
                # Keep NXT asserted through payload acceptance; the register
                # window emits STP and then reports done.
                ctx.set(self.ulpi.nxt, 0)
                mode = "write_done"

            elif mode == "write_done":
                mode = "idle"

            if ctx.get(self.dut.ready) or ctx.get(self.dut.fault):
                return

        raise AssertionError("initializer neither completed nor faulted within simulation bound")


class ULPISafePHYTests(unittest.TestCase):
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
        self.assertEqual(observed["writes"], [(0x04, 0x49), (0x0A, 0x00), (0x32, 0x00)])
        self.assertEqual(observed["reads"], [0x00, 0x01, 0x02, 0x03, 0x04, 0x0A, 0x32])
        self.assertFalse(observed["premature_drive"])
        self.assertEqual(observed["line_value"], 2)  # D- high, D+ low (K)
        self.assertEqual(observed["line_valid"], 1)
        self.assertEqual(observed["line_update"], 1)
        self.assertEqual(observed["line_update_ended"], 0)
        self.assertEqual(observed["drive_after_rxcmd"], 1)

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

if __name__ == "__main__":
    unittest.main()
