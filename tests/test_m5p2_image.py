"""m5-plan-2 image logic (firmware/m5p2), compiled natively against a
recording register model with a P33 frame decoder, a virtual TIMER4, an
SPI1/PORTC byte decoder and a cycle-cost clock. Never touches pi32v2 MMIO or
any device.

Time model: every register access costs ACCESS cycles, every P33 byte P33
more, every spin iteration SPIN; TIMER4 counts osc/16 of the elapsed cycles.
In a tight TIMER4 poll loop the model jumps STEP ticks per read (at most
STEP ticks of overshoot per wait slice) so a test runs in seconds. The kick
gap is measured between watchdog clear frames, in modelled cycles, and
converted to seconds at the modelled CPU clock."""
import ctypes as c
from functools import lru_cache
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
READ = c.CFUNCTYPE(c.c_uint, c.c_void_p, c.c_uint, c.c_uint)
WRITE = c.CFUNCTYPE(None, c.c_void_p, c.c_uint, c.c_uint, c.c_uint)
SYNC = c.CFUNCTYPE(None, c.c_void_p)
PAUSE = c.CFUNCTYPE(None, c.c_void_p, c.c_uint)
SPIN = c.CFUNCTYPE(None, c.c_void_p, c.c_uint)

P33_CON, P33_DAT = 0x13E08, 0x13E0C
TIMER_CON, TIMER_CNT, TIMER_PRD = 0x10800, 0x10804, 0x10808
SPI_CON, SPI_BAUD, SPI_BUF = 0x11D00, 0x11D04, 0x11D08
PORTC_OUT, PORTC_DIR, IOMAP_CON1 = 0x50080, 0x50088, 0x51020
PORT_A, PORT_B, PORT_H = 0x50000, 0x50040, 0x501C0
PORTS = {base + 4 * i for base in (PORT_A, PORT_B, PORT_H) for i in range(9)}
UART = {0x12100, 0x12104, 0x12108, 0x1210C, 0x10010, IOMAP_CON1, 0x51028,
        0x50040, 0x50048, 0x5004C, 0x50050, 0x50054}
UART1_CON0, UART1_BUF = 0x12100, 0x1210C
CRUMBS, CRUMB_WORDS, MAGIC = 0x01C05FC0, 12, 0x3250354D
CRUMB = {CRUMBS + 4 * i for i in range(CRUMB_WORDS)}
MARKER = 0x01C7FD80
MARKER_SET = {MARKER + 4 * i for i in range(4)}
MARKER_WORDS = [int.from_bytes(b'usb_update_mode\0'[i:i + 4], 'little') for i in range(0, 16, 4)]
WDT_CON, PR_PWR = 0x80, 0xA0
SPI = {SPI_CON, SPI_BAUD, SPI_BUF, PORTC_OUT, PORTC_DIR, IOMAP_CON1}
CORE = {P33_CON, P33_DAT, TIMER_CON, TIMER_CNT, TIMER_PRD} | CRUMB
FM1 = CORE | PORTS | SPI
EFUSE = range(0x13700, 0x13720)
MKEY = range(0x01C80108, 0x01C80114)
PA_OUT, PA_DIR = PORT_A, PORT_A + 8
FOREVER, STOP_KICKING, RESET_APP = 0, 1, 2
RETURNED, FAIL_ARGS, STOPPED, RESET_FAILED = 0, 1, 2, 3
DISPLAY_ON, FRAME_DONE, BLINKING, FINISHING = 10, 11, 12, 13
TIMER_DEAD_FLAG = 0x100
# Nominal costs (dev kit, 48 MHz CPU, 24 MHz oscillator): ~310 cycles per
# pixel and 59 us per kick were measured (notes/2026-11-10-devkit-watchdog-
# probes.md); 30 cycles per access and 300 per P33 byte reproduce both. A
# volatile spin costs 14-15 cycles: m5-plan-2's kit runs measured 94,669 and
# (final build) 88,414 TIMER4 ticks at 1.5 MHz for 200,000 spins at 48 MHz
# (notes/2026-11-14-m5-plan-2.md); the model gives 94,032.
ACCESS, P33_BYTE, SPIN_CYCLES = 30, 300, 15
# The longest kick gap is measure()'s 200,000-spin block: ~63 ms at 48 MHz
# (the final kit build measured 89,732 ticks, 59.8 ms). Every other gap is a 10 ms slice, a
# 100,000-spin unit (31 ms) or one pixel row. All scale with 1/cpu.
NOMINAL_GAP = 0.080


