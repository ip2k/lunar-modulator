"""M4 RAM test image logic, compiled natively against a recording register
model. Never touches pi32v2 MMIO or any device."""
import ctypes as c
from pathlib import Path
import subprocess

import pytest

READ = c.CFUNCTYPE(c.c_uint, c.c_void_p, c.c_uint, c.c_uint)
WRITE = c.CFUNCTYPE(None, c.c_void_p, c.c_uint, c.c_uint, c.c_uint)
SYNC = c.CFUNCTYPE(None, c.c_void_p)
PAUSE = c.CFUNCTYPE(None, c.c_void_p, c.c_uint)

UART1_CON0, UART1_BAUD, UART1_BUF = 0x12100, 0x12108, 0x1210C
P33_CON, P33_DAT = 0x13E08, 0x13E0C
MARKER = 0x01C7FD80
ALLOWED = ({0x12100, 0x12104, 0x12108, 0x1210C, 0x10010, 0x51020, 0x51028,
            0x50040, 0x50048, 0x5004C, 0x50050, 0x50054, P33_CON, P33_DAT}
           | {MARKER + i for i in range(0, 16, 4)})


class IO(c.Structure):
    _fields_ = [('context', c.c_void_p), ('read', READ), ('write', WRITE),
                ('sync', SYNC), ('pause', PAUSE), ('uart_failed', c.c_uint)]


@pytest.fixture(scope='module')
def lib(tmp_path_factory):
    root = Path(__file__).resolve().parents[1]
    out = tmp_path_factory.mktemp('ramtest') / 'ramtest.so'
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
                    str(root / 'firmware/ramtest/ramtest.c'), '-o', str(out)], check=True)
    library = c.CDLL(str(out))
    library.lunar_ramtest_baud.argtypes = [c.c_uint, c.c_uint, c.POINTER(c.c_uint)]
    library.lunar_ramtest_baud.restype = c.c_uint
    library.lunar_ramtest_run.argtypes = [c.POINTER(IO), c.c_char_p, c.c_uint, c.c_uint]
    library.lunar_ramtest_reset_to_app.argtypes = [c.POINTER(IO)]
    return library


class Chip:
    """Registers as a dict; the UART finishes each byte at once, P33 answers
    0x5a for P3_PR_PWR's current value and goes idle after `p33_busy_reads`."""

    def __init__(self, lib, *, marker_sticks=False, p33_busy_reads=1, p33_stuck=False,
                 uart_dead=False):
        self.lib, self.regs, self.trace, self.tx, self.p33 = lib, {}, [], bytearray(), []
        self.marker_sticks, self.p33_busy_reads, self.p33_stuck = marker_sticks, p33_busy_reads, p33_stuck
        self.busy, self.uart_dead = 0, uart_dead
        for i in range(0, 16, 4):
            self.regs[MARKER + i] = int.from_bytes(b'usb_update_mode\0'[i:i+4], 'little')
        self.pauses = []
        self.cb = READ(self.read), WRITE(self.write), SYNC(self.sync), PAUSE(self.pause)
        self.io = IO(None, *self.cb, 0)

    def read(self, _, address, width):
        assert address in ALLOWED, hex(address)
        self.trace.append(('r', address, width))
        if address == P33_CON and self.busy:
            if not self.p33_stuck:
                self.busy -= 1
            return self.regs.get(address, 0) | 2
        return self.regs.get(address, 0)

    def write(self, _, address, width, value):
        assert address in ALLOWED, hex(address)
        assert width in (1, 2, 4)
        self.trace.append(('w', address, width, value))
        if address == UART1_BUF:
            assert width == 1
            self.tx.append(value)
            if not self.uart_dead:
                self.regs[UART1_CON0] = self.regs.get(UART1_CON0, 0) | 0x8000
            return
        if address == UART1_CON0 and value & 0x2000:
            value &= ~0xA000
        if address == P33_CON and value & 0x10:
            self.p33.append(self.regs.get(P33_DAT, 0))
            self.busy = self.p33_busy_reads
            self.regs[P33_DAT] = 0x5A
            value &= ~0x10
        if address >= MARKER and self.marker_sticks:
            return
        self.regs[address] = value

    def sync(self, _):
        self.trace.append(('sync',))

    def pause(self, _, tenths):
        self.pauses.append(tenths)

    def run(self, build=b'abc123 2026-11-08', beats=3):
        return self.lib.lunar_ramtest_run(c.byref(self.io), build, 1234, beats)


