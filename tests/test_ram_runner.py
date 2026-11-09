"""tools/ram_runner.py: allow-list, refusals, window, order and pinning. No hardware:
the SG_IO transport is replaced by a model of the ROM's memory."""
import ast
import hashlib
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import bench_target  # noqa: E402
import fm1_uboot_read as base  # noqa: E402
import ram_runner as rr  # noqa: E402

BASE = 0x01C02000
IMAGE = bytes(range(256)) * 7 + b'\x01\x02\x03'   # 1795 bytes -> 4 blocks
SHA = hashlib.sha256(IMAGE).hexdigest()


def crc16_xmodem(data, crc):
    """Bitwise, as FM-1-transporter's jl_crc16, independent of binascii."""
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return crc


def reference_cipher(data):
    magic = bytes([0xC3, 0xCF, 0xC0, 0xE8, 0xCE, 0xD2, 0xB0, 0xAE,
                   0xC4, 0xE3, 0xA3, 0xAC, 0xD3, 0xF1, 0xC1, 0xD6])
    crc = crc16_xmodem(b'\xff\xff', 0xFFFF)
    out = bytearray(data)
    for i in range(len(out)):
        crc = crc16_xmodem(magic[i % 16:i % 16 + 1], crc)
        out[i] ^= crc & 0xFF
    return bytes(out)


# ---- cipher -------------------------------------------------------------

def test_cipher_matches_the_transporter_algorithm_and_is_its_own_inverse():
    for data in (bytes(512), IMAGE[:512], bytes([0xFF]) * 512):
        assert rr.cipher(data) == reference_cipher(data)
        assert rr.cipher(rr.cipher(data)) == data
    assert rr.cipher(bytes(4)).hex() == reference_cipher(bytes(4)).hex()


def test_cipher_seed_restarts_per_block():
    blocks = rr.plan(bytes(1024))
    assert blocks[0][2] == blocks[1][2] == rr.cipher(bytes(512))


# ---- admission and window ----------------------------------------------

def test_admit_requires_the_named_hash():
    assert rr.admit(IMAGE, SHA) == IMAGE
    with pytest.raises(rr.Refused, match='SHA-256'):
        rr.admit(IMAGE, '0' * 64)
    with pytest.raises(rr.Refused, match='expected SHA-256'):
        rr.admit(IMAGE, None)


def test_window_bounds():
    biggest = bytes(rr.WINDOW_SIZE)
    blocks = rr.plan(rr.admit(biggest, hashlib.sha256(biggest).hexdigest()))
    assert blocks[0][0] == BASE and blocks[-1][0] + 512 == BASE + 24064
    too_big = bytes(rr.WINDOW_SIZE + 1)
    with pytest.raises(rr.Refused, match='exceeds'):
        rr.admit(too_big, hashlib.sha256(too_big).hexdigest())
    with pytest.raises(rr.Refused, match='Empty'):
        rr.admit(b'', hashlib.sha256(b'').hexdigest())


def test_describe_lists_only_sram_writes():
    d = rr.describe(IMAGE, SHA)
    assert d['write_range'] == ['0x1c02000', '0x1c02800'] and d['blocks'] == 4
    assert d['flash_writes'] == 0
    assert d['commands'][0] == 'INQUIRY' and d['commands'][-1] == 'FB08 0x01c02000 arg 1'
    assert {c.split()[0] for c in d['commands']} == {'INQUIRY', 'FB06', 'FD07', 'FB08'}


# ---- the byte-level gate -------------------------------------------------

def cdb(op, *args):
    return (op.to_bytes(2, 'big') + b''.join(args)).ljust(16, b'\xff')


GOOD_WRITE = cdb(0xFB06, BASE.to_bytes(4, 'big'), b'\x02\x00\x00', b'\x12\x34')
GOOD_READ = cdb(0xFD07, BASE.to_bytes(4, 'big'), b'\x02\x00')
GOOD_JUMP = cdb(0xFB08, BASE.to_bytes(4, 'big'), b'\x00\x01')


