#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Create deterministic, explicitly incomplete native source/notices inventory."""
from __future__ import annotations
import argparse,gzip,hashlib,io,json,re,subprocess,tarfile
from pathlib import Path,PurePosixPath
HASH=re.compile(r"^[0-9a-f]{64}$"); MAX_JSON=4*1024*1024; MAX_FILES=10000; MAX_BYTES=512*1024*1024
ID=re.compile(r"^[a-z][a-z0-9-]{0,63}$")
PREFIXES=("engines/","firmware/native/","firmware/third_party/","tools/native/","tools/jieli/","sim/web/")
ROOT_FILES=("LICENSE","LICENSE-MIT","LICENSING.md","README.md","DEVELOPERS.md","Makefile")
FORBIDDEN_SUFFIXES=(".fwsc",".bin",".elf",".o",".a",".so",".dylib",".wasm",".zip",".tar",".gz")
FORBIDDEN_PARTS={"photos","scratch","reference","out","build","__pycache__",".git"}
def sha(b): return hashlib.sha256(b).hexdigest()
def _json(path):
    if path.is_symlink(): raise ValueError("symlink JSON input")
    raw=path.read_bytes()
    if len(raw)>MAX_JSON: raise ValueError("oversized JSON input")
    def unique(pairs):
        out={}
        for k,v in pairs:
            if k in out: raise ValueError("duplicate JSON key")
            out[k]=v
        return out
    value=json.loads(raw.decode("utf-8"),object_pairs_hook=unique)
    if not isinstance(value,dict): raise ValueError("JSON input must be object")
    return raw,value
def _git(root,*args): return subprocess.check_output(["git","-C",str(root),*args],text=True).strip()
def _selected(path):
    p=PurePosixPath(path)
    if p.is_absolute() or any(x in ("",".","..") or x in FORBIDDEN_PARTS for x in p.parts): return False
    if path in ROOT_FILES: return True
    if not path.startswith(PREFIXES) or path.lower().endswith(FORBIDDEN_SUFFIXES): return False
    return p.name in {"Makefile","CMakeLists.txt","meson.build","UPSTREAM.md","LICENSE","COPYING","NOTICE","LICENSING.md"} or p.suffix.lower() in {".c",".cc",".cpp",".h",".hpp",".py",".mk",".cmake",".json",".md",".txt",".S",".s",".inc",".ld",".sh",".yml",".yaml",".ini"}
def _source_rows(root,commit,expected):
    if _git(root,"rev-parse","HEAD")!=commit: raise ValueError("source checkout does not match tuple provenance commit")
    if _git(root,"status","--porcelain","--untracked-files=all"): raise ValueError("source checkout must be clean")
    tree=_git(root,"rev-parse",f"{commit}^{{tree}}"); allrows=[]; selected=[]; total=0
    paths=subprocess.check_output(["git","-C",str(root),"ls-files","-z"]).decode().split("\0")
    for path in paths:
        if not path: continue
        data=subprocess.check_output(["git","-C",str(root),"show",f"{commit}:{path}"])
        allrows.append({"path":path,"sha256":sha(data)})
        if _selected(path):
            if len(data)>MAX_BYTES: raise ValueError("source file exceeds per-file bound")
            selected.append((path,data)); total+=len(data)
            if len(selected)>MAX_FILES or total>MAX_BYTES: raise ValueError("source bundle exceeds bounds")
    allrows.sort(key=lambda row:row["path"])
    if expected.get("objects")!=allrows: raise ValueError("source manifest does not match exact committed source tree")
    return tree,selected
