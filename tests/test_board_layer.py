"""FM-1 board layer on the host: register allow-list, 595 key matrix and
decode, encoders, LEDs, ADC, MIDI parser and UART1 ring, and the M5 test
pattern's byte stream. Everything runs against firmware/board/host/board_sim.c;
no native register access and no device traffic."""
import ctypes as c
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import zlib

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ['firmware/board/board_io.c', 'firmware/board/matrix.c', 'firmware/board/adc.c',
           'firmware/board/midi_parser.c', 'firmware/board/midi_uart.c',
           'firmware/third_party/fm1-nes/fm1_keys.c', 'firmware/board/host/board_sim.c',
           'firmware/display/panel_probe.c', 'firmware/display/m5_pattern.c']

# Enum order of firmware/board/board_io.h.
FIELDS = ['OUT', 'IN', 'DIR', 'DIE', 'PU', 'PD', 'HD0', 'HD', 'DIEH']
PA, PB, PH = 0, 9, 18
IOMAP_CON2, IOMAP_CON3, CLOCK_CON1 = 27, 28, 29
UART1_CON0, UART1_CON1, UART1_BAUD, UART1_OTCNT = 30, 31, 32, 33
UART1_RXSADR, UART1_RXEADR, UART1_RXCNT, UART1_HRXCNT = 34, 35, 36, 37
ADC_CON, ADC_RES, ANA_WLA_CON0, ANA_PLL_CON1, COUNT = 38, 39, 40, 41, 42
OUT, IN, DIR, DIE, PU, PD, HD0, HD, DIEH = range(9)

# fm1-nes 870f305 fm1_stock_keys.c: scan-phase label << 4 | row bit.
NES_LABEL_CELLS = [
    0x14, 0x24, 0x71, 0x51, 0x31, 0x11, 0xa2, 0x92, 0x81, 0x61, 0x41, 0x21, 0x02, 0x82,
    0x44, 0x34, 0x64, 0x54, 0x84, 0x74, 0x94, 0xa4, 0x04, 0x13, 0x23, 0x33, 0x43, 0x53,
    0x63, 0x73, 0x83, 0x93, 0xa3, 0x03, 0x12, 0x22, 0x32, 0x42, 0x52, 0x72, 0x62]
NES_ENCODER_LABELS = [0x10, 0x20, 0x30, 0x40, 0x91, 0xa1, 0x90, 0xa0,
                      0x70, 0x80, 0x50, 0x60, 0x15, 0x25]


def physical(label_cell):
    return ((((label_cell >> 4) + 10) % 11) << 4) | (label_cell & 15)


class Msg(c.Structure):
    _fields_ = [('status', c.c_ubyte), ('data1', c.c_ubyte), ('data2', c.c_ubyte),
                ('length', c.c_ubyte)]


class Parser(c.Structure):
    _fields_ = [('status', c.c_ubyte), ('need', c.c_ubyte), ('count', c.c_ubyte),
                ('in_sysex', c.c_ubyte), ('data', c.c_ubyte * 2)]


class Encoders(c.Structure):
    _fields_ = [('previous', c.c_ubyte * 7), ('candidate', c.c_ubyte * 7),
                ('count', c.c_int * 7), ('invalid', c.c_uint * 7), ('valid', c.c_uint)]


class Adc(c.Structure):
    _fields_ = [('io', c.c_void_p), ('poll_limit', c.c_uint), ('ready', c.c_uint),
                ('failed', c.c_uint)]


class Pot(c.Structure):
    _fields_ = [('accepted', c.c_uint), ('debounce', c.c_uint), ('level', c.c_uint)]


class Uart(c.Structure):
    _fields_ = [('io', c.c_void_p), ('ring', c.c_void_p), ('ring_bytes', c.c_uint),
                ('cursor', c.c_uint), ('pending', c.c_uint), ('overruns', c.c_uint),
                ('configured', c.c_uint), ('parser', Parser)]


EMIT = c.CFUNCTYPE(None, c.c_void_p, c.POINTER(Msg))


