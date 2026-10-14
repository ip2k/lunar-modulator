"""Mock ioctl regression for expected detach, status failure and one-use reset."""
import ctypes as C
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import fm1_uboot_read as reader
from native import event120_reset as module


@pytest.mark.parametrize('fault', [None, 'status', 'exception', 'partial_reply'])
def test_reset_completion_survives_expected_detach(monkeypatch, fault):
    transport = object.__new__(module.CompletionFirstReset)
    events, calls = [], []
    transport.prepared = SimpleNamespace(check=lambda: None, header_type=reader.SGHeader)
    transport.consumed = transport.failed = False
    transport.fd, transport.ioctl_attempts, transport.phase = 42, 0, 'installed'
    transport.log = lambda event, **fields: events.append((event, fields))
    detached = False
    def binding():
        assert not detached, 'Must not recheck disappearing USB after reset ioctl'
    transport.binding = binding
    def close():
        transport.fd = None
    transport.close = close
    def ioctl(fd, request, h):
        nonlocal detached
        calls.append((fd, request))
        detached = True
        if fault == 'exception':
            raise OSError('USB detached before completion')
        if fault == 'partial_reply':
            # Actual Event120 bench completion: disconnected before reply data.
            h.host, h.resid, h.info = 7, 16, 1
            return
        C.memmove(h.data, module.reset.RESET_CDB, 16)
        if fault == 'status':
            h.host = 1
    monkeypatch.setattr(module.fcntl, 'ioctl', ioctl)
    if fault:
        with pytest.raises(OSError):
            transport.request_reset()
    else:
        result = transport.request_reset()
        assert result['request_completion'] and not result['boot_observed']
    assert transport.fd is None and transport.ioctl_attempts == 1
    assert len(calls) == 1 and events[0][0] == 'reset_submit_intent'
    assert len(events) == (1 if fault == 'exception' else 2)
    if fault == 'partial_reply':
        assert events[1][0] == 'reset_sg_completion'
        assert events[1][1]['host'] == 7
        assert events[1][1]['resid'] == 16
        assert events[1][1]['info'] == 1
        assert transport.failed and transport.phase == 'reset-ambiguous-closed'
    with pytest.raises(ValueError):
        transport.request_reset()
    assert len(calls) == 1
