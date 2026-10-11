"""Synthetic raw NOR validation, without vendor binaries or transport."""
import copy
import json
import os
from pathlib import Path
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/jieli'))
import raw_flash_profile as raw  # noqa: E402
from tests.test_inspect_stock_flash import synthetic_decoded, jlfs  # noqa: E402
from tests.test_diagnostic_report import fixture as diagnostic  # noqa: E402


def encode(decoded):
    image = bytearray(decoded)
    for offset in (0, 32, 64, 96, 128):
        image[offset:offset + 32] = raw.header_decode(decoded[offset:offset + 32])
    image[0xA0:0xB0] = raw.header_decode(decoded[0xA0:0xB0])
    image[0xB0:0x38D0] = raw.header_decode(decoded[0xB0:0x38D0])
    image[raw.APP_BASE:raw.PAYLOAD_END] = raw.sfc_decode(decoded[raw.APP_BASE:raw.PAYLOAD_END], 0)
    return bytes(image)


def repair_app(decoded, app):
    decoded[0x4120:0x4120 + len(app)] = app
    struct.pack_into('<H', decoded, 0x4022, raw.crc16(app))
    struct.pack_into('<I', decoded, 0x4028, len(app))
    struct.pack_into('<H', decoded, 0x4020, raw.crc16(decoded[0x4022:0x4040]))
    struct.pack_into('<H', decoded, 0x4002, raw.crc16(decoded[0x4020:raw.CFG_OFFSET]))
    struct.pack_into('<H', decoded, 0x4000, raw.crc16(decoded[0x4002:0x4020]))


@pytest.fixture
def sample(tmp_path, monkeypatch):
    decoded = synthetic_decoded()
    decoded[raw.APP_BASE:] = bytes(raw.FLASH_BYTES - raw.APP_BASE)
    old_app = b'S' * raw.APP_BYTES
    tool, eq = b'T' * 383, b'E' * 2873
    decoded[0x4120:0x4120 + len(old_app)] = old_app
    decoded[raw.CFG_TOOL_OFFSET:raw.CFG_OFFSET] = tool
    children = [jlfs('app.bin', 0x120, len(old_app), 0x82, 0, old_app),
                jlfs('cfg_tool.bin', 692032, len(tool), 0x82, 0, tool)]
    for name in ('VM', 'PRCT', 'BTIF', 'USR'):
        address, size, flags = raw.RESERVED[name]
        children.append(jlfs(name, address, size, flags, int(name == 'USR')))
    decoded[0x4020:0x40E0] = b''.join(children)
    decoded[0x4000:0x4020] = jlfs('app_area_head', 0x02000120, raw.AREA_BYTES, 0x83, 0,
                                decoded[0x4020:raw.CFG_OFFSET])
    c = raw.CFG_OFFSET
    decoded[c + 64:c + raw.CFG_BYTES] = eq
    decoded[c + 32:c + 64] = jlfs('eq_cfg_hw.bin', 64, len(eq), 0x82, 1, eq)
    decoded[c:c + 32] = jlfs('cfg', 32, raw.CFG_BYTES, 0x83, 1, decoded[c + 32:c + raw.CFG_BYTES])
    reference = tmp_path / 'reference'
    (reference / 'top').mkdir(parents=True)
    (reference / 'files').mkdir()
    components = {'top/uboot.boot': decoded[0xA0:0x38D0],
                  'top/isd_config.ini': decoded[0x38D0:0x38D0 + 699],
                  'files/app.bin': old_app, 'files/cfg_tool.bin': tool,
                  'files/cfg-extracted/eq_cfg_hw.bin': eq, 'files/cfg': decoded[c:c + raw.CFG_BYTES]}
    for name, data in components.items():
        (reference / name).parent.mkdir(parents=True, exist_ok=True)
        (reference / name).write_bytes(data)
    baseline = encode(decoded)
    # Substitute only provenance pins for public synthetic bytes; all format,
    # geometry, protected range, CRC, reference and audit checks still execute.
    monkeypatch.setattr(raw, 'STOCK_SPL_SHA256', raw.digest(components['top/uboot.boot']))
    monkeypatch.setattr(raw, 'RECORDED_PAYLOAD_SHA256', raw.digest(baseline[:raw.PAYLOAD_END]))
    manifest = dict(identical=True, flash_bytes=raw.FLASH_BYTES, loader_sha256=raw.LOADER_SHA256,
                    dumps=[dict(file=name, bytes=raw.FLASH_BYTES, sha256=raw.digest(baseline))
                           for name in ('dumpA.bin', 'dumpB.bin')])
    identity = dict(firmware='FM-1_092', unit_id='synthetic-recorded-profile', simulated=False)
    elf, app = diagnostic()
    target_decoded = bytearray(decoded)
    repair_app(target_decoded, app)
    return dict(baseline=baseline, decoded=decoded, target=encode(target_decoded),
                target_decoded=target_decoded, manifest=manifest, identity=identity,
                reference=reference, elf=elf, app=app)


