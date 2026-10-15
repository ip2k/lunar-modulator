from amaranth.sim import Simulator

from tools.cynthion_usb_key.gateware import CynthionUsbKey


def test_disconnected_selftest_terminates_without_entering_key_state():
    dut = CynthionUsbKey(clock_hz=1_000_000, selftest_state_us=3,
                         auto_selftest=True, selftest_only=True)
    sim = Simulator(dut)
    sim.add_clock(1e-6, domain="usb")

    async def bench(ctx):
        ctx.set(dut.phy_isolated, 1)
        ctx.set(dut.bank6_3v3_confirmed, 1)
        ctx.set(dut.ack_sense_valid, 1)
        for _ in range(10):
            if ctx.get(dut.state) == dut.SELFTEST:
                break
            await ctx.tick(domain="usb")
        assert ctx.get(dut.state) == dut.SELFTEST

        sequence = (2, 1, 0, 3)
        for index, expected_state in enumerate(sequence):
            assert ctx.get(dut.state) == dut.SELFTEST
            assert ctx.get(dut.dp_o) == (expected_state & 1)
            assert ctx.get(dut.dm_o) == ((expected_state >> 1) & 1)
            assert ctx.get(dut.dp_oe) == 1
            assert ctx.get(dut.dm_oe) == 1
            ctx.set(dut.line_state_value, expected_state)
            ctx.set(dut.line_state_valid, 1)
            ctx.set(dut.line_state_update, 1)
            await ctx.tick(domain="usb")
            ctx.set(dut.line_state_update, 0)
            # Wait for the dwell interval to advance to the next line state.
            for _ in range(5):
                await ctx.tick(domain="usb")
                if index == len(sequence) - 1:
                    if ctx.get(dut.state) == dut.DONE:
                        break
                else:
                    next_state = sequence[index + 1]
                    if (ctx.get(dut.dp_o), ctx.get(dut.dm_o)) == (
                        next_state & 1, (next_state >> 1) & 1
                    ):
                        break

        assert ctx.get(dut.state) == dut.DONE
        assert ctx.get(dut.done) == 1
        assert ctx.get(dut.fault) == 0
        assert ctx.get(dut.dp_oe) == 0
        assert ctx.get(dut.dm_oe) == 0
        assert ctx.get(dut.selftest_mask) == 0b1111
        assert ctx.get(dut.leds) == 0b100000

    sim.add_testbench(bench)
    sim.run()


def test_operation_image_stays_disarmed_without_debounced_button():
    dut = CynthionUsbKey(clock_hz=1_000_000, debounce_us=4)
    sim = Simulator(dut)
    sim.add_clock(1e-6, domain="usb")

    async def bench(ctx):
        ctx.set(dut.phy_isolated, 1)
        ctx.set(dut.bank6_3v3_confirmed, 1)
        ctx.set(dut.ack_sense_valid, 1)
        for _ in range(100):
            await ctx.tick(domain="usb")
            assert ctx.get(dut.state) == dut.SAFE
            assert ctx.get(dut.dp_oe) == 0
            assert ctx.get(dut.dm_oe) == 0

    sim.add_testbench(bench)
    sim.run()


def test_missing_interlock_keeps_all_key_outputs_high_z():
    dut = CynthionUsbKey(clock_hz=1_000_000, auto_selftest=True,
                         selftest_only=True)
    sim = Simulator(dut)
    sim.add_clock(1e-6, domain="usb")

    async def bench(ctx):
        ctx.set(dut.bank6_3v3_confirmed, 1)
        ctx.set(dut.ack_sense_valid, 1)
        for _ in range(20):
            await ctx.tick(domain="usb")
        assert ctx.get(dut.state) == dut.SAFE
        assert ctx.get(dut.dp_oe) == 0
        assert ctx.get(dut.dm_oe) == 0

    sim.add_testbench(bench)
    sim.run()
