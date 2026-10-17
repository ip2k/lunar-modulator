import hashlib, json, subprocess, tarfile, gzip
import os
from pathlib import Path
import sys
import pytest
from tools.native.create_gpl_source_bundle import build_bundle, _selected, SOURCE_PRELOAD_INPUTS

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/native'))

def _sha(b): return hashlib.sha256(b).hexdigest()
def _fixture(tmp_path):
    src=tmp_path/"src"; src.mkdir()
    subprocess.run(["git","init","-q",str(src)],check=True)
    subprocess.run(["git","-C",str(src),"config","user.name","Test"],check=True)
    subprocess.run(["git","-C",str(src),"config","user.email","test@example.invalid"],check=True)
    (src/"LICENSE").write_text("GPL-3.0-only\n")
    (src/"engines").mkdir(); (src/"engines"/"main.c").write_text("int main(void){return 0;}\n")
    for name,data in {
        'firmware/third_party/musl/COPYRIGHT': b'musl source notice\n',
        'engines/third_party/fm1-x0x/local.patch': b'local source adaptation\n',
        'engines/third_party/fm1-x0x/LICENSE-Open303': b'MIT component notice\n',
        'engines/third_party/fm1-x0x/assets/909/hh.wav': b'recorded source fixture',
        'engines/third_party/fm1-x0x/assets/909/unrelated.wav': b'not a build input',
    }.items():
        path=src/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data)
    (src/"photos").mkdir(); (src/"photos"/"bench.jpg").write_bytes(b"private")
    (src/"app.bin").write_bytes(b"binary")
    subprocess.run(["git","-C",str(src),"add","-A"],check=True)
    subprocess.run(["git","-C",str(src),"commit","-qm","fixture"],check=True)
    commit=subprocess.check_output(["git","-C",str(src),"rev-parse","HEAD"],text=True).strip()
    paths=subprocess.check_output(["git","-C",str(src),"ls-files","-z"]).decode().split("\0")
    rows=[]
    for path in paths:
        if path:
            data=subprocess.check_output(["git","-C",str(src),"show",f"{commit}:{path}"])
            rows.append({"path":path,"sha256":_sha(data)})
    rows.sort(key=lambda x:x["path"])
    manifest_raw=json.dumps({"schema":1,"commit":commit,"objects":rows},sort_keys=True,separators=(",",":")).encode()
    manifest=tmp_path/"source-tree-manifest.json"; manifest.write_bytes(manifest_raw)
    provenance_raw=json.dumps({"source_commit":commit,"source_tree_sha256":_sha(manifest_raw)}).encode()
    provenance=tmp_path/"provenance.json"; provenance.write_bytes(provenance_raw)
    tuple_raw=json.dumps({"schema":2,"source_tree_sha256":_sha(manifest_raw),"build_provenance_sha256":_sha(provenance_raw),
      "hardware_admitted":False,"hardware_tested":False,"installable":False,"profile_id":"test"}).encode()
    tuple_path=tmp_path/"tuple.json"; tuple_path.write_bytes(tuple_raw)
    return src,tuple_path,provenance,manifest,_sha(tuple_raw)

