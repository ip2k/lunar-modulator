"""tools/jieli/build_fwsc.py: synthetic packages (no vendor bytes), the
browser verifier cross-check, and opt-in real-V15 checks.

Set FM1_STOCK_FWSC to your stock V15 package (and optionally
FM1_STOCK_UNPACK to its fwunpack_newfw.py output) to run the real-file tests.
Nothing here opens a device.
"""
import json
import os
import pathlib
import re
import shutil
import struct
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/jieli'))
import build_fwsc as bf  # noqa: E402
import fm1_budget  # noqa: E402
import inspect_fwsc as outer  # noqa: E402
import inspect_stock_flash as nested  # noqa: E402
import model_app_replacement as model  # noqa: E402
from package_guard import STOCK_SPL_SHA256, STOCK_SPL_SIZE  # noqa: E402
from tests.test_inspect_stock_flash import jlfs  # noqa: E402

SLOT = 0x200
STOCK_APP = b'STOCK-APP:' + b'FM-1_015\0' + bytes(range(256)) * 2
STOCK_APP = STOCK_APP[:SLOT]
CLI = ROOT / 'sim/web/test/lunar-package-admission-cli.mjs'
REAL = os.environ.get('FM1_STOCK_FWSC')


def synthetic_decoded():
    """A V15-shaped flash.bin (0x93000 B) with a 0x200-byte app slot."""
    decoded = bytearray(0x93000)
    decoded[:32] = struct.pack('<H', outer.crc16(bytes(30))) + bytes(30)
    blob = bytes([100] * 16) + bytes(100 ^ (0 if 0x980f & (1 << i) else 255) for i in range(16))
    cfg = blob + struct.pack('<H', outer.crc16(blob)) + bytes(665)
    decoded[0x38d0:0x38d0 + 699] = cfg
    bank = bytes((i * 7) & 255 for i in range(14368))
    bank_head = struct.pack('<HHIIH', 1, len(bank), 0x01c02000, 16, outer.crc16(bank))
    spl = bank_head + struct.pack('<H', outer.crc16(bank_head)) + bank
    decoded[0xa0:0x38d0] = spl
    decoded[0x20:0xa0] = (
        jlfs('uboot.boot', 0xa0, len(spl), 0, 0, spl)
        + jlfs('isd_config.ini', 0x38d0, 699, 2, 0, cfg)
        + jlfs('app_dir_head', 0x4000, 0xffffffff, 0x81, 0)
        + jlfs('key_mac', 0xff000, 0x1000, 0x12, 0xffff))
    decoded[0x4120:0x4120 + SLOT] = STOCK_APP
    decoded[0x4320:0x4322] = b'CF'
    children = [jlfs('app.bin', 0x120, SLOT, 0x82, 0, STOCK_APP),
                jlfs('cfg_tool.bin', 0x320, 2, 0x82, 0, b'CF')]
    for index, name in enumerate(['VM', 'PRCT', 'BTIF', 'USR']):
        address, size, flags = nested.EXPECTED_RESERVED[name]
        children.append(jlfs(name, address, size, flags, int(index == 3)))
    decoded[0x4020:0x40e0] = b''.join(children)
    decoded[0x4000:0x4020] = jlfs('app_area_head', 0x02000120, 0x400, 0x83, 0, decoded[0x4020:0x4400])
    decoded[0x4440:0x4443] = b'EQ!'
    decoded[0x4420:0x4440] = jlfs('eq_cfg_hw.bin', 0x40, 3, 0x82, 1, b'EQ!')
    decoded[0x4400:0x4420] = jlfs('cfg', 0x20, 0x80, 0x83, 1, decoded[0x4420:0x4480])
    decoded[0x5000:0x5010] = b'UNREFERENCED-TAI'
    return decoded