def test_gate_admits_exactly_the_four_commands():
    for good in (GOOD_WRITE, GOOD_READ, GOOD_JUMP, bytes.fromhex('120000002400')):
        assert rr.check_cdb(good) == good


def test_gate_refuses_every_other_opcode_exhaustively():
    """All 65,536 opcodes with an otherwise valid in-window body."""
    admitted = []
    for op in range(0x10000):
        candidate = cdb(op, BASE.to_bytes(4, 'big'), b'\x02\x00\x00', b'\x00\x00')
        try:
            rr.check_cdb(candidate)
            admitted.append(op)
        except rr.Refused:
            pass
    # Only FB06 passes with this body: FD07 and FB08 need their own tails.
    assert admitted == [0xFB06]
    for op in range(0x10000):
        for body in (cdb(op, BASE.to_bytes(4, 'big'), b'\x02\x00'),
                     cdb(op, BASE.to_bytes(4, 'big'), b'\x00\x01')):
            try:
                rr.check_cdb(body)
            except rr.Refused:
                continue
            assert op in (0xFD07, 0xFB08), hex(op)


@pytest.mark.parametrize('raw,reason', [
    (cdb(0xFC12, bytes(6)), 'eFuse'),
    (cdb(0xA100, bytes(6)), 'A1'),
    (cdb(0xA1FF), 'A1'),
    (bytes.fromhex('F02224357DF7').ljust(16, b'\xff'), 'F0'),
    (bytes.fromhex('F02224357FF7').ljust(16, b'\xff'), 'F0'),
    (bytes.fromhex('5AAAA5').ljust(16, b'\x00'), '5A AA A5'),
    (cdb(0xFB01, bytes(4)), 'erase'),
    (cdb(0xFB04, bytes(6)), 'program'),
    (cdb(0xFD05, bytes(6)), 'flash read'),
    (cdb(0xFC09), 'key'),
    (cdb(0xFC0A), 'online'),
    (cdb(0xFC14), 'buffer'),
    (cdb(0xFC0C, b'\x00\x00\x00\x01'), 'run app'),
])
def test_named_refusals(raw, reason):
    with pytest.raises(rr.Refused, match=reason):
        rr.check_cdb(raw)


@pytest.mark.parametrize('address,length', [
    (BASE - 512, 512), (BASE + 24064, 512), (BASE + 24064 - 256, 512),
    (BASE + 1, 512), (BASE, 256), (BASE, 1024), (0x02000000, 512), (0, 512),
])
def test_gate_refuses_outside_the_window(address, length):
    for op in (0xFB06, 0xFD07):
        body = address.to_bytes(4, 'big') + length.to_bytes(2, 'big')
        raw = cdb(op, body, b'\x00\x00\x00') if op == 0xFB06 else cdb(op, body)
        with pytest.raises(rr.Refused):
            rr.check_cdb(raw)


def test_gate_refuses_jump_elsewhere_or_other_argument():
    for raw in (cdb(0xFB08, (BASE + 512).to_bytes(4, 'big'), b'\x00\x01'),
                cdb(0xFB08, BASE.to_bytes(4, 'big'), b'\x00\x00'),
                cdb(0xFB08, BASE.to_bytes(4, 'big'), b'\x00\x01\x00')):
        with pytest.raises(rr.Refused):
            rr.check_cdb(raw)


def test_gate_refuses_odd_lengths_and_types():
    with pytest.raises(rr.Refused):
        rr.check_cdb(GOOD_WRITE[:15])
    with pytest.raises(rr.Refused):
        rr.check_cdb('12')
    with pytest.raises(rr.Refused):
        rr.check_cdb(bytes.fromhex('120000002401'))


# ---- order ----------------------------------------------------------------

