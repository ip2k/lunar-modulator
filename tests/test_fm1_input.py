"""FM-1 application input on the host (firmware/fm1/fm1_input.c): the event
queue, panel debounce and encoder detents, MASTER, the MIDI and USB-MIDI
decoders, and the router that turns events into the pipelined app's
fence-safe actions. Host C through ctypes; no SDK, no device traffic."""
import ctypes as c
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ['firmware/fm1/fm1_input.c', 'firmware/board/board_io.c', 'firmware/board/adc.c',
           'firmware/board/midi_parser.c', 'firmware/third_party/fm1-nes/fm1_keys.c',
           'firmware/board/host/board_sim.c']

KEY, BUTTON, ENCODER, MASTER, NOTE_ON, NOTE_OFF, BEND, PANIC = range(1, 9)
ACT_ON, ACT_OFF, ACT_MASTER, ACT_CUTOFF, ACT_RES = range(1, 6)
# sim/web/src/fm1_panel.h
BTN_OCT_DOWN, BTN_OCT_UP, BTN_FX, BTN_PLAY = 0, 1, 2, 12
ENC_SELECT, ENC_PRESETS, ENC_ALGORITHM, ENC_KNOB1, ENC_KNOB2 = 0, 1, 2, 3, 4
# fm1-nes encoder contacts, label cells (tests/test_board_layer.py)
NES_ENCODER_LABELS = [0x10, 0x20, 0x30, 0x40, 0x91, 0xa1, 0x90, 0xa0,
                      0x70, 0x80, 0x50, 0x60, 0x15, 0x25]


def physical(label_cell):
    return ((((label_cell >> 4) + 10) % 11) << 4) | (label_cell & 15)


class Event(c.Structure):
    _fields_ = [('kind', c.c_uint8), ('a', c.c_uint8), ('b', c.c_uint8), ('c', c.c_uint8),
                ('value', c.c_int16)]


class Queue(c.Structure):
    _fields_ = [('head', c.c_uint32), ('tail', c.c_uint32), ('dropped', c.c_uint32),
                ('slot', Event * 64)]


class Action(c.Structure):
    _fields_ = [('kind', c.c_uint8), ('sound', c.c_uint8), ('note', c.c_uint8),
                ('velocity', c.c_uint8), ('down', c.c_uint8), ('value', c.c_float)]


class Router(c.Structure):
    _fields_ = [('octave', c.c_int), ('key_note', c.c_uint8 * 27),
                ('held', (c.c_uint8 * 128) * 4), ('cutoff', c.c_float), ('resonance', c.c_float),
                ('applied', c.c_uint), ('deferred', c.c_uint), ('ignored', c.c_uint),
                ('full', c.c_int)]


class Msg(c.Structure):
    _fields_ = [('status', c.c_ubyte), ('data1', c.c_ubyte), ('data2', c.c_ubyte),
                ('length', c.c_ubyte)]


EMIT = c.CFUNCTYPE(None, c.c_void_p, c.POINTER(Action))


@pytest.fixture(scope='module')
def lib(tmp_path_factory):
    path = tmp_path_factory.mktemp('fm1input') / 'fm1input.so'
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
                    '-I', str(ROOT / 'sim/web/src'), *[str(ROOT / s) for s in SOURCES],
                    '-o', str(path)], check=True)
    so = c.CDLL(str(path))
    so.lunar_fm1_route.restype = c.c_uint
    so.lunar_fm1_panel_update.restype = c.c_uint
    so.lunar_key_cell.restype = c.c_uint
    return so


def drain(lib, q):
    out, e = [], Event()
    while lib.lunar_fm1_queue_pop(c.byref(q), c.byref(e)):
        out.append((e.kind, e.a, e.b, e.c, e.value))
    return out


def rows_for(cells):
    rows = (c.c_ubyte * 11)(*([0xff] * 11))
    for cell in cells:
        rows[cell >> 4] &= ~(1 << (cell & 15)) & 0xff
    return rows


class Panel:
    def __init__(self, lib):
        self.lib, self.buf, self.q = lib, c.create_string_buffer(1024), Queue()
        lib.lunar_fm1_panel_reset(self.buf)
        lib.lunar_fm1_queue_reset(c.byref(self.q))

    def scan(self, cells=(), master=-1):
        self.lib.lunar_fm1_panel_update(self.buf, rows_for(cells), master, c.byref(self.q))
        return drain(self.lib, self.q)