@pytest.fixture(scope='module')
def lib(tmp_path_factory):
    path = tmp_path_factory.mktemp('board') / 'board.so'
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
                    *[str(ROOT / s) for s in SOURCES], '-o', str(path)], check=True)
    library = c.CDLL(str(path))
    library.sim_io.restype = c.c_void_p
    for name in ('sim_reg', 'sim_counter', 'sim_latched_at', 'sim_sink_used',
                 'lunar_board_address', 'lunar_board_width', 'lunar_matrix_word',
                 'lunar_matrix_select', 'lunar_key_cell', 'lunar_m5_pixel'):
        getattr(library, name).restype = c.c_uint
    library.sim_ring.restype = c.c_void_p
    library.sim_ring.argtypes = [c.POINTER(c.c_uint)]
    library.sim_sink.restype = c.c_void_p
    library.sim_sink.argtypes = [c.c_void_p, c.c_uint]
    library.sim_uart_rx.argtypes = [c.c_char_p, c.c_uint]
    for name in ('lunar_matrix_init', 'lunar_matrix_release', 'lunar_backlight_on',
                 'lunar_backlight_off', 'lunar_board_io_valid'):
        getattr(library, name).argtypes = [c.c_void_p]
    library.lunar_matrix_select.argtypes = [c.c_void_p, c.c_uint, c.c_uint]
    library.lunar_matrix_scan.argtypes = [c.c_void_p, c.c_void_p, c.c_void_p]
    library.lunar_panel_m5_pattern.argtypes = [c.c_void_p, c.c_char_p]
    library.lunar_panel_probe.argtypes = [c.c_void_p]
    library.lunar_m5_pixel.argtypes = [c.c_uint, c.c_uint, c.c_char_p]
    library.lunar_adc_init.argtypes = [c.POINTER(Adc), c.c_void_p, c.c_uint]
    library.lunar_adc_read.argtypes = [c.POINTER(Adc), c.c_uint, c.POINTER(c.c_uint)]
    library.lunar_midi_uart_configure.argtypes = [c.POINTER(Uart), c.c_void_p, c.c_void_p,
                                                  c.c_uint, c.c_uint]
    library.lunar_midi_uart_poll.argtypes = [c.POINTER(Uart), c.c_uint, EMIT, c.c_void_p]
    library.lunar_midi_uart_drain.argtypes = [c.POINTER(Uart), c.c_uint, c.c_uint, EMIT,
                                              c.c_void_p]
    library.sim_reset()
    return library


@pytest.fixture
def sim(lib):
    lib.sim_reset()
    return lib


def reg(lib, r):
    return lib.sim_reg(r)


# ---- allow-list ---------------------------------------------------------------

def test_register_allow_list_matches_wl82_addresses(lib):
    expected = {}
    for base, index in ((0x50000, PA), (0x50040, PB), (0x501c0, PH)):
        for n in range(9):
            expected[index + n] = base + 4 * n
    expected.update({IOMAP_CON2: 0x51024, IOMAP_CON3: 0x51028, CLOCK_CON1: 0x10010,
                     UART1_CON0: 0x12100, UART1_CON1: 0x12104, UART1_BAUD: 0x12108,
                     UART1_OTCNT: 0x12110, UART1_RXSADR: 0x1211c, UART1_RXEADR: 0x12120,
                     UART1_RXCNT: 0x12124, UART1_HRXCNT: 0x12128, ADC_CON: 0x13100,
                     ADC_RES: 0x13104, ANA_WLA_CON0: 0x11900, ANA_PLL_CON1: 0x119a4})
    assert {r: lib.lunar_board_address(r) for r in range(COUNT)} == expected
    for bad in (COUNT, COUNT + 1, 1000, -1):
        assert lib.lunar_board_address(bad) == 0 and lib.lunar_board_width(bad) == 0
    assert all(not 0x13700 <= a <= 0x1371f for a in expected.values())
    assert all(not 0x01c80108 <= a <= 0x01c80110 for a in expected.values())
    wide16 = {UART1_CON0, UART1_CON1, UART1_BAUD, UART1_HRXCNT}
    assert all(lib.lunar_board_width(r) == (2 if r in wide16 else 4) for r in range(COUNT))


def test_native_backend_is_target_only():
    for name in ('board_io.c',):
        text = (ROOT / 'firmware/board' / name).read_text()
        native = text[text.index('#ifdef LUNAR_PI32V2'):]
        assert 'volatile' in native and 'volatile' not in text[:text.index('#ifdef LUNAR_PI32V2')]


# ---- key matrix ---------------------------------------------------------------

def test_column_words_select_exactly_one_column(lib):
    for column in range(11):
        word = lib.lunar_matrix_word(column)
        low = [bit for bit in range(16) if not word >> bit & 1]
        assert [b for b in low if b < 11] == [column]
        assert low == ([column, 11 + column] if column < 2 else [column])


