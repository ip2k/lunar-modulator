"""Synthetic contract checks plus opt-in real stock validation; no vendor fixture."""
import hashlib
import os
from pathlib import Path

import pytest

from tests.test_inspect_fwsc import envelope
from inspect_fwsc import inspect
import inspect_version_contract as contract


def synthetic(monkeypatch, mutate=None):
    # The synthetic trailer stands in for opaque observed bytes, not their meaning.
    monkeypatch.setattr(contract, 'STOCK_TAIL_SHA256', hashlib.sha256(bytes(48) + b'JLUFW' + bytes(11)).hexdigest())
    raw = envelope(mutate)
    return raw, inspect(raw)


def test_evidence_never_asserts_acceptance(monkeypatch):
    raw, outer = synthetic(monkeypatch)
    result = contract._fields(raw, outer, b'CODEFM-1_015\0')
    assert result['decimal_version'] == 15 and result['app_identity_offset'] == 4
    assert result['tail_semantics'].startswith('opaque')
    assert not result['packaging_ready'] and not result['binary_emitted']
    assert result['device_acceptance'] == 'unverified'


@pytest.mark.parametrize('app', [b'FM-1_015', b'FM-1_016\0', b'FM-1_0150\0',
                               b'FM-1_015\0FM-1_015\0', b'FM-1_015\0FM-1_092\0', b'CODE'])
def test_rejects_absent_mismatching_ambiguous_app_identity(monkeypatch, app):
    raw, outer = synthetic(monkeypatch)
    with pytest.raises(ValueError, match='app identity'):
        contract._fields(raw, outer, app)


def test_crc_valid_trailer_profile_change_is_rejected(monkeypatch):
    def mutate(index, fields):
        if index == 3:
            fields[3] = 1  # Repaired outer list/header CRCs do not authorize metadata.
    raw, outer = synthetic(monkeypatch, mutate)
    with pytest.raises(ValueError, match='trailer record'):
        contract._fields(raw, outer, b'FM-1_015\0')


def test_valid_crc_opaque_tail_and_metadata_do_not_establish_contract(monkeypatch):
    raw, outer = synthetic(monkeypatch)
    monkeypatch.setattr(contract, 'STOCK_TAIL_SHA256', '0' * 64)
    with pytest.raises(ValueError, match='trailer bytes'):
        contract._fields(raw, outer, b'FM-1_015\0')
    outer['unknown_header_fields'] = [5, 512]
    with pytest.raises(ValueError, match='metadata'):
        contract._fields(raw, outer, b'FM-1_015\0')


@pytest.mark.skipif(not os.environ.get('FM1_STOCK_FWSC') or not os.environ.get('FM1_STOCK_UNPACK'),
                    reason='optional real stock identity/trailer profile')
def test_actual_stock_contract():
    result = contract.inspect_contract(Path(os.environ['FM1_STOCK_FWSC']).read_bytes(),
                                       Path(os.environ['FM1_STOCK_UNPACK']))
    assert result['identity'] == 'FM-1_015'
    assert result['app_identity_offset'] == 0x4ea64
    assert result['tail_sha256'] == contract.STOCK_TAIL_SHA256
