"""Strict Hera actual-file composition; requires reviewed literal dependencies."""
import pytest
from test_sdk_rehearsal import actual
from retained_partial_fixture import genuine_partial_recovery

@pytest.mark.parametrize('fault',['erase','program'])
def test_genuine_caught_install_dual_partial_stock_restore(actual,tmp_path,monkeypatch,fault):
    state=genuine_partial_recovery(actual,tmp_path,monkeypatch,fault)
    assert state.summary['acquired_commands']==8707
    assert state.summary['final_stock_sha256']=='96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4'
    assert state.summary['authority_overrides'] is False
