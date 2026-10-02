"""End-to-end simulation of the dongle logic against the ROM model."""
import pytest

from dongle.sim import cosim, pio_waveform
from dongle.sim.dongle import (POLARITY_ALTERNATE, POLARITY_DM_CLOCK, POLARITY_DP_CLOCK,
                               SOF_MODE_DONGLE, SOF_MODE_PC, DongleModel)
from dongle.sim.jieli_rom import JieLiMaskRom
from dongle.sim.params import PARAMS

KEY_WAVE = pio_waveform.key_packet_waveform(PARAMS["USB_KEY_WORD"])
SOF_WAVE = pio_waveform.sof_waveform(1)


def dongle(**kw):
    return DongleModel(key_waveform=KEY_WAVE, sof_waveform=SOF_WAVE, **kw)


def test_config_constants():
    assert PARAMS["USB_KEY_WORD"] == 0x16EF
    assert PARAMS["KEY_PIO_HZ"] // PARAMS["KEY_BIT_CYCLES"] == 50_000
    assert PARAMS["ACK_MIN_LOW_US"] < 1000            # a real ACK lasts 1-2 ms
    assert PARAMS["SOF_PERIOD_CYCLES"] == 1000 and PARAMS["SOF_PULSE_CYCLES"] == 4
    assert PARAMS["MUX_SEL_PC"] == 0                  # de-energised relay = PC


def test_each_pullup_has_its_own_pin():
    pins = [PARAMS[k] for k in ("PIN_DP", "PIN_DM", "PIN_PULLUP_DP", "PIN_PULLUP_DM", "PIN_MUX_SEL", "PIN_BUTTON")]
    assert len(set(pins)) == len(pins) and 25 not in pins   # GP25 is the on-board LED
    assert "PIN_PULLUP_EN" not in PARAMS                    # the shared pin of the first wiring


def test_shared_pullup_pin_fails_the_sof_phase():
    # The first wiring tied both 2.2 k pull-ups to one pin. Switched off, they still joined D+ and D-
    # through 4.4 k, so D- followed the chip's D+ pull-up and the SOF phase, which waits for D+ high
    # and D- low, timed out. One pin per pull-up (config.h) fixes it; the default model is that.
    rom = JieLiMaskRom(clock_line="dp")
    d = dongle(polarity_mode=POLARITY_DP_CLOCK, sof_mode=SOF_MODE_DONGLE)
    cosim.run(d, rom, max_us=600_000, pullup_node="shared")
    assert d.state == "failed" and ("failed", d.log[-1][1], "dp_never_high") == d.log[-1], d.log
    rom = JieLiMaskRom(clock_line="dp")
    d = dongle(polarity_mode=POLARITY_DP_CLOCK, sof_mode=SOF_MODE_DONGLE)
    cosim.run(d, rom, max_us=80_000)
    assert d.state == "done", d.log


@pytest.mark.parametrize("rom_clock", ["dp", "dm"])
def test_alternate_polarity_reaches_uboot_with_dongle_sof(rom_clock):
    rom = JieLiMaskRom(clock_line=rom_clock)
    d = dongle(polarity_mode=POLARITY_ALTERNATE, sof_mode=SOF_MODE_DONGLE)
    t = cosim.run(d, rom, max_us=80_000)
    assert d.state == "done", d.log
    expected = POLARITY_DP_CLOCK if rom_clock == "dp" else POLARITY_DM_CLOCK
    assert d.ack_polarity == expected
    assert rom.state in ("calibrated", "usb_ready"), rom.log
    assert abs(rom.measured_period_us - 1000) <= 1
    assert d.mux_pc and not d.pullups_on
    assert t < 80_000


@pytest.mark.parametrize("rom_clock,pol", [("dp", POLARITY_DP_CLOCK), ("dm", POLARITY_DM_CLOCK)])
def test_fixed_polarity_pc_sof_hands_over_right_after_ack(rom_clock, pol):
    rom = JieLiMaskRom(clock_line=rom_clock)
    d = dongle(polarity_mode=pol, sof_mode=SOF_MODE_PC)
    cosim.run(d, rom, max_us=30_000)
    assert d.state == "done" and d.ack_polarity == pol
    # the ACK is 1.5 ms long; the bus goes to the PC within a few ms of it
    assert d.done_at - d.ack_at < 5_000
    assert rom.state in ("sof_wait", "calibrated", "usb_ready")   # PC would now supply SOFs


@pytest.mark.parametrize("rom_clock,pol", [("dp", POLARITY_DM_CLOCK), ("dm", POLARITY_DP_CLOCK)])
def test_wrong_fixed_polarity_never_acks(rom_clock, pol):
    rom = JieLiMaskRom(clock_line=rom_clock)
    d = dongle(polarity_mode=pol, sof_mode=SOF_MODE_DONGLE)
    cosim.run(d, rom, max_us=40_000)
    assert d.state == "key" and rom.state == "listen"
    assert d.packets > 60


def test_no_ack_with_absent_or_unpowered_target():
    d = dongle(polarity_mode=POLARITY_ALTERNATE)
    cosim.run(d, None, max_us=40_000)
    assert d.state == "key" and d.ack_polarity is None
    rom = JieLiMaskRom(powered=False)
    d = dongle(polarity_mode=POLARITY_ALTERNATE)
    cosim.run(d, rom, max_us=40_000)
    assert d.state == "key" and rom.state == "off"


def test_selftest_fault_when_a_dongle_line_is_shorted():
    # A short or missing pull-up on the dongle's own side must stop the sequence before keying.
    d = dongle()
    cosim.run(d, JieLiMaskRom(), max_us=5_000, dongle_side_low={"dp"})
    assert d.state == "fault" and d.packets == 0


def test_short_listening_window_needs_matching_first_block():
    # If the ROM only listens for ~1.5 ms after power-up, the first polarity block must match.
    rom = JieLiMaskRom(clock_line="dp", listen_window_us=1500 + 2000)   # after the 2 ms self-test
    d = dongle(polarity_mode=POLARITY_ALTERNATE, sof_mode=SOF_MODE_PC)
    cosim.run(d, rom, max_us=20_000)
    assert d.state == "done" and d.ack_polarity == POLARITY_DP_CLOCK
    rom = JieLiMaskRom(clock_line="dm", listen_window_us=1500 + 2000)
    d = dongle(polarity_mode=POLARITY_ALTERNATE, sof_mode=SOF_MODE_PC)
    cosim.run(d, rom, max_us=20_000)
    assert rom.state == "boot_flash" and d.state == "key"   # documented limitation: use fixed polarity B


def test_sof_retry_window_is_survived():
    # The ROM's first SOF window can expire before enough edges arrived (it drops its D+ pull-up
    # for a moment and tries again). The dongle must keep pulsing through the short low period
    # and the second window must calibrate.
    rom = JieLiMaskRom(clock_line="dm", first_window_us=2500, sof_window_us=8000, retry_gap_us=500)
    d = dongle(polarity_mode=POLARITY_DM_CLOCK, sof_mode=SOF_MODE_DONGLE)
    cosim.run(d, rom, max_us=60_000)
    assert rom.attempt == 2, rom.log
    assert d.state == "done" and rom.state in ("calibrated", "usb_ready"), (d.log, rom.log)
