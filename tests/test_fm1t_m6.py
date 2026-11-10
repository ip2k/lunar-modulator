"""tools/fm1-transporter/fm1t_m6.py: the M6 host tool, against the same scripted
fake of the FM-1 Transporter data port that tests/test_fm1t_m5.py uses (after
src/transporter_proto.c at kurogedelic FM-1-transporter 80c5012). No serial
port is opened by any test.

fm1t_m6.py is a copy of fm1t_m5.py with the approved image swapped. The code
the two share is covered by tests/test_fm1t_m5.py; test_only_the_pinned_lines_differ
below fails if any other line of the M6 tool changes, so that coverage carries
over. The tests here cover what differs: the image, its three chunks, the
bounds and the lock."""
import ast
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'fm1-transporter' / 'fm1t_m6.py'
M5_TOOL = ROOT / 'tools' / 'fm1-transporter' / 'fm1t_m5.py'
M5_TOOL_SHA256 = '9673ccd83622a208644ae2b467a1fa5964b01807d2639b3d409537d5136c1a72'


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m6 = _load('fm1t_m6', TOOL)
m5 = _load('fm1t_m5_for_m6_tests', M5_TOOL)
# The fake and its helpers, not its fixtures (those patch the M5 module only).
harness = _load('test_fm1t_m5_harness', ROOT / 'tests' / 'test_fm1t_m5.py')
FakeTransporter, LOADER, FLASH, crc = (harness.FakeTransporter, harness.LOADER,
                                      harness.FLASH, harness.crc)
PORT = harness.PORT
LOADER_SHA = hashlib.sha256(LOADER).hexdigest()

M6_SHA256 = '37334c76760831e3137ec1c9d45943c3ef383f91a8fe632bfd78db07cbde3647'
M6_BYTES = 9796                                   # 4,096 + 4,096 + 1,604
IMAGE = bytes((i * 11 + 9) & 0xFF for i in range(M6_BYTES))   # synthetic, m6.bin's size
IMAGE_SHA = hashlib.sha256(IMAGE).hexdigest()
CHUNKS = [(0x01C02000, IMAGE[:4096]), (0x01C03000, IMAGE[4096:8192]),
          (0x01C04000, IMAGE[8192:])]


@pytest.fixture
def approved(monkeypatch):
    """Admit the synthetic image (same size as m6.bin, so the compiled chunk
    addresses still hold) and the synthetic loader. The real values stay in the
    tool and are checked by test_approved_constants and the end-to-end run."""
    monkeypatch.setattr(m6, 'APPROVED_IMAGE_SHA256', IMAGE_SHA)
    monkeypatch.setattr(m6, 'LOADER_SHA256', LOADER_SHA)


@pytest.fixture(autouse=True)
def no_serial(monkeypatch):
    def refuse(*_a, **_k):
        raise AssertionError('a test tried to open a real serial port')
    monkeypatch.setattr(m6, 'open_port', refuse)
    monkeypatch.setattr(m5, 'open_port', refuse)


@pytest.fixture
def files(tmp_path):
    (tmp_path / 'm6.bin').write_bytes(IMAGE)
    (tmp_path / 'wl82loader.bin').write_bytes(LOADER)
    return tmp_path


def run(fake, argv, tmp_path, environ=None, log='log.jsonl', tool=None):
    opened = []

    def opener(port):
        opened.append(port)
        return fake

    code = (tool or m6).main(['--port', PORT, '--log', str(tmp_path / log)] + argv,
                             environ=environ or {}, opener=opener)
    events = []
    if (tmp_path / log).exists():
        events = [json.loads(x) for x in (tmp_path / log).read_text().splitlines()]
    return code, events, opened


def ramrun_argv(files, sha=IMAGE_SHA, name='m6.bin'):
    return ['ramrun', str(files / name), '--sha256', sha]


def memw_line(addr, chunk):
    return f'memw {addr:#x} {len(chunk)} {crc(chunk):08X}'


# -- what is approved, and what M5 keeps -------------------------------------

