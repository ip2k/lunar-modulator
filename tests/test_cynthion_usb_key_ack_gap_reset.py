"""ACK counter packet-boundary regressions for the Cynthion USB_KEY core.

These RTL-only simulations model RXCMD line-state updates as events. They do
not claim continuous PHY sampling or validate FM-1 ROM electrical behavior.
"""

import pytest

pytest.importorskip("amaranth")
from amaranth.sim import Simulator

from tools.cynthion_usb_key.gateware import CynthionUsbKey


def _permit(dut, ctx):
    ctx.set(dut.phy_isolated, 1)
    ctx.set(dut.bank6_3v3_confirmed, 1)
    ctx.set(dut.ack_sense_valid, 1)


async def _reach_key(dut, ctx):
    """Complete self-test with one change event per required line state."""
    for _ in range(20):
        if ctx.get(dut.state) == dut.SELFTEST:
            break
        await ctx.tick(domain="usb")
    assert ctx.get(dut.state) == dut.SELFTEST

    sequence = (2, 1, 0, 3)
    for index, expected in enumerate(sequence):
        ctx.set(dut.line_state_valid, 1)
        ctx.set(dut.line_state_value, expected)
        ctx.set(dut.line_state_update, 1)
        await ctx.tick(domain="usb")
        ctx.set(dut.line_state_update, 0)
        for _ in range(8):
            if index < len(sequence) - 1 and (
                ctx.get(dut.dp_o), ctx.get(dut.dm_o)
            ) == (sequence[index + 1] & 1, sequence[index + 1] >> 1):
                break
            await ctx.tick(domain="usb")
    assert ctx.get(dut.state) == dut.KEY


async def _establish_receiver_witness(dut, ctx):
    """Supply a fresh matching J event during the first key's high phase."""
    for _ in range(100):
        if (ctx.get(dut.debug_key_bit) == 0
                and ctx.get(dut.debug_key_phase) >= 8
                and ctx.get(dut.dp_o) == 1 and ctx.get(dut.dm_o) == 0):
            break
        await ctx.tick(domain="usb")
    else:
        assert False, "first key bit did not reach high-phase J"

    ctx.set(dut.line_state_value, 1)
    ctx.set(dut.line_state_valid, 1)
    ctx.set(dut.line_state_update, 1)
    await ctx.tick(domain="usb")
    ctx.set(dut.line_state_update, 0)
    assert ctx.get(dut.debug_receiver_live) == 1


async def _candidate_for_last_99us(dut, ctx):
    """Hold one event-on-change SE0 event for the packet's final 99 us."""
    await _establish_receiver_witness(dut, ctx)
    for _ in range(400):
        if (ctx.get(dut.debug_key_bit) == 11
                and ctx.get(dut.debug_key_phase) == 1):
            break
        await ctx.tick(domain="usb")
    else:
        assert False, "key packet did not reach the selected boundary point"

    ctx.set(dut.line_state_value, 0)
    ctx.set(dut.line_state_valid, 1)
    ctx.set(dut.line_state_update, 1)
    await ctx.tick(domain="usb")
    ctx.set(dut.line_state_update, 0)
    assert ctx.get(dut.debug_ack_ticks) > 0

    for _ in range(120):
        if ctx.get(dut.state) == dut.GAP:
            break
        await ctx.tick(domain="usb")
    assert ctx.get(dut.state) == dut.GAP
    assert ctx.get(dut.debug_receiver_live) == 1
    return ctx.get(dut.debug_ack_ticks)


def _dut(**kwargs):
    return CynthionUsbKey(clock_hz=1_000_000, selftest_state_us=3,
                          ack_duration_us=100, auto_selftest=True, **kwargs)


def test_ack_ticks_reset_at_key_to_gap_boundary():
    dut = _dut(packet_limit=3)
    sim = Simulator(dut)
    sim.add_clock(1e-6, domain="usb")

    async def bench(ctx):
        _permit(dut, ctx)
        await _reach_key(dut, ctx)
        before_gap = await _candidate_for_last_99us(dut, ctx)
        assert before_gap == 0  # reset is applied on the boundary edge
        assert ctx.get(dut.state) == dut.GAP

        # The single SE0 RXCMD event remains cached; no periodic refreshes are
        # synthesized during the released gap or following KEY interval.
        for _ in range(dut.gap_cycles - 1):
            await ctx.tick(domain="usb")
            assert ctx.get(dut.state) == dut.GAP
            assert ctx.get(dut.debug_ack_ticks) == 0
        await ctx.tick(domain="usb")
        assert ctx.get(dut.state) == dut.KEY
        assert ctx.get(dut.debug_ack_ticks) == 0
        await ctx.tick(domain="usb")
        assert ctx.get(dut.state) == dut.KEY
        assert ctx.get(dut.debug_ack_ticks) == 1

    sim.add_testbench(bench)
    sim.run()


def test_held_se0_can_confirm_after_fresh_key_interval_without_new_event():
    dut = _dut(packet_limit=3)
    sim = Simulator(dut)
    sim.add_clock(1e-6, domain="usb")

    async def bench(ctx):
        _permit(dut, ctx)
        await _reach_key(dut, ctx)
        await _candidate_for_last_99us(dut, ctx)
        assert ctx.get(dut.debug_ack_ticks) == 0

        for _ in range(dut.gap_cycles):
            await ctx.tick(domain="usb")
            assert ctx.get(dut.debug_ack_ticks) == 0
        assert ctx.get(dut.state) == dut.KEY
        assert ctx.get(dut.debug_receiver_live) == 1

        for elapsed in range(1, dut.ack_duration_us):
            await ctx.tick(domain="usb")
            assert ctx.get(dut.state) == dut.KEY
            assert ctx.get(dut.debug_ack_ticks) == elapsed
        await ctx.tick(domain="usb")
        assert ctx.get(dut.state) == dut.WAIT_DP
        assert ctx.get(dut.debug_receiver_live) == 1
        assert ctx.get(dut.debug_ack_confirm) == 1

    sim.add_testbench(bench)
    sim.run()


def test_cached_se0_without_high_phase_receiver_witness_never_confirms():
    dut = _dut(packet_limit=2)
    sim = Simulator(dut)
    sim.add_clock(1e-6, domain="usb")

    async def bench(ctx):
        _permit(dut, ctx)
        await _reach_key(dut, ctx)
        # SE0 alone is insufficient: never deliver the required matching
        # high-phase J/SE1 witness before or after this event.
        ctx.set(dut.line_state_value, 0)
        ctx.set(dut.line_state_valid, 1)
        ctx.set(dut.line_state_update, 1)
        await ctx.tick(domain="usb")
        ctx.set(dut.line_state_update, 0)

        for _ in range(1_100):
            assert ctx.get(dut.state) != dut.WAIT_DP
            if ctx.get(dut.state) == dut.FAULT:
                break
            await ctx.tick(domain="usb")

        assert ctx.get(dut.state) == dut.FAULT
        assert ctx.get(dut.protocol_failure_reason) == dut.PROTOCOL_FAULT_PACKET_LIMIT
        assert ctx.get(dut.debug_receiver_live) == 0
        assert ctx.get(dut.debug_ack_ticks) == 0
        assert (ctx.get(dut.dp_oe), ctx.get(dut.dm_oe)) == (0, 0)

    sim.add_testbench(bench)
    sim.run()