def synthetic_stock():
    decoded = synthetic_decoded()
    flash = bytearray(decoded)
    for offset in [0, 0x20, 0x40, 0x60, 0x80]:
        flash[offset:offset + 32] = outer.header_decode(decoded[offset:offset + 32])
    flash[0xa0:0xb0] = outer.header_decode(decoded[0xa0:0xb0])
    flash[0xb0:0x38d0] = outer.header_decode(decoded[0xb0:0x38d0])
    flash[0x4000:] = outer.sfc_decode(decoded[0x4000:], 0)
    image = bytearray(0x400) + flash
    image += b'OTA' + bytes(29) + bytes(48) + b'JLUFW' + bytes(11)
    values = [(0, 'flash.bin', 0x400, 0x93000), (100, 'ota.bin', 0x93400, 3), (255, 'tail.bin', 0x93420, 64)]
    for ordinal, (kind, name, start, length) in enumerate(values):
        fields = (kind, ordinal, outer.crc16(image[start:start + length]), 0,
                  start, length, length, bytes(44), name.encode())
        image[64 + ordinal * 80:144 + ordinal * 80] = outer.header_decode(struct.pack('<HHHHIII44s16s', *fields))
    header = struct.pack('<HIHHI48s', outer.crc16(image[64:304]), len(image), 3, 4, 512, b'AC791N')
    image[:64] = outer.header_decode(struct.pack('<H', outer.crc16(header)) + header)
    raw = bytearray()
    for index in range(20):
        raw += image[index * 47:(index + 1) * 47]
        raw.append(b'FM-1_015'[index] + index + 1 if index < 8 else 125)
    return bytes(raw + image[940:])


@pytest.fixture
def stock(monkeypatch, tmp_path):
    # The synthetic SPL is not the FM-1's, so only inspect_fwsc's built-in
    # default-pin guard is bypassed; build_fwsc's own guard calls use the
    # profile's pin and still run.
    monkeypatch.setattr(outer, 'check_package', lambda *args, **kw: {'passed': True})
    raw = synthetic_stock()
    profile = bf.stock_profile(raw, nested.extract_stock_components(raw))
    path = tmp_path / 'stock.fwsc'
    path.write_bytes(raw)
    return raw, profile, {profile['package_sha256']: profile}, path


def lunar_app(identity='FM-1_501', size=0x80):
    body = b'LUNAR\0' + identity.encode() + b'\0'
    return body + bytes((i * 13) & 255 for i in range(size - len(body)))


def build(stock, tmp_path, app=None, identity='FM-1_501', name='lunar.fwsc'):
    raw, profile, profiles, path = stock
    app_path = tmp_path / f'{name}.app'
    app_path.write_bytes(lunar_app(identity) if app is None else app)
    return bf.build_install(path, app_path, identity, tmp_path / name, profiles=profiles)


def repack(pkg, profile, area_edit=None, flash_edit=None, log_edit=None, fix_app_record=True):
    """Apply an edit and repair every CRC, so only the content rules can catch it."""
    log = model.logical(pkg)
    fo, fb = profile['flash_offset'], profile['flash_bytes']
    flash = bytearray(log[fo:fo + fb])
    area = bytearray(outer.sfc_decode(flash[0x4000:], 0))
    if area_edit:
        area_edit(area)
    rec, addr = profile['app_record_offset'], profile['app_offset']
    if fix_app_record:
        size = struct.unpack_from('<I', area, rec + 8)[0]
        model.checksum_record(area, rec, area[addr:addr + size])
    model.checksum_record(area, 0, area[32:profile['app_area_record_bytes']])
    flash[0x4000:] = outer.sfc_decode(area, 0)
    if flash_edit:
        flash_edit(flash)
    log[fo:fo + fb] = flash
    if log_edit:
        log_edit(log)
    model.repair_outer(log, profile['flash_entry_index'], flash)
    return model.physical(log, pkg)


# ---- the pin ---------------------------------------------------------------

