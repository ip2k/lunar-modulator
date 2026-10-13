"""Read-only admission faults; no USB, SG open or flash operations."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import fm1_repeat_rom_backup as adapter


class RepeatReceiptTests(unittest.TestCase):
    def setUp(self):
        self.c = dict(returned_backup_campaign_sha256='a'*64,
            returned_backup_commands_sha256='b'*64, returned_backup_manifest_sha256='c'*64)
        self.sha = 'd'*64
        self.rows = [dict(time=10, event='trace_repeat_reset_prepared', campaign_sha256=self.sha,
            returned_backup_campaign_sha256='a'*64, returned_backup_commands_sha256='b'*64,
            backup_manifest_sha256='c'*64, adapter_sha256=adapter.REPEAT_SHA,
            commands=1, flash_operations=0, upload_operations=0,
            kernel_exclusivity=False, boot_observed=False),
            dict(time=11, event='reset_submit_intent', phase='trace-repeat-fixed-loader',
                cdb='fc0c00000001ffffffffffffffffffff', in_len=16, out_len=0,
                retry=False, boot_observed=False),
            dict(time=12, event='reset_stopped_ambiguous', error='ValueError',
                detail='Exactly one SG device on pinned topology required', retry=False,
                core_reset_observed=False, boot_observed=False)]
        self.usb = dict(path='1-1', busnum='1', devnum='13', vid='4c4a', pid='8057')
        self.snapshot = dict(schema=1, kind='fm1-passive-repeat-returned-usb', observed_at=20,
            usb_binding=dict(self.usb, devnum='14'), sg_binding={})

    def check_receipt(self, rows):
        raw = ('\n'.join(json.dumps(r) for r in rows)+'\n').encode()
        return adapter.validate_repeat_receipt(raw, self.c, self.sha, 9, 30)

    def test_valid(self):
        self.assertEqual(self.check_receipt(self.rows), 12)
        adapter.validate_snapshot(self.snapshot, self.usb, 12, 30)

    def test_closed_opener(self):
        with patch.object(adapter.os, 'open') as opened:
            with self.assertRaises(ValueError):
                adapter.FixedSG(object(), lambda *args, **kwargs: None)
            opened.assert_not_called()

    def test_marker_origin_ignores_campaign_formatting(self):
        class Candidate:
            parent = Path('/private/returned-repeat')
            repeat_sha256 = 'a'*64
        p = Candidate()
        first = adapter.marker_path(p)
        p.campaign_sha256 = 'b'*64
        self.assertEqual(first, adapter.marker_path(p))

    def test_symlink_evidence_refused(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)
            (path/'real').write_text('evidence')
            (path/'link').symlink_to(path/'real')
            with self.assertRaises(OSError):
                adapter.read_file(path/'link')


def fault_test(index):
    def test(self):
        rows, snapshot = copy.deepcopy(self.rows), copy.deepcopy(self.snapshot)
        if index == 0: rows[0]['campaign_sha256'] = '0'*64
        elif index == 1: rows[0]['backup_manifest_sha256'] = '0'*64
        elif index == 2: rows[0]['flash_operations'] = 1
        elif index == 3: rows[0]['upload_operations'] = 1
        elif index == 4: rows[1]['retry'] = True
        elif index == 5: rows[1]['cdb'] = 'fc1200000001ffffffffffffffffffff'
        elif index == 6: rows[1]['out_len'] = 1
        elif index == 7: rows[2]['core_reset_observed'] = True
        elif index == 8: rows[2]['event'] = 'reset_request_completed'
        elif index == 9: rows.append(copy.deepcopy(rows[-1]))
        elif index == 10: rows[1]['time'] = 31
        elif index == 11: rows[0]['time'] = True
        elif index == 12: snapshot['observed_at'] = -100
        elif index == 13: snapshot['observed_at'] = 31
        elif index == 14: snapshot['usb_binding']['devnum'] = '13'
        elif index == 15: snapshot['usb_binding']['path'] = '1-2'
        with self.assertRaises(ValueError):
            if index < 12:
                self.check_receipt(rows)
            else:
                adapter.validate_snapshot(snapshot, self.usb, 12, 30)
    return test


for _index in range(16):
    setattr(RepeatReceiptTests, 'test_fault_%02d'%_index, fault_test(_index))
