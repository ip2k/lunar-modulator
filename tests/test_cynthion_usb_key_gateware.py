import pytest

pytest.importorskip("amaranth")
pytest.importorskip("cynthion")
from amaranth.sim import Simulator

from tools.cynthion_usb_key.gateware import CynthionUsbKey
from tools.cynthion_usb_key.top import CynthionUsbKeyPlatform, CynthionUsbKeyTop


async def _enter_wait_dp(ctx, dut):
    """Drive the simulation contract through self-test and candidate ACK."""
    for _ in range(10):
        await ctx.tick(domain="usb")
        if ctx.get(dut.state) == dut.SELFTEST:
            break
    assert ctx.get(dut.state) == dut.SELFTEST

    sequence = (2, 1, 0, 3)
    for index, expected in enumerate(sequence):
        ctx.set(dut.line_state_valid, 1)
        ctx.set(dut.line_state_value, expected)
        ctx.set(dut.line_state_update, 1)
        await ctx.tick(domain="usb")
        ctx.set(dut.line_state_update, 0)
        for _ in range(5):
            await ctx.tick(domain="usb")
            if index < len(sequence) - 1 and (
                ctx.get(dut.dp_o), ctx.get(dut.dm_o)
            ) == (sequence[index + 1] & 1, sequence[index + 1] >> 1):
                break
    assert ctx.get(dut.state) == dut.KEY

    key_bit = (dut.key_word >> (dut.key_bits - 1)) & 1
    expected_live = 3 if key_bit else 1
    while ctx.get(dut.debug_key_phase) < 8:
        await ctx.tick(domain="usb")
    ctx.set(dut.line_state_value, expected_live)
    ctx.set(dut.line_state_update, 1)
    await ctx.tick(domain="usb")
    ctx.set(dut.line_state_update, 0)
    ctx.set(dut.line_state_value, 0)
    await ctx.tick(domain="usb")
    assert ctx.get(dut.state) == dut.WAIT_DP


def test_control_power_is_explicit_and_operation_only():
    assert CynthionUsbKeyTop().target_power_from_control is False
    assert CynthionUsbKeyTop(target_power_from_control=True).target_power_from_control
    with pytest.raises(ValueError, match="only in operation mode"):
        CynthionUsbKeyTop(mode="disconnected-selftest", target_power_from_control=True)


def test_target_gpio_resources_expose_input_output_and_output_enable():
    platform = CynthionUsbKeyPlatform()
    for name in ("target_usb_dp", "target_usb_dm"):
        pad = platform.request(name)
        assert hasattr(pad, "i")
        assert hasattr(pad, "o")
        assert hasattr(pad, "oe")


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
            ctx.set(dut.pad_dp_i, expected_state & 1)
            ctx.set(dut.pad_dm_i, (expected_state >> 1) & 1)
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
        assert ctx.get(dut.selftest_observed_valid) == 0b1111
        assert [ctx.get(event_count) for event_count in dut.selftest_step_events] == [1, 1, 1, 1]
        assert [ctx.get(value) for value in dut.selftest_step_observed] == [2, 1, 0, 3]
        assert [ctx.get(value) for value in dut.selftest_step_gpio] == [
            0b111010, 0b110101, 0b110000, 0b111111
        ]
        assert ctx.get(dut.leds) == 0b100000

    sim.add_testbench(bench)
    sim.run()


def test_disconnected_selftest_latches_first_failed_line_and_gpio_evidence():
    dut = CynthionUsbKey(clock_hz=1_000_000, selftest_state_us=4,
                         auto_selftest=True, selftest_only=True)
    sim = Simulator(dut)
    sim.add_clock(1e-6, domain="usb")

    async def bench(ctx):
        ctx.set(dut.phy_isolated, 1)
        ctx.set(dut.bank6_3v3_confirmed, 1)
        ctx.set(dut.ack_sense_valid, 1)
        ctx.set(dut.pad_dp_i, 1)
        ctx.set(dut.pad_dm_i, 0)
        for _ in range(20):
            await ctx.tick(domain="usb")
            if ctx.get(dut.state) == dut.FAULT:
                break

        assert ctx.get(dut.state) == dut.FAULT
        assert ctx.get(dut.state) != dut.KEY
        assert ctx.get(dut.selftest_failure_reason) == 1
        assert ctx.get(dut.selftest_failure_step) == 0
        assert ctx.get(dut.selftest_failure_expected) == 2  # K
        assert ctx.get(dut.selftest_failure_observed) == 0  # no RXCMD event
        assert ctx.get(dut.selftest_failure_gpio) == 0b111001
        assert ctx.get(dut.selftest_observed_valid) == 0
        assert [ctx.get(event_count) for event_count in dut.selftest_step_events] == [0, 0, 0, 0]
        assert ctx.get(dut.dp_oe) == 0
        assert ctx.get(dut.dm_oe) == 0

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


