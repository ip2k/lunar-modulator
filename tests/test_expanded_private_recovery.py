"""Optional real-candidate bytes in persistent simulation; no physical transport."""
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/native'))
import expanded_candidate
from tests.test_expanded_flash_recovery import exercise_recovery


@pytest.fixture(scope='module')
def private_candidate():
    name = os.environ.get('FM1_PRIVATE_EXPANDED_INPUTS')
    if not name:
        pytest.skip('Private stock/artifact inputs required; never commit them')
    root = Path(name)
    baseline = (root / 'stockA.bin').read_bytes()
    other = (root / 'stockB.bin').read_bytes()
    app = (root / 'app.bin').read_bytes()
    reference = root / 'reference'
    target, receipt = expanded_candidate.construct(
        baseline, other, json.loads((root / 'manifest.json').read_bytes()),
        json.loads((root / 'identity.json').read_bytes()), reference, app,
        (root / 'app.elf').read_bytes(), 'fixed-loader',
        (root / 'disassembly.txt').read_text(), 'combined')
    assert target == (root / 'target.bin').read_bytes()
    assert receipt['elf_verified'] and receipt['provenance_verified']
    return baseline, target, reference, app


@pytest.mark.parametrize('direction', ['install', 'restore'])
@pytest.mark.parametrize('fault', ['erase-torn', 'program-torn', 'program-ack', 'commit-erase'])
@pytest.mark.parametrize('after_bytes', [1, 127, 255, 256])
def test_actual_candidate_recovery(private_candidate, tmp_path, direction, fault, after_bytes):
    exercise_recovery(*private_candidate, tmp_path, direction, fault, after_bytes)
