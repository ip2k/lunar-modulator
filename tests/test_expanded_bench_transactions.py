"""Protected physical boundaries of the offline device36 preparation."""
import pytest
import os
from pathlib import Path

from tools.native.expanded_bench_transactions import (
    APP_BASE, AREA_END, FLASH_BYTES, SECTOR, changed_ranges,
    BASELINE_SHA, TARGET_SHA, STOCK_SHA, pinned, prepare)


def changed(*addresses):
    image = bytearray(b'\xff' * FLASH_BYTES)
    for address in addresses:
        image[address] = 0
    return bytes(image)


def test_changed_union_includes_last_app_sector_without_touching_vm():
    assert changed_ranges(changed(), changed(APP_BASE, APP_BASE + SECTOR,
                                            AREA_END - 1)) == [
        [APP_BASE, APP_BASE + 2 * SECTOR], [AREA_END - SECTOR, AREA_END]]


@pytest.mark.parametrize('address', [0, APP_BASE - 1, AREA_END, FLASH_BYTES - 1])
def test_protected_byte_changes_refused(address):
    with pytest.raises(ValueError, match='Protected'):
        changed_ranges(changed(), changed(APP_BASE, address))


@pytest.mark.parametrize('image', [b'', b'\xff' * (FLASH_BYTES - 1)])
def test_partial_flash_refused(image):
    with pytest.raises(ValueError, match='Complete'):
        changed_ranges(image, changed(APP_BASE))


@pytest.mark.parametrize('addresses', [(), (APP_BASE + SECTOR,)])
def test_missing_changed_directory_refused(addresses):
    with pytest.raises(ValueError, match='directory'):
        changed_ranges(changed(), changed(*addresses))


@pytest.fixture(scope='module')
def private_fresh_candidate(tmp_path_factory):
    name = os.environ.get('FM1_PRIVATE_FRESH_EXPANDED_INPUTS')
    if not name:
        pytest.skip('Private fresh device36 and stock inputs required')
    root = Path(name)
    output = tmp_path_factory.mktemp('device36') / 'plans'
    report = prepare(output, root / 'fresh', root / 'target.bin',
                     root / 'stockA.bin', root / 'stockB.bin')
    assert not report['hardware_admitted'] and not report['physical_writer_ready']
    return (pinned(root / 'fresh/dumpA.bin', BASELINE_SHA),
            pinned(root / 'target.bin', TARGET_SHA), root / 'reference',
            (root / 'app.bin').read_bytes(), pinned(root / 'stockA.bin', STOCK_SHA))


@pytest.mark.parametrize('direction', ['install', 'restore'])
@pytest.mark.parametrize('fault', ['erase-torn', 'program-torn', 'program-ack', 'commit-erase'])
@pytest.mark.parametrize('after_bytes', [1, 127, 255, 256])
def test_fresh_trio_to_full_candidate_recovery(private_fresh_candidate, tmp_path,
                                             direction, fault, after_bytes):
    from tests.test_expanded_flash_recovery import exercise_recovery
    baseline, target, reference, app, stock = private_fresh_candidate
    exercise_recovery(baseline, target, reference, app, tmp_path, direction, fault,
                      after_bytes, geometry_baseline=stock)
