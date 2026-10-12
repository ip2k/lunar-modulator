"""MIT. Lifecycle corruption models; these do not simulate device execution."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from fm1_prepare_stop_capture_receipt import FILES, digest, verify_capture


def encode(value):
    return json.dumps(value, sort_keys=True).encode()


def fixture():
    files = dict.fromkeys(FILES, b'')
    files.update({'execute-once.py': b'wrapper', 'execute-child.py': b'child'})
    expected = dict(wrapper_sha256=digest(b'wrapper'), child_sha256=digest(b'child'),
        native_campaign_path='/private/run/campaign.json', native_campaign_sha256='1'*64,
        preparation_stop_path='/private/run/stop.json', preparation_stop_sha256='2'*64,
        native_sha256='3'*64, reader_sha256='4'*64, proof_sha256='5'*64,
        usb_binding=dict(busnum='1', devnum='10', path='1-1', vid='4c4a', pid='8057'))
    records = {
        'wrapper-attempt.json': dict(time=10., campaign_sha256='1'*64,
            preparation_stop_sha256='2'*64, native_sha256='3'*64, reader_sha256='4'*64,
            proof_sha256='5'*64, usb_binding=expected['usb_binding'], retry=False,
            commands=5, upload_operations=0, reset_operations=0, flash_operations=0),
        'capture-open.json': dict(time=11., timeout_pid=100, cat_pid=101,
            process_group=100, open_capture_fd=True),
        'execution-exit.json': dict(time=14., exit_status=0, campaign_sha256='1'*64,
            capture_alive_after_child=True, retry=False, read_completion_attested=False,
            recovery_proven=False, boot_cause_proven=False),
        'capture-stop.json': dict(time=15., process_group=100, returncode=-15,
            owned_processes_only=True)}
    return files, expected, records


CASES = ['valid', 'missing-file', 'altered-wrapper', 'wrong-stop', 'extra-attempt',
         'retry', 'upload', 'wrong-group', 'same-pids', 'closed-fd', 'not-alive',
         'failed-exit', 'invented-recovery', 'bad-cleanup', 'outside-capture', 'bool-exit']


@pytest.mark.parametrize('case', CASES)
def test_capture_lifecycle(case):
    files, expected, records = fixture()
    start, terminal = 12., 13.
    if case == 'missing-file': files.pop('preflight.json')
    if case == 'altered-wrapper': files['execute-once.py'] += b'changed'
    if case == 'wrong-stop': records['wrapper-attempt.json']['preparation_stop_sha256'] = '6'*64
    if case == 'extra-attempt': records['wrapper-attempt.json']['unreviewed'] = True
    if case == 'retry': records['wrapper-attempt.json']['retry'] = True
    if case == 'upload': records['wrapper-attempt.json']['upload_operations'] = 1
    if case == 'wrong-group': records['capture-stop.json']['process_group'] = 999
    if case == 'same-pids': records['capture-open.json']['cat_pid'] = 100
    if case == 'closed-fd': records['capture-open.json']['open_capture_fd'] = False
    if case == 'not-alive': records['execution-exit.json']['capture_alive_after_child'] = False
    if case == 'failed-exit': records['execution-exit.json']['exit_status'] = 1
    if case == 'invented-recovery': records['execution-exit.json']['recovery_proven'] = True
    if case == 'bad-cleanup': records['capture-stop.json']['owned_processes_only'] = False
    if case == 'outside-capture': terminal = 16.
    if case == 'bool-exit': records['execution-exit.json']['exit_status'] = False
    files.update({name: encode(value) for name, value in records.items()})
    envelope = dict(schema=1, kind='fm1-owned-preparation-stop-trace-read-capture',
        native_campaign_path=expected['native_campaign_path'],
        native_campaign_sha256=expected['native_campaign_sha256'],
        preparation_stop_path=expected['preparation_stop_path'],
        preparation_stop_sha256=expected['preparation_stop_sha256'],
        wrapper_files_sha256={name: digest(raw) for name, raw in files.items()})
    # Reseal altered records so rejection tests semantics rather than only hashes.
    if case != 'valid':
        with pytest.raises(ValueError):
            verify_capture(encode(envelope), files, expected, read_outcome='completed',
                           read_started=start, read_terminal=terminal)
    else:
        result = verify_capture(encode(envelope), files, expected, read_outcome='completed',
                                read_started=start, read_terminal=terminal)
        assert result['terminal_at'] == 15.
        assert result['recovery_authorized'] is result['returned_proof_granted'] is False