def gap_bound(cpu):
    return NOMINAL_GAP * 48e6 / cpu


class IO(c.Structure):
    _fields_ = [('context', c.c_void_p), ('read', READ), ('write', WRITE),
                ('sync', SYNC), ('pause', PAUSE), ('uart_failed', c.c_uint),
                ('spin', SPIN)]


class Config(c.Structure):
    _fields_ = [('build_id', c.c_char_p), ('stub_pins', c.c_uint), ('trace', c.c_uint),
                ('mailbox', c.c_uint), ('finish', c.c_uint), ('finish_ms', c.c_uint),
                ('beats', c.c_uint)]


_STATE = {}


@pytest.fixture(scope='module')
def lib(tmp_path_factory):
    out = tmp_path_factory.mktemp('m5p2') / 'm5p2.so'
    sources = ['m5p2/m5p2.c', 'ramtest/ramtest.c', 'board/board_io.c', 'board/matrix.c',
               'display/spi1_transport.c', 'display/panel_probe.c', 'display/m5_pattern.c',
               'third_party/fm1-nes/fm1_keys.c']
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
                    *[str(ROOT / 'firmware' / s) for s in sources], '-o', str(out)], check=True)
    library = c.CDLL(str(out))
    library.lunar_m5p2_run.argtypes = [c.POINTER(IO), c.POINTER(Config)]
    library.lunar_m5p2_label.argtypes = [c.c_char_p, c.c_uint, c.c_char_p, c.c_uint, c.c_uint]
    _STATE['lib'] = library
    fm1_run.cache_clear()
    return library