def test_sequence_order_and_single_use():
    blocks = rr.plan(IMAGE)
    seq = rr.Sequence(blocks)
    with pytest.raises(rr.Refused):
        seq.request(0xFB06, blocks[0][0], blocks[0][2])     # before inquiry
    seq = rr.Sequence(blocks)
    seq.request(0x12)
    with pytest.raises(rr.Refused):
        seq.request(0xFB08, BASE)                             # jump before upload
    seq = rr.Sequence(blocks)
    seq.request(0x12)
    with pytest.raises(rr.Refused):
        seq.request(0xFB06, blocks[1][0], blocks[1][2])     # out of order
    seq = rr.Sequence(blocks)
    seq.request(0x12)
    with pytest.raises(rr.Refused):
        seq.request(0xFB06, blocks[0][0], blocks[0][1])     # plain, not ciphered
    seq = rr.Sequence(blocks)
    seq.request(0x12)
    for a, _p, c in blocks:
        cdb_, out, n = seq.request(0xFB06, a, c)
        assert out == c and n == 0
        assert cdb_[9:11] == crc16_xmodem(c, 0).to_bytes(2, 'little')
    with pytest.raises(rr.Refused):
        seq.request(0xFB06, blocks[0][0], blocks[0][2])     # no resend
    with pytest.raises(rr.Refused):
        seq.request(0xFB08, BASE)                             # jump before verify
    for a, _p, _c in blocks:
        seq.request(0xFD07, a)
    seq.request(0xFB08, BASE)
    assert seq.stage == 'done'
    with pytest.raises(rr.Refused):
        seq.request(0xFB08, BASE)                             # never twice
    with pytest.raises(rr.Refused):
        seq.request(0x12)


# ---- the runner against a model ROM --------------------------------------

class ModelRom:
    def __init__(self, *, corrupt=None, jump='answer', inquiry=b'WL82    UBOOT1.00       '):
        self.mem, self.sent, self.corrupt, self.jump, self.inquiry = {}, [], corrupt, jump, inquiry

    def __call__(self, cdb, data_out, in_size, timeout_ms=3000):
        self.sent.append(bytes(cdb))
        op = int.from_bytes(cdb[:2], 'big')
        if cdb[0] == 0x12:
            return bytes(8) + self.inquiry.ljust(28, b' ')
        address = int.from_bytes(cdb[2:6], 'big')
        if op == 0xFB06:
            assert int.from_bytes(cdb[9:11], 'little') == crc16_xmodem(data_out, 0)
            self.mem[address] = rr.cipher(data_out)   # the ROM deciphers
            return b''
        if op == 0xFD07:
            plain = self.mem[address]
            if self.corrupt == address:
                plain = bytes([plain[0] ^ 1]) + plain[1:]
            return rr.cipher(plain)                   # and ciphers reads
        if op == 0xFB08:
            if self.jump == 'timeout':
                raise OSError('SG_IO status=0 host=3 driver=0 resid=0 sense=')
            return cdb[:2] + bytes(14)
        raise AssertionError(cdb.hex())


@pytest.fixture
def runner(monkeypatch):
    calls = {}

    def fake_pin(role, usb_path, device, **kw):
        calls['pin'] = (role, usb_path, device, kw.get('devnum'))
        return {'role': role, 'path': usb_path, 'devnum': '9', 'dir': Path('/nonexistent')}

    monkeypatch.setattr(bench_target, 'pin_rom_target', fake_pin)
    monkeypatch.setattr(base, 'os', SimpleNamespace(
        open=lambda *a: calls.setdefault('opened', a) and 99, close=lambda fd: None,
        O_RDWR=2))

    def make(rom, image=IMAGE, sha=SHA):
        log = []
        r = rr.RamRunner('/dev/sg1', lambda e, **f: log.append((e, f)), image, sha,
                         usb_path='3-1.2', devnum='9')
        r.transport = rom
        r.events = log
        return r
    make.calls = calls
    return make


def test_runner_pins_the_devkit_role_before_opening(runner):
    rom = ModelRom()
    runner(rom)
    assert runner.calls['pin'] == ('devkit', '3-1.2', '/dev/sg1', '9')
    assert rr.RamRunner.ROLE == 'devkit'


def test_runner_refuses_a_bad_image_before_pinning(runner):
    with pytest.raises(rr.Refused):
        runner(ModelRom(), sha='0' * 64)
    assert 'pin' not in runner.calls and 'opened' not in runner.calls