def test_init_configures_pins_and_deselects(sim):
    io = sim.sim_io()
    assert sim.lunar_matrix_init(io)
    pa_dir, ph_dir = reg(sim, PA + DIR), reg(sim, PH + DIR)
    for bit in (1, 3, 4, 9, 10):
        assert not pa_dir >> bit & 1, f'PA{bit} output'
    for bit in (0, 5, 6, 7, 8):
        assert pa_dir >> bit & 1 and reg(sim, PA + PU) >> bit & 1 and reg(sim, PA + DIE) >> bit & 1
    assert reg(sim, PB + DIR) >> 7 & 1 and reg(sim, PB + PU) >> 7 & 1
    assert not ph_dir >> 6 & 1 and not ph_dir >> 9 & 1
    assert reg(sim, PA + HD0) & 0x600 == 0x600 and reg(sim, PH + HD) & 0x240 == 0x240
    assert reg(sim, PA + OUT) & 0x600 == 0 and reg(sim, PH + OUT) & 0x240 == 0
    assert sim.sim_counter(5) == 0xffff and sim.sim_counter(3) == 16


def test_key_table_is_fm1_nes_relabelled_to_physical_columns(lib):
    assert [lib.lunar_key_cell(i) for i in range(41)] == [physical(x) for x in NES_LABEL_CELLS]
    assert lib.lunar_key_cell(41) == 0xff
    assert len({physical(x) for x in NES_LABEL_CELLS + NES_ENCODER_LABELS}) == 55


def scan(sim, leds=None):
    rows = (c.c_ubyte * 11)()
    led_array = (c.c_ubyte * 11)(*leds) if leds else None
    assert sim.lunar_matrix_scan(sim.sim_io(), led_array, rows)
    return rows


def decode(sim, rows):
    pressed = (c.c_uint * 2)()
    sim.lunar_keys_decode(rows, pressed)
    return [i for i in range(41) if pressed[i >> 5] >> (i & 31) & 1]


def test_every_key_decodes_alone_through_the_595_chain(sim):
    sim.lunar_matrix_init(sim.sim_io())
    assert decode(sim, scan(sim)) == []
    for key in range(41):
        cell = sim.lunar_key_cell(key)
        sim.sim_press(cell, 1)
        assert decode(sim, scan(sim)) == [key]
        sim.sim_press(cell, 0)


def test_chord_and_scan_order(sim):
    sim.lunar_matrix_init(sim.sim_io())
    for key in (0, 14, 26, 40):
        sim.sim_press(sim.lunar_key_cell(key), 1)
    before = sim.sim_counter(6)
    rows = scan(sim)
    assert decode(sim, rows) == [0, 14, 26, 40]
    assert [sim.sim_latched_at(before + i) for i in range(11)] == \
        [sim.lunar_matrix_word(col) for col in range(11)]
    assert sim.lunar_matrix_select(sim.sim_io(), 11, 0) == 0xff


def test_edges_are_read_modify_write(sim):
    io = sim.sim_io()
    sim.lunar_matrix_init(io)
    sim.sim_set_reg(PA + OUT, reg(sim, PA + OUT) | (1 << 12))   # unrelated pin high
    sim.lunar_matrix_select(io, 4, 0)
    assert reg(sim, PA + OUT) >> 12 & 1


def test_led_lines_follow_the_selected_column(sim):
    io = sim.sim_io()
    sim.lunar_matrix_init(io)
    sim.lunar_matrix_select(io, 3, 0b0101)
    assert reg(sim, PA + OUT) & 0x600 == 0x200 and reg(sim, PH + OUT) & 0x240 == 0x40
    sim.lunar_matrix_select(io, 4, 0b1010)
    assert reg(sim, PA + OUT) & 0x600 == 0x400 and reg(sim, PH + OUT) & 0x240 == 0x200
    sim.lunar_matrix_release(io)
    assert reg(sim, PA + OUT) & 0x600 == 0 and reg(sim, PH + OUT) & 0x240 == 0
    assert sim.sim_counter(5) == 0xffff


DWELL = c.CFUNCTYPE(None, c.c_void_p, c.c_uint)