def test_disconnected_line_echo_cannot_falsely_ack_a_data_bit():
    dut = CynthionUsbKey(clock_hz=1_000_000, packet_limit=1,
                         selftest_state_us=3, ack_duration_us=100,
                         auto_selftest=True, selftest_only=False)
    sim = Simulator(dut)
    sim.add_clock(1e-6, domain="usb")
    seen_states = set()

    async def bench(ctx):
        ctx.set(dut.phy_isolated, 1)
        ctx.set(dut.bank6_3v3_confirmed, 1)
        ctx.set(dut.ack_sense_valid, 1)
        line_state = None
        for _ in range(1_000):
            state = ctx.get(dut.state)
            seen_states.add(state)
            driven = ctx.get(dut.dp_oe) or ctx.get(dut.dm_oe)
            # Disconnected target model: RXCMD echoes driven line states;
            # released lines resolve to SE0 through the target pulldowns.
            observed = ((ctx.get(dut.dp_o) | (ctx.get(dut.dm_o) << 1))
                        if driven else 0)
            changed = line_state is None or observed != line_state
            ctx.set(dut.line_state_value, observed)
            ctx.set(dut.line_state_valid, 1)
            ctx.set(dut.line_state_update, int(changed))
            if changed:
                line_state = observed
            await ctx.tick(domain="usb")
        assert dut.WAIT_DP not in seen_states
        assert ctx.get(dut.state) == dut.FAULT
        assert ctx.get(dut.dp_oe) == 0
        assert ctx.get(dut.dm_oe) == 0
        assert ctx.get(dut.protocol_failure_reason) == dut.PROTOCOL_FAULT_PACKET_LIMIT
        assert ctx.get(dut.protocol_failure_origin_state) == dut.GAP
        assert ctx.get(dut.debug_packets) == 1
        assert ctx.get(dut.debug_receiver_live) == 1
        assert ctx.get(dut.debug_ack_ticks) < dut.ack_duration_us

    sim.add_testbench(bench)
    sim.run()


def test_sof_output_has_exact_period_and_pulse_after_fresh_entry():
    dut = CynthionUsbKey(clock_hz=1_000_000, packet_limit=1,
                         selftest_state_us=2, ack_duration_us=1,
                         dp_high_timeout_ms=1, sof_done_low_ms=1,
                         sof_timeout_ms=1, sof_period_us=8, sof_pulse_us=2,
                         auto_selftest=True, selftest_only=False)
    sim = Simulator(dut)
    sim.add_clock(1e-6, domain="usb")

    async def bench(ctx):
        ctx.set(dut.phy_isolated, 1)
        ctx.set(dut.bank6_3v3_confirmed, 1)
        ctx.set(dut.ack_sense_valid, 1)
        for _ in range(10):
            await ctx.tick(domain="usb")
            if ctx.get(dut.state) == dut.SELFTEST:
                break
        assert ctx.get(dut.state) == dut.SELFTEST

        sequence = (2, 1, 0, 3)
        for index, expected in enumerate(sequence):
            ctx.set(dut.line_state_valid, 1)
            ctx.set(dut.line_state_value, expected)
            ctx.set(dut.line_state_update, 1)
            await ctx.tick(domain="usb")
            ctx.set(dut.line_state_update, 0)
            for _ in range(4):
                await ctx.tick(domain="usb")
                if index < len(sequence) - 1 and (
                    ctx.get(dut.dp_o), ctx.get(dut.dm_o)
                ) == (sequence[index + 1] & 1, sequence[index + 1] >> 1):
                    break
        assert ctx.get(dut.state) == dut.KEY

        # Receiver liveness comes from an RXCMD update matching an actively
        # driven high-phase state. Then a single SE0 event qualifies the
        # simulation-only ACK transition for this pulse-timing test.
        key_bit = (dut.key_word >> (dut.key_bits - 1)) & 1
        live_state = 3 if key_bit else 1
        for _ in range(8):
            await ctx.tick(domain="usb")
        ctx.set(dut.line_state_value, live_state)
        ctx.set(dut.line_state_update, 1)
        await ctx.tick(domain="usb")
        ctx.set(dut.line_state_update, 0)
        ctx.set(dut.line_state_value, 0)
        ctx.set(dut.line_state_update, 1)
        await ctx.tick(domain="usb")
        ctx.set(dut.line_state_update, 0)
        assert ctx.get(dut.state) == dut.WAIT_DP

        ctx.set(dut.line_state_value, 1)
        await ctx.tick(domain="usb")
        assert ctx.get(dut.state) == dut.SOF
        # Entry must reset the phase counter: low for two us, released for six,
        # repeating exactly at the configured eight-us interval.
        samples = []
        for _ in range(18):
            samples.append(ctx.get(dut.dp_oe))
            await ctx.tick(domain="usb")
        assert samples == [1, 1, 0, 0, 0, 0, 0, 0,
                           1, 1, 0, 0, 0, 0, 0, 0, 1, 1]

    sim.add_testbench(bench)
    sim.run()


