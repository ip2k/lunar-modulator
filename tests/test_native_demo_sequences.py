# SPDX-License-Identifier: MIT
"""Packed full-song examples survive native project sequence staging."""
import json
import hashlib
from pathlib import Path
import subprocess

import pytest

from tests.native_test_flags import native_host_link_flags

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = (
    ('afterglow-relay', 76),
    ('event-horizon', 116),
    ('packet-bloom', 88),
    ('neon-transit', 104),
)


def _production_modules(tmp_path):
    from tools.native.module_selection import resolve_modules

    _, catalogue = resolve_modules(ROOT, tmp_path / 'module-catalogue', 'all')
    modules = [item for item in catalogue['selected'] if not item.startswith('test-')]
    assert len(modules) == 55
    return ','.join(modules)


@pytest.fixture(scope='session')
def native_stage_probe(tmp_path_factory):
    build_root = tmp_path_factory.mktemp('native-demo-sequences')
    modules = _production_modules(build_root)
    build = build_root / 'engine-build'
    tool = build / 'fm1-state'
    subprocess.run([
        'make', '-s', '--no-print-directory', '-C', str(ROOT / 'engines'),
        'BUILD=' + str(build), 'FM1_GPL_MODS=1', 'FM1_MODULES=' + modules,
        str(tool),
    ], check=True)

    cc = 'cc'
    cxx = 'c++'
    includes = [ROOT / 'firmware/native', ROOT / 'engines/include', ROOT / 'engines/state',
                ROOT / 'sim/web/src']
    compile_objects = [
        ROOT / 'firmware/native/project_units.c',
        ROOT / 'firmware/native/project_seq.c',
        ROOT / 'firmware/native/content_set.c',
        *(ROOT / 'engines/state' / (name + '.c') for name in
          ('state_bin', 'state_names', 'state_movy1', 'fm1_num', 'fm1_deflate')),
        *(ROOT / 'engines/seq' / (name + '.c') for name in
          ('seq_clip', 'seq_engine', 'seq_cmd', 'seq_persist', 'seq_capture', 'seq_host')),
        ROOT / 'tests/native/demo_sequences.c',
    ]
    test_objects = []
    for index, source in enumerate(compile_objects):
        obj = build_root / ('stage-%02d.o' % index)
        subprocess.run([
            cc, '-std=c99', '-Os', '-Wall', '-Wextra', '-Werror',
            '-ffunction-sections', '-fdata-sections',
            *(arg for path in includes for arg in ('-I', str(path))),
            '-c', str(source), '-o', str(obj),
        ], check=True)
        test_objects.append(obj)

    # Reuse the objects that made fm1-state, preserving the same generated
    # production-55 registries; only its CLI/main objects are excluded.
    # These same files are compiled above into stage-*.o. Do not link a
    # second copy from the fm1-state build tree.
    stage_sources = {
        'state_bin.o', 'state_names.o', 'state_movy1.o', 'fm1_num.o',
        'fm1_deflate.o', 'seq_clip.o', 'seq_engine.o', 'seq_cmd.o',
        'seq_persist.o', 'seq_capture.o', 'seq_host.o',
    }
    registry_objects = [
        path for path in build.rglob('*.o')
        if path.name not in stage_sources | {
            'state_tool.o', 'render.o', 'render_state.o',
        }
    ]
    assert any(path.name == 'state_registry.o' for path in registry_objects)
    probe = build_root / 'demo-sequence-stage'
    subprocess.run([
        cxx, *native_host_link_flags(), '-o', str(probe),
        *(str(path) for path in test_objects),
        *(str(path) for path in registry_objects), '-lm',
    ], check=True)
    return tool, probe, build


@pytest.mark.parametrize(('project_id', 'expected_bars'), PROJECTS)
def test_full_song_survives_native_project_sequence_stage(
        project_id, expected_bars, native_stage_probe, tmp_path):
    tool, probe, _ = native_stage_probe
    source = ROOT / 'engines/state/examples' / (project_id + '.lunar')
    project = json.loads(source.read_text())
    expected = tmp_path / (project_id + '.movy1')
    expected.write_text(''.join(line + '\n' for line in project['set']))
    packed = tmp_path / (project_id + '.lunarb')
    subprocess.run([str(tool), 'pack', str(source), '-o', str(packed)], check=True)
    result = subprocess.run(
        [str(probe), str(packed), str(expected), str(expected_bars)],
        check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    metrics = dict(field.split('=', 1) for field in result.stdout.strip().split())
    assert int(metrics['bars']) == expected_bars
    assert int(metrics['scenes']) == 8
    assert int(metrics['tracks']) >= 1
    assert int(metrics['notes']) > 0
    assert int(metrics['locks']) > 0
    print(project_id,
          'source_sha256=' + hashlib.sha256(source.read_bytes()).hexdigest(),
          'packed_bytes=' + str(packed.stat().st_size),
          'packed_sha256=' + hashlib.sha256(packed.read_bytes()).hexdigest(),
          result.stdout.strip())