def test_approved_constants():
    src = TOOL.read_text()
    assert f'APPROVED_IMAGE_SHA256 = "{M6_SHA256}"' in src
    assert 'APPROVED_IMAGE_BYTES = 9796' in src
    assert 'APPROVED_BUILD_ID = "m6-plan-2"' in src
    assert 'LOADER_SHA256 = "d41da6126760c9d66660bcc0cac8d27d221806c5e369a8036921efe68dca5376"' in src
    assert m6.APPROVED_IMAGE_SHA256 == M6_SHA256 and m6.APPROVED_IMAGE_BYTES == M6_BYTES
    # As the approved sketch (M6 note section 5): RAM_END stays M5's 0x01C06000
    # for the image bytes; the runtime top is checked against the ROM window.
    assert m6.RAM_BASE == 0x01C02000 and m6.RAM_END == m5.RAM_END == 0x01C06000
    assert m6.JUMP_ARG == 1
    assert m6.RUNTIME_TOP == 0x01C06C70 and m6.ROM_WINDOW_END == 0x01C07E00
    assert m6.RAM_BASE + M6_BYTES == 0x01C04644 <= m6.RAM_END <= m6.RUNTIME_TOP <= m6.ROM_WINDOW_END
    assert m6.RAMRUN_LOCK == 'fm1t_m6-ramrun.lock' != m5.RAMRUN_LOCK
    assert m5.RAMRUN_LOCK in m6.OTHER_RAMRUN_LOCKS


def test_m5_tool_is_unchanged():
    assert hashlib.sha256(M5_TOOL.read_bytes()).hexdigest() == M5_TOOL_SHA256
    assert m5.APPROVED_IMAGE_SHA256.startswith('a60410de') and m5.APPROVED_IMAGE_BYTES == 4160


def test_no_override_flag_for_the_image():
    src = TOOL.read_text()
    assert 'allow-other-image' not in src and 'allow_other_image' not in src
    for action in m6.build_parser()._subparsers._group_actions[0].choices['ramrun']._actions:
        assert not {'--loader', '--addr', '--arg', '--clear', '--poke', '--read'} & set(action.option_strings)


def _code_lines(path):
    src = path.read_text()
    return src.splitlines()[ast.parse(src).body[0].end_lineno:]   # after the module docstring


