"""Private all13 model replay and boot refusal tests; no physical I/O."""
import os
from pathlib import Path
import pytest
from expanded_install_proof_model import check as proof_check
from expanded_boot_model import check as boot_check

@pytest.mark.parametrize('shard',range(16))
@pytest.mark.parametrize('kind',['proof','boot'])
def test_expanded_model_evidence(kind,shard):
    name=os.environ.get('FM1_PRIVATE_EXPANDED_PROOF_MODEL')
    if not name:pytest.skip('Private simulated installation transcript required')
    result=(proof_check if kind=='proof' else boot_check)(Path(name),shard)
    assert result['passed'] and result['hardware_operations']==0
