#!/usr/bin/env python3
"""Collect text-only reproducibility receipts from the private Hera builds."""
import hashlib
import json
import pathlib
import re

root = pathlib.Path('/research')
src = pathlib.Path('/src')
profile = pathlib.Path('/prepared')
out = pathlib.Path('/out')
out.mkdir(exist_ok=True)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
tool_paths = ['/opt/jieli/common/bin/clang', '/opt/jieli/pi32v2/bin/ld',
              '/opt/jieli/common/bin/LLVMgold.so', '/opt/jieli/common/bin/objdump',
              '/opt/jieli/pi32v2/bin/nm']
tools = {p: sha(pathlib.Path(p)) for p in tool_paths}
manifest = None
catalogues = {}
probes = {}
for variant in 'zs':
    cat = root / ('catalogue-' + variant)
    all_objects = []
    for index in range(16):
        directory = cat / ('shard-%02d' % index)
        report = json.loads((directory / 'report.json').read_text())
        if manifest is None:
            manifest = report['source_manifest']
        elif manifest != report['source_manifest']:
            raise SystemExit('source manifests differ across shards/variants')
        if report['optimization'] != '-O' + variant or not report['lto'] or not report['shared_resampler']:
            raise SystemExit('catalogue configuration mismatch: ' + str(directory))
        for item in report['results']:
            p = directory / 'obj' / item['object']
            if item['exit'] or sha(p) != item['sha256']:
                raise SystemExit('catalogue object check failed: ' + str(p))
            all_objects.append(dict(shard=index, path=item['object'], sha256=item['sha256'], bytes=p.stat().st_size))
    probes[variant] = json.loads((root / ('probe-' + variant) / 'launcher-result.json').read_text())
    build = root / ('probe-' + variant) / 'build'
    link_map = (build / 'lunar-app-probe.map').read_text()
    line = re.search(r'^\.text\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)$', link_map, re.M)
    if not line:
        raise SystemExit('text map range missing: ' + variant)
    other = {}
    for section in ('ram_text', 'data', 'bss'):
        match = re.search(r'^\.' + section + r'\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)', link_map, re.M)
        other[section] = {'address': int(match.group(1), 16), 'bytes': int(match.group(2), 16)} if match else None
    pool = re.search(r'^\s*(0x[0-9a-f]+)\s+_pool_end\s*=', link_map, re.M)
    guard = re.search(r'^\s*(0x[0-9a-f]+)\s+_guard0\s*=', link_map, re.M)
    extra = []
    for p in sorted(build.rglob('*.o')):
        extra.append(dict(path=str(p.relative_to(build)), bytes=p.stat().st_size, sha256=sha(p)))
    catalogues[variant] = dict(optimization='-O' + variant, shard_count=16, object_count=len(all_objects),
                               object_bytes=sum(x['bytes'] for x in all_objects), objects=all_objects,
                               app_text_address=int(line.group(1), 16), app_text_bytes=int(line.group(2), 16),
                               other_sections=other,
                               pool_end=int(pool.group(1), 16) if pool else None,
                               guard0=int(guard.group(1), 16) if guard else None,
                               arena_headroom=(int(guard.group(1), 16)-int(pool.group(1), 16)
                                               if guard and pool else None),
                               extra_app_objects=extra,
                               link_exit=probes[variant]['exit'],
                               link_stderr=probes[variant]['output'])
receipt = dict(schema='lunar-all13-fullsong-link-comparison-v1',
               source_commit='e435edadad48641e9e08c0023b71b80b5692cd44',
               toolchain_files=tools,
               driver_hashes={p.name: sha(p) for p in pathlib.Path('/evidence').glob('*.py')},
               profile_sha256=sha(profile/'profile.json'),
               profile_selected=json.loads((profile/'profile.json').read_text())['module_selection']['selected'],
               profile_content=[dict(path=x.name, bytes=x.stat().st_size, sha256=sha(x)) for x in sorted(profile.glob('content-*.bin'))],
               source_manifest=manifest, variants=catalogues,
               container_results={k:{x:y for x,y in v.items() if x!='output'} for k,v in probes.items()},
               flash_layout='expanded-d9000', app_budget_bytes=868836,
               semantics_verified=False, installable=False, hardware_tested=False)
(out/'comparison-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
for variant, data in catalogues.items():
    print(variant, 'text_bytes', data['app_text_bytes'], 'overflow', data['link_stderr'].strip(),
          'catalogue_objects', data['object_count'], 'pool_headroom', data['arena_headroom'])
print('receipt', out/'comparison-receipt.json')