EXPECTED_CODE_DIFF = [
    '-# -- What the owner approved (2026-11-09). Changing any of these needs a new',
    '-#    approval; there is deliberately no command-line override.',
    '-APPROVED_IMAGE_SHA256 = "a60410deb4ac5cedd5be2ab76c6155a604ae2efa43cea59430bf55c28d8d44e4"',
    '-APPROVED_IMAGE_BYTES = 4160',
    '-APPROVED_BUILD_ID = "m5-plan-1"',
    '+# -- What the owner approved (2026-11-10, docs/18 section 3 item 6). Changing',
    '+#    any of these needs a new approval; there is deliberately no command-line',
    '+#    override.',
    '+APPROVED_IMAGE_SHA256 = "37334c76760831e3137ec1c9d45943c3ef383f91a8fe632bfd78db07cbde3647"',
    '+APPROVED_IMAGE_BYTES = 9796',
    '+APPROVED_BUILD_ID = "m6-plan-2"',
    '+RUNTIME_TOP = 0x01C06C70         # m6-plan-2 uses nothing at or above this (its SSP stack top)',
    "+ROM_WINDOW_END = 0x01C07E00      # the ROM upload window's end, the owner-accepted bound",
    '+if not RAM_BASE + APPROVED_IMAGE_BYTES <= RAM_END <= RUNTIME_TOP <= ROM_WINDOW_END:',
    '+    raise SystemExit("fm1t_m6: the approved image\'s RAM bounds are inconsistent")',
    '-RAMRUN_LOCK = "fm1t_m5-ramrun.lock"',
    '+RAMRUN_LOCK = "fm1t_m6-ramrun.lock"',
    "+# M5's lock in the same directory also refuses: M6 needs its own run directory.",
    '+OTHER_RAMRUN_LOCKS = ("fm1t_m5-ramrun.lock",)',
    '-USB_KEY_STEPS = ("ROM entry is by USB_KEY only (docs/19 and docs/17 section 4): switch the "',
    '-                 "FM-1 OFF, run `fm1t_m5.py ... rekey --fm1-is-off`, reopen the console, wait "',
    '+USB_KEY_STEPS = ("ROM entry is by USB_KEY only (docs/20 and docs/17 section 4): switch the "',
    '+                 "FM-1 OFF, run `fm1t_m6.py ... rekey --fm1-is-off`, reopen the console, wait "',
    '-_RAM_ADDRS = "|".join(f"{a:#x}" for a in range(RAM_BASE, RAM_END, MEMW_CHUNK))',
    '+# Only the chunk addresses of the approved image: 0x1c02000, 0x1c03000, 0x1c04000.',
    '+_RAM_ADDRS = "|".join(f"{a:#x}" for a in range(RAM_BASE, RAM_BASE + APPROVED_IMAGE_BYTES,',
    '+                                               MEMW_CHUNK))',
    '-    power off; do not retry (docs/19)."""',
    '+    power off; do not retry (docs/20)."""',
    '-    """The image must fit the M5 window and be exactly the approved image."""',
    '+    """The image must fit the M6 window and be exactly the approved image."""',
    '-        raise Refused(f"{path}: {digest} ({len(data)} B) is not the approved M5 image "',
    '+        raise Refused(f"{path}: {digest} ({len(data)} B) is not the approved M6 image "',
    '-                raise Refused("refused: a RAM-run link needs the approved M5 image")',
    '+                raise Refused("refused: a RAM-run link needs the approved M6 image")',
    '-        return 3, (f"jump answered OK after {ms} ms: the image returned, which M5 never does; "',
    '+        return 3, (f"jump answered OK after {ms} ms: the image returned, which M6 never does; "',
    '-                   "that does not return. Image presumed running; the TFT and LEDs are the "',
    '-                   "proof. Nothing more is sent")',
    '+                   "that does not return. Image presumed running; the TFT and the codec\'s "',
    '+                   "output are the proof. Nothing more is sent")',
    '-               "The image may be running: watch the unit and photograph it, then power off; "',
    '+               "The image may be running: watch and listen, photograph the TFT, then power off; "',
    '-        print(f"image {args.image}: approved M5 image, {APPROVED_IMAGE_BYTES} B, "',
    '+        print(f"image {args.image}: approved M6 image, {APPROVED_IMAGE_BYTES} B, "',
    '-# Upstream ramrun options that M5 refuses by name (note section 4.2).',
    '+# Upstream ramrun options that M5 and M6 refuse by name (M5 note section 4.2).',
    '-    m = sub.add_parser("ramrun", help="load the approved M5 image at 0x01C02000 and jump once")',
    '+    m = sub.add_parser("ramrun", help="load the approved M6 image at 0x01C02000 and jump once")',
    '-            raise Refused(f"{args.log.parent / RAMRUN_LOCK} exists: M5 was already attempted "',
    '+            raise Refused(f"{args.log.parent / RAMRUN_LOCK} exists: M6 was already attempted "',
    '+        for other in OTHER_RAMRUN_LOCKS:',
    '+            if args.log and (args.log.parent / other).exists():',
    '+                raise Refused(f"{args.log.parent / other} exists: this is M5\'s run directory; "',
    '+                              "run M6 from a new one (docs/20)")',
    '-                print(f"fm1t_m5: refused: ramrun {flag}: {RAMRUN_REFUSED_FLAGS[flag]}",',
    '+                print(f"fm1t_m6: refused: ramrun {flag}: {RAMRUN_REFUSED_FLAGS[flag]}",',
    '-        print(f"fm1t_m5: {exc}", file=sys.stderr)',
    '+        print(f"fm1t_m6: {exc}", file=sys.stderr)',
    '-            why = ("M5 was already attempted from this run directory; no second attempt"',
    '+            why = ("M6 was already attempted from this run directory; no second attempt"',
    '-        print(f"fm1t_m5: {result.get(\'verdict\')}", file=sys.stderr)',
    '+        print(f"fm1t_m6: {result.get(\'verdict\')}", file=sys.stderr)',
]



def test_only_the_pinned_lines_differ():
    """Every line of fm1t_m6.py after its docstring equals fm1t_m5.py's except
    these. A change anywhere else needs this list updated, in review."""
    got = [l for l in difflib.unified_diff(_code_lines(M5_TOOL), _code_lines(TOOL),
                                           lineterm='', n=0)
           if l[:1] in '+-' and not l.startswith(('---', '+++'))]
    assert got == EXPECTED_CODE_DIFF


