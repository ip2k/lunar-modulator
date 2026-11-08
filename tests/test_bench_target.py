"""Target pinning for ROM-mode USB devices, on a fake sysfs tree. No hardware."""
import json
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import bench_target as bt  # noqa: E402
import fm1_softkey_probe as probe  # noqa: E402
import fm1_uboot_read as uboot  # noqa: E402
import devkit_flash_backup as backup  # noqa: E402

CONFIG = {'schema': 1, 'roles': {'fm1': {'paths': ['1-2'], 'buses': [1]},
                                 'devkit': {'paths': [], 'buses': [3]}}}


class Fake:
    """A sysfs lookalike: devices live under devices/, bus/usb/devices links to them."""

    def __init__(self, root):
        self.root = root
        self.usb = root / 'bus/usb/devices'
        self.sg = root / 'class/scsi_generic'
        self.usb.mkdir(parents=True)
        self.sg.mkdir(parents=True)
        self.n = 0

    def add(self, path, vid, pid, devnum, sg=None):
        real = self.root / 'devices' / f'usb{path.split("-")[0]}' / path
        real.mkdir(parents=True)
        for name, val in (('idVendor', vid), ('idProduct', pid), ('devnum', devnum)):
            (real / name).write_text(val + '\n')
        (self.usb / path).symlink_to(real)
        if sg:
            leaf = real / f'{path}:1.0' / 'host0' / 'target0:0:0' / '0:0:0:0'
            leaf.mkdir(parents=True)
            (self.sg / sg).mkdir()
            (self.sg / sg / 'device').symlink_to(leaf)
        return real

    def pin(self, role, path, device='/dev/sg1', **kw):
        return bt.pin_rom_target(role, path, device, config=CONFIG,
                                 usb_root=self.usb, sg_root=self.sg, **kw)


@pytest.fixture
def fake(tmp_path):
    return Fake(tmp_path)


def test_single_matching_device_pins_and_logs(fake):
    fake.add('1-2', '4c4a', '8057', '7', sg='sg1')
    log = Mock()
    t = fake.pin('fm1', '1-2', devnum='7', log=log)
    assert (t['role'], t['path'], t['devnum']) == ('fm1', '1-2', '7')
    log.assert_called_once_with('target_pinned', role='fm1', usb_path='1-2', devnum='7',
                                device='/dev/sg1')


def test_devkit_on_its_bus_pins(fake):
    fake.add('3-1.2', '4c4a', '8057', '9', sg='sg1')
    assert fake.pin('devkit', '3-1.2')['path'] == '3-1.2'


def test_two_rom_devices_refused_even_for_the_right_one(fake):
    fake.add('1-2', '4c4a', '8057', '7', sg='sg1')
    fake.add('3-1.2', '4c4a', '8057', '9', sg='sg2')
    for role, path, dev in (('fm1', '1-2', '/dev/sg1'), ('devkit', '3-1.2', '/dev/sg2')):
        with pytest.raises(bt.PinError, match='More than one'):
            fake.pin(role, path, dev)


def test_fm1_in_rom_but_devkit_requested_is_refused(fake):
    fake.add('1-2', '4c4a', '8057', '7', sg='sg1')
    # Devkit asked for on its own bus: the only ROM device is the FM-1's.
    with pytest.raises(bt.PinError, match='only 4c4a:8057 device is at 1-2'):
        fake.pin('devkit', '3-1.2')
    # Devkit asked for the FM-1's port: refused by role/config first.
    with pytest.raises(bt.PinError, match='fm1 port'):
        fake.pin('devkit', '1-2')


def test_devkit_in_rom_but_fm1_requested_is_refused(fake):
    fake.add('3-1.2', '4c4a', '8057', '9', sg='sg1')
    with pytest.raises(bt.PinError, match='not a configured fm1 path'):
        fake.pin('fm1', '3-1.2')
    with pytest.raises(bt.PinError, match='only 4c4a:8057 device is at 3-1.2'):
        fake.pin('fm1', '1-2')


def test_no_rom_device_refused(fake):
    fake.add('1-2', '4c4a', 'c755', '3')
    with pytest.raises(bt.PinError, match='No 4c4a:8057'):
        fake.pin('fm1', '1-2')


def test_sg_node_on_another_path_refused(fake):
    fake.add('1-2', '4c4a', '8057', '7', sg='sg1')
    fake.add('3-1.2', '0424', '2514', '2', sg='sg2')  # unrelated SCSI device
    with pytest.raises(bt.PinError, match='not on USB path'):
        fake.pin('fm1', '1-2', '/dev/sg2')


def test_devnum_change_refused(fake):
    fake.add('1-2', '4c4a', '8057', '7', sg='sg1')
    with pytest.raises(bt.PinError, match='devnum is 7, expected 8'):
        fake.pin('fm1', '1-2', devnum='8')


@pytest.mark.parametrize('bad', ['', '1', 'usb1', '1-2/..', '1-2:1.0', '01-2', '1-', None, '1-2 '])
def test_malformed_usb_path_refused(bad):
    with pytest.raises(bt.PinError):
        bt.check_role_path('fm1', bad, CONFIG)


def test_unknown_role_and_bad_sg_name_refused(fake):
    with pytest.raises(bt.PinError, match='Unknown role'):
        bt.check_role_path('both', '1-2', CONFIG)
    fake.add('1-2', '4c4a', '8057', '7', sg='sg1')
    with pytest.raises(bt.PinError, match='SCSI-generic'):
        fake.pin('fm1', '1-2', '/dev/sda')


