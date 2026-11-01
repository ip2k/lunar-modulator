#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Create deterministic, explicitly incomplete native source/notices inventory."""
from __future__ import annotations
import argparse,gzip,hashlib,io,json,re,subprocess,tarfile
import os,stat
from pathlib import Path,PurePosixPath
HASH=re.compile(r"^[0-9a-f]{64}$"); MAX_JSON=4*1024*1024; MAX_FILES=10000; MAX_BYTES=512*1024*1024
ID=re.compile(r"^[a-z][a-z0-9-]{0,63}$")
PREFIXES=("engines/","firmware/native/","firmware/third_party/","tools/native/","tools/jieli/","sim/web/")
ROOT_FILES=("LICENSE","LICENSE-MIT","LICENSING.md","README.md","DEVELOPERS.md","Makefile")
SOURCE_BUILD_INPUTS=frozenset({"engines/modules/default.list", "tools/lunar_state.py",
                               "tests/__init__.py", "tests/state_canon.py"})
# Preparation exports the entire fixed preload catalogue before selecting IDs.
# Retain those committed source inputs independently of selected-input snapshots.
SOURCE_PRELOAD_INPUTS=frozenset(
    [f"engines/state/examples/{name}.lunar" for name in
     ("afterglow-relay", "event-horizon", "packet-bloom", "neon-transit")]
    + [f"engines/state/examples/replacement-showcases/{name}.lunar" for name in
       ("afterglow-relay-showcase", "event-horizon-showcase",
        "packet-bloom-showcase", "satellite-hearts")]
    + [f"engines/state/examples/init-starters/{name}.lunar" for name in
       ("macro-init", "shapes-init", "trio-init")])
SOURCE_MEDIA=frozenset(f"engines/third_party/fm1-x0x/assets/909/{name}.wav"
                       for name in ("hh","ride","crash"))
GENERATED_LINK_SOURCE_FIXED=frozenset({
    "link/crt0.S", "link/gen/fm1_gpl_mods.h", "link/gfx.c", "link/libc.c",
    "link/gen/fm1_modules.h", "link/lunar_font.h", "link/measure_app_storage.c", "link/platform.c",
    "link/wave_tables.inc",
})
GENERATED_LINK_LEGACY_METADATA=frozenset({
    "selection/prepared/fm1_modules.h",
    "selection/prepared/modules/gen/fm1_modules.h",
    "link/module-all/gen/fm1_modules.h",
    "link/module-selection/gen/fm1_modules.h",
    "link/wave_tables.json",
})
GENERATED_LINK_RESOURCE_NAMESPACES=("braids","plaits")
MAX_GENERATED_LINK_FILE=8*1024*1024
MAX_GENERATED_LINK_BYTES=32*1024*1024
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
    if path in ROOT_FILES or path in SOURCE_BUILD_INPUTS: return True
    if not path.startswith(PREFIXES) or path.lower().endswith(FORBIDDEN_SUFFIXES): return False
    return path in SOURCE_BUILD_INPUTS or path in SOURCE_PRELOAD_INPUTS or path in SOURCE_MEDIA or p.name in {"Makefile","CMakeLists.txt","meson.build","UPSTREAM.md","LICENSE","LICENSE-Open303","COPYING","COPYRIGHT","NOTICE","LICENSING.md"} or p.suffix.lower() in {".c",".cc",".cpp",".h",".hpp",".py",".mk",".cmake",".json",".md",".txt",".S",".s",".inc",".ld",".sh",".yml",".yaml",".ini",".patch"}
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
    lexical=directory if directory.is_absolute() else Path.cwd()/directory
    if ".." in lexical.parts:
        raise ValueError("prepared directory path must not contain parent traversal")
    current=Path(lexical.anchor)
    for part in lexical.parts[1:]:
        current=current/part
        if current.is_symlink():
            raise ValueError("prepared directory path contains a symlink")
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

