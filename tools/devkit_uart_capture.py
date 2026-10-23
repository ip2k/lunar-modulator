#!/usr/bin/env python3
"""Receive-only Tigard UART capture; suitable for nohup on bench01.

Uses pyserial, exclusive access, 1 Mbaud 8N1, no flow control, DTR/RTS low.
Never sends serial data. Records capture lifecycle separately from raw bytes.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

import serial

PORT = '/dev/serial/by-id/usb-SecuringHardware.com_Tigard_V1.1_TG1108fc-if00-port0'


def capture(out, seconds):
    if not 1 <= seconds <= 3600:
        raise ValueError('Capture duration must be 1..3600 seconds')
    meta = out.with_suffix('.json')
    # Exclusive creation preserves every prior capture, including its metadata.
    with out.open('xb') as fp, meta.open('x') as info:
        os.chmod(out, 0o600)
        os.chmod(meta, 0o600)
        state = dict(port=PORT, baud=1000000, receive_only=True, bytes=0,
                     duration_seconds=seconds, status='opening')
        def record():
            info.seek(0)
            info.write(json.dumps(state, indent=2)+'\n')
            info.truncate()
            info.flush()
            os.fsync(info.fileno())
        record()
        uart = serial.Serial(port=None, baudrate=1000000, timeout=0.25, exclusive=True)
        uart.dtr = False
        uart.rts = False
        uart.port = PORT
        try:
            uart.open()
            state.update(status='armed', started_utc=datetime.now(timezone.utc).isoformat())
            record()
            print('UART armed, receive-only', flush=True)
            end = time.monotonic()+seconds
            while time.monotonic() < end:
                data = uart.read(4096)
                if data:
                    fp.write(data)
                    fp.flush()
                    os.fsync(fp.fileno())
                    state['bytes'] += len(data)
                    record()
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
    a = ap.parse_args()
    capture(a.out, a.seconds)
