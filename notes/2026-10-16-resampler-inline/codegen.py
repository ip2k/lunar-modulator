from pathlib import Path
import subprocess,json,hashlib
root=Path('/home/claude/.local/share/codex-workers/resampler-inline-experiment-20261016')
out=Path('/home/claude/mvave-fm1/resampler-inline-experiment-20261016')
out.mkdir(exist_ok=False)
base='d168869b5aa77385ccbecaaf32dbaa2379d65887'
for variant in ['original','candidate']:
 d=out/variant;d.mkdir()
 h=subprocess.check_output(['git','show',base+':engines/include/fm1_resampler.h'],cwd=root) if variant=='original' else (root/'engines/include/fm1_resampler.h').read_bytes()
 (d/'fm1_resampler.h').write_bytes(h)
 (d/'probe.c').write_text('#include "fm1_resampler.h"\nfloat pop(fm1_resampler_t *r) { return fm1_resampler_pop_ready_(r); }\nunsigned push(fm1_resampler_t*r,const float*x,unsigned n){return fm1_resampler_push_ready_(r,x,n);}\n')
script='''set -eu
for variant in original candidate; do
 for opt in z s; do
  /tc/common/bin/clang -target pi32v2 -mcpu=r3 -mfprev1 -std=c99 -O$opt -ffreestanding -fno-builtin -ffunction-sections -fdata-sections -DFM1_HOT_DSP_RAM=1 -DFM1_RESAMPLER_SHARED_TABLES=1 -isystem /tc/pi32v2/include -c /out/$variant/probe.c -o /out/$variant/probe-O$opt.o
  /tc/common/bin/objdump -h -t -d /out/$variant/probe-O$opt.o > /out/$variant/probe-O$opt.txt
 done
done
'''
(out/'run.sh').write_text(script)
tc='/home/claude/mvave-fm1/current-stage7-hall-o2-20261015/output/snapshots/toolchain'
cmd=['docker','run','--rm','--network=none','--cgroup-parent=docker-batch.slice','--cpus=2','--memory=2g','--memory-swap=2g','--label','lan.project=lunar-modulator','--label','lan.session=resampler-inline-experiment-20261016','--label','lan.task=resampler-codegen','--user','1001:1001','--read-only','--tmpfs','/tmp:rw,nosuid,nodev,size=64m','-v',tc+':/tc:ro','-v',str(out)+':/out:rw','sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc','sh','/out/run.sh']
(out/'command.json').write_text(json.dumps(cmd,indent=2)+'\n')
subprocess.run(cmd,check=True)
for f in sorted(out.glob('*/*')):
 if f.is_file():print(f.relative_to(out),hashlib.sha256(f.read_bytes()).hexdigest())
