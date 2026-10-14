"""Actual private-image admission checks with mocked discovery/opener."""
import os
from pathlib import Path
import pytest
from tests.expanded_bench_live import campaign


@pytest.mark.parametrize('shard', range(16))
def test_expanded_live_admission(shard):
    name = os.environ.get('FM1_PRIVATE_FRESH_EXPANDED_INPUTS')
    if not name:
        pytest.skip('Private device36 and candidate inputs required')
    result = campaign(Path(name), shard)
    assert result['passed'] and result['hardware_operations'] == 0
