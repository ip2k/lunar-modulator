"""ALNK0 bring-up for the FM-1 (firmware/board/alnk0_audio.c), on the host.

The expected sequence in tests/fixtures/alnk0/lunar_start.json is written by
hand from the facts table in notes/2026-11-08-alnk0-codec-driver.md. There is
no DAC datasheet yet (the part is unidentified), so the DAC requirements are
those of a control-less, MCLK-locked I2S DAC on this link [inferred]. The
callbacks touch no hardware.
"""
import ctypes as c
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / 'tests/fixtures/alnk0/lunar_start.json').read_text())
REGS = {name: (int(r['address'], 16), r['bytes']) for name, r in FIXTURE['registers'].items()}
BY_ADDRESS = {address: name for name, (address, _) in REGS.items()}

READ = c.CFUNCTYPE(c.c_uint32, c.c_void_p, c.c_uint32, c.c_uint)
WRITE = c.CFUNCTYPE(None, c.c_void_p, c.c_uint32, c.c_uint, c.c_uint32)
SYNC = c.CFUNCTYPE(None, c.c_void_p)
ATTACH = c.CFUNCTYPE(c.c_int, c.c_void_p, c.c_uint, c.c_uint)
DELAY = c.CFUNCTYPE(c.c_int, c.c_void_p, c.c_uint)


class Ops(c.Structure):
    _fields_ = [('context', c.c_void_p), ('read', READ), ('write', WRITE),
                ('sync', SYNC), ('attach_irq', ATTACH), ('delay_ms', DELAY)]


class Config(c.Structure):
    _fields_ = [('buffer', c.POINTER(c.c_int32)), ('dma_address', c.c_uint32),
                ('half_words', c.c_uint16), ('irq_priority', c.c_uint8),
                ('settle_ms', c.c_uint8)]


@pytest.fixture(scope='module')
def lib(tmp_path_factory):
    library = tmp_path_factory.mktemp('alnk0') / 'alnk0.so'
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-pedantic',
                    '-shared', '-fPIC', str(ROOT / 'firmware/board/alnk0_audio.c'),
                    str(ROOT / 'firmware/board/alnk0_audio_mmio.c'),
                    '-o', str(library)], check=True)
    so = c.CDLL(str(library))
    so.lunar_alnk0_start.argtypes = [c.POINTER(Ops), c.POINTER(Config)]
    so.lunar_alnk0_start.restype = c.c_int
    so.lunar_alnk0_validate.argtypes = [c.POINTER(Ops), c.POINTER(Config)]
    so.lunar_alnk0_validate.restype = c.c_int
    so.lunar_alnk0_default_config.argtypes = [c.POINTER(Config), c.POINTER(c.c_int32), c.c_uint32]
    so.lunar_alnk0_default_config.restype = None
    for name in ('lunar_alnk0_stop',):
        getattr(so, name).argtypes = [c.POINTER(Ops)]
        getattr(so, name).restype = None
    for name in ('lunar_alnk0_pending', 'lunar_alnk0_free_half'):
        getattr(so, name).argtypes = [c.POINTER(Ops)]
        getattr(so, name).restype = c.c_uint
    so.lunar_alnk0_ack.argtypes = [c.POINTER(Ops), c.c_uint]
    so.lunar_alnk0_ack.restype = None
    so.lunar_alnk0_word_from_q23.argtypes = [c.c_int32]
    so.lunar_alnk0_word_from_q23.restype = c.c_int32
    return so


class Bench:
    """A fake register file that logs every access in the fixture's notation."""

    def __init__(self, half_words=128, irq_result=0, delay_result=0):
        self.mem = {name: int(v, 16) for name, v in FIXTURE['initial'].items()}
        self.log = []
        self.bad = []
        self.buffer = (c.c_int32 * (2 * half_words))(*([0x5A5A5A] * (2 * half_words)))
        self.buffer_at_enable = None
        self.irq_result, self.delay_result = irq_result, delay_result

        def name_of(address, size):
            name = BY_ADDRESS.get(address)
            if name is None or REGS[name][1] != size:
                self.bad.append((hex(address), size))
                return None
            return name

        def read(_, address, size):
            name = name_of(address, size)
            value = self.mem.get(name, 0) if name else 0
            self.log.append(['r', name, value])
            return value

        def write(_, address, size, value):
            name = name_of(address, size)
            mask = (1 << (8 * size)) - 1
            if value & ~mask:
                self.bad.append(('wide', name, hex(value)))
            self.log.append(['w', name, value])
            if name == 'CON1' and value & 0x1000 and self.buffer_at_enable is None:
                self.buffer_at_enable = list(self.buffer)
            if name:
                self.mem[name] = value & mask

        def sync(_):
            self.log.append(['sync'])

        def attach(_, irq, priority):
            self.log.append(['irq', irq, priority])
            return self.irq_result

        def delay(_, ms):
            self.log.append(['delay', ms])
            return self.delay_result

        self.callbacks = (READ(read), WRITE(write), SYNC(sync), ATTACH(attach), DELAY(delay))
        self.ops = Ops(None, *self.callbacks)

    def config(self, lib, **override):
        cfg = Config()
        lib.lunar_alnk0_default_config(c.byref(cfg), self.buffer,
                                       int(FIXTURE['config']['dma_address'], 16))
        for key, value in override.items():
            setattr(cfg, key, value)
        return cfg


