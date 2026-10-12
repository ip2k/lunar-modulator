"""File-only rejection tests for preparation stops, never transport authority."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import fm1_sdk_trace_prepare_stop as stop


def records():
    return (
        {'time': 101, 'retry': False, 'source_sha256': stop.PREPARER_SHA},
        {'time': 102, 'exit_status': 1, 'nonzero_preserved': True,
         'retry': False, 'stdout_sha256': 'a' * 64},
        {'time': 103, 'automatic_recovery': False,
         'capture_cleanup_not_assumed': True, 'detail': 'native-prepare stopped; no retry',
         'error': 'RuntimeError', 'retry': False, 'stock_unchanged_not_assumed': True},
    )


CASES = ('valid', 'earlier_intent', 'nonfinite_time', 'boolean_time', 'successful_exit',
         'retry', 'wrong_source', 'wrong_stdout', 'automatic_recovery',
         'assumed_stock', 'extra_exit', 'absent_symlink', 'later_child',
         'missing_packet_file', 'extra_packet_file', 'symlink_packet_dir')


@pytest.mark.parametrize('case', CASES)
def test_preparation_stop_contract(case, tmp_path):
    intent, exited, stopped = copy.deepcopy(records())
    if case == 'valid':
        stop.validate_stop_records(intent, exited, stopped, 'a' * 64, 100)
        return
    if case == 'absent_symlink':
        path = tmp_path / 'receipt'; path.symlink_to(tmp_path / 'nonexistent')
        with pytest.raises(ValueError): stop.require_absent([path])
        return
    if case == 'later_child':
        (tmp_path / '09-unexpected.intent.json').write_text('{}')
        with pytest.raises(ValueError): stop.chain_inventory(tmp_path)
        return
    if case.endswith('packet_file') or case == 'symlink_packet_dir':
        packet = tmp_path / 'packet'; packet.mkdir()
        for name in stop.PARTIAL_PINS:
            target = packet / name
            target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(b'fixture')
        stop.packet_inventory(packet)
        if case == 'missing_packet_file': (packet / 'run/lineage.json').unlink()
        if case == 'extra_packet_file': (packet / 'run/worker.json').write_text('{}')
        if case == 'symlink_packet_dir': (packet / 'extra').symlink_to(packet / 'run', target_is_directory=True)
        with pytest.raises(ValueError): stop.packet_inventory(packet)
        return
    if case == 'earlier_intent': intent['time'] = 99
    if case == 'nonfinite_time': exited['time'] = float('nan')
    if case == 'boolean_time': exited['time'] = True
    if case == 'successful_exit': exited['exit_status'] = 0
    if case == 'retry': intent['retry'] = True
    if case == 'wrong_source': intent['source_sha256'] = 'b' * 64
    if case == 'wrong_stdout': exited['stdout_sha256'] = 'b' * 64
    if case == 'automatic_recovery': stopped['automatic_recovery'] = True
    if case == 'assumed_stock': stopped['stock_unchanged_not_assumed'] = False
    if case == 'extra_exit': exited['device_opened'] = False
    with pytest.raises(ValueError):
        stop.validate_stop_records(intent, exited, stopped, 'a' * 64, 100)
