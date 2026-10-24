"""Offline reset policy tests; no vendor bytes and no hardware access."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import devkit_loader_reset as reset


def test_reset_inventory_is_one_shot_and_read_only():
    r = object.__new__(reset.ResetReader)
    r.phase = 'loader'
    for op in range(65536):
        if op in (0xFD05, 0xFC0A, 0xFC0C):
            continue
        with pytest.raises(ValueError):
            r.build_request(op, 0, b'')
    for phase, address, payload in [('rom', 0, b''), ('loader', 1, b''),
                                     ('loader', 0, b'x')]:
        r.phase = phase
        with pytest.raises(ValueError):
            r.build_request(0xFC0C, address, payload)
    r.phase = 'loader'
    assert r.build_request(0xFC0C, 0, b'') == (reset.RESET_CDB, b'', 16)
    with pytest.raises(ValueError):
        r.build_request(0xFC0C, 0, b'')


def test_installation_receipt_and_full_readback_required(tmp_path, monkeypatch):
    data = bytes(reset.tx.backup.FLASH_SIZE)
    with pytest.raises(ValueError, match='reviewed'):
        reset.verify_transaction(tmp_path, data)
    monkeypatch.setattr(reset.tx, 'IMAGE_PLANS', {reset.tx.digest(data): ()})
    receipt = dict(mode='install', full_flash_verified=True, reset_sent=False,
                   after=dict(file='after.bin', sha256=reset.tx.digest(data), bytes=len(data)))
    (tmp_path/'receipt.json').write_text(json.dumps(receipt))
    (tmp_path/'after.bin').write_bytes(data)
    reset.verify_transaction(tmp_path, data)
    (tmp_path/'after.bin').write_bytes(data[:-1]+b'X')
    with pytest.raises(ValueError, match='readback'):
        reset.verify_transaction(tmp_path, data)
    (tmp_path/'after.bin').write_bytes(data)
    for key, bad in [('mode', 'restore'), ('full_flash_verified', False), ('reset_sent', True)]:
        wrong = {**receipt, key: bad}
        (tmp_path/'receipt.json').write_text(json.dumps(wrong))
        with pytest.raises(ValueError):
            reset.verify_transaction(tmp_path, data)


@pytest.mark.parametrize('fault', [None, 'wrong_flash', 'wrong_jedec', 'disconnect', 'bad_reply'])
def test_live_readback_precedes_one_request_and_never_retries(tmp_path, fault):
    class Reader:
        calls = []
        def online(self):
            return (3, 0) if fault == 'wrong_jedec' else (3, 0x5e4017)
        def dump(self, path):
            self.calls.append('read')
            path.write_bytes(b'bad' if fault == 'wrong_flash' else b'expected')
        def log(self, *args, **kwargs): pass
        def cmd(self, op):
            self.calls.append(op)
            if fault == 'disconnect': raise OSError('USB reset disconnect')
            if fault == 'bad_reply': raise ValueError('No echo')
    r = Reader()
    if fault in ('wrong_flash', 'wrong_jedec'):
        with pytest.raises(ValueError):
            reset.reset_verified(r, b'expected', tmp_path)
        assert 0xFC0C not in r.calls
    else:
        result = reset.reset_verified(r, b'expected', tmp_path)
        assert r.calls == ['read', 0xFC0C]
        assert result['request_completed'] == (fault is None)
        assert result['boot_observed'] is False
