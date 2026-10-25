"""Fault sensitivity of the public result gate; no vendor fixtures."""
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cpu1_ring', ROOT/'tools/devkit_cpu1_ring_result.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
CAPTURE = (
    '[00:00:03.220]LUNAR_CPU1_RING timer_check_ticks=2400021 delay_os_ticks=10 blocks=413607 frames=64 rate=44118 capacity=16 budget_ms=625000\n' +
    ''.join(f'[00:00:04.000]LUNAR_CPU1_RING fpu_op={op} parent_bits={bits} worker_bits={bits} parent_batches=8 worker_batches=8 iterations=1024 parent_ticks=50000 worker_ticks=60000\n'
            for op, bits in enumerate([1025, 0x40000000, 0x402df9fa, 0x3ebc6bf8])) +
    '[00:10:04.000]LUNAR_CPU1_RING complete=413607 consumed=413607 bad_crc=0 bad_data=0 bad_sequence=0 abort=0 exited=1 elapsed_ms=600000 parent0=413607 parent1=0 parent_other=0 worker0=0 worker1=413607 worker_other=0 peak_depth=2 late_blocks=0 max_late_ticks=4000 worker_stack_unused_words=900 stack_unused_words=1800\n'
).encode()


def test_ring_is_not_audio_or_irq_acceptance():
    result = module.parse(CAPTURE)
    assert result['paced_ring_pass']
    assert 'gates remain' in result['acceptance']


@pytest.mark.parametrize('before,after', [
    (b'blocks=413607', b'blocks=413606'), (b'rate=44118', b'rate=44100'),
    (b'complete=413607', b'complete=413606'), (b'consumed=413607', b'consumed=413606'),
    (b'bad_crc=0', b'bad_crc=1'), (b'bad_data=0', b'bad_data=1'),
    (b'bad_sequence=0', b'bad_sequence=1'), (b'abort=0', b'abort=1'),
    (b'exited=1', b'exited=0'), (b'parent0=413607', b'parent0=413606'),
    (b'worker1=413607', b'worker1=413606'), (b'late_blocks=0', b'late_blocks=1'),
    (b'elapsed_ms=600000', b'elapsed_ms=599980'), (b'elapsed_ms=600000', b'elapsed_ms=600060'),
    (b'max_late_ticks=4000', b'max_late_ticks=34815'), (b'peak_depth=2', b'peak_depth=17'),
    (b'worker_stack_unused_words=900', b'worker_stack_unused_words=0'),
    (b'stack_unused_words=1800', b'stack_unused_words=2048'),
    (b'worker_bits=1025', b'worker_bits=1026'),
    (b'parent_bits=1025 worker_bits=1025', b'parent_bits=1026 worker_bits=1026'),
    (b'parent_batches=8', b'parent_batches=7'), (b'iterations=1024', b'iterations=1023'),
    (b'parent_ticks=50000', b'parent_ticks=0'),
    (b'parent_bits=1073741824 worker_bits=1073741824', b'parent_bits=2139095040 worker_bits=2139095040'),
    (b'timer_check_ticks=2400021', b'timer_check_ticks=3000001'),
    (b'exited=1', b'exited=1 exited=0'),
])
def test_false_success_refused(before, after):
    assert before in CAPTURE
    with pytest.raises(ValueError):
        module.parse(CAPTURE.replace(before, after))


def test_missing_duplicate_quoted_and_error_receipts_refused():
    for data in (CAPTURE[:200], CAPTURE + CAPTURE,
                 CAPTURE.replace(b'[00:10:04.000]', b'quoted: '),
                 CAPTURE + b'LUNAR_CPU1_RING error=timer_busy\n'):
        with pytest.raises(ValueError): module.parse(data)


def test_phase_diagnostics_cannot_override_failed_pacing():
    diagnostic = b'LUNAR_CPU1_RING_PHASE producer_compute_blocks=413607 producer_compute_ticks=1 producer_compute_max=1 start_lag_max=1 worst_start_lag=1 worst_compute_ticks=1 worker_compute_blocks=413607 worker_compute_ticks=1 worker_compute_max=1\n'
    assert module.parse(CAPTURE + diagnostic)['paced_ring_pass']
    with pytest.raises(ValueError, match='late'):
        module.parse(CAPTURE.replace(b'late_blocks=0', b'late_blocks=1') + diagnostic)
