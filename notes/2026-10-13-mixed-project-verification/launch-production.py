import json,pathlib,subprocess
root=pathlib.Path('/home/claude/mvave-fm1/native-external-arenas-16-20261012')
name='lunar-mixed-project-production-v3'
cmd=['docker','run','--name',name,'--user','1001:1001','--network','none','--cgroup-parent','docker-batch.slice','--label','lan.project=lunar-modulator','--cpus','2','--memory','4096m','--memory-swap','4096m','-v',str(root/'mixed-project-production-source-v3')+':/src:ro,z','-v',str(root/'out')+':/out:rw,z','-v','/home/claude/mvave-fm1/native-catalogue-16-20261012/out-mod-cold-v1:/catalogue:ro,z','-v','/home/claude/mvave-fm1/sdk-v1213/toolchain/current:/opt/jieli:ro,z','-w','/src','sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d','python3','/src/notes/2026-10-13-mixed-project-verification/production-driver.py']
r=subprocess.run(cmd,capture_output=True,text=True)
(root/'out/mixed-project-production-v3.log').write_text(r.stdout+r.stderr)
state=json.loads(subprocess.check_output(['docker','inspect',name,'--format','{{json .State}}'],text=True))
report=dict(command=cmd,exit=r.returncode,state_exit=state['ExitCode'],oom=state['OOMKilled'])
(root/'out/mixed-project-production-v3-verification.json').write_text(json.dumps(report,indent=2)+'\n')
subprocess.run(['docker','rm',name],check=True,capture_output=True)
print(json.dumps(report));print(r.stdout[-1000:]);print(r.stderr[-3000:])
assert r.returncode==0 and state['ExitCode']==0 and not state['OOMKilled']
