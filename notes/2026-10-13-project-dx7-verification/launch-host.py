import concurrent.futures,json,pathlib,subprocess
root=pathlib.Path('/home/claude/mvave-fm1/native-external-arenas-16-20261012')
def run(i):
 name='lunar-project-dx7-v3-%02d'%i
 case=i
 cmd=['docker','run','--name',name,'--user','1001:1001','--network','none','--cgroup-parent','docker-batch.slice','--label','lan.project=lunar-modulator','--cpus','1','--memory','2048m','--memory-swap','2048m','-v',str(root/'dx7-source-v3')+':/src:ro,z','-v',str(root/'out')+':/out:rw,z','-v','/home/claude/mvave-fm1/sdk-v1213/toolchain/current:/opt/jieli:ro,z','-e','FM1_STATE_TOOL=/out/host-resources-shared/fm1-state','-e','FM1_NATIVE_TOOLCHAIN=/opt/jieli','-e','FM1_SIM_OPT=-Os','-e','FM1_SIM_CC=cc','-e','FM1_SIM_CXX=c++','-e','FM1_SIM_EXTRA=-fsanitize=address,undefined -fno-omit-frame-pointer','-w','/src','sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d','/out/pytest-venv/bin/python','-m','pytest','-q','-p','no:cacheprovider','tests/test_app_arenas.py::test_project_scalar_startup[%d]'%i]
 cmd.append('tests/test_app_arenas.py::test_project_dx7_startup[%d]'%i)
 if i < 16: cmd.append('tests/test_app_arenas.py::test_app_storage_and_audio[%d]'%i)
 r=subprocess.run(cmd,capture_output=True,text=True)
 (root/'out'/('project-dx7-v3-%02d.log'%i)).write_text(r.stdout+r.stderr)
 state=json.loads(subprocess.check_output(['docker','inspect',name,'--format','{{json .State}}'],text=True))
 subprocess.run(['docker','rm',name],check=True,capture_output=True)
 return dict(shard=i,optimizations=['-Os'],storage_profiles=['embedded','external'],case=case,exit=r.returncode,state_exit=state['ExitCode'],oom=state['OOMKilled'])
with concurrent.futures.ThreadPoolExecutor(30) as pool:results=list(pool.map(run,range(30)))
(root/'out/project-dx7-v3-verification.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results))
assert all(r['exit']==0 and r['state_exit']==0 and not r['oom'] for r in results)
