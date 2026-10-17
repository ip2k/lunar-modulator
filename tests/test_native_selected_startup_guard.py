"""Exercise the real CLI guard before any target compilation or toolchain IO."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/native'))
import build_application_probe as builder


class PastStartupGuard(Exception):
    pass


@pytest.mark.parametrize('selected', [['macro'], ['shapes'], ['macro', 'shapes']])
@pytest.mark.parametrize('mode,startup,accepted', [
    ('continuous', 0, True),
    ('continuous', None, False),
    ('diagnostic', 0, False),
    ('song-diagnostic', 0, False),
])
def test_selected_project_startup_reaches_toolchain_only_in_continuous_mode(
        monkeypatch, tmp_path, selected, mode, startup, accepted):
    header = b'selected-module-header'
    prepared = SimpleNamespace(module_header=header, report={
        'module_selection': {'selected': selected},
        'content': [{'kind': 'project'}],
    })
    monkeypatch.setattr(builder, 'load_prepared_profile', lambda *a: prepared)
    monkeypatch.setattr(builder, 'builder_content_parent_indices', lambda *a: (None, None))
    monkeypatch.setattr(builder, 'content_source', lambda *a, **kw: {})
    monkeypatch.setattr(builder, 'resolve_modules', lambda *a: (header, {'selected': selected}))

    def stop_before_toolchain(*args):
        raise PastStartupGuard

    monkeypatch.setattr(builder, 'check_pins', stop_before_toolchain)
    argv = ['build_application_probe.py', '--toolchain', str(tmp_path / 'tc'),
            '--catalogue', str(tmp_path / 'catalogue'), '--build', str(tmp_path / 'out'),
            '--runtime-mode', mode, '--prepared-profile', str(tmp_path / 'prepared'),
            '--expected-profile-sha256', 'a' * 64]
    if startup is not None:
        argv += ['--link-project-loader', '--startup-project-index', str(startup)]
    monkeypatch.setattr(sys, 'argv', argv)
    if accepted:
        with pytest.raises(PastStartupGuard):
            builder.main()
    else:
        with pytest.raises(SystemExit) as error:
            builder.main()
        assert error.value.code == 2