def route(lib, router, *events):
    got = []
    emit = EMIT(lambda ctx, a: got.append((a.contents.kind, a.contents.sound, a.contents.note,
                                           a.contents.velocity, round(a.contents.value, 4))))
    for kind, a, b, ch, value in events:
        lib.lunar_fm1_route(c.byref(router), c.byref(Event(kind, a, b, ch, value)), emit, None)
    return got


@pytest.fixture
def router(lib):
    r = Router()
    lib.lunar_fm1_router_reset(c.byref(r))
    return r


# ---- queue --------------------------------------------------------------------

def test_queue_is_fifo_and_counts_drops(lib):
    q = Queue()
    lib.lunar_fm1_queue_reset(c.byref(q))
    for i in range(70):
        lib.lunar_fm1_queue_push(c.byref(q), c.byref(Event(KEY, i, 1, 100, 0)))
    assert q.dropped == 6
    assert [e[1] for e in drain(lib, q)] == list(range(64))
    assert lib.lunar_fm1_queue_pop(c.byref(q), c.byref(Event())) == 0
    # wrap-around keeps order
    for i in range(40):
        lib.lunar_fm1_queue_push(c.byref(q), c.byref(Event(KEY, i, 0, 0, 0)))
    assert [e[1] for e in drain(lib, q)] == list(range(40))


# ---- panel --------------------------------------------------------------------

def test_key_needs_two_agreeing_scans(lib):
    p = Panel(lib)
    f3 = lib.lunar_key_cell(14)
    assert p.scan() == []
    assert p.scan([f3]) == []                     # first sight: candidate only
    assert p.scan([f3]) == [(KEY, 0, 1, 100, 0)]  # agreed: key 0 down
    assert p.scan([f3]) == []
    assert p.scan() == []
    assert p.scan() == [(KEY, 0, 0, 100, 0)]


def test_one_scan_glitch_is_ignored(lib):
    p = Panel(lib)
    cell = lib.lunar_key_cell(40)
    p.scan()
    assert p.scan([cell]) == [] and p.scan() == [] and p.scan() == []


def test_button_ids_map_to_panel_buttons(lib):
    p = Panel(lib)
    p.scan()
    for btn_id in (0, 1, 2, 12, 13):
        cell = lib.lunar_key_cell(btn_id)
        p.scan([cell])
        assert p.scan([cell]) == [(BUTTON, btn_id, 1, 0, 0)]
        p.scan()
        assert p.scan() == [(BUTTON, btn_id, 0, 0, 0)]


def test_held_at_power_on_is_not_a_press_until_seen_twice(lib):
    p = Panel(lib)
    cell = lib.lunar_key_cell(20)
    assert p.scan([cell]) == []                   # pass 0 only seeds
    assert p.scan([cell]) == [(KEY, 6, 1, 100, 0)]


@pytest.mark.parametrize('index,enc', [(0, ENC_SELECT), (2, ENC_KNOB1), (6, ENC_PRESETS)])
def test_encoder_cycle_gives_two_detents(lib, index, enc):
    p = Panel(lib)
    a = physical(NES_ENCODER_LABELS[2 * index])
    b = physical(NES_ENCODER_LABELS[2 * index + 1])
    contacts = {0: [], 1: [a], 2: [b], 3: [a, b]}
    events = []
    for state in (0, 2, 3, 1, 0):
        events += p.scan(contacts[state]) + p.scan(contacts[state])
    assert [e for e in events if e[0] == ENCODER] == [(ENCODER, enc, 0, 0, 1)] * 2
    events = []
    for state in (1, 3, 2, 0):
        events += p.scan(contacts[state]) + p.scan(contacts[state])
    assert [e for e in events if e[0] == ENCODER] == [(ENCODER, enc, 0, 0, -1)] * 2


def test_master_sends_first_reading_then_filtered_moves(lib):
    p = Panel(lib)
    assert p.scan(master=0) == [(MASTER, 0, 0, 0, 0)]   # the boot reading: no popup (sim init)
    assert p.scan(master=3) == []
    moved = []
    for _ in range(10):
        moved += p.scan(master=800)
    assert moved == [(MASTER, 100, 1, 0, 0)]            # a move shows the popup


# ---- MIDI ---------------------------------------------------------------------

def midi(lib, status, d1=0, d2=0, length=3):
    e = Event()
    ok = lib.lunar_fm1_midi_event(c.byref(Msg(status, d1, d2, length)), c.byref(e))
    return (e.kind, e.a, e.b, e.c, e.value) if ok else None