def profile(s, **changes):
    values = dict(baseline_a=s['baseline'], baseline_b=s['baseline'],
                  manifest=s['manifest'], identity=s['identity'], reference=s['reference'])
    values.update(changes)
    return raw.profile_dump(**values)


def validate(s, **changes):
    values = dict(baseline_a=s['baseline'], baseline_b=s['baseline'], target=s['target'],
                  manifest=s['manifest'], identity=s['identity'], reference=s['reference'],
                  app=s['app'], elf=s['elf'])
    values.update(changes)
    return raw.validate_target(**values)


def test_raw_profile_and_target_bind_exact_hashes(sample):
    s = sample
    p, result = profile(s), validate(s)
    assert p['image_base'] == 0 and p['app_image_offset'] == 0x4120
    assert p['reserved']['VM'][:2] == [0xD9000, 0x10000]
    assert p['prct_is_descriptor_not_writable_permission']
    assert result['allowed_sectors'] == [0x4000]
    assert result['writable_ranges'] == [[0x4000, 0x5000]]
    assert result['target_sha256'] == raw.digest(s['target'])
    assert result['baseline_sha256'] == raw.digest(s['baseline'])
    assert result['app_sha256'] == raw.digest(s['app']) and result['elf_sha256'] == raw.digest(s['elf'])
    assert result['profile_sha256'] == p['profile_sha256']
    assert result['protected_raw_bytes_identical'] and result['original_app_tail_identical']
    assert not result['hardware_validated'] and not result['physical_writer_ready'] and not result['binary_emitted']
    assert validate(s) == result


@pytest.mark.parametrize('kind', ['truncated', 'differing', 'manifest_hash', 'manifest_loader',
                                 'manifest_duplicate', 'wrong_identity', 'simulated'])
def test_rejects_backup_and_identity_binding(sample, kind):
    s, changes = sample, {}
    m = copy.deepcopy(s['manifest'])
    if kind == 'truncated':
        changes.update(baseline_a=s['baseline'][:-1], baseline_b=s['baseline'][:-1])
    elif kind == 'differing':
        changes['baseline_b'] = s['baseline'][:-1] + b'!'
    elif kind == 'manifest_hash':
        m['dumps'][0]['sha256'] = '0' * 64
    elif kind == 'manifest_loader':
        m['loader_sha256'] = '0' * 64
    elif kind == 'manifest_duplicate':
        m['dumps'].append(m['dumps'][0])
    elif kind == 'wrong_identity':
        changes['identity'] = dict(s['identity'], firmware='FM-1_015')
    else:
        changes['identity'] = dict(s['identity'], simulated=True)
    changes['manifest'] = m
    with pytest.raises(ValueError):
        profile(s, **changes)


def test_rejects_unsupported_baseline_fingerprint(sample):
    baseline = bytearray(sample['baseline'])
    baseline[0x5000] ^= 1
    with pytest.raises(ValueError, match='manifest'):
        profile(sample, baseline_a=bytes(baseline), baseline_b=bytes(baseline))
    m = copy.deepcopy(sample['manifest'])
    for item in m['dumps']:
        item['sha256'] = raw.digest(baseline)
    with pytest.raises(ValueError, match='fingerprint'):
        profile(sample, baseline_a=bytes(baseline), baseline_b=bytes(baseline), manifest=m)


@pytest.mark.parametrize('offset', [0, 0xA0, 0x38D0, raw.CFG_TOOL_OFFSET,
                                  raw.CFG_OFFSET + 64, 0xAE000, 0xD8000,
                                  0xD9000, 0xEA000, 0xFF000])
def test_rejects_protected_target_bytes(sample, offset):
    changed = bytearray(sample['target'])
    changed[offset] ^= 1
    with pytest.raises(ValueError):
        validate(sample, target=bytes(changed))


@pytest.mark.parametrize('kind', ['entry', 'VM', 'app_tail', 'unknown_gap', 'length', 'crc'])
def test_rejects_repaired_crc_target_layout_and_extra_changes(sample, kind):
    s = sample
    d = bytearray(s['target_decoded'])
    if kind == 'entry':
        d[0x4000:0x4020] = jlfs('app_area_head', 0x02000130, raw.AREA_BYTES, 0x83, 0,
                               d[0x4020:raw.CFG_OFFSET])
    elif kind == 'VM':
        d[0x4060:0x4080] = jlfs('VM', 0x93000, 0x56000, 0x12, 0)
        repair_app(d, s['app'])
    elif kind in ('app_tail', 'unknown_gap'):
        d[0x4120 + len(s['app']) if kind == 'app_tail' else 0x4100] ^= 1
        repair_app(d, s['app'])
    elif kind == 'length':
        repair_app(d, s['app'] + b'!')
    else:
        d[0x4000] ^= 1
    with pytest.raises(ValueError):
        validate(s, target=encode(d))


