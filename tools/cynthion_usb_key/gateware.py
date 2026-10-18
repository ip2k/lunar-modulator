"""Simulation-gated, bounded Cynthion USB_KEY protocol core.

No platform pin driver or upload path is enabled by this module. External
electrical interlocks default low. USB3343 RXCMD status is a line-state report,
not a protocol-level ACK or a guaranteed periodic sample stream.
"""

from amaranth import Array, Cat, Elaboratable, Module, Mux, Signal
from amaranth.lib.cdc import FFSynchronizer

from dongle.sim.params import PARAMS


class UsbKeyEventHistory(Elaboratable):
    """Diagnostic-only ring of fixed-width USB_KEY state snapshots.

    Each entry is 64 bits: microsecond timestamp (32 bits) followed by a
    32-bit packed snapshot. A terminal input
    freezes the ring after optionally recording that same-cycle event.
    """

    DEPTH = 32
    ENTRY_BITS = 64

    def __init__(self, *, domain="usb"):
        self.domain = domain
        self.tick_us = Signal()
        self.event = Signal()
        self.terminal = Signal()
        self.payload = Signal(32)
        self.timestamp_us = Signal(32)
        self.next_index = Signal(5)
        self.count = Signal(6)
        self.frozen = Signal()
        self.entries = [Signal(self.ENTRY_BITS, name=f"history_entry_{i}")
                        for i in range(self.DEPTH)]

    def elaborate(self, platform):
        m = Module()
        d = m.d[self.domain]
        entries = Array(self.entries)
        with m.If(~self.frozen):
            with m.If(self.tick_us):
                d += self.timestamp_us.eq(self.timestamp_us + 1)
            with m.If(self.event):
                d += [entries[self.next_index].eq(
                          Cat(self.timestamp_us, self.payload)),
                      self.next_index.eq(self.next_index + 1),
                      self.count.eq(Mux(self.count < self.DEPTH,
                                        self.count + 1, self.count))]
            with m.If(self.terminal):
                d += self.frozen.eq(1)
        return m


