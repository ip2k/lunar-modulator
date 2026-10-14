#!/usr/bin/env python3
"""Read-only per-chunk raw-DEFLATE size study for valid LUNARB files."""
import argparse, hashlib, json, struct, zlib, sys
from pathlib import Path

MAGIC = b"\x89Lunar\r\n"

def chunks(data):
    if len(data) < 32 or data[:8] != MAGIC: raise ValueError("not LUNARB")
    if struct.unpack_from('<I', data, 28)[0] != (zlib.crc32(data[:28]) & 0xffffffff): raise ValueError("header CRC")
    hdr,n,esz,_,total=struct.unpack_from('<HHHHI',data,12)
    if total != len(data) or esz < 20: raise ValueError("length/directory")
    de=hdr+n*esz
    if struct.unpack_from('<I',data,de)[0] != (zlib.crc32(data[hdr:de]) & 0xffffffff): raise ValueError("directory CRC")
    out=[]; prev=(de+4+3)&~3
    for i in range(n):
        e=data[hdr+i*esz:hdr+i*esz+20]
        tag=e[:4].decode('ascii'); ver,flags,off,ln,crc=struct.unpack_from('<HHIII',e,4)
        if flags & ~1 or off & 3 or off < prev or off+ln>total: raise ValueError(f"invalid entry {i}")
        if any(data[prev:off]): raise ValueError(f"nonzero padding {i}")
        stored=data[off:off+ln]
        if (zlib.crc32(stored) & 0xffffffff)!=crc: raise ValueError(f"chunk CRC {i}")
        if flags&1:
            if ln<4: raise ValueError("short deflated chunk")
            ulen=struct.unpack_from('<I',stored)[0]
            dec=zlib.decompressobj(-12); raw=dec.decompress(stored[4:])+dec.flush()
            if len(raw)!=ulen or not dec.eof or dec.unused_data or dec.unconsumed_tail: raise ValueError("bad existing raw stream")
        else: raw=stored
        out.append(dict(tag=tag,ver=ver,flags=flags,raw=raw,stored=stored))
        prev=off+ln
    if prev!=total: raise ValueError("trailing bytes")
    return out

def encode(raw, level):
    c=zlib.compressobj(level,zlib.DEFLATED,-12)
    packed=c.compress(raw)+c.flush()
    if len(packed)<=0: raise ValueError("compression returned nonpositive size")
    d=zlib.decompressobj(-12); restored=d.decompress(packed)+d.flush()
    if restored!=raw or not d.eof or d.unused_data or d.unconsumed_tail: raise ValueError("round trip mismatch")
    return packed

def reserialized_size(items, packed_by_index, policy):
    dir_end=32+20*len(items)+4; base=(dir_end+3)&~3; total=base
    for i,ch in enumerate(items):
        raw=ch['raw']; packed=packed_by_index[i]
        use=(packed is not None and policy(ch,packed))
        stored=(struct.pack('<I',len(raw))+packed) if use else raw
        total=(total+3)&~3; total+=len(stored)
    return total

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('files',nargs='+'); a=ap.parse_args()
    report={'python':sys.version.split()[0],'zlib_compile':zlib.ZLIB_VERSION,'zlib_runtime':zlib.ZLIB_RUNTIME_VERSION,'files':[]}
    for fn in a.files:
        data=Path(fn).read_bytes(); cs=chunks(data)
        policies={}
        for level in (1,6,9):
            packed=[encode(c['raw'],level) for c in cs]
            policies[f'zlib_raw_w12_level_{level}']={
              'always_deflated_container_bytes':reserialized_size(cs,packed,lambda c,p:True),
              'if_smaller_container_bytes':reserialized_size(cs,packed,lambda c,p:len(p)+4 < len(c['raw'])),
              'writer_75pct_gate_container_bytes':reserialized_size(cs,packed,lambda c,p:(len(p)+4)*4 <= len(c['raw'])*3),
              'chunks':[{'tag':c['tag'],'raw':len(c['raw']),'encoded':len(p),'existing_flag':c['flags']} for c,p in zip(cs,packed)]}
        report['files'].append({'path':fn,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'chunks':[
          {'tag':c['tag'],'raw_bytes':len(c['raw']),'stored_bytes':len(c['stored']),'old_deflated':bool(c['flags']&1),'raw_sha256':hashlib.sha256(c['raw']).hexdigest()} for c in cs],
          'policies':policies})
    print(json.dumps(report,indent=2,sort_keys=True))
if __name__=='__main__': main()
