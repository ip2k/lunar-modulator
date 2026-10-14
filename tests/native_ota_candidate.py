"""Sixteen actual-package corruption/output cases; private fixtures, no hardware."""
import argparse
import json
from pathlib import Path
import stat
import struct
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from native import ota_candidate as ota
from inspect_fwsc import inspect, header_decode, crc16
from model_app_replacement import logical, physical, repair_outer, _build


def refuses(fn):
    try:
        fn()
    except (ValueError, OSError, UnicodeError):
        return
    raise AssertionError('Corrupt candidate accepted')


def repair_outer_entry(candidate, entry_index, *, payload=None, mutate_record=None):
    image = logical(candidate)
    offset = 64 + entry_index * 80
    record = bytearray(header_decode(image[offset:offset + 80]))
    if payload is not None:
        struct.pack_into('<H', record, 4, crc16(payload))
    if mutate_record is not None:
        mutate_record(record)
    image[offset:offset + 80] = header_decode(record)
    header = bytearray(header_decode(image[:64]))
    count = struct.unpack_from('<H', header, 8)[0]
    struct.pack_into('<H', header, 2, crc16(image[64:64 + count * 80]))
    struct.pack_into('<H', header, 0, crc16(header[2:]))
    image[:64] = header_decode(header)
    return physical(image, candidate)


def check(root, shard):
    assert 0 <= shard < 18
    raw = (root / 'stock.fwsc').read_bytes()
    app = (root / 'app.bin').read_bytes()
    stock = root / 'stock'
    candidate, receipt = ota.compose(raw, stock, app)
    assert receipt['identity'] == 'FM-1_990'
    assert receipt['replacement']['stock_boot_config_resource_components_unchanged']
    correspondence = receipt['correspondence']
    assert correspondence['nested_full_container_noop']
    assert correspondence['app_identity'] == 'FM-1_990'
    assert correspondence['app_identity_matches_markers']
    assert correspondence['stock_ota_verified']
    assert correspondence['stock_spl_cfg_etc_verified']
    assert correspondence['device_version_acceptance'] is False
    assert correspondence['preserved_component_sha256']['top/uboot.boot'] == ota.digest(
        (root / 'stock/top/uboot.boot').read_bytes())
    assert not any(receipt[k] for k in ('hardware_operations', 'physical_boot_verified',
                                      'recovery_verified', 'web_install_verified', 'release_ready'))
    outer = inspect(candidate, stock)
    entries = {e['name']: e for e in outer['entries']}
    bad = bytearray(candidate)
    if shard == 0:
        bad[7 * 48 + 47] += 1  # syntactically valid but incorrect identity
    elif shard == 1:
        bad[19 * 48 + 47] = 126  # identity padding
    elif shard == 2:
        bad[0] ^= 1
    elif shard == 3:
        bad[64 + 1] ^= 1
    elif shard in (4, 5, 6):
        entry = entries[('flash.bin', 'ota.bin', 'tail.bin')[shard - 4]]
        bad[entry['physical_offset']] ^= 1
    elif shard in (7, 9):
        image = logical(candidate)
        entry = entries['flash.bin']
        flash = bytearray(image[entry['offset']:entry['offset'] + entry['bytes']])
        flash[-1 if shard == 7 else 0xa0] ^= 1
        image[entry['offset']:entry['offset'] + entry['bytes']] = flash
        repair_outer(image, entry['index'], flash)
        bad = physical(image, candidate)  # valid outer CRC; altered protected bytes
    elif shard == 8:
        image = logical(candidate)
        header = bytearray(header_decode(image[:64]))
        header[10] ^= 1
        struct.pack_into('<H', header, 0, crc16(header[2:]))
        image[:64] = header_decode(header)
        bad = physical(image, candidate)  # metadata with valid header CRC
    elif shard == 10:
        altered = bytearray(app); altered[-1] ^= 1
        bad = bytearray(_build(raw, stock, bytes(altered)))
        for index in range(20):
            bad[index * 48 + 47] = candidate[index * 48 + 47]
    elif shard == 11:
        refuses(lambda: ota.compose(raw, stock, app + b'\0'))
        return dict(shard=shard, passed=True, hardware_operations=0)
    elif shard == 12:
        refuses(lambda: ota.compose(raw + b'\0', stock, app))
        return dict(shard=shard, passed=True, hardware_operations=0)
    elif shard == 13:
        bad = candidate[:-1]
    elif shard == 14:
        bad = candidate + b'\0'
    elif shard == 15:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'private'
            ota.emit(output, candidate, receipt)
            assert stat.S_IMODE(output.stat().st_mode) == 0o700
            assert (output / 'lunar-native-controls.fwsc').read_bytes() == candidate
            for name in ('lunar-native-controls.fwsc', 'receipt.json'):
                assert stat.S_IMODE((output / name).stat().st_mode) == 0o600
            assert json.loads((output / 'receipt.json').read_text()) == receipt
            refuses(lambda: ota.emit(output, candidate, receipt))
        return dict(shard=shard, passed=True, hardware_operations=0)
    elif shard == 16:
        entry = entries['ota.bin']
        logical_candidate = logical(candidate)
        payload = bytearray(logical_candidate[entry['offset']:entry['offset'] + entry['bytes']])
        payload[0] ^= 1
        bad = repair_outer_entry(candidate, entry['index'], payload=payload)
    else:
        entry = entries['tail.bin']
        def corrupt_tail_record(record):
            record[6] ^= 1  # syntactically valid outer CRC, unsupported version-record field
        bad = repair_outer_entry(candidate, entry['index'], mutate_record=corrupt_tail_record)
    refuses(lambda: ota.verify(raw, bytes(bad), stock, app))
    return dict(shard=shard, passed=True, hardware_operations=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--shard', type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.inputs, args.shard)))