def _generated_link_source_paths(prov):
    """Return the exact allowed generated-source set asserted by a fresh capture."""
    marker=prov.get("generated_link_source_inventory")
    if (not isinstance(marker,dict) or set(marker)!={"schema","paths","bytes"}
            or type(marker.get("schema")) is not int or marker["schema"]!=1
            or type(marker.get("bytes")) is not int or marker["bytes"]<0):
        raise ValueError("fresh generated-link source inventory marker is required")
    rows=prov.get("generated_link_resources")
    if rows!=prov.get("module_and_generated_inputs") or not isinstance(rows,list):
        raise ValueError("generated-link inventory differs from tuple capture rows")
    recorded={}
    for row in rows:
        if not isinstance(row,dict) or set(row)!={"path","sha256"}:
            raise ValueError("generated-link provenance row is malformed")
        path=row["path"]
        if not isinstance(path,str) or not path or "\\" in path:
            raise ValueError("generated-link provenance path is malformed")
        rel=PurePosixPath(path)
        if rel.is_absolute() or str(rel)!=path or any(part in ("",".","..") for part in rel.parts):
            raise ValueError("generated-link provenance path is unsafe")
        if not isinstance(row["sha256"],str) or not HASH.fullmatch(row["sha256"]):
            raise ValueError("generated-link provenance digest is malformed")
        if path in recorded:
            raise ValueError("generated-link provenance repeats a path")
        recorded[path]=row["sha256"]
    embedded=prov.get("embedded_content")
    has_content=isinstance(embedded,dict) and bool(embedded)
    expected=set(GENERATED_LINK_SOURCE_FIXED)
    if has_content:
        if (type(embedded.get("asset_count")) is not int or embedded["asset_count"]<=0
                or not isinstance(embedded.get("source_sha256"),str)
                or not HASH.fullmatch(embedded["source_sha256"])):
            raise ValueError("embedded-content receipt cannot select generated content source")
        expected.add("link/content_catalogue.c")
    resource_rows={path for path in recorded if path.startswith("link/resources_")}
    allowed_resources=set()
    for namespace in GENERATED_LINK_RESOURCE_NAMESPACES:
        pair={f"link/resources_{namespace}.cc",f"link/resources_{namespace}.h"}
        if pair & resource_rows:
            if not pair <= resource_rows:
                raise ValueError("generated resource namespace is missing its source/header pair")
            allowed_resources.update(pair)
    if resource_rows!=allowed_resources:
        raise ValueError("generated resource namespace is not in the fixed selection policy")
    expected.update(allowed_resources)
    expected_rows=expected|GENERATED_LINK_LEGACY_METADATA
    if recorded.keys()!=expected_rows:
        raise ValueError("generated-link provenance has missing or unexpected inventory paths")
    paths=marker.get("paths")
    if (not isinstance(paths,list) or paths!=sorted(expected)
            or len(paths)!=len(set(paths))):
        raise ValueError("generated-link marker paths differ from fixed selected-source policy")
    # Other rows are pre-existing generated metadata (selected module headers,
    # wave_tables.json, etc.); they remain validated by the package loader but
    # are intentionally outside this source-payload namespace.
    return sorted(expected),recorded,marker["bytes"]

