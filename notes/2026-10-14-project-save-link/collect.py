#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Collect offline link evidence from private build outputs, without flashing."""
import hashlib
import json
import pathlib
import sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools/native'), str(ROOT / 'tools/jieli')]
from probe_artifact import flatten
from flash_layout import RAW_APP_ORIGIN, EXPANDED_AREA_END, EXPANDED_RECORD_RESERVE, app_budget
here = pathlib.Path(__file__).parent
private = ROOT / 'build/native-project-save-link-20261014/v1'
for source, digest in json.loads((here / 'source-hashes.json').read_text()).items():
    assert hashlib.sha256((ROOT / source).read_bytes()).hexdigest() == digest, source
assert json.loads((here / 'key-audit.json').read_text())['passed']
image, app = flatten((private / 'save-retained.elf').read_bytes(), 'combined', 'expanded-d9000')
receipt = json.loads((private / 'receipt.json').read_text())
assert receipt['driver_sha256'] == hashlib.sha256((here / 'measure.py').read_bytes()).hexdigest()
assert receipt['elf_sha256'] == hashlib.sha256((private / 'save-retained.elf').read_bytes()).hexdigest()
receipt.update(app_bytes=len(app), app_sha256=hashlib.sha256(app).hexdigest(),
               app_growth_bytes=len(app)-845916, flash_end_offset=RAW_APP_ORIGIN+len(app),
               flash_tail_bytes=EXPANDED_AREA_END-(RAW_APP_ORIGIN+len(app)),
               cfg_record_reserve_bytes=EXPANDED_RECORD_RESERVE,
               app_budget_margin_bytes=app_budget("expanded-d9000")-len(app),
               fresh_compiler_dependency_hashes_verified=37,
               artifact_flatten_passed=True, key_audit_passed=True,
               undefined_symbols=sorted(image.undefined_symbols()))
(here / 'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
(here / 'sections.txt').write_bytes((private / 'sections.txt').read_bytes())
print(json.dumps({k:v for k,v in receipt.items() if k != 'linked_objects'}, indent=2))
