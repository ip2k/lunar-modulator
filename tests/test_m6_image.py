"""M6 RAM image core and panel (firmware/m6), on the host.

The voice, the block timing, the status block, the stopwatch, the polled
ALNK0 loop and the panel's byte stream are portable C; these tests build them
into a shared library and drive them through ctypes against fake registers
and a virtual clock. The target entries (main_fm1.c, main_devkit.c) hold the
pi32v2-only parts (`cnum`, volatile accessors) and are checked by the JieLi
build (tools/jieli/link-m6-in-container.sh), not here.
"""
import ctypes as c
import json
from pathlib import Path
import re
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
M6 = ROOT / 'firmware/m6'
FIXTURE = json.loads((ROOT / 'tests/fixtures/alnk0/lunar_start.json').read_text())
REGS = {name: (int(r['address'], 16), r['bytes']) for name, r in FIXTURE['registers'].items()}
BY_ADDRESS = {address: name for name, (address, _) in REGS.items()}

# The PCM of the first 1,024 blocks (FNV-1a over their 32-bit words), as the
# Python model below computes it. Pinned so a change to the voice is seen; a
# dev-kit run reports the same value in its status block (pcm_hash).
PCM_HASH_1024 = 0x92CF0315

READ = c.CFUNCTYPE(c.c_uint32, c.c_void_p, c.c_uint32, c.c_uint)
WRITE = c.CFUNCTYPE(None, c.c_void_p, c.c_uint32, c.c_uint, c.c_uint32)
SYNC = c.CFUNCTYPE(None, c.c_void_p)
ATTACH = c.CFUNCTYPE(c.c_int, c.c_void_p, c.c_uint, c.c_uint)
DELAY = c.CFUNCTYPE(c.c_int, c.c_void_p, c.c_uint)
TREAD = c.CFUNCTYPE(c.c_uint, c.c_void_p, c.c_int)
TWRITE = c.CFUNCTYPE(None, c.c_void_p, c.c_int, c.c_uint)
REPORT = c.CFUNCTYPE(c.c_int, c.c_void_p)
KICK = c.CFUNCTYPE(None, c.c_void_p)
BEGIN = c.CFUNCTYPE(c.c_int, c.c_void_p, c.c_ubyte)
PWRITE = c.CFUNCTYPE(c.c_int, c.c_void_p, c.c_ubyte)
END = c.CFUNCTYPE(None, c.c_void_p)
WAIT = c.CFUNCTYPE(c.c_int, c.c_void_p, c.c_uint)

CON, CNT, PRD = 0, 1, 2
FIELDS = ['magic', 'layout', 'step', 'alnk0_result', 'report_result', 'flags', 'end',
          'tick_mod', 'blocks', 'late', 'missed', 'render_last', 'render_min',
          'render_max', 'interval_last', 'interval_min', 'interval_max', 'busy_max',
          'windows', 'win_render', 'win_interval', 'pcm_hash', 'pcm_hash_blocks',
          'cpu_polls', 'first_wait', 'sys_div', 'clk_con0', 'clk_con1', 'clk_con2',
          'timer_con_before', 'pins_masked']


class Ops(c.Structure):
    _fields_ = [('context', c.c_void_p), ('read', READ), ('write', WRITE),
                ('sync', SYNC), ('attach_irq', ATTACH), ('delay_ms', DELAY)]


class TimerIo(c.Structure):
    _fields_ = [('context', c.c_void_p), ('read', TREAD), ('write', TWRITE), ('sync', SYNC)]


class Status(c.Structure):
    _fields_ = [(name, c.c_int32 if name == 'alnk0_result' else c.c_uint32) for name in FIELDS] + [
        ('build_id', c.c_char * 20)]


class Voice(c.Structure):
    _fields_ = [('carrier', c.c_uint32), ('modulator', c.c_uint32), ('env', c.c_int32),
                ('note', c.c_uint32), ('block_in_note', c.c_uint32), ('attack', c.c_uint32)]


class Platform(c.Structure):
    _fields_ = [('context', c.c_void_p), ('alnk0', c.POINTER(Ops)),
                ('timer', c.POINTER(TimerIo)), ('report', REPORT), ('kick', KICK)]


