"""K1-K3 watchdog probe image logic, compiled natively against a recording
register model with a P33 frame decoder and a virtual TIMER4. Never touches
pi32v2 MMIO or any device."""
import ctypes as c
from pathlib import Path
import re
import subprocess

import pytest

READ = c.CFUNCTYPE(c.c_uint, c.c_void_p, c.c_uint, c.c_uint)
WRITE = c.CFUNCTYPE(None, c.c_void_p, c.c_uint, c.c_uint, c.c_uint)
SYNC = c.CFUNCTYPE(None, c.c_void_p)
PAUSE = c.CFUNCTYPE(None, c.c_void_p, c.c_uint)

UART1_CON0, UART1_BUF = 0x12100, 0x1210C
P33_CON, P33_DAT = 0x13E08, 0x13E0C
TIMER_CON, TIMER_CNT, TIMER_PRD = 0x10800, 0x10804, 0x10808
CLOCKS = [0x10000, 0x10008, 0x1000C, 0x10010, 0x10014, 0x10018,
          0x119A0, 0x119A4, 0x119A8, 0x119AC]
SYS_RST_SRC = 0x100C0
MARKER, CRUMB_A, CRUMB_B = 0x01C7FD80, 0x01C07C00, 0x01C7C000
MAGIC = 0x5444574C
MARKER_WORDS = [int.from_bytes(b'usb_update_mode\0'[i:i + 4], 'little') for i in range(0, 16, 4)]
WDT_CON, VLD_KEEP, RST_SRC, PR_PWR = 0x80, 0x17, 0x12, 0xA0
RAMTEST_UART = {0x12100, 0x12104, 0x12108, 0x1210C, 0x10010, 0x51020, 0x51028,
                0x50040, 0x50048, 0x5004C, 0x50050, 0x50054}
ALLOWED = (RAMTEST_UART | {P33_CON, P33_DAT, TIMER_CON, TIMER_CNT, TIMER_PRD, SYS_RST_SRC}
           | set(CLOCKS)
           | {base + i for base in (MARKER, CRUMB_A, CRUMB_B) for i in range(0, 16, 4)})
READ_MODE, KICK_MODE, DISARM_MODE, MAILBOX_MODE = 1, 2, 3, 4
NO_RESET, FAIL_P33, FAIL_TIMER = 4, 2, 3


class IO(c.Structure):
    _fields_ = [('context', c.c_void_p), ('read', READ), ('write', WRITE),
                ('sync', SYNC), ('pause', PAUSE), ('uart_failed', c.c_uint)]


@pytest.fixture(scope='module')
def lib(tmp_path_factory):
    root = Path(__file__).resolve().parents[1]
    out = tmp_path_factory.mktemp('wdtprobe') / 'wdtprobe.so'
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
                    str(root / 'firmware/wdtprobe/wdtprobe.c'),
                    str(root / 'firmware/ramtest/ramtest.c'),
                    str(root / 'firmware/display/m5_pattern.c'),
                    str(root / 'firmware/display/panel_probe.c'),
                    '-o', str(out)], check=True)
    library = c.CDLL(str(out))
    library.lunar_wdtprobe_run.argtypes = [c.POINTER(IO), c.c_uint, c.c_char_p, c.c_uint, c.c_uint]
    library.lunar_wdtprobe_p33_read.argtypes = [c.POINTER(IO), c.c_uint, c.POINTER(c.c_uint)]
    library.lunar_wdtprobe_p33_write.argtypes = [c.POINTER(IO), c.c_uint, c.c_uint]
    library.lunar_wdtprobe_ticks_between.argtypes = [c.c_uint, c.c_uint]
    library.lunar_wdtprobe_ticks_between.restype = c.c_uint
    return library


