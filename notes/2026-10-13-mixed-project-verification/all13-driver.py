import hashlib,json,pathlib,shutil,struct,subprocess,sys
sys.path[:0]=['/src/tools/native','/src/tools/jieli']
from prepare_image_profile import prepare
from verify_image_profile import load_prepared_profile
from audit_link import Elf
root=pathlib.Path('/out/mixed-project-all13-v2');root.mkdir()
shutil.copy('/src/notes/2026-10-13-mixed-project-verification/all13-profile.json',root/'input.json')
shutil.copy('/src/tests/fixtures/state/1.0/first-orbit.lunar',root/'first-orbit.lunar')
prepared=root/'prepared';prepare(root/'input.json',pathlib.Path('/out/host-resources-shared/fm1-state'),prepared)
expected=hashlib.sha256((prepared/'profile.json').read_bytes()).hexdigest()
inputs=load_prepared_profile(prepared,expected)
subprocess.run(['python3','/src/tools/native/build_application_probe.py','--toolchain','/opt/jieli','--catalogue','/catalogue','--build',str(root/'linked'),'--prepared-profile',str(prepared),'--expected-profile-sha256',expected,'--compressed-wavetables','--indexed-tft','--link-set-loader','--link-project-loader','--shapes-voices','12','--flash-plaits-wavetables','--flash-layout','expanded-d9000','--startup-project-index','0'],check=True)
report=json.loads((root/'linked/verification.json').read_text())
assert report['module_selection']['selected']==inputs.report['module_selection']['selected']
assert report['startup_project']['runtime_hook_linked'] and not report['startup_project']['hardware_tested']
assert not any(x.startswith('test-') for x in report['module_selection']['selected'])
elf=Elf((root/'linked/lunar-app-probe.elf').read_bytes())
address=elf.symbol_value('lunar_content_catalogue')
pointer,size,kind=struct.unpack('<IIB3x',elf.read(address,12))
assert kind==1 and size==len(inputs.packed_content[0])
assert elf.read(pointer,size)==inputs.packed_content[0]
(root/'linked-content-check.json').write_text(json.dumps(dict(production_engines=13,diagnostic_modules=False,packed_bytes=size,linked_bytes_verified=True,hardware_tested=False,installable=False))+'\n')
