import json,pathlib,subprocess,sys
shard=int(sys.argv[1]); out=pathlib.Path('/out/project-scalars-target-v1-%02d'%shard);out.mkdir(exist_ok=True)
cc='/opt/jieli/common/bin/clang'
flags=['-target','pi32v2','-mcpu=r3','-mfprev1','-ffreestanding','-fno-builtin','-ffunction-sections','-fdata-sections','-DFM1_APP_EXTERNAL_ARENAS=1','-I/catalogue/shard-00/obj/gen','-I/src/firmware/native','-I/src/engines/include','-I/src/engines/mod','-I/src/engines/host','-I/src/engines/state','-I/src/sim/web/src','-isystem','/opt/jieli/pi32v2/include']
for opt in ('-Os','-Oz'):
 for source,symbol in (('/src/sim/web/src/fm1_app.c','fm1_app_adopt_start_units'),('/src/firmware/native/project_start.c','lunar_project_adopt_audio_units')):
  obj=out/(pathlib.Path(source).stem+opt[1:]+'.o')
  subprocess.run([cc,*flags,opt,'-std=c99','-c',source,'-o',str(obj)],check=True)
  result=subprocess.check_output(['/opt/jieli/pi32v2/bin/nm',str(obj)],text=True)
  assert ' T '+symbol in result
  if source.endswith('project_start.c'): assert ' T lunar_project_restore_scalars' in result
(out/'receipt.json').write_text(json.dumps({'shard':shard,'target':'pi32v2','profiles':['-Os','-Oz'],'adoption_symbol_present':True,'linked':False})+'\n')
print('target compilation passed',shard)
