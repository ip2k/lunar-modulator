"""Assemble dongle/firmware/usb_key.pio and run it in rp2040-pio-emulator to
obtain the per-cycle pin-direction waveforms the real hardware would produce."""
import pathlib
from collections import deque

import adafruit_pioasm
from pioemu import State, emulate

PIO_FILE = pathlib.Path(__file__).resolve().parents[1] / "firmware" / "usb_key.pio"

DATA_BIT = 0    # emulation pin index used for the OUT pin (data)
CLOCK_BIT = 1   # emulation pin index used for the SET pin (clock / D+)


def programs(path=PIO_FILE):
    """Return {name: source_text} for every .program in the file."""
    out, name, lines = {}, None, []
    for line in path.read_text().splitlines():
        if line.startswith(".program"):
            if name:
                out[name] = "\n".join(lines)
            name, lines = line.split()[1], [line]
        elif name:
            lines.append(line)
    if name:
        out[name] = "\n".join(lines)
    return out


def assemble(name):
    prog = adafruit_pioasm.Program(programs()[name])
    return list(prog.assembled), prog.pio_kwargs


def key_packet_waveform(key=0x16EF):
    """Emulate one packet. Returns a list of (clock_low, data_low) per PIO cycle."""
    opcodes, kw = assemble("usb_key")
    word = ((~key) & 0xFFFF) << 16
    wrap_top = len(opcodes) - 1
    gen = emulate(opcodes, stop_when=lambda o, s: False,
                  initial_state=State(transmit_fifo=deque([word])),
                  out_base=DATA_BIT, out_count=1, set_base=CLOCK_BIT, set_count=1,
                  shift_osr_right=False, pull_threshold=16,
                  wrap_target=0, wrap_top=wrap_top)
    events = []
    started = False
    for before, after in gen:
        events.append((before.clock, before.pin_directions, after.clock, after.pin_directions))
        if before.program_counter != 0:
            started = True
        # back at "pull block" with an empty FIFO: packet complete
        if started and after.program_counter == 0 and not after.transmit_fifo:
            break
        if after.clock > 2000:
            raise RuntimeError("usb_key emulation did not finish")
    return _per_cycle(events)


def sof_waveform(periods=3):
    """Emulate the sof_pulse program for a few periods. Returns [(dp_low,)] per cycle."""
    opcodes, kw = assemble("sof_pulse")
    wrap_top = len(opcodes) - 1
    gen = emulate(opcodes, stop_when=lambda o, s: False, initial_state=State(),
                  set_base=CLOCK_BIT, set_count=1, wrap_target=0, wrap_top=wrap_top)
    events = []
    wraps = 0
    for before, after in gen:
        events.append((before.clock, before.pin_directions, after.clock, after.pin_directions))
        if after.program_counter == 0 and before.program_counter == wrap_top:
            wraps += 1
            if wraps >= periods:
                break
        if after.clock > periods * 2000:
            raise RuntimeError("sof_pulse emulation did not finish")
    cycles = _per_cycle(events)
    return [(c[0],) for c in cycles]  # (dp_low,) — the SET pin is bit CLOCK_BIT


def _per_cycle(events):
    """Expand instruction events into one (clock_low, data_low) tuple per cycle.
    The pin directions set by an instruction take effect for the cycles it
    occupies (including its delay cycles)."""
    total = events[-1][2]
    dirs = [None] * total
    for c0, _d0, c1, d1 in events:
        for c in range(c0, min(c1, total)):
            dirs[c] = d1
    last = 0
    out = []
    for d in dirs:
        if d is None:
            d = last
        last = d
        out.append((bool(d >> CLOCK_BIT & 1), bool(d >> DATA_BIT & 1)))
    return out