def test_midi_messages_follow_the_virtual_fm1(lib):
    assert midi(lib, 0x92, 60, 90) == (NOTE_ON, 60, 90, 2, 0)
    assert midi(lib, 0x92, 60, 0) == (NOTE_OFF, 60, 0, 2, 0)
    assert midi(lib, 0x83, 61, 40) == (NOTE_OFF, 61, 0, 3, 0)
    assert midi(lib, 0xE0, 0, 0x40) == (BEND, 0, 0, 0, 0)
    assert midi(lib, 0xE0, 0x7f, 0x7f) == (BEND, 0, 0, 0, 8191)
    assert midi(lib, 0xB0, 7, 99) == (MASTER, 99, 0, 0, 0)     # MIDI CC7 shows no popup
    assert midi(lib, 0xB5, 123, 0) == (PANIC, 0, 0, 0, 0)
    assert midi(lib, 0xB0, 74, 10) is None
    assert midi(lib, 0xC0, 5, 0, 2) is None
    assert midi(lib, 0xF8, 0, 0, 1) is None


def usb(lib, packet):
    m = Msg()
    ok = lib.lunar_fm1_usb_midi_packet((c.c_ubyte * 4)(*packet), c.byref(m))
    return (m.status, m.data1, m.data2, m.length) if ok else None


def test_usb_midi_event_packets(lib):
    assert usb(lib, [0x09, 0x90, 60, 100]) == (0x90, 60, 100, 3)
    assert usb(lib, [0x18, 0x81, 60, 0]) == (0x81, 60, 0, 3)    # cable 1
    assert usb(lib, [0x0C, 0xC0, 5, 99]) == (0xC0, 5, 0, 2)
    assert usb(lib, [0x0F, 0xF8, 0, 0]) == (0xF8, 0, 0, 1)
    assert usb(lib, [0x09, 0x80, 60, 0]) is None                # CIN disagrees
    assert usb(lib, [0x04, 0xF0, 0x7E, 0x7F]) is None           # SysEx
    assert usb(lib, [0x0F, 0xF0, 0, 0]) is None


# ---- router -------------------------------------------------------------------

def test_keys_play_sound_one_and_release_their_own_note(lib, router):
    got = route(lib, router, (KEY, 0, 1, 100, 0), (BUTTON, BTN_OCT_UP, 1, 0, 0),
                (KEY, 0, 0, 100, 0), (KEY, 0, 1, 100, 0), (KEY, 0, 0, 100, 0))
    assert got == [(ACT_ON, 0, 53, 100, 0), (ACT_OFF, 0, 53, 0, 0),
                   (ACT_ON, 0, 65, 100, 0), (ACT_OFF, 0, 65, 0, 0)]
    assert router.octave == 1


def test_octave_is_bounded(lib, router):
    route(lib, router, *[(BUTTON, BTN_OCT_DOWN, 1, 0, 0)] * 5)
    assert router.octave == -3
    assert route(lib, router, (KEY, 26, 1, 100, 0)) == [(ACT_ON, 0, 53 + 26 - 36, 100, 0)]


def test_midi_channels_map_to_sounds_and_sound_two_defers(lib, router):
    got = route(lib, router, (NOTE_ON, 60, 90, 0, 0), (NOTE_ON, 61, 90, 1, 0),
                (NOTE_ON, 36, 127, 2, 0), (NOTE_ON, 62, 80, 3, 0), (NOTE_ON, 63, 70, 9, 0))
    assert got == [(ACT_ON, 0, 60, 90, 0), (ACT_ON, 2, 36, 127, 0), (ACT_ON, 3, 62, 80, 0),
                   (ACT_ON, 0, 63, 70, 0)]
    assert router.deferred == 1


def test_note_off_only_for_notes_it_started(lib, router):
    assert route(lib, router, (NOTE_OFF, 60, 0, 0, 0)) == []
    assert router.ignored == 1
    got = route(lib, router, (NOTE_ON, 60, 90, 0, 0), (NOTE_ON, 60, 90, 0, 0),
                (NOTE_OFF, 60, 0, 0, 0), (NOTE_OFF, 60, 0, 0, 0), (NOTE_OFF, 60, 0, 0, 0))
    assert [g[0] for g in got] == [ACT_ON, ACT_ON, ACT_OFF, ACT_OFF]


