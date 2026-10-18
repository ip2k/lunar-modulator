"""Production-divider regressions through the top level's real capture block.

Synthetic RXCMD events validate telemetry only, never electrical/ROM behavior.
Long profiles are shortened; the 60 MHz clock and 60-cycle us divider are real.
"""
import pytest

pytest.importorskip('amaranth')
from amaranth import Module, ResetInserter, Signal
from amaranth.sim import Simulator
from tools.cynthion_usb_key.gateware import CynthionUsbKey
from tools.cynthion_usb_key.top import UsbKeyTerminalSnapshot
from tools.cynthion_usb_key.telemetry import decode_terminal


@pytest.mark.parametrize('outcome', ['candidate-timeout', 'candidate-done', 'no-candidate'])
def test_production_terminal_candidate_and_reset(outcome):
    core = CynthionUsbKey(clock_hz=60_000_000, auto_selftest=True,
                          selftest_state_us=3, ack_duration_us=2,
                          packet_limit=1, dp_high_timeout_ms=1,
                          sof_done_low_ms=1, sof_timeout_ms=2)
    receipt = UsbKeyTerminalSnapshot(core)
    m = Module()
    m.submodules.core = core
    m.submodules.receipt = receipt
    reset = Signal()
    sim = Simulator(ResetInserter({'usb': reset})(m))
    sim.add_clock(1 / 60_000_000, domain='usb')

    async def bench(ctx):
        ctx.set(core.phy_isolated, 1)
        ctx.set(core.bank6_3v3_confirmed, 1)
        ctx.set(core.ack_sense_valid, 1)
        previous_echo = None
        witness = False
        se0_sent = False
        pulse_seen = False
        candidate = outcome != 'no-candidate'
        for _ in range(120_000):
            state = ctx.get(core.state)
            ctx.set(core.line_state_update, 0)
            if state == core.SELFTEST:
                echo = ctx.get(core.dp_o) | ctx.get(core.dm_o) << 1
                if echo != previous_echo:
                    ctx.set(core.line_state_value, echo)
                    ctx.set(core.line_state_valid, 1)
                    ctx.set(core.line_state_update, 1)
                    previous_echo = echo
            elif candidate and state == core.KEY:
                if not witness and ctx.get(core.dp_o) and not ctx.get(core.dm_o):
                    ctx.set(core.line_state_value, 1)
                    ctx.set(core.line_state_update, 1)
                    witness = True
                elif witness and not se0_sent and ctx.get(core.debug_receiver_live):
                    ctx.set(core.line_state_value, 0)
                    ctx.set(core.line_state_update, 1)
                    se0_sent = True
            elif state == core.WAIT_DP and outcome == 'candidate-done':
                ctx.set(core.line_state_value, 1)
            elif state == core.SOF:
                ctx.set(core.line_state_value, 0)
            pulse_seen |= bool(ctx.get(core.debug_ack_confirm))
            if ctx.get(receipt.valid):
                break
            await ctx.tick(domain='usb')
        else:
            pytest.fail('No terminal capture within bounded production-clock simulation')
        assert pulse_seen == candidate
        assert ctx.get(core.debug_ack_confirm) == 0  # pulse expired before capture
        assert ctx.get(receipt.ack_progress) & 2 == 0  # legacy register stays transient
        assert ctx.get(receipt.ack_candidate) == (3 if candidate else 1)
        expected = core.DONE if outcome == 'candidate-done' else core.FAULT
        assert ctx.get(core.state) == expected
        reason = (ctx.get(receipt.protocol_failure) >> 1) & 7
        assert reason == {'candidate-timeout': 2, 'candidate-done': 0,
                          'no-candidate': 1}[outcome]
        retained = ctx.get(receipt.ack_candidate)
        for _ in range(123):
            await ctx.tick(domain='usb')
            assert ctx.get(receipt.ack_candidate) == retained
            assert not ctx.get(core.dp_oe) and not ctx.get(core.dm_oe)
        ctx.set(reset, 1)
        await ctx.tick(domain='usb')
        assert ctx.get(receipt.valid) == 0
        assert ctx.get(receipt.ack_candidate) == 0
        assert ctx.get(receipt.protocol_failure) == 0
        assert ctx.get(core.debug_ack_candidate) == 0
        ctx.set(reset, 0)
        await ctx.tick(domain='usb')
        assert not ctx.get(receipt.valid)
        assert not ctx.get(receipt.ack_candidate)

    sim.add_testbench(bench)
    sim.run()


@pytest.mark.parametrize('layout', [7, 8, 9])
def test_historical_decode_and_layout_compatibility(layout):
    registers = {1: 0x4C554E52, 2: layout, 0x0c: 1,
                 0x0e: 0x18d, 0x12: 19 << 8, 0x67: 3}
    decoded = decode_terminal(registers)
    assert decoded['receiver_live'] is True
    assert decoded['transient_ack_predicate'] is False
    assert decoded['ack_ticks_us'] == 99
    assert decoded['key_phase_us'] == 19
    assert decoded['local_ack_candidate'] == (True if layout == 9 else None)


def test_decoder_unknown_invalid_and_preterminal():
    registers = {1: 0x4C554E52, 2: 9, 0x0c: 0, 0x0e: 0, 0x12: 0, 0x67: 0}
    assert decode_terminal(registers)['local_ack_candidate'] is None
    for change in ({2: 10}, {1: 0}, {0x67: 1}, {0x67: 4}):
        with pytest.raises(ValueError):
            decode_terminal(registers | change)
    assert decode_terminal(registers | {0x0c: 1, 0x67: 1})['local_ack_candidate'] is False