def test_each_tool_refuses_the_others_image(tmp_path):
    """With the real constants: the M6 tool admits only m6.bin's hash, the M5
    tool only m5.bin's. Neither has a switch for the other."""
    other = bytes(4160)
    (tmp_path / 'm5-size.bin').write_bytes(other)
    (tmp_path / 'm6-size.bin').write_bytes(IMAGE)
    for tool, name, data in ((m6, 'm5-size.bin', other), (m5, 'm6-size.bin', IMAGE)):
        sha = hashlib.sha256(data).hexdigest()
        with pytest.raises(tool.Refused, match='not the approved'):
            tool.admit_image(tmp_path / name, sha)
        fake = FakeTransporter()
        code, events, opened = run(fake, ['ramrun', str(tmp_path / name), '--sha256', sha],
                                   tmp_path, tool=tool, log=f'{tool.__name__}.jsonl')
        assert code == 1 and opened == [] and fake.wire == b''
    assert m5.APPROVED_IMAGE_SHA256 != m6.APPROVED_IMAGE_SHA256
    with pytest.raises(m6.Refused, match='approved M6 image'):
        m6.Link(FakeTransporter(), 'ramrun', lambda *a, **k: None, image=other)


# -- happy path --------------------------------------------------------------

def test_ramrun_happy_path_wire_sequence(approved, files, tmp_path):
    fake = FakeTransporter()
    code, events, opened = run(fake, ramrun_argv(files), tmp_path)
    assert code == 0
    assert opened == [PORT]
    assert [len(c) for _, c in CHUNKS] == [4096, 4096, 1604]
    assert fake.lines == (['ping', 'status']
                          + [memw_line(a, c) for a, c in CHUNKS]
                          + [f'memr {a:#x} {len(c)}' for a, c in CHUNKS]
                          + ['jump 0x1c02000 0x1'])
    assert fake.wire == (b'ping\nstatus\n'
                         + b''.join(memw_line(a, c).encode() + b'\n' + c for a, c in CHUNKS)
                         + b'memr 0x1c02000 4096\nmemr 0x1c03000 4096\nmemr 0x1c04000 1604\n'
                         + b'jump 0x1c02000 0x1\n')
    assert sorted(fake.sram) == list(range(0x01C02000, 0x01C04644))
    assert bytes(fake.sram[a] for a in sorted(fake.sram)) == IMAGE
    assert fake.jumps == [(0x01C02000, 1)]
    assert not fake.softkey_sent and not fake.flash_written and not fake.runapp_sent
    assert fake.closed and fake.dropped == []
    end = events[-1]
    assert end['event'] == 'end' and end['exit'] == 0
    assert end['readback'] == 'equal' and end['jump_reply'] == 'ERR jump ms=2003'
    assert 'presumed running' in end['verdict'] and 'codec' in end['verdict']


def test_receipt_records_build_and_tool(approved, files, tmp_path):
    code, events, _ = run(FakeTransporter(), ramrun_argv(files), tmp_path)
    assert code == 0
    start = events[0]
    assert start['event'] == 'start' and start['cmd'] == 'ramrun'
    assert start['image_sha256'] == IMAGE_SHA and start['build_id'] == 'm6-plan-2'
    assert start['tool_sha256'] == hashlib.sha256(TOOL.read_bytes()).hexdigest()
    payloads = [e for e in events if e['event'] == 'tx-bytes']
    assert [(p['len'], p['sha256']) for p in payloads] == [
        (len(c), hashlib.sha256(c).hexdigest()) for _, c in CHUNKS]


def test_preflight_offline(approved, files, capsys):
    code = m6.main(['preflight', '--image', str(files / 'm6.bin'), '--sha256', IMAGE_SHA,
                    '--loader', str(files / 'wl82loader.bin')], environ={},
                   opener=lambda p: pytest.fail('preflight opened a port'))
    assert code == 0
    assert 'approved M6 image, 9796 B' in capsys.readouterr().out