def test_rejects_ambiguous_header_outside_recorded_payload(sample):
    # Both candidate bases have a valid header CRC; prefix content still binds.
    changed = bytearray(sample['baseline'])
    # 0x80000 is inside the pinned prefix, so call the same independent parser
    # directly to demonstrate ambiguity refusal beyond the fingerprint check.
    head = struct.pack('<H', raw.crc16(bytes(30))) + bytes(30)
    changed[0x80000:0x80020] = raw.header_decode(head)
    with pytest.raises(ValueError, match='ambiguous'):
        raw._parse(bytes(changed), sample['reference'])


def test_rejects_fwsc_coordinates_as_raw_image(sample):
    with pytest.raises(ValueError, match='1 MiB'):
        validate(sample, target=bytes(0x400) + sample['target'])
    shifted = bytes(0x400) + sample['target'][:-0x400]
    with pytest.raises(ValueError):
        validate(sample, target=shifted)


def test_recomputes_audit_and_refuses_unbound_pass_report(sample):
    with pytest.raises(ValueError, match='recomputed audit'):
        validate(sample, expected_audit=dict(passed=True, n_pending=0, runtime='sdk-free'))
    audit = raw.audit([('diagnostic.elf', raw.Elf(sample['elf']))],
                      [('diagnostic.bin', sample['app'])], True, runtime='sdk-free')
    result = validate(sample, expected_audit=audit)
    assert result['link_audit_sha256'] == raw.digest(raw.encoded(audit))
    with pytest.raises(ValueError):
        validate(sample, elf=bytes(64))
    with pytest.raises(ValueError, match='differs'):
        validate(sample, app=sample['app'][:-1] + b'!')


def test_shared_protected_sector_is_rejected(sample, monkeypatch):
    # Conservatively reject a policy boundary inside a changed erase sector,
    # even though final protected bytes still match the baseline.
    original = raw.profile_dump
    def boundary(*args, **kwargs):
        p = original(*args, **kwargs)
        p['protected_ranges'].append([0x4FFF, 0x5000])
        return p
    monkeypatch.setattr(raw, 'profile_dump', boundary)
    with pytest.raises(ValueError, match='crosses protected'):
        validate(sample)


def test_json_only_cli_and_no_overwrite(sample, tmp_path, monkeypatch, capsys):
    s = sample
    files = dict(a=s['baseline'], b=s['baseline'])
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    for name in ('manifest', 'identity'):
        (tmp_path / name).write_text(json.dumps(s[name]))
    output = tmp_path / 'receipt.json'
    argv = ['raw_flash_profile', '--baseline-a', str(tmp_path / 'a'), '--baseline-b', str(tmp_path / 'b'),
            '--manifest', str(tmp_path / 'manifest'), '--identity', str(tmp_path / 'identity'),
            '--reference', str(s['reference']), '--json', str(output)]
    monkeypatch.setattr(sys, 'argv', argv)
    raw.main()
    assert json.loads(output.read_text())['image_base'] == 0
    assert json.loads(capsys.readouterr().out)['binary_emitted'] is False
    with pytest.raises(FileExistsError):
        raw.main()
    monkeypatch.setattr(sys, 'argv', argv + ['--out', str(tmp_path / 'image.bin')])
    with pytest.raises(SystemExit):
        raw.main()
    assert not (tmp_path / 'image.bin').exists()


@pytest.mark.skipif(not os.environ.get('FM1_RAW_PRIVATE'), reason='optional private recorded 092 dumps')
def test_recorded_private_profile_and_in_memory_target():
    root = Path(os.environ['FM1_RAW_PRIVATE'])
    a, b = ((root / 'backup-session1' / name).read_bytes() for name in ('dumpA.bin', 'dumpB.bin'))
    manifest = json.loads((root / 'backup-session1/manifest.json').read_text())
    reference = root / 'FM-1_092.fwsc_unpack'
    identity = dict(firmware='FM-1_092', unit_id='recorded-owner-backup-session1', simulated=False)
    p = raw.profile_dump(a, b, manifest, identity, reference)
    assert p['baseline_sha256'] == '96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4'
    elf, app = diagnostic()
    # Private bytes remain in memory; no candidate is emitted or distributed.
    decoded = bytearray(a)
    decoded[raw.APP_BASE:raw.PAYLOAD_END] = raw.sfc_decode(a[raw.APP_BASE:raw.PAYLOAD_END], 0)
    repair_app(decoded, app)
    target = a[:raw.APP_BASE] + raw.sfc_decode(decoded[raw.APP_BASE:raw.PAYLOAD_END], 0) + a[raw.PAYLOAD_END:]
    result = raw.validate_target(a, b, target, manifest, identity, reference, app, elf)
    assert result['allowed_sectors'] == [0x4000] and not result['binary_emitted']
