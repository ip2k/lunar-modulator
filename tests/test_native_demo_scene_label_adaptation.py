# SPDX-License-Identifier: MIT
"""Prove the four compatibility label edits preserve source bytes and staging."""
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
ADAPTATIONS = (
    {
        'file': 'event-horizon-showcase.lunar',
        'original_sha256': '0d5d871bd31db1e628efbf291fd306671b81c93bef254a950291bf95f5413d1c',
        'changed_sha256': '22bf4e768ec1e55a9a92ebb7b2ef1ed5d5967703d226fca7798f0c67b441d24f',
        'labels': ((4, 'Suspense', 'Tense'), (5, 'OpenSky', 'Sky')),
        'bars': 68,
    },
    {
        'file': 'packet-bloom-showcase.lunar',
        'original_sha256': 'eb55a36129ef3db02136b2ed0859fafcad94e3b2cbc3fa42761383d380249731',
        'changed_sha256': '853be1d05bd206d9fce928e5d36944d932491a9b9c69cf79d96e6f78392700e7',
        'labels': ((1, 'Packets', 'Packet'), (4, 'Dissolve', 'Fade')),
        'bars': 40,
    },
)
ASSET_ROOT = ROOT / 'engines/state/examples/replacement-showcases'


@pytest.mark.parametrize('spec', ADAPTATIONS, ids=('event-horizon', 'packet-bloom'))
def test_adaptation_reverses_to_exact_fb92_bytes_and_changes_only_display_labels(spec):
    path = ASSET_ROOT / spec['file']
    adapted = path.read_bytes()
    assert hashlib.sha256(adapted).hexdigest() == spec['changed_sha256']
    restored = adapted
    for scene, original, replacement in spec['labels']:
        old = f'sn {scene} {original}'.encode()
        new = f'sn {scene} {replacement}'.encode()
        assert adapted.count(new) == 1
        assert adapted.count(old) == 0
        restored = restored.replace(new, old, 1)
    assert hashlib.sha256(restored).hexdigest() == spec['original_sha256']

    current = json.loads(adapted)
    original = json.loads(restored)
    assert current.keys() == original.keys()
    assert {key: value for key, value in current.items() if key != 'set'} == {
        key: value for key, value in original.items() if key != 'set'}
    restored_set = list(current['set'])
    for scene, old, new in spec['labels']:
        source = f'sn {scene} {old}'
        adapted_line = f'sn {scene} {new}'
        assert current['set'].count(adapted_line) == 1
        restored_set[restored_set.index(adapted_line)] = source
    assert restored_set == original['set']
    assert len(current['set']) == len(original['set'])
    scene_labels = [line[5:] for line in current['set'] if line.startswith('sn ')]
    assert all(0 < len(label) <= 6 for label in scene_labels)
    assert len(scene_labels) == spec['bars'] // spec['bars'] * (
        7 if 'event-horizon' in spec['file'] else 5)


