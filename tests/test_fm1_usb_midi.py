"""The FM-1 application's USB-MIDI device (firmware/fm1/fm1_usb_midi.c) on the
host: the device and configuration descriptors byte for byte, the MIDI class
layout walked descriptor by descriptor, the strings, the event-packet
encoder against the app's own decoder, the IN batch and the OUT split. The
SDK glue (fm1_usb_sdk.c) is checked by text only; it builds on aeon
(notes/2026-11-09-usb-midi.md). Host C through ctypes; no device traffic."""
import ctypes as c
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ['firmware/fm1/fm1_usb_midi.c', 'firmware/fm1/fm1_input.c', 'firmware/board/board_io.c',
           'firmware/board/adc.c', 'firmware/board/midi_parser.c',
           'firmware/third_party/fm1-nes/fm1_keys.c', 'firmware/board/host/board_sim.c']

# Stock FM-1 V15 app.bin fragments [verified: bytes; offsets in the note].
# Interface numbers in stock's tables are 0 and patched at run time.
STOCK_PRODUCT = bytes.fromhex('0a0346004d002d003100')
STOCK_MS_HEADER = bytes.fromhex('090400000201030000' '07240100014100')
STOCK_JACKS = bytes.fromhex('062402010100' '092403020201010100' '092403010801070100' '062402020700')
STOCK_ENDPOINTS = bytes.fromhex('090584024000000000' '0525010108' '090504024000000000' '0525010101')
STOCK_AC = bytes.fromhex('090400000001010009' '092401000109000101')
STOCK_CONFIG = bytes.fromhex('090200000001008032')


class Msg(c.Structure):
    _fields_ = [('status', c.c_ubyte), ('data1', c.c_ubyte), ('data2', c.c_ubyte),
                ('length', c.c_ubyte)]


class Batch(c.Structure):
    _fields_ = [('data', c.c_ubyte * 64), ('length', c.c_uint), ('dropped', c.c_uint)]


EMIT = c.CFUNCTYPE(None, c.c_void_p, c.POINTER(c.c_ubyte))


@pytest.fixture(scope='module')
def lib(tmp_path_factory):
    path = tmp_path_factory.mktemp('fm1usb') / 'fm1usb.so'
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
                    '-I', str(ROOT / 'sim/web/src'), *[str(ROOT / s) for s in SOURCES],
                    '-o', str(path)], check=True)
    so = c.CDLL(str(path))
    for name in ('lunar_usb_midi_device_descriptor', 'lunar_usb_midi_config_header'):
        getattr(so, name).restype = c.POINTER(c.c_ubyte)
    for name in ('lunar_usb_midi_function', 'lunar_usb_midi_config', 'lunar_usb_midi_string',
                 'lunar_usb_midi_split'):
        getattr(so, name).restype = c.c_uint
    return so


def device(lib):
    return bytes(lib.lunar_usb_midi_device_descriptor()[:18])


def config(lib):
    buf = (c.c_ubyte * 101)()
    assert lib.lunar_usb_midi_config(buf) == 101
    return bytes(buf)


def walk(blob):
    """Split a descriptor blob into (type, subtype, bytes) by bLength."""
    out, i = [], 0
    while i < len(blob):
        n = blob[i]
        assert n >= 2 and i + n <= len(blob), (i, n)
        d = blob[i:i + n]
        out.append((d[1], d[2] if n > 2 else None, d))
        i += n
    return out


def test_device_descriptor(lib):
    d = device(lib)
    assert d == bytes([18, 1, 0x00, 0x02, 0, 0, 0, 64, 0x4a, 0x4c, 0x55, 0xc7, 0x00, 0x01, 0, 2, 3, 1])
    # Stock's table carries PID 0x4155 and ORs the class bits in at run time
    # to 0xC755 (bench 2026-09-06); everything else is stock's byte for byte.
    stock = bytearray(bytes.fromhex('1201000200000040' '4a4c5541' '000100020301'))
    stock[11] |= 0x86
    assert d == bytes(stock)


def test_configuration_descriptor_bytes(lib):
    cfg = config(lib)
    expected = (bytes.fromhex('090265000201008032')
                + bytes.fromhex('090400000001010000' '092401000109000101')
                + bytes.fromhex('090401000201030000' '07240100014100')
                + STOCK_JACKS + STOCK_ENDPOINTS)
    assert cfg == expected
    header = bytes(lib.lunar_usb_midi_config_header()[:9])
    # The SDK's set_descriptor fills wTotalLength and bNumInterfaces.
    assert header == STOCK_CONFIG