def test_full_run_uploads_verifies_and_jumps_once(runner):
    rom = ModelRom()
    r = runner(rom)
    receipt = r.run()
    assert receipt['readback'] == 'equal' and receipt['jump']['answered']
    ops = [c[:2].hex() if c[0] != 0x12 else '12' for c in rom.sent]
    assert ops == ['12'] + ['fb06'] * 4 + ['fd07'] * 4 + ['fb08']
    image = b''.join(rom.mem[BASE + i * 512] for i in range(4))
    assert image[:len(IMAGE)] == IMAGE and image[len(IMAGE):] == bytes(4 * 512 - len(IMAGE))
    assert all(rr.check_cdb(c) for c in rom.sent)
    assert r.seq.stage == 'done'


def test_readback_mismatch_stops_before_the_jump(runner):
    rom = ModelRom(corrupt=BASE + 1024)
    r = runner(rom)
    with pytest.raises(ValueError, match='not jumping'):
        r.run()
    assert not any(c[:2] == b'\xfb\x08' for c in rom.sent)
    assert r.seq.stage == 'stopped'
    with pytest.raises(rr.Refused):
        r.cmd(0xFB08, address=BASE)


def test_unanswered_jump_is_recorded_not_retried(runner):
    rom = ModelRom(jump='timeout')
    r = runner(rom)
    receipt = r.run()
    assert receipt['jump']['answered'] is False and 'host=3' in receipt['jump']['error']
    assert sum(c[:2] == b'\xfb\x08' for c in rom.sent) == 1
    with pytest.raises(rr.Refused):
        r.cmd(0xFB08, address=BASE)


def test_wrong_rom_uploads_nothing(runner):
    rom = ModelRom(inquiry=b'BR25    UBOOT1.00       ')
    r = runner(rom)
    with pytest.raises(rr.Refused, match='WL82'):
        r.run()
    assert len(rom.sent) == 1


def test_write_failure_stops_the_sequence(runner):
    def failing(cdb, data_out, in_size, timeout_ms=3000):
        if cdb[:2] == b'\xfb\x06':
            raise OSError('gone')
        return ModelRom()(cdb, data_out, in_size)
    r = runner(failing)
    with pytest.raises(OSError):
        r.run()
    assert r.seq.stage == 'stopped'


def test_no_midi_serial_or_flash_code_is_imported():
    tree = ast.parse((TOOLS / 'ram_runner.py').read_text())
    names = {a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not names & {'mido', 'rtmidi', 'serial', 'termios', 'tty', 'usb', 'fm1_softkey_probe',
                        'devkit_boot_control', 'devkit_loader_reset', 'fm1_uboot_restore'}


def test_plan_cli_touches_no_device(tmp_path, capsys, monkeypatch):
    image = tmp_path / 'img.bin'
    image.write_bytes(IMAGE)
    monkeypatch.setattr(base, 'os', SimpleNamespace(open=lambda *a: pytest.fail('opened a device')))
    assert rr.main(['plan', '--image', str(image), '--sha256', SHA]) == 0
    assert '"blocks": 4' in capsys.readouterr().out


def test_run_cli_refuses_hash_mismatch_before_anything(tmp_path, monkeypatch):
    image = tmp_path / 'img.bin'
    image.write_bytes(IMAGE)
    monkeypatch.setattr(bench_target, 'pin_rom_target', lambda *a, **k: pytest.fail('pinned'))
    with pytest.raises(rr.Refused):
        rr.main(['run', '--device', '/dev/sg1', '--usb-path', '3-1.2', '--image', str(image),
                 '--sha256', '0' * 64, '--out', str(tmp_path / 'out')])
    assert not (tmp_path / 'out').exists()


def test_fm1_path_is_refused_by_pinning():
    config = {'schema': 1, 'roles': {'fm1': {'paths': ['1-2'], 'buses': [1]},
                                     'devkit': {'paths': [], 'buses': [3]}}}
    with pytest.raises(bench_target.PinError):
        bench_target.check_role_path(rr.RamRunner.ROLE, '1-2', config)