@pytest.fixture(scope='session')
def native_sequence_stage_probe(tmp_path_factory):
    build_root = tmp_path_factory.mktemp('native-demo-label-stage')
    from tools.native.module_selection import resolve_modules

    _, catalogue = resolve_modules(ROOT, build_root / 'module-catalogue', 'all')
    modules = [item for item in catalogue['selected'] if not item.startswith('test-')]
    assert len(modules) == 55
    build = build_root / 'engine-build'
    tool = build / 'fm1-state'
    subprocess.run([
        'make', '-s', '--no-print-directory', '-C', str(ROOT / 'engines'),
        'BUILD=' + str(build), 'FM1_GPL_MODS=1', 'FM1_MODULES=' + ','.join(modules),
        str(tool),
    ], check=True)

    includes = [ROOT / 'firmware/native', ROOT / 'engines/include', ROOT / 'engines/state']
    source_files = [
        ROOT / 'firmware/native/project_units.c',
        ROOT / 'firmware/native/project_seq.c',
        *(ROOT / 'engines/state' / (name + '.c') for name in
          ('state_bin', 'state_names', 'state_movy1', 'fm1_num', 'fm1_deflate')),
        *(ROOT / 'engines/seq' / (name + '.c') for name in
          ('seq_clip', 'seq_engine', 'seq_cmd', 'seq_persist', 'seq_capture', 'seq_host')),
    ]
    harness = build_root / 'demo_label_stage.c'
    harness.write_text(r'''#include "project_seq.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned char *read_file(const char *p, size_t *n) {
    FILE *f=fopen(p,"rb"); long z; unsigned char *b;
    if (!f || fseek(f,0,SEEK_END) || (z=ftell(f))<0 || fseek(f,0,SEEK_SET)) return NULL;
    b=(unsigned char*)malloc((size_t)z+1u); if(!b) return NULL;
    if(fread(b,1,(size_t)z,f)!=(size_t)z || fclose(f)) { free(b); return NULL; }
    b[z]=0; *n=(size_t)z; return b;
}
int main(int argc,char **argv) {
    unsigned char *bin,*set,*mem,*refmem; size_t binsz,setsz,cap,expsz;
    fm1_state_names_t names; fm1_state_report_t report;
    fm1_host_t host={.api_version=FM1_ENGINE_API_VERSION,.sample_rate=44118,.max_frames=64};
    fm1_seq_limits_t limits; fm1_seq_t *seq,*ref; fm1_seq_info_t info; fm1_seq_stats_t stats;
    unsigned has=0; char *exported,*refexport;
    if(argc!=3) return 2;
    bin=read_file(argv[1],&binsz); set=read_file(argv[2],&setsz);
    if(!bin||!set||binsz>FM1_STATE_BIN_MAX) return 3;
    fm1_state_names_default(&names); fm1_seq_limits_default(&limits,8); cap=fm1_seq_size(&limits);
    mem=(unsigned char*)calloc(1,cap); refmem=(unsigned char*)calloc(1,cap);
    if(!mem||!refmem||!(seq=fm1_seq_create(mem,&limits,44118))||
       !(ref=fm1_seq_create(refmem,&limits,44118))||
       !fm1_seq_import_movy1(ref,(const char*)set,setsz)) return 4;
    fm1_state_report_init(&report);
    if(!lunar_project_seq_stage(bin,(uint32_t)binsz,&names,&host,seq,&has,&report)||!has||report.code!=FM1_STATE_OK) {
       fprintf(stderr,"stage refused code=%u what=%s\n",report.code,report.what); return 5;
    }
    expsz=fm1_seq_export_movy1(ref,NULL,0);
    exported=(char*)malloc(expsz+1u); refexport=(char*)malloc(expsz+1u);
    if(!exported||!refexport||fm1_seq_export_movy1(seq,exported,expsz+1u)!=expsz||
       fm1_seq_export_movy1(ref,refexport,expsz+1u)!=expsz||memcmp(exported,refexport,expsz)) {
       fprintf(stderr,"canonical SET differs from direct source import\n"); return 6;
    }
    fm1_seq_get_info(seq,&info); fm1_seq_get_stats(seq,&stats);
    if(fm1_seq_song_bars(seq)==0 || info.song_entries==0 || info.tracks==0 ||
       stats.refused || stats.dropped_events || stats.gates_evicted || stats.movy_faults) {
       fprintf(stderr,"loss counters nonzero bars=%lu entries=%u tracks=%u refused=%lu dropped=%lu evicted=%lu faults=%lu\n",
          (unsigned long)fm1_seq_song_bars(seq),info.song_entries,info.tracks,
          (unsigned long)stats.refused,(unsigned long)stats.dropped_events,
          (unsigned long)stats.gates_evicted,(unsigned long)stats.movy_faults); return 7;
    }
    printf("bars=%lu song_entries=%u tracks=%u set_bytes=%lu refused=%lu dropped=%lu evicted=%lu faults=%lu\n",
       (unsigned long)fm1_seq_song_bars(seq),info.song_entries,info.tracks,(unsigned long)expsz,
       (unsigned long)stats.refused,(unsigned long)stats.dropped_events,
       (unsigned long)stats.gates_evicted,(unsigned long)stats.movy_faults);
    free(exported);free(refexport);free(mem);free(refmem);free(set);free(bin);return 0;
}
''')
    objects=[]
    for index, source in enumerate([*source_files, harness]):
        obj=build_root / ('stage-%02d.o' % index)
        subprocess.run([
            'cc','-std=c99','-Os','-Wall','-Wextra','-Werror',
            *(arg for path in includes for arg in ('-I',str(path))),
            '-c',str(source),'-o',str(obj),
        ],check=True)
        objects.append(obj)
    compiled_names={path.stem+'.o' for path in source_files}
    registry=[path for path in build.rglob('*.o') if path.name not in compiled_names | {
        'state_tool.o','render.o','render_state.o'}]
    assert any(path.name=='state_registry.o' for path in registry)
    probe=build_root/'demo-label-stage'
    subprocess.run(['c++','-o',str(probe),*(str(obj) for obj in objects),
                    *(str(obj) for obj in registry),'-lm'],check=True)
    return tool,probe


@pytest.mark.parametrize('spec', ADAPTATIONS, ids=('event-horizon', 'packet-bloom'))
def test_adapted_projects_pack_and_stage_without_importer_loss(spec, native_sequence_stage_probe, tmp_path):
    tool, probe = native_sequence_stage_probe
    source = ASSET_ROOT / spec['file']
    project = json.loads(source.read_text())
    expected_set = tmp_path / (source.stem + '.movy1')
    expected_set.write_text(''.join(line + '\n' for line in project['set']))
    packed = tmp_path / (source.stem + '.lunarb')
    subprocess.run([str(tool), 'pack', str(source), '-o', str(packed)], check=True)
    run = subprocess.run([str(probe), str(packed), str(expected_set)],
                         capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stderr
    metrics = dict(field.split('=', 1) for field in run.stdout.strip().split())
    assert int(metrics['bars']) == spec['bars']
    assert int(metrics['song_entries']) > 0
    assert int(metrics['tracks']) > 0
    assert int(metrics['set_bytes']) > 0
    assert all(int(metrics[key]) == 0 for key in ('refused','dropped','evicted','faults'))