def _prepared_fixture(tmp_path,args,*,extra=False):
    src,tup,prov,manifest,_=args
    prepared=tmp_path/'selection'/'prepared'; prepared.mkdir(parents=True)
    project_id='demo-project'; set_id='demo-set'
    request={'version':1,'engines':[],'effects':[],'midi':[],'modulation':[],
             'project_ids':[project_id],'startup_index':0,'set_ids':[set_id]}
    request_raw=(json.dumps(request,sort_keys=True,separators=(',',':'))+'\n').encode()
    (prepared.parent/'request.json').write_bytes(request_raw)
    sources=[(project_id,'project',b'{"title":"Demo"}\n',None),
             (set_id,'set',b'movy1\npattern 1\n',project_id)]
    if extra:
        sources.append(('unselected','project',b'{"title":"Other"}\n',None))
    header=b'/* fixture modules */\n'; (prepared/'fm1_modules.h').write_bytes(header)
    assets=[]; rows=[]; selected=[]; content_bytes=0
    project_bytes=b'{"title":"Demo"}\n'
    set_bytes=b'movy1\npattern 1\n'
    for index,(item_id,kind,source,parent) in enumerate(sources):
        suffix='.lunar' if kind=='project' else '.movy1'
        staged=f'{"projects" if kind=="project" else "sets"}/{item_id}{suffix}'
        packed=(f'packed-{index}'.encode())
        (prepared/f'content-{index:02d}.source').write_bytes(source)
        (prepared/f'content-{index:02d}.bin').write_bytes(packed)
        asset={'kind':kind,'source':staged,'source_sha256':_sha(source),
               'packed':f'content-{index:02d}.bin','packed_sha256':_sha(packed),
               'bytes':len(packed),'sequence_semantics_verified':False,'dependencies':[]}
        assets.append(asset); content_bytes+=len(packed)
        identity={'kind':kind,'id':item_id}
        row={'id':item_id,**asset}
        if parent:
            identity['parent_project_id']=parent; row['parent_project_id']=parent
        selected.append(identity); rows.append(row)
    module_selection={'selected':[],'header_sha256':_sha(header)}
    profile={'version':1,'installable':False,'native_link_verified':False,
             'native_ram_verified':False,'hardware_tested':False,
             'module_selection':module_selection,'content':assets,
             'packed_content_bytes':content_bytes}
    profile_raw=(json.dumps(profile,sort_keys=True,separators=(',',':'))+'\n').encode()
    (prepared/'profile.json').write_bytes(profile_raw)
    request_sha=_sha(request_raw); prepared_sha=_sha(profile_raw)
    selection={'version':1,'status':'prepared-build-inputs','request_sha256':request_sha,
               'prepared_profile_sha256':prepared_sha,'project_ids':[project_id],
               'startup_index':0,'startup_project_id':project_id,'set_ids':[set_id],
               'selected_content':selected,'content':rows,
               'installable':False,'native_link_verified':False,
               'native_ram_verified':False,'hardware_tested':False}
    (prepared.parent/'selection.json').write_text(json.dumps(selection))
    # Match capture_trusted_build_tuple.py, which inherits both tuple fields
    # and adds receipt-specific copies to provenance.
    provenance=json.loads(prov.read_text()); provenance.update(
        prepared_profile_sha256=prepared_sha,request_sha256=request_sha,
        prepared_profile_receipt_sha256=prepared_sha,request_receipt_sha256=request_sha)
    provenance_raw=json.dumps(provenance).encode(); prov.write_bytes(provenance_raw)
    tuple_obj=json.loads(tup.read_text()); tuple_obj.update(
        build_provenance_sha256=_sha(provenance_raw),prepared_profile_sha256=prepared_sha,
        request_sha256=request_sha)
    tuple_raw=json.dumps(tuple_obj).encode(); tup.write_bytes(tuple_raw)
    return prepared,_sha(tuple_raw)

def test_bundle_deterministic_and_explicitly_incomplete(tmp_path):
    args=_fixture(tmp_path); src,tup,prov,manifest,anchor=args
    a=tmp_path/"a.tgz"; b=tmp_path/"b.tgz"
    result=build_bundle(src,tup,prov,manifest,anchor,a); build_bundle(src,tup,prov,manifest,anchor,b)
    assert a.read_bytes()==b.read_bytes()
    assert result["distribution_eligible"] is False and result["corresponding_source_complete"] is False
    with tarfile.open(fileobj=gzip.GzipFile(fileobj=a.open("rb")),mode="r:") as archive:
        names=archive.getnames()
    assert "engines/main.c" in names and "LICENSE" in names
    assert "photos/bench.jpg" not in names and "app.bin" not in names

def test_archive_retains_build_notice_and_regeneration_inputs(tmp_path):
    src,tup,prov,manifest,anchor=_fixture(tmp_path)
    output=tmp_path/'source-inputs.tgz'
    build_bundle(src,tup,prov,manifest,anchor,output)
    included=['firmware/third_party/musl/COPYRIGHT',
              'engines/third_party/fm1-x0x/local.patch',
              'engines/third_party/fm1-x0x/LICENSE-Open303',
              'engines/third_party/fm1-x0x/assets/909/hh.wav']
    with tarfile.open(output,mode='r:gz') as archive:
        metadata=json.load(archive.extractfile('MANIFEST.json'))
        rows={row['path']:row for row in metadata['files']}
        for name in included:
            data=(src/name).read_bytes()
            assert archive.extractfile(name).read()==data
            assert rows[name]['sha256']==_sha(data)
            assert rows[name]['bytes']==len(data)
        assert 'engines/third_party/fm1-x0x/assets/909/unrelated.wav' not in archive.getnames()
        assert metadata['corresponding_source_complete'] is False