class Chip:
    def __init__(self, lib, *, allowed, cpu=48e6, osc=24e6, step=500, wdt=0x1C,
                 timer_dead=False, spi_stuck=False, crumbs=None):
        self.lib, self.allowed = lib, allowed
        self.cpu, self.osc, self.step = cpu, osc, step
        self.timer_dead, self.spi_stuck = timer_dead, spi_stuck
        self.regs, self.trace, self.tx = {}, [], bytearray()
        self.p33 = {WDT_CON: wdt, PR_PWR: 0x5A}
        self.frames, self.frame, self.selected = [], [], False
        self.cycles, self.kicks, self.tight = 0, [], False
        self.t_cycles, self.t_base, self.running = 0, 0, False
        self.spi_pending, self.spi_bytes = False, []
        if crumbs:
            for i, word in enumerate(crumbs):
                self.regs[CRUMBS + 4 * i] = word
        self.cb = (READ(self.read), WRITE(self.write), SYNC(self.sync), PAUSE(self.pause),
                   SPIN(self.spin))
        self.io = IO(None, self.cb[0], self.cb[1], self.cb[2], self.cb[3], 0, self.cb[4])

    # time
    def count(self):
        if not self.running or self.timer_dead:
            return self.t_base
        return self.t_base + int((self.cycles - self.t_cycles) * self.osc / (16 * self.cpu))

    def read(self, _, address, width):
        assert address in self.allowed, hex(address)
        if address == TIMER_CNT and self.tight and self.running and not self.timer_dead:
            self.cycles += max(ACCESS, int(self.step * 16 * self.cpu / self.osc))
        else:
            self.cycles += ACCESS
        self.tight = address == TIMER_CNT
        self.trace.append(('r', address, width))
        if address == TIMER_CNT:
            return self.count() % 0x8000
        if address == SPI_CON:
            return self.regs.get(SPI_CON, 0) | (0x8000 if self.spi_pending else 0)
        return self.regs.get(address, 0)

    def write(self, _, address, width, value):
        assert address in self.allowed, hex(address)
        assert width in (1, 2, 4)
        self.cycles += ACCESS
        self.tight = False
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
                self.cycles += P33_BYTE
                self.byte(self.regs.get(P33_DAT, 0) & 0xFF)
                value &= ~0x10
        if address == TIMER_CON:
            if value & 1 and not self.running:
                self.t_base, self.t_cycles, self.running = self.count(), self.cycles, True
            elif not value & 1:
                self.t_base, self.running = self.count(), False
        if address == TIMER_CNT:
            self.t_base, self.t_cycles = value, self.cycles
        if address == SPI_CON and value & 0x4000:
            self.spi_pending = False
        if address == SPI_BUF:
            out = self.regs.get(PORTC_OUT, 0)
            self.spi_bytes.append((value & 0xFF, bool(out & 0x100), bool(out & 0x80)))
            self.spi_pending = not self.spi_stuck
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
                if addr == WDT_CON and value & 0x40:
                    self.kicks.append(self.cycles)
        self.regs[P33_DAT] = reply

    def sync(self, _):
        self.trace.append(('sync',))

    def pause(self, _, tenths):
        self.trace.append(('pause', tenths))

    def spin(self, _, iterations):
        self.cycles += iterations * SPIN_CYCLES
        self.tight = False
        self.trace.append(('spin', iterations))

    # running and reading back
    def run(self, build=b'm5-plan-2', *, stub=0, trace=0, mailbox=0, finish=FOREVER,
            finish_ms=1, beats=0):
        self.config = Config(build, stub, trace, mailbox, finish, finish_ms, beats)
        return self.lib.lunar_m5p2_run(c.byref(self.io), c.byref(self.config))

    def text(self):
        return self.tx.decode()

    def p33_writes(self):
        return [(((f[0] & 3) << 8) | f[1], f[2]) for f in self.frames
                if len(f) == 3 and not f[0] & 0x80]

    def crumb(self, index):
        return self.regs.get(CRUMBS + 4 * index, 0)

    def max_gap_s(self):
        marks = [0] + self.kicks
        return max(b - a for a, b in zip(marks, marks[1:])) / self.cpu

    def written(self):
        return {e[1] for e in self.trace if e[0] == 'w'}

    def touched(self):
        return {e[1] for e in self.trace if e[0] in 'rw'}

    def commands(self):
        """SPI bytes sent with D/C low and CS low, in order."""
        return [b for b, dc, cs in self.spi_bytes if not dc and not cs]


@lru_cache(maxsize=None)
def fm1_run(cpu=48e6, osc=24e6, timer_dead=False, spi_stuck=False, mailbox=0):
    """One FM-1 configuration (no stubs, no trace), one blink cycle."""
    chip = Chip(_STATE['lib'], allowed=FM1 | (MARKER_SET if mailbox else set()),
                cpu=cpu, osc=osc, timer_dead=timer_dead, spi_stuck=spi_stuck)
    result = chip.run(mailbox=mailbox, finish=STOP_KICKING if mailbox else FOREVER)
    return chip, result


def test_label_fits_the_panel_line(lib):
    out = c.create_string_buffer(20)
    lib.lunar_m5p2_label(out, 20, b'm5-plan-2', 0x1C, 0x7A12)
    assert out.value == b'm5-plan-2 1C 07A12'
    lib.lunar_m5p2_label(out, 20, b'm5-plan-2m', 0x1C, 0x123456)
    assert out.value == b'm5-plan-2m 1C FFFFF'  # capped at 5 hex digits, 19 chars
    lib.lunar_m5p2_label(out, 8, b'm5-plan-2', 0, 0)
    assert out.value == b'm5-plan'


def test_bad_arguments_touch_nothing(lib):
    chip = Chip(lib, allowed=set())
    assert chip.run(build=None) == FAIL_ARGS
    assert chip.run(finish=3) == FAIL_ARGS
    assert chip.trace == []


