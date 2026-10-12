"""Pure receipt tampering checks; synthetic transcripts confer no authority."""
import copy
import json

import pytest

import fm1_prepare_stop_trace_receipt as v
import fm1_sdk_trace_read as reader
from test_sdk_trace_read import trace, stage


CASES = ('valid', 'cdb', 'boolean_status', 'bad_status', 'bad_hash', 'raw_changed',
         'raw_missing', 'native_extra', 'native_missing', 'future', 'reverse',
         'result_changed', 'pending', 'later_row', 'unterminated', 'bad_inquiry')


@pytest.mark.parametrize('case', CASES)
def test_completed_receipt_tampering(case):
    seal = b'{"synthetic":true}'
    mapping = {'node_identity': [1, 2, 3]}
    replies = [b'\0' * 8 + b'WL82'.ljust(8) + b'UBOOT1.00'.ljust(16) + b'1.00',
               reader.decode_transfer(trace(), 64), reader.decode_transfer(stage(), 4),
               reader.decode_transfer(trace(), 64), reader.decode_transfer(stage(), 4)]
    raw_files = dict(zip(v.NAMES, replies))
    outer = [dict(time=1, event='read_prepared', campaign_sha256=v.digest(seal),
        commands=5, upload_operations=0, reset_operations=0, flash_operations=0)]
    native = [dict(time=2, event='native_open_intent', advisory_lock=True, commands=5),
              dict(time=3, event='native_opened', fd_identity=mapping['node_identity'])]
    for i, (cdb, count) in enumerate(v.OPERATIONS):
        intent = dict(index=i, cdb=cdb.hex(), in_len=count, out_len=0, retry=False)
        outer.append(dict(time=4 + 3*i, event='submit_intent', **intent))
        native.append(dict(time=5 + 3*i, event='native_ioctl_intent', **intent))
        outer.append(dict(time=6 + 3*i, event='completion', index=i,
            **dict.fromkeys(v.STATUS, 0), response_sha256=v.digest(replies[i]),
            actual_response_bytes=count, sense_hex='', retry=False))
    result = dict(reader.interpret_repeated(*replies[1:]), campaign_sha256=v.digest(seal),
        preparation_outcome='failed-before-original-native-worker',
        raw_sha256=[v.digest(r) for r in replies])
    outer.append(dict(time=20, event='coherent_capture_completed', **result, retry=False))
    result_raw, pending_raw = v.canonical(result), None
    if case == 'cdb': outer[3]['cdb'] = 'fc0c'
    if case == 'boolean_status': outer[2]['status'] = False
    if case == 'bad_status': outer[2]['status'] = 1
    if case == 'bad_hash': outer[2]['response_sha256'] = '0' * 64
    if case == 'raw_changed': raw_files['trace-a'] = bytes(64)
    if case == 'raw_missing': del raw_files['inquiry']
    if case == 'native_extra': native.append(copy.deepcopy(native[-1]))
    if case == 'native_missing': native.pop()
    if case == 'future': outer[-1]['time'] = 101
    if case == 'reverse': outer[2]['time'] = 0
    if case == 'result_changed': result_raw = b'{}'
    if case == 'pending': pending_raw = result_raw
    if case == 'later_row': outer.append(dict(time=21, event='reset'))
    if case == 'unterminated': outer.pop(); result_raw = None
    if case == 'bad_inquiry':
        raw_files['inquiry'] = bytes(36)
        outer[2]['response_sha256'] = v.digest(raw_files['inquiry'])
    encode = lambda rows: b'\n'.join(v.canonical(r) for r in rows) + b'\n'
    def replay():
        return v.verify_receipt(encode(outer), encode(native), seal, raw_files, mapping,
            interpret=reader.interpret_repeated, evaluated_at=100,
            result_raw=result_raw, pending_raw=pending_raw)
    if case == 'valid':
        actual = replay()
        assert actual['outcome'] == 'completed'
        assert actual['retained_replies'] == actual['native']['ioctl_intents'] == 5
        assert actual['physical_boot_verified'] is actual['recovery_authorized'] is False
    else:
        with pytest.raises(ValueError): replay()
