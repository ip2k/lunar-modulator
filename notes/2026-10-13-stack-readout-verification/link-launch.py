import hashlib,json,pathlib,subprocess
cmd = ['docker', 'run', '--name', 'lunar-all13-stack-readout-v1', '--user', '1001:1001', '--network', 'none', '--cgroup-parent', 'docker-batch.slice', '--label', 'lan.project=lunar-modulator', '--cpus', '2', '--memory', '4096m', '--memory-swap', '4096m', '-v', '/home/claude/mvave-fm1/native-external-arenas-16-20261012/stack-readout-source-v1:/src:ro,z', '-v', '/home/claude/mvave-fm1/native-external-arenas-16-20261012/out:/out:rw,z', '-w', '/src', '-v', '/home/claude/mvave-fm1/native-catalogue-16-20261012/out-mod-cold-v1:/catalogue:ro,z', '-v', '/home/claude/mvave-fm1/sdk-v1213/toolchain/current:/opt/jieli:ro,z', 'sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d', 'python3', '/src/notes/2026-10-13-stack-readout-verification/build-driver.py']
out=pathlib.Path('/home/claude/mvave-fm1/native-external-arenas-16-20261012/out/stack-readout-link-v1')
out.mkdir(exist_ok=False)
r=subprocess.run(cmd,capture_output=True,text=True)
log=r.stdout+r.stderr
(out/'build.log').write_text(log)
state=json.loads(subprocess.check_output(['docker','inspect','lunar-all13-stack-readout-v1','--format','{{json .State}}'],text=True))
receipt=dict(command=cmd,exit=r.returncode,state_exit=state['ExitCode'],oom=state['OOMKilled'],log_sha256=hashlib.sha256(log.encode()).hexdigest())
(out/'container.json').write_text(json.dumps(receipt,indent=2)+'\n')
subprocess.run(['docker','rm','lunar-all13-stack-readout-v1'],check=True,capture_output=True)
print(json.dumps(receipt))
raise SystemExit(r.returncode)
