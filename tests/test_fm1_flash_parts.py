"""The FM-1 flash allow-list: both known parts accepted and named, anything else
refused, writes only on the tested part, and the timing worst case. No hardware."""
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


def test_restore_tool_writes_only_on_puya():
    assert fake(restore.RestoreReader, [fc0a(3, PUYA)]).online() == (3, PUYA)
    with pytest.raises(ValueError, match='UC25HQ80.*never run on that part'):
        fake(restore.RestoreReader, [fc0a(3, UCUN)]).online()
    with pytest.raises(ValueError, match='not a known FM-1 flash'):
        fake(restore.RestoreReader, [fc0a(3, 0xEF4014)]).online()


def test_owner_unit_tool_still_pins_the_owner_part():
    # fm1t_m5.py is hash-pinned and bound to the owner's unit: a different ID
    # there means "not this unit", so it must keep the exact Puya line.
    text = (TOOLS / 'fm1-transporter/fm1t_m5.py').read_text()
    assert 'EXPECTED_INFO = "OK key=980F type=3 id=856014"' in text
    assert 'B36014' not in text.upper() and 'fm1_flash_parts' not in text
