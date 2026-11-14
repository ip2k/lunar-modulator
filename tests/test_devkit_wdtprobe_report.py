"""The timestamped receive-only UART capture and the watchdog probe report,
against a fake serial port and synthetic logs. No device is opened."""
import json
import random

import pytest

from tools import devkit_uart_capture as cap
from tools import devkit_wdtprobe_report as rep


class FakeSerial:
    """Hands out queued chunks; any attempt to send fails the test."""

    def __init__(self, chunks, **kwargs):
        self.chunks, self.kwargs, self.opened, self.closed = list(chunks), kwargs, False, False
        self.dtr = self.rts = True

    def open(self):
        self.opened = True

    @property
    def in_waiting(self):
        return len(self.chunks[0]) if self.chunks else 0

    def read(self, size):
        if not self.chunks:
            return b''
        chunk = self.chunks.pop(0)
        assert len(chunk) <= size
        return chunk

    def write(self, data):
        raise AssertionError('capture must never send')

    def close(self):
        self.closed = True


def run_capture(tmp_path, chunks, timestamps):
    made = []

    def factory(**kwargs):
        made.append(FakeSerial(chunks, **kwargs))
        return made[0]
    out = tmp_path / 'uart.log'
    cap.capture(out, 1, timestamps=timestamps, open_serial=factory)
    return out, made[0]


def test_timestamped_capture_stamps_each_chunk_and_stays_receive_only(tmp_path):
    chunks = [b'LUNAR_WDTPROBE ready=1\r\n', b'beat=1', b'\r\n']
    out, port = run_capture(tmp_path, chunks, True)
    assert out.read_bytes() == b''.join(chunks)
    times = [json.loads(line) for line in out.with_suffix('.times.jsonl').read_text().splitlines()]
    assert [(t['offset'], t['n']) for t in times] == [(0, 24), (24, 6), (30, 2)]
    assert all(b['t'] >= a['t'] for a, b in zip(times, times[1:]))
    meta = json.loads(out.with_suffix('.json').read_text())
    assert meta['status'] == 'complete' and meta['bytes'] == 32 and meta['timestamps'] is True
    assert port.kwargs['timeout'] <= 0.05 and port.kwargs['exclusive'] is True
    assert port.dtr is False and port.rts is False and port.closed
    assert oct(out.with_suffix('.times.jsonl').stat().st_mode & 0o777) == '0o600'


def test_plain_capture_writes_no_times_file(tmp_path):
    out, port = run_capture(tmp_path, [b'abc'], False)
    assert out.read_bytes() == b'abc'
    assert not out.with_suffix('.times.jsonl').exists()
    assert port.kwargs['timeout'] == 0.25


def test_capture_never_overwrites_a_times_file(tmp_path):
    (tmp_path / 'uart.times.jsonl').write_text('kept\n')
    with pytest.raises(FileExistsError):
        run_capture(tmp_path, [b'x'], True)
    assert (tmp_path / 'uart.times.jsonl').read_text() == 'kept\n'


def synthetic(osc_hz=24_000_000, beats=30, reset_after=None, jitter=0.004, seed=7):
    """A probe log as the kit would print it, chunked by line, with host
    arrival times at the true tick rate plus up to `jitter` s of USB delay."""
    rng = random.Random(seed)
    tick_hz = osc_hz / 16
    lines = [(b'LUNAR_WDTPROBE ready=1 build=wdtprobe-1-read mode=read entry=0x01c02000 bytes=3000', 0.0),
             (b'LUNAR_WDTPROBE wdt armed=1 code=12 interrupt=0 expt_en=0', 0.0005)]
    start = 0.002
    for beat in range(1, beats + 1):
        ticks = 150_000 * beat + rng.randrange(0, 900)
        t = start + ticks / tick_hz
        if reset_after is not None and t > reset_after:
            break
        lines.append((f'LUNAR_WDTPROBE beat={beat} ticks={ticks} loops=4100 '
                      f'wdt_con=0x0000001c'.encode(), t))
    if reset_after is not None:
        lines.append((b'[00:00:00.100]========= system reset reason: WDT =========', reset_after + 0.1))
    raw, chunks, offset = b'', [], 0
    for text, t in lines:
        data = text + b'\r\n'
        chunks.append(dict(t=round(10 + t + rng.uniform(0, jitter), 6), offset=offset, n=len(data)))
        raw += data
        offset += len(data)
    return raw, chunks


def test_report_recovers_a_24mhz_oscillator_and_the_reset(tmp_path):
    raw, chunks = synthetic(beats=60, reset_after=4.0)
    out = rep.summarise(raw, chunks)
    assert out['build'] == 'wdtprobe-1-read' and out['mode'] == 'read'
    assert out['last_beat'] == 39            # 3.998 s at 100 ms a beat
    assert abs(out['oscillator_hz'] - 24_000_000) < 24_000_000 * 0.003
    assert out['reset_reason'] == 'WDT'
    assert 4.0 <= out['seconds_ready_to_reset_line'] <= 4.2
    assert out['wdt_con_seen'] == ['0x0000001c']
    assert out['probe_lines']['wdt'].startswith('LUNAR_WDTPROBE wdt armed=1')


def test_report_tells_40mhz_from_24mhz():
    raw, chunks = synthetic(osc_hz=40_000_000, beats=50)
    out = rep.summarise(raw, chunks)
    assert abs(out['oscillator_hz'] - 40_000_000) < 40_000_000 * 0.003
    assert 'reset_reason' not in out


def test_line_split_across_chunks_takes_the_later_time():
    raw = b'LUNAR_WDTPROBE beat=1 ticks=150000 loops=1 wdt_con=0x0000001c\r\n'
    chunks = [dict(t=1.0, offset=0, n=10), dict(t=1.5, offset=10, n=len(raw) - 10)]
    assert rep.stamped_lines(raw, chunks) == [(raw.decode().strip(), 1.5)]


def test_report_without_beats_has_no_fit():
    out = rep.summarise(b'LUNAR_WDTPROBE ready=1 build=x mode=disarm\r\n',
                        [dict(t=0.1, offset=0, n=44)])
    assert out['beats'] == 0 and 'oscillator_hz' not in out
