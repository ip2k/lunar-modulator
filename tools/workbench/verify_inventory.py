#!/usr/bin/env python3
"""Offline verifier for the pinned M-VAVE Workbench kit and source snapshot."""
from __future__ import annotations
import argparse, hashlib, json, os, re, stat, sys, tarfile, tempfile, unicodedata, zipfile
from pathlib import Path
from typing import BinaryIO

UPSTREAM_COMMIT = "b178ac43c25f010c60a878056fb5331fe693fd62"
KIT_SHA256 = "2a3b2ede16ac49c867831315714ef9d8c532c70ce28ce1dcf3fc76f0a9f68f57"
SOURCE_TAR_SHA256 = "b92779ec8bbff7ffdedce38932738261181aff8fa67718d7cd20cb687b789626"
EXPECTED_FILES, EXPECTED_MANIFEST_FILES = 150, 65
MAX_ARCHIVE_BYTES, MAX_FILE_BYTES, MAX_TOTAL_BYTES, MAX_FILES = 64<<20, 32<<20, 256<<20, 1000
CHUNK = 1<<20

class VerificationError(ValueError):
    """An archive or evidence input is malformed or does not match its pin."""

def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(CHUNK),b""): h.update(b)
    return h.hexdigest()

def norm(name: str, directory: bool=False) -> str:
    name=unicodedata.normalize("NFC",name.replace("\\","/"))
    if "\0" in name or name.startswith("/") or re.match(r"^[A-Za-z]:",name):
        raise VerificationError(f"unsafe absolute path: {name!r}")
    if directory and name.endswith("/"): name=name[:-1]
    parts=name.split("/")
    if not name or any(p in ("",".","..") for p in parts):
        raise VerificationError(f"unsafe/noncanonical path: {name!r}")
    return "/".join(parts)

def zip_index(z: zipfile.ZipFile) -> dict[str,zipfile.ZipInfo]:
    """Return regular ZIP files keyed by normalized path; reject unsafe entries."""
    out,seen={},{}
    total=0
    for i in z.infolist():
        mode=i.external_attr>>16; kind=stat.S_IFMT(mode); isdir=i.is_dir()
        if kind==stat.S_IFLNK or kind not in (0,stat.S_IFREG,stat.S_IFDIR):
            raise VerificationError(f"ZIP link/special file: {i.filename!r}")
        p=norm(i.filename,isdir); key=p.casefold()
        if key in seen: raise VerificationError(f"duplicate normalized ZIP path: {seen[key]!r}, {i.filename!r}")
        seen[key]=i.filename
        if isdir:
            if i.file_size: raise VerificationError(f"directory entry has data: {i.filename}")
            continue
        if kind==stat.S_IFDIR: raise VerificationError(f"directory mode without directory path: {i.filename}")
        if i.file_size>MAX_FILE_BYTES: raise VerificationError("ZIP member exceeds size limit")
        total+=i.file_size
        if len(out)>=MAX_FILES or total>MAX_TOTAL_BYTES: raise VerificationError("ZIP exceeds count/size limit")
        out[p]=i
    return out

def stream_sha(f: BinaryIO) -> str:
    h=hashlib.sha256()
    for b in iter(lambda:f.read(CHUNK),b""): h.update(b)
    return h.hexdigest()

def check_manifest(z: zipfile.ZipFile, files: dict[str,zipfile.ZipInfo]) -> dict:
    """Check all internal file hashes from sdk/manifest.json; no extraction."""
    if "sdk/manifest.json" not in files: raise VerificationError("kit lacks sdk/manifest.json")
    try: m=json.loads(z.read(files["sdk/manifest.json"]).decode("utf-8"))
    except (UnicodeDecodeError,json.JSONDecodeError,zipfile.BadZipFile) as e: raise VerificationError(f"invalid manifest: {e}") from e
    listed=m.get("files")
    if not isinstance(listed,dict) or len(listed)!=EXPECTED_MANIFEST_FILES:
        raise VerificationError(f"manifest file count mismatch: {len(listed) if isinstance(listed,dict) else 'invalid'}")
    for raw,expected in listed.items():
        p=norm(raw); i=files.get(p)
        if i is None: raise VerificationError(f"manifest file missing: {p}")
        if not isinstance(expected,str) or not re.fullmatch("[0-9a-f]{64}",expected):
            raise VerificationError(f"invalid SHA-256 in manifest: {p}")
        with z.open(i) as f: actual=stream_sha(f)
        if actual!=expected: raise VerificationError(f"manifest mismatch: {p}: {actual}")
    ext=m.get("external_toolchain",{}).get("files",{})
    return {"checked":len(listed),"external_toolchain_hash_entries":len(ext),"external_toolchain_bundled":False}

def source_index(root: Path) -> dict[str,Path]:
    root=root.resolve(strict=True); out={}; seen={}; total=0
    for current,dirs,files in os.walk(root,followlinks=False):
        base=Path(current)
        for d in dirs:
            if (base/d).is_symlink(): raise VerificationError(f"source symlink: {base/d}")
        for name in files:
            p=base/name
            if p.is_symlink() or not p.is_file(): raise VerificationError(f"source non-regular file: {p}")
            rel=norm(p.relative_to(root).as_posix()); key=rel.casefold()
            if key in seen: raise VerificationError(f"duplicate normalized source path: {seen[key]}, {rel}")
            seen[key]=rel; size=p.stat().st_size; total+=size
            if len(out)>=MAX_FILES or size>MAX_FILE_BYTES or total>MAX_TOTAL_BYTES: raise VerificationError("source exceeds count/size limit")
            out[rel]=p
    return out

