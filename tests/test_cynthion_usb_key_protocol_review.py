"""Independent focused regressions for the Cynthion USB_KEY protocol core.

These are RTL simulations only. RXCMD updates below model event-on-change
line-state observations; they are not evidence of USB3343 continuous sampling
or of the FM-1 ROM's electrical behavior.
"""

import pytest

pytest.importorskip("amaranth")
from amaranth.sim import Simulator

from tools.cynthion_usb_key.gateware import CynthionUsbKey


def _permit(dut, ctx):
    ctx.set(dut.phy_isolated, 1)
    ctx.set(dut.bank6_3v3_confirmed, 1)
    ctx.set(dut.ack_sense_valid, 1)


async def _reach_key_with_echo(dut, ctx):
    """Run four-state loopback using only line-change RXCMD updates."""
    observed_last = None
    for _ in range(500):
        if ctx.get(dut.state) == dut.KEY:
            return observed_last
        if ctx.get(dut.state) == dut.SELFTEST:
            observed = ctx.get(dut.dp_o) | (ctx.get(dut.dm_o) << 1)
            changed = observed != observed_last
            ctx.set(dut.line_state_value, observed)
            ctx.set(dut.line_state_valid, 1)
            ctx.set(dut.line_state_update, int(changed))
            if changed:
                observed_last = observed
        else:
            ctx.set(dut.line_state_update, 0)
        await ctx.tick(domain="usb")
    assert ctx.get(dut.state) == dut.KEY
    return observed_last


def test_absent_target_echo_never_acknowledges_and_hits_packet_limit():
    dut = CynthionUsbKey(clock_hz=1_000_000, packet_limit=2,
                         selftest_state_us=3, auto_selftest=True)
    sim = Simulator(dut)
    sim.add_clock(1e-6, domain="usb")
    visited = set()

    async def bench(ctx):
        _permit(dut, ctx)
        line_state = await _reach_key_with_echo(dut, ctx)
        for _ in range(2_000):
            state = ctx.get(dut.state)
            visited.add(state)
            driven = ctx.get(dut.dp_oe) or ctx.get(dut.dm_oe)
            # Faithful absent-target echo: active pads reflect FPGA outputs;
            # released pads resolve SE0 through the target-side pulldowns.
            observed = ((ctx.get(dut.dp_o) | (ctx.get(dut.dm_o) << 1))
                        if driven else 0)
            changed = observed != line_state
            ctx.set(dut.line_state_value, observed)
            ctx.set(dut.line_state_valid, 1)
            ctx.set(dut.line_state_update, int(changed))
            if changed:
                line_state = observed
            await ctx.tick(domain="usb")
            if ctx.get(dut.state) == dut.FAULT:
                break

        assert dut.KEY in visited
        assert dut.GAP in visited
        assert dut.WAIT_DP not in visited
        assert ctx.get(dut.state) == dut.FAULT
        assert (ctx.get(dut.dp_oe), ctx.get(dut.dm_oe)) == (0, 0)

    sim.add_testbench(bench)
    sim.run()


async def _reach_wait_dp(dut, ctx):
    """Echo self-test, then model a sustained clamp as one SE0 event."""
    line_state = await _reach_key_with_echo(dut, ctx)
    clamp_started = False
    for _ in range(1_000):
        if ctx.get(dut.state) == dut.WAIT_DP:
            return line_state
        if (not clamp_started and ctx.get(dut.state) == dut.KEY
                and ctx.get(dut.dp_o) == 1 and ctx.get(dut.dm_o) == 0):
            # This is a high-phase J bit. Let the event make receiver_live,
            # then report the candidate clamp once; subsequent SE0 is held
            # without synthetic periodic RXCMD refreshes.
            ctx.set(dut.line_state_value, 1)
            ctx.set(dut.line_state_valid, 1)
            ctx.set(dut.line_state_update, int(line_state != 1))
            if line_state != 1:
                line_state = 1
            await ctx.tick(domain="usb")
            ctx.set(dut.line_state_value, 0)
            ctx.set(dut.line_state_update, 1)
            line_state = 0
            clamp_started = True
            await ctx.tick(domain="usb")
            continue
        ctx.set(dut.line_state_value, line_state)
        ctx.set(dut.line_state_valid, 1)
        ctx.set(dut.line_state_update, 0)
        await ctx.tick(domain="usb")
    assert ctx.get(dut.state) == dut.WAIT_DP
    return line_state