def test_scan_lit_dwells_once_per_lit_column_with_its_leds_on(sim):
    sim.lunar_matrix_scan_lit.argtypes = [c.c_void_p, c.c_void_p, c.c_void_p, DWELL, c.c_void_p,
                                          c.c_uint]
    io = sim.sim_io()
    sim.lunar_matrix_init(io)
    leds = (c.c_ubyte * 11)(0b0001, 0, 0b0110, 0, 0, 0, 0, 0, 0, 0b1000, 0)
    seen = []

    def dwell(ctx, us):
        pa, ph = reg(sim, PA + OUT), reg(sim, PH + OUT)
        seen.append((us, pa >> 9 & 3, (ph >> 6 & 1) | (ph >> 9 & 1) << 1))

    rows = (c.c_ubyte * 11)()
    assert sim.lunar_matrix_scan_lit(io, leds, rows, DWELL(dwell), None, 200)
    assert [x[0] for x in seen] == [200, 200, 200]       # columns 0, 2, 9 only, equal dwell
    lines = [(pa | ph << 2) for _, pa, ph in seen]
    assert lines == [0b0001, 0b0110, 0b1000]
    assert reg(sim, PA + OUT) & 0x600 == 0 and reg(sim, PH + OUT) & 0x240 == 0   # all off after


def test_scan_lit_without_leds_never_dwells(sim):
    sim.lunar_matrix_scan_lit.argtypes = [c.c_void_p, c.c_void_p, c.c_void_p, DWELL, c.c_void_p,
                                          c.c_uint]
    io = sim.sim_io()
    sim.lunar_matrix_init(io)
    rows = (c.c_ubyte * 11)()
    calls = []
    assert sim.lunar_matrix_scan_lit(io, None, rows, DWELL(lambda *_: calls.append(1)), None, 200)
    assert calls == []


def test_backlight_pa2_active_low(sim):
    io = sim.sim_io()
    sim.sim_set_reg(PA + OUT, 0x4)
    sim.lunar_backlight_on(io)
    assert not reg(sim, PA + OUT) & 4 and not reg(sim, PA + DIR) & 4
    sim.lunar_backlight_off(io)
    assert reg(sim, PA + OUT) & 4


# ---- encoders -----------------------------------------------------------------

def encoder_step(sim, enc, state, a_cell, b_cell, times=2):
    sim.sim_press(a_cell, state & 1)
    sim.sim_press(b_cell, state >> 1 & 1)
    for _ in range(times):
        sim.lunar_encoders_sample(c.byref(enc), scan(sim))


@pytest.mark.parametrize('index', range(7))
def test_encoder_quadrature_counts_and_filter(sim, index):
    sim.lunar_matrix_init(sim.sim_io())
    a, b = (physical(NES_ENCODER_LABELS[2 * index]), physical(NES_ENCODER_LABELS[2 * index + 1]))
    enc = Encoders()
    sim.lunar_encoders_reset(c.byref(enc))
    encoder_step(sim, enc, 0, a, b)
    for state in (2, 3, 1, 0):
        encoder_step(sim, enc, state, a, b)
    assert enc.count[index] == 4
    for state in (1, 3, 2, 0):
        encoder_step(sim, enc, state, a, b)
    assert enc.count[index] == 0
    encoder_step(sim, enc, 2, a, b, times=1)  # one-scan glitch: ignored
    encoder_step(sim, enc, 0, a, b)
    assert enc.count[index] == 0
    encoder_step(sim, enc, 3, a, b)            # both contacts at once: invalid
    assert enc.invalid[index] == 1 and enc.count[index] == 0
    assert all(enc.count[i] == 0 for i in range(7) if i != index)


# ---- ADC ----------------------------------------------------------------------

def test_adc_reads_master_and_battery(sim):
    adc = Adc()
    sim.sim_set_reg(PB + DIE, 0xff)
    sim.sim_set_reg(ANA_WLA_CON0, 0xffffffff)
    sim.sim_set_reg(ANA_PLL_CON1, 0xffffffff)
    assert sim.lunar_adc_init(c.byref(adc), sim.sim_io(), 100)
    assert reg(sim, PB + DIR) & 0x42 == 0x42 and reg(sim, PB + DIE) & 0x42 == 0
    assert reg(sim, PB + PU) & 0x42 == 0 and reg(sim, PB + PD) & 0x42 == 0
    assert reg(sim, ANA_PLL_CON1) == 0xfffeffff
    assert reg(sim, ANA_WLA_CON0) == (0xffffffff & ~0x3c0ff) | 0x20005
    value = c.c_uint()
    sim.sim_adc(4, 777, 5)
    assert sim.lunar_adc_read(c.byref(adc), 4, c.byref(value)) and value.value == 777
    assert reg(sim, ADC_CON) == 0
    sim.sim_adc(3, 560, 2)
    assert sim.lunar_adc_read(c.byref(adc), 3, c.byref(value)) and value.value == 560
    assert not sim.lunar_adc_read(c.byref(adc), 5, c.byref(value))