class CynthionUsbKey(Elaboratable):
    """Finite D+ clock attempt, preceded by an RXCMD four-state self-test.

    FS line-state encoding is DP | (DM << 1): SE0/J/K/SE1 = 0/1/2/3. A fresh
    RXCMD update must agree with a driven high-phase J/SE1 state before the
    receiver is considered live. A candidate ACK requires SE0 while the key
    waveform is actively driven for 100 us; released GAP SE0 never counts.
    This contract is only a simulation target: change-reported RXCMD status
    does not establish continuous 100 us sampling or prove ROM behavior.
    """

    SAFE, ARMED, SELFTEST, KEY, GAP, WAIT_DP, SOF, DONE, FAULT, READY = range(10)
    PROTOCOL_FAULT_NONE = 0
    PROTOCOL_FAULT_PACKET_LIMIT = 1
    PROTOCOL_FAULT_WAIT_DP_TIMEOUT = 2
    PROTOCOL_FAULT_SOF_TIMEOUT = 3
    PROTOCOL_FAULT_INTERLOCK_LOST = 4

    def __init__(self, *, domain="usb", clock_hz=60_000_000,
                 packet_limit=30_000, debounce_us=5_000,
                 selftest_state_us=1_000, ack_duration_us=100,
                 dp_high_timeout_ms=None, sof_done_low_ms=None, sof_timeout_ms=None,
                 sof_period_us=None, sof_pulse_us=None,
                 auto_selftest=False, selftest_only=False, staged_operation=False):
        if clock_hz <= 0 or clock_hz % 1_000_000:
            raise ValueError("clock_hz must be a positive integer MHz")
        self.domain = domain
        self.cycles_per_us = clock_hz // 1_000_000
        self.packet_limit = packet_limit
        self.debounce_us = debounce_us
        self.selftest_state_us = selftest_state_us
        p = PARAMS
        self.ack_duration_us = ack_duration_us
        self.auto_selftest = auto_selftest
        if staged_operation and (auto_selftest or selftest_only):
            raise ValueError("staged operation requires physical USER preflight")
        self.staged_operation = staged_operation
        self.selftest_only = selftest_only
        self.key_word = p["USB_KEY_WORD"]
        self.key_bits = p["KEY_BITS"]
        self.bit_cycles = p["KEY_BIT_CYCLES"]
        self.gap_cycles = p["KEY_GAP_US"]
        self.sof_period = (p["SOF_PERIOD_CYCLES"] if sof_period_us is None
                           else sof_period_us)
        self.sof_pulse = (p["SOF_PULSE_CYCLES"] if sof_pulse_us is None
                          else sof_pulse_us)
        if not 0 < self.sof_pulse < self.sof_period:
            raise ValueError("SOF pulse must be shorter than its positive period")
        self.dp_high_timeout = (dp_high_timeout_ms if dp_high_timeout_ms is not None
                                else p["SOF_DP_HIGH_TIMEOUT_MS"]) * 1000
        self.sof_done_low = (sof_done_low_ms if sof_done_low_ms is not None
                             else p["SOF_DONE_LOW_MS"]) * 1000
        self.sof_timeout = (sof_timeout_ms if sof_timeout_ms is not None
                            else p["SOF_PHASE_TIMEOUT_MS"]) * 1000

        self.user_button = Signal()  # normalized active-high asynchronous input
        self.phy_isolated = Signal()
        self.bank6_3v3_confirmed = Signal()
        self.ack_sense_valid = Signal()
        self.line_state_value = Signal(2)
        self.line_state_valid = Signal()
        self.line_state_update = Signal()
        self.phy_fault = Signal()

        self.dp_o = Signal()
        self.dm_o = Signal()
        self.dp_oe = Signal()
        self.dm_oe = Signal()
        self.busy = Signal()
        self.done = Signal()
        self.fault = Signal()
        self.state = Signal(4, reset=self.SAFE)
        self.leds = Signal(6)
        self.selftest_mask = Signal(4)
        self.pad_dp_i = Signal()
        self.pad_dm_i = Signal()
        self.selftest_failure_reason = Signal(2)
        self.selftest_failure_step = Signal(2)
        self.selftest_failure_expected = Signal(2)
        self.selftest_failure_observed = Signal(2)
        self.selftest_failure_gpio = Signal(6)
        self.selftest_observed_valid = Signal(4)
        self.selftest_step_events = [Signal(8, name=f"selftest_step_{i}_events")
                                     for i in range(4)]
        self.selftest_step_observed = [Signal(2, name=f"selftest_step_{i}_observed")
                                       for i in range(4)]
        self.selftest_step_gpio = [Signal(6, name=f"selftest_step_{i}_gpio")
                                   for i in range(4)]
        # Read-only protocol diagnostics. The top level snapshots these once
        # after a terminal state; they do not feed the protocol decisions.
        self.protocol_failure_reason = Signal(3)
        self.protocol_failure_origin_state = Signal(4)
        self.debug_packets = Signal(32)
        self.debug_receiver_live = Signal()
        self.debug_ack_ticks = Signal(32)
        self.debug_ack_confirm = Signal()
        self.debug_wait_ticks = Signal(32)
        self.debug_sof_ticks = Signal(32)
        self.debug_dp_low_ticks = Signal(32)
        self.debug_key_bit = Signal(8)
        self.debug_key_phase = Signal(16)
        self.history_next_index = Signal(5)
        self.history_count = Signal(6)
        self.history_frozen = Signal()
        self.history_timestamp_us = Signal(32)
        self.history_entries = [Signal(UsbKeyEventHistory.ENTRY_BITS,
                                       name=f"debug_history_entry_{i}")
                               for i in range(UsbKeyEventHistory.DEPTH)]

    def elaborate(self, platform):
        m = Module()
        d = m.d[self.domain]
        permitted = self.phy_isolated & self.bank6_3v3_confirmed & self.ack_sense_valid
        if self.staged_operation:
            permitted = permitted & ~self.phy_fault
        button = Signal()
        m.submodules.button_sync = FFSynchronizer(self.user_button, button, o_domain=self.domain)

        div = Signal(range(self.cycles_per_us))
        us_tick = Signal()
        button_last = Signal()
        button_ticks = Signal(range(self.debounce_us + 1))
        button_released = Signal()
        arm_event = Signal()
        selftest_ticks = Signal(range(self.selftest_state_us + 1))
        selftest_step = Signal(2)
        selftest_seen = Signal()
        step_events = Array(self.selftest_step_events)
        step_observed = Array(self.selftest_step_observed)
        step_gpio = Array(self.selftest_step_gpio)
        tx_bit = Signal(range(self.key_bits))
        selftest_value = Signal(2)
        phase = Signal(range(self.bit_cycles))
        gap = Signal(range(self.gap_cycles))
        packets = Signal(range(self.packet_limit + 1))
        receiver_live = Signal()
        ack_ticks = Signal(range(self.ack_duration_us + 1))
        ack_confirm = Signal()
        ack_confirmed_latched = Signal()
        wait_ticks = Signal(range(self.dp_high_timeout + 1))
        sof_ticks = Signal(range(self.sof_timeout + 1))
        sof_phase = Signal(range(self.sof_period))
        dp_low_ticks = Signal(range(self.sof_done_low + 1))
        key_bit = Signal()
        history = UsbKeyEventHistory(domain=self.domain)
        m.submodules.event_history = history
        history_last_state = Signal(4, reset=self.SAFE)
        history_phase = Signal(11)
        history_gpio = Cat(self.pad_dp_i, self.pad_dm_i, self.dp_o, self.dm_o,
                           self.dp_oe & self.phy_isolated,
                           self.dm_oe & self.phy_isolated)
        history_payload = Cat(
            self.state, self.line_state_update, self.line_state_valid,
            self.line_state_value, history_gpio, tx_bit, history_phase,
            receiver_live, ack_confirmed_latched, (ack_ticks != 0))
        m.d.comb += [
            history.tick_us.eq(us_tick),
            history.event.eq(self.line_state_update |
                             (self.state != history_last_state)),
            history.terminal.eq((self.state == self.DONE) |
                                (self.state == self.FAULT)),
            history.payload.eq(history_payload),
            history_phase.eq(phase),
            self.history_next_index.eq(history.next_index),
            self.history_count.eq(history.count),
            self.history_frozen.eq(history.frozen),
            self.history_timestamp_us.eq(history.timestamp_us),
        ]
        for index in range(UsbKeyEventHistory.DEPTH):
            m.d.comb += self.history_entries[index].eq(history.entries[index])
        d += history_last_state.eq(self.state)

        m.d.comb += [
            us_tick.eq(div == self.cycles_per_us - 1),
            ack_confirm.eq(us_tick & receiver_live & self.line_state_valid &
                           (self.line_state_value == 0) &
                           (ack_ticks == self.ack_duration_us - 1)),
            key_bit.eq(Array([(self.key_word >> n) & 1
                              for n in reversed(range(self.key_bits))])[tx_bit]),
            # Start from a driven K state, then exercise J, SE0, and SE1. A
            # transition from the PHY's unknown/reset line state is therefore
            # observable on RXCMD before each subsequent state is accepted.
            selftest_value.eq(Array([2, 1, 0, 3])[selftest_step]),
            self.dp_o.eq(0), self.dm_o.eq(0), self.dp_oe.eq(0), self.dm_oe.eq(0),
            self.busy.eq((self.state != self.SAFE) & (self.state != self.DONE) & (self.state != self.FAULT)),
            self.done.eq(self.state == self.DONE), self.fault.eq(self.state == self.FAULT),
            self.debug_packets.eq(packets),
            self.debug_receiver_live.eq(receiver_live),
            self.debug_ack_ticks.eq(ack_ticks),
            self.debug_ack_confirm.eq(ack_confirm),
            # The threshold cycle faults before the free-running counter's
            # nonterminal increment. Report the configured elapsed threshold
            # on that terminal path so the read-only receipt reflects the
            # timeout duration rather than the preceding zero-based count.
            self.debug_wait_ticks.eq(Mux(
                self.protocol_failure_reason == self.PROTOCOL_FAULT_WAIT_DP_TIMEOUT,
                self.dp_high_timeout, wait_ticks)),
            self.debug_sof_ticks.eq(Mux(
                self.protocol_failure_reason == self.PROTOCOL_FAULT_SOF_TIMEOUT,
                self.sof_timeout, sof_ticks)),
            self.debug_dp_low_ticks.eq(dp_low_ticks),
            self.debug_key_bit.eq(tx_bit),
            self.debug_key_phase.eq(phase),
            self.leds.eq(Mux(self.state == self.SAFE, 0b000001,
                Mux((self.state == self.ARMED) | (self.state == self.SELFTEST), 0b000010,
                Mux((self.state == self.KEY) | (self.state == self.GAP), 0b000100,
                Mux(self.state == self.WAIT_DP, 0b001000,
                Mux(self.state == self.SOF, 0b010000,
                Mux(self.state == self.DONE, 0b100000,
                    Mux(self.state == self.READY, 0b010010, 0b111111)))))))),
        ]

        # USER is synchronized and must be released steadily after startup,
        # then pressed steadily. Reset the debounce interval on every edge.
        d += arm_event.eq(0)
        with m.If(button != button_last):
            d += [button_last.eq(button), button_ticks.eq(0)]
        with m.Elif(us_tick):
            with m.If(button_ticks < self.debounce_us):
                d += button_ticks.eq(button_ticks + 1)
            with m.If(button_ticks == self.debounce_us - 1):
                with m.If(~button):
                    d += button_released.eq(1)
                with m.Elif(button_released):
                    d += [arm_event.eq(1), button_released.eq(0)]
        d += div.eq(Mux(us_tick, 0, div + 1))

        # RXCMD line-change evidence must first agree with a driven high-phase
        # state. This prevents a latched startup value from enabling the
        # candidate ACK detector.
        with m.If(self.line_state_update & self.line_state_valid &
                  (self.state == self.KEY) & (phase >= 8) & self.dp_o):
            # Driven waveform is DP low / DM=data for 8 us, then DP high /
            # DM=data for 12 us. Thus low-phase bit 1 is K and high-phase
            # bit 0 is J; high-phase bit 1 is SE1, not K.
            with m.If(((self.line_state_value == 1) & ~key_bit) |
                      ((self.line_state_value == 3) & key_bit)):
                d += receiver_live.eq(1)
        with m.If(self.line_state_update & self.line_state_valid &
                  (self.state == self.SELFTEST) &
                  (self.line_state_value == selftest_value)):
            d += [selftest_seen.eq(1),
                  self.selftest_mask.eq(self.selftest_mask | (1 << selftest_step))]
        with m.If(self.line_state_update & self.line_state_valid &
                  (self.state == self.SELFTEST)):
            for index in range(4):
                with m.If(selftest_step == index):
                    with m.If(step_events[index] != 0xFF):
                        d += step_events[index].eq(step_events[index] + 1)
                    d += [step_observed[index].eq(self.line_state_value),
                          step_gpio[index].eq(Cat(
                              self.pad_dp_i, self.pad_dm_i, self.dp_o, self.dm_o,
                              self.dp_oe & self.phy_isolated,
                              self.dm_oe & self.phy_isolated)),
                          self.selftest_observed_valid[index].eq(1)]

        # Pad state selection is combinationally masked by all three gates.
        with m.If(permitted):
            with m.Switch(self.state):
                with m.Case(self.SELFTEST):
                    m.d.comb += [self.dp_o.eq(selftest_value[0]),
                                 self.dm_o.eq(selftest_value[1]),
                                 self.dp_oe.eq(1), self.dm_oe.eq(1)]
                with m.Case(self.KEY):
                    m.d.comb += [self.dp_oe.eq(1), self.dm_oe.eq(1)]
                    with m.If(phase < 8):
                        m.d.comb += [self.dp_o.eq(0), self.dm_o.eq(key_bit)]
                    with m.Else():
                        m.d.comb += [self.dp_o.eq(1), self.dm_o.eq(key_bit)]
                with m.Case(self.SOF):
                    m.d.comb += [self.dp_oe.eq(sof_phase < self.sof_pulse),
                                 self.dp_o.eq(0)]

        with m.Switch(self.state):
            with m.Case(self.SAFE):
                with m.If(self.phy_fault):
                    d += self.state.eq(self.FAULT)
                with m.Elif(arm_event):
                    with m.If(permitted):
                        d += self.state.eq(self.ARMED)
                    with m.Else():
                        d += self.state.eq(self.FAULT)
                with m.Elif(self.auto_selftest & permitted):
                    d += self.state.eq(self.ARMED)
            with m.Case(self.ARMED):
                with m.If(~permitted):
                    d += self.state.eq(self.FAULT)
                with m.Elif(us_tick):
                    d += [self.state.eq(self.SELFTEST), selftest_step.eq(0),
                          selftest_ticks.eq(0), selftest_seen.eq(0),
                          self.selftest_mask.eq(0),
                          self.selftest_failure_reason.eq(0),
                          self.selftest_failure_step.eq(0),
                          self.selftest_failure_expected.eq(0),
                          self.selftest_failure_observed.eq(0),
                          self.selftest_failure_gpio.eq(0),
                          self.selftest_observed_valid.eq(0),
                          self.protocol_failure_reason.eq(self.PROTOCOL_FAULT_NONE),
                          self.protocol_failure_origin_state.eq(self.SAFE)]
                    for index in range(4):
                        d += [step_events[index].eq(0), step_observed[index].eq(0),
                              step_gpio[index].eq(0)]
            with m.Case(self.SELFTEST):
                with m.If(~permitted):
                    d += [self.state.eq(self.FAULT),
                          self.selftest_failure_reason.eq(2),
                          self.selftest_failure_step.eq(selftest_step),
                          self.selftest_failure_expected.eq(selftest_value),
                          self.selftest_failure_observed.eq(
                              step_observed[selftest_step]),
                          self.selftest_failure_gpio.eq(Cat(
                              self.pad_dp_i, self.pad_dm_i, self.dp_o, self.dm_o,
                              self.dp_oe & self.phy_isolated,
                              self.dm_oe & self.phy_isolated))]
                with m.Elif(us_tick & (selftest_ticks == self.selftest_state_us - 1)):
                    # The disconnected-only image walks every driven state
                    # even after a mismatch, so JTAG retains a complete
                    # input/output/RXCMD comparison. Preserve the first fault
                    # snapshot and terminate high-Z after step 3. Operation
                    # mode still stops immediately on a mismatch.
                    with m.If(~selftest_seen &
                              (self.selftest_failure_reason == 0)):
                        d += [self.selftest_failure_reason.eq(1),
                              self.selftest_failure_step.eq(selftest_step),
                              self.selftest_failure_expected.eq(selftest_value),
                              self.selftest_failure_observed.eq(
                                  step_observed[selftest_step]),
                              self.selftest_failure_gpio.eq(Cat(
                                  self.pad_dp_i, self.pad_dm_i, self.dp_o, self.dm_o,
                                  self.dp_oe & self.phy_isolated,
                                  self.dm_oe & self.phy_isolated))]
                    with m.If(selftest_step == 3):
                        with m.If(self.selftest_only):
                            with m.If((self.selftest_failure_reason != 0) |
                                      ~selftest_seen):
                                d += self.state.eq(self.FAULT)
                            with m.Else():
                                d += self.state.eq(self.DONE)
                        with m.Elif(self.staged_operation & selftest_seen &
                                    (self.selftest_mask == 0b1111) &
                                    (self.selftest_failure_reason == 0)):
                            d += [self.state.eq(self.READY), button_released.eq(0),
                                  button_ticks.eq(0), arm_event.eq(0)]
                        with m.Elif(self.staged_operation | ~selftest_seen):
                            d += self.state.eq(self.FAULT)
                        with m.Else():
                            d += [self.state.eq(self.KEY), tx_bit.eq(0), phase.eq(0),
                                  packets.eq(0), receiver_live.eq(0), ack_ticks.eq(0)]
                    with m.Elif(self.selftest_only | selftest_seen):
                        d += [selftest_step.eq(selftest_step + 1), selftest_ticks.eq(0),
                              selftest_seen.eq(0)]
                    with m.Else():
                        d += self.state.eq(self.FAULT)
                with m.Elif(us_tick):
                    d += selftest_ticks.eq(selftest_ticks + 1)
            with m.Case(self.READY):
                with m.If(~permitted):
                    d += [self.state.eq(self.FAULT),
                          self.protocol_failure_reason.eq(
                              self.PROTOCOL_FAULT_INTERLOCK_LOST),
                          self.protocol_failure_origin_state.eq(self.READY)]
                with m.Elif(arm_event):
                    d += [self.state.eq(self.KEY), tx_bit.eq(0), phase.eq(0),
                          packets.eq(0), receiver_live.eq(0), ack_ticks.eq(0)]
            with m.Case(self.KEY):
                with m.If(~permitted):
                    d += [self.state.eq(self.FAULT),
                          self.protocol_failure_reason.eq(
                              self.PROTOCOL_FAULT_INTERLOCK_LOST),
                          self.protocol_failure_origin_state.eq(self.KEY)]
                with m.Else():
                    # Keep the key waveform advancing while measuring the
                    # receiver's continuous SE0 report. Otherwise a normal
                    # data-bit SE0 would freeze us low and self-confirm ACK.
                    with m.If(self.line_state_update & (self.line_state_value != 0)):
                        d += ack_ticks.eq(0)
                    with m.If(us_tick):
                        with m.If(receiver_live & self.line_state_valid &
                                  (self.line_state_value == 0)):
                            with m.If(~ack_confirm):
                                d += ack_ticks.eq(ack_ticks + 1)
                        with m.Else():
                            d += ack_ticks.eq(0)
                        with m.If(phase == self.bit_cycles - 1):
                            d += phase.eq(0)
                            with m.If(tx_bit == self.key_bits - 1):
                                with m.If(~ack_confirm):
                                    # Candidate duration belongs to one
                                    # actively driven key packet. Do not add
                                    # cached SE0 time from either side of the
                                    # released inter-packet interval.
                                    d += [self.state.eq(self.GAP), gap.eq(0),
                                          ack_ticks.eq(0)]
                            with m.Else():
                                d += tx_bit.eq(tx_bit + 1)
                        with m.Else():
                            d += phase.eq(phase + 1)
                        with m.If(ack_confirm):
                            d += [self.state.eq(self.WAIT_DP), wait_ticks.eq(0),
                                  sof_ticks.eq(0), sof_phase.eq(0),
                              dp_low_ticks.eq(0), ack_confirmed_latched.eq(1)]
            with m.Case(self.GAP):
                with m.If(~permitted):
                    d += [self.state.eq(self.FAULT),
                          self.protocol_failure_reason.eq(
                              self.PROTOCOL_FAULT_INTERLOCK_LOST),
                          self.protocol_failure_origin_state.eq(self.GAP)]
                with m.Elif(us_tick):
                    with m.If(gap == self.gap_cycles - 1):
                        d += [gap.eq(0), packets.eq(packets + 1)]
                        with m.If(packets + 1 >= self.packet_limit):
                            d += [self.state.eq(self.FAULT),
                                  self.protocol_failure_reason.eq(
                                      self.PROTOCOL_FAULT_PACKET_LIMIT),
                                  self.protocol_failure_origin_state.eq(self.GAP)]
                        with m.Else():
                            d += [self.state.eq(self.KEY), tx_bit.eq(0), phase.eq(0)]
                    with m.Else():
                        d += gap.eq(gap + 1)
            with m.Case(self.WAIT_DP):
                with m.If(~permitted):
                    d += [self.state.eq(self.FAULT),
                          self.protocol_failure_reason.eq(
                              self.PROTOCOL_FAULT_INTERLOCK_LOST),
                          self.protocol_failure_origin_state.eq(self.WAIT_DP)]
                with m.Elif(us_tick & self.line_state_valid &
                             (self.line_state_value == 1)):
                    d += [self.state.eq(self.SOF), sof_ticks.eq(0),
                          sof_phase.eq(0), dp_low_ticks.eq(0)]
                with m.Elif(us_tick & (wait_ticks == self.dp_high_timeout - 1)):
                    d += [self.state.eq(self.FAULT),
                          self.protocol_failure_reason.eq(
                              self.PROTOCOL_FAULT_WAIT_DP_TIMEOUT),
                          self.protocol_failure_origin_state.eq(self.WAIT_DP)]
                with m.Elif(us_tick):
                    d += wait_ticks.eq(wait_ticks + 1)
            with m.Case(self.SOF):
                with m.If(~permitted):
                    d += [self.state.eq(self.FAULT),
                          self.protocol_failure_reason.eq(
                              self.PROTOCOL_FAULT_INTERLOCK_LOST),
                          self.protocol_failure_origin_state.eq(self.SOF)]
                with m.Elif(us_tick & (sof_ticks == self.sof_timeout - 1)):
                    d += [self.state.eq(self.FAULT),
                          self.protocol_failure_reason.eq(
                              self.PROTOCOL_FAULT_SOF_TIMEOUT),
                          self.protocol_failure_origin_state.eq(self.SOF)]
                with m.Elif(us_tick):
                    d += sof_ticks.eq(sof_ticks + 1)
                    with m.If(sof_phase == self.sof_period - 1):
                        d += sof_phase.eq(0)
                    with m.Else():
                        d += sof_phase.eq(sof_phase + 1)
                    with m.If(self.line_state_valid & (self.line_state_value == 0)):
                        with m.If(dp_low_ticks == self.sof_done_low - 1):
                            d += self.state.eq(self.DONE)
                        with m.Else():
                            d += dp_low_ticks.eq(dp_low_ticks + 1)
                    with m.Elif(self.line_state_valid):
                        d += dp_low_ticks.eq(0)
            with m.Case(self.DONE, self.FAULT):
                pass

        return m
