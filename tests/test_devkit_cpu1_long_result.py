"""Long publication gate rejects false success; no private firmware fixtures."""
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cpu1_long', ROOT/'tools/devkit_cpu1_long_result.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
CAPTURE = (
    b'[00:00:03.220]LUNAR_CPU1_LONG timer_check_ticks=2400058 delay_os_ticks=10 rounds=100000000 budget_ticks=3840000000\n'
    b'[00:00:30.220]LUNAR_CPU1_LONG phase=0 complete=100000000 errors=2\n'
    b'[00:01:00.220]LUNAR_CPU1_LONG phase=1 complete=100000000 errors=0\n'
    b'[00:01:00.220]LUNAR_CPU1_LONG complete_unfenced=100000000 complete_fenced=100000000 '
    b'parent_errors_unfenced=2 parent_errors_fenced=0 worker_errors_unfenced=3 worker_errors_fenced=0 '
    b'abort=0 exited=1 ticks=1400000000 parent0=200000000 parent1=0 parent_other=0 '
    b'worker0=0 worker1=200000000 worker_other=0 worker_stack_unused_words=994 stack_unused_words=1900\n')


def test_long_publication_is_not_audio_acceptance():
    result = module.parse(CAPTURE)
    assert result['long_publication_pass']
    assert result['result']['worker_errors_unfenced'] == 3
    assert 'gates remain' in result['acceptance']
    assert module.parse(CAPTURE.replace(b'parent_errors_unfenced=2', b'parent_errors_unfenced=0')
                        .replace(b'errors=2', b'errors=0'))['long_publication_pass']


@pytest.mark.parametrize('before,after', [
    (b'rounds=100000000', b'rounds=99999999'),
    (b'complete_fenced=100000000', b'complete_fenced=99999999'),
    (b'parent_errors_fenced=0', b'parent_errors_fenced=1'),
    (b'worker_errors_fenced=0', b'worker_errors_fenced=1'),
    (b'parent_errors_unfenced=2', b'parent_errors_unfenced=1'),
    (b'worker_errors_unfenced=3', b'worker_errors_unfenced=bad'),
    (b'abort=0', b'abort=1'), (b'exited=1', b'exited=0'),
    (b'parent0=200000000', b'parent0=199999999'),
    (b'worker1=200000000', b'worker1=199999999'),
    (b'ticks=1400000000', b'ticks=3840000000'),
    (b'timer_check_ticks=2400058', b'timer_check_ticks=3000001'),
    (b'worker_stack_unused_words=994', b'worker_stack_unused_words=0'),
    (b'stack_unused_words=1900', b'stack_unused_words=2048'),
    (b'exited=1', b'exited=1 exited=0'),
])
def test_invalid_long_receipt_refused(before, after):
    with pytest.raises(ValueError):
        module.parse(CAPTURE.replace(before, after))


def test_incomplete_duplicate_and_explicit_failure_refused():
    for data in (CAPTURE[:200], CAPTURE+CAPTURE,
                 CAPTURE+b'LUNAR_CPU1_LONG error=timer_busy\n',
                 CAPTURE.replace(b'[00:01:00.220]', b'quoted: ')):
        with pytest.raises(ValueError):
            module.parse(data)