def test_info_and_dump_still_pass_the_ldr_gate(approved, files, tmp_path):
    """The ldr length pattern differs from M5's (plain decimal only), so the
    loader upload is exercised here too: six chunks, the last 3,584 B."""
    for cmd in (['info', '--loader', str(files / 'wl82loader.bin')],
                ['dump', str(tmp_path / 'out.bin'), '--loader', str(files / 'wl82loader.bin')]):
        fake = FakeTransporter()
        code, events, _ = run(fake, cmd, tmp_path, log=f'{cmd[0]}.jsonl')
        assert code == 0 and events[-1]['exit'] == 0
        ldr = [l for l in fake.lines if l.startswith('ldr')]
        assert [l.split()[1:3] for l in ldr] == [[str(o), '4096'] for o in range(0, 20480, 4096)] + [['20480', '3584']]
        assert not fake.sram and not fake.jumps and not fake.flash_written


# -- bounds ------------------------------------------------------------------

@pytest.mark.parametrize('line', [
    'memw 0x1c04000 1605 00000000',            # one byte past the image
    'memw 0x1c04000 4096 00000000',
    'memw 0x1c05000 4 00000000',               # inside the 0x01C07E00 window, past the image
    'memw 0x1c06000 4 00000000', 'memw 0x1c07000 4 00000000', 'memw 0x1c07e00 4 00000000',
    'memw 0x1c04644 4 00000000', 'memw 0x1c02000 4097 00000000',
    'memr 0x1c04000 1605', 'memr 0x1c05000 4', 'memr 0x1c06000 4', 'memr 0x1c07000 4',
    'memw 0x0 4 00000000', 'memw 0x2000 4 00000000', 'memw 0x2000000 4 00000000',
    'memw 0x1c00000 4 00000000', 'memw 0x1c01000 4 00000000',
    'jump 0x1c03000 0x1', 'jump 0x1c02000 0x0', 'jump 0x1c04000 0x1',
])
def test_writes_and_reads_outside_the_image_refused(line):
    for mode in m6.ALLOWED:
        with pytest.raises(m6.Refused):
            m6.check_line(mode, line)


def test_image_range_admitted():
    for line in ('memw 0x1c02000 4096 0123ABCD', 'memw 0x1c03000 4096 0123ABCD',
                 'memw 0x1c04000 1604 0123ABCD', 'memr 0x1c04000 1604', 'memr 0x1c03000 4096'):
        assert m6.check_line('ramrun', line) == line.split()[0]
    assert set(m6._RAM_ADDRS.split('|')) == {'0x1c02000', '0x1c03000', '0x1c04000'}


@pytest.mark.parametrize('line', [
    'memw 0x1c02000 04096 0123ABCD',   # strtoul(.., 0) on the Pico: octal 040 = 32 B
    'memw 0x1c04000 01604 0123ABCD', 'memw 0x1c02000 010 0123ABCD', 'memw 0x1c02000 0 0123ABCD',
    'memr 0x1c04000 01604', 'memr 0x1c02000 0100', 'memr 0x1c02000 00004',
    'memw 0x1c02000 0x100 0123ABCD', 'memr 0x1c02000 0x10',
    'ldr 0 04096 0123ABCD', 'ldr 4096 0100 0123ABCD',
])
def test_lengths_the_transporter_would_read_differently_are_refused(line):
    """The transporter parses memw/memr/ldr lengths with strtoul(..., NULL, 0)
    (src/transporter_proto.c at 80c5012): a leading 0 is octal there but decimal
    here, so the header and the payload would disagree. Only plain decimal passes."""
    for mode in m6.ALLOWED:
        with pytest.raises(m6.Refused):
            m6.check_line(mode, line)
    assert int('4096', 0) == 4096 and m6.check_line('ramrun', 'memr 0x1c02000 4096') == 'memr'


@pytest.mark.parametrize('mode', sorted(m6.ALLOWED))
def test_forbidden_lines_unsendable_in_every_mode(mode):
    lines = ['uboot', 'k', 'runapp', 'wsec 0x4000 00000000', 'wsec 0x92000 DEADBEEF',
             'read 0x4000 4096', 'read 0x0 4096', 'read 0x0 1048577',
             'status ', ' status', 'status\nuboot', 'ping\r', 'uboot ', 'UBOOT', 'wsec',
             'erase', 'write', 'selftest-write', '\xf0"$5}\xf7', 'F0 22 24 35 7D F7',
             'F0 22 24 35 7F F7', '5A AA A5', 'ldr 24064 1 00000000', '']
    lines += [chr(c) for c in range(0x20, 0x7F)]       # console one-letter commands
    for line in lines:
        with pytest.raises(m6.Refused):
            m6.check_line(mode, line)