def _collect_generated_link_sources(root,prov):
    paths,recorded,expected_total=_generated_link_source_paths(prov)
    root=Path(root)
    lexical=root if root.is_absolute() else Path.cwd()/root
    if ".." in lexical.parts:
        raise ValueError("generated-link root must not contain parent traversal")
    current=Path(lexical.anchor)
    for part in lexical.parts[1:]:
        current=current/part
        if current.is_symlink():
            raise ValueError("generated-link root contains a symlink")
    resolved=lexical.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("generated-link root is not a directory")
    entries={}; rows=[]; total=0
    for path in paths:
        rel=PurePosixPath(path)
        candidate=resolved.joinpath(*rel.parts)
        current=resolved
        for part in rel.parts:
            current=current/part
            if current.is_symlink():
                raise ValueError("generated-link source contains a symlink")
        try:
            descriptor=os.open(candidate,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0)|getattr(os,"O_NONBLOCK",0))
        except OSError as exc:
            raise ValueError("generated-link source is not a regular file: "+path) from exc
        with os.fdopen(descriptor,"rb") as stream:
            info=os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or not 0<info.st_size<=MAX_GENERATED_LINK_FILE:
                raise ValueError("generated-link source exceeds per-file bound or is not regular")
            raw=stream.read(MAX_GENERATED_LINK_FILE+1)
            if len(raw)!=info.st_size:
                raise ValueError("generated-link source changed while reading")
        if not raw:
            raise ValueError("generated-link source is not a regular file: "+path)
        total+=len(raw)
        if total>MAX_GENERATED_LINK_BYTES:
            raise ValueError("generated-link source inventory exceeds aggregate bound")
        if sha(raw)!=recorded[path]:
            raise ValueError("generated-link source bytes differ from tuple-bound provenance: "+path)
        archive_path="generated-link/"+path
        entries[archive_path]=raw
        rows.append({"source_path":path,"path":archive_path,"sha256":sha(raw),"bytes":len(raw)})
    if total!=expected_total:
        raise ValueError("generated-link source byte total differs from capture marker")
    return entries,{"schema":1,"bytes":total,"files":rows}