def test_pinned_profile_agrees_with_the_other_gates():
    p = bf.V15_PROFILE
    assert p['components_sha256']['top/uboot.boot'] == STOCK_SPL_SHA256
    assert p['spl_bytes'] == STOCK_SPL_SIZE
    assert p['app_slot_bytes'] == fm1_budget.APP_SLOT
    assert p['app_area_offset'] + p['app_offset'] == fm1_budget.APP_FLASH_OFFSET
    assert p['app_area_offset'] + p['app_offset'] + p['app_slot_bytes'] == fm1_budget.CFG_TOOL_OFFSET
    assert p['vm_base'] == nested.EXPECTED_RESERVED['VM'][0] == p['flash_bytes']
    assert p['sfc_key'] == outer.STOCK_CHIP_KEY
    # Baud Girl's installer constant for file bytes [0x414, 0x4414) [reported].
    assert p['flash_head_sha256'].startswith('d9f43191') and p['flash_head_sha256'].endswith('d9bd67')
    assert '__PIN__' not in json.dumps(p)


def test_browser_module_carries_the_same_profile():
    text = (ROOT / 'sim/web/www/lunar-package-admission.js').read_text()
    block = text.split('// BEGIN V15_PROFILE', 1)[1].split('// END V15_PROFILE', 1)[0]
    js = json.loads(block[block.index('{'):block.rindex('}') + 1])
    assert js == bf.V15_PROFILE
    assert 'http://' not in text and 'https://' not in text and 'import ' not in text


# ---- round trip and build --------------------------------------------------

def test_repack_of_stock_through_the_builder_is_byte_identical(stock):
    raw, profile, _, _ = stock
    comps = nested.extract_stock_components(raw)
    assert bf.assemble(raw, comps['files/app.bin'], profile['product'], profile) == raw


def test_install_changes_only_the_app_and_passes_every_gate(stock, tmp_path):
    raw, profile, profiles, _ = stock
    result = build(stock, tmp_path)
    pkg = (tmp_path / 'lunar.fwsc').read_bytes()
    manifest = json.loads((tmp_path / 'lunar.fwsc.manifest.json').read_text())
    assert result['guard']['passed']
    assert manifest == bf.describe_package(pkg, profile) and manifest['kind'] == 'lunar-install'
    assert manifest['product'] == 'FM-1_501' and manifest['version'] == 501
    assert manifest['app']['bytes'] == 0x80 and manifest['app']['spare_bytes'] == SLOT - 0x80
    assert manifest['app']['flash_offset'] == 0x4120 and manifest['app']['identity_offset'] == 6
    assert manifest['flash']['write_range'] == [0x4000, 0x93000]
    assert all(0x4000 <= lo < hi <= 0x93000 for lo, hi in manifest['flash']['mutable_ranges'])
    lo, hi = result['flash_changes']['hull']
    assert 0x4000 <= lo and hi <= 0x4120 + SLOT
    assert len(pkg) == len(raw) and bf.markers_identity(pkg) == 'FM-1_501'
    # Head, everything after flash.bin, and the cfg/reserved tree are stock.
    log, slog = model.logical(pkg), model.logical(raw)
    assert log[0x400:0x4400] == slog[0x400:0x4400] and log[0x93400:] == slog[0x93400:]
    area = outer.sfc_decode(log[0x4400:0x93400], 0)
    stock_area = outer.sfc_decode(slog[0x4400:0x93400], 0)
    assert area[0x120 + 0x80:0x120 + SLOT] == b'\xff' * (SLOT - 0x80)
    assert area[0x120 + SLOT:] == stock_area[0x120 + SLOT:]
    assert b'STOCK-APP' not in area
    assert bf.verify_file(tmp_path / 'lunar.fwsc', tmp_path / 'lunar.fwsc.manifest.json', profiles) == manifest
    with pytest.raises(FileExistsError):
        build(stock, tmp_path)


def test_a_full_slot_app_leaves_no_fill(stock, tmp_path):
    result = build(stock, tmp_path, app=lunar_app(size=SLOT))
    assert result['manifest']['app']['spare_bytes'] == 0