def expected(sequence):
    out = []
    for row in sequence:
        if row[0] in ('r', 'w'):
            out.append([row[0], row[1], int(row[2], 16)])
        else:
            out.append(list(row))
    return out


def started(lib):
    bench = Bench()
    cfg = bench.config(lib)
    assert lib.lunar_alnk0_start(c.byref(bench.ops), c.byref(cfg)) == 0
    return bench


def test_default_config_is_the_lunar_profile(lib):
    bench = Bench()
    cfg = bench.config(lib)
    want = FIXTURE['config']
    assert (cfg.dma_address, cfg.half_words, cfg.irq_priority, cfg.settle_ms) == (
        int(want['dma_address'], 16), want['half_words'], want['irq_priority'], want['settle_ms'])


def test_start_emits_the_fixture_sequence_exactly(lib):
    bench = started(lib)
    assert bench.bad == []
    assert bench.log == expected(FIXTURE['start'])


def test_final_state_meets_the_dac_requirements(lib):
    bench = started(lib)
    need = FIXTURE['dac_requirements']
    m = bench.mem
    ch = need['tx_channel']
    assert bool(m['CON0'] & 0x80) == need['master'] and m['CON3'] & 3 == 3
    assert bool(m['CON0'] & 0x100) == need['mclk_output']
    assert m['CON0'] & 0x800                          # module enabled
    assert m['CON0'] & 0x40 == 0                      # cleared, as every source does
    assert m['CON0'] & 0x400 == 0                     # update_edge 0
    sclk_per_frame = 32 if m['CON0'] & 0x200 else 64  # f32e
    assert sclk_per_frame == need['sclk_per_frame']
    nibble = (m['CON1'] >> (4 * ch)) & 0xF
    assert nibble == 0b0101                           # enabled, 24-bit, direction out
    assert need['data_bits'] == 24
    assert m['CON1'] & ~(0xF << (4 * ch)) == 0        # no other channel
    assert m['ADR3'] == int(FIXTURE['config']['dma_address'], 16)
    assert m['ADR0'] == m['ADR1'] == m['ADR2'] == 0
    assert m['LEN'] == 2 * need['frames_per_half']    # stereo words per half
    assert ['irq', need['irq'], FIXTURE['config']['irq_priority']] in bench.log
    # rate: CLK_CON2 bit 8 selects the source, CON3[7:5] the code (F13, F14)
    code = m['CON3'] >> 5
    source = FIXTURE['sdk_rate_table']['source_hz'][str((m['CLK_CON2'] >> 8) & 1)]
    assert source // (sclk_per_frame * code) == need['nominal_fs']
    assert sclk_per_frame * code == need['mclk_over_fs']   # MCLK = source
    assert m['CON3'] & 0x1C == 0


def test_rate_model_fits_every_row_of_the_sdk_table():
    table = FIXTURE['sdk_rate_table']
    for row in table['rows']:
        source = table['source_hz'][str(row['clk_bit8'])]
        assert source == 64 * row['code'] * row['fs'], row


def test_read_modify_writes_keep_unrelated_bits(lib):
    m = started(lib).mem
    assert m['IOMAP_CON5'] == 0xFFFFFFFF & ~0xC0           # port C, nothing else
    assert m['CLK_CON2'] == 0xFFFFFFFF & ~0x300            # ALNK1's bits 10, 11 untouched
    pins = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 6)
    for reg in ('PORTC_OUT', 'PORTC_DIR', 'PORTC_PU', 'PORTC_PD'):
        assert m[reg] == 0xFFFFFFFF & ~pins, reg           # PC3, PC4, PC5, PC7.. untouched


