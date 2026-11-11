#!/usr/bin/env python3
"""Receive-only Tigard UART capture; suitable for nohup on bench01.

Uses pyserial, exclusive access, 1 Mbaud 8N1, no flow control, DTR/RTS low.
Never sends serial data. Records capture lifecycle separately from raw bytes.
With --timestamps it also writes <out>.times.jsonl: one line per chunk read,
{"t": host monotonic seconds since armed, "offset": first byte, "n": bytes},
read as soon as one byte is waiting, so the times carry only the USB
adapter's latency (tools/devkit_wdtprobe_report.py fits them).
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

import serial

PORT = '/dev/serial/by-id/usb-SecuringHardware.com_Tigard_V1.1_TG1108fc-if00-port0'


def capture(out, seconds, timestamps=False, open_serial=serial.Serial):
    if not 1 <= seconds <= 3600:
        raise ValueError('Capture duration must be 1..3600 seconds')
    meta = out.with_suffix('.json')
    times_path = out.with_suffix('.times.jsonl')
    # Exclusive creation preserves every prior capture, including its metadata.
    with out.open('xb') as fp, meta.open('x') as info, \
            (times_path.open('x') if timestamps else open(os.devnull, 'w')) as times:
        os.chmod(out, 0o600)
        os.chmod(meta, 0o600)
        if timestamps:
            os.chmod(times_path, 0o600)
        state = dict(port=PORT, baud=1000000, receive_only=True, bytes=0,
                     duration_seconds=seconds, status='opening', timestamps=timestamps)
        def record():
            info.seek(0)
            info.write(json.dumps(state, indent=2)+'\n')
            info.truncate()
            info.flush()
            os.fsync(info.fileno())
        record()
        uart = open_serial(port=None, baudrate=1000000,
                           timeout=0.02 if timestamps else 0.25, exclusive=True)
        uart.dtr = False
        uart.rts = False
        uart.port = PORT
        try:
            uart.open()
            state.update(status='armed', started_utc=datetime.now(timezone.utc).isoformat())
            record()
            print('UART armed, receive-only', flush=True)
            armed = synced = time.monotonic()
            end = armed+seconds
            while time.monotonic() < end:
                # Timestamped: return on the first waiting byte, not after
                # 4096 bytes or the timeout, so each chunk is stamped on arrival.
                data = uart.read(max(1, uart.in_waiting) if timestamps else 4096)
                if data:
                    now = time.monotonic()
                    if timestamps:
                        times.write(json.dumps(dict(t=round(now-armed, 6),
                                                    offset=state['bytes'], n=len(data)))+'\n')
                        times.flush()
                    fp.write(data)
                    fp.flush()
                    state['bytes'] += len(data)
                    # fsync after every chunk would delay the next chunk's
                    # stamp, so timestamped captures sync at most once a second.
                    if not timestamps or now - synced >= 1.0:
                        os.fsync(fp.fileno())
                        record()
                        synced = now
            os.fsync(fp.fileno())
            state['status'] = 'complete'
        except BaseException as exc:
            state.update(status='error', error=str(exc))
            raise
        finally:
            uart.close()
            state['ended_utc'] = datetime.now(timezone.utc).isoformat()
            record()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--seconds', type=int, default=3600)
    ap.add_argument('--timestamps', action='store_true',
                    help='also write <out>.times.jsonl with per-chunk arrival times')
    a = ap.parse_args()
    capture(a.out, a.seconds, a.timestamps)