@pytest.mark.parametrize('app,identity,message', [
    (lunar_app(size=SLOT + 1), 'FM-1_501', 'fm1_budget'),
    (b'', 'FM-1_501', 'empty'),
    (lunar_app('FM-1_015'), 'FM-1_015', 'Lunar range'),
    (lunar_app('FM-1_092'), 'FM-1_092', 'Lunar range'),
    (lunar_app('FM-1_901'), 'FM-1_901', 'Lunar range'),
    (b'no identity here' * 4, 'FM-1_501', 'exactly once'),
    (lunar_app() + b'FM-1_501\0', 'FM-1_501', 'exactly once'),
    (lunar_app() + b'FM-1_015\0', 'FM-1_501', 'no other'),
    (lunar_app('FM-1_502'), 'FM-1_501', 'exactly once'),
])
def test_refuses_apps_and_identities_outside_the_rules(stock, tmp_path, app, identity, message):
    with pytest.raises(ValueError, match=message):
        build(stock, tmp_path, app=app, identity=identity)
    assert not (tmp_path / 'lunar.fwsc').exists()


def test_refuses_a_stock_package_that_is_not_pinned(stock, tmp_path):
    raw, _, profiles, path = stock
    path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
    with pytest.raises(ValueError, match='not a pinned stock V15'):
        build(stock, tmp_path)
    with pytest.raises(ValueError, match='not a pinned stock V15'):
        bf.build_install(path, path, 'FM-1_501', tmp_path / 'x.fwsc')  # default pins: real V15 only


def test_refuses_a_lunar_package_as_stock_input(stock, tmp_path):
    build(stock, tmp_path)
    _, _, profiles, _ = stock
    app = tmp_path / 'again.app'
    app.write_bytes(lunar_app('FM-1_502'))
    with pytest.raises(ValueError, match='not a pinned stock V15'):
        bf.build_install(tmp_path / 'lunar.fwsc', app, 'FM-1_502', tmp_path / 'again.fwsc', profiles=profiles)


def test_cross_check_against_an_independent_unpack(stock, tmp_path):
    raw, _, profiles, path = stock
    comps = nested.extract_stock_components(raw)
    unpack = tmp_path / 'unpack'
    for rel, data in comps.items():
        rel = 'files/cfg-extracted/eq_cfg_hw.bin' if rel == 'files/eq_cfg_hw.bin' else rel
        (unpack / rel).parent.mkdir(parents=True, exist_ok=True)
        (unpack / rel).write_bytes(data)
    app = tmp_path / 'a.app'
    app.write_bytes(lunar_app())
    bf.build_install(path, app, 'FM-1_501', tmp_path / 'ok.fwsc', stock_unpack=unpack, profiles=profiles)
    (unpack / 'files/cfg').write_bytes(b'not the same')
    with pytest.raises(ValueError, match='independent unpack differs: files/cfg'):
        bf.build_install(path, app, 'FM-1_501', tmp_path / 'no.fwsc', stock_unpack=unpack, profiles=profiles)


# ---- the verifier rejects every departure, with CRCs repaired ---------------

def _mutations(profile):
    rec, addr = profile['app_record_offset'], profile['app_offset']

    def area(fn):
        return dict(area_edit=fn)

    def grow(a):
        struct.pack_into('<I', a, rec + 8, SLOT + 1)
    return {
        'flash head': dict(flash_edit=lambda f: f.__setitem__(0x100, f[0x100] ^ 1)),
        'not 0xFF': area(lambda a: a.__setitem__(addr + SLOT - 1, 0)),
        'cfg or reserved': area(lambda a: a.__setitem__(0x420, a[0x420] ^ 1)),
        'reserved descriptors': area(lambda a: a.__setitem__(slice(0x60, 0x80),
                                                              jlfs('VM', 0x92000, 0x56000, 0x12, 0))),
        'unreferenced tail': area(lambda a: a.__setitem__(0x1000, 1)),
        'placement or size': area(grow),
        'app record CRC': dict(area_edit=grow, fix_app_record=False),
        'app.bin record placement': area(lambda a: struct.pack_into('<I', a, rec + 4, addr + 1)),
        'entries after flash.bin': dict(log_edit=lambda l: l.__setitem__(len(l) - 20, 1)),
        'between the entry list': dict(log_edit=lambda l: l.__setitem__(0x300, 1)),
    }


