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


@pytest.mark.parametrize('enabled', (False, True))
def test_compiler_hot_dsp_ram_flag_is_receipted_and_applied(tmp_path, monkeypatch, enabled):
    headers = tmp_path / 'headers'
    headers.mkdir()
    (headers / '__config').write_text('#define _LIBCPP_HAS_THREAD_API_PTHREAD\n')
    out = tmp_path / 'out'
    names = [f'c/unit-{i}.o' for i in range(16)]
    calls = []

    def check_output(command, **kwargs):
        return '\n'.join(str(out / 'obj' / name) for name in names) if command[-1] == 'print-objs' else ''

    def run(command, **kwargs):
        calls.append(command)
        obj = Path(command[-1])
        obj.parent.mkdir(parents=True, exist_ok=True)
        obj.write_bytes(b'obj')
        return subprocess.CompletedProcess(command, 0, '', '')

    monkeypatch.setattr(compiler, 'source_manifest', lambda root: {'x.c': 'current'})
    monkeypatch.setattr(compiler.subprocess, 'check_output', check_output)
    monkeypatch.setattr(compiler.subprocess, 'run', run)
    monkeypatch.setattr(sys, 'argv', ['compile_catalogue', '--toolchain', str(tmp_path),
                        '--cxx-headers', str(headers), '--out', str(out), '--shard', '0',
                        '--hot-dsp-ram'] if enabled else ['compile_catalogue', '--toolchain', str(tmp_path),
                        '--cxx-headers', str(headers), '--out', str(out), '--shard', '0'])
    assert compiler.main() == 0
    report = json.loads((out / 'report.json').read_text())
    assert report['hot_dsp_ram'] is enabled
    assert all(('FM1_HOT_DSP_RAM=1' in ' '.join(map(str, command))) is enabled
               for command in calls)


@pytest.mark.parametrize('enabled', (False, True))
def test_hot_dsp_linker_template_is_opt_in(enabled):
    source = (Path(builder.__file__).resolve().parents[2] / 'firmware/native/app.ld').read_text()
    generated = builder.hot_dsp_ram_linker_script(source, enabled)
    assert ('.ram_dsp' in generated) is enabled
    if not enabled:
        assert hashlib.sha256(generated.encode()).hexdigest() == (
            '833d79ca882336b4d61b2a977e6b4e13b5aed99e26fa21423fceb0b58ca0f16b')
        assert 'HOT_DSP_RAM_' not in generated
        assert 'ramdsp PT_LOAD' not in generated
        assert '_rd_' not in generated
    else:
        assert 'HOT_DSP_RAM_' not in generated
        assert 'ramdsp PT_LOAD FLAGS(5);' in generated
        assert '_rd_start >= _rt_end' in generated


def test_hot_dsp_ram_extent_reports_exact_linked_bounds(tmp_path):
    from test_native_probe_artifact import fixture
    elf = tmp_path / 'synthetic.elf'
    elf.write_bytes(fixture(hot_dsp_ram=True))
    assert builder.hot_dsp_ram_extent(elf) == dict(
        section='.ram_dsp', start='0x01c00004', end='0x01c00008',
        bytes=4, flash_load='0x02000170')


def test_hot_dsp_ram_requires_bounded_runtime_and_copies_extent_at_startup():
    with pytest.raises(ValueError, match='bounded diagnostic'):
        builder.hot_dsp_ram_configuration(True, 'continuous')
    receipt = builder.hot_dsp_ram_configuration(True, 'diagnostic')
    assert receipt['selected_bodies'] == builder.HOT_DSP_RAM_BODIES
    assert 'SixOp::Instance::RenderBlock' in receipt['selected_bodies']
    assert 'plaits::FMVoice::Render' in receipt['selected_bodies']
    assert 'plaits::fm::Voice<6>::Render(Parameters,float**,size_t)' in receipt['selected_bodies']
    assert receipt['all_callees_in_ram'] is False
    disabled = builder.hot_dsp_ram_configuration(False, 'continuous')
    assert disabled['enabled'] is False
    assert disabled['selected_bodies'] == []
    platform = ('    extern uint32_t _pool_start[], _pool_end[], _rt_start[], _rt_end[], _rt_load[];\n'
                '    for (s = _rt_load, d = _rt_start; d < _rt_end; s++, d++) *d = *s;\n'
                '    fm1_guard_enable(FM1_GUARD_STACK | FM1_GUARD_WRITE | FM1_GUARD_BUS | FM1_GUARD_PC);\n')
    default = builder.hot_dsp_ram_platform(platform, False)
    opted_in = builder.hot_dsp_ram_platform(platform, True)
    assert default == platform
    assert opted_in.count('_rd_start') == 2  # declaration plus copy-loop destination
    assert opted_in.index('_rt_end; s++, d++)') < opted_in.index('_rd_end; s++, d++)')
    assert opted_in.count('FM1_PC_LIMIT1_H = (uint32_t)(uintptr_t)_rd_end - 1u;') == 1
    assert opted_in.index('_rd_end; s++, d++)') < opted_in.index('fm1_guard_enable(')
    assert opted_in.index('fm1_guard_enable(') < opted_in.index('fm1__dbg_unlock();')
    assert opted_in.index('FM1_PC_LIMIT1_H =') < opted_in.index('fm1__dbg_lock();')
    # Never silently omit the guard adaptation if the pinned platform changes.
    with pytest.raises(SystemExit, match='Pinned adaptation'):
        builder.hot_dsp_ram_platform(platform.replace('FM1_GUARD_PC', '0'), True)


def test_plaits_hot_dsp_annotation_is_opt_in_and_scoped_to_used_voice_overload():
    root = Path(builder.__file__).resolve().parents[2]
    voice = (root / 'engines/third_party/mutable/plaits/dsp/fm/voice.h').read_text()
    macro = (root / 'engines/include/fm1_hot_dsp.h').read_text()
    assert '#if defined(FM1_HOT_DSP_RAM) && FM1_HOT_DSP_RAM' in macro
    assert '#define FM1_HOT_DSP_RENDER\n#endif' in macro
    assert voice.count('FM1_HOT_DSP_RENDER inline void Render(') == 1
    assert 'FM1_HOT_DSP_RENDER inline void Render(\n      const Parameters& parameters,\n      float* buffers[4],\n      size_t size)' in voice


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
                      hot_dsp_ram=False, device_sdk_headers=[], source_manifest={'x.c': 'current'},
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
        with pytest.raises(SystemExit):
            builder.checked_catalogue(tmp_path, hot_dsp_os=True, hot_dsp_ram=True)
        for shard in range(16):
            path = tmp_path / f'shard-{shard:02d}/report.json'
            report = json.loads(path.read_text())
            report['hot_dsp_ram'] = True
            path.write_text(json.dumps(report))
        objects, receipts = builder.checked_catalogue(
            tmp_path, hot_dsp_os=True, hot_dsp_ram=True)
        assert len(objects) == len(receipts) == 16
