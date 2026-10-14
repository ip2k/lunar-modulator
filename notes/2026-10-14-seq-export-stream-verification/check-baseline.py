"""Independent pre-refactor exporter comparison; run on Hera after staging files."""
import hashlib,json,pathlib,subprocess
root=pathlib.Path('/home/claude/mvave-fm1/native-external-arenas-16-20261012')
src=root/'seq-export-stream-source-v2'
out=root/'out/seq-export-stream-baseline-v2';out.mkdir(exist_ok=False)
base=['docker','run','--rm','--user','1001:1001','--network','none','--cgroup-parent','docker-batch.slice','--label','lan.project=lunar-modulator','--cpus','1','--memory','2048m','-v',str(src)+':/src:ro,z','-v',str(root/'out')+':/out:rw,z','-v','/tmp/lunar-seq-regression.c:/probe.c:ro,z','-v','/tmp/lunar-seq-persist-baseline.c:/baseline.c:ro,z','-w','/src','sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d']
for variant,persist in [('baseline','/baseline.c'),('current','/src/engines/seq/seq_persist.c')]:
 cmd=['cc','-std=c99','-Oz','-Wall','-Wextra','-Werror','-ffunction-sections','-fdata-sections','-I','/src/engines/include','-I','/src/engines/seq','/probe.c',persist]+['/src/engines/seq/'+name+'.c' for name in ['seq_clip','seq_engine','seq_cmd','seq_capture']]+['-Wl,--gc-sections','-lm','-o','/out/'+out.name+'/'+variant]
 r=subprocess.run(base+cmd,capture_output=True,text=True);(out/(variant+'-compile.log')).write_text(r.stdout+r.stderr);r.check_returncode()
files=[src/'tests/fixtures/state/1.0/orbit.set.movy1']+sorted((src/'tests/fixtures/movy').glob('*.out.movy1'))[:14]
rows=[]
for compat in [0,1]:
 for p in files:
  rel='/src/'+str(p.relative_to(src)); outputs=[]
  for v in ['baseline','current']:
   outputs.append(subprocess.check_output(base+['/out/'+out.name+'/'+v,rel,str(compat)]))
  assert outputs[0]==outputs[1],(compat,p)
  rows.append(dict(file=str(p.relative_to(src)),compat=compat,bytes=len(outputs[0]),sha256=hashlib.sha256(outputs[0]).hexdigest()))
r=dict(baseline_commit='b0908137b005ab9bf06cf94a7ff93ae4493e4f38',baseline_source_sha256=hashlib.sha256(pathlib.Path('/tmp/lunar-seq-persist-baseline.c').read_bytes()).hexdigest(),tests=len(rows),all_identical=True,rows=rows)
(out/'baseline-parity.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(dict(tests=len(rows),all_identical=True)))
