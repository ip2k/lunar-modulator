"""Refuse incomplete or incorrectly pinned CPU1 captures before further tests."""
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cpu1_result', ROOT / 'tools/devkit_cpu1_result.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
CAPTURE = (b'UART vendor startup\n'
           b'LUNAR_CPU1 timer_check_ticks=2400000 delay_os_ticks=10 rounds=4096 words=64\n'
           b'LUNAR_CPU1 complete=4096 errors=0 abort=0 exited=1 ticks=5000000 '
           b'parent0=4096 parent1=0 parent_other=0 worker0=0 worker1=4096 worker_other=0 '
           b'worker_stack_unused_words=700 stack_unused_words=1700\n')


def test_valid_short_capture_is_not_full_acceptance():
    result = module.parse(CAPTURE)
    assert result['short_publication_and_pinning_pass']
    assert 'gates remain' in result['acceptance']


def test_sdk_timestamped_receipts_preserve_validation():
    stamped = CAPTURE.replace(b'LUNAR_CPU1', b'[00:00:03.382]LUNAR_CPU1')
    assert module.parse(stamped) == module.parse(CAPTURE)
    for invalid in (stamped + CAPTURE,
                    stamped.replace(b'errors=0', b'errors=1'),
                    stamped.replace(b'[00:00:03.382]', b'quoted: ')):
        with pytest.raises(ValueError):
            module.parse(invalid)


@pytest.mark.parametrize('before,after', [
    (b'complete=4096', b'complete=4095'), (b'errors=0', b'errors=1'),
    (b'abort=0', b'abort=1'), (b'exited=1', b'exited=0'),
    (b'worker0=0 worker1=4096', b'worker0=1 worker1=4095'),
    (b'parent0=4096 parent1=0', b'parent0=4095 parent1=1'),
    (b'timer_check_ticks=2400000', b'timer_check_ticks=200000'),
    (b'rounds=4096', b'rounds=4095'), (b'words=64', b'words=63'),
    (b'stack_unused_words=1700', b'stack_unused_words=0'),
    (b'worker_stack_unused_words=700', b'worker_stack_unused_words=1024'),
    (b'ticks=5000000', b'ticks=4294967295'),
    (b'errors=0', b'errors=0 errors=1'), (b'exited=1', b'exited=bad'),
])
def test_corruption_timeout_pinning_and_missing_fields_refused(before, after):
    with pytest.raises(ValueError):
        module.parse(CAPTURE.replace(before, after))


def test_truncated_duplicate_and_error_captures_refused():
    for capture in (CAPTURE[:100], CAPTURE + CAPTURE, CAPTURE + b'LUNAR_CPU1 error=parent_core\n'):
        with pytest.raises(ValueError):
            module.parse(capture)
