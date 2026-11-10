"""tools/fm1-transporter/fm1t_m5.py: the M5 host tool, against a scripted fake of
the FM-1 Transporter data port (src/transporter_proto.c at kurogedelic
FM-1-transporter 80c5012). No serial port is opened by any test."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import re
import zlib

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'fm1-transporter' / 'fm1t_m5.py'
spec = importlib.util.spec_from_file_location('fm1t_m5', TOOL)
m5 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m5)

PORT = '/dev/serial/by-id/usb-kurogedelic_FM-1_Transporter_0123456789ABCDEF-if02'
CONSOLE = '/dev/serial/by-id/usb-kurogedelic_FM-1_Transporter_0123456789ABCDEF-if00'
IMAGE = bytes((i * 7 + 3) & 0xFF for i in range(4160))       # 4,096 + 64, like m5.bin
IMAGE_SHA = hashlib.sha256(IMAGE).hexdigest()
LOADER = bytes((i * 13 + 5) & 0xFF for i in range(24064))
LOADER_SHA = hashlib.sha256(LOADER).hexdigest()
FLASH = random.Random(1).randbytes(0x100000)


def crc(data):
    return zlib.crc32(data) & 0xFFFFFFFF


def strtoul(text, base):
    """C strtoul on a token: the longest valid prefix, 0 when there is none."""
    t = text.lstrip(' \t')
    if base == 0:
        if t[:2].lower() == '0x':
            base, t = 16, t[2:]
        elif t[:1] == '0':
            base = 8
        else:
            base = 10
    elif base == 16 and t[:2].lower() == '0x':
        t = t[2:]
    digits = '0123456789abcdef'[:base]
    n = 0
    while t and t[0].lower() in digits:
        n = n * base + digits.index(t[0].lower())
        t = t[1:]
    return n & 0xFFFFFFFF


def first_word_after(line, start):
    """`strtoul(strchr(rx_line + start, ' ') + 1, NULL, 0)`, or 0 without a space."""
    i = line.find(' ', start)
    return strtoul(line[i + 1:], 0) if i >= 0 else 0


class FakeTransporter:
    """The data port's line protocol and state, after transporter_proto.c:
    core 0's line and payload collection, core 1's command handlers."""

    def __init__(self, *, uboot=True, v15=False, jump='timeout', jump_ms=2003,
                 read_fail=False, info='OK key=980F type=3 id=856014', flash=FLASH,
                 memw_reply=None, loader=False, loader_running=False, corrupt_memr=False,
                 keying=False):
        self.uboot, self.v15 = uboot, v15
        self.jump, self.jump_ms = jump, jump_ms
        self.read_fail, self.info_reply, self.flash = read_fail, info, flash
        self.memw_reply, self.corrupt_memr = memw_reply, corrupt_memr
        self.keying = keying           # core 1 busy with USB_KEY: only core 0 answers
        self.pending = None            # the one request core 0 holds for core 1
        self.dropped = []              # lines core 0 dropped while a request was pending
        self.loader_buf = bytearray(LOADER) if loader else bytearray(24064)
        self.loader_have = 24064 if loader else 0
        self.loader_running = loader_running
        self.sram = {}
        self.out = bytearray()
        self.wire = bytearray()        # every byte the host wrote
        self.lines = []                # every request line
        self.softkey_sent = False
        self.flash_written = False
        self.runapp_sent = False
        self.jumps = []                # (addr, arg) of every jump core 1 served
        self.rebooted = False
        self.closed = False
        self.timeout = 1
        self._line = bytearray()
        self._payload = None           # (request line, expected length)
        self._buf = bytearray()

    # -- pyserial surface
    @property
    def in_waiting(self):
        return len(self.out)

    def write(self, data):
        assert not self.closed
        self.wire += data
        for b in data:
            self._rx(b)
        return len(data)

    def flush(self):
        pass

    def readline(self):
        i = self.out.find(b'\n')
        if i < 0:
            data, self.out = bytes(self.out), bytearray()
            return data
        data, self.out = bytes(self.out[:i + 1]), self.out[i + 1:]
        return data

    def read(self, n):
        data, self.out = bytes(self.out[:n]), self.out[n:]
        return data

    def reset_input_buffer(self):
        self.out.clear()

    def close(self):
        self.closed = True

    # -- core 0
    def _rx(self, b):
        if self._payload:
            self._buf.append(b)
            line, n = self._payload
            if len(self._buf) == n:
                self._payload = None
                self._request(line, bytes(self._buf))
            return
        if b == 0x0D:
            return
        if b != 0x0A:
            self._line.append(b)
            return
        line, self._line = self._line.decode('latin-1')[:63], bytearray()
        self.lines.append(line)
        if line == 'rekey':
            self._tx('OK rekey')
            self.rebooted = True
            return
        if line == 'ping':
            self._tx('PONG')
            return
        if self.pending is not None:
            self.dropped.append(line)      # `if (req_pending) continue;`
            return
        if line.startswith('wsec '):
            self._payload, self._buf = (line, 4096), bytearray()
            return
        if line.startswith('ldr ') or line.startswith('memw '):
            n = first_word_after(line, 4 if line.startswith('ldr ') else 5)
            if 1 <= n <= 4096:
                self._payload, self._buf = (line, n), bytearray()
                return
        self._request(line, b'')

    def _request(self, line, payload):
        """`req_pending = true`: core 1 serves it now, or after the USB_KEY
        handoff while it is still keying (until then, core 0 drops new lines)."""
        if self.keying:
            self.pending = line
            return
        self._poll(line, payload)

    def _tx(self, text):
        self.out += text.encode() + b'\n'

    # -- core 1
    def _poll(self, line, payload):
        argv = [t for t in re.split('[ \t]+', line) if t][:4]     # strtok, argc < 4
        if not argv:
            return
        cmd, argc = argv[0], len(argv)
        if cmd == 'status':
            self._tx(f'OK uboot={int(self.uboot)} v15={int(self.v15)} '
                     f'loader={int(self.loader_have == 24064)} '
                     f'loader_running={int(self.loader_running)}')
        elif cmd == 'uboot':
            if self.uboot:
                self._tx('OK uboot')
            elif self.v15:
                self.softkey_sent = True
                self._tx('OK softkey')
            else:
                self._tx('ERR no-v15')
        elif cmd == 'info':
            if not self.uboot:
                self._tx('ERR no-uboot')
            elif not self._ensure_loader():
                self._tx('ERR info')
            else:
                self._tx(self.info_reply)
        elif cmd == 'read' and argc == 3:
            addr, n = strtoul(argv[1], 0), strtoul(argv[2], 0)
            if not self.uboot:
                self._tx('ERR no-uboot')
            elif n == 0 or addr >= 0x100000 or n > 0x100000 - addr:
                self._tx('ERR range')
            elif not self._ensure_loader():
                self._tx('ERR loader')
            else:
                self._tx(f'DATA {n}')
                if self.read_fail:
                    self.out += bytes(n)
                    self._tx('END FAIL')
                else:
                    data = self.flash[addr:addr + n]
                    self.out += data
                    self._tx(f'END {crc(data):08X}')
        elif cmd == 'runapp':
            self.runapp_sent = True
            self._tx('OK' if self.loader_running else 'ERR no-loader')
            self.loader_running = False
        elif cmd == 'wsec' and argc == 3:
            if self.uboot:
                self.flash_written = True
            self._tx('OK' if self.uboot else 'ERR no-uboot')
        elif cmd == 'ldr' and argc == 4:
            off, n, c = strtoul(argv[1], 0), strtoul(argv[2], 0), strtoul(argv[3], 16)
            if crc(payload) != c:
                self._tx(f'ERR crc {crc(payload):08X}')
            elif self.loader_running:
                self._tx('ERR loader-running')
            else:
                if off == 0:
                    self.loader_have = 0           # jl_loader_load: restart at 0
                if off != self.loader_have or n > 24064 - off:
                    self._tx('ERR loader-range')
                else:
                    self.loader_buf[off:off + n] = payload
                    self.loader_have += n
                    self._tx('OK')
        elif cmd == 'memw' and argc == 4:
            addr, n, c = strtoul(argv[1], 0), strtoul(argv[2], 0), strtoul(argv[3], 16)
            if not self.uboot:
                self._tx('ERR no-uboot')
            elif not 1 <= n <= 4096:
                self._tx('ERR len')
            elif crc(payload) != c:
                self._tx(f'ERR crc {crc(payload):08X}')
            elif self.loader_running:
                self._tx('ERR loader-running')
            elif self.memw_reply:
                self._tx(self.memw_reply)
            else:
                for i, b in enumerate(payload):
                    self.sram[addr + i] = b
                self._tx('OK')
        elif cmd == 'memr' and argc == 3:
            addr, n = strtoul(argv[1], 0), strtoul(argv[2], 0)
            if not self.uboot:
                self._tx('ERR no-uboot')
            elif not 1 <= n <= 4096:
                self._tx('ERR len')
            elif self.loader_running:
                self._tx('ERR loader-running')
            else:
                data = bytearray(self.sram.get(addr + i, 0) for i in range(n))
                if self.corrupt_memr:
                    data[0] ^= 0xFF
                self._tx(f'DATA {n}')
                self.out += data
                self._tx(f'END {crc(data):08X}')
        elif cmd == 'jump' and argc == 3:
            self.jumps.append((strtoul(argv[1], 0), strtoul(argv[2], 0) & 0xFFFF))
            if not self.uboot:
                self._tx('ERR no-uboot')
            elif self.loader_running:
                self._tx('ERR loader-running')
            elif self.jump == 'timeout':
                self.uboot = False
                self._tx(f'ERR jump ms={self.jump_ms}')
            elif self.jump == 'ok':
                self._tx('OK ms=4')
            elif self.jump == 'fast':
                self._tx('ERR jump ms=3')
            elif self.jump == 'garbage':
                self._tx('HELLO')
            # 'silent': no reply
        else:
            self._tx('ERR unknown')

    def _ensure_loader(self):
        if self.loader_running:
            return True
        if not self.uboot or self.loader_have != 24064:
            return False
        self.loader_running = True
        return True


@pytest.fixture(autouse=True)
def approved(monkeypatch):
    """Tests run against a synthetic image and loader; the real hashes stay pinned
    in the tool and are checked by test_approved_constants."""
    monkeypatch.setattr(m5, 'APPROVED_IMAGE_SHA256', IMAGE_SHA)
    monkeypatch.setattr(m5, 'APPROVED_IMAGE_BYTES', len(IMAGE))
    monkeypatch.setattr(m5, 'LOADER_SHA256', LOADER_SHA)


@pytest.fixture(autouse=True)
def no_serial(monkeypatch):
    def refuse(*_a, **_k):
        raise AssertionError('a test tried to open a real serial port')
    monkeypatch.setattr(m5, 'open_port', refuse)


@pytest.fixture
def files(tmp_path):
    (tmp_path / 'm5.bin').write_bytes(IMAGE)
    (tmp_path / 'wl82loader.bin').write_bytes(LOADER)
    return tmp_path


def run(fake, argv, tmp_path, environ=None, log='log.jsonl'):
    opened = []

    def opener(port):
        opened.append(port)
        return fake

    code = m5.main(['--port', PORT, '--log', str(tmp_path / log)] + argv,
                   environ=environ or {}, opener=opener)
    events = []
    if (tmp_path / log).exists():
        events = [json.loads(x) for x in (tmp_path / log).read_text().splitlines()]
    return code, events, opened


def ramrun_argv(files, sha=IMAGE_SHA):
    return ['ramrun', str(files / 'm5.bin'), '--sha256', sha]


# -- constants ---------------------------------------------------------------

def test_approved_constants():
    src = TOOL.read_text()
    assert 'APPROVED_IMAGE_SHA256 = "a60410deb4ac5cedd5be2ab76c6155a604ae2efa43cea59430bf55c28d8d44e4"' in src
    assert 'APPROVED_IMAGE_BYTES = 4160' in src
    assert 'APPROVED_BUILD_ID = "m5-plan-1"' in src
    assert 'LOADER_SHA256 = "d41da6126760c9d66660bcc0cac8d27d221806c5e369a8036921efe68dca5376"' in src
    assert m5.RAM_BASE == 0x01C02000 and m5.RAM_END == 0x01C06000 and m5.JUMP_ARG == 1
    assert m5.RAM_BASE + 4160 == 0x01C03040        # the approved write range's end


def test_no_override_flag_for_the_image():
    src = TOOL.read_text()
    assert 'allow-other-image' not in src and 'allow_other_image' not in src
    for action in m5.build_parser()._subparsers._group_actions[0].choices['ramrun']._actions:
        assert not {'--loader', '--addr', '--arg', '--clear', '--poke', '--read'} & set(action.option_strings)


# -- happy path --------------------------------------------------------------

def test_ramrun_happy_path_wire_sequence(files, tmp_path):
    fake = FakeTransporter()
    code, events, opened = run(fake, ramrun_argv(files), tmp_path)
    assert code == 0
    assert opened == [PORT]
    first, rest = IMAGE[:4096], IMAGE[4096:]
    assert fake.lines == [
        'ping', 'status',
        f'memw 0x1c02000 4096 {crc(first):08X}',
        f'memw 0x1c03000 64 {crc(rest):08X}',
        'memr 0x1c02000 4096', 'memr 0x1c03000 64',
        'jump 0x1c02000 0x1',
    ]
    assert fake.wire == (b'ping\nstatus\n'
                         + f'memw 0x1c02000 4096 {crc(first):08X}\n'.encode() + first
                         + f'memw 0x1c03000 64 {crc(rest):08X}\n'.encode() + rest
                         + b'memr 0x1c02000 4096\nmemr 0x1c03000 64\njump 0x1c02000 0x1\n')
    written = sorted(fake.sram)
    assert written[0] == 0x01C02000 and written[-1] == 0x01C0303F and len(written) == 4160
    assert not fake.softkey_sent and not fake.flash_written and fake.closed
    end = events[-1]
    assert end['event'] == 'end' and end['exit'] == 0
    assert end['readback'] == 'equal' and end['jump_reply'] == 'ERR jump ms=2003'
    assert 'presumed running' in end['verdict']


def test_receipt_records_every_line_and_payload(files, tmp_path):
    fake = FakeTransporter()
    code, events, _ = run(fake, ramrun_argv(files), tmp_path)
    assert code == 0
    start = events[0]
    assert start['event'] == 'start' and start['cmd'] == 'ramrun' and start['port'] == PORT
    assert start['image_sha256'] == IMAGE_SHA and start['build_id'] == 'm5-plan-1'
    assert start['tool_sha256'] == hashlib.sha256(TOOL.read_bytes()).hexdigest()
    tx = [e['line'] for e in events if e['event'] == 'tx']
    assert tx == fake.lines
    payloads = [e for e in events if e['event'] == 'tx-bytes']
    assert [(p['len'], p['sha256']) for p in payloads] == [
        (4096, hashlib.sha256(IMAGE[:4096]).hexdigest()),
        (64, hashlib.sha256(IMAGE[4096:]).hexdigest())]
    rx = [e['line'] for e in events if e['event'] == 'rx']
    assert rx == ['PONG', 'OK uboot=1 v15=0 loader=0 loader_running=0', 'OK', 'OK',
                  'DATA 4096', f'END {crc(IMAGE[:4096]):08X}',
                  'DATA 64', f'END {crc(IMAGE[4096:]):08X}', 'ERR jump ms=2003']
    assert all('time' in e for e in events)
    # the bytes themselves are not in the receipt, only their summary
    assert IMAGE[:64].hex() not in (tmp_path / 'log.jsonl').read_text()


# -- refusals before the port opens -------------------------------------------

def test_ramrun_refused_without_uboot(files, tmp_path):
    fake = FakeTransporter(uboot=False, v15=True)
    code, events, _ = run(fake, ramrun_argv(files), tmp_path)
    assert code == 3
    assert fake.lines == ['ping', 'status']
    assert not fake.softkey_sent
    assert 'USB_KEY' in events[-1]['verdict'] and 'rekey' in events[-1]['verdict']


def test_ramrun_refused_when_loader_present(files, tmp_path):
    for kw in ({'loader': True}, {'loader': True, 'loader_running': True}):
        fake = FakeTransporter(**kw)
        code, events, _ = run(fake, ramrun_argv(files), tmp_path, log=f'{len(kw)}.jsonl')
        assert code == 3 and fake.lines == ['ping', 'status']
        assert 'fresh ROM entry' in events[-1]['verdict']


def test_hash_mismatch_refused_before_port(files, tmp_path):
    fake = FakeTransporter()
    code, events, opened = run(fake, ramrun_argv(files, sha='0' * 64), tmp_path)
    assert code == 1 and opened == [] and fake.wire == b'' and events == []


def test_other_image_with_its_own_hash_refused(files, tmp_path):
    other = bytes(4160)
    (files / 'other.bin').write_bytes(other)
    fake = FakeTransporter()
    code, _, opened = run(fake, ['ramrun', str(files / 'other.bin'), '--sha256',
                                 hashlib.sha256(other).hexdigest()], tmp_path)
    assert code == 1 and opened == []
    with pytest.raises(m5.Refused, match='not the approved M5 image'):
        m5.admit_image(files / 'other.bin', hashlib.sha256(other).hexdigest())


def test_oversize_image_refused(files, tmp_path):
    big = bytes(0x4001)                    # 0x01C02000 + 0x4001 > 0x01C06000
    (files / 'big.bin').write_bytes(big)
    with pytest.raises(m5.Refused, match='past 0x01c06000'):
        m5.admit_image(files / 'big.bin', hashlib.sha256(big).hexdigest())
    fake = FakeTransporter()
    code, _, opened = run(fake, ['ramrun', str(files / 'big.bin'), '--sha256',
                                 hashlib.sha256(big).hexdigest()], tmp_path)
    assert code == 1 and opened == []


def test_sha256_required(files, tmp_path):
    with pytest.raises(SystemExit) as exc:
        m5.main(['--port', PORT, '--log', str(tmp_path / 'l'), 'ramrun', str(files / 'm5.bin')],
                environ={}, opener=lambda p: pytest.fail('opened'))
    assert exc.value.code == 2


@pytest.mark.parametrize('flag', ['--loader', '--clear', '--poke', '--read', '--addr', '--arg'])
def test_ramrun_refused_flags(files, tmp_path, flag):
    fake = FakeTransporter()
    for argv in (ramrun_argv(files) + [flag, '0x1c02000:4'],
                 ramrun_argv(files) + [f'{flag}=0x1c02000:4']):
        code, _, opened = run(fake, argv, tmp_path)
        assert code == 1 and opened == [] and fake.wire == b''


def test_ramrun_refuses_fm1t_loader_env(files, tmp_path):
    fake = FakeTransporter()
    code, _, opened = run(fake, ramrun_argv(files), tmp_path,
                          environ={'FM1T_LOADER': str(files / 'wl82loader.bin')})
    assert code == 1 and opened == [] and fake.wire == b''


@pytest.mark.parametrize('port', [
    CONSOLE, '/dev/ttyACM0', '/dev/cu.usbmodem1101', '',
    '/dev/serial/by-id/usb-Raspberry_Pi_Pico_E661-if02',
    '/dev/serial/by-id/usb-kurogedelic_FM-1_Transporter_X-if00-if02x'])
def test_port_must_be_the_data_port(files, tmp_path, port):
    fake = FakeTransporter()
    code = m5.main(['--port', port, '--log', str(tmp_path / 'l.jsonl')] + ramrun_argv(files),
                   environ={}, opener=lambda p: pytest.fail('opened'))
    assert code == 1 and fake.wire == b''


def test_log_required_and_never_overwritten(files, tmp_path):
    code = m5.main(['--port', PORT] + ramrun_argv(files), environ={},
                   opener=lambda p: pytest.fail('opened'))
    assert code == 1
    old = tmp_path / 'old.jsonl'
    old.write_text('keep\n')
    code = m5.main(['--port', PORT, '--log', str(old)] + ramrun_argv(files), environ={},
                   opener=lambda p: pytest.fail('opened'))
    assert code == 1 and old.read_text() == 'keep\n'


# -- the jump ----------------------------------------------------------------

@pytest.mark.parametrize('mode,ms,code', [
    ('timeout', 2003, 0), ('timeout', 1500, 0), ('timeout', 10000, 0),
    ('timeout', 1499, 3), ('timeout', 10001, 3),
    ('ok', None, 3), ('fast', None, 3), ('silent', None, 3), ('garbage', None, 3)])
def test_jump_verdicts(files, tmp_path, mode, ms, code):
    fake = FakeTransporter(jump=mode, jump_ms=ms or 2003)
    got, events, _ = run(fake, ramrun_argv(files), tmp_path)
    assert got == code
    assert fake.lines[-1] == 'jump 0x1c02000 0x1'
    assert fake.lines.count('jump 0x1c02000 0x1') == 1
    assert fake.closed
    assert events[-1]['exit'] == code


def test_jump_verdict_function():
    assert m5.jump_verdict('ERR jump ms=2000')[0] == 0
    assert m5.jump_verdict('ERR jump ms=12')[0] != 0
    assert m5.jump_verdict('OK ms=2000')[0] != 0
    assert m5.jump_verdict('')[0] != 0
    assert m5.jump_verdict('ERR loader-running')[0] != 0
    assert m5.jump_verdict('ERR jump ms=2000 extra')[0] != 0


def write_image(link):
    for off in (0, 4096):
        chunk = IMAGE[off:off + 4096]
        link.send_line(f'memw {0x1c02000 + off:#x} {len(chunk)} {crc(chunk):08X}')
        link.send_payload(chunk)
        assert link.recv_line(1) == 'OK'


def test_nothing_sent_after_jump():
    fake = FakeTransporter()
    link = m5.Link(fake, 'ramrun', lambda *a, **k: None, image=IMAGE)
    link.request('ping', 1)
    write_image(link)
    link.request('jump 0x1c02000 0x1', 1)
    wire = bytes(fake.wire)
    for line in ('status', 'ping', 'jump 0x1c02000 0x1', 'memr 0x1c02000 64'):
        with pytest.raises(m5.Refused, match='after the jump'):
            link.send_line(line)
    assert fake.wire == wire


def test_memw_never_resent():
    fake = FakeTransporter()
    link = m5.Link(fake, 'ramrun', lambda *a, **k: None, image=IMAGE)
    chunk = IMAGE[:4096]
    link.send_line(f'memw 0x1c02000 4096 {crc(chunk):08X}')
    link.send_payload(chunk)
    link.recv_line(1)
    with pytest.raises(m5.Refused, match='never resent'):
        link.send_line(f'memw 0x1c02000 4096 {crc(chunk):08X}')
    assert fake.lines == [f'memw 0x1c02000 4096 {crc(chunk):08X}']


def test_gate_holds_the_approved_image():
    """Even code that bypasses cmd_ramrun cannot put other bytes, another order,
    or an early jump on the wire in a RAM-run session."""
    for bad in (None, bytes(4160), IMAGE[:-1]):
        with pytest.raises(m5.Refused, match='approved M5 image'):
            m5.Link(FakeTransporter(), 'ramrun', lambda *a, **k: None, image=bad)
    fake = FakeTransporter()
    link = m5.Link(fake, 'ramrun', lambda *a, **k: None, image=IMAGE)
    with pytest.raises(m5.Refused, match='before the whole approved image'):
        link.send_line('jump 0x1c02000 0x1')
    rest = IMAGE[4096:]
    with pytest.raises(m5.Refused, match='out of order'):
        link.send_line(f'memw 0x1c03000 64 {crc(rest):08X}')
    other = bytes(4096)
    link.send_line(f'memw 0x1c02000 4096 {crc(other):08X}')
    with pytest.raises(m5.Refused, match="not the approved image's bytes"):
        link.send_payload(other)
    assert fake.wire == f'memw 0x1c02000 4096 {crc(other):08X}\n'.encode()
    assert fake.sram == {}                       # the header alone writes nothing
    half = m5.Link(FakeTransporter(), 'ramrun', lambda *a, **k: None, image=IMAGE)
    first = IMAGE[:4096]
    half.send_line(f'memw 0x1c02000 4096 {crc(first):08X}')
    half.send_payload(first)
    half.recv_line(1)
    with pytest.raises(m5.Refused, match='4096 of 4160'):
        half.send_line('jump 0x1c02000 0x1')


def test_second_ramrun_from_the_same_directory_is_refused(files, tmp_path):
    fake = FakeTransporter()
    code, events, _ = run(fake, ramrun_argv(files), tmp_path, log='first.jsonl')
    assert code == 0
    lock = tmp_path / m5.RAMRUN_LOCK
    assert json.loads(lock.read_text())['receipt'] == 'first.jsonl'
    assert events[-1]['lock'] == str(lock)
    again = FakeTransporter()                     # say the ROM came back
    code, events, opened = run(again, ramrun_argv(files), tmp_path, log='second.jsonl')
    assert code == 1 and opened == [] and again.wire == b'' and events == []


def test_lock_only_once_the_first_memw_is_due(files, tmp_path):
    """A ramrun stopped at the status gate sent nothing to the FM-1, so it does
    not use up the attempt; one stopped after a memw does."""
    code, _, _ = run(FakeTransporter(uboot=False), ramrun_argv(files), tmp_path, log='a.jsonl')
    assert code == 3 and not (tmp_path / m5.RAMRUN_LOCK).exists()
    fake = FakeTransporter(memw_reply='ERR memw at 01C02000')
    code, _, _ = run(fake, ramrun_argv(files), tmp_path, log='b.jsonl')
    assert code == 3 and (tmp_path / m5.RAMRUN_LOCK).exists()
    code, _, opened = run(FakeTransporter(), ramrun_argv(files), tmp_path, log='c.jsonl')
    assert code == 1 and opened == []


# -- stops on unexpected replies ---------------------------------------------

@pytest.mark.parametrize('kw,last', [
    ({'memw_reply': 'ERR memw at 01C02000'}, 'memw'),
    ({'memw_reply': 'ERR loader-running'}, 'memw'),
    ({'corrupt_memr': True}, 'memr 0x1c03000 64'),
])
def test_unexpected_reply_stops_before_jump(files, tmp_path, kw, last):
    fake = FakeTransporter(**kw)
    code, events, _ = run(fake, ramrun_argv(files), tmp_path)
    assert code == 3
    assert not any(l.startswith('jump') for l in fake.lines)
    assert fake.lines[-1].startswith(last)
    assert sum(l.startswith('memw') for l in fake.lines) <= 2
    assert events[-1]['verdict'].startswith('STOP')


def test_no_pong_stops(files, tmp_path):
    fake = FakeTransporter()
    fake._rx = lambda b: None                        # a port that never answers
    code, events, _ = run(fake, ramrun_argv(files), tmp_path)
    assert code == 3 and fake.wire == b'ping\n'
    assert 'PONG' in events[-1]['verdict']


def test_unsolicited_bytes_stop(files, tmp_path):
    fake = FakeTransporter()
    orig = fake._poll

    def chatty(line, payload):
        orig(line, payload)
        if line == 'status':
            fake.out += b'surprise\n'
    fake._poll = chatty
    code, events, _ = run(fake, ramrun_argv(files), tmp_path)
    assert code == 3 and fake.lines == ['ping', 'status']
    assert any(e['event'] == 'rx-unexpected' for e in events)


def test_malformed_status_stops(files, tmp_path):
    fake = FakeTransporter()
    fake._poll = lambda line, payload: fake._tx('OK uboot=1')
    code, _, _ = run(fake, ramrun_argv(files), tmp_path)
    assert code == 3 and fake.lines == ['ping', 'status']


# -- info, dump, compare -----------------------------------------------------

def test_dump_happy_path(files, tmp_path):
    fake = FakeTransporter()
    out = tmp_path / 'before-A.bin'
    code, events, _ = run(fake, ['dump', str(out), '--loader', str(files / 'wl82loader.bin')],
                          tmp_path)
    assert code == 0
    assert out.read_bytes() == FLASH
    ldr = [f'ldr {o} {len(LOADER[o:o + 4096])} {crc(LOADER[o:o + 4096]):08X}'
           for o in range(0, 24064, 4096)]
    assert fake.lines == ['ping', 'status'] + ldr + ['status', 'info', 'read 0x0 1048576']
    assert bytes(fake.loader_buf) == LOADER
    assert not fake.softkey_sent and not fake.flash_written
    assert events[-1]['sha256'] == hashlib.sha256(FLASH).hexdigest()
    rxb = [e for e in events if e['event'] == 'rx-bytes']
    assert rxb[0]['len'] == 0x100000 and rxb[0]['sha256'] == hashlib.sha256(FLASH).hexdigest()


def test_dump_compare_identical_and_different(files, tmp_path):
    loader = ['--loader', str(files / 'wl82loader.bin')]
    code, _, _ = run(FakeTransporter(), ['dump', str(tmp_path / 'A.bin')] + loader, tmp_path,
                     log='a.jsonl')
    assert code == 0
    code, events, _ = run(FakeTransporter(loader=True),
                          ['dump', str(tmp_path / 'B.bin'), '--compare', str(tmp_path / 'A.bin')]
                          + loader, tmp_path, log='b.jsonl')
    assert code == 0 and events[-1]['compare']['identical'] is True
    changed = bytearray(FLASH)
    changed[0x95123] ^= 1                         # above 0x93000: upstream would let it pass
    code, events, _ = run(FakeTransporter(flash=bytes(changed)),
                          ['dump', str(tmp_path / 'C.bin'), '--compare', str(tmp_path / 'A.bin')]
                          + loader, tmp_path, log='c.jsonl')
    assert code == 3 and events[-1]['compare']['differing_sectors'] == ['0x95000']


def test_dump_with_loader_already_held_skips_upload(files, tmp_path):
    fake = FakeTransporter(loader=True, loader_running=True)
    code, _, _ = run(fake, ['dump', str(tmp_path / 'D.bin'), '--loader',
                            str(files / 'wl82loader.bin')], tmp_path)
    assert code == 0
    assert fake.lines == ['ping', 'status', 'info', 'read 0x0 1048576']


def test_dump_read_fail_writes_nothing(files, tmp_path):
    fake = FakeTransporter(read_fail=True)
    out = tmp_path / 'E.bin'
    code, events, _ = run(fake, ['dump', str(out), '--loader', str(files / 'wl82loader.bin')],
                          tmp_path)
    assert code == 3 and not out.exists()
    assert 'END FAIL' in events[-1]['verdict']


def test_dump_refuses_existing_output(files, tmp_path):
    out = tmp_path / 'F.bin'
    out.write_bytes(b'x')
    code, _, opened = run(FakeTransporter(), ['dump', str(out), '--loader',
                                              str(files / 'wl82loader.bin')], tmp_path)
    assert code == 1 and opened == [] and out.read_bytes() == b'x'


def test_info_without_uboot_stops_without_softkey(files, tmp_path):
    fake = FakeTransporter(uboot=False, v15=True)
    code, events, _ = run(fake, ['info', '--loader', str(files / 'wl82loader.bin')], tmp_path)
    assert code == 3 and fake.lines == ['ping', 'status'] and not fake.softkey_sent
    assert 'rekey' in events[-1]['verdict']


def test_info_wrong_chip_stops(files, tmp_path):
    fake = FakeTransporter(info='OK key=1234 type=3 id=856014')
    code, _, _ = run(fake, ['dump', str(tmp_path / 'G.bin'), '--loader',
                            str(files / 'wl82loader.bin')], tmp_path)
    assert code == 3 and 'read 0x0 1048576' not in fake.lines
    assert not (tmp_path / 'G.bin').exists()


def test_info_and_dump_need_the_right_loader(files, tmp_path):
    (files / 'bad.bin').write_bytes(LOADER[:-1] + b'\x00')
    for argv in (['info', '--loader', str(files / 'bad.bin')],
                 ['dump', str(tmp_path / 'H.bin'), '--loader', str(files / 'bad.bin')]):
        code, _, opened = run(FakeTransporter(), argv, tmp_path)
        assert code == 1 and opened == []
    with pytest.raises(SystemExit):
        m5.main(['--port', PORT, '--log', str(tmp_path / 'x'), 'info'], environ={},
                opener=lambda p: pytest.fail('opened'))


def test_fm1t_loader_env_is_never_read(files, tmp_path):
    with pytest.raises(SystemExit):                # info still requires --loader
        m5.main(['--port', PORT, '--log', str(tmp_path / 'x'), 'info'],
                environ={'FM1T_LOADER': str(files / 'wl82loader.bin')},
                opener=lambda p: pytest.fail('opened'))


def test_compare_helper(tmp_path, capsys):
    a, b, c = tmp_path / 'a.bin', tmp_path / 'b.bin', tmp_path / 'c.bin'
    a.write_bytes(FLASH)
    b.write_bytes(FLASH)
    changed = bytearray(FLASH)
    changed[5] ^= 0x80
    changed[0xFF000] ^= 1
    c.write_bytes(bytes(changed))
    assert m5.main(['compare', str(a), str(b)]) == 0
    assert 'IDENTICAL' in capsys.readouterr().out
    assert m5.main(['compare', str(a), str(c)]) == 1
    assert '0x00000 0xff000' in capsys.readouterr().out
    short = tmp_path / 's.bin'
    short.write_bytes(FLASH[:-1])
    assert m5.main(['compare', str(short), str(short)]) == 1


# -- rekey and status ----------------------------------------------------------

def test_rekey_only_with_nothing_mounted(tmp_path):
    fake = FakeTransporter(uboot=False, v15=False)
    code, events, _ = run(fake, ['rekey', '--fm1-is-off'], tmp_path, log='a.jsonl')
    assert code == 0 and fake.lines == ['ping', 'status', 'rekey'] and fake.rebooted
    for i, kw in enumerate(({'uboot': True}, {'uboot': False, 'v15': True})):
        fake = FakeTransporter(**kw)
        code, _, _ = run(fake, ['rekey', '--fm1-is-off'], tmp_path, log=f'mounted{i}.jsonl')
        assert code == 3 and fake.lines == ['ping', 'status'] and not fake.rebooted
    fake = FakeTransporter(uboot=False)
    code, _, opened = run(fake, ['rekey'], tmp_path, log='b.jsonl')
    assert code == 1 and opened == []


def test_status_and_rekey_while_keying(tmp_path):
    """Core 1 does not answer `status` until the USB_KEY handoff; the tool
    stops with an explanation, and `rekey` is never sent without a status."""
    fake = FakeTransporter(uboot=False, keying=True)
    code, events, _ = run(fake, ['status'], tmp_path, log='a.jsonl')
    assert code == 3 and fake.lines == ['ping', 'status']
    assert 'not a fault' in events[-1]['verdict'] and 'UBOOT READY' in events[-1]['verdict']
    fake = FakeTransporter(uboot=False, keying=True)
    code, events, _ = run(fake, ['rekey', '--fm1-is-off'], tmp_path, log='b.jsonl')
    assert code == 3 and fake.lines == ['ping', 'status'] and not fake.rebooted


def test_ramrun_while_keying_sends_nothing_after_status(files, tmp_path):
    fake = FakeTransporter(uboot=False, keying=True)
    code, _, _ = run(fake, ramrun_argv(files), tmp_path)
    assert code == 3 and fake.lines == ['ping', 'status'] and fake.sram == {}


def test_stale_bytes_at_open_are_logged_not_used(files, tmp_path):
    fake = FakeTransporter()
    fake.out += b'OK uboot=1 v15=0 loader=1 loader_running=1\n'   # an old reply
    code, events, _ = run(fake, ramrun_argv(files), tmp_path)
    assert code == 0
    assert events[1]['event'] == 'rx-discarded-at-open'
    assert 'loader_running=1' in events[1]['data']


def test_lost_rekey_reply_is_explained(tmp_path):
    fake = FakeTransporter(uboot=False)
    orig = fake._rx

    def swallow(b):
        orig(b)
        if fake.rebooted:
            fake.out.clear()
    fake._rx = swallow
    code, events, _ = run(fake, ['rekey', '--fm1-is-off'], tmp_path)
    assert code == 3 and fake.rebooted and 'took effect' in events[-1]['verdict']


def test_status_is_read_only(tmp_path):
    fake = FakeTransporter(uboot=False, v15=True)
    code, _, _ = run(fake, ['status'], tmp_path)
    assert code == 0 and fake.lines == ['ping', 'status'] and not fake.softkey_sent


# -- the gate ---------------------------------------------------------------

UPSTREAM_WORDS = ['rekey', 'ping', 'status', 'uboot', 'info', 'read', 'runapp', 'wsec',
                  'ldr', 'memw', 'memr', 'jump']     # every word fm1_proto_rx/poll handles


@pytest.mark.parametrize('mode', sorted(m5.ALLOWED))
def test_forbidden_lines_unsendable_in_every_mode(mode):
    lines = ['uboot', 'k', 'runapp', 'wsec 0x4000 00000000', 'wsec 0x92000 DEADBEEF',
             'read 0x4000 4096', 'read 0x0 4096', 'read 0x0 1048577', 'memw 0x1c06000 4 00000000',
             'memw 0x1c05000 4096 00000000x', 'memw 0x1c02004 4 00000000',
             'memw 0x0 4 00000000', 'memw 0x1c02000 0 00000000', 'memw 0x1c05f00 512 00000000',
             'memr 0x1c06000 4', 'memr 0x1c05000 4097', 'jump 0x1c02000 0x0',
             'memw 0x1c05000 4096 00000000', 'memw 0x1c03000 4096 00000000',
             'memw 0x1c03000 65 00000000', 'memw 0x1c04000 4 00000000',
             'memr 0x1c03000 4096', 'memr 0x1c04000 4',
             'jump 0x1c03000 0x1', 'jump 0x01c02000 0x1', 'ldr 24064 1 00000000',
             'ldr 20480 4096 00000000', 'ldr 0 0 00000000', 'ldr 100 4 00000000',
             'status ', ' status', 'status\nuboot', 'ping\r', 'uboot ', 'UBOOT', 'wsec',
             'erase', 'write', 'selftest-write', '\xf0"$5}\xf7', 'F0 22 24 35 7D F7', '']
    lines += [chr(c) for c in range(0x20, 0x7F)]       # console one-letter commands
    for line in lines:
        with pytest.raises(m5.Refused):
            m5.check_line(mode, line)


def test_allow_list_per_mode():
    ok = {
        'ping': 'ping', 'status': 'status', 'rekey': 'rekey', 'info': 'info',
        'ldr': 'ldr 20480 3584 0123ABCD', 'read': 'read 0x0 1048576',
        'memw': 'memw 0x1c03000 64 0123ABCD', 'memr': 'memr 0x1c02000 64',
        'jump': 'jump 0x1c02000 0x1',
    }
    for mode, names in m5.ALLOWED.items():
        for name, line in ok.items():
            if name in names:
                assert m5.check_line(mode, line) == name
            else:
                with pytest.raises(m5.Refused):
                    m5.check_line(mode, line)
    # the RAM-run session cannot reach the loader or flash; dumps cannot reach RAM
    assert not {'ldr', 'info', 'read', 'rekey'} & set(m5.ALLOWED['ramrun'])
    assert not {'memw', 'memr', 'jump', 'rekey'} & set(m5.ALLOWED['dump'])
    words = {w for names in m5.ALLOWED.values() for w in names}
    assert words <= set(UPSTREAM_WORDS) - {'uboot', 'runapp', 'wsec'}


def test_every_upstream_word_bare_is_refused_or_harmless():
    for word in UPSTREAM_WORDS:
        for mode in m5.ALLOWED:
            if word in ('ping', 'status', 'info', 'rekey') and word in m5.ALLOWED[mode]:
                continue
            with pytest.raises(m5.Refused):
                m5.check_line(mode, word)


def test_random_and_mutated_lines_never_escape_the_patterns():
    rng = random.Random(7)
    allowed = re.compile('|'.join(m5.PATTERNS.values()))
    seeds = ['ping', 'status', 'rekey', 'info', 'read 0x0 1048576', 'jump 0x1c02000 0x1',
             'memw 0x1c02000 4096 0123ABCD', 'memw 0x1c03000 64 0123ABCD', 'memr 0x1c02000 64', 'ldr 20480 3584 0123ABCD']
    alphabet = 'abcdefghijklmnopqrstuvwxyz0123456789x ABCDEF'
    for i in range(6000):
        if i % 2:
            line = ''.join(rng.choice(alphabet) for _ in range(rng.randint(1, 40)))
        else:
            chars = list(rng.choice(seeds))
            for _ in range(rng.randint(1, 3)):
                pos = rng.randrange(len(chars))
                if rng.random() < 0.5:
                    chars[pos] = rng.choice(alphabet)
                else:
                    chars.insert(pos, rng.choice(alphabet))
            line = ''.join(chars)
        for mode in m5.ALLOWED:
            try:
                name = m5.check_line(mode, line)
            except m5.Refused:
                continue
            assert allowed.fullmatch(line) and name in m5.ALLOWED[mode]
            if name in ('memw', 'memr'):
                addr, n = int(line.split()[1], 16), int(line.split()[2])
                assert 0x01C02000 <= addr and addr + n <= 0x01C03040 and 1 <= n <= 4096
            if name in ('memw', 'memr', 'ldr'):
                # The transporter parses lengths with strtoul(..., 0): no leading 0.
                assert int(line.split()[2], 0) == int(line.split()[2])


@pytest.mark.parametrize('line', [
    'memw 0x1c02000 04096 0123ABCD',   # strtoul(.., 0) on the Pico: octal 040 = 32 B
    'memw 0x1c03000 064 0123ABCD', 'memw 0x1c02000 010 0123ABCD', 'memw 0x1c02000 0 0123ABCD',
    'memr 0x1c02000 064', 'memr 0x1c02000 0100', 'memr 0x1c02000 00004',
    'memw 0x1c02000 0x100 0123ABCD', 'memr 0x1c02000 0x10',
    'ldr 0 04096 0123ABCD', 'ldr 4096 0100 0123ABCD', 'ldr 20480 03584 0123ABCD',
])
def test_lengths_the_transporter_would_read_differently_are_refused(line):
    """The transporter parses memw/memr/ldr lengths with strtoul(..., NULL, 0)
    (src/transporter_proto.c at 80c5012): a leading 0 is octal there but decimal
    here. Only plain decimal passes, in every mode."""
    for mode in m5.ALLOWED:
        with pytest.raises(m5.Refused):
            m5.check_line(mode, line)
    assert m5.check_line('ramrun', 'memr 0x1c02000 64') == 'memr'


def test_info_and_dump_lines_still_pass_the_ldr_gate():
    assert m5.check_line('dump', 'ldr 20480 3584 0123ABCD') == 'ldr'
    assert m5.check_line('dump', 'ldr 0 4096 0123ABCD') == 'ldr'
    assert m5.check_line('info', 'ldr 0 4096 0123ABCD') == 'ldr'
    assert m5.check_line('info', 'info') == 'info'


def test_payload_only_after_matching_header():
    fake = FakeTransporter()
    link = m5.Link(fake, 'ramrun', lambda *a, **k: None, image=IMAGE)
    head = IMAGE[:4]
    with pytest.raises(m5.Refused):
        link.send_payload(head)
    link.send_line(f'memw 0x1c02000 4 {crc(head):08X}')
    with pytest.raises(m5.Refused):
        link.send_payload(b'\x01' * 4)               # CRC does not match
    with pytest.raises(m5.Refused):
        link.send_payload(IMAGE[:5])                 # length does not match
    with pytest.raises(m5.Refused):
        link.send_line('status')                     # payload is due
    link.send_payload(head)
    assert fake.lines == [f'memw 0x1c02000 4 {crc(head):08X}']
    assert [fake.sram[0x01C02000 + i] for i in range(4)] == list(head)


def test_link_is_the_only_writer():
    tree = ast.parse(TOOL.read_text())
    writers = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr == 'write'
                        and isinstance(sub.func.value, ast.Attribute)
                        and sub.func.value.attr == '_port'):
                    writers.append(node.name)
    assert set(writers) == {'Link', '_write'}
    src = TOOL.read_text()
    assert src.count('serial.Serial(') == 1 and 'def open_port' in src
    assert 'glob' not in src and '1200' not in src.replace('# never 1200', '')
    for word in ('"uboot"', "'uboot'"):
        assert f'request(s, {word}' not in src and f'request({word}' not in src


def test_no_soft_key_bytes_in_the_tool():
    data = TOOL.read_bytes()
    assert b'\xf0\x22\x24\x35\x7d\xf7' not in data
    assert '04 F0 22 24 07 35' not in TOOL.read_text()



# -- the fake against the firmware -------------------------------------------

def test_fake_drops_lines_while_a_request_is_pending():
    """transporter_proto.c drops every line but ping/rekey while core 1 holds a
    request, so the payload of a dropped memw header would be read as text
    lines. The tool never sends a second request before a reply: shown here on
    the fake, which reproduces the hazard."""
    fake = FakeTransporter(keying=True)
    fake.write(b'status\n')
    payload = b'uboot\nwsec 0x4000 0\n'
    fake.write(f'memw 0x1c02000 {len(payload)} {crc(payload):08X}\n'.encode() + payload)
    assert fake.pending == 'status'
    assert fake.dropped == [f'memw 0x1c02000 {len(payload)} {crc(payload):08X}',
                            'uboot', 'wsec 0x4000 0']


def test_fake_parses_like_the_firmware():
    assert strtoul('0x1c02000', 0) == 0x1C02000 and strtoul('4096', 0) == 4096
    assert strtoul('0x1', 0) == 1 and strtoul('010', 0) == 8 and strtoul('2144DF1C', 16) == 0x2144DF1C
    assert first_word_after('memw 0x1c02000 64 ABCD', 5) == 64
    fake = FakeTransporter()
    fake.write(b'status x y z w\n')                      # argv[0] decides, extras ignored
    assert fake.readline().startswith(b'OK uboot=1')
    fake.write(b'read 0x0 0\n')
    assert fake.readline() == b'ERR range\n'
    fake.write(b'ldr 4096 4 ' + f'{crc(bytes(4)):08X}'.encode() + b'\n' + bytes(4))
    assert fake.readline() == b'ERR loader-range\n'       # chunks must arrive in order
    fake.write(b'memw 0x1c02000 0 00000000\n')
    assert fake.readline() == b'ERR len\n'
    fake.write(b'jump 0x1c02000 0x10001\n')
    assert fake.jumps == [(0x1C02000, 1)]                  # (uint16_t)arg


def test_tool_sends_exactly_what_the_firmware_reads():
    """Every line the tool sends in a full M5 session parses on the fake as the
    firmware would: the right command, address, length and argument."""
    fake = FakeTransporter()
    link = m5.Link(fake, 'ramrun', lambda *a, **k: None, image=IMAGE)
    link.request('ping', 1)
    write_image(link)
    link.request('jump 0x1c02000 0x1', 1)
    assert fake.jumps == [(0x01C02000, 1)]
    assert sorted(fake.sram) == list(range(0x01C02000, 0x01C03040))
    assert bytes(fake.sram[a] for a in sorted(fake.sram)) == IMAGE
    assert fake.dropped == [] and not fake.softkey_sent and not fake.flash_written
    assert not fake.runapp_sent


def test_lock_created_by_a_parallel_run_stops_before_memw(files, tmp_path):
    fake = FakeTransporter()
    orig = fake._poll

    def racing(line, payload):
        orig(line, payload)
        if line == 'status':                     # another invocation got there first
            (tmp_path / m5.RAMRUN_LOCK).write_text('{}\n')
    fake._poll = racing
    code, events, _ = run(fake, ramrun_argv(files), tmp_path)
    assert code == 3 and fake.lines == ['ping', 'status'] and fake.sram == {}
    assert 'no second attempt' in events[-1]['verdict']