def test_adc_refuses_owner_and_times_out(sim):
    adc = Adc()
    sim.sim_set_reg(ADC_CON, 0x10)
    assert not sim.lunar_adc_init(c.byref(adc), sim.sim_io(), 100)
    sim.sim_set_reg(ADC_CON, 0)
    assert sim.lunar_adc_init(c.byref(adc), sim.sim_io(), 10)
    sim.sim_adc(4, 1, 50)
    value = c.c_uint(1234)
    assert not sim.lunar_adc_read(c.byref(adc), 4, c.byref(value))
    assert value.value == 1234 and adc.failed and reg(sim, ADC_CON) == 0
    sim.sim_adc(4, 1, 1)
    assert not sim.lunar_adc_read(c.byref(adc), 4, c.byref(value))  # latched


def test_pot_deadband_and_debounce(lib):
    pot = Pot()
    lib.lunar_pot_reset(c.byref(pot))
    assert not any(lib.lunar_pot_update(c.byref(pot), 6) for _ in range(20))
    assert [lib.lunar_pot_update(c.byref(pot), 500) for _ in range(10)] == [0] * 9 + [1]
    assert pot.level == 500 >> 3
    assert [lib.lunar_pot_update(c.byref(pot), 520) for _ in range(9)] == [0] * 9
    lib.lunar_pot_update(c.byref(pot), 500)   # back inside the deadband: restart
    assert [lib.lunar_pot_update(c.byref(pot), 520) for _ in range(10)][-1] == 1


# ---- MIDI parser --------------------------------------------------------------

def parse(lib, data, parser=None):
    parser = parser or Parser()
    lib.lunar_midi_parser_reset(c.byref(parser))
    out, msg = [], Msg()
    for byte in data:
        if lib.lunar_midi_parse(c.byref(parser), byte, c.byref(msg)):
            out.append(bytes([msg.status, msg.data1, msg.data2][:msg.length]))
    return out


def test_midi_running_status_and_lengths(lib):
    assert parse(lib, [0x90, 60, 100, 62, 0, 0xc3, 5, 7, 0xe0, 0, 64]) == [
        b'\x90\x3c\x64', b'\x90\x3e\x00', b'\xc3\x05', b'\xc3\x07', b'\xe0\x00\x40']


def test_midi_realtime_inside_a_message(lib):
    assert parse(lib, [0xb1, 7, 0xf8, 99, 0xfa, 8, 0xfe, 1]) == [
        b'\xf8', b'\xb1\x07\x63', b'\xfa', b'\xfe', b'\xb1\x08\x01']


def test_midi_sysex_is_skipped_and_cancels_running_status(lib):
    data = [0x80, 1, 2, 0xf0, 0x22, 0x24, 0x35, 0x7d, 0xf7, 3, 4, 0x91, 5, 6]
    assert parse(lib, data) == [b'\x80\x01\x02', b'\x91\x05\x06']
    assert parse(lib, [0xf0, 1, 0xf8, 2, 0x90, 1, 2]) == [b'\xf8', b'\x90\x01\x02']


def test_midi_system_common_and_stray_data(lib):
    assert parse(lib, [5, 6, 0xf2, 1, 2, 3, 0xf1, 9, 0xf6, 0xf4, 1, 0xf3, 4]) == [
        b'\xf2\x01\x02', b'\xf1\x09', b'\xf6', b'\xf3\x04']
    assert parse(lib, [0x90, 60, 0x80, 61, 0]) == [b'\x80\x3d\x00']


# ---- UART1 RX -----------------------------------------------------------------

