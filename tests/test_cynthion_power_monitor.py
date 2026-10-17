"""Offline tests for the diagnostic-only r1.4 PAC1954 image."""

import ast
import inspect
import textwrap
import unittest
from types import SimpleNamespace

import pytest

pytest.importorskip("amaranth")
pytest.importorskip("cynthion")
pytest.importorskip("luna")

from amaranth import Elaboratable, Module, Signal
from amaranth.sim import Simulator
from luna.gateware.interface.i2c import I2CInitiator, I2CRegisterInterface

from tools.cynthion_usb_key.power_monitor import (
    CynthionPowerMonitorTop,
    PAC1954Channel1,
    current_ua_from_raw,
    vbus_uv_from_raw,
)


class _FakePACBus(Elaboratable):
    def __init__(self, *, manufacturer=0x54, active_range=0,
                 hang_address=None, nack_address=None, nack_after=0):
        self.address = Signal(8)
        self.size = Signal(2)
        self.read_request = Signal()
        self.write_request = Signal()
        self.read_data = Signal(16)
        self.busy = Signal()
        self.done = Signal()
        self.manufacturer = manufacturer
        self.active_range = active_range
        self.hang_address = hang_address
        self.nack_address = nack_address
        self.nack_after = nack_after

    def elaborate(self, platform):
        m = Module()
        countdown = Signal(4)
        saved_address = Signal(8)
        stuck = Signal()
        nack_this = Signal()
        completed = Signal(8)
        m.d.sync += self.done.eq(0)
        with m.If((self.read_request | self.write_request) & ~self.busy):
            m.d.sync += [
                saved_address.eq(self.address),
                stuck.eq(self.address == (self.hang_address or 0)),
                nack_this.eq((self.address == (self.nack_address or -1))
                             & (completed >= self.nack_after)),
                countdown.eq(3),
                self.busy.eq(1),
            ]
        with m.Elif(self.busy & ~stuck):
            with m.If(countdown != 0):
                m.d.sync += countdown.eq(countdown - 1)
            with m.Else():
                m.d.sync += self.busy.eq(0)
                m.d.sync += completed.eq(completed + 1)
                with m.If(~nack_this):
                    m.d.sync += self.done.eq(1)
                    with m.Switch(saved_address):
                        with m.Case(0xFE):
                            m.d.sync += self.read_data.eq(self.manufacturer)
                        with m.Case(0x22):
                            m.d.sync += self.read_data.eq(self.active_range)
                        with m.Case(0x07):
                            m.d.sync += self.read_data.eq(0x8000)
                        with m.Case(0x0B):
                            m.d.sync += self.read_data.eq(0x4000)
                        with m.Default():
                            m.d.sync += self.read_data.eq(0)
        return m


class _PACBench(Elaboratable):
    def __init__(self, bus, *, timeout=12, powerup=2, refresh=2, interval=4):
        self.bus = bus
        self.dut = PAC1954Channel1(
            bus, read_timeout_cycles=timeout,
            powerup_settle_cycles=powerup,
            refresh_settle_cycles=refresh,
            sample_interval_cycles=interval)

    def elaborate(self, platform):
        m = Module()
        m.submodules.bus = self.bus
        m.submodules.dut = self.dut
        return m


class _TwoByteI2CSlave(Elaboratable):
    """Line-level data source for two consecutive LUNA I2C reads."""

    def __init__(self, pads):
        self.pads = pads
        self.byte_index = Signal()
        self.bit_index = Signal(range(9))

    def elaborate(self, platform):
        m = Module()
        scl_d = Signal(init=1)
        line = Signal()
        rising = Signal()
        m.d.comb += [
            line.eq(~(self.pads.sda.oe | self._slave_pulls_low())),
            self.pads.sda.i.eq(line),
            rising.eq(~scl_d & self.pads.scl.o),
        ]
        m.d.sync += scl_d.eq(self.pads.scl.o)
        with m.If(rising):
            with m.If(self.bit_index == 8):
                m.d.sync += [self.bit_index.eq(0), self.byte_index.eq(1)]
            with m.Else():
                m.d.sync += self.bit_index.eq(self.bit_index + 1)
        return m

    def _slave_pulls_low(self):
        # Pull low for zero bits in 0x12 then 0x34; release for the ninth
        # clock where the initiator sends its ACK/NACK.
        from amaranth import Mux
        read_byte = Mux(self.byte_index == 0, 0x12, 0x34)
        read_bit = read_byte.bit_select(self.bit_index[:3] ^ 7, 1)
        return (self.bit_index != 8) & ~read_bit