def test_shipped_config_is_valid_and_disjoint():
    cfg = bt.load_config(TOOLS / 'bench_targets.json')
    bt.check_role_path('fm1', '1-2', cfg)
    bt.check_role_path('devkit', '3-1.4', cfg)
    with pytest.raises(bt.PinError):
        bt.check_role_path('fm1', '3-1.4', cfg)
    with pytest.raises(bt.PinError):
        bt.check_role_path('devkit', '1-2', cfg)


@pytest.mark.parametrize('cfg', [
    {'roles': {'fm1': {'buses': [1]}}},
    {'roles': {'fm1': {'buses': [1]}, 'devkit': {'buses': [1]}}},
    {'roles': {'fm1': {'paths': ['1-2']}, 'devkit': {'paths': ['1-2']}}},
    {'roles': {'fm1': {'paths': ['x']}, 'devkit': {'buses': [3]}}},
    {'roles': {'fm1': {}, 'devkit': {'buses': [3]}}},
])
def test_bad_configs_refused(tmp_path, cfg):
    f = tmp_path / 'c.json'
    f.write_text(json.dumps(cfg))
    with pytest.raises(bt.PinError):
        bt.load_config(f)


def test_env_override_and_missing_file(tmp_path, monkeypatch):
    f = tmp_path / 'c.json'
    f.write_text(json.dumps(CONFIG))
    monkeypatch.setenv('FM1_BENCH_TARGETS', str(f))
    assert bt.load_config() == CONFIG
    monkeypatch.setenv('FM1_BENCH_TARGETS', str(tmp_path / 'missing.json'))
    with pytest.raises(bt.PinError, match='Cannot read'):
        bt.load_config()


def test_reader_pins_before_opening_the_node(fake, monkeypatch):
    fake.add('1-2', '4c4a', '8057', '7', sg='sg1')
    fake.add('3-1.2', '4c4a', '8057', '9', sg='sg2')
    opened = Mock()
    monkeypatch.setattr(uboot.os, 'open', opened)
    monkeypatch.setattr(bt, 'load_config', lambda path=None: CONFIG)
    for cls, path, dev in ((uboot.Reader, '1-2', '/dev/sg1'), (backup.DevkitReader, '3-1.2', '/dev/sg2')):
        with pytest.raises(bt.PinError):
            cls(dev, Mock(), usb_path=path, usb_root=fake.usb, sg_root=fake.sg)
    opened.assert_not_called()


def test_reader_roles_are_fixed_per_tool(fake, monkeypatch):
    assert uboot.Reader.ROLE == 'fm1' and backup.DevkitReader.ROLE == 'devkit'
    fake.add('1-2', '4c4a', '8057', '7', sg='sg1')
    monkeypatch.setattr(uboot.os, 'open', Mock(return_value=5))
    monkeypatch.setattr(bt, 'load_config', lambda path=None: CONFIG)
    # The dev-kit adapter must not open the FM-1, nor the FM-1 reader a dev kit.
    with pytest.raises(bt.PinError):
        backup.DevkitReader('/dev/sg1', Mock(), usb_path='1-2', usb_root=fake.usb, sg_root=fake.sg)
    r = uboot.Reader('/dev/sg1', Mock(), usb_path='1-2', usb_root=fake.usb, sg_root=fake.sg)
    assert r.usb.name == '1-2' and r.fd == 5


@pytest.mark.parametrize('mod', ['fm1_uboot_read', 'fm1_uboot_restore_test', 'devkit_flash_backup',
                                 'devkit_flash_transaction', 'devkit_loader_reset', 'fm1_softkey_probe'])
def test_every_rom_tool_requires_usb_path(mod):
    text = (TOOLS / f'{mod}.py').read_text()
    assert "'--usb-path'" in text or "'usb-path'" in text


def _probe_env(monkeypatch, listing, parent='/usb1/1-2'):
    monkeypatch.setattr(probe, 'usb_parent', lambda _: Path(parent))
    monkeypatch.setattr(bt, 'load_config', lambda path=None: CONFIG)
    monkeypatch.setattr(probe, 'enumerate_usb', lambda: listing)
    opened = Mock()
    monkeypatch.setattr(probe.os, 'open', opened)
    return opened


def dev(path, pid):
    return {'path': path, 'vid': '4c4a', 'pid': pid}


def test_softkey_refused_on_wrong_path_before_open(monkeypatch):
    opened = _probe_env(monkeypatch, [], parent='/usb3/3-2')
    with pytest.raises(ValueError, match='not the requested 1-2'):
        probe.probe('/dev/snd/midiC2D0', 'FM-1_092', True, Mock(), usb_path='1-2')
    with pytest.raises(bt.PinError):
        probe.probe('/dev/snd/midiC2D0', 'FM-1_092', True, Mock(), usb_path='3-2')
    opened.assert_not_called()


def test_softkey_refused_when_a_rom_device_is_already_present(monkeypatch):
    opened = _probe_env(monkeypatch, [dev('1-2', 'c755'), dev('3-1.2', '8057')])
    with pytest.raises(ValueError, match='already present'):
        probe.probe('/dev/snd/midiC2D0', 'FM-1_092', True, Mock(), usb_path='1-2')
    opened.assert_not_called()


def test_identity_only_probe_ignores_present_rom_devices(monkeypatch):
    _probe_env(monkeypatch, [dev('1-2', 'c755'), dev('3-1.2', '8057')])
    monkeypatch.setattr(probe.os, 'close', lambda *a: None)
    monkeypatch.setattr(probe.select, 'select', lambda *a: ([], [], []))
    monkeypatch.setattr(probe, 'write_message', Mock())
    with pytest.raises(ValueError, match='identity'):  # reaches the identity wait, no soft key
        probe.probe('/dev/snd/midiC2D0', 'FM-1_092', False, Mock(), timeout=0.001, usb_path='1-2')
