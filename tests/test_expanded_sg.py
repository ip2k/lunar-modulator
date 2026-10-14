"""Budget regression checks; no actual SG handle is opened."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from native import expanded_sg as sg


def test_reviewed_transport_class_body_unchanged():
    original = Path(sg.__file__).resolve().parents[1] / 'fm1_sdk_rehearsal.py'
    text = original.read_text()
    start = text.index('class RehearsalSG:')
    block = text[start:text.index('\ndef run_campaign(', start)]
    expanded = Path(sg.__file__).read_text()
    assert expanded[expanded.index('class RehearsalSG:'):] == block


def transport(attempts):
    result = object.__new__(sg.RehearsalSG)
    result.attempts = attempts
    result.binding = lambda: {}
    result.validate_wire = lambda *args: None
    result.failed = False
    result.fd = 7
    result.close = Mock()
    result.log = lambda *args, **kwargs: None
    result.policy = SimpleNamespace(direction='install')
    def header(**fields):
        return SimpleNamespace(**fields, status=0, masked=0, msg=0, host=0,
                               driver=0, resid=0, info=0, sense_len=0)
    result.prepared = SimpleNamespace(header_type=header)
    return result


def test_old_limit_no_longer_stops_an_expanded_transaction(monkeypatch):
    ioctl = Mock()
    monkeypatch.setattr(sg.fcntl, 'ioctl', ioctl)
    t = transport(20000)
    cdb = (b'\xfd\x05' + b'\0' * 6).ljust(16, b'\xff')
    assert t.exchange(cdb, in_size=256) == b'\0' * 256
    assert t.attempts == 20001 and ioctl.call_count == 1
    t.close.assert_not_called()


def test_expanded_limit_still_stops_before_ioctl(monkeypatch):
    ioctl = Mock()
    monkeypatch.setattr(sg.fcntl, 'ioctl', ioctl)
    t = transport(sg.COMMAND_LIMIT)
    with pytest.raises(ValueError, match='command limit'):
        t.exchange(b'\xff' * 16)
    assert t.failed and t.attempts == sg.COMMAND_LIMIT
    ioctl.assert_not_called()
    t.close.assert_called_once()


def test_limit_covers_worst_case_and_time_bounded_read_heartbeats():
    # Two whole-flash reads, three per-sector reads, and full nonblank pages.
    reads = 2 * (1048576 // 256) + 3 * 16 * 213
    mutation_and_queries = 2 * (1 + 16) * 213
    heartbeats = sg.LIVE_SECONDS // 0.5
    assert reads + mutation_and_queries > 20000
    assert reads + mutation_and_queries + heartbeats + 1 < sg.COMMAND_LIMIT
