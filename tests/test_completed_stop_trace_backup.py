"""Freshness and closed-authority boundaries for completed-trace recovery."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import fm1_completed_stop_trace_backup as backup

CASES = ('valid', 'expired', 'future', 'nan', 'boolean', 'snapshot_pin',
         'usb_changed', 'sg_changed', 'state_changed', 'kind_changed',
         'extra_field', 'schema_boolean', 'before_snapshot', 'closed_backup',
         'unregistered_backup', 'copied_authority')


@pytest.mark.parametrize('case', CASES)
def test_completed_stop_trace_backup_boundary(case, tmp_path):
    # Factory refusal must precede even reading an absent campaign.
    if case == 'closed_backup':
        assert backup.PROOF_SOURCE_SHA is None
        with pytest.raises(ValueError, match='Closed'):
            backup.prepare_campaign(tmp_path / 'absent.json')
        return
    if case in ('unregistered_backup', 'copied_authority'):
        candidate = object.__new__(backup.Prepared)
        if case == 'copied_authority': candidate = copy.copy(candidate)
        with pytest.raises(ValueError, match='prepared backup instance'):
            backup.require_prepared(candidate)
        return
    snapshot = dict(observed_at=100, usb_binding={'busnum': '1', 'devnum': '10'},
                    sg_binding={'node': '/dev/sg0', 'node_identity': [1, 2, 3]})
    witness = dict(schema=1, kind='fm1-passive-sdk-completed-stop-trace-backup-connection',
                   observed_at=200, usb_binding=copy.deepcopy(snapshot['usb_binding']),
                   sg_binding=copy.deepcopy(snapshot['sg_binding']),
                   original_rom_snapshot_sha256='a' * 64,
                   completed_trace_sha256='b' * 64, quiet_state=backup.STATE)
    if case == 'expired': witness['observed_at'] = 179
    if case == 'future': witness['observed_at'] = 301
    if case == 'nan': witness['observed_at'] = float('nan')
    if case == 'boolean': witness['observed_at'] = True
    if case == 'snapshot_pin': witness['original_rom_snapshot_sha256'] = 'c' * 64
    if case == 'usb_changed': witness['usb_binding']['devnum'] = '11'
    if case == 'sg_changed': witness['sg_binding']['node_identity'][1] = 4
    if case == 'state_changed': witness['quiet_state'] = 'reader-completed'
    if case == 'kind_changed': witness['kind'] = 'fm1-passive-sdk-trace-admitted-backup-connection'
    if case == 'extra_field': witness['retry'] = True
    if case == 'schema_boolean': witness['schema'] = True
    if case == 'before_snapshot': witness['observed_at'] = 99
    if case == 'valid':
        backup.validate_connection_witness(witness, snapshot, 'a' * 64, 300)
    else:
        with pytest.raises(ValueError):
            backup.validate_connection_witness(witness, snapshot, 'a' * 64, 300)