class Chip:
    """SFRs and SRAM words as a dict. P33 frames are decoded: three bytes per
    select; a first byte with bit 7 reads the P33 register (the reply lands
    in DAT on the third byte), otherwise the third byte is written. TIMER4
    counts `step` ticks per CNT read while CON bit 0 is set."""

    def __init__(self, lib, *, wdt=0x1C, marker=True, crumbs=False, step=997,
                 p33_stuck=False):
        self.lib, self.regs, self.trace, self.tx = lib, {}, [], bytearray()
        self.p33 = {WDT_CON: wdt, VLD_KEEP: 0x40, RST_SRC: 0x41, PR_PWR: 0x5A}
        self.frames, self.frame, self.selected = [], [], False
        self.step, self.virtual, self.p33_stuck = step, 0, p33_stuck
        for i, address in enumerate(CLOCKS):
            self.regs[address] = 0x100 + i
        self.regs[0x1000C] = 0x1C1
        self.regs[SYS_RST_SRC] = 0x10
        if marker:
            for i, word in enumerate(MARKER_WORDS):
                self.regs[MARKER + 4 * i] = word
        if crumbs:
            for base in (CRUMB_A, CRUMB_B):
                for i, word in enumerate([MAGIC, 4, 0x1C, ~MAGIC & 0xFFFFFFFF]):
                    self.regs[base + 4 * i] = word
        self.cb = READ(self.read), WRITE(self.write), SYNC(self.sync), PAUSE(self.pause)
        self.io = IO(None, *self.cb, 0)

    def read(self, _, address, width):
        assert address in ALLOWED, hex(address)
        self.trace.append(('r', address, width))
        if address == P33_CON and self.p33_stuck:
            return self.regs.get(address, 0) | 2
        if address == TIMER_CNT:
            if self.regs.get(TIMER_CON, 0) & 1:
                self.virtual += self.step
            return self.virtual % (self.regs.get(TIMER_PRD, 0x7FFF) + 1)
        return self.regs.get(address, 0)

    def write(self, _, address, width, value):
        assert address in ALLOWED, hex(address)
        assert width in (1, 2, 4)
        self.trace.append(('w', address, width, value))
        if address == UART1_BUF:
            self.tx.append(value)
            self.regs[UART1_CON0] = self.regs.get(UART1_CON0, 0) | 0x8000
            return
        if address == UART1_CON0 and value & 0x2000:
            value &= ~0xA000
        if address == P33_CON:
            if value & 1 and not self.selected:
                self.frame = []
            if not value & 1 and self.selected:
                self.frames.append(tuple(self.frame))
            self.selected = bool(value & 1)
            if value & 0x10:
                self.byte(self.regs.get(P33_DAT, 0) & 0xFF)
                value &= ~0x10
        if address == TIMER_CNT:
            self.virtual = value
        self.regs[address] = value

    def byte(self, value):
        assert self.selected, 'P33 byte outside a select'
        self.frame.append(value)
        reply = 0
        if len(self.frame) == 3:
            first, addr = self.frame[0], ((self.frame[0] & 3) << 8) | self.frame[1]
            if first & 0x80:
                reply = self.p33.get(addr, 0)
            else:
                self.p33[addr] = value
        self.regs[P33_DAT] = reply

    def sync(self, _):
        self.trace.append(('sync',))

    def pause(self, _, tenths):
        self.trace.append(('pause', tenths))

    def run(self, mode, beats=4, build=b'wdtprobe-1-read'):
        return self.lib.lunar_wdtprobe_run(c.byref(self.io), mode, build, 2345, beats)

    def text(self):
        return self.tx.decode()

    def writes_to(self, addr):
        return [f[2] for f in self.frames if len(f) == 3 and not f[0] & 0x80
                and ((f[0] & 3) << 8 | f[1]) == addr]

    def reads_of(self, addr):
        return [f for f in self.frames if len(f) == 3 and f[0] & 0x80
                and ((f[0] & 3) << 8 | f[1]) == addr]

    def words(self, base):
        return [self.regs.get(base + 4 * i, 0) for i in range(4)]


