"""Offline finite Pico-style profile checks; no hardware access."""
import pytest

pytest.importorskip('amaranth')
pytest.importorskip('cynthion')
from amaranth.sim import Simulator
from tools.cynthion_usb_key.gateware import CynthionUsbKey
from tools.cynthion_usb_key.top import CynthionUsbKeyTop


async def _ticks(ctx, count):
    for _ in range(count):
        await ctx.tick(domain='usb')


async def _start(ctx, dut):
    for gate in (dut.phy_isolated, dut.bank6_3v3_confirmed, dut.ack_sense_valid):
        ctx.set(gate, 1)
    await _ticks(ctx, 8)
    assert ctx.get(dut.state) == dut.SAFE
    ctx.set(dut.user_button, 1)
    for _ in range(20):
        if ctx.get(dut.state) == dut.SELFTEST:
            break
        await _ticks(ctx, 1)
    assert ctx.get(dut.state) == dut.SELFTEST
    for value in (2, 1, 0, 3):
        ctx.set(dut.line_state_update, 1)
        ctx.set(dut.line_state_valid, 1)
        ctx.set(dut.line_state_value, value)
        await _ticks(ctx, 1)
        ctx.set(dut.line_state_update, 0)
        for _ in range(6):
            if ctx.get(dut.state) != dut.SELFTEST or (
                ctx.get(dut.dp_o), ctx.get(dut.dm_o)) != (value & 1, value >> 1):
                break
            await _ticks(ctx, 1)
    assert ctx.get(dut.state) == dut.READY
    await _ticks(ctx, 10)
    assert ctx.get(dut.state) == dut.READY
    assert not ctx.get(dut.dp_oe) and not ctx.get(dut.dm_oe)
    ctx.set(dut.user_button, 0)
    await _ticks(ctx, 10)
    ctx.set(dut.user_button, 1)
    for _ in range(20):
        await _ticks(ctx, 1)
        if ctx.get(dut.state) == dut.KEY:
            return
    pytest.fail('fresh second press did not start KEY')


def _dut(**kwargs):
    parameters = dict(clock_hz=1_000_000, debounce_us=2,
                      selftest_state_us=4, pico_repeat=True, repeat_cycles=2,
                      repeat_words=3, repeat_sof_us=20, sof_period_us=4, sof_pulse_us=2)
    parameters.update(kwargs)
    return CynthionUsbKey(**parameters)


@pytest.mark.parametrize('rx_mode', ['cached-se0', 'ack-candidate', 'invalid'])
@pytest.mark.parametrize('cycles', [1, 16])
def test_finite_repeat_complete_waveforms_and_duration_independent_of_rxcmd(rx_mode, cycles):
    dut = _dut(ack_duration_us=1, sof_done_low_ms=1, repeat_sof_us=2000, repeat_cycles=cycles)
    sim = Simulator(dut)
    sim.add_clock(1e-6, domain='usb')

    async def bench(ctx):
        await _start(ctx, dut)
        for cycle in range(cycles):
            for word in range(3):
                for bit in range(16):
                    data = (0x16EF >> (15 - bit)) & 1
                    for phase in range(20):
                        assert ctx.get(dut.state) == dut.KEY
                        assert ctx.get(dut.dp_oe) == ctx.get(dut.dm_oe) == 1
                        assert ctx.get(dut.dp_o) == int(phase >= 10)
                        assert ctx.get(dut.dm_o) == data
                        ctx.set(dut.line_state_update, int(rx_mode == 'ack-candidate'))
                        ctx.set(dut.line_state_valid, int(rx_mode != 'invalid'))
                        # A high phase first makes receiver-live, then cached
                        # SE0 exceeds ACK duration. It cannot alter fixed words.
                        ctx.set(dut.line_state_value,
                                (3 if data else 1) if rx_mode == 'ack-candidate'
                                and phase == 10 else 0)
                        await _ticks(ctx, 1)
                for gap in range(160):
                    assert ctx.get(dut.state) == dut.GAP
                    assert not ctx.get(dut.dp_oe) and not ctx.get(dut.dm_oe)
                    await _ticks(ctx, 1)
                assert ctx.get(dut.debug_packets) == word + 1
            for phase in range(2000):
                assert ctx.get(dut.state) == dut.SOF
                assert ctx.get(dut.dp_oe) == 1 and not ctx.get(dut.dm_oe)
                assert ctx.get(dut.dp_o) == int((phase % 4) >= 2)
                # Cached SE0, invalid reports and ACK candidates cannot stop PWM.
                ctx.set(dut.line_state_value, 0)
                await _ticks(ctx, 1)
            assert ctx.get(dut.debug_repeat_cycles) == cycle + 1
        assert ctx.get(dut.state) == dut.DONE
        assert ctx.get(dut.leds) == 0b100000
        assert ctx.get(dut.protocol_failure_reason) == 0
        assert not ctx.get(dut.dp_oe) and not ctx.get(dut.dm_oe)
        await _ticks(ctx, 10)  # Second press still held, terminal is absorbing.
        assert ctx.get(dut.state) == dut.DONE
        ctx.set(dut.user_button, 0)
        await _ticks(ctx, 10)
        ctx.set(dut.user_button, 1)
        await _ticks(ctx, 10)
        assert ctx.get(dut.state) == dut.DONE
        assert ctx.get(dut.debug_repeat_cycles) == cycles
        assert not ctx.get(dut.dp_oe) and not ctx.get(dut.dm_oe)

    sim.add_testbench(bench)
    sim.run()