class _RegisterReadSlave(Elaboratable):
    """Minimal open-drain target for one register-addressed two-byte read."""

    def __init__(self, pads):
        self.pads = pads
        self.phase = Signal(3)  # SLA+W, register, SLA+R, data0, data1, done
        self.bit_index = Signal(range(9))
        self.rx_shift = Signal(8)
        self.address_write = Signal(8)
        self.register = Signal(8)
        self.address_read = Signal(8)
        self.address_ack_mask = Signal(3)
        self.first_data_ack = Signal()
        self.final_nack = Signal()
        self.start_count = Signal(2)
        self.stop_seen = Signal()
        self.sampled_read = Signal(16)
        self.read_sample_count = Signal(range(17))

    def elaborate(self, platform):
        m = Module()
        scl_d = Signal(init=1)
        sda_d = Signal(init=1)
        saw_rise = Signal()
        line = Signal()
        rising = Signal()
        falling = Signal()
        start = Signal()
        stop = Signal()
        m.d.comb += [
            line.eq(~(self.pads.sda.oe | self._target_pulls_low())),
            self.pads.sda.i.eq(line),
            rising.eq(~scl_d & self.pads.scl.o),
            falling.eq(scl_d & ~self.pads.scl.o),
            start.eq(self.pads.scl.o & sda_d & ~line),
            stop.eq(self.pads.scl.o & ~sda_d & line),
        ]
        m.d.sync += [scl_d.eq(self.pads.scl.o), sda_d.eq(line)]

        with m.If(start):
            # The START setup edge is not part of the following address byte.
            m.d.sync += [self.start_count.eq(self.start_count + 1), saw_rise.eq(0)]
            with m.If(self.phase == 0):
                m.d.sync += [self.phase.eq(1), self.bit_index.eq(0)]
            with m.Elif(self.phase == 2):
                m.d.sync += [self.phase.eq(3), self.bit_index.eq(0)]
        with m.If(stop):
            m.d.sync += self.stop_seen.eq(1)

        with m.If(~start):
            with m.If(rising):
                m.d.sync += saw_rise.eq(1)
                with m.If((self.phase >= 1) & (self.phase <= 3)
                          & (self.bit_index < 8)):
                    m.d.sync += self.rx_shift.eq((self.rx_shift << 1) | line)
                    with m.If(self.bit_index == 7):
                        with m.Switch(self.phase):
                            with m.Case(1):
                                m.d.sync += self.address_write.eq((self.rx_shift << 1) | line)
                            with m.Case(2):
                                m.d.sync += self.register.eq((self.rx_shift << 1) | line)
                            with m.Case(3):
                                m.d.sync += self.address_read.eq((self.rx_shift << 1) | line)
                with m.If((self.phase >= 1) & (self.phase <= 3)
                          & (self.bit_index == 8)):
                    with m.Switch(self.phase):
                        with m.Case(1):
                            m.d.sync += self.address_ack_mask[0].eq(~line)
                        with m.Case(2):
                            m.d.sync += self.address_ack_mask[1].eq(~line)
                        with m.Case(3):
                            m.d.sync += self.address_ack_mask[2].eq(~line)
                with m.If((self.phase == 5) & (self.bit_index == 8)):
                    m.d.sync += self.final_nack.eq(line)
                with m.If((self.phase == 4) & (self.bit_index == 8)):
                    m.d.sync += self.first_data_ack.eq(~line)
                with m.If((self.phase == 4) | (self.phase == 5)):
                    with m.If(self.bit_index < 8):
                        m.d.sync += [
                            self.sampled_read.eq((self.sampled_read << 1) | line),
                            self.read_sample_count.eq(self.read_sample_count + 1),
                        ]

            with m.If(falling & saw_rise):
                m.d.sync += saw_rise.eq(0)
                with m.If(self.bit_index == 8):
                    m.d.sync += [self.bit_index.eq(0), self.rx_shift.eq(0)]
                    with m.Switch(self.phase):
                        with m.Case(1):
                            m.d.sync += self.phase.eq(2)
                        with m.Case(3):
                            m.d.sync += self.phase.eq(4)
                        with m.Case(4):
                            m.d.sync += self.phase.eq(5)
                        with m.Case(5):
                            m.d.sync += self.phase.eq(6)
                with m.Else():
                    m.d.sync += self.bit_index.eq(self.bit_index + 1)
        return m

    def _target_pulls_low(self):
        from amaranth import Mux
        ack_phase = (self.phase >= 1) & (self.phase <= 3)
        ack_slot = self.bit_index == 8
        read_byte = Mux(self.phase == 4, 0x12, 0x34)
        read_bit = read_byte.bit_select(self.bit_index[:3] ^ 7, 1)
        return ack_phase & ack_slot | ((self.phase == 4) | (self.phase == 5)) \
            & ~ack_slot & ~read_bit