class Run(c.Structure):
    _fields_ = [('status', c.POINTER(Status)), ('voice', Voice),
                ('platform', c.POINTER(Platform)), ('buffer', c.POINTER(c.c_int32)),
                ('dma_address', c.c_uint32), ('have_last', c.c_uint32),
                ('last_tick', c.c_uint32), ('last_half', c.c_uint32),
                ('acc_blocks', c.c_uint32), ('acc_render', c.c_uint32),
                ('acc_interval', c.c_uint32)]


class Panel(c.Structure):
    _fields_ = [('context', c.c_void_p), ('begin', BEGIN), ('write', PWRITE),
                ('end', END), ('wait_ms', WAIT)]


class Screen(c.Structure):
    _fields_ = [('bus', c.POINTER(Panel)), ('status', c.POINTER(Status)),
                ('line', c.c_uint), ('phase', c.c_uint), ('x', c.c_uint), ('y', c.c_uint),
                ('failed', c.c_uint), ('passes', c.c_uint), ('glyph', c.c_ubyte * 19),
                ('length', c.c_uint)]


def build(tmp, name, sources, extra=()):
    out = tmp / name
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-pedantic', *extra,
                    *map(str, sources), '-o', str(out)], check=True)
    return out


@pytest.fixture(scope='module')
def lib(tmp_path_factory):
    tmp = tmp_path_factory.mktemp('m6')
    so = c.CDLL(str(build(tmp, 'm6.so', [
        M6 / 'm6_core.c', M6 / 'm6_screen.c', ROOT / 'firmware/board/alnk0_audio.c',
        ROOT / 'firmware/display/panel_probe.c'], ['-shared', '-fPIC'])))
    sig = {
        'lunar_m6_sine': (c.c_int32, [c.c_uint32]),
        'lunar_m6_voice_init': (None, [c.POINTER(Voice)]),
        'lunar_m6_voice_render': (None, [c.POINTER(Voice), c.POINTER(c.c_int32)]),
        'lunar_m6_hash_words': (c.c_uint32, [c.c_uint32, c.POINTER(c.c_int32), c.c_uint]),
        'lunar_m6_status_init': (None, [c.POINTER(Status), c.c_char_p]),
        'lunar_m6_stopwatch_start': (None, [c.POINTER(TimerIo)]),
        'lunar_m6_stopwatch_alive': (c.c_int, [c.POINTER(TimerIo), c.c_uint32]),
        'lunar_m6_tick': (c.c_uint32, [c.POINTER(TimerIo)]),
        'lunar_m6_ticks_between': (c.c_uint32, [c.c_uint32, c.c_uint32]),
        'lunar_m6_wait_ticks': (c.c_uint32, [c.POINTER(TimerIo), c.c_uint32]),
        'lunar_m6_run': (c.c_int, [c.POINTER(Run), c.POINTER(Platform), c.POINTER(c.c_int32),
                                   c.c_uint32, c.c_uint32]),
        'lunar_m6_kit_masks': (c.c_int, [c.c_uint32]),
        'lunar_m6_put_u': (c.c_uint, [c.c_char_p, c.c_uint, c.c_uint32]),
        'lunar_m6_put_hex': (c.c_uint, [c.c_char_p, c.c_uint, c.c_uint32]),
        'lunar_m6_fs_estimate': (c.c_uint32, [c.c_uint32, c.c_uint32]),
        'lunar_m6_load_permille': (c.c_uint32, [c.c_uint32, c.c_uint32]),
        'lunar_m6_format_window': (c.c_uint, [c.POINTER(Status), c.c_char_p, c.c_uint]),
        'lunar_m6_frame_pixel': (c.c_uint, [c.c_uint, c.c_uint, c.c_char_p]),
        'lunar_m6_screen_frame': (c.c_int, [c.POINTER(Panel), c.c_char_p]),
        'lunar_m6_screen_text': (c.c_uint, [c.POINTER(Status), c.c_uint, c.c_char_p]),
        'lunar_m6_screen_init': (None, [c.POINTER(Screen), c.POINTER(Panel), c.POINTER(Status)]),
        'lunar_m6_screen_step': (c.c_int, [c.c_void_p]),
    }
    for name, (restype, argtypes) in sig.items():
        getattr(so, name).restype = restype
        getattr(so, name).argtypes = argtypes
    return so


# --- the sine and the voice ------------------------------------------------

def ksintab12():
    text = (ROOT / 'engines/src/msfa_rom.cc').read_text()
    body = text[text.index('kSinTab12[4096] = {'):]
    body = body[body.index('{') + 1:body.index('};')]
    values = [int(v) for v in re.findall(r'-?\d+', body)]
    assert len(values) == 4096
    return values


