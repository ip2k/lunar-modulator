#!/usr/bin/env python3
"""Summarise one K1-K3 watchdog probe capture (firmware/wdtprobe).

Reads the raw UART log and the <log>.times.jsonl written by
`devkit_uart_capture.py --timestamps`. Each line is stamped with the arrival
time of the chunk holding its last byte. The beats' TIMER4 tick totals are
fitted against those host times: the slope is the tick rate, and 16 times it
is the oscillator (TIMER4 runs at OSC/16, as M6). The time from the probe's
ready line to the application's "system reset reason" line bounds the
watchdog period. Offline only: opens no device.
"""
import argparse
import json
from pathlib import Path
import re

BEAT = re.compile(r'LUNAR_WDTPROBE beat=(\d+) ticks=(\d+) loops=(\d+) wdt_con=(0x[0-9a-f]+)')
READY = re.compile(r'LUNAR_WDTPROBE ready=1 build=(\S+) mode=(\w+)')
RESET = re.compile(r'system reset reason:\s*(\w+)')
TIMER_DIVIDER = 16


def stamped_lines(raw, chunks):
    """[(text, arrival seconds)] for every complete line in `raw`."""
    ends = []
    for chunk in chunks:
        ends.append((chunk['offset'] + chunk['n'], chunk['t']))
    ends.sort()
    lines, start, k = [], 0, 0
    for i, byte in enumerate(raw):
        if byte != 0x0A:
            continue
        while k < len(ends) and ends[k][0] <= i:
            k += 1
        t = ends[k][1] if k < len(ends) else None
        lines.append((raw[start:i].decode('ascii', 'replace').strip('\r'), t))
        start = i + 1
    return lines


def fit(points):
    """Least-squares slope and intercept of y on x, and the largest residual."""
    n = len(points)
    if n < 2:
        return None
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    sxx = sum((x - mx) ** 2 for x, _ in points)
    if not sxx:
        return None
    slope = sum((x - mx) * (y - my) for x, y in points) / sxx
    intercept = my - slope * mx
    worst = max(abs(y - (slope * x + intercept)) for x, y in points)
    return slope, intercept, worst


def summarise(raw, chunks):
    lines = stamped_lines(raw, chunks)
    out = dict(lines=len(lines))
    ready = next(((m, t) for text, t in lines if (m := READY.search(text))), None)
    if ready:
        out.update(build=ready[0].group(1), mode=ready[0].group(2), t_ready=ready[1])
    for text, _ in lines:
        for key in ('clock', 'p33', 'wdt', 'mailbox', 'crumb a', 'crumb b',
                    'm5_pixels', 'disarm', 'alive', 'timer=stalled'):
            if text.startswith('LUNAR_WDTPROBE ' + key):
                out.setdefault('probe_lines', {})[key] = text
    beats = [(int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4), t)
             for text, t in lines if (m := BEAT.search(text))]
    out['beats'] = len(beats)
    if beats:
        last = beats[-1]
        out.update(last_beat=last[0], last_ticks=last[1], t_last_beat=last[4],
                   loops_per_beat=[min(b[2] for b in beats), max(b[2] for b in beats)],
                   wdt_con_seen=sorted({b[3] for b in beats}))
    timed = [(t, ticks) for _, ticks, _, _, t in beats if t is not None]
    result = fit(timed)
    if result:
        slope, _, worst = result
        out.update(tick_hz=round(slope, 1), oscillator_hz=round(slope * TIMER_DIVIDER),
                   fit_worst_ticks=round(worst, 1),
                   fit_worst_ms=round(worst / slope * 1000, 2) if slope else None)
    reset = next(((m, t) for text, t in lines if (m := RESET.search(text))), None)
    if reset:
        out.update(reset_reason=reset[0].group(1), t_reset_line=reset[1])
        if ready and ready[1] is not None and reset[1] is not None:
            out['seconds_ready_to_reset_line'] = round(reset[1] - ready[1], 3)
    return out


def load(raw_path, times_path):
    raw = Path(raw_path).read_bytes()
    chunks = [json.loads(line) for line in Path(times_path).read_text().splitlines() if line]
    return raw, chunks


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--raw', required=True, type=Path)
    ap.add_argument('--times', type=Path, help='default: <raw>.times.jsonl')
    a = ap.parse_args()
    raw_bytes, chunk_list = load(a.raw, a.times or a.raw.with_suffix('.times.jsonl'))
    print(json.dumps(summarise(raw_bytes, chunk_list), indent=2))
