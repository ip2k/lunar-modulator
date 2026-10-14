import os,hashlib,json,pathlib,shutil,struct,subprocess,sys
sys.path.insert(0,'/src/tools/native')
sys.path.insert(0,'/src/tools/jieli')
from prepare_image_profile import prepare
from verify_image_profile import load_prepared_profile
from audit_link import Elf
os.environ['FM1_STATE_TOOL']='/out/host-resources-shared/fm1-state'
subprocess.run(['/out/pytest-venv/bin/python','-m','pytest','-q','-p','no:cacheprovider','/src/tests/test_audit_link.py','/src/tests/test_native_probe_artifact.py', '/src/tests/test_native_content_embedding.py::test_startup_set_option_refusal', '/src/tests/test_native_content_embedding.py::test_linker_profile_option_refusal'],cwd='/src',check=True)
i=int(sys.argv[1]);count=(0,1,2,4)[i%4];binary=bool((i//4)%2);plate=bool(i//8)
root=pathlib.Path('/out/mod-cold-link-v2-%02d'%i);root.mkdir()
content=[]
for j in range(count):
 fixture=('orbit.set.lunarb' if binary else 'orbit.set.movy1') if j%2 else ('first-orbit.lunarb' if binary else 'first-orbit.lunar')
 name='asset-%02d'%j;shutil.copy(pathlib.Path('/src/tests/fixtures/state/1.0')/fixture,root/name);content.append(name)
profile=root/'input.json';profile.write_text(json.dumps(dict(version=1,engines=['trio','drums','shapes','macro','dx7'],effects=['filter','drive','echo','hall','limit']+(['plate'] if plate else []),midi=['arp'],modulation=['lfo','env','chance'],content=content)))
prepared=root/'prepared';prepare(profile,pathlib.Path('/out/host-resources-shared/fm1-state'),prepared)
expected=hashlib.sha256((prepared/'profile.json').read_bytes()).hexdigest()
inputs=load_prepared_profile(prepared,expected)
subprocess.run(['python3','/src/tools/native/build_application_probe.py','--toolchain','/opt/jieli','--catalogue','/catalogue','--build',str(root/'linked'),'--prepared-profile',str(prepared),'--expected-profile-sha256',expected,'--compressed-wavetables','--indexed-tft','--link-set-loader','--link-project-loader','--shapes-voices','12','--flash-plaits-wavetables', *(['--startup-set-index','1'] if count >= 2 else [])],check=True)
report=json.loads((root/'linked/verification.json').read_text())
assert report['embedded_content']['prepared_sha256']==expected
assert report['embedded_content']['asset_count']==count
assert report['embedded_content']['native_playback_verified'] is False
assert report['module_selection']['selected']==inputs.report['module_selection']['selected']
assert report['set_loader']==dict(native_link_verified=True, activation_api_link_verified=True, activated=False, stack_margin_verified=False, hardware_tested=False, sequence_semantics_verified=False)
if count >= 2:
 assert report['startup_set']==dict(index=1,runtime_hook_linked=True,staging_reclaimed_before_engine_allocation=True,runtime_verified=False,stack_margin_verified=False,hardware_tested=False)
else:
 assert 'startup_set' not in report
elf=Elf((root/'linked/lunar-app-probe.elf').read_bytes())
assert struct.unpack('<I',elf.read(elf.symbol_value('lunar_content_count'),4))[0]==count
assert elf.symbol_value('lunar_content_load_set')
assert elf.symbol_value('lunar_content_activate_set')
assert elf.symbol_value('lunar_project_mod_stage')
assert elf.symbol_value('lunar_project_seq_stage')
assert elf.symbol_value('lunar_project_engines_stage')
assert elf.symbol_value('lunar_project_engines_release')
assert elf.symbol_value('lunar_project_engines_apply')
assert elf.symbol_value('lunar_project_adopt_audio_units')
assert elf.symbol_value('lunar_project_restore_scalars')
assert elf.symbol_value('lunar_project_restore_dx7')
assert elf.symbol_value('fm1_app_mod_prepare_cold')
assert elf.symbol_value('fm1_app_mod_adopt_cold')
assert report['project_loader']==dict(modulation_staging_link_verified=True,sequence_staging_link_verified=True,engine_staging_link_verified=True,engine_parameter_link_verified=True,audio_adoption_link_verified=True,midi_restore_link_verified=True,scalar_restore_link_verified=True,dx7_restore_link_verified=True,modulation_adoption_link_verified=True,activated=False,stack_margin_verified=False,timing_verified=False,hardware_tested=False,sequence_semantics_verified=False)
# LTO may inline the app helper; retain and verify the public activation entry.
address=elf.symbol_value('lunar_content_catalogue')
for j,(asset,payload) in enumerate(zip(inputs.report['content'],inputs.packed_content)):
 pointer,size,kind=struct.unpack('<IIB3x',elf.read(address+12*j,12))
 assert 0x02000120<=pointer<0x0208e0dc
 assert size==len(payload) and kind=={'project':1,'set':7}[asset['kind']]
 assert elf.read(pointer,size)==payload
(root/'linked-content-check.json').write_text(json.dumps(dict(shard=i,assets=count,packed_bytes=sum(map(len,inputs.packed_content)),binary_input=binary,plate=plate,linked_bytes_verified=True,installable=False,hardware_tested=False,playback_verified=False))+'\n')
