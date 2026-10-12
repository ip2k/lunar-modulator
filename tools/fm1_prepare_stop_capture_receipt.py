"""MIT. Pure lifecycle replay for the distinct preparation-stop trace capture.

This accepts the original stop-capture schema, not the earlier boot-capture
schema. It does not open devices, register recovery proofs, refresh witnesses,
or establish process origin. A recovery factory must freeze all inputs and
independently verify provenance, source derivatives, native and wire receipts.
"""
import hashlib
import json
import math
from pathlib import Path
import re

FILES = ('execute-once.py', 'execute-child.py', 'preflight.json',
         'wrapper-attempt.json', 'capture-open.json', 'capture-stop.json',
         'execution.stdout', 'execution-exit.json', 'usbmon.txt', 'usbmon.stderr')
EXPECTED = {'wrapper_sha256', 'child_sha256', 'native_campaign_path',
            'native_campaign_sha256', 'preparation_stop_path',
            'preparation_stop_sha256', 'native_sha256', 'reader_sha256',
            'proof_sha256', 'usb_binding'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def verify_capture(envelope_raw, files, expected, *, read_outcome,
                   read_started, read_terminal):
    """Check actual lifecycle bytes against separately frozen source/input pins.

    Only a completed five-read receipt is admitted here. Interrupted capture
    recovery requires its own admission; it must never borrow this success case.
    """
    if (type(envelope_raw) is not bytes or len(envelope_raw) > 65536
            or type(expected) is not dict or set(expected) != EXPECTED
            or type(files) is not dict or set(files) != set(FILES)):
        raise ValueError('Exact bounded preparation-stop capture inputs required')
    for name, value in expected.items():
        if name.endswith('sha256') and (type(value) is not str
                or re.fullmatch('[0-9a-f]{64}', value) is None):
            raise ValueError('Exact accepted source digest required')
        if name.endswith('_path') and (type(value) is not str or not Path(value).is_absolute()):
            raise ValueError('Original absolute capture input required')
    for name, raw in files.items():
        if type(raw) is not bytes or len(raw) > (16 * 1048576 if name == 'usbmon.txt' else 2 * 1048576):
            raise ValueError('Bounded actual capture bytes required')
    envelope = json.loads(envelope_raw)
    wanted = dict(schema=1, kind='fm1-owned-preparation-stop-trace-read-capture',
        native_campaign_path=expected['native_campaign_path'],
        native_campaign_sha256=expected['native_campaign_sha256'],
        preparation_stop_path=expected['preparation_stop_path'],
        preparation_stop_sha256=expected['preparation_stop_sha256'],
        wrapper_files_sha256={name: digest(raw) for name, raw in files.items()})
    if (canonical(envelope) != canonical(wanted)
            or digest(files['execute-once.py']) != expected['wrapper_sha256']
            or digest(files['execute-child.py']) != expected['child_sha256']
            or files['usbmon.stderr']):
        raise ValueError('Exact original capture envelope/source/hash required')
    attempt, opened, exited, stopped = [json.loads(files[name]) for name in
        ('wrapper-attempt.json', 'capture-open.json', 'execution-exit.json', 'capture-stop.json')]
    if any(type(record) is not dict for record in (attempt, opened, exited, stopped)):
        raise ValueError('Capture records must be objects')
    wanted_attempt = dict(campaign_sha256=expected['native_campaign_sha256'],
        preparation_stop_sha256=expected['preparation_stop_sha256'],
        native_sha256=expected['native_sha256'], reader_sha256=expected['reader_sha256'],
        proof_sha256=expected['proof_sha256'], usb_binding=expected['usb_binding'],
        retry=False, commands=5, upload_operations=0, reset_operations=0, flash_operations=0)
    if (set(attempt) != {'time', *wanted_attempt}
            or canonical({k: v for k, v in attempt.items() if k != 'time'}) != canonical(wanted_attempt)):
        raise ValueError('Exact original stop-capture attempt required')
    if (set(opened) != {'time', 'timeout_pid', 'cat_pid', 'process_group', 'open_capture_fd'}
            or set(stopped) != {'time', 'process_group', 'returncode', 'owned_processes_only'}
            or set(exited) != {'time', 'exit_status', 'campaign_sha256', 'capture_alive_after_child',
                'retry', 'read_completion_attested', 'recovery_proven', 'boot_cause_proven'}):
        raise ValueError('Exact owned capture/exit receipt shape required')
    if (any(type(opened[k]) is not int or opened[k] <= 0 for k in ('timeout_pid', 'cat_pid', 'process_group'))
            or opened['timeout_pid'] != opened['process_group']
            or opened['cat_pid'] == opened['timeout_pid'] or opened['open_capture_fd'] is not True
            or type(stopped['process_group']) is not int or stopped['process_group'] != opened['process_group']
            or type(stopped['returncode']) is not int or stopped['returncode'] != -15
            or stopped['owned_processes_only'] is not True
            or type(exited['exit_status']) is not int or exited['exit_status'] != 0
            or exited['campaign_sha256'] != expected['native_campaign_sha256']
            or exited['capture_alive_after_child'] is not True
            or any(exited[k] is not False for k in ('retry', 'read_completion_attested',
                                                  'recovery_proven', 'boot_cause_proven'))):
        raise ValueError('Exact owned process and successful terminal identity required')
    times = [record['time'] for record in (attempt, opened, exited, stopped)]
    if (not all(finite(t) for t in times) or times != sorted(times)
            or read_outcome != 'completed' or not finite(read_started) or not finite(read_terminal)
            or not opened['time'] <= read_started <= read_terminal <= exited['time']):
        raise ValueError('Completed native read must be inside original live capture')
    return dict(envelope_sha256=digest(envelope_raw), started_at=times[0], terminal_at=times[-1],
                exit_status=0, returned_proof_granted=False, wire_inventory_verified=False,
                process_origin_verified=False, physical_boot_verified=False, recovery_authorized=False)
