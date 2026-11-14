"""tools/fm1-transporter/fm1t_m8.py: the M8 flash-install tool, against a fake
of the FM-1 Transporter data port. The fake is tests/test_fm1t_m5.py's, with
`wsec` and flash made real after src/transporter_proto.c do_write_sector and
src/jieli_uboot.c jl_flash_write_sector (kurogedelic FM-1-transporter 80c5012):
reply order no-uboot, crc, range, then erase, program, verify. No serial port
is opened and no real package, loader or image is used: every pinned hash is
swapped for a synthetic one by the `world` fixture, and test_pinned_constants
checks the real values."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'fm1-transporter' / 'fm1t_m8.py'
V15_FWSC = ROOT.parents[2] / 'scratch' / 'FM-1_v15_cdn.fwsc'   # main checkout, git-ignored


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m8 = _load('fm1t_m8', TOOL)
harness = _load('test_fm1t_m5_harness_for_m8', ROOT / 'tests' / 'test_fm1t_m5.py')
LOADER, crc, strtoul = harness.LOADER, harness.crc, harness.strtoul

SERIAL = '560A5ACCF298BDCB'
PORT = f'/dev/serial/by-id/usb-kurogedelic_FM-1_Transporter_{SERIAL}-if02'
SEC = 0x1000

# -- A synthetic world: V15, a Lunar image and the flash they live in --------
_rng = random.Random(8)
V15_REGION = _rng.randbytes(0x93000)
LUNAR_REGION = bytearray(V15_REGION)
LUNAR_SECTORS = [0x4000, 0x5000, 0x6000, 0x50000, 0x92000]
for _s in LUNAR_SECTORS:
    LUNAR_REGION[_s:_s + SEC] = _rng.randbytes(SEC)
LUNAR_REGION = bytes(LUNAR_REGION)
VM = _rng.randbytes(0x100000 - 0x93000)
FLASH_V15 = V15_REGION + VM
FLASH_LUNAR = LUNAR_REGION + VM


def package(region, salt):
    return bytes([salt]) * 0x414 + region + bytes([salt]) * 64


V15_PKG = package(V15_REGION, 1)
LUNAR_PKG = package(LUNAR_REGION, 2)


def sha(data):
    return hashlib.sha256(data).hexdigest()


TOOL_SHA = sha(TOOL.read_bytes())


class FlashFake(harness.FakeTransporter):
    """The M5 fake with real flash: `wsec` erases, programs and verifies one
    4 KiB sector of `self.flash` (a bytearray), and `read` serves it."""

    def __init__(self, flash=FLASH_V15, *, wsec_fault=None, read_glitch=None,
                 after_writes=None, **kw):
        super().__init__(flash=bytearray(flash), **kw)
        self.wsec_fault = wsec_fault or {}     # addr -> 'write' | 'silent' | 'corrupt'
        self.read_glitch = read_glitch         # index of the full read to flip a byte in
        self.after_writes = after_writes       # callable(flash) once all wsecs are done
        self.full_reads = 0
        self.wsecs = []                        # sectors core 1 programmed

    def _poll(self, line, payload):
        argv = [t for t in re.split('[ \t]+', line) if t][:4]
        if argv and argv[0] == 'wsec' and len(argv) == 3:
            return self._wsec(strtoul(argv[1], 0), strtoul(argv[2], 16), payload)
        if argv and argv[0] == 'read' and argv[1:] == ['0x0', '1048576']:
            if self.after_writes and self.wsecs:
                self.after_writes(self.flash)
                self.after_writes = None
            idx, self.full_reads = self.full_reads, self.full_reads + 1
            if idx == self.read_glitch:
                saved = bytes(self.flash)
                self.flash[0x70000] ^= 0x01
                super()._poll(line, payload)
                self.flash[:] = saved
                return None
        return super()._poll(line, payload)

    def _wsec(self, addr, c, payload):
        if not self.uboot:
            return self._tx('ERR no-uboot')
        if crc(payload) != c:
            return self._tx(f'ERR crc {crc(payload):08X}')
        if addr < 0x4000 or addr >= 0x93000 or addr % SEC:
            return self._tx('ERR range')
        if not self._ensure_loader():
            return self._tx('ERR write')
        self.flash_written = True
        fault = self.wsec_fault.get(addr)
        self.flash[addr:addr + SEC] = b'\xff' * SEC          # CMD_ERASE_SECTOR
        if fault == 'write':
            return self._tx('ERR write')                      # erased, not programmed
        if fault == 'corrupt':
            bad = bytearray(payload)
            bad[7] ^= 0x40
            self.flash[addr:addr + SEC] = bad
            self.wsecs.append(addr)
            return self._tx('OK')                             # a verify the firmware missed
        self.flash[addr:addr + SEC] = payload
        self.wsecs.append(addr)
        if fault == 'silent':
            return None
        return self._tx('OK')


@pytest.fixture(autouse=True)
def world(monkeypatch, tmp_path):
    def refuse(*_a, **_k):
        raise AssertionError('a test tried to open a real serial port')
    monkeypatch.setattr(m8, 'open_port', refuse)
    monkeypatch.setattr(m8, 'LOADER_SHA256', sha(LOADER))
    monkeypatch.setattr(m8, 'HEAD_SHA256', sha(V15_REGION[:0x4000]))
    monkeypatch.setattr(m8, 'V15_PACKAGE_SHA256', sha(V15_PKG))
    monkeypatch.setattr(m8, 'V15_PACKAGE_BYTES', len(V15_PKG))
    monkeypatch.setattr(m8, 'V15_REGION_SHA256', sha(V15_REGION))
    monkeypatch.setattr(m8, 'KNOWN_REGIONS', {sha(V15_REGION): ('stock V15', 'FM-1_015', 0x93000)})
    monkeypatch.setattr(m8, 'APPROVED_PACKAGE_SHA256', sha(LUNAR_PKG))
    monkeypatch.setattr(m8, 'APPROVED_PACKAGE_BYTES', len(LUNAR_PKG))
    monkeypatch.setattr(m8, 'APPROVED_BUILD_ID', 'm8-test')
    monkeypatch.setattr(m8, 'LOCK_DIR', tmp_path / 'state' / 'fm1t_m8')
    (tmp_path / 'wl82loader.bin').write_bytes(LOADER)
    (tmp_path / 'FM-1.fwsc').write_bytes(V15_PKG)
    (tmp_path / 'lunar.fwsc').write_bytes(LUNAR_PKG)


def run(fake, argv, tmp_path, log='run/log.jsonl', port=PORT):
    fake.closed = False                     # the same unit, seen again in a new session
    (tmp_path / log).parent.mkdir(parents=True, exist_ok=True)
    opened = []

    def opener(p):
        opened.append(p)
        return fake

    code = m8.main(['--port', port, '--log', str(tmp_path / log)] + argv, opener=opener)
    events = []
    if (tmp_path / log).exists():
        events = [json.loads(x) for x in (tmp_path / log).read_text().splitlines()]
    return code, events, opened


def install(tmp_path, *extra, write=True, identity='FM-1_015', pkg='lunar.fwsc', digest=None):
    argv = ['install', str(tmp_path / pkg), '--sha256', digest or sha(LUNAR_PKG),
            '--identity', identity, '--loader', str(tmp_path / 'wl82loader.bin')]
    if write:
        argv += ['--write', '--tool-sha256', TOOL_SHA]
    return argv + list(extra)


def restore(tmp_path, *extra, write=True):
    argv = ['restore', '--v15', str(tmp_path / 'FM-1.fwsc'),
            '--loader', str(tmp_path / 'wl82loader.bin')]
    if write:
        argv += ['--write', '--tool-sha256', TOOL_SHA]
    return argv + list(extra)


def wsec_lines(fake):
    return [ln for ln in fake.lines if ln.startswith('wsec')]


def assert_nothing_written(fake):
    assert not wsec_lines(fake) and not fake.flash_written


def assert_never_sent_forbidden(fake):
    for ln in fake.lines:
        assert ln.split(' ')[0] not in ('uboot', 'k', 'memw', 'jump', 'runapp', 'memr')
    assert not fake.softkey_sent and not fake.runapp_sent and not fake.jumps


# -- What is pinned -----------------------------------------------------------

def test_pinned_constants():
    src = TOOL.read_text()
    real = _load('fm1t_m8_pristine', TOOL)
    assert real.APPROVED_PACKAGE_SHA256 is None and real.APPROVED_PACKAGE_BYTES is None
    assert 'APPROVED_PACKAGE_SHA256 = None' in src
    assert real.TRANSPORTER_SERIAL == SERIAL
    assert real.EXPECTED_INFO == 'OK key=980F type=3 id=856014'
    assert real.LOADER_SHA256 == 'd41da6126760c9d66660bcc0cac8d27d221806c5e369a8036921efe68dca5376'
    assert real.V15_PACKAGE_SHA256 == 'db1642b2b6fa5c2cccb11ffd13878068bb28601678d3644049f99dc40e7edb8a'
    assert real.V15_REGION_SHA256 == 'c1068a403c04a6378a626afb66cc217f72d13f10aa200e983b7a9817cc1dac03'
    assert real.HEAD_SHA256 == 'd9f43191777656de01c7bed4f9e9ba2e34e94832c5d2ed02c3fc7ab7a6d9bd67'
    assert (real.WRITE_MIN, real.WRITE_END, real.HEAD_END) == (0x4000, 0x93000, 0x4000)
    assert real.KNOWN_REGIONS == {real.V15_REGION_SHA256: ('stock V15', 'FM-1_015', 0x93000)}
    assert real.LOCK_DIR == Path.home() / '.local' / 'state' / 'fm1t_m8'
    assert real.LOCK_DIR != Path('.')


def test_head_pin_agrees_with_build_fwsc():
    bf = (ROOT / 'tools' / 'jieli' / 'build_fwsc.py').read_text()
    real = _load('fm1t_m8_pristine2', TOOL)
    assert f"'flash_head_sha256': '{real.HEAD_SHA256}'" in bf
    assert f"'package_sha256': '{real.V15_PACKAGE_SHA256}'" in bf
    assert f"'package_bytes': {real.V15_PACKAGE_BYTES}," in bf
    assert 'VM_BASE = 0x93000' in bf


@pytest.mark.skipif(not V15_FWSC.is_file(), reason='needs the private stock V15 package')
def test_real_v15_package_admits(monkeypatch):
    real = _load('fm1t_m8_real', TOOL)
    region = real.admit_v15(V15_FWSC)
    assert sha(region) == real.V15_REGION_SHA256 and sha(region[:0x4000]) == real.HEAD_SHA256


def test_install_refused_while_nothing_is_approved(tmp_path, monkeypatch):
    monkeypatch.setattr(m8, 'APPROVED_PACKAGE_SHA256', None)
    fake = FlashFake()
    for argv in (install(tmp_path), install(tmp_path, write=False)):
        code, _, opened = run(fake, argv, tmp_path, log=f'r{len(argv)}/log.jsonl')
        assert code == 1 and not opened


def test_no_override_flags():
    src = TOOL.read_text()
    for word in ('allow-unknown', 'allow_other', '--force', '--addr', '--range', '--offset',
                 '--sector'):
        assert word not in src
    sub = m8.build_parser()._subparsers._group_actions[0].choices
    opts = {o for name in ('install', 'restore') for a in sub[name]._actions
            for o in a.option_strings}
    assert opts == {'-h', '--help', '--sha256', '--identity', '--loader', '--write',
                    '--tool-sha256', '--v15'}


# -- Install -----------------------------------------------------------------

def test_install_dry_run_reads_twice_and_writes_nothing(tmp_path, capsys):
    fake = FlashFake()
    code, events, opened = run(fake, install(tmp_path, write=False), tmp_path)
    assert code == 0 and opened == [PORT]
    assert_nothing_written(fake)
    assert fake.lines.count('read 0x0 1048576') == 2
    end = events[-1]
    assert end['plan']['sectors'] == [f'{s:#07x}' for s in LUNAR_SECTORS]
    assert end['plan']['write_end'] == '0x93000'
    assert end['verdict'].startswith('dry run')
    for name in ('before-a', 'before-b'):
        assert (tmp_path / 'run' / f'log-{name}.bin').read_bytes() == FLASH_V15
    assert not (tmp_path / 'run' / 'log-after.bin').exists()
    assert not m8.LOCK_DIR.exists()


def test_install_writes_only_the_planned_sectors_and_proves_it(tmp_path):
    fake = FlashFake()
    code, events, _ = run(fake, install(tmp_path), tmp_path)
    assert code == 0, events[-1]
    assert bytes(fake.flash) == FLASH_LUNAR
    assert fake.wsecs == LUNAR_SECTORS
    assert wsec_lines(fake) == [f'wsec {s:#x} {crc(LUNAR_REGION[s:s + SEC]):08X}'
                                for s in LUNAR_SECTORS]
    # every wsec is followed by its own read-back, and the session ends with a full read
    seq = [ln for ln in fake.lines if ln.startswith(('wsec', 'read'))]
    assert seq[:2] == ['read 0x0 1048576'] * 2 and seq[-1] == 'read 0x0 1048576'
    body = seq[2:-1]
    assert body == [x for s in LUNAR_SECTORS for x in (f'wsec {s:#x} {crc(LUNAR_REGION[s:s + SEC]):08X}',
                                                       f'read {s:#x} 4096')]
    assert (tmp_path / 'run' / 'log-after.bin').read_bytes() == FLASH_LUNAR
    lock = m8.LOCK_DIR / f'install-{sha(LUNAR_PKG)}.lock'
    assert json.loads(lock.read_text())['package_sha256'] == sha(LUNAR_PKG)
    end = events[-1]
    assert end['sectors_written'] == [f'{s:#07x}' for s in LUNAR_SECTORS]
    assert events[0]['tool_sha256'] == TOOL_SHA and events[0]['build_id'] == 'm8-test'
    assert_never_sent_forbidden(fake)


def test_vm_and_head_are_never_touched(tmp_path):
    fake = FlashFake()
    run(fake, install(tmp_path), tmp_path)
    assert bytes(fake.flash[0x93000:]) == VM and bytes(fake.flash[:0x4000]) == V15_REGION[:0x4000]
    for ln in wsec_lines(fake):
        a = int(ln.split()[1], 16)
        assert 0x4000 <= a < 0x93000 and a % SEC == 0


def test_second_install_is_refused_from_any_directory(tmp_path):
    fake = FlashFake()
    assert run(fake, install(tmp_path), tmp_path)[0] == 0
    fake2 = FlashFake()
    code, _, opened = run(fake2, install(tmp_path), tmp_path, log='elsewhere/new/log.jsonl')
    assert code == 1 and not opened


def test_lock_taken_by_a_parallel_run_stops_before_any_wsec(tmp_path, monkeypatch):
    fake = FlashFake()
    real_read = m8.read_flash
    calls = []

    def racing_read(link):
        calls.append(1)
        if len(calls) == 2:
            m8.LOCK_DIR.mkdir(parents=True, exist_ok=True)
            m8.install_lock(sha(LUNAR_PKG)).write_text('other\n')
        return real_read(link)
    monkeypatch.setattr(m8, 'read_flash', racing_read)
    code, events, _ = run(fake, install(tmp_path), tmp_path)
    assert code == 3 and 'no second attempt' in events[-1]['verdict']
    assert_nothing_written(fake)


def test_install_dry_run_takes_no_lock_and_can_repeat(tmp_path):
    for i in range(2):
        assert run(FlashFake(), install(tmp_path, write=False), tmp_path,
                   log=f'd{i}/log.jsonl')[0] == 0
    assert run(FlashFake(), install(tmp_path), tmp_path, log='w/log.jsonl')[0] == 0


# -- Refusals before the port opens -------------------------------------------

@pytest.mark.parametrize('why', ['sha-arg', 'other-image', 'short', 'head', 'is-v15'])
def test_package_refusals_open_no_port(tmp_path, monkeypatch, why):
    pkg, digest = 'lunar.fwsc', None
    if why == 'sha-arg':
        digest = '0' * 64
    elif why == 'other-image':
        (tmp_path / 'x.fwsc').write_bytes(LUNAR_PKG + b'\0')
        pkg, digest = 'x.fwsc', sha(LUNAR_PKG + b'\0')
    else:
        data = {'short': LUNAR_PKG[:0x50000],
                'head': package(b'\0' + LUNAR_REGION[1:], 2),
                'is-v15': package(V15_REGION, 3)}[why]
        (tmp_path / 'x.fwsc').write_bytes(data)
        pkg, digest = 'x.fwsc', sha(data)
        monkeypatch.setattr(m8, 'APPROVED_PACKAGE_SHA256', sha(data))
        monkeypatch.setattr(m8, 'APPROVED_PACKAGE_BYTES', len(data))
    code, _, opened = run(FlashFake(), install(tmp_path, pkg=pkg, digest=digest), tmp_path)
    assert code == 1 and not opened


@pytest.mark.parametrize('cmd', ['install', 'restore'])
@pytest.mark.parametrize('tool_sha', [None, '0' * 64])
def test_write_needs_the_approved_tool_hash(tmp_path, cmd, tool_sha):
    argv = (install if cmd == 'install' else restore)(tmp_path, write=False) + ['--write']
    if tool_sha:
        argv += ['--tool-sha256', tool_sha]
    code, _, opened = run(FlashFake(), argv, tmp_path)
    assert code == 1 and not opened


@pytest.mark.parametrize('port', [
    PORT.replace('-if02', '-if00'),
    PORT.replace(SERIAL, '0123456789ABCDEF'),
    '/dev/ttyACM0', '/dev/serial/by-id/usb-kurogedelic_FM-1_Transporter_560A5ACCF298BDCB-if02x'])
def test_only_the_pinned_transporters_data_port(tmp_path, port):
    code, _, opened = run(FlashFake(), install(tmp_path), tmp_path, port=port)
    assert code == 1 and not opened


def test_v15_package_must_be_the_pinned_one(tmp_path):
    (tmp_path / 'FM-1.fwsc').write_bytes(package(V15_REGION, 9))
    code, _, opened = run(FlashFake(), restore(tmp_path), tmp_path)
    assert code == 1 and not opened


def test_loader_must_be_the_pinned_one(tmp_path):
    (tmp_path / 'wl82loader.bin').write_bytes(LOADER[:-1] + b'\0')
    code, _, opened = run(FlashFake(), install(tmp_path), tmp_path)
    assert code == 1 and not opened


def test_receipt_and_dumps_never_overwritten(tmp_path):
    (tmp_path / 'run').mkdir()
    (tmp_path / 'run' / 'log-before-a.bin').write_bytes(b'x')
    code, _, opened = run(FlashFake(), install(tmp_path), tmp_path)
    assert code == 1 and not opened
    (tmp_path / 'run2').mkdir()
    (tmp_path / 'run2' / 'log.jsonl').write_text('')
    code, _, opened = run(FlashFake(), install(tmp_path), tmp_path, log='run2/log.jsonl')
    assert code == 1 and not opened


# -- Stops inside the session, before any write --------------------------------

def test_running_v15_gets_nothing_but_status(tmp_path):
    fake = FlashFake(uboot=False, v15=True)
    code, events, _ = run(fake, install(tmp_path), tmp_path)
    assert code == 3 and 'D2' in events[-1]['verdict']
    assert fake.lines == ['ping', 'status']
    assert_never_sent_forbidden(fake)


def test_no_uboot_stops(tmp_path):
    fake = FlashFake(uboot=False)
    code, _, _ = run(fake, restore(tmp_path), tmp_path)
    assert code == 3 and fake.lines == ['ping', 'status']


@pytest.mark.parametrize('info', ['OK key=980F type=3 id=B36014', 'OK key=1234 type=3 id=856014',
                                  'ERR info'])
def test_other_chip_or_flash_stops(tmp_path, info):
    fake = FlashFake(info=info)
    code, _, _ = run(fake, install(tmp_path), tmp_path)
    assert code == 3 and 'read 0x0 1048576' not in fake.lines
    assert_nothing_written(fake)


@pytest.mark.parametrize('cmd', ['install', 'restore'])
def test_before_reads_that_differ_stop(tmp_path, cmd):
    fake = FlashFake(read_glitch=1)
    argv = install(tmp_path) if cmd == 'install' else restore(tmp_path)
    code, events, _ = run(fake, argv, tmp_path)
    assert code == 3 and 'differ in sectors 0x70000' in events[-1]['verdict']
    assert_nothing_written(fake)


def test_unknown_region_refuses_install(tmp_path):
    flash = bytearray(FLASH_V15)
    flash[0x60000] ^= 1
    fake = FlashFake(flash)
    code, events, _ = run(fake, install(tmp_path), tmp_path)
    assert code == 3 and 'not a known region' in events[-1]['verdict']
    assert_nothing_written(fake)


def test_a_lunar_unit_cannot_be_installed_over(tmp_path):
    code, events, _ = run(FlashFake(FLASH_LUNAR), install(tmp_path), tmp_path)
    assert code == 3 and 'not a known region' in events[-1]['verdict']


@pytest.mark.parametrize('identity', ['FM-1_092', 'FM-1_014', 'FM-1_501', ''])
def test_identity_must_match_the_layout(tmp_path, identity):
    fake = FlashFake()
    code, events, _ = run(fake, install(tmp_path, identity=identity), tmp_path)
    assert code == 3 and 'does not match the flash' in events[-1]['verdict']
    assert_nothing_written(fake)


@pytest.mark.parametrize('cmd', ['install', 'restore'])
def test_other_head_stops(tmp_path, cmd):
    flash = bytearray(FLASH_V15)
    flash[0x100] ^= 0x80
    fake = FlashFake(flash)
    argv = install(tmp_path) if cmd == 'install' else restore(tmp_path)
    code, events, _ = run(fake, argv, tmp_path)
    assert code == 3 and "not V15's" in events[-1]['verdict']
    assert_nothing_written(fake)


def test_read_failure_stops(tmp_path):
    fake = FlashFake(read_fail=True)
    code, _, _ = run(fake, install(tmp_path), tmp_path)
    assert code == 3
    assert_nothing_written(fake)


# -- Failures during the write, then the restore ---------------------------------

@pytest.mark.parametrize('fault,why', [('write', "'ERR write'"), ('silent', "''"),
                                       ('corrupt', 'read-back')])
def test_failed_sector_stops_and_restore_recovers(tmp_path, fault, why):
    fake = FlashFake(wsec_fault={0x5000: fault})
    code, events, _ = run(fake, install(tmp_path), tmp_path)
    assert code == 3 and why in events[-1]['verdict'] and 'restore' in events[-1]['verdict']
    assert [int(x.split()[1], 16) for x in wsec_lines(fake)] == [0x4000, 0x5000]
    assert bytes(fake.flash) not in (FLASH_V15, FLASH_LUNAR)       # a mixed state
    # The same unit, still in UBOOT, restored in a new session.
    fake.wsec_fault, fake.lines = {}, []
    fake.out.clear()
    code, events, _ = run(fake, restore(tmp_path), tmp_path, log='restore/log.jsonl')
    assert code == 0, events[-1]
    assert bytes(fake.flash) == FLASH_V15
    assert events[-1]['layout']['region'].startswith('unknown')
    assert [int(x.split()[1], 16) for x in wsec_lines(fake)] == [0x4000, 0x5000]


def test_change_outside_the_write_is_caught_by_the_final_read(tmp_path):
    def vm_moves(flash):
        flash[0xA0000] ^= 0xFF
    fake = FlashFake(after_writes=vm_moves)
    code, events, _ = run(fake, install(tmp_path), tmp_path)
    assert code == 3 and 'final read differs' in events[-1]['verdict']
    assert '0xa0000' in events[-1]['verdict']


def test_restore_after_a_full_install(tmp_path):
    fake = FlashFake()
    assert run(fake, install(tmp_path), tmp_path)[0] == 0
    fake.lines = []
    code, events, _ = run(fake, restore(tmp_path), tmp_path, log='r/log.jsonl')
    assert code == 0 and bytes(fake.flash) == FLASH_V15
    assert [int(x.split()[1], 16) for x in wsec_lines(fake)] == LUNAR_SECTORS
    assert (tmp_path / 'r' / 'log-after.bin').read_bytes() == FLASH_V15


def test_restore_from_erased_sectors_and_reruns(tmp_path):
    flash = bytearray(FLASH_V15)
    flash[0x30000:0x32000] = b'\xff' * 0x2000
    fake = FlashFake(flash)
    assert run(fake, restore(tmp_path, write=False), tmp_path, log='a/log.jsonl')[0] == 0
    assert_nothing_written(fake)
    assert run(fake, restore(tmp_path), tmp_path, log='b/log.jsonl')[0] == 0
    assert bytes(fake.flash) == FLASH_V15 and fake.wsecs == [0x30000, 0x31000]
    code, events, _ = run(fake, restore(tmp_path), tmp_path, log='c/log.jsonl')
    assert code == 0 and events[-1]['verdict'].startswith('nothing to write')
    assert fake.wsecs == [0x30000, 0x31000]


def test_restore_ignores_the_install_lock(tmp_path):
    m8.LOCK_DIR.mkdir(parents=True)
    m8.install_lock(sha(LUNAR_PKG)).write_text('x\n')
    fake = FlashFake(FLASH_LUNAR)
    assert run(fake, restore(tmp_path), tmp_path)[0] == 0
    assert bytes(fake.flash) == FLASH_V15


def test_restore_keeps_the_vm_as_it_was(tmp_path):
    flash = bytearray(FLASH_LUNAR)
    flash[0x95000:0x96000] = b'\x5a' * SEC          # V15 or Lunar wrote settings
    fake = FlashFake(flash)
    assert run(fake, restore(tmp_path), tmp_path)[0] == 0
    assert bytes(fake.flash[:0x93000]) == V15_REGION
    assert bytes(fake.flash[0x93000:]) == bytes(flash[0x93000:])


# -- The gate ----------------------------------------------------------------

GOOD_SECTORS = ['wsec 0x4000 0123ABCD', 'wsec 0x92000 0123ABCD', 'wsec 0x5a000 00000000']


@pytest.mark.parametrize('line', GOOD_SECTORS)
def test_wsec_lines_inside_the_range_pass_the_pattern(line):
    assert m8.check_line('install', line) == 'wsec'
    assert m8.check_line('restore', line) == 'wsec'


@pytest.mark.parametrize('line', [
    'wsec 0x0 0123ABCD', 'wsec 0x3000 0123ABCD', 'wsec 0x3fff 0123ABCD',
    'wsec 0x93000 0123ABCD', 'wsec 0xff000 0123ABCD', 'wsec 0x100000 0123ABCD',
    'wsec 0x4001 0123ABCD', 'wsec 0x4800 0123ABCD', 'wsec 16384 0123ABCD',
    'wsec 040000 0123ABCD', 'wsec 0x04000 0123ABCD', 'wsec 0X4000 0123ABCD',
    'wsec 0x4000 0123abcd', 'wsec 0x4000 123ABCD', 'wsec 0x4000', 'wsec  0x4000 0123ABCD',
    'wsec 0x4000 0123ABCD x', 'read 0x93000 4096', 'read 0x3000 4096', 'read 0x4000 4095',
    'read 0x4000 04096', 'read 0x0 1048575', 'read 0x93000 1048576'])
def test_lines_outside_the_range_are_refused(line):
    with pytest.raises(m8.Refused):
        m8.check_line('install', line)


def test_write_end_narrows_the_range():
    m8.check_line('install', 'wsec 0x8f000 0123ABCD', write_end=0x90000)
    with pytest.raises(m8.Refused):
        m8.check_line('install', 'wsec 0x90000 0123ABCD', write_end=0x90000)
    with pytest.raises(m8.Refused):                     # never wider than 0x93000
        m8.check_line('install', 'wsec 0x93000 0123ABCD', write_end=0xD9000)


@pytest.mark.parametrize('mode', list(m8.ALLOWED))
@pytest.mark.parametrize('line', ['uboot', 'k', 'runapp', 'memw 0x1c02000 16 00000000',
                                  'jump 0x1c02000 0x1', 'memr 0x1c02000 16', 'selftest',
                                  'ramrun', 'erase', 'wsec', 'ldr 0 4096 00000000x'])
def test_forbidden_lines_unsendable_in_every_mode(mode, line):
    with pytest.raises(m8.Refused):
        m8.check_line(mode, line)


@pytest.mark.parametrize('mode', ['status', 'rekey', 'info', 'dump'])
def test_read_only_modes_never_write(mode):
    for line in GOOD_SECTORS + ['read 0x4000 4096']:
        with pytest.raises(m8.Refused):
            m8.check_line(mode, line)


def test_random_and_mutated_lines_never_escape_the_range():
    rng = random.Random(88)
    alphabet = 'wsecradx0123456789abcdefABCDEF '
    seeds = GOOD_SECTORS + ['read 0x4000 4096', 'read 0x0 1048576', 'ldr 0 4096 0123ABCD']
    accepted = 0
    for i in range(20000):
        if i % 2:
            line = ''.join(rng.choice(alphabet) for _ in range(rng.randint(1, 30)))
        else:
            s = list(rng.choice(seeds))
            for _ in range(rng.randint(1, 3)):
                s[rng.randrange(len(s))] = rng.choice(alphabet)
            line = ''.join(s)
        try:
            name = m8.check_line('install', line)
        except m8.Refused:
            continue
        accepted += 1
        word, *rest = line.split(' ')
        if name in ('wsec', 'readsec'):
            a = strtoul(rest[0], 0)                       # what the firmware reads
            assert 0x4000 <= a < 0x93000 and a % 0x1000 == 0, line
        if name == 'read':
            assert line == 'read 0x0 1048576'
    assert accepted > 50


def test_link_refuses_wsec_until_armed_and_only_planned_sectors_once():
    sent = []

    class Port:
        in_waiting = 0

        def write(self, data):
            sent.append(bytes(data))

    link = m8.Link(Port(), 'install', lambda *a, **k: None)
    chunk = LUNAR_REGION[0x4000:0x5000]
    with pytest.raises(m8.Refused):                      # unarmed: the range is empty
        link.send_line(f'wsec 0x4000 {crc(chunk):08X}')
    with pytest.raises(m8.Refused):
        link.arm(LUNAR_REGION, 0x93000, [0x3000])
    with pytest.raises(m8.Refused):
        link.arm(LUNAR_REGION, 0x94000, [0x4000])
    link.arm(LUNAR_REGION, 0x93000, [0x4000, 0x5000])
    with pytest.raises(m8.Refused, match='armed once'):
        link.arm(LUNAR_REGION, 0x93000, [0x6000])
    with pytest.raises(m8.Refused, match='not a planned sector'):
        link.send_line(f'wsec 0x6000 {crc(LUNAR_REGION[0x6000:0x7000]):08X}')
    link.send_line(f'wsec 0x4000 {crc(chunk):08X}')
    link.send_payload(chunk)
    with pytest.raises(m8.Refused, match='never resent'):
        link.send_line(f'wsec 0x4000 {crc(chunk):08X}')
    other = V15_REGION[0x5000:0x6000]
    link.send_line(f'wsec 0x5000 {crc(other):08X}')
    with pytest.raises(m8.Refused, match="not the target's"):
        link.send_payload(other)
    with pytest.raises(m8.Refused, match='nothing is sent'):
        link.send_line('status')
    assert sent[-1].startswith(b'wsec 0x5000')            # the bad payload never went out


def test_link_refuses_arming_in_read_only_modes():
    link = m8.Link(object(), 'dump', lambda *a, **k: None)
    with pytest.raises(m8.Refused):
        link.arm(LUNAR_REGION, 0x93000, [0x4000])


def test_plan_write_refuses_changes_outside_the_range():
    target = bytearray(V15_REGION)
    target[0x1000] ^= 1
    with pytest.raises(m8.Refused, match='0x01000'):
        m8.plan_write(FLASH_V15, bytes(target), 0x93000)
    target = bytearray(V15_REGION)
    target[0x91000] ^= 1
    with pytest.raises(m8.Refused, match='0x91000'):
        m8.plan_write(FLASH_V15, bytes(target), 0x90000)
    with pytest.raises(m8.Refused):
        m8.plan_write(FLASH_V15, V15_REGION, 0x94000)
    assert m8.plan_write(FLASH_V15, LUNAR_REGION, 0x93000) == LUNAR_SECTORS


# -- Offline -------------------------------------------------------------------

def test_preflight_prints_the_plan_for_approval(tmp_path, capsys):
    code = m8.main(['preflight', '--package', str(tmp_path / 'lunar.fwsc'), '--sha256',
                    sha(LUNAR_PKG), '--v15', str(tmp_path / 'FM-1.fwsc'), '--loader',
                    str(tmp_path / 'wl82loader.bin')])
    out = capsys.readouterr().out
    assert code == 0
    assert f'sha256 {TOOL_SHA}' in out and SERIAL in out and '(APPROVED)' in out
    assert 'writes 5 sectors' in out and '0x92000' in out
    assert 'restore to V15 afterwards writes 5 sectors' in out


def test_compare(tmp_path, capsys):
    (tmp_path / 'a.bin').write_bytes(FLASH_V15)
    (tmp_path / 'b.bin').write_bytes(FLASH_V15)
    (tmp_path / 'c.bin').write_bytes(FLASH_LUNAR)
    assert m8.main(['compare', str(tmp_path / 'a.bin'), str(tmp_path / 'b.bin')]) == 0
    assert m8.main(['compare', str(tmp_path / 'a.bin'), str(tmp_path / 'c.bin')]) == 1


def test_dump_and_info_still_work(tmp_path):
    fake = FlashFake()
    code, _, _ = run(fake, ['dump', str(tmp_path / 'd.bin'), '--loader',
                            str(tmp_path / 'wl82loader.bin')], tmp_path)
    assert code == 0 and (tmp_path / 'd.bin').read_bytes() == FLASH_V15
    assert_nothing_written(fake)


# -- Structure -----------------------------------------------------------------

def test_link_is_the_only_writer_and_the_tool_is_self_contained():
    src = TOOL.read_text()
    tree = ast.parse(src)
    writers = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                        and sub.func.attr == 'write' and isinstance(sub.func.value, ast.Attribute)
                        and sub.func.value.attr == '_port'):
                    writers.add(node.name)
    assert writers == {'Link', '_write'}
    imports = {a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.Import)
               for a in n.names} | {n.module.split('.')[0] for n in ast.walk(tree)
                                    if isinstance(n, ast.ImportFrom)}
    assert imports <= {'argparse', 'hashlib', 'json', 'os', 'pathlib', 're', 'sys', 'time',
                       'zlib', 'serial'}
    assert src.count('serial.Serial(') == 1
    assert b'\xf0\x22\x24\x35\x7d\xf7' not in TOOL.read_bytes()
    for banned in ('0xFC12', 'FC12', '0xA1', '5A AA A5', '7F F7', 'sys.path'):
        assert banned not in src


def test_fake_wsec_follows_the_firmware():
    f = FlashFake()
    f.write(b'wsec 0x3000 00000000\n' + b'\0' * SEC)
    f.write(b'wsec 0x4000 00000000\n' + b'\0' * SEC)
    good = b'\x11' * SEC
    f.write(f'wsec 0x93000 {crc(good):08X}\n'.encode() + good)
    f.write(f'wsec 0x4000 {crc(good):08X}\n'.encode() + good)
    zero = f'ERR crc {crc(bytes(SEC)):08X}'
    assert f.out.decode().splitlines() == [zero, zero, 'ERR range', 'ERR write']   # no loader yet
    assert bytes(f.flash) == FLASH_V15