def test_uart_configuration_values(sim):
    uart = Uart()
    size = c.c_uint()
    ring = sim.sim_ring(c.byref(size))
    sim.sim_set_reg(IOMAP_CON3, 0xff)
    sim.sim_set_reg(IOMAP_CON2, 0xffffffff)
    sim.sim_set_reg(CLOCK_CON1, 0xffffffff)
    assert not sim.lunar_midi_uart_configure(c.byref(uart), sim.sim_io(), ring, 100, 0x01c03000)
    assert not sim.lunar_midi_uart_configure(c.byref(uart), sim.sim_io(), ring, 64, 0x01c03008)
    assert sim.lunar_midi_uart_configure(c.byref(uart), sim.sim_io(), ring, size.value, 0x01c03000)
    assert reg(sim, UART1_BAUD) == 383 and reg(sim, UART1_OTCNT) == 60000
    assert reg(sim, UART1_RXSADR) == 0x01c03000 and reg(sim, UART1_RXCNT) == size.value
    assert reg(sim, UART1_RXEADR) == 0x01c03000 + size.value and reg(sim, UART1_CON1) == 0
    assert reg(sim, UART1_CON0) == 0x41
    assert reg(sim, CLOCK_CON1) == 0xfffff7ff
    assert reg(sim, IOMAP_CON3) == 0x5f
    assert reg(sim, IOMAP_CON2) == (0xffffffff & ~0x3f00) | (49 << 8)
    assert reg(sim, PH + DIR) >> 8 & 1 and reg(sim, PH + DIE) >> 8 & 1
    assert reg(sim, PH + PU) >> 8 & 1 and not reg(sim, PH + PD) >> 8 & 1
    other = Uart()
    assert not sim.lunar_midi_uart_configure(c.byref(other), sim.sim_io(), ring, 64, 0x01c03000)


def test_uart_poll_parses_ring_and_recovers_from_overrun(sim):
    uart = Uart()
    size = c.c_uint()
    ring = sim.sim_ring(c.byref(size))
    assert sim.lunar_midi_uart_configure(c.byref(uart), sim.sim_io(), ring, size.value, 0x01c03000)
    got = []

    @EMIT
    def emit(_, msg):
        m = msg.contents
        got.append(bytes([m.status, m.data1, m.data2][:m.length]))

    data = bytes([0x90, 60, 100, 0xf8, 61, 90])
    sim.sim_uart_rx(data, len(data))
    assert sim.lunar_midi_uart_poll(c.byref(uart), 4, emit, None) == 4
    assert sim.lunar_midi_uart_poll(c.byref(uart), 64, emit, None) == 2
    assert got == [b'\x90\x3c\x64', b'\xf8', b'\x90\x3d\x5a']
    # Wrap around the ring several times in bounded chunks.
    got.clear()
    for n in range(100):
        sim.sim_uart_rx(bytes([0x80 | (n & 15), n & 0x7f, 1]), 3)
        assert sim.lunar_midi_uart_poll(c.byref(uart), 64, emit, None) == 3
    assert len(got) == 100 and got[-1] == bytes([0x80 | (99 & 15), 99, 1])
    # A torn message across an overrun is dropped, then parsing resumes.
    sim.sim_uart_rx(bytes([0x90, 1]), 2)
    sim.sim_uart_rx(bytes(size.value), size.value)
    got.clear()
    assert sim.lunar_midi_uart_poll(c.byref(uart), 64, emit, None) == -1
    assert uart.overruns == 1 and uart.pending == 0
    sim.sim_uart_rx(bytes([5, 0x90, 2, 3]), 4)
    assert sim.lunar_midi_uart_poll(c.byref(uart), 64, emit, None) == 4
    assert got == [b'\x90\x02\x03']


def test_uart_poll_reads_hrxcnt_before_clearing_pending(sim):
    uart = Uart()
    size = c.c_uint()
    ring = sim.sim_ring(c.byref(size))
    assert sim.lunar_midi_uart_configure(c.byref(uart), sim.sim_io(), ring, size.value, 0x01c03000)
    got = []

    @EMIT
    def emit(_, msg):
        m = msg.contents
        got.append(bytes([m.status, m.data1, m.data2][:m.length]))

    # The simulator drops the latched count when the pending bits are cleared
    # (a conservative model), so only a read made first sees the bytes.
    sim.sim_uart_rx(bytes([0x90, 60, 100]), 3)
    assert sim.lunar_midi_uart_poll(c.byref(uart), 64, emit, None) == 3
    assert got == [b'\x90\x3c\x64']
    assert reg(sim, UART1_HRXCNT) == 0


