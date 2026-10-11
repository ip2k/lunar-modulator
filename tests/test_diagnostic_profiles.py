"""Explicit profile propagation through real layout and package guards, synthetic only."""
import hashlib
import importlib.util
import json
import pathlib
import sys

import pytest

from tests.test_diagnostic_report import fixture
from tests.test_model_app_replacement import source, fix_envelope
from tests.test_inspect_stock_flash import jlfs

TOOLS = pathlib.Path(__file__).resolve().parents[1] / 'tools/jieli'
sys.path.insert(0, str(TOOLS))
import inspect_fwsc as outer
import model_app_replacement as model
from package_guard import check_package


@pytest.fixture
def inputs(source, tmp_path, monkeypatch):
    raw, stock = source
    # Fit the eight-byte synthetic linked image in the original allocation.
    image = model.logical(raw)
    decoded = bytearray(outer.sfc_decode(image[0x4400:0x93400], 0))
    decoded[0x120:0x128] = b'CODEMORE'
    decoded[32:64] = jlfs('app.bin', 0x120, 8, 0x82, 0, b'CODEMORE')
    decoded[:32] = jlfs('app_area_head', 0x02000120, 0x400, 0x83, 0, decoded[32:0x400])
    image[0x4400:0x93400] = outer.sfc_decode(decoded, 0)
    fix_envelope(image)
    raw = model.physical(image, raw)
    (stock / 'files/app.bin').write_bytes(b'CODEMORE')
    spec = importlib.util.spec_from_file_location('stage_diagnostic_profiles', TOOLS / 'stage-diagnostic.py')
    staging = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(staging)
    # Pin only this synthetic SPL; all actual tree guards still run unchanged.
    pin = hashlib.sha256((stock / 'top/uboot.boot').read_bytes()).hexdigest()
    monkeypatch.setattr(staging, 'check_package',
                        lambda package, reference: check_package(package, reference, spl_sha256=pin))
    return raw, stock, staging


def artifacts(tmp_path, *, handover=True, boundary_changes=None):
    elf, app = fixture(handover=handover, boundary_changes=boundary_changes)
    elf_path, app_path = tmp_path / 'diagnostic.elf', tmp_path / 'diagnostic.bin'
    elf_path.write_bytes(elf)
    app_path.write_bytes(app)
    return elf, app, elf_path, app_path


@pytest.mark.parametrize('profile', ['inert', 'handover', 'panel-protocol'])
def test_explicit_profile_preserves_layout_stock_guards_and_no_package(inputs, tmp_path, profile):
    raw, stock, staging = inputs
    elf, app, elf_path, app_path = artifacts(tmp_path, handover=profile != 'inert')
    result = model.model(raw, stock, elf, app, profile=profile)
    staged = staging.stage(stock, elf_path, app_path, tmp_path / 'stage', profile=profile)
    layout = 'inert' if profile == 'inert' else 'handover'
    for data, key in [(result, 'diagnostic_layout'), (staged, 'layout')]:
        assert data['profile'] == profile and data[key]['profile'] == layout
        assert data[key]['ssp_stack_bytes'] == (0 if profile == 'inert' else 4096)
        assert data['device_execution'] == 'unverified'
    assert not result['packaging_ready'] and not result['binary_emitted']
    assert not staged['package_created'] and staged['package_guard']['passed']
    for path in ('top/uboot.boot', 'top/isd_config.ini', 'ota.bin', 'files/cfg'):
        assert (tmp_path / 'stage' / path).read_bytes() == (stock / path).read_bytes()
    assert (tmp_path / 'stage/files/app.bin').read_bytes() == app
    assert json.loads((tmp_path / 'stage/staging-manifest.json').read_text()) == staged


def test_defaults_reject_supervisor_layout_before_output(inputs, tmp_path):
    raw, stock, staging = inputs
    elf, app, elf_path, app_path = artifacts(tmp_path)
    with pytest.raises(ValueError, match='unexpected allocated'):
        model.model(raw, stock, elf, app)
    with pytest.raises(ValueError, match='unexpected allocated'):
        staging.stage(stock, elf_path, app_path, tmp_path / 'stage')
    assert not (tmp_path / 'stage').exists()


@pytest.mark.parametrize('profile', ['handover', 'panel-protocol'])
@pytest.mark.parametrize('damage,message', [('missing', 'boundary'), ('overlap', 'SSP'), ('flat', 'differs')])
def test_explicit_profiles_cannot_bypass_layout_guards(inputs, tmp_path, profile, damage, message):
    raw, stock, staging = inputs
    elf, app, elf_path, app_path = artifacts(
        tmp_path, handover=damage != 'missing',
        boundary_changes={'__ssp_guard': 0x01C02020} if damage == 'overlap' else None)
    if damage == 'flat':
        app = app[:-1] + b'!'
        app_path.write_bytes(app)
    with pytest.raises(ValueError, match=message):
        model.model(raw, stock, elf, app, profile=profile)
    with pytest.raises(ValueError, match=message):
        staging.stage(stock, elf_path, app_path, tmp_path / 'stage', profile=profile)
    assert not (tmp_path / 'stage').exists()
    assert not list(tmp_path.glob('.diagnostic-stage-*'))


@pytest.mark.parametrize('profile', ['handover', 'panel-protocol'])
def test_explicit_profiles_do_not_bypass_stock_reference(inputs, tmp_path, profile):
    _raw, stock, staging = inputs
    _elf, _app, elf_path, app_path = artifacts(tmp_path)
    (stock / 'top/uboot.boot').write_bytes(b'wrong SPL')
    with pytest.raises(ValueError, match='stock reference'):
        staging.stage(stock, elf_path, app_path, tmp_path / 'stage', profile=profile)
    assert not (tmp_path / 'stage').exists()


def test_unknown_profiles_reject_before_inputs_or_output(inputs, tmp_path):
    raw, stock, staging = inputs
    with pytest.raises(ValueError, match='unknown diagnostic profile'):
        model.model(raw, stock, b'', b'', profile='visible')
    with pytest.raises(ValueError, match='unknown diagnostic profile'):
        staging.stage(stock, 'missing', 'missing', tmp_path / 'stage', profile='visible')
    assert not (tmp_path / 'stage').exists()


@pytest.mark.parametrize('profile', ['handover', 'panel-protocol'])
def test_clis_forward_explicit_profile_and_only_json_or_staged_tree(inputs, tmp_path, monkeypatch, profile):
    raw, stock, staging = inputs
    _elf, _app, elf_path, app_path = artifacts(tmp_path)
    fwsc = tmp_path / 'input.fwsc'
    fwsc.write_bytes(raw)
    report_path = tmp_path / 'model.json'
    monkeypatch.setattr(sys, 'argv', ['model_app_replacement', str(fwsc), '--stock', str(stock),
                        '--elf', str(elf_path), '--app', str(app_path), '--json', str(report_path),
                        '--profile', profile])
    model.main()
    result = json.loads(report_path.read_text())
    assert result['profile'] == profile and not result['binary_emitted']
    assert sorted(tmp_path.glob('*.fwsc')) == [fwsc]
    monkeypatch.setattr(sys, 'argv', ['stage-diagnostic', '--stock', str(stock),
                        '--elf', str(elf_path), '--app', str(app_path), '--out', str(tmp_path / 'stage'),
                        '--profile', profile])
    assert staging.main() == 0
    assert json.loads((tmp_path / 'stage/staging-manifest.json').read_text())['profile'] == profile
