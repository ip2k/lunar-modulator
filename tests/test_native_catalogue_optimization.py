"""Mixed optimization is explicit, source-bound and checked at object granularity."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/native'))
import compile_catalogue as compiler
import build_application_probe as builder


def test_profile_is_narrow_and_requires_size_base():
    assert compiler.optimization_overrides('s') == {}
    assert compiler.optimization_overrides('z') == {}
    assert compiler.optimization_overrides('z', True) == {
        'our/src/mi_sixop.o': '-Os', 'our/src/fx_hall.o': '-Os'}
    with pytest.raises(ValueError, match='-Oz base'):
        compiler.optimization_overrides('s', True)
    with pytest.raises(TypeError):
        compiler.optimization_overrides('z', 1)


@pytest.mark.parametrize('enabled', (False, True))
def test_compiler_records_settings_actually_passed_to_make(tmp_path, monkeypatch, enabled):
    headers = tmp_path / 'headers'
    headers.mkdir()
    (headers / '__config').write_text('#define _LIBCPP_HAS_THREAD_API_PTHREAD\n')
    out = tmp_path / 'out'
    names = ['our/src/mi_sixop.o'] + [f'c/unit-{i}.o' for i in range(15)] + [
        'our/src/fx_hall.o'] + [f'c/unit-{i}.o' for i in range(16, 31)] + [
        'c/unchanged.o']
    calls = []

    def check_output(command, **kwargs):
        if command[-1] == 'print-objs':
            return '\n'.join(str(out / 'obj' / name) for name in names)
        return ''  # nm undefined-symbol inspection

    def run(command, **kwargs):
        calls.append(command)
        obj = Path(command[-1])
        obj.parent.mkdir(parents=True, exist_ok=True)
        obj.write_bytes(command[-2].encode())
        return subprocess.CompletedProcess(command, 0, '', '')

    monkeypatch.setattr(compiler, 'source_manifest', lambda root: {'x.c': 'current'})
    monkeypatch.setattr(compiler.subprocess, 'check_output', check_output)
    monkeypatch.setattr(compiler.subprocess, 'run', run)
    monkeypatch.setattr(sys, 'argv', ['compile_catalogue', '--toolchain', str(tmp_path),
                        '--cxx-headers', str(headers), '--out', str(out), '--shard', '0',
                        '--opt', 'z', *(['--hot-dsp-os'] if enabled else [])])
    assert compiler.main() == 0
    report = json.loads((out / 'report.json').read_text())
    overrides = compiler.optimization_overrides('z', enabled)
    assert report['optimization_overrides'] == overrides
    assert len(calls) == len(report['results']) == 3
    for command, item in zip(calls, report['results']):
        expected = overrides.get(item['object'], '-Oz')
        assert command[-2] == 'OPT=' + expected
        assert item['optimization'] == expected
        assert item['sha256'] == hashlib.sha256(command[-2].encode()).hexdigest()


@pytest.mark.parametrize('fault', ('none', 'missing-map', 'extra-map', 'missing-unit',
                                  'wrong-hot-unit', 'wrong-cold-unit'))
def test_linker_requires_matching_explicit_receipts(tmp_path, monkeypatch, fault):
    monkeypatch.setattr(builder, 'source_manifest', lambda root: {'x.c': 'current'})
    names = ['our/src/mi_sixop.o', 'our/src/fx_hall.o'] + [
        f'c/unit-{i}.o' for i in range(14)]
    overrides = compiler.optimization_overrides('z', True)
    for shard, name in enumerate(names):
        directory = tmp_path / f'shard-{shard:02d}'
        (directory / 'obj' / name).parent.mkdir(parents=True)
        (directory / 'obj' / name).write_bytes(b'object')
        (directory / 'cxx').mkdir()
        (directory / 'cxx/__config').write_bytes(b'config')
        (directory / 'objects.json').write_text(json.dumps(names))
        report = dict(shard=shard, chunks=16, catalogue_objects=16,
                      gpl_mods=1, modules='all', optimization='-Oz', lto=True,
                      optimization_overrides=dict(overrides), shared_resampler=True,
                      indexed_tft=False, shapes_voices=12, closed_sdk_archives=[],
                      device_sdk_headers=[], source_manifest={'x.c': 'current'},
                      configured_sha256=hashlib.sha256(b'config').hexdigest(),
                      results=[dict(index=shard, object=name, exit=0,
                                    optimization=overrides.get(name, '-Oz'),
                                    sha256=hashlib.sha256(b'object').hexdigest())])
        if shard == 0:
            if fault == 'missing-map': del report['optimization_overrides']
            if fault == 'extra-map': report['optimization_overrides']['c/other.o'] = '-Os'
            if fault == 'missing-unit': del report['results'][0]['optimization']
            if fault == 'wrong-hot-unit': report['results'][0]['optimization'] = '-Oz'
        if shard == 2 and fault == 'wrong-cold-unit':
            report['results'][0]['optimization'] = '-Os'
        (directory / 'report.json').write_text(json.dumps(report))
    # A mixed catalogue is never silently accepted by the default builder.
    with pytest.raises(SystemExit):
        builder.checked_catalogue(tmp_path)
    if fault != 'none':
        with pytest.raises(SystemExit):
            builder.checked_catalogue(tmp_path, hot_dsp_os=True)
    else:
        objects, receipts = builder.checked_catalogue(tmp_path, hot_dsp_os=True)
        assert len(objects) == len(receipts) == 16
        assert [r['optimization'] for r in receipts] == ['-Os', '-Os'] + ['-Oz'] * 14