class PowerMonitorTests(unittest.TestCase):
    def test_scale_conversion_endpoints(self):
        self.assertEqual(vbus_uv_from_raw(0), 0)
        self.assertEqual(vbus_uv_from_raw(0xFFFF), 31_999_512)
        self.assertEqual(current_ua_from_raw(0), 0)
        self.assertEqual(current_ua_from_raw(0xFFFF), 4_999_924)
        with self.assertRaises(ValueError):
            current_ua_from_raw(12, 0)

    def test_wrong_manufacturer_fails_before_measurement(self):
        bus = _FakePACBus(manufacturer=0x53)
        top = _PACBench(bus)
        sim = Simulator(top)
        sim.add_clock(1e-6)
        async def bench(ctx):
            for _ in range(40):
                await ctx.tick()
                if ctx.get(top.dut.fault):
                    break
            self.assertEqual(ctx.get(top.dut.error_code), 1)
            self.assertEqual(ctx.get(top.dut.ready), 0)
            self.assertEqual(ctx.get(top.dut.sample_sequence), 0)
        sim.add_testbench(bench)
        sim.run()

    def test_i2c_timeout_is_bounded_and_fail_closed(self):
        bus = _FakePACBus(hang_address=0xFE)
        top = _PACBench(bus, timeout=8)
        sim = Simulator(top)
        sim.add_clock(1e-6)
        async def bench(ctx):
            for _ in range(40):
                await ctx.tick()
                if ctx.get(top.dut.fault):
                    break
            self.assertEqual(ctx.get(top.dut.error_code), 3)
            self.assertEqual(ctx.get(top.dut.ready), 0)
            self.assertEqual(ctx.get(top.dut.sample_sequence), 0)
        sim.add_testbench(bench)
        sim.run()

    def test_nondefault_range_fails_closed(self):
        bus = _FakePACBus(active_range=0x4000)
        top = _PACBench(bus)
        sim = Simulator(top)
        sim.add_clock(1e-6)
        async def bench(ctx):
            for _ in range(80):
                await ctx.tick()
                if ctx.get(top.dut.fault):
                    break
            self.assertEqual(ctx.get(top.dut.error_code), 4)
            self.assertEqual(ctx.get(top.dut.ready), 0)
            self.assertEqual(ctx.get(top.dut.active_range), 0x4000)
        sim.add_testbench(bench)
        sim.run()

    def test_monitor_top_never_requests_target_data_pads_or_key_core(self):
        source = inspect.getsource(CynthionPowerMonitorTop.elaborate)
        tree = ast.parse(textwrap.dedent(source))
        requested = [node.args[0].value for node in ast.walk(tree)
                     if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Attribute)
                     and node.func.attr == "request"
                     and node.args and isinstance(node.args[0], ast.Constant)]
        self.assertNotIn("target_usb_dp", requested)
        self.assertNotIn("target_usb_dm", requested)
        self.assertNotIn("button_user", requested)
        self.assertNotIn("CynthionUsbKey", source)
        for name, value in (("control_vbus.o.eq(1)", 1),
                            ("target_c_vbus.o.eq(0)", 0),
                            ("aux_vbus.o.eq(0)", 0),
                            ("target_discharge.o.eq(0)", 0)):
            self.assertIn(name, source)
        self.assertIn("period_cyc=600", source)

    def test_successful_reads_publish_raw_values(self):
        bus = _FakePACBus()
        top = _PACBench(bus)
        sim = Simulator(top)
        sim.add_clock(1e-6)
        async def bench(ctx):
            for _ in range(100):
                await ctx.tick()
                if ctx.get(top.dut.ready):
                    break
            self.assertEqual(ctx.get(top.dut.ready), 1)
            self.assertEqual(ctx.get(top.dut.vbus_raw), 0x8000)
            self.assertEqual(ctx.get(top.dut.vsense_raw), 0x4000)
            self.assertEqual(vbus_uv_from_raw(ctx.get(top.dut.vbus_raw)), 16_000_000)
            self.assertEqual(current_ua_from_raw(ctx.get(top.dut.vsense_raw)), 1_250_000)
            self.assertEqual(ctx.get(top.dut.sample_sequence), 1)
            self.assertEqual(ctx.get(top.dut.refresh_count), 1)
        sim.add_testbench(bench)
        sim.run()

    def test_second_successful_sample_advances_sequence_and_resets_age(self):
        bus = _FakePACBus()
        top = _PACBench(bus, interval=12)
        sim = Simulator(top)
        sim.add_clock(1e-6)
        async def bench(ctx):
            for _ in range(100):
                await ctx.tick()
                if ctx.get(top.dut.sample_sequence) == 2:
                    break
            self.assertEqual(ctx.get(top.dut.fault), 0)
            self.assertEqual(ctx.get(top.dut.sample_sequence), 2)
            self.assertLess(ctx.get(top.dut.sample_age_cycles), 5)
            self.assertEqual(ctx.get(top.dut.vbus_raw), 0x8000)
            self.assertEqual(ctx.get(top.dut.vsense_raw), 0x4000)
        sim.add_testbench(bench)
        sim.run()

    def test_failed_refresh_does_not_claim_stale_sample_as_fresh(self):
        bus = _FakePACBus(nack_address=0x07, nack_after=5)
        top = _PACBench(bus, interval=8)
        sim = Simulator(top)
        sim.add_clock(1e-6)
        async def bench(ctx):
            for _ in range(120):
                await ctx.tick()
                if ctx.get(top.dut.fault):
                    break
            await ctx.tick()  # FAILED clears ready on the following clock.
            self.assertEqual(ctx.get(top.dut.error_code), 9)
            self.assertEqual(ctx.get(top.dut.ready), 0)
            self.assertEqual(ctx.get(top.dut.sample_sequence), 1)
            self.assertGreater(ctx.get(top.dut.sample_age_cycles), 0)
            self.assertEqual(ctx.get(top.dut.vbus_raw), 0x8000)
            self.assertEqual(ctx.get(top.dut.vsense_raw), 0x4000)
        sim.add_testbench(bench)
        sim.run()

    def test_real_luna_size_zero_transfer_is_send_byte(self):
        pads = SimpleNamespace(
            scl=SimpleNamespace(o=Signal()),
            sda=SimpleNamespace(i=Signal(), o=Signal(), oe=Signal()),
        )
        i2c = I2CRegisterInterface(pads, period_cyc=8,
                                   address=PAC1954Channel1.I2C_ADDRESS,
                                   data_bytes=2)
        m = Module()
        m.submodules.i2c = i2c
        sim = Simulator(m)
        sim.add_clock(1e-6)

        async def bench(ctx):
            ctx.set(pads.sda.i, 1)
            ctx.set(i2c.address, PAC1954Channel1.REG_REFRESH_V)
            ctx.set(i2c.size, 0)
            ctx.set(i2c.write_request, 1)
            await ctx.tick()
            ctx.set(i2c.write_request, 0)
            slave_low = False
            rising_count = 0
            previous_scl = ctx.get(pads.scl.o)
            received = []
            for _ in range(5000):
                # Wired-AND line: master and target may only pull low.
                ctx.set(pads.sda.i, 0 if slave_low or ctx.get(pads.sda.oe) else 1)
                await ctx.tick()
                scl = ctx.get(pads.scl.o)
                if previous_scl == 0 and scl == 1:
                    if rising_count % 9 != 8:
                        received.append(0 if ctx.get(pads.sda.oe) else 1)
                    rising_count += 1
                elif previous_scl == 1 and scl == 0:
                    if rising_count % 9 == 8:
                        slave_low = True  # ACK after each eight data bits.
                    elif rising_count and rising_count % 9 == 0:
                        slave_low = False
                previous_scl = scl
                if ctx.get(i2c.done):
                    break
            self.assertEqual(ctx.get(i2c.done), 1)
            self.assertEqual(rising_count, 18)
            self.assertEqual(received, [int(bit) for byte in (0x20, 0x1F)
                                        for bit in f"{byte:08b}"])
            self.assertEqual(ctx.get(i2c.size), 0)

        sim.add_testbench(bench)
        sim.run()

    def test_real_luna_initiator_receives_two_msb_first_bytes(self):
        pads = SimpleNamespace(
            scl=SimpleNamespace(o=Signal(init=1)),
            sda=SimpleNamespace(i=Signal(init=1), o=Signal(), oe=Signal()),
        )
        i2c = I2CInitiator(pads, period_cyc=16, clk_stretch=False)
        slave = _TwoByteI2CSlave(pads)
        m = Module()
        m.submodules.i2c = i2c
        m.submodules.slave = slave
        sim = Simulator(m)
        sim.add_clock(1e-6)

        async def bench(ctx):
            ctx.set(i2c.ack_i, 1)
            ctx.set(i2c.read, 1)
            await ctx.tick()
            ctx.set(i2c.read, 0)
            for _ in range(2000):
                await ctx.tick()
                if not ctx.get(i2c.busy):
                    break
            self.assertEqual(ctx.get(i2c.data_o), 0x12)
            self.assertEqual(ctx.get(i2c.busy), 0)
            ctx.set(i2c.ack_i, 0)
            ctx.set(i2c.read, 1)
            await ctx.tick()
            ctx.set(i2c.read, 0)
            for _ in range(2000):
                await ctx.tick()
                if not ctx.get(i2c.busy):
                    break
            self.assertEqual(ctx.get(i2c.data_o), 0x34)
            self.assertEqual(ctx.get(slave.byte_index), 1)

        sim.add_testbench(bench)
        sim.run()

    def test_real_luna_register_wrapper_repeated_start_read(self):
        pads = SimpleNamespace(
            scl=SimpleNamespace(o=Signal(init=1)),
            sda=SimpleNamespace(i=Signal(init=1), o=Signal(), oe=Signal()),
        )
        i2c = I2CRegisterInterface(
            pads, period_cyc=64, address=PAC1954Channel1.I2C_ADDRESS,
            data_bytes=2)
        slave = _RegisterReadSlave(pads)
        m = Module()
        m.submodules.i2c = i2c
        m.submodules.slave = slave
        sim = Simulator(m)
        sim.add_clock(1e-6)

        async def bench(ctx):
            ctx.set(i2c.address, 0x07)
            ctx.set(i2c.size, 2)
            ctx.set(i2c.read_request, 1)
            await ctx.tick()
            ctx.set(i2c.read_request, 0)
            done_seen = False
            for _ in range(20_000):
                await ctx.tick()
                done_seen |= bool(ctx.get(i2c.done))
                if done_seen and ctx.get(slave.stop_seen):
                    break

            self.assertTrue(done_seen)
            self.assertEqual(ctx.get(i2c.read_data), 0x1234)
            self.assertEqual(ctx.get(slave.address_write), 0x20)
            self.assertEqual(ctx.get(slave.register), 0x07)
            self.assertEqual(ctx.get(slave.address_read), 0x21)
            self.assertEqual(ctx.get(slave.start_count), 2)  # START + repeated START.
            self.assertEqual(ctx.get(slave.address_ack_mask), 0b111)
            self.assertEqual(ctx.get(slave.first_data_ack), 1)
            self.assertEqual(ctx.get(slave.final_nack), 1)
            self.assertEqual(ctx.get(slave.stop_seen), 1)
            self.assertEqual(ctx.get(slave.read_sample_count), 16)
            self.assertEqual(ctx.get(slave.sampled_read), 0x1234)

        sim.add_testbench(bench)
        sim.run()

    def test_luna_register_wrapper_combines_first_byte_as_most_significant(self):
        source = inspect.getsource(I2CRegisterInterface.elaborate)
        self.assertIn("current_read.eq((current_read << 8) | i2c.data_o)", source)
        self.assertIn("self.read_data.eq((current_read << 8) | i2c.data_o)", source)


if __name__ == "__main__":
    unittest.main()
