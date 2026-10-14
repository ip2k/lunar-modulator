#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Hera: exact UAC functions plus production pause helper, 30 sanitizer shards."""
import concurrent.futures, hashlib, json, pathlib, subprocess, sys
src, out = [pathlib.Path(p).resolve() for p in sys.argv[1:]]
out.mkdir(exist_ok=False)
usb = (src/'firmware/third_party/dinghy/src/usb.c').read_text()
def function(start):
    a=usb.index(start); b=usb.index('{',a); level=1; end=b+1
    while level:
        level += (usb[end]=='{')-(usb[end]=='}'); end+=1
    return usb[a:end]+'\n'
declarations=usb[usb.index('#define UA_N'):usb.index('static uint32_t ep4tx')]
a=usb.index('static struct {',usb.index('static uint32_t ep4tx'))
b=usb.index('} uac;',a)+len('} uac;')
c=usb.index('#define RS_H',b); d=usb.index('} rs;',c)+len('} rs;')
fir=(src/'firmware/third_party/dinghy/src/uac_fir.h').read_text()
fir_defines='\n'.join(l for l in fir.splitlines() if l.startswith('#define'))
header=('/* SPDX-License-Identifier: GPL-3.0-only */\n#define FELUCCA_UAC_48K 1\n'
    '#define HALF_FRAMES 256u\n#define RING_PUBLISH() __asm__ volatile("" ::: "memory")\n'
    + declarations+usb[a:b]+'\n'+fir_defines+'\n'+usb[c:d]+'\n'
    'static struct { unsigned config; } usb;\n'
    +function('static __attribute__((noinline)) void uac_render_start(void)')
    +function('static uint32_t uac_packet(uint32_t *d)'))
(out/'uac_save_functions.h').write_text(header)
image='sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d'
base=['docker','run','--rm','--network','none','--cpus','1','--memory','512m',
    '--cgroup-parent','docker-batch.slice','--label','lan.project=lunar-modulator',
    '--user','1001:1001','-v',f'{src}:/src:ro,z','-v',f'{out}:/out:rw,z']
def run(name,args):
    r=subprocess.run(base+[image]+args,capture_output=True,text=True)
    (out/(name+'.log')).write_text(r.stdout+r.stderr)
    return dict(name=name,exit=r.returncode)
runs=[run('compile',['gcc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror',
    '-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-pie','-no-pie',
    '-I/out','-I/src/firmware/native','/src/tests/native/save_quiesce_test.c',
    '-o','/out/test'])]
if runs[0]['exit']==0:
    with concurrent.futures.ThreadPoolExecutor(30) as pool:
        runs+=list(pool.map(lambda i:run(f'shard-{i:02}',['/out/test',str(i)]),range(30)))
files=['firmware/native/save_quiesce.h','firmware/native/audio_pause.h',
    'firmware/native/audio_queue.h','tests/native/save_quiesce_test.c',
    'tests/native/verify_save_quiesce.py','firmware/third_party/dinghy/src/usb.c',
    'firmware/third_party/dinghy/src/uac_fir.h']
receipt=dict(schema='lunar-save-quiesce-v1',image=image,hardware_tested=False,
    runs=runs,source_hashes={p:hashlib.sha256((src/p).read_bytes()).hexdigest() for p in files},
    generated_header_sha256=hashlib.sha256(header.encode()).hexdigest(),
    success=len(runs)==31 and all(not r['exit'] for r in runs))
(out/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(dict(success=receipt['success'],runs=len(runs))))
sys.exit(0 if receipt['success'] else 1)