def build_bundle(source,tuple_path,provenance_path,source_manifest_path,expected_tuple_sha256,output,*,prepared_dir=None,
                 catalogue_root=None,catalogue_manifest=None,libcxx_license=None,pristine_headers=None,
                 compiler_trace=None,expected_trace_sha256=None,toolchain_root=None,
                 toolchain_manifest=None,newlib_copying_newlib=None,newlib_copying=None,
                 clang_license=None,llvm_license=None,generated_link_root=None):
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
    header_options=(catalogue_root,catalogue_manifest,libcxx_license,pristine_headers)
    if any(option is not None for option in header_options) and not all(
            option is not None for option in header_options):
        raise ValueError("libc++ inclusion requires catalogue root, manifest, license and pristine headers")
    external_entries={}; external_metadata=None
    if all(option is not None for option in header_options):
        if __package__:
            from .source_libcxx_inputs import collect_libcxx_inputs
        else:
            from source_libcxx_inputs import collect_libcxx_inputs
        external_entries,external_metadata=collect_libcxx_inputs(
            catalogue_root=Path(catalogue_root),catalogue_manifest=Path(catalogue_manifest),
            expected_catalogue_tree_sha256=prov.get("catalogue_tree_sha256"),
            official_license=Path(libcxx_license),pristine_headers=Path(pristine_headers))
    compiler_options=(compiler_trace,expected_trace_sha256,toolchain_root,toolchain_manifest,
                      newlib_copying_newlib,newlib_copying,clang_license,llvm_license)
    if any(option is not None for option in compiler_options) and not all(
            option is not None for option in compiler_options):
        raise ValueError("compiler-header inclusion requires trace anchor, toolchain, manifest and all fixed notices")
    compiler_entries={}; compiler_metadata=None
    if all(option is not None for option in compiler_options):
        if __package__:
            from .source_compiler_headers import collect_compiler_headers
        else:
            from source_compiler_headers import collect_compiler_headers
        manifest_raw,manifest_value=_json(Path(toolchain_manifest))
        manifest_digest=sha(manifest_raw)
        try:
            manifest_canonical=(json.dumps(manifest_value,sort_keys=True,separators=(",", ":"),ensure_ascii=True).encode("ascii"))
        except (TypeError,ValueError) as exc:
            raise ValueError("toolchain manifest is not canonical JSON data") from exc
        if manifest_raw.rstrip(b"\n") != manifest_canonical:
            raise ValueError("toolchain manifest must use canonical JSON encoding")
        compiler_entries,compiler_metadata=collect_compiler_headers(
            trace_path=Path(compiler_trace),expected_trace_sha256=expected_trace_sha256,
            tuple_record=rec,provenance=prov,source_root=Path(source).resolve(),toolchain_root=Path(toolchain_root),
            toolchain_manifest=manifest_value,toolchain_manifest_sha256=manifest_digest,
            expected_tuple_sha256=expected_tuple_sha256,
            official_sources={
                "newlib/COPYING.NEWLIB":Path(newlib_copying_newlib),
                "newlib/COPYING":Path(newlib_copying),
                "clang/LICENSE.TXT":Path(clang_license),"llvm/LICENSE.TXT":Path(llvm_license)})
    if prepared_dir is not None and (
            prov.get("prepared_profile_sha256") != rec.get("prepared_profile_sha256")
            or prov.get("request_sha256") != rec.get("request_sha256")
            or prov.get("prepared_profile_receipt_sha256") != rec.get("prepared_profile_sha256")
            or prov.get("request_receipt_sha256") != rec.get("request_sha256")):
        raise ValueError("tuple/provenance prepared selection identity mismatch")
    selected_inputs=_prepared_source_inputs(prepared_dir,rec) if prepared_dir is not None else []
    generated_link_entries={}; generated_link_metadata=None
    if generated_link_root is not None:
        generated_link_entries,generated_link_metadata=_collect_generated_link_sources(
            generated_link_root,prov)
    source_scope="Bounded committed source paths"
    if prepared_dir is not None:
        source_scope+=" and tuple-bound selected project/SET inputs"
    if external_metadata is not None:
        source_scope+=" and verified libc++ sources"
    if generated_link_metadata is not None:
        source_scope+=" and tuple-bound generated link source inputs"
    source_scope+="; see MANIFEST.json.\n"
    building=(f"Source commit: {commit}\nGit tree: {tree}\nProfile: {rec.get('profile_id')}\nToolchain image SHA-256: {rec.get('toolchain_image_sha256')}\nToolchain tree SHA-256: {rec.get('toolchain_tree_sha256')} (not included)\n"
              "\nHost state-codec tool (fm1-state):\n"
              "From a clean source extraction, build with a fresh output directory:\n"
              "  make -C engines BUILD=build/source-bundle-host FM1_GPL_MODS=1 FM1_MODULES=all OPT=-O2 EXTRA= CC=cc CXX=g++ -j4 build/source-bundle-host/fm1-state\n"
              "This host recipe uses the host C/C++ compilers; it is separate from the pi32v2 target compiler/toolchain identified above. The host compiler binaries, versions and consumed system dependencies are not separately inventoried here.\n"
              "No reproducible environment or distribution authorization is provided.\n")
    entries={"SOURCE-COMPLETENESS.txt":("INCOMPLETE SOURCE/NOTICES BUNDLE\ncorresponding_source_complete=false\ndistribution_eligible=false\n"+source_scope+("Exact project/SET source bytes used by the state codec are included.\n" if prepared_dir is not None else "Packed project/SET inputs are not bound to their original source bytes.\n")+"The external JieLi toolchain is identified by digest but is not included.\nDo not distribute as complete corresponding source.\n").encode(),
    "BUILDING.txt":building.encode()}
    entries.update(dict(rows)); files=[{"path":p,"sha256":sha(b),"bytes":len(b)} for p,b in rows]
    selected_rows=[]
    for item in selected_inputs:
        entries[item["path"]]=item["data"]
        selected_rows.append({k:v for k,v in item.items() if k!="data"})
    unresolved=["external compiler/toolchain sources and executables are not included"]
    if prepared_dir is None:
        unresolved.insert(0,"original project and companion SET source bytes are not bound by the tuple")
    manifest={"schema":1,"source_commit":commit,"git_tree":tree,"source_tree_sha256":rec["source_tree_sha256"],"external_tuple_sha256":expected_tuple_sha256,"files":files,"selected_source_inputs":selected_rows,"corresponding_source_complete":False,"distribution_eligible":False,"unresolved":unresolved}
    if generated_link_metadata is not None:
        if set(entries)&set(generated_link_entries):
            raise ValueError("generated-link source paths collide with archive inputs")
        entries.update(generated_link_entries)
        manifest["generated_link_sources"]=generated_link_metadata
        entries["SOURCE-COMPLETENESS.txt"]+=(
            b"Tuple-bound generated link source payloads are included under generated-link/.\n"
            b"This inventory does not prove compiler consumption or complete corresponding source.\n")
    if external_metadata is not None:
        if set(entries) & set(external_entries):
            raise ValueError("external source paths collide with archive inputs")
        entries.update(external_entries)
        manifest["libcxx"]=external_metadata
        manifest["external_source_inputs"]=[
            {"path":name,"sha256":sha(raw),"bytes":len(raw)}
            for name,raw in sorted(external_entries.items())]
        entries["SOURCE-COMPLETENESS.txt"]+=(
            b"Tuple-bound libc++ source headers and fixed component notice are included.\n"
            b"This bounded addition does not establish complete corresponding source.\n")
    if compiler_metadata is not None:
        if set(entries) & set(compiler_entries):
            raise ValueError("compiler trace/source paths collide with archive inputs")
        entries.update(compiler_entries)
        manifest["compiler_headers"]=compiler_metadata
        manifest["unresolved"].append(
            "container/system dependencies and non-header toolchain files in the trace are not exported by the compiler-header collector")
        entries["SOURCE-COMPLETENESS.txt"]+=(
            b"Independently anchored target trace, consumed pi32v2/Clang headers and fixed upstream notices are included.\n"
            b"System/container dependencies remain unarchived; this addition does not establish complete corresponding source.\n")
    entries["MANIFEST.json"]=(json.dumps(manifest,sort_keys=True,indent=2)+"\n").encode()
    if len(entries)>MAX_FILES or sum(len(raw) for raw in entries.values())>MAX_BYTES:
        raise ValueError("complete source archive exceeds bounds")
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
    p.add_argument("--catalogue-root",type=Path)
    p.add_argument("--catalogue-manifest",type=Path)
    p.add_argument("--libcxx-license",type=Path)
    p.add_argument("--pristine-headers",type=Path)
    p.add_argument("--compiler-trace",type=Path,help="independent final target trace aggregate (requires an external expected SHA-256)")
    p.add_argument("--expected-trace-sha256")
    p.add_argument("--toolchain-root",type=Path)
    p.add_argument("--toolchain-manifest",type=Path)
    p.add_argument("--newlib-copying-newlib",type=Path)
    p.add_argument("--newlib-copying",type=Path)
    p.add_argument("--clang-license",type=Path)
    p.add_argument("--llvm-license",type=Path)
    p.add_argument("--generated-link-root",type=Path,
                   help="build output root containing generated link sources; requires fresh inventory marker")
    a=p.parse_args(); print(json.dumps(build_bundle(a.source,a.tuple_path,a.provenance,a.source_manifest,a.expected_tuple_sha256,a.output,prepared_dir=a.prepared_dir,
        catalogue_root=a.catalogue_root,catalogue_manifest=a.catalogue_manifest,
        libcxx_license=a.libcxx_license,pristine_headers=a.pristine_headers,
        compiler_trace=a.compiler_trace,expected_trace_sha256=a.expected_trace_sha256,
        toolchain_root=a.toolchain_root,toolchain_manifest=a.toolchain_manifest,
        newlib_copying_newlib=a.newlib_copying_newlib,newlib_copying=a.newlib_copying,
        clang_license=a.clang_license,llvm_license=a.llvm_license,
        generated_link_root=a.generated_link_root),sort_keys=True))
if __name__=="__main__": main()