def test_ordering_constraints(lib):
    log = started(lib).log
    index = {}
    for i, row in enumerate(log):
        if row[0] == 'w' and row[1] == 'CON0' and row[2] & 0x800 and 'enable' not in index:
            index['enable'] = i
        if row[0] == 'w' and row[1] == 'CON1' and row[2] & 0x1000 and 'run' not in index:
            index['run'] = i
        if row[0] == 'w' and row[1] == 'ADR3' and row[2]:
            index['adr'] = i
        if row[0] == 'sync':
            index['sync'] = i
        if row[0] == 'irq':
            index['irq'] = i
        if row[0] == 'delay':
            index['delay'] = i
    assert index['adr'] < index['sync'] < index['enable'] < index['irq'] < index['run'] < index['delay']
    assert log[index['sync'] + 1:index['enable'] + 1][0][1] == 'CON0'


def test_buffer_is_silent_before_the_channel_runs(lib):
    bench = started(lib)
    assert bench.buffer_at_enable == [0] * 256


@pytest.mark.parametrize('override', [
    dict(dma_address=0), dict(dma_address=0x01C2A010), dict(half_words=0),
    dict(half_words=1), dict(half_words=127), dict(irq_priority=8)])
def test_validation_refuses_bad_configs_without_touching_registers(lib, override):
    bench = Bench()
    cfg = bench.config(lib, **override)
    assert lib.lunar_alnk0_start(c.byref(bench.ops), c.byref(cfg)) == -1
    assert bench.log == []


def test_validation_refuses_missing_buffer_and_callbacks(lib):
    bench = Bench()
    cfg = bench.config(lib)
    cfg.buffer = c.POINTER(c.c_int32)()
    assert lib.lunar_alnk0_validate(c.byref(bench.ops), c.byref(cfg)) == -1
    cfg = bench.config(lib)
    no_delay = Ops(None, *bench.callbacks[:4], DELAY())
    assert lib.lunar_alnk0_validate(c.byref(no_delay), c.byref(cfg)) == -1
    cfg.settle_ms = 0
    assert lib.lunar_alnk0_validate(c.byref(no_delay), c.byref(cfg)) == 0
    assert lib.lunar_alnk0_validate(c.POINTER(Ops)(), c.byref(cfg)) == -1


def test_irq_failure_disables_the_module_and_runs_no_channel(lib):
    bench = Bench(irq_result=1)
    cfg = bench.config(lib)
    assert lib.lunar_alnk0_start(c.byref(bench.ops), c.byref(cfg)) == -2
    assert bench.mem['CON0'] & 0x800 == 0
    assert bench.mem['CON1'] & 0x1000 == 0
    assert not any(row[0] == 'delay' for row in bench.log)


def test_delay_failure_stops_the_channel(lib):
    bench = Bench(delay_result=-1)
    cfg = bench.config(lib)
    assert lib.lunar_alnk0_start(c.byref(bench.ops), c.byref(cfg)) == -3
    assert bench.log[-6:] == expected(FIXTURE['stop'])


def test_stop_emits_the_fixture_sequence(lib):
    bench = started(lib)
    bench.log.clear()
    lib.lunar_alnk0_stop(c.byref(bench.ops))
    assert bench.log == expected(FIXTURE['stop'])


def test_isr_helpers(lib):
    bench = Bench()
    bench.mem['CON2'] = 0x80
    assert lib.lunar_alnk0_pending(c.byref(bench.ops)) == 0x8
    bench.mem['CON2'] = 0x00
    lib.lunar_alnk0_ack(c.byref(bench.ops), 0x8)
    assert bench.mem['CON2'] == 0x08
    bench.log.clear()
    lib.lunar_alnk0_ack(c.byref(bench.ops), 0x30)   # out-of-range bits only: nothing written
    assert bench.log == []
    bench.mem['CON0'] = 0x8980
    assert lib.lunar_alnk0_free_half(c.byref(bench.ops)) == 0
    bench.mem['CON0'] = 0x0980
    assert lib.lunar_alnk0_free_half(c.byref(bench.ops)) == 1


@pytest.mark.parametrize('sample, word', [
    (0, 0), (1, 1), (-1, -1), (8388607, 8388607), (8388608, 8388607),
    (-8388608, -8388608), (-8388609, -8388608), (2**31 - 1, 8388607), (-2**31, -8388608)])
def test_q23_word_saturates(lib, sample, word):
    assert lib.lunar_alnk0_word_from_q23(sample) == word