def extract_pinned_tar(tarpath: Path, dest: Path) -> dict[str,Path]:
    """Safely copy regular files from the exact pinned codeload tar into temp storage."""
    if tarpath.stat().st_size>MAX_ARCHIVE_BYTES: raise VerificationError("source tar exceeds compressed-size limit")
    actual=digest(tarpath)
    if actual!=SOURCE_TAR_SHA256: raise VerificationError(f"source tar SHA-256 mismatch: {actual}")
    try:
        with tarfile.open(tarpath,"r:gz") as t:
            members=t.getmembers()
            if len(members)>MAX_FILES*2: raise VerificationError("source tar exceeds member-count limit")
            roots=set(); names={}; regular=[]; total=0
            for m in members:
                raw=m.name.rstrip("/")
                if not raw: raise VerificationError(f"invalid tar member: {m.name!r}")
                parts=raw.split("/"); root=norm(parts[0]); roots.add(root)
                if len(parts)==1:
                    if not m.isdir(): raise VerificationError(f"unexpected tar root file: {m.name!r}")
                    continue
                rel=norm("/".join(parts[1:]),m.isdir())
                if m.isdir():
                    if m.size: raise VerificationError(f"directory with data: {m.name}")
                    continue
                if not m.isfile(): raise VerificationError(f"tar link/special file: {m.name!r}")
                key=rel.casefold()
                if key in names: raise VerificationError(f"duplicate normalized tar path: {names[key]}, {rel}")
                names[key]=rel; regular.append((m,rel)); total+=m.size
                if len(regular)>EXPECTED_FILES or m.size>MAX_FILE_BYTES or total>MAX_TOTAL_BYTES: raise VerificationError("source tar exceeds count/size limit")
            if len(roots)!=1 or len(regular)!=EXPECTED_FILES: raise VerificationError(f"source tar layout/count mismatch: roots={len(roots)}, files={len(regular)}")
            for m,rel in regular:
                target=dest.joinpath(*rel.split("/")); target.parent.mkdir(parents=True,exist_ok=True)
                if not target.parent.resolve().is_relative_to(dest.resolve()): raise VerificationError(f"tar path escapes destination: {rel}")
                f=t.extractfile(m)
                if f is None: raise VerificationError(f"unreadable tar member: {m.name}")
                with f,target.open("xb") as out:
                    remaining=m.size
                    while remaining:
                        b=f.read(min(CHUNK,remaining))
                        if not b: raise VerificationError(f"truncated tar member: {m.name}")
                        out.write(b); remaining-=len(b)
    except (tarfile.TarError,OSError) as e: raise VerificationError(f"cannot read pinned source tar: {e}") from e
    return source_index(dest)

def compare(z: zipfile.ZipFile, kit: dict[str,zipfile.ZipInfo], source: dict[str,Path]) -> dict:
    if set(kit)!=set(source):
        raise VerificationError(f"source path-set mismatch; missing={sorted(set(kit)-set(source))[:8]}, extra={sorted(set(source)-set(kit))[:8]}")
    differences=[]
    for name in sorted(kit):
        with z.open(kit[name]) as a,source[name].open("rb") as b:
            while True:
                x,y=a.read(CHUNK),b.read(CHUNK)
                if x!=y: differences.append(name); break
                if not x: break
    if differences: raise VerificationError(f"source byte differences: {differences[:12]}")
    return {"regular_files_compared":len(kit),"byte_differences":[]}

def verify(kitpath: Path, source_tar: Path) -> dict:
    if kitpath.stat().st_size>MAX_ARCHIVE_BYTES: raise VerificationError("kit exceeds compressed-size limit")
    kh=digest(kitpath)
    if kh!=KIT_SHA256: raise VerificationError(f"kit SHA-256 mismatch: {kh}")
    if kitpath.resolve()==source_tar.resolve(): raise VerificationError("kit and source tar must differ")
    try:
        with zipfile.ZipFile(kitpath) as z:
            files=zip_index(z)
            if len(files)!=EXPECTED_FILES: raise VerificationError(f"kit file count is {len(files)}, expected {EXPECTED_FILES}")
            manifest=check_manifest(z,files)
            with tempfile.TemporaryDirectory(prefix="workbench-source-") as tmp:
                src=extract_pinned_tar(source_tar,Path(tmp)/"src")
                result=compare(z,files,src)
    except zipfile.BadZipFile as e: raise VerificationError(f"invalid kit ZIP: {e}") from e
    return {"upstream_commit":UPSTREAM_COMMIT,"kit_sha256":kh,"source_tar_sha256":digest(source_tar),
            "kit_regular_files":len(files),"source_comparison":result,"manifest":manifest,
            "vendor_tools_executed":False,"device_accessed":False}

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kit",required=True,type=Path); p.add_argument("--source-tar",required=True,type=Path)
    a=p.parse_args()
    try: result=verify(a.kit,a.source_tar)
    except (OSError,VerificationError) as e:
        print(f"verification failed: {e}",file=sys.stderr); return 1
    print(json.dumps(result,indent=2,sort_keys=True)); return 0

if __name__=="__main__": raise SystemExit(main())\n