import concurrent.futures,hashlib,json,pathlib,subprocess
root=pathlib.Path('/home/claude/mvave-fm1/native-external-arenas-16-20261012')
out=root/'out/seq-collector-v2'
out.mkdir(exist_ok=False)
image='sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d'
base=['docker','run','--user','1001:1001','--network','none','--cgroup-parent','docker-batch.slice','--label','lan.project=lunar-modulator','--cpus','1','--memory','2048m','--memory-swap','2048m','-v',str(root/'seq-collector-source-v1')+':/src:ro,z','-v',str(root/'out')+':/out:rw,z','-v','/home/claude/mvave-fm1/sdk-v1213/toolchain/current:/opt/jieli:ro,z','-e','PYTHONPATH=/out/seq-collector-deps-311','-e','FM1_NATIVE_TOOLCHAIN=/opt/jieli','-w','/src']
py=['/out/pytest-venv/bin/python','-m','pytest','-o','addopts=','-q','-s','-p','no:cacheprovider']
col=subprocess.run(base+['--rm',image]+py+['--collect-only','tests/test_native_seq_export_stream.py','tests/test_app_state.py'],capture_output=True,text=True,check=True)
(out/'collection.txt').write_text(col.stdout+col.stderr)
nodes=[line.strip() for line in col.stdout.splitlines() if line.startswith('tests/') and '::' in line]
assert len(nodes)>=73, nodes
(out/'source-hashes.json').write_text(json.dumps({p:hashlib.sha256((root/'seq-collector-source-v1'/p).read_bytes()).hexdigest() for p in ['engines/include/fm1_seq.h','engines/state/state_seq_export.h','engines/state/fm1_state.h','engines/seq/seq_persist.c','sim/web/src/fm1_app_state.c','engines/state/fm1_json.h','engines/state/state_bin.c','engines/state/state_names.c','engines/state/state_movy1.c','engines/state/fm1_num.c','engines/state/fm1_deflate.c','tests/native/seq_record_target.c','tests/native/seq_export_stream.c','tests/test_native_seq_export_stream.py']},indent=2))
def run(i):
 name='lunar-seq-collector-v2-%02d'%i
 chosen=nodes[i::30]
 r=subprocess.run(base+['--name',name,image,'sh','-c','cp -a /src /tmp/collector-src && cd /tmp/collector-src && exec "$@"','collector-tests']+py+chosen,capture_output=True,text=True)
 (out/('%02d.log'%i)).write_text(r.stdout+r.stderr)
 state=json.loads(subprocess.check_output(['docker','inspect',name,'--format','{{json .State}}'],text=True))
 subprocess.run(['docker','rm',name],capture_output=True,check=True)
 return dict(shard=i,nodes=chosen,exit=r.returncode,state_exit=state['ExitCode'],oom=state['OOMKilled'])
with concurrent.futures.ThreadPoolExecutor(30) as pool: results=list(pool.map(run,range(30)))
report=dict(chunks=30,tests=len(nodes),results=results)
(out/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
assert all(r['exit']==0 and r['state_exit']==0 and not r['oom'] for r in results)
