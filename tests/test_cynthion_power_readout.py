"""Host decoder rejects unsafe interpretation while retaining diagnostic raw data."""
import pytest

from tools.cynthion_usb_key.read_power_monitor import (
    MAGIC, MAX_AGE_CYCLES, decode_registers, read_sweep,
)


def healthy():
    return {1: MAGIC, 2: 2, 3: 0x105, 4: 0x400054, 5: 10240, 6: 0xFFFF,
            7: 10, 8: 100, 9: 11, 10: 1}


def test_authenticated_fresh_sweep_converts_supply_not_power():
    result = read_sweep(healthy().__getitem__)
    assert result['valid'] and result['problems'] == []
    assert result['vbus_uv'] == 5_000_000
    assert result['current_ua'] == -153
    assert result['current_raw_signed'] == -1
    assert result['current_sign'] == 'positive TARGET_A_to_CONTROL; negative CONTROL_to_TARGET_A'
    assert result['atomic'] is False
    assert 'power' not in result
    assert result['raw_registers']['4'] == 0x400054


@pytest.mark.parametrize('address,value', [
    (1, 0x4c554e52), (2, 1), (3, 0x101), (3, 0x107), (3, 0x10d),
    (3, 0x115), (3, 0x305), (4, 0x10054), (4, 0x55),
    (5, 0x10000), (6, 0x10000), (7, 0), (8, MAX_AGE_CYCLES + 1), (10, 3),
])
def test_bad_status_identity_range_or_age_withholds_conversions(address, value):
    raw = healthy(); raw[address] = value
    result = decode_registers(raw)
    assert not result['valid'] and result['problems']
    assert result['vbus_uv'] is None and result['current_ua'] is None
    assert result['raw_registers'][str(address)] == value


def test_unknown_gateware_stops_after_identity_reads():
    addresses = []
    def read(address):
        addresses.append(address)
        return {1: 0x4c554e52, 2: 6}[address]
    with pytest.raises(ValueError, match='not loaded'):
        read_sweep(read)
    assert addresses == [1, 2]


@pytest.mark.parametrize(('raw', 'expected'), [
    (0x0000, 0), (0x0001, 153), (0x7FFF, 4_999_847),
    (0x8000, -5_000_000), (0xFFFF, -153),
])
def test_bipolar_signed_current_endpoints_and_sign(raw, expected):
    registers = healthy()
    registers[6] = raw
    result = decode_registers(registers)
    assert result['valid']
    assert result['current_ua'] == expected
    assert result['current_raw_signed'] == (raw if raw < 0x8000 else raw - 0x1_0000)


def test_status_is_read_last_and_fault_preserved():
    raw = healthy(); addresses = []
    def read(address):
        addresses.append(address)
        return 0x1bd if address == 3 else raw[address]
    result = read_sweep(read)
    assert addresses[-1] == 3
    assert not result['valid'] and result['pac_error_code'] == 11


@pytest.mark.parametrize('value', [-1, 0x100000000, True, 1.0])
def test_non_words_are_rejected(value):
    raw = healthy(); raw[5] = value
    with pytest.raises(ValueError, match='unsigned 32-bit'):
        decode_registers(raw)


def test_missing_register_is_rejected():
    raw = healthy(); del raw[8]
    with pytest.raises(ValueError, match='exactly ten'):
        decode_registers(raw)
