"""Boot authorization expires and freezes the completed install evidence."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from native import event120_boot as module


def test_boot_prepared_instances_cannot_be_forged(tmp_path):
    p = module.Prepared(b'{}', 'unused', b'{}', None, None, ())
    with pytest.raises(ValueError, match='factory-created'):
        p.check()


@pytest.mark.parametrize('fault', ['changed', 'expired', 'future'])
def test_boot_frozen_evidence_and_observation_are_checked(tmp_path, monkeypatch, fault):
    evidence = tmp_path / 'completed-readback'
    evidence.write_bytes(b'original')
    p = module.Prepared(module.canonical({'observed_at': 1000}), 'unused',
        b'{}', None, None, ((evidence, module.digest(b'original')),))
    module._AUTHORIZED.add(p)
    monkeypatch.setattr(module.time, 'time', lambda: 1000)
    p.check()
    if fault == 'changed':
        evidence.write_bytes(b'changed')
    else:
        monkeypatch.setattr(module.time, 'time', lambda: 1121 if fault == 'expired' else 999)
    with pytest.raises(ValueError):
        p.check()


def test_boot_does_not_open_sg_after_authorization_failure(monkeypatch):
    class Rejected:
        def check(self):
            raise ValueError('Completed installation proof rejected')
    def forbidden(*args, **kwargs):
        pytest.fail('SG must not open before completed installation authorization')
    monkeypatch.setattr(module.os, 'open', forbidden)
    with pytest.raises(ValueError, match='proof rejected'):
        module.BootSG(Rejected(), lambda *args, **kwargs: None)