@pytest.mark.parametrize('name', ['flash head', 'not 0xFF', 'cfg or reserved', 'reserved descriptors',
                                  'unreferenced tail', 'placement or size', 'app record CRC', 'app.bin record placement',
                                  'entries after flash.bin', 'between the entry list'])
def test_describe_rejects_content_changes_even_with_repaired_crcs(stock, tmp_path, name):
    raw, profile, _, _ = stock
    build(stock, tmp_path)
    pkg = (tmp_path / 'lunar.fwsc').read_bytes()
    edit = _mutations(profile)[name]
    bad = repack(pkg, profile, **edit)
    expected = {'unreferenced tail': 'cfg or reserved', 'reserved descriptors': 'cfg or reserved',
                'app.bin record placement': 'placement or size', 'app record CRC': 'app.bin record CRC',
                'entries after flash.bin': 'entries after flash.bin|entry records'}.get(name, name)
    with pytest.raises(ValueError, match=expected):
        bf.describe_package(bad, profile)


def test_describe_rejects_crc_damage_and_identity_games(stock, tmp_path):
    raw, profile, _, _ = stock
    build(stock, tmp_path)
    pkg = (tmp_path / 'lunar.fwsc').read_bytes()
    assert bf.describe_package(repack(pkg, profile), profile)['kind'] == 'lunar-install'
    damaged = bytearray(pkg)
    damaged[0x400 + 20 + 0x5000] ^= 1          # inside flash.bin, no CRC repair
    with pytest.raises(ValueError, match='CRC'):
        bf.describe_package(bytes(damaged), profile)
    for identity, message in [('FM-1_015', 'neither'), ('FM-1_092', 'neither'), ('FM-1_502', 'exactly once')]:
        with pytest.raises(ValueError, match=message):
            bf.describe_package(bf.set_identity(pkg, identity), profile)
    with pytest.raises(ValueError, match='package is'):
        bf.describe_package(pkg + b'\0', profile)
    assert bf.describe_package(raw, profile)['kind'] == 'stock-rollback'
    with pytest.raises(ValueError, match='foreign identity|neither|exactly once'):
        bf.describe_package(bf.set_identity(raw, 'FM-1_501'), profile)


# ---- roll-back -------------------------------------------------------------

def test_rollback_is_the_stock_package_byte_for_byte(stock, tmp_path):
    raw, profile, profiles, path = stock
    result = bf.build_rollback(path, tmp_path / 'back.fwsc', running='FM-1_501', profiles=profiles)
    assert (tmp_path / 'back.fwsc').read_bytes() == raw
    assert result['manifest']['kind'] == 'stock-rollback' and result['manifest']['app'] is None
    assert result['manifest']['flash']['mutable_ranges'] == []
    with pytest.raises(ValueError, match='same version'):
        bf.build_rollback(path, tmp_path / 'again.fwsc', running='FM-1_015', profiles=profiles)


def test_cli_refuses_without_writing(tmp_path):
    (tmp_path / 'not.fwsc').write_bytes(b'x' * 2000)
    (tmp_path / 'app.bin').write_bytes(lunar_app())
    rc = bf.main(['install', '--stock', str(tmp_path / 'not.fwsc'), '--app', str(tmp_path / 'app.bin'),
                  '--identity', 'FM-1_501', '--out', str(tmp_path / 'out.fwsc')])
    assert rc == 1 and not (tmp_path / 'out.fwsc').exists()
    assert bf.main(['verify', str(tmp_path / 'not.fwsc')]) == 1


# ---- the browser verifier on the builder's output ---------------------------

def _node(*args):
    node = shutil.which('node')
    if not node:
        pytest.skip('node is not installed')
    done = subprocess.run([node, str(CLI), *map(str, args)], capture_output=True, text=True, timeout=120)
    return json.loads(done.stdout)


