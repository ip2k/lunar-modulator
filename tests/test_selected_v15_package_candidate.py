# SPDX-License-Identifier: MIT
"""Synthetic-only composition proof; no vendor bytes, build, service or device."""
from dataclasses import replace
from contextlib import contextmanager
import json
import os
from pathlib import Path
import stat
import struct

import pytest

from tools.installer_service import selected_v15_package_candidate as candidate
from tests.test_installer_selected_trio_profile import evidence, request  # noqa: F401
from tests.test_inspect_stock_flash import synthetic_decoded, encode, jlfs

# These are the same original sibling modules imported by the model/inspectors.
import inspect_fwsc  # noqa: E402
import package_guard  # noqa: E402


CFG_OFFSET = 0x92100


def fix_envelope(image):
    header = bytearray(inspect_fwsc.header_decode(image[:64]))
    count = struct.unpack_from('<H', header, 8)[0]
    for index in range(count):
        start = 64 + index * 80
        record = bytearray(inspect_fwsc.header_decode(image[start:start + 80]))
        kind = struct.unpack_from('<H', record)[0]
        offset, size = struct.unpack_from('<II', record, 8)
        data = bytes(image[offset:offset + size])
        decoded = inspect_fwsc.sfc_decode(data, offset) if kind in inspect_fwsc.ENCRYPTED_TYPES else data
        struct.pack_into('<H', record, 4, inspect_fwsc.crc16(decoded))
        image[start:start + 80] = inspect_fwsc.header_decode(record)
    struct.pack_into('<H', header, 2, inspect_fwsc.crc16(image[64:64 + count * 80]))
    struct.pack_into('<H', header, 0, inspect_fwsc.crc16(header[2:]))
    image[:64] = inspect_fwsc.header_decode(header)


def synthetic_stock():
    """Full V15 sizes/placement, invented content, no copied vendor payload."""
    decoded = synthetic_decoded()
    decoded[0x4000:] = bytes(len(decoded) - 0x4000)
    app = bytearray(candidate.trio.APP_BUDGET)
    app[100:109] = b'FM-1_015\0'
    decoded[0x4120:0x4120 + len(app)] = app
    decoded[0x920dc:0x920de] = b'CF'
    children = [jlfs('app.bin', 0x120, len(app), 0x82, 0, app),
                jlfs('cfg_tool.bin', 0x8e0dc, 2, 0x82, 0, b'CF')]
    for index, name in enumerate(['VM', 'PRCT', 'BTIF', 'USR']):
        address, size, flags = candidate.nested.EXPECTED_RESERVED[name]
        children.append(jlfs(name, address, size, flags, int(index == 3)))
    decoded[0x4020:0x40e0] = b''.join(children)
    decoded[0x4000:0x4020] = jlfs('app_area_head', 0x02000120, CFG_OFFSET - 0x4000,
                                0x83, 0, decoded[0x4020:CFG_OFFSET])
    decoded[CFG_OFFSET + 0x40:CFG_OFFSET + 0x43] = b'EQ!'
    decoded[CFG_OFFSET + 0x20:CFG_OFFSET + 0x40] = jlfs('eq_cfg_hw.bin', 0x40, 3, 0x82, 1, b'EQ!')
    decoded[CFG_OFFSET:CFG_OFFSET + 0x20] = jlfs('cfg', 0x20, 0x80, 0x83, 1,
                                               decoded[CFG_OFFSET + 0x20:CFG_OFFSET + 0x80])
    image = candidate.model.logical(encode(decoded))
    image.extend(bytes(candidate.DONOR_BYTES - 20 - len(image)))
    tail = bytes(48) + b'JLUFW' + bytes(11)
    image[-64:] = tail
    ota = bytes(19969)
    image[0xa5f00:0xa5f00 + len(ota)] = ota
    entries = [(0, 'flash.bin', 0x400, 602112, 602112),
               (2, 'info.log', 0x93400, 0, 0),
               (50, 'USR', 0x93400, 73226, 73248),
               (52, 'isd_config.ini', 0xa5220, 3296, 3296),
               (100, 'ota.bin', 0xa5f00, len(ota), 20000),
               (251, 'script.ver', 0xaad20, 27, 32),
               (161, 'blimit.bin', 0xaad40, 144, 160),
               (255, 'tail.bin', 0xaade0, 64, 64)]
    for index, (kind, name, start, size, allocation) in enumerate(entries):
        record = struct.pack('<HHHHIII44s16s', kind, index, 0, 0, start, size,
                             allocation, bytes(44), name.encode())
        image[64 + index * 80:144 + index * 80] = inspect_fwsc.header_decode(record)
    header = struct.pack('<HIHHI48s', 0, len(image), len(entries), 4, 512, b'AC791N')
    image[:64] = inspect_fwsc.header_decode(bytes(2) + header)
    fix_envelope(image)
    donor = candidate.model.physical(image, encode(decoded))
    references = {'top/uboot.boot': bytes(decoded[0xa0:0x38d0]),
                  'top/isd_config.ini': bytes(decoded[0x38d0:0x38d0 + 699]),
                  'files/app.bin': bytes(app), 'files/cfg_tool.bin': b'CF',
                  'files/cfg': bytes(decoded[CFG_OFFSET:CFG_OFFSET + 0x80]),
                  'files/eq_cfg_hw.bin': b'EQ!', 'ota.bin': ota}
    return donor, references, tail