@pytest.mark.parametrize('abort_state', ['KEY', 'GAP', 'SOF', 'SOF-HIGH'])
@pytest.mark.parametrize('gate', ['phy_isolated', 'bank6_3v3_confirmed',
                                  'ack_sense_valid', 'phy_fault'])
def test_repeat_interlock_masks_immediately_then_latches_fault(abort_state, gate):
    dut = _dut()
    sim = Simulator(dut)
    sim.add_clock(1e-6, domain='usb')

    async def bench(ctx):
        await _start(ctx, dut)
        target = getattr(dut, abort_state.split("-")[0])
        for _ in range(1500):
            if ctx.get(dut.state) == target:
                break
            await _ticks(ctx, 1)
        assert ctx.get(dut.state) == target
        if abort_state == "SOF-HIGH":
            await _ticks(ctx, 2)
            assert ctx.get(dut.dp_o) == 1
        ctx.set(getattr(dut, gate), int(gate == 'phy_fault'))
        assert not ctx.get(dut.dp_oe) and not ctx.get(dut.dm_oe)
        await _ticks(ctx, 1)
        assert ctx.get(dut.state) == dut.FAULT
        assert ctx.get(dut.protocol_failure_origin_state) == target
        assert ctx.get(dut.protocol_failure_reason) == dut.PROTOCOL_FAULT_INTERLOCK_LOST
        ctx.set(getattr(dut, gate), int(gate != 'phy_fault'))
        ctx.set(dut.user_button, 0)
        await _ticks(ctx, 10)
        ctx.set(dut.user_button, 1)
        await _ticks(ctx, 10)
        assert ctx.get(dut.state) == dut.FAULT
        assert not ctx.get(dut.dp_oe) and not ctx.get(dut.dm_oe)
        assert ctx.get(dut.debug_repeat_cycles) == 0

    sim.add_testbench(bench)
    sim.run()


@pytest.mark.parametrize('kwargs', [dict(repeat_cycles=0), dict(repeat_cycles=17),
    dict(repeat_cycles=True), dict(repeat_words=0), dict(repeat_words=65536),
    dict(repeat_sof_us=0), dict(repeat_sof_us=0x100000000),
    dict(repeat_sof_us=1), dict(sof_pulse_us=4), dict(auto_selftest=True),
    dict(selftest_only=True)])
def test_repeat_rejects_invalid_bounds_and_automatic_preflight(kwargs):
    with pytest.raises(ValueError):
        CynthionUsbKey(pico_repeat=True, **kwargs)


def test_production_profile_defaults_and_distinct_mode():
    dut = CynthionUsbKey(pico_repeat=True)
    assert (dut.repeat_cycles, dut.repeat_words, dut.repeat_sof_us) == (16, 3000, 2_000_000)
    assert (dut.key_word, dut.key_bits, dut.bit_cycles, dut.key_low_us) == (0x16EF, 16, 20, 10)
    assert (dut.sof_period, dut.sof_pulse, dut.gap_cycles) == (1000, 500, 160)
    assert dut.staged_operation
    assert CynthionUsbKeyTop(mode='pico-repeat', target_power_from_control=True).mode == 'pico-repeat'


def test_first_repeat_bit_has_complete_microsecond_intervals_at_divided_clock():
    dut = _dut(clock_hz=2_000_000)
    sim = Simulator(dut)
    sim.add_clock(0.5e-6, domain='usb')

    async def bench(ctx):
        # Unlike the 1MHz accelerated checks this exercises divider alignment
        # on USER2 entry. Preflight uses sufficient cycles for each dwell.
        for gate in (dut.phy_isolated, dut.bank6_3v3_confirmed, dut.ack_sense_valid):
            ctx.set(gate, 1)
        await _ticks(ctx, 12)
        ctx.set(dut.user_button, 1)
        for _ in range(30):
            if ctx.get(dut.state) == dut.SELFTEST:
                break
            await _ticks(ctx, 1)
        for value in (2, 1, 0, 3):
            ctx.set(dut.line_state_update, 1)
            ctx.set(dut.line_state_valid, 1)
            ctx.set(dut.line_state_value, value)
            await _ticks(ctx, 1)
            ctx.set(dut.line_state_update, 0)
            for _ in range(12):
                if ctx.get(dut.state) != dut.SELFTEST or (
                    ctx.get(dut.dp_o), ctx.get(dut.dm_o)) != (value & 1, value >> 1):
                    break
                await _ticks(ctx, 1)
        assert ctx.get(dut.state) == dut.READY
        ctx.set(dut.user_button, 0)
        await _ticks(ctx, 20)
        ctx.set(dut.user_button, 1)
        for _ in range(20):
            await _ticks(ctx, 1)
            if ctx.get(dut.state) == dut.KEY:
                break
        assert ctx.get(dut.state) == dut.KEY
        for clock in range(40):
            assert ctx.get(dut.dp_o) == int(clock >= 20)
            assert ctx.get(dut.dm_o) == 0  # first MSB of0x16ef
            assert ctx.get(dut.debug_key_bit) == 0
            await _ticks(ctx, 1)
        assert ctx.get(dut.debug_key_bit) == 1
        assert ctx.get(dut.dp_o) == 0

    sim.add_testbench(bench)
    sim.run()
