import concurrent.futures,json,pathlib,subprocess
root=pathlib.Path('/home/claude/mvave-fm1/native-catalogue-16-20261012')
(root/'out-mod-cold-v1').mkdir(exist_ok=False)
image='sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d'
def run(i):
 name='lunar-native-mod-cold-v1-%02d'%i
 cmd=['docker','run','--name',name,'--user','1001:1001','--network','none','--cgroup-parent','docker-batch.slice','--label','lan.project=lunar-modulator','--cpus','1','--memory','1024m','--memory-swap','1024m','-v','/home/claude/mvave-fm1/native-external-arenas-16-20261012/mod-cold-source-link-v1'+':/src:ro,z','-v',str(root/'out-mod-cold-v1')+':/out:z','-v','/home/claude/mvave-fm1/sdk-v1213/toolchain/current:/opt/jieli:ro,z','-v','/home/claude/mvave-fm1/sdk-v1213/source-sdk/include_lib/c++/include:/cxx:ro,z','-w','/src',image,'python3','tools/native/compile_catalogue.py','--toolchain','/opt/jieli','--cxx-headers','/cxx','--out','/out/shard-%02d'%i,'--shard',str(i),'--opt','z','--shared-resampler','--lto','--indexed-tft','--shapes-voices','12']
 r=subprocess.run(cmd,capture_output=True,text=True)
 (root/'out-mod-cold-v1'/('shard-%02d.log'%i)).write_text(r.stdout+r.stderr)
 state=json.loads(subprocess.check_output(['docker','inspect',name,'--format','{{json .State}}'],text=True))
 subprocess.run(['docker','rm',name],check=True,capture_output=True)
 return dict(shard=i,exit=r.returncode,state_exit=state['ExitCode'],oom=state['OOMKilled'])
with concurrent.futures.ThreadPoolExecutor(16) as pool:results=list(pool.map(run,range(16)))
(root/'out-mod-cold-v1/verification.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results))
assert all(r['exit']==0 and r['state_exit']==0 and not r['oom'] for r in results)
