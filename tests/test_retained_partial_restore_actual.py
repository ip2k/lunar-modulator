"""Strict disposable Hera proposal; actual RESTORE stops, model device only."""
import pytest
from test_sdk_rehearsal import actual
from retained_partial_restore_fixture import run_genuine_restore_recovery


@pytest.mark.parametrize('fault', ['erase', 'program'])
def test_genuine_caught_restore_dual_partial_stock_restore(actual, tmp_path, monkeypatch, fault):
    state = run_genuine_restore_recovery(actual, tmp_path, monkeypatch, fault)
    assert state.summary['actual_returned_connection_negatives'] == 2
    assert state.summary['acquired_commands'] == 8707
    assert state.summary['final_stock_sha256'] == '96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4'
    assert state.summary['authority_overrides'] is False


def test_genuine_nested_failed_partial_restore_has_no_new_admission(actual, tmp_path, monkeypatch):
    state = run_genuine_restore_recovery(actual, tmp_path, monkeypatch, 'program', nested=True)
    assert state.summary['actual_returned_connection_negatives'] == 2
    assert state.summary['nested_failed_recovery_refused']
    assert state.summary['nested_capture_admitted'] is False
    assert state.summary['stock_baseline_restored'] is False