def test_runtime_inventories_and_named_recording_sources_are_selected():
    # The native runtime builders hash every inventory row, including notices.
    for component in ('musl','dinghy','compiler-rt','printf','tlsf','tinf','arduino-midi'):
        directory=ROOT/'firmware/third_party'/component
        inventory=json.loads((directory/'inventory.json').read_text())
        for name in inventory['files']:
            assert _selected((directory/name).relative_to(ROOT).as_posix())
    for name in ('hh','ride','crash'):
        assert _selected(f'engines/third_party/fm1-x0x/assets/909/{name}.wav')
    assert not _selected('engines/third_party/fm1-x0x/assets/909/extra.wav')
    assert not _selected('engines/third_party/fm1-x0x/assets/909/app.bin')

def test_requires_external_tuple_anchor_and_schema2(tmp_path):
    src,tup,prov,manifest,anchor=_fixture(tmp_path)
    with pytest.raises(ValueError,match="trust anchor"):
        build_bundle(src,tup,prov,manifest,"0"*64,tmp_path/"bad.tgz")
    obj=json.loads(tup.read_text()); obj["schema"]=1; tup.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match="schema-2"):
        build_bundle(src,tup,prov,manifest,_sha(tup.read_bytes()),tmp_path/"bad.tgz")

def test_refuses_dirty_source_and_source_manifest_drift(tmp_path):
    src,tup,prov,manifest,anchor=_fixture(tmp_path)
    (src/"engines"/"main.c").write_text("tampered")
    with pytest.raises(ValueError,match="clean"):
        build_bundle(src,tup,prov,manifest,anchor,tmp_path/"dirty.tgz")

def test_refuses_changed_source_manifest(tmp_path):
    src,tup,prov,manifest,anchor=_fixture(tmp_path)
    data=json.loads(manifest.read_text()); data["objects"][0]["sha256"]="0"*64
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError,match="source manifest differs"):
        build_bundle(src,tup,prov,manifest,anchor,tmp_path/"bad.tgz")

def test_binds_exact_selected_project_and_set_sources_deterministically(tmp_path):
    args=_fixture(tmp_path); prepared,anchor=_prepared_fixture(tmp_path,args)
    src,tup,prov,manifest,_=args
    a=tmp_path/'with-inputs-a.tgz'; b=tmp_path/'with-inputs-b.tgz'
    result=build_bundle(src,tup,prov,manifest,anchor,a,prepared_dir=prepared)
    build_bundle(src,tup,prov,manifest,anchor,b,prepared_dir=prepared)
    assert a.read_bytes()==b.read_bytes()
    assert result['corresponding_source_complete'] is False
    assert result['distribution_eligible'] is False
    with tarfile.open(fileobj=gzip.GzipFile(fileobj=a.open('rb')),mode='r:') as archive:
        manifest_obj=json.load(archive.extractfile('MANIFEST.json'))
        project=archive.extractfile('selected-inputs/projects/demo-project.lunar').read()
        companion=archive.extractfile('selected-inputs/sets/demo-set.movy1').read()
    assert project==b'{"title":"Demo"}\n'
    assert companion==b'movy1\npattern 1\n'
    assert [row['kind'] for row in manifest_obj['selected_source_inputs']]==['project','set']
    assert [row['bytes'] for row in manifest_obj['selected_source_inputs']]==[len(project),len(companion)]
    assert [row['sha256'] for row in manifest_obj['selected_source_inputs']]==[_sha(project),_sha(companion)]
    assert manifest_obj['corresponding_source_complete'] is False
    assert manifest_obj['distribution_eligible'] is False
    assert 'external toolchain/source inputs are not included' in manifest_obj['unresolved']
    assert not any('project and companion SET' in row for row in manifest_obj['unresolved'])

