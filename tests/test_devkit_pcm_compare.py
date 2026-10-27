"""Reject incomplete and inconsistent target evidence, using synthetic logs."""
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

spec = importlib.util.spec_from_file_location(
    'pcm_compare', Path(__file__).parents[1] / 'tools/devkit_pcm_compare.py')
pcm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pcm)


def row(n, case=None, value='0123abcd'):
    return f'LUNAR_PCM completed={n} case={(n-1)%12 if case is None else case} fnv1a={value}\n'


def test_uart_prefixes_repeated_snapshots_and_bounded_comparison():
    reference = ''.join(row(n) for n in range(1, 25))
    target = 'boot unrelated\n' + row(0, 0)
    target += ''.join('[00:01]'+row(n)+'[00:02]'+row(n) for n in range(1, 26))
    result = pcm.compare(reference, target)
    assert result['completed_pcm_comparison_passed']
    assert result['matched_cases'] == 24
    assert result['later_target_cases_not_compared'] == 1
    assert not result['certifies_analog_audio']
    assert not result['certifies_full_workload']


@pytest.mark.parametrize('fault', ['empty', 'startup', 'missing', 'hash', 'case',
                                 'conflict', 'regression', 'truncated', 'malformed'])
def test_bad_evidence_is_never_accepted(fault):
    reference = ''.join(row(n) for n in range(1, 25))
    target = reference
    if fault == 'empty': target = ''
    if fault == 'startup': target = row(0, 0)
    if fault == 'missing': target = reference.replace(row(13), '')
    if fault == 'hash': target = reference.replace(row(13), row(13, value='deadbeef'))
    if fault == 'case': target = reference.replace(row(13), row(13, case=2))
    if fault == 'conflict': target = reference.replace(row(13), row(13)+row(13, value='deadbeef'))
    if fault == 'regression': target = reference.replace(row(13)+row(14), row(14)+row(13))
    if fault == 'truncated': target = reference[:-6]
    if fault == 'malformed': target = reference+'LUNAR_PCM broken\n'
    result = pcm.compare(reference, target)
    assert not result['completed_pcm_comparison_passed']
    if fault == 'hash': assert result['mismatched_completed'] == [13]
    if fault == 'missing': assert result['missing_completed'] == [13]
    if fault in ('case', 'conflict', 'regression', 'truncated', 'malformed'):
        assert result['errors']


@pytest.mark.parametrize('reference', ['', row(1), row(2), row(1)+row(3), row(1, case=12)])
def test_reference_must_itself_be_complete(reference):
    assert not pcm.compare(reference, row(1)+row(2)+row(3))['completed_pcm_comparison_passed']


def test_cli_has_failing_exit_status_for_missing_evidence(tmp_path):
    reference = tmp_path/'host.log'
    target = tmp_path/'uart.bin'
    reference.write_text(''.join(row(n) for n in range(1, 25)))
    target.write_text(reference.read_text())
    command = [sys.executable, str(Path(pcm.__file__)), '--reference', str(reference),
               '--uart', str(target)]
    good = subprocess.run(command, capture_output=True, text=True)
    assert good.returncode == 0, good.stderr
    assert 'reference_sha256' in good.stdout and 'uart_sha256' in good.stdout
    target.write_text(row(1))
    bad = subprocess.run(command, capture_output=True, text=True)
    assert bad.returncode == 1
    assert '"completed_pcm_comparison_passed": false' in bad.stdout