def test_panic_releases_everything_held(lib, router):
    route(lib, router, (KEY, 3, 1, 100, 0), (NOTE_ON, 70, 90, 2, 0), (NOTE_ON, 70, 90, 2, 0))
    got = route(lib, router, (PANIC, 0, 0, 0, 0))
    assert sorted(got) == [(ACT_OFF, 0, 56, 0, 0), (ACT_OFF, 2, 70, 0, 0), (ACT_OFF, 2, 70, 0, 0)]
    assert route(lib, router, (KEY, 3, 0, 100, 0)) == []


def test_knob1_cutoff_in_semitones_and_clamped(lib, router):
    got = route(lib, router, (ENCODER, ENC_KNOB1, 0, 0, 12), (ENCODER, ENC_KNOB1, 0, 0, -24))
    assert got == [(ACT_CUTOFF, 0, 0, 0, 4800.0), (ACT_CUTOFF, 0, 0, 0, 1200.0)]
    got = route(lib, router, (ENCODER, ENC_KNOB1, 0, 0, 127), (ENCODER, ENC_KNOB1, 0, 0, -127),
                (ENCODER, ENC_KNOB1, 0, 0, 12))
    assert [g[4] for g in got] == [18000.0, 20.0, 40.0]


def test_knob2_resonance_and_other_controls(lib, router):
    got = route(lib, router, (ENCODER, ENC_KNOB2, 0, 0, 3), (ENCODER, ENC_KNOB2, 0, 0, 100),
                (MASTER, 127, 0, 0, 0), (ENCODER, ENC_ALGORITHM, 0, 0, 1),
                (BUTTON, BTN_PLAY, 1, 0, 0), (BEND, 0, 0, 0, 4000))
    assert got == [(ACT_RES, 0, 0, 0, 0.4), (ACT_RES, 0, 0, 0, 1.0), (ACT_MASTER, 0, 0, 0, 1.0)]
    assert router.deferred == 3


# ---- full-UI mode (LUNAR_FM1_FULL_UI): every control reaches the app ---------------

(ACT_UI_KEY, ACT_UI_BUTTON, ACT_UI_ENCODER, ACT_BEND, ACT_PANIC) = range(6, 11)


class Peekable(Queue):
    pass


def route_full(lib, router, *events):
    got = []
    emit = EMIT(lambda ctx, a: got.append((a.contents.kind, a.contents.note, a.contents.velocity,
                                           a.contents.down, round(a.contents.value, 4))))
    for kind, a, b, ch, value in events:
        lib.lunar_fm1_route(c.byref(router), c.byref(Event(kind, a, b, ch, value)), emit, None)
    return got


@pytest.fixture
def full_router(lib):
    r = Router()
    lib.lunar_fm1_router_reset(c.byref(r))
    lib.lunar_fm1_router_set_full(c.byref(r), 1)
    return r


def test_full_mode_sends_all_14_buttons_both_edges(lib, full_router):
    events = [(BUTTON, b, d, 0, 0) for b in range(14) for d in (1, 0)]
    got = route_full(lib, full_router, *events)
    assert got == [(ACT_UI_BUTTON, b, 0, d, 0.0) for b in range(14) for d in (1, 0)]
    assert route_full(lib, full_router, (BUTTON, 14, 1, 0, 0)) == []     # out of range


def test_full_mode_sends_all_7_encoders_both_ways(lib, full_router):
    events = [(ENCODER, e, 0, 0, d) for e in range(7) for d in (1, -1)]
    got = route_full(lib, full_router, *events)
    assert got == [(ACT_UI_ENCODER, e, 0, 0, float(d)) for e in range(7) for d in (1, -1)]
    assert route_full(lib, full_router, (ENCODER, 7, 0, 0, 1), (ENCODER, 0, 0, 0, 0)) == []


def test_full_mode_sends_all_27_keys_with_the_default_velocity(lib, full_router):
    got = route_full(lib, full_router, *[(KEY, k, 1, 0, 0) for k in range(27)])
    assert [g[:2] for g in got] == [(ACT_UI_KEY, k) for k in range(27)]
    assert {g[2] for g in got} == {100}
    assert route_full(lib, full_router, (KEY, 27, 1, 100, 0)) == []


def test_full_mode_bend_follows_the_simulator_scale(lib, full_router):
    got = route_full(lib, full_router, (BEND, 0, 0, 0, 0), (BEND, 0, 0, 0, 8191),
                     (BEND, 0, 0, 0, -8192))
    assert [g[4] for g in got] == [0.0, 1.9998, -2.0]


def test_full_mode_master_carries_the_popup_flag(lib, full_router):
    got = route_full(lib, full_router, (MASTER, 127, 1, 0, 0), (MASTER, 64, 0, 0, 0))
    assert got == [(ACT_MASTER, 0, 1, 0, 1.0), (ACT_MASTER, 0, 0, 0, round(64 / 127, 4))]