def test_rejects_tuple_prepared_digest_mismatch(tmp_path):
    args=_fixture(tmp_path); prepared,anchor=_prepared_fixture(tmp_path,args)
    src,tup,prov,manifest,_=args
    provenance=json.loads(prov.read_text())
    provenance['prepared_profile_sha256']='0'*64
    provenance['prepared_profile_receipt_sha256']='0'*64
    raw=json.dumps(provenance).encode(); prov.write_bytes(raw)
    tuple_obj=json.loads(tup.read_text()); tuple_obj['build_provenance_sha256']=_sha(raw)
    tuple_obj['prepared_profile_sha256']='0'*64
    tuple_raw=json.dumps(tuple_obj).encode(); tup.write_bytes(tuple_raw)
    with pytest.raises(ValueError,match='manifest digest mismatch'):
        build_bundle(src,tup,prov,manifest,_sha(tuple_raw),tmp_path/'mismatch.tgz',prepared_dir=prepared)

@pytest.mark.parametrize('field', [
    'request_sha256', 'prepared_profile_sha256',
    'request_receipt_sha256', 'prepared_profile_receipt_sha256',
])
def test_rejects_each_missing_provenance_selection_pin(tmp_path,field):
    args=_fixture(tmp_path); prepared,anchor=_prepared_fixture(tmp_path,args)
    src,tup,prov,manifest,_=args
    provenance=json.loads(prov.read_text()); provenance.pop(field)
    raw=json.dumps(provenance).encode(); prov.write_bytes(raw)
    tuple_obj=json.loads(tup.read_text()); tuple_obj['build_provenance_sha256']=_sha(raw)
    tuple_raw=json.dumps(tuple_obj).encode(); tup.write_bytes(tuple_raw)
    with pytest.raises(ValueError,match='tuple/provenance prepared selection identity mismatch'):
        build_bundle(src,tup,prov,manifest,_sha(tuple_raw),tmp_path/'missing-pin.tgz',prepared_dir=prepared)

@pytest.mark.parametrize('field', [
    'request_sha256', 'prepared_profile_sha256',
    'request_receipt_sha256', 'prepared_profile_receipt_sha256',
])
def test_rejects_each_mismatched_provenance_selection_pin(tmp_path,field):
    args=_fixture(tmp_path); prepared,anchor=_prepared_fixture(tmp_path,args)
    src,tup,prov,manifest,_=args
    provenance=json.loads(prov.read_text()); provenance[field]='0'*64
    raw=json.dumps(provenance).encode(); prov.write_bytes(raw)
    tuple_obj=json.loads(tup.read_text()); tuple_obj['build_provenance_sha256']=_sha(raw)
    tuple_raw=json.dumps(tuple_obj).encode(); tup.write_bytes(tuple_raw)
    with pytest.raises(ValueError,match='tuple/provenance prepared selection identity mismatch'):
        build_bundle(src,tup,prov,manifest,_sha(tuple_raw),tmp_path/'wrong-pin.tgz',prepared_dir=prepared)

@pytest.mark.skipif(not os.environ.get('FM1_STATE_TOOL'), reason='requires fresh FM1_STATE_TOOL')
def test_real_prepare_selection_receipt_binds_bundle_sources(tmp_path):
    from export_image_catalogue import export_catalogue
    from prepare_demo_selection import prepare_selection

    catalogue=export_catalogue(ROOT,tmp_path/'catalogue')
    project_id='replacement-showcase-candidate-event-horizon'
    assert project_id in [row['id'] for row in catalogue['projects']]
    request=dict(version=1,**catalogue['groups'],project_ids=[project_id],startup_index=0)
    selection_dir=tmp_path/'real-selection'
    receipt=prepare_selection(ROOT,request,Path(os.environ['FM1_STATE_TOOL']),selection_dir)

    args=_fixture(tmp_path); src,tup,prov,manifest,_=args
    provenance=json.loads(prov.read_text())
    provenance.update(request_sha256=receipt['request_sha256'],
        prepared_profile_sha256=receipt['prepared_profile_sha256'],
        request_receipt_sha256=receipt['request_sha256'],
        prepared_profile_receipt_sha256=receipt['prepared_profile_sha256'])
    provenance_raw=json.dumps(provenance).encode(); prov.write_bytes(provenance_raw)
    tuple_obj=json.loads(tup.read_text())
    tuple_obj.update(build_provenance_sha256=_sha(provenance_raw),
        request_sha256=receipt['request_sha256'],
        prepared_profile_sha256=receipt['prepared_profile_sha256'])
    tuple_raw=json.dumps(tuple_obj).encode(); tup.write_bytes(tuple_raw)
    output=tmp_path/'real-prepared.tgz'
    result=build_bundle(src,tup,prov,manifest,_sha(tuple_raw),output,
                        prepared_dir=selection_dir/'prepared')
    assert result['corresponding_source_complete'] is False
    assert result['distribution_eligible'] is False
    with tarfile.open(fileobj=gzip.GzipFile(fileobj=output.open('rb')),mode='r:') as archive:
        names=archive.getnames()
    assert f'selected-inputs/projects/{project_id}.lunar' in names