def test_quarter_table_rebuilds_ksintab12_bit_for_bit(lib):
    table = ksintab12()
    assert [lib.lunar_m6_sine(i << 20) for i in range(4096)] == table
    # the low 20 bits of the phase never matter (trunc12: no interpolation)
    assert lib.lunar_m6_sine((1234 << 20) | 0xFFFFF) == table[1234]


def test_sine_header_is_generated_and_current():
    subprocess.run([sys.executable, str(ROOT / 'tools/m6_tables.py'), '--check'], check=True)


QUARTER = ksintab12()[:1024]
INC = [((mhz << 32) + 22059000) // 44118000 for mhz in (220000, 277183, 329628, 440000)]


def model_sine(phase):
    index = (phase >> 20) & 4095
    point = index & 1023
    value = QUARTER[1023 - point if index & 1024 else point]
    return -value if index & 2048 else value


class ModelVoice:
    """The voice of m6_core.c in Python integers, written from its comments."""

    def __init__(self):
        self.carrier = self.modulator = self.env = 0
        self.note = self.block = 0
        self.attack = 1

    def block_words(self):
        top = 4096 << 16
        step = top // 128
        inc = INC[self.note & 3]
        if self.block == 0:
            self.attack = 1
        words = []
        for _ in range(64):
            if self.attack:
                self.env += step
                if self.env >= top:
                    self.env, self.attack = top, 0
            else:
                self.env -= self.env >> 13
            gain = self.env >> 16
            mod = model_sine(self.modulator) * (gain << 3)
            out = (model_sine((self.carrier + mod) & 0xFFFFFFFF) * gain) >> 7
            words += [out, out]
            self.carrier = (self.carrier + inc) & 0xFFFFFFFF
            self.modulator = (self.modulator + (inc << 1)) & 0xFFFFFFFF
        self.block += 1
        if self.block == 512:
            self.block, self.note = 0, (self.note + 1) & 3
        return words


def fnv(hash_, words):
    for word in words:
        hash_ = ((hash_ ^ (word & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    return hash_


def c_blocks(lib, count):
    voice = Voice()
    lib.lunar_m6_voice_init(c.byref(voice))
    words = (c.c_int32 * 128)()
    for _ in range(count):
        lib.lunar_m6_voice_render(c.byref(voice), words)
        yield list(words)


@pytest.fixture(scope='module')
def pcm(lib):
    """2,048 blocks (four notes) from C and from the model."""
    model = ModelVoice()
    return list(c_blocks(lib, 2048)), [model.block_words() for _ in range(2048)]


def test_voice_matches_the_python_model(pcm):
    c_side, model = pcm
    for index, (got, want) in enumerate(zip(c_side, model)):
        assert got == want, f'block {index}'


def test_pcm_hash_of_the_first_1024_blocks_is_pinned(lib, pcm):
    words = [w for block in pcm[0][:1024] for w in block]
    want = fnv(2166136261, words)
    buffer = (c.c_int32 * len(words))(*words)
    assert lib.lunar_m6_hash_words(2166136261, buffer, len(words)) == want
    assert want == PCM_HASH_1024, f'PCM hash changed: {want:#010x}'


def test_level_channels_and_range(pcm):
    samples = [w for block in pcm[0] for w in block]
    left, right = samples[0::2], samples[1::2]
    assert left == right
    peak = max(abs(s) for s in left)
    # -18 dBFS of Q23 at most: 32,767 * 4,096 >> 7
    assert 1_000_000 < peak <= 1_048_544
    assert all(-(1 << 23) <= s < (1 << 23) for s in left)


def period_of(samples, low, high):
    """Lag with the strongest autocorrelation between `low` and `high`."""
    best, best_lag = None, None
    for lag in range(low, high + 1):
        score = sum(a * b for a, b in zip(samples, samples[lag:]))
        if best is None or score > best:
            best, best_lag = score, lag
    return best_lag


@pytest.mark.parametrize('note,hz', [(0, 220.0), (1, 277.183), (2, 329.628), (3, 440.0)])
def test_each_arpeggio_note_has_its_pitch(pcm, note, hz):
    first = note * 512 + 8                    # past the attack
    samples = [w for block in pcm[0][first:first + 24] for w in block[0::2]]
    lag = period_of(samples, int(44118 / hz) - 20, int(44118 / hz) + 20)
    assert abs(44118 / lag - hz) / hz < 0.01


def test_no_clicks_at_note_boundaries(pcm):
    samples = [w for block in pcm[0] for w in block[0::2]]
    steps = [abs(b - a) for a, b in zip(samples, samples[1:])]
    within = max(steps)
    # the largest step anywhere is the slope of the loudest note, not a jump
    # where a note starts
    for boundary in (512 * 64, 1024 * 64, 1536 * 64):
        around = steps[boundary - 4:boundary + 132]
        assert max(around) <= within
    # A4 at full level bounds every step: with the modulator at twice the
    # carrier and index pi/2, the instantaneous frequency peaks at
    # 440 * (1 + 2 * pi/2) Hz
    assert within < 2 * 3.1416 * 440 * (1 + 3.1416) * 1_048_544 / 44118


# --- status block, formatting, timing math ----------------------------------

def test_status_layout_matches_the_header(tmp_path):
    names = FIELDS + ['build_id']
    probe = tmp_path / 'layout.c'
    probe.write_text('#include <stddef.h>\n#include <stdio.h>\n#include "m6_core.h"\n'
                     'int main(void) {\n'
                     + ''.join(f'printf("%zu\\n", offsetof(struct lunar_m6_status, {n}));\n'
                               for n in names)
                     + 'printf("%zu\\n", sizeof(struct lunar_m6_status));\nreturn 0;\n}\n')
    exe = build(tmp_path, 'layout', [probe], [f'-I{M6}'])
    got = [int(v) for v in subprocess.run([str(exe)], check=True, capture_output=True,
                                          text=True).stdout.split()]
    assert got[:-1] == [4 * i for i in range(len(names))]
    assert got[-1] == 144 == c.sizeof(Status)
    # the header's offset comments say the same
    header = (M6 / 'm6_core.h').read_text()
    block = header[header.index('struct lunar_m6_status {'):]
    block = block[:block.index('};')]
    comments = [int(m) for m in re.findall(r'/\*\s+(\d+)', block)]
    assert comments == [4 * i for i in range(len(names))]
    assert '#define LUNAR_M6_STATUS_BYTES 144u' in header


def test_status_init(lib):
    status = Status()
    for name in FIELDS:
        setattr(status, name, 7)
    lib.lunar_m6_status_init(c.byref(status), b'm6-plan-1')
    assert status.magic == 0x55413A4D and status.layout == 1 and status.step == 1
    assert status.tick_mod == 0x8000
    assert status.render_min == status.interval_min == 0xFFFFFFFF
    assert status.pcm_hash == 2166136261
    assert status.build_id == b'm6-plan-1'
    for name in FIELDS:
        if name not in ('magic', 'layout', 'step', 'tick_mod', 'render_min', 'interval_min',
                        'pcm_hash'):
            assert getattr(status, name) == 0, name
    lib.lunar_m6_status_init(c.byref(status), b'x' * 40)
    assert status.build_id == b'x' * 19


def test_formatters(lib):
    out = c.create_string_buffer(16)
    n = lib.lunar_m6_put_u(out, 16, 4294967295)
    assert out.raw[:n] == b'4294967295'
    n = lib.lunar_m6_put_u(out, 16, 0)
    assert out.raw[:n] == b'0'
    n = lib.lunar_m6_put_u(out, 3, 12345)
    assert out.raw[:n] == b'123'
    n = lib.lunar_m6_put_hex(out, 16, 0x01C043E0)
    assert out.raw[:n] == b'01C043E0'


def window_ticks(fs, tick_hz):
    return round(1024 * 64 * tick_hz / fs)


@pytest.mark.parametrize('tick_hz', [1_500_000, 2_500_000])
@pytest.mark.parametrize('fs', [44_118, 44_100, 48_000, 32_000])
def test_fs_estimate(lib, tick_hz, fs):
    got = lib.lunar_m6_fs_estimate(window_ticks(fs, tick_hz), tick_hz)
    assert abs(got - fs) <= 2


def test_fs_estimate_refuses_nonsense(lib):
    assert lib.lunar_m6_fs_estimate(0, 1_500_000) == 0
    assert lib.lunar_m6_fs_estimate(63, 1_500_000) == 0
    assert lib.lunar_m6_fs_estimate(2_000_000, 5_000_000) == 0


def test_load_permille(lib):
    assert lib.lunar_m6_load_permille(250, 1000) == 250
    assert lib.lunar_m6_load_permille(0, 0) == 0
    big = window_ticks(44_118, 2_500_000)
    assert lib.lunar_m6_load_permille(big // 4, big) == 250
    assert lib.lunar_m6_load_permille(4_000_000_000, 4_000_000_000) == 1000


def test_ticks_between_wraps_at_the_modulus(lib):
    assert lib.lunar_m6_ticks_between(100, 300) == 200
    assert lib.lunar_m6_ticks_between(0x7FF0, 0x10) == 0x20
    assert lib.lunar_m6_ticks_between(5, 5) == 0


def test_kit_masks_exactly_the_four_portc_registers(lib):
    masked = {a for a in range(0x50000, 0x50100, 4) if lib.lunar_m6_kit_masks(a)}
    assert masked == {0x50080, 0x50088, 0x50090, 0x50094}
    for name, (address, _) in REGS.items():
        assert bool(lib.lunar_m6_kit_masks(address)) == name.startswith('PORTC_'), name


# --- the stopwatch -----------------------------------------------------------

class Clock:
    """TIMER4 as a free-running counter: CNT advances `per_read` ticks on
    every read of it, and runs only while CON has the run bit."""

    def __init__(self, per_read=3, running=True):
        self.t = 0
        self.per_read = per_read
        self.con = 0
        self.cnt = 0
        self.prd = 0
        self.log = []
        self.running = running

        def read(_, reg):
            if reg == CNT:
                if self.con & 1 and self.running:
                    self.t += self.per_read
                return self.t % 0x8000 if self.con & 1 and self.running else self.cnt
            return {CON: self.con, PRD: self.prd}[reg]

        def write(_, reg, value):
            self.log.append(('w', reg, value))
            if reg == CON:
                self.con = value
            elif reg == CNT:
                self.cnt = value
                self.t = value
            else:
                self.prd = value

        def sync(_):
            self.log.append(('sync',))

        self.callbacks = (TREAD(read), TWRITE(write), SYNC(sync))
        self.io = TimerIo(None, *self.callbacks)

    def advance(self, ticks):
        self.t += ticks


def test_stopwatch_start_sequence(lib):
    clock = Clock()
    lib.lunar_m6_stopwatch_start(c.byref(clock.io))
    assert clock.log == [('w', CON, 1 << 14), ('sync',), ('w', CNT, 0), ('w', PRD, 0x7FFF),
                         ('w', CON, (2 << 4) | (1 << 3) | 1), ('sync',)]


def test_stopwatch_alive_and_dead(lib):
    clock = Clock()
    lib.lunar_m6_stopwatch_start(c.byref(clock.io))
    assert lib.lunar_m6_stopwatch_alive(c.byref(clock.io), 10) == 1
    dead = Clock(running=False)
    lib.lunar_m6_stopwatch_start(c.byref(dead.io))
    assert lib.lunar_m6_stopwatch_alive(c.byref(dead.io), 1000) == 0


def test_wait_ticks_counts_across_wraps(lib):
    clock = Clock(per_read=7)
    lib.lunar_m6_stopwatch_start(c.byref(clock.io))
    clock.t = 0x7F00
    start = clock.t
    polls = lib.lunar_m6_wait_ticks(c.byref(clock.io), 100_000)
    assert clock.t - start >= 100_000
    assert polls == pytest.approx(100_000 / 7, abs=2)


# --- the polled ALNK0 loop ----------------------------------------------------

class Rig:
    """Fake ALNK0 registers on a virtual clock shared with the stopwatch.

    Every register read costs `cost` ticks. Once CON1's channel-3 run bit is
    set, a boundary comes every `period` ticks: it raises CON2 bit 7 and makes
    the half just played free (CON0 bit 15 set = half 0). `report_cost` ticks
    pass per report() call. `blocks_then_stall` stops the boundaries.
    """

    def __init__(self, period=2228, cost=2, report_cost=20, never=False, blocks_then_stall=None,
                 kit=False):
        self.clock = Clock(per_read=cost)
        self.mem = {name: int(v, 16) for name, v in FIXTURE['initial'].items()}
        self.log = []
        self.period, self.cost, self.report_cost = period, cost, report_cost
        self.never, self.stall = never, blocks_then_stall
        self.run_at = None
        self.seen = 0            # boundaries raised so far
        self.pending = 1         # the fixture's CON2 starts 0x80
        self.reports = 0
        self.kit = kit
        self.masked = []

        def update():
            if self.run_at is None or self.never:
                return
            due = (self.clock.t - self.run_at) // self.period
            if self.stall is not None:
                due = min(due, self.stall)
            if due > self.seen:
                self.seen = due
                self.pending = 1

        def read(_, address, size):
            self.clock.advance(self.cost)
            update()
            name = BY_ADDRESS[address]
            assert REGS[name][1] == size
            if name == 'CON2':
                value = (self.mem['CON2'] & 0x7F) | (self.pending << 7)
            elif name == 'CON0' and self.run_at is not None:
                free = (self.seen - 1) % 2 if self.seen else 1
                value = (self.mem['CON0'] & ~0x8000) | (0x8000 if free == 0 else 0)
            else:
                value = self.mem[name]
            self.log.append(['r', name, value])
            return value

        def write(_, address, size, value):
            name = BY_ADDRESS[address]
            assert REGS[name][1] == size
            if self.kit and name.startswith('PORTC_'):
                self.masked.append(name)
                return
            self.log.append(['w', name, value])
            if name == 'CON2':
                if value & 0x08:
                    self.pending = 0
                self.mem['CON2'] = value & 0x0F
                return
            self.mem[name] = value
            if name == 'CON1' and value & 0x1000 and self.run_at is None:
                self.run_at = self.clock.t
            if name == 'CON1' and not value & 0x1000:
                self.run_at = None

        def sync(_):
            self.log.append(['sync'])

        def report(_):
            self.reports += 1
            self.clock.advance(self.report_cost)
            return 1

        self.callbacks = (READ(read), WRITE(write), SYNC(sync))
        # attach_irq and delay_ms stay NULL: the core supplies its own
        self.ops = Ops(None, *self.callbacks, ATTACH(), DELAY())
        self.report_cb = REPORT(report)
        self.buffer = (c.c_int32 * 256)(*([0x5A5A5A] * 256))
        self.status = Status()
        self.kicks = []

        def kick(_):
            self.kicks.append(self.status.blocks)

        self.kick_cb = KICK(kick)
        self.platform = Platform(None, c.pointer(self.ops), c.pointer(self.clock.io),
                                 self.report_cb, self.kick_cb)
        self.run = Run()

    def go(self, lib, blocks, build_id=b'm6-test'):
        lib.lunar_m6_status_init(c.byref(self.status), build_id)
        lib.lunar_m6_stopwatch_start(c.byref(self.clock.io))
        self.run.status = c.pointer(self.status)
        dma = int(FIXTURE['config']['dma_address'], 16)
        return lib.lunar_m6_run(c.byref(self.run), c.byref(self.platform), self.buffer, dma,
                                blocks)


def fixture_start(kit=False):
    rows = []
    for row in FIXTURE['start']:
        if row[0] in ('irq', 'delay'):
            continue                           # stub IRQ; the delay is stopwatch reads
        if kit and row[0] == 'w' and row[1].startswith('PORTC_'):
            continue
        rows.append([row[0], row[1], int(row[2], 16)] if row[0] in ('r', 'w') else row)
    return rows


def start_log(rig):
    """The register log up to the first boundary poll after start."""
    log = rig.log
    end = next(i for i, row in enumerate(log) if row[:2] == ['w', 'CON1'] and row[2] & 0x1000)
    return log[:end + 1]


def test_start_through_the_core_is_the_fixture_sequence(lib):
    rig = Rig()
    assert rig.go(lib, 4) == 0
    assert start_log(rig) == fixture_start()


def test_kit_start_is_the_fixture_sequence_without_portc_writes(lib):
    rig = Rig(kit=True)
    assert rig.go(lib, 4) == 0
    assert start_log(rig) == fixture_start(kit=True)
    assert rig.masked == ['PORTC_OUT', 'PORTC_DIR', 'PORTC_PD', 'PORTC_PU']


def test_settle_delay_is_at_least_5_ms_of_stopwatch(lib):
    rig = Rig()
    rig.go(lib, 1)
    # first_wait spans the settle delay: >= 5 ms at the 40 MHz upper tick rate
    assert rig.status.first_wait >= 5 * 2500


def test_steady_run_counts_and_times_every_block(lib):
    rig = Rig()
    assert rig.go(lib, 3000) == 0
    s = rig.status
    assert (s.end, s.step, s.flags) == (0, 9, 0)
    assert s.blocks == 3000 and s.late == 0 and s.missed == 0
    assert s.windows == 2
    assert s.interval_min >= 2228 - 4 and s.interval_max <= 2228 + 2 * rig.cost + 4
    assert abs(s.win_interval - 1024 * 2228) <= 1024 * 4
    assert s.pcm_hash_blocks == 1024 and s.pcm_hash == PCM_HASH_1024
    assert 0 < s.render_min <= s.render_max
    assert s.busy_max < 2228 // 2 + rig.report_cost + 50     # slack gate held
    assert rig.reports > 0
    assert s.alnk0_result == 0
    # stopped on the way out: channel off, pending acknowledged, module off
    assert rig.mem['CON1'] & 0x1000 == 0 and rig.mem['CON0'] & 0x800 == 0


def test_watchdog_kick_runs_every_256_blocks(lib):
    # Run 2026-11-09-m6-b on the kit was reset by the P33 watchdog after two
    # windows; the core now calls the platform's kick every 256 blocks.
    rig = Rig()
    assert rig.go(lib, 3000) == 0
    assert rig.kicks == list(range(256, 3000, 256))
    assert rig.status.late == 0 and rig.status.missed == 0


def test_kick_is_optional(lib):
    rig = Rig()
    rig.platform.kick = KICK()
    assert rig.go(lib, 600) == 0 and rig.status.blocks == 600


def test_rendered_halves_alternate_and_hold_the_voice(lib):
    rig = Rig()
    rig.go(lib, 2)
    model = ModelVoice()
    first, second = model.block_words(), model.block_words()
    # boundary 1 frees half 0, boundary 2 half 1
    assert list(rig.buffer[:128]) == first
    assert list(rig.buffer[128:]) == second


def test_report_work_stays_inside_the_slack(lib):
    rig = Rig(report_cost=50)
    rig.go(lib, 500)
    s = rig.status
    assert s.late == 0 and s.missed == 0
    # no report before 8 intervals are known
    assert rig.reports > 0
    assert s.busy_max <= s.interval_min // 2 + 50 + 4 * rig.cost + 200


def test_a_report_longer_than_a_block_is_late_and_missed(lib):
    rig = Rig(report_cost=6000)
    rig.go(lib, 200)
    s = rig.status
    assert s.late > 0 and s.missed > 0


def test_no_clock_stops_after_the_first_block_timeout(lib):
    rig = Rig(never=True)
    assert rig.go(lib, 10) == 2
    s = rig.status
    assert s.end == 2 and s.flags == 2 and s.blocks == 0 and s.step == 6
    assert rig.clock.t >= 100 * 2500
    assert rig.mem['CON1'] & 0x1000 == 0       # stopped


def test_stall_stops_after_the_stall_timeout(lib):
    rig = Rig(blocks_then_stall=40)
    assert rig.go(lib, 0) == 3
    s = rig.status
    # the boundaries during the settle delay arrive as one block
    assert s.end == 3 and s.flags == 4 and rig.seen == 40 and 30 <= s.blocks < 40


def test_window_report_line(lib):
    rig = Rig()
    rig.go(lib, 1100)
    out = c.create_string_buffer(128)
    n = lib.lunar_m6_format_window(c.byref(rig.status), out, 128)
    line = out.raw[:n].decode()
    assert line.endswith('\r\n') and n < 128
    s = rig.status
    assert line == (f'M6 win=1 blk=1100 render={s.win_render} interval={s.win_interval} '
                    f'busy_max={s.busy_max} late=0 missed=0\r\n')


# --- the panel -----------------------------------------------------------------

class Bus:
    def __init__(self, fail_after=None):
        self.ops = []
        self.bytes = 0
        self.fail_after = fail_after

        def ok():
            self.bytes += 1
            return 0 if self.fail_after is not None and self.bytes > self.fail_after else 1

        def begin(_, cmd):
            self.ops.append(['begin', cmd])
            return ok()

        def write(_, data):
            self.ops[-1].append(data) if self.ops and self.ops[-1][0] == 'begin' else None
            return ok()

        def end(_):
            self.ops.append(['end'])

        def wait(_, ms):
            self.ops.append(['wait', ms])
            return 1

        self.callbacks = (BEGIN(begin), PWRITE(write), END(end), WAIT(wait))
        self.panel = Panel(None, *self.callbacks)


def status_sample(lib):
    s = Status()
    lib.lunar_m6_status_init(c.byref(s), b'm6-plan-1')
    s.blocks, s.win_interval, s.win_render = 123456, window_ticks(44_118, 1_500_000), 556_000
    s.busy_max, s.interval_min, s.late, s.missed = 900, 2170, 3, 1
    s.pcm_hash, s.step, s.alnk0_result, s.flags = 0xDEADBEEF, 7, -2, 6
    return s


def test_screen_lines(lib):
    s = status_sample(lib)
    out = c.create_string_buffer(20)
    lines = []
    for line in range(8):
        n = lib.lunar_m6_screen_text(c.byref(s), line, out)
        assert n <= 19 and out.raw[n] == 0
        lines.append(out.raw[:n].decode())
    # 2,228,206 ticks per window: 2,175 per block; 44,119 Hz if the tick is
    # 1.5 MHz (24 MHz / 16), 73,532 Hz if 2.5 MHz; 556,000 / 2,228,206 = 25.0 %;
    # 900 / 2,170 = 41.5 %
    assert lines == ['BLK 123456', 'TPB 2175', 'FS24 44119', 'FS40 73532',
                     'LOAD 25.0 MAX 41.5', 'LATE 3 MISS 1', 'PCM DEADBEEF', 'STEP 7 RC -2 F 6']
    assert all(set(text) <= set(' -.:0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ') for text in lines)


def test_frame_pixels(lib):
    assert lib.lunar_m6_frame_pixel(0, 100, b'm6') == 0xFFFF            # border
    assert lib.lunar_m6_frame_pixel(120, 239, b'm6') == 0xFFFF
    assert lib.lunar_m6_frame_pixel(120, 150, b'm6') == 0x0008          # line area
    title = {lib.lunar_m6_frame_pixel(x, y, b'm6') for x in range(1, 239) for y in range(10, 31)}
    assert title == {0xFFFF, 0x0008}
    ident = {lib.lunar_m6_frame_pixel(x, y, b'm6-plan-1') for x in range(1, 239)
             for y in range(40, 54)}
    assert ident == {0xFFE0, 0x0008}


def test_frame_stream(lib):
    bus = Bus()
    assert lib.lunar_m6_screen_frame(c.byref(bus.panel), b'm6-plan-1') == 0
    ramwr = [op for op in bus.ops if op[0] == 'begin' and op[1] == 0x2C]
    assert len(ramwr) == 1 and len(ramwr[0]) == 2 + 240 * 240 * 2
    assert bus.ops[-2:] == [['begin', 0x29], ['end']]


def test_screen_steps_redraw_every_line_in_small_steps(lib):
    s = status_sample(lib)
    bus = Bus()
    screen = Screen()
    lib.lunar_m6_screen_init(c.byref(screen), c.byref(bus.panel), c.byref(s))
    largest = 0
    steps = 0
    while screen.passes == 0:
        before = bus.bytes
        assert lib.lunar_m6_screen_step(c.addressof(screen)) == 1
        largest = max(largest, bus.bytes - before)
        steps += 1
    assert largest <= 5
    assert steps == 8 * (3 + 240 * 14)
    windows = [op for op in bus.ops if op[0] == 'begin' and op[1] in (0x2A, 0x2B)]
    assert windows[:2] == [['begin', 0x2A, 0, 0, 0, 239], ['begin', 0x2B, 0, 104, 0, 117]]
    rows = [(op[2] << 8 | op[3], op[4] << 8 | op[5]) for op in windows if op[1] == 0x2B]
    assert rows == [(64 + 20 * i + 40, 64 + 20 * i + 40 + 13) for i in range(8)]
    ramwr = [op for op in bus.ops if op[0] == 'begin' and op[1] == 0x2C]
    assert len(ramwr) == 8 and all(len(op) == 2 + 240 * 14 * 2 for op in ramwr)
    # line 0 "BLK 123456": something lit, border white
    pixels = [ramwr[0][2 + 2 * i] << 8 | ramwr[0][3 + 2 * i] for i in range(240 * 14)]
    assert set(pixels) == {0xFFFF, 0x0008}
    assert pixels[0] == pixels[239] == 0xFFFF


def test_screen_failure_latches(lib):
    s = status_sample(lib)
    bus = Bus(fail_after=20)
    screen = Screen()
    lib.lunar_m6_screen_init(c.byref(screen), c.byref(bus.panel), c.byref(s))
    results = [lib.lunar_m6_screen_step(c.addressof(screen)) for _ in range(40)]
    assert 0 in results and screen.failed == 1
    assert results[results.index(0):] == [0] * (40 - results.index(0))
    assert bus.ops[-1] == ['end']               # CS released on the failure