def test_ticks_between_is_wrap_safe(lib):
    assert lib.lunar_wdtprobe_ticks_between(100, 300) == 200
    assert lib.lunar_wdtprobe_ticks_between(0x7F00, 0x0100) == 0x200
    assert lib.lunar_wdtprobe_ticks_between(5, 5) == 0
    assert lib.lunar_wdtprobe_ticks_between(0x8000 + 7, 9) == 2   # reduced first


def test_p33_read_frame_is_read_only(lib):
    chip = Chip(lib, wdt=0x3C)
    value = c.c_uint()
    assert lib.lunar_wdtprobe_p33_read(c.byref(chip.io), WDT_CON, c.byref(value)) == 1
    assert value.value == 0x3C
    assert chip.frames == [(0x80, 0x80, 0x5E)]
    assert chip.p33[WDT_CON] == 0x3C
    assert not chip.regs[P33_CON] & 0x101


def test_p33_rejects_addresses_beyond_ten_bits(lib):
    chip = Chip(lib)
    value = c.c_uint()
    assert lib.lunar_wdtprobe_p33_read(c.byref(chip.io), 0x400, c.byref(value)) == 0
    assert lib.lunar_wdtprobe_p33_write(c.byref(chip.io), 0x400, 0) == 0
    assert chip.frames == []


def test_read_mode_reports_then_beats_without_kicking(lib):
    chip = Chip(lib, crumbs=True)
    assert chip.run(READ_MODE, beats=4) == NO_RESET
    text = chip.text()
    assert text.startswith('\r\nLUNAR_WDTPROBE ready=1 build=wdtprobe-1-read mode=read '
                           'entry=0x01c02000 bytes=2345\r\n')
    assert ' clk_con0=0x000001c1 ' in text and ' pll2_con1=0x00000109 ' in text
    assert ('LUNAR_WDTPROBE p33 ok=1 wdt_con=0x0000001c vld_keep=0x00000040 '
            'rst_src=0x00000041 pr_pwr=0x0000005a sys_rst_src=0x00000010\r\n') in text
    assert 'LUNAR_WDTPROBE wdt armed=1 code=12 interrupt=0 expt_en=1\r\n' in text
    assert 'LUNAR_WDTPROBE mailbox usb_update_mode=1 0x5f627375 ' in text
    assert 'LUNAR_WDTPROBE crumb a=0x01c07c00 valid=1 0x5444574c 0x00000004' in text
    assert 'LUNAR_WDTPROBE crumb b=0x01c7c000 valid=1 ' in text
    beats = re.findall(r'beat=(\d+) ticks=(\d+) loops=(\d+) wdt_con=(0x[0-9a-f]+)', text)
    assert [int(b[0]) for b in beats] == [1, 2, 3, 4]
    assert all(int(t) >= 150_000 * int(b) for b, t, _, _ in beats)
    assert all(w == '0x0000001c' for *_, w in beats)
    assert text.endswith('LUNAR_WDTPROBE reset=app\r\nLUNAR_WDTPROBE reset_failed=no_reset\r\n')
    # Never a P33 write to the watchdog; the only write frame is the reset.
    assert chip.writes_to(WDT_CON) == []
    assert chip.writes_to(PR_PWR) == [0x5A | 0x10]
    assert chip.frames[-1] == (0x00, 0xA0, 0x5A | 0x10)
    assert chip.words(MARKER) == chip.words(CRUMB_A) == chip.words(CRUMB_B) == [0] * 4


def test_snapshot_reads_come_before_any_setup_write(lib):
    chip = Chip(lib)
    chip.run(READ_MODE, beats=1)
    first_write = next(i for i, t in enumerate(chip.trace)
                       if t[0] == 'w' and t[1] not in (P33_CON, P33_DAT))
    for address in CLOCKS + [SYS_RST_SRC, TIMER_CON, MARKER, CRUMB_A, CRUMB_B]:
        first_read = next(i for i, t in enumerate(chip.trace) if t[:2] == ('r', address))
        assert first_read < first_write, hex(address)
    # The four P33 registers are read, in order, before that write as well.
    early = chip.frames[:4]
    assert early == [(0x80, WDT_CON, 0x5E), (0x80, VLD_KEEP, 0x5E),
                     (0x80, RST_SRC, 0x5E), (0x80, PR_PWR, 0x5E)]