@pytest.fixture(scope='module')
def invented_stock():
    return synthetic_stock()


@pytest.fixture
def inputs(tmp_path, monkeypatch, evidence, invented_stock):
    receipt, app, elf, trusted = evidence
    donor, references, tail = invented_stock
    # Test-local fixed-hash substitution only. Every original structural reader,
    # CRC check, package_guard comparison and v2 validator remains in use.
    monkeypatch.setattr(candidate, 'DONOR_SHA256', candidate._sha(donor))
    monkeypatch.setattr(candidate, '_COMPONENT_PINS', {
        path: (len(references[path]), candidate._sha(references[path]))
        for path in candidate._COMPONENT_PINS})
    monkeypatch.setattr(candidate.version_contract, 'STOCK_TAIL_SHA256', candidate._sha(tail))
    guard = package_guard.check_package
    def synthetic_guard(package, stock):
        return guard(package, stock, spl_sha256=candidate._sha(references['top/uboot.boot']))
    monkeypatch.setattr(package_guard, 'check_package', synthetic_guard)
    monkeypatch.setattr(inspect_fwsc, 'check_package', synthetic_guard)
    pins = candidate.TrustedV15DonorPins('FM-1_015', len(donor), candidate._sha(donor),
        {name: candidate.ReferencePin(len(value), candidate._sha(value)) for name, value in references.items()},
        'synthetic acquisition; invented bytes', 'synthetic fixture; no protected input')
    root = tmp_path / 'owned-scratch'
    root.mkdir(mode=0o700)
    return dict(request_raw=request(), receipt_raw=json.dumps(receipt).encode(), app=app, elf=elf,
                trusted=trusted, donor_fwsc=donor, donor_reference=references,
                donor_pins=pins, scratch_root=root)


def assert_clean(inputs):
    assert list(inputs['scratch_root'].iterdir()) == []


def test_actual_v2_validator_and_model_preserve_full_synthetic_v15(inputs, monkeypatch, tmp_path):
    original = candidate.model._build
    calls = []
    def observe(raw, stock, app):
        assert stock.parent == inputs['scratch_root']
        assert stat.S_IMODE(stock.stat().st_mode) == 0o700
        assert set(p.relative_to(stock).as_posix() for p in stock.rglob('*') if p.is_file()) == candidate.REFERENCE_PATHS
        assert all(stat.S_IMODE(p.stat().st_mode) == 0o400 for p in stock.rglob('*') if p.is_file())
        calls.append(stock)
        return original(raw, stock, app)
    monkeypatch.setattr(candidate.model, '_build', observe)
    before = dict(inputs['donor_reference'])
    package, report = candidate.compose_selected_v15_candidate(**inputs)
    assert_clean(inputs)
    assert len(calls) == 1 and not calls[0].exists()
    oracle = tmp_path / 'oracle'
    for name, raw in before.items():
        path = oracle / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    assert package == original(inputs['donor_fwsc'], oracle, inputs['app'])
    assert len(package) == candidate.DONOR_BYTES and package != inputs['donor_fwsc']
    assert inputs['donor_reference'] == before
    assert report['identity'] == 'FM-1_015' and report['identity_changed'] is False
    assert report['candidate_returned_in_memory'] is True
    assert report['file_written'] is False and report['transport_used'] is False
    assert 'binary_emitted' not in report
    for key in candidate.trio.DENIED:
        assert report[key] is False and report['validation'][key] is False
    for key in ('packaging_ready', 'updater_acceptance_verified', 'release_candidate',
                'runtime_identity_service_verified'):
        assert report[key] is False
    assert report['candidate_sha256'] == candidate._sha(package)
    verified = report['replacement_check']
    assert verified['binary_emitted'] is False
    assert verified['stock_extent_bytes'] == 581564
    assert verified['preserved_unused_app_tail_bytes'] == 581564 - len(inputs['app'])
    assert verified['resource_and_partition_positions_unchanged'] is True
    assert verified['stock_boot_config_resource_components_unchanged'] is True
    assert verified['auxiliary_and_trailer_bytes_unchanged'] is True
    assert report['donor_version_check']['app_identity_matches_markers'] is True
    # The shortened app may lack the stock literal; the model never invents a
    # runtime identity service or copies that literal into the checked app.
    decoded = inspect_fwsc.sfc_decode(candidate.model.logical(package)[0x4400:0x93400], 0)
    assert decoded[0x120:0x120 + len(inputs['app'])] == inputs['app']


