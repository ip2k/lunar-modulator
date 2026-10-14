# SPDX-License-Identifier: MIT
"""Geometry matrix for the real two-slot journal and recovery decoder."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

import pytest

from tests.test_app_state import sim
from tests.test_sim_web import tools  # noqa: F401
from tests.test_native_project_capacity import (
    APP_FX_SLOTS, APP_INSERT_SLOTS, APP_MASTER_FX_SLOTS, APP_SOUND_UNITS,
    DX7_VOICES, LOCKS_PER_TRACK, MAX_METADATA, MOD_MODULES, MOD_SLOTS,
    NOTES_PER_TRACK, SEQ_TRACKS, TRIGS_PER_TRACK, _dense_max_args,
    _dense_max_mod, _max_drums_set,
)
from tools import lunar_state as ls

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/state/1.0/tin-kit.sound.lunarb'
GEOMETRIES = (102400, 49152)
FAILURE_SHARDS = 30
MAX_LABEL = "ABCDEFGHIJKLMNOPQRSTUVW"


def _compiler_flags():
    flags = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    if sys.platform.startswith('linux'):
        flags += ['-fno-pie', '-no-pie', '-Wl,--gc-sections']
    elif sys.platform == 'darwin':
        flags += ['-Wl,-dead_strip']
    return flags


@pytest.fixture(scope='session')
def adapter(tmp_path_factory):
    executable = tmp_path_factory.mktemp('project-store') / 'adapter'
    sources = ('state_bin.c', 'state_names.c', 'state_print.c', 'state_movy1.c',
               'fm1_num.c', 'fm1_deflate.c')
    command = [
        'cc', '-std=c99', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
        *_compiler_flags(), '-ffunction-sections', '-fdata-sections',
        '-DFM1_STATE_BIN_COMPACT_WRITER', '-DFM1_TFT_INDEXED=1',
        '-I' + str(ROOT / 'sim/web/src'), '-I' + str(ROOT / 'firmware/native'),
        '-I' + str(ROOT / 'engines/include'), '-I' + str(ROOT / 'engines/state'),
        str(ROOT / 'tests/native/project_store.c'),
    ]
    command.extend(str(ROOT / 'engines/state' / source) for source in sources)
    command.extend(('-lm', '-o', str(executable)))
    subprocess.run(command, check=True)
    return executable


@pytest.fixture(scope='session')
def legacy_adapter(tmp_path_factory):
    executable = tmp_path_factory.mktemp('project-store-legacy') / 'adapter'
    command = [
        'cc', '-std=c99', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
        *_compiler_flags(), '-I' + str(ROOT / 'firmware/native'),
        str(ROOT / 'tests/native/project_store_legacy.c'), '-o', str(executable),
    ]
    subprocess.run(command, check=True)
    return executable


@pytest.fixture(scope='session')
def large_collector_body(tools, tmp_path_factory):
    """Produce a real large app SAVE body for mutation-page coverage."""
    directory = tmp_path_factory.mktemp('large-collector-body')
    seq, mod = directory / 'max-drums.movy1', directory / 'max-drums.mod'
    _max_drums_set(seq)
    _dense_max_mod(mod)
    initial = directory / 'initial.lunar'
    sim(tools, *_dense_max_args(seq, mod), '--save', f'project:{initial}')
    doc = json.loads(initial.read_text(encoding='utf-8'))
    doc.update(MAX_METADATA)
    prepared = directory / 'max-metadata.lunar'
    prepared.write_text(json.dumps(doc), encoding='utf-8')
    body_path = directory / 'max-drums.native-save.lunarb'
    sim(tools, '--load', prepared, '--save', f'project:{body_path}')

    body = body_path.read_bytes()
    print(f'large collector SAVE: {len(body)} bytes sha256={hashlib.sha256(body).hexdigest()}')
    records, _ = ls.read_bin(body)
    assert len(body) == 35176
    assert len(body) >= 32 * 1024
    assert len([r for r in records if r['rec'] == 'param' and r['role'] == 'sound']) == APP_SOUND_UNITS * 149
    assert len([r for r in records if r['rec'] == 'param' and r['role'] == 'mfx']) == APP_SOUND_UNITS * 24
    assert len([r for r in records if r['rec'] == 'module']) == MOD_MODULES
    assert len([r for r in records if r['rec'] == 'param' and r['role'] == 'module']) == MOD_MODULES * 9
    assert len([r for r in records if r['rec'] == 'cable']) == MOD_SLOTS
    assert len([r for r in records if r['rec'] == 'dx7']) == DX7_VOICES
    assert len([r for r in records if r['rec'] == 'unit' and r['role'] in ('insert', 'master') and r['engine']]) == APP_FX_SLOTS
    assert len([r for r in records if r['rec'] == 'unit' and r['role'] == 'insert']) == APP_INSERT_SLOTS
    assert len([r for r in records if r['rec'] == 'unit' and r['role'] == 'master']) == APP_MASTER_FX_SLOTS
    set_lines = '\n'.join(str(r.get('text', '')) for r in records
                           if r['rec'] == 'line' and r['which'] == 'set').splitlines()
    assert sum(line.startswith('au ') for line in set_lines) == SEQ_TRACKS * 8
    assert all(line.endswith(MAX_LABEL) for line in set_lines if line.startswith('au '))
    assert sum(line.startswith('cl ') for line in set_lines) == SEQ_TRACKS
    assert sum(line.startswith('lk ') for line in set_lines) == SEQ_TRACKS
    assert sum(line.startswith('tg ') for line in set_lines) == SEQ_TRACKS
    assert all(len(next(line for line in set_lines if line.startswith(f'cl {track} 0 ')).split(' ', 5)[5].split(';')) == NOTES_PER_TRACK for track in range(SEQ_TRACKS))
    assert all(len(next(line for line in set_lines if line.startswith(f'lk {track} 0 ')).split(' ', 3)[3].split(';')) == LOCKS_PER_TRACK for track in range(SEQ_TRACKS))
    assert all(len(next(line for line in set_lines if line.startswith(f'tg {track} 0 ')).split(' ', 3)[3].split(';')) == TRIGS_PER_TRACK for track in range(SEQ_TRACKS))
    metadata = {r['key']: r.get('text', '') for r in records if r['rec'] == 'info'}
    assert {key: metadata[key] for key in MAX_METADATA} == MAX_METADATA
    return body_path


@pytest.mark.parametrize('slot_bytes', GEOMETRIES, ids=lambda n: f'slot-{n}')
@pytest.mark.parametrize('shard', range(FAILURE_SHARDS),
                         ids=lambda n: f'mutation-shard-{n:02}')
def test_project_transaction_torn_recovery(adapter, slot_bytes, shard):
    subprocess.run([str(adapter), str(FIXTURE), str(slot_bytes), str(shard)],
                   check=True)


@pytest.mark.parametrize('case_id', range(30), ids=lambda n: f'legacy-case-{n:02}')
def test_project_store_legacy_regressions(legacy_adapter, case_id):
    subprocess.run([str(legacy_adapter), str(case_id)], check=True)


@pytest.mark.parametrize('slot_bytes', GEOMETRIES, ids=lambda n: f'large-slot-{n}')
@pytest.mark.parametrize('shard', range(FAILURE_SHARDS),
                         ids=lambda n: f'large-mutation-shard-{n:02}')
def test_project_transaction_torn_recovery_large_body(
        adapter, large_collector_body, slot_bytes, shard):
    subprocess.run([str(adapter), str(large_collector_body), str(slot_bytes), str(shard)],
                   check=True)