def test_fm1_default_stays_on_the_allow_list(lib):
    chip, result = fm1_run()
    assert result == RETURNED                  # host only: finish_ms 1 ends the loop
    touched = chip.touched()
    assert touched <= FM1                      # the Chip asserts this on every access
    assert not touched & (UART - PORTS - SPI)  # no UART1, CLK_CON1 or IOMAP_CON3
    assert not touched & MARKER_SET            # no mailbox in the default
    assert not any(a in EFUSE or a in MKEY for a in touched)
    assert {a for a, _ in chip.p33_writes()} == {WDT_CON}
    assert all(v == 0x1C | 0x40 for _, v in chip.p33_writes())


def test_fm1_default_kicks_first_then_pa2_before_timer_and_panel(lib):
    chip, _ = fm1_run()
    writes = [e for e in chip.trace if e[0] == 'w']
    first_other = next(i for i, e in enumerate(writes) if e[1] not in (P33_CON, P33_DAT))
    first_kick = next(i for i, e in enumerate(writes) if e[1] == P33_CON and e[3] & 0x10)
    assert first_kick < first_other
    pa2 = [i for i, e in enumerate(writes) if e[1] == PA_OUT]
    timer = next(i for i, e in enumerate(writes) if e[1] == TIMER_CON)
    spi = next(i for i, e in enumerate(writes) if e[1] in SPI)
    assert pa2[0] < timer < spi
    assert not writes[pa2[0]][3] & 4           # PA2 low: backlight on, first
    # Six flashes (3 TIMER4-timed, 3 spin-timed) before any SPI1/PORTC write.
    levels = [bool(writes[i][3] & 4) for i in pa2 if i < spi]
    offs = sum(1 for a, b in zip(levels, levels[1:]) if b and not a)
    assert offs == 6 and levels[-1] is False


def test_fm1_default_sends_display_on_before_the_frame(lib):
    chip, _ = fm1_run()
    commands = chip.commands()
    assert commands[0] == 0x11 and commands.count(0x29) == 1 and commands.count(0x2C) == 1
    assert commands.index(0x29) < commands.index(0x2C)
    assert commands[-1] == 0x2C
    start = max(i for i, (b, dc, cs) in enumerate(chip.spi_bytes) if b == 0x2C and not dc)
    data = chip.spi_bytes[start + 1:]
    assert len(data) == 240 * 240 * 2 and all(dc and not cs for _, dc, cs in data)
    assert chip.crumb(1) & 0xFF == FINISHING and chip.crumb(7) == 0  # panel OK


def test_fm1_default_kicks_every_pixel_row_and_wait_slice(lib):
    chip, _ = fm1_run()
    assert len(chip.kicks) >= 240 + 2400 // 10
    gap = chip.max_gap_s()
    assert gap < NOMINAL_GAP, gap
    assert chip.crumb(0) == MAGIC and chip.crumb(11) == (~MAGIC & 0xFFFFFFFF)
    assert chip.crumb(2) == 0x1C
    assert chip.crumb(3) > 0                    # ticks per block measured
    assert chip.crumb(5) == len(chip.kicks)     # kick count matches the frames
    assert chip.crumb(6) == 0


@pytest.mark.parametrize('cpu,osc', [(48e6, 24e6), (48e6, 40e6), (12e6, 24e6), (3e6, 40e6)])
def test_tick_count_loses_no_wraps(lib, cpu, osc):
    # TIMER4 wraps at 0x8000; any stretch longer than one wrap between two
    # polls loses whole periods. The kit run of 2026-11-14 caught this in
    # cadence B (one poll per 100,000 spins); the TICKS crumb must match.
    chip, _ = fm1_run(cpu=cpu, osc=osc)
    assert abs(chip.crumb(10) - chip.count()) <= 0.002 * chip.count(), (chip.crumb(10), chip.count())
    gap_ticks = chip.max_gap_s() * osc / 16
    assert abs(chip.crumb(4) - gap_ticks) <= 0.02 * gap_ticks, (chip.crumb(4), gap_ticks)