@pytest.mark.parametrize('change', ['app', 'elf', 'object', 'prepared', 'source', 'toolchain', 'headers', 'admission', 'request', 'identity_request', 'return_request', 'trust'])
def test_invalid_v2_trust_refuses_before_donor_processing(inputs, monkeypatch, change):
    def forbidden(*args, **kwargs):
        pytest.fail('invalid evidence reached donor processing')
    monkeypatch.setattr(candidate, '_donor_inputs', forbidden)
    if change in ('app', 'elf'):
        inputs[change] += b'changed'
    elif change in ('admission', 'request', 'identity_request', 'return_request'):
        name = 'receipt_raw' if change == 'admission' else 'request_raw'
        value = json.loads(inputs[name])
        key, new_value = {'admission': ('hardware_admitted', True),
                          'request': ('flash_layout', 'expanded-d7000'),
                          'identity_request': ('application_identity', 'FM-1_999'),
                          'return_request': ('rom_return', True)}[change]
        value[key] = new_value
        inputs[name] = json.dumps(value).encode()
    elif change == 'trust':
        inputs['trusted'] = None
    else:
        names = dict(object='objects', prepared='prepared_files', source='source_manifest',
                     toolchain='toolchain_binding', headers='cxx_headers_manifest')
        name = names[change]
        values = dict(getattr(inputs['trusted'], name))
        key = next(iter(values))
        values[key] = b'changed' if change in ('object', 'prepared') else '0' * 64
        inputs['trusted'] = replace(inputs['trusted'], **{name: values})
    with pytest.raises(ValueError):
        candidate.compose_selected_v15_candidate(**inputs)
    assert_clean(inputs)


@pytest.mark.parametrize('change', ['raw_hash', 'raw_valid_crc', 'raw_size', 'pin', 'pin_identity', 'missing_pin', 'record', 'missing', 'extra', 'mutable', 'reference_hash', 'fixed_spl', 'config_size', 'per_file', 'aggregate'])
def test_donor_refusals_precede_decoding_and_materialization(inputs, monkeypatch, change):
    def forbidden(*args, **kwargs):
        pytest.fail('invalid donor reached decoder')
    monkeypatch.setattr(candidate.nested, 'inspect_nested', forbidden)
    references = dict(inputs['donor_reference'])
    pins = inputs['donor_pins']
    if change == 'raw_hash':
        inputs['donor_fwsc'] = bytes([inputs['donor_fwsc'][0] ^ 1]) + inputs['donor_fwsc'][1:]
    elif change == 'raw_valid_crc':
        image = candidate.model.logical(inputs['donor_fwsc'])
        image[0xa5f00 + 19969] ^= 1
        fix_envelope(image)
        inputs['donor_fwsc'] = candidate.model.physical(image, inputs['donor_fwsc'])
    elif change == 'raw_size':
        inputs['donor_fwsc'] += b'x'
    elif change == 'pin':
        inputs['donor_pins'] = replace(pins, sha256='0' * 64)
    elif change == 'pin_identity':
        inputs['donor_pins'] = replace(pins, identity='FM-1_092')
    elif change == 'missing_pin':
        inputs['donor_pins'] = replace(pins, references={})
    elif change == 'record':
        inputs['donor_pins'] = replace(pins, authorization_record='')
    elif change == 'missing':
        references.pop('ota.bin')
    elif change == 'extra':
        references['foreign.boot'] = b'x'
    elif change == 'mutable':
        references['ota.bin'] = bytearray(references['ota.bin'])
    elif change == 'reference_hash':
        references['ota.bin'] += b'x'
    elif change in ('fixed_spl', 'config_size'):
        name = 'top/uboot.boot' if change == 'fixed_spl' else 'top/isd_config.ini'
        references[name] += b'x'
        manifest = dict(pins.references)
        manifest[name] = candidate.ReferencePin(len(references[name]), candidate._sha(references[name]))
        inputs['donor_pins'] = replace(pins, references=manifest)
    else:
        name = 'files/cfg'
        references[name] = bytes(candidate.MAX_REFERENCE_FILE_BYTES + (1 if change == 'per_file' else 0))
        if change == 'aggregate':
            references['files/cfg_tool.bin'] = bytes(candidate.MAX_REFERENCE_FILE_BYTES)
        manifest = {name: candidate.ReferencePin(len(raw), candidate._sha(raw)) for name, raw in references.items()}
        inputs['donor_pins'] = replace(pins, references=manifest)
    inputs['donor_reference'] = references
    with pytest.raises(ValueError):
        candidate.compose_selected_v15_candidate(**inputs)
    assert_clean(inputs)