def test_rejects_changed_original_source_before_archive_write(tmp_path):
    args=_fixture(tmp_path); prepared,anchor=_prepared_fixture(tmp_path,args)
    src,tup,prov,manifest,_=args
    source=prepared/'content-00.source'; source.write_bytes(source.read_bytes()+b'changed')
    output=tmp_path/'changed.tgz'
    with pytest.raises(ValueError,match='source digest mismatch'):
        build_bundle(src,tup,prov,manifest,anchor,output,prepared_dir=prepared)
    assert not output.exists()

def test_rejects_omitted_and_unselected_prepared_assets(tmp_path):
    args=_fixture(tmp_path); prepared,anchor=_prepared_fixture(tmp_path,args)
    src,tup,prov,manifest,_=args
    (prepared/'content-01.source').unlink()
    with pytest.raises(ValueError,match='regular non-symlink'):
        build_bundle(src,tup,prov,manifest,anchor,tmp_path/'omitted.tgz',prepared_dir=prepared)
    assert not (tmp_path/'omitted.tgz').exists()
    extra_root=tmp_path/'extra-case'; extra_root.mkdir()
    args=_fixture(extra_root); prepared,anchor=_prepared_fixture(extra_root,args,extra=True)
    src,tup,prov,manifest,_=args
    with pytest.raises(ValueError,match='selection identity/order/parent'):
        build_bundle(src,tup,prov,manifest,anchor,tmp_path/'extra.tgz',prepared_dir=prepared)
    assert not (tmp_path/'extra.tgz').exists()

def test_rejects_symlinked_source_and_selection_mismatch(tmp_path):
    args=_fixture(tmp_path); prepared,anchor=_prepared_fixture(tmp_path,args)
    src,tup,prov,manifest,_=args
    source=prepared/'content-00.source'; source.unlink(); source.symlink_to(tmp_path/'outside')
    (tmp_path/'outside').write_bytes(b'{"title":"Demo"}\n')
    with pytest.raises(ValueError,match='regular non-symlink'):
        build_bundle(src,tup,prov,manifest,anchor,tmp_path/'symlink.tgz',prepared_dir=prepared)
    assert not (tmp_path/'symlink.tgz').exists()
    selection_root=tmp_path/'selection-case'; selection_root.mkdir()
    args=_fixture(selection_root); prepared,anchor=_prepared_fixture(selection_root,args)
    src,tup,prov,manifest,_=args
    receipt_path=prepared.parent/'selection.json'; receipt=json.loads(receipt_path.read_text())
    receipt['selected_content'][0]['id']='other-project'
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError,match='selection identity/order/parent'):
        build_bundle(src,tup,prov,manifest,anchor,tmp_path/'selection.tgz',prepared_dir=prepared)
    assert not (tmp_path/'selection.tgz').exists()

def test_rejects_escaped_source_path_in_selection_receipt(tmp_path):
    args=_fixture(tmp_path); prepared,anchor=_prepared_fixture(tmp_path,args)
    src,tup,prov,manifest,_=args
    receipt_path=prepared.parent/'selection.json'; receipt=json.loads(receipt_path.read_text())
    receipt['content'][0]['source']='../../outside.lunar'
    receipt_path.write_text(json.dumps(receipt))
    output=tmp_path/'escaped.tgz'
    with pytest.raises(ValueError,match='source bytes differ'):
        build_bundle(src,tup,prov,manifest,anchor,output,prepared_dir=prepared)
    assert not output.exists()

