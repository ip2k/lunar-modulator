"""The FM-1 flash allow-list: both known parts accepted and named, anything else
refused, writes only on the tested part, and the timing worst case. No hardware."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import fm1_flash_parts as fp  # noqa: E402
import fm1_uboot_read as uboot  # noqa: E402
import fm1_uboot_restore_test as restore  # noqa: E402

PUYA, UCUN = 0x856014, 0xB36014
# Same 0x14 capacity byte, other makers: a check on capacity alone would pass
# these (Winbond W25Q80, GigaDevice GD25Q80, Zbit), so they must be refused.
FOREIGN_1MIB = [0xEF4014, 0xC84014, 0x5E6014, 0x856015, 0x846014, 0x000000, 0xFFFFFF]


def test_both_parts_are_known_and_named():
    assert fp.FM1_FLASH_JEDEC_IDS == {PUYA, UCUN}
    assert fp.fm1_flash_part(PUYA).name == 'Puya P25Q80H'
    assert fp.fm1_flash_part(UCUN).name == 'UCUN UC25HQ80'
    for jedec in (PUYA, UCUN):
        part = fp.fm1_flash_part(jedec)
        assert part.jedec == jedec and part.size == 1 << 20
        # The low ID byte is the capacity code: 2**0x14 bytes = 1 MiB.
        assert 1 << (jedec & 0xFF) == part.size
        assert f'{jedec:06X}' in part.describe()


@pytest.mark.parametrize('jedec', FOREIGN_1MIB)
def test_unknown_ids_are_refused(jedec):
    with pytest.raises(fp.UnknownFlash, match=f'{jedec:06X} is not a known FM-1 flash'):
        fp.fm1_flash_part(jedec)


def test_writes_only_on_the_tested_part():
    assert fp.require_write_tested(PUYA).jedec == PUYA
    with pytest.raises(fp.UnknownFlash, match='UC25HQ80.*never run on that part'):
        fp.require_write_tested(UCUN)
    with pytest.raises(fp.UnknownFlash, match='not a known FM-1 flash'):
        fp.require_write_tested(0xEF4014)


def test_timing_bounds_use_the_worst_part():
    puya, ucun = fp.FM1_FLASH_PARTS[PUYA], fp.FM1_FLASH_PARTS[UCUN]
    assert (puya.erase_max_ms, ucun.erase_max_ms) == (20, 10)
    assert fp.FM1_FLASH_ERASE_MAX_MS == 20
    assert all(fp.FM1_FLASH_ERASE_MAX_MS >= p.erase_max_ms for p in fp.FM1_FLASH_PARTS.values())
    assert fp.FM1_FLASH_PROGRAM_MAX_MS == 3


def fc0a(kind, jedec):
    """A loader FC0A reply: op echo, device type, ID little-endian at [4:8]."""
    return b'\xfc\x0a' + bytes([kind, 0]) + jedec.to_bytes(4, 'little') + b'\xff' * 8


def fake(cls, replies):
    r = cls.__new__(cls)
    r.events = []
    r.log = lambda event, **f: r.events.append((event, f))
    seq = iter(replies)
    r.cmd = lambda op, **_k: (op == 0xFC0A or pytest.fail(f'unexpected {op:04x}')) and next(seq)
    return r


@pytest.mark.parametrize('jedec,name', [(PUYA, 'Puya P25Q80H'), (UCUN, 'UCUN UC25HQ80')])
def test_reader_accepts_and_logs_both_parts(jedec, name):
    r = fake(uboot.Reader, [fc0a(3, jedec)] * 3)
    for _ in range(3):  # FC0A doubles as the keepalive; logged once
        assert r.online() == (3, jedec)
    assert r.events == [('flash_identity', {'jedec': f'{jedec:06x}', 'part': name,
                                            'bytes': 1 << 20})]


@pytest.mark.parametrize('jedec', FOREIGN_1MIB)
def test_reader_refuses_other_ids(jedec):
    with pytest.raises(ValueError, match='not a known FM-1 flash'):
        fake(uboot.Reader, [fc0a(3, jedec)]).online()


def test_reader_refuses_other_device_type_and_a_changed_id():
    with pytest.raises(ValueError, match='Unexpected flash type'):
        fake(uboot.Reader, [fc0a(2, PUYA)]).online()
    r = fake(uboot.Reader, [fc0a(3, PUYA), fc0a(3, UCUN)])
    r.online()
    with pytest.raises(ValueError, match='changed in the session: 856014 then b36014'):
        r.online()


def run_backup_main(tmp_path, monkeypatch, jedec):
    """fm1_uboot_read.main() end to end with a fake loader and a fake Reader."""
    loader = tmp_path / 'loader.bin'
    loader.write_bytes(b'\0' * 16)
    monkeypatch.setattr(uboot, 'LOADER_SIZE', 16)
    monkeypatch.setattr(uboot, 'LOADER_SHA', hashlib.sha256(b'\0' * 16).hexdigest())
    usb = tmp_path / '1-2'
    usb.mkdir()
    (usb / 'devnum').write_text('7\n')
    entry = tmp_path / 'entry.jsonl'
    entry.write_text('\n'.join(json.dumps(e) for e in [
        {'event': 'identity', 'decoded': {'identity': 'FM-1_015'}},
        {'event': 'uboot_enumerated',
         'usb': [{'vid': '4c4a', 'pid': '8057', 'path': '1-2', 'devnum': '7'}]}]))

    class FakeReader(uboot.Reader):
        def __init__(self, device, log, usb_path):
            self.log, self.usb = log, usb

        def cmd(self, op, **_k):
            assert op == 0xFC0A, f'unexpected {op:04x}'
            return fc0a(3, jedec)

        def load(self, _loader):
            self.online()

        def dump(self, file):
            file.write_bytes(b'\xff' * uboot.FLASH_SIZE)
            return {'file': file.name, 'bytes': uboot.FLASH_SIZE, 'sha256': 'same'}

        def close(self):
            pass

    monkeypatch.setattr(uboot, 'Reader', FakeReader)
    out = tmp_path / 'out'
    monkeypatch.setattr(sys, 'argv', ['fm1_uboot_read.py', '--device', '/dev/sg9',
                                      '--usb-path', '1-2', '--loader', str(loader),
                                      '--entry-log', str(entry), '--out', str(out)])
    uboot.main()
    return out


@pytest.mark.parametrize('jedec,name', [(PUYA, 'Puya P25Q80H'), (UCUN, 'UCUN UC25HQ80')])
def test_backup_manifest_log_and_output_name_the_part(tmp_path, monkeypatch, capsys, jedec, name):
    out = run_backup_main(tmp_path, monkeypatch, jedec)
    manifest = json.loads((out / 'manifest.json').read_text())
    assert (manifest['flash_jedec'], manifest['flash_part']) == (f'{jedec:06x}', name)
    assert f'Flash: {name} (JEDEC {jedec:06X}, 1024 KiB)' in capsys.readouterr().err
    events = [json.loads(line) for line in (out / 'commands.jsonl').read_text().splitlines()]
    assert [e['part'] for e in events if e['event'] == 'flash_identity'] == [name]


def test_backup_stops_on_an_unknown_part_without_a_manifest(tmp_path, monkeypatch, capsys):
    with pytest.raises(SystemExit):
        run_backup_main(tmp_path, monkeypatch, 0xEF4014)
    out = tmp_path / 'out'
    assert not (out / 'manifest.json').exists()
    assert 'Stopped: Flash JEDEC EF4014 is not a known FM-1 flash' in capsys.readouterr().out


def test_restore_tool_writes_only_on_puya():
    assert fake(restore.RestoreReader, [fc0a(3, PUYA)]).online() == (3, PUYA)
    with pytest.raises(ValueError, match='UC25HQ80.*never run on that part'):
        fake(restore.RestoreReader, [fc0a(3, UCUN)]).online()
    with pytest.raises(ValueError, match='not a known FM-1 flash'):
        fake(restore.RestoreReader, [fc0a(3, 0xEF4014)]).online()


@pytest.mark.parametrize('tool', ['fm1t_m5.py', 'fm1t_m6.py', 'fm1t_m8.py'])
def test_owner_unit_tools_still_pin_the_owner_part(tool):
    # The M5/M6/M8 tools are bound to the owner's unit: a different ID there
    # means "not this unit", so they must keep the exact Puya line.
    text = (TOOLS / 'fm1-transporter' / tool).read_text()
    assert 'EXPECTED_INFO = "OK key=980F type=3 id=856014"' in text
    assert 'B36014' not in text.upper() and 'fm1_flash_parts' not in text
