"""Closed default and factory identity for the completed-trace restore."""
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "completed_trace_restore_boundary", Path(__file__).resolve().parents[1] / "tools/fm1_completed_stop_trace_restore.py")
restore = importlib.util.module_from_spec(_spec)
import sys
sys.modules[_spec.name] = restore
_spec.loader.exec_module(restore)


def test_restore_closed_before_reading_campaign(tmp_path):
    assert restore.BACKUP_SOURCE_SHA is None
    with pytest.raises(ValueError, match="not frozen"):
        restore.prepare_campaign(tmp_path / "absent.json")
    assert not list(tmp_path.iterdir())


def test_restore_rejects_unregistered_authority():
    with pytest.raises(ValueError, match="factory instance"):
        restore.require_prepared(restore.Prepared(None, None, None))
