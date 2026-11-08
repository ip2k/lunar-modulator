"""Native fault simulation only; never invokes pi32v2 MMIO."""
import ctypes as c
from pathlib import Path
import subprocess
import pytest

READ = c.CFUNCTYPE(c.c_uint, c.c_void_p, c.c_int)
WRITE = c.CFUNCTYPE(None, c.c_void_p, c.c_int, c.c_uint)
SYNC = c.CFUNCTYPE(None, c.c_void_p)


class IO(c.Structure):
    _fields_ = [('context', c.c_void_p), ('read', READ), ('write', WRITE), ('sync', SYNC)]


class State(c.Structure):
    _fields_ = [('io', IO), ('ticks', c.c_uint), ('limit', c.c_uint),
                ('failed', c.c_uint), ('active', c.c_uint)]


@pytest.fixture(scope='module')
def lib(tmp_path_factory):
    root = Path(__file__).resolve().parents[1]
    output = tmp_path_factory.mktemp('timer') / 'timer.so'
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared',
                    '-fPIC', str(root / 'firmware/timing/timer4.c'), '-o', str(output)], check=True)
    library = c.CDLL(str(output))
    library.lunar_timer_bind.argtypes = [c.POINTER(State), c.POINTER(IO), c.c_uint, c.c_uint]
    library.lunar_timer_delay.argtypes = [c.POINTER(State), c.c_uint]
    return library


class Timer:
    def __init__(self, lib, stuck_clear=False, fail_period=None, initial=0, ready=4):
        self.lib = lib
        self.con = initial
        self.stuck_clear, self.fail_period, self.ready = stuck_clear, fail_period, ready
        self.trace, self.periods, self.polls = [], [], []
        self.count = 0
        self.callbacks = READ(self.read), WRITE(self.write), SYNC(self.sync)
        self.io, self.state = IO(None, *self.callbacks), State()
        assert lib.lunar_timer_bind(c.byref(self.state), c.byref(self.io), 24000000, 4)
        assert not self.trace

    def read(self, _, reg):
        self.trace.append(('read', reg))
        if self.con & 1 and self.polls:
            self.count += 1
            self.polls[-1] += 1
            if self.count >= self.ready and len(self.periods) != self.fail_period:
                self.con |= 1 << 15
        return self.con

    def write(self, _, reg, value):
        self.trace.append(('write', reg, value))
        if reg == 0:
            self.con = value
            if value & (1 << 14):
                self.con = (1 << 15) if self.stuck_clear else 0
            if value & 1:
                self.count = 0
                self.polls.append(0)
        elif reg == 2:
            self.periods.append(value)

    def sync(self, _):
        self.trace.append(('sync',))

    def delay(self, ms):
        return self.lib.lunar_timer_delay(c.byref(self.state), ms)


@pytest.mark.parametrize('ms', [1, 100, 120])
def test_panel_waits_use_one_shot_periods_and_last_allowed_read(lib, ms):
    timer = Timer(lib, initial=1 << 15)
    assert timer.delay(ms)
    assert timer.periods == [24000] * ms
    assert timer.polls == [4] * ms
    assert not timer.con
    assert not timer.state.failed and not timer.state.active
    resets = [e for e in timer.trace if e == ('write', 1, 0)]
    assert len(resets) == ms
    assert timer.delay(1)  # Success remains reusable.


def test_stale_completion_cannot_masquerade_as_elapsed_time(lib):
    timer = Timer(lib, stuck_clear=True)
    assert not timer.delay(100)
    assert not timer.periods
    assert sum(e[0] == 'read' for e in timer.trace) == 5
    assert not timer.con and timer.state.failed


@pytest.mark.parametrize('period', [1, 50, 120])
def test_timer_timeout_stops_and_latches_without_later_periods(lib, period):
    timer = Timer(lib, fail_period=period)
    assert not timer.delay(120)
    assert len(timer.periods) == period
    assert timer.polls[-1] == 4
    assert not timer.con and timer.state.failed and not timer.state.active
    trace = timer.trace[:]
    assert not timer.delay(1)
    assert trace == timer.trace


@pytest.mark.parametrize('initial', [1, 2, 3, 9])
def test_enabled_timer_is_not_taken_over(lib, initial):
    timer = Timer(lib, initial=initial)
    assert not timer.delay(1)
    assert timer.con == initial
    assert timer.state.failed
    assert timer.trace == [('read', 0)]


def test_zero_invalid_and_reentrant_requests_have_no_io(lib):
    timer = Timer(lib)
    assert timer.delay(0)
    assert not timer.delay(1001)
    timer.state.active = 1
    assert not timer.delay(1)
    assert not lib.lunar_timer_delay(None, 1)
    assert not lib.lunar_timer_delay(c.byref(State()), 1)
    assert not timer.trace


@pytest.mark.parametrize('hz,limit', [(0, 4), (999999, 4), (40001000, 4),
                                     (24000001, 4), (24000000, 0), (24000000, 65537)])
def test_binding_rejects_unrepresentable_rates_and_unbounded_polling(lib, hz, limit):
    timer = Timer(lib)
    assert not lib.lunar_timer_bind(c.byref(timer.state), c.byref(timer.io), hz, limit)
    assert not timer.trace


@pytest.mark.parametrize('hz', [1000000, 24000000, 32000000, 40000000])
def test_verified_oscillator_rates_produce_complete_panel_sleep_out_wait(lib, hz):
    timer = Timer(lib)
    assert lib.lunar_timer_bind(c.byref(timer.state), c.byref(timer.io), hz, 4)
    assert not timer.trace
    assert timer.delay(120)
    assert timer.periods == [hz // 1000] * 120
    assert timer.polls == [4] * 120
    assert not timer.con and not timer.state.failed