@pytest.mark.parametrize('cpu', [12e6, 6e6])
def test_slow_cpu_still_kicks_well_inside_four_seconds(lib, cpu):
    chip, _ = fm1_run(cpu=cpu)
    # At 6 MHz (8x slower than the kit) the measure block is ~0.5 s, still
    # eight times inside the ROM's 4 s watchdog.
    assert chip.max_gap_s() < gap_bound(cpu), (cpu, chip.max_gap_s())
    assert chip.max_gap_s() < 0.6


def test_single_fault_dead_timer_falls_back_to_kicked_spins(lib):
    chip, result = fm1_run(cpu=12e6, timer_dead=True)
    assert result == RETURNED
    assert chip.crumb(1) & TIMER_DEAD_FLAG
    assert chip.max_gap_s() < gap_bound(12e6), chip.max_gap_s()
    writes = [e for e in chip.trace if e[0] == 'w']
    spi = next(i for i, e in enumerate(writes) if e[1] in SPI)
    levels = [bool(e[3] & 4) for e in writes[:spi] if e[1] == PA_OUT]
    offs = sum(1 for a, b in zip(levels, levels[1:]) if b and not a)
    assert offs == 5                            # the dead-timer cadence: five spin flashes


def test_single_fault_stuck_spi_abandons_the_frame_quickly(lib):
    chip, result = fm1_run(cpu=12e6, spi_stuck=True)
    assert result == RETURNED
    assert chip.crumb(7) == 2                   # LUNAR_PANEL_TRANSFER_FAILED
    assert chip.max_gap_s() < gap_bound(12e6), chip.max_gap_s()
    assert len(chip.spi_bytes) == 1             # the first command byte, then abort


def test_fm1_mailbox_option_sets_the_marker_and_stops_kicking(lib):
    chip, result = fm1_run(mailbox=1)
    assert result == STOPPED
    marker = [e for e in chip.trace if e[0] == 'w' and e[1] in MARKER_SET]
    assert [e[3] for e in marker] == MARKER_WORDS
    first_kick = next(i for i, e in enumerate(chip.trace) if e[0] == 'w' and e[1] == P33_CON)
    assert chip.trace.index(marker[0]) > first_kick
    assert {a for a, _ in chip.p33_writes()} == {WDT_CON}   # no PR_PWR: no P33 reset
    assert chip.crumb(1) & 0xFF == FINISHING
    assert chip.text() == ''                    # no UART on the FM-1


def test_kit_build_stubs_every_fm1_pin_and_resets_to_the_app(lib):
    port_b = {PORT_B + 4 * i for i in range(9)}
    chip = Chip(lib, allowed=CORE | UART | port_b | MARKER_SET)
    assert chip.run(b'm5-plan-2k', stub=1, trace=1, finish=RESET_APP, finish_ms=1) == RESET_FAILED
    touched = chip.touched()
    assert not touched & ({PORT_A + 4 * i for i in range(9)} | {PORT_H + 4 * i for i in range(9)})
    assert not touched & {SPI_CON, SPI_BAUD, SPI_BUF, PORTC_OUT, PORTC_DIR}
    # PORTB changes only PB3 (the UART); IOMAP_CON1 never gets SPI1's bit 4.
    before = {}
    for e in chip.trace:
        if e[0] == 'w' and e[1] in port_b:
            assert (e[3] ^ before.get(e[1], 0)) & ~0x8 == 0, hex(e[3])
            before[e[1]] = e[3]
    assert all(not e[3] & 0x10 for e in chip.trace if e[0] == 'w' and e[1] == IOMAP_CON1)
    # The marker is only cleared (ramtest's reset_to_app), then the P33 reset.
    assert [e[3] for e in chip.trace if e[0] == 'w' and e[1] in MARKER_SET] == [0, 0, 0, 0]
    assert chip.p33_writes()[-1] == (PR_PWR, 0x5A | 0x10)
    text = chip.text()
    assert text.startswith('\r\nLUNAR_M5P2 ready=1 build=m5-plan-2k entry=0x01c02000 '
                           'wdt_con=0x0000001c mailbox=0 stub=1 finish=2\r\n')
    assert 'LUNAR_M5P2 prev valid=0 ' in text
    assert re.search(r'LUNAR_M5P2 measure spins=200000 ticks_per_block=\d+\r\n', text)
    assert len(re.findall(r'LUNAR_M5P2 pa2=0 ', text)) == 6
    for number in (1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13):
        assert f'LUNAR_M5P2 stage={number} ' in text, number
    finish = re.search(r'LUNAR_M5P2 finish=reset_app ticks=\d+ elapsed_ms=\d+ kicks=(\d+) '
                       r'kick_failures=0 max_gap=(\d+) cycles=1 stub_reads=(\d+) '
                       r'stub_writes=(\d+)\r\n', text)
    assert finish and int(finish[3]) > 0 and int(finish[4]) > 240 * 240
    assert chip.max_gap_s() < NOMINAL_GAP