@pytest.mark.parametrize(
    ("stage", "expected_reason", "expected_origin"),
    [
        ("wait", CynthionUsbKey.PROTOCOL_FAULT_WAIT_DP_TIMEOUT,
         CynthionUsbKey.WAIT_DP),
        ("sof", CynthionUsbKey.PROTOCOL_FAULT_SOF_TIMEOUT,
         CynthionUsbKey.SOF),
    ],
)
def test_terminal_protocol_fault_reports_timeout_stage_and_progress(
    stage, expected_reason, expected_origin
):
    dut = CynthionUsbKey(clock_hz=1_000_000, selftest_state_us=2,
                         ack_duration_us=1, dp_high_timeout_ms=0.003,
                         sof_timeout_ms=0.003, auto_selftest=True)
    sim = Simulator(dut)
    sim.add_clock(1e-6, domain="usb")

    async def bench(ctx):
        ctx.set(dut.phy_isolated, 1)
        ctx.set(dut.bank6_3v3_confirmed, 1)
        ctx.set(dut.ack_sense_valid, 1)
        await _enter_wait_dp(ctx, dut)

        if stage == "sof":
            ctx.set(dut.line_state_value, 1)
            await ctx.tick(domain="usb")
            assert ctx.get(dut.state) == dut.SOF

        for _ in range(8):
            await ctx.tick(domain="usb")
            if ctx.get(dut.state) == dut.FAULT:
                break

        assert ctx.get(dut.state) == dut.FAULT
        assert ctx.get(dut.protocol_failure_reason) == expected_reason
        assert ctx.get(dut.protocol_failure_origin_state) == expected_origin
        assert ctx.get(dut.debug_wait_ticks) > 0
        if stage == "sof":
            assert ctx.get(dut.debug_sof_ticks) == 3
        else:
            assert ctx.get(dut.debug_sof_ticks) == 0
        assert ctx.get(dut.dp_oe) == 0
        assert ctx.get(dut.dm_oe) == 0

    sim.add_testbench(bench)
    sim.run()


def test_disconnected_walk_collects_all_four_states_after_swapped_rxcmd_mismatch():
    dut = CynthionUsbKey(clock_hz=1_000_000, selftest_state_us=3,
                         auto_selftest=True, selftest_only=True)
    sim = Simulator(dut)
    sim.add_clock(1e-6, domain="usb")

    async def bench(ctx):
        ctx.set(dut.phy_isolated, 1)
        ctx.set(dut.bank6_3v3_confirmed, 1)
        ctx.set(dut.ack_sense_valid, 1)
        for _ in range(10):
            await ctx.tick(domain="usb")
            if ctx.get(dut.state) == dut.SELFTEST:
                break
        assert ctx.get(dut.state) == dut.SELFTEST

        sequence = (2, 1, 0, 3)
        observed_values = []
        for index, expected in enumerate(sequence):
            assert ctx.get(dut.state) == dut.SELFTEST
            assert (ctx.get(dut.dp_o), ctx.get(dut.dm_o)) == (
                expected & 1, (expected >> 1) & 1
            )
            observed = ((expected & 1) << 1) | (expected >> 1)
            observed_values.append(observed)
            ctx.set(dut.pad_dp_i, expected & 1)
            ctx.set(dut.pad_dm_i, (expected >> 1) & 1)
            ctx.set(dut.line_state_value, observed)
            ctx.set(dut.line_state_valid, 1)
            ctx.set(dut.line_state_update, 1)
            await ctx.tick(domain="usb")
            ctx.set(dut.line_state_update, 0)
            for _ in range(5):
                await ctx.tick(domain="usb")
                if index < len(sequence) - 1 and (
                    ctx.get(dut.dp_o), ctx.get(dut.dm_o)
                ) == (sequence[index + 1] & 1, sequence[index + 1] >> 1):
                    break

        assert ctx.get(dut.state) == dut.FAULT
        assert ctx.get(dut.state) != dut.KEY
        assert ctx.get(dut.done) == 0
        assert ctx.get(dut.selftest_failure_reason) == 1
        assert ctx.get(dut.selftest_failure_step) == 0
        assert ctx.get(dut.selftest_failure_expected) == 2
        assert ctx.get(dut.selftest_failure_observed) == 1
        assert ctx.get(dut.selftest_failure_gpio) == 0b111010
        assert ctx.get(dut.selftest_mask) == 0b1100
        assert ctx.get(dut.selftest_observed_valid) == 0b1111
        assert [ctx.get(value) for value in dut.selftest_step_events] == [1, 1, 1, 1]
        assert [ctx.get(value) for value in dut.selftest_step_observed] == observed_values
        assert [ctx.get(value) for value in dut.selftest_step_gpio] == [
            0b111010, 0b110101, 0b110000, 0b111111
        ]
        assert ctx.get(dut.dp_oe) == 0
        assert ctx.get(dut.dm_oe) == 0

    sim.add_testbench(bench)
    sim.run()
