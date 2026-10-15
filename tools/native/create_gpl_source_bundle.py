#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Create deterministic, explicitly incomplete native source/notices inventory."""
from __future__ import annotations
import argparse,gzip,hashlib,io,json,re,subprocess,tarfile
from pathlib import Path,PurePosixPath
HASH=re.compile(r"^[0-9a-f]{64}$"); MAX_JSON=4*1024*1024; MAX_FILES=10000; MAX_BYTES=512*1024*1024
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
def build_bundle(source,tuple_path,provenance_path,source_manifest_path,expected_tuple_sha256,output):
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
    entries={"SOURCE-COMPLETENESS.txt":("INCOMPLETE SOURCE/NOTICES BUNDLE\ncorresponding_source_complete=false\ndistribution_eligible=false\nBounded committed source paths only; see MANIFEST.json.\nPacked project/SET inputs are not bound to their original source bytes.\nThe external JieLi toolchain is identified by digest but is not included.\nDo not distribute as complete corresponding source.\n").encode(),
    "BUILDING.txt":(f"Source commit: {commit}\nGit tree: {tree}\nProfile: {rec.get('profile_id')}\nToolchain image SHA-256: {rec.get('toolchain_image_sha256')}\nToolchain tree SHA-256: {rec.get('toolchain_tree_sha256')} (not included)\nNo reproducible environment or distribution authorization is provided.\n").encode()}
    entries.update(dict(rows)); files=[{"path":p,"sha256":sha(b),"bytes":len(b)} for p,b in rows]
    manifest={"schema":1,"source_commit":commit,"git_tree":tree,"source_tree_sha256":rec["source_tree_sha256"],"external_tuple_sha256":expected_tuple_sha256,"files":files,"corresponding_source_complete":False,"distribution_eligible":False,"unresolved":["original project and companion SET source bytes are not bound by the tuple","external toolchain/source inputs are not included"]}
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
    a=p.parse_args(); print(json.dumps(build_bundle(a.source,a.tuple_path,a.provenance,a.source_manifest,a.expected_tuple_sha256,a.output),sort_keys=True))
if __name__=="__main__": main()