def test_kit_reports_breadcrumbs_left_by_a_previous_run(lib):
    words = [MAGIC, FINISHING, 0x1C, 1234, 99, 7, 0, 0, 9000, 3, 555, ~MAGIC & 0xFFFFFFFF]
    chip = Chip(lib, allowed=CORE | UART | MARKER_SET | {PORT_B + 4 * i for i in range(9)},
                crumbs=words)
    chip.run(b'm5-plan-2k', stub=1, trace=1, finish=RESET_APP, finish_ms=1)
    assert ('LUNAR_M5P2 prev valid=1 0x3250354d 0x0000000d 0x0000001c 0x000004d2 '
            '0x00000063 0x00000007 ') in chip.text()
    assert chip.crumb(1) & 0xFF == FINISHING and chip.crumb(4) != 99


def test_kit_mailbox_stops_kicking_and_beats(lib):
    chip = Chip(lib, allowed=CORE | UART | MARKER_SET | {PORT_B + 4 * i for i in range(9)})
    assert chip.run(b'm5-plan-2km', stub=1, trace=1, mailbox=1, finish=STOP_KICKING,
                    finish_ms=1, beats=3) == STOPPED
    text = chip.text()
    beats = re.findall(r'LUNAR_M5P2 beat=(\d+) ticks=\d+ since_kick=(\d+)', text)
    assert [int(b) for b, _ in beats] == [1, 2, 3]
    assert [int(s) >= 1_250_000 * int(b) for b, s in beats] == [True] * 3
    last_kick = chip.kicks[-1]
    assert chip.cycles - last_kick > 3 * 0.5 * chip.cpu * 0.9  # no kick during the beats
    assert [w for w in chip.p33_writes() if w[0] != WDT_CON] == []


def test_build_switches_live_only_in_main_c():
    portable = (ROOT / 'firmware/m5p2/m5p2.c').read_text()
    assert 'LUNAR_M5P2_KIT' not in portable and 'LUNAR_M5P2_MAILBOX' not in portable
    assert '#if' not in portable
    main = (ROOT / 'firmware/m5p2/main.c').read_text()
    assert '#define LUNAR_M5P2_KIT 0' in main and '#define LUNAR_M5P2_MAILBOX 0' in main


def test_linker_keeps_the_m5_window_and_the_crumbs_clear():
    ld = (ROOT / 'firmware/m5p2/app.ld').read_text()
    assert 'ORIGIN = 0x01c02000, LENGTH = 16K' in ld
    assert '__m5p2_crumbs = 0x01c05fc0;' in ld
    assert 'ASSERT(__ssp_top <= __m5p2_crumbs' in ld
    assert 'ASSERT(__ssp_top <= 0x01c06000' in ld
    assert 'ASSERT(__m5p2_crumbs + 48 <= 0x01c06000' in ld
    assert CRUMBS + 4 * CRUMB_WORDS <= 0x01C06000
    header = (ROOT / 'firmware/m5p2/m5p2.h').read_text()
    assert '#define LUNAR_M5P2_CRUMBS 0x01c05fc0u' in header
