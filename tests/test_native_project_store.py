# SPDX-License-Identifier: MIT
"""Geometry matrix for the real two-slot journal and recovery decoder."""
from pathlib import Path
import hashlib
import json
import subprocess
import random

from tools import dx7_bank
from tests.native_test_flags import native_host_flags

import pytest

from tests.test_app_state import sim
from tests.test_sim_web import tools  # noqa: F401
from tests.test_native_project_capacity import (
    APP_FX_SLOTS, APP_INSERT_SLOTS, APP_MASTER_FX_SLOTS, APP_SOUND_UNITS,
    DX7_VOICES, LOCKS_PER_TRACK, MAX_METADATA, MOD_MODULES, MOD_SLOTS,
    NOTES_PER_TRACK, SEQ_TRACKS, TRIGS_PER_TRACK, _dense_max_args,
    _dense_max_mod,
)
from tools import lunar_state as ls

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/state/1.0/tin-kit.sound.lunarb'
GEOMETRIES = (102400, 49152)
FAILURE_SHARDS = 30
MAX_LABEL_LENGTH = 23


def _label_for(track: int, lane: int) -> str:
    """Give each accepted maximum-length label deterministic high entropy."""
    seed = f"project-store-max-label:{track}:{lane}".encode("ascii")
    return hashlib.shake_256(seed).hexdigest(12)[:MAX_LABEL_LENGTH].upper()


def _incompressible_dx7_bank(path: Path) -> None:
    """Write a deterministic valid 32-voice bank to stress stored SAVE bytes."""
    rng = random.Random(0x445837)
    voices = []
    for index in range(DX7_VOICES):
        ops = [dx7_bank.Op(
            level=rng.randrange(100), ratio=rng.randrange(50, 3200) / 100.0,
            rates=tuple(rng.randrange(100) for _ in range(4)),
            levels=tuple(rng.randrange(100) for _ in range(4)),
            detune=rng.randrange(15), vel=rng.randrange(8),
            rate_scaling=rng.randrange(8), ams=rng.randrange(4),
            bp=rng.randrange(100), ld=rng.randrange(100), rd=rng.randrange(100),
            lc=rng.randrange(4), rc=rng.randrange(4)) for _ in range(6)]
        voices.append(dx7_bank.Voice(
            name=f"T{index:02X}R{rng.randrange(256):02X}",
            alg=rng.randrange(1, 33), ops=ops, feedback=rng.randrange(8),
            pitch_rates=tuple(rng.randrange(100) for _ in range(4)),
            pitch_levels=tuple(rng.randrange(100) for _ in range(4)),
            lfo_speed=rng.randrange(100), lfo_delay=rng.randrange(100),
            lfo_pmd=rng.randrange(100), lfo_amd=rng.randrange(100),
            lfo_sync=rng.randrange(2), lfo_wave=rng.randrange(6),
            pms=rng.randrange(8), transpose=rng.randrange(49),
            osc_sync=rng.randrange(2)))
    path.write_bytes(dx7_bank.vmem_syx(voices))


def _max_project_set(path: Path) -> None:
    """Fill all 64 clip descriptors while keeping each per-track event pool full."""
    rng = random.Random(0x4C554E4152)
    lines = ["movy1", "bpm 30000", "swing 99", "link 1", "key 11 7"]
    for track in range(SEQ_TRACKS):
        lines.extend((f"tk {track} 0 0", f"rt {track} 1 {track % 4}"))
        for clip in range(8):
            notes = ";".join(
                f"{i * 10 + 25}:{rng.randint(10000, 65535)}:"
                f"{rng.randint(1, 126)}:{rng.randint(0, 127)}:{rng.randint(0, 255)}"
                for i in range(NOTES_PER_TRACK // 8)
            )
            locks = ";".join(
                f"{i % 8}:{i // 8}:{rng.randint(0, 127)}"
                for i in range(LOCKS_PER_TRACK // 8)
            )
            trigs = ";".join(
                f"{i}:-1:{rng.randint(0, 127)}:{rng.randint(0, 255)}:{rng.randint(0, 255)}:{rng.randint(0, 1)}"
                for i in range(TRIGS_PER_TRACK // 8)
            )
            lines.extend((
                f"cl {track} {clip} 256 0 {notes}",
                f"cp {track} {clip} {24 + clip} 1 {-36 + clip} {100 + clip}",
                f"lk {track} {clip} {locks}",
                f"tg {track} {clip} {trigs}",
            ))
        for lane in range(8):
            lines.append(f"au {track} {lane} 255 {_label_for(track, lane)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _compiler_flags():
    return native_host_flags()

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
    _max_project_set(seq)
    _dense_max_mod(mod)
    bank_path = directory / 'deterministic-high-entropy.syx'
    _incompressible_dx7_bank(bank_path)
    initial = directory / 'initial.lunar'
    args = _dense_max_args(seq, mod)
    args[args.index('--sysex') + 1] = bank_path
    sim(tools, *args, '--save', f'project:{initial}')
    doc = json.loads(initial.read_text(encoding='utf-8'))
    pad_rng = random.Random(0x50414453)
    for sound in doc.get('sounds', []):
        for pad_index, pad in enumerate(sound.get('pads', [])):
            pad.update({
                'Tune': round(pad_rng.uniform(-24, 24), 4),
                'Decay': round(pad_rng.random(), 4),
                'Level': round(pad_rng.random(), 4),
                'Tone': round(pad_rng.random(), 4),
                'Snap': round(pad_rng.random(), 4),
                'Sweep': round(pad_rng.random(), 4),
                'Drive': round(pad_rng.random(), 4),
            })
    doc.update(MAX_METADATA)
    prepared = directory / 'max-metadata.lunar'
    prepared.write_text(json.dumps(doc), encoding='utf-8')
    body_path = directory / 'max-drums.native-save.lunarb'
    sim(tools, '--load', prepared, '--save', f'project:{body_path}')

    body = body_path.read_bytes()
    print(f'large collector SAVE: {len(body)} bytes sha256={hashlib.sha256(body).hexdigest()}')
    records, _ = ls.read_bin(body)
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
    assert all(
        line.split()[4] == _label_for(int(line.split()[1]), int(line.split()[2]))
        for line in set_lines if line.startswith('au ')
    )
    assert sum(line.startswith('cl ') for line in set_lines) == SEQ_TRACKS * 8
    assert sum(line.startswith('lk ') for line in set_lines) == SEQ_TRACKS * 8
    assert sum(line.startswith('tg ') for line in set_lines) == SEQ_TRACKS * 8
    for track in range(SEQ_TRACKS):
        clips = [line for line in set_lines if line.startswith(f'cl {track} ')]
        locks = [line for line in set_lines if line.startswith(f'lk {track} ')]
        trigs = [line for line in set_lines if line.startswith(f'tg {track} ')]
        assert len(clips) == len(locks) == len(trigs) == 8
        assert sum(len(line.split(' ', 5)[5].split(';')) for line in clips) == NOTES_PER_TRACK
        assert sum(len(line.split(' ', 3)[3].split(';')) for line in locks) == LOCKS_PER_TRACK
        assert sum(len(line.split(' ', 3)[3].split(';')) for line in trigs) == TRIGS_PER_TRACK
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
