"""Offline replay exercised against the existing NOR/protocol simulator."""
import copy
import json
import time

import pytest

from tests.test_bound_diagnostic import ModelTransport, policy, prepared, sample  # noqa: F401
from fm1_flash_transaction import digest
from native.event120_install_proof import replay


@pytest.fixture
def recorded(prepared):
    events = []
    def log(event, **fields):
        events.append(dict(time=time.time(), event=event, **fields))
    class RecordingTransport(ModelTransport):
        def exchange(self, cdb, payload, size):
            index = len(self.calls)
            log('sg_submit_intent', index=index, direction='install', cdb=cdb.hex(),
                out_len=len(payload), in_len=size,
                payload_sha256=digest(payload) if payload else None, retry=False)
            response = super().exchange(cdb, payload, size)
            log('sg_completion', index=index, direction='install', status=0, masked=0,
                msg=0, host=0, driver=0, resid=0, info=0, sense_len=0, sense_hex='',
                response_sha256=digest(response) if size else None, retry=False)
            return response
    p = prepared
    bound_policy = policy(p)
    arguments = dict(campaign_sha256='a' * 64, sources={'mock': 'b' * 64},
        adapter_sha256='c' * 64, backup_manifest_sha256='d' * 64,
        sg_binding={'node': '/mock/sg0'}, baseline=p['sample']['baseline'],
        target=p['sample']['target'], sector_order=[0x4000], observed_at=time.time())
    log('native_transaction_prepared', campaign_sha256=arguments['campaign_sha256'],
        source_sha256=arguments['sources'], adapter_sha256=arguments['adapter_sha256'],
        backup_manifest_sha256=arguments['backup_manifest_sha256'],
        sg_binding=arguments['sg_binding'], variant='native', direction='install', retry=False)
    receipt = bound_policy.bind(RecordingTransport(p['device'], p['identity'])).run(checkpoint=log)
    result = dict(campaign_sha256=arguments['campaign_sha256'], direction='install',
        variant='native', verified_sha256=receipt['verified_sha256'],
        sectors_written=receipt['sectors_written'], full_flash_readback_verified=True,
        boot_observed=False, physical_recovery_verified=False, kernel_exclusivity=False,
        hardware_admitted=False, installable=False)
    log('native_transaction_completed', **result)
    return events, result, arguments


def encoded(events):
    return b'\n'.join(json.dumps(event).encode() for event in events)


def test_complete_simulated_protocol_transcript(recorded):
    events, result, arguments = recorded
    proof = replay(encoded(events), result, **arguments)
    assert proof['verified'] and proof['sectors'] == 1
    assert proof['commands'] > 8192
    assert proof['hardware_operations'] == 0
    assert not proof['boot_observed'] and not proof['physical_recovery_verified']


@pytest.mark.parametrize('fault', ['missing_completion', 'sg_error', 'wrong_final_page',
    'extra_event', 'wrong_intent', 'false_boot', 'expired', 'overlong',
    'wrong_order', 'protected_change'])
def test_corrupt_or_incomplete_record_is_rejected(recorded, fault):
    events, result, arguments = copy.deepcopy(recorded)
    if fault == 'missing_completion':
        del events[2]
    elif fault == 'sg_error':
        next(e for e in events if e['event'] == 'sg_completion')['host'] = 1
    elif fault == 'wrong_final_page':
        events[-2]['response_sha256'] = '0' * 64
    elif fault == 'extra_event':
        events.append(dict(events[-1]))
    elif fault == 'wrong_intent':
        next(e for e in events if e['event'] == 'durable_intent')['address'] = 0
    elif fault == 'false_boot':
        result['boot_observed'] = True
    elif fault == 'expired':
        arguments['observed_at'] -= 121
    elif fault == 'overlong':
        for event in events:
            event['time'] -= 3000
        arguments['observed_at'] -= 3000
        events[-1]['time'] += 2701
    elif fault == 'wrong_order':
        arguments['sector_order'] = [0x5000, 0x4000]
    else:
        arguments['target'] = bytes([arguments['target'][0] ^ 1]) + arguments['target'][1:]
    with pytest.raises(ValueError):
        replay(encoded(events), result, **arguments)


def test_duplicate_json_key_is_rejected(recorded):
    events, result, arguments = recorded
    raw = encoded(events).replace(b'"event": "native_transaction_prepared"',
        b'"event": "ignored", "event": "native_transaction_prepared"', 1)
    with pytest.raises(ValueError, match='Duplicate'):
        replay(raw, result, **arguments)