def test_stock_fragments_kept(lib):
    cfg = config(lib)
    assert STOCK_JACKS in cfg and STOCK_ENDPOINTS in cfg
    ms = bytearray(STOCK_MS_HEADER)
    ms[2] = 1                                         # MS interface 1 here
    assert bytes(ms) in cfg
    ac = bytearray(STOCK_AC)
    ac[8] = 0                                         # no AC string (see the note)
    ac[17] = 1
    assert bytes(ac) in cfg


def test_midi_class_layout(lib):
    cfg = config(lib)
    parts = walk(cfg)
    assert parts[0][0] == 0x02
    assert int.from_bytes(cfg[2:4], 'little') == len(cfg) == 101
    interfaces = [p for p in parts if p[0] == 0x04]
    assert cfg[4] == len(interfaces) == 2
    ac, ms = interfaces
    assert (ac[2][2], ac[2][4], ac[2][5], ac[2][6]) == (0, 0, 0x01, 0x01)    # AC, no endpoints
    assert (ms[2][2], ms[2][4], ms[2][5], ms[2][6]) == (1, 2, 0x01, 0x03)    # MIDIStreaming, 2 eps
    # The AC header names the MS interface as its one streaming interface.
    ac_header = next(p[2] for p in parts if p[0] == 0x24 and p[1] == 0x01 and p[2][0] == 9)
    assert ac_header[3:5] == b'\x00\x01' and ac_header[7] == 1 and ac_header[8] == 1
    assert int.from_bytes(ac_header[5:7], 'little') == 9

    # Everything after the MS interface descriptor is the MS function.
    start = cfg.index(ms[2]) + 9
    ms_parts = walk(cfg[start:])
    header = ms_parts[0][2]
    assert header[:5] == bytes([7, 0x24, 0x01, 0x00, 0x01])
    assert int.from_bytes(header[5:7], 'little') == len(cfg) - start == 65

    jacks = {}
    for kind, sub, d in ms_parts:
        if kind == 0x24 and sub == 0x02:              # MIDI IN jack: type, id
            jacks[d[4]] = ('in', d[3], None)
        elif kind == 0x24 and sub == 0x03:            # MIDI OUT jack: type, id, one source
            assert d[5] == 1 and d[7] == 1
            jacks[d[4]] = ('out', d[3], d[6])
    EMBEDDED, EXTERNAL = 1, 2
    assert jacks == {1: ('in', EMBEDDED, None), 2: ('out', EXTERNAL, 1),
                     8: ('out', EMBEDDED, 7), 7: ('in', EXTERNAL, None)}

    endpoints = []
    for i, (kind, _, d) in enumerate(ms_parts):
        if kind == 0x05:
            assert len(d) == 9 and d[3] == 0x02 and int.from_bytes(d[4:6], 'little') == 64
            cs = ms_parts[i + 1][2]
            assert cs[1] == 0x25 and cs[2] == 0x01 and cs[3] == len(cs) - 4
            endpoints.append((d[2], list(cs[4:])))
    # Host OUT feeds the embedded IN jack; the embedded OUT jack feeds host IN.
    assert endpoints == [(0x84, [8]), (0x04, [1])]
    for jack in (1, 8):
        assert jacks[jack][1] == EMBEDDED


def test_function_numbering(lib):
    buf = (c.c_ubyte * 92)()
    assert lib.lunar_usb_midi_function(buf, 3) == 92      # stock's AC 3, MS 4
    blob = bytes(buf)
    assert blob[2] == 3 and blob[17] == 4 and blob[20] == 4
    assert lib.lunar_usb_midi_function(buf, 7) == 0
    assert lib.lunar_usb_midi_function(None, 0) == 0


def string(lib, index, ident=None):
    out = (c.c_ubyte * 64)()
    arg = (c.c_ubyte * 8)(*ident) if ident is not None else None
    n = lib.lunar_usb_midi_string(index, arg, out)
    assert n == out[0] and out[1] == 3
    return bytes(out[:n])


def test_strings(lib):
    assert string(lib, 0) == bytes([4, 3, 0x09, 0x04])
    assert string(lib, 2) == STOCK_PRODUCT
    serial = string(lib, 3, [0x01, 0x23, 0x45, 0x67, 0x89, 0xab, 0xcd, 0xef])
    assert len(serial) == 34 and serial[2:].decode('utf-16-le') == '0123456789ABCDEF'
    assert string(lib, 3)[2:].decode('utf-16-le') == '0' * 16
    for unused in (1, 4, 0xee):
        assert string(lib, unused) == bytes([2, 3])


def encode(lib, status, d1=0, d2=0):
    p = (c.c_ubyte * 4)()
    return bytes(p) if lib.lunar_usb_midi_encode(status, d1, d2, p) else None