def test_unarmed_watchdog_is_reported_and_left_alone(lib):
    chip = Chip(lib, wdt=0x0B, marker=False)
    chip.run(READ_MODE, beats=2)
    text = chip.text()
    assert 'wdt armed=0 code=11 ' in text
    assert 'mailbox usb_update_mode=0 ' in text
    assert 'crumb a=0x01c07c00 valid=0 ' in text
    assert chip.writes_to(WDT_CON) == []


def test_stopwatch_takes_timer4_like_m6(lib):
    chip = Chip(lib)
    chip.run(READ_MODE, beats=1)
    timer_writes = [t for t in chip.trace if t[0] == 'w' and t[1] in (TIMER_CON, TIMER_CNT, TIMER_PRD)]
    assert timer_writes == [('w', TIMER_CON, 4, 0x4000), ('w', TIMER_CNT, 4, 0),
                            ('w', TIMER_PRD, 4, 0x7FFF), ('w', TIMER_CON, 4, 0x29)]


def test_stalled_timer_fails_safe_to_the_app(lib):
    chip = Chip(lib, step=0)
    assert chip.run(READ_MODE, beats=3) == FAIL_TIMER
    text = chip.text()
    assert 'LUNAR_WDTPROBE timer=stalled ticks=0\r\n' in text
    assert 'beat=' not in text
    assert chip.writes_to(PR_PWR) == [0x5A | 0x10]
    assert chip.words(MARKER) == [0] * 4


def test_kick_mode_kicks_every_beat_and_times_the_pixels(lib):
    chip = Chip(lib)
    assert chip.run(KICK_MODE, beats=3, build=b'wdtprobe-1-kick') == NO_RESET
    text = chip.text()
    beats = re.findall(r'beat=(\d+) .* wdt_con=(0x[0-9a-f]+)', text)
    assert [b for b, _ in beats] == ['1', '2', '3']
    m = re.search(r'LUNAR_WDTPROBE m5_pixels=57600 ticks=(\d+) kick240_ticks=(\d+) '
                  r'mix=0x[0-9a-f]{8}\r\n', text)
    assert m and int(m.group(1)) > 0 and int(m.group(2)) > 0
    # One kick per beat, one per pixel row, then 240 alone: wdt_clear sets bit 6.
    assert chip.writes_to(WDT_CON) == [0x1C | 0x40] * (3 + 240 + 240)
    assert text.endswith('LUNAR_WDTPROBE reset=app\r\nLUNAR_WDTPROBE reset_failed=no_reset\r\n')
    assert chip.words(MARKER) == [0] * 4


def test_kick_mode_pixel_mix_matches_the_m5_pattern(lib):
    lib.lunar_m5_pixel.argtypes = [c.c_uint, c.c_uint, c.c_char_p]
    lib.lunar_m5_pixel.restype = c.c_uint
    mix = 0
    for y in range(240):
        for x in range(240):
            mix = ((mix * 31) & 0xFFFFFFFF) ^ lib.lunar_m5_pixel(x, y, b'wdtprobe-1-kick')
    chip = Chip(lib)
    chip.run(KICK_MODE, beats=1, build=b'wdtprobe-1-kick')
    assert f'mix=0x{mix:08x}\r\n' in chip.text()


