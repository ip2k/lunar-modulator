import concurrent.futures,json,pathlib,subprocess
root=pathlib.Path('/home/claude/mvave-fm1/native-external-arenas-16-20261012')
def run(i):
 name='lunar-project-scalars-link-v1-%02d'%i
 cmd=['docker','run','--name',name,'--user','1001:1001','--network','none','--cgroup-parent','docker-batch.slice','--label','lan.project=lunar-modulator','--cpus','1','--memory','2048m','--memory-swap','2048m','-v',str(root/'scalar-source-link-v1')+':/src:ro,z','-v',str(root/'out')+':/out:rw,z','-v','/home/claude/mvave-fm1/native-catalogue-16-20261012/out-indexed-shapes12-adoption-v1:/catalogue:ro,z','-v','/home/claude/mvave-fm1/sdk-v1213/toolchain/current:/opt/jieli:ro,z','sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d','python3','/out/project-scalars-link-v1-driver.py',str(i)]
 r=subprocess.run(cmd,capture_output=True,text=True)
 (root/'out'/('project-scalars-link-v1-%02d.log'%i)).write_text(r.stdout+r.stderr)
 state=json.loads(subprocess.check_output(['docker','inspect',name,'--format','{{json .State}}'],text=True))
 subprocess.run(['docker','rm',name],check=True,capture_output=True)
 check=root/'out'/('project-scalars-link-v1-%02d'%i)/'linked-content-check.json'
 return dict(shard=i,exit=r.returncode,state_exit=state['ExitCode'],oom=state['OOMKilled'],check=json.loads(check.read_text()) if check.exists() else None)
with concurrent.futures.ThreadPoolExecutor(30) as pool:results=list(pool.map(run,range(30)))
(root/'out/project-scalars-link-v1-verification.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results))
assert all(r['exit']==0 and r['state_exit']==0 and not r['oom'] and r['check'] for r in results)
