import json,pathlib,subprocess
root=pathlib.Path('/out/mixed-project-production-v5');root.mkdir()
source=pathlib.Path('/src');native=source/'firmware/native'
build=root/'build32';binary=build/'production-startup'
sources=[native/(n+'.c') for n in ['project_boot','project_seq','project_engines','project_start','project_mod','project_units','instance_pool']]+[source/'firmware/third_party/tlsf/tlsf.c',source/'notes/2026-10-13-mixed-project-verification/production-startup.c']
objects=[build/(s.stem+'.o') for s in sources]
fragment=root/'host.mk'
fragment.write_text(f'{binary}: $(SIM_APP_OBJ) $(SIM_ENGINE_OBJ) $(SIM_META_OBJ) '+ ' '.join(map(str,objects))+'\n\t$(CXX) $(OPT) $(EXTRA) -o $@ $^ -lm\n'+''.join(f'{o}: {s}\n\t@mkdir -p $(dir $@)\n\t$(CC) $(SIM_CFLAGS) -Istate -I{native} -I{source / "firmware/third_party/tlsf"} -c $< -o $@\n' for o,s in zip(objects,sources)))
profile=json.loads((source/'notes/2026-10-13-mixed-project-verification/all13-profile.json').read_text())
modules=','.join(item for key in ['engines','effects','midi','modulation'] for item in profile[key])
subprocess.run(['make','-C',str(source/'engines'),'-f','Makefile','-f',str(source/'sim/web/mk/sim.mk'),'-f',str(fragment),f'SIM={source / "sim/web"}',f'BUILD={build}','FM1_GPL_MODS=1',f'FM1_MODULES={modules}','CC=cc','CXX=c++','OPT=-Os -m32',f'EXTRA=-fsanitize=address,undefined -fno-omit-frame-pointer -DFM1_APP_EXTERNAL_ARENAS=1 -DFM1_TFT_INDEXED=1 -DFM1_SHAPES_VOICES=12 -I{native} -I{source / "engines/state"}','-j4',str(binary)],check=True,stdout=subprocess.DEVNULL)
# The prepared file used by the audited all13-v3 link, not a re-encoded fixture.
prepared=pathlib.Path('/out/mixed-project-all13-v3/prepared')
files=list(prepared.glob('content-*.bin'))
print('prepared packed candidates',list(map(str,files)))
assert len(files)==1
result=subprocess.run([str(binary),str(files[0])],capture_output=True,text=True)
(root/'runtime.log').write_text(result.stdout+result.stderr)
print(result.stdout);print(result.stderr);assert result.returncode==0
(root/'runtime.json').write_text(json.dumps(json.loads(result.stdout),indent=2)+'\n')