@pytest.mark.parametrize('kind', ['shared', 'symlink'])
def test_scratch_root_refuses_shared_or_aliased_directory(inputs, tmp_path, kind):
    if kind == 'shared':
        inputs['scratch_root'].chmod(0o750)
    else:
        alias = tmp_path / 'alias'
        alias.symlink_to(inputs['scratch_root'], target_is_directory=True)
        inputs['scratch_root'] = alias
    with pytest.raises(ValueError, match='scratch root'):
        candidate.compose_selected_v15_candidate(**inputs)
    assert_clean(inputs)


@pytest.mark.parametrize('phase', ['write', 'build', 'verify', 'cleanup'])
def test_failure_cleans_owned_references_without_final_output(inputs, monkeypatch, phase):
    untouched = inputs['scratch_root'] / 'operator-record'
    untouched.write_bytes(b'keep')
    def fail(*args, **kwargs):
        raise OSError('injected ' + phase)
    if phase == 'cleanup':
        original = candidate.tempfile.TemporaryDirectory
        @contextmanager
        def fail_cleanup(*args, **kwargs):
            with original(*args, **kwargs) as temporary:
                yield temporary
            fail()
        monkeypatch.setattr(candidate.tempfile, 'TemporaryDirectory', fail_cleanup)
    elif phase == 'write':
        real_open = os.open
        def fail_open(path, *args, **kwargs):
            if Path(path).name == 'ota.bin':
                return fail()
            return real_open(path, *args, **kwargs)
        monkeypatch.setattr(candidate.os, 'open', fail_open)
    else:
        monkeypatch.setattr(candidate.model, '_build' if phase == 'build' else 'verify_replacement', fail)
    with pytest.raises(OSError, match='injected'):
        candidate.compose_selected_v15_candidate(**inputs)
    assert list(inputs['scratch_root'].iterdir()) == [untouched]
    assert untouched.read_bytes() == b'keep'


@pytest.mark.parametrize('app', [b'', bytes(581564), bytes(581565)])
def test_original_extent_bounds_without_claiming_random_bytes_are_valid_v2(inputs, tmp_path, app):
    stock = tmp_path / 'model-reference'
    for name, raw in inputs['donor_reference'].items():
        dest = stock / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
    if len(app) == 581564:
        package = candidate.model._build(inputs['donor_fwsc'], stock, app)
        assert candidate.model.verify_replacement(inputs['donor_fwsc'], package, stock, app)['replacement_bytes'] == len(app)
    else:
        with pytest.raises(ValueError, match='original app extent'):
            candidate.model._build(inputs['donor_fwsc'], stock, app)
    assert_clean(inputs)