def test_disarm_mode_writes_code_b_sets_marker_and_resets_to_uboot(lib):
    chip = Chip(lib)
    assert chip.run(DISARM_MODE, build=b'wdtprobe-1-disarm') == NO_RESET
    text = chip.text()
    assert chip.writes_to(WDT_CON) == [0x0B]
    assert chip.p33[WDT_CON] == 0x0B
    assert 'LUNAR_WDTPROBE disarm wdt_con=0x0000000b\r\n' in text
    assert chip.words(MARKER) == MARKER_WORDS
    for base in (CRUMB_A, CRUMB_B):
        assert chip.words(base) == [MAGIC, DISARM_MODE, 0x1C, ~MAGIC & 0xFFFFFFFF]
    assert chip.writes_to(PR_PWR) == [0x5A | 0x10]
    assert 'beat=' not in text
    assert text.endswith('LUNAR_WDTPROBE reset=uboot\r\nLUNAR_WDTPROBE reset_failed=no_reset\r\n')
    # The marker is the last SRAM write before the reset frame, and never cleared.
    marker_writes = [t for t in chip.trace if t[0] == 'w' and MARKER <= t[1] < MARKER + 16]
    assert [t[3] for t in marker_writes] == MARKER_WORDS


def test_mailbox_mode_with_armed_watchdog_never_writes_it(lib):
    chip = Chip(lib, marker=False)
    chip.run(MAILBOX_MODE, beats=3, build=b'wdtprobe-1-mailbox')
    text = chip.text()
    assert 'armed_by_probe' not in text
    assert 'LUNAR_WDTPROBE mailbox=set waiting_for_wdt=1\r\n' in text
    assert chip.writes_to(WDT_CON) == []
    marker_writes = [t[3] for t in chip.trace if t[0] == 'w' and MARKER <= t[1] < MARKER + 16]
    # Set before the beats; the host watchdog never fires, so the fallback
    # clears it and resets to the application.
    assert marker_writes == MARKER_WORDS + [0, 0, 0, 0]
    assert chip.words(CRUMB_A) == [MAGIC, MAILBOX_MODE, 0x1C, ~MAGIC & 0xFFFFFFFF]
    assert chip.words(CRUMB_B) == chip.words(CRUMB_A)
    assert len(re.findall(r'beat=\d+ ', text)) == 3
    assert chip.writes_to(PR_PWR) == [0x5A | 0x10]


def test_mailbox_mode_arms_an_unarmed_watchdog_for_4s_reset(lib):
    chip = Chip(lib, wdt=0x00)
    chip.run(MAILBOX_MODE, beats=1, build=b'wdtprobe-1-mailbox')
    assert chip.writes_to(WDT_CON) == [0x1C]
    assert 'LUNAR_WDTPROBE armed_by_probe=1 wdt_con=0x0000001c\r\n' in chip.text()


def test_dead_p33_bus_writes_nothing_and_fails(lib):
    chip = Chip(lib, p33_stuck=True)
    result = chip.run(MAILBOX_MODE, beats=2)
    text = chip.text()
    assert result == FAIL_P33
    assert 'p33 ok=0 wdt_con=0xffffffff ' in text
    assert 'wdt armed=9 ' in text
    assert chip.frames == []
    assert chip.words(MARKER) == [0] * 4   # reset_to_app clears it before the bus check
    assert not any(t[0] == 'w' and CRUMB_A <= t[1] < CRUMB_A + 16 for t in chip.trace)


@pytest.mark.parametrize('mode', [READ_MODE, KICK_MODE, DISARM_MODE, MAILBOX_MODE])
def test_only_known_registers_are_touched(lib, mode):
    chip = Chip(lib, wdt=0x00)
    chip.run(mode, beats=2)
    touched = {t[1] for t in chip.trace if t[0] in 'rw'}
    assert touched <= ALLOWED
    # Nothing in the eFuse controller range or the mkey words audit_link guards.
    assert not any(0x13700 <= a <= 0x1371F or 0x01C80108 <= a <= 0x01C80110 for a in touched)
    # P33 registers written: the watchdog and the reset bit only.
    written = {(f[0] & 3) << 8 | f[1] for f in chip.frames if not f[0] & 0x80}
    assert written <= {WDT_CON, PR_PWR}


def test_bad_mode_is_refused_before_any_access(lib):
    chip = Chip(lib)
    assert chip.run(0) == 1 and chip.run(5) == 1
    assert chip.trace == []