def test_rejects_symlinked_or_traversing_prepared_directory(tmp_path):
    args=_fixture(tmp_path); prepared,anchor=_prepared_fixture(tmp_path,args)
    src,tup,prov,manifest,_=args
    link=tmp_path/'prepared-link'; link.symlink_to(prepared,target_is_directory=True)
    with pytest.raises(ValueError,match='contains a symlink'):
        build_bundle(src,tup,prov,manifest,anchor,tmp_path/'root-link.tgz',prepared_dir=link)
    traversing=prepared.parent/'..'/'prepared'
    with pytest.raises(ValueError,match='parent traversal'):
        build_bundle(src,tup,prov,manifest,anchor,tmp_path/'traversal.tgz',prepared_dir=traversing)
    assert not (tmp_path/'root-link.tgz').exists()
    assert not (tmp_path/'traversal.tgz').exists()

def test_refuses_true_tuple_admission_flags_with_prepared_inputs(tmp_path):
    args=_fixture(tmp_path); prepared,anchor=_prepared_fixture(tmp_path,args)
    src,tup,prov,manifest,_=args
    tuple_obj=json.loads(tup.read_text()); tuple_obj['installable']=True
    raw=json.dumps(tuple_obj).encode(); tup.write_bytes(raw)
    with pytest.raises(ValueError,match='admission flags'):
        build_bundle(src,tup,prov,manifest,_sha(raw),tmp_path/'admitted.tgz',prepared_dir=prepared)
    assert not (tmp_path/'admitted.tgz').exists()

def test_refuses_true_prepared_selection_admission_flags(tmp_path):
    args=_fixture(tmp_path); prepared,anchor=_prepared_fixture(tmp_path,args)
    src,tup,prov,manifest,_=args
    path=prepared.parent/'selection.json'; selection=json.loads(path.read_text())
    selection['installable']=True; path.write_text(json.dumps(selection))
    output=tmp_path/'admitted-selection.tgz'
    with pytest.raises(ValueError,match='selection admission flags'):
        build_bundle(src,tup,prov,manifest,anchor,output,prepared_dir=prepared)
    assert not output.exists()



def test_selected_source_export_rebuilds_complete_preload_catalogue(tmp_path):
    """Preparation reads every catalogue project, even for a single-song image."""
    from export_image_catalogue import (
        PRELOAD_PROJECTS, export_preload_projects, export_preload_sets,
    )
    assert SOURCE_PRELOAD_INPUTS == frozenset(row['source_path'] for row in PRELOAD_PROJECTS)
    exported = tmp_path / 'exported'
    for row in PRELOAD_PROJECTS:
        relative = row['source_path']
        # Apply the real archive selector, rather than copying a second list.
        if _selected(relative):
            target = exported / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes())
    projects = export_preload_projects(exported)
    assert projects == export_preload_projects(ROOT)
    assert export_preload_sets(exported, projects) == export_preload_sets(ROOT)
    assert not _selected('engines/state/examples/unregistered.lunar')
    assert not _selected('scratch/private-song.lunar')
    # Losing an unselected legacy project still prevents normal preparation.
    (exported / PRELOAD_PROJECTS[0]['source_path']).unlink()
    with pytest.raises(ValueError, match='Missing regular preload source'):
        export_preload_projects(exported)


@pytest.mark.parametrize('option', ['catalogue_root', 'catalogue_manifest',
                                    'libcxx_license', 'pristine_headers'])
def test_refuses_partial_external_header_inputs(tmp_path, option):
    args = _fixture(tmp_path)
    output = tmp_path / 'partial.tgz'
    with pytest.raises(ValueError, match=r'libc\+\+ inclusion requires'):
        build_bundle(*args, output, **{option: tmp_path / 'external'})
    assert not output.exists()


