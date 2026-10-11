"""Offline construction uses independent fixtures; no vendor data or USB."""
import json
import os
from pathlib import Path
import stat
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/jieli'))
import build_raw_diagnostic as builder  # noqa: E402
from tests.test_raw_flash_profile import sample  # noqa: E402,F401


def construct(s, **changes):
    args = dict(baseline_a=s['baseline'], baseline_b=s['baseline'],
                manifest=s['manifest'], identity=s['identity'],
                reference=s['reference'], app=s['app'], elf=s['elf'])
    args.update(changes)
    return builder.construct(**args)


def test_construct_matches_independently_built_target_and_preserves_stock(sample):
    target, receipt = construct(sample)
    assert target == sample['target']
    assert len(target) == builder.raw.FLASH_BYTES
    assert receipt['allowed_sectors'] == [0x4000]
    assert receipt['original_app_tail_identical']
    assert receipt['protected_raw_bytes_identical']
    assert not receipt['hardware_approval'] and not receipt['physical_writer_ready']
    assert not receipt['hardware_validated'] and not receipt['binary_emitted']


@pytest.mark.parametrize('changes', [dict(app=b''), dict(app=bytearray(b'a')),
                                   dict(app=bytes(builder.raw.APP_BYTES + 1)),
                                   dict(elf=bytes(64)), dict(diagnostic_profile='sdk')])
def test_bad_candidate_cannot_be_constructed(sample, changes):
    with pytest.raises(ValueError):
        construct(sample, **changes)


def test_output_is_private_complete_and_refuses_existing_directory(sample, tmp_path):
    target, receipt = construct(sample)
    directory = tmp_path / 'private'
    saved = builder.emit(directory, target, receipt)
    assert saved['binary_emitted'] and receipt['binary_emitted'] is False
    assert (directory / 'target.bin').read_bytes() == sample['target']
    assert json.loads((directory / 'receipt.json').read_bytes()) == saved
    assert directory.stat().st_mode & 0o777 == 0o700
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in directory.iterdir())
    with pytest.raises(FileExistsError):
        builder.emit(directory, target, receipt)
    assert (directory / 'target.bin').read_bytes() == target


def test_emit_refuses_unbound_target_before_creating_directory(sample, tmp_path):
    target, receipt = construct(sample)
    directory = tmp_path / 'absent'
    with pytest.raises(ValueError):
        builder.emit(directory, target[:-1] + b'!', receipt)
    assert not directory.exists()


def test_interrupted_output_has_no_completion_receipt_and_cannot_be_overwritten(sample, tmp_path, monkeypatch):
    target, receipt = construct(sample)
    directory = tmp_path / 'partial'
    save = builder._save
    def interrupted(path, data):
        if path.name == '.receipt.json.pending':
            raise OSError('interrupted before completion marker')
        save(path, data)
    monkeypatch.setattr(builder, '_save', interrupted)
    with pytest.raises(OSError):
        builder.emit(directory, target, receipt)
    assert (directory / 'target.bin').is_file()
    assert not (directory / 'receipt.json').exists()
    with pytest.raises(FileExistsError):
        builder.emit(directory, target, receipt)


@pytest.mark.parametrize('failure', ['partial-write', 'receipt-fsync'])
def test_failed_receipt_write_never_publishes_final_marker(sample, tmp_path, monkeypatch, failure):
    target, receipt = construct(sample)
    directory = tmp_path / failure
    if failure == 'partial-write':
        save = builder._save
        def interrupted(path, data):
            if path.name == '.receipt.json.pending':
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(data[:5])
                raise OSError('interrupted while writing receipt')
            save(path, data)
        monkeypatch.setattr(builder, '_save', interrupted)
    else:
        fsync = os.fsync
        def interrupted(fd):
            info = os.fstat(fd)
            if stat.S_ISREG(info.st_mode) and 0 < info.st_size < builder.raw.FLASH_BYTES:
                raise OSError('receipt fsync failed')
            fsync(fd)
        monkeypatch.setattr(builder.os, 'fsync', interrupted)
    with pytest.raises(OSError):
        builder.emit(directory, target, receipt)
    assert (directory / 'target.bin').read_bytes() == target
    assert (directory / '.receipt.json.pending').exists()
    assert not (directory / 'receipt.json').exists()
    with pytest.raises(FileExistsError):
        builder.emit(directory, target, receipt)


def test_cli_checks_candidate_before_creating_output(sample, tmp_path, monkeypatch, capsys):
    s = sample
    for name in ('baseline', 'app', 'elf'):
        (tmp_path / name).write_bytes(s[name])
    for name in ('manifest', 'identity'):
        (tmp_path / name).write_text(json.dumps(s[name]))
    directory = tmp_path / 'result'
    argv = ['build_raw_diagnostic', '--baseline-a', str(tmp_path / 'baseline'),
            '--baseline-b', str(tmp_path / 'baseline'), '--app', str(tmp_path / 'app'),
            '--elf', str(tmp_path / 'elf'), '--manifest', str(tmp_path / 'manifest'),
            '--identity', str(tmp_path / 'identity'), '--reference', str(s['reference']),
            '--out', str(directory)]
    monkeypatch.setattr(sys, 'argv', argv + ['--diagnostic-profile', 'unknown'])
    with pytest.raises(ValueError):
        builder.main()
    assert not directory.exists()
    monkeypatch.setattr(sys, 'argv', argv)
    builder.main()
    assert json.loads(capsys.readouterr().out)['binary_emitted'] is True
    assert (directory / 'target.bin').read_bytes() == s['target']