def _prepared_source_inputs(prepared_dir,rec):
    """Return exact codec source bytes after the existing prepared-input checks."""
    # Keep the validator's existing script/package import convention working.
    import sys
    native_dir=str(Path(__file__).resolve().parent)
    if native_dir not in sys.path:
        sys.path.insert(0,native_dir)
    from verify_image_profile import load_prepared_profile
    expected=rec.get("prepared_profile_sha256")
    if not isinstance(expected,str) or not HASH.fullmatch(expected):
        raise ValueError("tuple lacks a prepared profile digest for selected source inputs")
    directory=Path(prepared_dir)
    # The validator reads the source files once and returns those exact bytes;
    # bundle those returned bytes rather than reopening after verification.
    checked=load_prepared_profile(directory,expected)
    prepared=directory.resolve(strict=True)
    selection_path=prepared.parent/"selection.json"
    request_path=prepared.parent/"request.json"
    for candidate in (selection_path,request_path):
        if candidate.is_symlink() or not candidate.is_file():
            raise ValueError("prepared selection/request receipt must be a regular file")
        if not candidate.resolve(strict=True).is_relative_to(prepared.parent.resolve(strict=True)):
            raise ValueError("prepared selection/request receipt escapes snapshot directory")
    _,selection=_json(selection_path); rr,request=_json(request_path)
    if (sha(rr)!=rec.get("request_sha256") or selection.get("request_sha256")!=sha(rr)
            or selection.get("status")!="prepared-build-inputs"
            or selection.get("prepared_profile_sha256")!=expected):
        raise ValueError("prepared selection/request is not bound to tuple")
    if type(request.get("version")) is not int or request.get("version")!=1:
        raise ValueError("prepared request schema is unsupported")
    if any(selection.get(key) is not False for key in
           ("installable","native_link_verified","native_ram_verified","hardware_tested")):
        raise ValueError("prepared selection admission flags must remain false")
    project_ids=request.get("project_ids"); set_ids=request.get("set_ids",[])
    startup=request.get("startup_index")
    if (not isinstance(project_ids,list) or not project_ids
            or any(not isinstance(x,str) or not ID.fullmatch(x) for x in project_ids)
            or len(set(project_ids))!=len(project_ids)
            or not isinstance(set_ids,list)
            or any(not isinstance(x,str) or not ID.fullmatch(x) for x in set_ids)
            or len(set(set_ids))!=len(set_ids)
            or type(startup) is not int or not 0<=startup<len(project_ids)):
        raise ValueError("prepared request selection identity is malformed")
    parent=project_ids[startup]
    expected_rows=([{"kind":"project","id":x} for x in project_ids]
                   +[{"kind":"set","id":x,"parent_project_id":parent} for x in set_ids])
    if (selection.get("selected_content")!=expected_rows
            or selection.get("project_ids")!=project_ids
            or selection.get("set_ids")!=set_ids
            or selection.get("startup_index")!=startup
            or selection.get("startup_project_id")!=parent):
        raise ValueError("prepared selection identity/order/parent differs from request")
    receipt_rows=selection.get("content")
    assets=checked.report.get("content")
    if (not isinstance(receipt_rows,list) or len(receipt_rows)!=len(expected_rows)
            or len(assets)!=len(expected_rows) or len(checked.source_content)!=len(expected_rows)):
        raise ValueError("prepared selected source inputs are incomplete")
    result=[]
    for identity,row,asset,raw in zip(expected_rows,receipt_rows,assets,checked.source_content):
        expected_path=(f"projects/{identity['id']}.lunar" if identity["kind"]=="project"
                       else f"sets/{identity['id']}.movy1")
        if (not isinstance(row,dict) or not isinstance(asset,dict)
                or row.get("id")!=identity["id"] or row.get("kind")!=identity["kind"]
                or row.get("parent_project_id")!=identity.get("parent_project_id")
                or row.get("source")!=expected_path or asset.get("source")!=expected_path
                or row.get("source_sha256")!=asset.get("source_sha256")
                or not isinstance(asset.get("source_sha256"),str)
                or not HASH.fullmatch(asset["source_sha256"])
                or sha(raw)!=asset["source_sha256"]):
            raise ValueError("prepared selected source bytes differ from receipt/profile")
        suffix=".lunar" if identity["kind"]=="project" else ".movy1"
        archive_path=f"selected-inputs/{identity['kind']}s/{identity['id']}{suffix}"
        result.append({"path":archive_path,"kind":identity["kind"],"id":identity["id"],
                       **({"parent_project_id":identity["parent_project_id"]}
                          if identity["kind"]=="set" else {}),
                       "sha256":sha(raw),"bytes":len(raw),"data":raw})
    return result