@pytest.mark.parametrize('damage', ['unused_tail', 'resource', 'cfg', 'partition', 'placement', 'spl', 'config', 'ota', 'tail', 'metadata', 'identity', 'allocation', 'padding'])
def test_crc_repaired_candidate_damage_cannot_bypass_original_verifier(inputs, monkeypatch, damage):
    original = candidate.model._build
    def damaged(raw, stock, app):
        good = original(raw, stock, app)
        image = candidate.model.logical(good)
        if damage in ('unused_tail', 'resource', 'cfg', 'partition', 'placement'):
            decoded = bytearray(inspect_fwsc.sfc_decode(image[0x4400:0x93400], 0))
            if damage == 'unused_tail':
                decoded[0x120 + len(app)] ^= 1
            elif damage == 'resource':
                decoded[0x8e0dc] ^= 1
                decoded[0x40:0x60] = jlfs('cfg_tool.bin', 0x8e0dc, 2, 0x82, 0, decoded[0x8e0dc:0x8e0de])
            elif damage == 'cfg':
                start = CFG_OFFSET - 0x4000
                decoded[start + 0x40] ^= 1
                decoded[start + 0x20:start + 0x40] = jlfs('eq_cfg_hw.bin', 0x40, 3, 0x82, 1,
                    decoded[start + 0x40:start + 0x43])
                decoded[start:start + 0x20] = jlfs('cfg', 0x20, 0x80, 0x83, 1,
                    decoded[start + 0x20:start + 0x80])
            elif damage == 'partition':
                decoded[0x60:0x80] = jlfs('VM', 0x92000, 0x56000, 0x12, 0)
            else:
                decoded[0x130:0x130 + len(app)] = app
                decoded[0x20:0x40] = jlfs('app.bin', 0x130, len(app), 0x82, 0, app)
            decoded[:32] = jlfs('app_area_head', 0x02000120, CFG_OFFSET - 0x4000, 0x83, 0,
                                decoded[32:CFG_OFFSET - 0x4000])
            image[0x4400:0x93400] = inspect_fwsc.sfc_decode(decoded, 0)
        elif damage in ('spl', 'config'):
            # Rebuild every nested checksum involved, not just the outer CRC.
            flash = bytearray(image[0x400:0x93400])
            if damage == 'spl':
                data = bytearray(inspect_fwsc.header_decode(flash[0xa0:0xb0])
                                 + inspect_fwsc.header_decode(flash[0xb0:0x38d0]))
                data[16] ^= 1
                struct.pack_into('<H', data, 12, inspect_fwsc.crc16(data[16:]))
                struct.pack_into('<H', data, 14, inspect_fwsc.crc16(data[:14]))
                flash[0xa0:0xb0] = inspect_fwsc.header_decode(data[:16])
                flash[0xb0:0x38d0] = inspect_fwsc.header_decode(data[16:])
                flash[0x20:0x40] = inspect_fwsc.header_decode(jlfs('uboot.boot', 0xa0, len(data), 0, 0, data))
            else:
                flash[0x38d0 + 698] ^= 1
                data = flash[0x38d0:0x38d0 + 699]
                flash[0x40:0x60] = inspect_fwsc.header_decode(jlfs('isd_config.ini', 0x38d0, 699, 2, 0, data))
            image[0x400:0x93400] = flash
        elif damage == 'ota':
            image[0xa5f00] ^= 1
        elif damage == 'tail':
            image[-64] ^= 1
        elif damage == 'allocation':
            offset = 64 + 4 * 80  # OTA allocation can shrink one byte without overlap.
            record = bytearray(inspect_fwsc.header_decode(image[offset:offset + 80]))
            struct.pack_into('<I', record, 16, 19999)
            image[offset:offset + 80] = inspect_fwsc.header_decode(record)
        elif damage == 'padding':
            image[0xa5f00 + 19969] ^= 1
        elif damage == 'metadata':
            header = bytearray(inspect_fwsc.header_decode(image[:64]))
            struct.pack_into('<I', header, 12, 513)
            image[:64] = inspect_fwsc.header_decode(header)
        fix_envelope(image)
        result = candidate.model.physical(image, good)
        if damage == 'identity':
            result = bytearray(result)
            result[7 * 48 + 47] = ord('6') + 8
            result = bytes(result)
        # Every candidate still has a valid outer checksum envelope. In the
        # unused-tail case even all nested binding/CRC checks pass, so only
        # the independent original-to-candidate byte mask can catch the loss.
        inspect_fwsc.inspect(result)
        if damage == 'unused_tail':
            candidate.nested._inspect_app_replacement(result, stock, app)
        elif damage in ('resource', 'cfg', 'spl', 'config'):
            with pytest.raises(ValueError, match='guarded decoded component differs'):
                candidate.nested._inspect_app_replacement(result, stock, app)
        return result
    monkeypatch.setattr(candidate.model, '_build', damaged)
    with pytest.raises(ValueError):
        candidate.compose_selected_v15_candidate(**inputs)
    assert_clean(inputs)


def test_legacy_d7000_packagers_still_refuse_v2(inputs):
    from tools.installer_service import private_package_candidate as legacy
    import trusted_fwsc_package
    with pytest.raises(ValueError):
        legacy._validate_request(inputs['request_raw'])
    tuple_raw = b'{"schema":2,"profile_id":"sdk-free-selected-trio-offline-diagnostic-v1"}'
    with pytest.raises(ValueError):
        trusted_fwsc_package._validate_tuple(tuple_raw, candidate._sha(tuple_raw))