def test_full_mode_panic_clears_the_note_balance(lib, full_router):
    route_full(lib, full_router, (NOTE_ON, 70, 90, 2, 0))
    got = route_full(lib, full_router, (PANIC, 0, 0, 0, 0))
    assert got == [(ACT_PANIC, 0, 0, 0, 0.0)]
    assert route_full(lib, full_router, (NOTE_OFF, 70, 0, 2, 0)) == []


def barrier(lib, router, *event):
    return lib.lunar_fm1_event_barrier(c.byref(router), c.byref(Event(*event)))


def test_barrier_classification(lib, router, full_router):
    ui = [(KEY, 0, 1, 100, 0), (BUTTON, 3, 1, 0, 0), (ENCODER, 2, 0, 0, 1), (BEND, 0, 0, 0, 5),
          (PANIC, 0, 0, 0, 0), (NOTE_ON, 60, 90, 1, 0), (NOTE_OFF, 60, 0, 1, 0)]
    for e in ui:
        assert barrier(lib, full_router, *e) == 1, e
        assert barrier(lib, router, *e) == 0, e          # default mode never holds
    for e in [(NOTE_ON, 60, 90, 0, 0), (NOTE_ON, 36, 90, 2, 0), (NOTE_OFF, 62, 0, 3, 0),
              (MASTER, 10, 1, 0, 0)]:
        assert barrier(lib, full_router, *e) == 0, e     # the fast path


def test_queue_peek_does_not_consume(lib):
    q = Queue()
    lib.lunar_fm1_queue_reset(c.byref(q))
    e = Event()
    assert lib.lunar_fm1_queue_peek(c.byref(q), c.byref(e)) == 0
    lib.lunar_fm1_queue_push(c.byref(q), c.byref(Event(KEY, 5, 1, 100, 0)))
    lib.lunar_fm1_queue_push(c.byref(q), c.byref(Event(KEY, 6, 1, 100, 0)))
    assert lib.lunar_fm1_queue_peek(c.byref(q), c.byref(e)) == 1 and e.a == 5
    assert lib.lunar_fm1_queue_peek(c.byref(q), c.byref(e)) == 1 and e.a == 5
    assert [x[1] for x in drain(lib, q)] == [5, 6]


# ---- LEDs and battery ----------------------------------------------------------

def pack(lib, lit):
    led = (c.c_uint8 * 41)(*[1 if i in lit else 0 for i in range(41)])
    cols = (c.c_ubyte * 11)()
    placed = lib.lunar_fm1_leds_pack(led, cols)
    return placed, list(cols)


def test_every_led_has_its_own_cell_and_line(lib):
    seen = set()
    for i in range(41):
        placed, cols = pack(lib, {i})
        assert placed == 41
        lit = [(col, bit) for col, m in enumerate(cols) for bit in range(4) if m >> bit & 1]
        assert len(lit) == 1, i
        assert lit[0] not in seen, i
        seen.add(lit[0])
        id_ = 14 + i if i < 27 else i - 27
        cell = lib.lunar_key_cell(id_)
        assert lit[0] == (cell >> 4, (cell & 15) - 1)    # LED line = row bit - 1
    assert len(seen) == 41


def test_button_leds_follow_the_button_map(lib):
    # A button's LED is at the physical cell the panel reads that button from.
    bmap = list((c.c_uint8 * 14).in_dll(lib, 'lunar_fm1_button_map'))
    for button in range(14):
        placed, cols = pack(lib, {27 + button})
        lit = [(col, bit) for col, m in enumerate(cols) for bit in range(4) if m >> bit & 1]
        cell = lib.lunar_key_cell(bmap.index(button))
        assert lit == [(cell >> 4, (cell & 15) - 1)], button


def test_leds_all_off_and_all_on(lib):
    assert pack(lib, set()) == (41, [0] * 11)
    placed, cols = pack(lib, set(range(41)))
    assert placed == 41 and all(m & ~0xf == 0 for m in cols) and sum(bin(m).count('1') for m in cols) == 41


@pytest.mark.parametrize('raw,cls', [(0, 0), (530, 0), (531, 1), (560, 1), (561, 2), (590, 2),
                                     (591, 3), (1023, 3)])
def test_battery_class_thresholds(lib, raw, cls):
    assert lib.lunar_fm1_battery_class(raw) == cls
