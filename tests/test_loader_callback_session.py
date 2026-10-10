"""Offline guard tests: extract helpers only, never import/run the proposal."""
import ast
import os
from pathlib import Path
import stat
import subprocess
from types import SimpleNamespace

import pytest

PROPOSAL = Path(__file__).resolve().parents[1] / 'notes/data/2026-10-10-loader-callback-session-proposal.txt'


@pytest.fixture
def guards():
    tree = ast.parse(PROPOSAL.read_text())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name != 'main']
    namespace = {'Path': Path, 'stat': stat, 'os': os, 'subprocess': subprocess}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(PROPOSAL), 'exec'), namespace)
    return namespace


def test_proposal_compiles_without_execution():
    compile(PROPOSAL.read_text(), str(PROPOSAL), 'exec')


@pytest.mark.parametrize('mode,device,expected_ok', [
    (stat.S_IFCHR, (21, 0), True), (stat.S_IFBLK, (21, 0), False),
    (stat.S_IFREG, (21, 0), False), (stat.S_IFCHR, (21, 1), False),
])
def test_actual_node_must_match_sysfs_type_and_number(guards, tmp_path, mode, device, expected_ok):
    (tmp_path / 'dev').write_text('21:0\n')
    node = SimpleNamespace(stat=lambda: SimpleNamespace(st_mode=mode, st_rdev=os.makedev(*device)))
    if expected_ok:
        assert guards['node_record'](node, tmp_path, True)['dev'] == '21:0'
    else:
        with pytest.raises(ValueError):
            guards['node_record'](node, tmp_path, True)


@pytest.mark.parametrize('mount,code,stdout,stderr,expected_ok', [
    ('', 1, b'', b'', True), ('1 0 8:0 / /media/fm1 rw - vfat /dev/sda rw', 1, b'', b'', False),
    ('', 0, b'', b'', False), ('', 1, b'123', b'', False),
    ('', 1, b'', b'error', False), ('', 2, b'', b'', False),
])
def test_mount_or_fuser_uncertainty_prevents_access(guards, mount, code, stdout, stderr, expected_ok):
    guards['Path'] = lambda _: SimpleNamespace(read_text=lambda: mount)
    calls = []
    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)
    guards['subprocess'] = SimpleNamespace(run=run)
    records = [{'node': '/dev/sda', 'dev': '8:0'}]
    logs = []
    log = lambda event, **fields: logs.append((event, fields))
    if expected_ok:
        guards['exclusive'](records, log)
        assert calls == [(['fuser', '-s', '/dev/sda'], {'capture_output': True, 'timeout': 5})]
        assert logs[0][1]['returncode'] == 1
    else:
        with pytest.raises(ValueError):
            guards['exclusive'](records, log)
    if mount:
        assert calls == []  # A mounted node stops before even running fuser.


def test_fuser_timeout_is_not_retried(guards):
    guards['Path'] = lambda _: SimpleNamespace(read_text=lambda: '')
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        raise subprocess.TimeoutExpired(args, 5)
    guards['subprocess'] = SimpleNamespace(run=run)
    with pytest.raises(subprocess.TimeoutExpired):
        guards['exclusive']([{'node': '/dev/sg0', 'dev': '21:0'}], lambda *a, **kw: None)
    assert len(calls) == 1


@pytest.mark.parametrize('change', ['path', 'busnum', 'devnum', 'vid', 'pid', 'product', 'duplicate', 'normal', None])
def test_usb_binding_changes_or_extra_fm1_stop_access(guards, change):
    expected = {'path': '3-2', 'busnum': '3', 'devnum': '17',
                'vid': '4c4a', 'pid': '8057', 'product': 'WL80UBOOT1.00'}
    devices = [dict(expected)]
    if change in expected:
        devices[0][change] = 'different'
    elif change == 'duplicate':
        devices.append(dict(expected))
    elif change == 'normal':
        devices.append({'vid': '4c4a', 'pid': 'c755'})
    guards['enumerate_usb'] = lambda: devices
    if change is None:
        guards['same_uboot'](expected)
    else:
        with pytest.raises(ValueError):
            guards['same_uboot'](expected)


@pytest.mark.parametrize('case', ['delayed', 'absent', 'changed_sg', 'partition'])
def test_readiness_requires_actual_nodes_and_fixed_set(guards, case):
    ticks, sleeps, checked = [], [], []
    class FakePath:
        def __init__(self, value):
            self.value = value
            self.name = value.rsplit('/', 1)[-1]
        def __truediv__(self, value):
            return FakePath(self.value + '/' + value)
        def resolve(self):
            return 'bound_usb'
        def glob(self, pattern):
            if self.name == 'scsi_generic':
                return [FakePath('/sg1' if case == 'changed_sg' else '/sg0')]
            return [FakePath('/sda'), FakePath('/sda1')] if case == 'partition' else [FakePath('/sda')]
        def exists(self):
            return case == 'delayed' and len(ticks) >= 3
    def monotonic():
        ticks.append(len(ticks))
        return ticks[-1]
    guards.update(Path=FakePath, ancestor=lambda _: 'bound_usb',
                  same_uboot=lambda _: None,
                  time=SimpleNamespace(monotonic=monotonic, sleep=sleeps.append),
                  node_record=lambda node, *_: {'node': node.value, 'dev': 'mock'},
                  exclusive=lambda records, _: checked.append(records))
    logs = []
    if case == 'delayed':
        assert guards['ready_sg']({}, lambda *a, **kw: logs.append(a)) == '/dev/sg0'
        assert sleeps and len(checked) == 1
    else:
        with pytest.raises(ValueError):
            guards['ready_sg']({}, lambda *a, **kw: logs.append(a))
        assert checked == []
        if case == 'absent':
            assert logs == [('device_nodes_not_ready',)]