def test_uart_drain_rejects_non_power_of_two(sim):
    uart = Uart(ring=sim.sim_ring(c.byref(c.c_uint())), ring_bytes=96)
    assert sim.lunar_midi_uart_drain(c.byref(uart), 0, 1, EMIT(lambda *_: None), None) == -1


# ---- M5 test pattern ----------------------------------------------------------

def stream(lib, function, *args):
    buffer = (c.c_ubyte * 400000)()
    bus = lib.sim_sink(buffer, len(buffer))
    assert function(bus, *args) == 0
    used = lib.sim_sink_used()
    assert used != 0xffffffff
    return bytes(buffer[:used])


def events(blob):
    out, i = [], 0
    while i < len(blob):
        kind = blob[i]
        if kind in (0, 1):
            out.append((kind, blob[i + 1]))
            i += 2
        elif kind == 2:
            out.append((2, None))
            i += 1
        else:
            out.append((3, blob[i + 1] | blob[i + 2] << 8))
            i += 3
    return out


M5_ID = b'8d790e30 2026-11-08'
# Regression pin of the whole sink stream (setup, waits, 115,200 pixel bytes,
# display on) for M5_ID; 230,580 sink bytes.
M5_SHA256 = '81b6a73104af206e78b49bd2a5cea6cc5366b100668d43d7509a0f946cc379fe'


def test_m5_pattern_shares_setup_and_frames_pixels(lib):
    m5 = events(stream(lib, lib.lunar_panel_m5_pattern, M5_ID))
    probe = events(stream(lib, lib.lunar_panel_probe))
    start = m5.index((1, 0x2c))
    assert m5[:start] == probe[:probe.index((1, 0x2c))]
    assert m5[:3] == [(3, 100), (1, 0x11), (2, None)]
    pixels = m5[start + 1:m5.index((2, None), start)]
    assert len(pixels) == 240 * 240 * 2 and all(kind == 0 for kind, _ in pixels)
    assert m5[-2:] == [(1, 0x29), (2, None)]
    words = [pixels[i][1] << 8 | pixels[i + 1][1] for i in range(0, len(pixels), 2)]
    assert words == [lib.lunar_m5_pixel(i % 240, i // 240, M5_ID) for i in range(240 * 240)]


def test_m5_pattern_stream_hash_is_pinned(lib):
    blob = stream(lib, lib.lunar_panel_m5_pattern, M5_ID)
    digest = hashlib.sha256(blob).hexdigest()
    path = os.environ.get('LUNAR_M5_PNG')
    if path:
        write_png(lib, Path(path), M5_ID)
    assert (len(blob), digest) == (230580, M5_SHA256)


def test_m5_pixels(lib):
    px = lambda x, y, i=M5_ID: lib.lunar_m5_pixel(x, y, i)  # noqa: E731
    assert {px(0, 5), px(239, 5), px(5, 0), px(5, 239), px(0, 0)} == {0xffff}
    assert [px(15 + 30 * n, 180) for n in range(8)] == [
        0xffff, 0xffe0, 0x07ff, 0x07e0, 0xf81f, 0xf800, 0x001f, 0x0000]
    assert px(5, 5) == 0x0008 and px(240, 5) == 0 and px(5, 240) == 0
    title = {px(x, y) for x in range(1, 239) for y in range(14, 35)}
    ident = {px(x, y) for x in range(1, 239) for y in range(52, 66)}
    tag = {px(x, y) for x in range(1, 239) for y in range(82, 96)}
    assert title == {0x0008, 0xffff} and ident == {0x0008, 0xffe0} and tag == {0x0008, 0x07ff}
    gaps = [range(35, 52), range(66, 82), range(96, 120)]
    assert all(px(x, y) == 0x0008 for r in gaps for y in r for x in range(1, 239))
    blank = {px(x, y, b'') for x in range(1, 239) for y in range(52, 66)}
    assert blank == {0x0008}
    assert px(120, 60, b'?') == 0x0008 and px(120, 60, b'abc') == px(120, 60, b'ABC')


def write_png(lib, path, build_id):
    rows = []
    for y in range(240):
        row = bytearray([0])
        for x in range(240):
            v = lib.lunar_m5_pixel(x, y, build_id)
            row += bytes([(v >> 11) * 255 // 31, (v >> 5 & 63) * 255 // 63, (v & 31) * 255 // 31])
        rows.append(bytes(row))

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 240, 240, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(b''.join(rows))) + chunk(b'IEND', b''))
