import json, pathlib, subprocess, time
p=pathlib.Path('/home/REDACTED/.local/share/codex-builds/lunar/cynthion-pico-repeat-20261018')
subprocess.run(['tar','-xf',str(p/'source.tar'),'-C',str(p/'source')],check=True)
a=['docker', 'create', '--name', 'lunar-pico-repeat-20261018', '--label', 'lan.project=lunar-modulator', '--label', 'lan.session=pico-repeat-20261018', '--cpus', '4', '--memory', '8g', '--memory-swap', '8g', '--pids-limit', '512', '--cgroup-parent', 'docker-batch.slice', '--network', 'none', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--user', '1003:1003', '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=256m', '--env', 'SOURCE_COMMIT=fef11263c88f4b79193ceff9b590094110124491', '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'PYTHONUNBUFFERED=1', '--env', 'PATH=/opt/oss-cad-suite/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin', '--mount', 'type=bind,src=/home/REDACTED/.local/share/codex-builds/lunar/cynthion-pico-repeat-20261018/source,dst=/workspace,readonly', '--mount', 'type=bind,src=/home/REDACTED/.local/share/codex-builds/lunar/cynthion-power-monitor-20261016/venv,dst=/venv,readonly', '--mount', 'type=bind,src=/home/REDACTED/.local/share/codex-builds/lunar/cynthion-power-monitor-20261016/toolchain/oss-cad-suite,dst=/opt/oss-cad-suite,readonly', '--mount', 'type=bind,src=/home/REDACTED/.local/share/codex-builds/lunar/cynthion-pico-repeat-20261018,dst=/run-root,readonly', '--mount', 'type=bind,src=/home/REDACTED/.local/share/codex-builds/lunar/cynthion-pico-repeat-20261018/output,dst=/output', '--entrypoint', '/venv/bin/python', 'sha256:d065eaf170070135564c88bd4273f30784278b35c9355d36a0a96bd6ba20cc8c', '/run-root/root-build.py']
(p/'argv.json').write_text(json.dumps(a,indent=2)+'\n')
cid=subprocess.check_output(a,text=True).strip()
(p/'container-id.txt').write_text(cid+'\n')
(p/'created.inspect.json').write_bytes(subprocess.check_output(['docker','inspect',cid]))
with (p/'stdout.log').open('wb') as so, (p/'stderr.log').open('wb') as se:
 result=subprocess.run(['docker','start','-a',cid],stdout=so,stderr=se)
(p/'terminal.inspect.json').write_bytes(subprocess.check_output(['docker','inspect',cid]))
(p/'exit.json').write_text(json.dumps({'exit':result.returncode})+'\n')
print(json.dumps({'container':cid,'exit':result.returncode,'root':str(p)}),flush=True)
raise SystemExit(result.returncode)