def test_bundle_binds_external_header_collector_to_provenance(tmp_path, monkeypatch):
    # Header tree verification has its own mutation suite. This checks the
    # archive boundary passes the tuple-bound digest, rather than a CLI hash.
    import types
    args = _fixture(tmp_path)
    src, tup, prov, manifest, _ = args
    catalogue_sha = 'a' * 64
    provenance = json.loads(prov.read_bytes())
    provenance['catalogue_tree_sha256'] = catalogue_sha
    provenance_raw = json.dumps(provenance).encode()
    prov.write_bytes(provenance_raw)
    tuple_obj = json.loads(tup.read_bytes())
    tuple_obj['build_provenance_sha256'] = _sha(provenance_raw)
    tuple_raw = json.dumps(tuple_obj).encode()
    tup.write_bytes(tuple_raw)
    calls = []
    external = {'external/libcxx-12.0.0/include/__config': b'pristine headers',
                'external/libcxx-12.0.0/LICENSE.TXT': b'component notice'}
    def collect(**kwargs):
        calls.append(kwargs)
        assert kwargs['expected_catalogue_tree_sha256'] == catalogue_sha
        return external, {'source_identity_verified': True}
    monkeypatch.setitem(sys.modules, 'tools.native.source_libcxx_inputs',
                        types.SimpleNamespace(collect_libcxx_inputs=collect))
    options = {name: tmp_path / name for name in (
        'catalogue_root', 'catalogue_manifest', 'libcxx_license', 'pristine_headers')}
    outputs = [tmp_path / 'headers-one.tgz', tmp_path / 'headers-two.tgz']
    for output in outputs:
        result = build_bundle(src, tup, prov, manifest, _sha(tuple_raw), output, **options)
        assert result['corresponding_source_complete'] is False
        assert result['distribution_eligible'] is False
    assert outputs[0].read_bytes() == outputs[1].read_bytes()
    assert len(calls) == 2
    assert calls[0]['official_license'] == options['libcxx_license']
    with tarfile.open(outputs[0], 'r:gz') as archive:
        report = json.load(archive.extractfile('MANIFEST.json'))
        assert report['libcxx']['source_identity_verified'] is True
        text = archive.extractfile('SOURCE-COMPLETENESS.txt').read().decode()
        assert 'Bounded committed source paths and verified libc++ sources;' in text
        assert 'tuple-bound selected project/SET inputs' not in text
        assert 'Packed project/SET inputs are not bound' in text
        assert report['corresponding_source_complete'] is False
        assert report['distribution_eligible'] is False
        for row in report['external_source_inputs']:
            raw = archive.extractfile(row['path']).read()
            assert raw == external[row['path']]
            assert row['sha256'] == _sha(raw)
            assert row['bytes'] == len(raw)


def test_extracted_recompressor_imports_only_archived_dependencies(tmp_path):
    exported = tmp_path / 'source'
    paths = ('tools/native/recompress_project.py', 'tools/lunar_state.py',
             'tests/__init__.py', 'tests/state_canon.py')
    for name in paths:
        assert _selected(name)
        target = exported / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    # Isolated Python excludes the checkout, PYTHONPATH and user site packages.
    # Import both transitive dependencies and require their actual file paths.
    code = """import sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
from tools.native import recompress_project
from tools import lunar_state
from tests import state_canon
for module in (recompress_project, lunar_state, state_canon):
    assert Path(module.__file__).resolve().is_relative_to(root)
assert recompress_project.MAX_FILE == lunar_state.BIN_MAX
"""
    subprocess.run([sys.executable, '-I', '-c', code, str(exported)],
                   check=True, cwd=tmp_path, capture_output=True)
    assert not _selected('tools/private_utility.py')
    assert not _selected('tests/test_private_fixture.py')


def test_prepared_source_status_text_names_only_included_inputs(tmp_path):
    args = _fixture(tmp_path)
    prepared, anchor = _prepared_fixture(tmp_path, args)
    output = tmp_path / 'prepared-status.tgz'
    build_bundle(*args[:4], anchor, output, prepared_dir=prepared)
    with tarfile.open(output, 'r:gz') as archive:
        text = archive.extractfile('SOURCE-COMPLETENESS.txt').read().decode()
    assert 'and tuple-bound selected project/SET inputs;' in text
    assert 'verified libc++ sources' not in text
    assert 'Exact project/SET source bytes' in text