def test_encode_and_decode_agree(lib):
    cases = {(0x90, 60, 100): '0990 3c64', (0x83, 60, 0): '0883 3c00', (0xb1, 74, 127): '0bb1 4a7f',
             (0xc2, 5, 99): '0cc2 0500', (0xd0, 64, 9): '0dd0 4000', (0xe0, 0, 64): '0ee0 0040',
             (0xf8, 0, 0): '0ff8 0000', (0xfa, 0, 0): '0ffa 0000'}
    for (s, a, b), want in cases.items():
        packet = encode(lib, s, a, b)
        assert packet == bytes.fromhex(want.replace(' ', '')), hex(s)
        m = Msg()
        assert lib.lunar_fm1_usb_midi_packet((c.c_ubyte * 4)(*packet), c.byref(m)) == 1
        assert m.status == s and m.data1 == (a if s < 0xf0 else 0)
    for refused in (0xf0, 0xf7, 0xf2, 0x40, 0x100):
        assert encode(lib, refused, 1, 2) is None
    assert encode(lib, 0x90, 0xff, 0x80) == bytes([0x09, 0x90, 0x7f, 0x00])


def test_batch(lib):
    b = Batch()
    lib.lunar_usb_midi_batch_reset(c.byref(b))
    for i in range(16):
        assert lib.lunar_usb_midi_batch_add(c.byref(b), (c.c_ubyte * 4)(9, 0x90, i, 1)) == 1
    assert b.length == 64 and b.dropped == 0
    assert lib.lunar_usb_midi_batch_add(c.byref(b), (c.c_ubyte * 4)(9, 0x90, 99, 1)) == 0
    assert b.dropped == 1 and bytes(b.data[60:64]) == bytes([9, 0x90, 15, 1])
    lib.lunar_usb_midi_batch_reset(c.byref(b))
    assert b.length == 0 and b.dropped == 1


def test_split(lib):
    seen = []
    cb = EMIT(lambda ctx, p: seen.append(bytes(p[:4])))
    data = (bytes([0x09, 0x90, 60, 100, 0x08, 0x80, 60, 0, 0x01, 0, 0, 0])
            + bytes(48) + bytes([0x0f, 0xf8, 0, 0]))
    buf = (c.c_ubyte * 64)(*data)
    assert lib.lunar_usb_midi_split(buf, 64, cb, None) == 3
    assert seen == [bytes([9, 0x90, 60, 100]), bytes([8, 0x80, 60, 0]), bytes([0x0f, 0xf8, 0, 0])]
    seen.clear()
    assert lib.lunar_usb_midi_split(buf, 6, cb, None) == 1     # trailing partial packet ignored
    assert lib.lunar_usb_midi_split(None, 64, cb, None) == 0


def test_glue_text():
    glue = (ROOT / 'firmware/fm1/fm1_usb_sdk.c').read_text()
    includes = re.findall(r'#include\s+[<"]([^>"]+)', glue)
    assert includes == ['app_config.h', 'system/includes.h', 'asm/usb.h', 'string.h', 'fm1_usb_midi.h']
    for banned in ('uac_audio', 'ch9.h', 'usb_stack.h', 'usb/device/'):
        assert banned not in ' '.join(includes)
    prio = int(re.search(r'#define USB_PRIORITY (\d+)u', glue).group(1))
    alnk0 = (ROOT / 'firmware/board/alnk0_audio.h').read_text()
    assert prio < int(re.search(r'LUNAR_ALNK0_IRQ_PRIORITY (\d+)u', alnk0).group(1))
    assert int(re.search(r'#define SETUP_BUFFER_BYTES (\d+)u', glue).group(1)) >= 101
    # A weak reference let LTO drop the UUID getter, and every unit's serial
    # read sixteen zeros (found in the 2026-11-09 link); keep it strong.
    assert re.search(r'^extern u8 \*get_norflash_uuid\(void\);$', glue, re.M)
    assert not re.search(r'weak\)\)\s*u8 \*get_norflash_uuid', glue)
    # Never call the spinning write while the endpoint still holds a packet.
    poll = glue[glue.index('unsigned lunar_usb_midi_poll'):]
    assert poll.index('TXCSR_PKT_READY') < poll.index('usb_g_ep_write(0')
    assert 'usb_slave_init' not in glue.split('*/', 1)[1].replace('usb_slave_init inlined', '')
    make = (ROOT / 'tools/jieli/fm1-app.mk').read_text()
    assert 'ifneq ($(filter -DLUNAR_FM1_USB_MIDI=1,$(EXTRA)),)\nFM1_APP_SOURCES += fm1/fm1_usb_midi fm1/fm1_usb_sdk' in make
    main = (ROOT / 'firmware/fm1/fm1_sdk_main.c').read_text()
    assert main.count('#if LUNAR_FM1_USB_MIDI') == 5