def test_sustained_candidate_se0_reaches_wait_for_dp_pullup():
    dut = CynthionUsbKey(clock_hz=1_000_000, selftest_state_us=3,
                         ack_duration_us=20, auto_selftest=True)
    sim = Simulator(dut)
    sim.add_clock(1e-6, domain="usb")

    async def bench(ctx):
        _permit(dut, ctx)
        await _reach_wait_dp(dut, ctx)
        assert ctx.get(dut.state) == dut.WAIT_DP
        assert ctx.get(dut.done) == 0
        assert ctx.get(dut.fault) == 0

    sim.add_testbench(bench)
    sim.run()


async def _reach_sof(dut, ctx):
    line_state = await _reach_wait_dp(dut, ctx)
    # Model ROM's D+ pull-up (J) as a single event-on-change RXCMD update.
    ctx.set(dut.line_state_value, 1)
    ctx.set(dut.line_state_valid, 1)
    ctx.set(dut.line_state_update, int(line_state != 1))
    await ctx.tick(domain="usb")
    assert ctx.get(dut.state) == dut.SOF


def test_own_sof_low_pulses_do_not_complete_calibration():
    dut = CynthionUsbKey(clock_hz=1_000_000, selftest_state_us=3,
                         ack_duration_us=20, auto_selftest=True,
                         sof_done_low_ms=3, sof_timeout_ms=8)
    sim = Simulator(dut)
    sim.add_clock(1e-6, domain="usb")

    async def bench(ctx):
        _permit(dut, ctx)
        await _reach_sof(dut, ctx)
        observed_last = 1
        done_seen = False
        # The target retains its D+ pull-up while FPGA D+ is released. During
        # each 4-us low pulse the host sees SE0; at release it returns to J.
        for _ in range(8_500):
            dp_low = bool(ctx.get(dut.dp_oe) and ctx.get(dut.dp_o) == 0)
            observed = 0 if dp_low else 1
            changed = observed != observed_last
            ctx.set(dut.line_state_value, observed)
            ctx.set(dut.line_state_valid, 1)
            ctx.set(dut.line_state_update, int(changed))
            observed_last = observed
            await ctx.tick(domain="usb")
            if ctx.get(dut.state) == dut.DONE:
                done_seen = True
                break
            if ctx.get(dut.state) == dut.FAULT:
                break

        assert not done_seen
        assert ctx.get(dut.state) == dut.FAULT  # bounded SOF timeout
        assert ctx.get(dut.done) == 0
        assert (ctx.get(dut.dp_oe), ctx.get(dut.dm_oe)) == (0, 0)

    sim.add_testbench(bench)
    sim.run()


def test_isolation_loss_masks_pad_outputs_before_next_clock():
    dut = CynthionUsbKey(clock_hz=1_000_000, selftest_state_us=3,
                         ack_duration_us=20, auto_selftest=True,
                         sof_done_low_ms=3, sof_timeout_ms=8)
    sim = Simulator(dut)
    sim.add_clock(1e-6, domain="usb")

    async def bench(ctx):
        _permit(dut, ctx)
        await _reach_sof(dut, ctx)
        assert ctx.get(dut.dp_oe) == 1
        ctx.set(dut.phy_isolated, 0)
        # Combinational interlock: no synchronous state transition is needed
        # before the pad output enables drop.
        assert (ctx.get(dut.dp_oe), ctx.get(dut.dm_oe)) == (0, 0)
        await ctx.tick(domain="usb")
        assert ctx.get(dut.state) == dut.FAULT

    sim.add_testbench(bench)
    sim.run()
