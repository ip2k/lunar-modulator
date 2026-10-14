#!/usr/bin/env bash
set -euo pipefail
TC=${TC:-/opt/jieli}; SRC=${SRC:-/src}; OUT=${OUT:-/out}
SPIKE="$SRC/tests/native/fixed_entry_verifier_spike"
CC="$TC/common/bin/clang"; LD="$TC/pi32v2/bin/ld"; OC="$TC/pi32v2/bin/objcopy"; OD="$TC/pi32v2/bin/objdump"
FLAGS=(-target pi32v2 -mcpu=r3 -mfprev1 -Oz -ffreestanding -fno-builtin -fno-common -fno-unwind-tables -ffunction-sections -fdata-sections -mllvm -pi32v2-large-program=true -Wall -Wextra -Werror)
mkdir -p "$OUT"
for variant in a b; do
 d="$OUT/$variant"; mkdir -p "$d"; def=(); [[ "$variant" == b ]] && def=(-DSPIKE_VARIANT_B)
 "$CC" "${FLAGS[@]}" -c "$SPIKE/startup.S" -o "$d/startup.o"
 "$CC" "${FLAGS[@]}" -c "$SPIKE/verifier.c" -o "$d/verifier.o"
 "$CC" "${FLAGS[@]}" "${def[@]}" -c "$SPIKE/payload.c" -o "$d/payload.o"
 "$CC" "${FLAGS[@]}" -c "$SPIKE/manifest.c" -o "$d/manifest.o"
 "$LD" -T "$SPIKE/app.ld" -Map="$d/app.map" -o "$d/app.elf" "$d/startup.o" "$d/verifier.o" "$d/payload.o" "$d/manifest.o"
 "$OC" -O binary -j .immutable_entry "$d/app.elf" "$d/immutable.bin"
 "$OC" -O binary -j .mutable "$d/app.elf" "$d/mutable.bin"
 python3 - "$d" <<'PY_PAD'
import pathlib,sys
p=pathlib.Path(sys.argv[1]); imm=(p/"immutable.bin").read_bytes(); mut=(p/"mutable.bin").read_bytes(); fixed=0xEE0
if len(imm)>fixed: raise SystemExit("immutable entry overflows first sector")
(p/"app.bin").write_bytes(imm+b"\xff"*(fixed-len(imm))+mut)
PY_PAD
 "$OD" -d -mcpu=r3 -mattr=+fprev1 "$d/app.elf" > "$d/app.disasm.txt"
 python3 - "$d" <<'PY'
import hashlib,pathlib,re,struct,sys
p=pathlib.Path(sys.argv[1]); m=(p/'app.map').read_text(); b=bytearray((p/'app.bin').read_bytes())
manifest=re.search(r"0x([0-9a-fA-F]+)\s+__mutable_manifest",m); end=re.search(r"0x([0-9a-fA-F]+)\s+__mutable_end",m)
if not manifest or not end: raise SystemExit('mutable linker symbols not found')
addr=int(manifest.group(1),16); endaddr=int(end.group(1),16); off=addr-0x02000120; endoff=endaddr-0x02000120; fixed=0x02001000-0x02000120
if endoff>len(b) or off+12!=endoff or fixed!=0xEE0: raise SystemExit('unexpected app binary geometry')
b=b[:endoff]; body=bytes(b[fixed:off]); crc=0
for x in body:
 crc^=x<<8
 for _ in range(8): crc=((crc<<1)^0x1021)&0xffff if crc&0x8000 else (crc<<1)&0xffff
b[off:off+12]=struct.pack('<IIHH',0x31525646,len(body),crc,1)
check=0
for x in b[fixed:off]:
 check^=x<<8
 for _ in range(8): check=((check<<1)^0x1021)&0xffff if check&0x8000 else (check<<1)&0xffff
if check!=crc: raise SystemExit('manifest integrity self-check failed')
(p/'app.bin').write_bytes(b)
(p/'artifact.json').write_text(__import__('json').dumps({'bytes':len(b),'immutable_bytes':fixed,'mutable_bytes':len(b)-fixed,'manifest_offset':off,'body_bytes':len(body),'body_crc16':crc,'app_sha256':hashlib.sha256(b).hexdigest(),'elf_sha256':hashlib.sha256((p/'app.elf').read_bytes()).hexdigest(),'map_sha256':hashlib.sha256((p/'app.map').read_bytes()).hexdigest(),'disassembly_sha256':hashlib.sha256((p/'app.disasm.txt').read_bytes()).hexdigest()},indent=2)+'\n')
PY
done
python3 - "$OUT" <<'PY'
import hashlib,json,pathlib,sys
p=pathlib.Path(sys.argv[1]); a=(p/'a/app.bin').read_bytes(); b=(p/'b/app.bin').read_bytes(); n=0xEE0
header=b'SPIKE-ONLY-NOT-A-VALID-FM1-HEADER'.ljust(0x120,b'\xff')
sector_a=header+a[:n]; sector_b=header+b[:n]
if sector_a!=sector_b: raise SystemExit('synthetic first-sector bytes differ')
if a[:n]!=b[:n]: raise SystemExit('immutable application prefix differs')
if a[n:]==b[n:]: raise SystemExit('mutable bodies unexpectedly identical')
if len(a)!=len(b): raise SystemExit('fixture lengths differ')
for name,data,sector in [('a',a,sector_a),('b',b,sector_b)]:
 (p/name/'synthetic_first_sector.bin').write_bytes(sector)
 (p/name/'immutable_prefix.sha256').write_text(hashlib.sha256(data[:n]).hexdigest()+'\n')
summary={'synthetic_header_valid':False,'synthetic_first_sector_bytes':len(sector_a),'synthetic_first_sector_sha256':hashlib.sha256(sector_a).hexdigest(),'application_immutable_prefix_bytes':n,'application_immutable_prefix_sha256':hashlib.sha256(a[:n]).hexdigest(),'a_mutable_sha256':hashlib.sha256(a[n:]).hexdigest(),'b_mutable_sha256':hashlib.sha256(b[n:]).hexdigest(),'same_first_sector':True,'different_mutable':True,'target_execution':False}
(p/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
PY
