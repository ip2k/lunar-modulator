#!/usr/bin/env python3
"""Collect runtime-mode link failures without changing or rebuilding source."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path('/home/claude/mvave-fm1/all13-fullsong-link-comparison-v1')
OUT = ROOT / 'runtime-followup-v2'
BASELINE = ROOT / 'receipts/comparison-receipt.json'
VARIANTS = (('diagnostic-watermark', 'z', None, True),
            ('diagnostic-no-watermark', None, 'diagnostic', False),
            ('continuous-watermark', None, 'continuous', True),
            ('continuous-no-watermark', None, 'continuous', False))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def section(text, name):
    match = re.search(r'^\.' + re.escape(name) + r'\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)(?:\s+load address (0x[0-9a-f]+))?$', text, re.M)
    return None if not match else dict(address=int(match.group(1), 16),
                                       bytes=int(match.group(2), 16),
                                       load_address=None if not match.group(3) else int(match.group(3), 16))


def main():
    old = json.loads(BASELINE.read_text())
    oldz = old['variants']['z']
    xip_origin = 0x02000120
    variants = {}
    label_dirs = {'diagnostic-no-watermark': 'diagnostic-no-watermark',
                  'continuous-watermark': 'continuous-watermark',
                  'continuous-no-watermark': 'continuous-no-watermark'}
    for label, prior_key, runtime, watermark in VARIANTS:
        if prior_key:
            sections = oldz['other_sections']
            text_bytes = oldz['app_text_bytes']
            overflow = 1272
            link_stderr = oldz['link_stderr']
            base_crt0 = ROOT / 'probe-z/build/crt0.S'
            guard_text = base_crt0.read_text()
            app_objects = oldz['extra_app_objects']
            object_count = oldz['object_count']
            object_bytes = oldz['object_bytes']
            variants[label] = dict(runtime='diagnostic', stack_watermark=True,
                                   optimization='-Oz', catalogue_object_count=object_count,
                                   catalogue_object_bytes=object_bytes, text_bytes=text_bytes,
                                   sections=sections, xip_image_bytes=text_bytes + sections['ram_text']['bytes'] + sections['data']['bytes'],
                                   xip_budget_bytes=old['app_budget_bytes'], linker_overflow_bytes=overflow,
                                   link_map_sha256=sha(ROOT / 'probe-z/build/lunar-app-probe.map'),
                                   link_stderr=link_stderr, generated_crt0_sha256=sha(base_crt0),
                                   entry_guard_cnum_check='if (r3 != 0) goto lunar_entry_rejected' in guard_text,
                                   entry_guard_boot_pointer_check='if (r0 != r3) goto lunar_entry_rejected' in guard_text,
                                   stack_painter_present='lunar_stack_watermark_begin' in guard_text,
                                   app_object_count=len(app_objects), app_objects=app_objects)
            continue
        directory = OUT / label_dirs[label] / 'build'
        map_path, log_path, crt0 = (directory / 'lunar-app-probe.map',
                                    directory / 'link.log', directory / 'crt0.S')
        map_text, log_text, crt0_text = map_path.read_text(), log_path.read_text(), crt0.read_text()
        xip = re.search(r'^XIP\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)', map_text, re.M)
        text_s, ram_s, data_s, bss_s = (section(map_text, n) for n in ('text', 'ram_text', 'data', 'bss'))
        if not all((xip, text_s, ram_s, data_s, bss_s)):
            raise SystemExit('Could not parse complete map for ' + label)
        origin, budget = int(xip.group(1), 16), int(xip.group(2), 16)
        loaded_end = data_s['load_address'] + data_s['bytes']
        built_objects = sorted(directory.rglob('*.o'))
        object_manifest = [dict(path=str(p.relative_to(directory)), bytes=p.stat().st_size, sha256=sha(p))
                           for p in built_objects]
        variants[label] = dict(runtime=runtime, stack_watermark=watermark, optimization='-Oz',
                               catalogue_object_count=167,
                               catalogue_object_bytes=oldz['object_bytes'],
                               text_bytes=text_s['bytes'],
                               sections=dict(ram_text=ram_s, data=data_s, bss=bss_s),
                               xip_image_bytes=loaded_end - origin,
                               xip_budget_bytes=budget,
                               linker_overflow_bytes=(loaded_end - origin) - budget,
                               link_map_sha256=sha(map_path), link_log_sha256=sha(log_path),
                               link_stderr=log_text, generated_crt0_sha256=sha(crt0),
                               entry_guard_cnum_check='if (r3 != 0) goto lunar_entry_rejected' in crt0_text,
                               entry_guard_boot_pointer_check='if (r0 != r3) goto lunar_entry_rejected' in crt0_text,
                               stack_painter_present='lunar_stack_watermark_begin' in crt0_text,
                               app_object_count=len(object_manifest), app_objects=object_manifest)
    result = dict(schema='lunar-all13-runtime-mode-link-comparison-v1',
                  source_commit=old['source_commit'],
                  prepared_profile_sha256=old['profile_sha256'],
                  prepared_content=old['profile_content'],
                  catalogue_z_object_manifest_sha256=hashlib.sha256(
                      json.dumps(oldz['objects'], sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                  catalogue_z_object_count=oldz['object_count'],
                  catalogue_z_object_bytes=oldz['object_bytes'],
                  xip_origin=xip_origin, app_budget_bytes=old['app_budget_bytes'],
                  variants=variants,
                  interpretation='XIP load image includes .text plus .ram_text and .data load bytes; .bss is zero-initialized RAM and not counted in the image extent.',
                  semantics_verified=False, installable=False, hardware_tested=False)
    path = ROOT / 'receipts/runtime-mode-comparison-receipt.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(path, sha(path))
    for name, item in variants.items():
        print(name, item['text_bytes'], item['xip_image_bytes'], item['xip_budget_bytes'],
              item['linker_overflow_bytes'], item.get('entry_guard_cnum_check'),
              item.get('entry_guard_boot_pointer_check'), item.get('stack_painter_present'))


if __name__ == '__main__':
    main()
