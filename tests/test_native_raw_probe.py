"""Native layout and existing protected NOR geometry, using synthetic bytes."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/native'))
import raw_probe
from tests.test_native_probe_artifact import fixture
from tests.test_raw_flash_profile import sample  # noqa: F401


def construct(s, **changes):
    elf = fixture()
    _, app = raw_probe.flatten(elf)
    args = dict(baseline_a=s['baseline'], baseline_b=s['baseline'], manifest=s['manifest'],
                identity=s['identity'], reference=s['reference'], app=app, elf=elf)
    args.update(changes)
    return raw_probe.construct(**args)


def test_native_candidate_preserves_protected_bytes(sample):
    target, receipt = construct(sample)
    raw = raw_probe.raw
    assert target[:raw.APP_BASE] == sample['baseline'][:raw.APP_BASE]
    assert target[raw.CFG_OFFSET:] == sample['baseline'][raw.CFG_OFFSET:]
    assert receipt['diagnostic_profile'] == 'native-trio-private'
    assert receipt['link_audit']['runtime'] == 'sdk-free'
    assert receipt['layout_passed']
    assert not receipt['hardware_approval'] and not receipt['physical_writer_ready']
    assert not receipt['installable']


@pytest.mark.parametrize('change', [dict(app=b'wrong'), dict(elf=b'bad'),
                                    dict(baseline_profile='sdk'), dict(baseline_b=b'bad')])
def test_candidate_rejects_unbound_inputs(sample, change):
    with pytest.raises((ValueError, IndexError)):
        construct(sample, **change)
