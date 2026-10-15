import hashlib, json, subprocess, tarfile, gzip
from pathlib import Path
import pytest
from tools.native.create_gpl_source_bundle import build_bundle

def _sha(b): return hashlib.sha256(b).hexdigest()
def _fixture(tmp_path):
    src=tmp_path/"src"; src.mkdir()
    subprocess.run(["git","init","-q",str(src)],check=True)
    subprocess.run(["git","-C",str(src),"config","user.name","Test"],check=True)
    subprocess.run(["git","-C",str(src),"config","user.email","test@example.invalid"],check=True)
    (src/"LICENSE").write_text("GPL-3.0-only\n")
    (src/"engines").mkdir(); (src/"engines"/"main.c").write_text("int main(void){return 0;}\n")
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