def test_random_and_mutated_lines_never_escape_the_image():
    rng = random.Random(11)
    allowed = re.compile('|'.join(m6.PATTERNS.values()))
    seeds = ['ping', 'status', 'jump 0x1c02000 0x1', 'memw 0x1c04000 1604 0123ABCD',
             'memr 0x1c04000 1604', 'memw 0x1c03000 4096 0123ABCD', 'read 0x0 1048576']
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
        for mode in m6.ALLOWED:
            try:
                name = m6.check_line(mode, line)
            except m6.Refused:
                continue
            assert allowed.fullmatch(line) and name in m6.ALLOWED[mode]
            if name in ('memw', 'memr'):
                addr, n = int(line.split()[1], 16), int(line.split()[2])
                assert 0x01C02000 <= addr and addr + n <= 0x01C04644 and 1 <= n <= 4096
            if name in ('memw', 'memr', 'ldr'):
                # The transporter parses lengths with strtoul(..., 0).
                assert int(line.split()[2], 0) == int(line.split()[2])


# -- the gate holds the image ------------------------------------------------

def test_gate_holds_the_approved_image(approved):
    for bad in (None, bytes(M6_BYTES), IMAGE[:-1], IMAGE + b'\0'):
        with pytest.raises(m6.Refused, match='approved M6 image'):
            m6.Link(FakeTransporter(), 'ramrun', lambda *a, **k: None, image=bad)
    fake = FakeTransporter()
    link = m6.Link(fake, 'ramrun', lambda *a, **k: None, image=IMAGE)
    with pytest.raises(m6.Refused, match='before the whole approved image'):
        link.send_line('jump 0x1c02000 0x1')
    with pytest.raises(m6.Refused, match='out of order'):
        link.send_line(memw_line(*CHUNKS[2]))
    for addr, chunk in CHUNKS[:2]:
        link.send_line(memw_line(addr, chunk))
        link.send_payload(chunk)
        assert link.recv_line(1) == 'OK'
    with pytest.raises(m6.Refused, match='8192 of 9796'):
        link.send_line('jump 0x1c02000 0x1')
    other = bytes(1604)
    link.send_line(memw_line(0x01C04000, other))
    with pytest.raises(m6.Refused, match="not the approved image's bytes"):
        link.send_payload(other)
    assert max(fake.sram) == 0x01C03FFF               # the third header alone wrote nothing


def test_nothing_sent_after_jump_and_no_resend(approved):
    fake = FakeTransporter()
    link = m6.Link(fake, 'ramrun', lambda *a, **k: None, image=IMAGE)
    link.request('ping', 1)
    for addr, chunk in CHUNKS:
        link.send_line(memw_line(addr, chunk))
        link.send_payload(chunk)
        assert link.recv_line(1) == 'OK'
    with pytest.raises(m6.Refused, match='never resent'):
        link.send_line(memw_line(*CHUNKS[0]))
    link.request('jump 0x1c02000 0x1', 1)
    wire = bytes(fake.wire)
    for line in ('status', 'ping', 'jump 0x1c02000 0x1', 'memr 0x1c02000 64'):
        with pytest.raises(m6.Refused, match='after the jump'):
            link.send_line(line)
    assert fake.wire == wire and fake.jumps == [(0x01C02000, 1)]


@pytest.mark.parametrize('mode,ms,code', [
    ('timeout', 2003, 0), ('timeout', 1500, 0), ('timeout', 10000, 0),
    ('timeout', 1499, 3), ('timeout', 10001, 3),
    ('ok', None, 3), ('fast', None, 3), ('silent', None, 3), ('garbage', None, 3)])
def test_jump_verdicts(approved, files, tmp_path, mode, ms, code):
    fake = FakeTransporter(jump=mode, jump_ms=ms or 2003)
    got, events, _ = run(fake, ramrun_argv(files), tmp_path)
    assert got == code
    assert fake.lines.count('jump 0x1c02000 0x1') == 1 and fake.lines[-1] == 'jump 0x1c02000 0x1'
    assert fake.closed and events[-1]['exit'] == code
    if mode == 'ok':
        assert 'M6 never does' in events[-1]['verdict']