def build_bundle(source,tuple_path,provenance_path,source_manifest_path,expected_tuple_sha256,output,*,prepared_dir=None):
    if not isinstance(expected_tuple_sha256,str) or not HASH.fullmatch(expected_tuple_sha256): raise ValueError("external tuple SHA-256 invalid")
    tr,rec=_json(tuple_path)
    if sha(tr)!=expected_tuple_sha256: raise ValueError("tuple differs from external trust anchor")
    if type(rec.get("schema")) is not int or rec["schema"]!=2: raise ValueError("only fresh schema-2 tuples accepted")
    if any(rec.get(k) is not False for k in ("hardware_admitted","hardware_tested","installable")): raise ValueError("tuple admission flags must remain false")
    pr,prov=_json(provenance_path)
    if sha(pr)!=rec.get("build_provenance_sha256"): raise ValueError("build provenance digest mismatch")
    commit=prov.get("source_commit")
    if not isinstance(commit,str) or not re.fullmatch(r"[0-9a-f]{40}",commit): raise ValueError("missing pinned source commit")
    if prov.get("source_tree_sha256")!=rec.get("source_tree_sha256"): raise ValueError("tuple/provenance source tree mismatch")
    mr,sm=_json(source_manifest_path)
    if sha(mr)!=rec.get("source_tree_sha256"): raise ValueError("source manifest differs from tuple digest")
    if sm.get("commit")!=commit or type(sm.get("schema")) is not int or sm.get("schema")!=1: raise ValueError("source manifest commit/schema mismatch")
    tree,rows=_source_rows(source.resolve(),commit,sm)
    if prepared_dir is not None and (prov.get("prepared_profile_sha256")!=rec.get("prepared_profile_sha256")
            or prov.get("request_sha256")!=rec.get("request_sha256")):
        raise ValueError("tuple/provenance prepared selection identity mismatch")
    selected_inputs=_prepared_source_inputs(prepared_dir,rec) if prepared_dir is not None else []
    entries={"SOURCE-COMPLETENESS.txt":("INCOMPLETE SOURCE/NOTICES BUNDLE\ncorresponding_source_complete=false\ndistribution_eligible=false\nBounded committed source paths and tuple-bound selected project/SET inputs only; see MANIFEST.json.\n"+("Exact project/SET source bytes used by the state codec are included.\n" if prepared_dir is not None else "Packed project/SET inputs are not bound to their original source bytes.\n")+"The external JieLi toolchain is identified by digest but is not included.\nDo not distribute as complete corresponding source.\n").encode(),
    "BUILDING.txt":(f"Source commit: {commit}\nGit tree: {tree}\nProfile: {rec.get('profile_id')}\nToolchain image SHA-256: {rec.get('toolchain_image_sha256')}\nToolchain tree SHA-256: {rec.get('toolchain_tree_sha256')} (not included)\nNo reproducible environment or distribution authorization is provided.\n").encode()}
    entries.update(dict(rows)); files=[{"path":p,"sha256":sha(b),"bytes":len(b)} for p,b in rows]
    selected_rows=[]
    for item in selected_inputs:
        entries[item["path"]]=item["data"]
        selected_rows.append({k:v for k,v in item.items() if k!="data"})
    unresolved=["external toolchain/source inputs are not included"]
    if prepared_dir is None:
        unresolved.insert(0,"original project and companion SET source bytes are not bound by the tuple")
    manifest={"schema":1,"source_commit":commit,"git_tree":tree,"source_tree_sha256":rec["source_tree_sha256"],"external_tuple_sha256":expected_tuple_sha256,"files":files,"selected_source_inputs":selected_rows,"corresponding_source_complete":False,"distribution_eligible":False,"unresolved":unresolved}
    entries["MANIFEST.json"]=(json.dumps(manifest,sort_keys=True,indent=2)+"\n").encode()
    raw=io.BytesIO()
    with tarfile.open(fileobj=raw,mode="w",format=tarfile.PAX_FORMAT) as tar:
        for name in sorted(entries):
            b=entries[name]; info=tarfile.TarInfo(name); info.size=len(b); info.mtime=0; info.uid=0; info.gid=0; info.uname=""; info.gname=""; info.mode=0o644; tar.addfile(info,io.BytesIO(b))
    packed=io.BytesIO()
    with gzip.GzipFile(fileobj=packed,mode="wb",filename="",mtime=0,compresslevel=9) as gz: gz.write(raw.getvalue())
    output.parent.mkdir(parents=True,exist_ok=True); output.write_bytes(packed.getvalue())
    return {"archive_sha256":sha(packed.getvalue()),"archive_bytes":len(packed.getvalue()),"tuple_sha256":expected_tuple_sha256,"source_commit":commit,"corresponding_source_complete":False,"distribution_eligible":False,"file_count":len(entries)}
def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--source",type=Path,required=True); p.add_argument("--tuple",dest="tuple_path",type=Path,required=True); p.add_argument("--provenance",type=Path,required=True); p.add_argument("--source-manifest",type=Path,required=True); p.add_argument("--expected-tuple-sha256",required=True); p.add_argument("--output",type=Path,required=True)
    p.add_argument("--prepared-dir",type=Path,help="tuple-bound prepared profile directory containing exact project/SET source snapshots")
    a=p.parse_args(); print(json.dumps(build_bundle(a.source,a.tuple_path,a.provenance,a.source_manifest,a.expected_tuple_sha256,a.output,prepared_dir=a.prepared_dir),sort_keys=True))
if __name__=="__main__": main()

