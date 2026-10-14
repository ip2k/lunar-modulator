"""Exact device36 policy admission and refusal, using private actual images."""
from dataclasses import replace
import json
import os
from pathlib import Path

import pytest

from tools.native.expanded_bench_transactions import prepare, AREA_END
from native.expanded_bench_policy import load_policy, LOADER_SHA


@pytest.fixture(scope='module')
def plans(tmp_path_factory):
    name = os.environ.get('FM1_PRIVATE_FRESH_EXPANDED_INPUTS')
    if not name:
        pytest.skip('Private actual device36 inputs required')
    root = Path(name)
    output = tmp_path_factory.mktemp('expanded-policy') / 'plans'
    prepare(output, root / 'fresh', root / 'target.bin',
            root / 'stockA.bin', root / 'stockB.bin')
    return output, root / 'fresh'


def policy(plans, variant='native', direction='install'):
    output, receipt = plans
    return load_policy(output / variant, receipt=receipt,
                       variant=variant, direction=direction)


class Assertions:
    """No exchange implementation: refusal must precede any wire operation."""
    def __init__(self, p):
        self.claim = dict(json.loads(p.binding_bytes), phase='loader',
                          loader_sha256=LOADER_SHA, session_id='mock-only',
                          identity=json.loads(p.plan_bytes)['identity'])
        self.closed = False

    def binding(self):
        return self.claim

    def close(self):
        self.closed = True


@pytest.mark.parametrize('variant,count', [('native', 213), ('stock', 13)])
@pytest.mark.parametrize('direction', ['install', 'restore'])
def test_exact_plans_admitted_offline(plans, variant, count, direction):
    p = policy(plans, variant, direction)
    assert len(p.sectors) == count and max(p.sectors) < AREA_END
    assert not p.receipt()['hardware_admitted']
    session = p.bind(Assertions(p))
    session.close()


@pytest.mark.parametrize('field', ['phase', 'loader_sha256', 'session_id', 'identity',
    'usb_binding', 'backup_manifest_sha256', 'backup_commands_sha256',
    'backup_campaign_sha256'])
def test_wrong_loader_or_backup_binding_stops_before_wire(plans, field):
    p = policy(plans)
    transport = Assertions(p)
    transport.claim[field] = '' if field == 'session_id' else 'wrong'
    with pytest.raises(ValueError, match='binding differs'):
        p.bind(transport)
    assert transport.closed


def test_copied_policy_is_not_factory_admission(plans):
    p = policy(plans)
    with pytest.raises(ValueError, match='factory-created'):
        replace(p).bind(Assertions(p))


@pytest.mark.parametrize('address', [0, AREA_END, 0xFFFFF])
def test_protected_erase_never_reaches_wire(plans, address):
    p = policy(plans)
    session = p.bind(Assertions(p))
    with pytest.raises(ValueError, match='derived changed sector'):
        session.erase(address)
    session.close()


def test_changed_loader_session_stops_before_wire(plans):
    p = policy(plans)
    transport = Assertions(p)
    session = p.bind(transport)
    transport.claim['session_id'] = 'changed'
    with pytest.raises(ValueError, match='binding changed'):
        session.online()
    assert transport.closed


def test_erase_requires_durable_intent(plans):
    p = policy(plans)
    session = p.bind(Assertions(p))
    with pytest.raises(ValueError, match='durable transaction'):
        session.erase(0x5000)
    session.close()


@pytest.mark.parametrize('command', [0xFC12, 0xFB08, 0xFC0C])
def test_efuse_upload_and_reset_forbidden(plans, command):
    p = policy(plans)
    session = p.bind(Assertions(p))
    with pytest.raises(ValueError):
        session.cmd(command)
    session.close()