def test_browser_verifier_admits_exactly_what_the_builder_makes(stock, tmp_path):
    raw, profile, profiles, path = stock
    build(stock, tmp_path)
    bf.build_rollback(path, tmp_path / 'back.fwsc', profiles=profiles)
    (tmp_path / 'profile.json').write_text(json.dumps(profile))
    got = _node(tmp_path / 'lunar.fwsc', '--manifest', tmp_path / 'lunar.fwsc.manifest.json',
                '--profile', tmp_path / 'profile.json')
    assert got['admitted'] and got['kind'] == 'lunar-install' and got['product'] == 'FM-1_501'
    expected = json.loads((tmp_path / 'lunar.fwsc.manifest.json').read_text())
    assert bf.canonical(got['manifest']) == bf.canonical(expected)
    got = _node(tmp_path / 'back.fwsc', '--manifest', tmp_path / 'back.fwsc.manifest.json',
                '--profile', tmp_path / 'profile.json')
    assert got['admitted'] and got['kind'] == 'stock-rollback'
    pkg = (tmp_path / 'lunar.fwsc').read_bytes()
    for name, edit in _mutations(profile).items():
        (tmp_path / 'bad.fwsc').write_bytes(repack(pkg, profile, **edit))
        got = _node(tmp_path / 'bad.fwsc', '--profile', tmp_path / 'profile.json')
        assert not got['admitted'], name
        assert got['reason'].startswith('package admission blocked'), name
    got = _node(tmp_path / 'lunar.fwsc', '--manifest', tmp_path / 'back.fwsc.manifest.json',
                '--profile', tmp_path / 'profile.json')
    assert not got['admitted'] and 'manifest does not match' in got['reason']
    got = _node(tmp_path / 'lunar.fwsc')       # default profile: the real V15 only
    assert not got['admitted']


# ---- opt-in: the real stock V15 ----------------------------------------------

real = pytest.mark.skipif(not REAL, reason='set FM1_STOCK_FWSC to your stock V15 package')


@real
def test_real_v15_profile_round_trip_install_and_rollback(tmp_path):
    raw = pathlib.Path(REAL).read_bytes()
    comps = nested.extract_stock_components(raw)
    assert bf.stock_profile(raw, comps) == bf.V15_PROFILE
    assert bf.assemble(raw, comps['files/app.bin'], 'FM-1_015', bf.V15_PROFILE) == raw
    unpack = os.environ.get('FM1_STOCK_UNPACK')
    app = tmp_path / 'app.bin'
    app.write_bytes(lunar_app(size=100_000))
    result = bf.build_install(REAL, app, 'FM-1_501', tmp_path / 'lunar.fwsc', stock_unpack=unpack)
    assert result['guard']['passed'] and result['manifest']['app']['spare_bytes'] == 581_564 - 100_000
    lo, hi = result['flash_changes']['hull']
    assert 0x4000 <= lo and hi <= 0x920DC
    back = bf.build_rollback(REAL, tmp_path / 'back.fwsc', running='FM-1_501', stock_unpack=unpack)
    assert (tmp_path / 'back.fwsc').read_bytes() == raw
    got = _node(tmp_path / 'lunar.fwsc', '--manifest', tmp_path / 'lunar.fwsc.manifest.json')
    assert got['admitted'] and bf.canonical(got['manifest']) == bf.canonical(result['manifest'])
    got = _node(tmp_path / 'back.fwsc', '--manifest', tmp_path / 'back.fwsc.manifest.json')
    assert got['admitted'] and bf.canonical(got['manifest']) == bf.canonical(back['manifest'])
    too_big = tmp_path / 'big.bin'
    too_big.write_bytes(lunar_app(size=581_565))
    with pytest.raises(ValueError, match='fm1_budget'):
        bf.build_install(REAL, too_big, 'FM-1_501', tmp_path / 'big.fwsc')
