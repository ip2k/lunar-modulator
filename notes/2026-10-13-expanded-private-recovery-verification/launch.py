import concurrent.futures,hashlib,json,pathlib,subprocess
root=pathlib.Path('/home/claude/mvave-fm1/native-external-arenas-16-20261012')
out=root/'out/expanded-private-recovery-v1'
out.mkdir(exist_ok=False)
image='sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d'
base=['docker','run','--user','1001:1001','--network','none','--cgroup-parent','docker-batch.slice','--label','lan.project=lunar-modulator','--cpus','1','--memory','2048m','--memory-swap','2048m','-v',str(root/'source')+':/src:ro,z','-v',str(root/'out')+':/out:rw,z','-w','/src','-e','FM1_PRIVATE_EXPANDED_INPUTS=/out/expanded-recovery-inputs-v1']
py=['/out/pytest-venv/bin/python','-m','pytest','-o','addopts=','-q','-p','no:cacheprovider']
col=subprocess.run(base+['--rm',image]+py+['--collect-only','tests/test_expanded_private_recovery.py'],capture_output=True,text=True,check=True)
(out/'collection.txt').write_text(col.stdout+col.stderr)
nodes=[line.strip() for line in col.stdout.splitlines() if line.startswith('tests/') and '::' in line]
assert len(nodes)==32, nodes
(out/'source-hashes.json').write_text(json.dumps({p:hashlib.sha256((root/'source'/p).read_bytes()).hexdigest() for p in ['tools/jieli/audit_link.py','tests/test_audit_link.py','tools/native/flash_layout.py','tools/native/probe_artifact.py','tools/native/build_application_probe.py','tests/test_native_probe_artifact.py','firmware/native/app.ld','tools/jieli/expanded_flash_profile.py','tests/test_expanded_flash_profile.py','tests/test_expanded_flash_recovery.py','tools/native/expanded_candidate.py','tests/test_expanded_native_candidate.py','tests/test_expanded_private_recovery.py','tools/fm1_flash_transaction.py','tools/fm1_simulated_device.py','tools/fm1_recovery_campaign.py']},indent=2))
def run(i):
 name='lunar-expanded-private-recovery-v1-%02d'%i
 chosen=nodes[i::30]
 r=subprocess.run(base+['--name',name,image]+py+chosen,capture_output=True,text=True)
 (out/('%02d.log'%i)).write_text(r.stdout+r.stderr)
 state=json.loads(subprocess.check_output(['docker','inspect',name,'--format','{{json .State}}'],text=True))
 subprocess.run(['docker','rm',name],capture_output=True,check=True)
 return dict(shard=i,nodes=chosen,exit=r.returncode,state_exit=state['ExitCode'],oom=state['OOMKilled'])
with concurrent.futures.ThreadPoolExecutor(30) as pool: results=list(pool.map(run,range(30)))
report=dict(chunks=30,tests=len(nodes),results=results)
(out/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
assert all(r['exit']==0 and r['state_exit']==0 and not r['oom'] for r in results)