@pytest.mark.parametrize('kw,last', [
    ({'memw_reply': 'ERR memw at 01C02000'}, 'memw'),
    ({'corrupt_memr': True}, 'memr 0x1c04000 1604'),
])
def test_unexpected_reply_stops_before_jump(approved, files, tmp_path, kw, last):
    fake = FakeTransporter(**kw)
    code, events, _ = run(fake, ramrun_argv(files), tmp_path)
    assert code == 3
    assert not any(l.startswith('jump') for l in fake.lines)
    assert fake.lines[-1].startswith(last)
    assert sum(l.startswith('memw') for l in fake.lines) <= 3
    assert events[-1]['verdict'].startswith('STOP')


def test_ramrun_refused_without_uboot_or_with_loader(approved, files, tmp_path):
    for i, kw in enumerate(({'uboot': False}, {'loader': True}, {'loader_running': True})):
        fake = FakeTransporter(**kw)
        code, _, _ = run(fake, ramrun_argv(files), tmp_path, log=f'{i}.jsonl')
        assert code == 3 and fake.lines == ['ping', 'status'] and fake.sram == {}
    assert not (tmp_path / m6.RAMRUN_LOCK).exists()


# -- the lock ----------------------------------------------------------------

def test_second_ramrun_from_the_same_directory_is_refused(approved, files, tmp_path):
    code, events, _ = run(FakeTransporter(), ramrun_argv(files), tmp_path, log='first.jsonl')
    assert code == 0
    lock = tmp_path / 'fm1t_m6-ramrun.lock'
    assert json.loads(lock.read_text())['receipt'] == 'first.jsonl'
    again = FakeTransporter()
    code, events, opened = run(again, ramrun_argv(files), tmp_path, log='second.jsonl')
    assert code == 1 and opened == [] and again.wire == b'' and events == []


def test_m5_run_directory_is_refused(approved, files, tmp_path, capsys):
    (tmp_path / 'fm1t_m5-ramrun.lock').write_text('{}\n')
    fake = FakeTransporter()
    code, events, opened = run(fake, ramrun_argv(files), tmp_path)
    assert code == 1 and opened == [] and fake.wire == b'' and events == []
    assert "M5's run directory" in capsys.readouterr().err


def test_lock_created_by_a_parallel_run_stops_before_memw(approved, files, tmp_path):
    fake = FakeTransporter()
    orig = fake._poll

    def racing(line, payload):
        orig(line, payload)
        if line == 'status':
            (tmp_path / m6.RAMRUN_LOCK).write_text('{}\n')
    fake._poll = racing
    code, events, _ = run(fake, ramrun_argv(files), tmp_path)
    assert code == 3 and fake.lines == ['ping', 'status'] and fake.sram == {}
    assert 'M6 was already attempted' in events[-1]['verdict']


def test_ramrun_refuses_fm1t_loader_env_and_upstream_flags(approved, files, tmp_path):
    fake = FakeTransporter()
    code, _, opened = run(fake, ramrun_argv(files), tmp_path,
                          environ={'FM1T_LOADER': str(files / 'wl82loader.bin')})
    assert code == 1 and opened == [] and fake.wire == b''
    for flag in ('--loader', '--addr', '--arg', '--clear', '--poke', '--read'):
        fake = FakeTransporter()
        code, _, opened = run(fake, ramrun_argv(files) + [flag, 'x'], tmp_path,
                              log=f'{flag[2:]}.jsonl')
        assert code in (1, 2) and opened == [] and fake.wire == b''


# -- the tool's shape --------------------------------------------------------

def test_link_is_the_only_writer_and_no_soft_key():
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
    data = TOOL.read_bytes()
    assert b'\xf0\x22\x24\x35\x7d\xf7' not in data and b'\xf0\x22\x24\x35\x7f\xf7' not in data
    text = TOOL.read_text()
    for banned in ('04 F0 22 24 07 35', '5A AA A5', '0xFC12', '0xfc12', '0xA1 ', 'wsec(', 'runapp('):
        assert banned not in text
