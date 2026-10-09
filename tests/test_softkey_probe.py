"""The boot-mode probe cannot send arbitrary messages or trust a stale identity."""
import importlib.util
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location('softkey_probe', TOOLS / 'fm1_softkey_probe.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def test_known_checksum_exception_is_exact_and_explicit():
    with pytest.raises(ValueError):
        p.checked_identity(p.KNOWN_092, 'FM-1_092')
    reply, info = p.checked_identity(p.KNOWN_092, 'FM-1_092', True)
    assert reply == p.KNOWN_092 and info['checksum_ok'] is False
    altered = bytearray(p.KNOWN_092)
    altered[-2] ^= 1
    with pytest.raises(ValueError):
        p.checked_identity(altered, 'FM-1_092', True)
    with pytest.raises(ValueError):
        p.checked_identity(p.KNOWN_092, 'FM-1_015', True)


def test_truncated_or_interrupted_identity_is_not_accepted():
    for raw in (p.KNOWN_092[:-1], b'noise', b'\xf0\x00\x90\xf7'):
        with pytest.raises(ValueError):
            p.checked_identity(raw, 'FM-1_092', True)
    # Real-time messages are legal inside MIDI SysEx.
    assert p.checked_identity(p.KNOWN_092[:10]+b'\xf8'+p.KNOWN_092[10:], 'FM-1_092', True)[0] == p.KNOWN_092


def test_upgrade_and_arbitrary_sysex_never_reach_device(monkeypatch):
    write = Mock()
    monkeypatch.setattr(p.os, 'write', write)
    for message in (bytes.fromhex('F0 22 24 35 7F F7'), b'\xf0\x35\x59\xf7', b''):
        with pytest.raises(ValueError):
            p.write_message(42, message)
    write.assert_not_called()


def test_partial_softkey_write_has_no_retry(monkeypatch):
    write = Mock(return_value=3)
    monkeypatch.setattr(p.os, 'write', write)
    with pytest.raises(OSError):
        p.write_message(42, p.SOFT_KEY)
    assert write.call_count == 1


def test_identity_timeout_never_sends_softkey(monkeypatch):
    monkeypatch.setattr(p, 'usb_parent', lambda _: Path('/usb3/3-2'))
    monkeypatch.setattr(p, 'enumerate_usb', lambda: [])
    monkeypatch.setattr(p.os, 'open', lambda *a: 42)
    monkeypatch.setattr(p.os, 'close', lambda *a: None)
    monkeypatch.setattr(p.select, 'select', lambda *a: ([], [], []))
    send = Mock()
    monkeypatch.setattr(p, 'write_message', send)
    with pytest.raises(ValueError):
        p.probe('/dev/snd/midiC2D0', 'FM-1_092', True, Mock(), timeout=0.001)
    send.assert_called_once_with(42, p.IDENTITY)


def test_unvetted_softkey_identity_refused_before_open(monkeypatch):
    open_device = Mock()
    monkeypatch.setattr(p.os, 'open', open_device)
    with pytest.raises(ValueError):
        p.probe('/dev/snd/midiC2D0', 'FM-1_096', True, Mock())
    open_device.assert_not_called()