@pytest.mark.parametrize('clock,baud,by3,value', [
    (48_000_000, 1_000_000, 1, 15),        # 48 % 4 = 0 >= 48 % 3 = 0
    (48_000_000, 115_200, 0, 103),          # div 416: 0 >= 2? no -> /4
    (48_000_000, 31_250, 1, 511),           # same rate as midi_uart.c's /4 383
])
def test_baud_follows_sdk_uart_init(lib, clock, baud, by3, value):
    flag = c.c_uint()
    got = lib.lunar_ramtest_baud(clock, baud, c.byref(flag))
    div = clock // baud
    expect_by3 = (div % 4) >= (div % 3)
    assert (flag.value, got) == (int(expect_by3), div // (3 if expect_by3 else 4) - 1)
    assert (flag.value, got) == (by3, value)


def test_baud_rejects_nonsense(lib):
    flag = c.c_uint()
    assert lib.lunar_ramtest_baud(1000, 0, c.byref(flag)) == 0
    assert lib.lunar_ramtest_baud(1000, 2000, c.byref(flag)) == 0
    assert lib.lunar_ramtest_baud(1000, 10, None) == 0


def test_run_prints_banner_beats_and_resets_last(lib):
    chip = Chip(lib)
    assert chip.run() == 4  # host: nothing resets, so LUNAR_RAMTEST_FAIL_NO_RESET
    text = chip.tx.decode()
    assert text.startswith('\r\nLUNAR_RAMTEST ready=1 build=abc123 2026-11-08 '
                           'entry=0x01c02000 bytes=1234 uart=uart1-pb3-1000000\r\n')
    assert 'LUNAR_RAMTEST beat=1\r\nLUNAR_RAMTEST beat=2\r\nLUNAR_RAMTEST beat=3\r\n' in text
    assert text.endswith('LUNAR_RAMTEST reset=app\r\nLUNAR_RAMTEST reset_failed=no_reset\r\n')
    # UART set up per uart_init: divide-by-3 bit, BAUD 15, then enable.
    writes = [t for t in chip.trace if t[0] == 'w']
    assert ('w', UART1_BAUD, 2, 15) in writes
    assert chip.regs[UART1_CON0] & 0x11 == 0x11
    assert chip.regs[0x10010] >> 10 & 3 == 1
    assert chip.regs[0x51020] >> 8 & 0xF == 1 and not chip.regs[0x51028] & 0x80
    assert chip.regs[0x50050] & 8 and chip.regs[0x50054] & 8
    assert not (chip.regs.get(0x50048, 0) | chip.regs.get(0x5004C, 0) | chip.regs.get(0x50040, 0)) & 8


def test_reset_clears_marker_then_reads_and_rewrites_pr_pwr(lib):
    chip = Chip(lib)
    chip.run(beats=0)
    assert all(chip.regs[MARKER + i] == 0 for i in range(0, 16, 4))
    # The SDK __cpu_reset: read P3_PR_PWR (0x80, 0xa0, dummy), then write it
    # back with bit 4 (0x00, 0xa0, value | 0x10).
    assert chip.p33 == [0x80, 0xA0, 0x5E, 0x00, 0xA0, 0x5A | 0x10]
    first_p33 = next(i for i, t in enumerate(chip.trace) if t[0] == 'w' and t[1] == P33_DAT)
    last_marker = max(i for i, t in enumerate(chip.trace) if t[0] == 'w' and t[1] >= MARKER)
    assert last_marker < first_p33
    assert not chip.regs[P33_CON] & 0x101  # deselected afterwards


def test_marker_that_will_not_clear_stops_before_p33(lib):
    chip = Chip(lib, marker_sticks=True)
    assert chip.run(beats=0) == 2
    assert chip.p33 == []
    assert chip.tx.decode().endswith('reset_failed=marker\r\n')


def test_stuck_p33_bus_is_bounded_and_reported(lib):
    chip = Chip(lib, p33_stuck=True)
    chip.busy = 1
    assert chip.run(beats=0) == 3
    assert chip.p33 == []
    assert chip.tx.decode().endswith('reset_failed=p33_busy\r\n')


def test_only_known_registers_are_touched(lib):
    chip = Chip(lib)
    chip.run(beats=2)
    touched = {t[1] for t in chip.trace if t[0] in 'rw'}
    assert touched <= ALLOWED
    # Nothing in the eFuse controller range or the mkey words audit_link guards.
    assert not any(0x13700 <= a <= 0x1371F or 0x01C80108 <= a <= 0x01C80110 for a in touched)


def test_dead_uart_costs_one_timeout_and_still_resets(lib):
    chip = Chip(lib, uart_dead=True)
    assert chip.run(beats=5) == 4
    assert len(chip.tx) == 1               # first byte only, then output skipped
    assert chip.io.uart_failed == 1
    assert chip.p33 == [0x80, 0xA0, 0x5E, 0x00, 0xA0, 0x5A | 0x10]
    polls = sum(1 for t in chip.trace if t[:2] == ('r', UART1_CON0))
    assert polls <= 200_000 + 50
