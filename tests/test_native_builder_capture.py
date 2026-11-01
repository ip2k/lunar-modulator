# SPDX-License-Identifier: MIT
"""Actual bounded subprocess failures at native builder/preparer seams."""
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools/native' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('failure', ['stdout', 'stderr', 'timeout', 'nonzero'])
def test_builder_refuses_actual_tool_failures_with_bounded_log(tmp_path, monkeypatch, failure):
    builder = load('build_diagnostic')
    monkeypatch.setattr(builder, 'MAX_COMMAND_OUTPUT', 128)
    monkeypatch.setattr(builder, 'COMMAND_TIMEOUT', 0.15)
    script = {'stdout': "print('x'*1024)",
              'stderr': "import sys;sys.stderr.write('x'*1024)",
              'timeout': 'import time;time.sleep(5)',
              'nonzero': 'raise SystemExit(3)'}[failure]
    expected = 'output_limit' if failure in ('stdout', 'stderr') else failure
    if failure == 'nonzero': expected = 'nonzero_exit'
    with (tmp_path / 'build.log').open('w') as log:
        with pytest.raises(RuntimeError, match=expected):
            builder._run_logged([sys.executable, '-c', script], log, True)
    assert (tmp_path / 'build.log').stat().st_size < 1024


def test_builder_preserves_normal_capture_and_non_capture(tmp_path):
    builder = load('build_diagnostic')
    with (tmp_path / 'build.log').open('w') as log:
        assert builder._run_logged([sys.executable, '-c', "print('normal')"], log, True) == 'normal\n'
        assert builder._run_logged([sys.executable, '-c', "print('normal')"], log) is None


@pytest.mark.parametrize('failure', ['stdout', 'stderr', 'timeout', 'nonzero'])
def test_preparer_refuses_actual_tool_failures(tmp_path, monkeypatch, failure):
    prepare = load('prepare_selected_project')
    original = prepare.run_bounded
    def bounded(command, **kwargs):
        assert kwargs['timeout_seconds'] == 90 and kwargs['max_stream_bytes'] == prepare.MAX_META
        return original(command, **(kwargs | dict(timeout_seconds=0.15, max_stream_bytes=128)))
    monkeypatch.setattr(prepare, 'run_bounded', bounded)
    monkeypatch.setattr(prepare, 'MAX_META', 128)
    script = {'stdout': "print('x'*1024)", 'stderr': "import sys;sys.stderr.write('x'*1024)",
              'timeout': 'import time;time.sleep(5)', 'nonzero': 'raise SystemExit(3)'}[failure]
    expected = 'output_limit' if failure in ('stdout', 'stderr') else failure
    if failure == 'nonzero': expected = 'nonzero_exit'
    with pytest.raises(ValueError, match=expected):
        prepare.tool_output(Path(sys.executable), '-c', script)


def test_preparer_returns_exact_stdout():
    prepare = load('prepare_selected_project')
    assert prepare.tool_output(Path(sys.executable), '-c', "import sys;sys.stdout.buffer.write(b'abc\\x00')") == b'abc\0'


def test_executed_capture_helper_is_bound_by_source_manifest(tmp_path, monkeypatch):
    builder = load('build_diagnostic')
    helper = tmp_path / 'tools/installer_service/process_capture.py'
    helper.parent.mkdir(parents=True)
    helper.write_bytes(b'first implementation')
    (helper.parent / '__init__.py').write_bytes(b'package initialization')
    monkeypatch.setattr(builder, 'ROOT', tmp_path)
    first = builder.manifest(True)
    helper.write_bytes(b'changed implementation')
    second = builder.manifest(True)
    key = 'tools/installer_service/process_capture.py'
    assert first[key] != second[key]
    init_key = 'tools/installer_service/__init__.py'
    assert first[init_key] == second[init_key]
    (helper.parent / '__init__.py').write_bytes(b'changed package initialization')
    assert builder.manifest(True)[init_key] != second[init_key]
