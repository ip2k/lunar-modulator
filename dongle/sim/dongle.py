"""The dongle firmware's control logic (dongle/firmware/main.c) in Python, driven
by the emulated PIO waveforms and the parameters from config.h."""
from .params import PARAMS
from . import pio_waveform

POLARITY_DP_CLOCK = PARAMS["POLARITY_DP_CLOCK"]
POLARITY_DM_CLOCK = PARAMS["POLARITY_DM_CLOCK"]
POLARITY_ALTERNATE = PARAMS["POLARITY_ALTERNATE"]
SOF_MODE_PC = PARAMS["SOF_MODE_PC"]
SOF_MODE_DONGLE = PARAMS["SOF_MODE_DONGLE"]


class DongleModel:
    def __init__(self, polarity_mode=None, sof_mode=None, params=PARAMS,
                 key_waveform=None, sof_waveform=None):
        self.p = params
        self.polarity_mode = params["DEFAULT_POLARITY_MODE"] if polarity_mode is None else polarity_mode
        self.sof_mode = params["DEFAULT_SOF_MODE"] if sof_mode is None else sof_mode
        self.key_wave = key_waveform or pio_waveform.key_packet_waveform(params["USB_KEY_WORD"])
        self.sof_wave = sof_waveform or pio_waveform.sof_waveform(1)
        self.state = "selftest"
        self.pol = POLARITY_DM_CLOCK if self.polarity_mode == POLARITY_DM_CLOCK else POLARITY_DP_CLOCK
        self.packets = 0
        self.in_block = 0
        self.packet_start = None
        self.gap_start = None
        self.ack_low_us = 0
        self.ack_polarity = None
        self.ack_at = None
        self.ack_indicator_pending = False
        self.pullups_on = False
        self.mux_pc = True
        self.drive_dp_low = False
        self.drive_dm_low = False
        self.phase_start = None
        self.sof_low_run = 0
        self.sof_next_sample = None
        self.done_at = None
        self.log = []

    # ---- helpers ----------------------------------------------------------------
    def _key_levels(self, t_us):
        """Which lines the key program drives low at packet time t (µs)."""
        clock_low, data_low = self.key_wave[t_us]
        if self.pol == POLARITY_DP_CLOCK:
            return clock_low, data_low      # D+ clock, D- data
        return data_low, clock_low          # D- clock, D+ data

    def _start_packet(self, t_us):
        self.packet_start = t_us
        self.gap_start = None
        self.ack_low_us = 0

    # ---- one microsecond ----------------------------------------------------------
    def step(self, t_us, dp, dm):
        p = self.p
        if self.state == "selftest":
            self.pullups_on = True
            self.mux_pc = True
            if t_us >= 2000:                      # firmware waits 2 ms before reading
                if dp and dm:
                    self.state = "key"
                    self.mux_pc = False
                    self._start_packet(t_us)
                    self.log.append(("key", t_us))
                else:
                    self.state = "fault"
                    self.log.append(("fault", t_us))
        elif self.state == "key":
            rel = t_us - self.packet_start
            if rel < len(self.key_wave):
                self.drive_dp_low, self.drive_dm_low = self._key_levels(rel)
            elif rel < p["KEY_PACKET_US"]:
                self.drive_dp_low = self.drive_dm_low = False
            else:
                # gap: sample both lines every ACK_SAMPLE_US
                self.drive_dp_low = self.drive_dm_low = False
                if self.gap_start is None:
                    self.gap_start = t_us
                    self.packets += 1
                    self.in_block += 1
                gap_rel = t_us - self.gap_start
                if gap_rel % p["ACK_SAMPLE_US"] == 0:
                    if not dp and not dm:
                        self.ack_low_us += p["ACK_SAMPLE_US"]
                        if self.ack_low_us >= p["ACK_MIN_LOW_US"]:
                            self.state = "ack"
                            self.ack_polarity = self.pol
                            self.ack_at = t_us
                            self.phase_start = t_us
                            self.ack_indicator_pending = True
                            self.log.append(("ack", t_us, self.pol, self.packets))
                            return
                    else:
                        self.ack_low_us = 0
                if gap_rel >= p["KEY_GAP_US"]:
                    if self.polarity_mode == POLARITY_ALTERNATE and self.in_block >= p["KEY_PACKETS_PER_POLARITY"]:
                        self.pol = POLARITY_DM_CLOCK if self.pol == POLARITY_DP_CLOCK else POLARITY_DP_CLOCK
                        self.in_block = 0
                    self._start_packet(t_us)
        elif self.state == "ack":
            # wait for the chip to release both lines (pull-ups still on)
            if dp and dm:
                self.log.append(("ack_released", t_us))
                if self.sof_mode == SOF_MODE_PC:
                    self.pullups_on = False
                    self.mux_pc = True
                    self.state = "done"
                    self.done_at = t_us
                    self.log.append(("done", t_us))
                else:
                    self.pullups_on = False
                    self.state = "sof_wait_high"
                    self.phase_start = t_us
            elif t_us - self.phase_start >= p["ACK_RELEASE_TIMEOUT_MS"] * 1000:
                self.log.append(("ack_release_timeout", t_us))
                self.pullups_on = False
                self.state = "sof_wait_high" if self.sof_mode == SOF_MODE_DONGLE else "done"
                if self.state == "done":
                    self.mux_pc = True
                    self.done_at = t_us
                    self.log.append(("done", t_us))
                self.phase_start = t_us
        elif self.state == "sof_wait_high":
            if dp and not dm:
                self.state = "sof_gen"
                self.phase_start = t_us
                self.sof_low_run = 0
                self.sof_next_sample = t_us + p["SOF_SAMPLE_US"]
                self.log.append(("sof_start", t_us))
            elif t_us - self.phase_start > p["SOF_DP_HIGH_TIMEOUT_MS"] * 1000:
                self.state = "failed"
                self.log.append(("failed", t_us, "dp_never_high"))
        elif self.state == "sof_gen":
            rel = (t_us - self.phase_start) % len(self.sof_wave)
            self.drive_dp_low = self.sof_wave[rel][0]
            if t_us >= self.sof_next_sample:
                self.sof_next_sample += p["SOF_SAMPLE_US"]
                if not dp:
                    self.sof_low_run += 1
                    if self.sof_low_run * p["SOF_SAMPLE_US"] >= p["SOF_DONE_LOW_MS"] * 1000:
                        self.drive_dp_low = False
                        self.mux_pc = True
                        self.state = "done"
                        self.done_at = t_us
                        self.log.append(("done", t_us))
                else:
                    self.sof_low_run = 0
            if self.state == "sof_gen" and t_us - self.phase_start > p["SOF_PHASE_TIMEOUT_MS"] * 1000:
                self.drive_dp_low = False
                self.state = "failed"
                self.log.append(("failed", t_us, "sof_timeout"))
        # done / failed / fault: drive nothing
        if self.state in ("done", "failed", "fault"):
            self.drive_dp_low = self.drive_dm_low = False
            self.pullups_on = False
            self.mux_pc = True
            if self.ack_indicator_pending:
                self.log.append(("ack_indicator_after_handoff", t_us))
                self.ack_indicator_pending = False
