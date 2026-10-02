"""Microsecond co-simulation of the dongle model and the ROM model on a shared
open-drain USB pair.

The relay has two positions. With the bus handed to the PC (`dongle.mux_pc`),
the dongle only sees its own side (its pull-ups, its drivers, any board fault)
and the target sees the PC, which is not modelled beyond the chip's own
pull-up. With the relay on the dongle side, both parties share the lines:
0 if anyone drives low, else 1 if any pull-up is present (dongle 2.2 k or the
chip's 1.5 k on D+), else 0 (the chip's 15 k pull-downs).

pullup_node="shared" models the first wiring, which tied both 2.2 k pull-ups
to one GPIO: switched off (hi-Z), the two resistors still join D+ and D-
through 4.4 k, so an undriven D- follows the chip's D+ pull-up. The firmware
now gives each pull-up its own pin ("separate", the default).
"""


def run(dongle, rom, max_us, until=("done", "failed", "fault"),
        stop_rom_states=("boot_flash",), dongle_side_low=(), pullup_node="separate"):
    for t in range(max_us):
        d_dp_low = dongle.drive_dp_low or ("dp" in dongle_side_low)
        d_dm_low = dongle.drive_dm_low or ("dm" in dongle_side_low)
        r_dp_low, r_dm_low = rom.drives_low() if rom is not None else (False, False)
        rom_pull_dp = rom is not None and rom.pulls_up_dp()
        if dongle.mux_pc:
            dp_d = 0 if d_dp_low else (1 if dongle.pullups_on else 0)
            dm_d = 0 if d_dm_low else (1 if dongle.pullups_on else 0)
            dp_r = 0 if r_dp_low else (1 if rom_pull_dp else 0)
            dm_r = 0
        else:
            dp_low, dm_low = d_dp_low or r_dp_low, d_dm_low or r_dm_low
            dp_d = dp_r = 0 if dp_low else (1 if (dongle.pullups_on or rom_pull_dp) else 0)
            dm_d = dm_r = 0 if dm_low else (1 if dongle.pullups_on else 0)
            if pullup_node == "shared" and not dongle.pullups_on and dp_d and not dm_low:
                dm_d = dm_r = 1
        dongle.step(t, dp_d, dm_d)
        if rom is not None:
            rom.step(t, dp_r, dm_r)
            if rom.state in stop_rom_states:
                return t
        if dongle.state in until:
            return t
    return max_us
